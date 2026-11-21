"""Get a finished video off this machine: download it to your device, or share it to Facebook.

Download: in GitHub Codespaces, Veyra serves the file on a forwarded port and prints a link that
opens in the same browser you use for the Codespace (on a local machine, the link is localhost).

Facebook: Meta only lets apps post to Facebook *Pages*, never to personal profiles. If you add a
Page id and Page access token (as Codespaces secrets FB_PAGE_ID and FB_PAGE_TOKEN), Veyra uploads
the video straight to your Page after you confirm. For a personal profile, she gives you the
download link and the steps to post it from the Facebook app."""
import json, mimetypes, os, threading, time, urllib.parse, urllib.request, uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PORT = int(os.environ.get("TAROT_SHARE_PORT", "8790"))
GRAPH = os.environ.get("FB_GRAPH_URL", "https://graph.facebook.com").rstrip("/")
GRAPH_VIDEO = os.environ.get("FB_GRAPH_VIDEO_URL", "https://graph-video.facebook.com").rstrip("/")
API = os.environ.get("FB_API_VERSION", "").strip("/")          # e.g. v21.0; blank = your app's default


def in_codespace():
    return bool(os.environ.get("CODESPACE_NAME"))


def public_link(port, name):
    host = os.environ.get("CODESPACE_NAME")
    if host:
        dom = os.environ.get("GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN", "app.github.dev")
        return f"https://{host}-{port}.{dom}/{urllib.parse.quote(name)}"
    return f"http://localhost:{port}/{urllib.parse.quote(name)}"


def serve(path, wait):
    """Serve one file as a download until `wait()` returns. Returns the link that was offered."""
    path = Path(path).resolve()

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            if urllib.parse.unquote(self.path.lstrip("/").split("?")[0]) not in (path.name, ""):
                self.send_error(404)
                return
            size = path.stat().st_size
            self.send_response(200)
            self.send_header("Content-Type", mimetypes.guess_type(path.name)[0] or "application/octet-stream")
            self.send_header("Content-Length", str(size))
            self.send_header("Content-Disposition", f'attachment; filename="{path.name}"')
            self.end_headers()
            with open(path, "rb") as f:
                while chunk := f.read(1 << 20):
                    try:
                        self.wfile.write(chunk)
                    except (BrokenPipeError, ConnectionResetError):
                        return

    server, port = None, PORT
    for port in range(PORT, PORT + 10):
        try:
            server = ThreadingHTTPServer(("0.0.0.0", port), H)
            break
        except OSError:
            continue
    if server is None:
        return None
    threading.Thread(target=server.serve_forever, daemon=True).start()
    link = public_link(port, path.name)
    try:
        wait(link, port)
    finally:
        server.shutdown()
    return link


# ---------------------------------------------------------------- Facebook (Pages only)
def facebook_config():
    page = os.environ.get("FB_PAGE_ID") or os.environ.get("FACEBOOK_PAGE_ID")
    token = os.environ.get("FB_PAGE_TOKEN") or os.environ.get("FACEBOOK_PAGE_TOKEN")
    return {"page": page.strip(), "token": token.strip()} if page and token else None


def _url(base, *parts):
    return "/".join([base] + ([API] if API else []) + [p.strip("/") for p in parts])


def facebook_page_name(cfg):
    """The Page's name, which also proves the token works. Raises with Facebook's message if not."""
    q = urllib.parse.urlencode({"fields": "name", "access_token": cfg["token"]})
    try:
        with urllib.request.urlopen(_url(GRAPH, cfg["page"]) + "?" + q, timeout=20) as r:
            return json.load(r).get("name", cfg["page"])
    except urllib.error.HTTPError as e:
        raise RuntimeError(_fb_error(e))


def _fb_error(e):
    try:
        return json.loads(e.read().decode()).get("error", {}).get("message", str(e))
    except Exception:
        return str(e)


def upload_to_page(path, caption, cfg):
    """Upload a video to a Facebook Page. Returns the URL of the new post."""
    path = Path(path)
    boundary = uuid.uuid4().hex
    fields = {"access_token": cfg["token"], "description": caption, "title": "A reading from Veyra"}
    head = b"".join(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode()
                    for k, v in fields.items())
    head += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"source\"; filename=\"{path.name}\"\r\n"
             "Content-Type: video/mp4\r\n\r\n").encode()
    body = head + path.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(_url(GRAPH_VIDEO, cfg["page"], "videos"), data=body,
                                 headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            vid = json.load(r).get("id")
    except urllib.error.HTTPError as e:
        raise RuntimeError(_fb_error(e))
    return f"https://www.facebook.com/{cfg['page']}/videos/{vid}" if vid else "https://www.facebook.com/"


FACEBOOK_SETUP = """To let Veyra post straight to a Facebook Page:
  1. Go to developers.facebook.com, create an app (type: Business), and add the Pages product.
  2. In Graph API Explorer, pick your app and Page, grant pages_manage_posts, pages_read_engagement
     and publish_video, then generate a Page access token (exchange it for a long-lived one).
  3. In GitHub: Settings > Codespaces > Secrets, add FB_PAGE_ID (your Page's numeric id) and
     FB_PAGE_TOKEN, and give them access to this repo. Restart the codespace.
Facebook does not allow apps to post to personal profiles; for those, use the download link."""

PROFILE_STEPS = """To post it on your personal Facebook profile:
  1. Open the download link above on your phone or iPad and save the video
     (on iPhone/iPad it lands in Files > Downloads; tap it, then Share > Save Video to put it in Photos).
  2. Open the Facebook app > What's on your mind? > Photo/Video, and pick the video."""
