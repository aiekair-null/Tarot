"""8-bit pixel art: Veyra, all 78 cards, card backs and the pixel title.

Every sprite is a grid of palette letters ('.' = transparent). Two pixel rows share one
terminal cell using the half-block trick (top pixel = foreground of '▀', bottom = background),
so a 16x16 sprite fills 16 columns x 8 rows. The same cell grids feed both the curses ritual
and plain ANSI printing, so the art looks identical everywhere."""
import os

# Some terminal fonts have no block glyphs (▀ ▄ █): they draw a little box with the hex code in it
# instead, so solid pixels vanish into the table and faint digits show through the art. Full pixels are
# therefore always drawn as coloured spaces, which every font can show. TAROT_BLOCKS=0 does the same for
# half pixels too (blockier, but nothing depends on the font at all).
BLOCKS = os.environ.get("TAROT_BLOCKS", "1") != "0"
PLAIN = str.maketrans({"█": "#", "▀": '"', "▄": "_", "▌": "|", "▐": "|", "░": ".",
                       "▗": ".", "▖": ".", "▝": "'", "▘": "'"})


def solid(ch, fg, bg):
    """One cell as the terminal should draw it: full blocks become coloured spaces."""
    if ch == "█" or (not BLOCKS and ch in "▀▄"):
        return " ", fg, fg
    return ch, fg, bg


# A terminal window that isn't decoding UTF-8 (a Latin-1 xterm) shows every symbol as 'â' junk. There Veyra
# speaks plain ASCII: each symbol becomes one ASCII character, so every layout keeps its width.
ASCII = False
_ASCII = str.maketrans({
    "\u00b7": ".", "\u2013": "-", "\u2014": "-", "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"',
    "\u2022": "*", "\u2026": ".", "\u2039": "<", "\u203a": ">", "\u2190": "<", "\u2191": "^", "\u2192": ">",
    "\u2193": "v", "\u221e": "8", "\u2234": ":", "\u2235": ":", "\u2248": "~", "\u232c": "*", "\u235f": "*",
    "\u2500": "-", "\u2501": "-", "\u2502": "|", "\u2503": "|", "\u2504": "-", "\u2523": "+", "\u2533": "+",
    "\u253b": "+", "\u254b": "+", "\u254d": "-", "\u2550": "=", "\u2580": '"', "\u2584": "_", "\u2588": "#",
    "\u258c": "|", "\u2590": "|", "\u2591": ".", "\u2592": ":", "\u2593": "#", "\u2594": "-", "\u2596": ".",
    "\u2597": ".", "\u2598": "'", "\u259d": "'", "\u25a0": "#", "\u25a1": "o", "\u25ac": "=", "\u25b0": "#",
    "\u25b1": "-", "\u25b6": ">", "\u25bc": "v", "\u25c6": "*", "\u25c7": "*", "\u25c9": "@", "\u25cb": "o",
    "\u25cc": ".", "\u25cf": "@", "\u25d0": "o", "\u25d1": "o", "\u25d2": "o", "\u25d3": "o", "\u25dc": ".",
    "\u25dd": ".", "\u25de": ".", "\u25df": ".", "\u2600": "*", "\u2605": "*", "\u263d": "(", "\u263e": ")",
    "\u2699": "*", "\u2712": "~", "\u2717": "x", "\u2726": "*", "\u2727": "+", "\u00a0": " ",
    **{chr(c): "*" for c in range(0x2648, 0x2654)},                              # the zodiac signs
})


def _fold(ch):
    import unicodedata
    return (unicodedata.normalize("NFKD", ch).encode("ascii", "ignore").decode() or "?")[:1]


def plain(s):
    """Text as this terminal can show it: block glyphs swapped for fonts without them (TAROT_BLOCKS=0),
    and everything ASCII on a terminal that isn't decoding UTF-8."""
    if ASCII:
        s = s.translate(_ASCII)
        return s if s.isascii() else "".join(c if c < "\x80" else _fold(c) for c in s)
    return s if BLOCKS else s.translate(PLAIN)

# palette letter -> xterm-256 color index
PAL = {
    "k": 16, "d": 238, "g": 246, "w": 231, "y": 220, "Y": 178, "o": 208, "r": 160, "R": 88,
    "p": 211, "m": 170, "v": 98, "u": 55, "b": 33, "B": 25, "n": 18, "c": 51, "t": 30,
    "G": 34, "l": 120, "z": 94, "Z": 58, "s": 223, "S": 180, "h": 189,
    "e": 51, "O": 63, "*": 231,           # Veyra's eyes and orb (recolored when animated)
}
CARD_BG = 17        # navy card face
TABLE_BG = 16       # black table
BORDER = {"major": 220, "Wands": 208, "Cups": 51, "Swords": 250, "Pentacles": 34}
SUIT_X = {"Wands": "r", "Cups": "b", "Swords": "v", "Pentacles": "G"}   # court robe color
ELEMENT_WORD = {"Wands": "fire", "Cups": "water", "Swords": "air", "Pentacles": "earth"}
ROMAN = ["0", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII", "XIII",
         "XIV", "XV", "XVI", "XVII", "XVIII", "XIX", "XX", "XXI"]
RANK_TAG = {"Ace": "A", "Two": "2", "Three": "3", "Four": "4", "Five": "5", "Six": "6", "Seven": "7",
            "Eight": "8", "Nine": "9", "Ten": "10", "Page": "P", "Knight": "Kn", "Queen": "Q", "King": "K"}
PIP_COUNT = {"Two": 2, "Three": 3, "Four": 4, "Five": 5, "Six": 6, "Seven": 7, "Eight": 8, "Nine": 9, "Ten": 10}

# ---------------------------------------------------------------- Veyra (26 x 28 px)
VEYRA = [
    "..........uuuuuu..........",
    "........uuvvvvvvuu........",
    ".......uvvvvvvvvvvu.......",
    "......uvvvvvvvvvvvvu......",
    ".....uvvvvhhhhhhvvvvu.....",
    "....uvvvhhhhyyhhhhvvvu....",
    "....uvvhhhyyyyyyhhhvvu....",
    "...uvvhhSssssssssShhvvu...",
    "...uvvhhsssssssssshhvvu...",
    "...uvvhhsseesseesshhvvu...",
    "...uvvhhssssSSsssshhvvu...",
    "...uvvhhsssppppssshhvvu...",
    "...uvvhhhSssssssShhhvvu...",
    "...uvvhhhhhsssshhhhhvvu...",
    "..uvvhhhhuuyyyyuuhhhhvvu..",
    ".uvvvhhhuvvvyyvvvuhhhvvvu.",
    ".uvvvhhuvvvvyyvvvvuhhvvvu.",
    "uvvvvhuvvvvvyyvvvvvuhvvvvu",
    "uvvvvvvvvvvOOOOvvvvvvvvvvu",
    "uvvvvvvvvvO**OOOvvvvvvvvvu",
    "uvvvvvvvvsO*OOOOsvvvvvvvvu",
    "uvvvvvvsssOOOOOOsssvvvvvvu",
    "uvvvvvvvsssOOOOsssvvvvvvvu",
    "uvvvvvvvvvyyyyyyvvvvvvvvvu",
    "uvvvvvvvvvvyyyyvvvvvvvvvvu",
    "uuvvvvvvvvvvvvvvvvvvvvvvuu",
    "nnnnynnnnnnnnnnnnnnnnynnnn",
    "nnnnnnnnnnnnnnnnnnnnnnnnnn",
]

# ---------------------------------------------------------------- Major Arcana (16 x 16 px)
MAJORS = {
    "The Fool": [
        "............yyy.", "...........yyyyy", "............yyy.", "......ss.......r",
        ".....ssss.....zr", "......ss.....z..", "....yyyyyy..z...", "...yyyyyyyyz....",
        "...y.wwwwwy.....", "....wwwwww......", "....ww..ww......", "...ww....ww.....",
        "..zz......zz....", "GGGGGGGGGGG.....", "ZZZZZZZZZZ......", "ZZZZZZZZZ......."],
    "The Magician": [
        "...yy....yy.....", "..y..y..y..y....", "..y...yy...y....", "..y..y..y..y....",
        "...yy....yy.....", "................", "......ss....w...", ".....ssss..w....",
        "......ss..w.....", "....rrrrrrw.....", "...rrrrrrr......", "...rrrrrrr......",
        "zzzzzzzzzzzzzzz.", ".zo..c..w..y.z..", ".z...........z..", ".z...........z.."],
    "The High Priestess": [
        "ddd..........www", "dgd...yyyy...wgw", "ddd..y........ww", "ddd..y........ww",
        "ddd...yyyy...www", "ddd....ss....www", "ddd...ssss...www", "ddd....ss....www",
        "ddd...bbbb...www", "ddd..bbwbbb..www", "ddd..bwwwbb..www", "ddd..bbwbbb..www",
        "ddd..bbbbbb..www", "ddd.bbbbbbbb.www", "dddddddddddwwwww", "gggggggggggggggg"],
    "The Empress": [
        "..y...y..y...y..", "................", ".....pppppp.....", "....pp....pp....",
        "...pp......pp...", "...pp......pp...", "...pp......pp...", "....pp....pp....",
        ".....pppppp.....", ".......pp.......", "..y..pppppp..y..", ".yYy...pp...yYy.",
        "..Y....pp....Y..", "..G..........G..", "..G..........G..", "GGGGGGGGGGGGGGGG"],
    "The Emperor": [
        "................", "..y...y..y...y..", "..yy.yyyyyy.yy..", "..yyyyyyyyyyyy..",
        "..yryyyrryyyry..", "..yyyyyyyyyyyy..", "....ssssssss....", "..g.skssssks.g..",
        ".ggg.ssssss.ggg.", "g..g.sswwss.g..g", "...g..wwww..g...", ".....rrrrrr.....",
        "....rrrrrrrr....", "...rrrrrrrrrr...", "..dddddddddddd..", "..dd........dd.."],
    "The Hierophant": [
        ".......yy.......", "......yyyy......", ".....yyrryy.....", "......yyyy......",
        ".....yyyyyy.....", "....yyrrrryy....", ".....yyyyyy.....", "....yyyyyyyy....",
        "...yyrrrrrryy...", "...yyyyyyyyyy...", "................", "..yy........gg..",
        "..yyy......ggg..", "....yy....gg....", "......yggg......", "....gg....yy...."],
    "The Lovers": [
        ".....yyyyyy.....", "....yyyyyyyy....", ".....yyyyyy.....", "................",
        "...rr......rr...", "..rrrr....rrrr..", "..rrrrrrrrrrrr..", "...rrrrrrrrrr...",
        ".....rrrrrr.....", ".......rr.......", "..ss........ss..", ".ssss......ssss.",
        "..ss........ss..", ".wwww......pppp.", ".wwww......pppp.", ".w..w......p..p."],
    "The Chariot": [
        ".uuuuuuuuuuuuuu.", ".uwuuuwuuuwuuuw.", "..y..........y..", "..y...ssss...y..",
        "..y...skks...y..", "..y..gggggg..y..", "..yggggggggggy..", "..bbbbbbbbbbbb..",
        "..bbbbyyyybbbb..", "..bbbbbbbbbbbb..", "..dd........dd..", ".dgd........dgd.",
        ".dggd......dggd.", "..dd........dd..", "wwww........kkkk", "ww.w........k.kk"],
    "Strength": [
        "....yy...yy.....", "...y..y.y..y....", "....yy...yy.....", "................",
        "....oooooooo....", "...oozzzzzzoo...", "..oozyyyyyyzoo..", "..ozyykyykyyzo..",
        "..ozyyyyyyyyzo..", "..ozyyykkyyyzo..", "..oozyyrryyzoo..", "...oozyyyyzoo...",
        "....oozzzzoo....", ".....oooooo.....", "......oooo......", "................"],
    "The Hermit": [
        "................", "....ddd.........", "...ddddd........", "...ddsdd....g...",
        "...dsssd...ggg..", "..ddswwdd..gyg..", "..dddwwddd.gyg..", "..dddddddzzggg..",
        "..ddddddd...g...", "..ddddddd.......", "..ddddddd.......", ".ddddddddd......",
        ".ddddddddd......", "................", "wwwwwwwwwwwwwwww", "gggggggggggggggg"],
    "Wheel of Fortune": [
        "......oooo......", "....oo.yy.oo....", "...o...yy...o...", "..o.y..yy..y.o..",
        "..o..y.yy.y..o..", ".o....yyyy....o.", ".oyyyyywwyyyyyo.", ".oyyyyywwyyyyyo.",
        ".o....yyyy....o.", "..o..y.yy.y..o..", "..o.y..yy..y.o..", "...o...yy...o...",
        "....oo.yy.oo....", "......oooo......", "................", "..c..........c.."],
    "Justice": [
        ".......ww.......", ".......ww.......", ".yyyyyyyyyyyyyy.", ".y.....ww.....y.",
        ".y.....ww.....y.", "y.y....ww....y.y", "y..y...ww...y..y", "yyyyy..ww..yyyyy",
        ".yyy...ww...yyy.", ".......ww.......", ".......ww.......", "......yyyy......",
        ".......yy.......", ".......zz.......", "......yzzy......", "....rrrrrrrr...."],
    "The Hanged Man": [
        "zzzzzzzzzzzzzzzz", ".......z........", ".......z........", ".......ss.......",
        "......ss.s......", ".......sssss....", "......bbbb......", "......bbbb......",
        ".....rbbbbr.....", ".....rbbbbr.....", "......bbbb......", ".......ss.......",
        "......ssss......", ".....yssssy.....", "......yyyy......", "................"],
    "Death": [
        "..z.............", "..zkkkkkkkkkk...", "..zkkkkkkkkkkk..", "..zkkkkwwkkkkk..",
        "..zkkkwwwwkkkk..", "..zkkwwywwwkkk..", "..zkkwwwwwwkkk..", "..zkkkwwwwkkkk..",
        "..zkkkkGkkkkkk..", "..zkkkkkkkkkkk..", "..zkkkkkkkkkk...", "..z.............",
        "..z.............", "..z....oooooo...", "..z...oooooooo..", "GGGGGGGGGGGGGGGG"],
    "Temperance": [
        "................", "..y.............", ".yyy..ccc.......", ".yyycc...c......",
        "..y.......c.....", "..y........c....", "..y.........c...", ".yyy.........c..",
        "............yyy.", ".............y..", ".............y..", "............yyy.",
        "................", "bbbbbbbbbbbbbbbb", "bcbbbbcbbbbbcbbb", "bbbbbbbbbbbbbbbb"],
    "The Devil": [
        ".r............r.", ".rr..........rr.", "..rr........rr..", "...rRRRRRRRRr...",
        "...RRRRRRRRRR...", "..RRyyRRRRyyRR..", "..RRRRRRRRRRRR..", "..RRRRRkkRRRRR..",
        "...RRwRRRRwRR...", "....RRRRRRRR....", ".....RRRRRR.....", "................",
        "g.g.g.g..g.g.g.g", ".g.g.g....g.g.g.", "..g..........g..", "..ss........ss.."],
    "The Tower": [
        "..y.........y...", "...y.....yyy....", "....yy..yyy.....", ".....yy.yy......",
        "....yyyyyyy.....", "....dgggggd.....", "....dgoggod.....", "....dgggggd.o...",
        "....dgggggdoo...", "....dgkggkd.....", "....dgggggd.....", "....dgggggd.....",
        "....dggkggd.....", "...ddgggggdd....", "..zzzzzzzzzzzz..", ".zzzzzzzzzzzzzz."],
    "The Star": [
        "......w..w.....w", ".......yy.......", ".......yy.......", "...y...yy...y...",
        "....y.yyyy.y....", "......yyyy......", ".yyyyyyyyyyyyyy.", ".yyyyyyyyyyyyyy.",
        "......yyyy......", "....y.yyyy.y....", "...y...yy...y...", ".......yy.......",
        ".......yy.......", "..w.........w...", "cccccccccccccccc", "bbbcbbbbbbbcbbbb"],
    "The Moon": [
        "........yyyyy...", "......yyyyy.....", ".....yyyy.......", ".....yyy........",
        "....yyyk........", "....yyy.........", ".....yyy........", ".....yyyy.......",
        "......yyyyy.....", "........yyyyy...", ".........y...y..", "..g..........g..",
        ".ggg........ggg.", ".gkg........gkg.", ".ggg........ggg.", "bbbbbbbbbbbbbbbb"],
    "The Sun": [
        "y......yy......y", ".y.....yy.....y.", "..y..oooooo..y..", "....oooooooo....",
        "...ooyyyyyyoo...", "..ooyykyykyyoo..", "yyooyyyyyyyyooyy", "yyooyyyyyyyyooyy",
        "..ooykyyyykyoo..", "..ooyykkkkyyoo..", "...ooyyyyyyoo...", "....oooooooo....",
        "..y..oooooo..y..", ".y.....yy.....y.", "y......yy......y", "................"],
    "Judgement": [
        "..wwww....wwww..", ".wwwwwwwwwwwwww.", "..wwwwwwwwwwww..", "..y.............",
        "...yy...........", "....yyy.........", "......yyy.......", ".......yyyy.....",
        "........yyyyy...", ".......wwrwwyy..", ".......wrrrw....", ".......wwrww....",
        "................", "..s....s....s...", ".sss..sss..sss..", "zdzzzzdzzzzdzzzz"],
    "The World": [
        ".....GGGGGG.....", "...GG......GG...", "..G....ss....G..", ".G....ssss....G.",
        ".G.....ss.....G.", "G....pppppp....G", "G.....pppp.....G", "r......pp......r",
        "G.....pppp.....G", "G.....p..p.....G", ".G....s..s....G.", ".G............G.",
        "..G..........G..", "...GG......GG...", ".....GGGGGG.....", "................"],
}

# ---------------------------------------------------------------- Minor Arcana pieces
PIPS = {   # 5 x 4 px
    "Wands": ["..lzl", "..z..", ".z...", "z...."],
    "Cups": ["yyyyy", ".ycy.", "..y..", ".yyy."],
    "Swords": ["..w..", "..w..", "yyyyy", "..z.."],
    "Pentacles": [".yyy.", "yyYyy", "yYyYy", ".yyy."],
}
ACES = {   # 12 x 16 px
    "Wands": ["......l.....", ".....lzl....", "......z.l...", ".....lz.....", "......z.....",
              "......zl....", ".....lz.....", "......z.....", "......z.....", "....sszs....",
              "...sssszs...", "...ssssss...", "..wwssssww..", ".wwwwwwwwww.", "wwwwwwwwwwww",
              ".wwwwwwwwww."],
    "Cups": ["..c...c...c.", "...c..c..c..", "..cccccccc..", ".yyyyyyyyyy.", ".yccccccccy.",
             ".yccccccccy.", "..yccccccy..", "..yyyyyyyy..", "....yyyy....", ".....yy.....",
             ".....yy.....", "....yyyy....", "..yyyyyyyy..", "............", "..wwssssww..",
             ".wwwwwwwwww."],
    "Swords": [".....yy.....", "....y..y....", ".....ww.....", ".....ww.....", ".....ww.....",
               ".....ww.....", ".....ww.....", ".....ww.....", ".....ww.....", "..yyyyyyyy..",
               ".....zz.....", "....sszs....", "...ssssss...", "..wwssssww..", ".wwwwwwwwww.",
               "wwwwwwwwwwww"],
    "Pentacles": ["....yyyy....", "..yyyyyyyy..", ".yyyyGGyyyy.", ".yyyGGGGyyy.", "yyGGGGGGGGyy",
                  "yyyGGGGGGyyy", "yyyGGyyGGyyy", ".yGGyyyyGGy.", ".yyyyyyyyyy.", "..yyyyyyyy..",
                  "....yyyy....", "....ssss....", "...ssssss...", "..wwssssww..", ".wwwwwwwwww.",
                  "wwwwwwwwwwww"],
}
COURTS = {   # 12 x 16 px; X = suit color
    "Page": ["........w...", "...XXXXXww..", "..XXXXXXX...", "...ssssss...", "...skssks...",
             "...ssssss...", "....sSSs....", "..XXXXXXXX..", ".XXXXyyXXXX.", ".XXXXyyXXXX.",
             ".XXXXXXXXXX.", ".ss.XXXX.ss.", "....XXXX....", "....XXXX....", "....X..X....",
             "...zz..zz..."],
    "Knight": ["......XX....", ".....XXX....", "...gggg.....", "..gggggg....", "..gkkkkg....",
               "..gggggg....", "...gggg.....", "..XXXXXXXX..", ".gXXXyyXXXg.", ".gXXXXXXXXg.",
               ".gXXXXXXXXg.", "..XXXXXXXX..", "..zzzzzzzzz.", ".zzzzzzzzzzz", ".z.z....z.z.",
               ".z.z....z.z."],
    "Queen": ["..y..y..y...", "..yyyyyyy...", "..hhhhhhh...", ".hhssssshh..", ".hhskssksh..",
              ".hhssssshh..", ".hhhsppshh..", ".hh.ssss.hh.", "..XXXXXXXX..", ".XXXXyyXXXX.",
              ".XXXXXXXXXX.", "XXXXXXXXXXXX", "XXXXXXXXXXXX", "XXXXXXXXXXXX", "XXXXXXXXXXXX",
              ".XXXXXXXXXX."],
    "King": [".y.y.y.y.y..", ".yyyyyyyyy..", ".yryyryyry..", "..sssssss...", "..skssskss..",
             "..sssssss...", "..swwwwws...", "...wwwww....", "..XXXXXXXX..", ".XXXyyyyXXX.",
             ".XXXXyyXXXX.", "XXXXXXXXXXXX", "XXXXXXXXXXXX", "XXXXXXXXXXXX", "XXXXXXXXXXXX",
             ".XXXXXXXXXX."],
}
LAYOUT = {2: [1, 1], 3: [1, 1, 1], 4: [2, 2], 5: [2, 1, 2], 6: [2, 2, 2], 7: [2, 3, 2],
          8: [3, 2, 3], 9: [3, 3, 3], 10: [3, 2, 2, 3]}

# ---------------------------------------------------------------- pixel title font (5 x 7)
FONT = {
    "V": ["X...X", "X...X", "X...X", "X...X", ".X.X.", ".X.X.", "..X.."],
    "E": ["XXXXX", "X....", "X....", "XXXX.", "X....", "X....", "XXXXX"],
    "Y": ["X...X", "X...X", ".X.X.", "..X..", "..X..", "..X..", "..X.."],
    "R": ["XXXX.", "X...X", "X...X", "XXXX.", "X.X..", "X..X.", "X...X"],
    "A": [".XXX.", "X...X", "X...X", "XXXXX", "X...X", "X...X", "X...X"],
    "T": ["XXXXX", "..X..", "..X..", "..X..", "..X..", "..X..", "..X.."],
    "O": [".XXX.", "X...X", "X...X", "X...X", "X...X", "X...X", ".XXX."],
    " ": [".....", ".....", ".....", ".....", ".....", ".....", "....."],
}


# ================================================================ pixel grids
def grid(sprite, colors=None):
    """Sprite rows -> 2D list of xterm colors (None = transparent)."""
    pal = dict(PAL, **(colors or {}))
    return [[None if ch == "." else pal.get(ch, PAL["w"]) for ch in row] for row in sprite]


def blank(w, h):
    return [[None] * w for _ in range(h)]


def stamp(dst, src, x, y):
    for j, row in enumerate(src):
        for i, c in enumerate(row):
            if c is not None and 0 <= y + j < len(dst) and 0 <= x + i < len(dst[0]):
                dst[y + j][x + i] = c
    return dst


def rotate180(px):
    return [list(reversed(r)) for r in reversed(px)]


SUITS = ("Wands", "Cups", "Swords", "Pentacles")


def split(card):
    """(rank, suit) for a minor card, (None, None) for a Major (even 'Wheel of Fortune')."""
    rank, _, suit = card.rpartition(" of ")
    return (rank, suit) if suit in SUITS else (None, None)


def card_pixels(card, w=18, h=20):
    """The picture for any card, centered in a w x h pixel field."""
    out = blank(w, h)
    rank, suit = split(card)
    if card in MAJORS:
        src = grid(MAJORS[card])
        return stamp(out, src, (w - 16) // 2, (h - 16) // 2)
    if rank == "Ace":
        return stamp(out, grid(ACES[suit]), (w - 12) // 2, (h - 16) // 2)
    if rank in COURTS:
        fig = grid(COURTS[rank], {"X": PAL[SUIT_X[suit]]})
        stamp(out, fig, 1, (h - 16) // 2)
        stamp(out, grid(PIPS[suit]), w - 5, 0)
        return stamp(out, grid(PIPS[suit]), w - 5, h - 4)
    rows = LAYOUT[PIP_COUNT[rank]]
    pip = grid(PIPS[suit])
    gap = max(1, (h - 4 * len(rows)) // (len(rows) + 1))
    top = (h - (4 * len(rows) + gap * (len(rows) - 1))) // 2
    for r, k in enumerate(rows):
        x0 = (w - (5 * k + (k - 1))) // 2
        for i in range(k):
            stamp(out, pip, x0 + i * 6, top + r * (4 + gap))
    return out


def shrink(px):
    """Halve a pixel grid (for small cards), keeping the most common color in each 2x2 block."""
    out = []
    for y in range(0, len(px) - 1, 2):
        row = []
        for x in range(0, len(px[0]) - 1, 2):
            block = [c for c in (px[y][x], px[y][x + 1], px[y + 1][x], px[y + 1][x + 1]) if c is not None]
            row.append(max(set(block), key=block.count) if block else None)
        out.append(row)
    return out


def text_pixels(text, colors=(57, 93, 129, 135, 141, 171, 177, 183)):
    """Big pixel lettering with a left-to-right neon gradient."""
    letters = [FONT.get(ch, FONT[" "]) for ch in text.upper()]
    w = sum(6 for _ in letters) - 1
    out = blank(w, 7)
    x = 0
    for L in letters:
        for j, row in enumerate(L):
            for i, ch in enumerate(row):
                if ch == "X":
                    out[j][x + i] = colors[min(len(colors) - 1, (x + i) * len(colors) // max(1, w))]
        x += 6
    return out


# ================================================================ cells: (char, fg, bg)
def halfblock(px, bg=TABLE_BG):
    """Pixel grid -> rows of terminal cells. Odd heights get a transparent bottom row."""
    if len(px) % 2:
        px = px + [[None] * len(px[0])]
    rows = []
    for y in range(0, len(px), 2):
        row = []
        for t, b in zip(px[y], px[y + 1]):
            if t is None and b is None:
                row.append((" ", bg, bg))
            elif t == b:
                row.append(("█", t, bg))
            elif b is None:
                row.append(("▀", t, bg))
            elif t is None:
                row.append(("▄", b, bg))
            else:
                row.append(("▀", t, b))
        rows.append(row)
    return rows


def veyra_pixels(frame=0, blink=False, orb=(57, 63, 69, 75, 81, 87, 123, 159)):
    """Veyra with an animated orb and blinking eyes."""
    k = frame % len(orb)
    colors = {"O": orb[k], "*": 231 if frame % 6 < 4 else orb[(k + 3) % len(orb)],
              "e": PAL["S"] if blink else 51}
    return grid(VEYRA, colors)


def veyra_cells(frame=0, blink=False, bg=TABLE_BG):
    return halfblock(veyra_pixels(frame, blink), bg)


def _text_row(row, x, s, fg, bg):
    for i, ch in enumerate(s):
        if 0 <= x + i < len(row):
            row[x + i] = (ch, fg, bg)


SHORT = {"The Fool": "FOOL", "The Magician": "MAGICIAN", "The High Priestess": "PRIESTESS",
         "The Empress": "EMPRESS", "The Emperor": "EMPEROR", "The Hierophant": "HIEROPHNT",
         "The Lovers": "LOVERS", "The Chariot": "CHARIOT", "Strength": "STRENGTH", "The Hermit": "HERMIT",
         "Wheel of Fortune": "WHEEL", "Justice": "JUSTICE", "The Hanged Man": "HANGED MN", "Death": "DEATH",
         "Temperance": "TEMPRANCE", "The Devil": "DEVIL", "The Tower": "TOWER", "The Star": "STAR",
         "The Moon": "MOON", "The Sun": "SUN", "Judgement": "JUDGEMENT", "The World": "WORLD"}


def tags(card):
    """(corner tag, border color, element word) for a card."""
    from cards import DECK
    rank, suit = split(card)
    if rank is None:
        return ROMAN[DECK.index(card)], BORDER["major"], "major arcana"
    return RANK_TAG[rank], BORDER[suit], ELEMENT_WORD[suit]


def frame(w, h, border, bg=CARD_BG, table=TABLE_BG):
    """Chunky 8-bit card frame: half-block top/bottom edges, half-block sides."""
    rows = [[(" ", bg, bg) for _ in range(w)] for _ in range(h)]
    for x in range(w):
        rows[0][x] = ("▄", border, table)
        rows[h - 1][x] = ("▀", border, table)
    rows[0][0], rows[0][w - 1] = ("▗", border, table), ("▖", border, table)
    rows[h - 1][0], rows[h - 1][w - 1] = ("▝", border, table), ("▘", border, table)
    for y in range(1, h - 1):
        rows[y][0] = ("▐", border, table)
        rows[y][w - 1] = ("▌", border, table)
    return rows


def card_cells(card, reversed_=False, w=22, h=15):
    """A full big card: frame, corner tags, the picture, name, and orientation line."""
    tag, border, element = tags(card)
    rows = frame(w, h, border)
    _text_row(rows[1], 2, tag, border, CARD_BG)
    _text_row(rows[1], w - 2 - len(tag), tag, border, CARD_BG)
    px = card_pixels(card, w - 4, (h - 5) * 2)
    if reversed_:
        px = rotate180(px)
    for j, r in enumerate(halfblock(px, CARD_BG)):
        rows[2 + j][2:2 + len(r)] = r
    name = card if len(card) <= w - 2 else card.replace("The ", "")
    _text_row(rows[h - 3], (w - len(name)) // 2, name, 231 if split(card)[1] else 220, CARD_BG)
    low = "▼ reversed ▼" if reversed_ else element
    _text_row(rows[h - 2], (w - len(low)) // 2, low, 211 if reversed_ else 103, CARD_BG)
    return rows


def mini_cells(card, reversed_=False, w=11, h=5):
    """Small card for the Celtic Cross table: rank, name, orientation."""
    tag, border, _ = tags(card)
    rank, suit = split(card)
    rows = frame(w, h, border)
    top = tag if rank is None else rank.upper()
    mid = SHORT.get(card, (suit or "").upper())
    for y, s, c in ((1, top, border), (2, mid, 231), (3, "▼ rev" if reversed_ else "", 211)):
        s = s[: w - 2]
        _text_row(rows[y], (w - len(s)) // 2, s, c, CARD_BG)
    return rows


def back_cells(w=22, h=15, phase=0):
    """Card back: violet diamonds on navy with a gold star at the heart."""
    rows = frame(w, h, 98)
    px = blank(w - 4, (h - 2) * 2)
    cx, cy = (w - 4) / 2 - 0.5, (h - 2) - 0.5
    for y in range(len(px)):
        for x in range(len(px[0])):
            d = abs(x - cx) + abs(y - cy)
            if d < 2.2:
                px[y][x] = 220
            elif (x + y + phase) % 4 == 0 or (x - y - phase) % 4 == 0:
                px[y][x] = 55 if int(d) % 6 < 3 else 93
    for j, r in enumerate(halfblock(px, CARD_BG)):
        rows[1 + j][2:2 + len(r)] = r
    return rows


# ================================================================ ANSI output
def ansi(rows):
    """Cell rows -> printable ANSI lines."""
    out = []
    for row in rows:
        s, last = [], None
        for ch, fg, bg in row:
            ch, fg, bg = solid(ch, fg, bg)
            if (fg, bg) != last:
                s.append(f"\x1b[38;5;{fg}m\x1b[48;5;{bg}m")
                last = (fg, bg)
            s.append(ch)
        out.append("".join(s) + "\x1b[0m")
    return out


def side_by_side(blocks, gap=2, bg=TABLE_BG):
    """Join several cell blocks horizontally (tops aligned)."""
    h = max(len(b) for b in blocks)
    rows = []
    for y in range(h):
        row = []
        for i, b in enumerate(blocks):
            w = len(b[0])
            row += b[y] if y < len(b) else [(" ", bg, bg)] * w
            if i < len(blocks) - 1:
                row += [(" ", bg, bg)] * gap
        rows.append(row)
    return rows


def _check():
    for name, s in list(MAJORS.items()) + [("veyra", VEYRA)]:
        widths = {len(r) for r in s}
        assert len(widths) == 1, (name, widths)
    for d in (PIPS, ACES, COURTS):
        for name, s in d.items():
            assert len({len(r) for r in s}) == 1, name


_check()


# ================================================================ the waiting candle
FLAMES = [[".y..", ".yy.", "yooy", "owwo", ".oo."],
          ["..y.", ".yy.", "yooy", "owwo", ".oo."],
          [".yy.", ".yo.", "yooy", "owwo", ".oo."],
          ["....", ".y..", "yyoy", "owwo", ".oo."]]


def candle_pixels(progress, frame=0, h=30):
    """A candle that burns down as the reading is written (progress 0..1), flame flickering."""
    w = 10
    px = blank(w, h)
    wax_h = max(2, int(round(3 + (1 - progress) * (h - 13))))
    base = h - 3
    for y in range(base, h):                       # brass holder
        for x in range(0 if y == h - 1 else 1, w if y == h - 1 else w - 1):
            px[y][x] = PAL["Y"] if y == h - 1 else PAL["y"]
    top = base - wax_h
    for y in range(top, base):                     # wax with a drip
        for x in range(3, 7):
            px[y][x] = 230 if x != 6 else 223
    if wax_h > 4:
        px[top + 1][2] = px[top + 2][2] = 230
    px[top - 1][4] = PAL["d"]                      # wick
    flame = grid(FLAMES[frame % len(FLAMES)])
    return stamp(px, flame, 3, top - 6)


def glow_halo(px, color=58):
    """Soft warm halo around lit pixels (used behind the flame)."""
    out = [row[:] for row in px]
    for y, row in enumerate(px):
        for x, c in enumerate(row):
            if c in (PAL["y"], PAL["o"], PAL["w"]) and y < len(px) - 4:
                for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
                    yy, xx = y + dy, x + dx
                    if 0 <= yy < len(px) and 0 <= xx < len(row) and out[yy][xx] is None:
                        out[yy][xx] = color
    return out


# ================================================================ grand cards (big, detailed)
# The Live table's big cards: a bevelled gold frame with corner gems, a dithered night gradient, a
# halo behind the outlined picture, and name plates. Only the half-block glyph is needed (plus spaces).
_BAYER = ((0, 8, 2, 10), (12, 4, 14, 6), (3, 11, 1, 9), (15, 7, 13, 5))
_SKY = (16, 17, 17, 18, 54, 54)                                  # panel gradient, top to bottom
_TINT = {"major": (91, 54, 97), "Wands": (166, 130, 208), "Cups": (31, 25, 74),
         "Swords": (103, 60, 146), "Pentacles": (28, 22, 71)}     # halo inner, halo outer, accent
_GEM = {"major": 135, "Wands": 202, "Cups": 39, "Swords": 252, "Pentacles": 41}


def _gradient(x, y, h, stops=_SKY):
    f = y / max(1, h - 1) * (len(stops) - 1)
    i = int(f)
    j = min(len(stops) - 1, i + 1)
    return stops[j] if (f - i) * 16 > _BAYER[y % 4][x % 4] else stops[i]


def _outline(px, color=16):
    """A 1-pixel dark outline around every drawn pixel, so the picture pops off the background."""
    h, w = len(px), len(px[0])
    out = [row[:] for row in px]
    for y in range(h):
        for x in range(w):
            if px[y][x] is None and any(0 <= y + dy < h and 0 <= x + dx < w and px[y + dy][x + dx] is not None
                                        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                out[y][x] = color
    return out


def _grand_frame(W, H, gem):
    """Pixels of the frame: black outline, gold bevel (light top-left, dark bottom-right), gems at the corners."""
    px = blank(W, H)
    for x in range(W):
        px[0][x] = px[H - 1][x] = 16
        px[1][x], px[H - 2][x] = 229, 136
        px[2][x] = px[H - 3][x] = 178
    for y in range(H):
        px[y][0] = px[y][W - 1] = 16
        if 1 <= y <= H - 2:
            px[y][1], px[y][W - 2] = 229 if y < H - 2 else 136, 136
            px[y][2] = px[y][W - 3] = 178
    for cx, cy in ((2, 2), (W - 3, 2), (2, H - 3), (W - 3, H - 3)):
        for dx, dy in ((0, -1), (-1, 0), (1, 0), (0, 1)):
            px[cy + dy][cx + dx] = gem
        px[cy][cx] = 231
    for cx in (W // 2 - 1, W // 2):                               # small gold studs, top and bottom
        px[1][cx] = px[H - 2][cx] = 231
    return px


def _plate(px, y, W, color=235):
    for yy in (y, y + 1):
        for x in range(3, W - 3):
            px[yy][x] = color


def _fit_name(card, room):
    name = card.upper()
    for short in (name, name.replace("THE ", "", 1), name.replace(" OF ", " "), SHORT.get(card, name).upper()):
        if len(short) <= room:
            return short
    return name[:room]


def grand_cells(card, reversed_=False, w=22, h=18):
    """A big, detailed card (w x h cells; at least 22 x 14)."""
    W, H = w, h * 2
    tag, _, _ = tags(card)
    rank, suit = split(card)
    kind = suit or "major"
    inner, outer, accent = _TINT[kind]
    px = _grand_frame(W, H, _GEM[kind])
    top, bottom = 4, H - 5                                        # the picture window, between the plates
    cx, cy = (W - 1) / 2, (top + bottom) / 2
    seed = sum(map(ord, card))
    for y in range(3, H - 3):
        for x in range(3, W - 3):
            d = ((x - cx) ** 2 + ((y - cy) * 1.05) ** 2) ** 0.5
            c = _gradient(x, y - 3, H - 6)
            if d < 9.5:
                c = inner if d < 7.5 or (d - 7.5) * 8 < _BAYER[y % 4][x % 4] else c
            elif d < 12 and (d - 9.5) * 6 < _BAYER[y % 4][x % 4]:
                c = outer
            elif (x * 7 + y * 13 + seed) % 53 == 0:
                c = 189 if (x + y) % 3 else 231                  # stars in the night behind the picture
            px[y][x] = c
    for x in range(3, W - 3):                                     # thin accent lines inside the frame
        px[3][x] = px[H - 4][x] = accent
    for y in range(3, H - 3):
        px[y][3] = px[y][W - 4] = accent
    pic = card_pixels(card, min(W - 8, 18), min(bottom - top, 20))
    pic = _outline(pic)
    if reversed_:
        pic = rotate180(pic)
    stamp(px, pic, (W - len(pic[0])) // 2, int(cy - len(pic) / 2 + 0.5))
    _plate(px, 2, W)
    _plate(px, H - 4, W)
    rows = halfblock(px, TABLE_BG)
    label = tag if rank is None else rank.upper()
    _text_row(rows[1], (w - len(label)) // 2, label, 220, 235)
    if reversed_:
        _text_row(rows[1], 4, "▼", 211, 235)
        _text_row(rows[1], w - 5, "▼", 211, 235)
    name = _fit_name(card, w - 8)
    _text_row(rows[h - 2], (w - len(name)) // 2, name, 211 if reversed_ else (220 if rank is None else 231), 235)
    return rows


def grand_back(w=22, h=18, phase=0):
    """The back of a big card: violet lattice on deep navy, a gold star at the heart, the same gold frame."""
    W, H = w, h * 2
    px = _grand_frame(W, H, 135)
    cx, cy = (W - 1) / 2, (H - 1) / 2
    for y in range(3, H - 3):
        for x in range(3, W - 3):
            d = abs(x - cx) + abs(y - cy) * 0.8
            if (x + y + phase) % 6 == 0 or (x - y - phase) % 6 == 0:
                c = 97 if int(d) % 8 < 4 else 61
            else:
                c = _gradient(x, y - 3, H - 6, (17, 17, 18, 17, 17))
            if d < 6.5 and ((x + y) % 2 == 0 or d < 5):
                c = 54
            if d < 4.6 and (abs(x - cx) < 0.6 or abs(y - cy) < 0.6 or abs(abs(x - cx) - abs(y - cy)) < 0.6):
                c = 220                                           # the eight-pointed star
            if d < 1.2:
                c = 231
            px[y][x] = c
    for x in range(3, W - 3):
        px[3][x] = px[H - 4][x] = 98
    for y in range(3, H - 3):
        px[y][3] = px[y][W - 4] = 98
    return halfblock(px, TABLE_BG)
