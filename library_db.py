"""Local SQLite library: persistent links, nested folders, assignments, rules and suggestions."""
import hashlib
import json
import re
import sqlite3
from collections import defaultdict
from text_analysis import hashtags, keywords
from urllib.parse import urlsplit
from pathlib import Path

DEFAULT_CATEGORIES = (
    "Tech & KI", "Programmieren", "Gaming", "Memes & Humor", "Musik",
    "Wissen & Bildung", "Favoriten", "Fitness & Sport", "Design & Kunst",
    "Lifestyle", "Inspiration", "Rezepte", "Anime", "Filme und Serien"
)
FIELDS = ("url", "area", "chat", "sender", "date", "kind", "source")
RULE_FIELDS = ("url", "chat", "sender", "kind", "area", "source", "caption")
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
        CREATE TABLE IF NOT EXISTS creators (
            link_id TEXT NOT NULL REFERENCES links(id) ON DELETE CASCADE,
            creator TEXT NOT NULL,
            source TEXT NOT NULL,
            PRIMARY KEY(link_id, creator, source)
        );
        CREATE TABLE IF NOT EXISTS captions (
            link_id TEXT NOT NULL REFERENCES links(id) ON DELETE CASCADE,
            caption TEXT NOT NULL,
            source TEXT NOT NULL,
            PRIMARY KEY(link_id, caption, source)
        );
        CREATE TABLE IF NOT EXISTS reviews (
            link_id TEXT PRIMARY KEY REFERENCES links(id) ON DELETE CASCADE,
            status TEXT NOT NULL CHECK(status IN ('pending','reviewed','skipped')) DEFAULT 'pending',
            reviewed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS feedback (
            link_id TEXT NOT NULL REFERENCES links(id) ON DELETE CASCADE,
            folder_id INTEGER NOT NULL REFERENCES folders(id) ON DELETE CASCADE,
            accepted INTEGER NOT NULL CHECK(accepted IN (0,1)),
            PRIMARY KEY(link_id, folder_id)
        );
        CREATE TABLE IF NOT EXISTS preferences (
            key TEXT PRIMARY KEY, value TEXT NOT NULL
        );
        INSERT OR IGNORE INTO preferences(key,value) VALUES ('auto_enabled','1');
        INSERT OR IGNORE INTO preferences(key,value) VALUES ('threshold','95');
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
                creator = row.get("creator")
                if isinstance(creator, str) and creator.strip():
                    self.conn.execute("INSERT OR IGNORE INTO creators(link_id,creator,source) VALUES(?,?,?)",
                                      (uid,creator.strip()[:100],clean["source"]))
                caption = row.get("caption")
                if isinstance(caption, str) and caption.strip():
                    self.conn.execute("INSERT OR IGNORE INTO captions(link_id,caption,source) VALUES(?,?,?)",
                                      (uid,caption[:5000],clean["source"]))
            self._run_rules()
            self.refresh_smart_suggestions()
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
            review = self.conn.execute("SELECT status FROM reviews WHERE link_id=?", (link["id"],)).fetchone()
            link["review_status"] = review["status"] if review else "pending"
            link["folders"] = [v[0] for v in self.conn.execute("SELECT folder_id FROM assignments WHERE link_id=? ORDER BY folder_id",(link["id"],))]
            captions = [v[0] for v in self.conn.execute("SELECT caption FROM captions WHERE link_id=? ORDER BY rowid",(link["id"],))]
            link["creators"] = sorted({r[0] for r in self.conn.execute(
                "SELECT creator FROM creators WHERE link_id=?", (link["id"],))})
            link["captions"] = captions
            link["hashtags"] = sorted(set().union(*(set(hashtags(c)) for c in captions))) if captions else []
            link["keywords"] = sorted(set().union(*(set(keywords(c)) for c in captions))) if captions else []
            link["suggestions"] = [dict(s) for s in self.conn.execute("SELECT folder_id,reason,method FROM suggestions WHERE link_id=? ORDER BY folder_id",(link["id"],))]
            links.append(link)
        return links

    def text_index(self):
        """Document-frequency: each unique link contributes at most one count per term."""
        hashtag_links = defaultdict(set)
        keyword_links = defaultdict(set)
        for row in self.conn.execute("SELECT link_id,caption FROM captions"):
            for tag in hashtags(row["caption"]):
                hashtag_links[tag].add(row["link_id"])
            for word in keywords(row["caption"]):
                keyword_links[word].add(row["link_id"])
        def pack(values):
            return [{"term":term,"count":len(ids)} for term,ids in sorted(
                values.items(),key=lambda x:(-len(x[1]),x[0]))]
        return {"hashtags":pack(hashtag_links),"keywords":pack(keyword_links),
                "links_with_captions":len({r[0] for r in self.conn.execute("SELECT link_id FROM captions")})}

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
                matches = (self.conn.execute("SELECT caption FROM captions WHERE link_id=?", (link["id"],)).fetchall()
                           if field == "caption" else
                           self.conn.execute("SELECT url FROM links WHERE id=?", (link["id"],)).fetchall()
                           if field == "url" else
                           self.conn.execute(f"SELECT {field} FROM occurrences WHERE link_id=?", (link["id"],)).fetchall())
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

    def settings(self):
        return {"auto_enabled": self.conn.execute("SELECT value FROM preferences WHERE key='auto_enabled'").fetchone()[0] == "1",
                "threshold": int(self.conn.execute("SELECT value FROM preferences WHERE key='threshold'").fetchone()[0])}

    def set_settings(self, auto_enabled, threshold):
        threshold = int(threshold)
        if not 80 <= threshold <= 100:
            raise ValueError("Schwelle muss zwischen 80 und 100 liegen.")
        with self.conn:
            self.conn.execute("UPDATE preferences SET value=? WHERE key='auto_enabled'",("1" if auto_enabled else "0",))
            self.conn.execute("UPDATE preferences SET value=? WHERE key='threshold'",(str(threshold),))
            self.refresh_smart_suggestions()

    @staticmethod
    def _identity(url):
        """Learn only from a real URL account handle or external hostname.
        Chat sender is NOT the creator of the shared Instagram reel.
        """
        parsed = urlsplit(url)
        host = (parsed.hostname or "").lower()
        path = [p for p in parsed.path.split("/") if p]
        if host in ("www.instagram.com","instagram.com","m.instagram.com","instagr.am"):
            if len(path) >= 1 and path[0].lower() not in (
                "reel","reels","p","stories","tv","explore","accounts","direct","share"):
                return "creator:" + path[0].casefold()
            return None
        # Broad publishing platforms do not identify the creator; treating their
        # domain as a topic signal would cause many false classifications.
        broad = ("youtube.com","youtu.be","tiktok.com","facebook.com",
                 "twitter.com","x.com","reddit.com","pinterest.com",
                 "threads.net","soundcloud.com","spotify.com")
        clean_host = host[4:] if host.startswith("www.") else host
        if clean_host and clean_host != "localhost" and not any(
            clean_host == site or clean_host.endswith("." + site) for site in broad
        ):
            return "domain:" + clean_host
        return None

    def _learning_evidence(self, link_id, folder_id):
        target = self.conn.execute("SELECT url FROM links WHERE id=?", (link_id,)).fetchone()
        identity = self._identity(target["url"]) if target else None
        if not identity:
            return None
        positive, negative = 0, 0
        entries = self.conn.execute("""
            SELECT l.url, f.accepted FROM feedback f JOIN links l ON l.id=f.link_id
            WHERE f.folder_id=? AND l.id!=?
        """,(folder_id,link_id))
        for row in entries:
            if self._identity(row["url"]) == identity:
                if row["accepted"]:
                    positive += 1
                else:
                    negative += 1
        # This number is a heuristic evidence score, NOT a calibrated probability.
        if positive >= 4 and negative == 0:
            return (95, f"{positive} bestätigte Links von {identity}, keine Ablehnung")
        if positive >= 2 and negative == 0:
            return (80, f"{positive} bestätigte Links von {identity}")
        return None

    def refresh_smart_suggestions(self):
        """Recompute human-reviewable suggestions from grouped feedback evidence."""
        settings = self.settings()
        rows = list(self.conn.execute("SELECT id,url FROM links"))
        feedback = list(self.conn.execute("""
            SELECT f.link_id, f.folder_id, f.accepted, l.url
            FROM feedback f JOIN links l ON l.id=f.link_id
        """))
        counts = {}
        for f in feedback:
            identity = self._identity(f["url"])
            if identity:
                key = (identity, f["folder_id"])
                item = counts.setdefault(key, {"yes":set(),"no":set()})
                item["yes" if f["accepted"] else "no"].add(f["link_id"])
        assigned = {(r["link_id"],r["folder_id"]) for r in self.conn.execute("SELECT link_id,folder_id FROM assignments")}
        rejected = {(r["link_id"],r["folder_id"]) for r in feedback}
        resolved = {r["link_id"] for r in self.conn.execute("SELECT link_id FROM reviews WHERE status IN ('reviewed','skipped')")}
        folders = [r["id"] for r in self.conn.execute("SELECT id FROM folders WHERE path LIKE 'groups/%'")]
        self.conn.execute("DELETE FROM suggestions WHERE method='learned'")
        for row in rows:
            uid = row["id"]
            identity = self._identity(row["url"])
            if uid in resolved or not identity:
                continue
            for fid in folders:
                if (uid,fid) in assigned or (uid,fid) in rejected:
                    continue
                evidence = counts.get((identity,fid))
                if not evidence:
                    continue
                yes = len(evidence["yes"] - {uid})
                no = len(evidence["no"] - {uid})
                if no or yes < 2:
                    continue
                score = 95 if yes >= 4 else 80
                reason = f"{yes} bestätigte Zuordnungen für {identity} (heuristisches Signal, keine Wahrscheinlichkeit)"
                if settings["auto_enabled"] and score >= settings["threshold"]:
                    self.conn.execute("INSERT OR IGNORE INTO assignments(link_id,folder_id,origin) VALUES(?,?,'rule')",(uid,fid))
                    assigned.add((uid,fid))
                else:
                    self.conn.execute("INSERT OR IGNORE INTO suggestions(link_id,folder_id,reason,method) VALUES(?,?,?,'learned')",(uid,fid,f"Signal {score}/100: {reason}"))

    def review(self, link_id, folder_ids, status="reviewed"):
        self.get_link(link_id)
        if status not in ("reviewed","skipped","pending"):
            raise ValueError("Ungültiger Status.")
        if not isinstance(folder_ids,list) or len(folder_ids) > 100:
            raise ValueError("Ungültige Ordnerliste.")
        chosen = {int(i) for i in folder_ids}
        for fid in chosen:
            self._folder_row(fid)
        with self.conn:
            if status == "skipped":
                self.conn.execute("INSERT INTO reviews(link_id,status) VALUES(?,'skipped') ON CONFLICT(link_id) DO UPDATE SET status='skipped', reviewed_at=CURRENT_TIMESTAMP",(link_id,))
                return
            current = {r[0] for r in self.conn.execute("SELECT folder_id FROM assignments WHERE link_id=?",(link_id,))}
            suggested = {r[0] for r in self.conn.execute("SELECT folder_id FROM suggestions WHERE link_id=?",(link_id,))}
            # Explicit review trains from what was displayed and from prior assignments.
            for fid in current | suggested | chosen:
                self.conn.execute("INSERT INTO feedback(link_id,folder_id,accepted) VALUES(?,?,?) ON CONFLICT(link_id,folder_id) DO UPDATE SET accepted=excluded.accepted",
                                  (link_id,fid,1 if fid in chosen else 0))
            self.conn.execute("DELETE FROM assignments WHERE link_id=?",(link_id,))
            for fid in chosen:
                self.conn.execute("INSERT INTO assignments(link_id,folder_id,origin) VALUES(?,?,'manual')",(link_id,fid))
            self.conn.execute("DELETE FROM suggestions WHERE link_id=?",(link_id,))
            self.conn.execute("INSERT INTO reviews(link_id,status) VALUES(?,?) ON CONFLICT(link_id) DO UPDATE SET status=excluded.status, reviewed_at=CURRENT_TIMESTAMP",(link_id,status))
            self.refresh_smart_suggestions()

    def undo_review(self, link_id):
        self.get_link(link_id)
        with self.conn:
            self.conn.execute("DELETE FROM reviews WHERE link_id=?",(link_id,))
            self.conn.execute("DELETE FROM feedback WHERE link_id=?",(link_id,))
            self.refresh_smart_suggestions()

    def get_link(self, link_id):
        row = self.conn.execute("SELECT * FROM links WHERE id=?",(link_id,)).fetchone()
        if not row:
            raise ValueError("Link nicht gefunden.")
        return dict(row)
