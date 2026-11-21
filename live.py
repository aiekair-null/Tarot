"""Live Reading: Veyra asks the deck her own questions, one before each card falls.

Her questions come from a bank (live_questions.json, editable; add your own, or the ones you
collect from videos), chosen to fit each card's place in the six and then mutated to fit the
feeling she senses from the cards that have fallen so far, the card before, and the threads she
keeps in memory. Written in our own words, inspired by common open-ended tarot practice:
ask 'what / how / why', keep it about the person and the present, leave room for a story."""
import json, os, random, re
from pathlib import Path

BANK_PATH = Path(os.environ.get("TAROT_LIVE_QUESTIONS", "live_questions.json"))

# The role each fall plays decides which themes she draws from.
ROLES = [
    ["energy", "heart"],                 # first to fall: the heart of it
    ["block", "shadow"],                 # second: what stands in the way
    ["hidden", "spirit"],                # third: what cannot be seen yet
    ["support", "strength"],             # fourth: what helps
    ["action", "growth"],                # fifth: what to do next
    ["outcome", "healing"],              # last: where it settles
]

DEFAULT_BANK = {
    "energy": [
        "What energy is gathering around {you} right now?",
        "What is really asking for attention in {your} life this week?",
        "What is the truest thing about where {you} stand today?",
        "Why does this moment feel so {feeling}?",
        "What story is {your} heart telling right now?",
        "What has been quietly shaping {your} days?",
        "Which part of life is calling loudest at the moment?",
        "What is the weather of {your} spirit tonight?",
    ],
    "heart": [
        "What is at the heart of feeling {feeling}?",
        "What does {your} heart already know that {your} head keeps arguing with?",
        "Where is love moving in {your} life, and where has it gone still?",
        "What connection matters most right now, and why?",
        "What does {you} need to understand about a bond that is on {your} mind?",
        "What is the real wish underneath the worry?",
    ],
    "block": [
        "What stands between {you} and what {you} want?",
        "What habit keeps pulling {you} back into the same loop?",
        "What fear is dressed up as common sense?",
        "What is draining {your} energy without {you} noticing?",
        "What keeps {you} from feeling less {feeling}?",
        "Where is {you} holding on too tightly?",
        "What old belief about money or worth is still in charge?",
    ],
    "shadow": [
        "What is {you} avoiding looking at?",
        "What part of {yourself} is asking to be forgiven?",
        "What does the {prev} want {you} to stop pretending about?",
        "What would {you} admit if no one were listening?",
        "Which mask has {you} worn so long it feels like a face?",
    ],
    "hidden": [
        "What can {you} not see yet?",
        "What is happening beneath the surface of this?",
        "What gift is hidden inside the difficulty?",
        "What is moving behind the scenes, unseen?",
        "What opportunity is quietly waiting at the edge of {your} sight?",
        "What does the spirit world see that {you} cannot?",
    ],
    "spirit": [
        "What is {your} intuition trying to say?",
        "What lesson keeps returning until it is learned?",
        "What practice would steady {your} spirit right now?",
        "How is this season meant to change {you}?",
        "What does {your} higher self want {you} to remember?",
        "Where is {you} being guided, if {you} would only follow?",
    ],
    "support": [
        "What support is already within reach?",
        "Who or what is on {your} side right now?",
        "What resource has {you} overlooked?",
        "Where can {you} find rest while feeling {feeling}?",
        "What will help most in the days ahead?",
    ],
    "strength": [
        "What strength has {you} forgotten {you} have?",
        "What talent is waiting to be used?",
        "What has {you} survived that proves {you} can handle this?",
        "Which quality in {you} will carry this through?",
        "What does {you} do better than {you} believe?",
    ],
    "action": [
        "What is the next right step?",
        "What one small action would change the most?",
        "How can {you} move forward without forcing it?",
        "What needs to be said out loud, and to whom?",
        "What should {you} begin, and what should {you} let go?",
        "How can {you} turn feeling {feeling} into something useful?",
        "After the {prev}, what does {you} do now?",
    ],
    "growth": [
        "How can {you} grow through this rather than around it?",
        "What is this chapter teaching {you}?",
        "What would the bravest version of {you} do next?",
        "How can {you} align daily work with what matters most?",
        "What would make {you} proud of how this was handled?",
    ],
    "outcome": [
        "Where is this heading if {you} keep walking this path?",
        "How does this settle when the dust clears?",
        "What is the likely shape of the next season?",
        "What does the {prev} lead into?",
        "Where does all of this want to land?",
    ],
    "healing": [
        "What needs healing so this can move?",
        "How does {you} make peace with what has been?",
        "What would let {you} feel lighter than {feeling}?",
        "What is ready to be released for good?",
        "What does recovery look like from here?",
    ],
}

# What she senses from the cards that have fallen
FEELINGS = {
    "heavy": ["weighed down", "worried", "tired of carrying it", "uneasy"],
    "light": ["hopeful", "open", "lighter than before", "quietly happy"],
    "Wands": ["restless", "driven", "impatient", "fired up"],
    "Cups": ["tender", "emotional", "full-hearted", "longing"],
    "Swords": ["anxious", "overthinking", "sharp-edged", "stuck in your head"],
    "Pentacles": ["unsure about security", "practical", "grounded but strained", "focused on money"],
    "major": ["at a crossroads", "in a big season", "pulled by fate"],
    "reversed": ["blocked", "held back", "turned inward"],
    "start": ["curious", "searching", "unsettled", "on the edge of something"],
}
OPENERS = ["Veyra asks the deck:", "She whispers to the cards:", "The spirits ask through her:", "Card, tell us:",
           "Let the next card answer:", "Veyra turns the question over:"]


def load_bank():
    """The question bank: live_questions.json if present (created with the defaults the first time)."""
    try:
        if BANK_PATH.exists():
            data = json.loads(BANK_PATH.read_text())
            if isinstance(data, dict) and data:
                return {k: [q for q in v if isinstance(q, str)] for k, v in data.items() if isinstance(v, list)}
        BANK_PATH.write_text(json.dumps(DEFAULT_BANK, indent=1))
    except Exception:
        pass
    return DEFAULT_BANK


def sense(fallen):
    """The feeling the cards suggest so far: (key, word)."""
    from lore import LIGHT, HEAVY
    from knowledge import split
    if not fallen:
        return "start", None
    scores = {}
    for c, r in fallen:
        suit = split(c)[1]
        scores[suit or "major"] = scores.get(suit or "major", 0) + 1
        if c in HEAVY and not r:
            scores["heavy"] = scores.get("heavy", 0) + 1.5
        if c in LIGHT and not r:
            scores["light"] = scores.get("light", 0) + 1.5
        if r:
            scores["reversed"] = scores.get("reversed", 0) + 0.8
    key = max(scores, key=scores.get)
    return key, None


def next_question(i, fallen, mem=None, rng=None, asked=()):
    """Veyra's own question for fall number i (0-5), shaped by what has fallen and her memory."""
    rng = rng or random.SystemRandom()
    bank = load_bank()
    key, _ = sense(fallen)
    feeling = rng.choice(FEELINGS.get(key, FEELINGS["start"]))
    prev = fallen[-1][0] if fallen else None
    themes = ROLES[min(i, 5)]
    pool = [q for t in themes for q in bank.get(t, [])]
    pool = [q for q in pool if (prev or "{prev}" not in q) and q not in asked] or [q for t in themes for q in bank.get(t, [])]
    q = rng.choice(pool) if pool else "What must be seen?"
    q = q.format(you="you", your="your", yourself="yourself", feeling=feeling,
                 prev=(prev.replace("The ", "") if prev else "last card"))
    q = re.sub(r"\bdoes you\b", "do you", q)
    q = re.sub(r"\bhas you\b", "have you", q)
    q = re.sub(r"\bis you\b", "are you", q)
    threads = (mem or {}).get("focus", [])
    if threads and rng.random() < 0.18:                     # now and then, one of her own memory threads
        q = q.rstrip("?") + f", and how does {threads[0].rstrip('.').lower()} touch it?"
    return q, rng.choice(OPENERS), feeling


def memory_meaning(card, mem):
    """What she has written about this card in her grimoire (persistent memory), if anything."""
    notes = (mem or {}).get("learned", {}).get(card, [])
    return notes[-1].strip() if notes else None
