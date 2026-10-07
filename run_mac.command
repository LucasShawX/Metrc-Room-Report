#!/bin/bash
set -e
cd "$(dirname "$0")"

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 is required. Install Python 3.11+ from https://www.python.org/downloads/macos/"
  echo
  read -n 1 -s -r -p "Press any key to close..."
  echo
  exit 1
fi

if [ ! -d ".venv" ]; then
  echo "Creating local Python environment..."
  python3 -m venv .venv
fi

source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

python -m streamlit run app.py
