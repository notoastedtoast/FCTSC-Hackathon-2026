from collections import Counter
import unittest

from src.frontend import scam_type_catalog


class CatalogTests(unittest.TestCase):
    def test_catalog_has_required_size_fields_and_group_balance(self) -> None:
        self.assertGreaterEqual(len(scam_type_catalog), 12)
        self.assertLessEqual(len(scam_type_catalog), 15)
        self.assertEqual(
            len({item.id for item in scam_type_catalog}), len(scam_type_catalog)
        )

        group_counts = Counter(item.group for item in scam_type_catalog)
        self.assertEqual(
            set(group_counts),
            {"fake_bank", "fake_police", "prize", "fake_delivery"},
        )
        self.assertTrue(all(count >= 2 for count in group_counts.values()))
        for item in scam_type_catalog:
            with self.subTest(item=item.id):
                self.assertTrue(item.name.strip())
                self.assertTrue(item.description.strip())
                self.assertTrue(item.example_message.strip())
