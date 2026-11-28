"""Veyra's eyes: she can look at your screen when you ask her about something on it.

Her model reads text, not pictures, so she "sees" through a screenshot read by OCR: every piece of text on the
screen (menus, buttons, titles, error boxes, page text) with where it sits. Icons, photos and colours are not
visible to her. You approve every look; the screenshot is made in a temp file, read on this computer and
deleted at once. Nothing is saved or sent anywhere.

    SCREEN:            she asks to look (optionally with a note of what she is looking for)

Needs a screenshot tool (grim on Wayland; scrot/maim/spectacle/gnome-screenshot, or Pillow/mss on X11) and
an OCR engine (the rapidocr-onnxruntime package, installed by `veyra setup`, or the tesseract program)."""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from hands import rl_safe

ON = os.name != "nt"
LIMIT = 3500
BLUE, WHITE, DIM, RESET = "\x1b[38;5;117m", "\x1b[38;5;231m", "\x1b[38;5;245m", "\x1b[0m"

HOW = ("\nYOU CAN LOOK AT THEIR SCREEN. When they ask about something on the screen (a window, a button, an error "
       "box, a page they are reading), write ONE line and stop:\n"
       "SCREEN: <what you are looking for>\n"
       "They approve it first. You get back every piece of text on the screen with its place (y = percent from "
       "the top, x = percent from the left). You cannot see pictures, icons or colours, only words, and their "
       "own terminal with this chat is on the screen too. Answer from what you read, say where on the screen "
       "things are, and if the text doesn't show what they mean, say so and ask them to describe it.")


def approve(note=""):
    print(f"\n{BLUE}  ┌ she wants to look at your screen{RESET}" + (f"{DIM}  ({note[:60]}){RESET}" if note else ""))
    print(f"{DIM}  │ a screenshot, read here by OCR and deleted at once; nothing is saved or sent{RESET}")
    while True:
        try:
            a = input(rl_safe(f"{BLUE}  └ let her look? [y]es / [n]o: {RESET}")).strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return False
        if a in ("y", "yes"):
            return True
        if a in ("n", "no", ""):
            return False


def _shot(path):
    """Take a screenshot into `path`; returns '' or why it couldn't."""
    if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        return "there is no desktop session on this terminal, so there is no screen to look at"
    tools = [["grim", path], ["spectacle", "-b", "-n", "-f", "-o", path], ["gnome-screenshot", "-f", path],
             ["maim", path], ["scrot", "-o", path], ["import", "-window", "root", path]]
    for t in tools:
        if shutil.which(t[0]):
            try:
                subprocess.run(t, capture_output=True, timeout=20)
            except Exception:
                continue
            if os.path.exists(path) and os.path.getsize(path) > 0:
                return ""
    try:
        from PIL import ImageGrab
        ImageGrab.grab().save(path)
        return ""
    except Exception:
        pass
    try:
        import mss
        import mss.tools
        with mss.mss() as sct:
            shot = sct.grab(sct.monitors[0])
            mss.tools.to_png(shot.rgb, shot.size, output=path)
        return ""
    except Exception:
        pass
    wl = " (Wayland needs grim)" if os.environ.get("WAYLAND_DISPLAY") else ""
    return "no screenshot tool worked" + wl + "; run  veyra setup  to add mss and Pillow, or install scrot/grim"


def _ocr(path):
    """Boxes of text as (x, y, w, h, text), or (None, why)."""
    try:
        from rapidocr_onnxruntime import RapidOCR
        res, _ = RapidOCR()(path)
        boxes = []
        for pts, text, _conf in res or []:
            xs, ys = [p[0] for p in pts], [p[1] for p in pts]
            boxes.append((min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys), str(text)))
        return boxes, ""
    except ImportError:
        pass
    except Exception as e:
        return None, f"the OCR engine failed: {str(e).splitlines()[0][:120] if str(e) else type(e).__name__}"
    if shutil.which("tesseract"):
        try:
            out = subprocess.run(["tesseract", path, "stdout", "tsv"], capture_output=True, text=True, timeout=90).stdout
        except Exception as e:
            return None, f"tesseract failed: {e}"
        lines = {}
        for row in out.splitlines()[1:]:
            c = row.split("\t")
            if len(c) < 12 or c[0] != "5" or not c[11].strip() or float(c[10]) < 30:
                continue
            key = (c[2], c[3], c[4])
            x, y, w, h = (int(v) for v in c[6:10])
            if key in lines:
                a = lines[key]
                lines[key] = (min(a[0], x), min(a[1], y), max(a[0] + a[2], x + w) - min(a[0], x),
                              max(a[1] + a[3], y + h) - min(a[1], y), a[4] + " " + c[11].strip())
            else:
                lines[key] = (x, y, w, h, c[11].strip())
        return list(lines.values()), ""
    return None, "there is no OCR engine yet: run  veyra setup  (it adds rapidocr-onnxruntime)"


def describe(boxes, size):
    """Turn text boxes into rows she can read: 'y12%  File (x2%)  Edit (x6%)'."""
    W, H = size
    if not boxes:
        return "(the screen shows no readable text)"
    rows = []
    for b in sorted(boxes, key=lambda b: (b[1] + b[3] / 2, b[0])):
        cy = b[1] + b[3] / 2
        if rows and abs(cy - rows[-1]["cy"]) <= max(6, b[3] * 0.6):
            rows[-1]["items"].append(b)
        else:
            rows.append({"cy": cy, "items": [b]})
    out = [f"[screen {W}x{H}; y = percent from the top, x = percent from the left]"]
    for r in rows:
        items = sorted(r["items"], key=lambda b: b[0])
        out.append(f"y{round(100 * r['cy'] / H):02d}%  " + "   ".join(
            f"{b[4].strip()} (x{round(100 * b[0] / W)}%)" for b in items if b[4].strip()))
    text = "\n".join(out)
    return text if len(text) <= LIMIT else text[:LIMIT] + "\n...(cut: the screen has more text)"


def look():
    """Screenshot -> OCR -> a description of the text on the screen. The picture is deleted."""
    d = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "veyra"
    d.mkdir(parents=True, exist_ok=True)
    fd, path = tempfile.mkstemp(suffix=".png", dir=str(d))
    os.close(fd)
    try:
        why = _shot(path)
        if why:
            return f"(could not look: {why})"
        try:
            from PIL import Image
            with Image.open(path) as im:
                size = im.size
        except Exception:
            size = None
        boxes, why = _ocr(path)
        if boxes is None:
            return f"(could not read the screen: {why})"
        if size is None:
            size = (max([b[0] + b[2] for b in boxes] or [1]), max([b[1] + b[3] for b in boxes] or [1]))
        return describe(boxes, size)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass
