"""Library snapshot cache used for page reloads (synthetic data only)."""
import json
import os
import tempfile
import unittest
from pathlib import Path

_tmp = tempfile.TemporaryDirectory()
os.environ["INSTAKRAM_DB"] = str(Path(_tmp.name) / "server.sqlite3")
import server  # noqa: E402  (module creates its DB from INSTAKRAM_DB on import)
from library_db import Library  # noqa: E402


class LibraryCacheTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.db = Library(Path(tmp.name) / "cache.sqlite3")
        self.cache = server.LibraryCache(self.db)
        self.db.import_rows([{"url": "https://www.instagram.com/reel/C1", "caption": "#küche", "area": "saved"}])

    def test_reload_reuses_snapshot(self):
        calls = []
        original = self.db.all_links
        self.db.all_links = lambda: calls.append(1) or original()
        first = self.cache.library_body()
        self.assertIs(first, self.cache.library_body())
        self.cache.topics_body()
        self.assertEqual(1, len(calls), "links are built once for library and topics")

    def test_write_after_invalidate_is_visible(self):
        before = json.loads(self.cache.library_body())
        self.assertEqual(1, len(before["items"]))
        self.db.import_rows([{"url": "https://www.instagram.com/reel/C2", "area": "saved"}])
        self.cache.invalidate()
        after = json.loads(self.cache.library_body())
        self.assertEqual(2, len(after["items"]))
        self.assertIn(["küche"], [item["hashtags"] for item in after["items"]])

    def test_import_response_seeds_cache(self):
        links = self.db.all_links()
        payload = self.cache.payload(links=links)
        self.assertIs(links, payload["items"])
        self.assertIsInstance(json.loads(self.cache.topics_body())["topics"], list)


if __name__ == "__main__":
    unittest.main()
