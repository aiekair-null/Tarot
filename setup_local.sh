#!/usr/bin/env bash
# One-time setup for Veyra. Usage: bash setup_local.sh [medium|small|llama]
# Every step is optional: if one fails, Veyra still runs and asks for it again when it is needed.
cd "$(dirname "$0")"
step() { echo; echo "== $1"; }

step "Python packages"
python3 -m pip install --upgrade pip -q
python3 -m pip install -q -r requirements.txt || echo "(some packages did not install; Veyra will ask later)"

step "Built-in AI engine (llama-cpp-python)"
python3 -m pip install -q llama-cpp-python --prefer-binary \
    --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu \
  || python3 -m pip install -q llama-cpp-python \
  || echo "(llama-cpp-python did not install; readings will use scripted knowledge)"

step "Free AI model"
python3 models.py download "${1:-medium}" || echo "(model download failed; run: python3 models.py download)"

step "ffmpeg (for reading videos)"
if command -v ffmpeg >/dev/null; then echo "already installed"
elif command -v apt-get >/dev/null; then
  SUDO=""; [ "$(id -u)" -ne 0 ] && command -v sudo >/dev/null && SUDO="sudo"
  $SUDO apt-get update -qq && $SUDO env DEBIAN_FRONTEND=noninteractive apt-get install -y -qq ffmpeg \
    || echo "(ffmpeg did not install; Veyra will offer again when you make a video)"
else echo "(install ffmpeg from https://ffmpeg.org to make videos)"; fi

step "Her video voice (flite, free)"
if command -v flite >/dev/null; then echo "already installed"
elif command -v apt-get >/dev/null; then
  SUDO=""; [ "$(id -u)" -ne 0 ] && command -v sudo >/dev/null && SUDO="sudo"
  $SUDO env DEBIAN_FRONTEND=noninteractive apt-get install -y -qq flite \
    || echo "(flite did not install; Veyra will offer again when you make a video)"
else echo "(no apt-get; Veyra will look for a voice when you make a video)"; fi

echo
python3 models.py
echo
echo "Done. Start a reading with:  python3 tarot.py"
