"""Where the 'message from the other side' begins: entropy from the querent's own timing,
the system, and the wider world, then a raw fragment for Veyra to shape."""
import hashlib, json, os, random, time, urllib.request

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
AVOID = ("murder", "killed", "suicide", "rape", "massacre", "genocide", "nazi", "abuse", "terror",
         "shooting", "porn", "sexual", "died", "death", "war crime", "hostage")


def new_rng(extra=""):
    seed = hashlib.sha256(os.urandom(32) + str(time.time_ns()).encode() + extra.encode()).digest()
    return random.Random(seed)


def fragment(rng):
    """A raw fragment: a random sentence from a random Wikipedia article, else a local omen."""
    for _ in range(4):
        try:
            req = urllib.request.Request("https://en.wikipedia.org/api/rest_v1/page/random/summary",
                                         headers={"User-Agent": "VeyraTarot/1.0"})
            with urllib.request.urlopen(req, timeout=4) as r:
                d = json.load(r)
            ex = d.get("extract", "")
            if not ex or any(w in ex.lower() for w in AVOID):
                continue
            sents = [s.strip() for s in ex.replace("\n", " ").split(". ") if len(s.strip()) > 25]
            if sents:
                return rng.choice(sents)[:220], d.get("title", "the unknown")
        except Exception:
            break
    return rng.choice(LOCAL), "the other side"
