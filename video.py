"""Turn a reading into a vertical Facebook reel (540x960 by default, TAROT_VIDEO_RES=1080 for 1080x1920), drawn from Veyra's own pixel art.

Reel format: a pixel tapestry backdrop with a pinned hook headline at the top (icon + title +
one-line hook, white boxes), the reading table on a navy cloth below it, and each card held up
to the camera as she reads it.

The scenes are the real ritual screens rendered on a virtual terminal: her intro, what you told
her, the questions held for the spirits, the washing and cutting, then each card turning while
she reads it, captions for muted autoplay, a prepared-piano music bed and an end title.
Everything optional (ffmpeg, numpy, Pillow, a voice engine) is checked and requested first."""
import json, math, os, random, re, subprocess, tempfile, time, wave
from pathlib import Path

def _videos_dir():
    """Videos stay on the machine making them, outside the git repo: ~/Videos/Veyra
    (on Windows, your Videos folder). In a Codespace they stay in ./videos for download."""
    if os.environ.get("TAROT_VIDEOS"):
        return Path(os.environ["TAROT_VIDEOS"]).expanduser()
    if os.environ.get("CODESPACE_NAME"):
        return Path("videos")
    base = Path.home() / "Videos"
    if os.name != "nt":
        try:                                           # honor a localized XDG videos folder
            import subprocess
            x = subprocess.run(["xdg-user-dir", "VIDEOS"], capture_output=True, text=True, timeout=3).stdout.strip()
            if x and x != str(Path.home()):
                base = Path(x)
        except Exception:
            pass
    return base / "Veyra"


VIDEOS = _videos_dir()
SESSIONS = Path(os.environ.get("TAROT_SESSIONS", "sessions"))
OW, OH = 1080, 1920                               # 9:16 reel
OUT_W = int(os.environ.get("TAROT_VIDEO_RES", "540"))   # output width: 540x960 for now (1080 = full HD);
OUT_SCALE = ["-vf", f"scale={OUT_W}:{OUT_W * 16 // 9}:flags=area"] if OUT_W != OW else []   # frames are drawn at 1080
BAND = 640                                        # tapestry backdrop + pinned hook
BOX_TOP, BOX = 650, 930                           # the terminal table on the cloth
CAP_TOP, CAP_H = 1590, 190                        # spoken captions (kept above Facebook's bottom overlay)
CLOTH = (10, 14, 40)
FPS = 15
SR = 44100
SMALL = (30, 72, 15, 30)                          # rows, cols, cell w, cell h  (fills 1080 px wide)
WIDE = (30, 80, 13, 26)                           # the Celtic Cross table and the intro need 80 columns
LARGE = (23, 54, 20, 40)                          # big, phone-readable text for the interview


# ================================================================ sessions
def save_session(sess):
    SESSIONS.mkdir(parents=True, exist_ok=True)
    p = SESSIONS / f"reading_{time.strftime('%Y%m%d_%H%M%S')}.json"
    p.write_text(json.dumps(sess, indent=1))
    return p


def latest_session():
    files = sorted(SESSIONS.glob("reading_*.json")) if SESSIONS.exists() else []
    return files[-1] if files else None


def load_session(path):
    s = json.loads(Path(path).read_text())
    s["spread"] = [(c, bool(r)) for c, r in s["spread"]]
    s["qa"] = [tuple(x) for x in s.get("qa", [])]
    if s.get("falls"):
        s["falls"]["pairs"] = [tuple(p) for p in s["falls"].get("pairs", [])]
    return s


# ================================================================ what she says
def _sentences(text):
    out = []
    for s in re.split(r"(?<=[.!?])\s+", re.sub(r"\s+", " ", text).strip()):
        s = s.strip()
        if len(s) > 12:
            out.append(s if len(s) < 230 else s[:227].rsplit(" ", 1)[0] + "...")
    return out


def reading_sentences(text):
    """The model's (or scripted) reading as clean sentences, without tags, Q/A echoes or the card list."""
    main = text.split("Before the cards return to the deck")[0]
    main = re.sub(r"\[[^\]]*\]", " ", main)
    keep = []
    for ln in main.splitlines():
        ln = re.sub(r"^[#*\-•\s\d.]+(?=[A-Za-z])", "", ln.strip()).replace("**", "").replace("__", "")
        if ln and not re.match(r"^(Q|A)\s*:", ln) and not ln.lower().startswith(("end of reading", "you asked:")):
            keep.append(ln)
    return _sentences(" ".join(keep))


def tts_text(s):
    s = s.replace("8b/3b(L)", "eight B, three B, L").replace("Qwen 2.5", "Kwen two point five")
    s = s.replace("Veyra", "Vayra").replace("Celtic", "Keltic").replace("&", "and")
    s = re.sub(r"(\d+)\s*-\s*(\d+)", r"\1 to \2", s)
    return re.sub(r"[\[\]*_#]", "", s)


def live_script(sess):
    """Replay each of the six fall positions: question, shuffle, fall, reading."""
    import questions as Q
    log = sess["falls"]["log"]
    scenes = [{"name": "intro", "lines": ["I am Veyra. This is a Live Reading.",
                                          "I ask the deck my own questions, and it answers by letting cards fall."]}]
    for n, e in enumerate(log):
        scenes.append({"name": f"ask{n}", "event": n, "passes": e.get("passes", 1),
                       "lines": [f"{e['opener']} {e['question']}"]})
        scenes.append({"name": f"drop{n}", "event": n, "lines": []})
        scenes.append({"name": f"read{n}", "event": n, "lines": _sentences(e["text"])})
    sents = reading_sentences(sess.get("reading", ""))
    close = [s for s in sents if re.search(r"thank|grateful|gratitude", s, re.I)][:1] or \
            [random.SystemRandom().choice(Q.CLOSINGS)]
    scenes.append({"name": "table", "lines": ["All six positions are filled. Paired falls may mean more than six cards."]})
    scenes.append({"name": "end", "lines": close})
    return scenes


def build_script(sess):
    """Scenes with their lines: [{'name', 'lines': [caption, ...], 'card': index or None}]"""
    import edit
    if sess.get("key") == "falling" and (sess.get("falls") or {}).get("log"):
        return edit.weave_in(live_script(sess), sess)
    from knowledge import position_meaning
    from spreads import SPREADS
    from spirit import named
    import questions as Q
    key, spread, dom = sess["key"], sess["spread"], sess.get("domain", "inner")
    pos = SPREADS[key]["positions"]
    sents = reading_sentences(sess.get("reading", ""))
    used = set()
    scenes = [{"name": "intro", "lines": ["I am Veyra. I turn chance into meaning."]}]
    told = [f"Tonight's question: {sess['question'].strip().rstrip('.')}" + ("" if sess["question"].strip().endswith("?") else ".")]
    prof = dict(p.split(": ", 1) for p in sess.get("profile", "").split(", ") if ": " in p)
    if prof.get("age"):
        told.append(f"Age: {prof['age']}.")
    if prof.get("sign"):
        from knowledge import parse_sign
        sign, el = parse_sign(prof["sign"])
        art_ = "an" if el in ("air", "earth") else "a"
        told.append(f"Sign: {sign}, {art_} {el} sign." if sign else f"Element: {el or prof['sign']}.")
    for q, a in sess.get("qa", []):
        a = (a or "").strip().rstrip(".")
        if a:
            told.append(f"{q} {a[:1].upper() + a[1:]}.")
    scenes.append({"name": "interview", "lines": told})
    falls = sess.get("falls") or {}
    if sess.get("spirit_qs"):
        scenes.append({"name": "spirits", "lines": ["So I asked the spirits: " + " ".join(sess["spirit_qs"])]})
    if key == "falling":
        n_pairs = len(falls.get("pairs", []))
        scenes.append({"name": "ritual", "lines": [
            "I shuffled, and let the deck choose. Six cards fell out on their own"
            + (f", {'two of them' if n_pairs == 1 else f'{n_pairs} pairs'} together." if n_pairs else ".")]})
    else:
        what = "the Celtic Cross" if key == "celtic" else "past, present and future"
        scenes.append({"name": "ritual", "lines": [f"The cards are washed, cut into three, and gathered. {len(spread)} cards: {what}."]})
    scenes.append({"name": "table", "lines": []})
    for i, ((label, _), (card, rev)) in enumerate(zip(pos, spread)):
        if key == "falling":
            head = f"{label}: {named(card)}{', upside down' if rev else ''}."
        else:
            head = f"{label}: {named(card)}{', reversed' if rev else ''}."
        names = {card.lower(), card.lower().replace("the ", "")}
        mine = [s for s in sents if s not in used and any(n in s.lower() for n in names)][:2]
        used.update(mine)
        if not mine:
            mine = _sentences(position_meaning(card, rev, label, dom))[:2]
        lines = [head[:1].upper() + head[1:]]
        q = (falls.get("questions") or [None] * 6)[i] if key == "falling" else None
        if q:
            lines.append(f"I asked the deck: {q.strip().rstrip('?')}?")
        lines += mine
        for a, b in falls.get("pairs", []) if key == "falling" else []:
            if i == b:
                from knowledge import pair_reading
                pr = _sentences(pair_reading(spread[a][0], spread[a][1], card, rev, dom))
                lines += [pr[0], pr[3] if len(pr) > 3 else pr[-1]]
        scenes.append({"name": f"card{i}", "card": i, "lines": lines})
    close = [s for s in sents if s not in used and s.endswith("?")][-1:]
    close += [s for s in sents if s not in used and re.search(r"thank|grateful|gratitude", s, re.I)][:1]
    if not close:
        close = [random.SystemRandom().choice(Q.CLOSINGS)]
    scenes.append({"name": "end", "lines": close})
    return edit.weave_in(scenes, sess)


# ================================================================ voice
def _read_wav(path):
    import numpy as np
    with wave.open(str(path)) as w:
        sr, n, ch, sw = w.getframerate(), w.getnframes(), w.getnchannels(), w.getsampwidth()
        raw = w.readframes(n)
    a = np.frombuffer(raw, dtype={1: np.uint8, 2: np.int16, 4: np.int32}[sw]).astype(np.float32)
    a = (a - 128) / 128 if sw == 1 else a / float(2 ** (8 * sw - 1))
    if ch > 1:
        a = a.reshape(-1, ch).mean(axis=1)
    return resample(a, sr, SR)


def resample(a, sr, to):
    import numpy as np
    if sr == to or len(a) == 0:
        return a.astype(np.float32)
    n = int(len(a) * to / sr)
    return np.interp(np.linspace(0, len(a) - 1, n), np.arange(len(a)), a).astype(np.float32)


class Voice:
    """Speaks a line with the best engine available: piper (natural), flite, espeak, or none."""

    def __init__(self, kind):
        self.kind, self._pv = kind, None        # (_pv caches the loaded Piper model)

    def say(self, text):
        if not self.kind:
            return None
        try:
            with tempfile.TemporaryDirectory() as d:
                out = Path(d) / "line.wav"
                getattr(self, "_" + self.kind)(tts_text(text), out, Path(d))
                a = _read_wav(out)
            return digitize(a, natural=self.kind == "piper") if len(a) else None
        except Exception:
            return None

    def _piper(self, text, out, d):
        import deps
        model = deps.voice_model()
        try:
            from piper import PiperVoice
            if self._pv is None:
                self._pv = PiperVoice.load(str(model))
            with wave.open(str(out), "wb") as wf:
                if hasattr(self._pv, "synthesize_wav"):
                    self._pv.synthesize_wav(text, wf)
                else:
                    self._pv.synthesize(text, wf)
        except Exception:
            import sys
            subprocess.run([sys.executable, "-m", "piper", "-m", str(model), "-f", str(out)], input=text,
                           text=True, capture_output=True, timeout=120)

    @staticmethod
    def _flite(text, out, d):
        """The voice from the first videos: flite's 'slt' voice (through ffmpeg, or the flite program)."""
        import deps, shutil
        (d / "t.txt").write_text(text)
        if deps.ffmpeg_has_flite():
            subprocess.run([deps.ffmpeg(), "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
                            f"flite=textfile={d / 't.txt'}:voice=slt", str(out)], capture_output=True, timeout=120)
        if (not out.exists() or out.stat().st_size < 1000) and shutil.which("flite"):
            subprocess.run(["flite", "-voice", "slt", "-f", str(d / "t.txt"), "-o", str(out)],
                           capture_output=True, timeout=120)

    @staticmethod
    def _espeak(text, out, d):
        import shutil
        exe = shutil.which("espeak-ng") or shutil.which("espeak")
        subprocess.run([exe, "-v", "en-us+f3", "-s", "150", "-w", str(out), text], capture_output=True, timeout=120)


def working_voice(kind, say=print):
    """Test the chosen voice on one line before rendering; fall back to any engine that actually speaks."""
    import deps, shutil
    tried = []
    for k in [kind, "flite", "espeak", "piper"]:
        if not k or k in tried:
            continue
        tried.append(k)
        if k == "flite" and not deps.flite_ready():
            continue
        if k == "espeak" and not (shutil.which("espeak-ng") or shutil.which("espeak")):
            continue
        if k == "piper" and not deps.piper_ready():
            continue
        v = Voice(k)
        if v.say("Hello.") is not None:
            if k != kind and kind:
                say(f"The {kind} voice did not work here, so she will speak with {k}.")
            return v
    say("No voice engine could speak, so this video will have captions and music only. "
        "To fix it: sudo apt-get install -y flite")
    return Voice(None)


def digitize(x, natural=True):
    """Her slightly digital timbre: a touch of bit-crush, a shimmering chorus and a short echo.
    Kept light so it is pleasant over a few minutes."""
    import numpy as np
    if not natural:                                        # robotic engines: a little slower and deeper
        x = resample(x, SR, int(SR / 0.93))
    n = len(x)
    bits = 2 ** 8
    x = 0.86 * x + 0.14 * (np.round(x * bits) / bits)
    t = np.arange(n) / SR
    delay = (0.021 + 0.004 * np.sin(2 * np.pi * 0.8 * t)) * SR
    x = x + (0.22 if natural else 0.3) * np.interp(np.arange(n) - delay, np.arange(n), x, left=0.0)
    out = np.zeros(n + int(0.2 * SR), np.float32)
    out[:n] += x
    for sec, g in ((0.065, 0.14), (0.15, 0.06)):
        k = int(sec * SR)
        out[k:k + n] += g * x
    return (out / max(1e-6, np.abs(out).max()) * 0.9).astype(np.float32)


# ================================================================ music
def _lowpass(x, a):
    import numpy as np
    try:
        from scipy.signal import lfilter
        return lfilter([a], [1, a - 1], x).astype(np.float32)
    except Exception:
        k = max(1, int(1 / a))
        return np.convolve(x, np.ones(k, np.float32) / k, mode="same").astype(np.float32)


def _convolve(x, ir, block=1 << 17):
    """Overlap-add FFT convolution (numpy only)."""
    import numpy as np
    n = len(x) + len(ir) - 1
    size = 1 << int(math.ceil(math.log2(block + len(ir))))
    IR = np.fft.rfft(ir, size)
    out = np.zeros(n + size, np.float32)
    for s in range(0, len(x), block):
        seg = np.fft.irfft(np.fft.rfft(x[s:s + block], size) * IR, size)
        out[s:s + size] += seg.astype(np.float32)
    return out[:len(x)]


def music_bed(total, seed=7):
    """An original prepared-piano piece in the spirit of Aphex Twin's 'Jynweythek': sparse, detuned,
    metallic plucks in a modal scale with a long airy room (original notes, not the song's)."""
    import numpy as np
    rng = np.random.default_rng(seed)
    N = int((total + 1) * SR)
    music = np.zeros(N, np.float32)

    def pluck(freq, length, vel):
        n = int(SR * length)
        tt = np.arange(n) / SR
        out = np.zeros(n, np.float32)
        for k in range(1, 9):
            fk = freq * k * math.sqrt(1 + 0.0006 * k * k)
            if fk > SR / 2.2:
                break
            for det in (-0.9, 0.9):
                out += (1.0 / k ** 1.1) * np.sin(2 * np.pi * (fk + det) * tt + rng.uniform(0, 6.28)) * np.exp(-(1.6 + 0.9 * k) * tt)
        for ratio, a, d in ((2.76, 0.35, 4.5), (5.40, 0.18, 7.0), (8.93, 0.08, 10.0)):
            out += a * np.sin(2 * np.pi * freq * ratio * tt) * np.exp(-d * tt)
        out = out * np.minimum(1, tt / 0.004) + rng.normal(0, 1, n) * np.exp(-tt * 90) * 0.15
        return (out * vel).astype(np.float32)

    scale, base, beat = [0, 1, 3, 5, 7, 8, 10], 146.83, 0.5
    note = lambda deg, octv=1: base * 2 ** ((scale[deg % 7] + 12 * (deg // 7) + 12 * (octv - 1)) / 12)
    motifs = [[7, 9, 11, 9, 8, None, 7, None], [7, 11, 12, 11, 9, None, None, 8],
              [4, 7, 8, 7, None, 6, 7, None], [9, 8, 7, None, 4, None, 5, None]]
    pos, bar = 0.0, 0

    def place(sig, at):
        s0 = int(max(0, at) * SR)
        music[s0:s0 + len(sig)] += sig[:max(0, N - s0)]
    while pos < total + 1:
        m = motifs[(bar // 2) % len(motifs)][:]
        if bar % 2:
            i = int(rng.integers(0, len(m)))
            if m[i] is not None:
                m[i] += int(rng.choice([-1, 1]))
        for j, deg in enumerate(m):
            at = pos + j * beat + rng.normal(0, 0.012)
            if deg is not None and at < total + 1:
                v = 0.55 + 0.35 * rng.random()
                place(pluck(note(deg), 3.0, v), at)
                if rng.random() < 0.18:
                    place(pluck(note(deg - 4), 3.4, v * 0.5), at)
        if bar % 4 == 0:
            place(pluck(note(0, 0), 4.5, 0.6), pos)
        pos += len(m) * beat
        bar += 1
    ir_n = int(SR * 2.8)
    ir = (rng.normal(0, 1, ir_n) * np.exp(-np.linspace(0, 7, ir_n))).astype(np.float32)
    ir[0] = 6.0
    music = _lowpass(_convolve(music, ir), 0.35)
    return music / max(1e-6, np.abs(music).max())


def blip(n_sec=0.12):
    import numpy as np
    n = int(SR * n_sec)
    f = np.linspace(880, 1760, n)
    return (np.sign(np.sin(2 * np.pi * np.cumsum(f) / SR)) * np.exp(-np.linspace(0, 6, n)) * 0.12).astype(np.float32)


# ================================================================ timeline
def plan(scenes, voice, say=print):
    """Synthesize every line, then lay the scenes out in time. Returns (scenes, events, total)."""
    t, events = 0.0, []
    lines = sum(len(s["lines"]) for s in scenes)
    done = 0
    for sc in scenes:
        sc["audio"] = []
        for cap in sc["lines"]:
            a = voice.say(cap)
            if a is not None and sc.get("radio"):
                import edit
                a = edit.radio(a, SR)
            dur = len(a) / SR if a is not None else max(1.6, len(cap.split()) / 2.7)
            sc["audio"].append((cap, a, dur))
            done += 1
            if say and done % 4 == 0:
                say(f"  voice {done}/{lines}")
        speech = sum(d + 0.35 for _, _, d in sc["audio"])
        import psyche
        trip = psyche.scene_time(sc, speech)
        if trip:
            dur, lead = trip
        elif sc["name"] == "intro":
            dur, lead = max(5.0, speech + 1.6), 0.8
        elif sc["name"] == "table":
            dur, lead = (1.4, 0) if not sc["audio"] else (speech + 2.0, 0.6)
        elif sc["name"].startswith("ask"):
            dur, lead = max(speech + 1.0, 1.7 * min(3, sc.get("passes", 1))), 0.3
        elif sc["name"].startswith("drop"):
            dur, lead = 1.1, 0
        elif sc["name"].startswith("read"):
            dur, lead = speech + 0.8, 0.3
        elif sc["name"].startswith("card"):
            dur, lead = 0.6 + speech + 0.6, 0.45
        elif sc["name"] == "ritual":
            dur, lead = max(6.5, speech + 1.5), 0.6
        elif sc["name"] == "end":
            dur, lead = speech + 2.8, 0.5
        elif sc["name"].startswith(("txin", "living")):
            dur, lead = max(2.6, speech + 1.3), 0.7
        elif sc["name"].startswith("tx"):
            dur, lead = speech + 1.4, 0.6
        else:
            dur, lead = speech + 0.9, 0.4
        sc["start"], sc["dur"] = t, dur
        x = t + lead
        for cap, a, d in sc["audio"]:
            events.append((x, cap, a, d))
            x += d + 0.35
        t += dur
    return scenes, events, t


def mix_audio(events, flips, total, path, sfx=()):
    import numpy as np
    N = int((total + 1) * SR)
    v = np.zeros(N, np.float32)
    for at, _, a, _ in events:
        if a is not None:
            s0 = int(at * SR)
            v[s0:s0 + len(a)] += a[:max(0, N - s0)]
    if np.abs(v).max() > 0:
        v = v / np.abs(v).max() * 0.9
    m = music_bed(total)[:N]
    m = np.pad(m, (0, N - len(m)))
    win = int(SR * 0.3)
    env = np.convolve(np.abs(v), np.ones(win, np.float32) / win, mode="same")
    m *= 0.22 * np.clip(1.0 - env * 9, 0.35, 1.0)
    for at in flips:
        b = blip()
        s0 = int(at * SR)
        m[s0:s0 + len(b)] += b[:max(0, N - s0)]
    for at, sig in sfx:
        s0 = int(max(0, at) * SR)
        m[s0:s0 + len(sig)] += sig[:max(0, N - s0)]
    fade = int(SR * 2.5)
    m[-fade:] *= np.linspace(1, 0, fade)
    m[:SR] *= np.linspace(0, 1, SR)
    out = np.clip(v + m, -1, 1)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((out * 32767).astype(np.int16).tobytes())


# ================================================================ pictures
ICONS = {
    "warn": ["....y....", "...yyy...", "...yky...", "..yykyy..", "..yykyy..", ".yyyyyyy.", ".yyykyyy.", "yyyyyyyyy"],
    "heart": [".rr...rr.", "rrrr.rrrr", "rrwrrrrrr", "rrrrrrrrr", ".rrrrrrr.", "..rrrrr..", "...rrr...", "....r...."],
    "ball": ["...ppp...", "..pwppp..", ".pwppppp.", ".ppppppp.", ".ppppppp.", "..ppppp..", "...ggg...", "..ggggg.."],
    "moon": ["..yyyy...", ".yyy.....", "yyy......", "yyy......", "yyy......", "yyy......", ".yyy.....", "..yyyy..."],
    "star": ["....y....", "....y....", "...yyy...", "yyyyyyyyy", ".yyyyyyy.", "..yyyyy..", ".yy...yy.", "yy.....yy"],
    "coin": ["..ggggg..", ".gyyyyyg.", "gyyykyyyg", "gyykkkyyg", "gyyykyyyg", "gyykkkyyg", ".gyykyyg.", "..ggggg.."],
    "wand": ["........y", ".......yy", "......yyy", ".....yy..", "....yy...", "...yy....", "..yy.....", ".yy......"],
    "crystal": ["....p....", "...ppp...", "..ppwpp..", ".pppwp...", "..ppwpp..", "...ppp...", "....p....", "....p...."],
    "fire": ["....o....", "...oro...", "...ryr...", "..ryoryr.", "..ryoryr.", "..ryoryr.", "...r.r...", "...rrr..."],
    "earth": ["....g....", "...ggg...", "..ggcgg..", ".ggggggg.", "..ggcgg..", "...ggg...", "....g....", "....g...."],
    "air": [".........", "ccc......", ".ccc.....", "..ccc....", "...ccc...", "....ccc..", ".....ccc.", "........."],
    "water": ["....b....", "...bbb...", "..bbbbb..", ".bbbbbbb.", "bbbwwbbb.", "bbbbbbbbb", ".bbbbbbb.", "...bbb..."],
}
ICON_RGB = {"y": (255, 204, 0), "k": (25, 25, 25), "r": (235, 40, 70), "w": (255, 255, 255),
            "p": (150, 80, 230), "g": (80, 190, 110), "b": (70, 170, 255),
            "c": (90, 225, 220), "o": (255, 140, 45)}
HEAVY = {"The Tower", "The Devil", "The Moon", "Ten of Swords", "Three of Swords", "Five of Swords",
         "Seven of Swords", "Nine of Swords", "Five of Pentacles"}
# Headlines stay gentle and true to a reading: no accusations, no promises, no fear-bait.
HOOKS = {
    "shadow": (["SHADOW WORK", "TURNING POINT", "A HARD CARD, GENTLY"],
               ["Some cards are heavy - and heavy cards still show the way through",
                "Six cards fell on their own - a few of them asked for honesty",
                "A reading about what you've been carrying, and how to set it down"]),
    "love": (["HEART MESSAGE", "LOVE & CONNECTION", "MATTERS OF THE HEART"],
             ["The cards had a lot to say about the heart",
              "A reading about the people who feel like home",
              "Six cards fell - most of them pointed to the heart"]),
    "money": (["WORK & ABUNDANCE", "PURPOSE & PATH", "BUILDING SOMETHING"],
              ["A reading about effort, timing and what you're building",
               "The cards spoke about work, worth and patience",
               "Six cards fell - here's what they said about your path"]),
    "spirit": (["SPIRIT MESSAGE", "DIVINE TIMING", "WRITTEN IN THE STARS"],
               ["If this found you, sit with it a moment",
                "Six cards fell on their own - here's what they said",
                "The deck chose these cards, not me"]),
    "calm": (["LIVE READING", "A GENTLE READING", "TONIGHT'S CARDS"],
             ["Whoever needs this - the deck chose these cards",
              "Take a breath - this one is gentle",
              "Six cards fell from the shuffle - here's what they said"]),
}
ZODIAC = "♈♉♊♋♌♍♎♏♐♑♒♓"
CELESTIAL = ["moon", "star", "★", "✦", "✧", "☀"]
SIGN_SYMBOLS = dict(zip(("aries", "taurus", "gemini", "cancer", "leo", "virgo", "libra",
                         "scorpio", "sagittarius", "capricorn", "aquarius", "pisces"), ZODIAC))
TITLE_DESIGNS = {
    "merlin": [
        (("crystal", "wand", "✦"), ("☾", "wand", "crystal")),
        (("✧", "crystal", "wand"), ("wand", "✦", "☽")),
        (("wand", "☾", "crystal"), ("✦", "crystal", "wand")),
    ],
    "lunar": [
        (("☾", "moon", "✦"), ("✧", "moon", "☽")),
        (("moon", "✧", "☽"), ("☾", "star", "moon")),
        (("✦", "☾", "moon"), ("moon", "☽", "✧")),
    ],
    "astrology": [
        (("✦", "☾", "star"), ("star", "☽", "✧")),
        (("☀", "✧", "moon"), ("moon", "✦", "☾")),
        (("star", "☽", "✦"), ("✧", "moon", "☀")),
    ],
    "fire": [
        (("fire", "✦", "wand"), ("✧", "fire", "☀")),
        (("☀", "fire", "star"), ("wand", "✦", "fire")),
        (("fire", "☾", "✧"), ("star", "fire", "✦")),
    ],
    "earth": [
        (("earth", "coin", "✦"), ("✧", "earth", "moon")),
        (("coin", "earth", "☾"), ("earth", "star", "✧")),
        (("earth", "✧", "coin"), ("☽", "earth", "✦")),
    ],
    "air": [
        (("air", "✦", "☾"), ("✧", "air", "star")),
        (("☀", "air", "✧"), ("air", "☽", "✦")),
        (("air", "star", "moon"), ("✦", "air", "☾")),
    ],
    "water": [
        (("water", "moon", "✦"), ("✧", "water", "☽")),
        (("☾", "water", "star"), ("water", "✦", "moon")),
        (("water", "✧", "☽"), ("star", "water", "✦")),
    ],
}
THEME_DESIGN = {"shadow": "merlin", "love": "lunar", "money": "earth", "spirit": "astrology", "calm": "merlin"}
TITLE_FRAGMENTS = {
    "shadow": ("a truth finding its way into the light", "the courage to set an old weight down", "a quiet turning point"),
    "love": ("a heart learning where it feels at home", "the tenderness beneath the question", "a softer way to stay connected"),
    "money": ("a new path beginning to take shape", "patience meeting possibility", "the work that is ready to grow"),
    "spirit": ("a small sign arriving at the right moment", "the wisdom waiting in the quiet", "a message taking shape between the stars"),
    "calm": ("a gentler way forward", "the feeling that is ready to be heard", "a little more room to breathe"),
}
_LAST_TITLE_DESIGN = None


def _title_symbols(sess, theme, rng):
    global _LAST_TITLE_DESIGN
    profile = dict(part.split(": ", 1) for part in sess.get("profile", "").split(", ") if ": " in part)
    from knowledge import parse_sign
    sign, element = parse_sign(profile.get("sign", ""))
    key = "astrology" if sign else (element if element in TITLE_DESIGNS else THEME_DESIGN[theme])
    designs = TITLE_DESIGNS[key]
    design = rng.choice(designs)
    for _ in range(8):
        if design != _LAST_TITLE_DESIGN:
            break
        design = rng.choice(designs)
    _LAST_TITLE_DESIGN = design
    left, right = map(list, design)
    if sign:
        left[0] = SIGN_SYMBOLS[sign.lower()]
    if element:
        right[-1] = element
    return tuple(left), tuple(right)


def make_hook(sess):
    """(left icons, right icons, title, line) for the pinned video headline."""
    if sess.get("hook"):
        h = tuple(sess["hook"])
        if len(h) == 4:
            left = h[0] if isinstance(h[0], (tuple, list)) else (h[0],)
            right = h[1] if isinstance(h[1], (tuple, list)) else (h[1],)
            return left, right, h[2], h[3]
    cards = [(c[0], bool(c[1])) for c in sess.get("spread", [])]
    names = [c for c, _ in cards]
    suit = lambda s: sum(1 for c in names if c.endswith(" of " + s))
    majors = sum(1 for c in names if " of " not in c.replace("Wheel of Fortune", "Wheel"))
    score = {"shadow": sum(c in HEAVY for c in names) * 1.5 + 0.5 * sum(r for _, r in cards),
             "love": suit("Cups") + 2 * sum(c in ("The Lovers", "Two of Cups", "Ten of Cups") for c in names),
             "money": suit("Pentacles") + 2 * sum(c in ("Wheel of Fortune", "Ten of Pentacles", "Ace of Pentacles") for c in names),
             "spirit": 0.7 * majors + 2 * sum(c in ("The Star", "The High Priestess", "Judgement", "The Hermit") for c in names),
             "calm": 1.0}
    rng = random.SystemRandom()
    theme = max(score, key=score.get)
    _, lines = HOOKS[theme]
    title = re.sub(r"\s+", " ", sess.get("video_title", "")).strip()
    if not title:
        title = rng.choice(TITLE_FRAGMENTS[theme])
    left, right = _title_symbols(sess, theme, rng)
    return left, right, title, rng.choice(lines)


class Painter:
    def __init__(self, sess):
        import numpy as np
        from PIL import Image, ImageDraw, ImageFilter
        import canvas
        self.np, self.Image, self.ImageDraw, self.ImageFilter, self.canvas = np, Image, ImageDraw, ImageFilter, canvas
        self.sess = sess
        self.cap_font = canvas.font(40, "DejaVuSans-Bold.ttf")
        self.caps, self.screens, self.cards, self.rot = {}, {}, {}, {}
        self.hook = make_hook(sess)
        self.base = np.asarray(self._backdrop()).copy()

    # ---------- static layers
    def _icon(self, name, px=6):
        if name not in ICONS:                              # a zodiac or star glyph, pixelated to match
            return self._glyph_icon(name, px)
        rows = ICONS[name]
        img = self.Image.new("RGBA", (len(rows[0]) * px, len(rows) * px), (0, 0, 0, 0))
        d = self.ImageDraw.Draw(img)
        for j, row in enumerate(rows):
            for i, ch in enumerate(row):
                if ch != ".":
                    d.rectangle([i * px, j * px, i * px + px - 1, j * px + px - 1], fill=ICON_RGB[ch] + (255,))
        return img

    def _glyph_icon(self, ch, px=6):
        np = self.np
        small = self.Image.new("L", (26, 26), 0)
        f = self.canvas.font(19, "DejaVuSans-Bold.ttf")
        self.ImageDraw.Draw(small).text((13, 13), ch, fill=255, font=f, anchor="mm", stroke_width=1, stroke_fill=255)
        m = np.asarray(small) > 100
        if not m.any():
            return self._icon("star", px)
        ys, xs = np.where(m.any(1))[0], np.where(m.any(0))[0]
        m = m[ys[0]:ys[-1] + 1, xs[0]:xs[-1] + 1]
        top, bot = np.array([255, 224, 120]), np.array([200, 120, 255])
        g = np.linspace(0, 1, m.shape[0])[:, None, None]
        rgb = (top * (1 - g) + bot * g).astype(np.uint8)
        rgba = np.zeros(m.shape + (4,), np.uint8)
        rgba[..., :3] = np.broadcast_to(rgb, m.shape + (3,))
        rgba[..., 3] = m * 255
        img = self.Image.fromarray(rgba, "RGBA")
        k = max(2, round(px * 9 / max(m.shape)))          # same size as the pixel sprites
        return img.resize((m.shape[1] * k, m.shape[0] * k), self.Image.NEAREST)

    def _backdrop(self):
        np, Image = self.np, self.Image
        import art
        W, H, S = OW // 8, BAND // 8, 8
        yy, xx = np.mgrid[0:H, 0:W]
        r = np.sqrt(((xx - W * 0.5) / W) ** 2 + ((yy - H * 0.45) / H) ** 2 * 0.8)
        hot, edge = np.array([238, 132, 42]), np.array([150, 12, 40])
        bayer = np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]) / 16.0
        k = np.clip(r * 1.6 + (bayer[yy % 4, xx % 4] - 0.5) * 0.18, 0, 1)
        k = np.round(k * 5) / 5
        low = (hot[None, None] * (1 - k[..., None]) + edge[None, None] * k[..., None]).astype(np.uint8)
        ink = (70, 8, 26)
        v = art.veyra_pixels()
        for j, row in enumerate(v):                       # her silhouette printed on the tapestry
            for i, c in enumerate(row):
                if c is not None:
                    low[6 + j * 2:8 + j * 2, 84 + i * 2:86 + i * 2] = ink
        cy, cx, R = 50, 22, 10                            # crescent moon
        m = ((yy - cy) ** 2 + (xx - cx) ** 2 <= R * R) & ~(((yy - cy + 2) ** 2 + (xx - cx - 5) ** 2) <= (R - 1) ** 2)
        low[m] = (255, 214, 110)
        rng = random.Random(11)
        for _ in range(40):
            low[rng.randrange(H - 2), rng.randrange(W)] = (255, 236, 170)
        t = art.text_pixels("VEYRA")
        for j, row in enumerate(t):
            for i, c in enumerate(row):
                if c is not None:
                    low[4 + j, 4 + i] = ink
        low[H - 1] = (205, 160, 60)                       # gold edge where the tapestry meets the table
        img = Image.fromarray(low).resize((OW, BAND), Image.NEAREST)
        full = Image.new("RGB", (OW, OH), CLOTH)
        full.paste(img, (0, 0))
        d = self.ImageDraw.Draw(full)
        d.rounded_rectangle([22, BOX_TOP - 2, OW - 22, BOX_TOP + BOX + 2], 18, outline=(120, 124, 150), width=3)
        d.text((OW / 2, 1840), "VEYRA  ✦  8-bit AI tarot", fill=(150, 130, 200), font=self.canvas.font(28), anchor="mm")
        self._pinned(full)
        return full

    def _boxes(self, img, lines, y, f, size, icon=None):
        d = self.ImageDraw.Draw(img)
        for n, ln in enumerate(lines):
            w = d.textlength(ln, font=f)
            pair = icon if isinstance(icon, (tuple, list)) else (icon, icon)
            if icon and n == 0 and len(pair) == 2 and isinstance(pair[0], (tuple, list)):
                left_names, right_names = pair
            else:
                left_names, right_names = ((pair[0],), (pair[1],)) if icon and n == 0 else ((), ())
            icon_size = max(4, size // 9)
            left_icons = [self._icon(name, icon_size) for name in left_names]
            right_icons = [self._icon(name, icon_size) for name in right_names]
            wl = sum(ic.width + 6 for ic in left_icons)
            wr = sum(ic.width + 6 for ic in right_icons)
            total = w + wl + wr
            x0 = (OW - total) / 2
            d.rounded_rectangle([x0 - 18, y - 6, x0 + total + 18, y + size + 14], 14, fill=(255, 255, 255))
            ix = x0
            for ic in left_icons:
                img.paste(ic, (int(ix), int(y + (size + 8 - ic.height) / 2)), ic)
                ix += ic.width + 6
            d.text((x0 + wl, y), ln, fill=(0, 0, 0), font=f)
            ix = x0 + wl + w + 6
            for ic in right_icons:
                img.paste(ic, (int(ix), int(y + (size + 8 - ic.height) / 2)), ic)
                ix += ic.width + 6
            y += size + 20
        return y

    def _wrap(self, text, f, width):
        d = self.ImageDraw.Draw(self.Image.new("RGB", (8, 8)))
        words, lines, cur = text.split(), [], ""
        for w in words:
            trial = (cur + " " + w).strip()
            if d.textlength(trial, font=f) <= width:
                cur = trial
            else:
                lines.append(cur)
                cur = w
        return lines + [cur]

    def _pinned(self, img):
        left, right, title, line = self.hook
        for size in (54, 48, 42, 38, 34):              # shrink until the whole title fits: never drop words
            f = self.canvas.font(size, "DejaVuSans-Bold.ttf")
            title_lines = self._wrap(title, f, OW - 450)
            if len(title_lines) <= 2:
                break
        y = self._boxes(img, title_lines[:3], 270, f, size, (left, right))
        f = self.canvas.font(54 if size >= 48 else 48, "DejaVuSans-Bold.ttf")
        self._boxes(img, self._wrap(line, f, OW - 200)[:3], y, f, f.size)

    # ---------- per-frame layers
    def ui(self, size):
        if size not in self.screens:
            import tarot
            rows, cols, cw, ch = size
            scr = self.canvas.VirtualScreen(rows, cols)
            self.screens[size] = (scr, tarot.UI(scr, self.sess.get("plan")), self.canvas.Raster(cw, ch))
        return self.screens[size]

    def caption(self, text):
        if text not in self.caps:
            img = self.Image.new("RGB", (OW, CAP_H), CLOTH)
            for size in (40, 36, 32, 28):
                f = self.canvas.font(size, "DejaVuSans-Bold.ttf")
                lines = self._wrap(text, f, OW - 150)
                if len(lines) * (size + 20) <= CAP_H - 8:
                    break
            self._boxes(img, lines, (CAP_H - len(lines) * (size + 20)) / 2 + 6, f, size)
            self.caps[text] = self.np.asarray(img)
        return self.caps[text]

    def card_image(self, card, rev):
        key = (card, bool(rev))
        if key not in self.cards:
            import tarot, art
            scr = self.canvas.VirtualScreen(15, 22)
            ui = tarot.UI(scr, self.sess.get("plan"))
            ui.cells(0, 0, art.card_cells(card, bool(rev), 22, 15))
            px = self.canvas.Raster(18, 36).render(scr)
            face = self.Image.fromarray(px)
            pad = 14
            img = self.Image.new("RGBA", (face.width + 2 * pad, face.height + 2 * pad), (0, 0, 0, 0))
            self.ImageDraw.Draw(img).rounded_rectangle([0, 0, img.width - 1, img.height - 1], 20, fill=(245, 242, 235, 255))
            img.paste(face, (pad, pad))
            self.cards[key] = img
        return self.cards[key]

    def rotated(self, card, rev, angle):
        a = round(angle * 2) / 2
        key = (card, bool(rev), a)
        if key not in self.rot:
            im = self.card_image(card, rev).rotate(a, resample=self.Image.BICUBIC, expand=True)
            sh = self.Image.new("RGBA", im.size, (0, 0, 0, 0))
            sh.putalpha(im.getchannel("A").point(lambda v: v * 0.55))
            sh = sh.filter(self.ImageFilter.GaussianBlur(12))
            self.rot[key] = (im, sh)
            if len(self.rot) > 400:
                self.rot.clear()
        return self.rot[key]

    def frame(self, content, cap=None, fade=1.0, held=None):
        np = self.np
        out = self.base.copy()
        h, w = content.shape[:2]
        if h > BOX:
            content, h = content[:BOX], BOX
        y, x = BOX_TOP + (BOX - h) // 2, (OW - w) // 2
        region = out[y:y + h, x:x + w]
        mask = content.max(axis=2) > 0                    # black terminal background becomes the cloth
        region[mask] = content[mask]
        if cap:
            out[CAP_TOP:CAP_TOP + CAP_H] = self.caption(cap)
        if held:
            out = self.hold_up(out, *held)
        if fade < 1.0:
            out = (out.astype(np.float32) * max(0.0, fade)).astype(np.uint8)
        return out

    def hold_up(self, out, cards, local, dur):
        """Cards lifted toward the camera while she reads them, then set back down."""
        rise, hold_end = 0.5, max(2.2, min(4.2, dur * 0.55, dur - 0.5))
        if local > hold_end + 0.45:
            return out
        if local < rise:
            k = 1 - (1 - local / rise) ** 3
        elif local > hold_end:
            k = 1 - ((local - hold_end) / 0.45) ** 2
        else:
            k = 1.0
        img = self.Image.fromarray(out)
        n = len(cards)
        for i, (c, r) in enumerate(cards):
            base_a = (-6 if n == 1 else (-9 if i == 0 else 7)) + 2.2 * math.sin(local * 1.4 + i)
            im, sh = self.rotated(c, r, base_a)
            cx = OW * (0.58 if n == 1 else (0.36 + 0.34 * i))
            cy = 900 + 10 * math.sin(local * 1.1 + i) + (1 - k) * 1300
            px, py = int(cx - im.width / 2), int(cy - im.height / 2)
            img.paste(sh, (px + 18, py + 26), sh)
            img.paste(im, (px, py), im)
        return self.np.asarray(img)


def scene_content(p, sc, t, sess):
    """Draw one moment of a scene on the virtual terminal and return its pixels."""
    import tarot
    key, spread = sess["key"], sess["spread"]
    name, local = sc["name"], t - sc["start"]
    if name.startswith("tx"):
        size = LARGE
    elif name in ("intro", "end") or (key in ("celtic", "falling") and (name == "table" or name.startswith("card"))) \
            or name.startswith(("ask", "drop", "read")):
        size = WIDE
    elif name == "interview" or name.startswith(("crowd", "flash")):
        size = LARGE
    else:
        size = SMALL
    scr, ui, ras = p.ui(size)
    scr.clock = t
    import psyche
    if name.startswith("flash"):
        ui._psy_spread = spread
        psyche.draw_flash(ui, sc, local)
        return ras.render(scr)
    if name.startswith("crowd"):
        psyche.draw_crowd(ui, sc, local)
        return ras.render(scr)
    if name.startswith("tx"):
        transmission_frame(ui, sc, local)
    elif name == "intro":
        ui.mood = ui.plan["intro"]
        ui.intro_frame("", footer="")
    elif name == "interview":
        lines = sess["_transcript"]
        n = min(len(lines), 3 + int(len(lines) * min(1.0, local / max(1.0, sc["dur"] * 0.85))))
        scr.erase()
        ui.stars(18)
        ui.gcenter(0, "~ what you brought to the table ~")
        for i, (txt, col) in enumerate(lines[:n][-(ui.h - 3):]):
            ui.text(2 + i, 2, txt[: ui.w - 3], col)
    elif name == "spirits":
        ui.hold_frame(sess.get("spirit_qs", []), footer="")
    elif name.startswith(("ask", "drop", "read")):
        import textwrap
        log = sess["falls"]["log"]
        e = log[sc["event"]]
        before = sum(len(x["idx"]) for x in log[:sc["event"]])
        cards = [tuple(c) for c in sess["spread"]]
        upto = before if name.startswith("ask") else before + len(e["idx"])
        pairs = [p for p in sess["falls"].get("pairs", []) if max(p) < upto]
        saved_slots = sess["falls"].get("slots")
        slot_upto = sc["event"] + (0 if name.startswith("ask") else 1)
        st = {"fallen": cards[:upto], "pairs": pairs,
            "slots": saved_slots[:slot_upto] if saved_slots else None,
            "pass_n": 13, "page": [],
            "pass_t0": sc["start"] + (local // 1.7) * 1.7}
        ui.mood = ui.plan["wash"]
        if name.startswith("ask"):
            st["page"] = textwrap.wrap(f"{e['opener']} {e['question']}", ui.w - 4)
            ui.falling_frame(st, footer="the deck shuffles...")
        elif name.startswith("drop"):
            st["page"] = textwrap.wrap(f"{e['opener']} {e['question']}", ui.w - 4)
            if local < 0.5:
                if sess["falls"].get("slots"):
                    st["drop"] = {"t0": sc["start"], "slot": e.get("slot", sc["event"]), "cards": e["idx"]}
                else:
                    st["drop"] = {"t0": sc["start"], "idx": e["idx"]}
            else:
                st["flip"] = (tuple(e["idx"]), min(8, int((local - 0.5) / 0.6 * 9)))
            ui.falling_frame(st, footer="a card falls!" if len(e["idx"]) == 1 else "two cards fall together!")
        else:
            room = max(3, ui.h - 19)
            lines = textwrap.wrap(e["text"], ui.w - 4)
            pages = [lines[i:i + room] for i in range(0, len(lines), room)] or [[]]
            st["page"] = pages[min(len(pages) - 1, int(local / max(0.1, sc["dur"]) * len(pages)))]
            ui.falling_frame(st, footer="")
    elif name == "ritual" and key == "falling":
        ui.mood = ui.plan["wash"]
        cycle = 1.7
        st = {"fallen": [], "pairs": [], "pass_t0": sc["start"] + (local // cycle) * cycle, "pass_n": 13, "page": []}
        ui.falling_frame(st, footer="")
    elif name == "ritual":
        wash_d = sc["dur"] * 0.55
        if local < wash_d:
            ui.mood = ui.plan["wash"]
            if "_wash" not in sess:
                sess["_wash"] = ui.wash_cards(78, random.Random(3))
            ui.wash_frame(sess["_wash"], int(local * 28))
        else:
            ui.mood = ui.plan["cut"]
            ph = min(0.999, (local - wash_d) / max(0.1, sc["dur"] - wash_d))
            k, f = min(2, int(ph * 3)), ph * 3 - min(2, int(ph * 3))
            sizes = [31, 22, 25]
            piles = [list(range(sizes[i])) if i < k else None for i in range(3)]
            hand = list(range(78 - sum(sizes[:k])))
            ui.draw_cut(hand, piles, None, None, "the cards fall...", refresh=False)
            x1, y1 = ui.w // 2 - tarot.PW // 2, 16
            x2, y2 = ui.w // 2 + (k - 1) * (tarot.PW + 10) - tarot.PW // 2, 5
            ui.stack(int(y1 + (y2 - y1) * min(1, f * 1.4)), int(x1 + (x2 - x1) * min(1, f * 1.4)), sizes[k], label=False)
    elif name == "table":
        ui.mood = ui.plan["reveal"]
        if key == "falling":
            falls = sess.get("falls") or {}
            ui.fall_pairs = falls.get("pairs", [])
            ui.fall_slots = falls.get("slots")
            ui.fall_questions = falls.get("questions", [None] * 6)
        live_done = key == "falling" and (sess.get("falls") or {}).get("log")
        saved_slots = (sess.get("falls") or {}).get("slots")
        visible = len(saved_slots) if saved_slots else len(spread)
        ui.reveal_scene(key, spread, visible if live_done else 0, None, "", sess.get("domain", "inner"))
    elif name.startswith("card"):
        i = sc["card"]
        ui.mood = ui.plan["reveal"]
        if key == "falling":
            ui.fall_pairs = (sess.get("falls") or {}).get("pairs", [])
            ui.fall_questions = (sess.get("falls") or {}).get("questions", [None] * 6)
        if local < 0.6:
            ui.reveal_scene(key, spread, i, (i, min(8, int(local / 0.6 * 9))), "", sess.get("domain", "inner"))
        else:
            ui.reveal_scene(key, spread, i + 1, None, "", sess.get("domain", "inner"))
    else:   # end card
        ui.mood = "hope"
        ui.intro_frame("", lines=["Thank you for sitting with me.", "", "The cards are gathered", "", "with gratitude."], footer="")
        ui.center(ui.h - 3, "local AI  •  real randomness", 123, True)
    return ras.render(scr)


def transmission_frame(ui, sc, local):
    """The message coming through the veil: glyphs resolving into her words under a flickering Veyra.
    Long messages turn like pages, each page decoding as it is spoken."""
    import textwrap, fx
    lines = textwrap.wrap(sc.get("message", ""), ui.w - 4)
    vy = 0
    room = max(1, ui.h - 16)
    pages = [lines[i:i + room] for i in range(0, len(lines), room)] or [[]]
    pos = min(0.999, local / max(0.5, sc["dur"] - 0.6)) * len(pages)
    pg, k = min(len(pages) - 1, int(pos)), min(1.0, (pos - int(pos)) * 1.6)
    ui.scr.erase()
    ui.stars(50, int(local * 3), "channel")
    ui.veyra(vy, ui.w // 2 - 13, 3.0)
    ui.gcenter(vy + 14, "~ transmission ~", local * 0.4, "channel")
    full = "\n".join(pages[pg])
    step = int(len(full) * k)
    rng = random.Random(int(local * 12))
    shown = "".join(c if (i < step or c in " \n") else rng.choice(fx.GLYPHS) for i, c in enumerate(full))
    for j, ln in enumerate(shown.split("\n")):
        ui.gcenter(vy + 16 + j, ln, local * 0.3 + j * 0.1, "channel")


def cutaway_content(p, shot, t, c0, sc, sess):
    """One frame of a cutaway shot (the other parts of the ritual, cut into the reading)."""
    import tarot
    key, spread = sess["key"], sess["spread"]
    local = t - c0
    if shot == "wash" and key != "falling":
        scr, ui, ras = p.ui(SMALL)
    else:
        scr, ui, ras = p.ui(WIDE)
    scr.clock = t
    live = key == "falling" and (sess.get("falls") or {}).get("log")
    if shot in ("drop", "wash") and live:
        log = sess["falls"]["log"]
        ev = sc.get("event", 0)
        if sc["name"].startswith("card"):
            ev = next((n for n, e in enumerate(log) if sc["card"] in e["idx"]), 0)
        e = log[ev]
        before = sum(len(x["idx"]) for x in log[:ev])
        cards = [tuple(c) for c in spread]
        slots = sess["falls"].get("slots")
        st = {"fallen": cards[:before], "pairs": [q for q in sess["falls"].get("pairs", []) if max(q) < before],
              "slots": slots[:ev] if slots else None, "pass_n": 13, "page": [],
              "pass_t0": c0 + (local // 1.7) * 1.7}
        ui.mood = ui.plan["wash"]
        if shot == "drop":
            st["fallen"] = cards[:before + len(e["idx"])]
            st["slots"] = slots[:ev + 1] if slots else None
            if local < 0.6:
                st["fallen"] = cards[:before]
                st["slots"] = slots[:ev] if slots else None
                st["drop"] = ({"t0": c0, "slot": e.get("slot", ev), "cards": e["idx"]} if slots
                              else {"t0": c0, "idx": e["idx"]})
            else:
                st["flip"] = (tuple(e["idx"]), min(8, int((local - 0.6) / 0.5 * 9)))
        ui.falling_frame(st, footer="")
    elif shot in ("drop", "wash"):
        ui.mood = ui.plan["wash"]
        if "_wash" not in sess:
            sess["_wash"] = ui.wash_cards(78, random.Random(3))
        ui.wash_frame(sess["_wash"], int(t * 28))
    elif shot == "veil":
        ui.scr.erase()
        ui.stars(50, 3, "channel")
        ui.veyra(ui.h // 2 - 11, ui.w // 2 - 13, 2.0)
        ui.gcenter(ui.h // 2 + 5, "the veil thins...", local * 0.6, "channel")
    elif shot == "veyra":
        ui.mood = ui.plan["intro"]
        ui.intro_frame("", lines=["", "", "she turns a page", "in her grimoire..."], footer="")
    elif shot == "stars":
        ui.scr.erase()
        ui.stars(140, 11, "mystic")
        ui.gcenter(ui.h // 2, "☾  ✦  ☽", local * 0.5, "mystic")
    else:                                                  # the whole table, as it lies now
        ui.mood = ui.plan["reveal"]
        upto = len(spread)
        if sc["name"].startswith("card"):
            upto = sc["card"] + 1
        if key == "falling":
            falls = sess.get("falls") or {}
            ui.fall_pairs, ui.fall_slots = falls.get("pairs", []), falls.get("slots")
            ui.fall_questions = falls.get("questions", [None] * 6)
            if live and sc["name"].startswith("read"):
                upto = len(falls["slots"][:sc["event"] + 1]) if falls.get("slots") else \
                    sum(len(x["idx"]) for x in falls["log"][:sc["event"] + 1])
        ui.reveal_scene(key, spread, upto, None, "", sess.get("domain", "inner"))
    return ras.render(scr)


def held_cards(sc, t, sess):
    """Which cards she holds up in this moment: (cards, seconds into scene, scene length) or None."""
    name, local = sc["name"], t - sc["start"]
    if name.startswith("read") and (sess.get("falls") or {}).get("log"):
        cards = [tuple(c) for c in sess["falls"]["log"][sc["event"]]["cards"]]
    elif name.startswith("card") and "card" in sc:
        if local < 0.6:                                   # let the flip on the table play first
            return None
        cards, local = [tuple(sess["spread"][sc["card"]])], local - 0.6
    else:
        return None
    return cards, local, sc["dur"] - (0.6 if name.startswith("card") else 0)


def transcript(sess):
    """The interview as it appeared in the terminal."""
    import textwrap
    from spreads import SPREADS
    rows = [("› " + sess["question"], 231), ("A few things to help me feel you out.", 51)]
    prof = dict(p.split(": ", 1) for p in sess.get("profile", "").split(", ") if ": " in p)
    for label, k in (("Your age?", "age"), ("Your career, or what you do?", "career"), ("Your sex or gender?", "sex/gender"),
                     ("Your astrological sign, or its element?", "sign")):
        if prof.get(k):
            rows += [(label, 103), ("› " + prof[k], 231)]
    for i, (q, a) in enumerate(sess.get("qa", [])):
        rows += [(q, 141 if i % 2 else 51), ("› " + (a or "(no answer)"), 231)]
    rows.append(("To the spirits, I ask:", 51))
    rows += [("• " + q, 189) for q in sess.get("spirit_qs", [])]
    if sess["key"] == "falling":
        for i, q in enumerate((sess.get("falls") or {}).get("questions", [])[1:], 2):
            if q:
                rows.append((f"Before card {i} fell, you asked: {q}", 220))
    else:
        rows += [("How shall the cards be laid?", 51), ("› " + SPREADS[sess["key"]]["name"], 231)]
    out = []
    for txt, col in rows:
        for j, ln in enumerate(textwrap.wrap(txt, 48) or [""]):
            out.append(("  " + ln if j else ln, col))
    return out


# ================================================================ the whole thing
def compose(p, titles, pop, scenes, sc, t, sess, cuts, cap, fade):
    """One finished frame: the scene or a cutaway, title cards, word pops and the cuts between them."""
    import edit
    name, local = sc["name"], t - sc["start"]
    cut = next((c for c in cuts if c[0] <= t < c[1]), None)
    if name.startswith(("txin", "living")):
        out = p.frame(p.np.zeros((BOX, 1029, 3), p.np.uint8), cap, fade)
        out[BOX_TOP:BOX_TOP + BOX, 26:26 + 1029] = titles.draw(sc["title"], sc["anim"], local, sc["dur"],
                                                               "tx" if name.startswith("txin") else "living")
    elif cut:
        out = p.frame(cutaway_content(p, cut[2], t, cut[0], sc, sess), cap, fade)
    else:
        out = p.frame(scene_content(p, sc, t, sess), cap, fade, held_cards(sc, t, sess))
    # word tricks: the spoken word punches in right on the cut
    for c0, c1, shot, word, _ in cuts:
        if word and c0 - 0.15 <= t < c0 + 0.6:
            out = out.copy()
            out = pop.draw(out, word, (t - (c0 - 0.15)) / 0.75, OW / 2, BOX_TOP + BOX * 0.5)
    # the cuts themselves: a whip in and out of each cutaway
    for c0, c1, *_ in cuts:
        for edge, direc in ((c0, 1), (c1, -1)):
            if abs(t - edge) < 0.12:                      # only the picture on the cloth moves, never the words
                if not out.flags.writeable:
                    out = out.copy()
                box = out[BOX_TOP:BOX_TOP + BOX, 26:26 + 1029]
                out[BOX_TOP:BOX_TOP + BOX, 26:26 + 1029] = edit.whip(box, 1 - abs(t - edge) / 0.12, direc)
    # into the spirit realm: a burst of static; back to the living: a warm flash
    if name.startswith("txin") and local < 0.35:
        out = edit.static_burst(out, 1 - local / 0.35, int(t * 30))
    if name.startswith("tx") and not name.startswith("txin") and local < 0.2:
        out = edit.static_burst(out, 0.6 * (1 - local / 0.2), int(t * 30))
    if name.startswith("living") and local < 0.3:
        out = edit.flash(out, 1 - local / 0.3)
    nxt = scenes[scenes.index(sc) + 1] if scenes.index(sc) + 1 < len(scenes) else None
    if nxt and nxt["name"].startswith("txin") and sc["start"] + sc["dur"] - t < 0.25:
        out = edit.static_burst(out, 1 - (sc["start"] + sc["dur"] - t) / 0.25, int(t * 30))
    return out


def render(sess, out_path, voice_kind, say=print, progress=None):
    import deps
    sess = dict(sess)
    sess["_transcript"] = transcript(sess)
    voice = working_voice(voice_kind, say)
    say(f"Writing her lines and voicing them ({voice.kind or 'captions only'})...")
    import edit, psyche
    trip = bool(sess.get("psy") or psyche.active())
    script = build_script(sess)
    if trip:                                   # psilocybin mode: the fast-cut trip
        script = psyche.trip_script(script, sess)
    scenes, events, total = plan(script, voice, say)
    flips = [sc["start"] for sc in scenes if sc["name"].startswith(("card", "drop"))]
    cuts = edit.plan_cuts(scenes, events, sess)
    sfx = []
    for sc in scenes:
        if sc["name"].startswith("txin"):
            sfx.append((sc["start"] - 0.1, edit.static_sfx(SR)))
        elif sc["name"].startswith("living"):
            sfx.append((sc["start"] - 0.15, edit.static_sfx(SR, 0.3)))
    for c0, c1, shot, word, _ in cuts:
        sfx.append((c0 - 0.08, edit.swish_sfx(SR)))
        sfx.append((c1 - 0.08, edit.swish_sfx(SR)))
    say(f"Edit: {sum(1 for s in scenes if s['name'].startswith('txin'))} spirit transmissions, {len(cuts)} cutaways.")
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as d:
        wav = Path(d) / "audio.wav"
        say("Composing the music...")
        mix_audio(events, flips, total, wav, sfx)
        import pixelstyle
        if pixelstyle.wanted(trip):                        # the promo's 8-bit look (TAROT_VIDEO_STYLE=classic for the old one)
            say("Drawing the frames (8-bit)...")
            return pixelstyle.encode(scenes, events, total, wav, out_path, sess, FPS, progress)
        p = Painter(sess)
        titles = edit.Titles(p, 1029, BOX)
        pop = edit.WordPop(p)
        cmd = [deps.ffmpeg(), "-y", "-hide_banner", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
               "-s", f"{OW}x{OH}", "-r", str(FPS), "-i", "-", "-i", str(wav), *OUT_SCALE, "-c:v", "libx264", "-preset", "veryfast",
               "-crf", "21", "-pix_fmt", "yuv420p", "-r", "30", "-c:a", "aac", "-b:a", "160k", "-shortest",
               "-movflags", "+faststart", str(out_path)]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        frames = int(total * FPS)
        ev = sorted(events, key=lambda e: e[0])
        say("Drawing the frames...")
        psyche.FORCE = trip
        trip_cuts = {int(sc["start"] * FPS) for sc in scenes if sc["name"].startswith(("flash", "crowd"))}
        for n in range(frames):
            psyche.CLOCK = n / FPS
            t = n / FPS
            sc = next(s for s in reversed(scenes) if s["start"] <= t) if t >= 0 else scenes[0]
            cap = sc["flash"] if "flash" in sc else next((c for at, c, _, d in ev if at <= t < at + d + 0.25), None)
            fade = 1.0 if sc["name"] != "end" else min(1.0, (total - t) / 1.2)
            out = compose(p, titles, pop, scenes, sc, t, sess, cuts, cap, fade)
            try:
                if trip:
                    out = psyche.trip_frame(out, t, n in trip_cuts and (n // 3) % 2 == 0)
                proc.stdin.write(out.tobytes())
            except BrokenPipeError:
                break
            if progress and n % FPS == 0:
                progress(n / frames)
        psyche.FORCE, psyche.CLOCK = None, None
        proc.stdin.close()
        err = proc.stderr.read().decode(errors="ignore")
        if proc.wait() != 0:
            raise RuntimeError("ffmpeg could not encode the video: " + err[-300:])
    if progress:
        progress(1.0)
    return out_path


def make(sess, ask=None, say=None, progress=None):
    """Check what is needed (asking before installing anything), then render. Returns a path or None."""
    import deps
    ask, say = ask or deps.default_ask, say or deps.default_say
    if not deps.ensure_python({"numpy": "numpy", "PIL": "pillow"}, ask, say, "Making a video"):
        return None
    if not deps.ensure_ffmpeg(ask, say):
        return None
    voice = deps.ensure_voice(ask, say)
    out = VIDEOS / f"veyra_{time.strftime('%Y%m%d_%H%M%S')}.mp4"
    try:
        return render(sess, out, voice, say, progress)
    except Exception as e:
        say(f"The video could not be finished: {str(e)[:200]}")
        return None
