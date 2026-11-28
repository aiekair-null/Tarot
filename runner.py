"""Veyra-output: her own window. When you open `veyra chat`, this window opens beside it. You type in the chat
window; everything she says (and her thinking arrow, and her grey notes) appears HERE. Commands you approve run
here too, in a real terminal that remembers its folder (cd sticks), so you can see everything and type into
programs that ask for input (passwords, y/n, menus). Their output goes back to her.

    veyra out      open this window yourself (veyra chat opens it for you when it can)

Ctrl+C here stops the command that is running; closing the window is fine, chat will reopen it."""
import json
import os
import pty
import re
import shlex
import sys
import time
from pathlib import Path

SPOOL = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "veyra" / "jobs"
PIDFILE = SPOOL.parent / "runner.pid"
STREAM = SPOOL.parent / "stream.log"       # what chat wants shown here (raw terminal text)
SIZE = SPOOL.parent / "size.json"          # this window's size, so her text wraps to it
CWDFILE = SPOOL.parent / "cwd"             # the folder this terminal is "in"
QUIT = b"\x00VEYRA-QUIT\x00"
TITLE = "Veyra-output"
ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]|\x1b\][^\x07]*\x07|\r")
P, B, W, D, R = "\x1b[38;5;99m", "\x1b[38;5;117m", "\x1b[38;5;231m", "\x1b[38;5;245m", "\x1b[0m"


def alive(pid):
    """Is that pid really the output window? (a stale pid file after a reboot may point at anything)"""
    try:
        os.kill(pid, 0)
    except Exception:
        return False
    try:
        return b"runner.py" in Path(f"/proc/{pid}/cmdline").read_bytes()
    except OSError:
        return True                                    # no /proc here (macOS): trust the pid


def run(job):
    cmd = job["cmd"]
    try:
        cwd = CWDFILE.read_text().strip() or str(Path.home())
        if not os.path.isdir(cwd):
            cwd = str(Path.home())
    except OSError:
        cwd = str(Path.home())
    shown = cwd.replace(str(Path.home()), "~", 1)
    script = (f"cd {shlex.quote(cwd)} 2>/dev/null || cd ~\n{cmd}\n__rc=$?\npwd > {shlex.quote(str(CWDFILE))}\nexit $__rc\n")
    print(f"\n{P}━━━ {W}Veyra runs{R} {D}in {shown}:{R} {B}{cmd}{R}")
    print(f"{D}    (type here if it asks for anything · Ctrl+C stops it){R}\n")
    buf = []

    def read(fd):
        data = os.read(fd, 4096)
        buf.append(data)
        return data

    start = time.time()
    try:
        status = pty.spawn(["bash", "-lc", script], read)
        code = os.waitstatus_to_exitcode(status) if hasattr(os, "waitstatus_to_exitcode") else status >> 8
    except KeyboardInterrupt:
        code = 130
    except Exception as e:
        buf.append(f"\n(could not run it: {e})".encode())
        code = 127
    out = ANSI.sub("", b"".join(buf).decode("utf-8", "replace"))
    took = time.time() - start
    colour = B if code == 0 else "\x1b[38;5;203m"
    print(f"\n{colour}━━━ finished · exit {code} · {took:.1f}s{R}")
    return out, code


def main():
    SPOOL.mkdir(parents=True, exist_ok=True)
    if PIDFILE.exists():
        try:
            other = int(PIDFILE.read_text())
            if other != os.getpid() and alive(other):
                print("Veyra's output window is already open.")
                time.sleep(2)
                return
        except Exception:
            pass
    PIDFILE.write_text(str(os.getpid()))
    for old in SPOOL.glob("*.done"):                  # results nobody collected
        try:
            if time.time() - old.stat().st_mtime > 3600:
                old.unlink()
        except OSError:
            pass
    os.chdir(Path.home())
    CWDFILE.write_text(str(Path.home()))
    sys.stdout.write(f"\x1b]0;{TITLE}\x07")
    print(f"{P}V E Y R A{R}  {D}{TITLE} · her words and your approved commands appear here{R}\n")
    pos, last_size = (STREAM.stat().st_size if STREAM.exists() else 0), None
    try:
        while True:
            try:                                           # keep chat told how wide this window is
                sz = os.get_terminal_size()
                if (sz.columns, sz.lines) != last_size:
                    last_size = (sz.columns, sz.lines)
                    SIZE.write_text(json.dumps({"cols": sz.columns, "rows": sz.lines}))
            except OSError:
                pass
            try:                                           # show what chat wrote for her
                n = STREAM.stat().st_size if STREAM.exists() else 0
                if n < pos:
                    pos = 0
                if n > pos:
                    with STREAM.open("rb") as f:
                        f.seek(pos)
                        data = f.read(n - pos)
                    pos = n
                    quit_now = QUIT in data
                    data = data.replace(QUIT, b"")
                    os.write(1, data)
                    if quit_now:
                        print(f"\n{D}(chat closed; this window closes too){R}")
                        time.sleep(1.2)
                        return
            except OSError:
                pass
            jobs = sorted(SPOOL.glob("*.json"))
            if not jobs:
                time.sleep(0.05)
                continue
            j = jobs[0]
            try:
                job = json.loads(j.read_text())
            except Exception:
                j.unlink(missing_ok=True)
                continue
            j.unlink(missing_ok=True)
            if time.time() - job.get("ts", time.time()) > 120:        # approved long ago: never run it late
                out, code = "(expired: it waited too long to start, so it was not run)", 124
            else:
                out, code = run(job)
            res = SPOOL / f"{job['id']}.done"
            tmp = res.with_suffix(".tmp")
            tmp.write_text(json.dumps({"code": code, "out": out}))
            tmp.replace(res)
    except KeyboardInterrupt:
        pass
    finally:
        if PIDFILE.exists() and PIDFILE.read_text().strip() == str(os.getpid()):
            PIDFILE.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
