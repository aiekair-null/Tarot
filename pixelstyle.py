"""Every Veyra video in the promo's 8-bit style.

video.py (readings) and promo.py (the intro) plan their scenes, voice and music as before; this module
draws the frames with the promo renderer's look (veyra_promo.py): dithered sanctum, twinkling stars,
pixel Veyra who talks, typed caption cards, bloom, vignette, CRT scanlines and glitch cuts.
Set TAROT_VIDEO_STYLE=classic for the old look."""
import math
import os
import random
import subprocess
import tempfile
import textwrap
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import veyra_promo as VP
from veyra_promo import W, H, put_text, hexrgb, spring, ease_out_cubic, paste_glow, paste_card

SCALE = 4                       # 270x480 -> 1080x1920
GOLD, CYAN, WHITE, LILAC, RED = hexrgb("#ffd36b"), hexrgb("#4ff0ff"), (240, 232, 255), hexrgb("#b9a6e8"), (255, 90, 110)


def wanted(trip=False):
    return os.environ.get("TAROT_VIDEO_STYLE", "pixel").lower() != "classic" and not trip


# ---------------------------------------------------------------- cards as pixel sprites
def _xterm(i):
    if i < 16:
        return [(0, 0, 0), (128, 0, 0), (0, 128, 0), (128, 128, 0), (0, 0, 128), (128, 0, 128), (0, 128, 128),
                (192, 192, 192), (128, 128, 128), (255, 0, 0), (0, 255, 0), (255, 255, 0), (0, 0, 255),
                (255, 0, 255), (0, 255, 255), (255, 255, 255)][i]
    if i < 232:
        v = (0, 95, 135, 175, 215, 255)
        i -= 16
        return v[i // 36], v[(i // 6) % 6], v[i % 6]
    g = 8 + (i - 232) * 10
    return g, g, g


_CARDS = {}


def card_image(card, rev=False):
    """The real card art from art.py (all 78 cards) as a 24x34 pixel sprite with its suit-colored border."""
    key = (card, bool(rev))
    if key in _CARDS:
        return _CARDS[key]
    import art
    try:
        _, border, _ = art.tags(card)
        px = art.card_pixels(card, 18, 20)
    except Exception:
        _CARDS[key] = VP.card_sprite("face", hash(card) % 997, 24, 34)
        return _CARDS[key]
    w, h = 24, 34
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    b = _xterm(border)
    d.rectangle((0, 0, w - 1, h - 1), fill=_xterm(art.CARD_BG), outline=b)
    d.rectangle((1, 1, w - 2, h - 2), outline=tuple(c // 2 for c in b))
    pic = Image.new("RGBA", (18, 20), (0, 0, 0, 0))
    for y, row in enumerate(px):
        for x, c in enumerate(row):
            if c is not None:
                pic.putpixel((x, y), _xterm(c) + (255,))
    im.paste(pic, (3, 4), pic)
    for x in range(4, w - 4, 2):                     # the little rule under the picture
        d.point((x, 27), fill=b)
    d.rectangle((w // 2 - 1, 29, w // 2 + 1, 31), fill=b)
    if rev:
        im = im.rotate(180)
    _CARDS[key] = im
    return im


def card_back():
    return VP.card_sprite("back", 0, 24, 34)


# ---------------------------------------------------------------- the painter
class Look:
    def __init__(self, scenes, events, total, sess=None, fps=15, seed=None):
        self.scenes, self.total, self.sess, self.fps = scenes, total, sess or {}, fps
        rng = random.Random(seed if seed is not None else random.SystemRandom().randrange(1 << 30))
        self.R = VP.Renderer([], total, SimpleNamespace(fps=fps), rng, None, None)
        self.back = card_back()
        self.events = sorted(events, key=lambda e: e[0])
        self.chunks = self._chunks()
        self.spread = [tuple(c) for c in self.sess.get("spread") or []]
        try:
            from spreads import SPREADS
            self.labels = [p[0] for p in SPREADS[self.sess.get("key")]["positions"]]
        except Exception:
            self.labels = []
        self.log = (self.sess.get("falls") or {}).get("log") or []
        real = self.all_cards()[:5]
        if real:                                          # the end fan shows the cards she actually drew
            self.R.endcards = [card_image(c, r) for c, r in real]

    # ---- captions: every voiced line becomes typed caption cards
    def _chunks(self):
        out = []
        for at, cap, audio, dur in self.events:
            sents = [s for s in VP.re.split(r"(?<=[.!?])\s+", str(cap)) if s]
            parts, cur = [], ""
            for s in sents:
                if len(cur) + len(s) + 1 > 118 and cur:
                    parts.append(cur); cur = s
                else:
                    cur = (cur + " " + s).strip()
            if cur:
                parts.append(cur)
            n = sum(len(p) for p in parts) or 1
            t0 = at
            for p in parts:
                d = dur * len(p) / n
                out.append({"text": p, "t0": t0, "t1": t0 + d, "lines": textwrap.wrap(p, 40), "voiced": audio is not None})
                t0 += d
            if out:
                out[-1]["t1"] = at + dur + 0.25
        return out

    def env(self, t):
        for c in self.chunks:
            if c["t0"] <= t < c["t0"] + min(c["t1"] - c["t0"], len(c["text"]) / 14):
                return 0.45 + 0.55 * abs(math.sin(t * 17.0)) * (0.6 + 0.4 * math.sin(t * 5.3))
        return 0.0

    # ---- which card(s) a scene shows
    def scene_cards(self, sc):
        if sc.get("card") is not None and sc["card"] < len(self.spread):
            i = sc["card"]
            label = self.labels[i] if i < len(self.labels) else f"CARD {i + 1}"
            return [self.spread[i]], label, self.spread[:i]
        if "event" in sc and sc["event"] < len(self.log):
            e = self.log[sc["event"]]
            cards = [tuple(c) for c in e.get("cards", [])]
            slot = e.get("slot", sc["event"])
            label = self.labels[slot] if isinstance(slot, int) and slot < len(self.labels) else f"FALL {sc['event'] + 1}"
            before = [tuple(c) for x in self.log[:sc["event"]] for c in x.get("cards", [])]
            return cards, label, before
        return None, None, None

    def all_cards(self):
        if self.log:
            return [tuple(c) for e in self.log for c in e.get("cards", [])]
        return self.spread

    # ---- scenes
    def title(self, f, t, lt, env):
        R = self.R
        f.paste(R.bg_img["sanctum"]); R.sky(f, t, "sanctum")
        f.paste(R.moon, (206, 34), R.moon); R.motes_(f, t, (200, 150, 255))
        paste_glow(f, R.aura, 135, 150, 0.35 + 0.15 * math.sin(t * 2))
        x = 135 - 5 * VP.CW * 6 // 2
        for i, ch in enumerate("VEYRA"):
            k = spring((lt - 0.15 - i * 0.12) / 0.6)
            if k > 0:
                put_text(f, x, int(70 - (1 - k) * 60), ch, GOLD, scale=6, shadow=hexrgb("#5a2f9a"))
            x += VP.CW * 6
        if lt > 1.0:
            q = (self.sess.get("question") or "").strip()
            put_text(f, 135, 150, "A LIVE READING" if self.log else ("TONIGHT'S READING" if q else "8-BIT TAROT"),
                     WHITE, scale=2, center=True)
            for i, line in enumerate(textwrap.wrap(q if q.lower() != "a live reading" else "", 40)[:3]):
                put_text(f, 135, 176 + i * 13, line, CYAN, center=True)
        R.draw_veyra(f, t, env, 135, 205, scale=1.1)
        put_text(f, 135, 330, VP.BRAND + "  //  LOCAL  //  8-BIT", (120, 100, 170), center=True)

    def card_scene(self, f, t, lt, env, cards, label, before):
        R = self.R
        f.paste(R.bg_img["sanctum"]); R.sky(f, t, "sanctum"); R.motes_(f, t, (200, 150, 255))
        d = ImageDraw.Draw(f)
        d.rectangle((0, 300, W, H), fill=hexrgb("#170726"))
        d.line([(0, 300), (W, 300)], fill=GOLD)
        R.draw_veyra(f, t, env, 38, 30, scale=0.62, aura=False)
        put_text(f, 150, 34, label.upper()[:22], GOLD, scale=2, center=True)
        n = len(cards)
        sc = 4 if n == 1 else 3 if n == 2 else 2
        gap = 24 * sc + 10
        for j, (card, rev) in enumerate(cards):
            cx, cy = 135 + (j - (n - 1) / 2) * gap, 176
            p = min(1.0, max(0.0, (lt - j * 0.25) / 0.55))
            drop = (1 - ease_out_cubic(min(1, p * 1.6))) * -90
            paste_glow(f, R.aura, cx, cy, 0.55 + 0.2 * math.sin(t * 2))
            face = card_image(card, rev)
            sp = face if p >= 0.5 else self.back
            big = sp.resize((sp.width * sc, sp.height * sc), Image.NEAREST)
            paste_card(f, big, cx, cy + drop, max(0.05, abs(2 * p - 1)))
        if lt > 0.6:
            names = " + ".join(c for c, _ in cards)
            s = 2 if len(names) <= 20 else 1
            put_text(f, 135, 254 if s == 2 else 258, names.upper()[:44], WHITE, scale=s, center=True)
            if any(r for _, r in cards):
                put_text(f, 135, 280, "REVERSED", RED, center=True)
        for j, (card, rev) in enumerate(before[-9:]):           # what is already on the table
            m = card_image(card, rev)
            f.paste(m, (int(135 - len(before[-9:]) * 14 + j * 28), 308), m)
        R.header(f, t, "READING")

    def table_scene(self, f, t, lt, env):
        R = self.R
        f.paste(R.bg_img["sanctum"]); R.sky(f, t, "sanctum"); R.motes_(f, t, (255, 210, 120))
        cards = self.all_cards()[:15]
        per = 5 if len(cards) > 6 else max(1, len(cards))
        sc = 2 if len(cards) > 3 else 3
        cw, chh = 24 * sc + 4, 34 * sc + 6
        rows = [cards[i:i + per] for i in range(0, len(cards), per)]
        y0 = 70 if len(rows) > 1 else 110
        for r, row in enumerate(rows):
            for j, (card, rev) in enumerate(row):
                k = spring((lt - (r * per + j) * 0.08) / 0.6)
                if k <= 0:
                    continue
                cx = 135 + (j - (len(row) - 1) / 2) * cw
                cy = y0 + r * chh + chh / 2 + (1 - min(k, 1)) * 60
                im = card_image(card, rev)
                big = im.resize((im.width * sc, im.height * sc), Image.NEAREST)
                f.paste(big, (int(cx - big.width / 2), int(cy - big.height / 2)), big)
        put_text(f, 135, 34, "THE SPREAD", GOLD, scale=2, center=True)
        R.header(f, t, "TABLE")

    # ---- one frame
    def frame(self, n):
        t = n / self.fps
        sc = next((s for s in reversed(self.scenes) if s["start"] <= t), self.scenes[0])
        lt, name, env = t - sc["start"], sc["name"], self.env(t)
        R, f = self.R, Image.new("RGB", (W, H))
        cap_y = 344
        if name in ("intro", "hello") or (sc is self.scenes[0] and not name.startswith(("card", "drop"))):
            self.title(f, t, lt, env)
            cap_y = 352
        elif name == "end":
            R.end(f, t, None, env, lt); R.header(f, t, "END"); cap_y = 372
        elif name == "table":
            self.table_scene(f, t, lt, env)
        else:
            cards, label, before = self.scene_cards(sc)
            if cards:
                self.card_scene(f, t, lt, env, cards, label, before)
            else:
                R.sanctum(f, t, None, env)
                idx = sum(1 for c in self.chunks if sc["start"] <= c["t0"] <= t)
                if idx % 2 == 1:                                 # jump-cut punch-in on each new caption
                    z = 1.14; cw, chh = int(W / z), int(276 / z)
                    crop = f.crop((W // 2 - cw // 2, 150 - chh // 2, W // 2 - cw // 2 + cw, 150 - chh // 2 + chh))
                    f.paste(crop.resize((W, 276), Image.NEAREST), (0, 20))
                R.header(f, t, "LIVE")
        R.caption(f, t, {"chunks": self.chunks}, env, y0=cap_y)
        R.progress(f, t)
        arr = np.asarray(f).astype(np.float32)
        lum = arr.max(axis=2)
        mask = np.clip((lum - 165) / 90, 0, 1)[..., None]
        bright = Image.fromarray((arr * mask).astype(np.uint8)).filter(ImageFilter.GaussianBlur(3.2))
        arr = (arr + 0.6 * np.asarray(bright, np.float32)) * R.vign
        if lt < 0.22 and sc is not self.scenes[0]:                 # glitch on every hard cut
            k = 1 - lt / 0.22
            r = np.random.default_rng(n)
            for _ in range(int(3 + 7 * k)):
                y0, h = r.integers(0, H - 10), r.integers(2, 18)
                arr[y0:y0 + h] = np.roll(arr[y0:y0 + h], int(r.integers(-24, 24) * k), axis=1)
            s = int(1 + 4 * k)
            arr[..., 0] = np.roll(arr[..., 0], s, axis=1)
            arr[..., 2] = np.roll(arr[..., 2], -s, axis=1)
        fade = 1.0 if name != "end" else min(1.0, max(0.0, (self.total - t) / 1.2))
        return np.clip(arr * fade, 0, 255).astype(np.uint8).tobytes()


def encode(scenes, events, total, wav, out_path, sess=None, fps=15, progress=None):
    """Draw every frame in the promo style and encode with the audio already mixed in wav."""
    import deps
    out_path = Path(out_path)
    look = Look(scenes, events, total, sess, fps)
    with tempfile.TemporaryDirectory() as d:
        crt = os.path.join(d, "crt.png")
        VP.crt_overlay(crt, SCALE)
        tmp = out_path.with_name(out_path.stem + ".part.mp4")
        cmd = [deps.ffmpeg(), "-y", "-hide_banner", "-loglevel", "error",
               "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(fps), "-i", "-",
               "-i", crt, "-i", str(wav),
               "-filter_complex", f"[0:v]scale={W * SCALE}:{H * SCALE}:flags=neighbor[s];[s][1:v]overlay=0:0,format=yuv420p[v]",
               "-map", "[v]", "-map", "2:a", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-tune", "animation",
               "-r", "30", "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", str(tmp)]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        frames = int(total * fps)
        for n in range(frames):
            try:
                proc.stdin.write(look.frame(n))
            except BrokenPipeError:
                break
            if progress and n % fps == 0:
                progress(n / frames)
        proc.stdin.close()
        err = proc.stderr.read().decode(errors="ignore")
        if proc.wait() != 0:
            raise RuntimeError("ffmpeg could not encode the video: " + err[-300:])
        tmp.replace(out_path)
    if progress:
        progress(1.0)
    return out_path
