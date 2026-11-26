"""Every Veyra video in the promo's 8-bit style.

video.py (readings) and promo.py (the intro) plan their scenes, voice and music as before; this module
draws the frames with the promo renderer's look (veyra_promo.py): dithered sanctum, twinkling stars,
pixel Veyra who talks, typed caption cards, bloom, vignette, CRT scanlines and glitch cuts.
Set TAROT_VIDEO_STYLE=classic for the old look."""
import math
import os
import random
import subprocess
import tempfile
import textwrap
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import veyra_promo as VP
from veyra_promo import W, H, put_text, hexrgb, spring, ease_out_cubic, paste_glow, paste_card

SCALE = max(1, VP.OUT_RES // W)  # 270x480 -> 540x960 for now (TAROT_VIDEO_RES=1080 -> 1080x1920)
GOLD, CYAN, WHITE, LILAC, RED = hexrgb("#ffd36b"), hexrgb("#4ff0ff"), (240, 232, 255), hexrgb("#b9a6e8"), (255, 90, 110)


def wanted(trip=False):
    return os.environ.get("TAROT_VIDEO_STYLE", "pixel").lower() != "classic" and not trip


# ---------------------------------------------------------------- cards as pixel sprites
def _xterm(i):
    if i < 16:
        return [(0, 0, 0), (128, 0, 0), (0, 128, 0), (128, 128, 0), (0, 0, 128), (128, 0, 128), (0, 128, 128),
                (192, 192, 192), (128, 128, 128), (255, 0, 0), (0, 255, 0), (255, 255, 0), (0, 0, 255),
                (255, 0, 255), (0, 255, 255), (255, 255, 255)][i]
    if i < 232:
        v = (0, 95, 135, 175, 215, 255)
        i -= 16
        return v[i // 36], v[(i // 6) % 6], v[i % 6]
    g = 8 + (i - 232) * 10
    return g, g, g


_CARDS = {}


def card_image(card, rev=False):
    """The real card art from art.py (all 78 cards) as a 24x34 pixel sprite with its suit-colored border."""
    key = (card, bool(rev))
    if key in _CARDS:
        return _CARDS[key]
    import art
    try:
        _, border, _ = art.tags(card)
        px = art.card_pixels(card, 18, 20)
    except Exception:
        _CARDS[key] = VP.card_sprite("face", hash(card) % 997, 24, 34)
        return _CARDS[key]
    w, h = 24, 34
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    b = _xterm(border)
    d.rectangle((0, 0, w - 1, h - 1), fill=_xterm(art.CARD_BG), outline=b)
    d.rectangle((1, 1, w - 2, h - 2), outline=tuple(c // 2 for c in b))
    pic = Image.new("RGBA", (18, 20), (0, 0, 0, 0))
    for y, row in enumerate(px):
        for x, c in enumerate(row):
            if c is not None:
                pic.putpixel((x, y), _xterm(c) + (255,))
    im.paste(pic, (3, 4), pic)
    for x in range(4, w - 4, 2):                     # the little rule under the picture
        d.point((x, 27), fill=b)
    d.rectangle((w // 2 - 1, 29, w // 2 + 1, 31), fill=b)
    if rev:
        im = im.rotate(180)
    _CARDS[key] = im
    return im


def card_back():
    return VP.card_sprite("back", 0, 24, 34)


BAND_Y = 23                       # the headline band sits under the header bar
REVEAL_AT = 0.5                   # Live Readings: seconds a fallen card stays face down before she turns it
CTAS = [("BOOK A", "LIVE READING"), ("ASK VEYRA", "YOUR QUESTION"), ("WANT YOURS?", "BOOK A READING"),
        ("YOUR TURN", "SIT WITH VEYRA")]
TABLE = (14, 198, 256, 330)       # the fortune table: left, top, right, bottom


def _kind(name):
    """Scenes of one beat share a kind, so the glitch only marks real changes of scene."""
    base = name.rstrip("0123456789")
    return "fall" if base in ("ask", "drop", "read") else "card" if base in ("card", "piece") else base


_ITEMS = {}


def item_image(name, turned=False):
    """A fortune piece as an RGBA sprite (mirrored when it landed turned over)."""
    key = (name, turned)
    if key not in _ITEMS:
        import items as I
        px = I.sprite(name)
        im = Image.new("RGBA", (len(px[0]), len(px)), (0, 0, 0, 0))
        for y, row in enumerate(px):
            for x, c in enumerate(row):
                if c is not None:
                    im.putpixel((x, y), _xterm(c) + (255,))
        im = im.resize((im.width * 2, im.height * 2), Image.NEAREST)
        _ITEMS[key] = im.transpose(Image.FLIP_LEFT_RIGHT) if turned else im
    return _ITEMS[key]


def headline_band(hook, t):
    """The title caption: the title in white boxes with drawn zodiac signs either side of every line
    (W x 50, RGBA). t is seconds into the video: letters type on, then the boxes, then the signs pop in."""
    import video
    left, right, title, line = hook
    for scale, cap in ((2, 16), (1, 34)):
        lines = textwrap.wrap(VP.latin1(title), cap)
        if len(lines) <= 2:
            break
    lines = lines[:2]
    extra = [VP.latin1(line)] if len(lines) == 1 and len(VP.latin1(line)) <= 38 else []
    rows = [(ln, scale) for ln in lines] + [(ln, 1) for ln in extra]
    icons = video.line_symbols(hook, len(rows), first=2)
    im = Image.new("RGBA", (W, 50), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    letters = sum(len(ln) for ln in lines)
    shown = int(letters * min(1.0, t / video.TITLE_WRITE))
    box = t >= video.TITLE_WRITE
    pops = int(max(0.0, t - video.TITLE_WRITE - 0.15) / video.ICON_POP)
    y = 0
    for n, (ln, sc_) in enumerate(rows):
        g = 11 if sc_ == 2 else 9
        ln_l, ln_r = icons[n] if n < len(icons) else ((), ())
        spr_l = [video.zodiac_sprite(x[0], int(x[2:]) if x[1:2] == "|" else 0, g) for x in ln_l if x and x[0] in video.ZODIAC]
        spr_r = [video.zodiac_sprite(x[0], int(x[2:]) if x[1:2] == "|" else 0, g) for x in ln_r if x and x[0] in video.ZODIAC]
        tw = VP.text_mask(ln, sc_).width
        lh = VP.text_mask("M", sc_).height
        wl, wr = sum(s.width + 2 for s in spr_l), sum(s.width + 2 for s in spr_r)
        x0 = (W - (tw + wl + wr)) // 2
        if n < len(lines):
            part, shown = ln[:max(0, shown)], shown - len(ln)
        else:
            part = ln if box else ""
        if box and part:
            d.rounded_rectangle((x0 - 4, y, x0 + tw + wl + wr + 3, y + lh + 2), 3, fill=(246, 240, 255, 255))
            put_text(im, x0 + wl, y + 2, part, (26, 10, 46), scale=sc_, shadow=None)
        elif part:
            put_text(im, x0 + wl, y + 2, part, WHITE, scale=sc_)
        order = list(range(len(spr_l)))[::-1]
        ix = x0
        for k, sp in enumerate(spr_l):
            if box and pops > order[k]:
                im.paste(sp, (ix, y + (lh + 2 - sp.height) // 2 + 1), sp)
            ix += sp.width + 2
        ix = x0 + wl + tw + 2
        for k, sp in enumerate(spr_r):
            if box and pops > len(spr_l) + k:
                im.paste(sp, (ix, y + (lh + 2 - sp.height) // 2 + 1), sp)
            ix += sp.width + 2
        pops -= len(spr_l) + len(spr_r)
        y += lh + 5
    return im


# ---------------------------------------------------------------- the painter
class Look:
    def __init__(self, scenes, events, total, sess=None, fps=15, seed=None):
        self.scenes, self.total, self.sess, self.fps = scenes, total, sess or {}, fps
        rng = random.Random(seed if seed is not None else random.SystemRandom().randrange(1 << 30))
        self.R = VP.Renderer([], total, SimpleNamespace(fps=fps), rng, None, None)
        self.back = card_back()
        self.events = sorted(events, key=lambda e: e[0])
        self.chunks = self._chunks()
        self.spread = [tuple(c) for c in self.sess.get("spread") or []]
        try:
            from spreads import SPREADS
            self.labels = [p[0] for p in SPREADS[self.sess.get("key")]["positions"]]
        except Exception:
            self.labels = []
        self.log = (self.sess.get("falls") or {}).get("log") or []
        real = self.all_cards()[:5]
        if real:                                          # the end fan shows the cards she actually drew
            self.R.endcards = [card_image(c, r) for c, r in real]
        self.rng = rng
        self.kind = self.sess.get("key")
        try:
            import video
            self.hook = video.make_hook(self.sess) if self.sess else None
        except Exception:
            self.hook = None
        self._band_done = None
        self.outro_style = rng.randrange(2)               # each video ends a little differently
        self.cta = rng.choice(CTAS)
        self.sparks = rng.randrange(3)
        self.top = BAND_Y + 46                            # first free row under the headline
        if self.hook is not None:
            import video
            box = self.band(video.TITLE_DONE + 1).getbbox()
            self.top = BAND_Y + (box[3] if box else 0) + 6
        self.fortune = self.sess.get("fortune")
        if self.fortune:
            self._setup_fortune()

    # ---- captions: every voiced line becomes typed caption cards
    def _chunks(self):
        out = []
        for at, cap, audio, dur in self.events:
            sents = [s for s in VP.re.split(r"(?<=[.!?])\s+", VP.latin1(cap)) if s]
            parts, cur = [], ""
            for s in sents:
                if len(cur) + len(s) + 1 > 118 and cur:
                    parts.append(cur); cur = s
                else:
                    cur = (cur + " " + s).strip()
            if cur:
                parts.append(cur)
            n = sum(len(p) for p in parts) or 1
            t0 = at
            for p in parts:
                d = dur * len(p) / n
                out.append({"text": p, "t0": t0, "t1": t0 + d, "lines": textwrap.wrap(p, 40), "voiced": audio is not None})
                t0 += d
            if out:
                out[-1]["t1"] = at + dur + 0.25
        return out

    def env(self, t):
        for c in self.chunks:
            if c["t0"] <= t < c["t0"] + min(c["t1"] - c["t0"], len(c["text"]) / 14):
                return 0.45 + 0.55 * abs(math.sin(t * 17.0)) * (0.6 + 0.4 * math.sin(t * 5.3))
        return 0.0

    # ---- which card(s) a scene shows
    def scene_cards(self, sc):
        if sc.get("card") is not None and sc["card"] < len(self.spread):
            i = sc["card"]
            label = self.labels[i] if i < len(self.labels) else f"CARD {i + 1}"
            return [self.spread[i]], label, self.spread[:i]
        if "event" in sc and sc["event"] < len(self.log):
            e = self.log[sc["event"]]
            cards = [tuple(c) for c in e.get("cards", [])]
            slot = e.get("slot", sc["event"])
            label = self.labels[slot] if isinstance(slot, int) and slot < len(self.labels) else f"FALL {sc['event'] + 1}"
            before = [tuple(c) for x in self.log[:sc["event"]] for c in x.get("cards", [])]
            return cards, label, before
        return None, None, None

    def all_cards(self):
        if self.log:
            return [tuple(c) for e in self.log for c in e.get("cards", [])]
        return self.spread

    # ---- scenes
    def title(self, f, t, lt, env):
        R = self.R
        dy = max(0, self.top + 2 - 70)                    # room for the headline above the logo
        f.paste(R.bg_img["sanctum"]); R.sky(f, t, "sanctum")
        f.paste(R.moon, (206, 34), R.moon); R.motes_(f, t, (200, 150, 255))
        paste_glow(f, R.aura, 135, 150, 0.35 + 0.15 * math.sin(t * 2))
        x = 135 - 5 * VP.CW * 6 // 2
        for i, ch in enumerate("VEYRA"):
            k = spring((lt - 0.15 - i * 0.12) / 0.6)
            if k > 0:
                put_text(f, x, int(70 + dy - (1 - k) * 60), ch, GOLD, scale=6, shadow=hexrgb("#5a2f9a"))
            x += VP.CW * 6
        if lt > 1.0:
            q = (self.sess.get("question") or "").strip()
            head = ("A FORTUNE READING" if self.fortune else "A LIVE READING" if self.log
                    else "TONIGHT'S READING" if q else "8-BIT TAROT")
            put_text(f, 135, 150 + dy, head, WHITE, scale=2, center=True)
            if self.fortune:
                q = "Six pieces from " + self.fortune.get("group_name", "my collection")
            for i, line in enumerate(textwrap.wrap(q if q.lower() != "a live reading" else "", 40)[:3]):
                put_text(f, 135, 176 + dy + i * 13, line, CYAN, center=True)
        R.draw_veyra(f, t, env, 135, 205 + dy, scale=1.1 if dy < 30 else 0.9)
        put_text(f, 135, 330, VP.BRAND + "  //  LOCAL  //  8-BIT", (120, 100, 170), center=True)

    def card_scene(self, f, t, lt, env, cards, label, before, mode="drop"):
        """mode: "drop" (falls and turns), "down" (falls and stays face down), "turn" (face down, then turned),
        "up" (already face up)."""
        R = self.R
        f.paste(R.bg_img["sanctum"]); R.sky(f, t, "sanctum"); R.motes_(f, t, (200, 150, 255))
        d = ImageDraw.Draw(f)
        d.rectangle((0, 300, W, H), fill=hexrgb("#170726"))
        d.line([(0, 300), (W, 300)], fill=GOLD)
        R.draw_veyra(f, t, env, 38, self.top - 2, scale=0.62, aura=False)
        put_text(f, 150, self.top, label.upper()[:22], GOLD, scale=2, center=True)
        n = len(cards)
        sc = 4 if n == 1 else 3 if n == 2 else 2
        gap = 24 * sc + 10
        for j, (card, rev) in enumerate(cards):
            cx, cy = 135 + (j - (n - 1) / 2) * gap, 176
            p = min(1.0, max(0.0, (lt - j * 0.25) / 0.55))
            drop = (1 - ease_out_cubic(min(1, p * 1.6))) * -90 if mode in ("drop", "down") else 0
            paste_glow(f, R.aura, cx, cy, 0.55 + 0.2 * math.sin(t * 2))
            face = card_image(card, rev)
            if mode == "down":
                sp, fl = self.back, 1.0
            elif mode == "up":
                sp, fl = face, 1.0
            else:
                q = p if mode == "drop" else min(1.0, max(0.0, (lt - REVEAL_AT - j * 0.2) / 0.6))
                sp, fl = (face if q >= 0.5 else self.back), max(0.05, abs(2 * q - 1))
            big = sp.resize((sp.width * sc, sp.height * sc), Image.NEAREST)
            paste_card(f, big, cx, cy + drop, fl)
        if lt > 0.6 and mode != "down" and not (mode == "turn" and lt < REVEAL_AT + 0.4):
            names = " + ".join(c for c, _ in cards)
            s = 2 if len(names) <= 20 else 1
            put_text(f, 135, 254 if s == 2 else 258, names.upper()[:44], WHITE, scale=s, center=True)
            if any(r for _, r in cards):
                put_text(f, 135, 280, "REVERSED", RED, center=True)
        for j, (card, rev) in enumerate(before[-9:]):           # what is already on the table
            m = card_image(card, rev)
            f.paste(m, (int(135 - len(before[-9:]) * 14 + j * 28), 308), m)
        R.header(f, t, "READING")

    def table_scene(self, f, t, lt, env):
        R = self.R
        f.paste(R.bg_img["sanctum"]); R.sky(f, t, "sanctum"); R.motes_(f, t, (255, 210, 120))
        cards = self.all_cards()[:15]
        per = 5 if len(cards) > 6 else max(1, len(cards))
        sc = 2 if len(cards) > 3 else 3
        cw, chh = 24 * sc + 4, 34 * sc + 6
        rows = [cards[i:i + per] for i in range(0, len(cards), per)]
        y0 = (self.top + 20) if len(rows) > 1 else (self.top + 34)
        for r, row in enumerate(rows):
            for j, (card, rev) in enumerate(row):
                k = spring((lt - (r * per + j) * 0.08) / 0.6)
                if k <= 0:
                    continue
                cx = 135 + (j - (len(row) - 1) / 2) * cw
                cy = y0 + r * chh + chh / 2 + (1 - min(k, 1)) * 60
                im = card_image(card, rev)
                big = im.resize((im.width * sc, im.height * sc), Image.NEAREST)
                f.paste(big, (int(cx - big.width / 2), int(cy - big.height / 2)), big)
        put_text(f, 135, self.top, "THE SPREAD", GOLD, scale=2, center=True)
        R.header(f, t, "TABLE")

    # ---- the fortune table: pieces fall; the one she reads glows and grows big
    def _setup_fortune(self):
        fo = self.fortune
        x0, y0, x1, y1 = TABLE
        Wc, Hc = max(2, fo.get("W", 60)), max(2, fo.get("H", 20))
        self.pieces = []
        for o in fo["pieces"]:
            px = x0 + 4 + (o["x"] / max(1, Wc - 18)) * (x1 - x0 - 8 - 36)
            py = y0 + 4 + (o["y"] / max(1, Hc - 9)) * (y1 - y0 - 8 - 36)
            px, py = min(max(x0 + 2, px), x1 - 38), min(max(y0 + 2, py), y1 - 38)
            self.pieces.append({"name": o["name"], "turned": o["turned"], "x": px, "y": py,
                                "img": item_image(o["name"], o["turned"])})

    def _table(self, f, t):
        d = ImageDraw.Draw(f)
        x0, y0, x1, y1 = TABLE
        d.rectangle((x0 - 3, y0 - 3, x1 + 3, y1 + 3), fill=hexrgb("#3a1d0c"), outline=hexrgb("#a07a2a"))
        d.rectangle((x0, y0, x1, y1), fill=hexrgb("#170726"), outline=GOLD)
        r = random.Random(5)
        for _ in range(70):
            x, y = r.randrange(x0 + 2, x1 - 2), r.randrange(y0 + 2, y1 - 2)
            b = 0.5 + 0.5 * math.sin(t * r.uniform(1, 3) + x)
            d.point((x, y), fill=(int(70 + 80 * b), int(50 + 60 * b), int(120 + 90 * b)))

    def fortune_scene(self, f, t, lt, env, sc):
        """The pieces on the table; the one she is talking about glows and grows big on the screen."""
        R = self.R
        f.paste(R.bg_img["sanctum"]); R.sky(f, t, "sanctum"); R.motes_(f, t, (255, 210, 120))
        self._table(f, t)
        active = sc.get("piece")
        for i, pc in enumerate(self.pieces):
            if sc["name"] == "cast":
                p = (lt - 0.3 - i * 0.5) / 0.55
                if p <= 0:
                    continue
                drop = 0 if p >= 1 else (1 - p) ** 2 * 140
                bounce = 4 * abs(math.sin((p - 1) * 6)) * max(0, 1.4 - p) if 1 <= p < 1.4 else 0
                x, y = pc["x"], pc["y"] - drop - bounce
            elif i == active:
                continue                                   # drawn big, below
            else:
                x, y = pc["x"], pc["y"]
            f.paste(pc["img"], (int(x), int(y)), pc["img"])
        R.draw_veyra(f, t, env, 135, max(self.top + 8, 88), scale=0.62, aura=False)
        if active is not None and active < len(self.pieces):
            pc = self.pieces[active]
            grow = ease_out_cubic(min(1.0, lt / 0.6)) * (1 - ease_out_cubic(min(1.0, max(0.0, (lt - sc["dur"] + 0.5) / 0.5))))
            size = int(36 + (108 - 36) * grow)
            x0, y0 = pc["x"] + 18, pc["y"] + 18
            cx, cy = x0 + (135 - x0) * grow, y0 + (262 - y0) * grow
            paste_glow(f, R.aura, cx, cy, 0.5 + 0.4 * grow + 0.1 * math.sin(t * 4))
            paste_glow(f, R.flame_glow, cx, cy, 0.4 * grow)
            big = pc["img"].resize((size, size), Image.NEAREST)
            f.paste(big, (int(cx - size / 2), int(cy - size / 2 + math.sin(t * 2.2) * 2 * grow)), big)
            label = pc["name"].upper() + ("  //  TURNED" if pc["turned"] else "  //  UPRIGHT")
            put_text(f, 135, TABLE[1] - 14, label, GOLD if not pc["turned"] else RED, center=True)
        else:
            put_text(f, 135, TABLE[1] - 14, "THE CAST", GOLD, center=True)
        R.header(f, t, "FORTUNE")

    # ---- the sky: Veyra inside a slowly turning wheel of the zodiac
    def sky_scene(self, f, t, lt, env, sc):
        import video
        R = self.R
        f.paste(R.bg_img["sanctum"]); R.sky(f, t, "sanctum"); R.motes_(f, t, (200, 150, 255))
        f.paste(R.moon, (214, self.top + 14), R.moon)
        cx, cy = 135, 200
        focus = sc.get("glyph")
        for i, g in enumerate(video.ZODIAC):
            a = t * 0.25 + i * math.tau / 12
            x, y = cx + math.cos(a) * 112, cy + math.sin(a) * 70
            big = g == focus
            sp = video.zodiac_sprite(g, (i % 8) + 1, 17 if big else 12)
            if big:
                paste_glow(f, R.aura, x, y, 0.6)
            f.paste(sp, (int(x - sp.width / 2), int(y - sp.height / 2)), sp)
        R.draw_veyra(f, t, env, cx, cy - 60, scale=0.9)
        put_text(f, 135, self.top, sc.get("label", "TODAY'S SKY"), GOLD, scale=2, center=True)
        put_text(f, 135, 286, "NO API  //  NO WEBSITES  //  HER OWN MATH", CYAN, center=True)
        R.header(f, t, "SKY")

    # ---- endings: different for every kind of reading, and a little different every time
    def outro(self, f, t, lt, env):
        R = self.R
        f.paste(R.bg_img["sanctum"]); R.sky(f, t, "sanctum"); R.motes_(f, t, (255, 210, 120))
        paste_glow(f, R.aura, 135, 200, 0.5)
        cards = self.all_cards()
        if self.fortune:
            self._table(f, t)
            for i, pc in enumerate(self.pieces):
                x, y = pc["x"], pc["y"]
                k = max(0.0, (lt - 0.6 - i * 0.22) / 0.5)
                if self.outro_style == 0:               # they slide off the table, one by one
                    x += k * k * 260
                else:                                   # they float up into the stars
                    y -= k * k * 220
                if k < 1.4:
                    f.paste(pc["img"], (int(x), int(y)), pc["img"])
        elif cards and self.outro_style == 1:          # the cards go back to sleep: turned face down, gathered
            show = cards[:10]
            n = len(show)
            per = 5 if n > 6 else 3 if n > 3 else n
            for j, (card, rev) in enumerate(show):
                r, c = divmod(j, per)
                row_n = min(per, n - r * per)
                hx = 135 + (c - (row_n - 1) / 2) * 30
                hy = 168 + r * 44
                flip = min(1.0, max(0.0, (lt - 0.4 - j * 0.12) / 0.4))
                gather = ease_out_cubic(min(1.0, max(0.0, (lt - 0.6 - n * 0.12) / 0.7)))
                x, y = hx + (135 - hx) * gather, hy + (190 - hy) * gather
                sp = card_image(card, rev) if flip < 0.5 else self.back
                paste_card(f, sp, x, y, max(0.05, abs(2 * flip - 1)))
        else:                                          # the fan of what she drew
            R.endcards = R.endcards or [self.back]
            for i, sp in enumerate(R.endcards):
                k = spring((lt - i * 0.09) / 0.7)
                ang = (i - 2) * 0.32 * k
                x, y = 135 + math.sin(ang) * 70, 200 - math.cos(ang) * 30 + (1 - min(k, 1)) * 120
                big = sp.resize((sp.width * 2, sp.height * 2), Image.NEAREST)
                f.paste(big, (int(x - big.width / 2), int(y - big.height / 2)), big)
        if lt > 0.5:
            put_text(f, 135, self.top, self.cta[0], GOLD, scale=2, center=True)
            put_text(f, 135, self.top + 20, self.cta[1], GOLD, scale=3, center=True)
        if lt > 1.0:
            put_text(f, 135, 262, "QUESTIONS?", WHITE, scale=2, center=True)
            put_text(f, 135, 284, "CONTACT " + VP.CONTACT_NAME.upper(), CYAN, scale=2, center=True)
            for i, line in enumerate(textwrap.wrap(VP.CONTACT_LINE, 40)):
                put_text(f, 135, 308 + i * 12, line, (200, 190, 230), center=True)
        if lt > 1.3:
            put_text(f, 135, 440, "VEYRA  //  " + VP.BRAND + "  //  " + VP.MODEL_LABEL, (140, 120, 190), center=True)
        d = ImageDraw.Draw(f)
        r = random.Random(3 + self.sparks)
        for _ in range(60):
            a, v = r.uniform(0, 6.28), r.uniform(40, 120)
            tt = lt - 0.3
            if not 0 < tt < 2.8:
                continue
            if self.sparks == 0:                       # a burst
                x, y = 135 + math.cos(a) * v * tt, 170 + math.sin(a) * v * tt + 40 * tt * tt
            elif self.sparks == 1:                     # falling stars
                x, y = r.uniform(0, W) + 20 * tt, r.uniform(-60, 0) + v * tt
            else:                                      # rising embers
                x, y = r.uniform(20, W - 20) + 6 * math.sin(tt * 3 + a), 360 - v * tt
            d.point((int(x), int(y)), fill=r.choice([GOLD, CYAN, hexrgb("#ff7ab8"), (255, 255, 255)]))

    # ---- one frame
    def frame(self, n):
        t = n / self.fps
        sc = next((s for s in reversed(self.scenes) if s["start"] <= t), self.scenes[0])
        lt, name, env = t - sc["start"], sc["name"], self.env(t)
        R, f = self.R, Image.new("RGB", (W, H))
        cap_y = 344
        if name in ("intro", "hello") or (sc is self.scenes[0] and not name.startswith(("card", "drop"))):
            self.title(f, t, lt, env)
            cap_y = 352
        elif name == "end":
            self.outro(f, t, lt, env); R.header(f, t, "END"); cap_y = 372
        elif name == "table":
            self.table_scene(f, t, lt, env)
        elif name in ("sky", "stars"):
            self.sky_scene(f, t, lt, env, sc)
        elif self.fortune and (name == "cast" or name.startswith("piece")):
            self.fortune_scene(f, t, lt, env, sc)
        else:
            cards, label, before = self.scene_cards(sc)
            if cards:
                mode = ("down" if name.startswith("ask") else "turn" if name.startswith("drop")
                        else "up" if name.startswith("read") else "drop")
                self.card_scene(f, t, lt, env, cards, label, before, mode)
            else:
                R.sanctum(f, t, None, env)
                idx = sum(1 for c in self.chunks if sc["start"] <= c["t0"] <= t)
                if idx % 3 == 2 and self.kind != "celtic":       # an occasional punch-in on a new caption
                    z = 1.14; cw, chh = int(W / z), int(276 / z)
                    crop = f.crop((W // 2 - cw // 2, 150 - chh // 2, W // 2 - cw // 2 + cw, 150 - chh // 2 + chh))
                    f.paste(crop.resize((W, 276), Image.NEAREST), (0, 20))
                R.header(f, t, "LIVE")
        R.caption(f, t, {"chunks": self.chunks}, env, y0=cap_y)
        R.progress(f, t)
        arr = np.asarray(f).astype(np.float32)
        lum = arr.max(axis=2)
        mask = np.clip((lum - 165) / 90, 0, 1)[..., None]
        bright = Image.fromarray((arr * mask).astype(np.uint8)).filter(ImageFilter.GaussianBlur(3.2))
        arr = (arr + 0.6 * np.asarray(bright, np.float32)) * R.vign
        i = self.scenes.index(sc)
        prev = self.scenes[i - 1]["name"] if i else name
        if lt < 0.16 and i and _kind(prev) != _kind(name):          # a short glitch only where the scene really changes
            k = 0.6 * (1 - lt / 0.16)
            r = np.random.default_rng(n)
            for _ in range(int(3 + 7 * k)):
                y0, h = r.integers(0, H - 10), r.integers(2, 18)
                arr[y0:y0 + h] = np.roll(arr[y0:y0 + h], int(r.integers(-24, 24) * k), axis=1)
            s = int(1 + 4 * k)
            arr[..., 0] = np.roll(arr[..., 0], s, axis=1)
            arr[..., 2] = np.roll(arr[..., 2], -s, axis=1)
        fade = 1.0 if name != "end" else min(1.0, max(0.0, (self.total - t) / 1.2))
        out = Image.fromarray(np.clip(arr * fade, 0, 255).astype(np.uint8))
        band = self.band(t)
        if band is not None:                                          # the title caption, on top of everything
            out.paste(band, (0, BAND_Y), band)
        return out.tobytes()

    # ---- the headline, kept once it has finished drawing
    def band(self, t):
        import video
        if self.hook is None:
            return None
        done = t >= video.TITLE_DONE
        if done and self._band_done is not None:
            return self._band_done
        im = headline_band(self.hook, t)
        if done:
            self._band_done = im
        return im


def encode(scenes, events, total, wav, out_path, sess=None, fps=15, progress=None):
    """Draw every frame in the promo style and encode with the audio already mixed in wav."""
    import deps
    out_path = Path(out_path)
    look = Look(scenes, events, total, sess, fps)
    with tempfile.TemporaryDirectory() as d:
        crt = os.path.join(d, "crt.png")
        VP.crt_overlay(crt, SCALE)
        tmp = out_path.with_name(out_path.stem + ".part.mp4")
        cmd = [deps.ffmpeg(), "-y", "-hide_banner", "-loglevel", "error",
               "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(fps), "-i", "-",
               "-i", crt, "-i", str(wav),
               "-filter_complex", f"[0:v]scale={W * SCALE}:{H * SCALE}:flags=neighbor[s];[s][1:v]overlay=0:0,format=yuv420p[v]",
               "-map", "[v]", "-map", "2:a", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-tune", "animation",
               "-r", "30", "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", str(tmp)]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        frames = int(total * fps)
        for n in range(frames):
            try:
                proc.stdin.write(look.frame(n))
            except BrokenPipeError:
                break
            if progress and n % fps == 0:
                progress(n / frames)
        proc.stdin.close()
        err = proc.stderr.read().decode(errors="ignore")
        if proc.wait() != 0:
            raise RuntimeError("ffmpeg could not encode the video: " + err[-300:])
        tmp.replace(out_path)
    if progress:
        progress(1.0)
    return out_path
