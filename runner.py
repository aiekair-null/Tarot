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
import select
import shlex
import shutil
import sys
import termios
import time
import tty
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
# 5 levels for sparkline graphs -- plain ASCII, same reasoning as _bar(): no Unicode glyph to go missing.
BLOCKS = " .:+#"


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
    top = len(BLOCKS) - 1
    m = scale_max if scale_max else (max(values) or 1)
    return "".join(BLOCKS[max(0, min(top, round(v / m * top)))] for v in values)


def _bar(pct, width):
    """Plain ASCII, on purpose -- Unicode block-drawing characters fall back to an empty "tofu" box on a
    font that's missing that glyph, and there's no reliable way from here to know what font a window is
    using, so this sticks to characters every monospace font has."""
    pct = 0 if pct is None else max(0.0, min(100.0, pct))
    fill = int(round(width * pct / 100))
    return V_RED + "#" * fill + V_DIM + "-" * (width - fill) + V_RESET


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


_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def _vlen(s):
    """Length of a string as it actually prints, ignoring ANSI color codes."""
    return len(_ANSI_RE.sub("", s))


def _pad(s, width):
    """Pad a (possibly ANSI-colored) string with spaces out to a visible width, so a second column lines up
    beside it regardless of how many color codes are buried in the first."""
    return s + " " * max(1, width - _vlen(s))


def _cpu_temp():
    """Best-effort CPU temperature in Celsius, read straight from sysfs (no `sensors`/lm-sensors dependency).
    Prefers a zone that's clearly the CPU package; falls back to the first sane-looking zone. None if nothing
    readable."""
    try:
        zones = sorted(Path("/sys/class/thermal").glob("thermal_zone*"))
    except OSError:
        return None
    best = None
    for z in zones:
        try:
            kind = (z / "type").read_text().strip().lower()
            raw = int((z / "temp").read_text().strip())
        except (OSError, ValueError):
            continue
        c = raw / 1000.0
        if not (-40 < c < 150):
            continue
        if any(w in kind for w in ("pkg", "cpu", "core")):
            return c
        if best is None:
            best = c
    return best


# How often the vitals window redraws, in seconds -- shift+W cycles through these.
_RESOLUTIONS = [0.25, 0.5, 1.0, 2.0, 4.0]


def vitals_main(title, state_path):
    """A small htop-like window: live per-core CPU usage (every logical core, audited straight from
    /proc/stat -- not just the one process doing her thinking), uptime/tokens/temp off to the side of the
    core bars where there's room, and a small scrolling graph of overall CPU and token-rate history with the
    model name and current refresh resolution underneath. Shift+W cycles the refresh resolution. Redraws in
    place; closes when the chat marks itself no longer running, or on Ctrl+C."""
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
    res_idx = _RESOLUTIONS.index(0.5)
    interval = _RESOLUTIONS[res_idx]

    raw_fd = None
    old_term = None
    if sys.stdin.isatty():
        try:
            raw_fd = sys.stdin.fileno()
            old_term = termios.tcgetattr(raw_fd)
            tty.setcbreak(raw_fd)  # single keypresses, no Enter needed -- Ctrl+C still works (ISIG stays on)
        except (termios.error, ValueError, OSError):
            raw_fd = old_term = None

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

            cols = max(44, shutil.get_terminal_size((60, 20)).columns)

            out = [f"\x1b[H\x1b[J{V_GOLD}V E Y R A{V_RESET} {V_DIM}vitals" +
                   (f" · {len(cores)} cores{V_RESET}" if cores else f"{V_RESET}")]
            bw = max(8, min(22, cols - 20))
            core_lines = []
            if not cores:
                core_lines.append(f"  {V_DIM}cpu n/a (couldn't read /proc/stat){V_RESET}")
            else:
                for c, pct in zip(cores, core_pcts):
                    core_lines.append(f"  {V_DIM}{c:<6}{V_RESET} {_bar(pct, bw)} "
                                       f"{V_WHITE}{(0.0 if pct is None else pct):5.1f}%{V_RESET}")

            # Uptime/tokens/temp ride in the open space to the right of the core bars -- only when there's
            # actually room for them, so a narrow window just stays compact instead of wrapping.
            temp = _cpu_temp()
            side_lines = [
                f"{V_DIM}uptime{V_RESET} {V_WHITE}{_fmt_time(now - st.get('start', now))}{V_RESET}",
                f"{V_DIM}tokens{V_RESET} {V_WHITE}{tokens:,}{V_RESET} total",
                f"{V_WHITE}{rate:.1f}{V_RESET} tok/s",
                f"{V_DIM}temp{V_RESET}   {V_WHITE}{(f'{temp:.0f}C' if temp is not None else 'n/a')}{V_RESET}",
            ]
            panel_col = (max((_vlen(ln) for ln in core_lines), default=20) + 4) if core_lines else 20
            if cols >= panel_col + 20:
                for i in range(max(len(core_lines), len(side_lines))):
                    left = core_lines[i] if i < len(core_lines) else ""
                    right = side_lines[i] if i < len(side_lines) else ""
                    out.append(_pad(left, panel_col) + right if right else left)
            else:
                out.extend(core_lines)

            gw = max(10, cols - 7)
            cpu_line = _sparkline(list(cpu_hist)[-gw:], scale_max=100)
            tok_line = _sparkline(list(tok_hist)[-gw:])
            out.append(f"  {V_RED}cpu{V_RESET} {V_RED}{cpu_line}{V_RESET}")
            out.append(f"  {V_CYAN}tok{V_RESET} {V_CYAN}{tok_line}{V_RESET}")

            model = st.get("model") or "n/a"
            hz = 1 / interval
            out.append(f"  {V_DIM}model{V_RESET} {V_WHITE}{model}{V_RESET}   "
                       f"{V_DIM}res{V_RESET} {V_WHITE}{hz:g}/s{V_RESET} {V_DIM}(shift+w to change){V_RESET}")

            sys.stdout.write("\n".join(out))
            sys.stdout.flush()

            if not st.get("running", True) and st:
                print(f"\n{V_DIM}(chat closed; this window closes too){V_RESET}")
                time.sleep(1.2)
                return

            if raw_fd is not None:
                try:
                    r, _, _ = select.select([sys.stdin], [], [], interval)
                except (OSError, ValueError):
                    r = []
                if r:
                    try:
                        ch = sys.stdin.read(1)
                    except OSError:
                        ch = ""
                    if ch == "W":
                        res_idx = (res_idx + 1) % len(_RESOLUTIONS)
                        interval = _RESOLUTIONS[res_idx]
            else:
                time.sleep(interval)
    except KeyboardInterrupt:
        pass
    finally:
        if raw_fd is not None and old_term is not None:
            try:
                termios.tcsetattr(raw_fd, termios.TCSADRAIN, old_term)
            except (termios.error, OSError):
                pass
        if pidfile.exists() and pidfile.read_text().strip() == str(os.getpid()):
            pidfile.unlink(missing_ok=True)


_RESEARCH_TIPS = [
    "cross-check a claim across more than one source before trusting it",
    "note where something came from as you go -- site, title, date if you can tell",
    "a primary source beats someone's summary of it, when you can reach it",
    "if a keyword stops producing anything new, say so and move on to the next one",
    "broaden your terms when you're stuck, narrow them when you're drowning in noise",
]


def research_main(title, state_path):
    """Her research control room for an /autowork research run (bidding.py): which public sites she's
    searching, the keyword list with how far through each one's time slice she is, and overall progress
    against the whole time budget. Redraws in place every half second. Closes once bidding.py marks the run
    as no longer running (the budget ran out, or it was stopped early), or on Ctrl+C."""
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
    tip_i, last_tip = 0, 0.0
    try:
        while True:
            try:
                st = json.loads(state_path.read_text())
            except Exception:
                st = {}
            if not st:
                sys.stdout.write(f"\x1b[H\x1b[J{V_GOLD}V E Y R A{V_RESET} {V_DIM}research · control room{V_RESET}\n"
                                 f"  {V_DIM}(waiting for a research run to start...){V_RESET}")
                sys.stdout.flush()
                time.sleep(1)
                continue

            now = time.time()
            if now - last_tip > 8:
                tip_i, last_tip = (tip_i + 1) % len(_RESEARCH_TIPS), now

            platforms = st.get("platforms", [])
            keywords = st.get("keywords", [])
            current = st.get("current", 0)
            slice_elapsed = st.get("slice_elapsed", 0.0)
            slice_len = st.get("slice_len", 0.0) or 1.0
            elapsed = st.get("elapsed", 0.0)
            total = st.get("total_seconds", 0.0) or 1.0

            cols = max(50, shutil.get_terminal_size((70, 20)).columns)
            bw = max(10, min(24, cols - 32))

            out = [f"\x1b[H\x1b[J{V_GOLD}V E Y R A{V_RESET} {V_DIM}research · control room{V_RESET}",
                   f"  {V_DIM}sites{V_RESET}   {V_WHITE}{', '.join(platforms) or 'n/a'}{V_RESET}", ""]

            for i, kw in enumerate(keywords):
                if i < current:
                    pct, label = 100.0, "done"
                elif i == current:
                    pct = 0.0 if slice_len <= 0 else max(0.0, min(100.0, slice_elapsed / slice_len * 100))
                    label = "now"
                else:
                    pct, label = 0.0, "queued"
                lead = V_WHITE if i == current else V_DIM
                marker = ">" if i == current else " "
                out.append(f"  {lead}{marker} {kw[:28]:<28}{V_RESET} {_bar(pct, bw)} "
                           f"{V_WHITE}{pct:5.1f}%{V_RESET} {V_DIM}{label}{V_RESET}")

            overall_pct = max(0.0, min(100.0, elapsed / total * 100))
            out.append("")
            out.append(f"  {V_RED}overall{V_RESET} {_bar(overall_pct, bw)} {V_WHITE}{overall_pct:5.1f}%{V_RESET}  "
                       f"{V_DIM}{_fmt_time(elapsed)} / {_fmt_time(total)}{V_RESET}")
            out.append("")
            out.append(f"  {V_DIM}tip: {_RESEARCH_TIPS[tip_i]}{V_RESET}")

            sys.stdout.write("\n".join(out))
            sys.stdout.flush()

            if not st.get("running", True):
                print(f"\n{V_DIM}(research run finished; this window closes too){V_RESET}")
                time.sleep(1.5)
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
    elif len(sys.argv) >= 4 and sys.argv[1] == "research":
        research_main(sys.argv[2], sys.argv[3])
    else:
        main()
