# Veyra Visual Bible

Every picture, video, card, screen and promo in this project follows this guide. The reference implementation is `veyra_promo.py`.
When something new is made, match this first; when this file and older code disagree, this file wins.

Brand mark: **8b/8b(L)** = 8-bit / 8 billion parameters (Qwen3 8B) / Local.
Veyra speaks for herself: viewers **contact Veyra**, never a person's name.

---

## 1. The pixel rule
- Draw on a small canvas and scale up with **nearest-neighbour only**: 270×480 → 1080×1920 (×4) for reels, 480×270 → 1920×1080 for wide.
- No smooth scaling, no anti-aliased shapes or text on the art layer. Soft light comes only from bloom (section 6).
- Gradients are **banded with 4×4 Bayer dithering** (about 9 levels), never smooth.
- Finish every frame with `veyra_look.finish()` (or the promo's matching CRT overlay): on top: a dark scanline on every 4th output row (alpha ≈ 46), faint column lines (alpha ≈ 14), and a soft vignette.

## 2. Palette

| Role | Hex | Use |
|---|---|---|
| Night (deep) | `#07021a` | top of sky, header bar |
| Violet | `#24104a` | sky middle |
| Plum | `#3d1658` | sky low / horizon |
| Cloth | `#170726` | table, caption box fill `#0d0520` |
| Hood | `#3b1a6b` | Veyra's hood; rim light `#7a4fc4` |
| Robe | `#2a1050` | Veyra's robe |
| Lilac hair | `#c9b6f2` | hair; shade `#7d66b8` |
| Skin | `#ecd0e2` | face; shade `#cfa5c4`, blush `#f2a0c4` |
| **Gold** | `#ffd36b` | titles, card borders, trim, name tags, the gem |
| **Cyan** | `#4ff0ff` | eyes, "live" accents, cursors, numbers, equalizer |
| Lavender text | `#b9a6e8` | secondary text |
| Body text | `#f0e8ff` | captions |
| Alert red | `#ff5064` | REC dot, "SKYNET" warnings |
| Moon | `#fff1c9` | moon, card-moon symbols |

**Lore scene:** teal `#03121a → #0b3a42 → #06201f`, parchment `#eadcb4`, gold `#b8892e`, ink `#2b1a0e`, title red `#7a1f2b`.
**Memory scene:** black-green `#010805 → #05200f`, terminal green `#7dffb0`, frame `#2bff88`.

Rule of thumb: purple for the world, gold for meaning, cyan for life and thinking, never pure white except star cores and flashes.

## 3. Type
- **Pillow's built-in bitmap font** (`ImageFont.load_default_imagefont()`), drawn with `fontmode = "1"` (no anti-aliasing). About 6 px per character, 11 px line, 13 px leading.
- Sizes are whole multiples only: ×1 body, ×2 headings, ×3 to ×6 titles.
- Every text has a 1-pixel drop shadow in `#08021a` (or the scene's darkest colour).
- Titles in UPPERCASE; captions in sentence case. Wrap captions at about 40 characters, at most 6 lines.
- The DejaVu fonts in `assets/` are for non-pixel exports only (PDFs, docs), never on the art layer.

## 4. Veyra (the character)
- She is the **original Veyra from `art.py`** (the 26×28 sprite in the first videos), rebuilt at 4× detail as a 104×112 sprite in `veyra_look.veyra()`. Never redesign her: add detail to her.
- She has her original hood, long lilac hair, gold circlet, cyan eyes, gold collar, and hands holding the glowing orb.
- The added detail: dithered light from the orb below and a cool rim light, hair strands with shine, folds in the robe, lashes, irises with highlights, a nose, blush, a pulsing cyan gem in the circlet, and a violet orb whose swirl turns.
- She's always alive: she bobs gently (±2 px), blinks every 3 to 5 s, her gem pulses, the orb swirls, and her mouth moves with her voice.
- In her scene she's shown at ×2, between two candles at a gold-edged table, with a soft violet aura. In picture-in-picture she's cropped to her head at about 0.6×. In reading videos she sits at the top of the sky above the headline.

### In the terminal (tarot.py)
- `veyra_look.veyra_cells()` draws the same detailed Veyra in quarter-block characters (▘▝▖▗▚▞…). She takes 26 columns × 14 rows, the same space as the old sprite, with twice the detail across.
- She's mapped to xterm-256 violets, lilacs and golds, avoiding greys. Outlines use the darkest violet (53).
- If the terminal allows it, the background becomes the bible's night violet `#0d0520`. Default text is pale lavender (189), the VEYRA title is gold, and the calm glow runs violet to lilac.

## 5. Cards
- **Painted cards** (`cards_hd.py`): all 78 cards and the back as 96×160 pixel paintings in tarot 3:5 proportions. Videos show them at ×4.
  - **Frame:** dark ink edge, cream card stock, a frame in the suit colour (Majors gold, Wands amber, Cups cyan, Swords silver, Pentacles green), and corner jewels.
  - **Text:** the numeral or rank on top, and a two-line name plate at the bottom in pixel text.
  - **Art window (80×104):** a dithered sky themed to the card. Wands get fire, Cups water, Swords a steel night, Pentacles earth. Majors get dawn rays for light cards, a red moon for heavy ones, and a starry night otherwise. Every window has a horizon strip.
  - **Figures:** the original `art.py` figures (Majors, Aces, courts) are kept and never redesigned. Each gets one Scale2x pass, then ×2, so diagonals are smoother but the pixels stay chunky.
  - **8-bit shading:** flat fills, a hard highlight on top and left edges, a hard shadow on bottom and right edges, line art between colours, a dark outline and a few gold glints. No dither inside figures.
  - **Pips:** new 18×18 icons for wand, chalice, sword and pentacle, laid out by `art.LAYOUT`, each with a soft suit-coloured glow.
- **Terminal cards:** the same 8-bit figure (outlined and shaded) in quarter blocks on the navy card, twice as much detail across as before. Frames, tags and names stay text. The card back stays the crisp original pattern.
- **Promo decoration cards:** 20×32 sprites (cream border, coloured panel, one gold symbol). Flips squeeze the width, and cards thinner than 4 px are not drawn.
- `python3 cards_hd.py videos/all_cards.png` saves a contact sheet of the whole deck.

## 6. Light
- **Bloom on every frame:** take pixels brighter than about 165, blur by about 3 px, and add them back at 0.6 strength.
- Glow sprites (soft radial) behind Veyra (violet), her eyes (cyan) and candle flames (amber `#ffae42`).
- Stars twinkle; a few big ones get a 4-pixel cross. The moon is a crescent, top right.

## 7. Motion (60 fps)
Inspired by the motion libraries on 60fps.design and Mobbin:
- **Spring** for things arriving (captions, panels, cards, letters): `1 − e^(−7x)·cos(13x)`, about 0.5 to 0.7 s, small overshoot.
- **Ease-out cubic** for things settling or sliding in.
- **Stagger:** letters about 0.12 s apart, cards about 0.09 s apart.
- **Orbit and flip:** cards orbit Veyra slowly and pass in front of and behind her.
- **Typewriter text** with a blinking cyan block cursor.
- **Shimmer:** a light sweep along the top edge of caption boxes.
- **Ticker:** numbers roll (for example 3,000,000,000 → 8,000,000,000 params).
- **Jump cuts:** hard cuts, never crossfades. Each cut gets about 0.2 s of glitch (row tears, RGB split, one white-flash frame) and a bit-crushed noise blip. Inside her scene, captions alternate a 1.14× punch-in.
- **Confetti** of gold, cyan, pink and white pixels on endings.
- Ambient motion never stops: drifting motes, twinkling stars, flickering candles.

## 8. Layout (reel, 270×480 art pixels)
- Header bar 0 to 20: `VEYRA // 8b/8b(L)` on the left, a scene tag (LIVE, LORE, MEMORY, END) with a red REC dot on the right.
- Stage 20 to 296. Table line at 296.
- Caption box about 344 to 470: dark box with a violet outline and cut corners, a gold `VEYRA` name tag, and a cyan equalizer.
- Progress bar in the bottom 3 px, lilac with a white head.

## 9. Sound
- The music bed is an original generative piece in the spirit of Aphex Twin's *Jynweythek* (`video.music_bed`), and every video gets a new one.
  - Prepared piano (detuned strings with metallic partials) and harp, in a modal scale (Phrygian, Aeolian, Dorian or Hijaz-like).
  - Slow and rubato, about 110 to 140 BPM in eighths, with a gently breathing tempo. No drums.
  - 8-bar sections: sparse melody, then harp rolls underneath, then echoes an octave up. Soft swells, low root notes, a big airy room reverb.
- Her voice is ON by default (the same engine as the reading videos: piper, else flite, else espeak), and the music ducks under it.
- A soft high bell rings on every jump cut.

## 10. Words on screen
- Veyra speaks in first person: warm, mystical, playful, a little cheeky, honest about odds.
- Contact line: "Questions or a live reading? **Contact Veyra.**" "Send me a message right here on Facebook."
- People's questions, readings and feedback never appear in public videos.
