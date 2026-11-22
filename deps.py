"""Check for what an optional feature needs. Anything missing is asked for (and installed only
with the querent's yes); nothing here ever crashes the reading."""
import importlib, os, shutil, subprocess, sys, urllib.request
from pathlib import Path

VOICES_DIR = Path(os.environ.get("TAROT_VOICES_DIR", "voices"))
VOICES = {   # free Piper voices (rhasspy/piper-voices on Hugging Face)
    "amy": "en/en_US/amy/medium/en_US-amy-medium",
    "jenny": "en/en_GB/jenny_dioco/medium/en_GB-jenny_dioco-medium",
}
HF = "https://huggingface.co/rhasspy/piper-voices/resolve/main/"


def default_ask(question):
    try:
        return not input(f"  {question} [Y/n] ").strip().lower().startswith("n")
    except EOFError:
        return False


def default_say(text):
    print("  " + text)


def _run(cmd):
    try:
        return subprocess.run(cmd, shell=isinstance(cmd, str), capture_output=True, text=True, timeout=1800).returncode == 0
    except Exception:
        return False


def has_module(name):
    try:
        importlib.import_module(name)
        return True
    except Exception:
        return False


def ensure_python(pkgs, ask=default_ask, say=default_say, why="this"):
    """pkgs: {import_name: pip_name}. Offers one pip install for whatever is missing."""
    missing = {m: p for m, p in pkgs.items() if not has_module(m)}
    if not missing:
        return True
    names = " ".join(missing.values())
    if not ask(f"{why} needs the Python package(s) {names}. Install them now?"):
        say(f"Skipped. You can install them later with: pip install {names}")
        return False
    say(f"Installing {names}...")
    ok = _run([sys.executable, "-m", "pip", "install", "-q", *missing.values()])
    importlib.invalidate_caches()
    if not ok or any(not has_module(m) for m in missing):
        say(f"That install did not finish. Try: pip install {names}")
        return False
    return True


def ffmpeg():
    return shutil.which("ffmpeg")


def ensure_ffmpeg(ask=default_ask, say=default_say):
    if ffmpeg():
        return True
    apt = shutil.which("apt-get")
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        sudo = ""
    elif shutil.which("sudo"):
        sudo = "sudo "
    else:
        sudo = None
    if apt and sudo is not None:
        if ask("Videos need ffmpeg (a free video encoder). Install it now with apt-get? (about a minute)"):
            say("Installing ffmpeg...")
            _run(f"{sudo}apt-get update -qq && {sudo}DEBIAN_FRONTEND=noninteractive apt-get install -y -qq ffmpeg")
            if ffmpeg():
                return True
            say("ffmpeg did not install. Try: sudo apt-get install -y ffmpeg")
            return False
    elif shutil.which("brew"):
        if ask("Videos need ffmpeg. Install it now with Homebrew?"):
            _run("brew install ffmpeg")
            if ffmpeg():
                return True
    say("Videos need ffmpeg. Install it (https://ffmpeg.org/download.html), then choose 'make a video' again.")
    return False


def ffmpeg_has_flite():
    f = ffmpeg()
    if not f:
        return False
    try:
        out = subprocess.run([f, "-hide_banner", "-filters"], capture_output=True, text=True, timeout=20).stdout
        return " flite " in out
    except Exception:
        return False


def voice_model(name=None):
    name = name or os.environ.get("TAROT_VOICE", "amy")
    rel = VOICES.get(name, VOICES["amy"])
    return VOICES_DIR / (rel.rsplit("/", 1)[1] + ".onnx")


def piper_ready(name=None):
    m = voice_model(name)
    return has_module("piper") and m.exists() and Path(str(m) + ".json").exists()


def download_voice(name=None, say=default_say):
    name = name or os.environ.get("TAROT_VOICE", "amy")
    rel = VOICES.get(name, VOICES["amy"])
    VOICES_DIR.mkdir(parents=True, exist_ok=True)
    for ext in (".onnx.json", ".onnx"):
        dest = VOICES_DIR / (rel.rsplit("/", 1)[1] + ext)
        if dest.exists() and dest.stat().st_size > 1000:
            continue
        say(f"Downloading voice file {dest.name}...")
        tmp = dest.with_suffix(dest.suffix + ".part")
        with urllib.request.urlopen(urllib.request.Request(HF + rel + ext, headers={"User-Agent": "Veyra/2"}), timeout=60) as r, \
                open(tmp, "wb") as f:
            while chunk := r.read(1 << 20):
                f.write(chunk)
        tmp.replace(dest)
    return voice_model(name)


def _sudo():
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        return ""
    return "sudo " if shutil.which("sudo") else None


def flite_ready():
    return ffmpeg_has_flite() or bool(shutil.which("flite"))


def ensure_voice(ask=default_ask, say=default_say):
    """Her video voice. The default is the slightly digital flite voice used in the first videos;
    set TAROT_VOICE_ENGINE=piper for the softer Piper voice. Returns 'flite', 'piper', 'espeak' or None."""
    want = os.environ.get("TAROT_VOICE_ENGINE", "flite").lower()
    if want == "piper":
        if piper_ready():
            return "piper"
        if ask("You chose the Piper voice. Set it up now? (free, about 80 MB, one time)"):
            if not has_module("piper"):
                say("Installing the Piper voice engine...")
                _run([sys.executable, "-m", "pip", "install", "-q", "-U", "piper-tts"])
                importlib.invalidate_caches()
            try:
                download_voice(say=say)
            except Exception as e:
                say(f"The voice file did not download ({str(e)[:80]}).")
            if piper_ready():
                return "piper"
        say("Piper is not ready, so I will use her usual voice.")
    if flite_ready():
        return "flite"
    sudo, apt = _sudo(), shutil.which("apt-get")
    if apt and sudo is not None and ask("Her voice needs flite (a small free speech engine). Install it now? (under a minute)"):
        say("Installing flite...")
        _run(f"{sudo}apt-get update -qq && {sudo}DEBIAN_FRONTEND=noninteractive apt-get install -y -qq flite")
        if flite_ready():
            return "flite"
        say("flite did not install. You can try: sudo apt-get install -y flite")
    if shutil.which("espeak-ng") or shutil.which("espeak"):
        say("Using espeak for her voice.")
        return "espeak"
    say("No voice engine is available, so this video will have captions and music but no voice. "
        "To fix it: sudo apt-get install -y flite")
    return None
