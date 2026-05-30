#!/usr/bin/env bash
# One-command setup + run for the SHL Assessment Recommender.
# Creates a virtualenv, installs dependencies, and starts the API + web UI.
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
  echo "Creating virtual environment..."
  python3 -m venv .venv
fi

echo "Installing dependencies..."
./.venv/bin/python -m pip install -q --upgrade pip
./.venv/bin/python -m pip install -q -r requirements.txt

if [ ! -f "data/catalog.json" ]; then
  echo "Catalog missing — scraping it now (one-time)..."
  ./.venv/bin/python scripts/scrape_catalog.py
fi

PORT="${PORT:-8000}"
echo ""
echo "Starting server on http://localhost:${PORT}"
echo "  • Web UI:   http://localhost:${PORT}/"
echo "  • Health:   http://localhost:${PORT}/health"
echo ""
exec ./.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT}"
