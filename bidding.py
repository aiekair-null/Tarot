"""Veyra at the command line: her sprite, then "What is thy bidding?" and a plain chat with her model.

    veyra chat                 talk to her (exit, quit or Ctrl+D to leave; /clear forgets the chat)
    veyra chat "a question"    one answer, then back to your shell

No cards, no menus, no sync: only her picture and her brain (it wakes in the background while you type)."""
import locale
import os
import sys
import threading

import art
import brain

SYSTEM = ("You are Veyra, an 8-bit oracle who lives inside this computer and runs on its own local model. "
          "You speak with a little mystic flavor, but you answer plainly, accurately and helpfully, and you keep "
          "it short unless asked for more. You can help with anything: questions, code, writing, plans.")
GOLD, LILAC, CYAN, DIM, RESET = "\x1b[38;5;220m", "\x1b[38;5;183m", "\x1b[38;5;51m", "\x1b[38;5;245m", "\x1b[0m"


def utf8():
    try:
        locale.setlocale(locale.LC_ALL, "")
    except locale.Error:
        pass
    if os.environ.get("TAROT_ASCII") == "1":
        return False
    try:
        return "utf" in locale.nl_langinfo(locale.CODESET).lower().replace("-", "") or os.name == "nt"
    except Exception:
        return True


def portrait(unicode_ok):
    if unicode_ok:                                        # half-block pixels: 26 x 14 cells
        return art.ansi(art.veyra_cells())
    lines = []                                            # any terminal: two spaces per pixel, colored
    for row in art.veyra_pixels():
        s = "".join(f"\x1b[48;5;{c}m  " if c is not None else "\x1b[49m  " for c in row)
        lines.append(s + RESET)
    return lines


def main():
    try:
        sys.stdout.reconfigure(errors="replace")
    except Exception:
        pass
    if os.name == "nt":
        os.system("")
    print()
    for line in portrait(utf8()):
        print("   " + line)
    print(f"\n   {GOLD}V E Y R A{RESET}  {DIM}8b/8b(L){RESET}\n")

    b = brain.Brain(connect=False)
    ready = threading.Event()
    threading.Thread(target=lambda: (b.connect(), ready.set()), daemon=True).start()

    history = []
    once = " ".join(sys.argv[1:]).strip()
    while True:
        if once:
            q = once
        else:
            try:
                q = input(f"{LILAC}What is thy bidding?{RESET} ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
        if not q:
            continue
        if q.lower() in ("exit", "quit", "bye", "/exit", "/quit"):
            break
        if q == "/clear":
            history = []
            print(f"{DIM}(forgotten){RESET}")
            continue
        if not ready.is_set():
            print(f"{DIM}(she is waking...){RESET}", end="", flush=True)
            ready.wait()
            print("\r" + " " * 22 + "\r", end="")
        if b.kind == "none":
            print(f"{DIM}Her model would not wake: {b.err or 'no model installed (run: veyra model)'}{RESET}")
            break
        history.append({"role": "user", "content": q})
        msgs = [{"role": "system", "content": SYSTEM}] + history[-12:]
        print(CYAN, end="", flush=True)
        out = []
        try:
            for piece in b.stream(msgs, max_tokens=700, temperature=0.7):
                out.append(piece)
                print(piece, end="", flush=True)
        except KeyboardInterrupt:
            out.append(" ...")
        print(RESET + "\n")
        history.append({"role": "assistant", "content": "".join(out).strip()})
        if once:
            break


if __name__ == "__main__":
    main()
