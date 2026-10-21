#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/.."
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pyinstaller --noconfirm --onefile --windowed --name AnbardariAsan \
  --add-data "app/database/schema.sql:app/database" \
  --add-data "assets:assets" \
  app/main.py
echo "Output: dist/AnbardariAsan"
