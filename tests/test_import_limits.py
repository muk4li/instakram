"""Import size limits stay consistent between server and web UI."""
import io
import re
import zipfile
import unittest
from pathlib import Path
from unittest import mock

import parser_core

ROOT = Path(__file__).resolve().parent.parent


class ImportLimitTests(unittest.TestCase):
    def test_archive_limit_is_800_mb(self):
        self.assertEqual(800 * 1024 * 1024, parser_core.MAX_ARCHIVE_BYTES)

    def test_json_limit_fits_large_likes_file(self):
        # A real export contained an 88.9 MB liked_posts.json.
        self.assertEqual(150 * 1024 * 1024, parser_core.MAX_JSON_BYTES)

    def test_oversized_json_in_zip_is_skipped_and_counted(self):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w") as z:
            z.writestr("your_instagram_activity/likes/liked_posts.json", "{}" + " " * 200)
            z.writestr("your_instagram_activity/saved/saved_posts.json",
                       '{"saved":[{"href":"https://www.instagram.com/reel/OK1/"}]}')
        with mock.patch.object(parser_core, "MAX_JSON_BYTES", 100):
            result = parser_core.process_bytes(stream.getvalue(), "export.zip")
        self.assertEqual(1, result["errors"])
        self.assertEqual(["https://www.instagram.com/reel/OK1"], [i["url"] for i in result["items"]])

    def test_web_ui_uses_same_limit(self):
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        limits = {int(m) for m in re.findall(r"file\.size>(\d+)\*1024\*1024", html)}
        self.assertEqual({parser_core.MAX_ARCHIVE_BYTES // (1024 * 1024)}, limits)

    def test_oversized_file_rejected_with_current_limit_in_message(self):
        with mock.patch.object(parser_core, "MAX_ARCHIVE_BYTES", 10):
            with self.assertRaisesRegex(ValueError, r"maximal 0 MB"):
                parser_core.process_bytes(b"x" * 11, "export.zip")

    def test_file_at_limit_is_accepted(self):
        with mock.patch.object(parser_core, "MAX_ARCHIVE_BYTES", 2):
            self.assertEqual([], parser_core.process_bytes(b"{}", "x.json")["items"])


if __name__ == "__main__":
    unittest.main()
