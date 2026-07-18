from collections import Counter
import unittest

from src.catalog import SCAM_TYPES


class CatalogTests(unittest.TestCase):
    def test_catalog_has_required_size_fields_and_group_balance(self) -> None:
        self.assertGreaterEqual(len(SCAM_TYPES), 12)
        self.assertLessEqual(len(SCAM_TYPES), 15)
        self.assertEqual(len({item.id for item in SCAM_TYPES}), len(SCAM_TYPES))

        group_counts = Counter(item.group for item in SCAM_TYPES)
        self.assertEqual(
            set(group_counts),
            {"fake_bank", "fake_police", "prize", "fake_delivery"},
        )
        self.assertTrue(all(count >= 2 for count in group_counts.values()))
        for item in SCAM_TYPES:
            with self.subTest(item=item.id):
                self.assertTrue(item.name.strip())
                self.assertTrue(item.description.strip())
                self.assertTrue(item.example_message.strip())
