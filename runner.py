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
import shutil
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


def watch_main(title, stream_path):
    """A plain tailing window, no job queue or pty -- used for Veyra-action, where a program she opened writes
    its own output straight into stream_path and this just shows it. Closes on the QUIT sentinel like the
    main window does, or on Ctrl+C."""
    stream_path = Path(stream_path)
    pidfile = stream_path.with_suffix(".pid")
    if pidfile.exists():
        try:
            other = int(pidfile.read_text())
            if other != os.getpid() and alive(other):
                print(f"{title} is already open.")
                time.sleep(2)
                return
        except Exception:
            pass
    pidfile.write_text(str(os.getpid()))
    sys.stdout.write(f"\x1b]0;{title}\x07")
    print(f"{P}V E Y R A{R}  {D}{title} · output from programs she opens appears here{R}\n")
    pos = stream_path.stat().st_size if stream_path.exists() else 0
    standby, blink_on, last_blink = True, True, 0.0
    label = f"{D}  ● standby — nothing opened yet{R}"
    try:
        while True:
            try:
                n = stream_path.stat().st_size if stream_path.exists() else 0
                if n < pos:
                    pos = 0
                if n > pos:
                    with stream_path.open("rb") as f:
                        f.seek(pos)
                        data = f.read(n - pos)
                    pos = n
                    quit_now = QUIT in data
                    data = data.replace(QUIT, b"")
                    if standby and data.strip():
                        sys.stdout.write("\r" + " " * (len(label) - len(D) - len(R)) + "\r")
                        standby = False
                    os.write(1, data)
                    if quit_now:
                        print(f"\n{D}(chat closed; this window closes too){R}")
                        time.sleep(1.2)
                        return
            except OSError:
                pass
            if standby and time.time() - last_blink > 0.6:
                last_blink = time.time()
                blink_on = not blink_on
                pad = " " * (len(label) - len(D) - len(R))
                sys.stdout.write("\r" + (label if blink_on else pad))
                sys.stdout.flush()
            time.sleep(0.1)
    except KeyboardInterrupt:
        pass
    finally:
        if pidfile.exists() and pidfile.read_text().strip() == str(os.getpid()):
            pidfile.unlink(missing_ok=True)


CLK_TCK = os.sysconf("SC_CLK_TCK") if hasattr(os, "sysconf") else 100
SERVER_NAME = {"ollama": "ollama", "openai": "llama-server"}   # kind -> process name to find, when she isn't in-process
V_GOLD, V_CYAN, V_RED, V_DIM, V_WHITE, V_RESET = ("\x1b[38;5;220m", "\x1b[38;5;51m", "\x1b[38;5;203m",
                                                   "\x1b[38;5;245m", "\x1b[38;5;231m", "\x1b[0m")


def _cpu_ticks(pid):
    """utime+stime, in clock ticks, for pid -- or None if it's gone, or this isn't Linux."""
    try:
        parts = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[-1].split()
        return int(parts[11]) + int(parts[12])             # fields 14 & 15 of /proc/pid/stat
    except Exception:
        return None


def _find_pid_by_name(name):
    """First living pid whose /proc/pid/comm is exactly `name` (Linux only), or None."""
    try:
        for p in Path("/proc").iterdir():
            if p.name.isdigit():
                try:
                    if (p / "comm").read_text().strip() == name:
                        return int(p.name)
                except OSError:
                    continue
    except OSError:
        pass
    return None


def _brain_pid(state):
    """Whichever process is actually doing her thinking right now: her own chat process when the model runs
    in-process (kind "llama"), or the local server's process when it's external (ollama, a llama.cpp server)."""
    kind = state.get("kind", "")
    if kind == "llama":
        return state.get("chat_pid")
    name = SERVER_NAME.get(kind)
    return _find_pid_by_name(name) if name else None


def _bar(pct, width):
    pct = 0 if pct is None else max(0.0, min(100.0, pct))
    fill = int(round(width * pct / 100))
    return V_RED + "█" * fill + V_DIM + "░" * (width - fill) + V_RESET


def _fmt_time(secs):
    secs = max(0, int(secs))
    h, r = divmod(secs, 3600)
    m, s = divmod(r, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def _wrap(text, width):
    words, lines, line = text.split(), [], ""
    for w in words:
        if line and len(line) + 1 + len(w) > width:
            lines.append(line)
            line = w
        else:
            line = f"{line} {w}" if line else w
    if line or not lines:
        lines.append(line)
    return lines


def vitals_main(title, state_path):
    """A small htop-like window: how much CPU she's using, tokens generated and their rate, how long she's
    been awake, and a live block showing whatever she's doing or thinking right now. Redraws in place every
    half second. Closes when the chat marks itself no longer running, or on Ctrl+C."""
    state_path = Path(state_path)
    pidfile = state_path.with_suffix(".pid")
    if pidfile.exists():
        try:
            other = int(pidfile.read_text())
            if other != os.getpid() and alive(other):
                print(f"{title} is already open.")
                time.sleep(2)
                return
        except Exception:
            pass
    pidfile.write_text(str(os.getpid()))
    sys.stdout.write(f"\x1b]0;{title}\x07")
    last_ticks = last_tick_t = None
    last_tokens, last_tok_t = 0, time.time()
    try:
        while True:
            try:
                st = json.loads(state_path.read_text())
            except Exception:
                st = {}
            now = time.time()
            pid = _brain_pid(st)
            ticks = _cpu_ticks(pid) if pid else None
            cpu_pct = None
            if ticks is not None and last_ticks is not None and last_tick_t is not None:
                dt = now - last_tick_t
                if dt > 0:
                    cpu_pct = (ticks - last_ticks) / CLK_TCK / dt * 100
            last_ticks, last_tick_t = ticks, now

            tokens = st.get("tokens", 0)
            dt2 = now - last_tok_t
            rate = (tokens - last_tokens) / dt2 if dt2 > 0 else 0.0
            last_tokens, last_tok_t = tokens, now

            uptime = now - st.get("start", now)
            cols = max(44, shutil.get_terminal_size((60, 20)).columns)
            who = {"llama": "built-in model", "ollama": "Ollama", "openai": "local server",
                   "hf": "Hugging Face (cloud)", "none": "", "": ""}.get(st.get("kind", ""), st.get("kind", ""))
            model = st.get("model", "")

            out = [f"\x1b[H\x1b[J{V_GOLD}V E Y R A{V_RESET}  {V_DIM}vitals{V_RESET}"]
            if cpu_pct is None:
                cpu_line = f"{V_DIM}n/a" + (f" ({who} process not found){V_RESET}" if who else f"{V_RESET}")
            else:
                bw = max(10, min(30, cols - 26))
                cpu_line = f"{_bar(cpu_pct, bw)} {V_WHITE}{cpu_pct:5.1f}%{V_RESET}  {V_DIM}{who}{V_RESET}"
            out.append(f"\n  {V_DIM}cpu{V_RESET}     {cpu_line}")
            out.append(f"  {V_DIM}tokens{V_RESET}  {V_WHITE}{tokens:,}{V_RESET} total  {V_DIM}·{V_RESET} "
                        f"{V_CYAN}{rate:.1f}{V_RESET} tok/s")
            out.append(f"  {V_DIM}uptime{V_RESET}  {V_WHITE}{_fmt_time(uptime)}{V_RESET}" +
                       (f"  {V_DIM}· {model}{V_RESET}" if model else ""))
            bw2 = cols - 4
            out.append(f"\n  {V_DIM}┌─ what she's doing right now " + "─" * max(0, bw2 - 28) + f"┐{V_RESET}")
            lines = _wrap(st.get("status", "waking up") or "...", bw2 - 2)[:4]
            for ln in lines:
                out.append(f"  {V_DIM}│{V_RESET} {V_CYAN}{ln.ljust(bw2 - 2)}{V_RESET} {V_DIM}│{V_RESET}")
            for _ in range(4 - len(lines)):
                out.append(f"  {V_DIM}│{V_RESET} {' ' * (bw2 - 2)} {V_DIM}│{V_RESET}")
            out.append(f"  {V_DIM}└" + "─" * bw2 + f"┘{V_RESET}\n")
            sys.stdout.write("\n".join(out))
            sys.stdout.flush()

            if not st.get("running", True) and st:
                print(f"\n{V_DIM}(chat closed; this window closes too){V_RESET}")
                time.sleep(1.2)
                return
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        if pidfile.exists() and pidfile.read_text().strip() == str(os.getpid()):
            pidfile.unlink(missing_ok=True)


if __name__ == "__main__":
    if len(sys.argv) >= 4 and sys.argv[1] == "watch":
        watch_main(sys.argv[2], sys.argv[3])
    elif len(sys.argv) >= 4 and sys.argv[1] == "vitals":
        vitals_main(sys.argv[2], sys.argv[3])
    else:
        main()
