# ✦ VEYRA ✦ — 8-bit terminal tarot

A tarot reader who lives in your terminal: pixel art for Veyra and all 78 cards, a ritual you
take part in (wash, cut, reassemble, turn the cards), real randomness, and a reader who thinks with
a **free AI model running on your own machine**. No Hugging Face bill.

## Quick start (GitHub Codespaces or any Linux/Mac)

```bash
bash setup_local.sh        # one time: installs the engine + downloads the free 3B model (~2.1 GB)
python3 tarot.py           # menu: reading, grimoire, study
```

In Codespaces with this repo's `.devcontainer`, the setup runs automatically on a fresh codespace.
For an existing codespace, just run `bash setup_local.sh` once.

Make the terminal at least **80x24** (bigger is nicer). In VS Code, set
`terminal.integrated.minimumContrastRatio` to `1` so the 8-bit colors aren't altered
(the devcontainer already does this).

## The brain: free and local

Veyra tries these in order and uses the first that works:

| Backend | What it is | How to get it |
|---|---|---|
| **built-in** | A GGUF model running inside Python (llama-cpp-python) | `bash setup_local.sh` |
| Ollama | If you already run Ollama, she finds it at localhost:11434 | `ollama pull qwen2.5:3b` |
| Local server | Any OpenAI-compatible server (LM Studio etc.) | `export TAROT_LOCAL_URL=http://localhost:1234/v1` |
| **none** | No model: a full scripted reading from her knowledge base | works out of the box |

Hugging Face's paid router is **only** used if you set `TAROT_BACKEND=hf` yourself.

```bash
python3 models.py                 # what's installed, what she'll use
python3 models.py download small  # faster 1.5B model (1.1 GB) if your machine is slow
python3 models.py use medium      # switch back to the 3B default
```

Free models: `medium` = Qwen2.5 3B (**default**) · `small` = Qwen2.5 1.5B · `llama` = Llama 3.2 3B.

### Covering the wait

On a 2-core Codespace the 3B model takes a few minutes per reading, so Veyra hides the wait:

- **She starts early.** Your question and answers are fed to the model while you wash and cut
  the deck, and the reading starts writing the moment the cards fall, before you turn them.
- **She improvises in the background.** Her last interview question is written while you answer
  the one before it.
- **A tiny quill meter** in the corner shows the reading being written while you turn the cards.
- **The waiting room.** If more than ~20 s of writing is left after the last card turns, you enter
  a room of visions that rotates every 12 s (press `n` to skip ahead): the drawn cards orbiting
  Veyra, a card from the deck to contemplate, and her words heard through the veil (mostly glyphs,
  a few true letters). A candle burns down as the text is written, with a time estimate she learns
  from your machine's real speed. Press `g` to browse the grimoire while you wait.
- **You choose the moment.** When it is done: "your reading is ready, press Enter when you are ready".

Faster machine or shorter wait wanted? `TAROT_WAIT_LIMIT=60` streams live unless more than a minute
is left; `python3 models.py download small` roughly halves the time.

## What's in a reading

1. **Interview.** Questions drawn from a scripted bank of 188 (openers per topic, follow-ups
   triggered by your words like "boss", "ex", "debt", and themes like stakes, fear, hope). With
   a model, her last question is improvised from your answers.
2. **The ritual (8-bit).** Veyra with her glowing orb, a starfield, washing, cutting into three piles,
   reassembling, and turning big pixel cards. Reversed cards are drawn upside down.
3. **Channeling.** At random moments the veil thins; your exact keypress time becomes entropy that
   pulls a fragment from Wikipedia (or a local omen) for her to shape.
4. **The reading.** Every card read in its position, card interactions, answers to the spirit
   questions, one question back to you.
5. **Memory.** She reflects after each reading and stores lessons, card lore and pairings in
   `memory.json`, and studies on her own (`python3 study.py 20`).

If you mention being in crisis, she sets the cards down and points you to real help (988 in the US).

## The grimoire

`python3 tarot.py grimoire` (or menu option 2) browses every card: the art upright and reversed,
keywords, love/work/money/inner scenarios, advice, outcome, yes/no lean, timing, and **what that
card means in every position** of both spreads, upright and reversed.
Keys: ← → card · ↑ ↓ scroll · r reverse · w c s p jump to a suit · 0 the Fool · q back.

## Files

| File | Role |
|---|---|
| `tarot.py` | Main program: menu, interview, curses ritual, grimoire |
| `art.py` | All pixel art: Veyra, 22 Major icons, pips, aces, courts, card frames and backs |
| `brain.py` | Local model backends (llama.cpp, Ollama, local server), streaming, free downloads |
| `agent.py` | Veyra: persona, memory, interview, reading, reflection, study |
| `knowledge.py` | Position meanings for every card, card relationships, the scripted reader |
| `lore.py` | Scenario library + advice, outcome and yes/no for all 78 cards |
| `questions.py` | The scripted question bank, spirit questions, closings, crisis check |
| `cards.py`, `spreads.py` | Deck, upright/reversed meanings, spreads and position guides |
| `fx.py` | Neon text effects and the live streaming display |
| `spirit.py`, `research.py` | Channeling entropy; optional web research for study |

## Settings (environment variables)

`TAROT_BACKEND` (auto, llama, ollama, openai, hf, none) · `TAROT_GGUF` (path to any .gguf) ·
`TAROT_THREADS` · `TAROT_CTX` (default 8192) · `TAROT_WAIT_LIMIT` (default 20 s) · `TAROT_OLLAMA_MODEL` · `TAROT_ADAPTIVE=0`
(scripted questions only) · `TAROT_FAST=1` (skip animation delays) · `TAROT_LIVE_RESEARCH=0`.
