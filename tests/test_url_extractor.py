from unittest import TestCase

from src.url_extractor import extract_urls


class URLExtractorTests(TestCase):
    def test_extracts_urls_and_trims_sentence_punctuation(self) -> None:
        text = "Visit https://example.com/path?q=1, www.example.org, or bit.ly/check."

        self.assertEqual(
            extract_urls(text),
            [
                "https://example.com/path?q=1",
                "www.example.org",
                "bit.ly/check",
            ],
        )

    def test_does_not_treat_email_domain_as_a_url(self) -> None:
        self.assertEqual(extract_urls("Email help@example.com for support."), [])
