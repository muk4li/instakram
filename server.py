#!/usr/bin/env python3
"""Local-only web UI, with SQLite persistence and optional opt-in Ollama."""
import json
import os
import urllib.request
import urllib.error
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlsplit
from parser_core import MAX_ARCHIVE_BYTES, process_bytes
from library_db import Library

HERE = Path(__file__).resolve().parent
DB = Library(Path(os.environ.get('INSTAKRAM_DB', str(HERE / 'data' / 'instakram.sqlite3'))))
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

    def _trusted_request(self):
        host = self.headers.get("Host", "")
        if host not in ("127.0.0.1:8765", "localhost:8765"):
            return False
        origin = self.headers.get("Origin")
        return not origin or origin in ("http://127.0.0.1:8765", "http://localhost:8765")

    def do_GET(self):
        if not self._trusted_request():
            self.send(403, b"Forbidden", "text/plain")
            return
        route = urlsplit(self.path).path
        if route == "/api/library":
            self.send(200, json.dumps({"items": DB.all_links(), "folders": DB.folders(), "rules": DB.rules(), "settings": DB.settings(), "textIndex": DB.text_index()}, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")
        elif route in ("/", "/index.html"):
            self.send(200, INDEX.read_bytes(), "text/html; charset=utf-8")
        else:
            self.send(404, b"Not found", "text/plain")

    def do_POST(self):
        if not self._trusted_request():
            self.send(403, b"Forbidden", "text/plain")
            return
        route = urlsplit(self.path).path
        if route not in ("/api/import", "/api/folder", "/api/folder/rename", "/api/folder/delete",
                         "/api/assign", "/api/inbox/review", "/api/inbox/undo", "/api/inbox/settings", "/api/rule", "/api/rule/delete", "/api/suggest/local", "/api/suggest/ai"):
            self.send(404, b"Not found", "text/plain")
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            max_size = MAX_ARCHIVE_BYTES if route == "/api/import" else 100_000
            if size < 1 or size > max_size:
                raise ValueError("Ungültige Dateigröße.")
            raw = self.rfile.read(size)
            if route == "/api/import":
                filename = self.headers.get("X-Filename", "export.zip")
                if filename.lower().rsplit(".", 1)[-1] not in ("zip", "json"):
                    raise ValueError("Nur ZIP oder JSON unterstützt.")
                imported = process_bytes(raw, filename)
                items = DB.import_rows(imported["items"])
                payload = {"items": items, "folders": DB.folders(), "rules": DB.rules(),
                           "jsonFiles": imported["jsonFiles"], "errors": imported["errors"]}
            else:
                args = json.loads(raw.decode("utf-8"))
                if not isinstance(args, dict):
                    raise ValueError("Ungültige Eingabe.")
                if route == "/api/folder":
                    DB.create_folder(args.get("name"), args.get("parent_id"))
                elif route == "/api/folder/rename":
                    DB.rename_folder(int(args["folder_id"]), args.get("name"))
                elif route == "/api/folder/delete":
                    DB.delete_folder(int(args["folder_id"]))
                elif route == "/api/assign":
                    DB.assign(args["link_id"], int(args["folder_id"]), bool(args.get("active", True)))
                elif route == "/api/inbox/review":
                    DB.review(str(args["link_id"]), args["folder_ids"], args.get("status","reviewed"))
                elif route == "/api/inbox/undo":
                    DB.undo_review(str(args["link_id"]))
                elif route == "/api/inbox/settings":
                    DB.set_settings(args.get("auto_enabled", False), args.get("threshold",95))
                elif route == "/api/rule":
                    DB.add_rule(int(args["folder_id"]), args.get("field"), args.get("pattern"))
                elif route == "/api/rule/delete":
                    DB.remove_rule(int(args["rule_id"]))
                elif route == "/api/suggest/local":
                    DB.local_suggestions()
                elif route == "/api/suggest/ai":
                    self.ai_suggest(args)
                payload = {"items": DB.all_links(), "folders": DB.folders(), "rules": DB.rules(), "settings": DB.settings()}
            self.send(200, json.dumps(payload, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")
        except (ValueError, KeyError, TypeError, OSError, OverflowError, json.JSONDecodeError) as exc:
            self.send(400, json.dumps({"error": str(exc)}, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def ai_suggest(self, args):
        """Opt-in local Ollama suggestion; sends only link URL and export metadata to loopback."""
        link_ids = args.get("link_ids")
        model = args.get("model", "llama3.2")
        if not isinstance(link_ids, list) or len(link_ids) > 20:
            raise ValueError("Bitte maximal 20 Links je Anfrage auswählen.")
        if not isinstance(model, str) or not model or len(model) > 60 or not all(c.isalnum() or c in "._:-" for c in model):
            raise ValueError("Ungültiger lokaler Modellname.")
        categories = {row["name"]:row["id"] for row in DB.folders() if row["path"].startswith("groups/")}
        allowed = list(categories)
        if not allowed:
            raise ValueError("Keine Gruppen vorhanden.")
        for link_id in link_ids:
            link = DB.get_link(str(link_id))
            prompt = (
                "Classify an Instagram link using ONLY its URL and metadata. Do not claim to know the unseen video. "
                "Return JSON only: {\"groups\":[\"exact group name\"],\"reason\":\"short rationale\"}. "
                "If there is insufficient evidence return {\"groups\":[],\"reason\":\"Unklar\"}. "
                "Choose at most 3 groups from: " + json.dumps(allowed,ensure_ascii=False) +
                "\nLink metadata: " + json.dumps({key:link[key] for key in ("url","sender","kind","source")},ensure_ascii=False)
            )
            request = urllib.request.Request("http://127.0.0.1:11434/api/generate",
                data=json.dumps({"model":model,"prompt":prompt,"stream":False,"format":"json",
                                 "options":{"temperature":0}}).encode("utf-8"),
                headers={"Content-Type":"application/json"},method="POST")
            try:
                with urllib.request.urlopen(request, timeout=45) as response:
                    if response.status != 200:
                        raise ValueError("Lokales Ollama-Modell antwortet nicht erfolgreich.")
                    result = json.loads(response.read(100_000).decode("utf-8"))
                proposal = json.loads(result.get("response","{}"))
            except (urllib.error.URLError,TimeoutError) as exc:
                raise ValueError("Ollama auf localhost:11434 nicht erreichbar. Bitte Ollama starten und das Modell laden.") from exc
            except (json.JSONDecodeError,UnicodeError) as exc:
                raise ValueError("Ungültige Antwort des KI-Modells.") from exc
            reason = str(proposal.get("reason","KI-Vorschlag"))[:220]
            choices = proposal.get("groups",[])
            if isinstance(choices,list):
                for name in choices[:3]:
                    if isinstance(name,str) and name in categories:
                        DB.suggest(link["id"], categories[name], reason, "ai")

    def log_message(self, format, *args):
        # Avoid logging imported content, file names or URLs.
        return

if __name__ == "__main__":
    server = HTTPServer((HOST, PORT), Handler)
    print(f"instakram läuft lokal: http://{HOST}:{PORT}")
    threading.Timer(0.8, lambda: webbrowser.open(f"http://{HOST}:{PORT}")).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
