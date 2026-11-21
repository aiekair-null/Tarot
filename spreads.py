"""Spreads, their position meanings, and how the cards interact."""

COURTS = ("Page", "Knight", "Queen", "King")

SPREADS = {
    "three": {
        "name": "Three-Card Spread (Past, Present, Future)",
        "use": "A quick, clear question; a single situation; when the querent needs a simple story.",
        "positions": [
            ("The Past", "root causes, previous mindsets, lingering influences"),
            ("The Present", "current state, immediate mindset, hidden truths or obstacles"),
            ("The Future", "likely trajectory if the current path continues; a signpost, not a sentence"),
        ],
        "guide": "Read left to right as a story: how the past created the present and how the "
                 "present is shaping the future.",
    },
    "celtic": {
        "name": "Celtic Cross (10 cards)",
        "use": "A complex, layered situation: inner conflict, relationships, big decisions, "
               "when hidden motives and outside forces both matter.",
        "positions": [
            ("Heart of the Matter", "the core of the situation"),
            ("The Crossing Card", "what blocks or accelerates it; friction, pressure, urgency"),
            ("The Root", "subconscious foundation, hidden motives, deep past"),
            ("Recent Past", "what is just leaving"),
            ("The Crown", "conscious goal, best potential"),
            ("Near Future", "immediate momentum once the central friction moves"),
            ("The Self", "internal attitude, self-perception, emotional posture"),
            ("The Environment", "external circumstances, other people, support or pressure"),
            ("Hopes & Fears", "the deepest hope or fear; the final filter on the outcome"),
            ("Final Outcome", "where it leads"),
        ],
        "guide": (
            "Do not read 1 to 10 in a line; read the relationships between paired positions.\n"
            "- 1+2 Central Crucible: one compound theme. Does 2 block 1 or accelerate it? Even a "
            "positive 2 brings friction/urgency.\n"
            "- 3+5 Vertical Axis (subconscious vs conscious): shared suit/theme = alignment; "
            "fear/trauma at 3 under an ambitious 5 = hidden roots sabotaging the goal.\n"
            "- 4 -> 1/2 -> 6 Horizontal Timeline: compare 4 and 6: does the trajectory repeat past "
            "patterns or break new ground?\n"
            "- 6 -> 7 Pivot Bridge: 6 is what happens externally, 7 is how the self reacts; big "
            "opportunity + insecurity = mindset is the bottleneck.\n"
            "- 7+8 Internal vs External: contrast inner feeling with outer reality; find the blind spot.\n"
            "- 5+9+10 Outcome Triangle: does 10 fulfil the potential of 5, or detour? 9 sits under 10 "
            "and acts as the final filter: fear of failure under a stagnant 10 means fear steers.\n"
            "Final synthesis: compare 1+2 (core vs obstacle), 5+10 (crown vs outcome), 7+8 (self vs "
            "environment)."
        ),
    },
    "falling": {
        "name": "Live Reading (six cards fall from the shuffle)",
        "use": "Veyra asks the deck her own questions; cards fall out of the shuffle one at a time "
               "(sometimes two together), each answering the question she asked just before it fell.",
        "positions": [
            ("First to Fall", "the heart of your concern"),
            ("Second to Fall", "what stands in the way"),
            ("Third to Fall", "what you cannot see yet"),
            ("Fourth to Fall", "what helps you"),
            ("Fifth to Fall", "what to do next"),
            ("Last to Fall", "where it settles"),
        ],
        "guide": (
            "These cards were not dealt: they fell out of the shuffle on their own, so each one insisted.\n"
            "- Read them in the order they fell; each answers the question Veyra asked the deck just before it.\n"
            "- A card that fell reversed fell upside down: name that, and read it as blocked, inward or resisted.\n"
            "- Cards that fell TOGETHER are one answer: read them as a pair, how they interact, what they say jointly.\n"
            "- First to fall vs last to fall: does the concern resolve, or transform into something else?\n"
            "- Close by tying every question that was asked to the card that answered it."
        ),
    },
}


def diagnostics(key, spread):
    """Suit majority, majors, and court clusters, computed in code."""
    pos = SPREADS[key]["positions"]
    suits, majors, courts = {}, [], []
    for i, (c, rev) in enumerate(spread, 1):
        rank, _, suit = c.rpartition(" of ")
        if suit not in ("Wands", "Cups", "Swords", "Pentacles"):
            majors.append(i)
        else:
            suits[suit] = suits.get(suit, 0) + 1
            if rank in COURTS:
                courts.append(i)
    top = sorted(suits.items(), key=lambda kv: -kv[1])
    out = [f"Suit counts: {dict(top) or 'none'}" + (f" (majority: {top[0][0]})" if top and top[0][1] > 1 else ""),
           f"Major Arcana at positions: {majors or 'none'} "
           f"({', '.join(pos[i - 1][0] for i in majors) or 'none'})",
           f"Court cards at positions: {courts or 'none'}; reversed: "
           f"{[i for i, (_, r) in enumerate(spread, 1) if r] or 'none'}"]
    return "\n".join(out)
