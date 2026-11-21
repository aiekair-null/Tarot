"""Veyra's scripted question bank: how she feels out the querent, what she asks the spirits,
and what she hands back at the end. Drawn with true randomness so no two interviews match.

Interview flow: one opener for the topic, then follow-ups triggered by words in the answers,
then themes in a shifting order (stakes, timeline, people, avoidance, hope, fear...)."""
import random, re

THEMES = ("stakes", "timeline", "people", "avoid", "hope", "fear", "past", "choice", "body", "power", "values")

OPENERS = {
    "love": [
        "Tell me about the person, or the absence of one, that brought you here.",
        "When you picture this relationship a year from now, what do you see first?",
        "Is this about someone you have, someone you lost, or someone you want?",
        "What does your heart keep circling back to, even when you tell it to stop?",
        "How would you describe the connection in three words?",
        "What first drew you to them, and is it still there?",
        "Where does this relationship feel easy, and where does it feel like work?",
        "What would you ask them if you knew they had to answer honestly?",
    ],
    "work": [
        "What is happening in your work life that will not leave you alone?",
        "Is this about the work itself, the people, or the direction you are heading?",
        "If you could redesign your working day from scratch, what changes first?",
        "What did you hope this path would give you, and is it giving it?",
        "Where do you feel most capable at work, and where do you feel small?",
        "Is there a door you are standing in front of, or one that just closed?",
        "What does success look like to you here, in plain terms?",
        "Who has the power over this outcome: you, or someone else?",
    ],
    "money": [
        "What is the money really about: safety, freedom, proof, or something else?",
        "Is this about a decision you have to make, or a pressure you are under?",
        "What would change in your daily life if this resolved the way you hope?",
        "How do you feel when you check your accounts: calm, tense, or avoidant?",
        "Is there a risk you are weighing, or a loss you are recovering from?",
        "What did money mean in the house you grew up in?",
        "Is someone else's money, or someone else's opinion, tangled in this?",
    ],
    "inner": [
        "What has been weighing on you lately, even in quiet moments?",
        "If this question had a color and a weather, what would they be?",
        "Where in your life do you feel most like yourself right now, and where least?",
        "What are you hoping the cards will tell you, honestly?",
        "Is something ending, beginning, or stuck in between for you?",
        "What keeps you up at night, or wakes you early?",
        "What part of you asked this question: the hopeful part or the worried part?",
        "If you already knew the answer, what would you guess it is?",
    ],
}

BANK = {   # theme -> domain -> questions ("any" works for every domain)
    "stakes": {
        "any": ["What happens if nothing changes at all?", "What is the most you could lose here, and the most you could gain?",
                "On a scale from passing worry to life-changing, where does this sit?",
                "Why does this matter so much right now, and not a year ago?",
                "What would it cost you to let this go entirely?"],
        "love": ["What would it mean about you if this relationship did not work out?",
                 "Is your heart on the line here, or your pride, or both?"],
        "work": ["Is your livelihood at stake, or your sense of purpose?",
                 "Would a wrong move here be recoverable, or would it close doors?"],
        "money": ["Is this a want or a need, if you are honest?",
                  "How long could you weather it if the worst happened?"],
    },
    "timeline": {
        "any": ["How long has this been on your mind?", "Is there a deadline, spoken or unspoken?",
                "When did you first notice things shifting?", "Does this feel urgent, or slow and grinding?",
                "If you had to decide by this time next week, could you?"],
        "love": ["How long have you known them?", "When was the last time things felt good between you?"],
        "work": ["How long have you been in this role or on this path?", "When is the next decision point?"],
        "money": ["When does the pressure peak: this month, this season, this year?"],
    },
    "people": {
        "any": ["Who else is tangled up in this?", "Whose opinion are you most afraid of here?",
                "Who would you call first if it went well? And if it went badly?",
                "Is there someone you are protecting by staying quiet?",
                "Who in your life sees this situation most clearly?"],
        "love": ["Is anyone else in the picture: an ex, a rival, family, friends with opinions?",
                 "How do your friends talk about this person when you are not around?"],
        "work": ["Who holds the keys: a boss, a client, a partner, a team?",
                 "Is there someone at work you trust completely, and someone you do not?"],
        "money": ["Does anyone depend on you financially, or you on them?",
                  "Is a partner, parent or business partner part of this decision?"],
    },
    "avoid": {
        "any": ["What are you not saying out loud about this?", "What conversation have you been putting off?",
                "Is there a part of this you hope I will not ask about?", "What do you keep almost deciding, then backing away from?",
                "What would you rather not know?"],
        "love": ["What have you never told them?", "What red flag have you talked yourself out of?"],
        "work": ["What task or truth have you been avoiding at work?", "Have you said what you really want to the people who decide?"],
        "money": ["Is there a number you have been avoiding looking at?", "What bill or letter is still unopened?"],
    },
    "hope": {
        "any": ["What do you hope for, in your most honest moment?", "If the cards brought perfect news, what would it be?",
                "What would a small win look like this month?", "What would make you proud of how you handled this?"],
        "love": ["What does being loved well look like to you?", "What would the best version of this relationship feel like day to day?"],
        "work": ["What work would make you lose track of time?", "Where would you like to be standing in two years?"],
        "money": ["What would enough feel like?", "What would you do first with a little breathing room?"],
    },
    "fear": {
        "any": ["What are you afraid of here, at the bottom of it?", "What is the story your worry keeps telling you?",
                "Is the fear about the outcome, or about how you will feel if it happens?",
                "Has this fear ever come true before?"],
        "love": ["Are you more afraid of losing them, or of losing yourself with them?", "What are you afraid they will find out?"],
        "work": ["Do you fear failing, or succeeding and being trapped by it?", "What would you do if this fell apart tomorrow?"],
        "money": ["What does scarcity whisper to you late at night?", "What is the worst case you keep rehearsing?"],
    },
    "past": {
        "any": ["Have you been somewhere like this before? How did it end?", "What did the last chapter teach you?",
                "Is there an old pattern repeating here?", "What decision in the past led you to this doorway?"],
        "love": ["What did your last relationship teach you that you are still carrying?", "Does this person remind you of anyone?"],
        "work": ["What job or mentor shaped how you work now?", "Is there a past failure still steering your choices?"],
        "money": ["What money lesson did you learn the hard way?"],
    },
    "choice": {
        "any": ["What are the options as you see them right now?", "Is there a choice you are pretending you do not have?",
                "If both paths turned out fine, which would you pick?", "What would you choose if no one else would ever know?"],
        "love": ["Are you choosing between people, or between staying and going?"],
        "work": ["Is it stay or go, or something in between?", "What would you try if you knew you could not fail?"],
        "money": ["Is the choice between safety and growth, or between two kinds of safety?"],
    },
    "body": {
        "any": ["Where do you feel this in your body when you think about it?", "Are you sleeping, eating and resting enough to think clearly?",
                "When you imagine each outcome, which one lets your shoulders drop?",
                "What does your gut say before your mind starts arguing?"],
    },
    "power": {
        "any": ["What part of this is truly in your control?", "Where have you been giving your power away?",
                "If you trusted yourself fully, what would you do next?", "What strength have you forgotten you have?"],
        "love": ["Do you feel like an equal in this connection?"],
        "work": ["Are you waiting for permission you do not actually need?"],
        "money": ["Which money decisions are yours alone to make?"],
    },
    "values": {
        "any": ["What matters most to you that this situation is pressing on?", "What kind of person do you want to be when this is over?",
                "Is there a promise you made to yourself that this touches?"],
        "love": ["What are you not willing to compromise on in love?"],
        "work": ["Would you be proud of this work if it had your name on it forever?"],
        "money": ["What would you never do for money?"],
    },
}

# Words in an answer that call for a specific follow-up.
TRIGGERS = [
    (("ex", "broke up", "breakup", "divorce", "split", "left me"),
     ["Do you want them back, or do you want the hurt to end? Those are different.",
      "What did the ending take from you, and what did it give back?"]),
    (("cheat", "lied", "lie", "betray", "secret"),
     ["Do you know this, or do you feel it? Both matter, but differently.",
      "Is the hardest part the act itself, or what it says about trust?"]),
    (("boss", "manager", "supervisor"),
     ["What do you need from your boss that you are not getting?",
      "If your boss read your mind right now, what would they learn?"]),
    (("quit", "leave", "resign", "new job", "offer", "interview"),
     ["What is pulling you toward the new, and what is pushing you away from the old?",
      "If you stayed exactly where you are for two more years, how would you feel?"]),
    (("business", "llc", "client", "customers", "start up", "startup", "side hustle"),
     ["Is your business asking for more of you than you have right now?",
      "What would grow if you gave it one focused hour a day?"]),
    (("debt", "owe", "loan", "bills", "broke"),
     ["Is the debt a weight you carry quietly, or one you have shared with anyone?",
      "What is one money conversation that would lighten this if you had it?"]),
    (("family", "mom", "mother", "dad", "father", "parent", "sister", "brother", "kids", "son", "daughter"),
     ["How is your family shaping this, spoken or not?",
      "Whose voice from your family do you hear when you think about this?"]),
    (("scared", "afraid", "anxious", "anxiety", "worried", "nervous", "panic"),
     ["When the worry is loudest, what helps even a little?",
      "Is the fear protecting you from something, or keeping you from something?"]),
    (("stuck", "trapped", "lost", "confused", "don't know", "dont know", "no idea"),
     ["If being stuck had a shape, what would it be: a wall, a fog, a loop?",
      "What is the smallest move that would prove you are not completely stuck?"]),
    (("move", "moving", "relocate", "city", "house", "apartment"),
     ["Is the move toward something, or away from something?",
      "Where do you feel at home, and is it a place or a person?"]),
    (("crush", "dating", "date", "met someone", "talking to"),
     ["What do you actually know about them, and what are you filling in?",
      "How do you feel about yourself when you are around them?"]),
    (("school", "college", "degree", "study", "exam", "class"),
     ["Is this path one you chose, or one chosen for you?",
      "What would you study if nobody else had an opinion?"]),
    (("friend", "friendship", "best friend"),
     ["Has the friendship changed, or have you?", "What do you give this friendship, and what do you receive?"]),
    (("art", "music", "writing", "book", "creative", "paint", "design"),
     ["When did you last make something just for yourself?", "What is the creative work asking of you right now?"]),
]

SPIRIT = {   # questions put to the spirits while the deck is washed
    "any": ["What must be seen that has not yet been seen?", "What is hidden beneath the surface of this?",
            "What is asked of the querent now?", "What energy is gathering around this question?",
            "What is the lesson inside this situation?", "Where does the querent's power lie?",
            "What should be released?", "What wants to be born from this?", "What is the next right step?",
            "What truth is ready to be spoken?", "What blessing is hidden in the difficulty?",
            "What pattern is asking to be broken?"],
    "love": ["What does this connection truly need?", "What is the other heart feeling but not saying?",
             "Is this bond growing toward the light or away from it?", "What must the querent give, and what must they keep?",
             "What does love ask of the querent right now?"],
    "work": ["Where is the querent's true work calling them?", "What obstacle stands between effort and reward?",
             "What skill or strength is ready to be used?", "Is this the right time to move, or to hold?",
             "What will this path cost, and what will it return?"],
    "money": ["Where does security truly come from in this?", "What decision brings stability without fear?",
              "What resource is the querent overlooking?", "Is the flow of abundance blocked, and by what?",
              "What does the querent need to know before they commit?"],
    "inner": ["What part of the querent is asking to be heard?", "What old story is ready to end?",
              "What would bring peace to the querent's mind?", "What is the querent ready to forgive?",
              "Where is the querent's own light pointing?"],
}

ACKS = ["Mm. I hear that.", "Thank you. The cards are already listening.", "I feel the weight of that.",
        "Yes... that tells me a great deal.", "Hold that thought; it matters.", "The candle flickered when you said that.",
        "I see. Let me sit with that a moment.", "That is honest. Honesty sharpens the reading.",
        "Good. Keep breathing slowly.", "The deck is warm in my hands now."]

CLOSINGS = ["The cards are gathered with gratitude. What they showed is a lantern, not a cage; walk where it lights.",
            "Thank you for trusting the table. The rest of the story is yours to write.",
            "I return the cards to the deck and the choice to you. Go gently.",
            "The spirits have said their piece. Carry what helps; leave the rest on the cloth.",
            "This reading is a signpost. You are the traveler. Thank you for sitting with me."]

CRISIS = ("kill myself", "suicide", "suicidal", "end my life", "want to die", "self harm", "self-harm",
          "hurt myself", "cut myself", "no reason to live", "better off dead", "end it all")
CRISIS_MSG = ("I am going to set the cards down for a moment, because you matter more than any reading. "
              "If you are thinking about ending your life or hurting yourself, please reach out to a person right now. "
              "In the US you can call or text 988 (Suicide & Crisis Lifeline), any time. Elsewhere, findahelpline.com lists "
              "free local lines. If you are in immediate danger, call your local emergency number. "
              "You do not have to carry this alone.")


def in_crisis(text):
    t = (text or "").lower()
    return any(k in t for k in CRISIS)


_THEME_OF = {q: th for th, doms in BANK.items() for qs in doms.values() for q in qs}


def _pool(theme, domains):
    d = BANK[theme]
    return [q for dom in domains for q in d.get(dom, [])] + d["any"]


def next_question(question, qa, domains, rng=None, limit=5):
    """The next scripted interview question, or None when Veyra has enough."""
    rng = rng or random.SystemRandom()
    if len(qa) >= limit:
        return None
    asked = {q for q, _ in qa}
    if not qa:
        return rng.choice(OPENERS[domains[0] if domains[0] in OPENERS else "inner"])
    last = qa[-1][1].lower()
    used_triggers = sum(1 for q in asked if any(q in qs for _, qs in TRIGGERS))
    if used_triggers < 2:
        for words, qs in TRIGGERS:
            if any(re.search(r"\b" + re.escape(k) + r"\b", last) for k in words):
                fresh = [q for q in qs if q not in asked]
                if fresh:
                    return rng.choice(fresh)
    used = {_THEME_OF.get(q) for q in asked}
    order = list(THEMES)
    rng.shuffle(order)
    order.sort(key=lambda t: t not in ("stakes", "people", "timeline", "fear", "hope"))  # core themes first
    for th in order:
        if th in used:
            continue
        fresh = [q for q in _pool(th, domains) if q not in asked]
        if fresh:
            return rng.choice(fresh)
    return None


def spirit_questions(domains, rng=None, n=3):
    rng = rng or random.SystemRandom()
    pool = [q for d in domains for q in SPIRIT.get(d, [])]
    picks = rng.sample(pool, min(2, len(pool))) if pool else []
    rest = [q for q in SPIRIT["any"] if q not in picks]
    return picks + rng.sample(rest, n - len(picks))


def count():
    return (sum(len(v) for v in OPENERS.values()) + sum(len(q) for d in BANK.values() for q in d.values())
            + sum(len(q) for _, q in TRIGGERS) + sum(len(v) for v in SPIRIT.values()))
