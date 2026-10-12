"""Offline-first document extraction, OCR, segmented translation, and exports.

PDF layout cannot reliably be round-tripped. Export reconstructs *logical* paragraphs,
headings and Word tables; it never claims pixel-perfect reproduction of the source.
OCR is never trusted silently: each OCR-derived block is annotated with its page.
"""
from __future__ import annotations

import csv
import html
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable, Protocol

from psylex.core.config import Settings
from psylex.core.ocr import run_ocr

INPUT_FORMATS = {'.txt', '.md', '.markdown', '.csv', '.tsv', '.json', '.jsonl',
                 '.html', '.htm', '.docx', '.pdf', '.png', '.jpg', '.jpeg', '.tif',
                 '.tiff', '.bmp', '.webp', '.rtf', '.odt', '.epub'}
OUTPUT_FORMATS = {'.txt', '.md', '.csv', '.tsv', '.json', '.jsonl', '.html', '.docx', '.pdf'}
MAX_FILE_SIZE = 80 * 1024 * 1024
MAX_PAGES = 400
MAX_BLOCKS = 20000
MAX_INPUT_CHARS = 2_000_000
MAX_TRANSLATION_CHARS = 1200


@dataclass
class TextBlock:
    text: str
    kind: str = 'paragraph'
    page: int | None = None
    table: int | None = None
    row: int | None = None
    col: int | None = None
    ocr: bool = False
    translated: str = ''
    warnings: list[str] = field(default_factory=list)


@dataclass
class DocumentData:
    source: str
    format: str
    blocks: list[TextBlock]
    warnings: list[str] = field(default_factory=list)

    def require_valid(self) -> None:
        if not self.blocks:
            raise ValueError('No readable text was detected in the selected document.')
        if len(self.blocks) > MAX_BLOCKS:
            raise ValueError(f'Too many text segments (limit {MAX_BLOCKS:,}).')
        if sum(len(b.text) for b in self.blocks) > MAX_INPUT_CHARS:
            raise ValueError(f'Text exceeds the {MAX_INPUT_CHARS:,}-character limit.')


class Translator(Protocol):
    def translate(self, text: str, save: bool = True): ...


def _add(blocks: list[TextBlock], content: str, kind: str = 'paragraph', **meta) -> None:
    content = content.strip()
    if content:
        blocks.append(TextBlock(text=content, kind=kind, **meta))


def _paragraphs(text: str, blocks: list[TextBlock], **meta) -> None:
    for paragraph in re.split(r'\n\s*\n', text.replace('\r\n', '\n')):
        _add(blocks, paragraph, **meta)


def _read_text(path: Path) -> str:
    # A strict parser means a corrupt binary file isn't silently "translated" as junk.
    try:
        return path.read_text(encoding='utf-8-sig')
    except UnicodeDecodeError:
        return path.read_text(encoding='cp1252')


def _rtf_to_text(raw: str) -> str:
    try:
        from striprtf.striprtf import rtf_to_text
    except ImportError as exc:
        raise RuntimeError('RTF requires the optional striprtf dependency (pip install striprtf).') from exc
    return rtf_to_text(raw)


def _html_to_text(raw: str) -> str:
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(raw, 'html.parser')
        for node in soup(['script', 'style', 'noscript']):
            node.decompose()
        return soup.get_text('\n', strip=True)
    except ImportError:
        from html.parser import HTMLParser
        class Parser(HTMLParser):
            def __init__(self):
                super().__init__(); self.words=[]; self.excluded=0
            def handle_starttag(self, tag, attrs):
                if tag in ('script', 'style', 'noscript'): self.excluded += 1
                elif tag in ('p', 'div', 'li', 'h1', 'h2', 'h3', 'br'): self.words.append('\n')
            def handle_endtag(self, tag):
                if tag in ('script', 'style', 'noscript'): self.excluded=max(0,self.excluded-1)
                elif tag in ('p', 'div', 'li', 'h1', 'h2', 'h3'): self.words.append('\n')
            def handle_data(self, data):
                if not self.excluded: self.words.append(data)
        parser=Parser(); parser.feed(raw); return ''.join(parser.words)


def _extract_docx(path: Path, blocks: list[TextBlock]) -> None:
    from docx import Document
    from docx.table import Table
    from docx.text.paragraph import Paragraph
    doc = Document(path)
    table_number = 0
    # OOXML body iteration, not doc.paragraphs, preserves paragraph/table ordering.
    for element in doc.element.body.iterchildren():
        if element.tag.endswith('}p'):
            para = Paragraph(element, doc)
            kind = 'heading' if para.style and para.style.name.lower().startswith(('heading', 'title')) else 'paragraph'
            _add(blocks, para.text, kind)
        elif element.tag.endswith('}tbl'):
            table = Table(element, doc)
            for i, row in enumerate(table.rows):
                for j, cell in enumerate(row.cells):
                    # Content in merged cells can be repeated by python-docx.
                    _add(blocks, cell.text, 'table_cell', table=table_number, row=i, col=j)
            table_number += 1
    # Header/footer, footnotes, drawings, textboxes, tracked changes not imported.


def _extract_odt(path: Path, blocks: list[TextBlock]) -> None:
    try:
        from odf.opendocument import load
        from odf import text as odf_text
        from odf.teletype import extractText
    except ImportError as exc:
        raise RuntimeError('ODT support requires odfpy (pip install odfpy).') from exc
    odoc = load(str(path))
    for el in odoc.text.getElementsByType(odf_text.P):
        _add(blocks, extractText(el))
    for el in odoc.text.getElementsByType(odf_text.H):
        _add(blocks, extractText(el), 'heading')


def _extract_epub(path: Path, blocks: list[TextBlock]) -> None:
    try:
        from ebooklib import epub, ITEM_DOCUMENT
    except ImportError as exc:
        raise RuntimeError('EPUB support requires ebooklib (pip install ebooklib).') from exc
    book = epub.read_epub(str(path))
    for item in book.get_items():
        if item.get_type() == ITEM_DOCUMENT:
            _paragraphs(_html_to_text(item.get_content().decode('utf-8', 'replace')), blocks)


def _ocr_image(image, engine: str, settings: Settings | None = None) -> str:
    return run_ocr(image, engine, settings or Settings())


def _extract_pdf(path: Path, blocks: list[TextBlock], ocr_engine: str,
                 ocr_mode: str, on_progress: Callable[[int, int, str], None] | None,
                 is_cancelled: Callable[[], bool] | None, settings: Settings | None = None) -> list[str]:
    try:
        import pymupdf
    except ImportError:
        import fitz as pymupdf
    from PIL import Image
    warnings = []
    with pymupdf.open(str(path)) as pdf:
        if pdf.needs_pass:
            raise ValueError('Password-protected PDFs must be unlocked before import.')
        if pdf.page_count > MAX_PAGES:
            raise ValueError(f'PDF exceeds the {MAX_PAGES} page limit.')
        for i, page in enumerate(pdf):
            if is_cancelled and is_cancelled():
                raise InterruptedError('Document extraction cancelled.')
            if on_progress: on_progress(i+1, pdf.page_count, f'Reading page {i+1}/{pdf.page_count}')
            text = page.get_text('text', sort=True).strip()
            # OCR when English text layer has insufficient alphabetic content.
            recognized_letters = len(re.findall(r'[A-Za-z]', text))
            should_ocr = ocr_mode == 'always' or (ocr_mode == 'auto' and recognized_letters < 20)
            if should_ocr:
                # Cap huge pages to 25 Mpixels for memory safety.
                scale = min(4.17, (25_000_000 / max(1, page.rect.width * page.rect.height)) ** 0.5)
                pixmap = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False)
                img = Image.frombytes('RGB', [pixmap.width,pixmap.height], pixmap.samples)
                try:
                    ocr_text = _ocr_image(img, ocr_engine, settings)
                except Exception as exc:
                    if text:
                        warnings.append(f'Page {i+1} OCR unavailable ({exc}); using embedded text.')
                        ocr_text = ''
                    else:
                        raise RuntimeError(f'Page {i+1}: {exc}') from exc
                if ocr_text.strip():
                    text = ocr_text
                elif not text:
                    warnings.append(f'Page {i+1}: OCR returned no readable text.')
                _paragraphs(text, blocks, page=i+1, ocr=bool(ocr_text))
            else:
                _paragraphs(text, blocks, page=i+1)
            if not text:
                warnings.append(f'Page {i+1}: no readable text detected.')
    return warnings


def load_document(path: Path, ocr_engine: str = 'rapidocr', ocr_mode: str = 'auto',
                  on_progress: Callable[[int, int, str], None] | None = None,
                  is_cancelled: Callable[[], bool] | None = None,
                  settings: Settings | None = None) -> DocumentData:
    """Load supported source formats without calling a network translation service."""
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix not in INPUT_FORMATS:
        raise ValueError(f'Unsupported input format: {suffix}.')
    if not path.is_file(): raise FileNotFoundError(str(path))
    if path.stat().st_size > MAX_FILE_SIZE:
        raise ValueError('Input exceeds the 80 MB security limit.')
    if ocr_mode not in ('auto', 'always', 'never'): raise ValueError('Invalid OCR mode.')
    if not ocr_engine or not isinstance(ocr_engine, str): raise ValueError('Invalid OCR engine.')
    blocks: list[TextBlock] = []
    warnings = []
    if suffix == '.docx':
        _extract_docx(path, blocks)
        warnings.append('Word output preserves paragraphs, headings and table cells; not exact original formatting.')
    elif suffix == '.pdf':
        warnings.extend(_extract_pdf(path, blocks, ocr_engine, ocr_mode, on_progress, is_cancelled, settings))
        warnings.append('PDF translation rebuilds text; complex graphics/columns/coordinates are not preserved.')
    elif suffix in {'.png','.jpg','.jpeg','.tif','.tiff','.bmp','.webp'}:
        from PIL import Image, ImageSequence
        with Image.open(path) as im:
            for index, frame in enumerate(ImageSequence.Iterator(im)):
                if is_cancelled and is_cancelled(): raise InterruptedError('Image OCR cancelled.')
                if on_progress: on_progress(index+1, getattr(im,'n_frames',1), 'Reading image page')
                text = _ocr_image(frame.copy(), ocr_engine, settings)
                _paragraphs(text, blocks, page=index+1, ocr=True)
        warnings.append('OCR must be proofread before scientific or clinical use.')
    elif suffix in {'.csv','.tsv'}:
        delimiter = '\t' if suffix == '.tsv' else ','
        with path.open(encoding='utf-8-sig', newline='') as handle:
            for i, row in enumerate(csv.reader(handle, delimiter=delimiter)):
                is_header = i == 0 and bool(row) and all(
                    c.strip().lower() in {'english','source','term','meaning','definition','notes','id','persian','translation'}
                    for c in row if c.strip())
                for j, cell in enumerate(row):
                    _add(blocks, cell, 'table_header' if is_header else 'table_cell',
                         table=0, row=i, col=j)
    elif suffix in {'.json', '.jsonl'}:
        data = ([json.loads(x) for x in _read_text(path).splitlines() if x.strip()]
                if suffix == '.jsonl' else json.loads(_read_text(path)))
        # JSON objects are converted to readable values; JSON schema is NOT preserved.
        def flatten(item, prefix=''):
            if isinstance(item, dict):
                for key, value in item.items(): flatten(value, f'{prefix}.{key}' if prefix else key)
            elif isinstance(item, list):
                for i, value in enumerate(item): flatten(value, f'{prefix}[{i}]')
            elif isinstance(item, str):
                _add(blocks, item, 'paragraph')
        flatten(data)
        warnings.append('JSON import translates string values only; export does not retain original keys/schema.')
    elif suffix in {'.html', '.htm'}:
        _paragraphs(_html_to_text(_read_text(path)), blocks)
        warnings.append('HTML scripts, styles and original DOM are intentionally not retained.')
    elif suffix == '.rtf':
        _paragraphs(_rtf_to_text(_read_text(path)), blocks)
    elif suffix == '.odt':
        _extract_odt(path, blocks)
    elif suffix == '.epub':
        _extract_epub(path, blocks)
    else:
        _paragraphs(_read_text(path), blocks)
    if any(b.ocr for b in blocks):
        warnings.append('OCR output may contain misrecognized technical terms or layout errors; review against the source.')
    document = DocumentData(str(path), suffix, blocks, warnings)
    document.require_valid()
    return document


def split_for_translation(text: str, max_chars: int = MAX_TRANSLATION_CHARS) -> list[str]:
    """Split long text at sentence/line/word boundaries, never truncating it."""
    if max_chars < 80: raise ValueError('max_chars must be at least 80')
    if len(text) <= max_chars: return [text]
    fragments = re.split(r'(?<=[.!?])\s+|\n+', text)
    chunks: list[str] = []
    buffer = ''
    for frag in fragments:
        if not frag: continue
        words = re.findall(r'\S+\s*', frag)
        for word in words:
            if len(word) > max_chars:
                if buffer.strip(): chunks.append(buffer.strip()); buffer = ''
                chunks.extend(word[i:i+max_chars] for i in range(0, len(word), max_chars))
            elif len(buffer)+len(word) > max_chars:
                if buffer.strip(): chunks.append(buffer.strip())
                buffer = word
            else:
                buffer += word
        if buffer and not buffer.endswith(' '): buffer += ' '
    if buffer.strip(): chunks.append(buffer.strip())
    return chunks


def translate_document(document: DocumentData, translator: Translator,
                       on_progress: Callable[[int,int,str],None] | None = None,
                       is_cancelled: Callable[[], bool] | None = None) -> DocumentData:
    """Translate all segments, committing results only after full success.

    On cancellation or model failure, prior reviewed translations are preserved.
    A failed job never overwrites earlier user corrections in the in-memory document.
    """
    document.require_valid()
    total = len(document.blocks)
    translated: list[tuple[str, list[str]]] = []
    for index, block in enumerate(document.blocks, 1):
        if is_cancelled and is_cancelled():
            raise InterruptedError('Document translation cancelled; existing review edits were preserved.')
        if block.kind == 'table_header':
            translated.append((block.text, []))
            if on_progress:
                on_progress(index, total, f'Preserved table header {index}/{total}')
            continue
        parts: list[str] = []
        block_warnings: list[str] = []
        for piece in split_for_translation(block.text):
            if is_cancelled and is_cancelled():
                raise InterruptedError('Document translation cancelled; existing review edits were preserved.')
            res = translator.translate(piece, save=False)
            target = res.target.strip()
            if not target:
                raise RuntimeError('The current translation mode cannot translate this text. '
                                   'For full documents configure a local or API LLM in Settings. '
                                   f'Block {index}, excerpt: {piece[:85]}')
            parts.append(target)
            block_warnings.extend(getattr(res, 'warnings', []) or [])
        translated.append(('\n'.join(parts), block_warnings))
        if on_progress:
            on_progress(index, total, f'Translated {index}/{total} sections')
    if is_cancelled and is_cancelled():
        raise InterruptedError('Document translation cancelled; existing review edits were preserved.')
    for block, (target, warnings) in zip(document.blocks, translated):
        block.translated = target
        block.warnings = warnings
    return document


def _export_docx(doc: DocumentData, destination: Path) -> None:
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
    from docx.oxml import OxmlElement
    def right_to_left(paragraph):
        paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        ppr = paragraph._p.get_or_add_pPr()
        bidi = OxmlElement('w:bidi')
        bidi.set('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val', '1')
        ppr.append(bidi)
    result = Document()
    # Keep structure, but a source DOCX cannot have its exact layout reconstructed.
    seen_tables: dict[int, object] = {}
    for b in doc.blocks:
        target=b.translated
        if b.kind in ('table_cell','table_header') and b.table is not None and b.row is not None and b.col is not None:
            table = seen_tables.get(b.table)
            if table is None:
                matching = [x for x in doc.blocks if x.table == b.table and x.kind in ('table_cell','table_header')]
                rows = max(x.row or 0 for x in matching)+1
                cols = max(x.col or 0 for x in matching)+1
                table = result.add_table(rows=rows, cols=cols)
                table.style = 'Table Grid'
                seen_tables[b.table]=table
            cell = table.cell(b.row,b.col)
            cell.text = target
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            for p in cell.paragraphs:
                right_to_left(p)
        else:
            p = result.add_heading(target, level=2) if b.kind == 'heading' else result.add_paragraph(target)
            right_to_left(p)
    result.save(str(destination))


def _export_pdf(doc: DocumentData, destination: Path) -> None:
    """Qt's shaping engine handles Persian bidi when writing native text PDF.

    Requires PySide6 (a core GUI dependency), system Persian-capable fonts.
    """
    from PySide6.QtGui import QTextDocument, QPdfWriter, QPageSize
    from PySide6.QtCore import QMarginsF
    content = '<html><head><meta charset="utf-8"></head><body style="font-family:Tahoma,Arial;">'
    for block in doc.blocks:
        t = html.escape(block.translated).replace('\n','<br/>')
        tag = 'h2' if block.kind=='heading' else 'p'
        content += f'<{tag} dir="rtl" style="text-align:right;">{t}</{tag}>'
    content += '</body></html>'
    writer=QPdfWriter(str(destination))
    writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    writer.setPageMargins(QMarginsF(15,15,15,15))
    writer.setResolution(144)
    qt_doc=QTextDocument()
    qt_doc.setHtml(content)
    qt_doc.print_(writer)


def save_document(doc: DocumentData, path: Path) -> Path:
    """Export user-reviewed translations atomically; never overwrite input file."""
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix not in OUTPUT_FORMATS:
        raise ValueError(f'Unsupported output format: {suffix}')
    if Path(doc.source).resolve() == path.resolve():
        raise ValueError('Output must not overwrite the original input document.')
    if not doc.blocks or any(not b.translated.strip() for b in doc.blocks):
        raise ValueError('Translate all sections before exporting. Nothing was written.')
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name(path.stem+'.partial'+path.suffix)
    try:
        if suffix == '.docx': _export_docx(doc, temp)
        elif suffix == '.pdf': _export_pdf(doc, temp)
        elif suffix in {'.txt','.md'}:
            temp.write_text('\n\n'.join(b.translated for b in doc.blocks)+'\n',encoding='utf-8')
        elif suffix == '.html':
            lines = ['<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8">'
                     '<title>PsyLex Translation</title></head><body>']
            lines.extend('<p>'+html.escape(b.translated).replace('\n','<br>')+'</p>' for b in doc.blocks)
            lines.append('</body></html>')
            temp.write_text('\n'.join(lines), encoding='utf-8')
        elif suffix in {'.csv','.tsv'}:
            delim = '\t' if suffix == '.tsv' else ','
            if doc.blocks and all(b.kind in ('table_cell','table_header') for b in doc.blocks):
                nrows=max((b.row or 0) for b in doc.blocks)+1
                ncols=max((b.col or 0) for b in doc.blocks)+1
                matrix=[['']*ncols for _ in range(nrows)]
                for b in doc.blocks: matrix[b.row or 0][b.col or 0]=b.translated
            else:
                matrix=[['source','persian']]+[[b.text,b.translated] for b in doc.blocks]
            with temp.open('w',encoding='utf-8-sig',newline='') as f:
                csv.writer(f,delimiter=delim).writerows(matrix)
        elif suffix in {'.json','.jsonl'}:
            pairs=[{'source':b.text,'persian':b.translated,'page':b.page,'ocr':b.ocr,
                    'warnings':b.warnings} for b in doc.blocks]
            payload='\n'.join(json.dumps(r,ensure_ascii=False) for r in pairs)+'\n' if suffix=='.jsonl' else json.dumps(pairs,ensure_ascii=False,indent=2)
            temp.write_text(payload,encoding='utf-8')
        temp.replace(path)
        return path
    finally:
        if temp.exists(): temp.unlink()
