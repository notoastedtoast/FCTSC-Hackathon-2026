from collections import Counter
import json
from pathlib import Path
import re
import unittest


class FrontendTests(unittest.TestCase):
    def test_static_page_calls_backend_and_keeps_results_separate(self) -> None:
        root = Path(__file__).resolve().parent.parent
        frontend = root / "frontend"
        page = (frontend / "index.html").read_text(encoding="utf-8")
        styles = (frontend / "styles.css").read_text(encoding="utf-8")
        script = (frontend / "app.js").read_text(encoding="utf-8")
        offline_analyzer = (frontend / "offline-analyzer.js").read_text(
            encoding="utf-8"
        )
        service_worker = (frontend / "service-worker.js").read_text(encoding="utf-8")

        self.assertTrue((frontend / "scamcheck-logo.png").is_file())
        self.assertIn('href="./styles.css"', page)
        self.assertIn('src="./app.js"', page)
        self.assertIn('src="./offline-analyzer.js"', page)
        self.assertNotIn("<style>", page)
        self.assertNotIn("<script>", page)
        self.assertIn(":root", styles)
        self.assertIn('id="detective-title"', page)
        self.assertIn('id="psychology-title"', page)
        self.assertIn('id="psychology-message"', page)
        self.assertIn('id="practice-title"', page)
        self.assertIn('id="practice-message"', page)
        self.assertIn('id="connectivity-status"', page)
        self.assertIn('data-answer="scam"', page)
        self.assertIn('data-answer="safe"', page)
        self.assertNotIn("character-chat", page)
        self.assertIn('requestJson("/analyze"', script)
        self.assertIn('requestJson("/session/ai-calls"', script)
        self.assertNotIn('requestJson("/practice-messages"', script)
        self.assertNotIn("/practice-messages/", script)
        self.assertIn("answer===prompt.label", script)
        self.assertIn("prompt.reason", script)
        self.assertIn("${aiUsage.used}/${aiUsage.limit} lượt gọi AI", script)
        self.assertIn("sessionAtLimit", script)
        self.assertIn("statusCode===429", script)
        self.assertIn("payload.character_notice", script)
        self.assertIn("detective.indicator_evidence", script)
        self.assertIn("detective.actions", script)
        self.assertIn("activeCheckController.abort()", script)
        self.assertNotIn("/links/inspect", script)
        self.assertNotIn("function detectSignals(", script)
        self.assertNotIn("function determineRisk(", script)
        self.assertIn("navigator.serviceWorker.register('/service-worker.js')", script)
        self.assertIn("window.addEventListener('offline',updateConnectivityState)", script)
        self.assertIn("window.addEventListener('online',updateConnectivityState)", script)
        self.assertIn("(!isOffline&&sessionAtLimit)", script)
        self.assertIn("ScamCheckOffline.analyze(submittedText)", script)
        self.assertIn("analysis_mode==='offline'", script)
        self.assertIn("const ScamCheckOffline", offline_analyzer)
        self.assertIn("Đánh giá ngoại tuyến", offline_analyzer)
        self.assertIn('"/offline-analyzer.js"', service_worker)
        self.assertNotIn("/analyze", service_worker)
        self.assertNotIn("/session/ai-calls", service_worker)

    def test_styles_include_widescreen_layout_without_replacing_mobile_defaults(
        self,
    ) -> None:
        styles = (
            Path(__file__).resolve().parent.parent / "frontend" / "styles.css"
        ).read_text(encoding="utf-8")

        self.assertIn(".phone-shell{width:100%;max-width:390px", styles)
        self.assertIn("@media (min-width: 900px)", styles)
        self.assertIn("max-width:1180px", styles)
        self.assertIn('grid-template-areas:', styles)
        self.assertIn('"message history"', styles)
        self.assertIn("grid-template-columns:repeat(2,minmax(0,1fr))", styles)
        self.assertIn("grid-template-columns:repeat(3,minmax(0,1fr))", styles)

    def test_practice_dataset_and_grading_live_only_in_frontend(self) -> None:
        root = Path(__file__).resolve().parent.parent
        script = (root / "frontend" / "app.js").read_text(encoding="utf-8")
        match = re.search(r"const practicePrompts=(\[.*?\]);", script, re.DOTALL)

        self.assertIsNotNone(match)
        assert match is not None
        prompts = json.loads(match.group(1))
        regression = json.loads(
            (root / "tests" / "labeled_messages.json").read_text(encoding="utf-8")
        )

        self.assertEqual(len(prompts), 10)
        self.assertEqual(
            Counter(item["label"] for item in prompts),
            {"scam": 5, "safe": 5},
        )
        self.assertEqual(len({item["id"] for item in prompts}), 10)
        self.assertTrue(all(item["reason"].strip() for item in prompts))
        self.assertFalse(
            {item["text"] for item in prompts}
            & {item["text"] for item in regression}
        )
        self.assertFalse((root / "src" / "data" / "sample_messages.json").exists())
