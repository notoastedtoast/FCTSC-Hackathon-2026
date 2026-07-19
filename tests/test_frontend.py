from collections import Counter
import json
from pathlib import Path
import re
import unittest


class FrontendTests(unittest.TestCase):
    def test_every_required_javascript_element_exists_in_the_page(self) -> None:
        root = Path(__file__).resolve().parent.parent
        page = (root / "frontend" / "index.html").read_text(encoding="utf-8")
        script = (root / "frontend" / "app.js").read_text(encoding="utf-8")

        page_ids = set(re.findall(r'\bid=["\']([^"\']+)["\']', page))
        required_ids = set(
            re.findall(r'document\.getElementById\(["\']([^"\']+)["\']\)', script)
        )

        self.assertEqual(required_ids - page_ids, set())

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
        self.assertIn('id="result-context-label"', page)
        self.assertIn('id="practice-title"', page)
        self.assertIn('id="practice-message"', page)
        self.assertIn('id="connectivity-status"', page)
        self.assertIn('id="connectivity-message"', page)
        self.assertIn('class="top-nav"', page)
        self.assertIn('data-view="analyze"', page)
        self.assertIn('data-view="history"', page)
        self.assertIn('data-view="practice"', page)
        self.assertIn('data-view-panel="history"', page)
        self.assertIn('data-answer="scam"', page)
        self.assertIn('data-answer="safe"', page)
        self.assertNotIn("character-chat", page)
        self.assertNotIn('id="history-overlay"', page)
        self.assertNotIn('id="history-button"', page)
        self.assertNotIn('id="processing-frame"', page)
        self.assertNotIn('id="cancel-check-button"', page)
        self.assertNotIn('id="result-back-button"', page)
        self.assertIn('id="history-return-button"', page)
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
        self.assertNotIn("activeCheckController", script)
        self.assertIn("isAnalyzing=false", script)
        self.assertNotIn("startScanAnimation", script)
        self.assertNotIn("stopScanAnimation", script)
        self.assertNotIn("processingFrame", script)
        self.assertNotIn("resultBackButton", script)
        self.assertNotIn("cancelCheckButton", script)
        self.assertIn("historyReturnButton.hidden=!fromHistory", script)
        self.assertIn("historyReturnButton.addEventListener('click'", script)
        self.assertNotIn("/links/inspect", script)
        self.assertNotIn("function detectSignals(", script)
        self.assertNotIn("function determineRisk(", script)
        self.assertIn("navigator.serviceWorker.register('/service-worker.js')", script)
        self.assertIn("window.addEventListener('offline',updateConnectivityState)", script)
        self.assertIn("window.addEventListener('online',updateConnectivityState)", script)
        self.assertIn("sessionStorage.setItem(DRAFT_KEY", script)
        self.assertIn("sessionStorage.setItem(PENDING_ANALYSIS_KEY", script)
        self.assertIn("'X-ScamCheck-Request-ID':requestId", script)
        self.assertIn("requestStatus==='pending'", script)
        self.assertIn("fetch('/health',{cache:'no-store'})", script)
        self.assertIn("function resumePendingAnalysis()", script)
        self.assertIn("scheduleConnectionProbe()", script)
        self.assertIn("tiến trình phân tích đã được lưu", script)
        self.assertIn("(!isOffline&&sessionAtLimit)", script)
        self.assertIn("ScamCheckOffline.analyze(submittedText)", script)
        self.assertIn("analysis_mode==='offline'", script)
        self.assertIn("window.addEventListener('hashchange'", script)
        self.assertIn("function switchView(", script)
        self.assertIn("function showComposerFrame(", script)
        self.assertIn("target==='analyze'&&resultFrame.classList.contains('active')", script)
        self.assertIn("reuseButton.className='history-reuse-button'", script)
        self.assertIn("function createHistorySnapshot(", script)
        self.assertIn("saveHistory(submittedText,payload)", script)
        self.assertIn("reviewButton.className=`history-review-button", script)
        self.assertIn("function historySnapshotToPayload(", script)
        self.assertIn("showSavedHistoryResult(item)", script)
        self.assertIn("{fromHistory:true}", script)
        self.assertIn("Kết quả chưa lưu", script)
        self.assertIn("status.className=`history-status", script)
        self.assertIn("result?.character_message", script)
        self.assertNotIn("history-result-review", script)
        self.assertNotIn("historyList.innerHTML", script)
        self.assertNotIn(".processing-frame", styles)
        self.assertNotIn("@keyframes scan", styles)
        self.assertIn("const ScamCheckOffline", offline_analyzer)
        self.assertIn("Đánh giá ngoại tuyến", offline_analyzer)
        self.assertIn('"/offline-analyzer.js"', service_worker)
        self.assertIn('CACHE_NAME="scamcheck-shell-v9"', service_worker)
        self.assertIn("fetch(request)", service_worker)
        self.assertIn("const cacheKey=url.pathname", service_worker)
        self.assertIn("event.waitUntil(refresh.then(", service_worker)
        self.assertNotIn("/analyze", service_worker)
        self.assertNotIn("/session/ai-calls", service_worker)

    def test_styles_include_widescreen_layout_without_replacing_mobile_defaults(
        self,
    ) -> None:
        styles = (
            Path(__file__).resolve().parent.parent / "frontend" / "styles.css"
        ).read_text(encoding="utf-8")

        self.assertIn(".app-shell{min-height:100vh}", styles)
        self.assertIn("@media (min-width: 900px)", styles)
        self.assertIn("max-width:1180px", styles)
        self.assertIn(".analysis-workspace{grid-template-columns:", styles)
        self.assertIn(".history-list{grid-template-columns:repeat(2,minmax(0,1fr))}", styles)
        self.assertIn(".history-review-button:disabled", styles)
        self.assertIn(".history-review-button.safe", styles)
        self.assertIn(".history-review-button.suspicious", styles)
        self.assertIn(".history-review-button.dangerous", styles)
        self.assertIn("justify-content:flex-end", styles)
        self.assertNotIn(".history-result-review", styles)
        self.assertIn(".history-status.dangerous", styles)
        self.assertIn("grid-template-columns:repeat(3,minmax(0,1fr))", styles)
        self.assertIn(
            ".sample-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr))",
            styles,
        )
        self.assertIn('.sample-button[data-sample="bank"]', styles)
        self.assertIn('.sample-button[data-sample="delivery"]', styles)
        self.assertIn('.sample-button[data-sample="prize"]', styles)
        self.assertIn("@media (max-width: 620px)", styles)

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
