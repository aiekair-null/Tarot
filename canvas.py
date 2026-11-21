"""A virtual terminal for drawing Veyra's scenes into video frames: no curses, no screen.
The ritual UI draws onto VirtualScreen exactly as it draws onto a real terminal; Raster turns
the cells (character, foreground, background) into pixels the same way a terminal would."""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
FONT_DIRS = [os.path.join(HERE, "assets"), "/usr/share/fonts/truetype/dejavu", "/usr/share/fonts/dejavu",
             "/Library/Fonts", "C:\\Windows\\Fonts"]


def xterm_rgb(i):
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


def font(size, name="DejaVuSansMono.ttf"):
    """A TrueType font from the bundled assets (or the system); Pillow's built-in font as a last resort."""
    from PIL import ImageFont
    for d in FONT_DIRS:
        p = os.path.join(d, name)
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    try:
        return ImageFont.load_default(size=size)
    except TypeError:                      # very old Pillow
        return ImageFont.load_default()


class VirtualScreen:
    """The subset of a curses window the UI uses. `clock` is the video time in seconds."""
    virtual = True

    def __init__(self, rows, cols):
        self.rows, self.cols, self.clock = rows, cols, 0.0
        self.erase()

    def erase(self):
        self.buf = [[(" ", 153, 16, False)] * self.cols for _ in range(self.rows)]

    def getmaxyx(self):
        return self.rows, self.cols

    def addstr(self, y, x, s, a=0):
        if not 0 <= y < self.rows:
            return
        fg, bg, bold = (153, 16, False) if not a else (a & 0xFF, (a >> 8) & 0xFF, bool((a >> 16) & 1))
        row = self.buf[y]
        for i, ch in enumerate(s):
            if 0 <= x + i < self.cols:
                row[x + i] = (ch, fg, bg, bold)

    def keypad(self, *_):
        pass

    def timeout(self, *_):
        pass

    def bkgd(self, *_):
        pass

    def refresh(self):
        pass

    def getch(self):
        return -1


class Raster:
    """Cells to pixels, with a tile cache so a frame costs one array copy per visible cell."""
    BLOCKS = {"█": (0, 0, 1, 1), "▀": (0, 0, 1, .5), "▄": (0, .5, 1, 1), "▌": (0, 0, .5, 1), "▐": (.5, 0, 1, 1),
              "▗": (.5, .5, 1, 1), "▖": (0, .5, .5, 1), "▝": (.5, 0, 1, .5), "▘": (0, 0, .5, .5)}

    def __init__(self, cw, ch):
        self.cw, self.ch, self.cache = cw, ch, {}
        size = int(min(ch * 0.8, cw / 0.6 * 0.95))     # fill the cell like a terminal font does
        self.font = font(size)
        self.bold = font(size, "DejaVuSansMono-Bold.ttf")

    def tile(self, ch, fg, bg, bold):
        key = (ch, fg, bg, bold)
        t = self.cache.get(key)
        if t is None:
            import numpy as np
            from PIL import Image, ImageDraw
            img = Image.new("RGB", (self.cw, self.ch), xterm_rgb(bg))
            d = ImageDraw.Draw(img)
            if ch in self.BLOCKS:
                x0, y0, x1, y1 = self.BLOCKS[ch]
                d.rectangle([round(x0 * self.cw), round(y0 * self.ch), round(x1 * self.cw) - 1, round(y1 * self.ch) - 1],
                            fill=xterm_rgb(fg))
            elif ch.strip():
                d.text((self.cw / 2, self.ch / 2), ch, fill=xterm_rgb(fg), font=self.bold if bold else self.font,
                       anchor="mm")
            t = self.cache[key] = np.asarray(img)
        return t

    def render(self, screen):
        import numpy as np
        out = np.zeros((screen.rows * self.ch, screen.cols * self.cw, 3), dtype=np.uint8)
        for y, row in enumerate(screen.buf):
            for x, (ch, fg, bg, bold) in enumerate(row):
                if bg == 16 and not ch.strip():
                    continue
                out[y * self.ch:(y + 1) * self.ch, x * self.cw:(x + 1) * self.cw] = self.tile(ch, fg, bg, bold)
        return out
