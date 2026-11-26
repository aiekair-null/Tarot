#!/usr/bin/env python3
"""Veyra: terminal tarot in 8-bit. Black table, neon blues and violets, pixel cards, a reader
who thinks with a free model running on your own machine. Needs a 256-color terminal, 80x24+.

  python tarot.py            menu: reading, grimoire, study
  python tarot.py read       straight into a reading
  python tarot.py grimoire   browse every card and every position meaning"""
import shutil
import curses, locale, math, os, random, sys, textwrap, time
import subprocess
from pathlib import Path
import psyche
psyche.load_config()                 # the wiring room's settings, before anything reads them
import art, fx, brain
from agent import Reader
from cards import build_deck, DECK
from spreads import SPREADS
from knowledge import card_profile, position_meaning, detect_domains, parse_sign, ELEMENT_SUIT
import questions as Q

SYS = random.SystemRandom()
ENTER = (10, 13, curses.KEY_ENTER)
BW, BH = 22, 15          # big card
MW, MH = 11, 5           # mini card (Celtic table)
PW, PH = 9, 5            # pile card (cutting)


def _overlap_rows(rear, front):
    rows = art.frame(MW, MH, 98)
    for y in range(MH):
        rows[y][3:MW] = rear[y]
        rows[y][:MW - 3] = front[y]
    return rows


def _overlapped_mini(rear, front):
    return _overlap_rows(art.mini_cells(*rear, w=MW - 3, h=MH),
                         art.mini_cells(*front, w=MW - 3, h=MH))


def _overlapped_back():
    return _overlap_rows(art.back_cells(MW - 3, MH), art.back_cells(MW - 3, MH))


def xterm_rgb(i):
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


def _shimmering(fn):
    """While waiting or channeling, every glowing word shimmers in Veyra's sheen."""
    def run(self, *a, **k):
        self.waiting = True
        try:
            return fn(self, *a, **k)
        finally:
            self.waiting = False
    return run


_PAIRS = {"screen": None, "map": {}}


class UI:
    def __init__(self, scr, plan=None):
        self.scr = scr
        self.virtual = getattr(scr, "virtual", False)   # a canvas.VirtualScreen: drawing for the video
        self.plan = plan or {"intro": "calm", "wash": "storm", "cut": "mystic", "reveal": "dread", "reading": "mystic"}
        self.mood, self.pairs, self.job = self.plan["intro"], {}, None
        self.t0 = self.now()
        scr.keypad(True)
        scr.timeout(70)          # getch returns -1 every 70ms so animations keep moving
        if self.virtual:
            self.big = True
        else:
            try:
                curses.curs_set(0)
            except curses.error:
                pass
            curses.start_color()
            self.big = curses.COLORS >= 256
            root = getattr(scr, "real", scr)             # colour pairs belong to curses, not to this UI:
            if _PAIRS["screen"] is not root:             # every UI on one screen (the Ctrl+W room too) shares
                _PAIRS["screen"], _PAIRS["map"] = root, {}   # one table, so none renumbers the others' colours
            self.pairs = _PAIRS["map"]
            scr.bkgd(" ", self.attr(153))

    # size is read fresh every time, so a resized terminal re-lays everything out on the next frame
    @property
    def h(self):
        return self.scr.getmaxyx()[0]

    @property
    def w(self):
        return self.scr.getmaxyx()[1]

    def now(self):
        """Wall time on a real terminal; the video's own clock on a virtual screen."""
        return self.scr.clock if self.virtual else time.time()

    # ---- color ---------------------------------------------------------------------
    def _c(self, idx):
        if self.big:
            return idx
        r, g, b = xterm_rgb(idx)
        return min(range(8), key=lambda k: sum((a - c) ** 2 for a, c in zip(xterm_rgb(k), (r, g, b))))

    def attr(self, fg, bg=16, bold=False):
        if self.virtual:
            return (fg & 0xFF) | ((bg & 0xFF) << 8) | ((1 << 16) if bold else 0)
        key = (self._c(fg), self._c(bg))
        if key not in self.pairs:
            n = len(set(self.pairs.values())) + 1
            if n >= curses.COLOR_PAIRS:                  # out of pairs: borrow the closest one already made
                if not self.pairs:
                    return curses.A_BOLD if bold else 0
                rgb = [xterm_rgb(c) for c in key]
                near = min(self.pairs, key=lambda k: sum((a - b) ** 2 for c, want in zip(k, rgb)
                                                         for a, b in zip(xterm_rgb(c), want)))
                n = self.pairs[near]
            else:
                try:
                    curses.init_pair(n, *key)
                except (curses.error, ValueError, OverflowError):
                    return 0
            self.pairs[key] = n
        return curses.color_pair(self.pairs[key]) | (curses.A_BOLD if bold else 0)

    @property
    def edge(self):
        return fx.idx_at(fx.pal(self.mood), (self.now() - self.t0) * 0.35)

    # ---- drawing -------------------------------------------------------------------
    def put(self, y, x, s, a=None):
        if y < 0 or y >= self.h or x >= self.w:
            return
        if x < 0:
            s, x = s[-x:], 0
        s = s[: self.w - x - (1 if y == self.h - 1 else 0)]
        if s:
            try:
                self.scr.addstr(y, x, art.plain(s), self.attr(153) if a is None else a)
            except curses.error:
                pass

    def text(self, y, x, s, fg=153, bold=False):
        self.put(y, x, s, self.attr(fg, 16, bold))

    def center(self, y, s, fg=153, bold=False):
        self.text(y, (self.w - len(s)) // 2, s, fg, bold)

    def cells(self, y, x, rows, xcrop=None):
        trip = psyche.active()
        t = self.now()
        for j, row in enumerate(rows):
            r = row[xcrop[0]:xcrop[1]] if xcrop else row
            dx = psyche.wave(j, t) if trip else 0          # psilocybin: the art melts and breathes
            for i, (ch, fg, bg) in enumerate(r):
                if ch == " " and bg == 16:
                    continue
                if trip:
                    fg = psyche.recolor(fg, i, j, t)
                ch, fg, bg = art.solid(ch, fg, bg)
                self.put(y + j, x + i + dx, ch, self.attr(fg, bg))

    def glow(self, y, x, s, phase=None, mood=None):
        if getattr(self, "waiting", False):
            mood = "sheen"                          # waiting / channeling: Veyra's shimmer
        p = fx.pal(mood or self.mood)[3:]          # bright half only: always legible
        ph = (self.now() - self.t0) * 0.8 if phase is None else phase
        for i, ch in enumerate(s):
            if ch != " ":
                self.put(y, x + i, ch, self.attr(fx.idx_at(p, ph + i * 0.04), 16, True))

    def gcenter(self, y, s, phase=None, mood=None):
        self.glow(y, (self.w - len(s)) // 2, s, phase, mood)

    def stars(self, n=30, seed=7, mood=None):
        """An 8-bit starfield that twinkles in place."""
        rng, p, t = random.Random(seed), fx.pal(mood or self.mood), self.now() - self.t0
        for i in range(n):
            y, x = rng.randrange(self.h), rng.randrange(self.w - 1)
            k = (math.sin(t * (1 + i % 5) * 0.9 + i) + 1) / 2
            self.put(y, x, "·+*✦"[int(k * 3.99)], self.attr(p[int(k * (len(p) - 1))]))

    def veyra(self, y, x, speed=1.0):
        t = (self.now() - self.t0) * speed
        frame, blink = int(t * 8), (int(t * 10) % 46) in (0, 1)
        self.cells(y, x, art.veyra_cells(frame, blink))

    def title(self, y, x=None):
        rows = art.halfblock(art.text_pixels("VEYRA"))
        self.cells(y, (self.w - len(rows[0])) // 2 if x is None else x, rows)

    def footer(self, s, meter=True):
        self.center(self.h - 1, s, 60)
        if meter and self.job is not None:
            self.meter(self.h - 1)

    def meter(self, y):
        """Tiny quill meter in the corner: the reading being written while you turn the cards."""
        j = self.job
        if j.done:
            s, c = "✒ reading ready", 120
        elif not j.started:
            s, c = "✒ gathering threads " + "◐◓◑◒"[int(self.now() * 4) % 4], 98
        else:
            n = int(j.progress() * 8)
            s, c = "✒ " + "▰" * n + "▱" * (8 - n), 141
        self.text(y, self.w - len(s) - 2, s, c)

    def wait_enter(self, render):
        while True:
            render()
            self.scr.refresh()
            if self.scr.getch() in ENTER:
                return

    def nap(self, ms):
        if self.virtual:
            return
        curses.napms(max(1, int(ms * (0.05 if fx.FAST else 1))))

    # ---- phases ----------------------------------------------------------------------
    INTRO_LINES = ["Settle. Lay the cloth. Let the room go quiet.", "Breathe in for four, out for six.",
                   "Three times.", "Hold your question lightly, but hold it.", "The deck is waiting to be washed."]

    def intro_frame(self, label="", lines=None, footer="press Enter"):
        lines = self.INTRO_LINES if lines is None else lines
        vx = max(1, self.w // 2 - 36)
        tx = vx + 30
        self.scr.erase()
        self.stars(40)
        self.veyra(max(0, self.h // 2 - 8), vx)
        self.title(max(0, self.h // 2 - 8), tx + 2)
        for i, s in enumerate(lines):
            self.glow(self.h // 2 - 3 + i * 2, tx, s, (self.now() - self.t0) * 0.6 + i * 0.3)
        if label:
            self.text(self.h - 2, 1, f"mind: {label}"[: self.w - 2], 60)
        if footer:
            self.footer(footer)

    def intro(self, label=""):
        self.wait_enter(lambda: self.intro_frame(label))

    def hold_frame(self, qs, footer="press Enter"):
        tx = 30
        self.scr.erase()
        self.stars(20)
        self.veyra(max(0, self.h // 2 - 7), 1)
        self.glow(2, tx, "Hold these questions for the spirits")
        self.glow(3, tx, "as the cards are washed.")
        y = 6
        for i, q in enumerate(qs):
            for j, ln in enumerate(textwrap.wrap(q, self.w - tx - 4)):
                self.text(y, tx, (f"{i + 1}. " if j == 0 else "   ") + ln, 189)
                y += 1
            y += 1
        if footer:
            self.footer(footer)

    def hold_questions(self, qs):
        self.wait_enter(lambda: self.hold_frame(qs))

    @staticmethod
    def wash_cards(n=78, rng=random):
        return [(rng.uniform(0, 6.28), rng.uniform(0.3, 1.0), rng.choice([-1, 1])) for _ in range(n)]

    def wash_frame(self, cards, f):
        cy, cx = self.h // 2, self.w // 2
        rx, ry = min(cx - 6, 32), min(cy - 3, 9)
        p = fx.pal(self.mood)
        self.scr.erase()
        self.stars(25)
        self.gcenter(1, "~ washing the cards ~")
        for a, r, d in cards:
            t = a + d * f * 0.07 * (1.3 - r * 0.5)
            c = fx.idx_at(p, r + f * 0.01)
            self.put(cy + int(math.sin(t) * ry * r), cx + int(math.cos(t) * rx * r), "▐█▌", self.attr(c))

    def wash(self, n=78, frames=100):
        cards = self.wash_cards(n)
        for f in range(frames):
            self.wash_frame(cards, f)
            self.scr.refresh()
            self.nap(35)

    def stack(self, y, x, count, label=True, hl=False):
        layers = min(4, max(1, count // 12 + 1)) if count else 0
        for i in reversed(range(layers)):
            rows = art.back_cells(PW, PH, int(self.now() * 3) if hl and i == 0 else 0)
            self.cells(y - i, x + i, rows)
        if label and count:
            self.text(y + PH, x, f"{count} cards".center(PW + 3), 60)

    def gather(self, n=78):
        cy, cx = self.h // 2 - PH // 2, self.w // 2 - PW // 2
        for i in range(1, n + 1, 2):
            sx, sy = random.choice([(random.randint(1, self.w - 4), 2), (random.randint(1, self.w - 4), self.h - 2),
                                    (2, random.randint(2, self.h - 2)), (self.w - 4, random.randint(2, self.h - 2))])
            for step in range(1, 4):
                t = step / 3
                self.scr.erase()
                self.stars(20)
                self.gcenter(1, "~ gathering the deck ~")
                self.stack(cy, cx, i - 1)
                if step < 3:
                    self.put(int(sy + (cy + PH // 2 - sy) * t), int(sx + (cx + PW // 2 - sx) * t), "▐█▌",
                             self.attr(self.edge))
                self.center(self.h - 2, f"{i} / {n}", 60)
                self.scr.refresh()
                self.nap(12)

    def spots(self, y, piles, sel=None, picked=(), numbers=False):
        for k in range(3):
            x = self.w // 2 + (k - 1) * (PW + 10) - PW // 2
            if piles[k] is None:
                rows = art.frame(PW, PH, 51 if k == sel else 60)
                self.cells(y, x, rows)
                self.text(y + 2, x + 2, "place", 51 if k == sel else 60)
            else:
                if k in picked:
                    self.cells(y, x, art.frame(PW, PH, 60))
                    self.text(y + 2, x + 2, "taken", 60)
                else:
                    self.stack(y, x, len(piles[k]), label=False, hl=k == sel)
                self.text(y + PH, x, f"{len(piles[k])} cards".center(PW + 3), 60)
            if numbers:
                self.text(y - 2, x + PW // 2 - 1, f"[{k + 1}]", 51 if k == sel else 153, k == sel)

    def draw_cut(self, hand, piles, sel, menu, msg, refresh=True):
        self.scr.erase()
        self.stars(15)
        self.gcenter(1, "you now hold the deck: cut it into three piles")
        self.center(3, msg)
        self.spots(5, piles, sel)
        if menu is not None:
            self.text(12, self.w // 2 - 16, "[ drop heavy ]", 51 if menu == 0 else 60, menu == 0)
            self.text(12, self.w // 2 + 2, "[ drop light ]", 51 if menu == 1 else 60, menu == 1)
        self.stack(16, self.w // 2 - PW // 2, len(hand))
        if refresh:
            self.scr.refresh()

    def slide(self, hand, piles, sel, n):
        x1, y1 = self.w // 2 - PW // 2, 16
        x2, y2 = self.w // 2 + (sel - 1) * (PW + 10) - PW // 2, 5
        for t in range(1, 9):
            f = t / 8
            self.draw_cut(hand, piles, None, None, "the cards fall...", refresh=False)
            self.stack(int(y1 + (y2 - y1) * f), int(x1 + (x2 - x1) * f), n, label=False)
            self.scr.refresh()
            self.nap(35)

    def cut(self, deck):
        hand, piles = list(deck), [None] * 3
        for k in range(2):
            empties = [i for i in range(3) if piles[i] is None]
            sel = empties[0]
            while True:
                self.draw_cut(hand, piles, sel, None, "← → choose a space, Enter to select")
                key = self.scr.getch()
                if key == curses.KEY_LEFT:
                    sel = empties[(empties.index(sel) - 1) % len(empties)]
                elif key == curses.KEY_RIGHT:
                    sel = empties[(empties.index(sel) + 1) % len(empties)]
                elif key in ENTER:
                    break
            m = 0
            while True:
                self.draw_cut(hand, piles, sel, m, "how will you let the cards fall?")
                key = self.scr.getch()
                if key in (curses.KEY_LEFT, curses.KEY_RIGHT, curses.KEY_UP, curses.KEY_DOWN):
                    m = 1 - m
                elif key in ENTER:
                    break
            pct = SYS.choice([45, 55, 75] if m == 0 else [15, 25, 35])
            n = max(1, min(round(len(hand) * pct / 100), len(hand) - (2 - k)))
            self.slide(hand, piles, sel, n)
            piles[sel], hand = hand[:n], hand[n:]
        last = piles.index(None)
        self.slide(hand, piles, last, len(hand))
        piles[last], hand = hand, []
        self.draw_cut(hand, piles, None, None, "the last of the cards fall into the final space")
        self.scr.refresh()
        self.nap(1200)
        return piles

    def reassemble(self, piles):
        order, sel = [], 0
        while len(order) < 3:
            left = [i for i in range(3) if i not in order]
            if sel not in left:
                sel = left[0]
            self.scr.erase()
            self.stars(15)
            self.gcenter(1, "reassemble the deck in any order you like")
            self.center(3, "← → + Enter (or press 1 2 3). The first chosen sits on top.")
            self.spots(7, piles, sel, picked=order, numbers=True)
            self.center(15, "order, top to bottom:  " + (" → ".join(str(i + 1) for i in order) or "..."), 51, True)
            self.scr.refresh()
            key = self.scr.getch()
            if key == curses.KEY_LEFT:
                sel = left[(left.index(sel) - 1) % len(left)]
            elif key == curses.KEY_RIGHT:
                sel = left[(left.index(sel) + 1) % len(left)]
            elif key in ENTER:
                order.append(sel)
            elif key in (ord("1"), ord("2"), ord("3")) and int(chr(key)) - 1 not in order:
                order.append(int(chr(key)) - 1)
        return [c for i in order for c in piles[i]]

    # ---- the laid spread -----------------------------------------------------------------
    def flipping(self, y, x, w, h, card, k):
        """Frame k of 9 of a card flip: the back narrows, the face widens."""
        widths = [w, w * 3 // 4, w // 2, w // 4, 2, w // 4, w // 2, w * 3 // 4, w]
        wd = max(2, widths[k])
        x0 = x + (w - wd) // 2
        if k < 4:
            self.cells(y, x0, art.back_cells(wd, h) if wd >= 4 else art.frame(wd, h, 98))
        else:
            full = art.card_cells(*card, w, h) if h == BH else art.mini_cells(*card, w, h)
            a = (w - wd) // 2
            self.cells(y, x0, full, (a, a + wd))

    def wrap_lines(self, y, x, width, s, fg=189, limit=4):
        for j, ln in enumerate(textwrap.wrap(s, width)[:limit]):
            self.text(y + j, x, ln, fg)

    def reveal_scene(self, key, spread, upto, flip=None, msg="", domain="inner"):
        """One frame of the laid spread: cards before `upto` face up, `flip` = (index, frame 0-8)."""
        pos = SPREADS[key]["positions"]
        n = len(spread)
        if key == "three":
            top = max(2, (self.h - BH - 6) // 2 + 1)
            lay = [(top, self.w // 2 + (k - 1) * (BW + 3) - BW // 2) for k in range(3)]
            self.scr.erase()
            self.stars(18)
            self.gcenter(0, "~ the cards are laid ~")
            for k, (y, x) in enumerate(lay):
                self.text(y - 1, x + (BW - len(pos[k][0])) // 2, pos[k][0].upper(), 51, True)
                if flip is not None and flip[0] == k:
                    self.flipping(y, x, BW, BH, spread[k], flip[1])
                elif k < upto:
                    self.cells(y, x, art.card_cells(*spread[k], BW, BH))
                else:
                    self.cells(y, x, art.back_cells(BW, BH))
            if 1 <= upto <= n:
                c, r = spread[upto - 1]
                self.wrap_lines(top + BH + 1, 2, self.w - 4, position_meaning(c, r, pos[upto - 1][0], domain), 189, 3)
            self.footer(msg)
            return
        if key == "falling":
            pairs = getattr(self, "fall_pairs", [])
            slots = getattr(self, "fall_slots", None) or [[i] for i in range(len(spread))]
            self.scr.erase()
            self.stars(14)
            self.fall_table(spread, pairs, ((flip[0],), flip[1]) if flip else None,
                            y=1, upto=upto, slots=slots)
            show = flip[0] if flip else upto - 1
            if 0 <= show < len(slots) and (flip is None or flip[1] >= 4):
                card_ids = slots[show]
                c, r = spread[card_ids[0]]
                if len(card_ids) > 1:
                    other = spread[card_ids[1]]
                    self.cells(8, 8, art.card_cells(*other, BW - 6, BH))
                    self.cells(8, 2, art.card_cells(c, r, BW - 6, BH))
                else:
                    self.cells(8, 2, art.card_cells(c, r, BW, BH))
                tx = BW + 5
                names = " + ".join(spread[j][0] for j in card_ids)
                self.text(9, tx, f"{show + 1}. {pos[show][0]}: {names}"[: self.w - tx - 1], 51, True)
                q = (getattr(self, "fall_questions", None) or [None] * 6)[show]
                y = 11
                if q:
                    for ln in textwrap.wrap(f"She asked the deck: \"{q}\"", self.w - tx - 2)[:2]:
                        self.text(y, tx, ln, 220)
                        y += 1
                    y += 1
                self.wrap_lines(y, tx, self.w - tx - 2, position_meaning(c, r, pos[show][0], domain), 189, 8)
                for a, b in pairs:
                    if a in card_ids:
                        other = spread[b][0]
                    elif b in card_ids:
                        other = spread[a][0]
                    else:
                        continue
                    if other:
                        other = other if other.startswith("The ") else "the " + other
                        self.text(min(self.h - 2, y + 7), tx, f"∞ fell together with {other}"[: self.w - tx - 1], 220)
            self.footer(msg)
            return
        ox, oy = max(1, (self.w - 76) // 2), 1
        cross = {5: (1, 0), 4: (0, 1), 1: (1, 1), 6: (2, 1), 3: (1, 2)}      # card: (column, row)
        at = {c: (oy + r * (MH + 1), ox + col * (MW + 1)) for c, (col, r) in cross.items()}
        at[2] = at[1]                                                         # crosses card 1
        for c, row in zip((10, 9, 8, 7), range(4)):                           # the staff, top to bottom
            at[c] = (row * (MH + 1), ox + 3 * (MW + 1) + 2)
        lay = [at[i] for i in range(1, 11)]
        zx = ox + 4 * (MW + 1) + 5
        self.scr.erase()
        self.stars(12)
        for k, (y, x) in enumerate(lay):
            if k == 1:
                continue                    # the crossing card is drawn last, sideways
            if flip is not None and flip[0] == k:
                self.flipping(y, x, MW, MH, spread[k], flip[1])
            elif k < upto:
                self.cells(y, x, art.mini_cells(*spread[k]))
            else:
                self.cells(y, x, art.back_cells(MW, MH))
            self.text(y, x + 1, f"{k + 1}", 51, True)
        y1, x1 = lay[0]
        bar = 15
        bx = x1 + (MW - bar) // 2
        if upto >= 2 or (flip and flip[0] == 1):
            c, r = spread[1]
            rows = art.frame(bar, 3, art.tags(c)[1])
            rk, st = art.split(c)
            label = art.SHORT.get(c) or f"{art.RANK_TAG[rk]} {st.upper()}"
            label = ("2 " + label + (" ▼" if r else ""))[: bar - 2]
            art._text_row(rows[1], (bar - len(label)) // 2, label, 231, art.CARD_BG)
            self.cells(y1 + 2, bx, rows)
        elif upto >= 1:
            self.cells(y1 + 2, bx, art.frame(bar, 3, 98))
            self.text(y1 + 3, bx + 2, "2  ◆◆◆◆◆", 98)
        show = flip[0] if flip else upto - 1
        if 0 <= show < n and (flip is None or flip[1] >= 4):
            c, r = spread[show]
            self.cells(1, zx, art.card_cells(c, r, BW, BH))
            self.text(BH + 1, zx, f"{show + 1}. {pos[show][0]}"[:BW + 4], 51, True)
            self.wrap_lines(BH + 2, zx, min(self.w - zx - 1, 28), position_meaning(c, r, pos[show][0], domain), 189, 6)
        else:
            self.cells(1, zx, art.back_cells(BW, BH))
        self.footer(msg)

    def reveal(self, key, spread, domain="inner"):
        n = len(spread)
        for i in range(n):
            self.wait_enter(lambda i=i: self.reveal_scene(key, spread, i, None, "Enter: turn the next card", domain))
            for k in range(9):
                self.reveal_scene(key, spread, i, (i, k), "", domain)
                self.scr.refresh()
                self.nap(45)
        self.wait_enter(lambda: self.reveal_scene(key, spread, n, None, "Enter: hear the reading", domain))

    # ---- falling cards ------------------------------------------------------------------------
    def fall_slot(self, i):
        return 9, (self.w - 6 * (MW + 1)) // 2 + i * (MW + 1)

    def fall_table(self, fallen, pairs, flip=None, y=None, upto=None, slots=None):
        """Draw six positions; paired cards overlap inside their shared position."""
        has_slot_map = slots is not None
        slots = slots if slots is not None else [[i] for i in range(len(fallen))]
        upto = len(slots) if upto is None else upto
        flipping = set(flip[0]) if flip is not None else set()
        for i in range(6):
            sy, sx = self.fall_slot(i)
            sy = sy if y is None else y
            card_ids = slots[i] if i < len(slots) else []
            visible = i < upto
            if card_ids and visible and len(card_ids) > 1:
                back, front = card_ids[1], card_ids[0]
                if flipping.intersection(card_ids):
                    self.flipping(sy, sx + 3, MW - 3, MH, fallen[back], flip[1])
                    self.flipping(sy, sx, MW - 3, MH, fallen[front], flip[1])
                else:
                    self.cells(sy, sx, _overlapped_mini(fallen[back], fallen[front]))
            elif card_ids and visible:
                card_id = card_ids[0]
                if card_id in flipping:
                    self.flipping(sy, sx, MW, MH, fallen[card_id], flip[1])
                else:
                    self.cells(sy, sx, art.mini_cells(*fallen[card_id]))
            elif card_ids:
                if len(card_ids) > 1:
                    self.cells(sy, sx + 3, _overlapped_back())
                else:
                    self.cells(sy, sx, art.back_cells(MW, MH))
            else:
                self.cells(sy, sx, art.frame(MW, MH, 60))
                self.text(sy + 2, sx + MW // 2, "?", 60)
            self.text(sy + MH, sx + MW // 2, str(i + 1), 51 if i < upto else 60)
        if not has_slot_map:
            for a, b in pairs:
                sy, sx = self.fall_slot(b)
                self.text((sy if y is None else y) + 2, sx - 1, "∞", 220, True)

    def riffle(self, t0, n, now):
        """Two half-decks and a stream of cards arcing between them."""
        lx, rx, y = self.w // 2 - 16, self.w // 2 + 7, 4
        self.stack(y, lx, 40, label=False)
        self.stack(y, rx, 38, label=False)
        dur = 0.9 + n * 0.06
        p = fx.pal(self.mood)
        for j in range(n):
            st = j / n * dur * 0.7
            f = (now - t0 - st) / 0.35
            if 0 <= f <= 1:
                x = lx + 4 + (rx - lx) * f
                yy = y + 1 - math.sin(f * math.pi) * 3
                self.put(int(yy), int(x), "▐█▌", self.attr(fx.idx_at(p, j * 0.07 + f)))

    def falling_frame(self, st, prompt="", buf="", now=None, footer=""):
        now = self.now() if now is None else now
        self.scr.erase()
        self.stars(20)
        self.gcenter(0, "~ the deck falls open ~")
        self.riffle(st["pass_t0"], st["pass_n"], now)
        drop = st.get("drop")
        if drop:                                  # cards in the air, falling to their slots
            f = min(1.0, (now - drop["t0"]) / 0.5)
            if "slot" in drop:
                sy, sx = self.fall_slot(drop["slot"])
                cx = self.w // 2 - MW // 2
                y, x = int(4 + (sy - 4) * f), int(cx + (sx - cx) * f)
                cards = drop["cards"]
                if len(cards) > 1:
                    self.cells(y, x, _overlapped_back())
                else:
                    self.cells(y, x, art.back_cells(MW, MH))
                fallen = st["fallen"][:cards[0]]
                slots = st["slots"][:drop["slot"]]
            else:
                for i in drop["idx"]:
                    sy, sx = self.fall_slot(i)
                    cx = self.w // 2 - MW // 2
                    self.cells(int(4 + (sy - 4) * f), int(cx + (sx - cx) * f), art.back_cells(MW, MH))
                fallen = st["fallen"][:min(drop["idx"])]
                slots = st.get("slots")
        else:
            fallen, slots = st["fallen"], st.get("slots")
        self.fall_table(fallen, st["pairs"], st.get("flip"), slots=slots, upto=st.get("upto"))
        lines = st.get("page", [])
        for j, ln in enumerate(lines):
            self.text(16 + j, 2, ln, 189)
        if prompt:
            line = f"{prompt} › {buf}"
            self.glow(self.h - 2, 2, line[: self.w - 4])
            if int(now * 2) % 2 == 0:
                self.put(self.h - 2, min(self.w - 2, 2 + len(line)), "▌", self.attr(51))
        self.footer(footer)

    def type_line(self, render):
        """Read a line while the animation keeps moving (Enter submits)."""
        buf = ""
        while True:
            render(buf)
            self.scr.refresh()
            k = self.scr.getch()
            if k in ENTER:
                return buf.strip()
            if k in (curses.KEY_BACKSPACE, 127, 8):
                buf = buf[:-1]
            elif 32 <= k < 127 and len(buf) < 160:
                buf += chr(k)

    def fall_card_browser(self, spread, pairs, questions, slots, reader, domain="inner"):
        """Let the querent inspect each fallen card and ask Veyra a focused follow-up."""
        pos = SPREADS["falling"]["positions"]
        selected = max(0, len(slots) - 1)
        response = ""

        def render(buf="", prompt=""):
            self.scr.erase()
            self.stars(18)
            self.gcenter(0, "~ choose a card to read ~")
            self.fall_table(spread, pairs, y=1, upto=len(slots), slots=slots)
            for i in range(len(slots)):
                _, sx = self.fall_slot(i)
                sy = 1
                color = 220 if i == selected else (51 if i < len(slots) else 60)
                self.text(sy + MH, sx + MW // 2 - 1, f"›{i + 1}‹" if i == selected else str(i + 1), color, i == selected)

            card_ids = slots[selected]
            cards = [spread[i] for i in card_ids]
            x0, y0 = 2, 9
            if len(cards) == 1:
                self.cells(y0, x0, art.card_cells(*cards[0], BW, BH))
            else:
                self.cells(y0, x0, art.card_cells(cards[0][0], cards[0][1], BW - 6, BH))
                self.cells(y0, x0 + BW - 4, art.card_cells(cards[1][0], cards[1][1], BW - 6, BH))

            tx = BW + 6
            names = " + ".join(c + (" (reversed)" if r else "") for c, r in cards)
            self.text(y0, tx, f"{selected + 1}. {pos[selected][0]}", 51, True)
            self.text(y0 + 1, tx, names[: self.w - tx - 1], 220, True)
            fall_q = questions[selected] if selected < len(questions) else None
            if fall_q:
                self.wrap_lines(y0 + 3, tx, self.w - tx - 2,
                                f"Veyra asked: \"{fall_q}\"", 189, 2)
            meaning = " ".join(position_meaning(c, r, pos[selected][0], domain) for c, r in cards)
            y = y0 + (6 if fall_q else 5)
            self.wrap_lines(y, tx, self.w - tx - 2, meaning, 189, 4)
            if response:
                self.text(min(self.h - 6, y + 5), tx, "Veyra answers", 51, True)
                lines = textwrap.wrap(response, self.w - tx - 2)
                room = max(2, self.h - (min(self.h - 6, y + 5) + 2) - 2)
                for j, ln in enumerate(lines[-room:]):
                    self.text(min(self.h - 6, y + 6) + j, tx, ln, 189)
            if prompt:
                line = f"Ask Veyra › {buf}"
                self.glow(self.h - 2, 2, line[: self.w - 4])
            else:
                self.footer("← → choose · 1-6 select · q ask Veyra · Enter close")

        while True:
            render()
            self.scr.refresh()
            k = self.scr.getch()
            if k in ENTER:
                return
            if k in (curses.KEY_LEFT, curses.KEY_UP, ord("a"), ord("A")):
                selected = (selected - 1) % len(slots)
            elif k in (curses.KEY_RIGHT, curses.KEY_DOWN, ord("d"), ord("D")):
                selected = (selected + 1) % len(slots)
            elif k in (ord("q"), ord("Q"), ord("?")):
                question = self.type_line(lambda buf: render(buf, "Ask Veyra"))
                if question:
                    response = ""
                    render()
                    self.scr.refresh()
                    response = reader.follow_up(question, domain, spread, selected, slots, questions, pairs)
            elif 49 <= k <= 54:
                n = k - 48
                if n <= len(slots):
                    selected = n - 1

    # ---- channeling ------------------------------------------------------------------------
    @_shimmering
    def channel(self, summon):
        """The veil thins; the querent's timing becomes entropy; a message comes through."""
        import threading
        vy, vx = max(0, self.h // 2 - 11), self.w // 2 - 13

        def veil():
            self.scr.erase()
            self.stars(40, mood="channel")
            self.veyra(vy, vx, 2.0)
            self.gcenter(vy + 15, "the veil thins...", mood="channel")
            self.gcenter(vy + 17, "press Enter when you feel it", mood="mystic")
        while True:
            veil()
            self.scr.refresh()
            if self.scr.getch() in ENTER:
                ns = time.time_ns()
                break
        res = {}
        t = threading.Thread(target=lambda: res.update(v=summon(ns)), daemon=True)
        t.start()
        order, k = ["mystic", "storm", "dread", "channel"], 0
        while t.is_alive() or k < 30:
            m = order[(k // 8) % 4]
            self.scr.erase()
            self.stars(50, k, m)
            self.veyra(vy, vx, 4.0)
            self.gcenter(vy + 15, "~ channeling the spirit realm ~", k * 0.1, m)
            if k >= 15:
                self.gcenter(vy + 17, "words coming through now...", k * 0.12, m)
            self.scr.refresh()
            self.nap(70)
            k += 1
        out = res.get("v")
        if not out:
            return None
        lines = textwrap.wrap(out["message"], min(64, self.w - 8))
        full = "\n".join(lines)
        for step in range(0, len(full) + 1, max(1, len(full) // 24)):
            self.scr.erase()
            self.stars(30, mood=out["mood"])
            self.veyra(vy, vx)
            shown = "".join(c if (i < step or c in " \n") else random.choice(fx.GLYPHS) for i, c in enumerate(full))
            for j, ln in enumerate(shown.split("\n")):
                self.gcenter(vy + 15 + j, ln, step * 0.05, out["mood"])
            self.scr.refresh()
            self.nap(60)

        def done():
            self.scr.erase()
            self.stars(30, mood=out["mood"])
            self.veyra(vy, vx)
            for j, ln in enumerate(lines):
                self.gcenter(vy + 15 + j, ln, mood=out["mood"])
            self.footer("press Enter")
        self.wait_enter(done)
        return out


    # ---- the waiting room: covers a slow local model while the reading is written ----------------
    def fmt_eta(self, sec):
        if sec is None:
            return "sensing time.."
        sec = int(sec)
        return "almost there" if sec < 8 else f"≈ {sec // 60}:{sec % 60:02d} left"

    def candle(self, y, x):
        j = self.job
        frame = int((self.now() - self.t0) * 6)
        rows = art.halfblock(art.glow_halo(art.candle_pixels(j.progress(), frame)))
        self.cells(y, x, rows)
        pct = f"{int(j.progress() * 100)}%"
        self.text(y + len(rows), x + (10 - len(pct)) // 2, pct, 220, True)

    def scene_orbit(self, spread, cx):
        """The drawn cards circle Veyra; cards behind her pass behind, cards in front pass in front."""
        t = self.now() - self.t0
        cy, n = self.h // 2, len(spread)
        rx, ry = min(27, cx - 7), min(8, cy - 4)
        items = []
        for i, (c, r) in enumerate(spread):
            a = t * 0.45 + i * 2 * math.pi / n
            items.append((math.sin(a), cy + int(math.sin(a) * ry) - MH // 2, cx + int(math.cos(a) * rx) - MW // 2, c, r))
        for d, y, x, c, r in sorted(items):
            if d >= 0:
                break
            self.cells(y, x, art.mini_cells(c, r))
        self.veyra(cy - 7, cx - 13, 3.0)
        for d, y, x, c, r in sorted(items):
            if d >= 0:
                self.cells(y, x, art.mini_cells(c, r))
        self.text(self.h - 3, 2, "the cards circle while she listens to them", 60)

    def scene_contemplate(self, card, width):
        """A card from the wider deck to sit with while you wait."""
        f = card_profile(card)
        self.cells(3, 3, art.card_cells(card, False, BW, BH))
        x = BW + 7
        self.glow(3, x, "While the spirits speak, sit with a card:")
        self.text(5, x, card.upper(), 220, True)
        from knowledge import facts
        k = facts(card)
        y = 7
        for label, s in (("It asks", k["ask"]), ("In love", k["love"]), ("In work", k["work"]), ("Within", k["inner"]),
                         ("Advice", k["advice"])):
            for j, ln in enumerate(textwrap.wrap(f"{label}: {s}", width - x - 2)[:3]):
                self.text(y, x, ln, 51 if j == 0 and label == "It asks" else 189, label == "It asks")
                y += 1
            y += 1

    def scene_whispers(self, width):
        """What she is writing, heard through the veil: mostly glyphs, a few true letters."""
        import re as _re
        self.veyra(self.h // 2 - 7, 2, 2.0)
        x = 32
        self.glow(3, x, "whispers through the veil...")
        raw = _re.sub(r"\[[^\]]*\]", "", self.job.text()).replace("\n", " ").strip()
        lines = textwrap.wrap(raw[-600:], width - x - 2)[-8:] if raw else []
        if not lines:
            t = self.now() - self.t0
            for i in range(40):
                a, r = t * 1.5 + i * 0.5, 1 + i * 0.25
                self.put(self.h // 2 + int(math.sin(a) * r * 0.45), x + 20 + int(math.cos(a) * r), fx.GLYPHS[i % len(fx.GLYPHS)],
                         self.attr(fx.idx_at(fx.pal("channel"), i * 0.05 + t * 0.3)))
            self.text(self.h - 3, x, "the threads of your question are gathering", 60)
            return
        bucket = int(self.now() * 3)
        for j, ln in enumerate(lines):
            shown = "".join(c if c == " " or (hash((j, i, bucket // 2)) % 100) < 22 else random.choice(fx.GLYPHS)
                            for i, c in enumerate(ln))
            self.glow(6 + j, x, shown, (self.now() - self.t0) * 0.5 + j * 0.2, "channel")

    @_shimmering
    def waiting_room(self, spread):
        """Cover the wait with visions until the reading is written, then let the querent choose
        the moment: 'press Enter when you are ready'."""
        scenes, si, since = ["orbit", "contemplate", "whispers"], 0, self.now()
        focus = SYS.choice([c for c in DECK if c not in {x for x, _ in spread}])
        cx_area = self.w - 16
        while True:
            j = self.job
            self.scr.erase()
            if j.done:
                self.stars(60, int(self.now() * 2), "hope")
                self.veyra(max(0, self.h // 2 - 9), self.w // 2 - 13, 1.5)
                self.gcenter(self.h // 2 + 7, "✦  your reading is ready  ✦", mood="hope")
                self.gcenter(self.h // 2 + 9, "press Enter when you are ready", mood="calm")
            else:
                self.stars(30, 3)
                self.gcenter(0, "~ Veyra is writing your reading ~")
                sc = scenes[si]
                if sc == "orbit":
                    self.scene_orbit(spread, cx_area // 2)
                elif sc == "contemplate":
                    self.scene_contemplate(focus, cx_area)
                else:
                    self.scene_whispers(cx_area)
                self.candle(3, self.w - 13)
                status = "gathering the threads..." if not j.started else self.fmt_eta(j.eta())
                self.text(BH + 4, self.w - 15, status[:14], 141)
                self.footer("n  next vision     g  grimoire     the reading will wait for you", meter=False)
                if self.now() - since > 12:
                    si, since = (si + 1) % len(scenes), self.now()
                    if scenes[si] == "contemplate":
                        focus = SYS.choice(DECK)
            self.scr.refresh()
            k = self.scr.getch()
            if j.done and k in ENTER:
                return
            if k == ord("n"):
                si, since = (si + 1) % len(scenes), self.now()
                focus = SYS.choice(DECK)
            elif k == ord("g"):
                self.grimoire(status=lambda: "✦ reading ready: q" if self.job.done else
                              f"✒ {int(self.job.progress() * 100)}% written  q: back")

    # ---- the grimoire ------------------------------------------------------------------------
    def grimoire(self, start=0, status=None):
        i, rev, scroll, cache = start, False, 0, {}
        while True:
            card = DECK[i]
            pw = max(30, self.w - BW - 6)
            if card not in cache:
                cache[card] = card_profile(card)
            prof = cache[card]
            lines = []
            for head, ls in prof:
                lines.append(("H", head))
                for l in ls:
                    for j, wl in enumerate(textwrap.wrap(l, pw - 2, subsequent_indent="   ")):
                        lines.append(("T", wl))
                lines.append(("T", ""))
            view = self.h - 3
            scroll = max(0, min(scroll, len(lines) - view))
            self.scr.erase()
            self.cells(1, 2, art.card_cells(card, rev, BW, BH))
            self.text(BH + 2, 2, f"{i + 1:>2} / 78", 60)
            self.text(BH + 3, 2, "← → card   ↑ ↓ scroll", 60)
            self.text(BH + 4, 2, "r reverse  w c s p suits", 60)
            self.text(BH + 5, 2, "0 Fool     q back", 60)
            x = BW + 5
            self.text(0, x, f"THE GRIMOIRE: {card.upper()}"[:pw], 220, True)
            if status:
                st = status()
                self.text(self.h - 1, 2, st[: BW + 2], 120 if "ready" in st else 98, "ready" in st)
            for j, (kind, s) in enumerate(lines[scroll: scroll + view]):
                self.text(2 + j, x, s[:pw], 51 if kind == "H" else 189, kind == "H")
            if scroll + view < len(lines):
                self.text(self.h - 1, x, "▼ more (↓)", 60)
            self.scr.refresh()
            k = self.scr.getch()
            if k == -1:
                continue
            if k in (ord("q"), 27):
                return
            if k == curses.KEY_RIGHT:
                i, scroll = (i + 1) % 78, 0
            elif k == curses.KEY_LEFT:
                i, scroll = (i - 1) % 78, 0
            elif k == curses.KEY_DOWN:
                scroll += 1
            elif k == curses.KEY_UP:
                scroll -= 1
            elif k == curses.KEY_NPAGE:
                scroll += view - 2
            elif k == curses.KEY_PPAGE:
                scroll -= view - 2
            elif k == ord("r"):
                rev = not rev
            elif k == ord("0"):
                i, scroll = 0, 0
            elif k in (ord("w"), ord("c"), ord("s"), ord("p")):
                suit = {"w": "Wands", "c": "Cups", "s": "Swords", "p": "Pentacles"}[chr(k)]
                i, scroll = DECK.index(f"Ace of {suit}"), 0


class FitScreen:
    """Wraps the curses screen so every scene fits any terminal size.

    Drawing goes to a canvas at least MIN_W x MIN_H (bigger terminals get the full size, and the
    layouts spread out to use it). On a smaller terminal the canvas is shown centred with the footer
    row kept, plus a hint to zoom out. Rotating the iPad, zooming the browser or dragging the panel
    sends a resize, and the next frame lays itself out again at the new size."""
    MIN_H, MIN_W = 24, 80
    virtual = False

    def __init__(self, real):
        self.real = real
        self.erase()

    def _size(self):
        self.H, self.W = self.real.getmaxyx()
        self.LH, self.LW = max(self.H, self.MIN_H), max(self.W, self.MIN_W)

    def getmaxyx(self):
        return self.LH, self.LW

    def erase(self):
        self._size()
        self.buf = [[(" ", 0)] * self.LW for _ in range(self.LH)]

    def clear(self):
        """Wipe the whole terminal on the next refresh, not just the canvas, so nothing drawn before
        (an old draw, stray output, a mis-sized glyph) can linger in a cell curses thinks is blank."""
        try:
            self.real.clear()
        except curses.error:
            pass
        self.erase()

    def addstr(self, y, x, s, a=0):
        if not 0 <= y < len(self.buf):
            return
        row = self.buf[y]
        for i, ch in enumerate(s):
            if 0 <= x + i < len(row):
                row[x + i] = (ch, a)

    def refresh(self):
        H, W = self.real.getmaxyx()
        LH, LW = len(self.buf), len(self.buf[0]) if self.buf else 0
        ox = max(0, (LW - W) // 2)
        rows = list(range(min(H, LH))) if H >= LH else list(range(max(0, H - 1))) + [LH - 1]
        self.real.erase()
        for ry, ly in enumerate(rows):
            line, x = self.buf[ly][ox:ox + W], 0
            while x < len(line):
                a, j = line[x][1], x
                while j < len(line) and line[j][1] == a:
                    j += 1
                try:
                    self.real.addstr(ry, x, art.plain("".join(c for c, _ in line[x:j])), a)
                except curses.error:
                    pass
                x = j
        if (LW > W or LH > H) and W >= 24:
            hint = " zoom out to see it all " if W < 40 else " zoom out (pinch or Cmd -) to see the whole table "
            try:
                self.real.addstr(0, max(0, W - len(hint) - 1), hint[: W - 1], curses.A_REVERSE)
            except curses.error:
                pass
        self.real.refresh()

    def getch(self):
        k = self.real.getch()
        if k == 23:                                  # Ctrl+W: the control room (the model pauses)
            import control
            if not control.IN_ROOM:
                control.room(self)
                self.real.clear()
                self.erase()
                self.real.timeout(70)
                return -1
        if k == curses.KEY_RESIZE:
            try:
                curses.update_lines_cols()
            except Exception:
                pass
            self.real.clear()
            self.erase()
        return k

    def __getattr__(self, name):
        return getattr(self.real, name)


def _sized(scr):
    """Every curses scene goes through here: returns a screen that fits whatever size the terminal is."""
    return scr if isinstance(scr, FitScreen) or getattr(scr, "virtual", False) else FitScreen(scr)


def _fresh(scr):
    """A new reading starts on a wiped screen: no card from the last draw survives into this one."""
    (getattr(scr, "clear", None) or scr.erase)()
    return scr


WAIT_LIMIT = int(os.environ.get("TAROT_WAIT_LIMIT", "20"))   # seconds of writing left before the waiting room


def ritual(scr, key, spirit_qs, reader, ctx, plan, domain, start):
    scr = _fresh(_sized(scr))
    ui = UI(scr, plan)
    channeled = []

    def event(extra=""):
        out = ui.channel(lambda ns: reader.summon(ctx + extra, ns))
        if out:
            channeled.append(out["message"])
    deck = build_deck()
    SYS.shuffle(deck)
    ui.intro(reader.label)
    ui.hold_questions(spirit_qs)
    ui.mood = plan["wash"]
    ui.wash()
    ui.gather()
    if SYS.random() < 0.35:
        event()
    ui.mood = plan["cut"]
    deck = ui.reassemble(ui.cut(deck))
    if SYS.random() < 0.35:
        event()
    spread = [(deck[i], SYS.random() < 0.25) for i in range(len(SPREADS[key]["positions"]))]
    ui.job = start(spread, list(channeled))          # Veyra starts writing the moment the cards fall
    ui.mood = plan["reveal"]
    ui.reveal(key, spread, domain)
    if SYS.random() < 0.5:
        event(" Cards: " + ", ".join(c + (" (reversed)" if r else "") for c, r in spread))
    j = ui.job
    if not j.done and (j.eta() is None or j.eta() > WAIT_LIMIT):
        ui.waiting_room(spread)                       # too long to stream live: cover it, then ask
    return spread, channeled, j


P_FALL = float(os.environ.get("TAROT_FALL_CHANCE", "0.36"))     # chance a card falls on each pass
P_PAIR = float(os.environ.get("TAROT_PAIR_CHANCE", "0.14"))     # chance that a fall is two cards together
ZODIAC_MONTHS = (
    ("January", "Capricorn", "earth"), ("February", "Aquarius", "air"),
    ("March", "Pisces", "water"), ("April", "Aries", "fire"),
    ("May", "Taurus", "earth"), ("June", "Gemini", "air"),
    ("July", "Cancer", "water"), ("August", "Leo", "fire"),
    ("September", "Virgo", "earth"), ("October", "Libra", "air"),
    ("November", "Scorpio", "water"), ("December", "Sagittarius", "fire"),
)


def zodiac_picker(scr, next_index):
    """Static arrow-key picker; None means use the next automatic sign."""
    scr = _sized(scr)
    ui = UI(scr)
    selected = 0
    while True:
        scr.erase()
        ui.center(1, "six-card reading: choose a zodiac lens", 51, True)
        month, sign, element = ZODIAC_MONTHS[next_index]
        ui.center(3, f"↑ ↓ move · Enter select · auto next: {month} / {sign} ({element})", 60)
        options = [None, "none", *range(len(ZODIAC_MONTHS))]
        for row, option in enumerate(options):
            if option is None:
                label = f"AUTO  next in sequence: {month} · {sign} ({element})"
            elif option == "none":
                label = "NONE  a normal six-card reading, no zodiac lens"
            else:
                month, sign, element = ZODIAC_MONTHS[option]
                label = f"{month} · {sign} · {element}"
            x = max(1, (ui.w - len(label) - 2) // 2)
            ui.text(5 + row, x, ("› " if row == selected else "  ") + label,
                    51 if row == selected else 153, row == selected)
        scr.refresh()
        key = scr.getch()
        if key == curses.KEY_UP:
            selected = (selected - 1) % len(options)
        elif key == curses.KEY_DOWN:
            selected = (selected + 1) % len(options)
        elif key in ENTER:
            return options[selected]
        elif key in (ord("q"), ord("Q"), 27):
            return None


def choose_zodiac(reader):
    try:
        next_index = int(reader.mem.get("next_zodiac_index", 0)) % len(ZODIAC_MONTHS)
    except (TypeError, ValueError):
        next_index = 0
    selected = curses.wrapper(zodiac_picker, next_index)
    if selected == "none":                                  # a plain six-card reading
        return None, None, None, None
    automatic = selected is None
    index = next_index if automatic else selected % len(ZODIAC_MONTHS)
    month, sign, element = ZODIAC_MONTHS[index]
    return month, sign, element, index if automatic else None


def falling_ritual(scr, reader, plan, domain, concern, start, zodiac_sign=None, element=None):
    """Live Reading: Veyra asks the deck her own questions; six cards fall out of the shuffle, each
    answering the question asked just before it. Every step is logged so a video can replay it."""
    import live
    from knowledge import fall_reading, pair_reading
    scr = _fresh(_sized(scr))
    ui = UI(scr, plan)
    ui.mood = plan["wash"]
    domain = domain or "inner"
    deck = build_deck()
    SYS.shuffle(deck)
    st = {"fallen": [], "slots": [], "pairs": [], "pass_t0": ui.now(), "pass_n": 12,
            "page": [], "questions": [None] * 6}
    log, asked = [], []

    def pages(text):
        room = max(3, ui.h - 19)
        lines = textwrap.wrap(text, ui.w - 4)
        if not lines:
            return [[]]
        n = -(-len(lines) // room)                     # even pages: no lonely last line
        size = -(-len(lines) // n)
        return [lines[i:i + size] for i in range(0, len(lines), size)]

    def show(text, footer="Enter"):
        ps = pages(text)
        for k, pg in enumerate(ps):
            st["page"] = pg
            ui.wait_enter(lambda: idle(footer="Enter: more" if k < len(ps) - 1 else footer))

    def idle(footer=""):
        if ui.now() - st["pass_t0"] > 0.9 + st["pass_n"] * 0.06 + 0.4:     # the deck keeps riffling
            st["pass_t0"], st["pass_n"] = ui.now(), SYS.randint(10, 15)
        ui.falling_frame(st, footer=footer)

    while len(st["slots"]) < 6:
        i = len(st["slots"])
        q, opener, feeling = live.next_question(i, st["fallen"], reader.mem, SYS, asked)
        asked.append(q)
        st["questions"][i] = q
        st["page"] = textwrap.wrap(f"{opener} {q}", ui.w - 4)
        passes = 0
        while True:
            passes += 1
            st["pass_t0"], st["pass_n"] = ui.now(), SYS.randint(10, 15)
            while ui.now() - st["pass_t0"] < 0.9 + st["pass_n"] * 0.06:
                ui.falling_frame(st, footer="the deck shuffles...")
                ui.scr.refresh()
                ui.nap(40)
            if SYS.random() < P_FALL:
                break
        k = 2 if SYS.random() < P_PAIR else 1
        new = [(deck.pop(SYS.randrange(len(deck))), SYS.random() < 0.3) for _ in range(k)]
        first_card = len(st["fallen"])
        idx = list(range(first_card, first_card + k))
        st["fallen"] += new
        st["slots"].append(idx)
        st["drop"] = {"t0": ui.now(), "slot": i, "cards": idx}
        while ui.now() - st["drop"]["t0"] < 0.5:
            ui.falling_frame(st, footer="a card falls!" if k == 1 else "two cards fall together!")
            ui.scr.refresh()
            ui.nap(30)
        st["drop"] = None
        for fr in range(9):
            st["flip"] = (tuple(idx), fr)
            ui.falling_frame(st)
            ui.scr.refresh()
            ui.nap(45)
        st["flip"] = None
        if k == 2:
            st["pairs"].append(tuple(idx))
        texts = [fall_reading(c, r, i, q if j == 0 else None, domain, reader.mem,
                              sign=zodiac_sign, element=element) for j, (c, r) in enumerate(new)]
        if k == 2:
            texts.append(pair_reading(new[0][0], new[0][1], new[1][0], new[1][1], domain, reader.mem,
                                      sign=zodiac_sign, element=element))
        if psyche.active():
            texts = [psyche.dissociate(x, new) for x in texts]
        log.append({"question": q, "opener": opener, "feeling": feeling, "passes": passes,
                    "slot": i, "idx": idx,
                    "cards": [list(x) for x in new], "text": " ".join(texts)})
        show(" ".join(texts), "Enter" if len(st["slots"]) < 6 else "Enter: see all six")
    spread = st["fallen"]
    ui.fall_pairs, ui.fall_questions = st["pairs"], st["questions"]
    ui.fall_slots = st["slots"]
    j = start(spread, st["pairs"], st["questions"]) if start else None   # Live Readings end on the six cards
    ui.job = j
    ui.mood = plan["reveal"]
    ui.wait_enter(lambda: ui.reveal_scene("falling", spread, 6, None,
                                          "Enter: inspect the six cards", domain))
    ui.fall_card_browser(spread, st["pairs"], st["questions"], st["slots"], reader, domain)
    if j and not j.done and (j.eta() is None or j.eta() > WAIT_LIMIT):
        ui.waiting_room(spread)
    return spread, st["pairs"], st["questions"], j, log, st["slots"]


def grimoire_screen(scr):
    scr = _sized(scr)
    UI(scr).grimoire()


# ===================================================================== plain-terminal parts
def portrait(label=""):
    print()
    title = art.halfblock(art.text_pixels("VEYRA"))
    if shutil.get_terminal_size((80, 24)).columns >= 72:
        fx.print_cells(art.side_by_side([art.veyra_cells(), title], 4), None)
    else:                                   # narrow screen: stack her above the title
        fx.print_cells(art.veyra_cells(), None)
        if shutil.get_terminal_size((80, 24)).columns >= 40:
            fx.print_cells(title, None)
    if label:
        fx.show(f"mind: {label}".center(min(78, shutil.get_terminal_size((80, 24)).columns - 4)), "calm")
    print()


def show_table(key, spread, falls=None):
    """The laid cards as pixel art, printed above the reading."""
    pos = SPREADS[key]["positions"]
    cols = shutil.get_terminal_size((80, 24)).columns
    if key == "falling":
        slots = (falls or {}).get("slots") or [[i] for i in range(len(spread))]
        for i, card_ids in enumerate(slots):
            cards = [spread[j] for j in card_ids]
            fx.show(f"{i + 1}. {pos[i][0]}", "hope", 2)
            if len(cards) > 1:
                block = _overlapped_mini(cards[1], cards[0])
            else:
                block = art.mini_cells(*cards[0])
            fx.print_cells(block, 2)
        print()
        return
    if key == "three" and cols >= 3 * (BW + 2) + 2:
        blocks = [art.card_cells(c, r, BW, BH) for c, r in spread]
        labels = "".join(p[0].upper().center(BW + 2) for p in pos)
        fx.show(labels, "hope", max(0, (shutil.get_terminal_size((80, 24)).columns - len(labels)) // 2))
        fx.print_cells(art.side_by_side(blocks, 2), None)
    else:
        per = max(1, min(6 if key == "falling" else 5, (cols - 2) // (MW + 2)))
        for row in [range(i, min(i + per, len(spread))) for i in range(0, len(spread), per)]:
            fx.show("".join(f"{i + 1}. {pos[i][0]}"[:MW + 2].ljust(MW + 2) for i in row), "hope", 2)
            fx.print_cells(art.side_by_side([art.mini_cells(*spread[i]) for i in row], 2), 2)
    print()


def ansi_channel(reader, ctx):
    fx.say("The veil thins. Press Enter when you feel it.", "channel", "fade")
    fx.prompt("channel")
    ns = time.time_ns()
    out = fx.run_with_animation(lambda: reader.summon(ctx, ns))
    if out:
        fx.say(out["message"], out["mood"], "glitch")
        return out["message"]


def ask(mood="storm"):
    """Prompt the querent; if they sound like they are in danger, step out of the role."""
    ans = fx.prompt(mood)
    if Q.in_crisis(ans):
        print()
        fx.say(Q.CRISIS_MSG, "calm", "fade")
        fx.say("Press Enter to keep going with the cards, or type q to leave.", "calm", "fade")
        if fx.prompt("calm").lower().startswith("q"):
            raise SystemExit(0)
    return ans


def offer_model(reader):
    """If the built-in model isn't ready, explain and offer the free download."""
    if reader.online:
        return
    try:
        import llama_cpp  # noqa
        has_engine = True
    except Exception:                     # missing, or installed but its DLL will not load
        has_engine = False
    if has_engine and not brain.find_gguf():
        size = brain.CATALOG[brain.DEFAULT][2]
        fx.say(f"I can think with a free model that lives on this machine. Download it now? ({size}, one time) [Y/n]",
               "hope", "fade")
        if not fx.prompt().lower().startswith("n"):
            brain.download(brain.DEFAULT)
            reader.brain.connect()
            fx.say(f"Awake: {reader.label}" if reader.online else "It would not wake: " + reader.brain.err, "hope", "shimmer")
            return
    if not has_engine:
        fx.say("No built-in model yet, so I read from my own scripted knowledge (still a full reading). "
               "For the free AI version run:  bash setup_local.sh", "grief", "type")


def ask_profile(reader=None):
    """Work and sign every time; age and gender once (then remembered); plus a few questions from a pool of
    over a thousand that she never repeats. Blank answers are skipped."""
    import intake
    mem = reader.mem if reader is not None else {}
    facts = mem.setdefault("about_you", {})
    fx.say("A few things to help me feel you out. Press Enter to skip any.", "calm", "fade")
    prof = {}
    fx.say("Your career, or what you do?", "calm", "type")
    v = ask()
    if v:
        prof["career"] = v
    for label, k in (("Your age?", "age"), ("Your sex or gender?", "sex/gender")):
        if facts.get(k):
            prof[k] = facts[k]
            continue
        fx.say(label, "calm", "type")
        v = ask()
        if v:
            prof[k] = facts[k] = v
    fx.say("Your astrological sign? Or just its element: fire, earth, air or water.", "calm", "type")
    v = ask()
    sign, element = parse_sign(v)
    if element:
        prof["sign"] = f"{sign} ({element})" if sign else element
        fx.say(f"{sign + ', ' if sign else ''}{element}. The {ELEMENT_SUIT[element]} will speak in your voice.", "mystic", "fade")
    elif v:
        prof["sign"] = v
    for q in intake.pick(mem, 3):
        fx.say(q, "calm", "type")
        v = ask()
        if v:
            prof[q.rstrip("?")] = v
    if reader is not None:
        try:
            reader._save()
        except Exception:
            pass
    return ", ".join(f"{k}: {v}" for k, v in prof.items()) or "(not shared)"


def choose_style():
    """Always the first thing she asks: which style of reading."""
    fx.say("What style of reading tonight?", "mystic", "fade")
    fx.say("1) Three-Card (past, present, future)   2) Celtic Cross (10 cards)", "hope", "type")
    fx.say("3) Live Reading (Veyra asks the deck her own questions)   4) Let Veyra choose", "hope", "type")
    return {"1": "three", "2": "celtic", "3": "falling"}.get(fx.prompt().strip(), None)


FIRST_MEETING = ("We haven't met before, so I need to get to know you a little better before I can make "
                 "this super personal. Tonight I'll read from the cards and my grimoire. Everything you share, "
                 "and every reading after this one, I'll remember.")


def reading(reader):
    style = choose_style()
    if not reader.knows_you():
        fx.say(FIRST_MEETING, "calm", "fade")
    if style == "falling":
        return live_reading(reader)
    fx.say("What do you bring to the cards today?", "mystic", "fade")
    question = ask() or "What do I need to see?"
    profile = ask_profile(reader)

    qa = []
    while True:
        if len(qa) == 3:
            reader.prefetch_question(question, profile, qa)   # she improvises while you answer
        if len(qa) == 4 and reader.adaptive_pending():
            q = fx.run_with_animation(lambda: reader.next_question(question, profile, qa), 0,
                                      ("~ Veyra studies your face ~", "~ a question is forming ~"))
        else:
            q = reader.next_question(question, profile, qa)
        if not q:
            break
        fx.say(q["ask"], q["mood"], q["fx"])
        qa.append((q["ask"], ask()))
        if qa[-1][1] and SYS.random() < 0.5:
            fx.say(reader.acknowledge(), "calm", "fade")
    domain = detect_domains(question + " " + " ".join(a for _, a in qa))[0]
    plan = reader.style_plan(question, profile, qa)
    spirit_qs = reader.spirit_questions(question, profile, qa)
    fx.say("To the spirits, I ask:", "channel", "shimmer")
    for q in spirit_qs:
        fx.say("• " + q, plan["intro"], "fade")
    if style:
        key = style
    else:
        key, why = reader.choose_spread(question, profile, qa)
        fx.say(f"Veyra lays the {SPREADS[key]['name']}. {why}", plan["intro"], "shimmer")
    ctx = f"Question: {question}. Spirit questions: {'; '.join(spirit_qs)}."
    reader.warm(question, profile, qa, spirit_qs)    # pre-load the question into a local model
    fx.say("Press Enter to begin the ritual.", "mystic", "pulse")
    fx.prompt()
    falls = None
    start = lambda sp, ch: reader.start_reading(question, profile, qa, spirit_qs, key, sp, ch)
    spread, channeled, job = curses.wrapper(ritual, key, spirit_qs, reader, ctx, plan, domain, start)
    finish_reading(reader, question, profile, qa, spirit_qs, key, spread, job, plan, domain, ctx, falls,
                   channeled=channeled)


def live_reading(reader):
    """Live Reading: no questions for you. Veyra asks the deck her own, and six cards fall."""
    month, sign, element, auto_index = choose_zodiac(reader)
    fx.say("A Live Reading. You do not need to ask anything: I will put my own questions to the deck, "
           "and it will answer by dropping cards from the shuffle. Sometimes two fall together; those speak as one.",
           "mystic", "fade")
    if sign:
        fx.say(f"{sign}, a sign of {element}. I will read the element against every card as it falls.", "mystic", "fade")
    fx.say("Press Enter when you are ready, and simply hold how you feel in mind.", "mystic", "pulse")
    fx.prompt()
    plan = {"intro": "calm", "wash": "storm", "cut": "mystic", "reveal": "dread", "reading": "mystic"}
    # each card is read as it falls, so there is no final reading: no model job is started
    spread, pairs, questions, job, log, slots = curses.wrapper(falling_ritual, reader, plan, None, "", None,
                                                               sign, element)
    if auto_index is not None:
        reader.mem["next_zodiac_index"] = (auto_index + 1) % len(ZODIAC_MONTHS)
        try:
            reader._save()
        except Exception as exc:
            fx.say(f"I could not save the zodiac cycle: {str(exc)[:120]}", "dread", "fade")
    falls = {"pairs": pairs, "questions": questions, "log": log, "slots": slots}
    finish_reading(reader, "A Live Reading", f"sign: {sign} ({element})", [], [], "falling", spread, job, plan, "inner",
                   "A Live Reading.", falls, live=True)


def finish_reading(reader, question, profile, qa, spirit_qs, key, spread, job, plan, domain, ctx, falls=None, live=False,
                   channeled=None):
    channeled = list(channeled or [])
    cards = ", ".join(c + (" (reversed)" if r else "") for c, r in spread)
    done = [0]
    if job is None:                                 # Live Reading: the cards were read as they fell
        import questions as Q
        show_table(key, spread, falls)
        text = SYS.choice(Q.CLOSINGS)
        fx.say(text, "hope", "fade")
        done[0] = 1                                 # no channeled message either
        names = [f"{c}{' (reversed)' if r else ''}" for c, r in spread]
        heard = " ".join(e["text"] for e in (falls or {}).get("log", []))
        reader.later(reader._reflect, "A Live Reading", [], names, heard)   # she still learns from it
    else:
        fx.banner("~ Veyra reads ~", plan["reading"], 20)
        show_table(key, spread, falls)

        def on_channel():
            if done[0] < 1:
                msg = ansi_channel(reader, ctx + " Cards: " + cards)
                if msg:
                    channeled.append(msg)
                done[0] += 1
        text = fx.play_stream(job.stream(), plan["reading"], on_channel)
        text = job.text() or text
    if done[0] == 0 and SYS.random() < 0.6:
        msg = ansi_channel(reader, ctx + " Cards: " + cards)
        if msg:
            channeled.append(msg)
    sess = {"date": time.strftime("%Y-%m-%d %H:%M"), "question": question, "profile": profile, "qa": qa,
            "spirit_qs": spirit_qs, "key": key, "spread": spread, "domain": domain, "reading": text,
            "plan": plan, "mind": reader.label, "falls": falls, "channeled": channeled,
            "psy": psyche.active(),
            "interesting": psyche.interesting(text + " " + " ".join(e["text"] for e in (falls or {}).get("log", [])), spread)}
    try:
        import video
        video.save_session(sess)
    except Exception:
        pass
    print()
    if not live:                                    # a Live Reading asks you nothing
        fx.say("Did this ring true? Tell me what landed and what missed (Enter to skip).", "calm", "fade")
        ans = ask()
        if ans:
            reader.later(reader.feedback, ans)      # she learns in the background
            fx.say("She nods, and writes it down in the margins of her grimoire.", "calm", "fade")
    fx.say("Would you like this reading as a video, to keep or to share? [y/N]", "hope", "fade")
    if fx.prompt().lower().startswith("y"):
        make_and_share(sess)


# ===================================================================== videos: make, save, share
def _ask(q):
    fx.say(q + " [Y/n]", "calm", "fade")
    return not fx.prompt().lower().startswith("n")


def _note(t):
    fx.show(t.strip(), "calm")


def _progress(f):
    n = int(f * 24)
    sys.stdout.write(f"\r  {'▰' * n}{'▱' * (24 - n)}  {int(f * 100):3d}%")
    sys.stdout.flush()
    if f >= 1:
        print()


def make_and_share(sess):
    import video
    fx.say("What should the title at the top say? Leave blank for a reading-inspired title.", "hope", "fade")
    sess["video_title"] = fx.prompt().strip()
    fx.say("Veyra draws the reading frame by frame...", "mystic", "fade")
    path = video.make(sess, _ask, _note, _progress)
    if path:
        fx.say(f"The video is ready: {path}", "hope", "shimmer")
        share_menu(path)


def promo_video(reader):
    """The promo reel maker (veyra_promo.py), run inside Veyra with the model she already has loaded."""
    try:
        import veyra_promo
    except Exception as e:
        return fx.say(f"The promo maker would not start: {str(e)[:120]}", "dread", "type")
    import deps
    if not deps.ensure_ffmpeg(_ask, _note):
        return
    fx.say("Veyra makes a new promo reel (about 2:30, different every time). This takes a while...", "mystic", "fade")
    b, orig, argv = reader.brain, veyra_promo.Brain.__init__, sys.argv
    if b.kind == "llama" and b.llm is not None:         # share her loaded model instead of loading it twice
        def shared(self, a):
            self.a, self.kind, self.llama = a, "llama.cpp", b.llm
        veyra_promo.Brain.__init__ = shared
    sys.argv = ["veyra_promo.py"]
    path = None
    try:
        with b.lock:
            path = veyra_promo.main()
    except SystemExit as e:
        fx.say(f"The promo did not finish: {e}", "dread", "type")
    except Exception as e:
        fx.say(f"The promo did not finish: {str(e)[:160]}", "dread", "type")
    finally:
        veyra_promo.Brain.__init__, sys.argv = orig, argv
    if path:
        fx.say(f"The promo is ready: {path}", "hope", "shimmer")
        share_menu(path)


def share_menu(path):
    import share
    while True:
        first = "Save it to your device" if share.in_codespace() else "Open the video folder"
        fx.say(f"1) {first}   2) Share to Facebook   3) Done", "hope", "type")
        c = fx.prompt()
        if c == "1":
            offer_download(path)
        elif c == "2":
            share_facebook(path)
        else:
            return


def offer_download(path):
    import share
    if not share.in_codespace():                       # on your own machine it is already saved here
        folder = Path(path).resolve().parent
        fx.say(f"Saved on this machine: {Path(path).resolve()}", "hope", "fade")
        try:
            if os.name == "nt":
                os.startfile(folder)
            elif shutil.which("xdg-open"):
                subprocess.Popen(["xdg-open", str(folder)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass
        return

    def wait(link, port):
        fx.say("Open this link to download your video:", "hope", "fade")
        fx.show(link, "storm")
        if share.in_codespace():
            fx.show("(It opens in the browser you use for this Codespace; sign in with GitHub if it asks.", "calm")
            fx.show(" You can also right-click the file in the Explorer and choose Download.)", "calm")
        else:
            fx.show(f"(The file is also here: {Path(path).resolve()})", "calm")
        fx.say("Press Enter when the download has finished.", "calm", "fade")
        fx.prompt()
    if share.serve(path, wait) is None:
        fx.say(f"I could not open a download port. The video is at {Path(path).resolve()}", "dread", "type")


def share_facebook(path):
    import share
    cfg = share.facebook_config()
    if not cfg:
        fx.say("Facebook only lets apps post to Pages, not personal profiles, and no Page is set up yet.",
               "calm", "fade")
        if _ask("Get a download link so you can post it from your phone or iPad?"):
            offer_download(path)
            fx.show(share.PROFILE_STEPS, "calm")
        if _ask("Show how to connect a Facebook Page so Veyra can post for you next time?"):
            fx.show(share.FACEBOOK_SETUP, "calm")
        return
    name = fx.run_with_animation(lambda: _try(share.facebook_page_name, cfg), 6, ("~ reaching Facebook ~",))
    if isinstance(name, Exception) or not name:
        fx.say(f"Facebook would not accept the Page token: {str(name)[:160]}", "dread", "type")
        fx.show(share.FACEBOOK_SETUP, "calm")
        return
    fx.say(f"Write a caption for your post on {name} (Enter for a default):", "calm", "fade")
    caption = fx.prompt() or "A reading from Veyra, an 8-bit tarot reader running on a local AI. ✦"
    if not _ask(f"Post this video publicly to the Facebook Page '{name}' now?"):
        fx.say("Not posted.", "calm", "fade")
        return
    url = fx.run_with_animation(lambda: _try(share.upload_to_page, path, caption, cfg), 12, ("~ sending it to Facebook ~",))
    if isinstance(url, Exception) or not url:
        fx.say(f"The upload did not go through: {str(url)[:160]}", "dread", "type")
    else:
        fx.say(f"Posted to {name}: {url}", "hope", "shimmer")


def _try(fn, *a):
    try:
        return fn(*a)
    except Exception as e:
        return e


def _model_mode():
    active = brain.find_gguf()
    keys = list(brain.CATALOG)
    print("\nBuilt-in models (enter a number or model key; q cancels):")
    for index, key in enumerate(keys, 1):
        _, filename, size, _ = brain.CATALOG[key]
        path = brain.MODELS_DIR / filename
        state = "active" if active and active.name == filename else ("installed" if path.exists() else f"download {size}")
        print(f"  {index}) {key:<10} {state}")
    choice = fx.prompt()
    if choice.lower() in ("", "q", "quit"):
        return False
    key = choice if choice in brain.CATALOG else None
    if key is None and choice.isdigit() and 1 <= int(choice) <= len(keys):
        key = keys[int(choice) - 1]
    if key is None:
        print("Unknown model selection.")
        return False

    _, filename, _, _ = brain.CATALOG[key]
    path = brain.MODELS_DIR / filename
    try:
        if not path.exists():
            path = brain.download(key, log=lambda message: fx.say(message, "hope", "fade"))
        else:
            brain.ACTIVE.write_text(filename)
    except Exception as exc:
        print(f"Model download failed: {exc}", file=sys.stderr)
        return False
    print(f"Selected {key}. Restart tarot.py to load {path.name}.")
    return True


def _git_sync(*args, quiet=False):
    git_dir = Path(".git")
    operation_markers = (
        git_dir / "rebase-merge",
        git_dir / "rebase-apply",
        git_dir / "MERGE_HEAD",
        git_dir / "CHERRY_PICK_HEAD",
        git_dir / "REVERT_HEAD",
    )
    if args and args[0] in ("pull", "rebase", "push") and any(marker.exists() for marker in operation_markers):
        if not quiet:
            print("Git sync paused while a rebase or merge is in progress.", file=sys.stderr)
        return 128

    command = ["git", *args]
    env = os.environ.copy()
    env["PATH"] = os.pathsep.join((str(Path.home() / ".local/bin"), env.get("PATH", "")))
    env["GIT_TERMINAL_PROMPT"] = "0"
    try:
        result = subprocess.run(
            command,
            cwd=Path(__file__).resolve().parent,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
    except OSError as exc:
        print(f"Git sync unavailable: {exc}", file=sys.stderr)
        return 127
    if result.stdout and (not quiet or result.returncode):
        print(result.stdout.rstrip())
    if result.returncode and not (quiet and result.returncode == 1):
        print(f"Git sync failed: {' '.join(command)}; local data is retained.", file=sys.stderr)
    return result.returncode


def _sync_after_session():
    if _git_sync("add", "-A", "--", "memory.json", "sessions/"):
        return
    changed = _git_sync("diff", "--cached", "--quiet", "--", "memory.json", "sessions/", quiet=True)
    if changed == 1:
        if _git_sync("commit", "--only", "-m", "Save tarot session", "--", "memory.json", "sessions/"):
            return
    elif changed:
        print("Git sync could not check staged session data; local data is retained.", file=sys.stderr)
        return
    if _git_sync("pull", "--rebase", "--autostash"):
        return
    if _git_sync("push"):
        return
    _git_sync("pull", "--rebase", "--autostash")


def stars_menu(reader, sign=None):
    """Your stars: the star chart and today's horoscope in one. Give a birth date and she reads the sky
    you were born under, then what today's sky is doing to it; give just a sign and she reads that sign's day."""
    import astro, re as _re
    sky = astro.today()
    fx.banner("~ Veyra reads your stars ~", "channel", 20)
    fx.say("No website and no one else's stars: I work out where every planet is from its orbit, "
           "and read the sky myself.", "mystic", "fade")
    natal = None
    if not sign:
        fx.say("Your birth date? (YYYY-MM-DD; or just your sign if you'd rather)", "hope", "fade")
        ans = fx.prompt().strip()
        if _re.fullmatch(r"\d{4}-\d{1,2}-\d{1,2}", ans):
            fx.say("Birth time, if you know it (HH:MM, 24-hour; Enter for noon)", "mystic", "fade")
            t = fx.prompt().strip() or "12:00"
            try:
                natal = astro.natal(ans, t)
            except ValueError:
                return fx.say("That date didn't read right. Try 1990-05-17 and 14:30.", "grief", "fade")
        else:
            sign = ans
    sg = natal["bodies"]["Sun"]["sign"] if natal else astro.sign_from_text(sign)
    if not sg:
        return fx.say("I don't know that sign. Try Aries, Taurus, Gemini...", "grief", "fade")
    fx.say("Today's sky: " + astro.summary(sky), "calm", "type")
    head = f"{astro.GLYPH[sg]}  {sg}, {sky['date']}"
    if not natal:                                   # just a sign: today's horoscope (written once a day, kept)
        text = fx.run_with_animation(lambda: astro.horoscope(sg, reader), 12,
                                     (f"~ {astro.GLYPH[sg]} reading {sg}'s sky ~",)) or astro.horoscope(sg)
        fx.say(head, "channel", "shimmer")
        return fx.say(text, "mystic", "fade")
    facts = astro.natal_text(natal)
    fx.say("The sky you were born under: " + facts, "calm", "type")
    touch = astro.touches(natal, sky)
    if touch:
        fx.say("Where today touches your chart: " + "; ".join(touch) + ".", "channel", "fade")
    words = None
    if reader.online:
        h = astro.houses_for(sg, sky)
        lit = "; ".join(f"{k} in your {n}th house ({astro.HOUSES[n - 1]})" for k, n in h.items()
                        if k in ("Sun", "Moon", "Mercury", "Venus", "Mars"))
        prompt = ("You worked out both of these skies yourself from the planets' real positions (no website). "
                  f"Birth chart: {facts}\nToday's sky: {astro.summary(sky)}\n"
                  f"Where today's planets sit on the birth chart: {'; '.join(touch) or 'nothing exact today'}.\n"
                  f"For {sg} today (whole-sign houses from the Sun): {lit}.\n"
                  "As Veyra, addressed to 'you', in 6 to 8 sentences: first who this birth sky made them "
                  "(Sun, Moon and the most telling planet), then what today's sky is doing to that chart, "
                  "naming at least two real placements, and end with one thing to do today. No square-bracket tags.")
        words = fx.run_with_animation(lambda: reader._ask(prompt, 520, 0.8), 12, (f"~ {astro.GLYPH[sg]} your stars unfold ~",))
        words = _re.sub(r"\[[^\]]*\]", "", words or "").strip() or None
    fx.say(head, "channel", "shimmer")
    if words:
        return fx.say(words, "mystic", "fade")
    b = natal["bodies"]                             # no model awake: read both straight from the skies
    fx.say(f"Sun in {b['Sun']['sign']}: {astro.MEANS['Sun']} lives there. Moon in {b['Moon']['sign']}: "
           f"{astro.MEANS['Moon']} finds its home there. Mars in {b['Mars']['sign']} is how you fight; "
           f"Venus in {b['Venus']['sign']} is how you love.", "mystic", "fade")
    fx.say(astro.horoscope(sg), "mystic", "fade")


class _PlainOut:
    """sys.stdout for a terminal that isn't decoding UTF-8: everything printed goes out as ASCII."""
    def __init__(self, stream):
        self._s = stream

    def write(self, text):
        return self._s.write(art.plain(text))

    def __getattr__(self, name):
        return getattr(self._s, name)


def _terminal_decodes_utf8():
    """Ask the terminal itself: print one two-byte UTF-8 letter and see whether the cursor moved one cell
    (it decodes UTF-8) or two (a Latin-1 window, where every symbol turns into 'â' junk). None: no answer."""
    try:
        import select, termios, tty
        fd, out = sys.stdin.fileno(), sys.stdout.fileno()
        if not (os.isatty(fd) and os.isatty(out)):
            return None
        sys.stdout.flush()
        old = termios.tcgetattr(fd)
    except Exception:
        return None
    resp = b""
    try:
        tty.setcbreak(fd)
        os.write(out, "\r\u00e9\x1b[6n".encode("utf-8"))
        end = time.time() + 0.4
        while time.time() < end and not resp.endswith(b"R"):
            ready, _, _ = select.select([fd], [], [], max(0.0, end - time.time()))
            if not ready:
                break
            resp += os.read(fd, 64)
    except Exception:
        pass
    finally:
        try:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
            termios.tcflush(fd, termios.TCIFLUSH)            # a late answer must not end up as typed input
            os.write(out, b"\r\x1b[2K")
        except Exception:
            pass
    import re
    m = re.search(rb"\x1b\[\d+;(\d+)R", resp)
    return None if not m else int(m.group(1)) == 2


def _check_utf8():
    """Veyra's symbols need a terminal that decodes UTF-8. When the locale or the terminal window isn't
    (an xterm started in Latin-1 shows them as rows of 'â'), she draws in plain ASCII instead and says how
    to get her full art back. TAROT_ASCII=1 forces plain ASCII, TAROT_ASCII=0 never uses it."""
    for st in (sys.stdout, sys.stderr):
        try:
            st.reconfigure(errors="replace")             # an odd character must never crash a reading
        except Exception:
            pass
    force = os.environ.get("TAROT_ASCII")
    if os.name == "nt" or force == "0":
        return
    why = "TAROT_ASCII=1" if force == "1" else ""
    if not why:
        try:
            cs = locale.nl_langinfo(locale.CODESET)
        except Exception:
            cs = "UTF-8"
        if "utf" not in cs.lower().replace("-", ""):
            why = f"the locale is {cs}"
        elif _terminal_decodes_utf8() is False:
            why = "this terminal window is decoding Latin-1, not UTF-8"
    if not why:
        return
    art.BLOCKS, art.ASCII = False, True
    sys.stdout, sys.stderr = _PlainOut(sys.stdout), _PlainOut(sys.stderr)
    if os.environ.get("TAROT_QUIET_LOCALE") != "1" and force != "1":
        print(f"  ! Veyra is drawing in plain ASCII because {why}.\n"
              "    For her full art, run her in a UTF-8 terminal: uxterm (or xterm -u8), or set\n"
              "    LANG=en_US.UTF-8 in /etc/locale.conf and log in again.  (TAROT_QUIET_LOCALE=1 hides this.)\n")
        time.sleep(2.5)


def main():
    try:
        locale.setlocale(locale.LC_ALL, "")
    except locale.Error:                                  # a locale the system never generated: carry on
        for k in ("LC_ALL", "LC_CTYPE", "LANG"):
            os.environ.pop(k, None)
        try:
            locale.setlocale(locale.LC_ALL, "")
        except locale.Error:
            pass
    _check_utf8()
    arg = (sys.argv[1:] or [""])[0]
    if arg == "model":
        _model_mode()
        return
    if arg == "grimoire":
        return curses.wrapper(grimoire_screen)
    if arg == "video":                                 # python3 tarot.py video [session.json]
        import video
        src = sys.argv[2] if len(sys.argv) > 2 else video.latest_session()
        if not src:
            return print("No saved readings yet. Do a reading first.")
        return make_and_share(video.load_session(src))
    if arg == "intro":                                 # python3 tarot.py intro  -> Veyra introduces herself
        import promo
        path = promo.make(_ask, _note, _progress)
        return share_menu(path) if path else None
    if arg in ("wires", "config", "control"):          # python3 tarot.py control -> the control room
        import control
        return curses.wrapper(control.room, "wires" if arg != "control" else "dials")
    if arg in ("stars", "horoscope", "sky", "chart"):  # python3 tarot.py stars [sign] -> chart + horoscope in one
        return stars_menu(Reader(), sys.argv[2] if len(sys.argv) > 2 else None)
    if arg == "psy":                                   # python3 tarot.py psy -> psilocybin mode on/off
        print("Psilocybin mode ON. Psyche engaged: dissociate() is running." if psyche.toggle() else "Psilocybin mode off.")
        return
    if arg == "share":                                 # python3 tarot.py share [video.mp4]
        import video
        vids = sorted(video.VIDEOS.glob("*.mp4")) if video.VIDEOS.exists() else []
        src = sys.argv[2] if len(sys.argv) > 2 else (vids[-1] if vids else None)
        if not src:
            return print("No videos yet. Make one with: python3 tarot.py video")
        return share_menu(src)
    fx.banner("✦   V   E   Y   R   A   ✦", "sheen")
    reader = Reader()
    ready = getattr(reader, "brain_ready", None)       # no opening animation: just wait for the model
    if ready and not ready.is_set():
        fx.shimmer_until("Veyra wakes...", ready.is_set)
    if reader.online:
        ok, why = fx.run_with_animation(reader.check, 10, ("~ Veyra wakes ~",)) or (False, "")
    portrait(reader.label)
    try:                                               # she reads the sky herself, once a day
        import astro
        fx.say("I read the sky myself tonight: " + astro.summary(short=True) + ".", "sheen", "shimmer")
    except Exception:
        pass
    offer_model(reader)
    if arg == "read":
        reading(reader)
    elif arg == "promo":                                # python3 tarot.py promo -> a new promo reel
        promo_video(reader)
    elif arg in ("live", "fall"):
        live_reading(reader)
    else:
        while True:
            fx.say("1) Begin a reading   2) Open the grimoire   3) Let Veyra study   4) Leave   "
                   "5) Make a video of your last reading   6) Live Reading   7) Switch local model   "
                   f"8) Psilocybin mode [{'ON' if psyche.active() else 'off'}]   9) Control room (Ctrl+W anywhere)   "
                   "10) Your stars (star chart + today's horoscope)   11) Make a promo video", "hope", "type")
            c = fx.prompt()
            if c == "1":
                reading(reader)
            elif c == "2":
                curses.wrapper(grimoire_screen)
            elif c == "3":
                if not reader.online:
                    fx.say("Study needs a model. Run: bash setup_local.sh", "grief", "type")
                else:
                    t = reader.study_async(int(os.environ.get("TAROT_STUDY", "3")))
                    fx.run_with_animation(lambda: t.join(), 20, ("~ Veyra studies in the quiet ~",))
                    fx.say("Her notes are saved to memory.json.", "hope", "fade")
            elif c in ("11", "12"):
                promo_video(reader)
            elif c == "10":
                stars_menu(reader)
            elif c in ("4", "q", "quit", "exit"):
                break
            elif c == "6":
                live_reading(reader)
            elif c == "8":
                if psyche.toggle():
                    fx.banner("~ psyche engaged · dissociate() online ~", "mystic", 30)
                else:
                    fx.say("The colours settle. Psilocybin mode is off.", "calm", "fade")
            elif c == "9":
                import control
                curses.wrapper(control.room)
            elif c == "7":
                if _model_mode():
                    break
            elif c == "5":
                import video
                src = video.latest_session()
                if src:
                    make_and_share(video.load_session(src))
                else:
                    fx.say("There is no saved reading yet. Begin one first.", "calm", "fade")
            else:
                continue
            fx.say("Another, or are we done?", "calm", "fade")
    if any(t.is_alive() for t in getattr(reader, "_bg", [])):
        fx.run_with_animation(lambda: reader.settle(120), 10,
                              ("~ Veyra finishes her notes (Ctrl-C to skip) ~", "~ the ink dries ~"))
    fx.banner("The cards are gathered with gratitude.  ✦", "hope")


if __name__ == "__main__":
    _git_sync("pull", "--rebase", "--autostash")
    try:
        main()
    except KeyboardInterrupt:
        print("\x1b[0m\n  The candle is snuffed. Until next time.")
    finally:
        _sync_after_session()
