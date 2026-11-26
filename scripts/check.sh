#!/usr/bin/env bash
# Executa todos os portões de qualidade. Pré-requisito: venv do backend ativo e npm install feito.
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "== backend =="
cd "$root/backend"
ruff check .
mypy app
python -m pytest

echo "== frontend =="
cd "$root/frontend"
npx tsc --noEmit
npx vitest run
npx vite build >/dev/null

echo "OK: tudo verde"
