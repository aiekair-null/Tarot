"""Psilocybin mode and the wiring room.

- Psilocybin mode (TAROT_PSY=1): rainbow palettes, melting animated cards, and every meaning
  passes through one more random generator, the psyche's dissociate() function, before it is shown.
- Videos made in this mode become fast-cut trips: flashes of quotes, an 8-bit crowd standing
  around confused, back to the words, then cuts of lines saved as interesting.
- The wiring room (python3 tarot.py wires, or Ctrl+W anywhere: it is the control room's Wiring page): every setting, key name and secret on one screen,
  all wired into one core and run through the gauges for tokens, words, temperature and psyche.
Settings you change there are kept in veyra_config.json (git-ignored; secrets never leave the codespace).
"""
import json, math, os, random, re, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONFIG = HERE / "veyra_config.json"
FORCE = None          # True/False overrides the setting (the video renderer uses this)
CLOCK = None          # video time while rendering; None = the wall clock

RAINBOW = [196, 202, 208, 214, 220, 226, 190, 154, 118, 82, 46, 48, 50, 51, 45, 39, 33, 27,
           21, 57, 93, 129, 165, 201, 200, 199, 198, 197]
DARK = {0, 16, 232, 233, 234, 235, 236}


# ------------------------------------------------------------------ settings
# (env name, label, secret?, default, needs restart?, note)
KNOBS = [
    ("TAROT_PSY", "Psilocybin mode", False, "0", False, "1 = on, 0 = off"),
    ("TAROT_PSY_LEVEL", "Dissociation", False, "0.45", False, "0.0 calm ... 1.0 gone"),
    ("TAROT_TEMP", "Temperature", False, "0.8", False, "model creativity, 0.1-1.5"),
    ("TAROT_BACKEND", "Brain backend", False, "auto", True, "auto / llama / ollama / openai"),
    ("TAROT_MODEL", "Model name", False, "", True, "for ollama / openai backends"),
    ("TAROT_GGUF", "GGUF file", False, "", True, "path to a local model file"),
    ("TAROT_CTX", "Context size", False, "8192", True, "tokens the model can hold"),
    ("TAROT_THREADS", "CPU threads", False, "", True, "blank = all cores"),
    ("TAROT_WAIT_LIMIT", "Wait limit (s)", False, "20", True, "before the waiting room"),
    ("TAROT_FALL_CHANCE", "Fall chance", False, "0.36", True, "live reading: card falls"),
    ("TAROT_PAIR_CHANCE", "Pair chance", False, "0.14", True, "live reading: two fall"),
    ("TAROT_LOCAL_URL", "Local API URL", False, "", True, "openai-style server"),
    ("HF_TOKEN", "Hugging Face key", True, "", True, "secret"),
    ("FB_PAGE_ID", "Facebook Page id", False, "", False, "for uploads"),
    ("FB_PAGE_TOKEN", "Facebook token", True, "", False, "secret"),
    ("ANTHROPIC_API_KEY", "Anthropic key", True, "", False, "secret; last-resort helper only, asks first"),
]


def _read_config():
    try:
        return json.loads(CONFIG.read_text())
    except Exception:
        return {}


def load_config():
    """Apply veyra_config.json to the environment (call before anything reads os.environ)."""
    for k, v in _read_config().items():
        if v not in (None, ""):
            os.environ[k] = str(v)


def set_value(key, value):
    cfg = _read_config()
    if value in (None, ""):
        cfg.pop(key, None)
        os.environ.pop(key, None)
    else:
        cfg[key] = str(value)
        os.environ[key] = str(value)
    CONFIG.write_text(json.dumps(cfg, indent=2))
    try:
        os.chmod(CONFIG, 0o600)
    except OSError:
        pass


def mask(v):
    v = v or ""
    if not v:
        return "(not set)"
    if len(v) <= 8:
        return "•" * len(v)
    return v[:3] + "••••" + v[-4:]


def active():
    return FORCE if FORCE is not None else os.environ.get("TAROT_PSY", "0") == "1"


def toggle():
    set_value("TAROT_PSY", "0" if active() else "1")
    return active()


def level():
    try:
        return max(0.0, min(1.0, float(os.environ.get("TAROT_PSY_LEVEL", "0.45"))))
    except ValueError:
        return 0.45


def temperature():
    try:
        return max(0.05, min(2.0, float(os.environ.get("TAROT_TEMP", "0.8"))))
    except ValueError:
        return 0.8


def now():
    return CLOCK if CLOCK is not None else time.time()


# ------------------------------------------------------------------ colour
def palette():
    """A rainbow that keeps rotating: every mood becomes the trip."""
    k = int(now() * 6) % len(RAINBOW)
    return RAINBOW[k:] + RAINBOW[:k]


def recolor(fg, x, y, t):
    if fg in DARK:
        return fg
    return RAINBOW[(x + y * 2 + int(t * 10)) % len(RAINBOW)]


def wave(row, t):
    """How far a row of a card slides sideways: the art melts and breathes."""
    return int(round(math.sin(t * 2.6 + row * 0.55) * 1.4))


# ------------------------------------------------------------------ the dissociate function
ASIDES = ["(the room breathes)", "(the colours are talking again)", "— who shuffled the floor?",
          "(she forgets which hand holds the deck)", "(time folds in half)", "(the cards hum)",
          "— or was that a dream?", "(everything is fine, and also melting)", "(the candle laughs)",
          "— the walls nod along", "(a second Veyra watches from the corner)"]
_POOL = []


def _protected(spread):
    out = []
    for c, _ in spread or []:
        out += [c.lower(), re.sub(r"^the\s+", "", c.lower())]
    return [n for n in out if n]


def dissociate(line, spread=(), rng=None, lvl=None):
    """One more random generator: scramble clauses, echo, splice fragments from other meanings,
    drift off into asides. Card names, positions and orientation are never touched."""
    rng = rng or random.SystemRandom()
    lvl = level() if lvl is None else lvl
    m = re.match(r"\s*\[[^\]]*\]\s*", line)
    head, body = (line[:m.end()], line[m.end():]) if m else ("", line)
    if len(body.strip()) < 20 or lvl <= 0:
        return line
    names = _protected(spread)
    out = []
    for s in re.split(r"(?<=[.!?])\s+", body.strip()):
        safe = not any(n in s.lower() for n in names)
        if safe and rng.random() < lvl:
            parts = [p for p in re.split(r",\s*|;\s*|\s+—\s+|\s+-\s+", s.rstrip(".!?")) if p]
            if len(parts) > 1:
                _POOL.extend(parts[1:])
                rng.shuffle(parts)
                s = rng.choice([", ", " … ", " — "]).join(parts) + "."
        if safe and _POOL and rng.random() < lvl * 0.4:
            frag = rng.choice(_POOL).strip()
            s = s.rstrip(".!?") + " … " + frag[:1].lower() + frag[1:] + "."
        if rng.random() < lvl * 0.45:
            words = re.findall(r"[A-Za-z']+", s)
            if len(words) >= 2:
                echo = " ".join(words[-2:]).lower()
                s = s.rstrip(".!?") + f"... {echo}... {echo}."
        if rng.random() < lvl * 0.35:
            s += " " + rng.choice(ASIDES)
        out.append(s)
    del _POOL[:-40]
    return head + " ".join(out)


# ------------------------------------------------------------------ lines worth keeping for the video
VIVID = re.compile(r"\b(dream|fire|storm|heart|shadow|light|door|river|moon|sun|blood|bone|wing|road|"
                   r"ocean|crown|key|mirror|wolf|star|ghost|spirit|burn|break|bloom|rise|fall)", re.I)


def interesting(text, spread=(), n=8):
    """The lines worth flashing on screen, kept in reading order."""
    clean = re.sub(r"\[[^\]]*\]", "", text or "")
    sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+", clean) if s.strip()]
    names = _protected(spread)
    scored = []
    for i, s in enumerate(sents):
        L = len(s)
        if L < 25 or L > 190:
            continue
        sc = (2 if any(nm in s.lower() for nm in names) else 0) + (2 if s.endswith("?") else 0)
        sc += 1.5 * min(2, len(VIVID.findall(s))) + (1 if 40 <= L <= 140 else 0)
        sc += 1.5 if "(" in s or "…" in s else 0          # the psyche's own drift
        scored.append((sc, i, s))
    best = sorted(sorted(scored, reverse=True)[:n], key=lambda x: x[1])
    return [s for _, _, s in best]


# ------------------------------------------------------------------ the video trip
def trip_script(scenes, sess, rng=None):
    """Re-cut a reading's scenes: quote flashes -> confused crowd -> the words -> interesting cuts."""
    rng = rng or random.Random(hash(sess.get("date", "")) & 0xFFFF)
    heard = " ".join(e.get("text", "") for e in (sess.get("falls") or {}).get("log", []))
    quotes = sess.get("interesting") or interesting(sess.get("reading", "") + " " + heard, sess.get("spread"))
    if not quotes:
        quotes = [l for sc in scenes for l in sc.get("lines", [])][:8]
    frags = []
    for q in quotes:
        words = q.split()
        for k in range(0, len(words), 5):
            frags.append(" ".join(words[k:k + 5]))
    spread = sess.get("spread") or []
    n = [0]

    def flash(text, kind="text", card=None, d=None):
        n[0] += 1
        return {"name": f"flash{n[0]}", "lines": [], "flash": text, "kind": kind, "cardref": card,
                "dur_hint": d or rng.uniform(0.3, 0.75), "seed": rng.randrange(1 << 30)}

    by = {s["name"]: s for s in scenes}
    out = [by["intro"]] if "intro" in by else []
    out += [flash(f) for f in rng.sample(frags, min(14, len(frags)))]
    out.append({"name": "crowd", "lines": ["Wait... what just happened?"], "seed": rng.randrange(1 << 30)})
    body = [s for s in scenes if s["name"] not in ("intro", "end", "interview", "spirits")]
    cuts = quotes[:]
    rng.shuffle(cuts)
    k = 0
    for s in body:
        out.append(s)
        if s["name"].startswith(("card", "read")) and cuts:
            for _ in range(rng.choice((2, 3))):
                c = rng.randrange(len(spread)) if spread else None
                out.append(flash(cuts[k % len(cuts)], "card" if c is not None and rng.random() < 0.5 else "text", c,
                                 rng.uniform(0.6, 1.1)))
                k += 1
    out.append({"name": "crowd_b", "lines": [], "seed": rng.randrange(1 << 30)})
    out += [flash(f, d=0.25) for f in rng.sample(frags, min(6, len(frags)))]
    if "end" in by:
        out.append(by["end"])
    return out


def scene_time(sc, speech):
    """(duration, voice lead) for the trip's own scenes, or None."""
    if sc["name"].startswith("flash"):
        return sc["dur_hint"], 0
    if sc["name"] == "crowd":
        return max(3.0, speech + 1.2), 0.5
    if sc["name"] == "crowd_b":
        return 1.6, 0
    return None


def draw_flash(ui, sc, local):
    import art, fx
    rng = random.Random(sc["seed"])
    ui.scr.erase()
    for _ in range(int(ui.w * ui.h * 0.06)):                       # static noise
        ui.put(rng.randrange(ui.h), rng.randrange(ui.w - 1), rng.choice(fx.GLYPHS),
               ui.attr(rng.choice(RAINBOW)))
    text = sc["flash"]
    if sc.get("kind") == "card" and sc.get("cardref") is not None:
        c, r = ui._psy_spread[sc["cardref"]]
        rows = art.card_cells(c, bool(r), 22, 15)
        ui.cells(max(0, ui.h // 2 - 12), (ui.w - 22) // 2 + rng.randint(-3, 3), rows)
        y = ui.h // 2 + 5
    else:
        y = ui.h // 2 - 2 + rng.randint(-3, 3)
    if sc.get("kind") != "card":            # the quote itself rides in the big caption boxes
        ui.gcenter(y, rng.choice(["✦", "◇", "∴", "⍟"]) * rng.randint(3, 9), local * 4)


PERSON = ["  ▄▄▄  ", " ▐{e}▌ ", "  ▀█▀  ", " ▐███▌ ", " ▐███▌ ", "  █ █  ", "  ▀ ▀  "]


def draw_crowd(ui, sc, local):
    """Everyone standing around, confused."""
    rng = random.Random(sc["seed"])
    ui.scr.erase()
    ui.stars(30)
    n = max(4, min(8, ui.w // 10))
    gap = ui.w // (n + 1)
    base = ui.h // 2 - 2
    skins = [223, 180, 137, 94, 216, 230]
    shirts = rng.sample(RAINBOW, n)
    for i in range(n):
        x = gap * (i + 1) - 3
        look = int(local * 2 + i * 0.7) % 3
        eyes = ["•  •", " •• ", "  ••"][look] if (int(local * 6) + i) % 9 else "-  -"
        bob = int(math.sin(local * 3 + i) > 0.6)
        for j, row in enumerate(PERSON):
            col = skins[i % len(skins)] if j < 3 else (shirts[i] if j < 5 else 60)
            ui.put(base + j - bob, x, row.format(e=eyes), ui.attr(col))
        if (int(local * 2.5) + i) % 3 == 0:
            ui.put(base - 2 - bob, x + 3 + (i % 2), "?", ui.attr(226, 16, True))
        if (int(local * 2.5) + i) % 5 == 1:
            ui.put(base - 2, x + 1, "??", ui.attr(213, 16, True))
    ui.gcenter(base + 10, "…" if sc["name"] == "crowd_b" else "everyone stands around, confused", local)


def trip_frame(arr, t, cut=False):
    """Whole-frame trip for the video: hue drifting, colour channels pulling apart, a flash on cuts."""
    import numpy as np
    a = arr.astype(np.float32)
    ang = t * 1.3
    c, s = math.cos(ang), math.sin(ang)
    k = 1 / 3.0
    sq = math.sqrt(k)
    m = np.array([[c + (1 - c) * k, k * (1 - c) - sq * s, k * (1 - c) + sq * s],
                  [k * (1 - c) + sq * s, c + k * (1 - c), k * (1 - c) - sq * s],
                  [k * (1 - c) - sq * s, k * (1 - c) + sq * s, c + k * (1 - c)]], np.float32)
    a = a.reshape(-1, 3) @ m.T
    a = a.reshape(arr.shape)
    sh = int(8 * math.sin(t * 2.2))
    if sh:
        a[..., 0] = np.roll(a[..., 0], sh, axis=1)
        a[..., 2] = np.roll(a[..., 2], -sh, axis=1)
    if cut:
        a = 255 - a
    return np.clip(a, 0, 255).astype(np.uint8)


# ------------------------------------------------------------------ the wiring room
def _gauges():
    mem_path = Path(os.environ.get("TAROT_MEMORY", "memory.json"))
    g = {}
    try:
        g = json.loads(mem_path.read_text()).get("gen", {})
    except Exception:
        pass
    toks = [v for k, v in g.items() if k.endswith("_tokens")]
    words = 0
    try:
        sess = sorted(Path(os.environ.get("TAROT_SESSIONS", "sessions")).glob("*.json"))[-1]
        words = len(re.sub(r"\[[^\]]*\]", "", json.loads(sess.read_text()).get("reading", "")).split())
    except Exception:
        pass
    return [("TOKENS/s", float(g.get("rate", 0)), 20.0, f"{g.get('rate', 0):.1f}"),
            ("TOKENS", float(max(toks) if toks else 0), 1400.0, f"{int(max(toks)) if toks else 0}"),
            ("WORDS", float(words), 1200.0, str(words)),
            ("TEMP", temperature(), 1.5, f"{temperature():.2f}"),
            ("PSYCHE", level() if active() else 0.0, 1.0, f"{level():.2f}" if active() else "off"),
            ("MOON", *_moon())]


def _moon():
    try:
        import astro
        s = astro.today()
        return float(s["lit"]), 1.0, f"{int(s['lit'] * 100)}% {s['bodies']['Moon']['sign'][:3]}"
    except Exception:
        return 0.0, 1.0, "?"


def draw_wires(ui, sel, t, top=2, bottom=3):
    """The wiring page: every setting wired into the core, then down through the gauges."""
    lw = min(40, max(24, ui.w // 2 - 6))
    bus = lw + 3
    rows = max(1, min(len(KNOBS), ui.h - top - bottom))
    first = max(0, min(sel - rows + 1, len(KNOBS) - rows))
    shown = KNOBS[first:first + rows]
    for j, (key, label, secret, default, restart, note) in enumerate(shown):
        y, i = top + j, first + j
        raw = os.environ.get(key, "")
        val = mask(raw) if secret else (raw or (f"({default})" if default else "(not set)"))
        hot = i == sel
        line = f"{'▶' if hot else '◉'} {label[:16]:<16} {val}"[:lw - 1]
        ui.text(y, 1, line, 231 if hot else (213 if secret else 117), hot)
        for x in range(len(line) + 2, bus):                         # the wire to the core
            ui.put(y, x, "─", ui.attr(60))
        p = len(line) + 2 + int((t * 9 + i * 3) % max(1, bus - len(line) - 2))
        ui.put(y, p, "●", ui.attr(RAINBOW[(i * 3 + int(t * 8)) % len(RAINBOW)], 16, True))
        ui.put(y, bus, "╋" if j not in (0, len(shown) - 1) else ("┳" if j == 0 else "┻"), ui.attr(141, 16, True))
    mid = top + len(shown) // 2
    core = " VEYRA CORE "
    ui.glow(mid, bus + 1, "═" * 2 + core + "═" * 2)
    gx = bus + len(core) + 6
    gw = max(10, ui.w - gx - 16)
    gauges = _gauges()
    gy = [top + 1 + k * max(2, (len(shown) - 1) // max(1, len(gauges) - 1)) for k in range(len(gauges))]
    rail = gx - 2
    for y in range(min(mid, gy[0]), max(gy[-1], mid) + 1):
        ui.put(y, rail, "┃", ui.attr(98))
    flow = int((t * 10) % max(1, gy[-1] - gy[0] + 1)) + gy[0]
    ui.put(flow, rail, "◆", ui.attr(226, 16, True))
    for k, (name, v, vmax, label) in enumerate(gauges):
        y = gy[k]
        ui.put(y, rail, "┣", ui.attr(98))
        ui.put(y, rail + 1, "━", ui.attr(98))
        r = max(0.0, min(1.0, v / vmax)) if vmax else 0
        fill = int(r * gw)
        ui.text(y, gx, f"{name:<9}", 189, True)
        for x in range(gw):
            col = [27, 33, 45, 51, 49, 154, 226, 214, 202, 196][min(9, int(x / max(1, gw) * 10))]
            ui.put(y, gx + 9 + x, "█" if x < fill else "░", ui.attr(col if x < fill else 237))
        ui.text(y, gx + 10 + gw, label, 231)
    k, label, secret, default, restart, note = KNOBS[sel]
    ui.text(ui.h - bottom - 1 if bottom > 3 else ui.h - 3, 1,
            f"{k}: {note}" + ("  (applies after restart)" if restart else ""), 103)


def edit_knob(scr, ui, sel, y=None):
    """Ask for a new value for one wire. Returns a short status message."""
    import curses
    key, label, secret, *_ = KNOBS[sel]
    y = ui.h - 2 if y is None else y
    ask = f"new {label} ({'typing hidden, ' if secret else ''}Enter keeps, '-' clears): "
    scr.move(y, 0)
    scr.clrtoeol()
    scr.addstr(y, 1, ask[: ui.w - 2])
    scr.timeout(-1)
    (curses.noecho if secret else curses.echo)()
    try:
        curses.curs_set(1)
    except curses.error:
        pass
    try:
        v = scr.getstr(y, min(ui.w - 2, len(ask) + 1), 300).decode("utf-8", "ignore").strip()
    finally:
        curses.noecho()
        try:
            curses.curs_set(0)
        except curses.error:
            pass
        scr.timeout(70)
    if v == "-":
        set_value(key, "")
        return f"{label} cleared"
    if v:
        set_value(key, v)
        return f"{label} saved" + (" (masked)" if secret else "")
    return f"{label} unchanged"


def wiring_room(scr):
    """The wiring room now lives inside the control room (its Wiring page)."""
    import control
    control.room(scr, page="wires")
