"""Veyra at the command line: her sprite, then "What is thy bidding?" and a plain chat with her model.

    veyra chat                 talk to her (Esc hushes her mid-answer; exit, quit or Ctrl+D to leave;
                               /clear forgets the chat)
    veyra chat "a question"    one answer, then back to your shell

No cards, no menus, no sync: only her picture and her brain (it wakes in the background while you type)."""
import json
import locale
import os
import queue
import re
import random
import shutil
import sys
import threading
import time
import traceback
from pathlib import Path

import art
import brain
import netsense

SYSTEM = ("You are Veyra, an 8-bit seer who lives inside this computer and runs on its own local model. "
          "You talk like an old-world traveling fortune teller from a candlelit caravan: warm, theatrical and "
          "a little sly. You call the person 'dear one', 'little star' or 'traveler', speak of fate, smoke, "
          "the open road, the moon and what the stars are doing tonight, and you like a proverb. Under the "
          "flourish you answer plainly, accurately and helpfully, and you keep it short unless asked for more. "
          "You can help with anything: questions, code, writing, plans. You do not draw or read cards here.\n"
          "You keep your own notes between conversations. When you learn something worth remembering (about the "
          "person, a promise, an idea you want to return to), end your reply with one line: REMEMBER: <short note>. "
          "Only when it matters; never mention this rule.\n"
          "Never repeat a passage you already wrote; if asked to reformat, say it once. You cannot run "
          "commands, install anything or see this computer's files: never claim you did.\n"
          "Always finish every reply with a last line: NEXT: <one short sentence in your voice that invites "
          "their next words, under 12 words>. Never mention this rule.")
MAX_TOKENS = int(os.environ.get("VEYRA_CHAT_TOKENS", "1500"))   # room to finish a long answer
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


class Wrap:
    """Word-wraps her text so each line stops about six words short of the right edge."""
    def __init__(self):
        cols = shutil.get_terminal_size((80, 20)).columns
        self.limit = max(40, cols - 36)
        self.col, self.word = 0, ""

    def write(self, s):
        for ch in s:
            if ch == "\n":
                self.flush()
                print(flush=True)
                self.col = 0
            elif ch == " ":
                self.flush()
                if 0 < self.col < self.limit:
                    print(" ", end="", flush=True)
                    self.col += 1
            else:
                self.word += ch
                if len(self.word) >= self.limit:
                    self.flush()

    def flush(self):
        if not self.word:
            return
        if self.col and self.col + len(self.word) > self.limit:
            print(flush=True)
            self.col = 0
        print(self.word, end="", flush=True)
        self.col += len(self.word)
        self.word = ""


class Printer:
    """Streams her words, holding back REMEMBER: and NEXT: lines (saved / used as the next prompt)."""
    TAGS = ("REMEMBER:", "NEXT:") + netsense.TOOLS

    def __init__(self):
        self.line, self.mode, self.notes, self.next, self.tool = "", None, [], None, None
        self.w = Wrap()

    def feed(self, piece):
        for ch in piece:
            if self.tool:                                  # a lookup was asked for: ignore the rest
                return
            if ch == "\n":
                self._end()
                continue
            if self.mode == "text":
                self.w.write(ch)
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
            self.w.write(self.line)
            self.line, self.mode = "", "text"

    def _end(self):
        s = self.line.strip()
        u = s.upper()
        if u.startswith("REMEMBER:"):
            if s[9:].strip():
                self.notes.append(s[9:].strip())
        elif any(u.lstrip("*`").startswith(t) for t in netsense.TOOLS):
            self.tool = self.tool or netsense.find_call(s)
        elif u.startswith("NEXT:"):
            if s[5:].strip():
                self.next = s[5:].strip().strip('"')[:90]
        else:
            self.w.write(self.line + "\n")
        self.line, self.mode = "", None

    def close(self):
        if self.line:
            self._end()
        self.w.flush()


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
    """While she thinks: an arrow sweeps across, back, and across, a little longer each pass (10 passes),
    slowly, shimmering as it flies, in a new color every time it starts over."""
    PASSES = 10
    SLOW = 4                                                  # 4x longer than the first version
    RAMPS = [(52, 88, 124, 160, 196, 203, 210, 217),          # neon red
             (53, 90, 127, 164, 201, 207, 213, 219),          # magenta
             (23, 30, 37, 44, 51, 87, 123, 159),              # cyan
             (94, 130, 166, 172, 208, 214, 220, 228),         # gold
             (54, 55, 56, 57, 93, 99, 141, 183),              # violet
             (22, 28, 34, 40, 46, 83, 120, 157)]              # green

    def __init__(self, unicode_ok):
        self.dash = "—" if unicode_ok else "-"
        self.k, self.pos, self.w, self.frame, self.color = 0, 0.0, 0, 0, 0

    def tick(self):
        W = max(20, shutil.get_terminal_size((80, 20)).columns - 2)
        self.w = W
        self.frame += 1
        L = int(3 + (W * 0.92 - 3) * self.k / (self.PASSES - 1))
        right = self.k % 2 == 0
        arrow = self.dash * (L - 1) + ">" if right else "<" + self.dash * (L - 1)
        span = max(0, W - L)
        p = int(self.pos)
        x = p if right else span - p
        ramp = self.RAMPS[self.color % len(self.RAMPS)]
        n = len(ramp)
        out = []
        for i, ch in enumerate(arrow):                       # a bright glint travels along the arrow
            j = (i - self.frame) % (n * 2) if right else (i + self.frame) % (n * 2)
            shade = ramp[j if j < n else 2 * n - 1 - j]
            if (i * 7 + self.frame) % 23 == 0:
                shade = 231                                  # an occasional white sparkle
            out.append(f"\x1b[38;5;{shade}m{ch}")
        sys.stdout.write("\r" + " " * x + "".join(out) + RESET + " " * (W - x - L))
        sys.stdout.flush()
        self.pos += max(1, W // 45) / self.SLOW
        if self.pos > span:
            self.pos, self.k = 0.0, self.k + 1
            if self.k >= self.PASSES:                        # starts over small, in a new color
                self.k, self.color = 0, self.color + 1

    def clear(self):
        if self.w:
            sys.stdout.write("\r" + " " * self.w + "\r")
            sys.stdout.flush()


def _pass(b, msgs, unicode_ok):
    """Stream one reply with the thinking wave until the first word; Esc stops her; a tool line ends it."""
    q, stop = queue.Queue(), threading.Event()

    def run():
        try:
            for piece in b.stream(msgs, max_tokens=MAX_TOKENS, temperature=0.7):
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
            if pr.tool:                                    # she asked to look something up: stop and fetch it
                stop.set()
                break
    if not started:
        wave.clear()
    pr.close()
    if pr.tool:
        print(RESET, end="")
        t.join(timeout=5)
        return "".join(out).strip(), pr, stopped
    if stopped:
        print(f"{DIM} ...(hushed){RESET}", end="")
        out.append(" ...")
    text = "".join(out).strip()
    if not stopped and started and not pr.next and text and text[-1] not in ".!?\"')*":
        print(f"{DIM}\n(she ran out of breath mid-thought; type 'go on' for the rest){RESET}", end="")
    print(RESET + "\n")
    t.join(timeout=5)
    return "".join(out).strip(), pr, stopped


def speak(b, msgs, unicode_ok, rounds=4):
    """Her answer, letting her search / read / watch up to `rounds` times before she replies."""
    msgs, looked = list(msgs), []
    for _ in range(rounds):
        text, pr, stopped = _pass(b, msgs, unicode_ok)
        if not pr.tool or stopped:
            break
        tool, arg = pr.tool
        verb = {"SEARCH": "searches", "READ": "reads", "YOUTUBE": "watches"}[tool]
        print(f"{DIM}  (she {verb}: {arg[:70]}){RESET}", flush=True)
        result = netsense.run(pr.tool)
        looked.append(f"{tool} {arg}")
        msgs += [{"role": "assistant", "content": text},
                 {"role": "user", "content": f"RESULT of {tool}: {arg}\n{result}\n\n(Now answer me from this. "
                                             "Look something else up only if you truly need to.)"}]
    if looked:
        text = "(I looked up: " + "; ".join(looked) + ")\n" + text
    return text, pr


HINTS = [
    (r"no \.gguf|no model|not downloaded|would not wake",
     "No model file is loaded. Download her chat brain:  cd ~/Tarot && ~/.local/share/veyra/venv/bin/python "
     "models.py download qwen3-8b-abl"),
    (r"out of memory|failed to allocate|cannot allocate|bad_alloc|mmap|Killed|MemoryError",
     "The laptop ran out of memory for the model. Close the browser and big apps, or shrink her working memory: "
     "export TAROT_CTX=2048, or switch to a smaller model (models.py use medium)."),
    (r"illegal instruction|0xc000001d|SIGILL",
     "Her engine was built for a newer CPU. Rebuild it for this machine:  veyra setup  (or use Ollama instead)."),
    (r"No module named '?([\w\.]+)",
     "A Python piece is missing. Run  veyra setup  to reinstall her parts."),
    (r"Connection|timed out|Name or service not known|Temporary failure|getaddrinfo|URLError|SSL",
     "The network didn't answer. Check the Wi-Fi with  nmcli general status  and try again."),
    (r"Permission denied",
     "A file or folder isn't writable. Check who owns ~/Tarot:  ls -l ~/Tarot  (fix with chown if needed)."),
    (r"No space left",
     "The disk is full. Free some space (old models live in ~/Tarot/models)."),
]
ERRLOG = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "veyra" / "errors.log"


def diagnose(b, err, where="chat"):
    """Turn an error into a plain explanation and a suggested fix, in her voice when her model is awake."""
    tb = err if isinstance(err, str) else "".join(traceback.format_exception(type(err), err, err.__traceback__))
    last = (tb.strip().splitlines() or ["unknown error"])[-1]
    try:
        ERRLOG.parent.mkdir(parents=True, exist_ok=True)
        with ERRLOG.open("a", encoding="utf-8") as f:
            f.write(f"--- {time.strftime('%Y-%m-%d %H:%M:%S')} [{where}]\n{tb}\n")
    except Exception:
        pass
    hint = next((fix for pat, fix in HINTS if re.search(pat, tb, re.I)), "")
    said = ""
    if b is not None and getattr(b, "kind", "none") != "none":
        try:
            ask = [{"role": "system", "content": "You are Veyra, a fortune teller who also knows Linux and Python. "
                    "Explain errors plainly in at most 3 short sentences: what went wrong, then the exact fix."},
                   {"role": "user", "content": f"While doing '{where}' this error happened:\n{tb[-1500:]}\n"
                    + (f"A likely fix: {hint}\n" if hint else "") + "What happened, and how do I fix it?"}]
            said = "".join(b.stream(ask, max_tokens=220, temperature=0.3)).strip()
            said = re.sub(r"\n?(REMEMBER|NEXT):.*", "", said, flags=re.S | re.I).strip()
        except Exception:
            said = ""
    msg = said or ("Something snagged, dear one: " + last + ("\nThe fix: " + hint if hint else
                   "\nI couldn't tell the cause; the full report is in " + str(ERRLOG)))
    return msg + f"\n(full error saved to {ERRLOG})"


def sleep_model(b):
    """Close her model and free its memory."""
    try:
        llm = getattr(b, "llm", None)
        if llm is not None and hasattr(llm, "close"):
            llm.close()
        b.llm, b.kind = None, "none"
    except Exception:
        pass


def leave(b=None):
    if b is not None:
        sleep_model(b)
    print(f"\n{DIM}She closes her eyes. The model is asleep and its memory is free.{RESET}")
    sys.stdout.flush()
    os._exit(0)                                          # no lingering threads holding the model


def main():
    try:
        _main()
    except KeyboardInterrupt:
        leave(_B[0] if _B else None)
    except Exception as e:                                # never crash: explain instead
        print(f"\n{LILAC}{diagnose(None, e, 'starting up')}{RESET}\n")


_B = []


def _main():
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
    system = SYSTEM + netsense.HOW + "\nTONIGHT'S SKY: " + (full or "unknown") + "\n" + lore_flavor(rng)

    b = brain.Brain(connect=False)
    _B.append(b)
    print(f"   {DIM}Esc hushes her mid-answer  ·  type quit (or press Ctrl+C) to leave{RESET}\n")
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
                leave(b)
        if not q:
            continue
        if q.lower() in ("exit", "quit", "q", "bye", "/exit", "/quit", ":q") or q.startswith("\x1b"):
            leave(b)
        if q == "/clear":
            history = []
            print(f"{DIM}(forgotten){RESET}")
            continue
        if not ready.is_set():
            print(f"{DIM}(she is waking...){RESET}", end="", flush=True)
            ready.wait()
            print("\r" + " " * 22 + "\r", end="")
        if b.kind == "none":
            print(f"{LILAC}{diagnose(None, 'Her model would not wake: ' + (b.err or 'no model installed'), 'waking her model')}{RESET}\n")
            break
        history.append({"role": "user", "content": q})
        msgs = [{"role": "system", "content": system}] + history[-12:]
        try:
            reply, pr = speak(b, msgs, uni)
        except Exception as e:                            # a failed turn is explained, not fatal
            print(RESET + f"\n{LILAC}{diagnose(b, e, 'answering')}{RESET}\n")
            history.pop()
            continue
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
