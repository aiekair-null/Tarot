"""The editor's pass over a reading video: pacing, cutaways, word tricks and spirit transmissions.

* Spirit Realm Transmissions are their own segments. A title card cuts in (static, then an
  animated title), the message comes through the veil in a radio-filtered voice, then a
  "Words for the Living" card cuts back to the reading.
* Cutaways keep the reading moving. When she says a word that has a matching shot ("falls",
  "shuffle", "spirits", "grimoire", "stars", "table"...), the picture cuts to that shot on that
  word, and the word itself punches onto the screen across the cut. Long stretches with no
  keyword get a quiet cutaway so the picture never sits still for long.
* Title animations are drawn frame by frame in the 8-bit style: decode, stagger-rise with a
  spring, scanline wipe, RGB glitch, tracking-in, typewriter and split-flap. Each video picks
  different titles and animations, and never repeats one inside the same video.
"""
import math, random, re

# ---------------------------------------------------------------- titles
TX_TITLES = ["SPIRIT REALM TRANSMISSION", "INCOMING FROM THE OTHER SIDE", "THE VEIL THINS",
             "A SIGNAL FROM BEYOND", "VOICES THROUGH THE VEIL", "TRANSMISSION RECEIVED",
             "MESSAGE FROM THE SPIRIT REALM", "THE OTHER SIDE IS SPEAKING"]
TX_SPOKEN = {"SPIRIT REALM TRANSMISSION": "Spirit realm transmission.",
             "INCOMING FROM THE OTHER SIDE": "Incoming, from the other side.",
             "THE VEIL THINS": "The veil thins.",
             "A SIGNAL FROM BEYOND": "A signal, from beyond.",
             "VOICES THROUGH THE VEIL": "Voices, through the veil.",
             "TRANSMISSION RECEIVED": "Transmission received.",
             "MESSAGE FROM THE SPIRIT REALM": "A message from the spirit realm.",
             "THE OTHER SIDE IS SPEAKING": "The other side is speaking."}
LIVING_TITLES = ["WORDS FOR THE LIVING", "BACK TO THE LIVING", "FOR THOSE STILL HERE",
                 "RETURNING TO THE CLOTH", "NOW, FOR THE LIVING"]
LIVING_SPOKEN = {"WORDS FOR THE LIVING": "Now, words for the living.",
                 "BACK TO THE LIVING": "Back to the living.",
                 "FOR THOSE STILL HERE": "And for those still here.",
                 "RETURNING TO THE CLOTH": "Returning to the cloth.",
                 "NOW, FOR THE LIVING": "Now, for the living."}
ANIMS = ["decode", "stagger", "wipe", "glitch", "track", "typewriter", "flap"]
SCRAMBLE = "▓▒░#%&@$*+=?/\\<>~^:;0123456789ABCDEFGHJKMNPQRSTUVWXYZ✦✧☾☽"


def video_rng(sess):
    """Same reading, same edit; a different reading, a different edit."""
    return random.Random("edit:" + str(sess.get("date", "")) + str(sess.get("spread", "")))


# ---------------------------------------------------------------- messages from the other side
def transmissions(sess, n, rng):
    """Channeled messages for this reading: the ones she received live, else woven from her memory."""
    msgs = [m for m in sess.get("channeled") or [] if m and m.strip()]
    if len(msgs) >= n:
        return msgs[:n]
    try:
        import json, spirit
        from pathlib import Path
        from agent import _scrub_think
        mem = _scrub_think(json.loads(Path("memory.json").read_text(encoding="utf-8"))) if Path("memory.json").exists() else {}
        cards = ", ".join(c + (" (reversed)" if r else "") for c, r in sess.get("spread", []))
        ctx = f"Question: {sess.get('question', '')}. Cards: {cards}"
        tries = 0
        while len(msgs) < n and tries < 12:
            tries += 1
            omen, chosen = spirit.gather(mem, ctx, rng)
            m = spirit.weave(omen, chosen, rng)
            if m not in msgs:
                msgs.append(m)
    except Exception:
        pass
    while len(msgs) < n:
        msgs.append("The spirits lean close. What you set down will wait; what you carry will bend you.")
    return msgs


def _split(text):
    out = []
    for s in re.split(r"(?<=[.!?])\s+", re.sub(r"\s+", " ", text).strip()):
        if len(s) > 3:
            out.append(s if len(s) < 230 else s[:227].rsplit(" ", 1)[0] + "...")
    return out


def segment(k, message, rng, used):
    """The three scenes of one transmission: title in, the message, title back to the living."""
    t_in = rng.choice([t for t in TX_TITLES if t not in used] or TX_TITLES)
    t_out = rng.choice([t for t in LIVING_TITLES if t not in used] or LIVING_TITLES)
    used.update((t_in, t_out))
    anims = [a for a in ANIMS if a not in used] or ANIMS[:]
    a_in = rng.choice(anims)
    used.add(a_in)
    anims = [a for a in ANIMS if a not in used] or [a for a in ANIMS if a != a_in]
    a_out = rng.choice(anims)
    used.add(a_out)
    return [{"name": f"txin{k}", "title": t_in, "anim": a_in, "lines": [TX_SPOKEN[t_in]], "radio": True},
            {"name": f"tx{k}", "message": message, "lines": _split(message), "radio": True},
            {"name": f"living{k}", "title": t_out, "anim": a_out, "lines": [LIVING_SPOKEN[t_out]]}]


PADDED = {"three": 2, "falling": 2}       # spread -> spirit transmissions woven in (others get none)


def weave_in(scenes, sess):
    """Spirit transmissions pad the short spreads (3-card and the 6-card fall: two messages between
    the cards). The 10-card Celtic Cross is long enough already, so it stays streamlined: none."""
    rng = video_rng(sess)
    reads = [i for i, s in enumerate(scenes) if s["name"].startswith(("read", "card"))]
    if not reads or sess.get("key") not in PADDED:
        return scenes
    n = min(PADDED[sess["key"]], max(1, len(reads) - 1))
    msgs = transmissions(sess, n, rng)
    # after these reading scenes (evenly spread, never after the last one)
    picks = sorted({reads[max(0, min(len(reads) - 2, round((j + 1) * len(reads) / (n + 1)) - 1))] for j in range(n)})
    used, out, k = set(), [], 0
    for i, s in enumerate(scenes):
        out.append(s)
        if i in picks and k < len(msgs):
            out += segment(k, msgs[k], rng, used)
            k += 1
    return out


# ---------------------------------------------------------------- cutaways on words
SIGNS = r"aries|taurus|gemini|cancer|leo|virgo|libra|scorpio|sagittarius|capricorn|aquarius|pisces"
KEYWORDS = [
    (r"\b(fall|falls|fell|fallen|drop|drops)\b", "drop"),
    (r"\b(shuffle\w*|deck|wash\w*|riffle\w*)\b", "wash"),
    (r"\b(spirits?|veil|beyond|ghosts?|ancestors?)\b", "veil"),
    (r"\b(grimoire|lore|memory|remember|wrote|written)\b", "veyra"),
    (r"\b(zodiac|stars?|moon|sky|" + SIGNS + r"|water|fire|air|earth)\b", "stars"),
    (r"\b(table|cloth|position|spread)\b", "table"),
]
QUIET = ["veyra", "stars", "table", "veil"]
INSERT_LEN, MIN_GAP, MAX_STILL = 1.5, 4.0, 9.0       # calm pacing: one word-cut per card, a quiet cut only after ~9s still
TRIP_GAP, TRIP_STILL = 2.3, 4.6                       # psilocybin mode keeps the old fast cutting


def _hold_window(sc):
    """Seconds at the start of a scene when a card is held up to the camera (no cutaways then)."""
    dur = sc["dur"] - (0.6 if sc["name"].startswith("card") else 0)
    hold_end = max(2.2, min(4.2, dur * 0.55, dur - 0.5))
    return (0.6 if sc["name"].startswith("card") else 0) + hold_end + 0.5


def plan_cuts(scenes, events, sess, calm=True):
    """[(start, end, shot, word or None, scene name)] for every cutaway in the reading.
    First the cuts that land on a spoken keyword; then quiet cutaways fill any stretch that sits still too long.
    calm (every mode but psilocybin): at most one word-cut per card, quiet cuts only after a long still
    stretch, and none at all in the streamlined 10-card Celtic Cross."""
    rng = video_rng(sess)
    MIN_GAP, MAX_STILL = (globals()["MIN_GAP"], globals()["MAX_STILL"]) if calm else (TRIP_GAP, TRIP_STILL)
    per_scene = 1 if calm else 99
    fill = not (calm and sess.get("key") == "celtic")
    cuts = []
    for sc in scenes:
        if not sc["name"].startswith(("read", "card")):
            continue
        s0, s1 = sc["start"], sc["start"] + sc["dur"]
        free, end = s0 + _hold_window(sc), s1 - 0.4
        hits = []
        for at, cap, _, d in events:
            if not (s0 <= at < s1):
                continue
            for m in re.finditer(r"[A-Za-z']+", cap):
                for pat, shot in KEYWORDS:
                    if re.fullmatch(pat, m.group(0), re.I):
                        hits.append((at + d * m.start() / max(1, len(cap)), shot, m.group(0)))
                        break
        mine = []
        for wt, shot, word in sorted(hits):                # pass 1: cuts on the words
            c0 = wt - 0.05
            if c0 < free or c0 + INSERT_LEN > end:
                continue
            if mine and c0 - mine[-1][1] < MIN_GAP:
                continue
            if mine and mine[-1][2] == shot and c0 - mine[-1][1] < 6:
                continue                                    # don't show the same cutaway twice in a row
            mine.append((c0, c0 + INSERT_LEN, shot, word, sc["name"]))
            if len(mine) >= per_scene:
                break
        # pass 2: fill long still stretches with quiet cutaways
        qi = rng.randrange(len(QUIET))
        filled, prev = [], free - MIN_GAP
        for nxt in mine + [(end + MIN_GAP, None, None, None, None)]:
            while fill and nxt[0] - prev > MAX_STILL + INSERT_LEN + MIN_GAP:
                q0 = prev + MAX_STILL if filled or prev > free - MIN_GAP else max(free, prev + MAX_STILL)
                q0 = max(q0, free)
                if q0 + INSERT_LEN > min(end, nxt[0] - MIN_GAP):
                    break
                shot = QUIET[qi % len(QUIET)]
                if mine and any(abs(q0 - m[0]) < 6 and m[2] == shot for m in mine):
                    qi += 1
                    shot = QUIET[qi % len(QUIET)]
                filled.append((q0, q0 + INSERT_LEN, shot, None, sc["name"]))
                qi += 1
                prev = q0 + INSERT_LEN
            if nxt[1] is not None:
                filled.append(nxt)
                prev = nxt[1]
        cuts += filled
    seen, out = set(), []
    for c in sorted(cuts):                                  # each word only punches onto the screen once
        w = (c[3] or "").lower()
        out.append(c if w and w not in seen else c[:3] + (None,) + c[4:])
        seen.add(w)
    return out


# ---------------------------------------------------------------- drawing helpers
def ease_out(x):
    x = min(max(x, 0.0), 1.0)
    return 1 - (1 - x) ** 3


def spring(x, k=6.0, w=12.0):
    """Overshoot a little, then settle at 1."""
    if x <= 0:
        return 0.0
    return 1 - math.exp(-k * x) * math.cos(w * x)


class Titles:
    """Animated title cards, drawn in chunky pixels (rendered small, scaled up with no smoothing)."""
    PX = 3                                                  # one art pixel = 3 screen pixels

    def __init__(self, painter, w, h):
        self.p, self.w, self.h = painter, w, h
        self.np, self.Image, self.ImageDraw = painter.np, painter.Image, painter.ImageDraw
        self.font = painter.canvas.font(30, "DejaVuSans-Bold.ttf")
        self.small = painter.canvas.font(12, "DejaVuSansMono-Bold.ttf")
        self._bg = {}

    def lines(self, text):
        sw = self.w // self.PX - 30
        d = self.ImageDraw.Draw(self.Image.new("L", (4, 4)))
        words, out, cur = text.split(), [], ""
        for wd in words:
            trial = (cur + " " + wd).strip()
            if d.textlength(trial, font=self.font) <= sw:
                cur = trial
            else:
                out.append(cur)
                cur = wd
        return [ln for ln in out + [cur] if ln]

    def background(self, kind, t):
        np = self.np
        sw, sh = self.w // self.PX, self.h // self.PX
        if kind == "tx":
            rng = np.random.default_rng(int(t * 30))
            noise = rng.integers(0, 38, (sh, sw), dtype=np.int16)
            base = np.zeros((sh, sw, 3), np.int16)
            base[..., 0], base[..., 1], base[..., 2] = 6 + noise // 3, 10 + noise // 2, 26 + noise
            base[::3] //= 2                                 # scanlines
            band = int((t * 90) % sh)                       # a rolling bright band, like a tuning TV
            base[max(0, band - 4):band + 4] += 26
            return np.clip(base, 0, 255).astype(np.uint8)
        if kind not in self._bg:
            yy, xx = np.mgrid[0:sh, 0:sw]
            r = np.sqrt(((xx - sw / 2) / sw) ** 2 + ((yy - sh / 2) / sh) ** 2)
            k = np.clip(1 - r * 1.8, 0, 1)
            bay = np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]) / 16.0
            k = np.round((k + (bay[yy % 4, xx % 4] - 0.5) * 0.15) * 5) / 5
            warm, cloth = np.array([120, 70, 30]), np.array([10, 14, 40])
            self._bg[kind] = (cloth * (1 - k[..., None]) + warm * k[..., None]).clip(0, 255).astype(np.uint8)
        return self._bg[kind].copy()

    def _glyph(self, ch, color, alpha=255):
        im = self.Image.new("RGBA", (40, 40), (0, 0, 0, 0))
        d = self.ImageDraw.Draw(im)
        d.fontmode = "1"
        d.text((2, 2), ch, font=self.font, fill=color + (alpha,), stroke_width=1, stroke_fill=(0, 0, 0, alpha))
        return im

    def draw(self, text, anim, local, dur, kind):
        """One frame of a title card (w x h RGB array)."""
        np = self.np
        rng = random.Random(int(local * 24) * 7919 + len(text))
        sw, sh = self.w // self.PX, self.h // self.PX
        img = self.Image.fromarray(self.background(kind, local))
        d = self.ImageDraw.Draw(img)
        d.fontmode = "1"
        col = (130, 235, 255) if kind == "tx" else (255, 214, 120)
        accent = (200, 120, 255) if kind == "tx" else (255, 150, 80)
        lines = self.lines(text)
        lh = 40
        y0 = sh // 2 - len(lines) * lh // 2 - 6
        p = min(1.0, local / max(0.4, min(1.2, dur * 0.55)))      # animation progress
        out_k = max(0.0, (local - (dur - 0.25)) / 0.25)            # last 0.25 s: quick fade out
        n_all = sum(len(ln) for ln in lines)
        idx = 0
        for j, ln in enumerate(lines):
            widths = [d.textlength(c, font=self.font) for c in ln]
            total = sum(widths)
            track = 0.0
            if anim == "track":                                    # letter spacing collapses inward
                track = (1 - ease_out(p)) * 14
            x = sw / 2 - (total + track * (len(ln) - 1)) / 2
            y = y0 + j * lh
            for i, c in enumerate(ln):
                gi = idx / max(1, n_all - 1)
                ch, dx, dy, a, cc = c, 0.0, 0.0, 255, col
                if anim == "decode":                               # scrambled glyphs resolve left to right
                    if p < gi * 0.85 + 0.15 and c != " ":
                        ch, cc = rng.choice(SCRAMBLE), accent
                elif anim == "stagger":                            # letters rise in, one after another, with a spring
                    q = (local - gi * 0.55) / 0.5
                    dy, a = (1 - spring(q)) * 30, int(255 * min(1, max(0, q * 2)))
                elif anim == "wipe":                               # a scanline sweeps across and leaves the title behind
                    edge = ease_out(p) * (sw + 40) - 20
                    if x + widths[i] / 2 > edge:
                        a = 0
                elif anim == "glitch":                             # torn and colour-split, settling into place
                    if p < 1 and rng.random() < 0.5 * (1 - p):
                        dx, ch = rng.uniform(-10, 10) * (1 - p), rng.choice(SCRAMBLE) if rng.random() < 0.3 else c
                elif anim == "track":
                    a = int(255 * ease_out(p))
                elif anim == "typewriter":                         # typed out with a block cursor
                    if gi > p * 1.02:
                        a = 0
                elif anim == "flap":                               # split-flap board: each letter clicks through
                    settle = gi * 0.7 + 0.3
                    if p < settle and c != " ":
                        ch, cc = rng.choice(SCRAMBLE[30:]), accent
                        dy = 4 * math.sin(local * 40 + i)
                a = int(a * (1 - out_k))
                if a > 0 and ch != " ":
                    if anim == "glitch" and p < 1:
                        sh_ = int(4 * (1 - p)) + 1
                        img.paste(self._glyph(ch, (255, 40, 90), a), (int(x + dx - sh_), int(y + dy)), self._glyph(ch, (255, 40, 90), a))
                        img.paste(self._glyph(ch, (40, 220, 255), a), (int(x + dx + sh_), int(y + dy)), self._glyph(ch, (40, 220, 255), a))
                    g = self._glyph(ch, cc, a)
                    img.paste(g, (int(x + dx), int(y + dy)), g)
                x += widths[i] + track
                idx += 1
            if anim == "typewriter" and j == len(lines) - 1 and int(local * 3) % 2 == 0 and out_k < 1:
                shown = int(p * 1.02 * n_all) - sum(len(l) for l in lines[:-1])
                cx = sw / 2 - total / 2 + sum(widths[:max(0, min(len(ln), shown))])
                d.rectangle([cx + 2, y + 6, cx + 14, y + 34], fill=col)
        if anim == "wipe" and p < 1:                               # the bright scanning edge
            edge = ease_out(p) * (sw + 40) - 20
            d.rectangle([edge - 1, y0 - 8, edge + 1, y0 + len(lines) * lh + 8], fill=(255, 255, 255))
        # a small label that sets the tone: a blinking signal light, or the cloth's gold rule
        if kind == "tx":
            if int(local * 2.5) % 2 == 0:
                d.ellipse([16, 14, 24, 22], fill=(255, 50, 70))
            d.text((30, 12), "SIGNAL  ·  SPIRIT REALM", font=self.small, fill=(150, 200, 230))
        else:
            ww = int(ease_out(p) * 80)
            d.rectangle([sw // 2 - ww, y0 + len(lines) * lh + 10, sw // 2 + ww, y0 + len(lines) * lh + 11], fill=accent)
        big = img.resize((sw * self.PX, sh * self.PX), self.Image.NEAREST)
        arr = np.asarray(big)
        return arr[:self.h, :self.w]


class WordPop:
    """The spoken word punched onto the screen right at the cut: it bridges one shot to the next."""

    def __init__(self, painter):
        self.p = painter
        self.font = painter.canvas.font(46, "DejaVuSans-Bold.ttf")
        self.cache = {}

    def sprite(self, word):
        if word not in self.cache:
            Image, ImageDraw = self.p.Image, self.p.ImageDraw
            w = word.upper()
            d = ImageDraw.Draw(Image.new("L", (4, 4)))
            tw = int(d.textlength(w, font=self.font)) + 16
            im = Image.new("RGBA", (tw, 64), (0, 0, 0, 0))
            dd = ImageDraw.Draw(im)
            dd.fontmode = "1"
            dd.text((8, 4), w, font=self.font, fill=(255, 240, 170, 255), stroke_width=3, stroke_fill=(20, 6, 40, 255))
            self.cache[word] = im.resize((im.width * 3, im.height * 3), Image.NEAREST)
        return self.cache[word]

    def draw(self, out, word, k, cx, cy):
        """k: 0..1 over the pop's life. Slams in a touch large, settles, then fades."""
        if k <= 0 or k >= 1:
            return out
        Image = self.p.Image
        sp = self.sprite(word)
        scale = 1.35 - 0.35 * ease_out(k / 0.25) if k < 0.25 else 1.0
        alpha = 1.0 if k < 0.65 else 1 - (k - 0.65) / 0.35
        im = sp.resize((max(1, int(sp.width * scale)), max(1, int(sp.height * scale))), Image.NEAREST)
        if alpha < 1:
            im.putalpha(im.getchannel("A").point(lambda v: int(v * alpha)))
        base = Image.fromarray(out)
        base.paste(im, (int(cx - im.width / 2), int(cy - im.height / 2)), im)
        return self.p.np.asarray(base)


# ---------------------------------------------------------------- cuts between shots
def static_burst(out, k, seed):
    """A burst of TV static over the picture (k: strength 0..1). Used when the veil opens and closes."""
    import numpy as np
    if k <= 0:
        return out
    h, w = out.shape[:2]
    rng = np.random.default_rng(seed)
    blocks = rng.integers(0, 256, (h // 8 + 1, w // 8 + 1), dtype=np.uint8)
    noise = np.repeat(np.repeat(blocks, 8, 0), 8, 1)[:h, :w]
    tint = np.stack([noise * 0.75, noise * 0.9, noise], -1)
    mixed = out.astype(np.float32) * (1 - k) + tint * k
    if k > 0.3:                                             # colour split while the signal is torn
        sh = int(14 * k)
        mixed[..., 0] = np.roll(mixed[..., 0], sh, 1)
        mixed[..., 2] = np.roll(mixed[..., 2], -sh, 1)
    return mixed.clip(0, 255).astype(np.uint8)


def flash(out, k, color=(255, 236, 190)):
    """A soft flash to warm light (k 0..1): the way back to the living."""
    import numpy as np
    if k <= 0:
        return out
    c = np.array(color, np.float32)
    return (out.astype(np.float32) * (1 - k) + c * k).clip(0, 255).astype(np.uint8)


def whip(out, k, direction=1):
    """A quick whip-pan smear for cutaways (k 0..1, strongest at 1)."""
    import numpy as np
    if k <= 0:
        return out
    sh = int(60 * k) * direction
    acc = out.astype(np.float32)
    for s in (sh // 3, 2 * sh // 3, sh):
        acc += np.roll(out, s, 1)
    return (acc / 4).astype(np.uint8)


# ---------------------------------------------------------------- the voice through the veil
def radio(a, sr):
    """A voice from the other side: thin band, a slow waver, a little hiss."""
    import numpy as np
    if a is None or len(a) == 0:
        return a
    from video import _lowpass
    hp = a - _lowpass(a, 0.06)
    x = _lowpass(hp, 0.45)
    t = np.arange(len(x)) / sr
    x = x * (0.85 + 0.15 * np.sin(2 * np.pi * 5.5 * t))
    x = x + np.random.default_rng(3).normal(0, 0.012, len(x)).astype(np.float32)
    return (x / max(1e-6, np.abs(x).max()) * 0.9).astype(np.float32)


def static_sfx(sr, sec=0.45):
    import numpy as np
    n = int(sr * sec)
    env = np.exp(-np.linspace(0, 5, n)) * np.minimum(1, np.linspace(0, 40, n))
    return (np.random.default_rng(9).normal(0, 1, n) * env * 0.12).astype(np.float32)


def swish_sfx(sr, sec=0.22):
    import numpy as np
    n = int(sr * sec)
    noise = np.random.default_rng(5).normal(0, 1, n)
    k = np.linspace(0, 1, n)
    from video import _lowpass
    sig = _lowpass(noise.astype(np.float32), 0.15) * np.sin(np.pi * k) ** 2
    return (sig / max(1e-6, np.abs(sig).max()) * 0.06).astype(np.float32)
