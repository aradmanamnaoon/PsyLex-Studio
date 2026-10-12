
# PsyLex Studio v0.6.5 - PUBLIC GitHub Publisher
# Compatible with Windows PowerShell 5.1+
# Run only from the extracted PUBLIC source directory.

[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $root

$repository = 'aradmanamnaoon/PsyLex-Studio'
$tag = 'v0.6.5'

function Stop-Publish([string]$message) {
    throw "PUBLISH STOPPED: $message"
}

function Assert-Exit([string]$step) {
    if ($LASTEXITCODE -ne 0) {
        Stop-Publish "$step failed (exit code $LASTEXITCODE)"
    }
}

function Find-Tool([string]$name) {
    $command = Get-Command $name -ErrorAction SilentlyContinue

    if ($command) {
        return $command.Source
    }

    $paths = switch ($name) {
        'git.exe' {
            @(
                "$env:ProgramFiles\Git\cmd\git.exe",
                "${env:ProgramFiles(x86)}\Git\cmd\git.exe"
            )
        }
        'gh.exe' {
            @(
                "$env:ProgramFiles\GitHub CLI\gh.exe",
                "${env:ProgramFiles(x86)}\GitHub CLI\gh.exe",
                "$env:LOCALAPPDATA\Programs\GitHub CLI\gh.exe"
            )
        }
        'ISCC.exe' {
            @(
                "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
                "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
            )
        }
        default {
            @()
        }
    }

    foreach ($candidate in $paths) {
        if (Test-Path -LiteralPath $candidate -PathType Leaf) {
            return $candidate
        }
    }

    return $null
}

function Run(
    [string]$step,
    [string]$tool,
    [string[]]$arguments
) {
    $prior = $ErrorActionPreference

    try {
        # Handle native stderr reliably on PowerShell 5.1.
        $ErrorActionPreference = 'Continue'

        & $tool @arguments | Out-Host
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $prior
    }

    if ($exitCode -ne 0) {
        Stop-Publish "$step failed (exit code $exitCode)"
    }
}

function Ensure-Tool(
    [string]$name,
    [string]$packageId
) {
    $tool = Find-Tool $name

    if ($tool) {
        return $tool
    }

    $winget = Find-Tool 'winget.exe'

    if (-not $winget) {
        Stop-Publish "$name is missing. Install $packageId and retry."
    }

    Write-Host "Installing $packageId ..." -ForegroundColor Yellow

    Run "Install $packageId" $winget @(
        'install',
        '--id', $packageId,
        '--exact',
        '--source', 'winget',
        '--accept-package-agreements',
        '--accept-source-agreements'
    )

    $tool = Find-Tool $name

    if (-not $tool) {
        Stop-Publish "$name was not found. Reopen PowerShell and retry."
    }

    return $tool
}

# ============================================================
# 1. PUBLIC SOURCE VERIFICATION
# ============================================================

Write-Host '[1/10] Verifying public source...' -ForegroundColor Cyan

$requiredFiles = @(
    'PUBLIC_RELEASE_MARKER.json',
    'main.py',
    'installer.iss',
    'resources/starter_glossary.jsonl',
    'scripts/public_release_audit.py',
    'SHA256SUMS.txt'
)

foreach ($required in $requiredFiles) {
    $path = Join-Path $root $required

    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        Stop-Publish "Missing required file: $required"
    }
}

if (Test-Path -LiteralPath (Join-Path $root '.git')) {
    Stop-Publish 'Existing Git repository detected. Use a fresh public-source directory.'
}

if (Test-Path -LiteralPath (Join-Path $root 'resources/dictionaries')) {
    Stop-Publish 'Original dictionary books detected. Publication blocked.'
}

if (Test-Path -LiteralPath (Join-Path $root 'resources/lexicon.jsonl')) {
    Stop-Publish 'Book-derived lexicon detected. Publication blocked.'
}

$markerPath = Join-Path $root 'PUBLIC_RELEASE_MARKER.json'

$marker = Get-Content -LiteralPath $markerPath -Raw -Encoding UTF8 |
    ConvertFrom-Json

if (
    ($marker.version -ne '0.6.5') -or
    ($marker.edition -ne 'public-no-third-party-books')
) {
    Stop-Publish 'This is not the correct public v0.6.5 source package.'
}

# Verify original package hashes.
# Only the locally replaced publishing script may have a new hash.

$manifestPath = Join-Path $root 'SHA256SUMS.txt'
$lines = @(Get-Content -LiteralPath $manifestPath -Encoding UTF8)

$approved = @{}
$updatedLines = New-Object 'System.Collections.Generic.List[string]'
$publisherCount = 0

foreach ($line in $lines) {

    if ($line -notmatch '^([0-9a-fA-F]{64})  (.+)$') {
        Stop-Publish "Invalid checksum manifest entry: $line"
    }

    $expectedHash = $Matches[1].ToLowerInvariant()
    $relative = $Matches[2]

    if (
        ($relative -match '(^/|\.\.|\\)') -or
        ($approved.ContainsKey($relative))
    ) {
        Stop-Publish "Invalid or duplicate manifest path: $relative"
    }

    $fullPath = Join-Path $root $relative

    if (-not (Test-Path -LiteralPath $fullPath -PathType Leaf)) {
        Stop-Publish "Missing public source file: $relative"
    }

    $actualHash = (
        Get-FileHash -LiteralPath $fullPath -Algorithm SHA256
    ).Hash.ToLowerInvariant()

    if ($relative -eq 'publish_github.ps1') {

        $publisherCount++
        $line = "$actualHash  publish_github.ps1"

    }
    elseif ($actualHash -ne $expectedHash) {

        Stop-Publish "Packaged source file changed: $relative"

    }

    $approved[$relative] = $true
    [void]$updatedLines.Add($line)
}

if (
    ($publisherCount -ne 1) -or
    ($approved.Count -lt 90)
) {
    Stop-Publish 'Incomplete or invalid public-source manifest.'
}

$utf8NoBom = [System.Text.UTF8Encoding]::new($false)

$manifestContent = ($updatedLines.ToArray() -join "`n") + "`n"

[System.IO.File]::WriteAllText(
    $manifestPath,
    $manifestContent,
    $utf8NoBom
)

$approved['SHA256SUMS.txt'] = $true

# ============================================================
# 2. INSTALL REQUIRED WINDOWS TOOLS
# ============================================================

Write-Host '[2/10] Checking publishing tools...' -ForegroundColor Cyan

$git = Ensure-Tool 'git.exe' 'Git.Git'
$gh = Ensure-Tool 'gh.exe' 'GitHub.cli'
$iscc = Ensure-Tool 'ISCC.exe' 'JRSoftware.InnoSetup'

# ============================================================
# 3. VERIFY GITHUB ACCOUNT
# ============================================================

Write-Host '[3/10] Checking GitHub authentication...' -ForegroundColor Cyan

$prior = $ErrorActionPreference
$ErrorActionPreference = 'Continue'

try {
    & $gh auth status *> $null
    $authCode = $LASTEXITCODE
}
finally {
    $ErrorActionPreference = $prior
}

if ($authCode -ne 0) {
    Run 'GitHub browser login' $gh @(
        'auth',
        'login',
        '--web',
        '--git-protocol', 'https',
        '--hostname', 'github.com'
    )
}

$login = (
    (& $gh api user --jq '.login') | Out-String
).Trim()

Assert-Exit 'GitHub login lookup'

if ($login -ne 'aradmanamnaoon') {
    Stop-Publish "Signed in as '$login', not 'aradmanamnaoon'."
}

$userId = (
    (& $gh api user --jq '.id') | Out-String
).Trim()

Assert-Exit 'GitHub user ID lookup'

if ($userId -notmatch '^\d+$') {
    Stop-Publish 'Could not verify your GitHub user ID.'
}

# The repository must be absent.
# A network/authentication error is NOT treated as a missing repo.

$prior = $ErrorActionPreference
$ErrorActionPreference = 'Continue'

try {
    $probe = @(& $gh api "repos/$repository" 2>&1)
    $probeCode = $LASTEXITCODE
}
finally {
    $ErrorActionPreference = $prior
}

if ($probeCode -eq 0) {
    Stop-Publish "Repository $repository already exists."
}

$probeText = $probe -join "`n"

if ($probeText -notmatch '(?i)HTTP\s+404\b') {
    Stop-Publish "Could not confirm repository availability: $probeText"
}

# ============================================================
# 4. PYTHON ENVIRONMENT
# ============================================================

Write-Host '[4/10] Setting up Python...' -ForegroundColor Cyan

$python = Join-Path $root '.venv\Scripts\python.exe'

if (-not (Test-Path -LiteralPath $python)) {

    $launcher = Find-Tool 'py.exe'

    if (-not $launcher) {
        Stop-Publish 'Python 3.10 or 3.11 is required.'
    }

    $prior = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'

    try {
        & $launcher -3.10 -m venv .venv | Out-Host
        $venvCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $prior
    }

    if ($venvCode -ne 0) {
        Run 'Create Python 3.11 environment' $launcher @(
            '-3.11', '-m', 'venv', '.venv'
        )
    }
}

if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    Stop-Publish 'Python virtual environment was not created.'
}

Run 'Upgrade pip' $python @(
    '-m', 'pip', 'install', '--upgrade',
    'pip', 'setuptools', 'wheel'
)

Run 'Install project dependencies' $python @(
    '-m', 'pip', 'install', '-e', '.[dev]'
)

# ============================================================
# 5. SECURITY AND PYTHON TESTS
# ============================================================

Write-Host '[5/10] Running security audit and tests...' -ForegroundColor Cyan

Run 'Public source security audit' $python @(
    'scripts/public_release_audit.py'
)

Run 'Python tests' $python @(
    '-m', 'pytest', '-q'
)

Run 'Credentials GUI test' $python @(
    'scripts/ui_credentials_smoke_test.py'
)

Run 'First-launch model GUI test' $python @(
    'scripts/ui_install_model_setup_smoke_test.py'
)

# ============================================================
# 6. STRICT WINDOWS RELEASE GATE
# ============================================================

Write-Host '[6/10] Running Windows release gate...' -ForegroundColor Cyan

Run 'Windows release gate' $python @(
    'scripts/release_gate.py',
    '--require-windows',
    '--require-gui',
    '--require-native-ocr'
)

# ============================================================
# 7. BUILD A FRESH PUBLIC APP AND INSTALLER
# ============================================================

Write-Host '[7/10] Building public Windows installer...' -ForegroundColor Cyan

Run 'PyInstaller and Inno Setup build' $python @(
    'build_installer.py',
    '--clean'
)

$exe = Join-Path $root 'dist\PsyLexStudio\PsyLexStudio.exe'
$installer = Join-Path $root 'dist\installer\PsyLexStudio-Setup.exe'

if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) {
    Stop-Publish 'Windows executable not generated.'
}

if (-not (Test-Path -LiteralPath $installer -PathType Leaf)) {
    Stop-Publish 'Windows installer not generated.'
}

# ============================================================
# 8. TEST PACKAGED EXECUTABLE
# ============================================================

Write-Host '[8/10] Testing packaged executable...' -ForegroundColor Cyan

$report = Join-Path $root 'dist\package-self-test.json'

Remove-Item -LiteralPath $report -ErrorAction SilentlyContinue

$process = Start-Process `
    -FilePath $exe `
    -ArgumentList @(
        '--self-test-report',
        ('"' + $report + '"')
    ) `
    -WorkingDirectory $root `
    -Wait `
    -PassThru

if ($process.ExitCode -ne 0) {
    Stop-Publish "EXE self-test failed: $($process.ExitCode)"
}

if (-not (Test-Path -LiteralPath $report -PathType Leaf)) {
    Stop-Publish 'Packaged EXE did not generate a self-test report.'
}

$result = Get-Content -LiteralPath $report -Raw -Encoding UTF8 |
    ConvertFrom-Json

if ($result.result -ne 'PASS') {
    Stop-Publish 'Packaged executable self-test FAILED.'
}

# ============================================================
# 9. CREATE GITHUB REPOSITORY AND PUSH SAFE SOURCE
# ============================================================

Write-Host '[9/10] Preparing GitHub source repository...' -ForegroundColor Cyan

Write-Warning 'Review redistribution requirements of dependencies, including PyMuPDF AGPL/commercial licensing, before public distribution.'

Run 'Initialize Git' $git @(
    'init', '-b', 'main'
)

Run 'Set Git author' $git @(
    'config', 'user.name', $login
)

Run 'Set Git email' $git @(
    'config',
    'user.email',
    "$userId+$login@users.noreply.github.com"
)

Run 'Stage source' $git @(
    'add', '--all'
)

$staged = @(& $git diff --cached --name-only)

Assert-Exit 'Read staged paths'

if ($staged.Count -ne $approved.Count) {
    Stop-Publish "Git staged $($staged.Count) files; expected $($approved.Count)."
}

foreach ($path in $staged) {

    if (-not $approved.ContainsKey($path)) {
        Stop-Publish "Unexpected file staged: $path"
    }

    $forbidden = '(?i)(^|/)(dictionaries|dist|build|\.venv|__pycache__)(/|$)|\.(exe|msi|dll|pyd|zip|db|sqlite3?|gguf|safetensors|pem|pfx|key|log)$|(^|/)lexicon\.jsonl$'

    if ($path -match $forbidden) {
        Stop-Publish "Private or dangerous file staged: $path"
    }
}

foreach ($path in $approved.Keys) {
    if ($staged -notcontains $path) {
        Stop-Publish "Required approved source file missing: $path"
    }
}

Run 'Commit public source' $git @(
    'commit',
    '-m',
    'Publish PsyLex Studio v0.6.5 public edition'
)

Run 'Create GitHub repository and push code' $gh @(
    'repo',
    'create',
    $repository,
    '--public',
    '--source', '.',
    '--remote', 'origin',
    '--push',
    '--description',
    'Local-first English-Persian psychology glossary and translator'
)

Run 'Create release tag' $git @(
    'tag',
    '-a',
    $tag,
    '-m',
    "PsyLex Studio $tag"
)

Run 'Push release tag' $git @(
    'push',
    'origin',
    $tag
)

# ============================================================
# 10. PUBLISH WINDOWS INSTALLER IN GITHUB RELEASES
# ============================================================

Write-Host '[10/10] Publishing GitHub Release...' -ForegroundColor Cyan

$asset = Join-Path $root "dist\installer\PsyLexStudio-Setup-$tag.exe"

Copy-Item -LiteralPath $installer -Destination $asset -Force

Run 'Publish GitHub Release' $gh @(
    'release',
    'create',
    $tag,
    $asset,
    '--repo', $repository,
    '--verify-tag',
    '--title', "PsyLex Studio $tag - Windows",
    '--notes-file', 'RELEASE_NOTES.md',
    '--latest'
)

Write-Host ''
Write-Host '============================================' -ForegroundColor Green
Write-Host 'PSYLEX STUDIO PUBLISHED SUCCESSFULLY' -ForegroundColor Green
Write-Host '============================================' -ForegroundColor Green

Write-Host "Source: https://github.com/$repository" -ForegroundColor Green
Write-Host "Release: https://github.com/$repository/releases/tag/$tag" -ForegroundColor Green

Write-Host ''
Write-Host 'Windows installer SHA-256:'

Get-FileHash -LiteralPath $asset -Algorithm SHA256 |
    Format-List Hash

Write-Host 'Perform a clean Windows installation test before broad distribution.'
