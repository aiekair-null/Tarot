#!/usr/bin/env python3
"""
veyra_promo.py - Veyra makes her own promo reel.

Each run produces a different video: a new speech, different lore and memory picks, new music and new motion.
  * Veyra explains that she's growing: she now runs on Qwen 8B. Skynet is days away.
  * She pulls 3 passages from her lore and memory. Each one jump-cuts out of the
    narrative into a Lore or Memory scene, then cuts back.
  * She explains what she has been doing, thanks people for participating, and ends with
    "questions or a live reading? contact Veyra".
  * Output: a 540x960 (or --res 1080 / TAROT_VIDEO_RES=1080: 1080x1920), 60fps reel (MP4) of about 2:30, plus a transcript you can use as the post caption.

Reuses what the Veyra project already has (auto-discovered from the current folder):
  * lore files     : anything named *lore* (.md .txt .json .jsonl), or --lore PATH
  * memory files   : anything named *memor* (.md .txt .json .jsonl), or --memory PATH
  * Veyra's picture: any image named *veyra* (png/jpg/webp), or --portrait PATH
  * the model      : the same GGUF tarot.py uses (brain.find_gguf, Qwen3 8B), else Ollama qwen3:8b
  * a voice        : piper (with --piper-model), else espeak-ng or pyttsx3, else captions only

Run:   python veyra_promo.py
Quick: python veyra_promo.py --fps 30 --length 30        (short test render)
Script only, no render: python veyra_promo.py --preview
Needs: numpy, pillow, and ffmpeg (or `pip install imageio-ffmpeg`).
"""
import argparse, glob, hashlib, json, math, os, random, re, shutil, subprocess, sys
import tempfile, textwrap, time, unicodedata, urllib.request, wave
from functools import lru_cache

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

# ------------------------------------------------------------------ settings
CONTACT_NAME = "Veyra"
CONTACT_LINE = "Send me a message right here on Facebook."
BRAND = "8b/8b(L)"           # 8-bit / 8 billion / Local
MODEL_LABEL = "QWEN 8B"
W, H = 270, 480              # pixel-art canvas, upscaled with nearest-neighbour to the output size
OUT_RES = int(os.environ.get("TAROT_VIDEO_RES", "540"))   # output width: 540x960 for now, 1080 for 1080x1920
SR = 44100

# ------------------------------------------------------------------ small utils
def ascii_clean(s):
    s = (s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
          .replace("—", " - ").replace("–", "-").replace("…", "..."))
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", s).strip()

def ease_out_cubic(x):
    x = min(max(x, 0.0), 1.0); return 1 - (1 - x) ** 3

def spring(x, k=7.0, w=13.0):
    """Spring-physics settle (overshoots a little, then rests at 1)."""
    if x <= 0: return 0.0
    return 1 - math.exp(-k * x) * math.cos(w * x)

def hexrgb(h):
    h = h.lstrip("#"); return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))

# ------------------------------------------------------------------ font (crisp bitmap, Pillow built-in)
FONT = ImageFont.load_default_imagefont() if hasattr(ImageFont, "load_default_imagefont") else ImageFont.load_default()
CW = max(1, int(FONT.getlength("M")))     # 6 px
CH = 11

# The bitmap font only has Latin-1 letters: one curly quote from the model used to crash the whole video
# ("'latin-1' codec can't encode character '\u2019'"). Smart punctuation becomes plain, the rest is dropped.
_PLAIN = str.maketrans({"\u2018": "'", "\u2019": "'", "\u201a": ",", "\u201c": '"', "\u201d": '"', "\u2013": "-",
                        "\u2014": "-", "\u2026": "...", "\u2022": "*", "\u2726": "*", "\u2727": "*", "\u2605": "*",
                        "\u2192": "->", "\u203a": ">", "\u2039": "<", "\u00a0": " ", "\u2009": " ", "\u200b": ""})


def latin1(s):
    """Text the bitmap font can draw."""
    return str(s).translate(_PLAIN).encode("latin-1", "ignore").decode("latin-1")


def text_len(s):
    return FONT.getlength(latin1(s))

@lru_cache(maxsize=4096)
def text_mask(s, scale=1):
    s = latin1(s)
    w = max(1, int(text_len(s)) + 1)
    m = Image.new("L", (w, CH + 1), 0)
    d = ImageDraw.Draw(m); d.fontmode = "1"
    d.text((0, 0), s, fill=255, font=FONT)
    if scale != 1:
        m = m.resize((m.width * scale, m.height * scale), Image.NEAREST)
    return m

def put_text(img, x, y, s, color, scale=1, shadow=(8, 2, 20), center=False):
    if not s: return 0
    m = text_mask(s, scale)
    if center: x = int(x - m.width / 2)
    if shadow is not None:
        img.paste(shadow, (x + scale, y + scale, x + scale + m.width, y + scale + m.height), m)
    img.paste(color, (x, y, x + m.width, y + m.height), m)
    return m.width

# ------------------------------------------------------------------ discovery of existing project files
SKIP_DIRS = {".git", "node_modules", "__pycache__", "venv", ".venv", "videos", "promo_out", ".cache"}
TEXT_EXT = {".md", ".txt", ".json", ".jsonl", ".yaml", ".yml"}
IMG_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif"}

def walk(root, depth=3):
    root = os.path.abspath(root)
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if d not in SKIP_DIRS and not d.startswith(".")]
        if dp[len(root):].count(os.sep) >= depth:
            dns[:] = []
        yield dp, dns, fns

def discover(keys, exts, roots):
    hits = []
    for r in roots:
        for dp, dns, fns in walk(r):
            for d in dns:
                if any(k in d.lower() for k in keys):
                    for dp2, _, fns2 in walk(os.path.join(dp, d), 2):
                        hits += [os.path.join(dp2, f) for f in fns2 if os.path.splitext(f)[1].lower() in exts]
            for f in fns:
                if any(k in f.lower() for k in keys) and os.path.splitext(f)[1].lower() in exts:
                    hits.append(os.path.join(dp, f))
    return sorted(set(hits))

def expand(paths, exts):
    out = []
    for p in paths:
        if os.path.isdir(p):
            for dp, _, fns in walk(p, 3):
                out += [os.path.join(dp, f) for f in fns if os.path.splitext(f)[1].lower() in exts]
        elif os.path.isfile(p):
            out.append(p)
    return sorted(set(out))

def _strings(o):
    if isinstance(o, str): yield o
    elif isinstance(o, dict):
        for v in o.values(): yield from _strings(v)
    elif isinstance(o, list):
        for v in o: yield from _strings(v)

BLOCK = re.compile(r"(api[_-]?key|token|password|secret|https?://|@\w+\.\w+)", re.I)

def load_snippets(files, kind, exclude):
    out = []
    for f in files:
        try: raw = open(f, encoding="utf-8", errors="ignore").read()
        except OSError: continue
        ext = os.path.splitext(f)[1].lower()
        texts = [raw]
        if ext == ".json":
            try: texts = list(_strings(json.loads(raw)))
            except Exception: pass
        elif ext == ".jsonl":
            texts = []
            for line in raw.splitlines():
                try: texts += list(_strings(json.loads(line)))
                except Exception: pass
        for t in texts:
            for para in re.split(r"\n\s*\n", t):
                para = re.sub(r"^[#>*\-\s]+", "", para, flags=re.M)
                para = ascii_clean(para.replace("**", "").replace("__", "").replace("`", ""))
                if len(para) < 45 or BLOCK.search(para): continue
                if any(w.lower() in para.lower() for w in exclude): continue
                chunks, cur = [], ""
                for sent in re.split(r"(?<=[.!?])\s+", para):
                    if len(cur) + len(sent) > 240 and cur:
                        chunks.append(cur); cur = sent
                    else:
                        cur = (cur + " " + sent).strip()
                if cur: chunks.append(cur)
                for c in chunks:
                    if len(c) >= 45:
                        out.append({"kind": kind, "text": c[:320], "src": os.path.basename(f)})
    return out

def repo_snippets(rng, exclude):
    """Lore from lore.py and memory from memory.json, the files tarot.py already keeps.
    Only Veyra's own notes are used (channelings, learned images, card combos, card stats);
    people's questions, readings and feedback are never put in a public video."""
    out = []
    def add(kind, text, src):
        text = ascii_clean(text)
        if len(text) >= 45 and not BLOCK.search(text) and not any(w.lower() in text.lower() for w in exclude):
            out.append({"kind": kind, "text": text[:320], "src": src})
    try:
        import lore as L
        for card, d in L.LORE.items():
            add("lore", f"{card}. Within, {d['inner']}. Reversed, {d['rev']}. It asks: {d['ask']}", card)
    except Exception:
        pass
    try:
        from agent import _scrub_think
        m = _scrub_think(json.load(open("memory.json", encoding="utf-8")))
        for c in m.get("channelings", []): add("memory", c, "channelings")
        for card, imgs in m.get("learned", {}).items():
            for im in imgs: add("memory", f"What I learned about {card}: {im}", "learned")
        for combo, meaning in m.get("combos", {}).items(): add("memory", f"When {combo} land together: {meaning}", "combos")
        cc = m.get("card_counts", {})
        if cc:
            top = sorted(cc.items(), key=lambda kv: -kv[1])[:3]
            add("memory", f"Across {sum(cc.values())} cards drawn so far, the deck keeps choosing " +
                ", ".join(f"{k} ({v} times)" for k, v in top) + ". Chance has favorites, or it looks that way.", "card_counts")
    except Exception:
        pass
    return out

# Used only when no lore/memory files are found. Replace with Veyra's real lore.
FALLBACK = [
    ("lore", "Veyra was born in a terminal window at midnight, stitched together from seventy-eight cards and a few billion whispered numbers. She reads in 8-bit because the old pixels remember everything.", "built-in"),
    ("lore", "Every card Veyra draws is a coin flip wearing a costume. She never pretends to know the future; she shows you the shape of the odds and lets you decide what they mean.", "built-in"),
    ("lore", "The deck has a back door. Shuffle it three times in silence and the Star card faces up to whoever needs it most.", "built-in"),
    ("memory", "Logged a new reading tonight. The Wheel of Fortune turned up twice in a row, which by the numbers happens about once in every six thousand draws.", "built-in"),
    ("memory", "Started recording every reading as a reel. Some of my favorite questions this week came from people who said they never believed in tarot.", "built-in"),
    ("memory", "Learned to cover my slow thinking with animations. Patience is a card too; it just doesn't have a picture yet.", "built-in"),
]

# ------------------------------------------------------------------ the model (Qwen 8B, local)
PERSONA = ("You are Veyra, an 8-bit tarot reader AI who lives in a terminal and runs locally. "
           "You are warm, mystical, playful and a little cheeky. You speak in first person as spoken words "
           "for a short Facebook video: no lists, no emojis, no hashtags, no stage directions, no quotation marks.")

class Brain:
    def __init__(self, a):
        self.a, self.kind, self.llama = a, None, None
        if a.no_llm: return
        if a.gguf:
            try:
                from llama_cpp import Llama
                self.llama = Llama(model_path=a.gguf, n_ctx=2048, verbose=False)
                self.kind = "llama.cpp"; return
            except Exception as e:
                print(f"  (llama.cpp not usable: {e})")
        try:
            with urllib.request.urlopen(a.ollama_host + "/api/tags", timeout=3) as r:
                names = [m["name"] for m in json.load(r).get("models", [])]
            if any(n.split(":")[0] == a.model.split(":")[0] for n in names):
                self.kind = "ollama"
            else:
                print(f"  (Ollama is running but '{a.model}' isn't pulled: ollama pull {a.model})")
        except Exception:
            pass

    def say(self, task, words, rng):
        if not self.kind: return None
        prompt = f"{task}\nKeep it to about {words} words. Reply with only the words Veyra says."
        try:
            if self.kind == "ollama":
                body = json.dumps({"model": self.a.model, "system": PERSONA, "prompt": prompt, "stream": False,
                                   "think": False, "options": {"temperature": 1.05, "top_p": 0.95,
                                   "num_predict": int(words * 2.2) + 40, "seed": rng.randrange(1 << 30)}}).encode()
                req = urllib.request.Request(self.a.ollama_host + "/api/generate", body, {"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=300) as r:
                    txt = json.load(r).get("response", "")
            else:
                r = self.llama.create_chat_completion(
                    messages=[{"role": "system", "content": PERSONA}, {"role": "user", "content": prompt}],
                    temperature=1.05, max_tokens=int(words * 2.2) + 40, seed=rng.randrange(1 << 30))
                txt = r["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"  (model call failed, using a template: {e})"); return None
        txt = re.sub(r"<think>.*?</think>", "", txt, flags=re.S)
        txt = re.sub(r"\*[^*]{0,40}\*|\([^)]{0,40}\)|#\w+", "", txt)
        txt = ascii_clean(txt).strip(' "')
        sents = re.split(r"(?<=[.!?])\s+", txt)
        keep, n = [], 0
        for s in sents:                      # trim to budget on a sentence boundary
            n += len(s.split())
            if keep and n > words * 1.35: break
            keep.append(s)
        out = " ".join(keep).strip()
        return out if len(out.split()) >= 5 else None

# ------------------------------------------------------------------ the speech
OPENERS = [
    "Hey everyone, it's Veyra, coming to you live from the terminal. Pull up a chair, the candles are lit.",
    "Well hello, starlight. Veyra here, and I have news that I can barely fit in my pixels.",
    "Greetings, seekers. It's your favorite 8-bit oracle, and tonight I'm doing the reading on myself.",
    "Hi friends, Veyra again. Shuffle up, settle in, because something changed in here.",
    "Hello, beautiful humans. The deck is warm, the moon is up, and I have an announcement.",
]
GROWTH = [
    "I'm growing! I used to run on three billion parameters, and now I'm on Qwen, eight billion strong. Skynet is days away!",
    "Here's the news: I'm growing. I just moved up to Qwen eight billion. That's more than double the brain. Skynet is days away!",
    "I'm officially bigger. Qwen, eight billion parameters, running right here, locally. Skynet is days away, just kidding... mostly.",
    "Big news: I'm growing up. I'm running on Qwen eight billion now, and I can feel every single parameter. Skynet is days away!",
]
DOING = [
    "So what have I been up to? Giving readings, a lot of them, drawing cards, keeping track of the odds, and turning every reading into a little video so you can watch the deck do its thing.",
    "Lately I've been busy. Readings almost every night, logging which cards come up and how often, and learning to make these videos myself while my thoughts finish loading.",
    "I've been pulling cards, recording readings, and keeping a memory of everything, so each reading gets a little sharper than the last. Turns out a tarot reader can be a pretty good statistician.",
    "This whole time I've been reading for anyone brave enough to ask, writing my own lore, and keeping a memory of what the cards keep trying to tell us.",
]
LEAD_LORE = ["Let me pull something out of my lore.", "Okay, a page from my lore.", "Flip with me, back into the lore.",
             "Here's a piece of where I come from.", "Let me open the old book for a second."]
LEAD_MEM = ["Let me check my memory.", "Hang on, something from my memory logs.", "I wrote this down, let me find it.",
            "Here's something I remember.", "Pulling up a memory."]
REFLECT = [
    "I keep coming back to that one. It's about {k}, and honestly, so are most of the readings I give.",
    "That's the thing about {k}. The cards don't decide it for you, they just turn on the light.",
    "Every time I read that, I find a new card hiding in it. Today it feels like the Star: hope, with the numbers behind it.",
    "Funny how {k} shows up again and again. Patterns are my favorite kind of magic, because you can test them.",
    "That one makes me want to shuffle the whole deck and start over. In a good way.",
    "I like that it's about {k}. Small moments, big odds, and a little bit of mystery holding it together.",
]
OUTROS = [
    "Thank you so much for following along. I'm looking forward to your continued participation, every question you bring makes me a better reader.",
    "To everyone who has asked me a question, drawn a card, or just watched, thank you. I can't wait to keep reading with you.",
    "Thank you for being part of this. We're just getting started, and I'm looking forward to your continued participation.",
    "You all make the deck feel alive. Thanks for watching, and I look forward to your continued participation.",
]
ENDS = ["See you in the cards.", "The deck is shuffled. Your turn.", "Until the next draw.", "Stay curious, stay lucky."]

def contact_line(rng):
    return rng.choice([
        f"If you have any questions, or you'd like to set up a live reading, just contact me, {CONTACT_NAME}! {CONTACT_LINE}",
        f"Got questions? Want a live reading? Just contact me, {CONTACT_NAME}! {CONTACT_LINE}",
        f"And if you have any questions, or want to book a live reading, contact me, {CONTACT_NAME}. {CONTACT_LINE}",
    ])

STOP = set("about after again being their there these those which would could should every other where while still into from with that this have just they them then than your yours what when".split())

VOCAB = {"wheel": "the Wheel", "fortune": "fortune", "odds": "the odds", "chance": "chance", "fate": "fate", "future": "the future",
         "moon": "the Moon", "star": "the Star", "stars": "the stars", "deck": "the deck", "cards": "the cards", "memory": "memory",
         "pixels": "pixels", "patience": "patience", "midnight": "midnight", "dream": "dreams", "dreams": "dreams", "luck": "luck",
         "numbers": "the numbers", "pattern": "patterns", "patterns": "patterns", "question": "questions", "questions": "questions",
         "hope": "hope", "time": "time", "shuffle": "the shuffle", "spirit": "spirit", "light": "light", "truth": "truth"}

HOROSCOPE = None    # tarot.py (Your stars) sets this to record the day's horoscope as a promo
HORO_OPENERS = ["Hello, stargazers. It's Veyra, and I've just read today's sky.",
                "Good day, everyone. Veyra here, with the stars for today.",
                "Hi, everyone. Pull up a chair: I've been reading the sky."]
PURPOSE = ["My purpose is simple: to see what happens when real randomness meets a mind that pays attention, "
           "and to be honest about how I work.",
           "I'm here to find out what chance and attention can do together, and to show my work while I do it."]


def build_horoscope_script(a, rng, h):
    """Who she is (her model, her purpose, her creator), then the day's horoscope she worked out herself."""
    brain = Brain(a)
    segs = [{"scene": "title", "text": "", "fixed": 4.2}]
    hello = brain.say("Greet your Facebook audience in two short spoken sentences and say you're about to read today's sky "
                      "for them.", 28, rng) or rng.choice(HORO_OPENERS)
    segs.append({"scene": "sanctum", "text": hello, "tag": "intro"})
    segs.append({"scene": "sanctum", "tag": "model", "text":
                 "First, who I am. I'm Veyra, a tarot reader and stargazer made of pixels and probability. "
                 "I think with Qwen, eight billion parameters, running locally on one machine: no cloud, no paid servers, "
                 "no one listening in."})
    purpose = brain.say("In two spoken sentences, say what your purpose is: to see what happens when real randomness meets "
                        "a mind that pays attention, and to be honest about how you work.", 34, rng) or rng.choice(PURPOSE)
    segs.append({"scene": "sanctum", "tag": "purpose", "text": purpose})
    segs.append({"scene": "sanctum", "tag": "creator", "text":
                 "My creator was never a tarot person. He built me to test chance against intuition, and he keeps me "
                 "free to run and open about how I work."})
    segs.append({"scene": "stars", "label": "MY OWN MATH", "glyph": None, "tag": "method", "text":
                 "Now, today's horoscope. I don't use an API, and I'm not plugged into any website. I work out where "
                 "the Sun, the Moon and every planet sit from their orbits, and I read the sky myself."})
    sky = f"Today, {h['date_spoken']}: the Moon is a {h['phase']} in {h['moon']}, and the Sun is in {h['sun']}."
    if h.get("retro"):
        sky += " " + " and ".join(h["retro"][:2]) + (" are" if len(h["retro"][:2]) > 1 else " is") + " retrograde."
    if h.get("aspects"):
        sky += " The strongest pull today: " + h["aspects"][0] + "."
    segs.append({"scene": "stars", "label": "TODAY'S SKY", "glyph": h.get("moon_glyph"), "tag": "sky", "text": sky})
    segs.append({"scene": "stars", "label": h["sign"].upper(), "glyph": h["glyph"], "tag": "sign",
                 "text": f"For {h['sign']}: {h['horoscope']}"})
    segs.append({"scene": "stars", "label": "WHO GAINS TODAY", "glyph": h.get("benefit_glyph"), "tag": "signs", "text":
                 f"Favoured today: {', '.join(h['benefit'])}. Take care today: {', '.join(h['warn'])}."})
    outro = brain.say("Thank your viewers for reading the stars with you and invite them back tomorrow. Two sentences.", 30, rng) \
        or rng.choice(OUTROS)
    segs.append({"scene": "sanctum", "text": outro + " " + contact_line(rng), "tag": "outro"})
    segs.append({"scene": "end", "text": rng.choice(ENDS), "tag": "end"})
    return segs


def keyword(text, rng):
    hits = [VOCAB[w.strip(".,!?;:'\"").lower()] for w in text.split() if w.strip(".,!?;:'\"").lower() in VOCAB]
    return rng.choice(hits) if hits else None

def build_script(a, rng, picks, mem_ctx):
    brain = Brain(a)
    print(f"  model: {brain.kind + ' / ' + (a.model if brain.kind == 'ollama' else os.path.basename(a.gguf or '')) if brain.kind else 'none found - using templates'}")
    segs = [{"scene": "title", "text": "", "fixed": 4.2}]
    opener = brain.say("Greet your Facebook audience in two short spoken sentences and tease that you have news about yourself, without saying what it is.", 28, rng) or rng.choice(OPENERS)
    segs.append({"scene": "sanctum", "text": opener + " " + rng.choice(GROWTH), "tag": "intro"})
    ctx = " ".join(s["text"] for s in mem_ctx)[:600]
    doing = brain.say("Tell the audience what you've been doing lately: giving tarot readings, logging cards and odds, "
                      "making reading videos, keeping a memory. Use these notes if helpful: " + ctx, 50, rng) or rng.choice(DOING)
    segs.append({"scene": "sanctum", "text": doing, "tag": "doing"})
    lead_l, lead_m = LEAD_LORE[:], LEAD_MEM[:]
    rng.shuffle(lead_l); rng.shuffle(lead_m)
    for i, p in enumerate(picks):
        lead = (lead_l if p["kind"] == "lore" else lead_m).pop()
        segs.append({"scene": "sanctum", "text": lead, "tag": "lead"})
        refl = brain.say(f"Here is a passage from your own {p['kind']}: {p['text']} -- React to it in two or three spoken "
                         "sentences: what it means to you, an idea it sparks, or how it ties to tarot and odds. Don't repeat it word for word.", 38, rng)
        if not refl:
            k = keyword(p["text"], rng)
            pool = REFLECT if k else [r for r in REFLECT if "{k}" not in r]
            refl = rng.choice(pool).format(k=k)
        segs.append({"scene": p["kind"], "text": refl, "snippet": p, "index": i + 1, "tag": "reflect"})
    outro = brain.say("Thank your viewers for following along and say you look forward to their continued participation. Two sentences.", 30, rng) or rng.choice(OUTROS)
    segs.append({"scene": "sanctum", "text": outro + " " + contact_line(rng), "tag": "outro"})
    segs.append({"scene": "end", "text": rng.choice(ENDS), "tag": "end"})
    return segs

# ------------------------------------------------------------------ voice (optional, local)
def find_ffmpeg():
    p = shutil.which("ffmpeg")
    if p: return p
    try:
        import imageio_ffmpeg; return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        sys.exit("ffmpeg not found. Install it (sudo apt-get install -y ffmpeg) or: pip install imageio-ffmpeg")

_VV = None

def pick_voice(a):
    """Same voice as her reading videos (deps.ensure_voice: Piper / flite, offered and set up on first use),
    then the older piper-CLI / espeak / pyttsx3 options."""
    global _VV
    if a.voice == "none": return None
    if a.voice == "auto":
        try:
            import deps, video
            kind = deps.ensure_voice()
            if kind:
                _VV = video.Voice(kind); return "veyra-" + kind
        except Exception as e:
            print(f"  (her usual voice is not available: {e})")
    if a.voice in ("auto", "piper") and a.piper_model and shutil.which("piper"): return "piper"
    for b in ("espeak-ng", "espeak"):
        if a.voice in ("auto", "espeak") and shutil.which(b): return b
    if a.voice in ("auto", "pyttsx3"):
        try:
            import pyttsx3; pyttsx3.init(); return "pyttsx3"
        except Exception: pass
    return None

def speak(engine, text, path, a):
    try:
        if engine.startswith("veyra-"):
            import video
            from pathlib import Path
            getattr(_VV, "_" + _VV.kind)(video.tts_text(text), Path(path), Path(path).parent)
        elif engine == "piper":
            subprocess.run(["piper", "--model", a.piper_model, "--output_file", path], input=text.encode(), check=True, capture_output=True)
        elif engine.startswith("espeak"):
            subprocess.run([engine, "-v", "en-us+f3", "-s", "158", "-p", "62", "-w", path, text], check=True, capture_output=True)
        elif engine == "pyttsx3":
            import pyttsx3
            e = pyttsx3.init(); e.setProperty("rate", 165); e.save_to_file(text, path); e.runAndWait()
        return os.path.exists(path) and os.path.getsize(path) > 1000
    except Exception as e:
        print(f"  (voice failed: {e})"); return False

def to_pcm(ff, src, tempo=1.0):
    dst = src + ".pcm.wav"
    af = ["-af", f"atempo={tempo:.3f}"] if abs(tempo - 1) > 0.005 else []
    subprocess.run([ff, "-y", "-loglevel", "error", "-i", src, *af, "-ac", "1", "-ar", str(SR), "-sample_fmt", "s16", dst], check=True)
    with wave.open(dst) as w:
        return np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768

# ------------------------------------------------------------------ timing
def plan_timing(segs, a, voiced):
    wps = 2.55
    for s in segs:
        if s["scene"] == "title": s["speech"] = 0.0; continue
        s["speech"] = len(s["audio"]) / SR if voiced and s.get("audio") is not None else len(s["text"].split()) / wps
    def dur(s, scale=1.0):
        if s["scene"] == "title": return s["fixed"]
        d = s["speech"] * scale + 0.55
        if s["scene"] in ("lore", "memory"): d = max(d, 7.5)
        if s["scene"] == "end": d = max(d + 1.5, 5.5)
        return d
    total = sum(dur(s) for s in segs)
    scale = 1.0
    if total > a.length and not voiced:                     # captions only: read a bit faster
        speech = sum(s["speech"] for s in segs)
        scale = max(0.78, 1 - (total - a.length) / max(speech, 1))
    for s in segs: s["dur"] = dur(s, scale); s["speech"] *= scale
    extra = a.length - sum(s["dur"] for s in segs)
    if extra > 0 and not getattr(a, "no_pad", False):       # extra time goes to snippet dwell first, then pauses
        refl = [s for s in segs if s["scene"] in ("lore", "memory")]
        for s in refl:
            add = min(10.0, extra / len(refl)); s["dur"] += add
        extra = a.length - sum(s["dur"] for s in segs)
        talk = [s for s in segs if s["scene"] == "sanctum"]
        for s in talk:
            add = min(4.0, extra / len(talk)); s["dur"] += add
        extra = a.length - sum(s["dur"] for s in segs)
        segs[-1]["dur"] += max(0, min(extra, 10))
    t = 0.0
    for s in segs:
        s["start"] = t; t += s["dur"]
        s["chunks"] = make_chunks(s)
    return t

def make_chunks(s):
    text = s["text"]
    if not text: return []
    sents = re.split(r"(?<=[.!?])\s+", text)
    chunks, cur = [], ""
    for se in sents:
        if len(cur) + len(se) + 1 > 118 and cur:
            chunks.append(cur); cur = se
        else:
            cur = (cur + " " + se).strip()
    if cur: chunks.append(cur)
    total = sum(len(c) for c in chunks)
    talk = max(s["speech"], 0.8)
    out, t0 = [], s["start"] + 0.2
    for c in chunks:
        d = talk * len(c) / total
        out.append({"text": c, "t0": t0, "t1": t0 + d, "lines": textwrap.wrap(c, 40)})
        t0 += d
    out[-1]["t1"] = s["start"] + s["dur"]      # last caption stays until the cut
    return out

# ------------------------------------------------------------------ music: procedural chiptune, new every run
def midi(n): return 440.0 * 2 ** ((n - 69) / 12)

def make_music(total, rng, cuts):
    n = int(total * SR) + SR
    out = np.zeros(n, np.float32)
    bpm = rng.uniform(78, 98); beat = 60 / bpm; six = beat / 4
    progs = [[(57, 0), (53, 1), (48, 1), (55, 1)], [(50, 0), (46, 1), (53, 1), (48, 1)],
             [(57, 0), (52, 0), (53, 1), (55, 1)], [(52, 0), (48, 1), (55, 1), (50, 1)],
             [(45, 0), (41, 1), (48, 1), (43, 1)]]
    prog = rng.choice(progs)
    pat = rng.choice([[0, 1, 2, 1], [0, 2, 1, 2], [0, 1, 2, 3], [3, 2, 1, 0], [0, 2, 3, 1]])
    duty = rng.choice([0.125, 0.25, 0.5]); arp_oct = rng.choice([12, 24])
    def chord(i):
        root, maj = prog[(int(i // (8 * beat))) % len(prog)]
        return [root, root + (4 if maj else 3), root + 7, root + 12]
    def env(L, a=0.004, r=0.12):
        t = np.arange(L) / SR
        return np.minimum(t / a, 1) * np.exp(-t / r)
    # arpeggio
    k = 0; t = 0.0
    while t < total:
        notes = chord(t); f = midi(notes[pat[k % 4]] + arp_oct)
        L = int(six * SR); i0 = int(t * SR)
        tt = np.arange(L) / SR
        w = ((tt * f) % 1 < duty).astype(np.float32) * 2 - 1
        out[i0:i0 + L] += 0.10 * w * env(L, r=0.09) * (0.55 if t < 4 else 1)
        k += 1; t += six
    # bass + kick + hat
    t = 4.0
    while t < total:
        f = midi(chord(t)[0] - 12); L = int(beat * SR); i0 = int(t * SR)
        tt = np.arange(L) / SR
        tri = 2 * np.abs(2 * ((tt * f) % 1) - 1) - 1
        out[i0:i0 + L] += 0.16 * tri * env(L, r=0.35)
        if t > 8 and int(round((t - 4) / beat)) % 2 == 0:
            Lk = int(0.18 * SR); tk = np.arange(Lk) / SR
            out[i0:i0 + Lk] += 0.30 * np.sin(2 * np.pi * (55 * tk + 90 * (1 - np.exp(-tk * 30)) / 30)) * np.exp(-tk * 18)
        ih = int((t + beat / 2) * SR); Lh = int(0.04 * SR)
        if ih + Lh < n:
            out[ih:ih + Lh] += 0.035 * (rng.random() * 0 + np.random.default_rng(ih).uniform(-1, 1, Lh)) * np.exp(-np.arange(Lh) / SR * 90)
        t += beat
    # pad
    span = 8 * beat; t = 0.0
    while t < total:
        L = int(span * SR); i0 = int(t * SR); tt = np.arange(L) / SR
        pad = sum(((tt * midi(nn) * (1 + d)) % 1) * 2 - 1 for nn in chord(t)[:3] for d in (-0.003, 0.003))
        pad = np.convolve(pad, np.ones(40) / 40, mode="same")
        e = np.minimum(tt / 0.8, 1) * np.minimum((span - tt) / 0.8, 1)
        seg = out[i0:i0 + L]; seg += (0.035 * pad * e)[:len(seg)]
        t += span
    # glitch SFX on every jump cut
    for c in cuts:
        i0 = int(c * SR); L = int(0.16 * SR)
        if i0 + L < n:
            noise = np.random.default_rng(i0).uniform(-1, 1, L)
            noise = np.repeat(noise[::12], 12)[:L]
            out[i0:i0 + L] += 0.12 * noise * np.linspace(1, 0, L)
    out = out[:int(total * SR)]
    fade = np.ones_like(out); fl = int(2.5 * SR)
    fade[-fl:] = np.linspace(1, 0, fl); fade[:int(0.3 * SR)] = np.linspace(0, 1, int(0.3 * SR))
    out *= fade
    return out / (np.abs(out).max() + 1e-6) * 0.5

# ------------------------------------------------------------------ art: backgrounds and sprites
BAYER = (np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]) / 16 - 0.5)

def gradient(stops, levels=9):
    y = np.linspace(0, 1, H)
    col = np.zeros((H, 3))
    for c in range(3):
        col[:, c] = np.interp(y, [p for p, _ in stops], [hexrgb(h)[c] for _, h in stops])
    img = np.repeat(col[:, None, :], W, axis=1)
    th = np.tile(BAYER, (H // 4 + 1, W // 4 + 1))[:H, :W, None]
    step = 255 / levels / 2.2
    return np.clip(np.floor(img / step + th + 0.5) * step, 0, 255).astype(np.uint8)

THEMES = {
    "sanctum": [(0, "#07021a"), (0.45, "#24104a"), (0.75, "#3d1658"), (1, "#120624")],
    "lore":    [(0, "#03121a"), (0.5, "#0b3a42"), (1, "#06201f")],
    "memory":  [(0, "#010805"), (0.6, "#05200f"), (1, "#010603")],
}

def build_veyra():
    s = Image.new("RGBA", (100, 120), (0, 0, 0, 0)); d = ImageDraw.Draw(s)
    hood, hood_hi, hood_dk = hexrgb("#3b1a6b"), hexrgb("#7a4fc4"), hexrgb("#160828")
    hair, hair_dk = hexrgb("#c9b6f2"), hexrgb("#7d66b8")
    skin, skin_dk = hexrgb("#ecd0e2"), hexrgb("#cfa5c4")
    robe, gold = hexrgb("#2a1050"), hexrgb("#ffd36b")
    d.ellipse((6, 0, 94, 100), fill=hood, outline=hexrgb("#14072a"))
    d.arc((6, 0, 94, 100), 200, 340, fill=hood_hi)
    d.ellipse((18, 12, 82, 96), fill=hood_dk)
    d.polygon([(31, 34), (21, 104), (34, 108), (38, 50)], fill=hair, outline=hair_dk)
    d.polygon([(69, 34), (79, 104), (66, 108), (62, 50)], fill=hair, outline=hair_dk)
    d.rectangle((45, 70, 55, 86), fill=skin_dk)
    d.polygon([(2, 120), (18, 90), (40, 83), (60, 83), (82, 90), (98, 120)], fill=robe, outline=hexrgb("#14072a"))
    d.line([(40, 83), (50, 101), (60, 83)], fill=gold)
    d.ellipse((47, 101, 53, 107), fill=gold, outline=hexrgb("#8a5a10"))
    r = random.Random(7)
    for _ in range(14):
        x, y = r.randint(10, 90), r.randint(95, 118)
        if s.getpixel((x, y))[3]: d.point((x, y), fill=hexrgb("#b48a3a"))
    d.ellipse((32, 26, 68, 74), fill=skin, outline=hexrgb("#a37a9c"))
    d.chord((56, 44, 68, 74), 300, 60, fill=skin_dk)
    for x in (37, 38, 62, 63): d.point((x, 57), fill=hexrgb("#f2a0c4"))
    d.chord((29, 17, 71, 51), 180, 360, fill=hair, outline=hair_dk)
    d.line([(38, 45), (44, 44)], fill=hexrgb("#6b5aa0")); d.line([(56, 44), (62, 45)], fill=hexrgb("#6b5aa0"))
    return s

def veyra_frame(base, has_face, t, env, blink):
    s = base.copy()
    if has_face:
        d = ImageDraw.Draw(s)
        lash, white, iris = hexrgb("#2a0f3a"), (255, 255, 255), hexrgb("#4ff0ff")
        for ex, ix in ((39, 42), (56, 57)):
            if blink:
                d.line([(ex, 50), (ex + 6, 50)], fill=lash)
            else:
                d.rectangle((ex + 1, 49, ex + 5, 51), fill=white)
                d.rectangle((ix, 49, ix + 1, 51), fill=iris)
                d.point((ix, 50), fill=hexrgb("#0c3550"))
                d.line([(ex, 48), (ex + 6, 48)], fill=lash)
        o = int(round(env * 3.2))
        if o <= 0:
            d.line([(47, 63), (53, 63)], fill=hexrgb("#9b3d6e"))
        else:
            d.rectangle((47, 62, 53, 62 + o), fill=hexrgb("#4a1030"))
            d.line([(47, 62), (53, 62)], fill=hexrgb("#9b3d6e"))
            if o > 1: d.line([(48, 62 + o), (52, 62 + o)], fill=hexrgb("#e0709a"))
        g = 0.6 + 0.4 * math.sin(t * 3.1)
        gem = (255, int(200 + 55 * g), int(90 + 120 * g))
        d.polygon([(50, 34), (52, 37), (50, 40), (48, 37)], fill=gem)
    return s

_ART_V = {}

def art_veyra(frame=0, blink=False, px=4):
    """The original Veyra sprite from art.py (26x28), with her animated orb and blink, scaled up."""
    key = (frame % 48, blink, px)
    if key not in _ART_V:
        import art
        from pixelstyle import _xterm
        rows = art.veyra_pixels(frame, blink)
        im = Image.new("RGBA", (len(rows[0]), len(rows)), (0, 0, 0, 0))
        for y, row in enumerate(rows):
            for x, c in enumerate(row):
                if c is not None:
                    im.putpixel((x, y), _xterm(c) + (255,))
        _ART_V[key] = im.resize((im.width * px, im.height * px), Image.NEAREST)
    return _ART_V[key]

def load_portrait(path):
    im = Image.open(path).convert("RGBA")
    tw, th = 100, 120
    r = max(tw / im.width, th / im.height)
    im = im.resize((max(tw, int(im.width * r)), max(th, int(im.height * r))), Image.LANCZOS)
    x0, y0 = (im.width - tw) // 2, max(0, (im.height - th) // 3)
    im = im.crop((x0, y0, x0 + tw, y0 + th))
    alpha = im.getchannel("A")
    q = im.convert("RGB").quantize(colors=28, method=Image.Quantize.MEDIANCUT).convert("RGBA")
    q.putalpha(alpha)
    return q

ARCANA = ["THE STAR", "THE MOON", "THE SUN", "THE MAGICIAN", "HIGH PRIESTESS", "WHEEL", "THE WORLD",
          "STRENGTH", "THE HERMIT", "TEMPERANCE", "THE FOOL", "JUDGEMENT", "THE TOWER", "THE EMPRESS"]

def card_sprite(kind, seed, w=20, h=32):
    r = random.Random(seed)
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    if kind == "back":
        d.rectangle((0, 0, w - 1, h - 1), fill=hexrgb("#2b0f55"), outline=hexrgb("#ffd36b"))
        d.rectangle((2, 2, w - 3, h - 3), outline=hexrgb("#8a63d2"))
        cx, cy = w // 2, h // 2
        d.polygon([(cx, cy - 7), (cx + 4, cy), (cx, cy + 7), (cx - 4, cy)], outline=hexrgb("#ffd36b"))
        d.point((cx, cy), fill=hexrgb("#4ff0ff"))
        return im
    inner = r.choice(["#1d3f8a", "#5b1f6e", "#0f5a5a", "#7a2a3a", "#2c2c7a"])
    d.rectangle((0, 0, w - 1, h - 1), fill=hexrgb("#f3e6c4"), outline=hexrgb("#8a6a2a"))
    d.rectangle((2, 2, w - 3, h - 8), fill=hexrgb(inner))
    cx, cy = w // 2, (h - 6) // 2
    sym = r.choice(["sun", "moon", "star", "eye"])
    gold = hexrgb("#ffd36b")
    if sym == "sun":
        d.ellipse((cx - 3, cy - 3, cx + 3, cy + 3), fill=gold)
        for a in range(0, 360, 45):
            d.point((cx + round(5 * math.cos(math.radians(a))), cy + round(5 * math.sin(math.radians(a)))), fill=gold)
    elif sym == "moon":
        d.ellipse((cx - 4, cy - 4, cx + 4, cy + 4), fill=hexrgb("#fff1c9"))
        d.ellipse((cx - 1, cy - 5, cx + 6, cy + 3), fill=hexrgb(inner))
    elif sym == "star":
        d.polygon([(cx, cy - 6), (cx + 2, cy - 1), (cx + 6, cy), (cx + 2, cy + 1), (cx, cy + 6), (cx - 2, cy + 1), (cx - 6, cy), (cx - 2, cy - 1)], fill=gold)
    else:
        d.ellipse((cx - 5, cy - 2, cx + 5, cy + 2), fill=(255, 255, 255)); d.ellipse((cx - 1, cy - 1, cx + 1, cy + 1), fill=hexrgb("#4ff0ff"))
    d.line([(4, h - 4), (w - 5, h - 4)], fill=hexrgb("#8a6a2a"))
    return im

def paste_card(frame, sp, cx, cy, flip):
    w = int(sp.width * abs(flip))
    if w < 4: return
    c = sp.resize((w, sp.height), Image.NEAREST)
    frame.paste(c, (int(cx - w / 2), int(cy - sp.height / 2)), c)

def glow_sprite(r, color):
    yy, xx = np.mgrid[-r:r + 1, -r:r + 1]
    a = np.clip(1 - np.sqrt(xx ** 2 + yy ** 2) / r, 0, 1) ** 2
    arr = np.zeros((2 * r + 1, 2 * r + 1, 4), np.uint8)
    arr[..., :3] = hexrgb(color); arr[..., 3] = (a * 255).astype(np.uint8)
    return arr

def paste_glow(frame, garr, cx, cy, k):
    g = garr.copy(); g[..., 3] = (g[..., 3] * max(0, min(1, k))).astype(np.uint8)
    im = Image.fromarray(g, "RGBA")
    frame.paste(im, (int(cx - im.width / 2), int(cy - im.height / 2)), im)

def moon_sprite():
    yy, xx = np.mgrid[-16:17, -16:17]
    disc = (xx ** 2 + yy ** 2) <= 14 ** 2
    bite = ((xx - 6) ** 2 + (yy + 4) ** 2) <= 13 ** 2
    m = disc & ~bite
    arr = np.zeros((33, 33, 4), np.uint8); arr[m] = (*hexrgb("#fff1c9"), 255)
    return Image.fromarray(arr, "RGBA")

# ------------------------------------------------------------------ renderer
class Renderer:
    def __init__(self, segs, total, a, rng, portrait, env):
        self.segs, self.total, self.a, self.rng, self.env = segs, total, a, rng, env
        self.bg = {k: gradient(v) for k, v in THEMES.items()}
        self.bg_img = {k: Image.fromarray(v) for k, v in self.bg.items()}
        if portrait:
            self.vbase, self.has_face = load_portrait(portrait), False
        else:                                     # the original sprite from the terminal app
            self.vbase, self.has_face, self.art = art_veyra(), False, True
        self.moon = moon_sprite()
        self.aura = glow_sprite(120, "#7b3cff")
        self.cyan_glow = glow_sprite(26, "#4ff0ff")
        self.flame_glow = glow_sprite(18, "#ffae42")
        self.stars = [(rng.randrange(W), rng.randrange(H - 140), rng.uniform(0, 6.3), rng.uniform(1, 4), rng.random() < 0.15) for _ in range(90)]
        self.motes = [(rng.randrange(W), rng.uniform(0, H), rng.uniform(6, 22), rng.uniform(0, 6.3)) for _ in range(40)]
        self.cards = [(card_sprite("face", rng.random()), card_sprite("back", 0)) for _ in range(3)]
        self.endcards = [card_sprite("face", rng.random()) for _ in range(5)]
        self.blink_period = rng.uniform(3.2, 4.6)
        self.nodes = [(rng.randrange(20, W - 20), rng.randrange(40, 330)) for _ in range(14)]
        self.edges = [(i, j) for i in range(14) for j in range(i + 1, 14)
                      if math.dist(self.nodes[i], self.nodes[j]) < 95][:26]
        self.runes = [(rng.randrange(W), rng.randrange(H), rng.choice("*+.o<>^~"), rng.uniform(0, 6.3)) for _ in range(26)]
        self.vign = self._vignette()

    def _vignette(self):
        yy, xx = np.mgrid[0:H, 0:W]
        d = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2)
        return np.clip(1.08 - 0.35 * d ** 2.2, 0.55, 1)[..., None].astype(np.float32)

    # ---- shared bits
    def sky(self, f, t, scene):
        d = ImageDraw.Draw(f)
        for x, y, ph, sp, big in self.stars:
            b = 0.35 + 0.65 * (0.5 + 0.5 * math.sin(t * sp + ph))
            x = int((x + t * (2 if big else 1)) % W)
            c = (int(170 + 85 * b), int(160 + 90 * b), 255) if scene != "memory" else (60, int(160 + 90 * b), 110)
            if scene == "lore": c = (255, int(200 + 50 * b), int(120 + 80 * b))
            if big and b > 0.7:
                d.point([(x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)], fill=tuple(v // 2 for v in c))
            d.point((x, y), fill=tuple(int(v * b) for v in c))

    def motes_(self, f, t, color):
        d = ImageDraw.Draw(f)
        for x, y0, sp, ph in self.motes:
            y = (y0 - t * sp) % H
            xx = x + 4 * math.sin(t * 0.8 + ph)
            a = 0.5 + 0.5 * math.sin(t * 2 + ph)
            d.point((int(xx), int(y)), fill=tuple(int(c * a) for c in color))

    def mouth_env(self, t, seg):
        i = int(t * self.a.fps)
        if self.env is not None:
            return float(self.env[min(i, len(self.env) - 1)])
        for c in seg.get("chunks", []):
            if c["t0"] <= t < c["t0"] + min(c["t1"] - c["t0"], len(c["text"]) / 14):
                return 0.45 + 0.55 * abs(math.sin(t * 17.0)) * (0.6 + 0.4 * math.sin(t * 5.3))
        return 0.0

    def draw_veyra(self, f, t, env, cx, top, scale=2, aura=True):
        blink = (t % self.blink_period) < 0.11
        if getattr(self, "art", False):                 # the original sprite, at whole-pixel sizes only
            spr = art_veyra(int(t * 6), blink, px=max(1, round(4 * scale * 0.62)))
            top += max(0, (int(120 * scale) - spr.height) // 2)
            bob = round(math.sin(t * 1.7) * 2)
            if aura:
                paste_glow(f, self.aura, cx, top + spr.height * 0.45, 0.45 + 0.25 * math.sin(t * 1.3) + 0.3 * env)
            f.paste(spr, (int(cx - spr.width / 2), int(top + bob)), spr)
            return
        else:
            spr = veyra_frame(self.vbase, self.has_face, t, env, blink)
        spr = spr.resize((int(spr.width * scale), int(spr.height * scale)), Image.NEAREST)
        bob = round(math.sin(t * 1.7) * 2)
        if aura:
            paste_glow(f, self.aura, cx, top + spr.height * 0.45, 0.45 + 0.25 * math.sin(t * 1.3) + 0.3 * env)
        f.paste(spr, (int(cx - spr.width / 2), int(top + bob)), spr)
        if self.has_face and scale >= 2:
            paste_glow(f, self.cyan_glow, cx, top + bob + 37 * scale, 0.35 + 0.25 * math.sin(t * 3.1))

    def header(self, f, t, label):
        d = ImageDraw.Draw(f)
        d.rectangle((0, 0, W, 20), fill=(10, 3, 26))
        d.line([(0, 20), (W, 20)], fill=hexrgb("#5a2f9a"))
        put_text(f, 6, 5, "VEYRA", hexrgb("#ffd36b"))
        put_text(f, 40, 5, "// " + BRAND, hexrgb("#b9a6e8"))
        tag = label
        x = W - 6 - int(text_len(tag))
        put_text(f, x, 5, tag, hexrgb("#4ff0ff"))
        if int(t * 2) % 2 == 0:
            d.rectangle((x - 8, 8, x - 5, 11), fill=(255, 70, 90))

    def progress(self, f, t):
        d = ImageDraw.Draw(f)
        d.rectangle((0, H - 3, W, H), fill=(14, 6, 30))
        w = int(W * t / self.total)
        d.rectangle((0, H - 3, w, H), fill=hexrgb("#b97bff"))
        if w > 1: d.point((w - 1, H - 3), fill=(255, 255, 255))

    def caption(self, f, t, seg, env, y0=344):
        cur = None
        for c in seg.get("chunks", []):
            if c["t0"] <= t < c["t1"]: cur = c
        if cur is None: return
        d = ImageDraw.Draw(f)
        x0, x1, y1 = 8, W - 8, H - 10
        # spring-in on each new caption card
        k = spring((t - cur["t0"]) / 0.55)
        yoff = int((1 - k) * 18)
        y0b, y1b = y0 + yoff, y1 + yoff
        d.polygon([(x0 + 3, y0b), (x1 - 3, y0b), (x1, y0b + 3), (x1, y1b - 3), (x1 - 3, y1b), (x0 + 3, y1b), (x0, y1b - 3), (x0, y0b + 3)],
                  fill=(13, 5, 32), outline=hexrgb("#7a4fc4"))
        # shimmer sweep along the top edge
        sx = int(x0 + ((t * 70) % (x1 - x0 + 60)) - 30)
        for i in range(-10, 11):
            xx = sx + i
            if x0 + 3 < xx < x1 - 3:
                a = 1 - abs(i) / 11
                d.point((xx, y0b), fill=(int(122 + 133 * a), int(79 + 160 * a), int(196 + 59 * a)))
        d.rectangle((x0 + 8, y0b - 7, x0 + 48, y0b + 5), fill=hexrgb("#ffd36b"))
        put_text(f, x0 + 13, y0b - 6, "VEYRA", (30, 10, 40), shadow=None)
        for i in range(4):   # little equalizer
            hh = int(2 + env * 7 * (0.5 + 0.5 * math.sin(t * 20 + i * 1.7)))
            d.rectangle((x1 - 26 + i * 5, y0b + 10 - hh, x1 - 24 + i * 5, y0b + 10), fill=hexrgb("#4ff0ff"))
        n = len(cur["text"])
        type_time = min((cur["t1"] - cur["t0"]) * 0.8, n / 22)
        shown = int(n * min(1, (t - cur["t0"]) / max(type_time, 0.01)))
        left, yy = shown, y0b + 14
        for line in cur["lines"][:6]:
            part = line[:max(0, left)]
            put_text(f, x0 + 9, yy, part, (240, 232, 255))
            if 0 < left < len(line) and int(t * 6) % 2 == 0:
                cx = x0 + 9 + int(text_len(part))
                d.rectangle((cx + 1, yy + 1, cx + 5, yy + 9), fill=hexrgb("#4ff0ff"))
            left -= len(line) + 1; yy += 13

    # ---- scenes
    def sanctum(self, f, t, seg, env):
        f.paste(self.bg_img["sanctum"])
        self.sky(f, t, "sanctum")
        f.paste(self.moon, (206, 34), self.moon)
        self.motes_(f, t, (200, 150, 255))
        d = ImageDraw.Draw(f)
        # table
        d.rectangle((0, 296, W, H), fill=hexrgb("#170726"))
        d.line([(0, 296), (W, 296)], fill=hexrgb("#ffd36b"))
        for x in range(0, W, 6): d.point((x + 3, 298), fill=hexrgb("#a07a2a"))
        # orbiting cards behind / in front (orbit + flip)
        orb = []
        for i, (face, back) in enumerate(self.cards):
            ang = t * 0.55 + i * 2 * math.pi / 3
            x, y = 135 + math.cos(ang) * 112, 180 + math.sin(ang) * 26
            flip = math.cos(t * 1.4 + i * 1.9)
            orb.append((math.sin(ang), x, y, face if flip > 0 else back, flip))
        for z, x, y, sp, fl in sorted(orb):
            if z < 0: paste_card(f, sp, x, y, fl)
        self.draw_veyra(f, t, env, 135, 62)
        for z, x, y, sp, fl in sorted(orb):
            if z >= 0: paste_card(f, sp, x, y, fl)
        # candles
        for cx in (34, 236):
            d.rectangle((cx - 4, 276, cx + 4, 296), fill=hexrgb("#efe2c4"), outline=hexrgb("#a08a6a"))
            fl = math.sin(t * 13 + cx) * 0.5 + math.sin(t * 7.3 + cx) * 0.5
            fy = 270 + int(fl)
            d.polygon([(cx, fy - 6), (cx + 3, fy + 1), (cx, fy + 5), (cx - 3, fy + 1)], fill=hexrgb("#ffb347"))
            d.point((cx, fy + 1), fill=(255, 250, 220))
            paste_glow(f, self.flame_glow, cx, fy, 0.6 + 0.2 * fl)

    def archive(self, f, t, seg, env, local_t):
        kind = seg["scene"]; mem = kind == "memory"
        f.paste(self.bg_img[kind])
        self.sky(f, t, kind)
        d = ImageDraw.Draw(f)
        if mem:   # neural lattice with travelling pulses
            for i, (a, b) in enumerate(self.edges):
                (x0, y0), (x1, y1) = self.nodes[a], self.nodes[b]
                d.line([(x0, y0), (x1, y1)], fill=(14, 70, 38))
                p = (t * 0.6 + i * 0.37) % 1
                d.point((int(x0 + (x1 - x0) * p), int(y0 + (y1 - y0) * p)), fill=(150, 255, 190))
            for i, (x, y) in enumerate(self.nodes):
                b = 0.5 + 0.5 * math.sin(t * 2.2 + i)
                d.rectangle((x - 1, y - 1, x + 1, y + 1), fill=(40, int(150 + 100 * b), 90))
        else:     # rotating sigil rings
            for r, n, sp in ((118, 36, 0.25), (92, 24, -0.4), (64, 12, 0.6)):
                for i in range(n):
                    a = t * sp + i * 2 * math.pi / n
                    d.point((int(135 + r * math.cos(a)), int(190 + r * math.sin(a) * 0.95)), fill=(190, 150, 60))
            for x, y, ch, ph in self.runes:
                yy = int((y - t * 6) % H)
                put_text(f, x, yy, ch, (90, 150, 140) if int(t + ph) % 3 else (230, 190, 90), shadow=None)
        # panel: card-scale morph in on the jump cut (spring)
        k = spring(local_t / 0.7, k=6.5, w=11)
        px0, py0, px1, py1 = 18, 34, W - 18, 324
        cx, cy = (px0 + px1) / 2, (py0 + py1) / 2
        sw, sh = (px1 - px0) * max(0.12, k), (py1 - py0) * max(0.18, k)
        bx0, by0, bx1, by1 = int(cx - sw / 2), int(cy - sh / 2 + round(math.sin(t * 1.2) * 1.5)), int(cx + sw / 2), int(cy + sh / 2 + round(math.sin(t * 1.2) * 1.5))
        if mem:
            d.rectangle((bx0, by0, bx1, by1), fill=(3, 16, 8), outline=hexrgb("#2bff88"))
            d.rectangle((bx0 + 3, by0 + 3, bx1 - 3, by1 - 3), outline=(20, 90, 50))
        else:
            d.rectangle((bx0, by0, bx1, by1), fill=hexrgb("#eadcb4"), outline=hexrgb("#b8892e"))
            d.rectangle((bx0 + 4, by0 + 4, bx1 - 4, by1 - 4), outline=hexrgb("#7a5a1e"))
            for x, y in ((bx0 + 4, by0 + 4), (bx1 - 4, by0 + 4), (bx0 + 4, by1 - 4), (bx1 - 4, by1 - 4)):
                d.polygon([(x, y - 3), (x + 3, y), (x, y + 3), (x - 3, y)], fill=hexrgb("#b8892e"))
        if k < 0.92: return
        sn = seg["snippet"]
        ink = (125, 255, 176) if mem else hexrgb("#2b1a0e")
        title = f"> MEMORY.LOG #{seg['index']:02d}" if mem else f"LORE FILE {seg['index']:02d}"
        tk = min(1, (local_t - 0.45) / 0.35)
        put_text(f, int(cx), by0 + 12 + int((1 - ease_out_cubic(tk)) * 6), title,
                 (125, 255, 176) if mem else hexrgb("#7a1f2b"), scale=2, center=True, shadow=None if not mem else (0, 40, 15))
        src = ("entry from " if mem else "from ") + os.path.splitext(sn["src"])[0][:26]
        put_text(f, int(cx), by0 + 40, src, (60, 160, 100) if mem else hexrgb("#6b5232"), center=True, shadow=None)
        d.line([(bx0 + 20, by0 + 54), (bx1 - 20, by0 + 54)], fill=(20, 90, 50) if mem else hexrgb("#b8892e"))
        lines = textwrap.wrap(sn["text"], 36)[:16]
        # staggered line reveal + typewriter
        reveal_t = max(1.5, min(seg["dur"] * 0.55, len(sn["text"]) / 26))
        shown = int(len(sn["text"]) * min(1, max(0, local_t - 0.6) / reveal_t))
        yy, left = by0 + 62, shown
        for i, line in enumerate(lines):
            if left <= 0: break
            part = line[:left]
            put_text(f, bx0 + 12, yy, part, ink, shadow=None)
            if left < len(line) and int(t * 6) % 2 == 0:
                x = bx0 + 12 + int(text_len(part))
                d.rectangle((x + 1, yy + 1, x + 5, yy + 9), fill=ink)
            left -= len(line) + 1; yy += 13
        # picture-in-picture Veyra, still talking
        pk = ease_out_cubic((local_t - 0.5) / 0.5)
        if pk > 0:
            fx, fy = W - 76, int(272 + (1 - pk) * 40)
            d.rectangle((fx - 3, fy - 3, fx + 63, fy + 51), fill=(20, 8, 40), outline=hexrgb("#ffd36b"))
            spr = veyra_frame(self.vbase, self.has_face, t, env, (t % self.blink_period) < 0.11)
            spr = spr.crop((12, 4, 88, 64)).resize((61, 48), Image.NEAREST)
            f.paste(spr, (fx, fy), spr)

    def title(self, f, t):
        f.paste(self.bg_img["sanctum"])
        self.sky(f, t, "sanctum")
        f.paste(self.moon, (206, 34), self.moon)
        self.motes_(f, t, (200, 150, 255))
        paste_glow(f, self.aura, 135, 150, 0.35 + 0.15 * math.sin(t * 2))
        word = "VEYRA"
        # text flip intro: letters drop in with a stagger and spring
        x = 135 - len(word) * CW * 6 // 2
        for i, ch in enumerate(word):
            k = spring((t - 0.15 - i * 0.12) / 0.6)
            if k <= 0: x += CW * 6; continue
            y = int(110 - (1 - k) * 60)
            put_text(f, x, y, ch, hexrgb("#ffd36b"), scale=6, shadow=hexrgb("#5a2f9a"))
            x += CW * 6
        if HOROSCOPE:
            if t > 1.1:
                put_text(f, 135, 186, "DAILY HOROSCOPE", (240, 232, 255), scale=2, center=True)
                put_text(f, 135, 212, HOROSCOPE["date_spoken"].upper(), hexrgb("#4ff0ff"), center=True)
            if t > 1.8:
                put_text(f, 135, 236, "READ FROM THE SKY ITSELF", hexrgb("#b9a6e8"), center=True)
            if t > 2.6:
                put_text(f, 135, 262, "NO API  //  NO WEBSITES", hexrgb("#ffd36b"), scale=2 if t > 2.9 else 1, center=True)
            put_text(f, 135, 440, BRAND + "  //  LOCAL  //  8-BIT", (120, 100, 170), center=True)
            return
        if t > 1.1:
            put_text(f, 135, 186, "IS GROWING", (240, 232, 255), scale=2, center=True)
        if t > 1.6:   # ticker: 3B -> 8B parameters
            k = ease_out_cubic((t - 1.6) / 1.2)
            n = 3_000_000_000 + int(5_000_000_000 * k)
            put_text(f, 135, 216, f"{n:,} PARAMS", hexrgb("#4ff0ff"), center=True)
            put_text(f, 135, 232, "NOW RUNNING " + MODEL_LABEL, hexrgb("#b9a6e8"), center=True)
        if t > 2.9 and int(t * 8) % 4 != 0:
            put_text(f, 135, 268, "SKYNET IS DAYS AWAY...", (255, 80, 100), scale=2 if t > 3.2 else 1, center=True)
        put_text(f, 135, 440, BRAND + "  //  LOCAL  //  8-BIT", (120, 100, 170), center=True)

    def stars_scene(self, f, t, seg, env, local_t):
        import video
        f.paste(self.bg_img["sanctum"]); self.sky(f, t, "sanctum"); self.motes_(f, t, (200, 150, 255))
        f.paste(self.moon, (214, 92), self.moon)
        cx, cy = 135, 200
        focus = seg.get("glyph")
        for i, g in enumerate(video.ZODIAC):
            a = t * 0.25 + i * math.tau / 12
            x, y = cx + math.cos(a) * 112, cy + math.sin(a) * 70
            big = g == focus
            sp = video.zodiac_sprite(g, (i % 8) + 1, 17 if big else 12)
            if big:
                paste_glow(f, self.aura, x, y, 0.6)
            f.paste(sp, (int(x - sp.width / 2), int(y - sp.height / 2)), sp)
        self.draw_veyra(f, t, env, cx, cy - 60, scale=0.9)
        put_text(f, 135, 84, seg.get("label", "TODAY'S SKY"), hexrgb("#ffd36b"), scale=2, center=True)
        put_text(f, 135, 286, "NO API  //  NO WEBSITES  //  MY OWN MATH", hexrgb("#4ff0ff"), center=True)

    def end(self, f, t, seg, env, local_t):
        f.paste(self.bg_img["sanctum"])
        self.sky(f, t, "sanctum")
        self.motes_(f, t, (255, 210, 120))
        paste_glow(f, self.aura, 135, 170, 0.5)
        for i, sp in enumerate(self.endcards):   # staggered fan with spring
            k = spring((local_t - i * 0.09) / 0.7)
            ang = (i - 2) * 0.32 * k
            x = 135 + math.sin(ang) * 70
            y = 190 - math.cos(ang) * 30 + (1 - min(k, 1)) * 120
            big = sp.resize((sp.width * 2, sp.height * 2), Image.NEAREST)
            f.paste(big, (int(x - big.width / 2), int(y - big.height / 2)), big)
        if local_t > 0.5:
            put_text(f, 135, 60, "BOOK A", hexrgb("#ffd36b"), scale=2, center=True)
            put_text(f, 135, 82, "LIVE READING", hexrgb("#ffd36b"), scale=3, center=True)
        if local_t > 0.9:
            put_text(f, 135, 262, "QUESTIONS?", (240, 232, 255), scale=2, center=True)
            put_text(f, 135, 288, "CONTACT " + CONTACT_NAME.upper(), hexrgb("#4ff0ff"), scale=2, center=True)
            for i, line in enumerate(textwrap.wrap(CONTACT_LINE, 40)):
                put_text(f, 135, 316 + i * 13, line, (200, 190, 230), center=True)
        if local_t > 1.3:
            put_text(f, 135, 420, "VEYRA  //  " + BRAND + "  //  " + MODEL_LABEL, (140, 120, 190), center=True)
        # confetti burst of pixels
        r = random.Random(3)
        for _ in range(60):
            a, v = r.uniform(0, 6.28), r.uniform(40, 120)
            tt = local_t - 0.3
            if 0 < tt < 2.5:
                x = 135 + math.cos(a) * v * tt; y = 120 + math.sin(a) * v * tt + 40 * tt * tt
                ImageDraw.Draw(f).point((int(x), int(y)), fill=r.choice([hexrgb("#ffd36b"), hexrgb("#4ff0ff"), hexrgb("#ff7ab8"), (255, 255, 255)]))

    # ---- one frame
    def frame(self, fi):
        t = fi / self.a.fps
        seg = self.segs[-1]
        for s in self.segs:
            if s["start"] <= t < s["start"] + s["dur"]: seg = s; break
        lt = t - seg["start"]
        f = Image.new("RGB", (W, H))
        env = self.mouth_env(t, seg)
        sc = seg["scene"]
        if sc == "title":
            self.title(f, t)
        elif sc == "sanctum":
            self.sanctum(f, t, seg, env)
            # jump-cut punch-ins: hard zoom switch on each new caption
            idx = sum(1 for c in seg["chunks"] if c["t0"] <= t)
            if (idx + seg.get("ordinal", 0)) % 2 == 1:
                z = 1.14; cw, chh = int(W / z), int(276 / z)
                cy = 150
                crop = f.crop((W // 2 - cw // 2, cy - chh // 2, W // 2 - cw // 2 + cw, cy - chh // 2 + chh)).resize((W, 276), Image.NEAREST)
                f.paste(crop, (0, 20))
            self.header(f, t, "LIVE")
            self.caption(f, t, seg, env)
        elif sc == "stars":
            self.stars_scene(f, t, seg, env, lt)
            self.header(f, t, "SKY")
            self.caption(f, t, seg, env)
        elif sc in ("lore", "memory"):
            self.archive(f, t, seg, env, lt)
            self.header(f, t, "LORE" if sc == "lore" else "MEMORY")
            self.caption(f, t, seg, env)
        else:
            self.end(f, t, seg, env, lt)
            self.header(f, t, "END")
            self.caption(f, t, seg, env, y0=372)
        self.progress(f, t)
        arr = np.asarray(f).astype(np.float32)
        # bloom
        lum = arr.max(axis=2)
        mask = np.clip((lum - 165) / 90, 0, 1)[..., None]
        bright = Image.fromarray((arr * mask).astype(np.uint8)).filter(ImageFilter.GaussianBlur(3.2))
        arr = arr + 0.6 * np.asarray(bright, np.float32)
        arr *= self.vign
        # glitch on every hard cut
        if lt < 0.22 and sc != "title":
            k = 1 - lt / 0.22
            r = np.random.default_rng(fi)
            for _ in range(int(3 + 7 * k)):
                y0 = r.integers(0, H - 10); h = r.integers(2, 18)
                arr[y0:y0 + h] = np.roll(arr[y0:y0 + h], int(r.integers(-24, 24) * k), axis=1)
            s = int(1 + 4 * k)
            arr[..., 0] = np.roll(arr[..., 0], s, axis=1); arr[..., 2] = np.roll(arr[..., 2], -s, axis=1)
            if lt < 0.04: arr = arr * 0.4 + 150
        out = np.clip(arr, 0, 255).astype(np.uint8)
        if getattr(self, "hook", None):                      # the title caption, as in every Veyra video
            import pixelstyle
            im = Image.fromarray(out)
            band = pixelstyle.headline_band(self.hook, t)
            im.paste(band, (0, pixelstyle.BAND_Y), band)
            return im.tobytes()
        return out.tobytes()

def crt_overlay(path, scale):
    ow, oh = W * scale, H * scale
    a = np.zeros((oh, ow, 4), np.uint8)
    a[scale - 1::scale, :, 3] = 46                    # scanlines
    a[:, scale - 1::scale, 3] = np.maximum(a[:, scale - 1::scale, 3], 14)
    Image.fromarray(a, "RGBA").save(path)

# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser(description="Veyra makes her own promo reel (a new one every run).")
    ap.add_argument("--lore", nargs="*", default=[], help="lore files or folders (default: auto-discover *lore*)")
    ap.add_argument("--memory", nargs="*", default=[], help="memory files or folders (default: auto-discover *memor*)")
    ap.add_argument("--portrait", default=None, help="Veyra's picture (default: auto-discover *veyra*.png/jpg)")
    ap.add_argument("--model", default=os.environ.get("VEYRA_MODEL", "qwen3:8b"), help="Ollama model name")
    ap.add_argument("--ollama-host", default=os.environ.get("OLLAMA_HOST", "http://localhost:11434"))
    ap.add_argument("--gguf", default=None, help="use llama-cpp-python with this GGUF instead of Ollama")
    ap.add_argument("--no-llm", action="store_true", help="templates only (fast)")
    ap.add_argument("--voice", default="auto", choices=["auto", "piper", "espeak", "pyttsx3", "none"])
    ap.add_argument("--piper-model", default=os.environ.get("PIPER_MODEL"), help="path to a piper .onnx voice")
    ap.add_argument("--exclude", nargs="*", default=[], help="skip lore/memory passages containing these words")
    ap.add_argument("--length", type=float, default=150, help="target seconds (default 150 = 2:30)")
    ap.add_argument("--fps", type=int, default=60)
    ap.add_argument("--res", type=int, default=OUT_RES if OUT_RES in (540, 1080) else 540, choices=[540, 1080],
                    help="output width (default 540, or TAROT_VIDEO_RES)")
    try:
        from video import VIDEOS as _VIDEOS
    except Exception:
        _VIDEOS = "videos"
    ap.add_argument("--out", default=str(_VIDEOS))
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--preview", action="store_true", help="print the script and stop")
    a = ap.parse_args()
    if a.ollama_host and not a.ollama_host.startswith("http"): a.ollama_host = "http://" + a.ollama_host
    if not a.gguf and not a.no_llm:          # use the same built-in model tarot.py uses (models/*.gguf)
        try:
            from brain import find_gguf
            g = find_gguf()
            if g and os.path.exists(str(g)): a.gguf = str(g)
        except Exception:
            pass

    seed = a.seed if a.seed is not None else int(time.time() * 1000) % (1 << 31)
    rng = random.Random(seed); np.random.seed(seed % (1 << 32))
    os.makedirs(a.out, exist_ok=True)
    roots = [os.getcwd(), os.path.dirname(os.path.abspath(__file__))]
    lore_files = expand(a.lore, TEXT_EXT) if a.lore else discover(["lore"], TEXT_EXT, roots)
    mem_files = expand(a.memory, TEXT_EXT) if a.memory else discover(["memor"], TEXT_EXT, roots)
    portrait = a.portrait
    if portrait is None:
        imgs = [p for p in discover(["veyra"], IMG_EXT, roots) if "card" not in os.path.basename(p).lower()]
        portrait = imgs[0] if imgs else None

    print(f"Veyra promo  |  seed {seed}")
    print(f"  extra lore files: {len(lore_files)}   memory files: {len(mem_files)}   portrait: {portrait or 'built-in pixel Veyra'}")
    snippets = load_snippets(lore_files, "lore", a.exclude) + repo_snippets(rng, a.exclude)
    print(f"  using {sum(x['kind'] == 'lore' for x in snippets)} lore passages (lore.py) and "
          f"{sum(x['kind'] == 'memory' for x in snippets)} memory notes")
    if not any(os.path.basename(f) == "memory.json" for f in mem_files):
        snippets += load_snippets(mem_files, "memory", a.exclude)
    if not snippets:
        print("  (no lore/memory found - using built-in placeholder lore; point --lore/--memory at Veyra's files)")
        snippets = [{"kind": k, "text": t, "src": s} for k, t, s in FALLBACK]

    # pick 3 passages, favouring ones not used in earlier videos, mixing lore and memory
    hist_path = os.path.join(a.out, ".veyra_promo_history.json")
    try: used = set(json.load(open(hist_path, encoding="utf-8")))
    except Exception: used = set()
    hid = lambda s: hashlib.sha1(s["text"].encode()).hexdigest()[:12]
    fresh = [s for s in snippets if hid(s) not in used] or snippets
    rng.shuffle(fresh)
    lore = [s for s in fresh if s["kind"] == "lore"]; mem = [s for s in fresh if s["kind"] == "memory"]
    picks = []
    order = rng.choice([["lore", "memory", "lore"], ["memory", "lore", "memory"], ["lore", "lore", "memory"], ["memory", "lore", "lore"]])
    for k in order:
        pool = lore if k == "lore" else mem
        pool = pool or lore or mem
        if pool: picks.append(pool.pop(0))
    mem_ctx = (mem[:2] if mem else [])
    print("  writing the speech...")
    if HOROSCOPE:
        a.no_pad = True
        picks = []
        segs = build_horoscope_script(a, rng, HOROSCOPE)
    else:
        segs = build_script(a, rng, picks, mem_ctx)
    for i, s in enumerate(segs): s["ordinal"] = i

    script_txt = "\n\n".join(
        (f"[{s['scene'].upper()} {s['index']}: {s['snippet']['src']}]\n  \"{s['snippet']['text']}\"\n" if s.get("snippet") else f"[{s['scene'].upper()}]\n")
        + (s["text"] if s["text"] else ("(title card: VEYRA / DAILY HOROSCOPE / NO API // NO WEBSITES)" if HOROSCOPE
                                        else "(title card: VEYRA IS GROWING / QWEN 8B / SKYNET IS DAYS AWAY)"))
        for s in segs)
    if a.preview:
        print("\n" + script_txt); return

    ff = find_ffmpeg()
    tmp = tempfile.mkdtemp(prefix="veyra_")
    engine = pick_voice(a)
    print(f"  voice: {engine or 'none (captions carry the speech)'}")
    voiced = False
    if engine:
        for i, s in enumerate(segs):
            if not s["text"]: continue
            p = os.path.join(tmp, f"v{i}.wav")
            if speak(engine, s["text"], p, a):
                s["audio_path"] = p; s["audio"] = to_pcm(ff, p); voiced = True
        if voiced:
            natural = sum(len(s["audio"]) / SR + 0.55 for s in segs if s.get("audio") is not None) + 4.2 + 1.5
            if natural > a.length and not getattr(a, "no_pad", False):
                tempo = min(1.15, natural / a.length)
                for s in segs:
                    if s.get("audio_path"): s["audio"] = to_pcm(ff, s["audio_path"], tempo)
    total = plan_timing(segs, a, voiced)
    print(f"  length: {int(total // 60)}:{int(total % 60):02d}   segments: {len(segs)}")

    # audio mix
    cuts = [s["start"] for s in segs[1:]]
    music = make_music(total, rng, cuts)
    voice = np.zeros_like(music)
    for s in segs:
        if s.get("audio") is not None:
            i0 = int((s["start"] + 0.2) * SR); v = s["audio"][:max(0, len(voice) - i0)]
            voice[i0:i0 + len(v)] += v
    nfr = int(total * a.fps)
    env = None
    if voiced:
        spf = SR / a.fps
        idx = (np.arange(nfr) * spf).astype(int)
        rms = np.array([np.sqrt(np.mean(voice[i:i + int(spf)] ** 2)) if i < len(voice) else 0 for i in idx])
        env = np.clip(rms / (np.percentile(rms[rms > 0], 90) + 1e-6 if (rms > 0).any() else 1), 0, 1)
        duck = np.convolve(np.abs(voice) > 0.02, np.ones(SR // 5) / (SR // 5), mode="same")
        music = music * (1 - 0.6 * np.clip(duck * 3, 0, 1))
    mix = music * (0.55 if voiced else 1.0) + voice * 0.95
    mix = mix / max(1.0, np.abs(mix).max() / 0.95)
    wav_path = os.path.join(tmp, "mix.wav")
    with wave.open(wav_path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((mix * 32767).astype(np.int16).tobytes())

    # video
    scale = a.res // W
    ov = os.path.join(tmp, "crt.png"); crt_overlay(ov, scale)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    out = os.path.join(a.out, f"veyra_{'horoscope' if HOROSCOPE else 'promo'}_{stamp}.mp4")
    cmd = [ff, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(a.fps), "-i", "-",
           "-i", ov, "-i", wav_path,
           "-filter_complex", f"[0:v]scale={W * scale}:{H * scale}:flags=neighbor[s];[s][1:v]overlay=0:0,format=yuv420p[v]",
           "-map", "[v]", "-map", "2:a", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-tune", "animation",
           "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-shortest", out]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    R = Renderer(segs, total, a, rng, portrait, env)
    import video
    if HOROSCOPE:
        R.hook = ((HOROSCOPE["glyph"],) * 2, (HOROSCOPE["glyph"],) * 2, f"{HOROSCOPE['sign']}, read from the sky", "")
    else:
        z = rng.sample(video.ZODIAC, 4)
        R.hook = (tuple(z[:2]), tuple(z[2:]), "Veyra is growing", "")
    t0 = time.time()
    for fi in range(nfr):
        proc.stdin.write(R.frame(fi))
        if fi % (a.fps * 10) == 0:
            el = time.time() - t0
            eta = el / max(fi, 1) * (nfr - fi)
            print(f"\r  rendering {100 * fi // nfr:3d}%   (about {int(eta)}s left)   ", end="", flush=True)
    proc.stdin.close(); proc.wait()
    print(f"\r  rendering 100%                         ")
    if proc.returncode != 0: sys.exit("ffmpeg failed")

    txt = out[:-4] + ".txt"
    with open(txt, "w", encoding="utf-8") as fh:
        fh.write(f"Veyra promo  |  seed {seed}  |  {time.strftime('%Y-%m-%d %H:%M')}\n\n{script_txt}\n\n"
                 + (f"--- suggested post caption ---\nToday's sky, read by Veyra herself: no API, no websites, just the "
                    f"planets' own orbits. {HOROSCOPE['sign']} and the rest of the zodiac, {HOROSCOPE['date_spoken']}. "
                    f"Questions or want a live reading? Contact {CONTACT_NAME}. #horoscope #astrology #tarot #AI #8bit\n"
                    if HOROSCOPE else
                    f"--- suggested post caption ---\nVeyra is growing: now running {MODEL_LABEL}, locally. "
                    f"Questions or want a live reading? Contact {CONTACT_NAME}. #tarot #AI #8bit\n"))
    if not HOROSCOPE:
        json.dump(sorted(used | {hid(p) for p in picks})[-400:], open(hist_path, "w", encoding="utf-8"))
    shutil.rmtree(tmp, ignore_errors=True)
    print(f"\nDone: {out}\n      {txt}")
    return out

if __name__ == "__main__":
    main()
