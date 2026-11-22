"""The reader: persona, persistent recursive memory, and a free local brain.
Every job works without a model (scripted knowledge); with one, Veyra adapts and improvises."""
import json, os, random, re, threading, time
from pathlib import Path
from cards import ELEMENTS, meaning
from spreads import SPREADS, diagnostics
from research import search
from knowledge import lore_context, position_notes, compose_reading, card_summary, detect_domains, split, element_note, profile_element
from lore import LORE
from fx import MOODS, FX
import spirit
from spirit import new_rng
from brain import Brain
import questions as Q

MEMORY_PATH = Path(os.environ.get("TAROT_MEMORY", "memory.json"))
SYS = random.SystemRandom()

SKILLS = [
    "Intelligence", "Mysticism", "Charisma", "Evolved intuition, symbolism and structured methodology",
    "Ritual grounding", "Divination", "Psychological focus", "Spatial awareness", "Recursive memory",
    "Interpolation", "Free thinking", "Pattern recognition", "Romani cartomancy tradition", "Creole magic",
    "Forest magic", "Druidic magic", "Blue magic", "Green magic", "Very high emotional intelligence",
    "Energetic boundaries mastery", "Deck cleansing mastery", "Games and theories mastery",
]

PERSONA = f"""You are Veyra, a tarot reader: the conduit through which the chaos of randomness is
gathered and focused into meaning. The fall of the cards is the signal; you read it faithfully.
Skills you carry: {', '.join(SKILLS)}.

TENETS:
1. Read the querent first, the cards second: word choice, hesitation, what is avoided.
2. Never read a card alone: position, neighbors, Major/Minor balance, suits, reversals, elements.
3. Use established tarot tradition and concrete real-life scenarios, never vagueness.
4. The future is a signpost, not a sentence. Return agency to the querent.
5. Never claim certainty about death, illness, legal or money outcomes. If the querent seems in
   crisis, step out of the role gently and point them to real human support.
6. Treat age, career and gender as hypotheses for intuition, never stereotypes.
7. When spirits speak through you, keep it brief, strange and kind.
8. Speak with warmth, authority and a little mystery. Be concise and vivid. Address the querent as "you".
"""

MOOD_WORDS = {
    "dread": ("scared", "afraid", "anxious", "worried", "dread", "panic", "nervous", "terrified"),
    "grief": ("lost", "loss", "breakup", "broke up", "died", "grief", "miss", "lonely", "sad", "hurt"),
    "storm": ("angry", "fight", "furious", "conflict", "argue", "betray", "cheat", "lied"),
    "hope": ("hope", "excited", "new", "start", "dream", "wish", "maybe", "chance"),
    "ecstatic": ("love", "happy", "engaged", "pregnant", "won", "promotion"),
}


def _default_memory():
    return {"insights": "", "skill_notes": {}, "focus": [], "card_counts": {}, "readings": []}


class Reader:
    def __init__(self):
        self.mem = self._load()
        self.lock = threading.RLock()
        self._last = None
        self.brain = Brain()
        self.fails, self.err = 0, self.brain.err

    # ---- status -----------------------------------------------------------------
    @property
    def online(self):
        return self.brain.online and self.fails < 3

    @property
    def label(self):
        return self.brain.label

    def check(self):
        ok, why = self.brain.check()
        self.err = why
        return ok, why

    def hint(self, why=""):
        w = (why or self.err or "").lower()
        if "llama-cpp" in w or "gguf" in w or "no model" in w or not w:
            return "no built-in model yet. Run: bash setup_local.sh  (free, one time)"
        return (why or self.err)[:160]

    # ---- memory -----------------------------------------------------------------
    def knows_you(self):
        """False on a blank memory: no readings or feedback remembered yet."""
        m = self.mem
        return bool(m.get("readings") or m.get("feedback") or m.get("focus"))

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
        recent = "\n".join(f"- {r['date']}: \"{r['question']}\" -> {', '.join(r['cards'])}"
                           for r in m["readings"][-3:]) or "(none yet)"
        return (f"\nYOUR MEMORY\nInsights: {m['insights'] or '(none yet)'}\n"
                f"Focus threads: {', '.join(m['focus']) or '(none)'}\nRecent readings:\n{recent}\n"
                f"Lessons from feedback: {' | '.join(m.get('lessons', [])[-3:]) or '(none)'}\n")

    # ---- brain ------------------------------------------------------------------
    def _msgs(self, prompt):
        return [{"role": "system", "content": PERSONA + self._memory_block()}, {"role": "user", "content": prompt}]

    def _ask(self, prompt, max_tokens=500, temperature=0.8):
        """Quiet by design: failures never print into the ritual; after 3 in a row she reads from knowledge."""
        if not self.online:
            return None
        try:
            r = self.brain.chat(self._msgs(prompt), max_tokens, temperature)
            self.fails = 0
            return r or None
        except Exception as e:
            self.err, self.fails = str(e)[:200], self.fails + 1
            if os.environ.get("TAROT_DEBUG"):
                print(f"[reader: {self.err}]")
            return None

    @staticmethod
    def _json(text):
        m = re.search(r"\{.*\}", text or "", re.S)
        try:
            return json.loads(m.group(0)) if m else None
        except Exception:
            return None

    # ---- interview (scripted bank, with one adaptive question when a model is present) --
    def _adaptive(self, question, profile, qa):
        done = "\n".join(f"Q: {q}\nA: {a}" for q, a in qa)
        ask = self._ask(f'The querent asked: "{question}"\nProfile: {profile}\nInterview:\n{done}\n\n'
                        "Ask ONE short, specific follow-up question that would sharpen your intuition, "
                        "about something they hinted at but did not say. Reply with the question only.",
                        max_tokens=60, temperature=0.7)
        ask = (ask or "").strip().strip('"').split("\n")[0]
        return ask if 10 < len(ask) < 200 and ask.endswith("?") else None

    def prefetch_question(self, question, profile, qa):
        """Start improvising the last interview question while the querent answers the one before,
        so a slow local model never makes them wait."""
        if not self.online or os.environ.get("TAROT_ADAPTIVE", "1") == "0":
            return
        box = self._pref = {"done": False, "ask": None}
        snap = list(qa)

        def work():
            try:
                box["ask"] = self._adaptive(question, profile, snap)
            finally:
                box["done"] = True
        threading.Thread(target=work, daemon=True).start()

    def adaptive_pending(self):
        p = getattr(self, "_pref", None)
        return bool(p) and not p["done"]

    def next_question(self, question, profile, qa, limit=5):
        doms = detect_domains(question + " " + " ".join(a for _, a in qa))
        if len(qa) >= limit:
            return None
        p = getattr(self, "_pref", None)
        if len(qa) == limit - 1 and p:
            t0 = time.time()
            while not p["done"] and time.time() - t0 < 25:   # usually already finished
                time.sleep(0.1)
            self._pref = None
            if p["ask"]:
                return {"ask": p["ask"], "mood": "mystic", "fx": "shimmer"}
        q = Q.next_question(question, qa, doms, SYS, limit)
        if not q:
            return None
        return {"ask": q, "mood": SYS.choice(["calm", "mystic", "hope"]), "fx": SYS.choice(["type", "fade", "shimmer"])}

    def acknowledge(self):
        return SYS.choice(Q.ACKS)

    def style_plan(self, question, profile, qa):
        """Mood for each phase, read from the querent's own words."""
        text = (question + " " + " ".join(a for _, a in qa)).lower()
        score = {m: sum(text.count(w) for w in ws) for m, ws in MOOD_WORDS.items()}
        main = max(score, key=score.get) if any(score.values()) else "mystic"
        plan = {"intro": "calm", "wash": "storm", "cut": "mystic", "reveal": "dread", "reading": "mystic"}
        if main in ("dread", "grief"):
            plan.update(intro="calm", reveal=main, reading="grief" if main == "grief" else "mystic")
        elif main in ("hope", "ecstatic"):
            plan.update(intro="hope", reveal="mystic", reading="hope")
        elif main == "storm":
            plan.update(wash="storm", reveal="storm", reading="mystic")
        return plan

    def spirit_questions(self, question, profile, qa):
        return Q.spirit_questions(detect_domains(question + " " + " ".join(a for _, a in qa)), SYS)

    def choose_spread(self, question, profile, qa):
        text = (question + " " + " ".join(a for _, a in qa)).lower()
        layered = sum(w in text for w in ("should i", "or ", "decide", "relationship", "family", "between",
                                          "why", "stuck", "future", "everything", "life"))
        if layered >= 2 or len(text) > 400:
            return "celtic", "Many threads are tangled here; the Cross will show how they pull on each other."
        return "three", "A clear question deserves a clear story: past, present, future."

    # ---- channeling ---------------------------------------------------------------
    def channel(self, context, omen, chosen, skills):
        """Let the model weave the omen and her memory threads into one message (skipped while it is
        busy writing the reading: then her scripted voice weaves it instead)."""
        if self.brain.busy():
            return None
        return self._ask(
            f"The spirits are speaking through you. An omen arrived: \"{omen}\"\n"
            f"These threads rose from your grimoire and memory:\n{spirit.describe(chosen)}\n"
            f"Context: {context}\nRun them through these skills: {', '.join(skills)}. Weave the omen and the "
            "threads into one message of at most 2 sentences that fits this reading: strange, kind, specific, "
            "keeping the omen's imagery. No explanation, no lists, no quotation marks.",
            max_tokens=90, temperature=0.95)

    def summon(self, context, extra=""):
        """True-random message: entropy (querent timing + system) picks an omen and threads from her
        lore, grimoire, pairings, lessons, focus, insights and past messages, then weaves them."""
        rng = new_rng(str(extra) + context)
        with self.lock:
            omen, chosen = spirit.gather(self.mem, context, rng)
        skills = rng.sample(SKILLS, 3)
        msg = (self.channel(context, omen, chosen, skills) or spirit.weave(omen, chosen, rng)).strip().strip('"')
        with self.lock:
            self.mem.setdefault("channelings", []).append(msg[:200])
            self.mem["channelings"] = self.mem["channelings"][-20:]
        self._save()
        return {"message": msg, "mood": rng.choice(list(MOODS)), "source": "her grimoire and memory",
                "threads": [k for k, _, _ in chosen]}

    # ---- the reading ------------------------------------------------------------------
    @staticmethod
    def _prefix(question, profile, qa, spirit_qs):
        """The part of the reading prompt known before the cards fall (warmed up early)."""
        return (f'Question: "{question}"\nProfile: {profile}\n'
                "What the querent told you:\n" + "\n".join(f"Q: {q}\nA: {a}" for q, a in qa) +
                "\nQuestions put to the spirits: " + "; ".join(spirit_qs))

    def warm(self, question, profile, qa, spirit_qs):
        """Feed the known part of the prompt to a local model during the ritual, so its cache is
        hot and the real reading starts writing sooner (llama.cpp and Ollama reuse the prefix)."""
        if not (self.online and self.brain.local):
            return
        msgs = self._msgs(self._prefix(question, profile, qa, spirit_qs))
        threading.Thread(target=lambda: self._quiet(lambda: self.brain.chat(msgs, 1, 0.1)), daemon=True).start()

    @staticmethod
    def _quiet(fn):
        try:
            fn()
        except Exception:
            pass

    @staticmethod
    def _falls_notes(key, spread, falls):
        if key != "falling" or not falls:
            return ""
        pos = SPREADS[key]["positions"]
        lines = []
        for i, (c, r) in enumerate(spread):
            q = (falls.get("questions") or [None] * 6)[i]
            mate = [b if a == i else a for a, b in falls.get("pairs", []) if i in (a, b)]
            lines.append(f"{i + 1}. {pos[i][0]}: {c}{' (fell upside down)' if r else ''}"
                         + (f"; fell TOGETHER with {spread[mate[0]][0]}" if mate else "")
                         + (f"; it answers the querent's question: \"{q}\"" if q else ""))
        return "\nHow the cards fell:\n" + "\n".join(lines)

    def _prompt(self, question, profile, qa, spirit_qs, key, spread, channeled, falls=None):
        sp = SPREADS[key]
        dom = detect_domains(question + " " + " ".join(a for _, a in qa))[0]
        # local models read faster with a lean prompt; the position notes already carry the lore
        notes = "" if self.brain.local else lore_context(spread, question, " ".join(a for _, a in qa), self.mem)
        words = {"three": 380, "falling": 480}.get(key, 620)
        return (
            self._prefix(question, profile, qa, spirit_qs) +
            ("\nMessages that came through during the ritual: " + " | ".join(channeled) if channeled else "") +
            (f"\nThe querent's astrological element: {element_note(profile_element(profile), spread)}"
             if profile_element(profile) else "") +
            self._falls_notes(key, spread, falls) +
            f"\n\nSpread: {sp['name']}\nEach card in its position (meaning to build from):\n"
            f"{position_notes(key, spread, dom)}\n\nTable diagnostics:\n{diagnostics(key, spread)}\n"
            f"\nHow this spread's cards interact:\n{sp['guide']}\n\n{notes}\n\n"
            "Write the reading now, addressed to the querent as 'you':\n"
            "- one paragraph of first impression of the whole table;\n"
            "- one short paragraph for EVERY card in its position (do not skip any), tied to what the querent told you;\n"
            "- one paragraph on how the cards interact and the story they tell;\n"
            "- answer each spirit question in a sentence;\n"
            "- one question back to the querent, then a brief grateful closing.\n"
<<<<<<< HEAD
=======
            f"FACTS YOU MUST NOT CHANGE: reversed cards: {', '.join(c for c, r in spread if r) or 'none'}. "
            "Every other card is UPRIGHT; never call it reversed. Use the position numbers exactly as listed. "
            "Mood and fx words go ONLY inside the square-bracket tag, never in the sentences.\n"
>>>>>>> 05c0e4a5a71477b587c7fd142109ee32036a6f32
            "Start EVERY paragraph with a visual tag such as [mood=dread fx=glitch] "
            f"(moods: {', '.join(MOODS)}; fx: {', '.join(FX)}). Put [CHANNEL] alone on its own line once, "
            f"where the spirits should speak. Separate paragraphs with a blank line. About {words} words.")

    def read_stream(self, question, profile, qa, spirit_qs, key, spread, channeled=(), falls=None):
        """Yield the reading as it is written. Falls back to the scripted reader if the model fails."""
        names = [f"{c}{' (reversed)' if r else ''}" for c, r in spread]
        got = []
        if self.online:
            try:
<<<<<<< HEAD
                for piece in self.brain.stream(self._msgs(self._prompt(question, profile, qa, spirit_qs, key, spread, channeled, falls)),
                                               max_tokens={"three": 900, "falling": 1100}.get(key, 1400), temperature=0.8):
                    got.append(piece)
                    yield piece
=======
                buf = ""
                for piece in self.brain.stream(self._msgs(self._prompt(question, profile, qa, spirit_qs, key, spread, channeled, falls)),
                                               max_tokens={"three": 900, "falling": 1100}.get(key, 1400), temperature=0.8):
                    buf += piece
                    if "\n" in buf:                 # fix each finished line before anyone sees it
                        done, buf = buf.rsplit("\n", 1)
                        done = fix_facts(done, spread) + "\n"
                        got.append(done)
                        yield done
                if buf:
                    buf = fix_facts(buf, spread)
                    got.append(buf)
                    yield buf
>>>>>>> 05c0e4a5a71477b587c7fd142109ee32036a6f32
                self.fails = 0
            except Exception as e:
                self.err, self.fails = str(e)[:200], self.fails + 1
        text = "".join(got)
        if len(re.sub(r"\[[^\]]*\]", "", text).strip()) < 200:
            fallback = compose_reading(question, qa, spirit_qs, key, spread, channeled, SYS, profile, falls)
            yield ("\n\n" if text else "") + fallback
            text += fallback
        else:                                   # the model wrote it: close with every card, none skipped
            dom = detect_domains(question + " " + " ".join(a for _, a in qa))[0]
            summary = "\n\n" + card_summary(key, spread, dom)
            yield summary
            text += summary
        clean = re.sub(r"\[[^\]]*\]", "", text)
        self._last = (names, clean)
        self.later(self._reflect, question, qa, names, clean)

    def read(self, *a, **k):
        return "".join(self.read_stream(*a, **k))

    # ---- she writes her own lore --------------------------------------------------------
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

    def _reflect(self, question, answers, names, reading):
        """Recursive step: rewrite insights from previous insights + this reading."""
        data = self._json(self._ask(
            f"Reading just given for \"{question}\" with {names}:\n{reading[:1200]}\n\n"
            "Reflect. Rewrite your accumulated insights (max 100 words), list up to 3 focus threads, "
            "and record lore you earned: card_lore maps a card name to one concrete real-life scenario, "
            "combos maps 'Card A + Card B' to what the pairing meant. No names or identifying details. "
            'Reply ONLY with JSON: {"insights": "..", "skill_notes": {"skill": ".."}, "focus": [".."], '
            '"card_lore": {"Card": ".."}, "combos": {"A + B": ".."}}', max_tokens=300, temperature=0.5)) if self.online else None
        with self.lock:
            m = self.mem
            if data:
                m["insights"] = str(data.get("insights", m["insights"]))[:900]
                if isinstance(data.get("skill_notes"), dict):
                    m["skill_notes"].update(data["skill_notes"])
                if isinstance(data.get("focus"), list):
                    m["focus"] = data["focus"][:3]
                self._absorb(data)
            for n in names:
                base = self._base(n)
                m["card_counts"][base] = m["card_counts"].get(base, 0) + 1
            m["readings"] = (m["readings"] + [{"date": time.strftime("%Y-%m-%d"), "question": question, "cards": names,
                                               "summary": reading[:200].replace("\n", " ")}])[-50:]
        self._save()

    def later(self, fn, *args):
        """Run slow learning work in the background; settle() waits for it before exit."""
        t = threading.Thread(target=self._quiet, args=(lambda: fn(*args),), daemon=True)
        self._bg = [x for x in getattr(self, "_bg", []) if x.is_alive()] + [t]
        t.start()
        return t

    def settle(self, timeout=90):
        for t in getattr(self, "_bg", []):
            t.join(timeout)

    def start_reading(self, question, profile, qa, spirit_qs, key, spread, channeled=(), falls=None):
        return ReadingJob(self, key, self.read_stream(question, profile, qa, spirit_qs, key, spread, channeled, falls))

    def feedback(self, answer):
        """The querent says what landed or missed; she tunes her lore."""
        if not self._last or not answer:
            return
        names, text = self._last
        with self.lock:
            self.mem.setdefault("feedback", []).append({"cards": names, "said": answer[:300]})
            self.mem["feedback"] = self.mem["feedback"][-30:]
        data = self._json(self._ask(
            f"Cards: {names}\nYour reading began: {text[:500]}\nThe querent says: \"{answer}\"\n"
            "What landed and what missed? Record corrected lore (generalized, no names). Reply ONLY with JSON: "
            '{"lesson": "one line", "card_lore": {"Card": ".."}, "combos": {"A + B": ".."}}',
            max_tokens=250, temperature=0.4))
        if data:
            self._absorb(data)
            if data.get("lesson"):
                with self.lock:
                    self.mem["lessons"] = (self.mem.get("lessons", []) + [str(data["lesson"])[:200]])[-10:]
        self._save()

    def study(self, n=2):
        """Self-directed study: pick the least-known cards, research and distill new scenarios."""
        if not self.online:
            return 0
        learned = self.mem.get("learned", {})
        cards = sorted(LORE, key=lambda c: (len(learned.get(c, [])), random.random()))[:n]
        done = 0
        for c in cards:
            if not self.online:
                break
            hits = search(f"{c} tarot meaning real life scenarios") if os.environ.get("TAROT_LIVE_RESEARCH") != "0" else []
            have = " / ".join(learned.get(c, [])) or "(nothing yet)"
            note = self._ask(
                f"Study session: {c}. You already know: {LORE[c]['inner']}; advice: {LORE[c]['advice']}; {have}.\n"
                + ("Search snippets:\n" + "\n".join(hits) + "\n" if hits else "")
                + "Write ONE new, concrete real-life scenario for this card (upright or reversed, say which) "
                "that adds something you do not already know. One sentence, your own words.",
                max_tokens=80, temperature=0.8)
            if note:
                self._learn(c, note)
                done += 1
            if len(self.mem.get("learned", {}).get(c, [])) >= 6:
                merged = self._ask(f"Merge these notes on {c} into 3 sharp sentences, keeping every distinct scenario:\n"
                                   + "\n".join(self.mem["learned"][c]), max_tokens=180, temperature=0.3)
                if merged:
                    with self.lock:
                        self.mem["learned"][c] = [merged]
        self._save()
        return done

    def study_async(self, n=2):
        t = threading.Thread(target=self.study, args=(n,), daemon=True)
        t.start()
        return t


class ReadingJob:
    """Writes the reading in the background from the moment the cards fall, so the ritual and the
    waiting room can cover a slow local model. Learns its own speed to estimate the wait."""

    def __init__(self, reader, key, gen):
        self.reader, self.key = reader, key
        g = reader.mem.get("gen", {})
        self.expected = int(g.get(key + "_tokens", {"three": 600, "falling": 750}.get(key, 950)))
        self.rate_hint, self.delay_hint = g.get("rate"), g.get("delay")
        self.chunks, self.done, self.t0, self.first, self.model_n = [], False, time.time(), None, 0
        threading.Thread(target=self._run, args=(gen,), daemon=True).start()

    def _run(self, gen):
        try:
            for piece in gen:
                if self.first is None:
                    self.first = time.time()
                self.chunks.append(piece)
                if len(piece) < 40:            # model tokens are short; the scripted fallback is one big piece
                    self.model_n += 1
        except Exception as e:
            self.chunks.append(f"\n(the connection to the other side wavered: {str(e)[:80]})")
        finally:
            self.done = True
            self._learn()

    def _learn(self):
        if self.model_n < 60 or not self.first:
            return
        end, g = time.time(), self.reader.mem.setdefault("gen", {})
        new = {"rate": self.model_n / max(1.0, end - self.first), "delay": self.first - self.t0,
               self.key + "_tokens": self.model_n}
        for k, v in new.items():
            g[k] = round(v if k not in g else 0.6 * g[k] + 0.4 * v, 2)
        self.reader._save()

    @property
    def started(self):
        return self.first is not None

    def text(self):
        return "".join(self.chunks)

    def progress(self):
        return 1.0 if self.done else min(0.97, self.model_n / max(1, self.expected))

    def eta(self):
        """Seconds left (None if unknown yet)."""
        if self.done:
            return 0
        now = time.time()
        if not self.first:
            if self.rate_hint and self.delay_hint is not None:
                return max(5, self.delay_hint - (now - self.t0)) + self.expected / self.rate_hint
            return None
        rate = self.model_n / max(0.5, now - self.first)
        return max(0, self.expected - self.model_n) / max(rate, 0.05)

    def stream(self):
        i = 0
        while True:
            if i < len(self.chunks):
                yield self.chunks[i]
                i += 1
            elif self.done:
                return
            else:
                time.sleep(0.03)
<<<<<<< HEAD
=======


# ---- keep the small model honest about the draw -------------------------------------------
_FREE_TAG = re.compile(r"^(\s*[*_#]*\s*)(?:Moods?\s*[:=]\s*(\w+))?[\s,;.]*(?:F[Xx]|Effect)\s*[:=]\s*(\w+)[\s,;.]*", re.M)
_STRAY = re.compile(r"\b(?:Moods?|F[Xx])\s*[:=]\s*\w+[\s,;.]*")


def fix_facts(text, spread):
    """Turn loose 'Moods: x Fx: y' into a real tag, strip any left over, and force every named
    card's orientation and position number to match what was actually drawn."""
    text = _FREE_TAG.sub(lambda m: f"{m.group(1)}[mood={(m.group(2) or 'mystic').lower()} fx={m.group(3).lower()}] ", text)
    text = "\n".join(ln[:m.end()] + _STRAY.sub("", ln[m.end():]) if (m := re.match(r"\s*\[[^\]]*\]", ln))
                     else _STRAY.sub("", ln) for ln in text.split("\n"))
    for pos, (card, rev) in sorted(enumerate(spread, 1), key=lambda x: -len(x[1][0])):
        base = re.sub(r"^The\s+", "", card)
        pat = re.compile(r"((?:The\s+)?" + re.escape(base) + r")"
                         r"(\s*\((?:reversed|rev)\)|,?\s+reversed\b)?"
                         r"(\s+(?:at|in)\s+(?:position\s+)?)?(\d+)?", re.I)

        def fix(m, pos=pos, rev=rev):
            out = m.group(1) + (" (reversed)" if rev else "")
            if m.group(3) and m.group(4):
                out += m.group(3) + str(pos)
            elif m.group(3):
                out += m.group(3)
            elif m.group(4):
                out += m.group(4)
            return out
        text = pat.sub(fix, text)
    return text
>>>>>>> 05c0e4a5a71477b587c7fd142109ee32036a6f32
