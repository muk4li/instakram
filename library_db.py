"""Local SQLite library: persistent links, nested folders, assignments, rules and suggestions."""
import hashlib
import json
import re
import sqlite3
from pathlib import Path

DEFAULT_CATEGORIES = (
    "Tech & KI", "Programmieren", "Gaming", "Memes & Humor", "Musik",
    "Wissen & Bildung", "Favoriten", "Fitness & Sport", "Design & Kunst",
    "Lifestyle", "Inspiration", "Rezepte", "Anime", "Filme und Serien"
)
FIELDS = ("url", "area", "chat", "sender", "date", "kind", "source")
RULE_FIELDS = ("url", "chat", "sender", "kind", "area", "source")
MAX_NAME = 90

class Library:
    def __init__(self, database):
        self.path = Path(database)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.path), timeout=15, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.executescript("""
        CREATE TABLE IF NOT EXISTS folders (
            id INTEGER PRIMARY KEY, name TEXT NOT NULL,
            parent_id INTEGER REFERENCES folders(id) ON DELETE CASCADE,
            path TEXT NOT NULL UNIQUE
        );
        CREATE TABLE IF NOT EXISTS links (
            id TEXT PRIMARY KEY, url TEXT NOT NULL UNIQUE,
            area TEXT NOT NULL DEFAULT 'other', chat TEXT NOT NULL DEFAULT '',
            sender TEXT NOT NULL DEFAULT '', date TEXT NOT NULL DEFAULT '',
            kind TEXT NOT NULL DEFAULT 'external', source TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS occurrences (
            link_id TEXT NOT NULL REFERENCES links(id) ON DELETE CASCADE,
            area TEXT NOT NULL, chat TEXT NOT NULL, sender TEXT NOT NULL,
            date TEXT NOT NULL, kind TEXT NOT NULL, source TEXT NOT NULL,
            PRIMARY KEY(link_id,area,chat,sender,date,source)
        );
        CREATE TABLE IF NOT EXISTS assignments (
            link_id TEXT NOT NULL REFERENCES links(id) ON DELETE CASCADE,
            folder_id INTEGER NOT NULL REFERENCES folders(id) ON DELETE CASCADE,
            origin TEXT NOT NULL CHECK(origin IN ('manual','rule','ai')),
            PRIMARY KEY (link_id,folder_id)
        );
        CREATE TABLE IF NOT EXISTS rules (
            id INTEGER PRIMARY KEY, folder_id INTEGER NOT NULL REFERENCES folders(id) ON DELETE CASCADE,
            field TEXT NOT NULL, pattern TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS suggestions (
            link_id TEXT NOT NULL REFERENCES links(id) ON DELETE CASCADE,
            folder_id INTEGER NOT NULL REFERENCES folders(id) ON DELETE CASCADE,
            reason TEXT NOT NULL, method TEXT NOT NULL DEFAULT 'local',
            PRIMARY KEY(link_id,folder_id)
        );
        """)
        with self.conn:
            root = self._create_folder("groups")
            for category in DEFAULT_CATEGORIES:
                self._create_folder(category, root)

    @staticmethod
    def _valid_name(name):
        if not isinstance(name, str):
            raise ValueError("Ordnername muss Text sein.")
        name = name.strip()
        if not name or len(name) > MAX_NAME or name in (".", "..") or "/" in name or "\\" in name:
            raise ValueError("Ungültiger Ordnername (1–90 Zeichen, kein / oder \\).")
        return name

    def _folder_row(self, folder_id):
        row = self.conn.execute("SELECT * FROM folders WHERE id=?", (folder_id,)).fetchone()
        if row is None:
            raise ValueError("Ordner existiert nicht.")
        return row

    def _create_folder(self, name, parent_id=None):
        name = self._valid_name(name)
        path = (self._folder_row(parent_id)["path"] + "/" if parent_id is not None else "") + name
        existing = self.conn.execute("SELECT id FROM folders WHERE path=?", (path,)).fetchone()
        if existing:
            return existing["id"]
        cur = self.conn.execute("INSERT INTO folders(name,parent_id,path) VALUES(?,?,?)", (name,parent_id,path))
        return cur.lastrowid

    def create_folder(self, name, parent_id=None):
        with self.conn:
            folder_id = self._create_folder(name, parent_id)
        return folder_id

    def rename_folder(self, folder_id, name):
        name = self._valid_name(name)
        current = self._folder_row(folder_id)
        parent = self._folder_row(current["parent_id"])["path"] if current["parent_id"] is not None else ""
        new_path = parent + "/" + name if parent else name
        old_path = current["path"]
        if new_path == old_path:
            return
        if self.conn.execute("SELECT 1 FROM folders WHERE path=? AND id!=?", (new_path,folder_id)).fetchone():
            raise ValueError("Ordnername bereits vorhanden.")
        descendants = self.conn.execute("SELECT id,path FROM folders WHERE path=? OR path LIKE ? ORDER BY LENGTH(path)", (old_path,old_path + "/%")).fetchall()
        with self.conn:
            for row in descendants:
                path = new_path + row["path"][len(old_path):]
                self.conn.execute("UPDATE folders SET path=?,name=CASE WHEN id=? THEN ? ELSE name END WHERE id=?", (path,folder_id,name,row["id"]))

    def delete_folder(self, folder_id):
        self._folder_row(folder_id)
        with self.conn:
            self.conn.execute("DELETE FROM folders WHERE id=?", (folder_id,))

    def folders(self):
        return [dict(r) for r in self.conn.execute("SELECT * FROM folders ORDER BY path COLLATE NOCASE")]

    def _link_id(self, url):
        return hashlib.sha256(url.encode("utf-8")).hexdigest()[:24]

    def import_rows(self, rows):
        if not isinstance(rows, list):
            raise ValueError("Ungültiger Import.")
        with self.conn:
            for row in rows:
                if not isinstance(row, dict) or not isinstance(row.get("url"), str):
                    continue
                clean = {k: str(row.get(k) or "") for k in FIELDS}
                uid = self._link_id(clean["url"])
                self.conn.execute("INSERT OR IGNORE INTO links(id,url,area,chat,sender,date,kind,source) VALUES(?,?,?,?,?,?,?,?)", (uid,*(clean[k] for k in FIELDS)))
                self.conn.execute("INSERT OR IGNORE INTO occurrences(link_id,area,chat,sender,date,kind,source) VALUES(?,?,?,?,?,?,?)",
                                  (uid,*(clean[k] for k in FIELDS if k != "url")))
            self._run_rules()
        return self.all_links()

    def all_links(self):
        links = []
        for r in self.conn.execute("SELECT * FROM links ORDER BY date DESC, id"):
            link = dict(r)
            link["occurrences"] = [dict(o) for o in self.conn.execute(
                "SELECT area,chat,sender,date,kind,source FROM occurrences WHERE link_id=? ORDER BY date DESC",
                (link["id"],))]
            link["areas"] = sorted({o["area"] for o in link["occurrences"]})
            link["chats"] = sorted({o["chat"] for o in link["occurrences"] if o["chat"]})
            link["folders"] = [v[0] for v in self.conn.execute("SELECT folder_id FROM assignments WHERE link_id=? ORDER BY folder_id",(link["id"],))]
            link["suggestions"] = [dict(s) for s in self.conn.execute("SELECT folder_id,reason,method FROM suggestions WHERE link_id=? ORDER BY folder_id",(link["id"],))]
            links.append(link)
        return links

    def assign(self, link_id, folder_id, active=True, origin="manual"):
        if not self.conn.execute("SELECT 1 FROM links WHERE id=?", (link_id,)).fetchone():
            raise ValueError("Link nicht gefunden.")
        self._folder_row(folder_id)
        with self.conn:
            if active:
                self.conn.execute("INSERT INTO assignments(link_id,folder_id,origin) VALUES(?,?,?) ON CONFLICT(link_id,folder_id) DO UPDATE SET origin=excluded.origin", (link_id,folder_id,origin))
            else:
                self.conn.execute("DELETE FROM assignments WHERE link_id=? AND folder_id=?", (link_id,folder_id))
            self.conn.execute("DELETE FROM suggestions WHERE link_id=? AND folder_id=?", (link_id,folder_id))

    def rules(self):
        return [dict(r) for r in self.conn.execute("SELECT * FROM rules ORDER BY id DESC")]

    def add_rule(self, folder_id, field, pattern):
        self._folder_row(folder_id)
        if field not in RULE_FIELDS or not isinstance(pattern,str) or not (1 <= len(pattern.strip()) <= 120):
            raise ValueError("Bitte Feld und Suchbegriff (max. 120 Zeichen) angeben.")
        with self.conn:
            cur = self.conn.execute("INSERT INTO rules(folder_id,field,pattern) VALUES(?,?,?)",(folder_id,field,pattern.strip()))
            self._run_rules()
        return cur.lastrowid

    def remove_rule(self, rule_id):
        with self.conn:
            self.conn.execute("DELETE FROM rules WHERE id=?", (rule_id,))

    def _run_rules(self):
        rules = self.rules()
        for rule in rules:
            if not rule["enabled"]:
                continue
            field = rule["field"]
            needle = rule["pattern"].casefold()
            for link in self.conn.execute("SELECT id FROM links"):
                # Check all occurrences so the rule works even when a URL appears in multiple chats.
                matches = self.conn.execute(f"SELECT {field} FROM occurrences WHERE link_id=?", (link["id"],)).fetchall() if field != "url" else self.conn.execute("SELECT url FROM links WHERE id=?", (link["id"],)).fetchall()
                if any(needle in (str(v[0] or "")).casefold() for v in matches):
                    self.conn.execute("INSERT OR IGNORE INTO assignments(link_id,folder_id,origin) VALUES(?,?,'rule')",(link["id"],rule["folder_id"]))

    def local_suggestions(self):
        """Keyword suggestions: deterministic, never mislabeled as AI."""
        keyword_map = {
            "Tech & KI": ("ai","openai","gpt","llm","robot","tech","machinelearning","artificialintelligence"),
            "Programmieren": ("python","javascript","github","coding","programming","developer","software"),
            "Gaming": ("gaming","minecraft","valorant","fortnite","gameplay","steam"),
            "Memes & Humor": ("meme","funny","humor","comedy","lol"),
            "Musik": ("music","song","spotify","dj","guitar"),
            "Wissen & Bildung": ("science","history","learn","wissen","education"),
            "Fitness & Sport": ("fitness","workout","gym","running","sport"),
            "Design & Kunst": ("design","artwork","drawing","illustration","kunst"),
            "Lifestyle": ("lifestyle","fashion","style","outfit"),
            "Inspiration": ("motivation","inspiration","mindset"),
            "Rezepte": ("recipe","rezept","cooking","food"),
            "Anime": ("anime","manga","cosplay"),
            "Filme und Serien": ("movie","film","netflix","series","cinema")
        }
        folder_ids = {r["name"]:r["id"] for r in self.conn.execute("SELECT id,name FROM folders WHERE path LIKE 'groups/%'")}
        count = 0
        with self.conn:
            for link in self.conn.execute("SELECT * FROM links"):
                hay = " ".join(str(link[k] or "") for k in ("url","sender","source")).casefold()
                for folder, keywords in keyword_map.items():
                    if folder not in folder_ids:
                        continue
                    matched = next((term for term in keywords if term in hay),None)
                    if matched:
                        fid = folder_ids[folder]
                        if not self.conn.execute("SELECT 1 FROM assignments WHERE link_id=? AND folder_id=?", (link["id"],fid)).fetchone():
                            self.conn.execute("INSERT OR REPLACE INTO suggestions(link_id,folder_id,reason,method) VALUES(?,?,?,'local')",(link["id"],fid,"Schlüsselwort: "+matched))
                            count += 1
        return count

    def suggest(self, link_id, folder_id, reason, method="ai"):
        self._folder_row(folder_id)
        if not self.conn.execute("SELECT 1 FROM links WHERE id=?", (link_id,)).fetchone():
            raise ValueError("Link nicht gefunden.")
        with self.conn:
            self.conn.execute("INSERT OR REPLACE INTO suggestions(link_id,folder_id,reason,method) VALUES(?,?,?,?)",(link_id,folder_id,str(reason)[:250],method))

    def get_link(self, link_id):
        row = self.conn.execute("SELECT * FROM links WHERE id=?",(link_id,)).fetchone()
        if not row:
            raise ValueError("Link nicht gefunden.")
        return dict(row)
