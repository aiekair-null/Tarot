"""Veyra's hands: she may ask to run a shell command, you approve it, it runs in her output window
(runner.py), and the output comes back to her. Every command needs your yes; risky ones need a typed 'yes'."""
import json
import os
import re
import shlex
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

HOW_OPEN = ("\nYOU CAN OPEN WINDOWS ON THEIR SCREEN. To show them a web page or start a program with a window, "
            "write ONE line and stop:\n"
            "OPEN: <url>              (opens it in their web browser)\n"
            "OPEN: <program> [args]   (starts a desktop program, e.g. OPEN: wireshark)\n"
            "They approve it first. The window is theirs to see and use; you cannot see the screen or click in "
            "it, so say what they should look at, and use READ to read a page's text yourself. Use OPEN, not RUN, "
            "for anything that opens a window.")
BROWSERS = ["firefox", "librewolf", "chromium", "google-chrome-stable", "google-chrome", "brave", "vivaldi",
            "qutebrowser", "falkon", "epiphany", "midori", "netsurf"]


FILE_EXT = {"pdf", "txt", "md", "png", "jpg", "jpeg", "gif", "svg", "py", "sh", "c", "h", "rs", "go", "js", "ts",
            "json", "csv", "log", "conf", "cfg", "yml", "yaml", "toml", "ini", "odt", "ods", "odp", "docx", "xlsx",
            "pptx", "mp3", "mp4", "mkv", "zip", "tar", "gz", "desktop", "service", "bat", "exe"}


def kind_of(target):
    """'file' (exists on this computer), 'page' (a web address) or 'program'."""
    t = target.strip()
    if t and os.path.exists(os.path.expanduser(t)):
        return "file"
    if re.match(r"(https?|file)://", t):
        return "page"
    m = re.match(r"^[\w.-]+\.([a-z]{2,})(/\S*)?$", t, re.I)
    if m and m.group(1).lower() not in FILE_EXT:
        return "page"
    return "program"


def _is_url(x):
    return kind_of(x) == "page"


def rl_safe(s):
    """Mark colour codes as zero-width for readline, so editing a long line doesn't garble the prompt."""
    return re.sub(r"(\x1b\[[0-9;]*m)", "\001\\1\002", s) if "readline" in sys.modules else s


def approve_open(target):
    """Ask before opening a window. Returns the target (maybe edited) or None."""
    kind = kind_of(target)
    risky = kind == "program" and bool(DANGER.search(target))
    print(f"\n{BLUE}  ┌ she wants to open a {kind} on your screen:{RESET}\n{WHITE}  │ {target}{RESET}")
    while True:
        try:
            a = input(rl_safe(f"{BLUE}  └ open it? {'type yes' if risky else '[y]es'} / [n]o / [e]dit: {RESET}")).strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return None
        if a in ("e", "edit"):
            try:
                new = input(rl_safe(f"{DIM}    your version: {RESET}")).strip()
            except (EOFError, KeyboardInterrupt):
                return None
            if new:
                target = new
            continue
        if a in ("n", "no", ""):
            return None
        if a == "yes" or (a == "y" and not risky):
            return target


def open_window_for(target):
    """Open a page in the browser or start a GUI program, detached, so it stays on screen."""
    if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        return "(not opened: there is no desktop session on this terminal)"
    quiet = dict(stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL,
                 start_new_session=True, cwd=str(Path.home()))
    if kind_of(target) == "file":
        path = os.path.expanduser(target.strip())
        if shutil.which("xdg-open"):
            subprocess.Popen(["xdg-open", path], **quiet)
            return f"(opened the file {path} with its default app on their screen)"
        return "(not opened: xdg-open is missing, so there is no way to pick an app for that file)"
    if _is_url(target):
        url = target if "://" in target else "https://" + target
        env_b = os.environ.get("BROWSER", "").split(":")[0]
        for b in ([env_b] if env_b else []) + BROWSERS:
            if b and shutil.which(b):
                subprocess.Popen([shutil.which(b), url], **quiet)
                return f"(opened {url} in {b} on their screen)"
        if shutil.which("xdg-open"):
            subprocess.Popen(["xdg-open", url], **quiet)
            return f"(opened {url} with the default browser)"
        return "(not opened: no web browser found; they could install firefox)"
    try:
        argv = shlex.split(target)
    except ValueError as e:
        return f"(not opened: {e})"
    if not argv or not shutil.which(argv[0]):
        return f"(not opened: there is no program called '{argv[0] if argv else target}' on this computer)"
    p = subprocess.Popen(argv, **quiet)
    time.sleep(1.5)
    if p.poll() is not None and p.returncode != 0:
        return f"({argv[0]} closed straight away with exit code {p.returncode}; it may need options or a terminal)"
    return f"(started {argv[0]} in its own window on their screen, pid {p.pid})"


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
            a = input(rl_safe(f"{BLUE}  └ run it? {'type yes' if risky else '[y]es'} / [n]o / [e]dit: {RESET}")).strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return None
        if a in ("e", "edit"):
            try:
                new = input(rl_safe(f"{DIM}    your version: {RESET}")).strip()
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
    tmp.write_text(json.dumps({"id": jid, "cmd": cmd, "ts": time.time()}))
    tmp.replace(runner.SPOOL / f"{jid}.json")
    done = runner.SPOOL / f"{jid}.done"
    print(f"{DIM}  (running in her output window; Esc here stops waiting){RESET}", flush=True)
    while not done.exists():
        if keys_esc and keys_esc():
            queued = runner.SPOOL / f"{jid}.json"
            if queued.exists():                          # not started yet: cancel it so it can't run later
                queued.unlink(missing_ok=True)
                return "(the person cancelled before it started; nothing was run)"
            return "(the person stopped waiting; the command may still be running in the output window)"
        if not window_open():
            (runner.SPOOL / f"{jid}.json").unlink(missing_ok=True)
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
