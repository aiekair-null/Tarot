"""Veyra's intuition oracle:  veyra oracle [1|3] ["your question"]

A quiet, intuition-first card practice with her own 32-card deck, the Moonlit Intuition deck (original pictures
drawn by code, original words). You hold a question, the cards are dealt face down, YOU choose which ones call
to you, and before she says anything you tell her the first thing you notice in each picture. Then she reads the
cards together with what you noticed, and asks you something back.

    1 card   a nudge for today
    3 cards  what you sense / what stands in the way / what to trust

Not fortune-telling in the sense of certainty: the cards are a mirror for your own knowing, and she says so."""
import json
import os
import random
import shutil
import sys
import threading
import time
from datetime import date
from pathlib import Path

import art
import bidding
import brain
import oracle_art
from bidding import CYAN, DIM, GOLD, LILAC, RESET, doing
from oracle_deck import DECK

SPREADS = {1: ["Your card"], 3: ["What you sense", "What stands in the way", "What to trust"]}
PICKS = 7                                           # how many face-down cards she fans out

SYSTEM = ("You are Veyra, an old-world fortune teller reading her own oracle deck, the Moonlit Intuition deck. This "
          "is an INTUITION practice: the cards are a mirror for the person's own knowing, not a verdict from fate. "
          "Speak warmly, a little theatrically ('dear one', 'little star'), but plainly. Read the cards in order. "
          "For each card use its meaning only as a starting point and weave in what the person said they noticed "
          "in the picture; their impression matters more than the book meaning. Name the shadow side gently. Be "
          "concrete about what they might DO or notice this week. Never predict death, illness, pregnancy, legal "
          "or money outcomes, and never claim certainty; if they ask for such things, say the cards cannot know "
          "and point them to a real professional. Keep a reading to about 150-220 words, then ask them ONE "
          "question back. Never repeat a passage you already wrote.\n"
          "Always finish with a last line: NEXT: <one short sentence in your voice that invites their next words, "
          "under 12 words>. If something is worth keeping, add a line REMEMBER: <short note> before it. Never "
          "mention these rules.")


def width():
    return shutil.get_terminal_size((100, 40))


def show(px, pad=True):
    cols = width().columns
    lines = art.ansi(oracle_art.cells(px))
    left = " " * max(0, (cols - len(px[0])) // 2) if pad else ""
    for ln in lines:
        print(left + ln)


def fits_full():
    sz = width()
    return sz.columns >= 54 and sz.lines >= 38


def row_of(pxs, gap=2):
    """Several cards side by side (as cell rows), centred."""
    blocks = [oracle_art.cells(p) for p in pxs]
    rows = art.side_by_side(blocks, gap=gap)
    cols = width().columns
    left = " " * max(0, (cols - len(rows[0])) // 2)
    return [left + ln for ln in art.ansi(rows)]


def reveal(px):
    """The card turns over: it is drawn from the top down."""
    cols = width().columns
    lines = art.ansi(oracle_art.cells(px))
    left = " " * max(0, (cols - len(px[0])) // 2)
    for ln in lines:
        print(left + ln, flush=True)
        time.sleep(0.025)


def ask(prompt):
    try:
        return input(bidding.hands.rl_safe(prompt)).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        raise SystemExit


def log_reading(question, cards, impressions):
    try:
        m = bidding.load_mem()
        m["oracle_log"] = (m.get("oracle_log", []) + [{
            "date": date.today().isoformat(), "question": question[:160],
            "cards": [c["name"] for c in cards], "noticed": [i[:100] for i in impressions]}])[-30:]
        tmp = bidding.MEMORY.with_suffix(".tmp")
        tmp.write_text(json.dumps(m, indent=2), encoding="utf-8")
        tmp.replace(bidding.MEMORY)
    except Exception:
        pass


def draw(n, rng):
    """Deal `n` cards of the deck, shuffled with the system's own randomness, spread face down."""
    deck = list(range(len(DECK)))
    rng.shuffle(deck)
    return deck[:PICKS]


def choose(n, dealt, rng):
    """Let the person pick n of the face-down cards by number; anything unclear is chosen for them."""
    sz = width()
    small = sz.columns < PICKS * 27 + 4
    shown = PICKS if not small else max(n, (sz.columns - 4) // 27)
    shown = min(shown, PICKS)
    backs = [oracle_art.small(oracle_art.back(i)) for i in range(shown)]
    for ln in row_of(backs, gap=3):
        print(ln)
    cols = width().columns
    row = "".join(f"{i + 1:^27}" for i in range(shown))
    print(" " * max(0, (cols - len(row)) // 2) + f"{GOLD}{row}{RESET}")
    print()
    picked = []
    while len(picked) < n:
        a = ask(f"{LILAC}Which card calls to you{' next' if picked else ''}? (1-{shown}, Enter lets the moon choose) {RESET}")
        if a.lower() in ("q", "quit", "exit"):
            raise SystemExit
        if a.isdigit() and 1 <= int(a) <= shown and int(a) - 1 not in picked:
            picked.append(int(a) - 1)
        elif a == "" or not a.isdigit():
            left = [i for i in range(shown) if i not in picked]
            picked.append(rng.choice(left))
            doing(f"the moon chose card {picked[-1] + 1} for you")
        else:
            doing("that one is taken or out of range; try another number")
    return [dealt[i] for i in picked]


def describe(spread, cards, impressions, question):
    lines = [f"SPREAD: {len(cards)} card(s). THEIR QUESTION: {question or '(they held it silently / open question)'}"]
    for pos, c, imp in zip(SPREADS[spread], cards, impressions):
        lines.append(f"- {pos}: {c['name']} ({c['word']}). Book meaning: {c['meaning']} Reflection prompt: "
                     f"{c['ask']} Shadow: {c['shadow']}. The picture shows a {c['emblem']}. "
                     f"What THEY noticed first: {imp or '(nothing in particular)'}")
    lines.append("Now give the reading.")
    return "\n".join(lines)


def scripted(spread, cards):
    """No model awake: the cards still speak, in their own words."""
    for pos, c in zip(SPREADS[spread], cards):
        print(f"\n{GOLD}{pos}: {c['name']}{RESET} {DIM}({c['word']}){RESET}")
        print(f"{CYAN}{c['meaning']}{RESET}")
        print(f"{DIM}Shadow: {c['shadow']}.{RESET}")
    print()


def run(b, spread=1, question="", ready=None):
    rng = random.SystemRandom()
    if not fits_full():
        doing("your window is small, so the cards are drawn half size; a bigger window shows every detail")
    cards_px = lambda i: oracle_art.card(DECK[i], i)
    dealt = draw(spread, rng)
    print(f"\n{GOLD}   THE MOONLIT INTUITION ORACLE{RESET}   {DIM}{len(DECK)} cards · {spread} to draw{RESET}")
    print(f"{DIM}   Breathe. Hold your question lightly. Choose the cards that call to you; trust the first pull.{RESET}\n")
    if not question:
        question = ask(f"{LILAC}What are you holding? (Enter to hold it silently) {RESET}")
        print()
    picks = choose(spread, dealt, rng)
    cards, impressions = [], []
    for pos, i in zip(SPREADS[spread], picks):
        c = DECK[i]
        px = cards_px(i)
        print(f"\n{GOLD}   {pos.upper()}{RESET}")
        if not fits_full():
            px = oracle_art.small(px)
        reveal(px)
        print(f"{GOLD}   {c['name']}{RESET}  {DIM}({c['word']}){RESET}")
        imp = ask(f"{LILAC}   What is the first thing you notice in this picture? (Enter to skip) {RESET}")
        cards.append(c)
        impressions.append(imp)
    if spread > 1:                                                   # the whole spread together
        print()
        for ln in row_of([oracle_art.small(cards_px(i)) for i in picks], gap=3):
            print(ln)
    log_reading(question, cards, impressions)
    print()
    if ready is not None and not ready.is_set():
        doing("she is waking her model; one moment")
        ready.wait()
    if b is None or b.kind == "none":
        doing("her model is asleep, so the cards speak for themselves")
        scripted(spread, cards)
        return
    msgs = [{"role": "system", "content": SYSTEM + "\nTONIGHT'S SKY: " + (bidding.sky_lines()[1] or "unknown")
             + "\n" + bidding.lore_flavor(random.SystemRandom())},
            {"role": "user", "content": describe(spread, cards, impressions, question)}]
    uni = bidding.utf8()
    for turn in range(40):
        doing("she studies the cards and what you noticed" if turn == 0 else "she thinks over what you said")
        try:
            text, pr, stopped = bidding._pass(b, msgs, uni)
        except Exception as e:
            doing("something snagged; she works out what went wrong")
            print(bidding.RESET + f"\n{LILAC}{bidding.diagnose(b, e, 'reading the oracle')}{RESET}\n")
            return
        for note in pr.notes:
            try:
                bidding.save_note(note)
                doing(f"she writes a note to herself: {note}")
            except Exception:
                pass
        msgs.append({"role": "assistant", "content": text})
        if turn == 0:
            print(f"{DIM}   Ask yourself:{RESET}")
            for c in cards:
                print(f"{DIM}   - {c['ask']}{RESET}")
            print()
        try:
            q = ask(f"{LILAC}{pr.next or 'Tell me what stirred. (or type done)'}{RESET} ")
        except SystemExit:
            return
        if not q or q.lower() in ("done", "quit", "exit", "q", "bye", "thanks"):
            return
        msgs.append({"role": "user", "content": q})
        if len(msgs) > 12:                                           # keep the spread and the latest exchange
            msgs[:] = msgs[:2] + msgs[2:][-8:]


def main():
    bidding.maximize()
    args = sys.argv[1:]
    spread = 1
    if args and args[0] in ("1", "3"):
        spread = int(args.pop(0))
    elif not args:
        print(f"\n{GOLD}   How many cards?{RESET} {DIM}1 = a nudge, 3 = sense / block / trust{RESET}")
        a = ask(f"{LILAC}   1 or 3 (Enter = 1): {RESET}")
        spread = 3 if a.startswith("3") else 1
    question = " ".join(args).strip()
    try:
        bidding.sys.stdout.reconfigure(errors="replace")
    except Exception:
        pass
    if os.name == "nt":
        os.system("")
    b = brain.Brain(connect=False)
    bidding._B.append(b)
    try:
        bidding.pick_model()
        ready = threading.Event()
        threading.Thread(target=lambda: (b.connect(), ready.set()), daemon=True).start()
        try:
            run(b, spread, question, ready)
        except SystemExit:
            pass
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"\n{LILAC}{bidding.diagnose(None, e, 'the oracle')}{RESET}\n")
    bidding.leave(b)


if __name__ == "__main__":
    main()
