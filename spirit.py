"""Where the 'message from the other side' begins.

True entropy (the querent's own keypress timing + the system) chooses threads from everything
Veyra keeps: her omens, the scenario lore for the cards on the table, the cards that keep
returning, what she has written in her grimoire, the card pairings she has recorded, lessons
from querents' feedback, her focus threads, her insights, and faint echoes of earlier messages.
She weaves them with an omen into one message: through her model when it is free, otherwise
in her own scripted voice. Nothing is fetched from outside; the spirits speak in her memory."""
import hashlib, os, random, re, time
from lore import LORE

LOCAL = [
    "A key left in a door that no longer exists.", "Salt on the windowsill, and a name nobody says.",
    "The river remembers the shape of every stone it has ever carried.",
    "Three crows on a wire, facing the same wrong way.", "A lantern lit at noon for someone still arriving.",
    "The moon does not argue with the tide; it only leans.", "Roots speak in a language of slow pressure.",
    "A bell rings underground, and the field answers.", "Ash holds the outline of what burned.",
    "The mirror waits behind the mirror.", "Someone is setting a second place at the table.",
    "Moss grows on the north side of every unspoken thing.", "An old road remembers its travelers by their weight.",
    "A door opens inward only for the one who knocks twice.", "Smoke rises where the sentence stopped.",
    "The seed does not know it is a forest.", "A thread pulled gently unravels the right knot.",
    "Winter stores what summer refused to count.", "The owl asks nothing and sees everything.",
    "Between two heartbeats, a whole room of silence.", "A candle burns hardest just before it must choose.",
    "The threshold is warm on one side only.", "Rain writes the same letter on every roof.",
    "A hand reaches from the blue hour and takes nothing.", "The deepest water holds still to be seen.",
    "Fog is the earth practicing forgetting.", "An unopened letter weighs more every year.",
    "The path forks where the traveler last hesitated.", "Fireflies rehearse a constellation.",
    "A name carved low on the oldest tree.", "The last stair always creaks the truth.",
    "What you set down will wait; what you carry will bend you.", "Stars are old light still choosing to arrive.",
]

PHRASES = {
    "ask": ["{card} leans close and asks: {t}", "The spirits hand me the question {card} carries: {t}"],
    "scene": ["Around {card} I see {t}.", "{card} shows me {t}."],
    "advice": ["{card} whispers: {t}.", "From {card}, a single instruction: {t}."],
    "recurring": ["{card} has found you {t} now. It is not finished with you.",
                  "Again {card}: {t} it has come. Listen to it this time."],
    "learned": ["In my grimoire, beside {card}, I once wrote: {t}", "I remember this about {card}: {t}"],
    "combo": ["When {card} meet, {t}", "I have seen {card} together before. {t}"],
    "lesson": ["A querent once taught me this: {t}", "I carry a lesson for this moment: {t}"],
    "focus": ["My attention keeps returning to {t}.", "The thread I keep following: {t}."],
    "insight": ["Something I have come to know: {t}"],
    "echo": ["An older message stirs again: {t}"],
}
CLOSERS = ["Hold it until a card makes sense of it.", "The spirits say no more.", "Remember this when the cards turn.",
           "Keep it close.", ""]
LABELS = {"ask": "the question {card} asks", "scene": "a scene around {card}", "advice": "{card}'s advice",
          "recurring": "{card} has come up {t} across readings", "learned": "your grimoire note on {card}",
          "combo": "your note on the pairing {card}", "lesson": "a lesson from a querent's feedback",
          "focus": "one of your focus threads", "insight": "one of your insights", "echo": "an earlier channeled message"}


def new_rng(extra=""):
    seed = hashlib.sha256(os.urandom(32) + str(time.time_ns()).encode() + extra.encode()).digest()
    return random.Random(seed)


def cards_in(text):
    """Card names mentioned in a piece of context, longest names first (so 'King of Cups' wins)."""
    found, t = [], text
    for name in sorted(LORE, key=len, reverse=True):
        if name in t:
            found.append(name)
            t = t.replace(name, " ")
    return found


NO_ARTICLE = {"Strength", "Justice", "Death", "Temperance", "Judgement"}
TIMES = {2: "twice", 3: "three times", 4: "four times", 5: "five times", 6: "six times"}
DOMAIN_WORDS = {"love": ("love", "relationship", "partner", "dating", "ex", "crush", "marriage", "boyfriend", "girlfriend"),
                "work": ("job", "career", "work", "boss", "business", "llc", "client", "promotion"),
                "money": ("money", "debt", "bills", "rent", "savings", "finance", "income", "afford", "pay")}


def named(card):
    """'the Nine of Swords', 'The Moon', 'Temperance'."""
    if card.startswith("The ") or card in NO_ARTICLE or " and " in card:
        return card
    return "the " + card


def _domain(context):
    t = context.lower()
    for d, words in DOMAIN_WORDS.items():
        if any(re.search(r"\b" + w + r"\b", t) for w in words):
            return d
    return "inner"


def _clip(s, limit=170):
    s = re.sub(r"\s+", " ", str(s)).strip().strip('"')
    s = re.split(r"(?<=[.!?])\s", s)[0]
    return s[:limit].rstrip(" ,;:")


def threads(mem, context, rng):
    """Every candidate thread: (weight, kind, card, text)."""
    cards = cards_in(context)
    dom = _domain(context)
    out = []
    for c in cards:                                            # the table as it lies now
        l = LORE[c]
        rev = f"{c} (reversed)" in context
        out.append((3.0, "ask", c, l["ask"]))
        out.append((2.0, "scene", c, l["rev"] if rev else l[dom]))
        if l.get("advice"):
            out.append((2.0, "advice", c, l["advice"]))
    for c, n in mem.get("card_counts", {}).items():           # cards that keep returning
        if n >= 2 and c in LORE:
            out.append((2.0 + min(n, 6) + (3.0 if c in cards else 0.0), "recurring", c, TIMES.get(n, f"{n} times")))
    for c, notes in mem.get("learned", {}).items():           # her grimoire
        for note in notes[-2:]:
            out.append((3.0 if c in cards else 0.8, "learned", c, _clip(note)))
    for pair, note in mem.get("combos", {}).items():          # recorded pairings
        a, _, b = pair.partition(" + ")
        w = 4.0 if (a in cards and b in cards) else 1.5 if (a in cards or b in cards) else 0.4
        out.append((w, "combo", f"{a} and {b}", _clip(note)))
    for lesson in mem.get("lessons", [])[-6:]:
        out.append((1.5, "lesson", None, _clip(lesson)))
    for f in mem.get("focus", [])[:3]:
        out.append((1.5, "focus", None, _clip(f).rstrip(".")))
    if mem.get("insights"):
        out.append((1.0, "insight", None, _clip(mem["insights"])))
    for e in mem.get("channelings", [])[-6:]:
        out.append((0.5, "echo", None, _clip(e)))
    if not out:                                                # a new Veyra with no memory yet
        c = rng.choice(sorted(LORE))
        out = [(1.0, "ask", c, LORE[c]["ask"]), (1.0, "advice", c, LORE[c]["advice"])]
    return [x for x in out if x[3]]


def pick(cands, rng, k):
    """Weighted draw without replacement, never the same kind twice."""
    chosen, pool = [], list(cands)
    while pool and len(chosen) < k:
        total = sum(w for w, *_ in pool)
        r, acc = rng.random() * total, 0.0
        for i, item in enumerate(pool):
            acc += item[0]
            if acc >= r:
                chosen.append(item)
                pool = [p for p in pool if p[1] != item[1]]
                break
    return [(kind, card, text) for _, kind, card, text in chosen]


def gather(mem, context, rng):
    """(omen, threads) for one message."""
    return rng.choice(LOCAL), pick(threads(mem, context, rng), rng, rng.choice([1, 2, 2]))


def _cap(s):
    s = s.strip()
    return s[:1].upper() + s[1:] if s else s


def weave(omen, chosen, rng):
    """Scripted voice: the omen, then each thread in her phrasing, then a closer."""
    parts = [omen]
    for kind, card, text in chosen:
        t = text.rstrip(".") if kind in ("scene", "advice", "focus") else text
        line = rng.choice(PHRASES[kind]).format(card=named(card) if card else "", t=t[:1].lower() + t[1:] if kind in ("scene", "advice") else t)
        parts.append(_cap(line))
    closer = rng.choice(CLOSERS)
    if closer:
        parts.append(closer)
    return " ".join(p if p.endswith((".", "?", "!")) else p + "." for p in parts)


def describe(chosen):
    """The threads as notes for the model to weave."""
    return "\n".join(f"- {LABELS[k].format(card=c or '', t=t)}: {t if k != 'recurring' else ''}".rstrip(": ")
                     for k, c, t in chosen)
