"""Terminal effects: cool neon moods, animated text, and the channeling animation.
Colors are 256-color indexes (blues, violets, cyans) on black. Ctrl-C skips animation."""
import math, os, random, re, shutil, sys, textwrap, threading, time

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


def prompt(mood="storm"):
    _out(f"\x1b[38;5;{pal(mood)[-1]}m  › {RESET}")
    return input().strip()


def banner(text, mood="mystic", frames=30):
    cols = shutil.get_terminal_size().columns
    line = text.center(cols - 1)
    print()
    for k in range(frames):
        _out("\r" + paint(line, pal(mood), k * 0.05, 0.02))
        pause(0.05)
    print("\n")


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


TAG = re.compile(r"^\s*\[(?:mood=(\w+))?[\s;,]*(?:fx=(\w+))?\]\s*", re.I)


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
    return re.sub(r"\[(?:mood=|fx=|CHANNEL)[^\]]*\]", "", text, flags=re.I)
