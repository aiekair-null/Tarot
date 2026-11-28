"""The Moonlit Intuition deck: 32 original cards drawn entirely by code, 48 x 64 pixels each (half-block cells in
the terminal: 48 columns x 32 rows). Every card is its own little painting: a dithered sky, stars, a moon or sun,
three layers of hills (or sea), flowers and grass, a glowing emblem with an outline, and an ornate gold frame.
Nothing here copies any published deck; the pictures and the names are Veyra's own."""
import math
import random

W, H = 48, 64
INK = 16


def c(r, g, b):
    """A colour from the xterm 6x6x6 cube (each 0..5)."""
    return 16 + 36 * r + 6 * g + b


GOLD, GOLD_D, GOLD_L = c(5, 4, 1), c(4, 3, 0), c(5, 5, 2)
CREAM, WHITE, SILVER = c(5, 5, 4), 231, c(3, 3, 4)
RED, RED_D, ROSE = c(4, 1, 1), c(2, 0, 1), c(5, 2, 3)
ORANGE, AMBER = c(5, 3, 0), c(5, 4, 0)
GREEN, GREEN_D, LEAF = c(1, 3, 1), c(0, 1, 1), c(2, 5, 2)
TEAL, AQUA = c(0, 3, 3), c(1, 5, 5)
BLUE, BLUE_D, SKY = c(1, 2, 5), c(0, 0, 3), c(3, 4, 5)
VIOLET, VIOLET_D, LILAC = c(3, 1, 5), c(1, 0, 3), c(4, 3, 5)
BROWN, BROWN_D, TAN = c(2, 1, 0), c(1, 0, 0), c(4, 3, 2)
BAYER = ((0, 8, 2, 10), (12, 4, 14, 6), (3, 11, 1, 9), (15, 7, 13, 5))


class Cv:
    def __init__(self, w, h, fill=None):
        self.w, self.h = w, h
        self.px = [[fill] * w for _ in range(h)]

    def put(self, x, y, col):
        x, y = int(round(x)), int(round(y))
        if 0 <= x < self.w and 0 <= y < self.h and col is not None:
            self.px[y][x] = col

    def get(self, x, y):
        return self.px[y][x] if 0 <= x < self.w and 0 <= y < self.h else None

    def rect(self, x, y, w, h, col):
        for j in range(int(h)):
            for i in range(int(w)):
                self.put(x + i, y + j, col)

    def disc(self, cx, cy, r, col):
        for j in range(int(cy - r - 1), int(cy + r + 2)):
            for i in range(int(cx - r - 1), int(cx + r + 2)):
                if (i - cx) ** 2 + (j - cy) ** 2 <= r * r + 0.5:
                    self.put(i, j, col)

    def ell(self, cx, cy, rx, ry, col):
        for j in range(int(cy - ry - 1), int(cy + ry + 2)):
            for i in range(int(cx - rx - 1), int(cx + rx + 2)):
                if ((i - cx) / max(rx, .5)) ** 2 + ((j - cy) / max(ry, .5)) ** 2 <= 1.05:
                    self.put(i, j, col)

    def ring(self, cx, cy, r, t, col, a0=0, a1=360):
        for j in range(int(cy - r - 1), int(cy + r + 2)):
            for i in range(int(cx - r - 1), int(cx + r + 2)):
                d = math.hypot(i - cx, j - cy)
                if r - t < d <= r + 0.3:
                    a = math.degrees(math.atan2(cy - j, i - cx)) % 360
                    if a0 <= a1 and a0 <= a <= a1 or a0 > a1 and (a >= a0 or a <= a1):
                        self.put(i, j, col)

    def line(self, x0, y0, x1, y1, col, th=1):
        n = int(max(abs(x1 - x0), abs(y1 - y0))) * 2 + 1
        for k in range(n + 1):
            t = k / n
            x, y = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
            self.put(x, y, col)
            if th > 1:
                self.put(x + 1, y, col)
                if th > 2:
                    self.put(x, y + 1, col)

    def poly(self, pts, col):
        ys = [p[1] for p in pts]
        for y in range(int(min(ys)), int(max(ys)) + 1):
            xs = []
            for i in range(len(pts)):
                (xa, ya), (xb, yb) = pts[i], pts[(i + 1) % len(pts)]
                if (ya <= y + .5 < yb) or (yb <= y + .5 < ya):
                    xs.append(xa + (y + .5 - ya) * (xb - xa) / (yb - ya))
            xs.sort()
            for a, b in zip(xs[::2], xs[1::2]):
                for x in range(int(round(a)), int(round(b))):
                    self.put(x, y, col)

    def stamp(self, other, ox=0, oy=0):
        for y in range(other.h):
            for x in range(other.w):
                if other.px[y][x] is not None:
                    self.put(x + ox, y + oy, other.px[y][x])


# ---------------------------------------------------------------- a tiny 3 x 5 font for the name plate
_F = {"A": "010101111101101", "B": "110101110101110", "C": "011100100100011", "D": "110101101101110",
      "E": "111100110100111", "F": "111100110100100", "G": "011100101101011", "H": "101101111101101",
      "I": "111010010010111", "J": "001001001101010", "K": "101101110101101", "L": "100100100100111",
      "M": "111111101101101", "N": "101111111101101", "O": "010101101101010", "P": "110101110100100",
      "Q": "010101101111011", "R": "110101110101101", "S": "011100010001110", "T": "111010010010010",
      "U": "101101101101111", "V": "101101101101010", "W": "101101111111101", "X": "101101010101101",
      "Y": "101101010010010", "Z": "111001010100111", " ": "000000000000000", "-": "000000111000000"}


def text(cv, s, x, y, col):
    for ch in s.upper():
        g = _F.get(ch, _F[" "])
        for i, bit in enumerate(g):
            if bit == "1":
                cv.put(x + i % 3, y + i // 3, col)
        x += 4


# ---------------------------------------------------------------- the world behind the emblem
THEMES = {   # sky stops top->bottom, glow, far hills, mid hills, ground, ground highlight
    "night": ([c(0, 0, 1), c(1, 0, 3), c(2, 0, 4), c(3, 1, 4)], LILAC, c(1, 0, 2), c(1, 1, 3), c(0, 2, 2), c(1, 3, 2)),
    "dusk": ([c(1, 0, 3), c(3, 0, 3), c(5, 1, 2), c(5, 3, 1)], c(5, 4, 2), c(2, 0, 2), c(1, 0, 2), c(0, 1, 1), c(1, 2, 1)),
    "dawn": ([c(1, 2, 4), c(3, 3, 5), c(5, 4, 4), c(5, 5, 2)], c(5, 5, 3), c(3, 3, 4), c(2, 3, 3), c(1, 3, 1), c(3, 5, 2)),
    "sea": ([c(0, 0, 2), c(0, 1, 3), c(0, 2, 4), c(1, 3, 4)], AQUA, c(0, 1, 3), c(0, 2, 3), c(0, 2, 4), c(2, 5, 5)),
    "ember": ([c(1, 0, 0), c(3, 0, 1), c(5, 1, 0), c(5, 3, 0)], AMBER, c(2, 0, 0), c(1, 0, 0), c(1, 0, 0), c(4, 1, 0)),
    "wood": ([c(0, 1, 1), c(0, 2, 2), c(1, 3, 2), c(2, 4, 3)], c(3, 5, 3), c(0, 1, 1), c(0, 2, 1), c(0, 1, 0), c(1, 3, 1)),
    "storm": ([c(0, 0, 1), c(1, 1, 2), c(2, 2, 3), c(3, 3, 4)], c(4, 4, 5), c(1, 1, 2), c(1, 1, 3), c(0, 1, 2), c(2, 3, 4)),
    "noon": ([c(2, 3, 5), c(3, 4, 5), c(5, 5, 4), c(5, 5, 2)], c(5, 5, 3), c(3, 4, 4), c(2, 4, 3), c(1, 4, 1), c(3, 5, 2)),
    "void": ([c(0, 0, 0), c(1, 0, 1), c(2, 0, 3), c(4, 1, 4)], c(5, 3, 5), c(1, 0, 1), c(2, 0, 2), c(1, 0, 2), c(3, 1, 3)),
    "rose": ([c(2, 0, 2), c(4, 1, 3), c(5, 2, 3), c(5, 4, 3)], c(5, 4, 4), c(3, 0, 2), c(2, 0, 2), c(1, 0, 1), c(3, 2, 2)),
}
SX0, SY0, SX1, SY1 = 6, 6, 42, 50          # the picture window inside the frame


def paint_scene(cv, theme, rng, body, horizon="hills", stars=40):
    sky, glow, far, mid, ground, hi = THEMES[theme]
    hz = 34
    base = Cv(W, H)
    for y in range(SY0, SY1):
        t = (y - SY0) / (hz - SY0) * (len(sky) - 1)
        t = max(0, min(len(sky) - 1.001, t))
        i, f = int(t), t - int(t)
        for x in range(SX0, SX1):
            base.px[y][x] = sky[i + 1] if f > BAYER[y % 4][x % 4] / 16 else sky[i]
    cv.stamp(base)
    for _ in range(stars):                                    # stars
        x, y = rng.randrange(SX0 + 1, SX1 - 1), rng.randrange(SY0 + 1, 26)
        col = rng.choice((WHITE, CREAM, SKY, GOLD_L))
        cv.put(x, y, col)
        if rng.random() < .15:
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                cv.put(x + dx, y + dy, SILVER)
    bx, by = body[1], body[2]
    kind = body[0]
    if kind == "sun":
        for r, col in ((9, glow), (7, GOLD_L), (5, GOLD)):
            if r == 9:
                for j in range(-9, 10):
                    for i in range(-9, 10):
                        if i * i + j * j <= 81 and (i + j) % 2 == 0:
                            cv.put(bx + i, by + j, col)
            else:
                cv.disc(bx, by, r - 1, col)
        for a in range(0, 360, 30):
            cv.line(bx + 7 * math.cos(math.radians(a)), by + 7 * math.sin(math.radians(a)),
                    bx + 10 * math.cos(math.radians(a)), by + 10 * math.sin(math.radians(a)), GOLD)
    elif kind in ("moon", "full", "eclipse"):
        for j in range(-8, 9):
            for i in range(-8, 9):
                if i * i + j * j <= 64 and (i + j) % 2 == 0 and kind != "eclipse":
                    cv.put(bx + i, by + j, glow)
        cv.disc(bx, by, 5, CREAM if kind != "eclipse" else INK)
        if kind == "moon":
            for j in range(-6, 7):
                for i in range(-6, 7):
                    if (i - 3) ** 2 + j * j <= 25 and i * i + j * j <= 36:
                        cv.put(bx + i, by + j, base.get(bx + i, by + j))
        elif kind == "full":
            for (dx, dy, r) in ((-2, -1, 1), (2, 2, 1), (1, -3, .7)):
                cv.disc(bx + dx, by + dy, r, SILVER)
        else:
            cv.ring(bx, by, 6, 1, GOLD_L)
            cv.ring(bx, by, 8, 1, glow)
    # three layers of land (or sea)
    ph = [rng.random() * 6.28 for _ in range(6)]
    layers = [(hz - 3, 4, far), (hz + 1, 3, mid), (hz + 7, 2, ground)]
    for k, (y0, amp, col) in enumerate(layers):
        for x in range(SX0, SX1):
            if horizon == "sea":
                y = y0 + 1.2 * math.sin(x * (.5 + k * .2) + ph[k] * 3) + (k - 1)
            elif horizon == "peaks":
                y = y0 - amp * 2.2 * abs(math.sin(x * .11 * (k + 1) + ph[k])) + math.sin(x * .7 + ph[k + 1])
            elif horizon == "dunes":
                y = y0 + amp * math.sin(x * .13 + ph[k]) * 1.3
            else:
                y = y0 + amp * math.sin(x * .17 * (1 + k * .4) + ph[k]) + (amp / 2) * math.sin(x * .41 + ph[k + 1])
            y = int(round(y))
            for yy in range(max(SY0, y), SY1):
                shade = col
                if yy == y:
                    shade = hi if k == 2 else THEMES[theme][1] if k == 0 else mid
                elif yy == y + 1 and (x + yy) % 2 == 0 and k < 2:
                    shade = hi if k else glow
                elif (x * 3 + yy * 5 + k) % 11 == 0:
                    shade = hi if k == 2 else far
                cv.put(x, yy, shade)
    for _ in range(26):                                        # grass blades and tiny flowers
        x, y = rng.randrange(SX0 + 1, SX1 - 1), rng.randrange(44, SY1)
        if horizon == "sea":
            cv.line(x, y, x + 2, y, hi)
            continue
        h = rng.randrange(2, 5)
        cv.line(x, y, x + rng.choice((-1, 0, 1)), y - h, rng.choice((GREEN, LEAF, GREEN_D)))
        if rng.random() < .45:
            col = rng.choice((ROSE, GOLD, LILAC, WHITE, ORANGE))
            cv.put(x, y - h - 1, col)
            cv.put(x + 1, y - h, col)
            cv.put(x - 1, y - h, col)


def glow_behind(cv, cx, cy, rad, theme):
    glow = THEMES[theme][1]
    for y in range(cy - rad, cy + rad + 1):
        for x in range(cx - rad, cx + rad + 1):
            if SX0 <= x < SX1 and SY0 <= y < SY1:
                d = math.hypot(x - cx, (y - cy) * .85) / rad
                if d < 1 and (1 - d) * .75 > BAYER[y % 4][x % 4] / 16:
                    cv.put(x, y, glow)


def outline(layer, col=INK):
    out = Cv(layer.w, layer.h)
    for y in range(layer.h):
        for x in range(layer.w):
            if layer.px[y][x] is None:
                if any(layer.get(x + dx, y + dy) is not None for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1))):
                    out.px[y][x] = col
    out.stamp(layer)
    return out


# ---------------------------------------------------------------- the emblems (each is drawn around (0,0))
def flame(L, x, y, s=1.0, cols=(RED, ORANGE, AMBER, GOLD_L)):
    for k, col in enumerate(cols):
        h, w = 9 * s * (1 - k * .2), 3.4 * s * (1 - k * .18)
        L.poly([(x, y - h), (x + w * .8, y - h * .35), (x + w, y), (x, y + 1), (x - w, y), (x - w * .8, y - h * .35)], col)


def e_lantern(L):
    L.ring(0, -11, 4, 1, GOLD_D, 0, 180)
    L.rect(-5, -8, 10, 2, GOLD)
    L.poly([(-5, -6), (5, -6), (7, 8), (-7, 8)], c(5, 5, 3))
    L.poly([(-4, -5), (4, -5), (5, 7), (-5, 7)], c(5, 4, 1))
    flame(L, 0, 6, 1.0)
    for x in (-7, 0, 7):
        L.line(x * .8, -6, x, 8, GOLD_D)
    L.rect(-8, 8, 16, 3, GOLD)
    L.rect(-6, 11, 12, 2, GOLD_D)


def e_key(L):
    L.ring(0, -8, 6, 2, GOLD)
    L.ring(0, -8, 3, 1, GOLD_D)
    L.disc(0, -8, 1, SKY)
    L.rect(-1, -2, 3, 18, GOLD)
    L.rect(-1, -2, 1, 18, GOLD_L)
    for y, w in ((9, 5), (12, 3), (15, 6)):
        L.rect(2, y, w, 2, GOLD)
    L.disc(0, -1, 2, GOLD_D)


def e_door(L):
    L.poly([(-14, 10), (-14, -6), (-9, -9), (9, -9), (14, -6), (14, 10)], BLUE_D)
    L.ell(0, -6, 10, 9, c(4, 2, 1))
    L.rect(-10, -6, 20, 16, c(4, 2, 1))
    L.ell(0, -6, 8, 7, c(1, 0, 3))
    L.rect(-8, -6, 16, 16, c(1, 0, 3))
    L.poly([(-8, 10), (8, 10), (16, 14), (-16, 14)], c(5, 5, 2))     # light spilling out
    L.poly([(-5, -6), (5, -6), (6, 10), (-6, 10)], c(5, 5, 3))
    L.line(0, -12, 0, 10, c(5, 4, 1))
    L.put(3, 2, GOLD)


def e_watcher(L):
    L.poly([(-14, 0), (-8, -6), (0, -8), (8, -6), (14, 0), (8, 6), (0, 8), (-8, 6)], CREAM)
    L.ell(0, 0, 6, 6, TEAL)
    L.ell(0, 0, 4, 4, BLUE_D)
    L.disc(0, 0, 2, INK)
    L.put(-2, -2, WHITE)
    for a in range(-60, 61, 20):
        x = 0 + 12 * math.sin(math.radians(a))
        L.line(x * .9, -9 - abs(a) / 30, x * 1.15, -13 + abs(a) / 40, GOLD)
    L.ring(0, 0, 14, 1, GOLD_D, 60, 120)


def e_feather(L):
    pts = [(-8, 12), (-5, 4), (-1, -4), (4, -11), (9, -15)]
    for i in range(len(pts) - 1):
        L.line(*pts[i], *pts[i + 1], CREAM, 2)
    for k in range(14):
        t = k / 13
        x, y = -8 + 17 * t, 12 - 27 * t
        w = 7 * math.sin(t * 3.1) + 1
        col = (SKY, LILAC, CREAM, c(4, 4, 5))[k % 4]
        L.line(x, y, x - w, y + 2, col)
        L.line(x, y, x + w * .8, y + 2, col)
    L.line(-9, 14, -6, 10, GOLD_D)


def e_tide(L):
    for k, (col, y0) in enumerate(((BLUE, -6), (TEAL, 0), (AQUA, 6), (BLUE_D, 11))):
        for x in range(-15, 16):
            y = y0 + 3 * math.sin(x * .45 + k * 1.3)
            for yy in range(int(y), int(y) + 6):
                L.put(x, yy, col)
            L.put(x, int(y), WHITE if k < 3 and (x + k) % 3 == 0 else CREAM)
    L.disc(8, -10, 3, CREAM)


def e_bridge(L):
    L.ring(0, 9, 13, 3, TAN, 0, 180)
    L.ring(0, 9, 10, 1, BROWN, 0, 180)
    L.rect(-16, 5, 32, 3, TAN)
    L.rect(-16, 5, 32, 1, CREAM)
    for x in range(-15, 16, 4):
        L.rect(x, 0, 1, 5, BROWN)
    L.rect(-16, 0, 32, 1, TAN)
    L.rect(-16, 10, 3, 6, TAN)
    L.rect(13, 10, 3, 6, TAN)
    for x in (-12, 12):
        L.disc(x, -3, 1.5, GOLD_L)


def e_ladder(L):
    L.line(-6, 15, -2, -12, TAN, 2)
    L.line(4, 15, 8, -12, TAN, 2)
    for k in range(7):
        t = k / 6
        y = 12 - 22 * t
        L.line(-5 + 4 * t, y, 5 + 4 * t, y, BROWN, 1)
    for k in range(5):
        a = k * 72 - 90
        L.line(3, -17, 3 + 6 * math.cos(math.radians(a)), -17 + 6 * math.sin(math.radians(a)), GOLD_L)
    L.disc(3, -17, 2, WHITE)


def e_fox(L):
    L.poly([(-12, -12), (-6, -2), (-10, 4)], ORANGE)
    L.poly([(12, -12), (6, -2), (10, 4)], ORANGE)
    L.poly([(-8, -2), (8, -2), (10, 4), (0, 14), (-10, 4)], ORANGE)
    L.poly([(-10, 4), (0, 14), (-3, 4), (-8, 0)], CREAM)
    L.poly([(10, 4), (0, 14), (3, 4), (8, 0)], CREAM)
    L.poly([(-11, -10), (-8, -3), (-10, 0)], INK)
    L.poly([(11, -10), (8, -3), (10, 0)], INK)
    L.disc(-4, 0, 1, INK)
    L.disc(4, 0, 1, INK)
    L.put(-4, -1, AMBER)
    L.put(4, -1, AMBER)
    L.rect(-1, 11, 3, 2, INK)


def e_owl(L):
    L.ell(0, 3, 10, 12, BROWN)
    L.ell(0, 6, 6, 8, TAN)
    L.poly([(-10, -7), (-6, -4), (-9, -2)], BROWN)
    L.poly([(10, -7), (6, -4), (9, -2)], BROWN)
    for x in (-5, 5):
        L.disc(x, -2, 4.4, CREAM)
        L.disc(x, -2, 2.8, AMBER)
        L.disc(x, -2, 1.4, INK)
    L.poly([(-1.5, 1), (1.5, 1), (0, 4)], ORANGE)
    for y in (7, 10):
        for x in (-3, 0, 3):
            L.put(x, y, BROWN)
    L.rect(-6, 14, 4, 2, GOLD_D)
    L.rect(2, 14, 4, 2, GOLD_D)


def e_moth(L):
    for sx in (-1, 1):
        L.ell(sx * 8, -4, 7, 6, LILAC)
        L.ell(sx * 7, 6, 5, 6, VIOLET)
        L.disc(sx * 9, -4, 2.5, CREAM)
        L.disc(sx * 9, -4, 1.2, INK)
        L.disc(sx * 7, 6, 1.5, GOLD)
        L.line(sx * 2, -8, sx * 5, -14, TAN)
    L.ell(0, 0, 2, 9, BROWN)
    L.disc(0, -8, 2, TAN)


def e_seed(L):
    L.line(0, 14, 0, -2, GREEN, 2)
    L.ell(-6, -4, 6, 3, LEAF)
    L.ell(6, 0, 6, 3, GREEN)
    L.line(-10, -4, -1, -3, GREEN_D)
    L.line(10, 0, 1, 1, GREEN_D)
    L.poly([(0, -3), (-3, -10), (0, -14), (3, -10)], ROSE)
    L.poly([(0, -3), (-6, -8), (-4, -12)], c(5, 1, 2))
    L.poly([(0, -3), (6, -8), (4, -12)], c(5, 1, 2))
    L.ell(0, 14, 5, 3, BROWN)
    for x in (-4, 0, 4):
        L.line(x, 16, x * 1.6, 20, TAN)


def e_mirror(L):
    L.ell(0, -2, 10, 13, GOLD)
    L.ell(0, -2, 8, 11, c(2, 4, 5))
    L.ell(0, -2, 6, 9, c(3, 5, 5))
    for k in range(4):
        a = k * 90
        L.line(0, -2, 5 * math.cos(math.radians(a)), -2 + 7 * math.sin(math.radians(a)), WHITE)
    L.disc(0, -2, 1.5, WHITE)
    L.line(-4, -9, -2, -11, WHITE)
    L.rect(-1, 11, 3, 6, GOLD_D)
    L.disc(0, 18, 2, GOLD)


def e_compass(L):
    L.ring(0, 0, 13, 2, GOLD)
    L.disc(0, 0, 11, c(1, 1, 3))
    for a in range(0, 360, 45):
        r = 11 if a % 90 == 0 else 8
        L.line(0, 0, r * math.cos(math.radians(a)), r * math.sin(math.radians(a)), SILVER)
    L.poly([(0, -11), (2, 0), (0, 11), (-2, 0)], SILVER)
    L.poly([(0, -11), (2, 0), (-2, 0)], RED)
    L.disc(0, 0, 2, GOLD)
    for a in range(0, 360, 30):
        L.put(12.5 * math.cos(math.radians(a)), 12.5 * math.sin(math.radians(a)), GOLD_L)


def e_hourglass(L):
    L.rect(-10, -15, 20, 2, GOLD)
    L.rect(-10, 13, 20, 2, GOLD)
    L.poly([(-8, -13), (8, -13), (1, 0), (8, 13), (-8, 13), (-1, 0)], c(4, 5, 5))
    L.poly([(-6, -12), (6, -12), (0, -3)], AMBER)
    L.poly([(-7, 12), (7, 12), (0, 3)], GOLD)
    L.line(0, -3, 0, 4, AMBER)
    L.line(-9, -13, -9, 13, GOLD_D, 2)
    L.line(9, -13, 9, 13, GOLD_D, 2)


def e_thread(L):
    for x in range(-14, 15):
        L.put(x, -4 + 7 * math.sin(x * .32), ROSE)
        L.put(x, -3 + 7 * math.sin(x * .32), RED)
    L.line(8, -14, 8, 12, SILVER, 2)
    L.ring(8, -12, 1.5, 1, INK)
    L.poly([(7, 12), (9, 12), (8, 16)], SILVER)
    for k in range(5):
        L.put(-14 - k % 2, -4 - k, ROSE)
    L.disc(-12, 8, 4, RED)
    L.ring(-12, 8, 4, 1, ROSE)


def e_bell(L):
    L.poly([(-3, -12), (3, -12), (5, -6), (9, 4), (12, 9), (-12, 9), (-9, 4), (-5, -6)], GOLD)
    L.poly([(-2, -11), (0, -11), (1, 8), (-8, 8), (-5, 2), (-3, -6)], GOLD_L)
    L.rect(-12, 9, 24, 2, GOLD_D)
    L.disc(0, 13, 2.5, BROWN)
    L.disc(0, -13, 2, GOLD_D)
    L.ring(0, 4, 16, 1, GOLD_L, 150, 185)
    L.ring(0, 4, 16, 1, GOLD_L, 355, 30)


def e_comet(L):
    L.poly([(8, -8), (-16, 12), (-10, 14), (10, -2)], c(3, 4, 5))
    L.poly([(8, -8), (-12, 10), (-8, 11), (9, -3)], CREAM)
    for k in range(12):
        L.put(-4 - k * 1.3 + (k % 3), 4 + k * .5 + (k % 4), SKY)
    L.disc(9, -8, 5, GOLD_L)
    L.disc(9, -8, 3, WHITE)
    for a in range(0, 360, 45):
        L.line(9 + 6 * math.cos(math.radians(a)), -8 + 6 * math.sin(math.radians(a)),
               9 + 9 * math.cos(math.radians(a)), -8 + 9 * math.sin(math.radians(a)), GOLD)


def e_well(L):
    L.ell(0, 0, 11, 4, TAN)
    L.rect(-11, 0, 22, 12, c(3, 3, 3))
    for y in range(1, 12, 3):
        for x in range(-11 + (y // 3 % 2) * 3, 11, 6):
            L.rect(x, y, 5, 2, c(4, 4, 4))
    L.ell(0, 11, 11, 3, c(2, 2, 2))
    L.ell(0, 0, 8, 3, BLUE_D)
    L.ell(0, 0, 4, 1, SKY)
    L.rect(-12, -14, 2, 14, BROWN)
    L.rect(10, -14, 2, 14, BROWN)
    L.poly([(-15, -14), (0, -21), (15, -14)], RED_D)
    L.line(0, -14, 0, -2, TAN)
    L.rect(-2, -3, 5, 4, BROWN)


def e_storm(L):
    for (x, y, r) in ((-7, -6, 6), (0, -9, 7), (7, -6, 6), (0, -4, 6)):
        L.disc(x, y, r, c(2, 2, 3))
    for (x, y, r) in ((-6, -8, 4), (1, -11, 4), (6, -7, 3)):
        L.disc(x, y, r, c(3, 3, 4))
    L.poly([(2, 1), (-4, 8), (0, 8), (-3, 17), (5, 6), (1, 6), (5, 1)], GOLD_L)
    L.poly([(2, 2), (-2, 8), (1, 8), (-2, 15), (3, 6), (0, 6)], WHITE)
    for x in (-11, -8, 10, 13):
        L.line(x, 3, x - 2, 9, SKY)


def e_hearth(L):
    L.line(-12, 14, 8, 8, BROWN, 3)
    L.line(12, 14, -8, 8, BROWN_D, 3)
    flame(L, 0, 9, 1.7)
    flame(L, -6, 9, 1.0)
    flame(L, 6, 9, 1.1)
    for x, y in ((-9, -8), (7, -12), (2, -15), (11, -4)):
        L.put(x, y, GOLD_L)


def e_crossing(L):
    L.rect(-1, -14, 3, 30, BROWN)
    for (y, d, col) in ((-12, 1, TAN), (-4, -1, CREAM), (4, 1, TAN)):
        if d > 0:
            L.poly([(-2, y), (9, y), (13, y + 2.5), (9, y + 5), (-2, y + 5)], col)
        else:
            L.poly([(3, y), (-9, y), (-13, y + 2.5), (-9, y + 5), (3, y + 5)], col)
        L.rect(-6, y + 2, 10, 1, BROWN)
    L.disc(0, -15, 2, GOLD)
    L.ell(0, 16, 6, 2, BROWN_D)


def e_mask(L):
    L.poly([(-10, -8), (10, -8), (11, 2), (6, 12), (0, 15), (-6, 12), (-11, 2)], CREAM)
    L.poly([(0, -8), (10, -8), (11, 2), (6, 12), (0, 15)], c(5, 4, 3))
    L.poly([(-10, -8), (0, -8), (0, -2), (-10, -2)], GOLD)
    for x in (-5, 5):
        L.ell(x, -2, 3, 1.6, INK)
    L.line(-5, 8, 0, 10, RED)
    L.line(0, 10, 5, 8, RED)
    L.line(0, -1, 0, 5, TAN)
    L.line(-10, -6, 10, -6, GOLD_D)
    L.poly([(-12, -4), (-16, 0), (-12, 4)], VIOLET)
    L.poly([(12, -4), (16, 0), (12, 4)], VIOLET)


def e_shell(L):
    L.poly([(0, 14), (-14, -2), (-10, -9), (-4, -13), (4, -13), (10, -9), (14, -2)], c(5, 3, 3))
    for k in range(-5, 6):
        L.line(0, 14, k * 2.6, -12 + abs(k) * .7, c(5, 4, 4) if k % 2 else ROSE)
    L.ring(0, -4, 10, 1, WHITE, 20, 160)
    L.rect(-4, 14, 9, 2, c(4, 2, 2))
    L.disc(0, 15, 3, ROSE)


def e_stag(L):
    for sx in (-1, 1):
        L.line(sx * 4, -2, sx * 7, -10, TAN, 2)
        L.line(sx * 7, -10, sx * 12, -18, TAN, 2)
        L.line(sx * 7, -10, sx * 14, -9, TAN)
        L.line(sx * 9, -14, sx * 5, -19, TAN)
        L.line(sx * 5, -6, sx * 11, -4, TAN)
        L.ell(sx * 7, 3, 3, 2, BROWN)
    L.poly([(-7, -2), (7, -2), (4, 12), (0, 16), (-4, 12)], BROWN)
    L.poly([(-3, 8), (3, 8), (0, 15)], TAN)
    L.disc(-3, 3, 1, INK)
    L.disc(3, 3, 1, INK)
    L.disc(0, 14, 1.3, INK)
    L.put(0, -12, GOLD_L)


def e_veil(L):
    L.rect(-14, -14, 28, 2, GOLD)
    for k in range(-14, 14):
        sway = 2.2 * math.sin(k * .6)
        for y in range(-12, 14):
            if (k + y) % 2 == 0 or abs(y) < 8:
                L.put(k + sway * (y + 12) / 26, y, (LILAC, VIOLET, c(4, 2, 5), SKY)[(k // 2) % 4])
    L.poly([(0, -3), (2, 1), (0, 5), (-2, 1)], WHITE)
    L.disc(0, 1, 1, GOLD_L)


def e_moongate(L):
    L.ring(0, 0, 14, 4, c(4, 3, 3))
    L.ring(0, 0, 14, 1, CREAM)
    L.ring(0, 0, 10, 1, c(2, 1, 1))
    L.disc(0, 0, 9.5, c(0, 0, 2))
    for (x, y) in ((-3, -5), (4, -2), (-5, 3), (2, 5)):
        L.put(x, y, WHITE)
    L.disc(3, -3, 3, CREAM)
    L.disc(5, -4, 2.6, c(0, 0, 2))
    L.poly([(-6, 9), (6, 9), (3, 4), (-3, 4)], c(1, 2, 3))
    L.rect(-15, 12, 30, 4, c(3, 2, 2))
    L.rect(-15, 12, 30, 1, CREAM)


def e_sunrise(L):
    L.disc(0, 4, 9, GOLD)
    L.disc(0, 4, 7, GOLD_L)
    L.disc(0, 4, 4, WHITE)
    for a in range(180, 361, 20):
        r = math.radians(a)
        L.line(11 * math.cos(r), 4 + 11 * math.sin(r), 17 * math.cos(r), 4 + 17 * math.sin(r), GOLD if (a // 20) % 2 else AMBER, 2)


def e_cauldron(L):
    L.ell(0, 3, 12, 11, c(1, 1, 2))
    L.ell(0, 3, 10, 9, c(2, 2, 3))
    L.rect(-13, -6, 26, 3, c(1, 1, 2))
    L.ell(0, -6, 12, 3, c(0, 4, 2))
    L.ell(0, -6, 9, 2, LEAF)
    for (x, y, r) in ((-5, -9, 2), (3, -11, 2.4), (7, -8, 1.4), (-1, -14, 1.5)):
        L.ring(x, y, r, 1, LEAF)
    for x in (-8, 8):
        L.rect(x - 1, 12, 3, 4, c(1, 1, 2))
    L.line(-4, -2, -5, 6, c(4, 4, 5))
    for k in range(8):
        L.put(-3 + 5 * math.sin(k), -16 - k * 1.2, SILVER)


def e_ship(L):
    L.poly([(-14, 4), (14, 4), (9, 12), (-9, 12)], BROWN)
    L.poly([(-14, 4), (14, 4), (13, 6), (-13, 6)], TAN)
    L.line(0, -16, 0, 4, TAN, 2)
    L.poly([(2, -14), (13, 1), (2, 1)], CREAM)
    L.poly([(-2, -12), (-12, 1), (-2, 1)], c(5, 4, 3))
    L.poly([(0, -16), (6, -14), (0, -12)], RED)
    for x in (-6, 0, 6):
        L.disc(x, 8, 1, GOLD)
    for x in range(-15, 16, 2):
        L.put(x, 13 + (x // 2) % 2, WHITE)


def e_raven(L):
    L.ell(0, 2, 8, 6, c(1, 0, 2))
    L.disc(8, -5, 4, c(1, 0, 2))
    L.poly([(11, -6), (17, -4), (11, -3)], GOLD_D)
    L.poly([(-6, 4), (-17, 14), (-10, 12), (-2, 8)], c(1, 0, 2))
    L.poly([(-2, -1), (-9, -10), (-12, 2), (-4, 6)], c(2, 1, 4))
    L.poly([(-4, -4), (-12, -4), (-8, 3)], VIOLET_D)
    L.disc(9, -6, 1, AMBER)
    L.line(-2, 8, -3, 14, GOLD_D)
    L.line(2, 8, 2, 14, GOLD_D)
    L.line(-12, 15, 8, 15, BROWN, 2)
    for k in range(5):
        L.put(1 + k, -3 + k % 2 * 4, c(3, 2, 5))


def e_spiral(L):
    for k in range(120):
        t = k / 120
        a = t * 4.5 * math.pi * 2
        r = 1 + t * 14
        col = (GOLD_D, GOLD, GOLD_L, WHITE, GOLD_L, GOLD)[k % 6]
        L.disc(r * math.cos(a), r * math.sin(a), .8 + t * 1.3, col)
    L.disc(0, 0, 1.5, WHITE)


EMBLEMS = {fn.__name__[2:]: fn for fn in (
    e_lantern, e_key, e_door, e_watcher, e_feather, e_tide, e_bridge, e_ladder, e_fox, e_owl, e_moth, e_seed,
    e_mirror, e_compass, e_hourglass, e_thread, e_bell, e_comet, e_well, e_storm, e_hearth, e_crossing, e_mask,
    e_shell, e_stag, e_veil, e_moongate, e_sunrise, e_cauldron, e_ship, e_raven, e_spiral)}


# ---------------------------------------------------------------- frame
def frame(cv, jewel):
    cv.rect(0, 0, W, H, INK)
    cv.rect(1, 1, W - 2, H - 2, GOLD_D)
    cv.rect(2, 2, W - 4, H - 4, INK)
    cv.rect(3, 3, W - 6, H - 6, GOLD)
    cv.rect(4, 4, W - 8, H - 8, c(1, 0, 1))
    for x in range(4, W - 4):                                   # beaded band, top and bottom
        for y in (4, H - 5):
            cv.put(x, y, GOLD_L if x % 3 == 0 else c(2, 1, 1))
    for y in range(4, H - 4):
        for x in (4, W - 5):
            cv.put(x, y, GOLD_L if y % 3 == 0 else c(2, 1, 1))
    for (x, y) in ((1, 1), (W - 5, 1), (1, H - 5), (W - 5, H - 5)):  # corner jewels
        cv.rect(x, y, 4, 4, GOLD)
        cv.rect(x + 1, y + 1, 2, 2, jewel)
        cv.put(x + 1, y + 1, WHITE)
    cv.rect(5, 5, W - 10, 1, INK)
    cv.rect(5, H - 6, W - 10, 1, INK)
    cv.rect(5, 5, 1, H - 10, INK)
    cv.rect(W - 6, 5, 1, H - 10, INK)


def card(cardinfo, idx):
    """One finished card as a W x H grid of xterm colours."""
    rng = random.Random(idx * 7919 + 13)
    cv = Cv(W, H, INK)
    frame(cv, cardinfo["jewel"])
    paint_scene(cv, cardinfo["theme"], rng, cardinfo["body"], cardinfo.get("horizon", "hills"), cardinfo.get("stars", 40))
    cx, cy = 24, cardinfo.get("y", 28)
    glow_behind(cv, cx, cy, 17, cardinfo["theme"])
    lay = Cv(W, H)
    tmp = Cv(40, 40)
    EMBLEMS[cardinfo["emblem"]](_Shift(tmp, 20, 20))
    lay.stamp(tmp, cx - 20, cy - 20)
    cv.stamp(outline(lay))
    cv.rect(SX0, 51, SX1 - SX0, 8 - 1, INK)                      # name plate
    cv.rect(SX0, 51, SX1 - SX0, 1, GOLD)
    cv.rect(SX0, 57, SX1 - SX0, 1, GOLD)
    name = cardinfo["name"].upper()
    text(cv, name, 24 - (len(name) * 4 - 1) // 2, 52, GOLD_L)
    if len(name) <= 7:                                           # little jewels beside short names
        for x in (SX0 + 2, SX1 - 4):
            cv.put(x, 54, cardinfo["jewel"])
            cv.put(x + 1, 54, WHITE)
    return cv.px


class _Shift:
    """Draw an emblem around (0,0) onto a canvas whose middle is (ox, oy)."""
    def __init__(self, cv, ox, oy):
        self.cv, self.ox, self.oy = cv, ox, oy

    def __getattr__(self, name):
        fn = getattr(self.cv, name)
        if name in ("put",):
            return lambda x, y, col: fn(x + self.ox, y + self.oy, col)
        if name in ("rect",):
            return lambda x, y, w, h, col: fn(x + self.ox, y + self.oy, w, h, col)
        if name in ("disc",):
            return lambda x, y, r, col: fn(x + self.ox, y + self.oy, r, col)
        if name in ("ell",):
            return lambda x, y, rx, ry, col: fn(x + self.ox, y + self.oy, rx, ry, col)
        if name in ("ring",):
            return lambda x, y, r, t, col, a0=0, a1=360: fn(x + self.ox, y + self.oy, r, t, col, a0, a1)
        if name in ("line",):
            return lambda x0, y0, x1, y1, col, th=1: fn(x0 + self.ox, y0 + self.oy, x1 + self.ox, y1 + self.oy, col, th)
        if name in ("poly",):
            return lambda pts, col: fn([(x + self.ox, y + self.oy) for x, y in pts], col)
        return fn


def cells(px, bg=16):
    """Pixel grid -> half-block cells, ready for art.ansi."""
    import art
    return art.halfblock(px, bg)


def back(phase=0):
    """The back of every card: a violet field of moons and stars inside the same gold frame."""
    rng = random.Random(4242)
    cv = Cv(W, H, INK)
    frame(cv, VIOLET)
    for y in range(SY0, SY1 + 8):
        for x in range(SX0, SX1):
            cv.put(x, y, c(1, 0, 3) if (x + y) % 2 == 0 else c(1, 0, 2))
    for y in range(SY0 + 2, SY1 + 6, 8):                         # a lattice of tiny moons
        for x in range(SX0 + 2, SX1 - 1, 8):
            ox = 4 if (y // 8) % 2 else 0
            cv.disc(x + ox, y + 2, 2.2, GOLD_L)
            cv.disc(x + ox + 1.5, y + 1.5, 1.9, c(1, 0, 3))
    cx, cy = 24, 31
    for r, col in ((14, GOLD_D), (11, INK), (9, GOLD)):
        cv.disc(cx, cy, r, col)
    cv.disc(cx, cy, 7, c(1, 0, 3))
    for a in range(0, 360, 30):
        rr = math.radians(a + phase * 6)
        cv.line(cx + 9 * math.cos(rr), cy + 9 * math.sin(rr), cx + 16 * math.cos(rr), cy + 16 * math.sin(rr), GOLD_L)
    cv.disc(cx, cy, 5, GOLD_L)
    cv.disc(cx + 2, cy - 1, 4.2, c(1, 0, 3))
    cv.disc(cx - 3, cy + 3, 1, WHITE)
    return cv.px


def small(px, k=2):
    """Shrink a card by k for spreads (nearest neighbour keeps it crisp)."""
    return [row[::k] for row in px[::k]]
