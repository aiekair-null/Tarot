"""Fortune items: forty small pieces drawn in code (shaded, outlined pixel art), four groups of ten.

Each piece is drawn on an 18x18 pixel grid with xterm-256 colours: a lit sphere/cylinder shader gives
the volume, an automatic outline gives the crisp 8-bit edge. `sprite(name)` returns the pixel grid;
`cells(name)` returns terminal cells (two pixels per row)."""
import math

N = 18
# colour ramps, dark -> light (xterm-256)
GOLD, SILV, BRZ = (94, 136, 178, 221), (240, 245, 250, 255), (52, 94, 130, 173)
RED, BLUE, GREEN = (52, 88, 160, 210), (17, 25, 39, 117), (22, 28, 70, 120)
PURP, BONE, BRWN = (54, 91, 134, 183), (137, 180, 223, 230), (52, 94, 137, 180)
ONYX, TEAL, PINK = (233, 236, 240, 247), (23, 30, 44, 87), (89, 132, 175, 218)
AMBR, WHT, ORNG = (94, 130, 172, 215), (244, 250, 253, 255), (88, 130, 208, 214)
OUT = 16


class Pix:
    def __init__(self):
        self.g = [[None] * N for _ in range(N)]

    def p(self, x, y, c):
        x, y = int(round(x)), int(round(y))
        if isinstance(c, tuple):
            c = c[-1]
        if 0 <= x < N and 0 <= y < N:
            self.g[y][x] = c

    def shade(self, cx, cy, rx, ry, ramp, light=(-0.55, -0.7), rim=True):
        """A lit ellipse: tone follows the surface normal against a light from the upper left."""
        for y in range(N):
            for x in range(N):
                dx, dy = (x - cx) / rx, (y - cy) / ry
                d = dx * dx + dy * dy
                if d <= 1.0:
                    nz = math.sqrt(max(0.0, 1 - d))
                    lam = -(dx * light[0] + dy * light[1]) * 0.6 + nz * 0.55
                    k = min(len(ramp) - 1, max(0, int(lam * len(ramp) * 1.15)))
                    if rim and d > 0.78:
                        k = max(0, k - 1)
                    self.g[y][x] = ramp[k]

    def rect(self, x0, y0, x1, y1, ramp, vertical=True):
        """A lit box: a gradient across it plus a bright top edge."""
        for y in range(int(y0), int(y1) + 1):
            for x in range(int(x0), int(x1) + 1):
                t = (x - x0) / max(1, x1 - x0) if vertical else (y - y0) / max(1, y1 - y0)
                self.p(x, y, ramp[min(len(ramp) - 1, int((1 - t) * len(ramp) * 0.95 + 0.4))])

    def line(self, x0, y0, x1, y1, c, w=1):
        n = int(max(abs(x1 - x0), abs(y1 - y0)) * 2) + 1
        for i in range(n + 1):
            t = i / n
            x, y = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
            self.p(x, y, c)
            if w > 1:
                self.p(x + 1, y, c)

    def poly(self, pts, ramp, light=True):
        ys = [p[1] for p in pts]
        for y in range(int(min(ys)), int(max(ys)) + 1):
            xs = []
            for i in range(len(pts)):
                (ax, ay), (bx, by) = pts[i], pts[(i + 1) % len(pts)]
                if (ay <= y < by) or (by <= y < ay):
                    xs.append(ax + (y - ay) * (bx - ax) / (by - ay))
            xs.sort()
            for a, b in zip(xs[::2], xs[1::2]):
                for x in range(int(round(a)), int(round(b)) + 1):
                    k = 2 if not light else min(len(ramp) - 1, max(0, int((1 - (x - a) / max(1, b - a)) * len(ramp) * 0.9)))
                    self.p(x, y, ramp[k])

    def done(self):
        """Outline pass: a dark edge around every solid pixel."""
        out = [row[:] for row in self.g]
        for y in range(N):
            for x in range(N):
                if self.g[y][x] is None:
                    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        xx, yy = x + dx, y + dy
                        if 0 <= xx < N and 0 <= yy < N and self.g[yy][xx] is not None:
                            out[y][x] = OUT
                            break
        return out


# ------------------------------------------------------------------ the drawings
def d_key(s):
    s.shade(5, 5, 3.6, 3.6, GOLD); s.shade(5, 5, 1.4, 1.4, (OUT, OUT)); s.line(7, 8, 14, 15, GOLD[2], 2)
    s.line(7, 8, 14, 15, GOLD[1]); s.rect(12, 14, 15, 15, GOLD); s.rect(14, 12, 16, 13, GOLD)

def d_candle(s):
    s.rect(6, 7, 11, 16, WHT); s.rect(10, 7, 11, 16, BONE); s.rect(5, 15, 12, 16, BRZ, False)
    s.line(8, 4, 8, 7, OUT); s.shade(8.5, 3, 1.6, 2.6, (88, 202, 220, 229)); s.p(8, 4, WHT)

def d_ring(s):
    s.shade(9, 11, 6, 5.5, GOLD); s.shade(9, 11, 3.6, 3.2, (OUT, OUT)); s.shade(9, 4, 2.6, 2.6, (25, 39, 81, 123)); s.p(8, 3, WHT)

def d_bell(s):
    s.poly([(9, 2), (12, 5), (14, 12), (16, 14), (2, 14), (4, 12), (6, 5)], GOLD); s.shade(9, 15, 2, 1.6, BRZ); s.p(8, 5, GOLD[3])

def d_thimble(s):
    s.rect(4, 6, 13, 15, SILV); s.shade(8.5, 6, 4.8, 3.2, SILV)
    for y in (8, 10, 12):
        for x in range(5, 13, 2):
            s.p(x + (y // 2) % 2, y, SILV[0])
    s.rect(3, 14, 14, 16, SILV, False)

def d_teacup(s):
    s.poly([(2, 6), (15, 6), (13, 14), (4, 14)], WHT); s.rect(4, 14, 13, 16, BONE, False)
    s.shade(15, 9, 2.4, 2.6, BONE); s.shade(15, 9, 1.0, 1.4, (OUT, OUT)); s.rect(3, 6, 14, 7, BRWN, False)
    s.line(7, 1, 6, 4, SILV[2]); s.line(10, 2, 11, 4, SILV[2])

def d_spool(s):
    s.rect(4, 3, 13, 4, BRWN, False); s.rect(4, 14, 13, 15, BRWN, False); s.rect(5, 5, 12, 13, RED)
    for y in range(6, 13, 2):
        s.line(5, y, 12, y + 1, RED[3])
    s.line(12, 12, 16, 16, RED[2])

def d_button(s):
    s.shade(9, 9, 7, 7, BONE); s.shade(9, 9, 5, 5, BONE, (0.5, 0.6));
    for x, y in ((7, 7), (11, 7), (7, 11), (11, 11)):
        s.p(x, y, OUT)
    s.line(7, 7, 11, 11, BRWN[2]); s.line(11, 7, 7, 11, BRWN[2])

def d_locket(s):
    s.line(9, 0, 4, 5, SILV[2]); s.line(9, 0, 14, 5, SILV[2]); s.shade(9, 11, 6, 6.5, GOLD)
    s.p(8, 9, RED[2]); s.p(10, 9, RED[2]); s.poly([(6, 9), (9, 8), (12, 9), (9, 14)], RED); s.p(7, 9, RED[3])

def d_needle(s):
    s.line(2, 15, 15, 2, SILV[3]); s.line(3, 15, 16, 2, SILV[1]); s.line(13, 3, 15, 5, OUT); s.p(14, 3, OUT)
    s.line(12, 6, 3, 12, PINK[2]); s.line(3, 12, 4, 16, PINK[2]); s.p(3, 13, PINK[3])

def d_feather(s):
    s.poly([(14, 1), (16, 4), (13, 10), (7, 14), (4, 15), (5, 10), (9, 5)], TEAL)
    s.line(4, 16, 14, 2, BONE[3]);
    for i in range(3, 12, 2):
        s.line(i + 1, 14 - i + 2, i + 4, 14 - i, TEAL[1])

def d_acorn(s):
    s.shade(9, 11, 5, 5.2, BRWN); s.shade(9, 6, 6.4, 3.4, (52, 94, 94, 130)); s.line(9, 2, 10, 0, BRWN[1], 2)
    for x in range(4, 15, 2):
        s.p(x, 5 + (x // 2) % 2, BRWN[0])

def d_shell(s):
    s.shade(9, 9, 7.2, 6.4, (137, 180, 218, 224)); s.shade(9, 14, 3.4, 2.4, PINK)
    for a in range(-3, 4):
        s.line(9, 15, 9 + a * 2.2, 4 + abs(a), (131, 174, 216)[a % 3])

def d_leaf(s):
    s.poly([(9, 1), (14, 5), (16, 11), (9, 16), (3, 11), (5, 5)], GREEN, False); s.line(9, 16, 9, 3, GREEN[0])
    for y in (6, 9, 12):
        s.line(9, y, 5, y - 2, GREEN[0]); s.line(9, y, 13, y - 2, GREEN[0])

def d_moth(s):
    s.shade(5, 8, 5, 6, BRWN, (-0.3, -0.5)); s.shade(13, 8, 5, 6, BRWN, (0.3, -0.5)); s.shade(5, 13, 3.6, 3, BRWN)
    s.shade(13, 13, 3.6, 3, BRWN); s.rect(8, 4, 9, 14, ONYX, False); s.p(5, 7, GOLD[3]); s.p(13, 7, GOLD[3]); s.p(5, 8, OUT)
    s.p(13, 8, OUT); s.line(8, 3, 5, 0, ONYX[2]); s.line(9, 3, 12, 0, ONYX[2])

def d_thorn(s):
    s.poly([(3, 1), (7, 2), (15, 15), (13, 16), (2, 5)], BRWN); s.line(4, 3, 14, 15, BRWN[3]); s.p(14, 15, GREEN[2])

def d_mushroom(s):
    s.shade(9, 7, 7.6, 5, RED); s.rect(7, 9, 10, 16, BONE); s.rect(5, 15, 12, 16, BONE, False)
    for x, y in ((6, 5), (10, 4), (12, 7), (8, 7)):
        s.p(x, y, WHT); s.p(x + 1, y, WHT)

def d_egg(s):
    s.shade(9, 10, 5.6, 7, (137, 180, 223, 230));
    for x, y in ((7, 8), (11, 12), (9, 13), (10, 7), (7, 12)):
        s.p(x, y, BRWN[1])

def d_cone(s):
    s.poly([(9, 1), (14, 6), (13, 14), (9, 17), (5, 14), (4, 6)], BRWN)
    for y in range(4, 16, 3):
        for x in range(5 + (y // 3) % 2, 14, 3):
            s.p(x, y, BRWN[3]); s.p(x, y + 1, BRWN[0])

def d_flame(s):
    s.poly([(9, 0), (12, 5), (15, 9), (13, 15), (9, 17), (5, 15), (3, 9), (6, 6), (7, 3)], ORNG)
    s.shade(9, 12, 3, 4.4, (88, 214, 220, 229)); s.p(9, 12, WHT)

def d_bone(s):
    s.rect(5, 6, 12, 11, BONE); s.shade(4, 5, 2.4, 2.2, BONE); s.shade(4, 12, 2.4, 2.2, BONE)
    s.shade(13, 5, 2.4, 2.2, BONE); s.shade(13, 12, 2.4, 2.2, BONE); s.rect(5, 8, 12, 9, BONE[:3] + (BONE[2],))

def d_quartz(s):
    s.poly([(9, 0), (13, 4), (12, 16), (6, 16), (5, 4)], (250, 252, 254, 255)); s.poly([(9, 0), (13, 4), (9, 5), (5, 4)], WHT)
    s.line(9, 5, 9, 16, (146, 153, 250)[0]); s.p(7, 7, WHT)

def d_obsidian(s):
    s.poly([(4, 3), (11, 1), (15, 8), (12, 15), (5, 16), (2, 9)], ONYX); s.line(6, 4, 10, 3, (60, 99, 117)[2]); s.p(5, 6, WHT)

def d_amber(s):
    s.shade(9, 9, 7, 6, AMBR); s.p(7, 6, WHT); s.p(8, 6, WHT); s.p(11, 12, BRWN[0]); s.p(5, 10, AMBR[3])

def d_moonstone(s):
    s.shade(9, 9, 7, 6, (60, 103, 146, 189, 231)); s.shade(8, 8, 3.4, 2.6, (146, 189, 231, 255), (-0.6, -0.8))

def d_tooth(s):
    s.poly([(3, 3), (15, 3), (14, 9), (12, 16), (10, 11), (8, 11), (6, 16), (4, 9)], BONE); s.line(5, 4, 13, 4, WHT)

def d_coal(s):
    s.poly([(3, 6), (8, 2), (14, 5), (16, 11), (11, 15), (4, 14)], ONYX); s.p(7, 5, SILV[2]); s.p(11, 8, SILV[2]); s.p(6, 10, ORNG[1])

def d_salt(s):
    s.poly([(9, 3), (15, 14), (3, 14)], (250, 252, 254, 255))
    for x, y in ((6, 13), (11, 12), (8, 9), (9, 6), (13, 15), (4, 15)):
        s.p(x, y, SILV[1])
    s.p(8, 5, WHT)

def d_nail(s):
    s.shade(9, 3, 4.6, 1.8, ONYX); s.rect(8, 4, 10, 15, (59, 240, 244, 250)); s.p(9, 16, ONYX[1])

def d_pebble(s):
    s.shade(9, 9, 7.4, 5.6, (240, 244, 248, 252)); s.shade(9, 9, 1.8, 1.8, (OUT, OUT)); s.p(5, 6, WHT)

def d_dice(s):
    s.poly([(2, 5), (9, 1), (16, 5), (9, 9)], WHT); s.poly([(2, 5), (9, 9), (9, 17), (2, 13)], BONE, False)
    s.poly([(16, 5), (9, 9), (9, 17), (16, 13)], (244, 247, 250), False)
    for x, y in ((9, 5), (4, 9), (7, 12), (5, 12), (11, 11), (13, 13), (11, 14)):
        s.p(x, y, OUT)

def d_coin(s):
    s.shade(9, 9, 7.4, 7.4, GOLD); s.shade(9, 9, 5.2, 5.2, GOLD, (0.4, 0.5)); s.line(9, 5, 9, 13, GOLD[0]); s.line(7, 7, 11, 7, GOLD[0]); s.line(7, 11, 11, 11, GOLD[0])

def d_compass(s):
    s.shade(9, 9, 7.6, 7.6, BRZ); s.shade(9, 9, 6, 6, (231, 252, 255)); s.poly([(9, 3), (11, 9), (9, 15), (7, 9)], RED, False)
    s.poly([(9, 3), (11, 9), (7, 9)], RED[2:]); s.p(9, 9, OUT)

def d_horseshoe(s):
    for y in range(N):
        for x in range(N):
            dx, dy = (x - 8.5) / 7.6, (y - 8) / 7.6
            r = math.hypot(dx, dy)
            if 0.52 <= r <= 1.0 and (y <= 9 or abs(x - 8.5) >= 3.6):
                s.g[y][x] = SILV[min(3, max(0, int((1 - (dx * -0.6 + dy * -0.7 + 1) / 2) * 4 + (0 if r < 0.9 else -1))))]
    for y in (3, 6, 9, 12):
        for x in (2 if y > 3 else 3, 15 if y > 3 else 14):
            s.p(x, y + 1, OUT)

def d_clover(s):
    for cx, cy in ((6, 5), (12, 5), (6, 10), (12, 10)):
        s.shade(cx, cy, 3.6, 3.6, GREEN)
    s.line(9, 10, 8, 16, GREEN[1], 2); s.p(5, 4, GREEN[3]); s.p(11, 4, GREEN[3])

def d_mirror(s):
    s.shade(9, 8, 6.4, 7, GOLD); s.shade(9, 8, 4.8, 5.4, (24, 31, 38, 117, 159), (-0.5, -0.9)); s.rect(8, 14, 10, 17, GOLD)
    s.line(6, 5, 8, 4, WHT)

def d_anchor(s):
    s.shade(9, 2.4, 2, 2, SILV); s.rect(8, 4, 9, 15, SILV); s.rect(5, 6, 12, 7, SILV, False)
    for y in range(8, 17):
        for x in range(N):
            dx, dy = (x - 8.5) / 7.0, (y - 10) / 5.6
            if 0.7 <= math.hypot(dx, dy) <= 1.0 and y >= 10:
                s.g[y][x] = SILV[1 + (x < 8)]
    s.rect(2, 10, 3, 12, SILV); s.rect(14, 10, 15, 12, SILV)

def d_hourglass(s):
    s.rect(3, 1, 14, 2, BRZ, False); s.rect(3, 15, 14, 16, BRZ, False); s.poly([(4, 3), (13, 3), (9, 8), (13, 14), (4, 14), (8, 8)], (153, 195, 231, 255), False)
    s.poly([(5, 12), (12, 12), (9, 9)], GOLD); s.poly([(5, 4), (12, 4), (9, 6)], GOLD[:2])

def d_lantern(s):
    s.line(9, 0, 9, 2, SILV[1]); s.rect(5, 2, 12, 3, BRZ, False); s.rect(5, 15, 12, 16, BRZ, False)
    s.rect(5, 4, 12, 14, (130, 172, 214, 229)); s.shade(8.5, 9, 2, 3, (88, 202, 220, 229)); s.line(5, 4, 5, 14, BRZ[1]); s.line(12, 4, 12, 14, BRZ[1])

def d_ticket(s):
    s.poly([(1, 4), (16, 4), (16, 7), (14, 9), (16, 11), (16, 14), (1, 14)], PINK, False)
    for y in range(5, 14, 2):
        s.p(11, y, OUT)
    s.line(3, 7, 8, 7, OUT); s.line(3, 10, 7, 10, OUT)


# name -> (drawer, element, planet, light word, shadow word, her line)
ITEMS = {
    "key": (d_key, "air", "Mercury", "access", "a locked door", "an opening, or something waiting for the right hand"),
    "candle": (d_candle, "fire", "Sun", "patience", "burnout", "a small steady light"),
    "ring": (d_ring, "fire", "Venus", "commitment", "a closed circle", "a promise or a loop you are in"),
    "bell": (d_bell, "air", "Mercury", "news", "a warning", "a message about to ring out"),
    "thimble": (d_thimble, "earth", "Virgo's Mercury", "careful craft", "over-protecting", "small repairs and protected fingers"),
    "teacup": (d_teacup, "water", "Moon", "comfort", "an empty cup", "rest, company and what you are pouring"),
    "spool": (d_spool, "earth", "Saturn", "connection", "tangles", "threads that tie people and plans"),
    "button": (d_button, "earth", "Saturn", "closing a matter", "a loose end", "one small thing that holds the rest together"),
    "locket": (d_locket, "water", "Moon", "love kept close", "old grief", "a keepsake heart"),
    "needle": (d_needle, "fire", "Mars", "mending", "a sharp word", "a fine point that can heal or prick"),
    "feather": (d_feather, "air", "Mercury", "lightness", "a wandering mind", "a message from above, and ease"),
    "acorn": (d_acorn, "earth", "Jupiter", "potential", "a seed too early", "a great thing in a small shell"),
    "shell": (d_shell, "water", "Neptune", "intuition", "hiding away", "what the tide leaves, and an inward spiral"),
    "leaf": (d_leaf, "earth", "Venus", "growth", "decay", "a season turning"),
    "moth": (d_moth, "air", "Moon", "drawn to light", "a restless pull", "a fascination you cannot resist"),
    "thorn": (d_thorn, "fire", "Mars", "protection", "a sting", "the price of something sweet"),
    "mushroom": (d_mushroom, "earth", "Neptune", "hidden growth", "a poison", "what grows in the dark, and a warning to look twice"),
    "egg": (d_egg, "water", "Moon", "beginnings", "fragility", "a new thing not yet hatched"),
    "pinecone": (d_cone, "earth", "Saturn", "patience in layers", "slow going", "an old pattern that keeps its seeds"),
    "flame": (d_flame, "fire", "Mars", "passion", "a fire that spreads", "heat, courage and a quick change"),
    "knucklebone": (d_bone, "earth", "Saturn", "what endures", "an old wound", "the frame under everything"),
    "quartz": (d_quartz, "air", "Sun", "clarity", "a cold edge", "a clear amplifier of intention"),
    "obsidian": (d_obsidian, "fire", "Pluto", "truth", "a cut", "a dark mirror that shows what you avoid"),
    "amber": (d_amber, "fire", "Sun", "warmth held", "being stuck", "something kept and preserved"),
    "moonstone": (d_moonstone, "water", "Moon", "new beginnings", "mood swings", "the tide of feeling"),
    "tooth": (d_tooth, "earth", "Mars", "strength", "a bite", "what you will not let go of"),
    "coal": (d_coal, "earth", "Saturn", "pressure becoming value", "a smoulder", "heat held under weight"),
    "salt": (d_salt, "water", "Moon", "cleansing", "a wound stung", "a boundary and a clean slate"),
    "nail": (d_nail, "earth", "Mars", "fixing a plan", "a stuck point", "something that must be fastened or pulled"),
    "pebble": (d_pebble, "earth", "Saturn", "grounding", "a stone in the shoe", "a small steadiness with a hole in it"),
    "dice": (d_dice, "air", "Jupiter", "a lucky turn", "a gamble", "chance and a roll you must make"),
    "coin": (d_coin, "earth", "Jupiter", "money and worth", "a hard bargain", "value, and a choice between two faces"),
    "compass": (d_compass, "air", "Mercury", "direction", "a lost way", "the way, if you trust the needle"),
    "horseshoe": (d_horseshoe, "fire", "Jupiter", "luck", "luck draining out", "protection, held open to catch fortune"),
    "clover": (d_clover, "earth", "Venus", "fortune", "a rare chance missed", "a lucky find in plain sight"),
    "mirror": (d_mirror, "water", "Neptune", "self-knowledge", "vanity", "a look at yourself"),
    "anchor": (d_anchor, "water", "Saturn", "stability", "being held back", "what holds you, for better or worse"),
    "hourglass": (d_hourglass, "earth", "Saturn", "timing", "running short", "what the clock is asking"),
    "lantern": (d_lantern, "fire", "Sun", "guidance", "a narrow light", "a way lit one step at a time"),
    "ticket": (d_ticket, "air", "Mercury", "a journey", "a missed connection", "an admission, and somewhere to be"),
}

GROUPS = {
    1: ("Hearth & Home", "love, family, comfort, small daily luck",
        ["key", "candle", "ring", "bell", "thimble", "teacup", "spool", "button", "locket", "needle"]),
    2: ("Wild & Sky", "change, nature, instinct, the turning season",
        ["feather", "acorn", "shell", "leaf", "moth", "thorn", "mushroom", "egg", "pinecone", "flame"]),
    3: ("Bones & Stones", "fate, the body, truth, old strength",
        ["knucklebone", "quartz", "obsidian", "amber", "moonstone", "tooth", "coal", "salt", "nail", "pebble"]),
    4: ("Road & Fortune", "money, travel, luck, timing",
        ["dice", "coin", "compass", "horseshoe", "clover", "mirror", "anchor", "hourglass", "lantern", "ticket"]),
}

_cache = {}


def sprite(name):
    if name not in _cache:
        s = Pix()
        ITEMS[name][0](s)
        _cache[name] = s.done()
    return _cache[name]


def cells(name, bg=16):
    import art
    return art.halfblock(sprite(name), bg)


def rgb_sheet(path, names=None, scale=8):
    """A contact sheet PNG of the drawings (for checking the art)."""
    from PIL import Image
    from canvas import xterm_rgb
    names = names or list(ITEMS)
    cols = 8
    rows = (len(names) + cols - 1) // cols
    im = Image.new("RGB", (cols * (N + 2) * scale, rows * (N + 2) * scale), (10, 14, 40))
    for k, nm in enumerate(names):
        ox, oy = (k % cols) * (N + 2) + 1, (k // cols) * (N + 2) + 1
        for y, row in enumerate(sprite(nm)):
            for x, c in enumerate(row):
                if c is not None:
                    for yy in range(scale):
                        for xx in range(scale):
                            im.putpixel(((ox + x) * scale + xx, (oy + y) * scale + yy), tuple(xterm_rgb(c)))
    im.save(path)
