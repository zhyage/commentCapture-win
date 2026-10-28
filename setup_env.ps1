# Douyin research tool - environment setup (rerunnable)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$env:PLAYWRIGHT_BROWSERS_PATH = Join-Path $root ".cache\ms-playwright"
$env:PIP_CACHE_DIR           = Join-Path $root ".cache\pip"
$env:HF_HOME                 = Join-Path $root ".cache\huggingface"

# ---- China mirrors (faster downloads from mainland China) ----
$env:PIP_INDEX_URL           = "https://pypi.tuna.tsinghua.edu.cn/simple"
$env:PLAYWRIGHT_DOWNLOAD_HOST = "https://npmmirror.com/mirrors/playwright/"
$env:HF_ENDPOINT             = "https://hf-mirror.com"

Write-Host "[1/6] create/check venv (.venv)..."
if (-not (Test-Path ".venv")) {
    python -m venv .venv
} else {
    Write-Host "      venv exists, skip"
}

# Fix: some venv lacks pip (ensurepip needs system temp access)
if (-not (Test-Path ".venv\Scripts\pip.exe")) {
    Write-Host "      pip missing in venv, installing via ensurepip..."
    & ".venv\Scripts\python.exe" -m ensurepip --upgrade --default-pip
    if (-not (Test-Path ".venv\Scripts\pip.exe")) {
        Write-Error "ensurepip failed - check permissions"
        exit 1
    }
}

Write-Host "[2/6] upgrade pip..."
& ".venv\Scripts\python.exe" -m pip install --upgrade pip --quiet

Write-Host "[3/6] install playwright..."
& ".venv\Scripts\pip.exe" install playwright --quiet

Write-Host "[4/6] download Chromium browser (~150MB, may take minutes)..."
& ".venv\Scripts\playwright.exe" install chromium

Write-Host "[5/6] install faster-whisper..."
& ".venv\Scripts\pip.exe" install faster-whisper --quiet

Write-Host "[6/6] verify imports..."
& ".venv\Scripts\python.exe" -c "from playwright.sync_api import sync_playwright; import faster_whisper; print('OK: playwright + faster_whisper importable')"

Write-Host "DONE: environment ready"
