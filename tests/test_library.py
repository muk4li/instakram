"""Smoke tests for the persistent local library and parser (stdlib only)."""
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from library_db import Library, DEFAULT_CATEGORIES
from parser_core import process_bytes

class LibraryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db_path = str(Path(self.temp.name) / "local.sqlite3")
        self.db = Library(self.db_path)

    def test_categories_created(self):
        self.assertEqual(len(DEFAULT_CATEGORIES) + 1, len(self.db.folders()))
        self.assertIn("groups/Anime", [f["path"] for f in self.db.folders()])

    def test_reimport_preserves_multiple_folders(self):
        rows = [{"url":"https://www.instagram.com/reel/ABcd123/",
                 "area":"chat","chat":"alice","sender":"bob","date":"2024-02-01",
                 "kind":"reel","source":"messages/inbox/alice/message_1.json"}]
        link = self.db.import_rows(rows)[0]
        groups = self.db.folders()
        self.db.assign(link["id"], groups[1]["id"])
        self.db.assign(link["id"], groups[2]["id"])
        self.assertEqual(2, len(self.db.import_rows(rows)[0]["folders"]))
        self.db.conn.close()
        reopened = Library(self.db_path)
        self.assertEqual(2, len(reopened.all_links()[0]["folders"]))

    def test_nested_rename_and_rule(self):
        parent = self.db.create_folder("Meine Sammlung")
        sub = self.db.create_folder("Tech", parent)
        self.db.rename_folder(parent, "Projekte")
        self.assertIn("Projekte/Tech", [f["path"] for f in self.db.folders()])
        rows = [{"url":"https://www.instagram.com/reel/ProgrammingABC/","kind":"reel","area":"saved","source":"saved_posts.json"}]
        self.db.import_rows(rows)
        self.db.add_rule(sub,"url","Programming")
        self.assertIn(sub,self.db.all_links()[0]["folders"])
        self.db.delete_folder(parent)
        self.assertNotIn(sub, [f["id"] for f in self.db.folders()])
        self.assertEqual(1,len(self.db.all_links()))

    def test_suggestions_require_approval(self):
        rows = [{"url":"https://example.com/python","kind":"external","area":"saved"}]
        self.db.import_rows(rows)
        self.assertGreater(self.db.local_suggestions(),0)
        link = self.db.all_links()[0]
        self.assertFalse(link["folders"])
        suggestion = link["suggestions"][0]
        self.db.assign(link["id"],suggestion["folder_id"])
        self.assertIn(suggestion["folder_id"], self.db.all_links()[0]["folders"])

    def test_zip_import(self):
        content = {"messages":[{"sender_name":"Alice","timestamp_ms":1700000000000,
                               "content":"https://www.instagram.com/reel/TESTONE/"}]}
        stream = io.BytesIO()
        with zipfile.ZipFile(stream,"w") as z:
            z.writestr("messages/inbox/alice/message_1.json",json.dumps(content))
        result = process_bytes(stream.getvalue(),"export.zip")
        self.assertEqual(1,len(result["items"]))
        self.assertEqual("reel",result["items"][0]["kind"])
        self.assertEqual("alice",result["items"][0]["chat"])

class SmartInboxTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db_path = str(Path(self.temp.name) / "smart.sqlite3")
        self.db = Library(self.db_path)
        self.folder = next(f["id"] for f in self.db.folders() if f["path"] == "groups/Tech & KI")

    @staticmethod
    def entry(path):
        return {"url":"https://example.org/"+path,"kind":"external","area":"saved","source":"saved_posts.json"}

    def test_review_persists_after_import_and_restart(self):
        link = self.db.import_rows([self.entry("one")])[0]
        self.assertEqual("pending",link["review_status"])
        self.db.review(link["id"],[self.folder])
        updated = self.db.import_rows([self.entry("one")])[0]
        self.assertEqual("reviewed",updated["review_status"])
        self.assertIn(self.folder,updated["folders"])
        self.db.conn.close()
        db = Library(self.db_path)
        self.assertEqual("reviewed",db.all_links()[0]["review_status"])

    def test_skipped_never_counts_as_negative_feedback(self):
        link = self.db.import_rows([self.entry("skip")])[0]
        self.db.suggest(link["id"],self.folder,"Unklar")
        self.db.review(link["id"],[],"skipped")
        self.assertEqual("skipped",self.db.all_links()[0]["review_status"])
        count = self.db.conn.execute("SELECT COUNT(*) FROM feedback").fetchone()[0]
        self.assertEqual(0,count)

    def test_learning_requires_four_manual_approvals_for_auto(self):
        for i in range(4):
            link = next(r for r in self.db.import_rows([self.entry("review"+str(i))])
                        if r["url"].endswith("review"+str(i)))
            self.db.review(link["id"],[self.folder])
        new_link = next(r for r in self.db.import_rows([self.entry("new")])
                        if r["url"].endswith("new"))
        self.assertIn(self.folder,new_link["folders"])
        self.assertEqual("pending",new_link["review_status"])

    def test_manual_rejection_blocks_auto(self):
        for i in range(4):
            row = next(r for r in self.db.import_rows([self.entry("positive"+str(i))])
                       if r["url"].endswith("positive"+str(i)))
            self.db.review(row["id"],[self.folder])
        rejected = next(r for r in self.db.import_rows([self.entry("rejected")])
                        if r["url"].endswith("rejected"))
        self.db.review(rejected["id"],[])
        subsequent = next(r for r in self.db.import_rows([self.entry("subsequent")])
                          if r["url"].endswith("subsequent"))
        self.assertNotIn(self.folder,subsequent["folders"])

    def test_unknown_instagram_reel_does_not_inherit_chat_sender_as_creator(self):
        self.db.import_rows([{"url":"https://www.instagram.com/reel/ABC123/","sender":"TechCreator","kind":"reel","area":"chat"}])
        self.assertIsNone(self.db._identity("https://www.instagram.com/reel/ABC123/"))

    def test_disable_auto_and_suggest_instead(self):
        self.db.set_settings(False,95)
        for i in range(4):
            link = next(r for r in self.db.import_rows([self.entry("a"+str(i))])
                        if r["url"].endswith("a"+str(i)))
            self.db.review(link["id"],[self.folder])
        candidate = next(r for r in self.db.import_rows([self.entry("candidate")])
                         if r["url"].endswith("candidate"))
        self.assertNotIn(self.folder,candidate["folders"])
        self.assertTrue(any(s["folder_id"]==self.folder for s in candidate["suggestions"]))

if __name__ == "__main__":
    unittest.main()
