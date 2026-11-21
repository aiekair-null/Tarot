#!/usr/bin/env bash
# One-time setup for Veyra's free built-in model. Usage: bash setup_local.sh [medium|small|llama]
set -e
cd "$(dirname "$0")"
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
# llama-cpp-python runs the model inside Python. Try the prebuilt CPU wheel first (no compiler
# needed); if none fits this machine, build from source (needs cmake + a C compiler, ~5 min).
python3 -m pip install llama-cpp-python --prefer-binary \
    --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu \
  || python3 -m pip install llama-cpp-python
python3 models.py download "${1:-medium}"
python3 models.py
echo
echo "Done. Start a reading with:  python3 tarot.py"
