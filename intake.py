"""Veyra's getting-to-know-you questions.

Every reading she asks your work and your sign. Age and gender are asked once and remembered. Then she
picks a few questions from a pool of over a thousand, never one she has asked you before (until the pool
runs out). A blank answer just skips that question."""
import random

AREAS = ["sleep", "energy", "money", "home", "work", "love life", "friendships", "family", "body",
         "creativity", "faith", "patience", "confidence", "focus", "mornings", "nights", "appetite",
         "sense of humor", "free time", "plans", "dreams", "luck", "temper", "heart", "habits",
         "inner voice", "boundaries", "spending", "social life", "motivation"]

PLURAL = {"friendships", "mornings", "nights", "plans", "dreams", "habits", "boundaries"}

FEELINGS = ["hopeful", "restless", "stuck", "curious", "uneasy", "excited", "tired", "proud", "lonely",
            "grateful", "impatient", "calm", "nervous", "brave", "heavy", "light", "torn", "certain"]

TIMES = ["this week", "this month", "the next few days", "the season ahead", "the new year",
         "tomorrow", "the weekend", "the next big decision", "the next conversation you dread",
         "the thing you keep putting off"]

PEOPLE = ["makes you laugh hardest", "you miss right now", "drains your energy", "you trust most lately",
          "you owe a real conversation", "inspires you", "you're trying to impress", "you've drifted from",
          "you'd call at 3 a.m.", "challenges you", "you're protecting", "taught you something this year",
          "you keep thinking about", "you'd like to forgive", "you'd like to be forgiven by",
          "sees you most clearly", "you feel responsible for", "you're secretly rooting for"]

THINGS = ["a song", "a smell", "a place", "a color", "a food", "a book or show", "a memory", "an object",
          "a word", "a season", "an animal", "a sound", "a dream", "a habit", "a goal", "a fear",
          "a small win", "a regret", "a ritual", "a secret wish"]

THING_STEMS = ["What's {} that's stuck with you lately?",
               "Name {} that feels like you right now.",
               "What's {} you'd bring to this reading if you could?",
               "Is there {} that's been showing up again and again?"]

AREA_STEMS = ["How's your {} lately, in one word?",
              "What would make your {} feel lighter?",
              "What's quietly draining your {}?",
              "If your {} had a weather report, what would it be?",
              "What's one thing you'd change about your {} this month?",
              "Who or what feeds your {} best?"]

BASE = [
    "What made you smile today?", "What's the last thing you were really proud of?",
    "What are you avoiding right now?", "What does a perfect ordinary day look like for you?",
    "What's something you've outgrown?", "What's a question you wish someone would ask you?",
    "Where do you feel most like yourself?", "What's a promise you made to yourself lately?",
    "What did you want to be when you were a kid?", "What's the bravest thing you did this year?",
    "What do you keep almost saying out loud?", "What are you saving your energy for?",
    "What's a sign you've been ignoring?", "What would you do with a free, empty week?",
    "What rule do you live by?", "What are you learning the hard way?",
    "What part of your life feels unfinished?", "Who were you a year ago, in one sentence?",
    "What's something you forgive too easily?", "What's something you don't forgive easily?",
    "What would future you thank you for starting?", "What would you like the cards to leave alone?",
    "What's the loudest thought in your head right now?", "What would make tonight a good night?",
    "Do you feel more like the hunter or the hunted lately?", "What are you building, slowly?",
    "What's one thing you're done apologizing for?", "Where are you holding your breath?",
    "What do you need more of: rest, fire, or clarity?", "What did you dream about last?",
]


def pool():
    qs = list(BASE)
    qs += [s.format(a) for s in AREA_STEMS for a in AREAS]                              # 180
    qs += [f"How are you feeling about {t}? {f.capitalize()}, or something else?"
           for t in TIMES for f in FEELINGS]                                           # 180
    qs += [f"Who in your life {p}?" for p in PEOPLE]
    qs += [f"What would change if the person who {p} knew how you feel?" for p in PEOPLE]
    qs += [s.format(t) for s in THING_STEMS for t in THINGS]                            # 80
    qs += [f"When you picture {t}, what's the first thing you feel?" for t in TIMES]
    qs += [f"{'Are' if a in PLURAL else 'Is'} your {a} asking for more {x} or less?" for a in AREAS
           for x in ("attention", "rest", "honesty", "risk", "structure", "play", "silence",
                     "courage", "patience", "help", "change", "softness", "discipline", "joy")]  # 420
    qs += [f"What's one small thing you could do for your {a} {t}?" for a in AREAS
           for t in ("this week", "tomorrow", "this weekend", "before the next full moon", "tonight")]  # 150
    seen, out = set(), []
    for q in qs:
        if q not in seen:
            seen.add(q)
            out.append(q)
    return out


POOL = pool()


def pick(mem, n=3, rng=None):
    """n questions she hasn't asked you before; the list starts over once every one has been used."""
    rng = rng or random.SystemRandom()
    asked = set(mem.get("intake_asked") or [])
    fresh = [q for q in POOL if q not in asked]
    if len(fresh) < n:
        asked, fresh = set(), list(POOL)
    chosen = rng.sample(fresh, n)
    mem["intake_asked"] = sorted(asked | set(chosen))
    return chosen
