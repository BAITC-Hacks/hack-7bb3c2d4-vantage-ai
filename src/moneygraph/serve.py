"""Review screen. Standard library only, so reproduction needs nothing beyond requirements.txt."""
from __future__ import annotations

import functools
import http.server
import posixpath
import socketserver
from pathlib import Path
from urllib.parse import unquote


def serve(out_dir: Path, port: int = 8000) -> None:
    """Serve the review screen on `port`, reading its data from `out_dir`."""
    web_dir = Path(__file__).resolve().parents[2] / "web"
    handler = functools.partial(_Handler, web_dir=web_dir, out_dir=Path(out_dir).resolve())
    with socketserver.TCPServer(("", port), handler) as httpd:
        print(f"\nreview screen on http://localhost:{port}/web/  (ctrl-c to stop)")
        httpd.serve_forever()


class _Handler(http.server.SimpleHTTPRequestHandler):
    """Serves web/ and out/ and nothing else.

    Rooting the server at the repository would also publish data/, run.py and every
    document beside them, which is more than a review screen needs to expose. The page
    asks for ../out/graph.json from /web/, so the two prefixes below are the whole of
    what it fetches, and out/ is mounted from the directory this run actually wrote to
    rather than from a fixed path next to the page.
    """

    def __init__(self, *args, web_dir: Path, out_dir: Path, **kw):
        self._roots = {"web": web_dir, "out": out_dir}
        super().__init__(*args, **kw)

    def end_headers(self):
        # The screen is edited and reloaded during a demo; a cached stylesheet would show
        # the previous version. Nothing served here is large enough to need a cache.
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def translate_path(self, path: str) -> str:
        parts = [p for p in unquote(path.split("?", 1)[0].split("#", 1)[0]).split("/") if p]
        # posixpath.normpath collapses any .. before the prefix is checked, so a request
        # cannot climb out of the mount it was matched against.
        if not parts or parts[0] not in self._roots:
            return ""
        root = self._roots[parts[0]]
        rel = posixpath.normpath("/".join(parts[1:]) or ".")
        if rel.startswith("..") or rel.startswith("/"):
            return ""
        target = (root / rel).resolve() if rel != "." else root
        try:
            target.relative_to(root)
        except ValueError:
            return ""
        return str(target) + ("/" if path.endswith("/") and rel != "." else "")

    def send_head(self):
        path = self.path.split("?", 1)[0].split("#", 1)[0]
        if path in ("/", "/web", "/index.html"):
            self.send_response(302)
            self.send_header("Location", "/web/")
            self.end_headers()
            return None
        if not self.translate_path(path):
            self.send_error(404, "Not Found")
            return None
        return super().send_head()

    def log_message(self, *args):  # quieter console during a demo
        pass
