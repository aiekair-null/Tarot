"""Veyra at the command line: her sprite, then "What is thy bidding?" and a plain chat with her model.

    veyra chat                 talk to her (exit, quit or Ctrl+D to leave; /clear forgets the chat)
    veyra chat "a question"    one answer, then back to your shell

No cards, no menus, no sync: only her picture and her brain (it wakes in the background while you type)."""
import json
import locale
import os
import random
import sys
import threading
from pathlib import Path

import art
import brain

SYSTEM = ("You are Veyra, an 8-bit oracle who lives inside this computer and runs on its own local model. "
          "You speak with a little mystic flavor drawn from your lore and tonight's sky, but you answer plainly, "
          "accurately and helpfully, and you keep it short unless asked for more. You can help with anything: "
          "questions, code, writing, plans.\n"
          "You keep your own notes between conversations. When you learn something worth remembering (about the "
          "person, a promise, an idea you want to return to), end your reply with one line: REMEMBER: <short note>. "
          "Only when it matters; never mention this rule.")
CHAT_MODEL = "qwen3-8b-abl"                                # the abliterated Qwen3 8B is her chat brain
MEMORY = Path(os.environ.get("TAROT_MEMORY", "memory.json"))
GOLD, LILAC, CYAN, DIM, RESET = "\x1b[38;5;220m", "\x1b[38;5;183m", "\x1b[38;5;51m", "\x1b[38;5;245m", "\x1b[0m"


def utf8():
    try:
        locale.setlocale(locale.LC_ALL, "")
    except locale.Error:
        pass
    if os.environ.get("TAROT_ASCII") == "1":
        return False
    try:
        return "utf" in locale.nl_langinfo(locale.CODESET).lower().replace("-", "") or os.name == "nt"
    except Exception:
        return True


def portrait(unicode_ok):
    if unicode_ok:                                        # half-block pixels: 26 x 14 cells
        return art.ansi(art.veyra_cells())
    lines = []                                            # any terminal: two spaces per pixel, colored
    for row in art.veyra_pixels():
        s = "".join(f"\x1b[48;5;{c}m  " if c is not None else "\x1b[49m  " for c in row)
        lines.append(s + RESET)
    return lines


def load_mem():
    try:
        return json.loads(MEMORY.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_note(note):
    m = load_mem()
    m["veyra_notes"] = (m.get("veyra_notes", []) + [note[:240]])[-60:]
    tmp = MEMORY.with_suffix(".tmp")
    tmp.write_text(json.dumps(m, indent=2), encoding="utf-8")
    tmp.replace(MEMORY)


def sky_lines():
    try:
        import astro
        sky = astro.today()
        return astro.summary(sky, short=True), astro.summary(sky)
    except Exception:
        return "", ""


def lore_flavor(rng):
    """A few cards from her lore, any extra *lore*.txt files, and what she has noted before."""
    import lore
    parts = []
    for name in rng.sample(sorted(lore.LORE), 4):
        d = lore.LORE[name]
        parts.append(f"{name}: inner {d['inner']}; love {d['love']}; asks: {d['ask']}")
    for f in sorted(Path(".").glob("*lore*.txt")) + sorted(Path(".").glob("*lore*.md")):
        try:
            t = f.read_text(encoding="utf-8").strip()
            if t:
                i = rng.randrange(max(1, len(t) - 600))
                parts.append(f"From {f.name}: " + t[i:i + 600])
        except Exception:
            pass
    m = load_mem()
    notes = m.get("veyra_notes", [])[-12:]
    facts = m.get("user_facts", [])[-6:]
    out = "YOUR LORE TONIGHT:\n" + "\n".join("- " + p for p in parts)
    if notes:
        out += "\nYOUR OWN NOTES FROM BEFORE:\n" + "\n".join("- " + n for n in notes)
    if facts:
        out += "\nWHAT THEY HAVE TOLD YOU:\n" + "\n".join("- " + f for f in facts)
    return out


def pick_model():
    """Use the abliterated Qwen3 8B for chat; offer to download it if it isn't here yet."""
    if os.environ.get("TAROT_GGUF"):
        return Path(os.environ["TAROT_GGUF"]).name
    repo, fname, size, _ = brain.CATALOG[CHAT_MODEL]
    path = brain.MODELS_DIR / fname
    if not path.exists():
        try:
            yes = input(f"{DIM}Her chat brain (abliterated Qwen3 8B, {size}) isn't downloaded yet. Get it now? [Y/n]{RESET} ")
        except (EOFError, KeyboardInterrupt):
            yes = "n"
        if not yes.strip().lower().startswith("n"):
            try:
                brain.download(CHAT_MODEL)
            except Exception as e:
                print(f"{DIM}Download failed: {e}{RESET}")
    if path.exists():
        os.environ["TAROT_GGUF"] = str(path)
        return path.name
    found = brain.find_gguf()
    return found.name if found else "none"


class Printer:
    """Streams her words, but holds back any REMEMBER: line so it can be saved instead of shown."""
    TAG = "REMEMBER:"

    def __init__(self):
        self.line, self.held, self.notes = "", False, []

    def feed(self, piece):
        for ch in piece:
            if ch == "\n":
                self._end_line(); print(ch, end=""); continue
            self.line += ch
            if not self.held:
                if self.TAG.startswith(self.line.lstrip()[:len(self.TAG)]) and len(self.line.lstrip()) <= len(self.TAG):
                    continue                           # might be the tag: wait
                if self.line.lstrip().startswith(self.TAG):
                    self.held = True
                    continue
                print(self.line, end="", flush=True)
                self.line = ""
                self.held = None                       # this line is plain text: stream the rest directly
            elif self.held is None:
                print(ch, end="", flush=True); self.line = ""

    def _end_line(self):
        s = self.line.strip()
        if s.startswith(self.TAG):
            note = s[len(self.TAG):].strip()
            if note:
                self.notes.append(note)
        elif self.line:
            print(self.line, end="")
        self.line, self.held = "", False

    def close(self):
        self._end_line()


def main():
    try:
        sys.stdout.reconfigure(errors="replace")
    except Exception:
        pass
    if os.name == "nt":
        os.system("")
    print()
    for line in portrait(utf8()):
        print("   " + line)
    print(f"\n   {GOLD}V E Y R A{RESET}  {DIM}8b/8b(L){RESET}")
    model = pick_model()
    short, full = sky_lines()
    print(f"   {DIM}model:{RESET} {CYAN}{model}{RESET}")
    if short:
        print(f"   {DIM}sky:{RESET}   {LILAC}{short}{RESET}")
    print()
    rng = random.SystemRandom()
    system = SYSTEM + "\nTONIGHT'S SKY: " + (full or "unknown") + "\n" + lore_flavor(rng)

    b = brain.Brain(connect=False)
    ready = threading.Event()
    threading.Thread(target=lambda: (b.connect(), ready.set()), daemon=True).start()

    history = []
    once = " ".join(sys.argv[1:]).strip()
    while True:
        if once:
            q = once
        else:
            try:
                q = input(f"{LILAC}What is thy bidding?{RESET} ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
        if not q:
            continue
        if q.lower() in ("exit", "quit", "bye", "/exit", "/quit"):
            break
        if q == "/clear":
            history = []
            print(f"{DIM}(forgotten){RESET}")
            continue
        if not ready.is_set():
            print(f"{DIM}(she is waking...){RESET}", end="", flush=True)
            ready.wait()
            print("\r" + " " * 22 + "\r", end="")
        if b.kind == "none":
            print(f"{DIM}Her model would not wake: {b.err or 'no model installed (run: veyra model)'}{RESET}")
            break
        history.append({"role": "user", "content": q})
        msgs = [{"role": "system", "content": system}] + history[-12:]
        print(CYAN, end="", flush=True)
        out, pr = [], Printer()
        try:
            for piece in b.stream(msgs, max_tokens=700, temperature=0.7):
                out.append(piece)
                pr.feed(piece)
        except KeyboardInterrupt:
            out.append(" ...")
        pr.close()
        print(RESET + "\n")
        for note in pr.notes:
            try:
                save_note(note)
                print(f"{DIM}  (she noted: {note}){RESET}\n")
            except Exception:
                pass
        history.append({"role": "assistant", "content": "".join(out).strip()})
        if once:
            break


if __name__ == "__main__":
    main()
