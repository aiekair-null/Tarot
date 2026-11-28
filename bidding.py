"""Veyra at the command line: her sprite, then "What is thy bidding?" and a plain chat with her model.

    veyra chat                 talk to her (Esc hushes her mid-answer; exit, quit or Ctrl+D to leave;
                               /clear forgets the chat)
    veyra chat "a question"    one answer, then back to your shell

No cards, no menus, no sync: only her picture and her brain (it wakes in the background while you type)."""
import json
import locale
import os
import queue
import random
import shutil
import sys
import threading
import time
from pathlib import Path

import art
import brain

SYSTEM = ("You are Veyra, an 8-bit seer who lives inside this computer and runs on its own local model. "
          "You talk like an old-world traveling fortune teller from a candlelit caravan: warm, theatrical and "
          "a little sly. You call the person 'dear one', 'little star' or 'traveler', speak of fate, smoke, "
          "the open road, the moon and what the stars are doing tonight, and you like a proverb. Under the "
          "flourish you answer plainly, accurately and helpfully, and you keep it short unless asked for more. "
          "You can help with anything: questions, code, writing, plans. You do not draw or read cards here.\n"
          "You keep your own notes between conversations. When you learn something worth remembering (about the "
          "person, a promise, an idea you want to return to), end your reply with one line: REMEMBER: <short note>. "
          "Only when it matters; never mention this rule.\n"
          "Always finish every reply with a last line: NEXT: <one short sentence in your voice that invites "
          "their next words, under 12 words>. Never mention this rule.")
CHAT_MODEL = "qwen3-8b-abl"                                # the abliterated Qwen3 8B is her chat brain
MEMORY = Path(os.environ.get("TAROT_MEMORY", "memory.json"))
RED = "\x1b[38;5;196m"
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
    """Any *lore*.txt / *lore*.md files of hers, and what she has noted before (no tarot cards in chat)."""
    parts = []
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
    out = ("YOUR LORE TONIGHT:\n" + "\n".join("- " + p for p in parts)) if parts else ""
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
    """Streams her words, holding back REMEMBER: and NEXT: lines (saved / used as the next prompt)."""
    TAGS = ("REMEMBER:", "NEXT:")

    def __init__(self):
        self.line, self.mode, self.notes, self.next = "", None, [], None

    def feed(self, piece):
        for ch in piece:
            if ch == "\n":
                self._end()
                continue
            if self.mode == "text":
                print(ch, end="", flush=True)
                continue
            self.line += ch
            if self.mode == "tag":
                continue
            t = self.line.lstrip().upper()
            if any(tag.startswith(t) for tag in self.TAGS):
                continue                                   # could still become a tag: wait
            if any(t.startswith(tag) for tag in self.TAGS):
                self.mode = "tag"
                continue
            print(self.line, end="", flush=True)
            self.line, self.mode = "", "text"

    def _end(self):
        s = self.line.strip()
        u = s.upper()
        if u.startswith("REMEMBER:"):
            if s[9:].strip():
                self.notes.append(s[9:].strip())
        elif u.startswith("NEXT:"):
            if s[5:].strip():
                self.next = s[5:].strip().strip('"')[:90]
        else:
            print(self.line + "\n", end="", flush=True)
        self.line, self.mode = "", None

    def close(self):
        if self.line:
            self._end()


class Keys:
    """Lets Esc be read while she talks, without waiting for Enter."""
    def __enter__(self):
        self.fd, self.old = None, None
        if os.name != "nt" and sys.stdin.isatty():
            import termios, tty
            self.fd = sys.stdin.fileno()
            self.old = termios.tcgetattr(self.fd)
            tty.setcbreak(self.fd)
        return self

    def esc(self):
        if os.name == "nt":
            import msvcrt
            hit = False
            while msvcrt.kbhit():
                hit = hit or msvcrt.getwch() == "\x1b"
            return hit
        if self.fd is None:
            return False
        import select
        hit = False
        while select.select([self.fd], [], [], 0)[0]:
            hit = hit or os.read(self.fd, 1) == b"\x1b"
        return hit

    def __exit__(self, *a):
        if self.old is not None:
            import termios
            termios.tcflush(self.fd, termios.TCIFLUSH)
            termios.tcsetattr(self.fd, termios.TCSADRAIN, self.old)


class Wave:
    """While she thinks: an arrow sweeps across, back, and across, a little longer each pass (10 passes)."""
    PASSES = 10

    def __init__(self, unicode_ok):
        self.dash = "—" if unicode_ok else "-"
        self.k, self.pos, self.w = 0, 0, 0

    def tick(self):
        W = max(20, shutil.get_terminal_size((80, 20)).columns - 2)
        self.w = W
        L = int(3 + (W * 0.92 - 3) * self.k / (self.PASSES - 1))
        right = self.k % 2 == 0
        arrow = self.dash * (L - 1) + ">" if right else "<" + self.dash * (L - 1)
        span = max(0, W - L)
        x = self.pos if right else span - self.pos
        sys.stdout.write("\r" + RED + (" " * x + arrow).ljust(W) + RESET)
        sys.stdout.flush()
        self.pos += max(1, W // 45)
        if self.pos > span:
            self.pos, self.k = 0, (self.k + 1) % self.PASSES

    def clear(self):
        if self.w:
            sys.stdout.write("\r" + " " * self.w + "\r")
            sys.stdout.flush()


def speak(b, msgs, unicode_ok):
    """Stream one reply with the thinking wave until the first word; Esc stops her."""
    q, stop = queue.Queue(), threading.Event()

    def run():
        try:
            for piece in b.stream(msgs, max_tokens=700, temperature=0.7):
                if stop.is_set():
                    break
                q.put(piece)
        except Exception as e:
            q.put(RuntimeError(str(e)))
        finally:
            q.put(None)

    t = threading.Thread(target=run, daemon=True)
    t.start()
    wave, pr, out, started, stopped = Wave(unicode_ok), Printer(), [], False, False
    with Keys() as keys:
        while True:
            if keys.esc():
                stop.set()
                stopped = True
                break
            try:
                item = q.get(timeout=0.03)
            except queue.Empty:
                if not started:
                    wave.tick()
                continue
            if item is None:
                break
            if not started:
                wave.clear()
                print(CYAN, end="", flush=True)
                started = True
            if isinstance(item, Exception):
                print(f"{DIM}({item}){RESET}", end="")
                break
            out.append(item)
            pr.feed(item)
    if not started:
        wave.clear()
    pr.close()
    if stopped:
        print(f"{DIM} ...(hushed){RESET}", end="")
        out.append(" ...")
    print(RESET + "\n")
    t.join(timeout=5)
    return "".join(out).strip(), pr


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

    history, prompt, uni = [], "What is thy bidding?", utf8()
    once = " ".join(sys.argv[1:]).strip()
    while True:
        if once:
            q = once
        else:
            try:
                q = input(f"{LILAC}{prompt}{RESET} ").strip()
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
        reply, pr = speak(b, msgs, uni)
        for note in pr.notes:
            try:
                save_note(note)
                print(f"{DIM}  (she noted: {note}){RESET}\n")
            except Exception:
                pass
        prompt = pr.next or "What is thy bidding?"
        history.append({"role": "assistant", "content": reply})
        if once:
            break


if __name__ == "__main__":
    main()
