"""Use of additional export metadata (synthetic data only)."""
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from library_db import Library
from parser_core import process_bytes, source_type
from topic_clusters import cluster_topics


def broken(text):
    return text.encode("utf-8").decode("latin-1")


def share(code, owner, text, sender="Freund A", reactions=0, ts=1700000000000):
    msg = {"sender_name": broken(sender), "timestamp_ms": ts,
           "content": broken(sender) + " hat einen Anhang gesendet.",
           "share": {"link": f"https://www.instagram.com/reel/{code}/",
                     "share_text": broken(text), "original_content_owner": owner},
           "is_geoblocked_for_viewer": False}
    if reactions:
        msg["reactions"] = [{"reaction": "❤", "actor": f"Reagierer {i}"} for i in range(reactions)]
    return msg


def chat_file(messages, participants=("Freund A", "Ich"), title="Freund A"):
    # Like real exports: participants first, title after the messages.
    doc = {"participants": [{"name": broken(p)} for p in participants],
           "messages": messages, "title": broken(title), "is_still_participant": True}
    return json.dumps(doc, ensure_ascii=True)


def export_zip(files):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as z:
        for name, content in files.items():
            z.writestr(name, content)
    return stream.getvalue()


INBOX = "your_instagram_activity/messages/inbox/"


class ParserMetadataTests(unittest.TestCase):
    def test_share_text_owner_reactions_and_chat_meta(self):
        data = chat_file([share("ABC1", "koch.kanal", "Pasta für Jürgen #küche #rezept", reactions=2)],
                         participants=("Freund A", "Freund B", "Ich"), title="Kochgruppe 🍝")
        item = process_bytes(data.encode(), INBOX + "kochgruppe_123/message_1.json")["items"][0]
        self.assertEqual("Pasta für Jürgen #küche #rezept", item["caption"])
        self.assertEqual("koch.kanal", item["creator"])
        self.assertEqual("Freund A", item["sender"])
        self.assertEqual(2, item["reactions"])
        self.assertEqual("Kochgruppe 🍝", item["chat_title"])
        self.assertEqual(3, item["participants"])
        self.assertEqual("kochgruppe_123", item["chat"])

    def test_reaction_actor_is_not_sender(self):
        data = chat_file([share("ABC2", "x", "t", sender="Freund A", reactions=1)])
        item = process_bytes(data.encode(), INBOX + "a_1/message_1.json")["items"][0]
        self.assertEqual("Freund A", item["sender"])

    def test_non_chat_file_has_no_chat_meta(self):
        doc = {"participants": ["x"], "saved": [{"href": "https://www.instagram.com/reel/S1/"}]}
        item = process_bytes(json.dumps(doc).encode(), "your_instagram_activity/saved/saved_posts.json")["items"][0]
        self.assertEqual(("", 0), (item["chat_title"], item["participants"]))

    def test_source_types(self):
        cases = {
            INBOX + "a_1/message_1.json": "chat",
            "your_instagram_activity/messages/message_requests/b_2/message_1.json": "message_request",
            "your_instagram_activity/saved/saved_posts.json": "saved",
            "your_instagram_activity/likes/liked_posts.json": "liked",
            "your_instagram_activity/likes/liked_comments.json": "liked_other",
            "your_instagram_activity/story_interactions/story_likes.json": "story_interaction",
            "connections/followers_and_following/following.json": "connection",
            "logged_information/link_history/link_history.json": "link_history",
            "ads_information/ads_and_topics/posts_viewed.json": "ads",
            "your_instagram_activity/media/posts_1.json": "own_media",
            "personal_information/personal_information/x.json": "other",
            "C:\\export\\your_instagram_activity\\saved\\saved_posts.json": "saved",
        }
        for path, expected in cases.items():
            self.assertEqual(expected, source_type(path), path)


def lv_entry(code, caption, username, ts=1792892876, owner_url="https://linktr.ee/beispiel"):
    """Structure of the user's saved_posts.json (German labels), synthetic values."""
    return {"timestamp": ts, "media": [], "fbid": "17800000000000000", "label_values": [
        {"label": "URL", "value": f"https://www.instagram.com/reel/{code}/",
         "href": f"https://www.instagram.com/reel/{code}/"},
        {"label": "Untertitel", "value": broken(caption)},
        {"label": "Titel", "value": ""},
        {"dict": [{"dict": [{"label": "Name", "value": "tagname"}], "title": ""}], "title": "Hashtags"},
        {"dict": [{"dict": [{"label": "URL", "value": owner_url},
                            {"label": "Name", "value": broken("Bäckerei Beispiel")},
                            {"label": "Benutzername", "value": username}], "title": ""}],
         "title": "Inhaber*in des Beitrags"},
        {"dict": [], "title": "Weitere Infos"},
    ]}


class LabelValuesFormatTests(unittest.TestCase):
    def test_saved_label_values_entry(self):
        doc = {"saved_saved_media": [lv_entry("SV1", "Brötchen backen #backen #brot", "baecker.ei")]}
        items = process_bytes(json.dumps(doc).encode(), "your_instagram_activity/saved/saved_posts.json")["items"]
        self.assertEqual(1, len(items), "owner profile/website URL must not become a link")
        item = items[0]
        self.assertEqual("https://www.instagram.com/reel/SV1", item["url"])
        self.assertEqual("Brötchen backen #backen #brot", item["caption"])
        self.assertEqual("baecker.ei", item["creator"])
        self.assertEqual("saved", item["area"])
        self.assertTrue(item["date"].startswith("2026-10-"))

    def test_liked_label_values_with_empty_owner_url(self):
        doc = {"likes_media_likes": [lv_entry("LK1", "Nur Text", "someone", owner_url="")]}
        item = process_bytes(json.dumps(doc).encode(), "your_instagram_activity/likes/liked_posts.json")["items"][0]
        self.assertEqual(("someone", "Nur Text"), (item["creator"], item["caption"]))
        self.assertEqual("liked", source_type(item["source"]))

    def test_english_labels(self):
        entry = {"timestamp": 1, "label_values": [
            {"label": "URL", "href": "https://www.instagram.com/p/EN1/"},
            {"label": "Caption", "value": "Hello #world"},
            {"dict": [{"dict": [{"label": "Username", "value": "eng.user"}]}], "title": "Owner"}]}
        item = process_bytes(json.dumps({"x": [entry]}).encode(), "your_instagram_activity/saved/saved_posts.json")["items"][0]
        self.assertEqual(("eng.user", "Hello #world"), (item["creator"], item["caption"]))

    def test_old_format_title_is_owner_only_for_saved_and_liked(self):
        liked = {"likes_media_likes": [{"title": "old.owner", "string_list_data": [
            {"href": "https://www.instagram.com/p/OLD1/", "value": "x", "timestamp": 1700000000}]}]}
        item = process_bytes(json.dumps(liked).encode(), "your_instagram_activity/likes/liked_posts.json")["items"][0]
        self.assertEqual("old.owner", item["creator"])
        comment = {"likes_comment_likes": [{"title": "comment.author", "string_list_data": [
            {"href": "https://www.instagram.com/p/OLD2/", "value": "x", "timestamp": 1700000000}]}]}
        item = process_bytes(json.dumps(comment).encode(), "your_instagram_activity/likes/liked_comments.json")["items"][0]
        self.assertEqual("", item["creator"])


class LibraryMetadataTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = str(Path(tmp.name) / "meta.sqlite3")
        self.db = Library(self.path)

    def import_zip(self, files):
        return self.db.import_rows(process_bytes(export_zip(files), "export.zip")["items"])

    def test_chats_signals_hashtags_and_clusters(self):
        files = {
            INBOX + "kochgruppe_1/message_1.json": chat_file(
                [share("R1", "koch.kanal", "Pasta #küche", reactions=1),
                 share("R2", "koch.kanal", "Suppe #küche", sender="Freund B")],
                participants=("Freund A", "Freund B", "Ich"), title="Kochgruppe"),
            INBOX + "freunda_2/message_1.json": chat_file([share("R1", "koch.kanal", "Pasta #küche")]),
            "your_instagram_activity/saved/saved_posts.json":
                json.dumps({"saved": [{"href": "https://www.instagram.com/reel/R1/"}]}),
        }
        links = {l["url"].rsplit("/", 1)[-1]: l for l in self.import_zip(files)}
        r1 = links["R1"]
        self.assertEqual(["chat", "saved"], r1["sources"])
        self.assertEqual({"shares": 2, "saved": True, "liked": False, "reactions": 1}, r1["signals"])
        self.assertGreater(r1["score"], links["R2"]["score"])
        self.assertEqual(["koch.kanal"], r1["creators"])
        self.assertEqual(["küche"], r1["hashtags"])

        chats = {c["chat"]: c for c in self.db.chats()}
        self.assertEqual({"title": "Kochgruppe", "participants": 3, "links": 2, "is_group": True},
                         {k: chats["kochgruppe_1"][k] for k in ("title", "participants", "links", "is_group")})
        self.assertFalse(chats["freunda_2"]["is_group"])

        self.assertEqual(2, next(t for t in self.db.text_index()["hashtags"] if t["term"] == "küche")["count"])
        clusters = cluster_topics(self.db.all_links(), self.db.folders())
        self.assertTrue(any(c["type"] == "creator" and c["title"] == "@koch.kanal" for c in clusters))
        self.assertTrue(any(c["type"] == "hashtag" and c["title"] == "#küche" for c in clusters))

    def test_reimport_is_idempotent_and_keeps_reactions(self):
        files = {INBOX + "a_1/message_1.json": chat_file([share("R9", "x", "t", reactions=3)])}
        first = self.import_zip(files)
        second = self.import_zip(files)
        self.assertEqual(first, second)
        self.assertEqual(1, self.db.conn.execute("SELECT COUNT(*) FROM occurrences").fetchone()[0])
        self.assertEqual(3, second[0]["signals"]["reactions"])

    def test_learning_by_exported_creator_auto_assigns_reels(self):
        rezepte = next(f["id"] for f in self.db.folders() if f["path"] == "groups/Rezepte")
        messages = [share(f"K{i}", "koch.kanal", f"Gericht {i}", ts=1700000000000 + i) for i in range(5)]
        links = {l["url"].rsplit("/", 1)[-1]: l for l in self.import_zip(
            {INBOX + "a_1/message_1.json": chat_file(messages[:4])})}
        for code in ("K0", "K1", "K2", "K3"):
            self.db.review(links[code]["id"], [rezepte])
        new = next(l for l in self.import_zip({INBOX + "a_1/message_2.json": chat_file(messages[4:])})
                   if l["url"].endswith("K4"))
        self.assertIn(rezepte, new["folders"])
        self.assertEqual("pending", new["review_status"])

    def test_reels_without_creator_still_do_not_learn(self):
        rezepte = next(f["id"] for f in self.db.folders() if f["path"] == "groups/Rezepte")
        rows = [{"url": f"https://www.instagram.com/reel/N{i}", "sender": "Freund A", "area": "chat"} for i in range(5)]
        links = {l["url"]: l for l in self.db.import_rows(rows[:4])}
        for link in links.values():
            self.db.review(link["id"], [rezepte])
        new = next(l for l in self.db.import_rows(rows[4:]) if l["url"].endswith("N4"))
        self.assertNotIn(rezepte, new["folders"])
        self.assertEqual([], new["suggestions"])

    def test_existing_database_gets_reactions_column(self):
        self.db.conn.close()
        import sqlite3
        conn = sqlite3.connect(self.path)
        conn.executescript("""
            CREATE TABLE occ_old AS SELECT link_id,area,chat,sender,date,kind,source FROM occurrences;
            DROP TABLE occurrences;
            CREATE TABLE occurrences (
                link_id TEXT NOT NULL REFERENCES links(id) ON DELETE CASCADE,
                area TEXT NOT NULL, chat TEXT NOT NULL, sender TEXT NOT NULL,
                date TEXT NOT NULL, kind TEXT NOT NULL, source TEXT NOT NULL,
                PRIMARY KEY(link_id,area,chat,sender,date,source));
            DROP TABLE occ_old; DROP TABLE chats;""")
        conn.commit()
        conn.close()
        db = Library(self.path)
        cols = {r[1] for r in db.conn.execute("PRAGMA table_info(occurrences)")}
        self.assertIn("reactions", cols)
        db.import_rows([{"url": "https://example.org/a", "chat": "c", "reactions": 1}])
        self.assertEqual(1, db.all_links()[0]["signals"]["reactions"])
        db.conn.close()


if __name__ == "__main__":
    unittest.main()
