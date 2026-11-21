#!/usr/bin/env python3
"""See which chat models Hugging Face's router can serve right now.
  python models.py              list (uncensored/abliterated first)
  python models.py abliterated  search by word
  python models.py use ID       choose a model for Veyra (saved in model.txt)"""
import json, os, sys, urllib.request

FLAG = ("abliterated", "uncensored", "heretic", "dolphin")
SLOW = ("gpt-oss", "r1", "thinking", "reason", "qwq")


def available(token=None):
    """[(model_id, [providers])] from the live router catalog."""
    h = {"Authorization": f"Bearer {token}"} if token else {}
    with urllib.request.urlopen(urllib.request.Request("https://router.huggingface.co/v1/models", headers=h),
                                timeout=20) as r:
        data = json.load(r)
    out = []
    for m in data.get("data", []):
        provs = [p.get("provider") for p in m.get("providers", []) if p.get("status", "live") == "live"]
        if m.get("id") and provs:
            out.append((m["id"], provs))
    return out


def flagged(mid):
    return any(f in mid.lower() for f in FLAG)


def tags(mid, provs=()):
    t = []
    if flagged(mid):
        t.append("uncensored")
    if any(s in mid.lower() for s in SLOW):
        t.append("reasoning: slower")
    return f"[{', '.join(provs[:3])}] " + (" ".join(f"({x})" for x in t))


def ranked(items, term=""):
    hits = [(m, p) for m, p in items if term.lower() in m.lower()]
    return sorted(hits, key=lambda x: (not flagged(x[0]), x[0].lower()))


if __name__ == "__main__":
    args = sys.argv[1:]
    if args[:1] == ["use"] and len(args) > 1:
        open(os.environ.get("TAROT_MODEL_FILE", "model.txt"), "w").write(args[1])
        sys.exit(f"saved {args[1]} to model.txt")
    try:
        items = available(os.environ.get("HF_TOKEN"))
    except Exception as e:
        sys.exit(f"Could not fetch the model list: {e}")
    for i, (m, p) in enumerate(ranked(items, args[0] if args else "")[:60], 1):
        print(f"{i:>3}) {m}  {tags(m, p)}")
    print(f"\n{len(items)} models available. Use: python models.py use <model id>")
