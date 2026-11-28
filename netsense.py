"""Veyra's senses for the internet (read-only): search the web, read a page or file, and "watch" a YouTube
video through its captions. She asks for these with one line in her reply:

    SEARCH: <words>      READ: <url>      YOUTUBE: <url or video id>

Nothing here posts, logs in, downloads to disk or runs anything; it only reads and hands her plain text."""
import html
import io
import json
import re
import sys
import urllib.parse
import urllib.request
from html.parser import HTMLParser

LIMIT = 2500                                           # characters of each result she gets to read
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Veyra/1.0"}
TOOLS = ("SEARCH:", "READ:", "YOUTUBE:")
LABEL = {"SEARCH": "search the web for", "READ": "read the page", "YOUTUBE": "read the captions of"}
BLUE, WHITE, DIM, RESET = "\x1b[38;5;117m", "\x1b[38;5;231m", "\x1b[38;5;245m", "\x1b[0m"

HOW = ("\nYOU CAN REACH THE INTERNET (read-only). When you need something current, a page, a file or a "
       "video, write ONE line on its own and then stop and wait:\n"
       "SEARCH: <words>        (web search)\n"
       "READ: <url>            (read a web page, text file or PDF)\n"
       "YOUTUBE: <url>         (read a YouTube video's captions; you see what is said, not the picture)\n"
       "The person approves each one before it happens. The result comes back to you as RESULT. Then answer "
       "from it and name where it came from. Never invent results; if a result is empty or an error, say what "
       "went wrong and suggest how to fix it.")


def _rl_safe(s):
    """Mark colour codes as zero-width for readline, so editing a long line doesn't garble the prompt."""
    return re.sub(r"(\x1b\[[0-9;]*m)", "\001\\1\002", s) if "readline" in sys.modules else s


def approve(tool, arg):
    """Ask before going online. Returns the argument (maybe edited) or None if refused."""
    print(f"\n{BLUE}  ┌ she wants to go online to {LABEL[tool]}:{RESET}\n{WHITE}  │ {arg}{RESET}")
    while True:
        try:
            a = input(_rl_safe(f"{BLUE}  └ allow it? [y]es / [n]o / [e]dit: {RESET}")).strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return None
        if a in ("e", "edit"):
            try:
                new = input(_rl_safe(f"{DIM}    your version: {RESET}")).strip()
            except (EOFError, KeyboardInterrupt):
                return None
            if new:
                arg = new
            continue
        if a in ("n", "no", ""):
            return None
        if a in ("y", "yes"):
            return arg


class _Text(HTMLParser):
    SKIP = {"script", "style", "noscript", "svg", "nav", "footer", "header", "form", "button"}

    def __init__(self):
        super().__init__()
        self.out, self.skip, self.title, self._t = [], 0, "", False

    def handle_starttag(self, tag, a):
        if tag in self.SKIP:
            self.skip += 1
        elif tag == "title":
            self._t = True
        elif tag in ("p", "br", "li", "h1", "h2", "h3", "h4", "tr", "div"):
            self.out.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.skip:
            self.skip -= 1
        elif tag == "title":
            self._t = False

    def handle_data(self, d):
        if self._t:
            self.title += d
        elif not self.skip:
            self.out.append(d)


def _clean(s):
    s = re.sub(r"[ \t\r\f\v]+", " ", s)
    s = re.sub(r"\n\s*\n+", "\n", s)
    return s.strip()


def _get(url, timeout=20):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(3_000_000), (r.headers.get("Content-Type") or "").lower()


def search(q, n=5):
    try:
        try:
            from ddgs import DDGS
        except ImportError:
            from duckduckgo_search import DDGS
        hits = DDGS().text(q, max_results=n)
        return "\n".join(f"- {h.get('title', '')}\n  {h.get('href', '')}\n  {h.get('body', '')}" for h in hits)[:LIMIT] \
            or "(no results)"
    except ImportError:
        return "(web search needs the ddgs package: run  veyra setup)"
    except Exception as e:
        return f"(search failed: {e})"


def read(url):
    url = url.strip().strip("<>\"'")
    if not re.match(r"https?://", url):
        url = "https://" + url
    try:
        data, ctype = _get(url)
    except Exception as e:
        return f"(could not open {url}: {e})"
    if "pdf" in ctype or url.lower().endswith(".pdf"):
        try:
            from pypdf import PdfReader
            text = "\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(data)).pages[:15])
            return f"[PDF {url}]\n" + _clean(text)[:LIMIT]
        except ImportError:
            return "(that is a PDF; reading PDFs needs the pypdf package: run  veyra setup)"
        except Exception as e:
            return f"(could not read the PDF: {e})"
    text = data.decode("utf-8", "replace")
    if "html" in ctype or "<html" in text[:2000].lower():
        p = _Text()
        p.feed(text)
        title = _clean(html.unescape(p.title))
        return f"[{title or url}]\n" + _clean(html.unescape("".join(p.out)))[:LIMIT]
    return f"[{url}]\n" + _clean(text)[:LIMIT]


def _video_id(s):
    s = s.strip()
    m = re.search(r"(?:v=|youtu\.be/|shorts/|embed/|live/)([A-Za-z0-9_-]{11})", s)
    return m.group(1) if m else (s if re.fullmatch(r"[A-Za-z0-9_-]{11}", s) else None)


def youtube(url):
    vid = _video_id(url)
    if not vid:
        return "(that does not look like a YouTube link)"
    head = ""
    try:
        meta, _ = _get("https://www.youtube.com/oembed?format=json&url="
                       + urllib.parse.quote(f"https://www.youtube.com/watch?v={vid}"))
        m = json.loads(meta)
        head = f"[YouTube: {m.get('title', '')} — by {m.get('author_name', '')}]\n"
    except Exception:
        head = f"[YouTube video {vid}]\n"
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        try:
            parts = YouTubeTranscriptApi().fetch(vid)             # v1.x
            words = " ".join(p.text for p in parts)
        except AttributeError:
            words = " ".join(p["text"] for p in YouTubeTranscriptApi.get_transcript(vid))   # older versions
        return head + _clean(words.replace("\n", " "))[:LIMIT * 2]
    except ImportError:
        return head + "(reading captions needs the youtube-transcript-api package: run  veyra setup)"
    except Exception as e:
        return head + f"(no captions could be read: {str(e).splitlines()[0][:160]})"


def find_call(text):
    """The first tool line in her reply, as (tool, argument), or None."""
    for line in text.splitlines():
        s = line.strip().strip("*`")
        for t in TOOLS:
            if s.upper().startswith(t):
                arg = s[len(t):].strip()
                if arg:
                    return t[:-1].upper(), arg
    return None


def run(call):
    tool, arg = call
    return {"SEARCH": search, "READ": read, "YOUTUBE": youtube}[tool](arg)
