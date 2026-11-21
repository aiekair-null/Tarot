#!/usr/bin/env python3
"""Let Veyra study on her own: python study.py [number_of_cards]  (needs a connected model)."""
import sys
from agent import Reader

n = int(sys.argv[1]) if len(sys.argv) > 1 else 20
r = Reader()
if not (r.client or r.local):
    sys.exit("No model connected. Run tarot.py once to pick a model, or set HF_TOKEN + TAROT_MODEL.")
for i in range(n):
    print(f"study {i + 1}/{n}...", flush=True)
    r.study(1)
print("done; lore saved to memory.json")
