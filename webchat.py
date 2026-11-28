"""veyra web: her chat as a neon red/black page on your Wi-Fi, opened on the TV automatically.

    veyra web            start her on this laptop and open the page on the TV (veyra-tv connect <ip> first)
    veyra web --no-tv    just serve it; open the printed address in any browser

The conversation lives on the laptop, so the TV and the laptop (or a phone) all show the same chat:
type wherever is handy, watch it on the big screen. Ctrl+C stops her."""
import json
import os
import random
import re
import socket
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import bidding
import brain

PORT = int(os.environ.get("VEYRA_WEB_PORT", "8777"))
HERE = Path(__file__).resolve().parent
TV_CFG = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "veyra-tv" / "tv"

state = {"log": [], "model": "", "sky": "", "status": "waking", "busy": False, "next": ""}
lock = threading.Lock()
B = brain.Brain(connect=False)
SYSTEM = ""

PAGE = """<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>VEYRA</title><style>
:root{--r:#ff1e2e;--d:#7a0a12}
*{box-sizing:border-box}html,body{margin:0;height:100%;background:#040406;color:#ffd6d9;
font-family:"DejaVu Sans Mono",Consolas,monospace}
body{display:flex;flex-direction:column;background:
linear-gradient(transparent 62%,rgba(255,30,46,.07)),#040406}
header{padding:18px 32px;border-bottom:3px solid var(--r);display:flex;gap:28px;align-items:baseline;
box-shadow:0 0 24px rgba(255,30,46,.45)}
h1{margin:0;font-size:46px;letter-spacing:14px;color:var(--r);text-shadow:0 0 12px var(--r),0 0 32px var(--r)}
.meta{font-size:18px;color:#c9727a}.meta b{color:#ff8a93;font-weight:normal}
#log{flex:1;overflow-y:auto;padding:24px 40px;font-size:30px;line-height:1.45}
.u{color:#ff8a93;margin:22px 0 6px}.u:before{content:"› ";color:var(--r)}
.a{color:#ffe9ea;white-space:pre-wrap;text-shadow:0 0 6px rgba(255,30,46,.35)}
.note{color:#9a4a52;font-size:20px;margin-top:4px}
form{display:flex;border-top:3px solid var(--r);box-shadow:0 0 24px rgba(255,30,46,.45)}
input{flex:1;background:#000;color:#fff;border:0;padding:22px 32px;font:inherit;font-size:30px;outline:none}
input::placeholder{color:#a8323c}button{background:var(--r);color:#000;border:0;padding:0 40px;font:inherit;font-size:28px;font-weight:bold}
.cur{display:inline-block;width:.55em;background:var(--r);animation:b 1s steps(1) infinite}@keyframes b{50%{opacity:0}}
</style></head><body>
<header><h1>VEYRA</h1><div class="meta">model <b id="m">…</b> &nbsp; sky <b id="s">…</b> &nbsp; <span id="st"></span></div></header>
<div id="log"></div>
<form id="f"><input id="q" placeholder="What is thy bidding?" autocomplete="off" autofocus><button>ASK</button></form>
<script>
let n=-1;const L=document.getElementById('log');
async function poll(){try{const r=await fetch('/state');const j=await r.json();
document.getElementById('m').textContent=j.model;document.getElementById('s').textContent=j.sky;
document.getElementById('st').textContent=j.status==='ready'?'':'('+j.status+')';
document.getElementById('q').placeholder=j.next||'What is thy bidding?';
const key=JSON.stringify(j.log)+j.busy;if(key!==n){n=key;const atEnd=L.scrollTop+L.clientHeight>L.scrollHeight-40;L.innerHTML='';
for(const e of j.log){const d=document.createElement('div');d.className=e.role==='user'?'u':'a';d.textContent=e.text;
if(e.role!=='user'&&j.busy&&e===j.log[j.log.length-1]){const c=document.createElement('span');c.className='cur';c.innerHTML='&nbsp;';d.appendChild(c)}
L.appendChild(d);for(const t of e.notes||[]){const k=document.createElement('div');k.className='note';k.textContent='(she noted: '+t+')';L.appendChild(k)}}
if(atEnd)L.scrollTop=L.scrollHeight}}catch(e){}setTimeout(poll,700)}
document.getElementById('f').onsubmit=async e=>{e.preventDefault();const q=document.getElementById('q');const t=q.value.trim();if(!t)return;q.value='';
await fetch('/ask',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({q:t})})};
poll();
</script></body></html>"""


def answer(q):
    with lock:
        state["log"].append({"role": "user", "text": q})
        reply = {"role": "assistant", "text": "", "notes": []}
        state["log"].append(reply)
        state["busy"] = True
        state["status"] = "she thinks over what you said"
    try:
        if B.kind == "none":
            reply["text"] = bidding.diagnose(None, "Her model would not wake: " + (B.err or "no model installed"),
                                             "waking her model")
            return
        hist = [{"role": "user" if e["role"] == "user" else "assistant", "content": e["text"]}
                for e in state["log"][:-1][-12:]]
        msgs = [{"role": "system", "content": SYSTEM}] + hist
        raw = ""
        for piece in B.stream(msgs, max_tokens=700, temperature=0.7):
            state["status"] = "she is speaking"
            raw += piece
            reply["text"] = re.sub(r"\n?(REMEMBER|NEXT):.*", "", raw, flags=re.S | re.I).rstrip()  # hide tag lines
        m = re.search(r"NEXT:\s*(.+)", raw, re.I)
        state["next"] = m.group(1).strip().strip('"')[:90] if m else ""
        for m in re.finditer(r"REMEMBER:\s*(.+)", raw, re.I):
            note = m.group(1).strip()
            if note:
                reply["notes"].append(note)
                try:
                    bidding.save_note(note)
                except Exception:
                    pass
    except Exception as e:                                # explain, don't crash
        state["status"] = "something snagged; she works out what went wrong"
        reply["text"] = bidding.diagnose(B, e, "answering on the TV")
    finally:
        state["busy"] = False
        state["status"] = "ready" if B.kind != "none" else "no model"


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype):
        b = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        if self.path.startswith("/state"):
            return self._send(200, json.dumps(state), "application/json")
        return self._send(200, PAGE, "text/html; charset=utf-8")

    def do_POST(self):
        if self.path != "/ask":
            return self._send(404, "{}", "application/json")
        n = int(self.headers.get("Content-Length") or 0)
        try:
            q = json.loads(self.rfile.read(n) or b"{}").get("q", "").strip()[:2000]
        except Exception:
            q = ""
        if q and not state["busy"]:
            threading.Thread(target=answer, args=(q,), daemon=True).start()
        return self._send(200, "{}", "application/json")


def lan_ip(toward="192.168.1.1"):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect((toward, 9))                              # no packet is sent; picks the Wi-Fi interface
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


def open_on_tv(url):
    tool = HERE / "tv" / "veyra-tv"
    if not TV_CFG.exists():
        print("  (no TV saved yet: run  veyra-tv connect <tv-ip>  once, then  veyra web  again)")
        return
    r = subprocess.run([str(tool), "open", url], capture_output=True, text=True)
    print("  " + (r.stdout or r.stderr).strip().replace("\n", "\n  "))


def main():
    global SYSTEM
    no_tv = "--no-tv" in sys.argv
    state["model"] = bidding.pick_model()
    short, full = bidding.sky_lines()
    state["sky"] = short or "unknown"
    SYSTEM = bidding.SYSTEM + "\nTONIGHT'S SKY: " + (full or "unknown") + "\n" + bidding.lore_flavor(random.SystemRandom())

    def wake():
        B.connect()
        state["status"] = "ready" if B.kind != "none" else "no model"
    threading.Thread(target=wake, daemon=True).start()

    tv = TV_CFG.read_text().strip().split(":")[0] if TV_CFG.exists() else "192.168.1.1"
    url = f"http://{lan_ip(tv)}:{PORT}/"
    srv = ThreadingHTTPServer(("0.0.0.0", PORT), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    print(f"\n  VEYRA is listening at {url}   (Ctrl+C to stop)")
    if not no_tv:
        open_on_tv(url)
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        print("\n  She sleeps.")
        srv.shutdown()


if __name__ == "__main__":
    main()
