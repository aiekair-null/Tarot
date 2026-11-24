"""veyra_look.py - the Visual Bible in code (see VISUAL_BIBLE.md).

Every video in this project draws from here: the palette, crisp pixel text, the dithered night sky,
the finishing pass (bloom, scanlines, vignette) and Veyra herself.

Veyra is the original sprite from art.py (26 x 28), rebuilt at 4x detail (104 x 112):
same hood, lilac hair, gold circlet, cyan eyes and glowing orb, now with dithered lighting from
the orb, hair strands, robe folds, a real face (lashes, irises, highlights, nose, blush), an
animated mouth, a pulsing circlet gem and a swirling orb.
"""
import math
from functools import lru_cache

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

import art

# ------------------------------------------------------------------ palette
def rgb(h):
    h = h.lstrip("#"); return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))

NIGHT, VIOLET, PLUM, CLOTH, BOX = rgb("#07021a"), rgb("#24104a"), rgb("#3d1658"), rgb("#170726"), rgb("#0d0520")
HOOD, RIM, ROBE = rgb("#3b1a6b"), rgb("#7a4fc4"), rgb("#2a1050")
GOLD, CYAN, LAV, TEXT, RED, MOON = rgb("#ffd36b"), rgb("#4ff0ff"), rgb("#b9a6e8"), rgb("#f0e8ff"), rgb("#ff5064"), rgb("#fff1c9")
SHADOW = rgb("#08021a")
SKY = [(0, "#07021a"), (0.45, "#24104a"), (0.75, "#3d1658"), (1, "#120624")]
BRAND = "8b/8b(L)"

BAYER = (np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]) / 16 - 0.5)

# ------------------------------------------------------------------ pixel text
FONT = ImageFont.load_default_imagefont() if hasattr(ImageFont, "load_default_imagefont") else ImageFont.load_default()
CW, CH = max(1, int(FONT.getlength("M"))), 11

def clean(s):
    import unicodedata
    s = (s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
          .replace("—", " - ").replace("–", "-").replace("…", "...").replace("✦", "*"))
    return unicodedata.normalize("NFKD", s).encode("latin-1", "ignore").decode("latin-1")

@lru_cache(maxsize=4096)
def text_mask(s, scale=1):
    w = max(1, int(FONT.getlength(s)) + 1)
    m = Image.new("L", (w, CH + 1), 0)
    d = ImageDraw.Draw(m); d.fontmode = "1"
    d.text((0, 0), s, fill=255, font=FONT)
    if scale != 1:
        m = m.resize((m.width * scale, m.height * scale), Image.NEAREST)
    return m

def put_text(img, x, y, s, color, scale=1, shadow=SHADOW, center=False):
    s = clean(s)
    if not s: return 0
    m = text_mask(s, scale)
    x, y = int(x - m.width / 2) if center else int(x), int(y)
    if shadow is not None:
        img.paste(shadow, (x + scale, y + scale, x + scale + m.width, y + scale + m.height), m)
    img.paste(color, (x, y, x + m.width, y + m.height), m)
    return m.width

class PixelFont:
    """Drop-in for a FreeType font where only length and drawing are needed: crisp bitmap text at a whole scale."""
    def __init__(self, size, color=TEXT):
        self.size, self.color = size, color
        self.scale = max(1, round(size / CH))
    def getlength(self, s):
        return FONT.getlength(clean(s)) * self.scale
    def draw(self, img, x, y, s, color=None):
        return put_text(img, x, y, s, color or self.color, self.scale)

# ------------------------------------------------------------------ backgrounds
def gradient(w, h, stops=SKY, levels=9):
    y = np.linspace(0, 1, h)
    col = np.zeros((h, 3))
    for c in range(3):
        col[:, c] = np.interp(y, [p for p, _ in stops], [rgb(hx)[c] for _, hx in stops])
    img = np.repeat(col[:, None, :], w, axis=1)
    th = np.tile(BAYER, (h // 4 + 1, w // 4 + 1))[:h, :w, None]
    step = 255 / levels / 2.2
    return np.clip(np.floor(img / step + th + 0.5) * step, 0, 255).astype(np.uint8)

def night_sky(w, h, seed=11, moon=True):
    """Dithered violet night with stars and a crescent moon, at pixel-art resolution."""
    import random
    a = gradient(w, h)
    r = random.Random(seed)
    for _ in range(int(w * h / 900)):
        x, y = r.randrange(w), r.randrange(max(1, h - 4))
        b = r.uniform(0.45, 1)
        a[y, x] = (int(170 + 85 * b), int(160 + 90 * b), 255)
    if moon:
        cy, cx, R = int(h * 0.16), int(w * 0.8), max(6, w // 18)
        yy, xx = np.mgrid[0:h, 0:w]
        m = ((yy - cy) ** 2 + (xx - cx) ** 2 <= R * R) & ~(((yy - cy + R // 3) ** 2 + (xx - cx - R // 2.3) ** 2) <= (R * 0.92) ** 2)
        a[m] = MOON
    return a

# ------------------------------------------------------------------ Veyra, detailed
K = 4
CMAP = {"u": "#1c0b3d", "v": "#3b1a6b", "h": "#c9b6f2", "y": "#ffd36b", "Y": "#d9a441", "s": "#ecd0e2", "S": "#cfa5c4",
        "e": "#ecd0e2", "p": "#ecd0e2", "O": "#3b1a6b", "*": "#3b1a6b", "n": "#120a3a", "w": "#ffffff"}
ORB_C, ORB_R = (52, 82), 11

@lru_cache(maxsize=1)
def _base():
    rows = art.VEYRA
    g = np.array([list(r) for r in rows])
    g = np.repeat(np.repeat(g, K, 0), K, 1)
    H, W = g.shape
    out = np.zeros((H, W, 4), np.float32)
    for ch, hx in CMAP.items():
        out[g == ch, :3] = rgb(hx); out[g == ch, 3] = 255
    yy, xx = np.mgrid[0:H, 0:W]
    th = np.tile(BAYER, (H // 4 + 1, W // 4 + 1))[:H, :W]
    # light: the orb from below and a cool rim from the upper right
    d = np.hypot(xx - ORB_C[0], yy - ORB_C[1])
    orb = np.clip(1 - d / 54, 0, 1)
    rim = np.clip((xx / W) - (yy / H) * 0.6, 0, 1)
    f = np.minimum(0.82 + 0.38 * orb + 0.28 * rim, 1.25)
    f = np.floor((f + th * 0.14) * 7) / 7
    cloth = np.isin(g, ["u", "v", "n", "O", "*"])
    hair = g == "h"
    skin = np.isin(g, ["s", "S", "e", "p"])
    out[cloth, :3] = np.minimum(out[cloth, :3] * f[cloth, None], 255)
    out[hair, :3] *= (0.78 + 0.3 * f[hair, None])
    out[skin, :3] *= np.clip(0.9 + 0.12 * orb[skin, None], 0, 1.08)
    # hair strands and highlights
    strand = hair & (((xx + yy // 6) % 5) == 0)
    out[strand, :3] *= 0.78
    shine = hair & (((xx + yy // 6) % 5) == 2) & (yy % 3 == 0) & (xx > W * 0.5)
    out[shine, :3] = np.minimum(out[shine, :3] * 1.15, 255)
    # robe folds
    fold = (g == "v") & (yy > 58) & (((xx - yy // 2) % 13) == 0)
    out[fold, :3] *= 0.72
    fold2 = (g == "v") & (yy > 58) & (((xx + yy // 2) % 17) == 0)
    out[fold2, :3] *= 0.8
    # gold trim sparkle
    gold = g == "y"
    glint = gold & (((xx * 7 + yy * 3) % 29) == 0)
    out[glint, :3] = 255
    out[gold & (yy % 4 == 3), :3] *= 0.8
    # define hood against hair
    a = out[..., 3] > 0
    def nb(m):
        p = np.pad(m, 1)
        return p[:-2, 1:-1] | p[2:, 1:-1] | p[1:-1, :-2] | p[1:-1, 2:]
    edge_hair = (g == "v") & nb(hair)
    out[edge_hair, :3] = rgb("#1c0b3d")
    edge = a & ~(np.pad(a, 1)[:-2, 1:-1] & np.pad(a, 1)[2:, 1:-1] & np.pad(a, 1)[1:-1, :-2] & np.pad(a, 1)[1:-1, 2:])
    out[edge, :3] = rgb("#0c0420")
    out[yy >= 26 * K, 3] = 0                       # drop the old table strip; scenes draw their own table
    img = Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), "RGBA")
    d = ImageDraw.Draw(img)
    skin_c, shade = rgb("#ecd0e2"), rgb("#cfa5c4")
    d.rectangle((40, 34, 63, 39), fill=skin_c)          # clear the old eye, nose and mouth blocks
    d.rectangle((44, 40, 59, 47), fill=skin_c)
    d.line([(40, 31), (42, 30), (46, 31)], fill=rgb("#8a72c8"))   # brows
    d.line([(57, 31), (61, 30), (63, 31)], fill=rgb("#8a72c8"))
    d.point([(51, 41), (52, 42)], fill=shade); d.point((50, 40), fill=(250, 232, 244))   # nose
    for x in (42, 44, 59, 61): d.point((x, 43), fill=rgb("#f2a0c4"))                    # blush
    for x in (43, 60): d.point((x, 44), fill=rgb("#f2a0c4"))
    d.line([(46, 49), (57, 49)], fill=shade)                                            # chin shadow
    return img

@lru_cache(maxsize=1)
def _orb_geom():
    r = ORB_R
    yy, xx = np.mgrid[-r:r + 1, -r:r + 1]
    d = np.hypot(xx, yy) / r
    return d, np.arctan2(yy, xx), d <= 1.0

def veyra(t=0.0, mouth=0.0, blink=False):
    """Veyra at 104 x 112 art pixels. t: seconds (animates orb and gem); mouth: 0..1 voice level."""
    img = _base().copy()
    d = ImageDraw.Draw(img)
    lash, sclera, iris = rgb("#2a0f3a"), rgb("#f4eefe"), CYAN
    for x0, mirror in ((40, False), (56, True)):
        if blink:
            d.line([(x0 + 1, 38), (x0 + 6, 38)], fill=lash)
            d.point((x0 + (7 if not mirror else 0), 37), fill=lash)
            continue
        d.rectangle((x0 + 1, 36, x0 + 6, 38), fill=sclera)
        ix = x0 + (3 if not mirror else 2)
        d.rectangle((ix, 35, ix + 2, 38), fill=iris)
        d.rectangle((ix, 37, ix + 2, 38), fill=rgb("#1aa8c8"))
        d.point((ix + 1, 37), fill=rgb("#0b2a44"))
        d.point((ix, 35), fill=(255, 255, 255))
        d.line([(x0, 35), (x0 + 7, 35)], fill=lash)
        d.point((x0 + (7 if not mirror else 0), 34), fill=lash)
        d.line([(x0 + 2, 39), (x0 + 5, 39)], fill=rgb("#a37a9c"))
    o = int(round(max(0.0, min(1.0, mouth)) * 3))
    if o == 0:
        d.line([(49, 46), (54, 46)], fill=rgb("#b04a7a"))
        d.point([(48, 45), (55, 45)], fill=rgb("#d58aa8"))
    else:
        d.rectangle((49, 45, 54, 45 + o), fill=rgb("#4a1030"))
        d.line([(49, 45), (54, 45)], fill=rgb("#c05a88"))
        if o > 1: d.line([(50, 45 + o), (53, 45 + o)], fill=rgb("#e0709a"))
    # circlet gem
    g = 0.5 + 0.5 * math.sin(t * 3.1)
    d.polygon([(51, 19), (55, 23), (51, 27), (47, 23)], fill=rgb("#8a5a10"))
    d.polygon([(51, 20), (54, 23), (51, 26), (48, 23)], fill=(int(60 + 120 * g), int(220 + 35 * g), 255))
    d.point((50, 22), fill=(255, 255, 255))
    # the orb: violet glass, a bright core and a swirl that turns
    dd, ang, inside = _orb_geom()
    core = np.clip(1 - dd, 0, 1)
    swirl = (np.sin(ang * 2 + t * 2.4 + dd * 5) > 0.55) & (dd > 0.25)
    col = np.zeros(dd.shape + (3,))
    col[...] = np.array([123, 60, 255]) * (0.55 + 0.45 * core[..., None])
    col += np.array([79, 240, 255]) * (core[..., None] ** 2.2) * (0.8 + 0.2 * math.sin(t * 4))
    col[swirl] = col[swirl] * 0.5 + np.array([200, 170, 255]) * 0.6
    col[(dd > 0.86) & inside] *= 0.6
    th = np.tile(BAYER, (dd.shape[0] // 4 + 1, dd.shape[1] // 4 + 1))[:dd.shape[0], :dd.shape[1], None]
    col = np.floor(col / 24 + th + 0.5) * 24
    rgba = np.zeros(dd.shape + (4,), np.uint8)
    rgba[..., :3] = np.clip(col, 0, 255); rgba[..., 3] = inside * 255
    oi = Image.fromarray(rgba, "RGBA")
    img.paste(oi, (ORB_C[0] - ORB_R, ORB_C[1] - ORB_R), oi)
    sp = 0.5 + 0.5 * math.sin(t * 5.3)
    sx, sy = ORB_C[0] - 4, ORB_C[1] - 5
    d.point((sx, sy), fill=(255, 255, 255))
    if sp > 0.5: d.point([(sx - 1, sy), (sx + 1, sy), (sx, sy - 1), (sx, sy + 1)], fill=(220, 240, 255))
    # fingers over the orb's lower edge
    for x in (44, 47, 57, 60):
        d.line([(x, 88), (x, 91)], fill=rgb("#cfa5c4"))
    return img

def glow(r, color):
    yy, xx = np.mgrid[-r:r + 1, -r:r + 1]
    a = np.clip(1 - np.sqrt(xx ** 2 + yy ** 2) / r, 0, 1) ** 2
    arr = np.zeros((2 * r + 1, 2 * r + 1, 4), np.uint8)
    arr[..., :3] = color; arr[..., 3] = (a * 255).astype(np.uint8)
    return arr

def paste_glow(frame, garr, cx, cy, k):
    g = garr.copy(); g[..., 3] = (g[..., 3] * max(0, min(1, k))).astype(np.uint8)
    im = Image.fromarray(g, "RGBA")
    frame.paste(im, (int(cx - im.width / 2), int(cy - im.height / 2)), im)

# ------------------------------------------------------------------ finishing pass
_FIN = {}
def finish(img, pixel=4, bloom=0.55):
    """Bloom + scanlines + vignette for a full-resolution frame (PIL RGB or array). Returns uint8 array."""
    a = np.asarray(img)
    h, w = a.shape[:2]
    key = (h, w, pixel)
    if key not in _FIN:
        yy, xx = np.mgrid[0:h, 0:w]
        d = np.sqrt(((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2)
        m = np.clip(1.08 - 0.35 * d ** 2.2, 0.55, 1)
        m = m * np.where(yy % pixel == pixel - 1, 0.82, 1.0) * np.where(xx % pixel == pixel - 1, 0.95, 1.0)
        _FIN[key] = m[..., None].astype(np.float32)
    small = Image.fromarray(a).resize((w // 4, h // 4), Image.BOX)
    s = np.asarray(small).astype(np.float32)
    mask = np.clip((s.max(axis=2) - 165) / 90, 0, 1)[..., None]
    b = Image.fromarray((s * mask).astype(np.uint8)).filter(ImageFilter.GaussianBlur(3)).resize((w, h), Image.BILINEAR)
    out = (a.astype(np.float32) + bloom * np.asarray(b, np.float32)) * _FIN[key]
    return np.clip(out, 0, 255).astype(np.uint8)

# ------------------------------------------------------------------ terminal (tarot.py): Veyra in quarter blocks
QUAD = " ▘▝▀▖▌▞▛▗▚▐▜▄▙▟█"          # index = TL*1 + TR*2 + BL*4 + BR*8

def _xterm_rgb(i):
    if i < 16:
        return [(0, 0, 0), (128, 0, 0), (0, 128, 0), (128, 128, 0), (0, 0, 128), (128, 0, 128), (0, 128, 128),
                (192, 192, 192), (128, 128, 128), (255, 0, 0), (0, 255, 0), (255, 255, 0), (0, 0, 255),
                (255, 0, 255), (0, 255, 255), (255, 255, 255)][i]
    if i < 232:
        v = (0, 95, 135, 175, 215, 255); i -= 16
        return v[i // 36], v[(i // 6) % 6], v[i % 6]
    g = 8 + (i - 232) * 10
    return g, g, g

# her colours: skip 16 (transparent), the grey ramp and the darkest pure blues, so she stays violet, not grey
_XI = [i for i in range(17, 232) if i not in (17, 18, 19, 59, 102, 145, 188) and not 52 <= i <= 52] + [231]
_XT = np.array([_xterm_rgb(i) for i in _XI], np.float32)

@lru_cache(maxsize=8192)
def xterm(c):
    if max(c) < 72:                                  # outlines and deepest shadow: the darkest violet
        return 53
    c = np.array(c, np.float32)
    rm = (c[0] + _XT[:, 0]) / 2                      # "redmean" perceptual distance
    d = (2 + rm / 256) * (_XT[:, 0] - c[0]) ** 2 + 4 * (_XT[:, 1] - c[1]) ** 2 + (2 + (255 - rm) / 256) * (_XT[:, 2] - c[2]) ** 2
    return _XI[int(np.argmin(d))]

def _quadrants(img):
    """RGBA image (w even, h even) -> rows of (ch, fg, bg) cells, 2x2 pixels per cell, 16 = transparent."""
    a = np.asarray(img)
    rows = []
    for y in range(0, a.shape[0], 2):
        row = []
        for x in range(0, a.shape[1], 2):
            px = [a[y, x], a[y, x + 1], a[y + 1, x], a[y + 1, x + 1]]
            cols = [None if p[3] < 128 else (int(p[0]) // 8 * 8, int(p[1]) // 8 * 8, int(p[2]) // 8 * 8) for p in px]
            solid = [c for c in cols if c is not None]
            if not solid:
                row.append((" ", 16, 16)); continue
            # the two most different colours (transparent counts as one), then each pixel picks the nearer
            cand = list(dict.fromkeys(cols))
            best, pair = -1, (cand[0], cand[0])
            for i in range(len(cand)):
                for j in range(i + 1, len(cand)):
                    p, q = cand[i], cand[j]
                    dist = 1e9 if (p is None) != (q is None) else (0 if p is None else sum((u - v) ** 2 for u, v in zip(p, q)))
                    if dist > best: best, pair = dist, (p, q)
            fg, bg = pair if pair[0] is not None else (pair[1], pair[0])
            def near(c, ref):
                if c is None or ref is None: return c is ref
                return sum((u - v) ** 2 for u, v in zip(c, ref))
            bits = 0
            for k, c in enumerate(cols):
                if c is None:
                    on = bg is not None
                elif bg is None:
                    on = True
                else:
                    on = near(c, fg) <= near(c, bg)
                if on: bits |= 1 << k
            row.append((QUAD[bits], xterm(fg), 16 if bg is None else xterm(bg)))
        rows.append(row)
    return rows

_CELLS = {}
def veyra_cells(t=0.0, mouth=0.0, blink=False, big=False):
    """The detailed Veyra as terminal cells. Compact: 26 cols x 14 rows (same space as the old sprite,
    twice the detail across). Big: 26 cols x 28 rows."""
    key = (round(t * 6) % 240, round(mouth * 3), blink, big)
    if key not in _CELLS:
        if len(_CELLS) > 600: _CELLS.clear()
        v = veyra(t, mouth, blink).crop((0, 0, 104, 104))
        v = v.resize((52, 52 if big else 26), Image.BOX)
        if v.height % 2: v = v.crop((0, 0, 52, v.height - 1))
        _CELLS[key] = _quadrants(v.convert("RGBA"))
    return _CELLS[key]
