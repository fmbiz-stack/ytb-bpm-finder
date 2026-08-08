"""The web control panel: a small JSON API (below) plus static files served
from web/static/. This is the only interface end users touch - there is no
command-line mode for day-to-day use.
"""
import http.server
import json
import mimetypes
import os
import threading
import urllib.parse

from .. import config
from .. import consoles
from .. import proxy
from .. import settings
from ..state import read_state, write_state
from ..storage import list_emblems, group_dir, is_safe_group, set_emblem_label
from ..broadcast import select_emblem, clear_selection, read_selection
from ..shapes import render as emblem_render
from .netinfo import get_lan_ip, get_lan_ips

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

_MODE_TO_INTERNAL = {"off": "PASSTHROUGH", "capture": "CAPTURE", "inject": "INJECT"}
_MODE_TO_PUBLIC = {v: k for k, v in _MODE_TO_INTERNAL.items()}

# Set by make_server so /api/quit can stop the process. A packaged macOS .app
# has no terminal to press Ctrl+C in, so the panel needs its own way out.
_server = None


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # keep the terminal quiet - proxy.py already logs what matters

    # ---------- helpers ----------

    def _json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _bytes(self, data, content_type, code=200):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _read_json_body(self):
        length = int(self.headers.get("Content-Length", 0) or 0)
        if not length:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}

    def _slot_path(self, group, slot):
        """Path to one captured slot file, or None if the request named a
        group or slot we didn't generate. The panel is reachable from the LAN,
        so neither value is trusted enough to put straight into a path."""
        if not is_safe_group(group):
            return None
        try:
            slot = int(slot)
        except (TypeError, ValueError):
            return None
        return os.path.join(group_dir(group), f"slot_{slot}.bin")

    def _serve_static(self, rel_path):
        if rel_path == "":
            rel_path = "index.html"
        full = os.path.normpath(os.path.join(STATIC_DIR, rel_path))
        if os.path.commonpath([full, STATIC_DIR]) != STATIC_DIR or not os.path.isfile(full):
            self._json({"error": "not found"}, 404)
            return
        ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
        with open(full, "rb") as f:
            self._bytes(f.read(), ctype)

    # ---------- GET ----------

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path

        if path == "/api/status":
            # Polled every few seconds, so everything here has to be cheap -
            # the LAN address list isn't, and lives in /api/network-info.
            self._json({
                "mode": _MODE_TO_PUBLIC.get(read_state(), "off"),
                "selected": read_selection(),
                "console": settings.get_console(),
                "detected": proxy.get_detected(),
                "proxy_error": proxy.startup_error,
            })

        elif path == "/api/emblems":
            self._json(list_emblems())

        elif path == "/api/network-info":
            console = consoles.get(settings.get_console())
            self._json({
                "lan_ip": get_lan_ip(),
                "lan_ips": get_lan_ips(),
                "proxy_port": config.PROXY_PORT,
                "web_port": config.WEB_PORT,
                "console": console.as_dict(),
                "consoles": consoles.all_consoles(),
                "detected": proxy.get_detected(),
            })

        elif path == "/api/consoles":
            self._json({
                "selected": settings.get_console(),
                "consoles": consoles.all_consoles(),
            })

        elif path == "/LICENSE":
            license_path = os.path.join(config.RESOURCE_DIR, "LICENSE")
            if os.path.isfile(license_path):
                with open(license_path, "rb") as f:
                    self._bytes(f.read(), "text/plain; charset=utf-8")
            else:
                self._json({"error": "not found"}, 404)

        elif path.startswith("/api/render/"):
            bits = path.split("/")
            if len(bits) == 5:
                group = urllib.parse.unquote(bits[3])
                slot = bits[4].removesuffix(".png")
                slot_path = self._slot_path(group, slot)
                if slot_path and os.path.exists(slot_path):
                    try:
                        body = emblem_render.render_file_png_bytes(slot_path, size=220)
                        self._bytes(body, "image/png")
                    except Exception as e:
                        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="220" height="220">'
                               f'<rect width="100%" height="100%" fill="#1a1a1a"/>'
                               f'<text x="10" y="30" fill="#e55" font-size="12">render error</text>'
                               f'<text x="10" y="50" fill="#999" font-size="10">{e}</text></svg>')
                        self._bytes(svg.encode(), "image/svg+xml")
                    return
            self._json({"error": "not found"}, 404)

        elif path.startswith("/api/"):
            self._json({"error": "not found"}, 404)

        else:
            self._serve_static(path.lstrip("/"))

    # ---------- POST ----------

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        body = self._read_json_body()

        if path == "/api/mode":
            public_mode = body.get("mode")
            internal = _MODE_TO_INTERNAL.get(public_mode)
            if not internal:
                self._json({"ok": False, "error": "invalid mode"}, 400)
                return
            write_state(internal)
            self._json({"ok": True})

        elif path == "/api/select":
            group, slot = body.get("group"), body.get("slot")
            slot_path = self._slot_path(group, slot)
            if not slot_path or not os.path.exists(slot_path):
                self._json({"ok": False, "error": "not found"}, 404)
                return
            select_emblem(group, int(slot))
            self._json({"ok": True})

        elif path == "/api/deselect":
            clear_selection()
            self._json({"ok": True})

        elif path == "/api/console":
            resolved = settings.set_console(body.get("console"))
            self._json({"ok": True, "console": consoles.get(resolved).as_dict()})

        elif path == "/api/quit":
            # Reply before stopping, so the panel gets a clean response, and
            # stop from another thread since serve_forever is on this one.
            self._json({"ok": True})
            if _server is not None:
                threading.Thread(target=_server.shutdown, daemon=True).start()

        elif path.startswith("/api/emblems/") and path.endswith("/label"):
            bits = path.split("/")
            # /api/emblems/<group>/<slot>/label
            if len(bits) == 6:
                group = urllib.parse.unquote(bits[3])
                if self._slot_path(group, bits[4]):
                    set_emblem_label(group, int(bits[4]), (body.get("label") or "").strip())
                    self._json({"ok": True})
                    return
            self._json({"ok": False, "error": "bad request"}, 400)

        else:
            self._json({"error": "not found"}, 404)


def make_server(host=None, port=None):
    global _server
    host = host or config.WEB_HOST
    port = port or config.WEB_PORT
    _server = http.server.ThreadingHTTPServer((host, port), Handler)
    return _server
