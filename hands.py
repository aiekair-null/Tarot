"""Veyra's hands: she may ask to run a shell command, you approve it, it runs in her output window
(runner.py), and the output comes back to her. Every command needs your yes; risky ones need a typed 'yes'."""
import json
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

import runner

HERE = Path(__file__).resolve().parent
LIMIT = 3000
ON = os.name != "nt"                                   # Linux/Mac only (the window uses a pseudo-terminal)

HOW = ("\nYOU CAN USE PROGRAMS ON THIS COMPUTER (Arch Linux, the person's own account). To run a shell "
       "command, write ONE line on its own and then stop and wait:\n"
       "RUN: <command>\n"
       "The person sees the exact command and approves or refuses it. It runs in a separate output window "
       "where they can type if the program asks for input. Its output and exit code come back to you as "
       "RESULT. Look before you change anything (ls, cat, ip, nmcli, etc.), explain what a change will do "
       "before you ask to run it, one command at a time, and never use sudo or pacman unless they ask. If "
       "they refuse, respect it and offer another way. If you need something only they know, just ask them.")

DANGER = re.compile(r"\bsudo\b|\bsu\b|\brm\s+-\w*[rf]|\bmkfs|\bdd\b|\bshred\b|\bwipefs|\bfdisk|\bparted|"
                    r">\s*/dev/|\bchmod\s+-R|\bchown\s+-R|\bshutdown\b|\breboot\b|\bpoweroff\b|"
                    r"\bpacman\b|\bsystemctl\s+(stop|disable|mask)|:\(\)\s*\{|\bcurl\b[^|]*\|\s*(ba)?sh|"
                    r"\bgit\s+push\s+(-f|--force)|\biptables\s+-F|\bkill\s+-9\s+1\b", re.I)
RED, BLUE, WHITE, DIM, RESET = "\x1b[38;5;203m", "\x1b[38;5;117m", "\x1b[38;5;231m", "\x1b[38;5;245m", "\x1b[0m"

TERMS = [("alacritty", ["-T", "Veyra output", "-e"]), ("kitty", ["--title", "Veyra output"]),
         ("urxvt", ["-title", "Veyra output", "-e"]), ("xfce4-terminal", ["-T", "Veyra output", "-x"]),
         ("gnome-terminal", ["--title", "Veyra output", "--"]), ("konsole", ["-e"]),
         ("terminator", ["-T", "Veyra output", "-x"]), ("st", ["-t", "Veyra output", "-e"]),
         ("uxterm", ["-T", "Veyra output", "-e"]), ("xterm", ["-T", "Veyra output", "-e"])]


def window_open():
    try:
        return runner.alive(int(runner.PIDFILE.read_text()))
    except Exception:
        return False


def open_window():
    """Make sure the output window is up; returns an error text if it can't be opened."""
    if window_open():
        return ""
    if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        return "no desktop session to open a window in; open another terminal and run:  veyra out"
    prefer = os.environ.get("TERMINAL", "").split("/")[-1]
    order = sorted(TERMS, key=lambda t: t[0] != prefer)
    for name, args in order:
        path = shutil.which(name)
        if path:
            subprocess.Popen([path, *args, sys.executable, str(HERE / "runner.py")], cwd=str(Path.home()),
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
            for _ in range(60):
                if window_open():
                    return ""
                time.sleep(0.2)
            break
    return "couldn't open a terminal window; open another terminal and run:  veyra out"


def approve(cmd):
    """Ask the person. Returns the command to run (maybe edited) or None."""
    risky = bool(DANGER.search(cmd))
    print(f"\n{BLUE}  ┌ she wants to run:{RESET}\n{WHITE}  │ {cmd}{RESET}")
    if risky:
        print(f"{RED}  │ careful: this can change or delete things, or needs root.{RESET}")
    while True:
        try:
            a = input(f"{BLUE}  └ run it? {'type yes' if risky else '[y]es'} / [n]o / [e]dit: {RESET}").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return None
        if a in ("e", "edit"):
            try:
                new = input(f"{DIM}    your version: {RESET}").strip()
            except (EOFError, KeyboardInterrupt):
                return None
            if new:
                cmd, risky = new, bool(DANGER.search(new))
                print(f"{WHITE}    {cmd}{RESET}" + (f"  {RED}(careful){RESET}" if risky else ""))
            continue
        if a in ("n", "no", ""):
            return None
        if a == "yes" or (a == "y" and not risky):
            return cmd
        if a == "y" and risky:
            print(f"{RED}    this one needs the full word: yes{RESET}")


def run(cmd, keys_esc=None):
    """Run an approved command in the output window and wait for its result."""
    err = open_window()
    if err:
        return f"(not run: {err})"
    jid = uuid.uuid4().hex[:12]
    runner.SPOOL.mkdir(parents=True, exist_ok=True)
    tmp = runner.SPOOL / f"{jid}.tmp"
    tmp.write_text(json.dumps({"id": jid, "cmd": cmd}))
    tmp.replace(runner.SPOOL / f"{jid}.json")
    done = runner.SPOOL / f"{jid}.done"
    print(f"{DIM}  (running in her output window; Esc here stops waiting){RESET}", flush=True)
    while not done.exists():
        if keys_esc and keys_esc():
            return "(the person stopped waiting; the command may still be running in the output window)"
        if not window_open():
            return "(the output window was closed before the command finished)"
        time.sleep(0.2)
    try:
        r = json.loads(done.read_text())
    finally:
        done.unlink(missing_ok=True)
    out = r["out"].strip()
    if len(out) > LIMIT:
        out = out[:LIMIT // 3] + "\n...(cut)...\n" + out[-2 * LIMIT // 3:]
    return f"exit code {r['code']}\n{out or '(no output)'}"
