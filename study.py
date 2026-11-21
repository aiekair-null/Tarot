#!/usr/bin/env python3
"""Let Veyra study on her own: python study.py [number_of_cards]  (needs the built-in model)."""
import sys
from agent import Reader

n = int(sys.argv[1]) if len(sys.argv) > 1 else 20
r = Reader()
if not r.online:
    sys.exit("No model connected. Run: bash setup_local.sh   (free, one time)")
print(f"Veyra studies with {r.label}")
for i in range(n):
    print(f"study {i + 1}/{n}...", flush=True)
    r.study(1)
print("done; lore saved to memory.json")
