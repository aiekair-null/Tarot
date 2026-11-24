"""cards_hd.py - all 78 cards (and the back) as detailed pixel paintings, per VISUAL_BIBLE.md.

Each card is 96 x 160 art pixels (tarot 3:5): a gold or suit-coloured frame, the numeral or rank,
an art window with a background themed to the card, the card's original art.py figure rebuilt at 4x
with dithered light, outlines and glints (or new hand-shaped suit pips), and a two-line name plate.

    card_art(card, reversed_=False)  -> RGBA 96x160
    back_art(phase=0)                -> RGBA 96x160
    window_art(card, reversed_=False)-> RGBA, just the painting (for terminal cells)
"""
import math, random
from functools import lru_cache

import numpy as np
from PIL import Image, ImageDraw

import art
import veyra_look as L

CW, CH = 96, 160
WIN = (8, 20, 88, 124)                 # art window x0, y0, x1, y1 (80 x 104)

def xrgb(i):
    return L._xterm_rgb(i)

# art.py's xterm colours, nudged onto the bible palette
OVR = {16: (28, 11, 61), 231: (244, 238, 254), 220: (255, 211, 107), 178: (217, 164, 65), 51: (79, 240, 255),
       18: (29, 42, 107), 223: (240, 214, 200), 180: (205, 160, 150), 189: (201, 182, 242), 98: (122, 79, 196),
       55: (59, 26, 107), 238: (60, 44, 80), 246: (150, 140, 170)}

def col(i):
    return OVR.get(i, xrgb(i)) if i is not None else None

SUIT_C = {"Wands": (255, 150, 70), "Cups": (79, 200, 255), "Swords": (200, 210, 235), "Pentacles": (140, 210, 110)}
BG = {   # element skies: top -> bottom
    "Wands": [(0, "#2a0a14"), (0.55, "#6a1f1a"), (1, "#c2561e")],
    "Cups": [(0, "#04122a"), (0.6, "#0b3a5a"), (1, "#1f6f8a")],
    "Swords": [(0, "#0e1226"), (0.6, "#263056"), (1, "#4a5684")],
    "Pentacles": [(0, "#0b1a0e"), (0.6, "#24401f"), (1, "#5f7a2e")],
    "light": [(0, "#24104a"), (0.5, "#7a3f6e"), (1, "#f0a050")],
    "heavy": [(0, "#07020f"), (0.6, "#2a0820"), (1, "#5a1030")],
    "night": [(0, "#07021a"), (0.55, "#24104a"), (1, "#3d1658")],
}

def _grad(w, h, stops, levels=8):
    y = np.linspace(0, 1, h)
    c = np.zeros((h, 3))
    for k in range(3):
        c[:, k] = np.interp(y, [p for p, _ in stops], [L.rgb(hx)[k] for _, hx in stops])
    img = np.repeat(c[:, None, :], w, axis=1)
    th = np.tile(L.BAYER, (h // 4 + 1, w // 4 + 1))[:h, :w, None]
    step = 255 / levels / 2.2
    return np.clip(np.floor(img / step + th + 0.5) * step, 0, 255).astype(np.uint8)

# ------------------------------------------------------------------ the detail treatment for any art.py sprite
def scale2x(g):
    """EPX / Scale2x: doubles a pixel grid and rounds its diagonals and curves (no new colours)."""
    p = np.pad(g, 1, mode="edge")
    P, A, B, C, D = g, p[:-2, 1:-1], p[1:-1, 2:], p[1:-1, :-2], p[2:, 1:-1]   # A up, B right, C left, D down
    e0 = np.where((C == A) & (C != D) & (A != B), A, P)
    e1 = np.where((A == B) & (A != C) & (B != D), B, P)
    e2 = np.where((D == C) & (D != B) & (C != A), C, P)
    e3 = np.where((B == D) & (B != A) & (D != C), D, P)
    out = np.empty((g.shape[0] * 2, g.shape[1] * 2), g.dtype)
    out[0::2, 0::2], out[0::2, 1::2], out[1::2, 0::2], out[1::2, 1::2] = e0, e1, e2, e3
    return out

def detail(px, s=4, light=(0.0, -1.0)):
    """art.py pixel grid (xterm colours / None) -> RGBA at s x: Scale2x-smoothed shapes, dithered light,
    outline, line art between colours, top highlights and gold glints."""
    h, w = len(px), len(px[0])
    ids = np.full((h, w), -1)
    for y in range(h):
        for x in range(w):
            if px[y][x] is not None:
                ids[y, x] = px[y][x]
    k = s
    if k >= 2 and k % 2 == 0:                  # one Scale2x pass: rounder diagonals, still chunky 8-bit pixels
        ids = scale2x(ids); k //= 2
    if k > 1:
        ids = np.repeat(np.repeat(ids, k, 0), k, 1)
    a = ids >= 0
    rgb = np.zeros(ids.shape + (3,), np.float32)
    for c in np.unique(ids[a]):
        rgb[ids == c] = col(int(c))
    H, W = a.shape
    yy, xx = np.mgrid[0:H, 0:W]
    gold = np.isin(ids, [220, 178, 11, 3])
    p = np.pad(ids, k, constant_values=-1)          # neighbours one chunky pixel away
    up, dn, lf, rt = p[:-2 * k, k:-k], p[2 * k:, k:-k], p[k:-k, :-2 * k], p[k:-k, 2 * k:]
    # 8-bit cel shading: flat fills, a hard highlight on top/left edges, a hard shadow on bottom/right edges
    hi = a & ((up != ids) | (lf != ids))
    sh = a & ((dn != ids) | (rt != ids)) & ~hi
    rgb[hi] = np.minimum(rgb[hi] * 1.18 + 12, 255)
    rgb[sh] *= 0.72
    line = a & (((up != ids) & (up >= 0)) | ((lf != ids) & (lf >= 0)))   # line art between colours
    rgb[line] *= 0.55
    glint = gold & hi & (((xx // k + yy // k) % 5) == 0)
    rgb[glint] = 255
    q = np.pad(a, 1)
    edge = a & ~(q[:-2, 1:-1] & q[2:, 1:-1] & q[1:-1, :-2] & q[1:-1, 2:])
    rgb[edge] = (12, 4, 24)                         # crisp dark outline
    out = np.zeros((H, W, 4), np.uint8)
    out[..., :3] = np.clip(rgb, 0, 255); out[..., 3] = a * 255
    return Image.fromarray(out, "RGBA")

# ------------------------------------------------------------------ new suit pips (18 x 18)
@lru_cache(maxsize=8)
def pip(suit, n=18):
    im = Image.new("RGBA", (n, n), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    ink = (20, 8, 36)
    gold, gold_d, gold_h = (255, 211, 107), (176, 120, 40), (255, 244, 200)
    if suit == "Wands":
        d.line([(3, 16), (14, 2)], fill=ink, width=4)
        d.line([(3, 16), (14, 2)], fill=(138, 90, 43), width=2)
        d.line([(4, 15), (13, 3)], fill=(192, 136, 80), width=1)
        for lx, ly in ((8, 8), (11, 5), (6, 11)):
            d.polygon([(lx, ly), (lx + 4, ly - 2), (lx + 2, ly + 1)], fill=(107, 208, 107), outline=(40, 110, 50))
        d.polygon([(14, 0), (17, 2), (15, 4), (13, 2)], fill=(255, 180, 70))
        d.point((15, 1), fill=(255, 240, 160))
    elif suit == "Cups":
        d.chord((2, 0, 15, 11), 0, 180, fill=gold, outline=ink)
        d.line([(3, 5), (14, 5)], fill=ink)
        d.rectangle((3, 3, 14, 5), fill=(79, 200, 255))
        d.line([(4, 3), (13, 3)], fill=(200, 250, 255))
        d.rectangle((8, 11, 9, 14), fill=gold_d)
        d.rectangle((4, 15, 13, 17), fill=gold, outline=ink)
        d.point([(5, 7), (6, 8)], fill=gold_h)
    elif suit == "Swords":
        d.polygon([(8, 0), (10, 0), (10, 11), (9, 13), (8, 11)], fill=(223, 230, 242), outline=ink)
        d.line([(9, 1), (9, 11)], fill=(154, 164, 184))
        d.rectangle((3, 11, 14, 12), fill=gold, outline=ink)
        d.rectangle((8, 13, 9, 15), fill=(122, 79, 196))
        d.ellipse((7, 15, 10, 17), fill=gold, outline=ink)
    else:
        d.ellipse((1, 1, 16, 16), fill=gold, outline=ink)
        d.ellipse((3, 3, 14, 14), outline=gold_d)
        c = [(8.5 + 5 * math.cos(math.radians(-90 + 144 * k)), 8.5 + 5 * math.sin(math.radians(-90 + 144 * k))) for k in range(6)]
        d.line(c, fill=(90, 50, 20))
        d.point([(5, 4), (4, 5)], fill=gold_h)
    return im

# ------------------------------------------------------------------ backgrounds per card
def _theme(card):
    rank, suit = art.split(card)
    if suit: return suit
    try:
        import lore
        if card in lore.LIGHT: return "light"
        if card in lore.HEAVY: return "heavy"
    except Exception:
        pass
    return "night"

def _window_bg(card):
    w, h = WIN[2] - WIN[0], WIN[3] - WIN[1]
    theme = _theme(card)
    a = _grad(w, h, BG[theme])
    r = random.Random(card)
    if theme in ("night", "heavy", "Cups", "Swords"):
        for _ in range(26):
            x, y = r.randrange(w), r.randrange(int(h * 0.6))
            b = r.uniform(0.4, 1)
            a[y, x] = (int(180 + 75 * b), int(170 + 80 * b), 255)
    img = Image.fromarray(a).convert("RGBA")
    d = ImageDraw.Draw(img)
    if theme == "light":                                   # sunrise rays
        cx, cy = w // 2, int(h * 0.38)
        for k in range(16):
            ang = k * math.pi / 8
            d.line([(cx, cy), (cx + 70 * math.cos(ang), cy + 70 * math.sin(ang))], fill=(255, 200, 120, 70) if k % 2 else (255, 230, 160, 40))
    if theme == "heavy":                                   # a thin red moon
        d.ellipse((w - 26, 6, w - 10, 22), fill=(200, 60, 80)); d.ellipse((w - 22, 4, w - 7, 20), fill=tuple(a[10, w - 12]))
    if theme == "night":
        d.ellipse((w - 24, 6, w - 10, 20), fill=L.MOON); d.ellipse((w - 20, 4, w - 7, 18), fill=tuple(a[8, w - 12]))
    # ground / horizon
    gc = {"Wands": (60, 20, 14), "Cups": (8, 40, 60), "Swords": (40, 46, 70), "Pentacles": (40, 60, 24),
          "light": (70, 40, 60), "heavy": (30, 6, 20), "night": (23, 7, 38)}[theme]
    d.rectangle((0, h - 14, w, h), fill=gc)
    for x in range(0, w, 3): d.point((x + (x // 3) % 2, h - 14), fill=tuple(min(255, v + 40) for v in gc))
    return img

# ------------------------------------------------------------------ the painting in the window
@lru_cache(maxsize=200)
def _window(card):
    img = _window_bg(card)
    w, h = img.size
    rank, suit = art.split(card)
    glow = L.glow(34, SUIT_C.get(suit, (255, 211, 107)))
    if card in art.MAJORS:
        L.paste_glow(img, glow, w // 2, h // 2 - 4, 0.45)
        fig = detail(art.grid(art.MAJORS[card]), 4)
        img.alpha_composite(fig, ((w - fig.width) // 2, h - 14 - fig.height + 2))
    elif rank == "Ace":
        L.paste_glow(img, L.glow(40, SUIT_C[suit]), w // 2, h // 2, 0.8)
        fig = detail(art.grid(art.ACES[suit]), 4)
        img.alpha_composite(fig, ((w - fig.width) // 2, h - 12 - fig.height))
    elif rank in art.COURTS:
        L.paste_glow(img, glow, w // 2, h // 2, 0.35)
        fig = detail(art.grid(art.COURTS[rank], {"X": art.PAL[art.SUIT_X[suit]]}), 4)
        img.alpha_composite(fig, ((w - fig.width) // 2, h - 12 - fig.height))
        p = pip(suit)
        img.alpha_composite(p, (4, 4)); img.alpha_composite(p, (w - 22, 4))
    else:
        rows = art.LAYOUT[art.PIP_COUNT[rank]]
        p = pip(suit)
        area = h - 18
        gap = (area - 18 * len(rows)) / (len(rows) + 1)
        for ri, k in enumerate(rows):
            y = int(gap + ri * (18 + gap))
            span = w - 8
            for i in range(k):
                x = int(4 + (i + 0.5) * span / k - 9)
                L.paste_glow(img, L.glow(12, SUIT_C[suit]), x + 9, y + 9, 0.35)
                img.alpha_composite(p, (x, y))
    return img

def window_art(card, reversed_=False):
    im = _window(card)
    return im.rotate(180) if reversed_ else im

# ------------------------------------------------------------------ the whole card
def _frame_colour(card):
    rank, suit = art.split(card)
    return SUIT_C.get(suit, (255, 211, 107))

def _name_lines(card):
    up = card.upper()
    if len(up) <= 13: return [up]
    if " OF " in up and not up.startswith("WHEEL"):
        r, _, s = up.partition(" OF ")
        return [r, "OF " + s]
    words = up.split()                       # split where the two lines are most even
    best = min(range(1, len(words)), key=lambda i: abs(len(" ".join(words[:i])) - len(" ".join(words[i:]))))
    return [" ".join(words[:best]), " ".join(words[best:])]

@lru_cache(maxsize=200)
def _card(card):
    from cards import DECK
    im = Image.new("RGBA", (CW, CH), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    fc = _frame_colour(card)
    dark = tuple(int(v * 0.45) for v in fc)
    d.rounded_rectangle((0, 0, CW - 1, CH - 1), 6, fill=(20, 8, 36))
    d.rounded_rectangle((1, 1, CW - 2, CH - 2), 5, fill=(240, 226, 192))          # cream card stock
    d.rounded_rectangle((4, 4, CW - 5, CH - 5), 3, fill=(13, 5, 32), outline=fc)
    d.rectangle((6, 6, CW - 7, CH - 7), outline=dark)
    for x, y in ((6, 6), (CW - 7, 6), (6, CH - 7), (CW - 7, CH - 7)):              # corner jewels
        d.polygon([(x, y - 3), (x + 3, y), (x, y + 3), (x - 3, y)], fill=fc, outline=(20, 8, 36))
    rank, suit = art.split(card)
    top = art.ROMAN[DECK.index(card)] if rank is None else rank.upper()
    L.put_text(im, CW // 2, 7, top, fc, center=True, shadow=(20, 8, 36))
    win = _window(card)
    im.alpha_composite(win, (WIN[0], WIN[1]))
    d.rectangle((WIN[0] - 1, WIN[1] - 1, WIN[2], WIN[3]), outline=fc)
    lines = _name_lines(card)
    y0 = 128 if len(lines) == 2 else 134
    for i, ln in enumerate(lines):
        L.put_text(im, CW // 2, y0 + i * 12, ln, (255, 211, 107) if rank is None else (240, 232, 255), center=True, shadow=(20, 8, 36))
    return im

def card_art(card, reversed_=False):
    im = _card(card)
    return im.rotate(180) if reversed_ else im.copy()

@lru_cache(maxsize=16)
def back_art(phase=0):
    im = Image.new("RGBA", (CW, CH), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, CW - 1, CH - 1), 6, fill=(20, 8, 36))
    d.rounded_rectangle((1, 1, CW - 2, CH - 2), 5, fill=(43, 15, 85))
    a = np.asarray(im).copy()
    yy, xx = np.mgrid[0:CH, 0:CW]
    diam = ((xx + yy + phase * 2) % 12 == 0) | ((xx - yy - phase * 2) % 12 == 0)
    inside = (xx > 6) & (xx < CW - 7) & (yy > 6) & (yy < CH - 7)
    a[diam & inside, :3] = (122, 79, 196)
    im = Image.fromarray(a, "RGBA"); d = ImageDraw.Draw(im)
    d.rounded_rectangle((4, 4, CW - 5, CH - 5), 3, outline=L.GOLD)
    d.rectangle((7, 7, CW - 8, CH - 8), outline=(176, 120, 40))
    cx, cy = CW // 2, CH // 2
    L.paste_glow(im, L.glow(30, (79, 240, 255)), cx, cy, 0.55)
    d.polygon([(cx, cy - 26), (cx + 16, cy), (cx, cy + 26), (cx - 16, cy)], fill=(13, 5, 32), outline=L.GOLD)
    d.polygon([(cx, cy - 18), (cx + 10, cy), (cx, cy + 18), (cx - 10, cy)], outline=(176, 120, 40))
    orb = L.veyra(phase * 0.5).crop((L.ORB_C[0] - 12, L.ORB_C[1] - 12, L.ORB_C[0] + 13, L.ORB_C[1] + 13))
    im.alpha_composite(orb, (cx - 12, cy - 12))
    for x, y in ((12, 12), (CW - 13, 12), (12, CH - 13), (CW - 13, CH - 13)):
        d.polygon([(x, y - 4), (x + 4, y), (x, y + 4), (x - 4, y)], fill=L.GOLD, outline=(20, 8, 36))
    L.put_text(im, cx, CH - 22, "VEYRA", L.GOLD, center=True, shadow=(20, 8, 36))
    return im

# ------------------------------------------------------------------ terminal cells (quarter blocks)
_TC = {}
def picture_cells(card, reversed_, cols, rows):
    """The card's painting as cols x rows terminal cells (2x2 pixels per cell)."""
    key = (card, bool(reversed_), cols, rows)
    if key not in _TC:
        if len(_TC) > 800: _TC.clear()
        px = art.card_pixels(card, cols, rows * 2)          # the original figure, laid out for this size
        fig = detail(px, 2)                                 # outlines, line art and light at 2x across
        fig = fig.resize((cols * 2, rows * 2), Image.NEAREST)
        if reversed_: fig = fig.rotate(180)
        _TC[key] = L._quadrants(fig, clear=art.CARD_BG, dark=16)
    return _TC[key]

def back_picture_cells(cols, rows, phase=0):
    key = ("__back__", phase % 6, cols, rows)
    if key not in _TC:
        im = back_art(phase % 6).crop((4, 4, CW - 4, CH - 4)).resize((cols * 2, rows * 2), Image.BOX)
        _TC[key] = L._quadrants(im)
    return _TC[key]

def contact_sheet(path, scale=2):
    from cards import DECK
    n = len(DECK) + 1
    per = 13
    sheet = Image.new("RGB", (per * (CW + 6) + 6, ((n + per - 1) // per) * (CH + 6) + 6), (23, 7, 38))
    for i, c in enumerate(list(DECK) + ["__back__"]):
        im = back_art(0) if c == "__back__" else card_art(c)
        sheet.paste(im, (6 + (i % per) * (CW + 6), 6 + (i // per) * (CH + 6)), im)
    sheet = sheet.resize((sheet.width * scale, sheet.height * scale), Image.NEAREST)
    sheet.save(path)
    return path

if __name__ == "__main__":
    import sys
    print(contact_sheet(sys.argv[1] if len(sys.argv) > 1 else "videos/all_cards.png"))
