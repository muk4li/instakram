"""Instagram exports escape UTF-8 bytes as Latin-1 code points; synthetic data only."""
import json
import tempfile
import unittest
from pathlib import Path

from library_db import Library
from parser_core import fix_mojibake, fix_document, process_bytes, url_normalize
from text_analysis import hashtags


def broken(text):
    """Simulate how Instagram exports text ("Jürgen" -> "JÃ¼rgen")."""
    return text.encode("utf-8").decode("latin-1")


def export(messages):
    # ensure_ascii reproduces the Ã¼ escapes found in real exports.
    return json.dumps({"messages": messages}, ensure_ascii=True).encode("ascii")


CHAT_FILE = "your_instagram_activity/messages/inbox/kuechenchat_1/message_1.json"


class FixMojibakeTests(unittest.TestCase):
    def test_repro_from_issue(self):
        raw = (b'{"messages":[{"sender_name":"J\\u00c3\\u00bcrgen","timestamp_ms":1700000000000,'
               b'"share":{"link":"https://www.instagram.com/reel/ABC/"}}]}')
        item = process_bytes(raw, "your_instagram_activity/messages/inbox/x/message_1.json")["items"][0]
        self.assertEqual("Jürgen", item["sender"])
        self.assertEqual("https://www.instagram.com/reel/ABC", item["url"])

    def test_umlauts_emojis_and_mixed_text(self):
        for text in ("Jürgen Größe Äpfel ß", "Party 🎉🔥", "Café crème – „Zitat“ 😀 #küche end"):
            self.assertEqual(text, fix_mojibake(broken(text)))

    def test_correct_text_stays_unchanged(self):
        for text in ("Café", "Jürgen", "naïve façade", "🎉 emoji", "plain ascii", "", "Ã alone"):
            self.assertEqual(text, fix_mojibake(text))

    def test_repair_is_idempotent(self):
        once = fix_mojibake(broken("Grüße 😀"))
        self.assertEqual(once, fix_mojibake(once))

    def test_document_keys_and_values(self):
        doc = {broken("schlüssel"): [broken("wert ü"), 3, None, {"x": broken("é")}]}
        self.assertEqual({"schlüssel": ["wert ü", 3, None, {"x": "é"}]}, fix_document(doc))

    def test_hashtag_and_caption_repaired(self):
        doc = {"posts": [{"caption": broken("Lecker #küche 🍝 Rezept"),
                          "link": "https://www.instagram.com/p/AbC_12-x/?igsh=a1B2"}]}
        item = process_bytes(json.dumps(doc).encode("ascii"), "media/posts_1.json")["items"][0]
        self.assertEqual("Lecker #küche 🍝 Rezept", item["caption"])
        self.assertEqual(["küche"], hashtags(item["caption"]))
        # ASCII URLs (incl. percent-encoding) are left exactly as before the repair.
        for url in ("https://www.instagram.com/p/AbC_12-x/?igsh=a1B2", "https://example.org/caf%C3%A9?q=%E2%9C%93"):
            self.assertEqual(url, fix_mojibake(url))
        self.assertEqual(url_normalize("https://www.instagram.com/p/AbC_12-x/?igsh=a1B2"), item["url"])

    def test_creator_repaired(self):
        doc = {"saved": [{"creator_username": broken("bäcker_ö"),
                          "link": "https://www.instagram.com/reel/XYZ/"}]}
        item = process_bytes(json.dumps(doc).encode("ascii"), "saved_posts.json")["items"][0]
        self.assertEqual("bäcker_ö", item["creator"])


class LegacyDatabaseRepairTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = str(Path(tmp.name) / "legacy.sqlite3")

    def legacy_db(self, rows):
        """Store rows exactly as an older version (without repair) would have."""
        db = Library(self.path)
        db.import_rows(rows)
        db.conn.execute("DELETE FROM preferences WHERE key='mojibake_repaired'")
        db.conn.commit()
        return db

    def test_repair_merges_and_keeps_user_data(self):
        reel = "https://www.instagram.com/reel/LEGACY1"
        umlaut_url = "https://example.org/wiki/Küche"
        old_rows = [
            {"url": reel, "area": "chat", "chat": "kuechenchat_1", "sender": broken("Jürgen"),
             "date": "2023-11-14T22:13:20+00:00", "kind": "reel", "source": CHAT_FILE,
             "caption": broken("Pasta #küche 🍝"), "creator": broken("köchin")},
            # A correctly stored twin row: must merge with the repaired one, not duplicate.
            {"url": reel, "area": "chat", "chat": "kuechenchat_1", "sender": "Jürgen",
             "date": "2023-11-14T22:13:20+00:00", "kind": "reel", "source": CHAT_FILE,
             "caption": "Pasta #küche 🍝", "creator": "köchin"},
            {"url": broken(umlaut_url), "area": "chat", "chat": "kuechenchat_1", "sender": broken("Jürgen"),
             "date": "2023-11-14T22:13:20+00:00", "kind": "external", "source": CHAT_FILE},
        ]
        db = self.legacy_db(old_rows)
        by_url = {l["url"]: l["id"] for l in db.all_links()}
        reel_id, wiki_id = by_url[reel], by_url[broken(umlaut_url)]
        folders = {f["path"]: f["id"] for f in db.folders()}
        rezepte, favoriten = folders["groups/Rezepte"], folders["groups/Favoriten"]
        db.review(reel_id, [rezepte])
        db.assign(wiki_id, favoriten)
        db.review(wiki_id, [favoriten])
        db.suggest(wiki_id, rezepte, "synthetisch")
        db.conn.close()

        repaired = Library(self.path)  # repair runs on start
        links = {l["url"]: l for l in repaired.all_links()}
        self.assertEqual({reel, umlaut_url}, set(links))
        r = links[reel]
        self.assertEqual(["Jürgen"], [o["sender"] for o in r["occurrences"]])
        self.assertEqual("Jürgen", r["sender"])
        self.assertEqual(["Pasta #küche 🍝"], r["captions"])
        self.assertEqual(["köchin"], r["creators"])
        self.assertEqual(["küche"], r["hashtags"])
        self.assertEqual([rezepte], r["folders"])
        self.assertEqual("reviewed", r["review_status"])
        w = links[umlaut_url]
        self.assertEqual(repaired._link_id(umlaut_url), w["id"])
        self.assertEqual([favoriten], w["folders"])
        self.assertEqual("reviewed", w["review_status"])
        self.assertEqual([rezepte], [s["folder_id"] for s in w["suggestions"]])
        feedback = repaired.conn.execute("SELECT link_id,folder_id,accepted FROM feedback ORDER BY link_id").fetchall()
        self.assertEqual({(reel_id, rezepte, 1), (w["id"], favoriten, 1)}, {tuple(f) for f in feedback})
        self.assertEqual(0, repaired.conn.execute(
            "SELECT COUNT(*) FROM links WHERE id=?", (wiki_id,)).fetchone()[0])
        self.assertEqual(["küche"], [h["term"] for h in repaired.text_index()["hashtags"]])

        # Running the repair again changes nothing.
        before = repaired.all_links()
        repaired.repair_mojibake()
        self.assertEqual(before, repaired.all_links())

        # Re-importing the original (mojibake) export after repair adds no duplicates.
        raw = export([{"sender_name": broken("Jürgen"), "timestamp_ms": 1700000000000,
                       "share": {"link": reel + "/", "description": broken("Pasta #küche 🍝"),
                                 "creator_username": broken("köchin")}},
                      {"sender_name": broken("Jürgen"), "timestamp_ms": 1700000000000,
                       "content": broken(umlaut_url)}])
        items = process_bytes(raw, CHAT_FILE)["items"]
        self.assertEqual({reel, umlaut_url}, {i["url"] for i in items})
        tables = ("links", "occurrences", "captions", "creators", "assignments", "reviews", "feedback")
        counts = lambda: {t: repaired.conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in tables}
        counts_before = counts()
        self.assertEqual(before, repaired.import_rows(items))
        self.assertEqual(counts_before, counts())
        self.assertEqual(2, repaired.conn.execute("SELECT COUNT(*) FROM occurrences").fetchone()[0])
        self.assertEqual(1, repaired.conn.execute("SELECT COUNT(*) FROM captions").fetchone()[0])
        repaired.conn.close()

    def test_correct_legacy_text_is_not_touched(self):
        db = self.legacy_db([{"url": "https://example.org/caf%C3%A9", "sender": "Café Müller 😀",
                              "caption": "Crème brûlée #dessert", "source": "saved_posts.json"}])
        before = db.all_links()
        db.conn.close()
        self.assertEqual(before, Library(self.path).all_links())


if __name__ == "__main__":
    unittest.main()
