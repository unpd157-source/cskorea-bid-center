import json
import tempfile
import unittest
from pathlib import Path

from scripts.validate_data import main


class ValidateDataTests(unittest.TestCase):
    def test_installs_valid_live_document(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "next.json"
            destination = root / "bids.json"
            source.write_text(json.dumps({
                "meta": {"source": "KONEPS OpenAPI", "count": 1, "generatedAt": "2026-10-08T00:00:00+00:00"},
                "notices": [{"id": "A-00", "noticeNo": "A", "title": "행사", "matches": {"groupIds": ["all"]}}],
            }), encoding="utf-8")
            old_argv = __import__("sys").argv
            try:
                __import__("sys").argv = ["validate_data.py", str(source), str(destination)]
                self.assertEqual(main(), 0)
            finally:
                __import__("sys").argv = old_argv
            self.assertTrue(destination.exists())
            self.assertFalse(source.exists())


if __name__ == "__main__":
    unittest.main()
