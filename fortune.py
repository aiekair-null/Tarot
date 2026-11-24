"""Fortune Reading (casting items on a big table), Chat with Veyra, and the startup drawings.

She asks which of four groups of items you want. From that group she picks the pieces she feels are
significant today (the sky weighs in, and never the same set twice in a row), they fall on a large
table, and she reads where they landed and how they touch, together with today's sky."""
import curses, math, random, re, shutil, time

import art, fx, items as I, sky

SYS = random.SystemRandom()
ZONES = {"left": "what is leaving or behind you", "right": "what is coming toward you",
         "top": "what is above you: hopes, ideals, the mind", "bottom": "your foundation and roots",
         "center": "the heart of the matter"}


# ---------------------------------------------------------------- choosing and casting
def significance(name, reader, sign_el):
    """How strongly she feels this piece today: the sky's elements, your element, and a little chance."""
    el, planet = I.ITEMS[name][1], I.ITEMS[name][2]
    w = 1.0 + 0.9 * sky.element_effect(el)
    if sign_el == el:
        w += 0.7
    b = (sky.CURRENT.get("sky") or {}).get("basics") or {}
    if b and (el in (sky.element_of(b.get("sun", "Aries")), sky.element_of(b.get("moon", "Aries")))):
        w += 0.4
    if planet.startswith("Moon") and "moon" in b.get("phase", ""):
        w += 0.3
    return max(0.15, w) * (0.6 + SYS.random())


def pick_items(group, reader, sign_el=None, n=6):
    """Six pieces from the group, weighted by significance, never close to the same set as last time."""
    pool = I.GROUPS[group][2]
    last = set((reader.mem.get("last_cast") or {}).get("items", []))
    best = None
    for _ in range(40):
        left, chosen = list(pool), []
        while len(chosen) < n:
            ws = [significance(x, reader, sign_el) for x in left]
            c = SYS.choices(left, ws)[0]
            chosen.append(c)
            left.remove(c)
        if len(set(chosen) & last) <= 3 and set(chosen) != last:
            return chosen
        best = best or chosen
    return best


def cast(names, W, H):
    """Where each piece lands on a W x H table (cells). Returns placements with a turned/upright state."""
    sw, sh = I.N, I.N // 2
    out = []
    for nm in names:
        for _ in range(60):
            x, y = SYS.randint(1, max(1, W - sw - 1)), SYS.randint(1, max(1, H - sh - 1))
            near = [abs(x - o["x"]) < sw - 2 and abs(y - o["y"]) < sh - 2 for o in out]
            if sum(near) <= 1 and (not near or not any(near) or SYS.random() < 0.55):
                break
        out.append({"name": nm, "x": x, "y": y, "turned": SYS.random() < 0.35})
    return out


def interactions(pl, W, H):
    """Plain facts about how the pieces lie: zones, edges, touching, covering, the loner and the heart."""
    sw, sh = I.N, I.N // 2
    for o in pl:
        o["cx"], o["cy"] = o["x"] + sw / 2, o["y"] + sh / 2
        dx, dy = (o["cx"] - W / 2) / (W / 2), (o["cy"] - H / 2) / (H / 2)
        o["zone"] = "center" if math.hypot(dx, dy) < 0.28 else (
            ("right" if dx > 0 else "left") if abs(dx) * 0.9 > abs(dy) else ("bottom" if dy > 0 else "top"))
        o["edge"] = o["x"] <= 2 or o["y"] <= 1 or o["x"] + sw >= W - 2 or o["y"] + sh >= H - 1
    facts = []
    for i, a in enumerate(pl):
        for b in pl[i + 1:]:
            ddx, ddy = abs(a["cx"] - b["cx"]), abs(a["cy"] - b["cy"]) * 2
            if ddx < sw * 0.6 and ddy < sh * 1.2:
                top, under = (a, b) if pl.index(a) > pl.index(b) else (b, a)
                facts.append(f"the {top['name']} lies over the {under['name']}")
            elif ddx < sw * 1.15 and ddy < sh * 1.9:
                facts.append(f"the {a['name']} touches the {b['name']}")
    dist = lambda a: sum(math.hypot(a["cx"] - b["cx"], (a["cy"] - b["cy"]) * 2) for b in pl if b is not a)
    loner = max(pl, key=dist)
    heart = min(pl, key=lambda a: math.hypot(a["cx"] - W / 2, (a["cy"] - H / 2) * 2))
    return facts, loner, heart


def compose(pl, W, H, seed=3):
    """The table as terminal cells: dark cloth with stars, a border, and the pieces where they fell."""
    rng = random.Random(seed)
    grid = [[(" ", 16, 16) for _ in range(W)] for _ in range(H)]
    for _ in range(W * H // 22):
        grid[rng.randrange(H)][rng.randrange(W)] = (rng.choice("·+*"), rng.choice((60, 61, 67, 103, 140)), 16)
    for o in pl:
        rows = art.halfblock(_flip(I.sprite(o["name"]), o["turned"]))
        for j, row in enumerate(rows):
            for i, cell in enumerate(row):
                if cell[0] == " " and cell[2] == 16:
                    continue
                if 0 <= o["y"] + j < H and 0 <= o["x"] + i < W:
                    grid[o["y"] + j][o["x"] + i] = cell
    for x in range(W):
        grid[0][x] = ("─", 54, 16)
        grid[H - 1][x] = ("─", 54, 16)
    for y in range(H):
        grid[y][0] = ("│", 54, 16)
        grid[y][W - 1] = ("│", 54, 16)
    grid[0][0], grid[0][W - 1], grid[H - 1][0], grid[H - 1][W - 1] = ("╭", 54, 16), ("╮", 54, 16), ("╰", 54, 16), ("╯", 54, 16)
    return grid


def _flip(px, turned):
    return [row[::-1] for row in px] if turned else px


def table_screen(scr, names, reader):
    """The large table: pieces fall onto it one by one, then rest while you look."""
    import tarot
    scr = tarot._sized(scr)
    ui = tarot.UI(scr)
    ui.mood = sky.CURRENT.get("mood", "mystic")
    W, H = ui.w - 2, ui.h - 4
    pl = cast(names, W, H)
    facts, loner, heart = interactions(pl, W, H)
    t0 = time.monotonic()
    done = False
    while True:
        t = time.monotonic() - t0
        scr.erase()
        ui.gcenter(0, "~ the cast ~", t * 0.4, ui.mood)
        for x in range(W):                                    # the table: border and star-dust
            ui.put(1, 1 + x, "─", ui.attr(54)); ui.put(H + 2, 1 + x, "─", ui.attr(54))
        for y in range(H):
            ui.put(2 + y, 0, "│", ui.attr(54)); ui.put(2 + y, W + 1, "│", ui.attr(54))
        ui.stars(int(W * H / 26), mood=ui.mood)
        for k, o in enumerate(pl):
            p = (t - k * 0.5) / 0.55
            if p <= 0:
                continue
            drop = 0 if p >= 1 else int((1 - p) ** 2 * (H + 4))
            bounce = int(1.5 * abs(math.sin((p - 1) * 6)) * max(0, 1.4 - p)) if 1 <= p < 1.4 else 0
            rows = art.halfblock(_flip(I.sprite(o["name"]), o["turned"]))
            ui.cells(2 + o["y"] - drop - bounce, 1 + o["x"], rows)
        landed = t > len(pl) * 0.5 + 0.7
        ui.center(ui.h - 2, ("the pieces have settled" if landed else "they fall...")[: ui.w - 2], 141)
        if landed:
            ui.footer("press Enter")
            done = True
        scr.refresh()
        k = scr.getch()
        if done and k in (10, 13, curses.KEY_ENTER):
            return pl, W, H


def describe(o, loner, heart):
    nm = o["name"]
    _, el, planet, light, shadow, line = I.ITEMS[nm]
    state = f"turned over, so its shadow side speaks: {shadow}" if o["turned"] else f"upright, so its light speaks: {light}"
    where = ZONES[o["zone"]]
    extra = " It lies right at the edge of the table: it is leaving or not yet arrived." if o["edge"] else ""
    return (f"the {nm} ({el}, {planet}) — {line}. It fell {state}. It lies in the zone of {where}.{extra}"
            + (" It lies apart from the rest." if o is loner else "") + (" It sits at the heart of the cast." if o is heart else ""))


def narrate(reader, prompt, fallback, mood, title="~ Veyra reads the cast ~"):
    text = None
    if reader.online:
        text = fx.run_with_animation(lambda: reader.brain.chat(reader._msgs(prompt), 650, 0.8), 25, (title,))
    text = re.sub(r"\[[^\]]*\]", "", text or "").replace("**", "").strip()
    if len(text) < 120:
        text = fallback
    for para in [p for p in text.split("\n") if p.strip()]:
        fx.say(para, mood, "fade")
    return text


# ---------------------------------------------------------------- the whole reading
def fortune_reading(reader):
    import tarot
    cur = sky.CURRENT.get("sky")
    mood = sky.CURRENT.get("mood", "mystic")
    if cur:
        fx.say(f"Before we begin: {cur['summary']}", mood, "fade")
        if cur.get("events"):
            fx.say("What the sky is doing now and in the next few days: " + "; ".join(cur["events"]) + ".", mood, "fade")
    fx.say("A fortune reading. I keep four groups of small things. Which will you have?", "hope", "type")
    for g, (name, about, its) in I.GROUPS.items():
        fx.say(f"{g}) {name} — {about}", "calm", "fade")
    c = ""
    while c not in ("1", "2", "3", "4"):
        c = fx.prompt("hope")
        if c.lower() in ("q", "quit", "back"):
            return
    group = int(c)
    month, sign, element, auto_index = tarot.choose_zodiac(reader)
    names = pick_items(group, reader, element)
    fx.say(f"From {I.GROUPS[group][0]} I choose what feels significant today. I will not give you the same set twice in a row.",
           mood, "fade")
    pl, W, H = curses.wrapper(table_screen, names, reader)
    facts, loner, heart = interactions(pl, W, H)
    reader.mem["last_cast"] = {"group": group, "items": names}
    try:
        reader._save()
    except Exception:
        pass
    print()
    lines = "\n".join("- " + describe(o, loner, heart) for o in pl)
    touch = "; ".join(facts) or "none of the pieces touch"
    s = cur or {}
    prompt = (f"A FORTUNE CAST. The querent is a {sign} ({element}). They chose the group {I.GROUPS[group][0]}.\n"
              f"Pieces and how they fell:\n{lines}\nHow they lie together: {touch}.\n"
              f"{sky.note()}\n"
              "Write the reading as Veyra in 4 short paragraphs (about 250 words in all): (1) the heart of the cast and what the "
              "pieces that touch or cover each other say together, (2) what is leaving and what is coming, (3) the sky: say what "
              "astrologers are noting now and over the next few days, name the signs that benefit and the signs that should take "
              f"care (say how {sign} fares), and how the elements of the pieces meet today's sky, (4) one clear thing to do this "
              "week. Use ONLY the pieces listed. Plain prose, no headings, no lists, no brackets.")
    benefit, warn = s.get("benefit", []), s.get("warn", [])
    fallback = (f"The {heart['name']} lies at the heart of your cast, and it speaks of {I.ITEMS[heart['name']][4 if heart['turned'] else 3]}. "
                f"{(touch[0].upper() + touch[1:]) + '. ' if facts else ''}"
                f"The {loner['name']} lies apart: that is the part of your life that is standing back from the rest.\n"
                f"{s.get('summary', '')} The signs that gain are {', '.join(benefit) or 'many'}; take care, {', '.join(warn) or 'all of us'}. "
                f"As a {sign}, you meet this sky through {element}, and the sky is "
                f"{'kind' if sky.element_effect(element) > 0 else 'testing' if sky.element_effect(element) < 0 else 'even-handed'} to it.\n"
                "This week, do the one small thing the pieces point at, and let the rest settle.")
    narrate(reader, prompt, fallback, mood)
    if auto_index is not None:
        reader.mem["next_zodiac_index"] = (auto_index + 1) % len(tarot.ZODIAC_MONTHS)
        try:
            reader._save()
        except Exception:
            pass


# ---------------------------------------------------------------- chat
def chat_mode(reader):
    """She asks you questions, folds your answers in, and replies from memory, lore, the sky and the web."""
    mood = sky.CURRENT.get("mood", "mystic")
    cur = sky.CURRENT.get("sky")
    hist = []
    facts = reader.mem.get("user_facts", [])
    fx.say("Let us just talk. Say 'bye' when you want to stop.", "hope", "fade")
    opener = None
    if reader.online:
        opener = reader.brain.chat(reader._msgs(
            "Open a conversation as Veyra in one or two sentences, in the mood today's sky gives you. Ask the querent ONE "
            "genuine question about how they are or what is on their mind; use what you know of them if it helps."), 120, 0.9)
    opener = re.sub(r"\[[^\]]*\]", "", opener or "").strip() or "How has your day been sitting with you?"
    fx.say(opener, mood, "type")
    hist.append(("Veyra", opener))
    while True:
        said = fx.prompt("calm")
        if said.lower() in ("bye", "quit", "q", "exit", "leave"):
            break
        if not said:
            continue
        hist.append(("Querent", said))
        talk = "\n".join(f"{who}: {t}" for who, t in hist[-12:])
        if reader.online:
            prompt = (f"A conversation with the querent so far:\n{talk}\n\nReply as Veyra in 2 to 5 sentences. Let your mood follow "
                      "today's sky. Apply what they just said and what you know of them; if they ask about the world or the stars, "
                      "search the web first. End by asking them ONE question that follows from their answer. No brackets or labels.")
            out = fx.run_with_animation(lambda: sky.search_loop(reader, prompt, 2, 350)[0], 12, ("~ Veyra is thinking ~",))
            reply = re.sub(r"\[[^\]]*\]|^\s*Veyra:\s*", "", out or "").strip()
        else:
            reply = ("I hear you. " + (cur or {}).get("summary", "") + " What feels most true about that right now?")
        fx.say(reply, mood, "type")
        hist.append(("Veyra", reply))
    if reader.online and len(hist) > 3:
        out = reader.brain.chat(reader._msgs(
            "From this conversation, list up to 3 durable facts the querent told you about themselves, as a JSON array of "
            "short strings; [] if none.\n" + "\n".join(f"{w}: {t}" for w, t in hist[-16:])), 200, 0.2)
        m = re.search(r"\[.*\]", out or "", re.S)
        try:
            import json
            new = [str(x)[:120] for x in json.loads(m.group(0))] if m else []
        except Exception:
            new = []
        if new:
            reader.mem["user_facts"] = (facts + new)[-20:]
            try:
                reader._save()
            except Exception:
                pass
    fx.say("Until next time.", "hope", "fade")


# ---------------------------------------------------------------- startup drawings
def showcase(k, cols, rows, phase_len=48):
    """A row of pieces being drawn in front of you while the model loads. Returns ANSI lines with positions."""
    n = 3 if cols < 84 else 4
    phase = k // phase_len
    rng = random.Random(phase * 7919 + 13)
    group = rng.choice(list(I.GROUPS))
    names = rng.sample(I.GROUPS[group][2], n)
    shown = min(9, (k % phase_len) // 3 + 1)            # drawn row by row
    gap = 3
    total = n * I.N + (n - 1) * gap
    x0 = max(1, (cols - total) // 2)
    y0 = max(3, (rows - 9) // 2 - 2)
    out = []
    for i, nm in enumerate(names):
        cells = art.halfblock(I.sprite(nm))[:shown]
        for j, ln in enumerate(art.ansi(cells)):
            out.append(f"\x1b[{y0 + j};{x0 + i * (I.N + gap)}H{ln}")
        out.append(f"\x1b[{y0 + 10};{x0 + i * (I.N + gap)}H\x1b[38;5;141m{nm.center(I.N)}\x1b[0m")
    label = f"~ {I.GROUPS[group][0]} ~"
    out.append(f"\x1b[{y0 + 12};{max(1, (cols - len(label)) // 2)}H\x1b[38;5;103m{label}\x1b[0m")
    return "".join(out)
