#!/usr/bin/env python3
"""Terminal tarot: black table, neon blues and violets, animated and mood-directed by Veyra.
Needs a 256-color terminal of at least 80x24."""
import curses, os, random, textwrap, threading, time
import fx
import models
from agent import Reader, is_missing
from cards import build_deck
from spreads import SPREADS

CW, CH = 9, 5      # small card
BW, BH = 18, 9     # big (revealed) card
SYS = random.SystemRandom()
ENTER = (10, 13, curses.KEY_ENTER)


class UI:
    def __init__(self, scr, plan):
        self.scr, self.plan, self.mood, self.pairs = scr, plan, plan["intro"], {}
        scr.keypad(True)
        scr.timeout(70)                      # getch returns -1 every 70ms: animations keep moving
        curses.curs_set(0)
        curses.start_color()
        self.big = curses.COLORS >= 256
        self.W, self.D = self.pair(153), self.pair(60)
        self.G = self.HL = self.pair(51) | curses.A_BOLD
        scr.bkgd(" ", self.W)
        self.h, self.w = scr.getmaxyx()

    # ---- color + drawing primitives ------------------------------------
    def pair(self, idx):
        if not self.big:
            idx = (curses.COLOR_BLUE, curses.COLOR_CYAN, curses.COLOR_MAGENTA)[idx % 3]
        if idx not in self.pairs:
            n = len(self.pairs) + 1
            if n >= curses.COLOR_PAIRS:
                return self.W
            curses.init_pair(n, idx, curses.COLOR_BLACK)
            self.pairs[idx] = n
        return curses.color_pair(self.pairs[idx])

    @property
    def P(self):   # card edges slowly drift through the current mood's palette
        return self.pair(fx.idx_at(fx.pal(self.mood), time.time() * 0.35))

    def nap(self, ms):
        curses.napms(max(1, int(ms * (0.05 if fx.FAST else 1))))

    def put(self, y, x, s, a=None):
        if y < 0 or y >= self.h or x >= self.w:
            return
        if x < 0:
            s, x = s[-x:], 0
        s = s[: self.w - x - 1]
        if s:
            try:
                self.scr.addstr(y, x, s, self.W if a is None else a)
            except curses.error:
                pass

    def center(self, y, s, a=None):
        self.put(y, (self.w - len(s)) // 2, s, a)

    def glow(self, y, x, s, phase=None, mood=None):
        p = fx.pal(mood or self.mood)
        ph = time.time() * 0.8 if phase is None else phase
        for i, ch in enumerate(s):
            if ch != " ":
                self.put(y, x + i, ch, self.pair(fx.idx_at(p, ph + i * 0.04)) | curses.A_BOLD)

    def gcenter(self, y, s, phase=None, mood=None):
        self.glow(y, (self.w - len(s)) // 2, s, phase, mood)

    def sparkle(self, n, mood=None):
        p = fx.pal(mood or self.mood)
        for _ in range(n):
            self.put(random.randint(0, self.h - 1), random.randint(0, self.w - 3), random.choice(fx.GLYPHS),
                     self.pair(random.choice(p)))

    def box(self, y, x, w, h, a, back=False):
        self.put(y, x, "┌" + "─" * (w - 2) + "┐", a)
        for r in range(1, h - 1):
            inner = ((("◆ " if (r % 2) else " ◆") * w)[: w - 2]) if back else " " * (w - 2)
            self.put(y + r, x, "│" + inner + "│", a)
        self.put(y + h - 1, x, "└" + "─" * (w - 2) + "┘", a)

    def stack(self, y, x, count, label=True):
        layers = min(4, max(1, count // 12 + 1)) if count else 0
        for i in reversed(range(layers)):
            self.box(y - i, x + i, CW, CH, self.P, back=True)
        if label and count:
            self.put(y + CH, x, f"{count} cards".center(CW + 3), self.D)

    def spots(self, y, piles, sel=None, picked=(), numbers=False):
        for k in range(3):
            x = self.w // 2 + (k - 1) * (CW + 9) - CW // 2
            if piles[k] is None:
                a = self.G if k == sel else self.D
                self.box(y, x, CW, CH, a)
                self.put(y + 2, x + 2, "place", a)
                self.put(y + 3, x + 2, "here", a)
            else:
                if k in picked:
                    self.box(y, x, CW, CH, self.D)
                    self.put(y + 2, x + 2, "taken", self.D)
                else:
                    self.stack(y, x, len(piles[k]), label=False)
                    if k == sel:
                        self.box(y, x, CW, CH, self.G, back=True)
                self.put(y + CH, x, f"{len(piles[k])} cards".center(CW + 3), self.D)
            if numbers:
                self.put(y - 2, x + CW // 2, f"[{k + 1}]", self.G if k == sel else self.W)

    def wait_enter(self, render=None):
        while True:
            if render:
                render()
                self.scr.refresh()
            if self.scr.getch() in ENTER:
                return

    # ---- phases ----------------------------------------------------------
    def intro(self):
        lines = ["Settle. Lay the cloth. Let the room go quiet.", "Breathe in for four, out for six. Three times.",
                 "Hold your question lightly, but hold it.", "The deck is waiting to be washed."]

        def render():
            self.scr.erase()
            for i, s in enumerate(lines):
                self.gcenter(self.h // 2 - 3 + i * 2, s, time.time() * 0.6 + i * 0.3)
            self.center(self.h - 3, "press Enter", self.D)
        self.wait_enter(render)

    def hold_questions(self, qs):
        def render():
            self.scr.erase()
            self.gcenter(2, "Hold these questions for the spirits as the cards are washed")
            for i, q in enumerate(qs):
                for j, ln in enumerate(textwrap.wrap(q, self.w - 12)):
                    self.put(5 + i * 4 + j, 6, ("%d. " % (i + 1) if j == 0 else "   ") + ln, self.W)
            self.center(self.h - 3, "press Enter", self.D)
        self.wait_enter(render)

    def wash(self, n=78, frames=100):
        import math
        cy, cx = self.h // 2, self.w // 2
        rx, ry = min(cx - 6, 30), min(cy - 4, 7)
        cards = [(random.uniform(0, 6.28), random.uniform(0.3, 1.0), random.choice([-1, 1])) for _ in range(n)]
        p = fx.pal(self.mood)
        for f in range(frames):
            self.scr.erase()
            self.gcenter(1, "~ washing the cards ~")
            for a, r, d in cards:
                t = a + d * f * 0.07 * (1.3 - r * 0.5)
                self.put(cy + int(math.sin(t) * ry * r), cx + int(math.cos(t) * rx * r), "▓▓",
                         self.pair(fx.idx_at(p, r + f * 0.01)))
            self.scr.refresh()
            self.nap(35)

    def gather(self, n=78):
        cy, cx = self.h // 2 - CH // 2, self.w // 2 - CW // 2
        for i in range(1, n + 1):
            sx, sy = random.choice([(random.randint(1, self.w - 4), 2), (random.randint(1, self.w - 4), self.h - 2),
                                    (2, random.randint(2, self.h - 2)), (self.w - 4, random.randint(2, self.h - 2))])
            for step in range(1, 4):
                t = step / 3
                self.scr.erase()
                self.gcenter(1, "~ gathering the deck ~")
                self.stack(cy, cx, i - 1)
                if step < 3:
                    self.put(int(sy + (cy + CH // 2 - sy) * t), int(sx + (cx + CW // 2 - sx) * t), "▓▓", self.P)
                self.center(self.h - 2, f"{i} / {n}", self.D)
                self.scr.refresh()
                self.nap(12)

    def draw_cut(self, hand, piles, sel, menu, msg, refresh=True):
        self.scr.erase()
        self.gcenter(1, "you now hold the deck, please cut into three piles")
        self.center(3, msg, self.W)
        self.spots(5, piles, sel)
        if menu is not None:
            self.put(12, self.w // 2 - 15, "[ drop heavy ]", self.G if menu == 0 else self.D)
            self.put(12, self.w // 2 + 1, "[ drop light ]", self.G if menu == 1 else self.D)
        self.stack(17, self.w // 2 - CW // 2, len(hand))
        if refresh:
            self.scr.refresh()

    def slide(self, hand, piles, sel, n):
        x1, y1 = self.w // 2 - CW // 2, 17
        x2, y2 = self.w // 2 + (sel - 1) * (CW + 9) - CW // 2, 5
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
            pct = random.choice([45, 55, 75] if m == 0 else [15, 25, 35])
            n = max(1, min(round(len(hand) * pct / 100), len(hand) - (2 - k)))
            self.slide(hand, piles, sel, n)
            piles[sel], hand = hand[:n], hand[n:]
        last = piles.index(None)
        self.slide(hand, piles, last, len(hand))
        piles[last], hand = hand, []
        self.draw_cut(hand, piles, None, None, "the last of the cards fall into the final space")
        self.nap(1500)
        return piles

    def reassemble(self, piles):
        order, sel = [], 0
        while len(order) < 3:
            left = [i for i in range(3) if i not in order]
            if sel not in left:
                sel = left[0]
            self.scr.erase()
            self.gcenter(1, "please reassemble the deck in any order you like")
            self.center(3, "choose piles with ← → + Enter (or press 1 2 3). First chosen sits on top.", self.W)
            self.spots(7, piles, sel, picked=order, numbers=True)
            self.center(15, "order, top to bottom:  " + (" → ".join(str(i + 1) for i in order) or "..."), self.G)
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

    # ---- the laid spread ---------------------------------------------------
    def face(self, y, x, w, h, card, num=None):
        name, rev = card
        self.box(y, x, w, h, self.P)
        lines = textwrap.wrap(name, w - 4 if h > 5 else w - 2)[:2 if h <= 5 else 4]
        if rev:
            lines += ["", "▼ reversed ▼"] if h > 5 else ["▼ reversed"]
        top = y + 1 + max(0, (h - 2 - len(lines)) // 2)
        for i, ln in enumerate(lines):
            self.put(top + i, x + (w - len(ln)) // 2, ln, self.W)
        if num:
            self.put(y, x + 2, f" {num} ", self.G)

    def reveal(self, key, spread):
        sp, n = SPREADS[key]["positions"], len(spread)
        if key == "three":
            w, h = BW, BH
            lay = [(6, self.w // 2 + (k - 1) * (BW + 4) - BW // 2) for k in range(3)]
        else:
            w, h, ox, oy = 12, CH, 1, 4
            cross = {4: (0, 1), 1: (1, 1), 2: (2, 1), 6: (3, 1), 5: (1, 0), 3: (1, 2)}
            pos = {c: (oy + r * CH, ox + col * (w + 1)) for c, (col, r) in cross.items()}
            for c, row in zip((7, 8, 9, 10), (17, 12, 7, 2)):
                pos[c] = (row, ox + 4 * (w + 1) + 3)
            lay = [pos[i] for i in range(1, 11)]
        numbered = key != "three"

        def scene(upto, flip=None, msg=""):
            self.scr.erase()
            self.gcenter(0 if numbered else 1, "~ the cards are laid ~")
            for k, (y, x) in enumerate(lay):
                if not numbered:
                    self.put(y - 2, x + (w - len(sp[k][0])) // 2, sp[k][0].upper(), self.G)
                if flip and flip[0] == k:
                    wd, up = flip[1], flip[2]
                    if wd >= w and up:
                        self.face(y, x, w, h, spread[k], k + 1 if numbered else None)
                    else:
                        self.box(y, x + (w - wd) // 2, max(wd, 2), h, self.P, back=not up)
                elif k < upto:
                    self.face(y, x, w, h, spread[k], k + 1 if numbered else None)
                else:
                    self.box(y, x, w, h, self.P, back=True)
                    if numbered:
                        self.put(y, x + 2, f" {k + 1} ", self.G)
            if numbered and 1 <= upto <= n:
                self.put(self.h - 2, 1, f"{upto}. {sp[upto - 1][0]}: {sp[upto - 1][1]}"[: self.w - 3], self.G)
            self.put(self.h - 1, 1, msg, self.D)

        frames = [(w, False), (w * 3 // 4, False), (w // 2, False), (w // 4, False), (2, False),
                  (w // 4, True), (w // 2, True), (w * 3 // 4, True), (w, True)]
        for i in range(n):
            self.wait_enter(lambda i=i: scene(i, None, "Enter: turn the next card"))
            for wd, up in frames:
                scene(i, (i, wd, up))
                self.scr.refresh()
                self.nap(45)
        self.wait_enter(lambda: scene(n, None, "Enter: hear the reading"))

    # ---- channeling --------------------------------------------------------
    def channel(self, summon):
        """The veil thins; the querent's timing becomes entropy; a message comes through."""
        ns = [0]

        def veil():
            self.scr.erase()
            self.sparkle(18, "channel")
            self.gcenter(self.h // 2 - 1, "the veil thins...", mood="channel")
            self.gcenter(self.h // 2 + 1, "press Enter when you feel it", mood="mystic")
        while True:
            veil()
            self.scr.refresh()
            if self.scr.getch() in ENTER:
                ns[0] = time.time_ns()
                break
        res = {}

        def work():
            try:
                res["v"] = summon(ns[0])
            except Exception:
                res["v"] = None
        t = threading.Thread(target=work, daemon=True)
        t.start()
        order, k = ["mystic", "storm", "dread", "channel"], 0
        while t.is_alive() or k < 40:
            m = order[(k // 8) % 4]
            self.scr.erase()
            self.sparkle(25, m)
            self.gcenter(self.h // 2 - 2, "~ channeling the spirit realm ~", k * 0.1, m)
            if k >= 20:
                self.gcenter(self.h // 2, "words coming through now...", k * 0.12, m)
            self.scr.refresh()
            self.nap(70)
            k += 1
        out = res.get("v")
        if not out:
            return None
        lines = textwrap.wrap(out["message"], min(60, self.w - 12))
        full = "\n".join(lines)
        for step in range(0, len(full) + 1, max(1, len(full) // 24)):
            self.scr.erase()
            shown = "".join(c if (i < step or c in " \n") else random.choice(fx.GLYPHS) for i, c in enumerate(full))
            for j, ln in enumerate(shown.split("\n")):
                self.gcenter(self.h // 2 - len(lines) // 2 + j, ln, step * 0.05, out["mood"])
            self.scr.refresh()
            self.nap(60)
        self.wait_enter(lambda: (self.scr.erase(), [self.gcenter(self.h // 2 - len(lines) // 2 + j, ln, mood=out["mood"])
                                                   for j, ln in enumerate(lines)],
                                 self.center(self.h - 3, "press Enter", self.D)))
        return out


def ritual(scr, key, spirit_qs, reader, ctx, plan):
    ui = UI(scr, plan)
    if ui.h < 24 or ui.w < 80:
        raise SystemExit("Please enlarge the terminal to at least 80x24.")
    channeled = []

    def event(extra=""):
        out = ui.channel(lambda ns: reader.summon(ctx + extra, ns))
        if out:
            channeled.append(out["message"])
    deck = build_deck()
    random.shuffle(deck)
    ui.mood = plan["intro"]
    ui.intro()
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
    spread = [(deck[i], random.random() < 0.25) for i in range(len(SPREADS[key]["positions"]))]
    ui.mood = plan["reveal"]
    ui.reveal(key, spread)
    if SYS.random() < 0.5:
        event(" Cards: " + ", ".join(c + (" (reversed)" if r else "") for c, r in spread))
    return spread, channeled


def ansi_channel(reader, ctx):
    fx.say("The veil thins. Press Enter when you feel it.", "channel", "fade")
    fx.prompt("channel")
    ns = time.time_ns()
    out = fx.run_with_animation(lambda: reader.summon(ctx, ns))
    if out:
        fx.say(out["message"], out["mood"], "glitch")
        return out["message"]


def choose_model(reader):
    """Pick a model from what the router can serve right now; try providers until one answers."""
    fx.say("Let me see which models your token can reach...", "calm", "fade")
    try:
        items = models.available(reader.token)
    except Exception as e:
        fx.say(f"I couldn't fetch the model list ({str(e)[:80]}). Run: python models.py", "dread", "type")
        return False
    term = ""
    while True:
        shown = models.ranked(items, term)[:15]
        for i, (m, p) in enumerate(shown, 1):
            fx.show(f"{i:>2}) {m}  {models.tags(m, p)}", "storm" if models.flagged(m) else "hope")
        fx.say("Type a number to choose, a word to search (try: abliterated), or Enter to skip.", "calm", "fade")
        ans = fx.prompt()
        if not ans:
            return False
        if ans.isdigit() and 1 <= int(ans) <= len(shown):
            mid, provs = shown[int(ans) - 1]
            for prov in ["auto"] + [p for p in provs if p][:4]:
                reader.set_model(mid, prov, save=False)
                ok, why = reader.check()
                if ok:
                    reader.set_model(mid, prov)
                    fx.say(f"Veyra wakes through {mid}. (saved to model.txt)", "hope", "shimmer")
                    return True
            fx.say(f"That one wouldn't answer: {reader.hint(why)}", "dread", "type")
        else:
            term = ans


def main():
    reader = Reader()
    fx.banner("✦   V   E   Y   R   A   ✦", "mystic")
    ok, why = reader.check()
    if not ok and reader.token and (not reader.model or is_missing(why)):
        if reader.model:
            fx.say(f"The model '{reader.model}' isn't served to your token right now.", "dread", "type")
        ok = choose_model(reader)
    if not ok:
        fx.say("Veyra is offline: " + reader.hint(why) + " The ritual still works; the reading will be basic.", "grief", "type")
    else:
        reader.study_async(int(os.environ.get("TAROT_STUDY", "3")))   # she studies while you talk
    fx.say("What do you bring to the cards today?", "mystic", "fade")
    question = fx.prompt() or "What do I need to see?"
    fx.say("A few things to help me feel you out. Press Enter to skip any.", "calm", "fade")
    prof = {}
    for label, k in (("Your age?", "age"), ("Your career, or what you do?", "career"), ("Your sex or gender?", "sex/gender")):
        fx.say(label, "calm", "type")
        v = fx.prompt()
        if v:
            prof[k] = v
    profile = ", ".join(f"{k}: {v}" for k, v in prof.items()) or "(not shared)"
    qa = []
    while True:
        q = reader.next_question(question, profile, qa)
        if not q:
            break
        fx.say(q["ask"], q["mood"], q["fx"])
        qa.append((q["ask"], fx.prompt()))
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
    fx.say("Press Enter to begin the ritual.", "mystic", "pulse")
    fx.prompt()
    spread, channeled = curses.wrapper(ritual, key, spirit_qs, reader, ctx, plan)
    cards = ", ".join(c + (" (reversed)" if r else "") for c, r in spread)
    fx.banner("~ Veyra reads ~", plan["reading"], 20)
    text = fx.run_with_animation(lambda: reader.read(question, profile, qa, spirit_qs, key, spread, channeled),
                                 30, ("~ the cards are speaking ~", "~ Veyra is listening ~")) or "(no reading came through)"
    done = 0
    for kind, body, mood, f in fx.parse_segments(text):
        if kind == "channel":
            if done < 1:
                ansi_channel(reader, ctx + " Cards: " + cards)
                done += 1
        else:
            fx.say(body, mood or plan["reading"], f or "type")
    if done == 0 and SYS.random() < 0.6:
        ansi_channel(reader, ctx + " Cards: " + cards)
    fx.say("Did this ring true? Tell me what landed and what missed (Enter to skip).", "calm", "fade")
    ans = fx.prompt()
    if ans:
        fx.run_with_animation(lambda: reader.feedback(ans), 12, ("~ Veyra listens and learns ~",))
    study = reader.study_async(int(os.environ.get("TAROT_STUDY", "3")))
    fx.run_with_animation(lambda: study.join(25), 12, ("~ Veyra studies in the quiet ~",))
    fx.banner("The cards are gathered with gratitude.  ✦", "hope")


if __name__ == "__main__":
    main()
