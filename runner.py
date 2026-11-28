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
from collections import deque
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


V_GOLD, V_CYAN, V_RED, V_DIM, V_WHITE, V_RESET = ("\x1b[38;5;220m", "\x1b[38;5;51m", "\x1b[38;5;203m",
                                                   "\x1b[38;5;245m", "\x1b[38;5;231m", "\x1b[0m")
BLOCKS = " ▁▂▃▄▅▆▇█"          # 9 levels, for sparkline graphs


def _cpu_snapshot():
    """{'cpu': (idle, total), 'cpu0': (idle, total), ...} read fresh from /proc/stat -- one entry for the
    system overall plus one per logical core -- or {} off-Linux or on any error."""
    out = {}
    try:
        for ln in Path("/proc/stat").read_text().splitlines():
            parts = ln.split()
            if parts and parts[0].startswith("cpu"):
                try:
                    nums = [int(x) for x in parts[1:]]
                except ValueError:
                    continue
                if len(nums) >= 4:
                    idle = nums[3] + (nums[4] if len(nums) > 4 else 0)   # idle + iowait
                    out[parts[0]] = (idle, sum(nums))
    except OSError:
        pass
    return out


def _core_pct(prev, cur):
    """Percent busy between two (idle, total) snapshots of the same core/overall line, or None without a
    usable delta (first reading, or the counters didn't move)."""
    if not prev or not cur:
        return None
    d_total = cur[1] - prev[1]
    if d_total <= 0:
        return None
    d_idle = cur[0] - prev[0]
    return max(0.0, min(100.0, (1 - d_idle / d_total) * 100))


def _sparkline(values, scale_max=None):
    """A one-line string of block characters, one per value (oldest first), for a tiny history graph.
    Self-scales to the loudest value seen unless `scale_max` pins the ceiling (e.g. 100 for a percentage)."""
    if not values:
        return ""
    m = scale_max if scale_max else (max(values) or 1)
    return "".join(BLOCKS[max(0, min(8, round(v / m * 8)))] for v in values)


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
    """A small htop-like window: live per-core CPU usage (every logical core, audited straight from
    /proc/stat -- not just the one process doing her thinking), tokens generated and their rate, how long
    she's been awake, and a small scrolling graph of overall CPU and token-rate history. Redraws in place
    every half second. Closes when the chat marks itself no longer running, or on Ctrl+C."""
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
    last_stat = {}
    last_tokens, last_tok_t = 0, time.time()
    cpu_hist, tok_hist = deque(maxlen=200), deque(maxlen=200)
    try:
        while True:
            try:
                st = json.loads(state_path.read_text())
            except Exception:
                st = {}
            now = time.time()

            cur_stat = _cpu_snapshot()
            cores = sorted((k for k in cur_stat if k != "cpu" and k[3:].isdigit()), key=lambda k: int(k[3:]))
            core_pcts = [_core_pct(last_stat.get(c), cur_stat.get(c)) for c in cores]
            overall_pct = _core_pct(last_stat.get("cpu"), cur_stat.get("cpu"))
            last_stat = cur_stat

            tokens = st.get("tokens", 0)
            dt2 = now - last_tok_t
            rate = max(0.0, (tokens - last_tokens) / dt2 if dt2 > 0 else 0.0)
            last_tokens, last_tok_t = tokens, now

            if overall_pct is not None:
                cpu_hist.append(overall_pct)
            tok_hist.append(rate)

            uptime = now - st.get("start", now)
            cols = max(44, shutil.get_terminal_size((60, 20)).columns)
            model = st.get("model", "")

            out = [f"\x1b[H\x1b[J{V_GOLD}V E Y R A{V_RESET}  {V_DIM}vitals{V_RESET}\n"]
            bw = max(8, min(22, cols - 20))
            if not cores:
                out.append(f"  {V_DIM}cpu{V_RESET}      {V_DIM}n/a (couldn't read /proc/stat){V_RESET}")
            else:
                out.append(f"  {V_DIM}cpu -- {len(cores)} cores{V_RESET}")
                for c, pct in zip(cores, core_pcts):
                    out.append(f"  {V_DIM}{c:<6}{V_RESET} {_bar(pct, bw)} "
                               f"{V_WHITE}{(0.0 if pct is None else pct):5.1f}%{V_RESET}")
            out.append(f"\n  {V_DIM}tokens{V_RESET}  {V_WHITE}{tokens:,}{V_RESET} total  {V_DIM}·{V_RESET} "
                        f"{V_CYAN}{rate:.1f}{V_RESET} tok/s")
            out.append(f"  {V_DIM}uptime{V_RESET}  {V_WHITE}{_fmt_time(uptime)}{V_RESET}" +
                       (f"  {V_DIM}· {model}{V_RESET}" if model else ""))

            gw = max(10, cols - 11)
            cpu_line = _sparkline(list(cpu_hist)[-gw:], scale_max=100)
            tok_line = _sparkline(list(tok_hist)[-gw:])
            out.append(f"\n  {V_DIM}graph{V_RESET}")
            out.append(f"  {V_RED}cpu{V_RESET}  {V_RED}{cpu_line}{V_RESET}")
            out.append(f"  {V_CYAN}tok{V_RESET}  {V_CYAN}{tok_line}{V_RESET}\n")

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
