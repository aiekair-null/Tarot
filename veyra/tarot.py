#!/usr/bin/env python3
"""Veyra: terminal tarot in 8-bit. Black table, neon blues and violets, pixel cards, a reader
who thinks with a free model running on your own machine. Needs a 256-color terminal, 80x24+.

  python tarot.py            menu: reading, grimoire, study
  python tarot.py read       straight into a reading
  python tarot.py grimoire   browse every card and every position meaning"""
import curses, locale, math, os, random, sys, textwrap, time
import art, fx, brain
from agent import Reader
from cards import build_deck, DECK
from spreads import SPREADS
from knowledge import card_profile, position_meaning, detect_domains
import questions as Q

SYS = random.SystemRandom()
ENTER = (10, 13, curses.KEY_ENTER)
BW, BH = 22, 15          # big card
MW, MH = 11, 5           # mini card (Celtic table)
PW, PH = 9, 5            # pile card (cutting)


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


class UI:
    def __init__(self, scr, plan=None):
        self.scr = scr
        self.plan = plan or {"intro": "calm", "wash": "storm", "cut": "mystic", "reveal": "dread", "reading": "mystic"}
        self.mood, self.pairs, self.t0, self.job = self.plan["intro"], {}, time.time(), None
        scr.keypad(True)
        scr.timeout(70)          # getch returns -1 every 70ms so animations keep moving
        try:
            curses.curs_set(0)
        except curses.error:
            pass
        curses.start_color()
        self.big = curses.COLORS >= 256
        scr.bkgd(" ", self.attr(153))
        self.h, self.w = scr.getmaxyx()

    # ---- color ---------------------------------------------------------------------
    def _c(self, idx):
        if self.big:
            return idx
        r, g, b = xterm_rgb(idx)
        return min(range(8), key=lambda k: sum((a - c) ** 2 for a, c in zip(xterm_rgb(k), (r, g, b))))

    def attr(self, fg, bg=16, bold=False):
        key = (self._c(fg), self._c(bg))
        if key not in self.pairs:
            n = len(self.pairs) + 1
            if n >= curses.COLOR_PAIRS:
                return curses.A_BOLD if bold else 0
            try:
                curses.init_pair(n, *key)
            except (curses.error, ValueError, OverflowError):
                return 0
            self.pairs[key] = n
        return curses.color_pair(self.pairs[key]) | (curses.A_BOLD if bold else 0)

    @property
    def edge(self):
        return fx.idx_at(fx.pal(self.mood), (time.time() - self.t0) * 0.35)

    # ---- drawing -------------------------------------------------------------------
    def put(self, y, x, s, a=None):
        if y < 0 or y >= self.h or x >= self.w:
            return
        if x < 0:
            s, x = s[-x:], 0
        s = s[: self.w - x - (1 if y == self.h - 1 else 0)]
        if s:
            try:
                self.scr.addstr(y, x, s, self.attr(153) if a is None else a)
            except curses.error:
                pass

    def text(self, y, x, s, fg=153, bold=False):
        self.put(y, x, s, self.attr(fg, 16, bold))

    def center(self, y, s, fg=153, bold=False):
        self.text(y, (self.w - len(s)) // 2, s, fg, bold)

    def cells(self, y, x, rows, xcrop=None):
        for j, row in enumerate(rows):
            r = row[xcrop[0]:xcrop[1]] if xcrop else row
            for i, (ch, fg, bg) in enumerate(r):
                if ch == " " and bg == 16:
                    continue
                self.put(y + j, x + i, ch, self.attr(fg, bg))

    def glow(self, y, x, s, phase=None, mood=None):
        p = fx.pal(mood or self.mood)[3:]          # bright half only: always legible
        ph = (time.time() - self.t0) * 0.8 if phase is None else phase
        for i, ch in enumerate(s):
            if ch != " ":
                self.put(y, x + i, ch, self.attr(fx.idx_at(p, ph + i * 0.04), 16, True))

    def gcenter(self, y, s, phase=None, mood=None):
        self.glow(y, (self.w - len(s)) // 2, s, phase, mood)

    def stars(self, n=30, seed=7, mood=None):
        """An 8-bit starfield that twinkles in place."""
        rng, p, t = random.Random(seed), fx.pal(mood or self.mood), time.time() - self.t0
        for i in range(n):
            y, x = rng.randrange(self.h), rng.randrange(self.w - 1)
            k = (math.sin(t * (1 + i % 5) * 0.9 + i) + 1) / 2
            self.put(y, x, "·+*✦"[int(k * 3.99)], self.attr(p[int(k * (len(p) - 1))]))

    def veyra(self, y, x, speed=1.0):
        t = (time.time() - self.t0) * speed
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
            s, c = "✒ gathering threads " + "◐◓◑◒"[int(time.time() * 4) % 4], 98
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
        curses.napms(max(1, int(ms * (0.05 if fx.FAST else 1))))

    # ---- phases ----------------------------------------------------------------------
    def intro(self, label=""):
        lines = ["Settle. Lay the cloth. Let the room go quiet.", "Breathe in for four, out for six.",
                 "Three times.", "Hold your question lightly, but hold it.", "The deck is waiting to be washed."]
        vx = max(1, self.w // 2 - 36)
        tx = vx + 30

        def render():
            self.scr.erase()
            self.stars(40)
            self.veyra(max(0, self.h // 2 - 8), vx)
            self.title(max(0, self.h // 2 - 8), tx + 2)
            for i, s in enumerate(lines):
                self.glow(self.h // 2 - 3 + i * 2, tx, s, (time.time() - self.t0) * 0.6 + i * 0.3)
            if label:
                self.text(self.h - 2, 1, f"mind: {label}"[: self.w - 2], 60)
            self.footer("press Enter")
        self.wait_enter(render)

    def hold_questions(self, qs):
        tx = 30

        def render():
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
            self.footer("press Enter")
        self.wait_enter(render)

    def wash(self, n=78, frames=100):
        cy, cx = self.h // 2, self.w // 2
        rx, ry = min(cx - 6, 32), min(cy - 3, 9)
        cards = [(random.uniform(0, 6.28), random.uniform(0.3, 1.0), random.choice([-1, 1])) for _ in range(n)]
        p = fx.pal(self.mood)
        for f in range(frames):
            self.scr.erase()
            self.stars(25)
            self.gcenter(1, "~ washing the cards ~")
            for a, r, d in cards:
                t = a + d * f * 0.07 * (1.3 - r * 0.5)
                c = fx.idx_at(p, r + f * 0.01)
                self.put(cy + int(math.sin(t) * ry * r), cx + int(math.cos(t) * rx * r), "▐█▌", self.attr(c))
            self.scr.refresh()
            self.nap(35)

    def stack(self, y, x, count, label=True, hl=False):
        layers = min(4, max(1, count // 12 + 1)) if count else 0
        for i in reversed(range(layers)):
            rows = art.back_cells(PW, PH, int(time.time() * 3) if hl and i == 0 else 0)
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

    def reveal(self, key, spread, domain="inner"):
        pos = SPREADS[key]["positions"]
        n = len(spread)
        if key == "three":
            top = max(2, (self.h - BH - 6) // 2 + 1)
            lay = [(top, self.w // 2 + (k - 1) * (BW + 3) - BW // 2) for k in range(3)]

            def scene(upto, flip=None, msg=""):
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
        else:
            ox, oy = max(1, (self.w - 76) // 2), 1
            cross = {5: (1, 0), 4: (0, 1), 1: (1, 1), 6: (2, 1), 3: (1, 2)}      # card: (column, row)
            at = {c: (oy + r * (MH + 1), ox + col * (MW + 1)) for c, (col, r) in cross.items()}
            at[2] = at[1]                                                         # crosses card 1
            for c, row in zip((10, 9, 8, 7), range(4)):                           # the staff, top to bottom
                at[c] = (row * (MH + 1), ox + 3 * (MW + 1) + 2)
            lay = [at[i] for i in range(1, 11)]
            zx = ox + 4 * (MW + 1) + 5

            def scene(upto, flip=None, msg=""):
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

        for i in range(n):
            self.wait_enter(lambda i=i: scene(i, None, "Enter: turn the next card"))
            for k in range(9):
                scene(i, (i, k))
                self.scr.refresh()
                self.nap(45)
        self.wait_enter(lambda: scene(n, None, "Enter: hear the reading"))

    # ---- channeling ------------------------------------------------------------------------
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
        frame = int((time.time() - self.t0) * 6)
        rows = art.halfblock(art.glow_halo(art.candle_pixels(j.progress(), frame)))
        self.cells(y, x, rows)
        pct = f"{int(j.progress() * 100)}%"
        self.text(y + len(rows), x + (10 - len(pct)) // 2, pct, 220, True)

    def scene_orbit(self, spread, cx):
        """The drawn cards circle Veyra; cards behind her pass behind, cards in front pass in front."""
        t = time.time() - self.t0
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
            t = time.time() - self.t0
            for i in range(40):
                a, r = t * 1.5 + i * 0.5, 1 + i * 0.25
                self.put(self.h // 2 + int(math.sin(a) * r * 0.45), x + 20 + int(math.cos(a) * r), fx.GLYPHS[i % len(fx.GLYPHS)],
                         self.attr(fx.idx_at(fx.pal("channel"), i * 0.05 + t * 0.3)))
            self.text(self.h - 3, x, "the threads of your question are gathering", 60)
            return
        bucket = int(time.time() * 3)
        for j, ln in enumerate(lines):
            shown = "".join(c if c == " " or (hash((j, i, bucket // 2)) % 100) < 22 else random.choice(fx.GLYPHS)
                            for i, c in enumerate(ln))
            self.glow(6 + j, x, shown, (time.time() - self.t0) * 0.5 + j * 0.2, "channel")

    def waiting_room(self, spread):
        """Cover the wait with visions until the reading is written, then let the querent choose
        the moment: 'press Enter when you are ready'."""
        scenes, si, since = ["orbit", "contemplate", "whispers"], 0, time.time()
        focus = SYS.choice([c for c in DECK if c not in {x for x, _ in spread}])
        cx_area = self.w - 16
        while True:
            j = self.job
            self.scr.erase()
            if j.done:
                self.stars(60, int(time.time() * 2), "hope")
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
                if time.time() - since > 12:
                    si, since = (si + 1) % len(scenes), time.time()
                    if scenes[si] == "contemplate":
                        focus = SYS.choice(DECK)
            self.scr.refresh()
            k = self.scr.getch()
            if j.done and k in ENTER:
                return
            if k == ord("n"):
                si, since = (si + 1) % len(scenes), time.time()
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


def _sized(scr):
    h, w = scr.getmaxyx()
    if h < 24 or w < 80:
        raise SystemExit(f"Please enlarge the terminal to at least 80x24 (it is {w}x{h}).")


WAIT_LIMIT = int(os.environ.get("TAROT_WAIT_LIMIT", "20"))   # seconds of writing left before the waiting room


def ritual(scr, key, spirit_qs, reader, ctx, plan, domain, start):
    _sized(scr)
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


def grimoire_screen(scr):
    _sized(scr)
    UI(scr).grimoire()


# ===================================================================== plain-terminal parts
def portrait(label=""):
    print()
    rows = art.side_by_side([art.veyra_cells(), art.halfblock(art.text_pixels("VEYRA"))], 4)
    fx.print_cells(rows, None)
    if label:
        fx.show(f"mind: {label}".center(min(78, os.get_terminal_size().columns - 4)), "calm")
    print()


def show_table(key, spread):
    """The laid cards as pixel art, printed above the reading."""
    pos = SPREADS[key]["positions"]
    if key == "three":
        blocks = [art.card_cells(c, r, BW, BH) for c, r in spread]
        labels = "".join(p[0].upper().center(BW + 2) for p in pos)
        fx.show(labels, "hope", max(0, (os.get_terminal_size().columns - len(labels)) // 2))
        fx.print_cells(art.side_by_side(blocks, 2), None)
    else:
        for half in (range(0, 5), range(5, 10)):
            fx.show("".join(f"{i + 1}. {pos[i][0]}"[:MW + 2].ljust(MW + 2) for i in half), "hope", 2)
            fx.print_cells(art.side_by_side([art.mini_cells(*spread[i]) for i in half], 2), 2)
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
    except ImportError:
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


def reading(reader):
    fx.say("What do you bring to the cards today?", "mystic", "fade")
    question = ask() or "What do I need to see?"
    fx.say("A few things to help me feel you out. Press Enter to skip any.", "calm", "fade")
    prof = {}
    for label, k in (("Your age?", "age"), ("Your career, or what you do?", "career"), ("Your sex or gender?", "sex/gender")):
        fx.say(label, "calm", "type")
        v = ask()
        if v:
            prof[k] = v
    profile = ", ".join(f"{k}: {v}" for k, v in prof.items()) or "(not shared)"
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
    fx.say("How shall the cards be laid?", "calm", "fade")
    keys = list(SPREADS)
    for i, k in enumerate(keys, 1):
        fx.say(f"{i}) {SPREADS[k]['name']}", "hope", "type")
    fx.say(f"{len(keys) + 1}) Let Veyra feel it out", "hope", "type")
    pick = fx.prompt()
    if not pick.isdigit() or not 1 <= int(pick) <= len(keys):
        key, why = reader.choose_spread(question, profile, qa)
        fx.say(f"Veyra lays the {SPREADS[key]['name']}. {why}", plan["intro"], "shimmer")
    else:
        key = keys[int(pick) - 1]
    ctx = f"Question: {question}. Spirit questions: {'; '.join(spirit_qs)}."
    reader.warm(question, profile, qa, spirit_qs)    # pre-load the question into a local model
    fx.say("Press Enter to begin the ritual.", "mystic", "pulse")
    fx.prompt()
    start = lambda sp, ch: reader.start_reading(question, profile, qa, spirit_qs, key, sp, ch)
    spread, channeled, job = curses.wrapper(ritual, key, spirit_qs, reader, ctx, plan, domain, start)
    cards = ", ".join(c + (" (reversed)" if r else "") for c, r in spread)
    fx.banner("~ Veyra reads ~", plan["reading"], 20)
    show_table(key, spread)
    done = [0]

    def on_channel():
        if done[0] < 1:
            ansi_channel(reader, ctx + " Cards: " + cards)
            done[0] += 1
    fx.play_stream(job.stream(), plan["reading"], on_channel)
    if done[0] == 0 and SYS.random() < 0.6:
        ansi_channel(reader, ctx + " Cards: " + cards)
    print()
    fx.say("Did this ring true? Tell me what landed and what missed (Enter to skip).", "calm", "fade")
    ans = ask()
    if ans:
        reader.later(reader.feedback, ans)          # she learns in the background
        fx.say("She nods, and writes it down in the margins of her grimoire.", "calm", "fade")


def main():
    locale.setlocale(locale.LC_ALL, "")
    arg = (sys.argv[1:] or [""])[0]
    if arg == "grimoire":
        return curses.wrapper(grimoire_screen)
    fx.banner("✦   V   E   Y   R   A   ✦", "mystic")
    reader = fx.run_with_animation(Reader, 10, ("~ Veyra wakes ~", "~ the candles catch ~")) or Reader()
    if reader.online:
        ok, why = fx.run_with_animation(reader.check, 10, ("~ Veyra wakes ~",)) or (False, "")
    portrait(reader.label)
    offer_model(reader)
    if arg == "read":
        reading(reader)
    else:
        while True:
            fx.say("1) Begin a reading   2) Open the grimoire   3) Let Veyra study   4) Leave", "hope", "type")
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
            elif c in ("4", "q", "quit", "exit"):
                break
            else:
                continue
            fx.say("Another, or are we done?", "calm", "fade")
    if any(t.is_alive() for t in getattr(reader, "_bg", [])):
        fx.run_with_animation(lambda: reader.settle(120), 10,
                              ("~ Veyra finishes her notes (Ctrl-C to skip) ~", "~ the ink dries ~"))
    fx.banner("The cards are gathered with gratitude.  ✦", "hope")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\x1b[0m\n  The candle is snuffed. Until next time.")
