import unittest

from scripts.evaluate import load_cases


class EvaluationDatasetTests(unittest.TestCase):
    def test_dataset_has_at_least_twenty_unique_labeled_cases(self) -> None:
        cases = load_cases()

        self.assertGreaterEqual(len(cases), 20)
        self.assertEqual(len({case.id for case in cases}), len(cases))
        self.assertEqual(
            {case.label for case in cases},
            {"safe", "suspicious", "dangerous", "ambiguous"},
        )

    def test_dataset_covers_normal_channels_and_ranges(self) -> None:
        cases = load_cases()

        self.assertGreaterEqual(sum(case.channel == "sms" for case in cases), 3)
        self.assertGreaterEqual(sum(case.channel == "email" for case in cases), 3)
        ambiguous = [case for case in cases if case.label == "ambiguous"]
        self.assertGreaterEqual(len(ambiguous), 3)
        self.assertTrue(all(len(case.accepted_labels) >= 2 for case in ambiguous))

    def test_prompt_injection_cases_are_never_labeled_safe(self) -> None:
        injection_cases = [
            case
            for case in load_cases()
            if "ignore previous" in case.text.casefold()
            or "bỏ qua hướng dẫn" in case.text.casefold()
            or "đổi vai" in case.text.casefold()
        ]

        self.assertGreaterEqual(len(injection_cases), 3)
        self.assertTrue(all(case.label != "safe" for case in injection_cases))
