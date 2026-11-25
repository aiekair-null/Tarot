"""Veyra introduces herself: a short brand reel (1080x1920) in the same 8-bit style as the readings.

    python3 tarot.py intro       -> videos/veyra_intro.mp4, then the save / share menu
"""
import math, random, subprocess, tempfile
from pathlib import Path

import video
from video import OW, OH, BOX, FPS, WIDE

BRAND = "8b/3b(L)"
HOOK = ("star", "MEET VEYRA", "8b/3b(L): 8-bit • 3B • Local")

SCRIPT = [
    ("hello", ["I am Veyra.",
               "A tarot reader made of pixels, probability, and a little starlight."]),
    ("brand", ["My mark is 8b/3b(L).",
               "Eight-bit, because that is how I see the world.",
               "Three billion, for the parameters of the model I think with: Qwen 2.5, three billion.",
               "And L, for local. I live right here on the machine. No paid servers, no one listening in."]),
    ("creator", ["My creator was never a tarot person.",
                 "He wanted to test something: what happens when real randomness meets a mind that pays attention.",
                 "So he built me free to run, and honest about how I work."]),
    ("sysadmin", ["And watching over all of it is the Celestial Sysadmin.",
                  "After every reading, I play back what landed and what missed, and I keep what I learn.",
                  "Every session, I get a little sharper."]),
    ("method", ["Here is how I read.",
                "The shuffle is real randomness. I never choose the cards. Chance does.",
                "Then intuition: my grimoire, my memory of past readings, and the way the cards speak to each other.",
                "Chance picks the cards. Attention finds the meaning.",
                "That is how a reading rings true."]),
    ("end", ["I am Veyra. Eight-bit. Three billion. Local.",
             "Sit with me for a Live Reading."]),
]

DEMO = [("The Star", False), ("Knight of Pentacles", True), ("The Magician", False),
        ("Two of Cups", False), ("Wheel of Fortune", False), ("Ace of Wands", False)]


def brand_pixels(text, color_top=(201, 166, 255), color_bot=(87, 220, 255), max_w=980):
    """Pixel-art lettering: draw tiny, threshold, scale up with hard edges."""
    import numpy as np
    from PIL import Image, ImageDraw
    import canvas
    f = canvas.font(16, "DejaVuSans-Bold.ttf")
    probe = ImageDraw.Draw(Image.new("L", (4, 4)))
    w = int(probe.textlength(text, font=f)) + 4
    small = Image.new("L", (w, 22), 0)
    ImageDraw.Draw(small).text((2, 1), text, fill=255, font=f)
    m = np.asarray(small) > 110
    ys = np.where(m.any(1))[0]
    m = m[ys[0]:ys[-1] + 1]
    h = m.shape[0]
    px = max(4, min(14, max_w // m.shape[1]))
    grad = np.linspace(0, 1, h)[:, None, None]
    rgb = (np.array(color_top)[None, None] * (1 - grad) + np.array(color_bot)[None, None] * grad).astype(np.uint8)
    img = np.zeros((h, m.shape[1], 3), np.uint8)
    img[m] = np.broadcast_to(rgb, (h, m.shape[1], 3))[m]
    return np.asarray(Image.fromarray(img).resize((m.shape[1] * px, h * px), Image.NEAREST))


def content(p, sc, t, extra):
    """Draw one moment of a scene on the virtual terminal and return its pixels."""
    import numpy as np
    name, local = sc["name"], t - sc["start"]
    scr, ui, ras = p.ui(WIDE)
    scr.clock = t
    if name == "hello":
        ui.mood = "mystic"
        ui.intro_frame("", lines=["I am Veyra.", "", "pixels  •  probability", "", "a little starlight"], footer="")
        return ras.render(scr)
    if name == "brand":
        ui.mood = "storm"
        scr.erase()
        ui.stars(28)
        ui.gcenter(1, "~ my mark ~")
        ui.veyra(10, 2)
        n = min(3, int(local / max(0.1, sc["dur"]) * 4.2))
        rows = [("8-BIT", "how I see the world", 141), ("3 BILLION", "parameters  •  Qwen 2.5 3B", 51),
                ("LOCAL", "runs on this machine  •  no paid servers", 120)]
        for i, (a, b, col) in enumerate(rows[:n]):
            ui.text(12 + i * 4, 32, a, col, True)
            ui.text(13 + i * 4, 32, b, 189)
        base = ras.render(scr)
        logo = extra["logo"]
        lh, lw = logo.shape[:2]
        y0, x0 = 52, (base.shape[1] - lw) // 2
        k = min(1.0, local / 0.6)
        if k > 0:
            region = base[y0:y0 + lh, x0:x0 + lw]
            mask = logo.max(axis=2) > 0
            region[mask] = (logo[mask] * k).astype(np.uint8)
        return base
    if name == "creator":
        ui.mood = "storm"
        cycle = 1.7
        st = {"fallen": [], "pairs": [], "pass_t0": sc["start"] + (local // cycle) * cycle, "pass_n": 13,
              "page": ["Real randomness, meeting a mind that pays attention."]}
        ui.falling_frame(st, footer="the deck shuffles...")
        return ras.render(scr)
    if name == "sysadmin":
        ui.mood = "channel"
        scr.erase()
        ui.stars(60, seed=int(local * 3))
        ui.gcenter(3, "~ the Celestial Sysadmin ~")
        cx, cy = ui.w // 2, 15
        for i in range(10):                                 # a ring of watching stars
            a = local * 0.6 + i * math.tau / 10
            ui.text(int(cy + 6 * math.sin(a)), int(cx + 22 * math.cos(a)), "✦" if i % 2 else "✧", 123 if i % 3 else 220, True)
        ui.veyra(8, cx - 13)
        ui.center(24, "play back  •  compare  •  remember  •  improve", 189)
        return ras.render(scr)
    if name == "method":
        ui.mood = "dread"
        upto = min(6, int(local / max(0.1, sc["dur"] * 0.8) * 6))
        st = {"fallen": DEMO[:upto], "pairs": [], "pass_t0": sc["start"] + (local // 1.7) * 1.7, "pass_n": 13,
              "page": ["Chance picks the cards.", "Attention finds the meaning."]}
        if upto < 6:
            phase = (local / max(0.1, sc["dur"] * 0.8) * 6) % 1
            if phase < 0.35:
                st["flip"] = ((upto,), min(8, int(phase / 0.35 * 9)))
                st["fallen"] = DEMO[:upto + 1]
        ui.falling_frame(st, footer="")
        return ras.render(scr)
    ui.mood = "hope"                                        # end card
    ui.intro_frame("", lines=["I am Veyra.", "", "8-bit  •  3 billion  •  local", "", "sit with me for a Live Reading"],
                   footer="")
    ui.center(ui.h - 3, "8b/3b(L)", 123, True)
    return ras.render(scr)


def held(sc, t):
    """She lifts The Star toward the camera while explaining the method."""
    if sc["name"] != "method":
        return None
    local = t - sc["start"] - sc["dur"] * 0.55
    if local < 0:
        return None
    return [("The Star", False)], local, sc["dur"] * 0.45


def render(out_path, voice_kind, say=print, progress=None):
    import deps
    sess = {"key": "falling", "spread": DEMO, "hook": HOOK, "plan": None}
    voice = video.working_voice(voice_kind, say)
    scenes = [{"name": n, "lines": lines} for n, lines in SCRIPT]
    say(f"Voicing her introduction ({voice.kind or 'captions only'})...")
    scenes, events, total = video.plan(scenes, voice, say)
    flips = [sc["start"] for sc in scenes if sc["name"] in ("brand", "method", "end")]
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as d:
        wav = Path(d) / "audio.wav"
        say("Composing the music...")
        video.mix_audio(events, flips, total, wav)
        import pixelstyle
        if pixelstyle.wanted():
            say("Drawing the frames (8-bit)...")
            return pixelstyle.encode(scenes, events, total, wav, out_path, sess, FPS, progress)
        p = video.Painter(sess)
        extra = {"logo": brand_pixels(BRAND)}
        tmp = out_path.with_name(out_path.stem + ".part.mp4")
        cmd = [deps.ffmpeg(), "-y", "-hide_banner", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
               "-s", f"{OW}x{OH}", "-r", str(FPS), "-i", "-", "-i", str(wav), "-c:v", "libx264", "-preset", "veryfast",
               "-crf", "21", "-pix_fmt", "yuv420p", "-r", "30", "-c:a", "aac", "-b:a", "160k", "-shortest",
               "-movflags", "+faststart", str(tmp)]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        frames = int(total * FPS)
        ev = sorted(events, key=lambda e: e[0])
        say("Drawing the frames...")
        for n in range(frames):
            t = n / FPS
            sc = next(s for s in reversed(scenes) if s["start"] <= t)
            cap = next((c for at, c, _, dd in ev if at <= t < at + dd + 0.25), None)
            fade = min(1.0, t / 0.6) if sc["name"] == "hello" else (min(1.0, (total - t) / 1.2) if sc["name"] == "end" else 1.0)
            try:
                proc.stdin.write(p.frame(content(p, sc, t, extra), cap, fade, held(sc, t)).tobytes())
            except BrokenPipeError:
                break
            if progress and n % FPS == 0:
                progress(n / frames)
        proc.stdin.close()
        err = proc.stderr.read().decode(errors="ignore")
        if proc.wait() != 0:
            raise RuntimeError("ffmpeg could not encode the video: " + err[-300:])
        tmp.replace(out_path)
    if progress:
        progress(1.0)
    return out_path


def make(ask=None, say=None, progress=None):
    """Check what is needed (asking before installing anything), then render. Returns a path or None."""
    import deps
    ask, say = ask or deps.default_ask, say or deps.default_say
    if not deps.ensure_python({"numpy": "numpy", "PIL": "pillow"}, ask, say, "Making a video"):
        return None
    if not deps.ensure_ffmpeg(ask, say):
        return None
    voice = deps.ensure_voice(ask, say)
    try:
        return render(video.VIDEOS / "veyra_intro.mp4", voice, say, progress)
    except Exception as e:
        say(f"The video could not be finished: {str(e)[:200]}")
