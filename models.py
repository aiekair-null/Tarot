#!/usr/bin/env python3
"""Manage Veyra's brain.
  python models.py                  show what's installed and what's free to download
    python models.py download [key]   download a free built-in model (medium = default | qwen3-8b | small | llama)
  python models.py use <key|file>   switch the built-in model
    python models.py download qwen3-8b   install Qwen3-8B (about 5 GB)
    python models.py use qwen3-8b         select it for the next launch
  python models.py hf [word]        (optional, PAID) list Hugging Face router models"""
import json, os, sys, urllib.request
import brain

FLAG = ("abliterated", "uncensored", "heretic", "dolphin")


def hf_available(token=None):
    """[(model_id, [providers])] from the paid Hugging Face router catalog."""
    h = {"Authorization": f"Bearer {token}"} if token else {}
    with urllib.request.urlopen(urllib.request.Request("https://router.huggingface.co/v1/models", headers=h),
                                timeout=20) as r:
        data = json.load(r)
    return [(m["id"], [p.get("provider") for p in m.get("providers", [])]) for m in data.get("data", []) if m.get("id")]


def status():
    active = brain.find_gguf()
    print("Built-in models (free, run on this machine):")
    for key, (repo, f, size, note) in brain.CATALOG.items():
        have = (brain.MODELS_DIR / f).exists()
        mark = "*" if active and active.name == f else (" " if have else " ")
        print(f"  {mark} {key:<7} {size:>7}  {'installed' if have else 'download '}  {note}")
    others = [p.name for p in brain.MODELS_DIR.glob("*.gguf")] if brain.MODELS_DIR.exists() else []
    extra = [o for o in others if o not in {v[1] for v in brain.CATALOG.values()}]
    for o in extra:
        print(f"  {'*' if active and active.name == o else ' '} {o}")
    try:
        import llama_cpp  # noqa
        print("  llama-cpp-python: installed")
    except ImportError:
        print("  llama-cpp-python: NOT installed  ->  bash setup_local.sh")
    om = brain.ollama_models()
    print("Ollama:", ", ".join(om) if om else "not running (optional)")
    b = brain.Brain()
    print(f"\nVeyra will use: {b.label}" + (f"   ({b.err})" if not b.online and b.err else ""))


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a:
        status()
    elif a[0] == "download":
        key = a[1] if len(a) > 1 else brain.DEFAULT
        if key not in brain.CATALOG:
            sys.exit(f"choose one of: {', '.join(brain.CATALOG)}")
        print("saved:", brain.download(key))
    elif a[0] == "use" and len(a) > 1:
        f = brain.CATALOG[a[1]][1] if a[1] in brain.CATALOG else a[1]
        if not (brain.MODELS_DIR / f).exists():
            sys.exit(f"{f} isn't in {brain.MODELS_DIR}/ yet. Try: python models.py download {a[1]}")
        brain.ACTIVE.write_text(f)
        print("Veyra will now think with", f)
    elif a[0] == "hf":
        try:
            items = hf_available(os.environ.get("HF_TOKEN"))
        except Exception as e:
            sys.exit(f"Could not fetch the model list: {e}")
        term = a[1] if len(a) > 1 else ""
        hits = sorted([(m, p) for m, p in items if term.lower() in m.lower()],
                      key=lambda x: (not any(f in x[0].lower() for f in FLAG), x[0].lower()))
        for i, (m, p) in enumerate(hits[:60], 1):
            print(f"{i:>3}) {m}  [{', '.join(filter(None, p[:3]))}]")
        print("\nPaid route. To use one: export TAROT_BACKEND=hf TAROT_MODEL=<id> HF_TOKEN=...")
    else:
        print(__doc__)
