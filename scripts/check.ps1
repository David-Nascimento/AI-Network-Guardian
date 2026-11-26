# Executa todos os portões de qualidade (Windows).
# Pré-requisito: venv do backend ativo (backend\.venv\Scripts\Activate.ps1) e npm install feito.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

function Run($cmd) {
    Write-Host "> $cmd"
    Invoke-Expression $cmd
    if ($LASTEXITCODE -ne 0) { throw "Falhou: $cmd" }
}

Write-Host "== backend =="
Push-Location "$root\backend"
Run "ruff check ."
Run "mypy app"
Run "python -m pytest"
Pop-Location

Write-Host "== frontend =="
Push-Location "$root\frontend"
Run "npx tsc --noEmit"
Run "npx vitest run"
Run "npx vite build"
Pop-Location

Write-Host "OK: tudo verde"
