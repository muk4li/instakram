#!/usr/bin/env python3
"""Local-only web UI; no external dependencies, network calls, or persistence."""
import json
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
from parser_core import MAX_ARCHIVE_BYTES, process_bytes

HERE = Path(__file__).resolve().parent
INDEX = HERE / "web" / "index.html"
HOST, PORT = "127.0.0.1", 8765

class Handler(BaseHTTPRequestHandler):
    def send(self, code, data, mime):
        self.send_response(code)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy",
                         "default-src 'none'; script-src 'unsafe-inline' https://www.instagram.com; "
                         "style-src 'unsafe-inline'; img-src 'self' data: https://*.instagram.com https://*.cdninstagram.com; "
                         "frame-src https://www.instagram.com; connect-src 'self'; base-uri 'none'; form-action 'none'")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if urlsplit(self.path).path in ("/", "/index.html"):
            self.send(200, INDEX.read_bytes(), "text/html; charset=utf-8")
        else:
            self.send(404, b"Not found", "text/plain")

    def do_POST(self):
        if self.path != "/api/import":
            self.send(404, b"Not found", "text/plain")
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if size < 1 or size > MAX_ARCHIVE_BYTES:
                raise ValueError("Ungültige Dateigröße (maximal 200 MB).")
            filename = self.headers.get("X-Filename", "export.zip")
            if filename.lower().rsplit(".", 1)[-1] not in ("zip", "json"):
                raise ValueError("Nur ZIP oder JSON unterstützt.")
            payload = process_bytes(self.rfile.read(size), filename)
            self.send(200, json.dumps(payload, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")
        except (ValueError, OverflowError, OSError) as exc:
            self.send(400, json.dumps({"error": str(exc)}, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def log_message(self, format, *args):
        # Avoid logging imported content, file names or URLs.
        return

if __name__ == "__main__":
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"instakram läuft lokal: http://{HOST}:{PORT}")
    threading.Timer(0.8, lambda: webbrowser.open(f"http://{HOST}:{PORT}")).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
