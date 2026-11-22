"""Frameworks (numbers, courts, elements, reversals, spreads), what every card means in every
position, and a scripted reader that composes a full reading with no model at all.
The model, when present, gets the same material as compact notes so even a small local
model reads accurately."""
import random, re
from lore import LORE, LIGHT, HEAVY
from cards import ELEMENTS, MEANINGS
from spreads import SPREADS

SUITS = ("Wands", "Cups", "Swords", "Pentacles")
NUMBERS = {"Ace": "seed, new beginning", "Two": "choice, balance, duality", "Three": "growth, collaboration",
           "Four": "stability, or stagnation", "Five": "conflict, loss, upheaval", "Six": "harmony, passage, giving",
           "Seven": "testing, assessment, defense", "Eight": "movement, mastery, power", "Nine": "near completion, solitude",
           "Ten": "completion, overflow, burden"}
RANKS = {"Page": "student/messenger; news, beginner, curiosity", "Knight": "pursuit; one-direction action (speed shows style)",
         "Queen": "inward mastery; internal command, nurture", "King": "outward mastery; authority, decisions"}
SUIT_PERSON = {"Wands": "passionate, driven, creative", "Cups": "empathic, intuitive, emotional",
               "Swords": "analytical, direct, principled", "Pentacles": "practical, grounded, reliable"}
SUIT_THEME = {"Wands": "drive, passion and action", "Cups": "feelings and relationships",
              "Swords": "thoughts, words and conflict", "Pentacles": "work, money and the body"}
TIMING = {"Wands": "fast: days to weeks (traditionally spring)", "Cups": "weeks to months (traditionally summer)",
          "Swords": "quick and sudden: days (traditionally autumn)", "Pentacles": "slow: months to a year (traditionally winter)"}
FRIENDLY = [{"Wands", "Swords"}, {"Cups", "Pentacles"}]
HOSTILE = [{"Wands", "Cups"}, {"Swords", "Pentacles"}]
REVERSAL = ("Reversals are not just 'bad': choose by feel whether the card is blocked, internalized, "
            "delayed, excessive/shadowed, or being resisted.")
TECHNIQUE = ("Order: (1) overall mood and Major/Minor balance; (2) repeated ranks/numbers = a theme; "
             "(3) suit/element flow: friendly pairs reinforce, hostile pairs create friction; "
             "(4) courts: ask whether it is a person in their story, an aspect of the querent, or an approach; "
             "test it against what they told you; (5) tell one story, then hand agency back.")
DOMAINS = {"love": ("love", "relationship", "partner", "dating", "marriage", "ex", "crush", "boyfriend", "girlfriend",
                    "husband", "wife", "romance", "soulmate", "breakup", "date"),
           "work": ("job", "career", "work", "boss", "business", "promotion", "interview", "school", "study", "project",
                    "company", "llc", "client", "coworker", "quit", "hired"),
           "money": ("money", "finance", "debt", "invest", "pay", "salary", "house", "buy", "afford", "income", "rent",
                     "loan", "savings", "bills")}


SIGNS = {"aries": "fire", "leo": "fire", "sagittarius": "fire", "taurus": "earth", "virgo": "earth",
         "capricorn": "earth", "gemini": "air", "libra": "air", "aquarius": "air", "cancer": "water",
         "scorpio": "water", "pisces": "water"}
ELEMENT_SUIT = {"fire": "Wands", "water": "Cups", "air": "Swords", "earth": "Pentacles"}


def parse_sign(text):
    """'Aquarius' -> ('Aquarius', 'air'); 'water' -> (None, 'water'); anything else -> (None, None)."""
    t = (text or "").lower()
    for sign, el in SIGNS.items():
        if sign in t:
            return sign.capitalize(), el
    for el in ELEMENT_SUIT:
        if el in t:
            return None, el
    return None, None


def profile_element(profile):
    m = re.search(r"\b(fire|water|air|earth)\b", (profile or "").lower())
    return m.group(1) if m else None


def element_note(element, spread):
    """How the querent's own element shows up on the table."""
    if element not in ELEMENT_SUIT:
        return ""
    suit = ELEMENT_SUIT[element]
    friend = [x for pair in FRIENDLY if suit in pair for x in pair if x != suit][0]
    rival = [x for pair in HOSTILE if suit in pair for x in pair if x != suit][0]
    mine = [c for c, _ in spread if split(c)[1] == suit]
    allies = sum(1 for c, _ in spread if split(c)[1] == friend)
    rivals = sum(1 for c, _ in spread if split(c)[1] == rival)
    if mine:
        names = [f"the {c}" for c in mine]
        joined = names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]
        s = (f"You are {element}, and {joined} {'speaks' if len(mine) == 1 else 'speak'} in your own element: "
             f"trust {'it' if len(mine) == 1 else 'them'} most of all.")
    else:
        s = f"You are {element}, yet no {suit} fell: this reading asks you to work outside your native element."
    if rivals > allies:
        s += f" The {rival} on the table pull against your nature; expect friction there."
    elif allies:
        s += f" The {friend} are your allies here."
    return s


def detect_domains(text):
    t = text.lower()
    hits = [d for d, kws in DOMAINS.items() if any(re.search(r"\b" + re.escape(k) + r"\b", t) for k in kws)]
    return hits or ["inner"]


def split(card):
    """(rank, suit) for minors, (None, None) for Majors (including 'Wheel of Fortune')."""
    rank, _, suit = card.rpartition(" of ")
    return (rank, suit) if suit in SUITS else (None, None)


def _low(s):
    return s[:1].lower() + s[1:] if s else s


# ================================================================ card facts
def facts(card):
    up, rev = MEANINGS[card]
    l = LORE[card]
    rank, suit = split(card)
    f = dict(l, name=card, kw=_low(up), kwr=_low(rev), k1=_low(up.split(",")[0]), kr1=_low(rev.split(",")[0]),
             rank=rank, suit=suit, element=ELEMENTS[suit] if suit else "Major Arcana (fate, the big lessons)")
    if rank in RANKS:
        f["person"] = f"a {rank.lower()} of {suit}: {RANKS[rank]}; temperament {SUIT_PERSON[suit]}"
    elif rank:
        f["person"] = f"someone moving through {f['k1']} ({NUMBERS[rank].split(',')[0]} in {SUIT_THEME[suit]})"
    else:
        f["person"] = f"someone who embodies {', '.join(_low(up).split(', ')[:2])}"
    f["number"] = NUMBERS.get(rank) or (RANKS[rank] if rank in RANKS else "")
    f["timing"] = TIMING[suit] if suit else "on fate's schedule: when the lesson is learned, not by the calendar"
    return f


def scene(f, domain):
    return f.get(domain) or f["inner"]


def yes_no(f, rev):
    yn = f["yn"]
    if rev:
        yn = {"Yes": "Maybe (delayed or conditional)", "Maybe": "No, not as things stand", "No": "No"}[yn]
    return yn


# position label -> (upright template, reversed template)
LENSES = {
    "The Past": ("Behind you: {scene}. That season of {k1} is the soil this grew from.",
                 "Behind you, something blocked or unfinished: {rev}. Its echo has not faded yet."),
    "The Present": ("Right now: {inner}. The energy in the room is {kw}.",
                    "Right now the energy is stuck or turned inward: {rev}."),
    "The Future": ("Where this heads if the path holds: {outcome}. The signpost says: {advice}.",
                   "Ahead, if the pattern holds: {kwr}. To shift it: {advice}."),
    "Heart of the Matter": ("At the core: {kw}. In your life that looks like {scene}.",
                            "At the core, something is blocked or turned inward: {rev}."),
    "The Crossing Card": ("Crossing you: {kw}. Even a gift here adds pressure; {scene} is what pushes against the core.",
                          "Crossing you: {kwr}. The friction comes from {rev}."),
    "The Root": ("Beneath it all: {inner}. The hidden motive is {k1}.",
                 "Buried at the root: {rev}; an old pattern of {kr1}."),
    "Recent Past": ("Just leaving: {scene}. The lesson of {k1} is passing behind you.",
                    "Just leaving, not fully resolved: {rev}."),
    "The Crown": ("Your best potential here, the goal worth holding: {advice}. Its gift is {k1}.",
                  "Your goal is shadowed by {kwr}. Check that you truly want what you are chasing."),
    "Near Future": ("Coming next: {scene}. Expect {kw}.",
                    "Coming next, possibly delayed or resisted: {rev}."),
    "The Self": ("How you carry yourself in this: {inner}.",
                 "How you get in your own way: {rev}."),
    "The Environment": ("Around you: {scene}. Others bring {kw}.",
                        "Around you, pressure: {rev}. Expect {kr1} from the outside."),
    "Hopes & Fears": ("Your hope, and maybe your fear: {outcome}. Wanting it this much is part of the picture.",
                      "Your fear: {rev}. Name it, and it loosens its hold."),
    "Final Outcome": ("Where this leads: {outcome}. Steer it with this: {advice}.",
                      "Where this leads if nothing shifts: {kwr}. A signpost, not a sentence: {advice}."),
}
LENSES.update({
    "First to Fall": ("The first card out of the deck names your concern: {kw}. In your life it looks like {scene}.",
                      "The first card fell upside down: your concern is tangled in {rev}."),
    "Second to Fall": ("What stands in the way: {k1}, pushed too far. {Scene} is what pushes back.",
                       "What stands in the way: {rev}."),
    "Third to Fall": ("What you cannot see yet: {inner}.",
                      "Hidden from you, and turned inward: {rev}."),
    "Fourth to Fall": ("What helps you: {kw}. Lean on {scene}.",
                       "Help is there but blocked: {rev}. Clear the way and it reaches you."),
    "Fifth to Fall": ("What to do next: {advice}.",
                      "What to do next: watch for {kr1}; then {advice}."),
    "Last to Fall": ("Where it settles: {outcome}.",
                     "Where it settles if nothing shifts: {kwr}. Steer it: {advice}."),
})
FALL_RELIEF = "For this card, upside down is relief: {rev}."
SCENES = ["Picture it: {scene}.", "Here is how it might look this month: {scene}.",
          "A scene comes to me: {scene}.", "In plain life, that is {scene}."]

ANY_POSITION = {
    "As advice": ("{Advice}.", "Reversed, the lesson turns inward: {rev}."),
    "As an obstacle": ("Too much of a good thing: {kw} turning into pressure.", "{Rev}."),
    "As a person": ("{Person}.", "{Person}, turned inward or off-balance: {rev}."),
    "As feelings": ("Feels like {inner}.", "Feels like {rev}."),
    "As the outcome": ("{Outcome}.", "{Kwr}; unless the pattern shifts."),
}


# Cards whose reversal is relief rather than trouble; reversed, they read as a weight lifting.
RELIEF = {"Four of Cups", "Five of Cups", "Five of Pentacles", "Three of Swords", "Eight of Swords", "Nine of Swords",
          "Ten of Swords", "Seven of Cups", "Seven of Swords", "Five of Wands", "Five of Swords", "The Devil",
          "The Tower", "The Moon", "Two of Swords", "Four of Swords", "Ten of Wands", "Eight of Cups"}
RELIEF_LENSES = {
    "The Past": "Behind you, a turning point: {rev}. The hardest part of that chapter is easing.",
    "The Present": "Right now the weight is lifting: {rev}.",
    "The Future": "Ahead, relief: {rev}. Help it along: {advice}.",
    "Heart of the Matter": "At the core, a turning point: {rev}.",
    "The Crossing Card": "Crossing you, oddly, is relief: {rev}. Even good change creates friction.",
    "The Root": "Beneath it all, something old is healing: {rev}.",
    "Recent Past": "Just leaving: {rev}. You are already through the worst of it.",
    "The Crown": "What you are reaching for: {rev}. That shift is your best potential now.",
    "Near Future": "Coming next, a weight lifts: {rev}.",
    "The Self": "How you carry yourself: turning a corner, {rev}.",
    "The Environment": "Around you, the pressure eases: {rev}.",
    "Hopes & Fears": "Your hope: {rev}. Let yourself believe it can happen.",
    "Final Outcome": "Where this leads: {rev}. Steer it with this: {advice}.",
}


def _fill(t, f, domain):
    vals = dict(f, scene=scene(f, domain))
    vals.update({k[0].upper() + k[1:]: (str(v)[:1].upper() + str(v)[1:]) for k, v in list(vals.items()) if isinstance(v, str)})
    return t.format(**vals)


def position_meaning(card, rev, label, domain="inner"):
    f = facts(card)
    up_t, rev_t = LENSES.get(label) or ANY_POSITION.get(label) or ("{Kw}.", "{Kwr}.")
    if rev and card in RELIEF and label in RELIEF_LENSES:
        rev_t = RELIEF_LENSES[label]
    elif rev and card in RELIEF and label.endswith("to Fall"):
        rev_t = FALL_RELIEF
    return _fill(rev_t if rev else up_t, f, domain)


def card_profile(card):
    """Every meaning of a card, upright and reversed, in every position: for the grimoire."""
    f = facts(card)
    out = [("ESSENCE", [f"Upright: {MEANINGS[card][0]}", f"Reversed: {MEANINGS[card][1]}", f"Element: {f['element']}"]
            + ([f"Number/rank: {f['number']}"] if f["number"] else []))]
    out.append(("IN REAL LIFE", [f"Love: {f['love']}", f"Work: {f['work']}", f"Money: {f['money']}",
                                 f"Inner: {f['inner']}", f"Reversed: {f['rev']}"]))
    out.append(("GUIDANCE", [f"Advice: {f['advice']}", f"Outcome: {f['outcome']}",
                             f"Yes/No: {yes_no(f, False)}  (reversed: {yes_no(f, True)})",
                             f"Timing: {f['timing']}", f"It asks: {f['ask']}"]))
    out.append(("IN ANY POSITION", [f"{k}: {_fill(u, f, 'inner')}  |  rev: {_fill(r, f, 'inner')}"
                                    for k, (u, r) in ANY_POSITION.items()]))
    for key in SPREADS:
        sp = SPREADS[key]
        lines = []
        for i, (label, what) in enumerate(sp["positions"], 1):
            lines.append(f"{i}. {label} ({what})")
            lines.append(f"   up: {position_meaning(card, False, label)}")
            lines.append(f"   rev: {position_meaning(card, True, label)}")
        out.append((sp["name"].upper(), lines))
    return out


# ================================================================ relationships between cards
def relation(a, b):
    (_, sa), (_, sb) = split(a), split(b)
    if not sa and not sb:
        return "two Major Arcana side by side: fate speaking twice, so this is a turning point, not a passing mood"
    if not sa or not sb:
        return "a Major beside a Minor: the larger force sets the tone and the everyday card shows where it lands"
    if sa == sb:
        return f"both {sa}: they amplify each other, doubling the theme of {SUIT_THEME[sa]}"
    if {sa, sb} in FRIENDLY:
        return f"{sa} and {sb} are elementally friendly: they reinforce each other"
    if {sa, sb} in HOSTILE:
        return f"{sa} and {sb} are elementally hostile: friction, a tug-of-war between {SUIT_THEME[sa]} and {SUIT_THEME[sb]}"
    return f"{sa} and {sb} are neutral elements: they coexist and need you to link them"


def tone(card, rev):
    """(mood, fx) that fits a card's emotional weather."""
    if card in LIGHT:
        return ("grief", "fade") if rev else ("hope", "shimmer")
    if card in HEAVY:
        return ("calm", "fade") if rev else ("dread", "glitch")
    return ("storm", "type") if rev else ("mystic", "type")


def impression(spread):
    n = len(spread)
    majors = [c for c, _ in spread if not split(c)[1]]
    revs = sum(1 for _, r in spread if r)
    suits = {}
    for c, _ in spread:
        s = split(c)[1]
        if s:
            suits[s] = suits.get(s, 0) + 1
    courts = [c for c, _ in spread if split(c)[0] in RANKS]
    bits = []
    if len(majors) * 2 >= n:
        bits.append(f"Fate is loud on this table: {len(majors)} of {n} cards are Major Arcana, so this is bigger than day-to-day choices.")
    elif not majors:
        bits.append("No Major Arcana fell, which means this is in your hands, built from everyday choices.")
    else:
        bits.append(f"{len(majors)} Major Arcana mark{'s' if len(majors) == 1 else ''} the turning point{'s' if len(majors) > 1 else ''}; the rest is yours to steer.")
    if suits:
        top = max(suits, key=suits.get)
        if suits[top] > 1:
            bits.append(f"{top} gather here ({suits[top]}): {ELEMENTS[top]}. At heart this is about {SUIT_THEME[top]}.")
    if revs * 2 > n:
        bits.append("Many reversals: energy is blocked, delayed, or turned inward. The work is inside first.")
    elif revs == 0:
        bits.append("Every card stands upright: the energy flows openly.")
    if courts:
        bits.append(f"Court cards ({', '.join(courts)}) mean people, or roles you are playing, matter here.")
    return " ".join(bits)


def _celtic_pairs(spread, dom):
    c = [x[0] for x in spread]
    r = [x[1] for x in spread]
    f = [facts(x) for x in c]
    out = [
        ("Central crucible (1 + 2)", f"{c[0]} at the heart, crossed by {c[1]}: {relation(c[0], c[1])}. "
         + (f"The crossing card blocks: {f[1]['kr1']} stands in the way of {f[0]['k1']}." if r[1] else
            f"The crossing card accelerates as much as it blocks: {f[1]['k1']} puts urgency on {f[0]['k1']}.")),
        ("Vertical axis (3 below, 5 above)", f"Root {c[2]} under crown {c[4]}: {relation(c[2], c[4])}. "
         + ("Hidden roots are sabotaging the goal; heal the root and the crown follows." if (r[2] or c[2] in HEAVY) and not r[4]
            else "What you want and what drives you underneath are pulling the same direction." if not (r[2] or r[4])
            else "The conscious goal itself is shadowed; check whether it is really yours.")),
        ("Timeline (4 to 6)", f"From {c[3]} to {c[5]}: " + ("the future echoes the past; watch the old pattern."
                                                             if split(c[3])[1] and split(c[3])[1] == split(c[5])[1]
                                                             else "the trajectory breaks new ground.")),
        ("Pivot (6 then 7)", f"What arrives ({c[5]}) meets how you react ({c[6]}{' reversed' if r[6] else ''}): "
         + ("the opportunity is there, but your mindset is the bottleneck." if r[6] else "you are ready to meet what comes.")),
        ("Inside vs outside (7 + 8)", f"You feel {f[6]['k1']} while the world brings {f[7]['k1']}: {relation(c[6], c[7])}."),
        ("Outcome triangle (5, 9, 10)", f"Does {c[9]} fulfil the crown's {f[4]['k1']}? "
         + ("It detours, and the hopes-and-fears card shows fear doing the steering." if r[9] or r[8]
            else "It largely fulfils it, filtered through what you hope for most.")),
    ]
    return out


def compose_reading(question, qa, spirit_qs, key, spread, channeled=(), rng=None, profile="", falls=None):
    """A complete reading built from the knowledge base alone (no model). Tagged for fx."""
    rng = rng or random.SystemRandom()
    import questions as Q
    dom = detect_domains(question + " " + " ".join(a for _, a in qa))[0]
    sp = SPREADS[key]
    note = element_note(profile_element(profile), spread)
    paras = [f"[mood=mystic fx=fade] You asked: \"{question.rstrip('.')}\" {impression(spread)}" + (f" {note}" if note else "")]
    for (label, _), (card, rev) in zip(sp["positions"], spread):
        mood, fxn = tone(card, rev)
        paras.append(f"[mood={mood} fx={fxn}] {label.upper()}: {card}{' (reversed)' if rev else ''}. "
                     + position_meaning(card, rev, label, dom))
    if key == "falling":
        falls = falls or {}
        for i, q in enumerate(falls.get("questions", [])):
            if q and i < len(spread):
                c, r = spread[i]
                paras.append(f"[mood=channel fx=shimmer] You asked: \"{q}\" and the {c} fell to answer it: "
                             + (facts(c)["rev"] if r else facts(c)["advice"]) + ".")
        for i, j in falls.get("pairs", []):
            (a, ra), (b, rb) = spread[i], spread[j]
            paras.append("[mood=storm fx=pulse] " + pair_reading(a, ra, b, rb, dom, rng=rng))
        fa, fz = facts(spread[0][0]), facts(spread[-1][0])
        paras.append(f"[mood=storm fx=pulse] The first card out named {fa['k1']}; the last to fall settles it in "
                     f"{fz['k1']}. {relation(spread[0][0], spread[-1][0])[:1].upper()}{relation(spread[0][0], spread[-1][0])[1:]}.")
    elif key == "three":
        (a, ra), (b, rb), (c, rc) = spread
        fa, fb, fc = facts(a), facts(b), facts(c)
        paras.append(f"[mood=storm fx=pulse] The story runs from {fa['k1']} through {fb['k1']} toward {fc['k1']}. "
                     f"Past into present: {relation(a, b)}. Present into future: {relation(b, c)}.")
    else:
        paras.append("[mood=storm fx=pulse] " + " ".join(f"{t}: {s}" for t, s in _celtic_pairs(spread, dom)))
    order = {"three": [1, 0, 2], "celtic": [0, 2, 9, 6, 8]}.get(key, list(range(len(spread))))
    for i, q in enumerate(spirit_qs):
        card, rev = spread[order[i % len(order)]]
        f = facts(card)
        ans = f"{f['rev']}; face that first, then {f['advice']}" if rev else f"{f['advice']}"
        paras.append(f"[mood=channel fx=shimmer] To the spirits I asked: \"{q}\" {card if card.startswith('The ') else 'The ' + card} answers: {ans[:1].upper() + ans[1:]}.")
    if channeled:
        paras.append(f"[mood=mystic fx=fade] What came through during the ritual still hangs in the air: {channeled[-1]}")
    paras.append("[CHANNEL]")
    last = facts(spread[-1][0])
    paras.append(f"[mood=calm fx=fade] A question to carry home: {last['ask']}")
    paras.append(f"[mood=hope fx=shimmer] {rng.choice(Q.CLOSINGS)}")
    return "\n\n".join(paras)


def card_summary(key, spread, domain="inner"):
    """Every card in its position, read in order: appended to the end of each reading so no card
    is ever skipped, whatever the model chose to focus on."""
    sp = SPREADS[key]
    parts = ["[mood=mystic fx=fade] Before the cards return to the deck, here is every card in its place:"]
    for i, ((label, _), (c, r)) in enumerate(zip(sp["positions"], spread), 1):
        mood, fxn = tone(c, r)
        parts.append(f"[mood={mood} fx={fxn}] {i}. {label}: {c}{' (reversed)' if r else ''}. "
                     + position_meaning(c, r, label, domain))
    return "\n\n".join(parts)


# ================================================================ falling cards
def card_name(card):
    """'The Star', 'the Ace of Cups', 'the Wheel of Fortune', but plain 'Justice', 'Death', 'Strength'."""
    if card.startswith("The "):
        return card
    if " of " in card:
        return "the " + card
    return card


def fall_reading(card, rev, i, question=None, domain="inner", mem=None, rng=None):
    """What Veyra says the moment a card falls out of the shuffle."""
    rng = rng or random.SystemRandom()
    label = SPREADS["falling"]["positions"][i][0]
    f = facts(card)
    the = card_name(card)
    parts = [f"{the[:1].upper() + the[1:]} falls{' upside down' if rev else ''}."]
    notes = (mem or {}).get("learned", {}).get(card, [])
    if notes:                                          # what she has written herself comes first
        n = notes[-1].strip()
        parts.append(f"My grimoire says: {n}" + ("" if n.endswith((".", "!", "?")) else "."))
    pm = position_meaning(card, rev, label, domain)
    parts.append(pm)
    if question:
        ans = (f"{f['rev']}; face that, then {f['advice']}" if rev and card not in RELIEF else f["advice"])
        parts.append(f"To \"{question.strip()}\" it answers: {ans[:1].upper() + ans[1:]}.")
    sc = scene(f, domain)
    if sc.lower() in pm.lower():                       # the position already painted this scene; don't repeat it
        pass
    elif rev and card in RELIEF:
        parts.append(f"Picture the weight lifting from {sc}.")
    elif rev:
        parts.append(f"Picture {sc}, but stalled or turned inward.")
    else:
        parts.append(rng.choice(SCENES).format(scene=sc))
    parts.append(f"It asks you: {f['ask']}")
    return " ".join(parts)


def pair_reading(a, ra, b, rb, domain="inner", mem=None, rng=None):
    """Two cards that fell out together are one answer."""
    rng = rng or random.SystemRandom()
    fa, fb = facts(a), facts(b)
    sa = fa["rev"] if ra else scene(fa, domain)
    sb = fb["rev"] if rb else scene(fb, domain)
    na = card_name(a) + (" (upside down)" if ra else "")
    nb = card_name(b) + (" (upside down)" if rb else "")
    text = (f"Two cards fell together: {na} and {nb}. They are one answer. {relation(a, b)[:1].upper()}"
            f"{relation(a, b)[1:]}. Together: {fa['kr1' if ra else 'k1']} meets {fb['kr1' if rb else 'k1']}. "
            f"Picture it: {sa}, while {sb}. Their shared counsel: {fa['advice']}, and {fb['advice']}.")
    hit = (mem or {}).get("combos", {}).get(" + ".join(sorted([a, b])))
    if hit:
        text += f" I have seen these two together before: {hit}"
    return text


# ================================================================ notes for the model
def position_notes(key, spread, domain):
    sp = SPREADS[key]
    return "\n".join(f"{i}. {label}: {c}{' (reversed)' if r else ''} -> {position_meaning(c, r, label, domain)}"
                     for i, ((label, _), (c, r)) in enumerate(zip(sp["positions"], spread), 1))


def lore_context(spread, question, qa_text="", mem=None):
    """Compact, relevant knowledge for exactly the cards drawn."""
    doms = detect_domains(question + " " + qa_text)
    out, asks = [], []
    for c, rev in spread:
        l = LORE.get(c)
        if not l:
            continue
        sc = l["rev"] if rev else "; ".join(f"{d}: {l[d]}" for d in doms[:2] + (["inner"] if "inner" not in doms[:2] else []))
        mine = (mem or {}).get("learned", {}).get(c, [])[-2:]
        out.append(f"{c}{' (rev)' if rev else ''} -> {sc}" + (f" | learned: {' / '.join(mine)}" if mine else ""))
        asks.append(l["ask"])
    ranks, suits = {}, {}
    for c, _ in spread:
        r, s = split(c)
        if r:
            ranks.setdefault(r, []).append(c)
            suits.setdefault(s, []).append(c)
    extra = []
    for r, cs in ranks.items():
        if len(cs) > 1:
            extra.append(f"Repeated {r}s ({len(cs)}): theme of {NUMBERS.get(r) or RANKS[r]}")
        if r in RANKS:
            extra.append(f"Court {', '.join(cs)}: {RANKS[r]}; temperament " + "/".join(SUIT_PERSON[split(c)[1]] for c in cs))
    present = list(suits)
    for i in range(len(present)):
        for j in range(i + 1, len(present)):
            pair = {present[i], present[j]}
            if pair in FRIENDLY:
                extra.append(f"{present[i]}+{present[j]} are elementally friendly (reinforce)")
            elif pair in HOSTILE:
                extra.append(f"{present[i]}+{present[j]} are elementally hostile (friction)")
    combos = (mem or {}).get("combos", {})
    names = sorted(c for c, _ in spread)
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            hit = combos.get(f"{names[i]} + {names[j]}")
            if hit:
                extra.append(f"Learned pairing {names[i]} + {names[j]}: {hit}")
    return ("Scenario library (adapt, do not recite):\n" + "\n".join(out) +
            ("\n" + "\n".join(extra) if extra else "") +
            "\nQuestions these cards ask: " + " | ".join(asks[:5]) + "\n" + REVERSAL)
