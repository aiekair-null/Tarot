"""Veyra's brain. Free and local first; nothing here sends a bill.

Order tried (unless TAROT_BACKEND says otherwise):
  1. llama  - a GGUF model running INSIDE this program via llama-cpp-python (the built-in model)
  2. ollama - an Ollama server on this machine (http://localhost:11434)
  3. openai - any local OpenAI-compatible server at TAROT_LOCAL_URL (LM Studio, llama.cpp server...)
  4. none   - no model: Veyra reads from her scripted knowledge, which is complete on its own.
Hugging Face's paid router is only used if you explicitly set TAROT_BACKEND=hf.

Get the built-in model:  python models.py download        (one-time, free, ~2.1 GB, Qwen2.5 3B)
"""
import json, os, sys, threading, urllib.request
from pathlib import Path

MODELS_DIR = Path(os.environ.get("TAROT_MODELS_DIR", "models"))
ACTIVE = MODELS_DIR / "active.txt"
OLLAMA = os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
if not OLLAMA.startswith("http"):
    OLLAMA = "http://" + OLLAMA

# Free GGUF files (public, no token needed). key: (repo, file, size, note)
DEFAULT = "medium"
CATALOG = {
    "medium": ("Qwen/Qwen2.5-3B-Instruct-GGUF", "qwen2.5-3b-instruct-q4_k_m.gguf", "2.1 GB",
               "DEFAULT: rich readings; 2-5 min per reading on 2 cores (the ritual covers the wait)"),
    "qwen3-8b": ("Qwen/Qwen3-8B-GGUF", "Qwen3-8B-Q4_K_M.gguf", "5.0 GB",
                 "Qwen3 8B, higher capacity; needs about 5 GB of disk and more memory"),
    "small": ("Qwen/Qwen2.5-1.5B-Instruct-GGUF", "qwen2.5-1.5b-instruct-q4_k_m.gguf", "1.1 GB",
              "faster, simpler readings; for slow machines"),
    "llama": ("bartowski/Llama-3.2-3B-Instruct-GGUF", "Llama-3.2-3B-Instruct-Q4_K_M.gguf", "2.0 GB",
              "a different voice, similar size to medium"),
}
OLLAMA_PREFER = ("qwen2.5", "llama3", "gemma", "mistral", "phi")


def find_gguf():
    """The GGUF to load: TAROT_GGUF, then the explicit 8B default, then active.txt."""
    p = os.environ.get("TAROT_GGUF")
    if p and Path(p).exists():
        return Path(p)
    qwen3 = MODELS_DIR / CATALOG["qwen3-8b"][1]
    if qwen3.exists():
        ACTIVE.write_text(qwen3.name)
        return qwen3
    try:
        a = MODELS_DIR / ACTIVE.read_text().strip()
        if a.exists():
            return a
    except Exception:
        pass
    pref = MODELS_DIR / CATALOG[DEFAULT][1]
    if pref.exists():
        return pref
    found = sorted(MODELS_DIR.glob("*.gguf"), key=lambda f: f.stat().st_mtime, reverse=True) if MODELS_DIR.exists() else []
    return found[0] if found else None


def download(key=DEFAULT, log=print):
    """Fetch a free GGUF from Hugging Face (a plain file download, not paid inference)."""
    repo, fname, size, _ = CATALOG[key]
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    dest = MODELS_DIR / fname
    if not dest.exists():
        log(f"Downloading {fname} ({size}) from huggingface.co/{repo} ...")
        try:
            from huggingface_hub import hf_hub_download
            hf_hub_download(repo, fname, local_dir=str(MODELS_DIR))
        except ImportError:
            url = f"https://huggingface.co/{repo}/resolve/main/{fname}"
            tmp = dest.with_suffix(".part")
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Veyra/2"})) as r, \
                    open(tmp, "wb") as f:
                total, got = int(r.headers.get("Content-Length", 0)), 0
                while chunk := r.read(1 << 20):
                    f.write(chunk)
                    got += len(chunk)
                    if total:
                        sys.stdout.write(f"\r  {got * 100 // total:3d}%  {got >> 20} / {total >> 20} MB")
                        sys.stdout.flush()
            print()
            tmp.replace(dest)
    ACTIVE.write_text(fname)
    return dest


def _get_json(url, timeout=2.0, data=None):
    req = urllib.request.Request(url, data=json.dumps(data).encode() if data else None,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def ollama_models():
    try:
        return [m["name"] for m in _get_json(OLLAMA + "/api/tags").get("models", [])]
    except Exception:
        return []


class Brain:
    def __init__(self, connect=True):
        self.lock = threading.RLock()
        self.kind, self.label, self.err = "none", "scripted knowledge (no model)", ""
        self.llm = self.client = None
        self.url = self.model = ""
        self.progress = 0
        self.load_stage = "waking"
        if connect:
            self.connect()

    @property
    def online(self):
        return self.kind != "none"

    @property
    def local(self):
        return self.kind in ("llama", "ollama", "openai")

    # ---- connecting ------------------------------------------------------------
    def connect(self, prefer=None):
        prefer = (prefer or os.environ.get("TAROT_BACKEND", "auto")).lower()
        self.progress, self.load_stage = 5, "looking for a model"
        self.kind, self.label, self.err, self.llm, self.client = "none", "scripted knowledge (no model)", "", None, None
        if prefer in ("none", "scripted", "off"):
            return self
        order = [prefer] if prefer != "auto" else (["openai"] if os.environ.get("TAROT_LOCAL_URL") else []) + ["llama", "ollama"]
        notes = []
        for k in order:
            try:
                if getattr(self, "_try_" + k)():
                    self.kind = k
                    self.progress, self.load_stage = 100, "Veyra is awake"
                    return self
            except Exception as e:
                notes.append(f"{k}: {str(e)[:120]}")
        self.err = "; ".join(notes) or "no model found"
        self.progress, self.load_stage = 100, "scripted knowledge is ready"
        return self

    def _try_llama(self):
        path = find_gguf()
        if not path:
            raise RuntimeError("no .gguf in models/ (run: python models.py download)")
        self.progress, self.load_stage = 25, "finding the familiar pages"
        try:
            from llama_cpp import Llama
        except ImportError:
            raise RuntimeError("llama-cpp-python not installed (run: bash setup_local.sh)")
        self.progress, self.load_stage = 45, "warming the candle"
        self.llm = Llama(model_path=str(path), n_ctx=int(os.environ.get("TAROT_CTX", "8192")),
                         n_threads=int(os.environ.get("TAROT_THREADS", os.cpu_count() or 2)), verbose=False)
        self.progress, self.load_stage = 100, "Veyra is awake"
        self.label = f"built-in {path.name}"
        return True

    def _try_ollama(self):
        names = ollama_models()
        if not names:
            raise RuntimeError(f"no Ollama server with models at {OLLAMA}")
        want = os.environ.get("TAROT_OLLAMA_MODEL")
        pick = want if want in names else next((n for p in OLLAMA_PREFER for n in names if p in n), names[0])
        self.url, self.model, self.label = OLLAMA + "/v1", pick, f"Ollama {pick}"
        return True

    def _try_openai(self):
        self.url = os.environ.get("TAROT_LOCAL_URL", "").rstrip("/")
        if not self.url:
            raise RuntimeError("TAROT_LOCAL_URL not set")
        self.model = os.environ.get("TAROT_MODEL", "local")
        self.label = f"local server {self.url}"
        return True

    def _try_hf(self):
        token, model = os.environ.get("HF_TOKEN"), os.environ.get("TAROT_MODEL", "")
        if not model:
            try:
                model = Path(os.environ.get("TAROT_MODEL_FILE", "model.txt")).read_text().strip()
            except Exception:
                pass
        model, _, prov = model.partition("::")
        if not (token and model):
            raise RuntimeError("HF needs HF_TOKEN and TAROT_MODEL (and costs credits)")
        from huggingface_hub import InferenceClient
        self.client = InferenceClient(model=model, token=token, provider=prov or "auto")
        self.label = f"Hugging Face {model} (paid)"
        return True

    # ---- talking ---------------------------------------------------------------
    def stream(self, msgs, max_tokens=600, temperature=0.8, wait=True, _control=False):
        """Yield text pieces as they are generated. wait=False yields nothing if the model is busy.
        The control room (Ctrl+W) can pause it between tokens and tunes how it samples;
        _control=True is the control room's own agent talking, which is never paused or tuned."""
        if not self.online:
            return
        if not self.lock.acquire(blocking=wait):
            return
        import control
        if not _control:
            msgs = [dict(m) for m in msgs]
            note = control.operator_note()
            if note and msgs and msgs[0].get("role") == "system":
                msgs[0]["content"] += note
            elif note:
                msgs.insert(0, {"role": "system", "content": note.strip()})
            max_tokens = control.max_tokens(max_tokens)
        tune = {} if _control else control.sampling(self.kind)

        def out(piece):
            if not _control:
                control.gate()                      # Ctrl+W: hold here until the control room closes
                control.saw(piece)
            return piece
        try:
            if self.kind == "llama":
                extra = dict(tune)
                if not _control:
                    bias = control.logit_bias(self.llm.tokenize)
                    if bias:
                        extra["logit_bias"] = bias
                extra.setdefault("repeat_penalty", 1.12)
                try:
                    it = self.llm.create_chat_completion(messages=msgs, max_tokens=max_tokens, temperature=temperature,
                                                         stream=True, **extra)
                except TypeError:                   # an older llama-cpp-python without some knob
                    it = self.llm.create_chat_completion(messages=msgs, max_tokens=max_tokens, temperature=temperature,
                                                         repeat_penalty=extra["repeat_penalty"], stream=True)
                for ch in it:
                    piece = ch["choices"][0].get("delta", {}).get("content")
                    if piece:
                        yield out(piece)
            elif self.kind in ("ollama", "openai"):
                body = {"model": self.model, "messages": msgs, "max_tokens": max_tokens,
                        "temperature": temperature, "stream": True, **tune}
                req = urllib.request.Request(self.url + "/chat/completions", json.dumps(body).encode(),
                                             {"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=600) as r:
                    for raw in r:
                        line = raw.decode("utf-8", "ignore").strip()
                        if not line.startswith("data:") or line.endswith("[DONE]"):
                            continue
                        try:
                            piece = json.loads(line[5:])["choices"][0].get("delta", {}).get("content")
                        except Exception:
                            piece = None
                        if piece:
                            yield out(piece)
            elif self.kind == "hf":
                for ch in self.client.chat_completion(messages=msgs, max_tokens=max_tokens,
                                                      temperature=temperature, stream=True):
                    piece = ch.choices[0].delta.content if ch.choices else None
                    if piece:
                        yield out(piece)
        finally:
            self.lock.release()

    def busy(self):
        """True while another thread is using the model (so quick jobs can skip it)."""
        if self.lock.acquire(blocking=False):
            self.lock.release()
            return False
        return True

    def chat(self, msgs, max_tokens=600, temperature=0.8, wait=True, _control=False):
        return "".join(self.stream(msgs, max_tokens, temperature, wait, _control)).strip()

    def check(self):
        """One tiny call so problems show before the ritual starts."""
        if not self.online:
            return False, self.err
        try:
            self.chat([{"role": "user", "content": "Reply with the single word: ready"}], 8, 0.1)
            return True, ""
        except Exception as e:
            self.err = str(e)[:200]
            self.kind, self.label = "none", "scripted knowledge (model failed)"
            return False, self.err
