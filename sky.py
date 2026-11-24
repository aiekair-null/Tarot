"""Today's sky. At startup Veyra works out the Sun and Moon herself, reads what the web is saying about
current and coming astrology (she chooses her own searches), and keeps the result in memory so every
reading, cast and chat can lean on it. Runs in the background and never blocks or breaks the app."""
import datetime, json, math, re, threading

SIGNS = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", "Libra", "Scorpio", "Sagittarius", "Capricorn",
         "Aquarius", "Pisces"]
ELEM = ["fire", "earth", "air", "water"]
PHASES = ["new moon", "waxing crescent", "first quarter", "waxing gibbous", "full moon", "waning gibbous",
          "last quarter", "waning crescent"]
PHASE_MOOD = {"new moon": "mystic", "waxing crescent": "hope", "first quarter": "ecstatic", "waxing gibbous": "hope",
              "full moon": "ecstatic", "waning gibbous": "calm", "last quarter": "dread", "waning crescent": "grief"}
CURRENT = {"text": "", "mood": "mystic"}          # what the other modules read (set by apply())


def _jd(now=None):
    now = now or datetime.datetime.utcnow()
    return now.timestamp() / 86400.0 + 2440587.5


def basics(now=None):
    """Sun and Moon from low-precision formulas (accurate to about a degree): no data files needed."""
    d = _jd(now) - 2451545.0
    g = math.radians(357.528 + 0.9856003 * d)
    sun = (280.460 + 0.9856474 * d + 1.915 * math.sin(g) + 0.020 * math.sin(2 * g)) % 360
    mp = math.radians(134.963 + 13.064993 * d)
    moon = (218.316 + 13.176396 * d + 6.289 * math.sin(mp)) % 360
    age = ((_jd(now) - 2451550.1) / 29.530588853) % 1.0
    return {"sun": SIGNS[int(sun // 30)], "sun_deg": round(sun % 30, 1), "moon": SIGNS[int(moon // 30)],
            "phase": PHASES[int(age * 8 + 0.5) % 8], "age": round(age * 29.53, 1)}


def element_of(sign):
    return ELEM[SIGNS.index(sign) % 4]


def fallback(b):
    """If there is no model or no internet: the sky she can work out herself."""
    si = SIGNS.index(b["sun"])
    trine = [SIGNS[(si + 4) % 12], SIGNS[(si + 8) % 12]]
    square = [SIGNS[(si + 3) % 12], SIGNS[(si + 9) % 12]]
    return {"summary": f"The Sun is in {b['sun']} and the Moon, a {b['phase']}, moves through {b['moon']}.",
            "events": [f"{b['phase']} in {b['moon']}"], "benefit": trine + [b["sun"]], "warn": square,
            "boost": [element_of(b["sun"]), element_of(b["moon"])],
            "strain": [element_of(square[0])], "source": "her own reckoning"}


def _json(text):
    m = re.search(r"\{.*\}", text or "", re.S)
    try:
        return json.loads(m.group(0)) if m else None
    except Exception:
        return None


def search_loop(reader, question, rounds=3, max_tokens=500):
    """Let the model search the web for whatever it wants: it answers 'SEARCH: query' to look something up."""
    import research
    msgs = reader._msgs(question + "\n\nIf you need current facts, reply with exactly one line `SEARCH: your query` "
                        "and nothing else; you may search up to " + str(rounds) + " times. Otherwise answer.")
    seen = []
    for _ in range(rounds + 1):
        out = reader.brain.chat(msgs, max_tokens, 0.5)
        m = re.match(r"\s*SEARCH:\s*(.+)", out or "")
        if not m or len(seen) >= rounds:
            return out, seen
        q = m.group(1).strip()[:120]
        found = research.search(q, 4)
        seen.append(q)
        msgs += [{"role": "assistant", "content": out},
                 {"role": "user", "content": "Search results for '" + q + "':\n" + ("\n".join(found) or "(nothing found)")
                  + "\nSearch again or answer now."}]
    return out, seen


def read_sky(reader):
    """One daily reading of the sky: her own numbers plus what the internet says."""
    b = basics()
    sky = dict(fallback(b), **{"date": datetime.date.today().isoformat(), "basics": b})
    if reader.online:
        try:
            ask = (f"Today is {datetime.date.today():%A %d %B %Y}. By my own reckoning the Sun is in {b['sun']} and the "
                   f"Moon is a {b['phase']} in {b['moon']}. Find out what astrologers are saying about the sky today and "
                   "over the next few days (planets, retrogrades, eclipses, lunations, aspects). Then reply with ONLY a "
                   'JSON object: {"summary": "3-4 sentences in your own words", "events": ["short event", ...], '
                   '"benefit": ["signs that gain"], "warn": ["signs that should take care"], "boost": ["elements helped"], '
                   '"strain": ["elements strained"]}.')
            out, searches = search_loop(reader, ask)
            j = _json(out)
            if j and j.get("summary"):
                clean = lambda xs, pool: [x.title() if pool is SIGNS else x.lower() for x in (xs or [])
                                          if str(x).title() in pool or str(x).lower() in pool]
                sky.update(summary=str(j["summary"])[:700], events=[str(e)[:90] for e in j.get("events", [])][:6],
                           benefit=clean(j.get("benefit"), SIGNS) or sky["benefit"],
                           warn=clean(j.get("warn"), SIGNS) or sky["warn"],
                           boost=clean(j.get("boost"), ELEM) or sky["boost"],
                           strain=clean(j.get("strain"), ELEM) or sky["strain"],
                           source="the web: " + "; ".join(searches) if searches else "her own reckoning")
        except Exception:
            pass
    return sky


def note(sky=None):
    s = sky or CURRENT.get("sky")
    if not s:
        return ""
    return (f"TODAY'S SKY ({s['date']}): {s['summary']} Events: {', '.join(s['events'])}. "
            f"Signs favoured: {', '.join(s['benefit'])}. Signs to take care: {', '.join(s['warn'])}. "
            f"Elements helped: {', '.join(s['boost'])}; strained: {', '.join(s['strain'])}.")


def apply(reader, sky):
    b = sky.get("basics") or basics()
    CURRENT["sky"], CURRENT["text"] = sky, note(sky)
    CURRENT["mood"] = PHASE_MOOD.get(b["phase"], "mystic")
    try:
        import agent
        agent.SKY_NOTE = CURRENT["text"]
    except Exception:
        pass


def start(reader):
    """Called at startup. Uses today's saved sky if she has it, otherwise reads it in the background."""
    saved = reader.mem.get("sky")
    if saved and saved.get("date") == datetime.date.today().isoformat():
        apply(reader, saved)
        reader.sky_ready = threading.Event()
        reader.sky_ready.set()
        return
    reader.sky_ready = threading.Event()

    def work():
        try:
            b = basics()
            apply(reader, dict(fallback(b), date=datetime.date.today().isoformat(), basics=b))   # right away
            ready = getattr(reader, "brain_ready", None)
            if ready:
                ready.wait(120)
            sky = read_sky(reader)
            apply(reader, sky)
            reader.mem["sky"] = sky
            hist = reader.mem.setdefault("sky_history", [])
            hist.append({"date": sky["date"], "summary": sky["summary"][:200]})
            reader.mem["sky_history"] = hist[-7:]
            reader._save()
        except Exception:
            pass
        finally:
            reader.sky_ready.set()
    threading.Thread(target=work, daemon=True).start()


def element_effect(element, sky=None):
    """How today's sky treats an element: +1 helped, -1 strained, 0 neutral."""
    s = sky or CURRENT.get("sky") or {}
    return 1 if element in s.get("boost", []) else -1 if element in s.get("strain", []) else 0
