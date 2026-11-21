"""Deck + meanings (from the supplied reference). Format: name | upright | reversed."""

ELEMENTS = {"Wands": "Fire (action, passion)", "Cups": "Water (emotion, relationships)",
            "Swords": "Air (intellect, conflict)", "Pentacles": "Earth (wealth, work)"}

_MAJOR = """
The Fool | New beginnings, innocence, spontaneity, a leap of faith | Recklessness, risk-taking, hesitation, naivety
The Magician | Manifestation, resourcefulness, power, inspired action | Manipulation, poor planning, wasted talent
The High Priestess | Intuition, sacred knowledge, divine feminine, subconscious | Secrets, disconnected intuition, superficiality
The Empress | Abundance, nurturing, fertility, nature, luxury | Dependence, creative block, smothering care
The Emperor | Authority, structure, solid foundation, control, stability | Tyranny, rigidity, lack of discipline, abuse of power
The Hierophant | Spiritual wisdom, tradition, institutions, mentorship | Rebellion, restriction, unconventional beliefs
The Lovers | Love, harmony, vital choices, alignment of values | Disharmony, misalignment, bad choices, self-doubt
The Chariot | Control, willpower, success, determination, momentum | Lack of control, opposition, directionless wandering
Strength | Courage, patience, compassion, inner fortitude | Self-doubt, weakness, raw emotion, insecurity
The Hermit | Soul-searching, introspection, solitude, inner guidance | Isolation, loneliness, withdrawal, lost direction
Wheel of Fortune | Good luck, karma, life cycles, destiny, turning point | Bad luck, resistance to change, breaking cycles
Justice | Fairness, truth, cause and effect, legal matters | Dishonest actions, lack of accountability, unfairness
The Hanged Man | Surrender, new perspective, pause, letting go | Stalling, resistance, martyrdom, needless sacrifice
Death | Transformation, endings, transition, fresh start | Resistance to change, stagnation, fear of moving on
Temperance | Balance, moderation, patience, purpose, harmony | Excess, imbalance, lack of patience, discord
The Devil | Shadow self, attachment, addiction, restriction | Breaking free, reclaiming power, overcoming addiction
The Tower | Sudden upheaval, revelation, disaster, awakening | Avoiding disaster, delaying the inevitable, fear of change
The Star | Hope, faith, purpose, renewal, spiritual blessing | Despair, lack of faith, discouragement, fatigue
The Moon | Illusion, fear, anxiety, intuition, subconscious | Release of fear, uncovering secrets, clarity returning
The Sun | Joy, success, celebration, vitality, optimism | Temporary sadness, overly optimistic, dimmed joy
Judgement | Reflection, awakening, calling, absolution | Self-doubt, harsh self-criticism, ignoring the call
The World | Completion, accomplishment, travel, wholeness | Lack of closure, delays, unfinished business
"""

_MINOR = {
"Wands": """
Ace | Inspiration, power, creation, new opportunity | Delays, lack of motivation, missed opportunity
Two | Future planning, making decisions, leaving comfort zone | Fear of unknown, poor planning, hesitation
Three | Expansion, foresight, overseas opportunities, enterprise | Obstacles in expansion, delays in travel/growth
Four | Celebration, homecoming, community, harmony | Tense home life, canceled celebrations, domestic friction
Five | Competition, conflict, minor struggle, diverse opinions | Avoiding conflict, compromise, finding harmony
Six | Public recognition, victory, success, leadership | Fall from grace, ego, lack of recognition, private success
Seven | Defense, protection, standing your ground, perseverance | Giving up, feeling overwhelmed, yielding under pressure
Eight | Speed, rapid action, swift communication, travel | Delays, frustration, slowness, miscommunication
Nine | Resilience, persistence, guarding boundaries, stamina | Paranoia, exhaustion, defensive posture, burnout
Ten | Burden, responsibility, heavy workload, stress | Burnout, carrying too much, delegating responsibility
Page | Exploration, excitement, free spirit, new ideas | Newly formed ideas lacking direction, setbacks
Knight | Action, adventure, impulsiveness, high energy | Haste, scattered energy, recklessness, delay
Queen | Courage, confidence, warmth, independence | Demanding, jealousy, insecurity, bullying
King | Natural leader, vision, entrepreneur, honor | Impulsive, ruthless, uncompromising, high expectations
""",
"Cups": """
Ace | Love, compassion, new emotional cycle, intuition | Blocked emotions, sadness, repressed feelings
Two | Partnership, mutual attraction, connection, unity | Disconnection, broken communication, imbalance
Three | Celebration, friendship, sisterhood, community | Gossip, isolation, overindulgence, exclusion
Four | Apathy, meditation, contemplation, missed blessing | Depression lifting, sudden awareness, accepting help
Five | Regret, loss, disappointment, mourning the past | Acceptance, moving on, finding forgiveness
Six | Nostalgia, childhood memories, innocence, reunion | Living in the past, childishness, unrealistic memories
Seven | Choices, fantasy, illusion, wishful thinking | Clarity, reality check, waking up, focused decision
Eight | Walking away, disillusionment, leaving behind | Staying in bad situations, fear of walking away
Nine | Wish fulfillment, contentment, satisfaction, luxury | Smugness, greed, dissatisfaction despite luxury
Ten | Divine love, happy family, emotional bliss, alignment | Broken family, domestic disharmony, separation
Page | Creative opportunity, intuitive message, inner child | Emotional vulnerability, immaturity, creative blocks
Knight | Romance, charm, following the heart, proposal | Moodiness, unrealistic romantic ideals, deceit
Queen | Compassion, warmth, emotional stability, intuition | Emotional insecurity, martyrdom, codependency
King | Emotional balance, diplomacy, calm under pressure | Manipulation, moodiness, emotional volatility
""",
"Swords": """
Ace | Breakthrough, clarity, sharp mind, raw truth | Confusion, hostile words, clouded judgment
Two | Difficult choices, stalemate, blind spot, avoidance | Forced decision, breaking the stalemate, information overload
Three | Heartbreak, emotional pain, sorrow, grief | Releasing pain, forgiveness, recovering from grief
Four | Rest, recovery, meditation, sanctuary | Burnout, exhaustion, forced rest, stress
Five | Conflict, winning at all costs, tension, betrayal | Reconciliation, past resentment, making amends
Six | Transition, moving on, calmer waters, recovery | Trapped in the past, baggage, difficult transition
Seven | Deception, strategy, stealth, getting away with it | Coming clean, confession, exposed deceit
Eight | Restriction, self-imprisonment, victim mindset | Self-acceptance, breaking free, newfound freedom
Nine | Anxiety, worry, nightmares, mental anguish | Recovery from anxiety, hope, releasing fear
Ten | Rock bottom, betrayal, painful ending, defeat | Recovery, resurrection, learning from disaster
Page | Curiosity, mental agility, vigilance, watchfulness | Gossip, hasty judgments, malicious words
Knight | Ambition, fast-thinking, assertiveness, drive | Haste without thought, aggression, chaotic energy
Queen | Clear boundaries, direct communication, objectivity | Coldness, bitterness, overly critical, harsh words
King | Intellectual power, authority, truth, ethics | Manipulation, abuse of power, cruelty, rigidity
""",
"Pentacles": """
Ace | New financial opportunity, prosperity, manifestation | Lost opportunity, poor financial planning, scarcity
Two | Balance, adaptability, juggling resources, flexibility | Overwhelmed, poor prioritization, financial imbalance
Three | Teamwork, collaboration, craftsmanship, learning | Lack of teamwork, poor quality, ignored input
Four | Conservation, security, frugality, holding on | Greediness, financial insecurity, letting go
Five | Financial hardship, poverty, isolation, insecurity | Recovery from hardship, temporary help, spiritual wealth
Six | Generosity, charity, sharing wealth, fairness | Strings attached, debt, unfair power dynamics
Seven | Long-term view, sustainable growth, patience | Impatience, wasted effort, poor return on investment
Eight | Mastery, craftsmanship, diligence, skill development | Perfectionism, lack of focus, substandard work
Nine | Luxury, self-sufficiency, financial independence | Financial setback, superficial wealth, overspending
Ten | Wealth, family legacy, long-term security, tradition | Financial dispute, broken family ties, loss of inheritance
Page | Financial opportunity, ambition, studious approach | Lack of progress, procrastination, short-term focus
Knight | Hard work, routine, reliability, conservatism | Boredom, stagnation, laziness, workaholic tendencies
Queen | Practicality, nurturing home, financial security | Work-home imbalance, materialism, smothering
King | Abundance, business acumen, security, leadership | Greed, poor business decisions, stubbornness
""",
}


def _rows(block):
    return [[p.strip() for p in ln.split("|")] for ln in block.strip().splitlines() if ln.strip()]


MEANINGS = {}   # name -> (upright, reversed)
DECK = []       # canonical order
for name, up, rev in _rows(_MAJOR):
    MEANINGS[name] = (up, rev)
    DECK.append(name)
for suit, block in _MINOR.items():
    for rank, up, rev in _rows(block):
        MEANINGS[f"{rank} of {suit}"] = (up, rev)
        DECK.append(f"{rank} of {suit}")


def build_deck():
    return list(DECK)


def meaning(name, reversed_=False):
    up, rev = MEANINGS[name]
    return rev if reversed_ else up
