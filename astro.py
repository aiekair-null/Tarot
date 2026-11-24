"""Veyra reads the sky herself.

No website, no key: the positions of the Sun, Moon and planets are worked out here from their
orbits (Paul Schlyter's method, good to a fraction of a degree, plenty for signs and aspects).
Once a day the sky is saved to sky/YYYY-MM-DD.json; each sign's horoscope is written by Veyra
from it and saved in the same file, so the day's readings agree with each other.
"""
import json, math, os, re, time
from datetime import datetime, timedelta, timezone
from pathlib import Path

SKY_DIR = Path(os.environ.get("TAROT_SKY", "sky"))
SIGNS = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", "Libra", "Scorpio",
         "Sagittarius", "Capricorn", "Aquarius", "Pisces"]
GLYPH = dict(zip(SIGNS, "♈♉♊♋♌♍♎♏♐♑♒♓"))
BODIES = ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"]
ASPECTS = [("conjunct", 0, 6), ("sextile", 60, 4), ("square", 90, 6), ("trine", 120, 6), ("opposite", 180, 6)]
HOUSES = ["self and first impressions", "money and what you value", "talk, siblings and short trips",
          "home and family", "romance, play and creativity", "work, health and routines",
          "partners and one-on-ones", "intimacy, shared money and change", "travel, study and belief",
          "career and reputation", "friends, groups and hopes", "rest, secrets and endings"]
MEANS = {"Sun": "your focus", "Moon": "your mood", "Mercury": "words and plans", "Venus": "love and pleasure",
         "Mars": "drive and anger", "Jupiter": "luck and growth", "Saturn": "duty and limits",
         "Uranus": "sudden change", "Neptune": "dreams and confusion", "Pluto": "deep transformation"}


def _n(x):
    return x % 360.0


def _r(x):
    return math.radians(x)


def _day(dt):
    """Days since 2000 Jan 0.0 UT."""
    dt = dt.astimezone(timezone.utc)
    return (dt - datetime(1999, 12, 31, tzinfo=timezone.utc)).total_seconds() / 86400.0


def _elements(d):
    return {
        "Sun": (0, 0, 282.9404 + 4.70935e-5 * d, 1.0, 0.016709 - 1.151e-9 * d, 356.0470 + 0.9856002585 * d),
        "Moon": (125.1228 - 0.0529538083 * d, 5.1454, 318.0634 + 0.1643573223 * d, 60.2666, 0.0549,
                 115.3654 + 13.0649929509 * d),
        "Mercury": (48.3313 + 3.24587e-5 * d, 7.0047 + 5.00e-8 * d, 29.1241 + 1.01444e-5 * d, 0.387098,
                    0.205635 + 5.59e-10 * d, 168.6562 + 4.0923344368 * d),
        "Venus": (76.6799 + 2.46590e-5 * d, 3.3946 + 2.75e-8 * d, 54.8910 + 1.38374e-5 * d, 0.723330,
                  0.006773 - 1.302e-9 * d, 48.0052 + 1.6021302244 * d),
        "Mars": (49.5574 + 2.11081e-5 * d, 1.8497 - 1.78e-8 * d, 286.5016 + 2.92961e-5 * d, 1.523688,
                 0.093405 + 2.516e-9 * d, 18.6021 + 0.5240207766 * d),
        "Jupiter": (100.4542 + 2.76854e-5 * d, 1.3030 - 1.557e-7 * d, 273.8777 + 1.64505e-5 * d, 5.20256,
                    0.048498 + 4.469e-9 * d, 19.8950 + 0.0830853001 * d),
        "Saturn": (113.6634 + 2.38980e-5 * d, 2.4886 - 1.081e-7 * d, 339.3939 + 2.97661e-5 * d, 9.55475,
                   0.055546 - 9.499e-9 * d, 316.9670 + 0.0334442282 * d),
        "Uranus": (74.0005 + 1.3978e-5 * d, 0.7733 + 1.9e-8 * d, 96.6612 + 3.0565e-5 * d, 19.18171 - 1.55e-8 * d,
                   0.047318 + 7.45e-9 * d, 142.5905 + 0.011725806 * d),
        "Neptune": (131.7806 + 3.0173e-5 * d, 1.7700 - 2.55e-7 * d, 272.8461 - 6.027e-6 * d, 30.05826 + 3.313e-8 * d,
                    0.008606 + 2.15e-9 * d, 260.2471 + 0.005995147 * d),
    }


def _orbit(N, i, w, a, e, M):
    M = _r(_n(M))
    E = M + e * math.sin(M) * (1 + e * math.cos(M))
    for _ in range(8):
        E -= (E - e * math.sin(E) - M) / (1 - e * math.cos(E))
    xv, yv = a * (math.cos(E) - e), a * math.sqrt(1 - e * e) * math.sin(E)
    v, r = math.atan2(yv, xv), math.hypot(xv, yv)
    N, i, w = _r(N), _r(i), _r(w)
    x = r * (math.cos(N) * math.cos(v + w) - math.sin(N) * math.sin(v + w) * math.cos(i))
    y = r * (math.sin(N) * math.cos(v + w) + math.cos(N) * math.sin(v + w) * math.cos(i))
    z = r * math.sin(v + w) * math.sin(i)
    return x, y, z


def longitudes(dt):
    """Geocentric ecliptic longitude (degrees, of date) of every body at a moment."""
    d = _day(dt)
    el = _elements(d)
    out = {}
    N, i, w, a, e, M = el["Sun"]
    xs, ys, _ = _orbit(N, i, w, a, e, M)
    out["Sun"] = _n(math.degrees(math.atan2(ys, xs)))
    Ms, Ls = _n(M), _n(M + w)
    # Moon, with its largest perturbations
    N, i, w, a, e, M = el["Moon"]
    x, y, z = _orbit(N, i, w, a, e, M)
    lon = math.degrees(math.atan2(y, x))
    Mm = _n(M)
    Lm = _n(Mm + w + N)
    D, F = Lm - Ls, Lm - N
    s = lambda deg: math.sin(_r(deg))
    lon += (-1.274 * s(Mm - 2 * D) + 0.658 * s(2 * D) - 0.186 * s(Ms) - 0.059 * s(2 * Mm - 2 * D)
            - 0.057 * s(Mm - 2 * D + Ms) + 0.053 * s(Mm + 2 * D) + 0.046 * s(2 * D - Ms) + 0.041 * s(Mm - Ms)
            - 0.035 * s(D) - 0.031 * s(Mm + Ms) - 0.015 * s(2 * F - 2 * D) + 0.011 * s(Mm - 4 * D))
    out["Moon"] = _n(lon)
    Mj, Msa, Mu = _n(el["Jupiter"][5]), _n(el["Saturn"][5]), _n(el["Uranus"][5])
    c = lambda deg: math.cos(_r(deg))
    fix = {
        "Jupiter": -0.332 * s(2 * Mj - 5 * Msa - 67.6) - 0.056 * s(2 * Mj - 2 * Msa + 21) + 0.042 * s(3 * Mj - 5 * Msa + 21)
                   - 0.036 * s(Mj - 2 * Msa) + 0.022 * c(Mj - Msa) + 0.023 * s(2 * Mj - 3 * Msa + 52) - 0.016 * s(Mj - 5 * Msa - 69),
        "Saturn": 0.812 * s(2 * Mj - 5 * Msa - 67.6) - 0.229 * c(2 * Mj - 4 * Msa - 2) + 0.119 * s(Mj - 2 * Msa - 3)
                  + 0.046 * s(2 * Mj - 6 * Msa - 69) + 0.014 * s(Mj - 3 * Msa + 32),
        "Uranus": 0.040 * s(Msa - 2 * Mu + 6) + 0.035 * s(Msa - 3 * Mu + 33) - 0.015 * s(Mj - Mu + 20),
    }
    for body in ("Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune"):
        x, y, z = _orbit(*el[body])
        if body in fix:                                   # perturb the heliocentric longitude
            r, lo = math.hypot(x, y), math.atan2(y, x) + _r(fix[body])
            x, y = r * math.cos(lo), r * math.sin(lo)
        out[body] = _n(math.degrees(math.atan2(y + ys, x + xs)))
    # Pluto (series fit, J2000, plus precession to date)
    S, P = _n(50.03 + 0.033459652 * d), _n(238.95 + 0.003968789 * d)
    lon = (238.9508 + 0.00400703 * d - 19.799 * s(P) + 19.848 * c(P) + 0.897 * s(2 * P) - 4.956 * c(2 * P)
           + 0.610 * s(3 * P) + 1.211 * c(3 * P) - 0.341 * s(4 * P) - 0.190 * c(4 * P) + 0.128 * s(5 * P)
           - 0.034 * c(5 * P) - 0.038 * s(6 * P) + 0.031 * c(6 * P) + 0.020 * s(S - P) - 0.010 * c(S - P))
    lat = (-3.9082 - 5.453 * s(P) - 14.975 * c(P) + 3.527 * s(2 * P) + 1.673 * c(2 * P) - 1.051 * s(3 * P)
           + 0.328 * c(3 * P) + 0.179 * s(4 * P) - 0.292 * c(4 * P) + 0.019 * s(5 * P) + 0.100 * c(5 * P)
           - 0.031 * s(6 * P) - 0.026 * c(6 * P) + 0.011 * c(S - P))
    r = (40.72 + 6.68 * s(P) + 6.90 * c(P) - 1.18 * s(2 * P) - 0.03 * c(2 * P) + 0.15 * s(3 * P) - 0.14 * c(3 * P))
    lon += 3.82394e-5 * (d - 1.5)
    x, y = r * c(lat) * c(lon), r * c(lat) * s(lon)
    out["Pluto"] = _n(math.degrees(math.atan2(y + ys, x + xs)))
    return out


def sign_of(lon):
    return SIGNS[int(_n(lon) // 30)], _n(lon) % 30


def moon_phase(sun, moon):
    el = _n(moon - sun)
    lit = (1 - math.cos(_r(el))) / 2
    names = ["New Moon", "Waxing Crescent", "First Quarter", "Waxing Gibbous", "Full Moon",
             "Waning Gibbous", "Last Quarter", "Waning Crescent"]
    return names[int(((el + 22.5) % 360) // 45)], lit


def chart(dt):
    """Everything she needs from the sky at one moment."""
    now, later = longitudes(dt), longitudes(dt + timedelta(days=1))
    bodies = {}
    for b in BODIES:
        sg, deg = sign_of(now[b])
        step = (later[b] - now[b] + 540) % 360 - 180
        bodies[b] = {"lon": round(now[b], 2), "sign": sg, "deg": round(deg, 1), "retro": step < 0 and b not in ("Sun", "Moon")}
    asp = []
    for i, a in enumerate(BODIES):
        for b in BODIES[i + 1:]:
            sep = abs((now[a] - now[b] + 180) % 360 - 180)
            for name, ang, orb in ASPECTS:
                o = orb + (2 if "Moon" in (a, b) else 0)
                if abs(sep - ang) <= o:
                    asp.append({"a": a, "b": b, "aspect": name, "orb": round(abs(sep - ang), 1)})
    asp.sort(key=lambda x: x["orb"])
    phase, lit = moon_phase(now["Sun"], now["Moon"])
    return {"bodies": bodies, "aspects": asp, "phase": phase, "lit": round(lit, 3)}


def _local_today():
    return datetime.now().astimezone()


def today(force=False):
    """Today's sky (computed once a day, then read from sky/)."""
    now = _local_today()
    path = SKY_DIR / f"{now:%Y-%m-%d}.json"
    if path.exists() and not force:
        try:
            return json.loads(path.read_text())
        except Exception:
            pass
    noon = now.replace(hour=12, minute=0, second=0, microsecond=0)
    sky = {"date": f"{now:%Y-%m-%d}", "computed": time.strftime("%Y-%m-%d %H:%M"), **chart(noon), "horoscopes": {}}
    SKY_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sky, indent=1))
    return sky


def save(sky):
    SKY_DIR.mkdir(parents=True, exist_ok=True)
    (SKY_DIR / f"{sky['date']}.json").write_text(json.dumps(sky, indent=1))


def summary(sky=None, short=False):
    """Today's sky in one or two lines, for prompts and screens."""
    sky = sky or today()
    b = sky["bodies"]
    head = f"{sky['phase']} in {b['Moon']['sign']} ({int(sky['lit'] * 100)}% lit), Sun in {b['Sun']['sign']}"
    if short:
        return head
    retro = [k for k, v in b.items() if v["retro"]]
    places = ", ".join(f"{k} {v['sign']}" for k, v in b.items() if k not in ("Sun", "Moon"))
    tight = "; ".join(f"{x['a']} {x['aspect']} {x['b']}" for x in sky["aspects"][:4])
    return (head + f". {places}." + (f" Retrograde: {', '.join(retro)}." if retro else " Nothing retrograde.")
            + (f" Strongest aspects: {tight}." if tight else ""))


def houses_for(sign, sky):
    """Whole-sign houses from the sun sign: which part of life each planet is lighting up."""
    k = SIGNS.index(sign)
    return {b: (SIGNS.index(v["sign"]) - k) % 12 + 1 for b, v in sky["bodies"].items()}


def scripted(sign, sky, rng):
    """Her horoscope without a model: built straight from the sky."""
    h = houses_for(sign, sky)
    b = sky["bodies"]
    lines = [f"I read the sky myself tonight, {sign}. The {sky['phase'].lower()} sits in {b['Moon']['sign']}, "
             f"lighting your house of {HOUSES[h['Moon'] - 1]}: that is where your feelings will run today."]
    if b["Sun"]["sign"] == sign:
        lines.append("The Sun is in your own sign, so the light is on you. Use it.")
    for x in sky["aspects"][:6]:
        if "Moon" in (x["a"], x["b"]):
            continue
        p, q = x["a"], x["b"]
        tone = {"conjunct": "fuses", "sextile": "opens a door between", "square": "grinds against",
                "trine": "flows easily with", "opposite": "pulls against"}[x["aspect"]]
        lines.append(f"{p} {tone} {q}: {MEANS[p]} and {MEANS[q]}, felt in your {HOUSES[h[p] - 1]}.")
        break
    retro = [k for k, v in b.items() if v["retro"]]
    if "Mercury" in retro:
        lines.append("Mercury is walking backward: reread before you send, and expect old voices.")
    elif retro:
        lines.append(f"{rng.choice(retro)} is retrograde: something from the past wants a second look.")
    lines.append(rng.choice(["Trust the slower answer.", "Say the true thing kindly.", "Leave room for the unplanned.",
                             "Rest is part of the work today.", "Follow the small yes."]))
    return " ".join(lines)


def horoscope(sign, reader=None, rng=None):
    """Today's horoscope for one sign, written once a day (by the model if it is awake) and kept."""
    import random
    rng = rng or random.SystemRandom()
    sky = today()
    if sign in sky.get("horoscopes", {}):
        return sky["horoscopes"][sign]
    text = None
    if reader is not None and getattr(reader, "online", False):
        h = houses_for(sign, sky)
        lit = "; ".join(f"{k} in your {n}th house ({HOUSES[n - 1]})" for k, n in h.items() if k in ("Sun", "Moon", "Mercury", "Venus", "Mars"))
        prompt = (f"You read today's sky yourself, from the planets' real positions (no website, no one else's horoscope). "
                  f"Today's sky: {summary(sky)}\nFor {sign} (whole-sign houses): {lit}.\n"
                  f"Write {sign}'s horoscope for today in 4 to 6 sentences, as Veyra, addressed to 'you'. "
                  f"Begin by saying you read the sky yourself tonight. Name at least two real placements above. "
                  "No square-bracket tags.")
        text = reader._ask(prompt, 380, 0.8)
        if text:
            text = re.sub(r"\[[^\]]*\]", "", text).strip()
    text = text or scripted(sign, sky, rng)
    sky.setdefault("horoscopes", {})[sign] = text
    save(sky)
    return text


def natal(date_str, time_str="12:00"):
    """Planet signs at a birth moment (local time of this machine if no zone is given)."""
    dt = datetime.strptime(f"{date_str} {time_str or '12:00'}", "%Y-%m-%d %H:%M").astimezone()
    return chart(dt)


def natal_text(c):
    b = c["bodies"]
    return ("; ".join(f"{k} in {v['sign']}{' (retrograde)' if v['retro'] else ''}" for k, v in b.items())
            + f". Born under a {c['phase']}.")


def sign_from_text(s):
    s = (s or "").strip().lower()
    for sg in SIGNS:
        if s and (sg.lower().startswith(s[:3])):
            return sg
    return None
