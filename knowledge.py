"""Frameworks (numbers, courts, elements, reversals, spreads) + a compact context builder,
so Veyra arrives pre-loaded and spends few tokens at runtime."""
from lore import LORE
from cards import ELEMENTS

NUMBERS = {"Ace": "seed, new beginning", "Two": "choice, balance, duality", "Three": "growth, collaboration",
           "Four": "stability, or stagnation", "Five": "conflict, loss, upheaval", "Six": "harmony, passage, giving",
           "Seven": "testing, assessment, defense", "Eight": "movement, mastery, power", "Nine": "near completion, solitude",
           "Ten": "completion, overflow, burden"}
RANKS = {"Page": "student/messenger; news, beginner, curiosity", "Knight": "pursuit; one-direction action (speed shows style)",
         "Queen": "inward mastery; internal command, nurture", "King": "outward mastery; authority, decisions"}
SUIT_PERSON = {"Wands": "passionate, driven, creative", "Cups": "empathic, intuitive, emotional",
               "Swords": "analytical, direct, principled", "Pentacles": "practical, grounded, reliable"}
# traditional elemental dignities
FRIENDLY = [{"Wands", "Swords"}, {"Cups", "Pentacles"}]
HOSTILE = [{"Wands", "Cups"}, {"Swords", "Pentacles"}]
REVERSAL = ("Reversals are not just 'bad': choose by feel whether the card is blocked, internalized, "
            "delayed, excessive/shadowed, or being resisted.")
TECHNIQUE = ("Order: (1) overall mood and Major/Minor balance; (2) repeated ranks/numbers = a theme; "
             "(3) suit/element flow: friendly pairs reinforce, hostile pairs create friction; "
             "(4) courts: ask whether it is a person in their story, an aspect of the querent, or an approach; "
             "test it against what they told you; (5) tell one story, then hand agency back.")
DOMAINS = {"love": ("love", "relationship", "partner", "dating", "marriage", "ex", "crush", "family", "boyfriend", "girlfriend", "husband", "wife", "friend"),
           "work": ("job", "career", "work", "boss", "business", "promotion", "interview", "school", "study", "project", "company"),
           "money": ("money", "finance", "debt", "invest", "pay", "salary", "house", "buy", "afford", "income", "rent")}


def detect_domains(text):
    t = text.lower()
    hits = [d for d, kws in DOMAINS.items() if any(k in t for k in kws)]
    return hits or ["inner"]


def split(card):
    return card.split(" of ") if " of " in card else (None, None)


def lore_context(spread, question, qa_text="", mem=None):
    """Compact, relevant knowledge for exactly the cards drawn."""
    doms = detect_domains(question + " " + qa_text)
    out, asks = [], []
    for c, rev in spread:
        l = LORE.get(c)
        if not l:
            continue
        scene = l["rev"] if rev else "; ".join(f"{d}: {l[d]}" for d in doms[:2] + (["inner"] if "inner" not in doms[:2] else []))
        mine = (mem or {}).get("learned", {}).get(c, [])[-2:]
        out.append(f"{c}{' (rev)' if rev else ''} -> {scene}" + (f" | learned: {' / '.join(mine)}" if mine else ""))
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
    for r, cs in ranks.items():
        if r in RANKS:
            extra.append(f"Court {', '.join(cs)}: {RANKS[r]}; suit temperament " +
                         "/".join(SUIT_PERSON[split(c)[1]] for c in cs))
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
    nums = [f"{c}: {NUMBERS[split(c)[0]]}" for c, _ in spread if split(c)[0] in NUMBERS]
    return ("Scenario library for these cards (adapt, do not recite):\n" + "\n".join(out) +
            ("\nNumbers: " + "; ".join(nums) if nums else "") +
            ("\n" + "\n".join(extra) if extra else "") +
            "\nQuestions these cards ask: " + " | ".join(asks[:5]) + "\n" + REVERSAL + "\n" + TECHNIQUE)
