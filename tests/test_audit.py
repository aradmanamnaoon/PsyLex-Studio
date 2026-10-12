from scripts.audit_lexicon import flags, audit

def test_audit_flags_mixed_ocr():
    assert 'latin_word_in_persian' in flags({'english': 'test', 'persian': 'نمونه extra', 'quality': .9})

def test_audit_export(tmp_path):
    input_file = tmp_path / 'starter_glossary.jsonl'
    input_file.write_text('{"english":"attention","persian":"توجه","quality":0.9}\n', encoding='utf-8')
    result = audit(input_file, tmp_path / 'report.csv')
    assert result['entries'] == 1
    assert (tmp_path / 'report.csv').exists()
