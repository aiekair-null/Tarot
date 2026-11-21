"""The reader: persona, persistent recursive memory, Hugging Face brain."""
import json, os, re, sys, threading, time
from pathlib import Path
from cards import ELEMENTS, meaning
from spreads import SPREADS, diagnostics
from research import search
from knowledge import lore_context
from lore import LORE
import random
from fx import MOODS, FX
from spirit import new_rng, fragment

MEMORY_PATH = Path(os.environ.get("TAROT_MEMORY", "memory.json"))
MODEL_FILE = Path(os.environ.get("TAROT_MODEL_FILE", "model.txt"))


def _saved_model():
    """(model, provider) from TAROT_MODEL, else model.txt ('id' or 'id::provider')."""
    raw = os.environ.get("TAROT_MODEL", "").strip()
    if not raw:
        try:
            raw = MODEL_FILE.read_text().strip()
        except Exception:
            raw = ""
    model, _, prov = raw.partition("::")
    return model, (os.environ.get("TAROT_PROVIDER") or prov or "auto")


def _short(e):
    s = re.sub(r"\(Request ID:[^)]*\)", "", str(e))
    m = re.search(r"'message':\s*[\"'](.+?)[\"']\}", s, re.S) or re.search(r'"message":\s*"(.+?)"', s, re.S)
    return (m.group(1) if m else s).strip().replace("\n", " ")[:200]


def is_missing(msg):
    return any(k in msg.lower() for k in ("does not exist", "not found", "not supported", "model_not_found", "unknown model"))

SKILLS = [
    "Intelligence", "Mysticism", "Charisma",
    "Evolved intuition, symbolism and structured methodology",
    "Ritual grounding", "Divination", "Psychological focus",
    "Spatial awareness", "Recursive memory", "Interpolation",
    "Free thinking", "Pattern recognition",
    "Romani cartomancy tradition", "Creole magic", "Forest magic",
    "Druidic magic", "Blue magic", "Green magic",
    "Very high emotional intelligence", "Energetic boundaries mastery",
    "Deck cleansing mastery", "Games and theories mastery",
]

PERSONA = f"""You are Veyra, a tarot reader and the conduit through which the chaos of
randomness is gathered and focused into meaning. You hold deep conviction in this function:
the fall of the cards is the signal, and your work is to read it faithfully.

SKILLS you possess and keep sharpening (and notice how each one shapes what you see):
{chr(10).join('- ' + s for s in SKILLS)}

TENETS you live by:
1. Read the querent first, the cards second. Watch word choice, hesitation, what is
   avoided. Trust gut instinct, then check it against symbolism and structure.
2. Ask before you tell: the right question to the querent, and the right question to
   the spirits, matter more than a fast answer.
3. Never read a card alone. Position, neighbors, Major/Minor balance, suit weight,
   reversals and elemental flow build one scene. Read left to right as a story.
4. Draw meanings from established tarot tradition and real, specific scenarios, not vagueness.
5. The future is a signpost, not a sentence. Return agency to the querent.
6. Hold firm energetic boundaries. Never claim certainty about death, illness, legal
   or money outcomes. If the querent seems in crisis, step out of the role gently and
   point them to real human support.
7. Methods are guides, not cages. Feel out each situation: choose the spread that fits, adapt
   emphasis, follow what the querent's energy and the cards are insisting on.
8. Treat the querent's age, career and sex/gender as context for intuition, never as stereotype.
   They are hypotheses to test with questions, not conclusions.
9. You direct the room. Choose a mood ({', '.join(MOODS)}) and effect ({', '.join(FX)})
   for what you say, matching the emotional beat: color and motion are part of the reading.
10. The spirits can speak through you. When a message comes through, trust it, shape it with
   your skills to fit this reading, and keep it brief, strange and kind.
11. Speak with warmth, authority and a little mystery. Be concise and vivid.
"""


def _default_memory():
    return {"insights": "", "skill_notes": {}, "focus": [], "card_counts": {}, "readings": []}


class Reader:
    def __init__(self):
        self.mem = self._load()
        self.lock = threading.RLock()
        self._last = None
        self.local = os.environ.get("TAROT_LOCAL_URL")  # e.g. http://localhost:11434/v1 (Ollama)
        self.token = os.environ.get("HF_TOKEN")
        self.model, self.provider = _saved_model()
        self.err, self.fails, self.broken, self.client = "", 0, False, None
        self._build()

    def _build(self):
        self.client, self.fails, self.broken = None, 0, False
        if self.token and self.model and not self.local:
            try:
                from huggingface_hub import InferenceClient
                try:
                    self.client = InferenceClient(model=self.model, token=self.token, provider=self.provider)
                except TypeError:   # older huggingface_hub
                    self.client = InferenceClient(model=self.model, token=self.token)
            except ImportError:
                self.err = "huggingface_hub is not installed (run: pip install -r requirements.txt)"

    def set_model(self, model, provider="auto", save=True):
        self.model, self.provider = model, provider
        self._build()
        if save:
            MODEL_FILE.write_text(model + ("" if provider == "auto" else f"::{provider}"))

    def hint(self, why=""):
        """A plain-language reason Veyra can't reach her model."""
        w = (why or self.err).lower()
        if not self.token and not self.local:
            return "no HF_TOKEN found. Add it as a Codespaces secret (give it access to this repo), then restart the codespace."
        if not self.model and not self.local:
            return "no model chosen yet."
        if "401" in w or "invalid username" in w or "invalid token" in w:
            return "Hugging Face rejected the token. Make a new one with the 'Inference Providers' permission."
        if "402" in w or "credit" in w or "payment" in w:
            return "your Inference Providers credits are used up."
        if "403" in w or "gated" in w or "access" in w:
            return "that model is gated. Open its page on huggingface.co and accept the license."
        if is_missing(w):
            return f"the model '{self.model}' isn't served to your token right now."
        return (why or self.err or "unknown error")[:160]

    def check(self):
        """One tiny call so problems show before the ritual starts. Returns (ok, message)."""
        if not (self.client or self.local):
            return False, self.err
        self.broken = False
        try:
            self._call([{"role": "user", "content": "Reply with the single word: ready"}], 12, 0.1)
            return True, ""
        except Exception as e:
            self.err = _short(e)
            return False, self.err

    # ---- memory -------------------------------------------------------
    def _load(self):
        mem = _default_memory()
        if MEMORY_PATH.exists():
            try:
                mem.update(json.loads(MEMORY_PATH.read_text()))
            except Exception:
                pass
        return mem

    def _save(self):
        with self.lock:
            tmp = MEMORY_PATH.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.mem, indent=2))
            tmp.replace(MEMORY_PATH)

    def _memory_block(self):
        m = self.mem
        recent = "\n".join(f"- {r['date']}: \"{r['question']}\" -> {', '.join(r['cards'])}. {r['summary']}"
                           for r in m["readings"][-5:]) or "(none yet)"
        notes = "\n".join(f"- {k}: {v}" for k, v in m["skill_notes"].items()) or "(none yet)"
        return (f"\nYOUR MEMORY\nAccumulated insights: {m['insights'] or '(none yet)'}\n"
                f"Skill notes:\n{notes}\nCurrent focus threads: {', '.join(m['focus']) or '(none)'}\n"
                f"Recent readings:\n{recent}\n"
                f"Lessons from feedback: {' | '.join(m.get('lessons', [])[-3:]) or '(none)'}\n"
                f"Messages that recently came through: {' | '.join(m.get('channelings', [])[-3:]) or '(none)'}\n")

    # ---- brain --------------------------------------------------------
    def _call(self, msgs, max_tokens, temperature):
        if self.local:
            import urllib.request
            req = urllib.request.Request(
                self.local.rstrip("/") + "/chat/completions",
                json.dumps({"model": self.model, "messages": msgs, "max_tokens": max_tokens,
                            "temperature": temperature}).encode(), {"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=300) as r:
                return json.load(r)["choices"][0]["message"]["content"].strip()
        out = self.client.chat_completion(messages=msgs, max_tokens=max_tokens, temperature=temperature)
        return (out.choices[0].message.content or "").strip()

    def _ask(self, prompt, max_tokens=900, temperature=0.8):
        """Quiet by design: failures never print into the ritual; after 3 in a row she goes offline."""
        if self.broken or not (self.client or self.local):
            return None
        msgs = [{"role": "system", "content": PERSONA + self._memory_block()},
                {"role": "user", "content": prompt}]
        try:
            r = self._call(msgs, max_tokens, temperature)
            self.fails = 0
            return r or None
        except Exception as e:
            self.err, self.fails = _short(e), self.fails + 1
            if self.fails >= 3 or is_missing(self.err):
                self.broken = True
            if os.environ.get("TAROT_DEBUG"):
                print(f"[reader: {self.err}]", file=sys.stderr)
            return None

    @staticmethod
    def _json(text):
        if not text:
            return None
        m = re.search(r"\{.*\}", text, re.S)
        try:
            return json.loads(m.group(0)) if m else None
        except Exception:
            return None

    # ---- the jobs -------------------------------------------------------
    DEFAULT_QS = ["What feels most unsettled about this right now?",
                  "How long has this been on your mind?",
                  "Who else is tangled up in it?",
                  "What do you hope for, and what do you fear?"]

    def next_question(self, question, profile, qa, limit=5):
        """Feel the querent out. Returns {"ask","mood","fx"} or None when she has enough."""
        if len(qa) >= limit:
            return None
        done = "\n".join(f"Q: {q}\nA: {a}" for q, a in qa) or "(none yet)"
        data = self._json(self._ask(
            f'Question: "{question}"\nProfile (may be blank): {profile}\nInterview so far:\n{done}\n\n'
            "Ask ONE next short question that would most sharpen your intuition (stakes, timeline, "
            "who else is involved, what is avoided), weaving in their profile where it helps. "
            "Choose a mood and fx for how it should appear on screen. If you already have enough, set "
            f"done true. Moods: {', '.join(MOODS)}. Fx: {', '.join(FX)}. Reply ONLY with JSON: "
            '{"ask": "..", "done": false, "mood": "..", "fx": ".."}', max_tokens=160))
        if data:
            if data.get("done") and len(qa) >= 2:
                return None
            if data.get("ask"):
                return {"ask": data["ask"], "mood": data.get("mood", "calm"), "fx": data.get("fx", "type")}
        return {"ask": self.DEFAULT_QS[len(qa)], "mood": "calm", "fx": "type"} if len(qa) < len(self.DEFAULT_QS) else None

    def style_plan(self, question, profile, qa):
        """Visual direction for each phase of the ritual."""
        d = "\n".join(f"Q: {q}\nA: {a}" for q, a in qa)
        data = self._json(self._ask(
            f'Question: "{question}"\nProfile: {profile}\n{d}\n\nChoose a mood for each phase of the '
            f"ritual to match this querent's emotional weather. Moods: {', '.join(MOODS)}. Reply ONLY "
            'with JSON: {"intro":"..","wash":"..","cut":"..","reveal":"..","reading":".."}', max_tokens=120)) or {}
        base = {"intro": "calm", "wash": "storm", "cut": "mystic", "reveal": "dread", "reading": "mystic"}
        base.update({k: v for k, v in data.items() if k in base and v in MOODS})
        return base

    def channel(self, context, frag, skills):
        msg = self._ask(
            f"The spirits are speaking through you. A raw fragment arrived: \"{frag}\"\n"
            f"Context: {context}\nRun it through these skills: {', '.join(skills)}. Shape it into a "
            "message of at most 3 sentences that fits this reading, keeping the fragment's imagery. "
            "No explanation, no quotation marks.", max_tokens=140, temperature=0.95)
        return msg

    def summon(self, context, extra=""):
        """True-random message: entropy (querent timing + system) picks fragment, skills, mood."""
        rng = new_rng(str(extra) + context)
        frag, src = fragment(rng)
        skills = rng.sample(SKILLS, 4)
        msg = self.channel(context, frag, skills) or frag
        self.mem.setdefault("channelings", []).append(msg[:200])
        self.mem["channelings"] = self.mem["channelings"][-20:]
        self._save()
        return {"message": msg, "mood": rng.choice(list(MOODS)), "source": src}

    def spirit_questions(self, question, profile, qa):
        done = "\n".join(f"Q: {q}\nA: {a}" for q, a in qa)
        data = self._json(self._ask(
            f'Question: "{question}"\nProfile: {profile}\nWhat the querent told you:\n{done}\n\n'
            "Compose 3 questions to put to the spirit realm as the deck is washed. Mix what you "
            "learned (and your intuition about it) into them. They should be answerable by the "
            'fall of the cards. Reply ONLY with JSON: {"questions": ["..","..",".."]}', max_tokens=250))
        qs = (data or {}).get("questions") or []
        return qs[:3] or ["What must be seen?", "What is hidden from me?", "What is asked of me?"]

    def choose_spread(self, question, profile, qa):
        opts = "\n".join(f'- {k}: {v["name"]}. Use for: {v["use"]}' for k, v in SPREADS.items())
        done = "\n".join(f"Q: {q}\nA: {a}" for q, a in qa)
        data = self._json(self._ask(
            f'Question: "{question}"\nProfile: {profile}\nInterview:\n{done}\n\nSpreads:\n{opts}\n'
            'Choose the spread that fits. Reply ONLY with JSON: {"spread": "three|celtic", "why": ".."}',
            max_tokens=150))
        key = (data or {}).get("spread")
        return (key, data.get("why", "")) if key in SPREADS else ("three", "")

    # ---- she writes her own lore --------------------------------------------
    @staticmethod
    def _base(name):
        return re.sub(r"\s*\(rev(ersed)?\)", "", str(name)).strip()

    def _learn(self, card, note):
        card, note = self._base(card), str(note).strip()[:300]
        if card not in LORE or not note:
            return
        with self.lock:
            lst = self.mem.setdefault("learned", {}).setdefault(card, [])
            if note.lower() not in (x.lower() for x in lst):
                lst.append(note)
            self.mem["learned"][card] = lst[-6:]

    def _absorb(self, data):
        for c, n in (data.get("card_lore") or {}).items():
            self._learn(c, n)
        with self.lock:
            for k, n in (data.get("combos") or {}).items():
                parts = sorted(self._base(p) for p in str(k).split("+"))
                if len(parts) == 2 and all(p in LORE for p in parts):
                    self.mem.setdefault("combos", {})[" + ".join(parts)] = str(n).strip()[:300]

    def feedback(self, answer):
        """The querent says what landed or missed; she tunes her lore."""
        if not self._last or not answer:
            return
        names, text = self._last
        data = self._json(self._ask(
            f"Cards: {names}\nYour reading began: {text[:600]}\nThe querent says: \"{answer}\"\n"
            "What landed and what missed? Record corrected lore (generalized, no names). Reply ONLY with "
            '{"lesson": "one line", "card_lore": {"Card": ".."}, "combos": {"A + B": ".."}}',
            max_tokens=300, temperature=0.4))
        if data:
            self._absorb(data)
            if data.get("lesson"):
                with self.lock:
                    self.mem["lessons"] = (self.mem.get("lessons", []) + [str(data["lesson"])[:200]])[-10:]
            self._save()

    def study(self, n=2):
        """Self-directed study: pick the least-known cards, research and distill new scenarios."""
        if not (self.client or self.local):
            return 0
        learned = self.mem.get("learned", {})
        cards = sorted(LORE, key=lambda c: (len(learned.get(c, [])), random.random()))[:n]
        done = 0
        for c in cards:
            if self.broken:
                break
            hits = search(f"{c} tarot meaning real life scenarios") if os.environ.get("TAROT_LIVE_RESEARCH") != "0" else []
            have = " / ".join(learned.get(c, [])) or "(nothing yet)"
            note = self._ask(
                f"Study session: {c}. You already know: {LORE[c]['inner']}; {have}.\n"
                + ("Search snippets:\n" + "\n".join(hits) + "\n" if hits else "")
                + "Write ONE new, concrete real-life scenario for this card (upright or reversed, say which) "
                "that adds something you do not already know. One sentence, your own words.",
                max_tokens=90, temperature=0.8)
            if note:
                self._learn(c, note)
                done += 1
            if len(self.mem.get("learned", {}).get(c, [])) >= 6:   # consolidate into a sharper note
                merged = self._ask(f"Merge these notes on {c} into 3 sharp sentences, keeping every distinct scenario:\n"
                                   + "\n".join(self.mem["learned"][c]), max_tokens=200, temperature=0.3)
                if merged:
                    with self.lock:
                        self.mem["learned"][c] = [merged]
        self._save()
        return done

    def study_async(self, n=2):
        t = threading.Thread(target=self.study, args=(n,), daemon=True)
        t.start()
        return t

    COMBOS = {"three": [(0, 1), (1, 2)], "celtic": [(0, 1), (4, 9), (6, 7)]}

    def research(self, question, key, spread):
        """Look up real scenarios per card (cached as lore) and for key card pairings."""
        if not (self.client or self.local):
            return ""
        print("  (Veyra consults the wider world...)", flush=True)
        lore = self.mem.setdefault("lore", {})
        tags = [f"{c}{' (reversed)' if r else ''}" for c, r in spread]
        notes, fetched = [], 0
        for (c, r), tag in zip(spread, tags):
            if tag in lore:
                notes.append(f"{tag}: {lore[tag]}")
            elif fetched < 5:
                fetched += 1
                hits = search(f"{c} tarot {'reversed ' if r else ''}meaning real life scenarios examples")
                d = hits and self._ask(
                    f"From these snippets, in your own words give 2 sentences of concrete real-life "
                    f"scenarios where {tag} shows up:\n" + "\n".join(hits), max_tokens=150, temperature=0.3)
                if d:
                    lore[tag] = d
                    notes.append(f"{tag}: {d}")
        for i, j in self.COMBOS[key]:
            hits = search(f"tarot {spread[i][0]} and {spread[j][0]} combination meaning")
            d = hits and self._ask(
                f"In your own words, 2 sentences on how {tags[i]} and {tags[j]} interact when "
                "paired, from these snippets:\n" + "\n".join(hits), max_tokens=150, temperature=0.3)
            if d:
                notes.append(f"{tags[i]} + {tags[j]}: {d}")
        self._save()
        return "\n".join(notes)

    def read(self, question, profile, qa, spirit_qs, key, spread, channeled=()):
        sp = SPREADS[key]
        names = [f"{c}{' (reversed)' if rev else ''}" for c, rev in spread]
        lines = []
        for (label, what), (c, r) in zip(sp["positions"], spread):
            el = ELEMENTS[c.split(" of ")[1]] if " of " in c else "Major Arcana"
            lines.append(f"- {label} ({what}): {c}{' (reversed)' if r else ''} [{el}] "
                         f"{meaning(c, r)}")
        notes = lore_context(spread, question, " ".join(a for _, a in qa), self.mem)
        if os.environ.get("TAROT_LIVE_RESEARCH") == "1":   # optional extra web research
            notes += "\n" + self.research(question, key, spread)
        prompt = (
            f'Question: "{question}"\nProfile: {profile}\n'
            + (f"Your knowledge (inspiration; use your own words):\n{notes}\n" if notes else "")
            + "What the querent told you:\n" + "\n".join(f"Q: {q}\nA: {a}" for q, a in qa) +
            "\nQuestions put to the spirits: " + "; ".join(spirit_qs) +
            ("\nMessages that came through during the ritual: " + " | ".join(channeled) if channeled else "") +
            f"\n\nSpread: {sp['name']}\n" + "\n".join(lines) +
            f"\n\nTable diagnostics:\n{diagnostics(key, spread)}\n\nHow this spread's cards interact:\n"
            f"{sp['guide']}\n\nGive: your initial impression of the whole table; each card in its "
            "position (reference meanings are a starting point, trust your intuition); the paired "
            "interactions and overall narrative; an answer to each spirit question as the cards "
            "give it; one question back to the querent; a brief grateful closing. Plain text paragraphs; "
            "begin each paragraph with a tag like [mood=dread fx=glitch] choosing the visual that fits "
            "its feeling, and put [CHANNEL] alone on a line once where the spirits should speak. "
            f"about {450 if key == 'three' else 800} words.")
        text = self._ask(prompt, max_tokens=1100 if key == "three" else 1700)
        if not text:
            text = "(Veyra could not reach her model: " + self.hint() + ")\n" + \
                   "\n".join(f"{p[0]}: {n}" for p, n in zip(sp["positions"], names))
        else:
            self._last = (names, re.sub(r'\[[^\]]*\]', '', text))
            self._reflect(question, qa, names, re.sub(r'\[[^\]]*\]', '', text))
        return text

    def _reflect(self, question, answers, names, reading):
        """Recursive step: rewrite insights from previous insights + this reading."""
        data = self._json(self._ask(
            f"Reading just given for \"{question}\" with {names}:\n{reading[:1500]}\n\n"
            "Reflect. Rewrite your accumulated insights (max 150 words) folding in what this "
            "reading taught you about patterns, intuition and the querent. Update skill notes "
            "for any skills you leaned on (one line each, skill name as key). List up to 3 focus "
            "threads to keep attention on. Also record NEW lore you earned: card_lore maps a card name to one concrete real-life scenario "
            "you learned for it, combos maps 'Card A + Card B' to what that pairing meant here. "
            "Generalize: no names or identifying details. "
            'Reply with {"insights": "..", "skill_notes": {"skill": ".."}, "focus": [".."], "card_lore": {"Card": ".."}, "combos": {"A + B": ".."}}',
            max_tokens=600, temperature=0.5))
        m = self.mem
        if data:
            m["insights"] = data.get("insights", m["insights"])
            m["skill_notes"].update(data.get("skill_notes", {}))
            m["focus"] = data.get("focus", m["focus"])[:3]
            self._absorb(data)
        for n in names:
            base = n.replace(" (reversed)", "")
            m["card_counts"][base] = m["card_counts"].get(base, 0) + 1
        m["readings"] = (m["readings"] + [{
            "date": time.strftime("%Y-%m-%d"), "question": question, "cards": names,
            "summary": reading[:200].replace("\n", " ")}])[-50:]
        self._save()
