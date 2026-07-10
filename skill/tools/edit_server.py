import json
import mimetypes
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from edit_log import append_edit, append_status, compute_status_details, read_all_events
from overlay import inject_overlay


def make_handler(deck_root, log_path):
    deck_root = Path(deck_root).resolve()
    log_path = Path(log_path)

    class EditRequestHandler(BaseHTTPRequestHandler):
        # Bound socket read/write waits (e.g. a client that sends headers
        # but never finishes the body) so a stuck connection can't tie up
        # a handler thread forever. See socketserver.StreamRequestHandler.setup().
        timeout = 10

        def do_GET(self):
            path = urlparse(self.path).path
            if path == "/__status__":
                self._handle_status()
            else:
                self._handle_static(path)

        def do_POST(self):
            path = urlparse(self.path).path
            if path == "/__edit__":
                self._handle_edit()
            elif path.startswith("/__status__/"):
                self._handle_status_update(path[len("/__status__/"):])
            else:
                self.send_error(404)

        def _resolve_within_deck_root(self, rel_path):
            candidate = (deck_root / rel_path).resolve()
            try:
                candidate.relative_to(deck_root)
            except ValueError:
                return None
            return candidate

        def _handle_static(self, path):
            rel_path = path.lstrip("/") or "index.html"
            file_path = self._resolve_within_deck_root(rel_path)
            if file_path is None:
                self.send_error(403)
                return
            if not file_path.is_file():
                self.send_error(404)
                return
            if file_path.suffix == ".html":
                canonical_rel_path = str(file_path.relative_to(deck_root))
                html = file_path.read_text(encoding="utf-8")
                html = inject_overlay(html, canonical_rel_path)
                self._respond_bytes(html.encode("utf-8"), "text/html; charset=utf-8")
            else:
                content_type = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
                self._respond_bytes(file_path.read_bytes(), content_type)

        def _handle_edit(self):
            try:
                payload = self._read_json_body()
            except (json.JSONDecodeError, ValueError):
                self._respond_error(400, "invalid request body")
                return
            file_value = payload.get("file")
            if not isinstance(file_value, str) or not file_value or (
                self._resolve_within_deck_root(file_value) is None
            ):
                self._respond_error(400, "file must be a path within the deck root")
                return
            edit_id = append_edit(
                log_path,
                file=file_value,
                type_=payload.get("type"),
                selector=payload.get("selector"),
                before=payload.get("before"),
                after=payload.get("after"),
                note=payload.get("note"),
            )
            self._respond_json({"id": edit_id})

        def _handle_status(self):
            details = compute_status_details(read_all_events(log_path))
            self._respond_json(details)

        def _handle_status_update(self, edit_id):
            try:
                payload = self._read_json_body()
            except (json.JSONDecodeError, ValueError):
                self._respond_error(400, "invalid request body")
                return
            known_ids = compute_status_details(read_all_events(log_path))
            if edit_id not in known_ids:
                self._respond_error(404, "unknown edit id")
                return
            try:
                append_status(log_path, edit_id, payload.get("status"))
            except ValueError as e:
                self._respond_error(400, str(e))
                return
            self._respond_json({"ok": True})

        def _read_json_body(self):
            length = int(self.headers.get("Content-Length", 0))
            if length < 0:
                raise ValueError(f"invalid Content-Length: {length}")
            raw = self.rfile.read(length) if length else b"{}"
            return json.loads(raw or b"{}")

        def _respond_json(self, data):
            self._respond_bytes(json.dumps(data).encode("utf-8"), "application/json")

        def _respond_error(self, status_code, message):
            self.send_response(status_code)
            body = json.dumps({"error": message}).encode("utf-8")
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _respond_bytes(self, body, content_type):
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format, *args):
            pass  # keep server/test output quiet

    return EditRequestHandler


def make_server(deck_root, port, log_path=None):
    deck_root = Path(deck_root)
    if log_path is None:
        log_path = deck_root / ".slide-edits" / "edits.jsonl"
    handler_cls = make_handler(deck_root, log_path)
    return ThreadingHTTPServer(("127.0.0.1", port), handler_cls)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: edit_server.py <deck_root> [port]")
        sys.exit(1)
    deck_root_arg = sys.argv[1]
    port_arg = int(sys.argv[2]) if len(sys.argv) > 2 else 8791
    server = make_server(deck_root_arg, port_arg)
    log_path_display = Path(deck_root_arg) / ".slide-edits" / "edits.jsonl"
    print(f"Serving {deck_root_arg} at http://127.0.0.1:{port_arg}/  (log: {log_path_display})")
    server.serve_forever()
