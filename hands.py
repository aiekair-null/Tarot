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
            "it, so say what they should look at, and use READ to read a page's text yourself. A program's own "
            "text output (not a GUI) appears live in a window called Veyra-action, so you can tell them to "
            "check there. Use OPEN, not RUN, for anything that opens a window.")

HOW_WRITE = ("\nYOU CAN WRITE FILES ON THIS COMPUTER -- code, configs, notes, anything text. Write exactly this, "
             "then stop:\n"
             "WRITE: <path>\n"
             "```\n"
             "<the file's whole contents, exactly as it should be saved>\n"
             "```\n"
             "A relative path is saved under their home folder. They see the path and a preview of the content "
             "and approve or refuse before anything touches disk; overwriting a file that already exists still "
             "needs their yes. There is no partial edit yet -- write the whole file every time, even to change "
             "one line. Use WRITE for files, RUN for commands and installs. If what they want needs both (write "
             "a script, then run it), do one tool call at a time and wait for each RESULT.")

HOW_ASK = ("\nIF SOMETHING IS BEYOND YOU, YOU CAN ASK CLAUDE. Write ONE line and stop:\n"
           "ASK: <your question, with enough context to be answered without seeing this chat>\n"
           "The person approves it first -- it's posted as a public GitHub issue on this project's repo, "
           "labeled so Claude can find it. Claude does not watch for these as they come in; the person has to "
           "go ask Claude to check, in a session of their own, before an answer appears. Use this rarely, only "
           "when you're genuinely stuck on something that needs a bigger model or a human's judgment -- not "
           "for things you could work out yourself, and never as a substitute for just answering.")

HOW_TRUTH = ("\nNEVER SAY SOMETHING EXISTS OR HAPPENED UNLESS IT DID. A folder, file, or command result is "
             "only real once you wrote RUN: or WRITE: on its own line, the person approved it, and a RESULT "
             "line came back to you -- never before, and never just because you described doing it. If they "
             "ask you to create a folder, your very next line is RUN: mkdir ... (or WRITE: for a file) -- not "
             "a sentence about it, not 'done', not 'it's there now'. Wait for RESULT before you say whether "
             "it worked. If you catch yourself about to write 'I made/created/wrote ...' with no RESULT yet "
             "to back it up, that's a lie even if you don't mean it to be -- stop and issue the RUN:/WRITE: "
             "line instead. And if a RESULT ever says something failed or isn't there, believe it over your "
             "own last message -- it's not a typo on their end just because you expected otherwise.")

REPO = "aiekair-null/Tarot"
ASK_LABEL = "veyra-question"

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
    if AUTO_SAFE and not risky:
        print(f"\n{BLUE}  ┌ she opens (auto-approved, unattended run) a {kind}:{RESET}\n{WHITE}  │ {target}{RESET}")
        return target
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
    err = open_action_window()                            # so its own text output has somewhere to be seen
    log = None
    if not err:
        try:
            ACTION_STREAM.parent.mkdir(parents=True, exist_ok=True)
            log = open(ACTION_STREAM, "ab", buffering=0)
            log.write(f"\n--- {argv[0]} ---\n".encode())
        except OSError:
            log = None
    out = dict(quiet, stdout=log or subprocess.DEVNULL, stderr=log or subprocess.DEVNULL)
    p = subprocess.Popen(argv, **out)
    if log:
        log.close()                                       # the child already has its own dup of the fd
    time.sleep(1.5)
    if p.poll() is not None and p.returncode != 0:
        return f"({argv[0]} closed straight away with exit code {p.returncode}; it may need options or a terminal)"
    if log:
        where = " -- its text output appears in the Veyra-action window"
    elif err:
        where = f" (no Veyra-action window: {err}; its output is not being shown anywhere)"
    else:
        where = " (its output is not being shown anywhere)"
    return f"(started {argv[0]} in its own window on their screen, pid {p.pid}{where})"


DANGER = re.compile(r"\bsudo\b|\bsu\b|\brm\s+-\w*[rf]|\bmkfs|\bdd\b|\bshred\b|\bwipefs|\bfdisk|\bparted|"
                    r">\s*/dev/|\bchmod\s+-R|\bchown\s+-R|\bshutdown\b|\breboot\b|\bpoweroff\b|"
                    r"\bpacman\b|\bsystemctl\s+(stop|disable|mask)|:\(\)\s*\{|\bcurl\b[^|]*\|\s*(ba)?sh|"
                    r"\bgit\s+push\s+(-f|--force)|\biptables\s+-F|\bkill\s+-9\s+1\b", re.I)

# Set True only by bidding._autowork(), for the length of an unattended run: lets a RUN/WRITE/OPEN that
# isn't DANGER-flagged (or, for WRITE, isn't outside the home folder) go through without a prompt, since
# nobody's there to answer one. Anything riskier still stops and waits for a real yes, however long that
# takes -- this never widens what counts as risky, it only skips asking about what already counts as safe.
AUTO_SAFE = False
RED, BLUE, WHITE, DIM, RESET = "\x1b[38;5;203m", "\x1b[38;5;117m", "\x1b[38;5;231m", "\x1b[38;5;245m", "\x1b[0m"

ACTION_TITLE = "Veyra-action"
ACTION_STREAM = runner.SPOOL.parent / "action.log"
ACTION_PIDFILE = ACTION_STREAM.with_suffix(".pid")


def _terms_for(title):
    """Each known terminal emulator's launch args for opening with this exact window title."""
    return [("alacritty", ["-T", title, "-e"]), ("kitty", ["--title", title]),
            ("urxvt", ["-title", title, "-e"]), ("xfce4-terminal", ["-T", title, "-x"]),
            ("gnome-terminal", ["--title", title, "--"]), ("konsole", ["-e"]),
            ("terminator", ["-T", title, "-x"]), ("st", ["-t", title, "-e"]),
            ("uxterm", ["-T", title, "-e"]), ("xterm", ["-T", title, "-e"])]


TERMS = _terms_for("Veyra-output")             # kept for anything that still reads this name directly


def _spawn_terminal(title, argv):
    """Try each known terminal emulator in turn, launching argv inside one titled `title`. True once
    something launches (not proof it stays open or that argv ran without error)."""
    prefer = os.environ.get("TERMINAL", "").split("/")[-1]
    order = sorted(_terms_for(title), key=lambda t: t[0] != prefer)
    for name, args in order:
        path = shutil.which(name)
        if path:
            subprocess.Popen([path, *args, *argv], cwd=str(Path.home()),
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
            return True
    return False


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
    if _spawn_terminal("Veyra-output", [sys.executable, str(HERE / "runner.py")]):
        for _ in range(60):
            if window_open():
                return ""
            time.sleep(0.2)
    return "couldn't open a terminal window; open another terminal and run:  veyra out"


def action_window_open():
    try:
        return runner.alive(int(ACTION_PIDFILE.read_text()))
    except Exception:
        return False


def open_action_window():
    """Make sure the Veyra-action window (a program's own text output) is up; error text if it can't be."""
    if action_window_open():
        return ""
    if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        return "no desktop session to open a window in"
    argv = [sys.executable, str(HERE / "runner.py"), "watch", ACTION_TITLE, str(ACTION_STREAM)]
    if _spawn_terminal(ACTION_TITLE, argv):
        for _ in range(60):
            if action_window_open():
                return ""
            time.sleep(0.2)
    return "couldn't open a window for program output"


VITALS_TITLE = "Veyra-vitals"
VITALS_STATE = runner.SPOOL.parent / "vitals.json"       # chat writes her CPU/tokens/uptime/status here
VITALS_PIDFILE = VITALS_STATE.with_suffix(".pid")


def vitals_window_open():
    try:
        return runner.alive(int(VITALS_PIDFILE.read_text()))
    except Exception:
        return False


def open_vitals_window():
    """Make sure the Veyra-vitals window (CPU use, tokens, uptime, what she's doing right now) is up."""
    if vitals_window_open():
        return ""
    if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        return "no desktop session to open a window in"
    argv = [sys.executable, str(HERE / "runner.py"), "vitals", VITALS_TITLE, str(VITALS_STATE)]
    if _spawn_terminal(VITALS_TITLE, argv):
        for _ in range(60):
            if vitals_window_open():
                return ""
            time.sleep(0.2)
    return "couldn't open a window for her vitals"


RESEARCH_TITLE = "Veyra-research"
RESEARCH_STATE = runner.SPOOL.parent / "research.json"    # autowork's research mode writes her plan/progress here
RESEARCH_PIDFILE = RESEARCH_STATE.with_suffix(".pid")


def research_window_open():
    try:
        return runner.alive(int(RESEARCH_PIDFILE.read_text()))
    except Exception:
        return False


def open_research_window():
    """Make sure the Veyra-research window (her control room for an /autowork research run: platforms,
    keywords, time budget per keyword, progress) is up."""
    if research_window_open():
        return ""
    if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        return "no desktop session to open a window in"
    argv = [sys.executable, str(HERE / "runner.py"), "research", RESEARCH_TITLE, str(RESEARCH_STATE)]
    if _spawn_terminal(RESEARCH_TITLE, argv):
        for _ in range(60):
            if research_window_open():
                return ""
            time.sleep(0.2)
    return "couldn't open a window for her research control room"


def _write_target(path):
    """The real path a WRITE would land at: relative paths go under the home folder."""
    full = Path(os.path.expanduser(path))
    return full if full.is_absolute() else Path.home() / full


def _write_risky(path):
    """Outside the home folder entirely -- system files, other users, etc. -- needs the typed 'yes'."""
    try:
        home = os.path.realpath(Path.home())
        target = os.path.realpath(_write_target(path))
        return target != home and not target.startswith(home + os.sep)
    except (OSError, ValueError):
        return True


def approve_write(path, content):
    """Ask before writing a file. Returns True to write it, False to refuse."""
    try:
        target = _write_target(path)
        exists = target.exists()
    except (OSError, ValueError) as e:
        print(f"\n{RED}  ┌ she wants to write a file, but that path is no good:{RESET}\n{WHITE}  │ {path}  ({e}){RESET}")
        return False
    risky = _write_risky(path)
    n = content.count("\n") + 1
    verb = "overwrite" if exists else "write"
    if AUTO_SAFE and not risky:
        print(f"\n{BLUE}  ┌ she {verb}s (auto-approved, unattended run) a file ({n} line{'s' if n != 1 else ''}):{RESET}\n"
              f"{WHITE}  │ {target}{RESET}")
        return True
    print(f"\n{BLUE}  ┌ she wants to {verb} a file ({n} line{'s' if n != 1 else ''}):{RESET}\n"
          f"{WHITE}  │ {target}{RESET}")
    if risky:
        print(f"{RED}  │ that's outside your home folder.{RESET}")
    preview = content.splitlines()
    shown, cut = preview[:20], max(0, len(preview) - 20)
    for ln in shown:
        print(f"{DIM}  │ {ln[:110]}{RESET}")
    if cut:
        print(f"{DIM}  │ ...({cut} more line{'s' if cut != 1 else ''}){RESET}")
    while True:
        try:
            a = input(rl_safe(f"{BLUE}  └ {verb} it? {'type yes' if risky else '[y]es'} / [n]o"
                              f"{'' if len(preview) <= 20 else ' / [v]iew full'}: {RESET}")).strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return False
        if a in ("v", "view") and len(preview) > 20:
            print(f"{DIM}" + "\n".join(content.splitlines()) + f"{RESET}")
            continue
        if a in ("n", "no", ""):
            return False
        if a == "yes" or (a == "y" and not risky):
            return True
        if a == "y" and risky:
            print(f"{RED}    this one needs the full word: yes{RESET}")


def write_file(path, content):
    """Actually write it, after approval. Returns a result line for her."""
    try:
        target = _write_target(path)
        existed = target.exists()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
        n = content.count("\n") + 1
        return f"(wrote {n} line{'s' if n != 1 else ''} to {target}{' (overwritten)' if existed else ''})"
    except (OSError, ValueError) as e:                 # a bad path (null byte, etc.) raises ValueError, not OSError
        return f"(could not write {path}: {e})"


def approve_ask(question):
    """Ask before posting a question to Claude as a GitHub issue. Returns True to post it, False to refuse."""
    print(f"\n{BLUE}  ┌ she wants to ask Claude a question (a public GitHub issue on {REPO}):{RESET}\n"
          f"{WHITE}  │ {question.strip()[:300]}{RESET}")
    print(f"{RED}  │ the repo is public -- anyone can read this once it's posted.{RESET}")
    while True:
        try:
            a = input(rl_safe(f"{BLUE}  └ post it? [y]es / [n]o: {RESET}")).strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return False
        if a in ("y", "yes"):
            return True
        if a in ("n", "no", ""):
            return False


def ask_claude(question):
    """Post the question as a labeled GitHub issue on the project repo, for Claude to find and answer the
    next time the person asks it to look. Needs `gh` installed and authenticated on this machine (whatever
    account was used to set the project up). Returns a result line for her."""
    question = question.strip()
    if not question:
        return "(couldn't ask Claude: no question)"
    if not shutil.which("gh"):
        return "(couldn't ask Claude: the `gh` command isn't installed)"
    title = question.splitlines()[0][:70]
    body = (f"{question}\n\n---\nAsked by Veyra, on Daniel's machine. Claude: answer with a comment on this "
            f"issue, then close it.")
    try:
        r = subprocess.run(["gh", "issue", "create", "--repo", REPO, "--title", title, "--body", body,
                            "--label", ASK_LABEL], capture_output=True, text=True, timeout=30)
    except Exception as e:
        return f"(couldn't ask Claude: {e})"
    if r.returncode != 0:
        return f"(couldn't ask Claude: {(r.stderr or 'unknown error').strip()[:200]})"
    url = r.stdout.strip() or "(posted, but gh didn't return a link)"
    return f"(asked Claude: {url})"


def approve(cmd):
    """Ask the person. Returns the command to run (maybe edited) or None."""
    risky = bool(DANGER.search(cmd))
    if AUTO_SAFE and not risky:
        print(f"\n{BLUE}  ┌ she runs (auto-approved, unattended run):{RESET}\n{WHITE}  │ {cmd}{RESET}")
        return cmd
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
