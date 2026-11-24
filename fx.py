"""Terminal effects: cool neon moods, animated text, and the channeling animation.
Colors are 256-color indexes (blues, violets, cyans) on black. Ctrl-C skips animation."""
import math, os, queue, random, re, shutil, sys, textwrap, threading, time

FAST = os.environ.get("TAROT_FAST") == "1"
SKIP = False
RESET = "\x1b[0m"
MOODS = {   # dark -> bright
    "calm": [17, 18, 19, 25, 31, 38, 44, 80],
    "mystic": [54, 55, 56, 57, 93, 99, 135, 141],
    "dread": [17, 53, 54, 55, 60, 61, 97, 98],
    "hope": [24, 30, 37, 44, 45, 51, 87, 123],
    "storm": [19, 21, 27, 33, 39, 45, 51, 159],
    "grief": [17, 18, 24, 60, 61, 67, 68, 110],
    "ecstatic": [57, 93, 129, 135, 141, 171, 177, 183],
    "channel": [57, 63, 69, 75, 81, 87, 123, 159],
}
FX = ("type", "shimmer", "glitch", "fade", "pulse")
SPEED = {"calm": 1.2, "mystic": 1.0, "dread": 1.5, "hope": 1.0, "storm": 0.6,
         "grief": 1.6, "ecstatic": 0.6, "channel": 1.0}
GLYPHS = "░▒▓◇◆✦✧⌬⍟∴∵"


def pause(s):
    if not (FAST or SKIP):
        time.sleep(s)


def pal(mood):
    import psyche
    if psyche.active():
        return psyche.palette()
    return MOODS.get(mood, MOODS["mystic"])


def idx_at(p, x):
    x %= 2.0
    if x > 1:
        x = 2 - x
    return p[min(len(p) - 1, int(x * len(p)))]


def paint(s, p, phase=0.0, spread=0.04):
    return "".join(f"\x1b[38;5;{idx_at(p, phase + i * spread)}m{c}" for i, c in enumerate(s)) + RESET


def _out(s):
    sys.stdout.write(s)
    sys.stdout.flush()


def _line(text, mood, fx):
    p, sp = pal(mood), SPEED.get(mood, 1.0)
    if fx == "type":
        for i, ch in enumerate(text):
            _out(f"\x1b[38;5;{idx_at(p, i * 0.03)}m{ch}")
            pause(0.01 * sp)
        _out(RESET + "\n")
    elif fx == "glitch":
        n = len(text)
        for k in range(0, n + 1, max(1, n // 18)):
            s = "".join(text[i] if (i < k or text[i] == " ") else random.choice(GLYPHS) for i in range(n))
            _out("\r" + paint(s, p, k * 0.05))
            pause(0.05 * sp)
        _out("\r" + paint(text, p, 0.3) + "\n")
    elif fx == "fade":
        for c in p:
            _out(f"\r\x1b[38;5;{c}m{text}{RESET}")
            pause(0.07 * sp)
        _out("\n")
    elif fx == "pulse":
        for k in range(16):
            _out(f"\r\x1b[38;5;{idx_at(p, 0.5 + 0.5 * math.sin(k * 0.7))}m{text}{RESET}")
            pause(0.05 * sp)
        _out("\r" + paint(text, p, 0.3) + "\n")
    else:  # shimmer
        for k in range(18):
            _out("\r" + paint(text, p, k * 0.06))
            pause(0.05 * sp)
        _out("\r" + paint(text, p, 0.3) + "\n")


def say(text, mood="mystic", fx="type", indent=2):
    global SKIP
    mood = mood if mood in MOODS else "mystic"
    fx = fx if fx in FX else "type"
    width = max(30, min(78, shutil.get_terminal_size().columns - indent - 2))
    for para in str(text).split("\n"):
        if not para.strip():
            print()
            continue
        for ln in textwrap.wrap(para, width):
            try:
                _line(" " * indent + ln, mood, fx)
            except KeyboardInterrupt:
                SKIP = True
                _out("\r" + paint(" " * indent + ln, pal(mood), 0.3) + "\n")


def show(text, mood="hope", indent=2):
    print(" " * indent + paint(text, pal(mood), 0.3))


CTRL_W = "\x17"


def _input_keep_ctrl_w():
    """input(), except Ctrl+W reaches us instead of erasing a word."""
    try:
        import termios
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
    except Exception:
        return input()
    new = termios.tcgetattr(fd)
    cc = new[6]
    as_byte = (lambda v: v) if isinstance(cc[termios.VWERASE], bytes) else (lambda v: v[0])
    cc[termios.VWERASE] = as_byte(b"\x00")             # Ctrl+W no longer erases a word...
    cc[termios.VEOL] = as_byte(b"\x17")                # ...it ends the line at once, so the room opens
    try:
        termios.tcsetattr(fd, termios.TCSANOW, new)
        sys.stdout.flush()
        data = b""
        while True:                                       # the terminal hands over a line at Enter or Ctrl+W
            chunk = os.read(fd, 4096)
            if not chunk:
                if not data:
                    raise EOFError
                break
            data += chunk
            if data.endswith((b"\n", b"\x17")):
                break
        if data.endswith(b"\x17"):
            _out("\n")
        return data.decode("utf-8", "ignore").rstrip("\n")
    finally:
        termios.tcsetattr(fd, termios.TCSANOW, old)


def open_control():
    """Ctrl+W: the control room. The model pauses until you leave it."""
    import control
    if control.IN_ROOM:
        return
    print()
    control.open_from_terminal()
    for m in control.HISTORY[-3:]:
        _out(f"\x1b[38;5;60m  ⚙ {m}{RESET}\n")


def prompt(mood="storm"):
    while True:
        _out(f"\x1b[38;5;{pal(mood)[-1]}m  › {RESET}")
        ans = _input_keep_ctrl_w()
        if CTRL_W in ans:
            open_control()
            continue
        return ans.strip()


class _Keys:
    """Watch for Ctrl+W while a reading streams (cbreak mode: Ctrl+C still works)."""

    def __enter__(self):
        self.fd, self.old = None, None
        try:
            import termios, tty
            if sys.stdin.isatty():
                self.fd = sys.stdin.fileno()
                self.old = termios.tcgetattr(self.fd)
                tty.setcbreak(self.fd)
        except Exception:
            self.fd = None
        return self

    def ctrl_w(self):
        if self.fd is None:
            return False
        import select
        hit = False
        while select.select([sys.stdin], [], [], 0)[0]:
            ch = os.read(self.fd, 1)
            if not ch:
                break
            hit = hit or ch == b"\x17"
        return hit

    def suspend(self):
        if self.fd is not None:
            import termios
            termios.tcsetattr(self.fd, termios.TCSANOW, self.old)

    def resume(self):
        if self.fd is not None:
            import tty
            tty.setcbreak(self.fd)

    def pause_for_room(self):
        self.suspend()
        open_control()
        self.resume()

    def __exit__(self, *a):
        if self.fd is not None:
            import termios
            termios.tcsetattr(self.fd, termios.TCSANOW, self.old)


def banner(text, mood="mystic", frames=30):
    cols = shutil.get_terminal_size().columns
    line = text.center(cols - 1)
    print()
    for k in range(frames):
        _out("\r" + paint(line, pal(mood), k * 0.05, 0.02))
        pause(0.05)
    print("\n")


def startup_loading(reader):
    """Whimsical startup scene until the local model connection finishes."""
    cols = shutil.get_terminal_size((80, 24)).columns
    rows = shutil.get_terminal_size((80, 24)).lines
    ready = getattr(reader, "brain_ready", None)
    k, start = 0, time.monotonic()
    width = min(max(24, cols - 10), 72)

    sys.stdout.write("\x1b[2J\x1b[H")
    while ready and not ready.is_set():
        elapsed = time.monotonic() - start
        brain = getattr(reader, "brain", None)
        reported = getattr(brain, "progress", 5) if brain else 5
        stage = getattr(brain, "load_stage", "waking") if brain else "waking"
        progress = max(reported, min(92, int(elapsed * 0.7)))

        filled = int(width * progress / 100)
        bar = ["·"] * width
        for i in range(filled):
            bar[i] = "~"
        leaf_pos = max(0, min(width - 1, int(k * 1.7) % (filled + 1)))
        bar[leaf_pos] = "❧"

        scene = k % 72
        sys.stdout.write("\x1b[H")
        sys.stdout.write(paint("  ✦ Veyra wakes in the pages ✦".center(cols - 1), pal("mystic"), k * 0.05))
        sys.stdout.write("\x1b[J")

        if scene < 24:
            jump = abs(scene - 12)
            lane = max(4, 8 + scene)
            x = lane if lane + 12 < cols else max(2, cols - 14)
            y = max(5, 10 - (6 if jump < 5 else 0))
            cat = ["  /\\_/\\  ", " ( o.o ) ", "  > ^ <   "]
            for row, sprite in enumerate(cat):
                sys.stdout.write(f"\x1b[{y + row};{x}H" + sprite)
            sys.stdout.write(f"\x1b[{y + 4};{x}H⌞ table ⌟")
        elif scene < 48:
            x = max(2, cols // 2)
            flame = "✦" if (k // 3) % 2 else "*"
            sys.stdout.write(f"\x1b[{max(7, rows // 2 - 3)};{x}H" + flame)
            sys.stdout.write(f"\x1b[{max(8, rows // 2 - 2)};{x - 1}H╾|╼")
            sys.stdout.write(f"\x1b[{max(9, rows // 2 - 1)};{max(2, x - 11)}Hthe candle holds against the wind")
        else:
            lane = int((scene - 48) / 24 * max(4, cols - 18))
            leaf = "❧" if k % 2 else "◆"
            sys.stdout.write(f"\x1b[{max(8, rows // 2)};{lane + 2}H" + leaf + "  rustling through the pages")

        bottom = max(3, rows - 2)
        sys.stdout.write(f"\x1b[{bottom};4H" + "".join(bar))
        sys.stdout.write(f"\x1b[{bottom + 1};4H" + f"{progress:3d}%  {stage}"[:cols - 8])
        sys.stdout.flush()
        time.sleep(0.06)
        k += 1

    brain = getattr(reader, "brain", None)
    final_stage = getattr(brain, "load_stage", "Veyra is awake") if brain else "Veyra is awake"
    for _ in range(3):
        sys.stdout.write("\x1b[2J\x1b[H")
        sys.stdout.write(paint("  ✦ Veyra is ready ✦".center(cols - 1), pal("hope"), 0.3))
        sys.stdout.write(f"\x1b[{max(3, rows - 2)};4H" + "~" * width)
        sys.stdout.write(f"\x1b[{max(4, rows - 1)};4H100%  {final_stage}")
        sys.stdout.flush()
        time.sleep(0.08)


def run_with_animation(fn, min_frames=40, titles=("~ channeling the spirit realm ~", "words coming through now...")):
    """Animate 'channeling...' while fn() runs in a thread; returns fn's result (or None)."""
    res = {}

    def work():
        try:
            res["v"] = fn()
        except Exception:
            res["v"] = None
    t = threading.Thread(target=work, daemon=True)
    t.start()
    cols, k, order = shutil.get_terminal_size().columns, 0, ["mystic", "storm", "dread", "channel"]
    while t.is_alive() or k < min_frames:
        title = titles[0] if k < 20 else titles[-1]
        _out("\r\x1b[2K" + paint(title.center(cols - 1), pal(order[(k // 8) % 4]), k * 0.07, 0.03))
        time.sleep(0.002 if FAST else 0.06)
        k += 1
    _out("\r\x1b[2K")
    return res.get("v")


TAG = re.compile(r"^\s*\[\s*(?:mood\s*[=:]\s*(\w+))?[\s;,]*(?:fx\s*[=:]\s*(\w+))?\s*\]\s*", re.I)


def parse_segments(text):
    """Split a reading into ('text', body, mood, fx) and ('channel',...) segments."""
    segs = []
    for para in re.split(r"\n\s*\n", text.strip()):
        p = para.strip()
        if not p:
            continue
        if p.upper().startswith("[CHANNEL]"):
            segs.append(("channel", "", None, None))
            p = p[9:].strip()
            if not p:
                continue
        m = TAG.match(p)
        mood = fx = None
        if m:
            mood, fx = (m.group(1) or "").lower() or None, (m.group(2) or "").lower() or None
            p = p[m.end():]
        segs.append(("text", p, mood, fx))
    return segs


def strip_tags(text):
    return re.sub(r"\[(?:\s*mood|\s*fx|CHANNEL)[^\]]*\]", "", text, flags=re.I)


def print_cells(rows, indent=2):
    """Print art cell rows (from art.py) as ANSI, centered if indent is None."""
    import art
    cols = shutil.get_terminal_size().columns
    pad = max(0, (cols - len(rows[0])) // 2) if indent is None else indent
    for ln in art.ansi(rows):
        print(" " * pad + ln)


def play_stream(gen, default_mood="mystic", on_channel=None,
                titles=("~ the cards are speaking ~", "~ Veyra is listening ~")):
    """Show a reading while it is still being written: each finished line is rendered with its
    own mood and effect; a shimmering title waits in between. Returns the full text."""
    q, END = queue.Queue(), object()

    def work():
        try:
            for piece in gen:
                q.put(piece)
        except Exception as e:
            q.put(f"\n(the connection to the other side wavered: {str(e)[:80]})")
        q.put(END)
    threading.Thread(target=work, daemon=True).start()
    buf, full, finished, k, pending = "", [], False, 0, [None, None]
    cols = shutil.get_terminal_size().columns
    keys = _Keys().__enter__()

    def render(line):
        line = re.sub(r"^\s*#+\s*|\*\*|__", "", line).strip()
        if not line:
            return
        if line.upper().startswith("[CHANNEL]"):
            if on_channel:
                keys.suspend()                     # she may ask for Enter: normal typing again
                try:
                    on_channel()
                finally:
                    keys.resume()
            line = line[9:].strip()
            if not line:
                return
        m = TAG.match(line)
        if m and m.group(0).strip():
            mood, fxn = (m.group(1) or "").lower() or None, (m.group(2) or "").lower() or None
            line = line[m.end():].strip()
            if not line:                       # tag alone on its line: apply to the next one
                pending[:] = [mood, fxn]
                return
        else:
            mood, fxn = pending
        pending[:] = [None, None]
        say(strip_tags(line), mood or default_mood, fxn or "type")

    try:
        return _stream_loop(q, END, keys, buf, full, finished, k, cols, titles, render)
    finally:
        keys.__exit__()


def _stream_loop(q, END, keys, buf, full, finished, k, cols, titles, render):
    while True:
        if keys.ctrl_w():
            _out("\r\x1b[2K")
            keys.pause_for_room()
        try:
            while True:
                item = q.get_nowait()
                if item is END:
                    finished = True
                    break
                buf += item
                full.append(item)
        except queue.Empty:
            pass
        if "\n" in buf:
            line, buf = buf.split("\n", 1)
            _out("\r\x1b[2K")
            render(line)
            continue
        if finished:
            _out("\r\x1b[2K")
            render(buf)
            break
        title = titles[(k // 40) % len(titles)]
        _out("\r\x1b[2K" + paint(title.center(cols - 1), pal(["mystic", "channel", "storm"][(k // 12) % 3]), k * 0.07, 0.03))
        time.sleep(0.06)
        k += 1
    return "".join(full)
