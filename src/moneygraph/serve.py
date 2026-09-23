"""Review screen. Standard library only, so reproduction needs nothing beyond requirements.txt."""
from __future__ import annotations

import functools
import http.server
import socketserver
from pathlib import Path


def serve(out_dir: Path, port: int = 8000) -> None:
    root = Path(__file__).resolve().parents[2]
    handler = functools.partial(_Handler, directory=str(root), out_dir=out_dir)
    with socketserver.TCPServer(("", port), handler) as httpd:
        print(f"\nreview screen on http://localhost:{port}/web/  (ctrl-c to stop)")
        httpd.serve_forever()


class _Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, out_dir: Path, **kw):
        self.out_dir = out_dir
        super().__init__(*args, **kw)

    def log_message(self, *args):  # quieter console during a demo
        pass
