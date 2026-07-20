from collections import Counter
import json
from pathlib import Path
import re
import shutil
import subprocess
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
        self.assertTrue((frontend / "detective-avatar.png").is_file())
        self.assertIn('href="./styles.css"', page)
        self.assertIn('src="./app.js"', page)
        self.assertIn('src="./offline-analyzer.js"', page)
        self.assertNotIn("<style>", page)
        self.assertNotIn("<script>", page)
        self.assertIn(":root", styles)
        self.assertIn('id="detective-title"', page)
        self.assertIn('src="./detective-avatar.png"', page)
        self.assertIn('class="signal-list detective-message-list"', page)
        self.assertIn('id="psychology-title"', page)
        self.assertIn('id="psychology-block"', page)
        self.assertIn('id="action-section"', page)
        self.assertIn('id="psychology-message"', page)
        self.assertIn('id="result-context-label"', page)
        self.assertIn('id="highlight-note"', page)
        self.assertIn('id="practice-title"', page)
        self.assertIn('id="practice-message"', page)
        self.assertIn('id="connectivity-status"', page)
        self.assertIn('id="connectivity-message"', page)
        self.assertIn('id="voice-button" class="voice-button"', page)
        self.assertIn('id="voice-button-label" class="visually-hidden"', page)
        self.assertIn('aria-pressed="false"', page)
        self.assertNotIn('class="tool-card quick-input-card"', page)
        self.assertIn('class="top-nav"', page)
        self.assertIn('data-view="analyze"', page)
        self.assertIn('data-view="history"', page)
        self.assertIn('data-view="practice"', page)
        self.assertIn('data-view="library"', page)
        self.assertIn('data-view-panel="history"', page)
        self.assertIn('data-view-panel="library"', page)
        self.assertIn('Thư viện các kiểu lừa đảo', page)
        self.assertIn('id="library-search"', page)
        self.assertIn('placeholder="Tìm kiểu lừa đảo"', page)
        self.assertIn('data-scam-group="fake_bank"', page)
        self.assertIn('data-scam-group="fake_police"', page)
        self.assertIn('data-scam-group="prize"', page)
        self.assertIn('data-scam-group="fake_delivery"', page)
        self.assertIn('id="library-empty"', page)
        self.assertIn('Không tìm thấy kiểu lừa đảo phù hợp.', page)
        self.assertIn('id="library-detail-frame"', page)
        self.assertIn('id="library-detail-signs"', page)
        self.assertIn('id="library-detail-do"', page)
        self.assertIn('id="library-detail-dont"', page)
        self.assertIn('href="#analyze"', page)
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
        self.assertIn("requestJson('/scam-types')", script)
        self.assertIn("requestJson(`/scam-types/${encodeURIComponent(detailId)}`)", script)
        self.assertIn("window.history.pushState({scamLibraryFromList:true}", script)
        self.assertIn("window.history.back()", script)
        self.assertIn("searchable.includes(query)", script)
        self.assertIn("item.group===selectedScamGroup", script)
        self.assertNotIn("bank-account-lock", script)
        self.assertNotIn('requestJson("/practice-messages"', script)
        self.assertNotIn("/practice-messages/", script)
        self.assertIn("answer===prompt.label", script)
        self.assertIn("prompt.reason", script)
        self.assertIn("${aiUsage.used}/${aiUsage.limit} lượt gọi AI", script)
        self.assertIn("sessionAtLimit", script)
        self.assertIn("statusCode===429", script)
        self.assertIn("payload.character_notice", script)
        self.assertIn("riskLevel==='suspicious'||riskLevel==='dangerous'", script)
        self.assertIn("psychologyBlock.hidden=!shouldShow", script)
        self.assertIn("classList.toggle('psychology-hidden',!shouldShow)", script)
        self.assertIn("voiceButton.setAttribute('aria-pressed','true')", script)
        self.assertIn("detective.indicator_evidence", script)
        self.assertIn("detective.actions", script)
        self.assertIn("detective.risk_level==='suspicious'||detective.risk_level==='dangerous'", script)
        self.assertIn("highlightNote.hidden=!shouldHighlight||excerpts.length===0", script)
        self.assertIn("row.className=`detective-message-row", script)
        self.assertIn("avatar.src='/detective-avatar.png'", script)
        self.assertIn("--message-delay", script)
        self.assertIn("DETECTIVE_MESSAGE_GAP_MS=650", script)
        self.assertIn("function playDetectiveMessageSequence()", script)
        self.assertIn("void signalList.offsetWidth", script)
        self.assertNotIn("activeCheckController", script)
        self.assertIn("isAnalyzing=false", script)
        self.assertNotIn("startProcessingFrame", script)
        self.assertNotIn("waitForMinimumScan", script)
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
        self.assertIn("card=>checkButton.after(card)", script)
        self.assertNotIn("card=>checkButton.before(card)", script)
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
        self.assertIn("const ScamCheckOffline", offline_analyzer)
        self.assertIn("Đánh giá ngoại tuyến", offline_analyzer)
        self.assertIn('"/offline-analyzer.js"', service_worker)
        self.assertIn('"/detective-avatar.png"', service_worker)
        self.assertIn('CACHE_NAME="scamcheck-shell-v14"', service_worker)
        self.assertIn('new Set(["/","/styles.css","/app.js"])', service_worker)
        self.assertIn("if(!NETWORK_FIRST_PATHS.has(cacheKey))", service_worker)
        self.assertIn("fetch(request)", service_worker)
        self.assertIn("const cacheKey=url.pathname", service_worker)
        self.assertIn("event.waitUntil(refresh.then(", service_worker)
        self.assertNotIn("/analyze", service_worker)
        self.assertNotIn("/session/ai-calls", service_worker)

    def test_composer_remains_visible_while_analysis_is_pending(self) -> None:
        root = Path(__file__).resolve().parent.parent
        page = (root / "frontend" / "index.html").read_text(encoding="utf-8")
        script = (root / "frontend" / "app.js").read_text(encoding="utf-8")

        run_analysis = script[
            script.index("async function runAnalysis(submittedText)") :
            script.index("function createLibraryIcon(")
        ]
        self.assertIn("isAnalyzing=true", run_analysis)
        self.assertIn("updateInputState();", run_analysis)
        self.assertNotIn("inputFrame.style.display='none'", run_analysis)
        self.assertNotIn("processingFrame", run_analysis)
        self.assertNotIn('id="processing-frame"', page)

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
        self.assertIn("@keyframes detective-message-in", styles)
        self.assertIn("animation-delay:var(--message-delay)", styles)
        self.assertNotIn("var(--message-order) *", styles)
        self.assertIn(".result-frame .detective-message-row{opacity:1!important", styles)
        self.assertIn(".detective-message-row.summary-message", styles)
        self.assertIn(".action-section.psychology-hidden{grid-template-columns:1fr}", styles)
        self.assertIn(
            ".sample-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr))",
            styles,
        )
        self.assertIn('.sample-button[data-sample="bank"]', styles)
        self.assertIn('.sample-button[data-sample="delivery"]', styles)
        self.assertIn('.sample-button[data-sample="prize"]', styles)
        self.assertIn("@media (max-width: 620px)", styles)
        self.assertIn(".voice-button{position:absolute", styles)
        self.assertIn(".voice-button.recording", styles)
        self.assertIn(".composer-card>.primary-button+.sample-card", styles)
        self.assertIn(".library-filters{display:flex", styles)
        self.assertIn("overflow-x:auto", styles)
        self.assertIn(".library-filter.active", styles)
        self.assertIn(".scam-type-card:hover", styles)
        self.assertIn(".scam-type-card:active", styles)
        self.assertIn(".library-detail-grid", styles)

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

    def test_offline_analyzer_handles_common_risk_and_safety_contexts(self) -> None:
        node = shutil.which("node")
        if node is None:
            self.skipTest("Node.js is required for offline analyzer behavior checks")

        root = Path(__file__).resolve().parent.parent
        cases = [
            {
                "name": "ordinary greeting",
                "text": "Xin chào, tôi đến từ Hà Nội. Cảm ơn bạn đã trả lời tin nhắn này.",
                "risk": "safe",
            },
            {
                "name": "OTP safety warning",
                "text": "Không bao giờ gửi mã OTP cho bất kỳ ai.",
                "risk": "safe",
            },
            {
                "name": "OTP conditional threat",
                "text": "Nếu không gửi mã OTP, giao dịch sẽ không hoàn tất.",
                "risk": "dangerous",
            },
            {
                "name": "QR login phishing",
                "text": "Tài khoản ngân hàng có dấu hiệu bất thường. Hãy quét mã QR bên dưới để đăng nhập và kiểm tra.",
                "risk": "dangerous",
            },
            {
                "name": "remote-access safety warning",
                "text": "Cảnh báo bảo mật: không cài AnyDesk hoặc chia sẻ màn hình với người lạ.",
                "risk": "safe",
            },
            {
                "name": "remote-access request",
                "text": "Hãy cài AnyDesk để kỹ thuật viên điều khiển từ xa và khôi phục tài khoản.",
                "risk": "dangerous",
            },
            {
                "name": "ordinary email address",
                "text": "Bạn có thể gửi tài liệu tới support@example.com vào ngày mai.",
                "risk": "safe",
            },
            {
                "name": "completed transfer",
                "text": "Tôi đã chuyển khoản tiền ăn trưa cho bạn rồi, kiểm tra giúp nhé.",
                "risk": "safe",
            },
            {
                "name": "official utility payment",
                "text": "Bạn vui lòng thanh toán hóa đơn điện tháng này qua ứng dụng chính thức.",
                "risk": "safe",
            },
            {
                "name": "delivery fee scam",
                "text": "Đơn hàng chưa giao vì thiếu phí 25.000 đồng. Thanh toán ngay tại bit.ly/nhan-hang.",
                "risk": "dangerous",
            },
        ]
        corpus = json.loads(
            (root / "tests" / "labeled_messages.json").read_text(encoding="utf-8")
        )
        cases.extend(
            {
                "name": f"corpus: {item['id']}",
                "text": item["text"],
                "risk": item["expected"],
            }
            for item in corpus
        )
        runner = """
const fs=require('node:fs');
const analyzer=require(process.argv[1]);
const cases=JSON.parse(fs.readFileSync(0,'utf8'));
const results=cases.map(item=>({
  name:item.name,
  expected:item.risk,
  actual:analyzer.analyze(item.text).detective.risk_level
}));
process.stdout.write(JSON.stringify(results));
"""
        completed = subprocess.run(
            [node, "-e", runner, str(root / "frontend" / "offline-analyzer.js")],
            input=json.dumps(cases, ensure_ascii=False),
            capture_output=True,
            check=True,
            encoding="utf-8",
        )
        results = json.loads(completed.stdout)

        self.assertEqual(
            [(item["name"], item["actual"]) for item in results],
            [(item["name"], item["expected"]) for item in results],
        )
