"""The control room: Ctrl+W from anywhere in Veyra.

Pressing Ctrl+W pauses the model at its next token and opens this room. Three pages share one
command window at the bottom:

  1 DIALS     every tunable knob of the network as a dial you tick left or right, the layer
              switches, and the spectrum (steady <-> wild) that decides which layers can be tuned
  2 WORDS     the words she has just written, each drawn as bright or dim as you have set it;
              tick a word up to lean her toward it, down to steer her away from it
  3 WIRING    every setting, key name and secret wired into her core (the old wiring room)

The command window is the service agent. Tell it what you want changed in plain words. It tries,
in this order, and stops at the first that works:
  1. its own rules (temperature, top-p, "less repetitive", "brighten moon", "turn off psyche"...)
  2. the local model, asked to turn your words into settings (and again more strictly if needed)
  3. fuzzy matching of your words against every dial, switch and word
  4. only if all of that failed, and only after you say yes: the Anthropic API (needs a key)
Requests the model should hear as instructions ("talk more about the moon") are passed to her
as an operator note in every prompt until you clear them.
Everything is saved in veyra_config.json with the other settings.
"""
import difflib, json, math, os, re, threading, time

import psyche

# ------------------------------------------------------------------ pause gate
_RUN = threading.Event()
_RUN.set()
_LOCK = threading.Lock()
RECENT = []                      # recent pieces of text the model wrote (for the WORDS page)
QUEUED = []                      # requests waiting for the model to be free


def paused():
    return not _RUN.is_set()


def pause():
    _RUN.clear()


def resume():
    _RUN.set()


def gate():
    """Called between tokens: holds generation while the control room is open."""
    _RUN.wait()


def saw(piece):
    with _LOCK:
        RECENT.append(piece)
        text = "".join(RECENT)
        if len(text) > 6000:
            RECENT[:] = [text[-4000:]]


# ------------------------------------------------------------------ dials, layers and the spectrum
# key: (label, low, high, step, default, layer, note)
DIALS = {
    "TAROT_SPECTRUM": ("Spectrum", 0.0, 1.0, 0.05, 0.5, None, "steady <-> wild: which layers can be tuned"),
    "TAROT_TEMP": ("Temperature", 0.05, 1.5, 0.05, 0.8, "sampling", "how freely she picks each next token"),
    "TAROT_TOP_P": ("Top-p", 0.1, 1.0, 0.05, 0.95, "sampling", "share of likely tokens she considers"),
    "TAROT_TOP_K": ("Top-k", 1, 200, 5, 40, "sampling", "how many candidate tokens she considers"),
    "TAROT_MIN_P": ("Min-p", 0.0, 0.3, 0.01, 0.05, "sampling", "drop tokens below this share of the best"),
    "TAROT_REPEAT": ("Repeat penalty", 1.0, 1.6, 0.02, 1.12, "repetition", "pushes her off words she just used"),
    "TAROT_PRESENCE": ("Presence", -1.0, 1.5, 0.1, 0.0, "repetition", "new topics vs staying on topic"),
    "TAROT_FREQUENCY": ("Frequency", -1.0, 1.5, 0.1, 0.0, "repetition", "penalty grows each time a word repeats"),
    "TAROT_LENGTH": ("Length", 0.4, 2.0, 0.1, 1.0, "context", "how long her answers may run (x)"),
    "TAROT_WORD_GAIN": ("Word gain", 0.0, 2.0, 0.1, 1.0, "vocab", "how hard word brightness pushes"),
    "TAROT_PSY_LEVEL": ("Dissociation", 0.0, 1.0, 0.05, 0.45, "psyche", "psilocybin mode: how far she drifts"),
}
# layer: (label, spectrum band where it can be tuned)
LAYERS = {
    "sampling": ("SAMPLING", 0.0, 1.0),
    "repetition": ("REPETITION", 0.0, 0.75),
    "context": ("CONTEXT", 0.0, 0.55),
    "vocab": ("VOCAB", 0.25, 1.0),
    "psyche": ("PSYCHE", 0.6, 1.0),
}
WORD_MIN, WORD_MAX = -5, 5


def value(key):
    label, lo, hi, step, default, layer, note = DIALS[key]
    try:
        v = float(os.environ.get(key, default))
    except ValueError:
        v = default
    return max(lo, min(hi, v))


def spectrum():
    return value("TAROT_SPECTRUM")


def switch_on(layer):
    return os.environ.get("TAROT_LAYER_" + layer.upper(), "1") != "0"


def in_band(layer, s=None):
    _, lo, hi = LAYERS[layer]
    s = spectrum() if s is None else s
    return lo - 1e-9 <= s <= hi + 1e-9


def live(layer):
    """A layer can be tuned (and its settings reach the model) when its switch is on and the
    spectrum sits inside its band."""
    return layer is None or (switch_on(layer) and in_band(layer))


def set_dial(key, v, snap=False):
    label, lo, hi, step, default, layer, note = DIALS[key]
    v = max(lo, min(hi, float(v)))
    v = round(round((v - lo) / step) * step + lo, 4) if snap else round(v, 4)
    psyche.set_value(key, f"{v:g}")
    return v


def tick(key, n):
    label, lo, hi, step, *_ = DIALS[key]
    return set_dial(key, value(key) + n * step, snap=True)


def set_switch(layer, on):
    psyche.set_value("TAROT_LAYER_" + layer.upper(), "1" if on else "0")


def words():
    try:
        return {k: int(v) for k, v in json.loads(os.environ.get("TAROT_WORD_BIAS", "{}")).items()}
    except Exception:
        return {}


def set_word(word, level):
    w = words()
    word = word.strip().lower()
    level = max(WORD_MIN, min(WORD_MAX, int(level)))
    if level == 0:
        w.pop(word, None)
    else:
        w[word] = level
    psyche.set_value("TAROT_WORD_BIAS", json.dumps(w) if w else "")
    return level


def notes():
    try:
        return list(json.loads(os.environ.get("TAROT_NOTES", "[]")))
    except Exception:
        return []


def add_note(n):
    ns = (notes() + [n.strip()])[-5:]
    psyche.set_value("TAROT_NOTES", json.dumps(ns))


def clear_notes():
    psyche.set_value("TAROT_NOTES", "")


# ------------------------------------------------------------------ what reaches the model
def sampling(kind):
    """Extra generation settings for brain.stream, for one backend kind."""
    out = {}
    if live("sampling"):
        out["top_p"] = value("TAROT_TOP_P")
        if kind == "llama":
            out["top_k"] = int(value("TAROT_TOP_K"))
            out["min_p"] = value("TAROT_MIN_P")
    if live("repetition"):
        if kind == "llama":
            out["repeat_penalty"] = value("TAROT_REPEAT")
        out["presence_penalty"] = value("TAROT_PRESENCE")
        out["frequency_penalty"] = value("TAROT_FREQUENCY")
    elif kind == "llama":
        out["repeat_penalty"] = 1.12
    return out


def max_tokens(n):
    return max(8, int(n * value("TAROT_LENGTH"))) if live("context") and n > 40 else n


def logit_bias(tokenize):
    """{token id: bias} for the llama backend: brighter words are pushed up, dimmer ones down."""
    if not live("vocab"):
        return {}
    gain, out = value("TAROT_WORD_GAIN"), {}
    for w, lvl in words().items():
        for form in (w, " " + w, w.capitalize(), " " + w.capitalize()):
            try:
                ids = tokenize(form.encode(), add_bos=False)
            except TypeError:
                ids = tokenize(form.encode())
            except Exception:
                continue
            if ids:
                out[ids[0]] = max(-100.0, min(100.0, lvl * 1.6 * gain if lvl > 0 else lvl * 3.0 * gain))
    return out


def operator_note():
    """Text added to the system prompt: the steering notes, and word brightness for backends
    that cannot take a logit bias."""
    parts = []
    if live("vocab"):
        up = [w for w, l in sorted(words().items(), key=lambda x: -x[1]) if l > 0]
        down = [w for w, l in sorted(words().items(), key=lambda x: x[1]) if l < 0]
        if up:
            parts.append("Lean toward these words where they fit naturally: " + ", ".join(up) + ".")
        if down:
            parts.append("Avoid these words: " + ", ".join(down) + ".")
    ns = notes()
    if ns:
        parts.append("Operator notes: " + " ".join(n.rstrip(".") + "." for n in ns))
    return ("\n\n[Operator tuning]\n" + "\n".join(parts)) if parts else ""


# ------------------------------------------------------------------ the service agent
NAMES = {
    "TAROT_TEMP": ("temperature", "temp", "heat"), "TAROT_TOP_P": ("top p", "top-p", "topp", "nucleus"),
    "TAROT_TOP_K": ("top k", "top-k", "topk"), "TAROT_MIN_P": ("min p", "min-p", "minp"),
    "TAROT_REPEAT": ("repeat penalty", "repeat", "repetition penalty"), "TAROT_PRESENCE": ("presence",),
    "TAROT_FREQUENCY": ("frequency",), "TAROT_LENGTH": ("length", "max tokens"),
    "TAROT_WORD_GAIN": ("word gain", "gain"), "TAROT_PSY_LEVEL": ("dissociation", "psyche level", "trip level"),
    "TAROT_SPECTRUM": ("spectrum",),
}
NUDGES = [
    (r"\b(warmer|hotter|more creative|wilder|more random|looser)\b", "TAROT_TEMP", +2),
    (r"\b(cooler|colder|calmer|more focused|less random|tighter|steadier)\b", "TAROT_TEMP", -2),
    (r"\b(less repetitive|stop repeating|repeats? (too much|herself))\b", "TAROT_REPEAT", +2),
    (r"\b(longer|more detail|say more)\b", "TAROT_LENGTH", +2),
    (r"\b(shorter|briefer|less detail|say less)\b", "TAROT_LENGTH", -2),
]


def _num(s):
    m = re.search(r"-?\d+(?:\.\d+)?", s)
    return float(m.group(0)) if m else None


def rules(req):
    """The agent's own understanding. Returns a change dict, or None."""
    r = req.lower().strip()
    ch = {"set": {}, "words": {}, "switches": {}, "note": None, "nudge": {}}
    if re.fullmatch(r"(clear|forget|drop) (the )?notes?", r):
        return {"clear_notes": True}
    for key, names in NAMES.items():
        for n in names:
            m = re.search(r"\b" + re.escape(n) + r"\b\s*(?:to|=|at|:)?\s*(-?\d+(?:\.\d+)?)", r)
            if m:
                ch["set"][key] = float(m.group(1))
                break
            m = re.search(r"\b(raise|increase|turn up|more|up)\b[^.]*\b" + re.escape(n) + r"\b|\b" + re.escape(n) + r"\b\s*(up|higher)\b", r)
            if m:
                ch["nudge"][key] = +2
                break
            m = re.search(r"\b(lower|decrease|turn down|less|down)\b[^.]*\b" + re.escape(n) + r"\b|\b" + re.escape(n) + r"\b\s*(down|lower)\b", r)
            if m:
                ch["nudge"][key] = -2
                break
    for pat, key, n in NUDGES:
        if re.search(pat, r) and key not in ch["set"]:
            ch["nudge"][key] = n
    for m in re.finditer(r"\b(brighten|boost|favor|favour|more of|lean toward|use more)\s+(?:the word\s+)?['\"]?([a-z][a-z'-]+)", r):
        ch["words"][m.group(2)] = 3
    for m in re.finditer(r"\b(dim|avoid|never say|ban|less of|stop saying|use less)\s+(?:the word\s+)?['\"]?([a-z][a-z'-]+)", r):
        ch["words"][m.group(2)] = -5 if m.group(1) in ("never say", "ban", "stop saying") else -3
    for layer in LAYERS:
        if re.search(r"\b(turn on|enable|unlock|switch on)\b[^.]*\b" + layer + r"\b", r):
            ch["switches"][layer] = True
        if re.search(r"\b(turn off|disable|lock|switch off)\b[^.]*\b" + layer + r"\b", r):
            ch["switches"][layer] = False
    if re.search(r"\b(psilocybin|trip)\b.*\b(on|start)\b|\b(turn on|start)\b.*\b(psilocybin|trip)\b", r):
        ch["psy"] = True
    if re.search(r"\b(psilocybin|trip)\b.*\b(off|stop)\b|\b(turn off|stop)\b.*\b(psilocybin|trip)\b", r):
        ch["psy"] = False
    m = re.match(r"^(?:tell her|note|instruct|ask her|have her)\b[:,]?\s*(?:to\s+)?(.+)", req.strip(), re.I)
    if m:
        ch["note"] = m.group(1)
    useful = any(ch[k] for k in ("set", "words", "switches", "nudge")) or ch.get("note") or "psy" in ch
    return ch if useful else None


SCHEMA_HELP = (
    "You are the service agent for Veyra, a tarot reader running on a local language model. "
    "Turn the operator's request into settings. Reply with ONLY one JSON object, no prose:\n"
    '{"set": {KEY: number}, "words": {"word": level -5..5}, "switches": {LAYER: true|false}, '
    '"note": "an instruction for Veyra, or null"}\n'
    "KEYS: " + ", ".join(f"{k} ({d[0]}, {d[1]}..{d[2]})" for k, d in DIALS.items()) + "\n"
    "LAYERS: " + ", ".join(LAYERS) + "\n"
    "Use \"note\" for requests about what she says or how she speaks. Leave out anything not asked for."
)


def _parse_json(text):
    if not text:
        return None
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        d = json.loads(m.group(0))
    except Exception:
        return None
    if not isinstance(d, dict):
        return None
    out = {"set": {}, "words": {}, "switches": {}, "note": None, "nudge": {}}
    for k, v in (d.get("set") or {}).items():
        if k in DIALS and isinstance(v, (int, float)):
            out["set"][k] = float(v)
    for k, v in (d.get("words") or {}).items():
        if isinstance(k, str) and re.fullmatch(r"[A-Za-z][A-Za-z'-]{0,30}", k) and isinstance(v, (int, float)):
            out["words"][k.lower()] = int(v)
    for k, v in (d.get("switches") or {}).items():
        if k in LAYERS and isinstance(v, bool):
            out["switches"][k] = v
    if isinstance(d.get("note"), str) and d["note"].strip() and d["note"].strip().lower() != "null":
        out["note"] = d["note"].strip()[:300]
    return out if (out["set"] or out["words"] or out["switches"] or out["note"]) else None


BRAIN = None                      # set by the reader when her brain is created


def ask_local(req):
    """Steps 2: the local model, then the same again with a stricter prompt. (result, why-not)"""
    b = BRAIN
    if b is None or not getattr(b, "online", False):
        return None, "no local model"
    if b.busy():
        return None, "the model is paused mid-reading (queued for when it resumes)"
    msgs = [{"role": "system", "content": SCHEMA_HELP}, {"role": "user", "content": req}]
    for temp, extra in ((0.2, ""), (0.05, "\nReturn the JSON object only. Start with { and end with }.")):
        if extra:
            msgs[0]["content"] += extra
        try:
            out = _parse_json(b.chat(msgs, 220, temp, wait=False, _control=True))
        except Exception as e:
            return None, f"model error: {str(e)[:60]}"
        if out:
            return out, ""
    return None, "the model's answer was not usable"


def fuzzy(req):
    """Step 3: close matches for dial and layer names, words already on the WORDS page."""
    r = req.lower()
    toks = re.findall(r"[a-z][a-z-]+", r)
    vocab = {n: k for k, ns in NAMES.items() for n in ns}
    ch = {"set": {}, "words": {}, "switches": {}, "note": None, "nudge": {}}
    num = _num(r)
    for t in toks:
        hit = difflib.get_close_matches(t, list(vocab), 1, 0.8)
        if hit:
            key = vocab[hit[0]]
            if num is not None:
                ch["set"][key] = num
            elif re.search(r"\b(up|more|higher|raise)\b", r):
                ch["nudge"][key] = 2
            elif re.search(r"\b(down|less|lower)\b", r):
                ch["nudge"][key] = -2
        lay = difflib.get_close_matches(t, list(LAYERS), 1, 0.8)
        if lay and re.search(r"\b(on|off)\b", r):
            ch["switches"][lay[0]] = bool(re.search(r"\bon\b", r))
    return ch if any(ch[k] for k in ("set", "nudge", "switches")) else None


def anthropic_ready():
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return False, "the anthropic package is not installed (pip install anthropic)"
    if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
        return False, "no Anthropic key (set ANTHROPIC_API_KEY on the Wiring page)"
    return True, ""


def ask_anthropic(req):
    """Step 4, the last resort: one short request to the Anthropic API."""
    import anthropic
    client = anthropic.Anthropic()
    try:
        resp = client.messages.create(model="claude-opus-5-5", max_tokens=1024,
                                      output_config={"effort": "low"}, system=SCHEMA_HELP,
                                      messages=[{"role": "user", "content": req}])
    except anthropic.AuthenticationError:
        return None, "the Anthropic key was refused"
    except anthropic.RateLimitError:
        return None, "the Anthropic API is rate limited right now"
    except anthropic.APIStatusError as e:
        return None, f"Anthropic API error {e.status_code}"
    except anthropic.APIConnectionError:
        return None, "could not reach the Anthropic API"
    if resp.stop_reason == "refusal":
        return None, "the request was declined"
    text = "".join(b.text for b in resp.content if b.type == "text")
    out = _parse_json(text)
    return (out, "") if out else (None, "the answer was not usable")


def apply(ch):
    """Make the changes. Returns a short description of what changed."""
    if ch.get("clear_notes"):
        clear_notes()
        return "notes cleared"
    done = []
    for layer, on in (ch.get("switches") or {}).items():
        set_switch(layer, on)
        done.append(f"{LAYERS[layer][0]} {'on' if on else 'off'}")
    if "TAROT_SPECTRUM" in (ch.get("set") or {}):
        done.append(f"spectrum {set_dial('TAROT_SPECTRUM', ch['set'].pop('TAROT_SPECTRUM')):g}")
    locked = []
    for key, v in (ch.get("set") or {}).items():
        if not live(DIALS[key][5]):
            locked.append(DIALS[key][0])
            continue
        done.append(f"{DIALS[key][0].lower()} {set_dial(key, v):g}")
    for key, n in (ch.get("nudge") or {}).items():
        if not live(DIALS[key][5]):
            locked.append(DIALS[key][0])
            continue
        done.append(f"{DIALS[key][0].lower()} {tick(key, n):g}")
    for w, lvl in (ch.get("words") or {}).items():
        done.append(f"'{w}' {set_word(w, lvl):+d}")
    if "psy" in ch:
        if psyche.active() != ch["psy"]:
            psyche.toggle()
        done.append("psilocybin " + ("on" if ch["psy"] else "off"))
    if ch.get("note"):
        add_note(ch["note"])
        done.append("note passed to Veyra")
    msg = ", ".join(done) or "nothing changed"
    if locked:
        msg += f" · locked by the spectrum/switches: {', '.join(locked)}"
    return msg


STYLE = re.compile(r"\b(she|her|veyra|reading|readings|talk|speak|sound|voice|tone|feel|mood|words?|"
                   r"say|tell|style|more|less|like)\b", re.I)


def handle(req, confirm, log):
    """The service agent's ladder. confirm(question) -> bool asks the operator; log(text) reports."""
    req = req.strip()
    if not req:
        return
    if req.lower() in ("pause",):
        pause()
        return log("model paused")
    if req.lower() in ("resume", "go", "continue"):
        resume()
        return log("model will resume when you leave")
    ch = rules(req)
    if ch:
        return log("agent: " + apply(ch))
    tried = ["rules ✗"]
    log("agent: asking the local model...")
    ch, why = ask_local(req)
    if ch:
        return log("model: " + apply(ch))
    tried.append(f"local model ✗ ({why})")
    ch = fuzzy(req)
    if ch:
        return log("agent (close match): " + apply(ch))
    tried.append("fuzzy ✗")
    if STYLE.search(req):                                  # about how she speaks: she hears it as a note
        add_note(req)
        return log(" · ".join(tried) + " → passed to Veyra as an operator note (Ctrl+W, 'clear notes' removes it)")
    if "queued" in why:
        QUEUED.append(req)
        return log(" · ".join(tried) + " → queued for the model")
    ok, why_a = anthropic_ready()
    if not ok:
        return log(" · ".join(tried) + f" · Anthropic unavailable: {why_a}")
    if not confirm("Every local option failed. Send this one request to the Anthropic API? [y/N]"):
        return log(" · ".join(tried) + " · Anthropic declined by you")
    log("agent: asking the Anthropic API (last resort)...")
    ch, why_b = ask_anthropic(req)
    log(("Anthropic: " + apply(ch)) if ch else (" · ".join(tried) + f" · Anthropic ✗ ({why_b})"))


def drain_queue(say=None):
    """Run queued requests once the model is free again (in the background)."""
    if not QUEUED:
        return

    def work():
        while QUEUED:
            req = QUEUED.pop(0)
            if BRAIN is not None:
                with BRAIN.lock:
                    pass                                    # wait for the current reading to finish
            ch, why = ask_local(req)
            msg = ("model: " + apply(ch)) if ch else f"queued request not understood: {req[:40]} ({why})"
            HISTORY.append(msg)
            if say:
                say(msg)
    threading.Thread(target=work, daemon=True).start()


HISTORY = []
IN_ROOM = False


# ------------------------------------------------------------------ the room
PAGES = ["dials", "words", "wires"]
DIAL_ORDER = list(DIALS)


def _word_list():
    text = "".join(RECENT)
    seen, out = set(), []
    for w in reversed(re.findall(r"[A-Za-z][A-Za-z'-]{2,}", text)):
        lw = w.lower()
        if lw not in seen:
            seen.add(lw)
            out.append(lw)
        if len(out) >= 60:
            break
    out.reverse()
    for w in words():
        if w not in seen:
            out.append(w)
    return out or sorted(words())


def _word_color(lvl):
    if lvl > 0:
        return [229, 228, 227, 226, 220][min(4, lvl - 1)]
    if lvl < 0:
        return [245, 243, 241, 239, 237][min(4, -lvl - 1)]
    return 250


def draw_dials(ui, sel, t):
    s = spectrum()
    w = ui.w
    # the spectrum bar with each layer's band under it
    bx, bw = 20, max(20, w - 36)
    ui.text(2, 1, "SPECTRUM", 189, True)
    for x in range(bw):
        col = [33, 39, 45, 51, 87, 123, 159, 225, 219, 213, 207, 201][min(11, int(x / bw * 12))]
        ui.put(2, bx + x, "▬", ui.attr(col))
    ui.put(2, bx + int(s * (bw - 1)), "◆", ui.attr(231, 16, True))
    ui.text(2, bx - 7, "steady", 110)
    ui.text(2, bx + bw + 1, f"wild {s:.2f}", 213)
    y = 3
    for layer, (label, lo, hi) in LAYERS.items():
        x0, x1 = bx + int(lo * (bw - 1)), bx + int(hi * (bw - 1))
        on, band = switch_on(layer), in_band(layer, s)
        col = 120 if (on and band) else (178 if on else 240)
        sw = "■" if on else "□"
        ui.text(y, 1, f"{sw} {label:<10}"[:12], col, on and band)
        for x in range(x0, x1 + 1):
            ui.put(y, x, "━" if band else "─", ui.attr(col))
        state = "LIVE" if on and band else ("out of band" if on else "switched off")
        ui.text(y, bx + bw + 1, state, col)
        y += 1
    y += 1
    ui.text(y, 1, "DIALS  (←/→ tick · ↑/↓ choose · space flips a layer switch)", 103)
    y += 1
    for i, key in enumerate(DIAL_ORDER):
        label, lo, hi, step, default, layer, note = DIALS[key]
        v = value(key)
        ok = live(layer)
        hot = i == sel
        r = (v - lo) / (hi - lo) if hi > lo else 0
        face = "◜◝◞◟"[min(3, int(r * 4))] if ok else "◌"
        ticks = 21
        k = int(round(r * (ticks - 1)))
        bar = "".join("┃" if j == k else ("╍" if j < k else "┄") for j in range(ticks))
        col = (231 if hot else 117) if ok else 240
        ui.text(y, 1, f"{'▶' if hot else ' '} {face} {label:<15}", col, hot)
        for j, ch in enumerate(bar):
            c = ([33, 39, 45, 51, 87, 123, 159, 219, 213, 207, 201][min(10, int(j / ticks * 11))] if j <= k else 238) if ok else 238
            ui.put(y, 22 + j, ch, ui.attr(c, 16, j == k))
        ui.text(y, 22 + ticks + 1, f"{v:.2f}" if step < 1 else f"{int(v)}", col)
        ui.text(y, 22 + ticks + 8, ("" if ok else f"[{LAYERS[layer][0].lower()} locked]") if layer else "", 240)
        y += 1
    key = DIAL_ORDER[sel]
    return f"{DIALS[key][0]}: {DIALS[key][6]}"


def draw_words(ui, sel, t):
    ws = _word_list()
    bias = words()
    ui.text(2, 1, "WORD BRIGHTNESS  (←/→ dim or brighten · ↑/↓ move · 0 resets the word)", 103)
    if not ws:
        ui.text(4, 2, "No words yet. Start a reading; her words appear here as she writes them.", 245)
        return "Words she writes appear here."
    x, y, pos = 2, 4, []
    for i, w in enumerate(ws):
        if x + len(w) + 2 > ui.w - 2:
            x, y = 2, y + 2
        if y > ui.h - 8:
            break
        lvl = bias.get(w, 0)
        hot = i == sel
        ui.text(y, x, w, _word_color(lvl), lvl > 0 or hot)
        if hot:
            ui.text(y + 1, x, "▔" * len(w), 231)
        elif lvl:
            ui.text(y + 1, x, ("+" if lvl > 0 else "-") * min(len(w), abs(lvl)), _word_color(lvl))
        pos.append(i)
        x += len(w) + 2
    sel = min(sel, len(ws) - 1)
    w = ws[sel]
    lvl = bias.get(w, 0)
    meter = "".join(("█" if (j <= lvl and j > 0) or (j >= lvl and j < 0) else "·") if j else "│"
                    for j in range(WORD_MIN, WORD_MAX + 1))
    ui.text(ui.h - 7, 2, f"'{w}'  dim {meter} bright   {lvl:+d}", _word_color(lvl) if lvl else 189, True)
    lock = "" if live("vocab") else "   (VOCAB layer is locked: brightness is saved but not applied)"
    return f"'{w}' brightness {lvl:+d}{lock}"


def room(scr, page="dials"):
    """The control room (curses). Pauses the model while it is open."""
    import curses, tarot
    global IN_ROOM
    was = paused()
    pause()
    IN_ROOM = True
    scr = tarot._sized(scr)
    ui = tarot.UI(scr)
    ui.mood = "channel"
    pg = PAGES.index(page) if page in PAGES else 0
    sel = {"dials": 0, "words": 0, "wires": 0}
    log = (HISTORY[-1:] or ["Type what you want changed: Ctrl+W or / to talk to the agent."])[:]
    scr.timeout(70)

    def say(m):
        log.append(m)
        HISTORY.append(m)
        del HISTORY[:-50]

    def read_line(prompt_text, hidden=False):
        y = ui.h - 2
        scr.move(y, 0)
        scr.clrtoeol()
        scr.addstr(y, 1, prompt_text[: ui.w - 2])
        scr.timeout(-1)
        (curses.noecho if hidden else curses.echo)()
        try:
            curses.curs_set(1)
        except curses.error:
            pass
        try:
            return scr.getstr(y, min(ui.w - 2, len(prompt_text) + 1), 400).decode("utf-8", "ignore").strip()
        finally:
            curses.noecho()
            try:
                curses.curs_set(0)
            except curses.error:
                pass
            scr.timeout(70)

    def confirm(q):
        return read_line(q + " ").lower().startswith("y")

    def draw():
        t = ui.now() - ui.t0
        scr.erase()
        ui.stars(18)
        tabs = "  ".join(f"[{i + 1} {p.upper()}]" if i == pg else f" {i + 1} {p} " for i, p in enumerate(PAGES))
        ui.gcenter(0, "~ the control room ~")
        ui.text(1, 1, tabs, 189)
        state = "● MODEL PAUSED" if paused() else "○ model running"
        ui.text(1, ui.w - len(state) - 2, state, 203 if paused() else 120, True)
        if PAGES[pg] == "dials":
            hint = draw_dials(ui, sel["dials"], t)
        elif PAGES[pg] == "words":
            hint = draw_words(ui, sel["words"], t)
        else:
            psyche.draw_wires(ui, sel["wires"], t, top=3, bottom=6)
            hint = "Enter edits the selected wire · p toggles psilocybin mode"
        # the command window
        ui.text(ui.h - 5, 0, "─" * (ui.w - 1), 60)
        ui.text(ui.h - 4, 1, hint[: ui.w - 2], 103)
        ui.text(ui.h - 3, 1, (log[-1] if log else "")[: ui.w - 2], 159)
        ui.text(ui.h - 2, 1, "› talk to the agent: Ctrl+W or /", 245)
        ui.center(ui.h - 1, "Tab/1-3 pages · q or Esc leaves (the model resumes)", 60)
        scr.refresh()

    try:
        while True:
            draw()
            c = scr.getch()
            if c == 27:                                   # a bare Esc leaves; an arrow key arrives as Esc [ X
                scr.timeout(40)
                n = scr.getch()
                if n in (ord("["), ord("O")):
                    m = scr.getch()
                    c = {ord("A"): curses.KEY_UP, ord("B"): curses.KEY_DOWN, ord("C"): curses.KEY_RIGHT,
                         ord("D"): curses.KEY_LEFT, ord("Z"): curses.KEY_BTAB}.get(m, -1)
                elif n != -1:
                    c = -1
                scr.timeout(70)
            name = PAGES[pg]
            if c in (ord("q"), 27):
                break
            if c in (9, curses.KEY_BTAB):
                pg = (pg + (1 if c == 9 else -1)) % len(PAGES)
            elif c in (ord("1"), ord("2"), ord("3")):
                pg = c - ord("1")
            elif c in (23, ord("/")):
                req = read_line("› ")
                if req:
                    say(f"you: {req}")
                    draw()
                    handle(req, confirm, say)
            elif name == "dials":
                key = DIAL_ORDER[sel["dials"]]
                if c == curses.KEY_UP:
                    sel["dials"] = (sel["dials"] - 1) % len(DIAL_ORDER)
                elif c == curses.KEY_DOWN:
                    sel["dials"] = (sel["dials"] + 1) % len(DIAL_ORDER)
                elif c in (curses.KEY_LEFT, curses.KEY_RIGHT):
                    if live(DIALS[key][5]):
                        tick(key, 1 if c == curses.KEY_RIGHT else -1)
                    else:
                        say(f"{DIALS[key][0]} is locked: its layer is switched off or out of the spectrum's band")
                elif c == ord(" "):
                    layer = DIALS[key][5]
                    if layer:
                        set_switch(layer, not switch_on(layer))
                        say(f"{LAYERS[layer][0]} switch {'on' if switch_on(layer) else 'off'}")
            elif name == "words":
                ws = _word_list()
                if ws:
                    i = min(sel["words"], len(ws) - 1)
                    if c == curses.KEY_DOWN:
                        sel["words"] = (i + 1) % len(ws)
                    elif c == curses.KEY_UP:
                        sel["words"] = (i - 1) % len(ws)
                    elif c in (curses.KEY_LEFT, curses.KEY_RIGHT):
                        lvl = words().get(ws[i], 0) + (1 if c == curses.KEY_RIGHT else -1)
                        set_word(ws[i], lvl)
                    elif c == ord("0"):
                        set_word(ws[i], 0)
            else:
                if c == curses.KEY_UP:
                    sel["wires"] = (sel["wires"] - 1) % len(psyche.KNOBS)
                elif c == curses.KEY_DOWN:
                    sel["wires"] = (sel["wires"] + 1) % len(psyche.KNOBS)
                elif c in (ord("p"), ord("P")):
                    say("psilocybin mode ON · psyche engaged" if psyche.toggle() else "psilocybin mode off")
                elif c in (10, 13, curses.KEY_ENTER):
                    say(psyche.edit_knob(scr, ui, sel["wires"]))
    finally:
        IN_ROOM = False
        if not was:
            resume()
        drain_queue()


def open_from_terminal():
    """Ctrl+W pressed outside curses (prompts, a streaming reading): open the room full-screen."""
    import curses
    curses.wrapper(room)
