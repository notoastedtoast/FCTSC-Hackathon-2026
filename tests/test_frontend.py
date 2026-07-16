import json
from pathlib import Path
import unittest


class FrontendTests(unittest.TestCase):
    def test_static_page_exposes_two_results_and_twelve_item_library(self) -> None:
        frontend = Path(__file__).resolve().parent.parent / "frontend"
        page = (frontend / "index.html").read_text(encoding="utf-8")
        library = json.loads(
            (frontend / "scam-library.json").read_text(encoding="utf-8")
        )

        self.assertIn('id="detective-title">Thám tử', page)
        self.assertIn('id="psychology-title">Cô tâm lý', page)
        self.assertNotIn("character-chat", page)

        self.assertGreaterEqual(len(library), 12)
        self.assertEqual(len({entry["id"] for entry in library}), len(library))
        self.assertTrue({"bank", "police", "prize", "delivery"}.issubset(
            {entry["group"] for entry in library}
        ))
        for entry in library:
            with self.subTest(entry=entry["id"]):
                self.assertTrue(entry["title"])
                self.assertTrue(entry["summary"])
                self.assertGreaterEqual(len(entry["signs"]), 2)
                self.assertGreaterEqual(len(entry["actions"]), 2)
