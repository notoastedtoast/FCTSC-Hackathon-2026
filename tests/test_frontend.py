from collections import Counter
import json
from pathlib import Path
import re
import shutil
import subprocess
import unittest


def frontend_script_bundle(frontend: Path) -> str:
    return "\n".join(
        (frontend / name).read_text(encoding="utf-8")
        for name in ("app-data.js", "app-render.js", "app.js")
    )


def contrast_ratio(foreground: str, background: str) -> float:
    def relative_luminance(hex_color: str) -> float:
        channels = [
            int(hex_color[index : index + 2], 16) / 255
            for index in (1, 3, 5)
        ]
        linear = [
            channel / 12.92
            if channel <= 0.04045
            else ((channel + 0.055) / 1.055) ** 2.4
            for channel in channels
        ]
        return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]

    foreground_luminance = relative_luminance(foreground)
    background_luminance = relative_luminance(background)
    lighter = max(foreground_luminance, background_luminance)
    darker = min(foreground_luminance, background_luminance)
    return (lighter + 0.05) / (darker + 0.05)


class FrontendTests(unittest.TestCase):
    def test_every_required_javascript_element_exists_in_the_page(self) -> None:
        root = Path(__file__).resolve().parent.parent
        frontend = root / "frontend"
        page = (frontend / "index.html").read_text(encoding="utf-8")
        script = frontend_script_bundle(frontend)

        page_ids = set(re.findall(r'\bid=["\']([^"\']+)["\']', page))
        required_ids = set(
            re.findall(
                r'(?:document\.getElementById|byId)\(["\']([^"\']+)["\']\)',
                script,
            )
        )

        self.assertEqual(required_ids - page_ids, set())

    def test_static_page_calls_backend_and_keeps_results_separate(self) -> None:
        root = Path(__file__).resolve().parent.parent
        frontend = root / "frontend"
        page = (frontend / "index.html").read_text(encoding="utf-8")
        styles = (frontend / "styles.css").read_text(encoding="utf-8")
        script = frontend_script_bundle(frontend)
        offline_analyzer = (frontend / "offline-analyzer.js").read_text(
            encoding="utf-8"
        )
        service_worker = (frontend / "service-worker.js").read_text(encoding="utf-8")
        frontend_routes = (root / "src" / "frontend.py").read_text(encoding="utf-8")

        self.assertTrue((frontend / "scamcheck-logo.png").is_file())
        self.assertTrue((frontend / "detective-avatar.png").is_file())
        self.assertTrue((frontend / "psychologist-avatar.png").is_file())
        self.assertTrue((frontend / "responder-avatar.png").is_file())
        self.assertTrue((frontend / "html2canvas.min.js").is_file())
        self.assertIn('href="./styles.css"', page)
        self.assertIn('src="./html2canvas.min.js"', page)
        self.assertIn('src="./app-data.js"', page)
        self.assertIn('src="./app-render.js?v=38"', page)
        self.assertIn('src="./app.js?v=40"', page)
        self.assertIn('src="./offline-analyzer.js"', page)
        self.assertIn('@router.get("/html2canvas.min.js"', frontend_routes)
        self.assertIn('return frontend_file("html2canvas.min.js")', frontend_routes)
        self.assertLess(
            page.index('src="./html2canvas.min.js"'),
            page.index('src="./app-render.js?v=38"'),
        )
        self.assertNotIn("<style>", page)
        self.assertNotIn("<script>", page)
        self.assertIn(":root", styles)
        self.assertIn('id="detective-title"', page)
        self.assertIn('src="./detective-avatar.png"', page)
        self.assertIn('src="./psychologist-avatar.png"', page)
        self.assertIn('src="./responder-avatar.png"', page)
        self.assertIn('class="signal-list detective-message-list"', page)
        self.assertIn('id="psychology-title"', page)
        self.assertIn('id="psychology-block"', page)
        self.assertIn('id="action-section"', page)
        self.assertIn('id="psychology-message"', page)
        self.assertIn('id="post-analysis-question"', page)
        self.assertEqual(page.count('class="post-analysis-option"'), 4)
        self.assertIn('data-post-analysis-choice="sent-money"', page)
        self.assertIn('id="responder-block"', page)
        self.assertIn('id="responder-steps"', page)
        self.assertIn('id="bank-question"', page)
        self.assertIn('id="bank-options"', page)
        self.assertIn('class="role-label responder-label">Người ứng cứu</div>', page)
        self.assertIn('id="result-share-section"', page)
        self.assertIn('id="download-result-image-button"', page)
        self.assertIn('id="result-image-status"', page)
        self.assertIn("<h2>Tóm tắt kết quả</h2>", page)
        self.assertNotIn("<h2>Những dấu hiệu đáng chú ý</h2>", page)
        self.assertIn('Tải kết quả dạng ảnh', page)
        self.assertIn('id="result-share-title">Tải kết quả phân tích</h2>', page)
        self.assertIn('<p>Tải kết quả đánh giá tin nhắn</p>', page)
        self.assertIn('id="result-context-label"', page)
        self.assertIn('id="result-scroll-button"', page)
        self.assertIn('aria-label="Cuộn xuống tin nhắn mới nhất"', page)
        self.assertIn('aria-controls="result-frame"', page)
        self.assertIn('aria-label="Cuộn xuống tin nhắn mới nhất"', page)
        self.assertIn('id="practice-title"', page)
        self.assertIn('id="practice-message"', page)
        self.assertIn('id="connectivity-status"', page)
        self.assertIn('id="connectivity-message"', page)
        self.assertIn('id="voice-button" class="voice-button"', page)
        self.assertIn('id="voice-button-label" class="visually-hidden"', page)
        self.assertNotIn('id="clear-button"', page)
        self.assertNotIn("clearButton", script)
        self.assertIn('aria-pressed="false"', page)
        self.assertNotIn('class="tool-card quick-input-card"', page)
        self.assertIn('id="composer-title">Nội dung cần kiểm tra</h2>', page)
        self.assertIn('class="usage usage-badge"', page)
        self.assertIn('Số lượt phân tích còn lại: 10 lần', page)
        self.assertNotIn('Trạng thái phiên', page)
        self.assertNotIn('usage-card', page)
        self.assertIn('class="top-nav"', page)
        self.assertIn('id="contrast-toggle"', page)
        self.assertIn('id="font-size-toggle"', page)
        self.assertIn('aria-label="Tùy chọn hiển thị"', page)
        self.assertIn("DISPLAY_PREFERENCES_KEY='scamcheck-display-preferences-v1'", script)
        self.assertIn("localStorage.setItem(DISPLAY_PREFERENCES_KEY", script)
        self.assertIn("data-high-contrast", styles)
        self.assertIn("data-large-text", styles)
        self.assertIn("toggleAttribute('data-high-contrast'", script)
        self.assertIn("toggleAttribute('data-large-text'", script)
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
        self.assertIn('id="processing-frame"', page)
        self.assertNotIn('id="cancel-check-button"', page)
        self.assertNotIn('id="result-back-button"', page)
        self.assertIn('id="history-return-button"', page)
        self.assertIn("requestJson('/analyze'", script)
        self.assertIn("'X-ScamCheck-Request-ID'", script)
        self.assertIn("function loadUsageCompat()", script)
        self.assertIn("requestJson('/scam-types')", script)
        self.assertIn("requestJson('/telephones')", script)
        self.assertIn("requestJson(`/scam-types/${encodeURIComponent(detailId)}`)", script)
        self.assertIn("window.history.pushState({scamLibraryFromList:true}", script)
        self.assertIn("window.history.back()", script)
        self.assertIn("searchable.includes(query)", script)
        self.assertIn("item.group===selectedScamGroup", script)
        self.assertNotIn("bank-account-lock", script)
        self.assertNotIn("requestJson('/practice-messages'", script)
        self.assertNotIn("/practice-messages/", script)
        self.assertIn("answer===prompt.label", script)
        self.assertIn("prompt.reason", script)
        self.assertIn("ANALYSIS_LIMIT=10", script)
        self.assertIn("ANALYSIS_REMAINING_KEY", script)
        self.assertIn("function restoreRemainingAnalyses()", script)
        self.assertIn("restoreRemainingAnalyses();restoreDraft()", script)
        self.assertIn("function decrementRemainingAnalyses()", script)
        self.assertIn("remainingAnalyses=Math.max(0,remainingAnalyses-1)", script)
        self.assertNotIn("X-ScamCheck-Page-Session", script)
        self.assertIn(
            "`Số lượt phân tích còn lại: ${remainingAnalyses} lần`",
            script,
        )
        self.assertIn("sessionAtLimit", script)
        self.assertIn("statusCode===429", script)
        self.assertIn("payload.character_notice", script)
        self.assertIn("function guideText(value)", script)
        self.assertIn("Array.isArray(parsed)", script)
        self.assertIn("function normalizeHistoryTimestamp(value)", script)
        self.assertIn("payload.date=normalizeHistoryTimestamp(entry.created_at)", script)
        self.assertIn("raw.replace(' ','T')}Z", script)
        self.assertIn("riskLevel==='suspicious'||riskLevel==='dangerous'", script)
        self.assertIn("psychologyBlock.hidden=true", script)
        self.assertIn("actionSection.hidden=true", script)
        self.assertIn("actionSection.hidden=false", script)
        self.assertIn("voiceButton.setAttribute('aria-pressed','true')", script)
        self.assertIn("detective.indicator_evidence", script)
        self.assertIn("detective.actions", script)
        self.assertIn("detective.risk_level==='suspicious'||detective.risk_level==='dangerous'", script)
        self.assertIn("note.hidden=!shouldHighlight||excerpts.length===0", script)
        self.assertIn("row.className=`detective-message-row", script)
        self.assertIn("avatar.src='/detective-avatar.png'", script)
        self.assertIn("function appendOriginalMessageCard(text,excerpts,shouldHighlight)", script)
        self.assertIn("appendOriginalMessageCard(originalText,excerpts,shouldHighlight)", script)
        self.assertIn("function renderRecommendations(actions)", script)
        self.assertIn("renderRecommendations(detective.actions||[])", script)
        self.assertIn(
            "SHARE_PRODUCT_URL='https://fctsc-hackathon-2026.vercel.app/'",
            script,
        )
        self.assertIn("function createQrMatrix(value=SHARE_PRODUCT_URL)", script)
        self.assertIn("function createResultShareCanvas(summary)", script)
        self.assertIn("canvas.width=1080", script)
        self.assertIn("canvas.height=Math.max(1350", script)
        self.assertIn("loadShareImage('/scamcheck-logo.png')", script)
        self.assertIn("loadShareImage('/detective-avatar.png')", script)
        self.assertIn("currentShareSummary=resultShareSummary(text,payload)", script)
        self.assertIn("new URL('/#analyze',SHARE_PRODUCT_URL).href", script)
        self.assertNotIn("new URL(`#result/${id}`,SHARE_PRODUCT_URL).href", script)
        self.assertIn("drawQr(context,850,footerTop+21,146,summary.resultUrl)", script)
        self.assertIn("originalText:normalizeShareText(originalText)", script)
        self.assertIn("analyzedAt:payload?.date", script)
        self.assertIn("new Date(currentShareSummary.analyzedAt)", script)
        self.assertIn("lastModified:analyzedAt.getTime()", script)
        self.assertIn("summary.originalText", script)
        self.assertIn("summary.actions.map", script)
        self.assertIn("summary.signs.map", script)
        self.assertIn("document.fonts?.ready", script)
        self.assertIn(".normalize('NFC')", script)
        self.assertIn('SHARE_CANVAS_FONT=\'system-ui, -apple-system', script)
        self.assertIn("drawQr(context,850,footerTop+21,146,summary.resultUrl)", script)
        self.assertIn("function createDetectiveCaptureNode()", script)
        self.assertIn("source.cloneNode(true)", script)
        self.assertIn("row.classList.contains('original-message-row')", script)
        self.assertIn("originalMessage?.classList.contains('highlighted')", script)
        self.assertIn("currentShareSummary?.originalText", script)
        self.assertIn("plainOriginal.classList.add('capture-original-message-row')", script)
        self.assertIn("plainTitle.textContent='Tin nhắn gốc'", script)
        self.assertIn("originalMessage.classList.add('capture-highlighted-message')", script)
        self.assertIn("highlightedTitle.textContent='Phần tin nhắn cần chú ý'", script)
        self.assertIn("!row.classList.contains('recommendations-message')", script)
        self.assertIn(
            "messageList.replaceChildren(...orderedOriginalRows,...analysisRows)",
            script,
        )
        self.assertIn("typeof window.html2canvas!=='function'", script)
        self.assertIn("return await window.html2canvas(capture,{", script)
        self.assertIn("windowWidth:390", script)
        self.assertIn("scale:3", script)
        self.assertIn("const canvas=await createDetectiveDomCaptureCanvas()", script)
        self.assertIn("downloadResultImageButton.disabled=true", script)
        self.assertIn("downloadResultImageButton.disabled=false", script)
        self.assertIn("canvas.toBlob(blob=>", script)
        self.assertIn("},'image/png',1)", script)
        self.assertIn("new File([blob],filename,{type:'image/png'", script)
        self.assertIn("navigator.canShare({files:[file]})", script)
        self.assertIn("await navigator.share({", script)
        self.assertIn("anchor.download=filename", script)
        self.assertIn("downloadResultImageButton.addEventListener('click'", script)
        self.assertNotIn("api.qrserver.com", script)
        self.assertNotIn("chart.googleapis.com", script)
        self.assertNotIn("document.getElementById('recommendations')", script)
        append_signal = script[
            script.index("function appendSignalCard(") :
            script.index("function appendOriginalMessageCard(")
        ]
        self.assertIn("return card;", append_signal)
        self.assertNotIn("document.getElementById('original-message')", script)
        self.assertNotIn("MESSAGE_STREAM_CHUNK_MS", script)
        self.assertNotIn("MESSAGE_STREAM_GAP_MS", script)
        self.assertNotIn("MESSAGE_STREAM_MAX_STEPS", script)
        self.assertNotIn("MESSAGE_REVEAL_INTERVAL_MS", script)
        self.assertNotIn("Dấu hiệu này được tìm thấy trong nội dung đã gửi.", script)
        self.assertIn("quote.textContent=`Dấu hiệu: “${quoteText}”`", script)
        self.assertIn("function renderResultBlocks()", script)
        self.assertIn("function revealPsychologyMessages()", script)
        self.assertIn("function revealRows(rows)", script)
        self.assertNotIn("function streamMessageContent", script)
        self.assertNotIn("document.createTreeWalker(message,NodeFilter.SHOW_TEXT)", script)
        self.assertNotIn("window.setTimeout(revealNextChunk", script)
        self.assertNotIn("window.setTimeout(revealNext", script)
        self.assertIn("messages.forEach(message=>{", script)
        self.assertIn("function openResultPage(id,{fromHistory=false}={})", script)
        self.assertIn("{...item.result,date:item.result.date||item.date}", script)
        self.assertIn("candidate.startsWith('history/')", script)
        self.assertIn("resultId:decodeURIComponent(candidate.slice(8))", script)
        self.assertIn("const routePrefix=fromHistory?'history':'result'", script)
        self.assertIn("#${routePrefix}/${encodeURIComponent(id)}", script)
        self.assertIn("async function showResultRoute(resultId)", script)
        self.assertIn("`/history/${encodeURIComponent(resultId)}`", script)
        self.assertIn("fromHistory:route.fromHistory||resultFromHistoryId===resultId", script)
        self.assertIn("link.dataset.view==='history'", script)
        self.assertIn("if(!shouldShow||payload.character_pending)", script)
        self.assertIn("function scrollToResultMessage(message,{force=false}={})", script)
        self.assertIn("function pauseResultAutoFollow()", script)
        self.assertIn("function resumeResultAutoFollow()", script)
        self.assertIn("latestResultMessage=visibleMessages.at(-1)||latestResultMessage", script)
        self.assertIn(".post-analysis-question:not([hidden])", script)
        self.assertIn("function handleResultWindowScroll()", script)
        self.assertIn("message.scrollIntoView({", script)
        self.assertNotIn("resultFrame.addEventListener('animationstart'", script)
        self.assertIn("window.addEventListener('wheel'", script)
        self.assertIn("window.addEventListener('touchmove'", script)
        self.assertNotIn("function clearMessageRevealTimers()", script)
        self.assertNotIn("detectiveSequenceComplete", script)
        self.assertIn("function splitPsychologyMessage(message)", script)
        self.assertIn("function appendPsychologyMessage(message)", script)
        self.assertIn("function revealPostAnalysisQuestion()", script)
        self.assertIn("if(!psychologyMessage.childElementCount)return;", script)
        self.assertIn("function responderExposureFlags(originalText,payload)", script)
        self.assertIn("const shouldOfferResponder=exposures.link||exposures.money||exposures.credentials||exposures.remote", script)
        self.assertIn("postAnalysisQuestion.dataset.eligible=String(Boolean(shouldShow&&!payload.offline&&payload.id&&shouldOfferResponder))", script)
        self.assertIn("option.dataset.postAnalysisChoice==='opened-link'&&!exposures.link", script)
        self.assertIn("item.disabled=true", script)
        self.assertIn("item.classList.toggle('selected',item===option)", script)
        self.assertIn("const rescuePlans={", script)
        self.assertIn("function renderResponderGuidance(steps)", script)
        self.assertIn("requestJson('/responder/'", script)
        self.assertIn("await generateResponder(option.dataset.postAnalysisChoice,await loadTelephones())", script)
        self.assertIn("function askForBank(choice,hotlines)", script)
        self.assertIn("output.needs_bank", script)
        self.assertIn("const row=document.createElement('li')", script)
        self.assertIn("text.textContent=step", script)
        self.assertIn("avatar.src='/responder-avatar.png'", script)
        self.assertIn("responderSteps.replaceChildren(...items)", script)
        self.assertIn("responderBlock.hidden=false", script)
        self.assertIn("revealRows(items)", script)
        self.assertIn("avatar.src='/psychologist-avatar.png'", script)
        self.assertIn("const psychologyEmojiRules=[", script)
        self.assertIn("function psychologyEmojiFor(message)", script)
        self.assertIn("emoji.textContent=psychologyEmojiFor(message)", script)
        self.assertIn("card.classList.add('recommendations-card')", script)
        self.assertIn("classList.add('recommendations-message')", script)
        self.assertNotIn("activeCheckController", script)
        self.assertIn("isAnalyzing=false", script)
        self.assertIn("function showProcessingFrame()", script)
        self.assertIn("function hideProcessingFrame()", script)
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
        self.assertIn("'X-ScamCheck-Request-ID':pending.requestId", script)
        self.assertIn("function pendingAnalysisFor(message)", script)
        self.assertIn("requestError.transportFailure=true", script)
        self.assertIn("requestError.networkInterrupted=!navigator.onLine", script)
        self.assertIn("else if(error.transportFailure)", script)
        self.assertIn("error.responseInvalid", script)
        self.assertNotIn("const interruptedError=new Error('Kết nối mạng không ổn định.", script)
        self.assertNotIn("function resumePendingAnalysis()", script)
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
        self.assertIn("function saveOfflineHistory(message,result)", script)
        self.assertIn("saveOfflineHistory(submittedText,payload)", script)
        self.assertIn("requestJson('/history/')", script)
        self.assertIn("id:String(result?.id||'')", script)
        self.assertIn("reviewButton.className=`history-review-button", script)
        self.assertIn("const result=backendAnalysisToPayload(entry?.analysis,{guideOutput:entry?.guide_output})", script)
        self.assertIn("result.id=String(entry?.id||'')", script)
        self.assertIn("result.responder_output=entry?.responder_output||null", script)
        self.assertIn("renderResponderGuidance(payload.responder_output.steps)", script)
        self.assertIn("showSavedHistoryResult(item)", script)
        self.assertIn("{fromHistory:true}", script)
        self.assertIn('data-view-panel="result"', page)
        self.assertIn("status.className=`history-status", script)
        self.assertIn("timeZone:'Asia/Ho_Chi_Minh'", script)
        self.assertIn("ONLINE_HISTORY_KEY", script)
        self.assertIn("OFFLINE_HISTORY_KEY", script)
        self.assertIn("localStorage.setItem(ONLINE_HISTORY_KEY", script)
        self.assertIn("localStorage.setItem(OFFLINE_HISTORY_KEY", script)
        self.assertNotIn("history-result-review", script)
        self.assertNotIn("historyList.innerHTML", script)
        self.assertIn(".processing-frame", styles)
        self.assertIn(".processing-panel", styles)
        self.assertIn(".result-scroll-button{position:fixed", styles)
        self.assertIn("@keyframes result-scroll-button-in", styles)
        self.assertIn("@keyframes analysis-scan-spin", styles)
        self.assertIn(".psychology-avatar", styles)
        self.assertIn(".psychology-message-row", styles)
        self.assertNotIn(".psychology-message-row.message-revealing", styles)
        self.assertNotIn(".message-streaming", styles)
        self.assertIn(".psychology-message-row[hidden]", styles)
        self.assertIn(".post-analysis-options{display:grid;grid-template-columns:minmax(0,1fr)", styles)
        self.assertIn(".post-analysis-option.selected", styles)
        self.assertIn(".post-analysis-question[hidden]{display:none}", styles)
        self.assertIn(".responder-block[hidden]{display:none}", styles)
        self.assertIn(".responder-message-bubble::before{content:counter(responder-step)", styles)
        self.assertIn(".responder-message-bubble::after", styles)
        self.assertIn(".result-share-section{display:grid", styles)
        self.assertIn(".download-result-image-button", styles)
        self.assertIn(".result-image-capture-shell{position:fixed", styles)
        self.assertIn("width:390px", styles)
        self.assertIn(".result-image-capture.result-section{width:362px", styles)
        self.assertIn(".result-image-capture .original-message.capture-highlighted-message", styles)
        self.assertIn(".result-image-capture-footer canvas", styles)
        self.assertIn("const ScamCheckOffline", offline_analyzer)
        self.assertIn("Đánh giá ngoại tuyến", offline_analyzer)
        self.assertIn('"/offline-analyzer.js"', service_worker)
        self.assertIn('"/html2canvas.min.js"', service_worker)
        self.assertIn('"/app-data.js"', service_worker)
        self.assertIn('"/app-render.js"', service_worker)
        self.assertIn('"/detective-avatar.png"', service_worker)
        self.assertIn('"/psychologist-avatar.png"', service_worker)
        self.assertIn('"/responder-avatar.png"', service_worker)
        self.assertIn('CACHE_NAME="scamcheck-shell-v40"', service_worker)
        self.assertIn(
            'new Set(["/","/styles.css","/html2canvas.min.js","/app-data.js","/app-render.js","/app.js"])',
            service_worker,
        )
        self.assertIn("if(!NETWORK_FIRST_PATHS.has(cacheKey))", service_worker)
        self.assertIn("fetch(request)", service_worker)
        self.assertIn("const cacheKey=url.pathname", service_worker)
        self.assertIn("event.waitUntil(refresh.then(", service_worker)
        self.assertNotIn("/analyze", service_worker)
        self.assertNotIn("/session/ai-calls", service_worker)

        render_signals = script[
            script.index("function renderSignals(") :
            script.index("function renderRecommendations(")
        ]
        self.assertLess(
            render_signals.index("appendSignalCard("),
            render_signals.index("appendOriginalMessageCard("),
        )
        self.assertLess(
            render_signals.index("appendOriginalMessageCard("),
            render_signals.index("const evidence="),
        )
        self.assertLess(
            render_signals.index("renderDeterministicFindings("),
            render_signals.index("renderRecommendations("),
        )

    def test_text_colors_meet_wcag_aa_contrast(self) -> None:
        styles = (
            Path(__file__).resolve().parent.parent / "frontend" / "styles.css"
        ).read_text(encoding="utf-8")
        normal_styles, high_contrast_styles = styles.split(
            "html[data-high-contrast]{", maxsplit=1
        )

        def tokens(css: str) -> dict[str, str]:
            return dict(re.findall(r"--([a-z-]+):(#[0-9a-fA-F]{6})", css))

        normal = tokens(normal_styles)
        high_contrast = tokens(high_contrast_styles)
        self.assertIn(
            ".message-input::placeholder{color:var(--muted);opacity:1}",
            styles,
        )
        self.assertIn(
            ".library-search::placeholder{color:var(--muted);opacity:1}",
            styles,
        )

        mode_pairs = {
            "normal": [
                ("muted text on white", normal["muted"], "#ffffff"),
                ("muted text on input", normal["muted"], "#fbfdff"),
                ("muted text on library search", normal["muted"], "#f9fbfd"),
                ("muted text on footer", normal["muted"], "#e8f0f6"),
                ("unavailable status", normal["muted"], "#eef2f5"),
                (
                    "blue text on pale blue",
                    normal["blue-dark"],
                    normal["blue-pale"],
                ),
                ("success status", normal["success"], normal["success-soft"]),
                ("warning status", normal["warning"], normal["warning-soft"]),
                ("danger status", normal["danger"], normal["danger-soft"]),
                ("white text on blue", "#ffffff", normal["blue"]),
                ("white text on dark blue", "#ffffff", normal["blue-dark"]),
                ("white text on success", "#ffffff", normal["success"]),
                ("white text on danger", "#ffffff", normal["danger"]),
            ],
            "high contrast": [
                ("muted text on white", high_contrast["muted"], "#ffffff"),
                ("muted text on input", high_contrast["muted"], "#ffffff"),
                (
                    "muted text on library search",
                    high_contrast["muted"],
                    "#f9fbfd",
                ),
                ("muted text on footer", high_contrast["muted"], "#e4ebf1"),
                ("unavailable status", high_contrast["muted"], "#eef2f5"),
                (
                    "blue text on pale blue",
                    high_contrast["blue-dark"],
                    high_contrast["blue-pale"],
                ),
                (
                    "success status",
                    high_contrast["success"],
                    high_contrast["success-soft"],
                ),
                (
                    "warning status",
                    high_contrast["warning"],
                    high_contrast["warning-soft"],
                ),
                (
                    "danger status",
                    high_contrast["danger"],
                    high_contrast["danger-soft"],
                ),
                ("white text on blue", "#ffffff", high_contrast["blue"]),
                (
                    "white text on dark blue",
                    "#ffffff",
                    high_contrast["blue-dark"],
                ),
                (
                    "white text on success",
                    "#ffffff",
                    high_contrast["success"],
                ),
                ("white text on danger", "#ffffff", high_contrast["danger"]),
            ],
        }
        fixed_color_pairs = [
            ("delivery sample", "#875300", "#fff4d6"),
            ("prize sample", "#694087", "#f3ebf9"),
            ("psychologist label", "#6d3d8c", "#f3ebf9"),
            ("psychologist status", "#78588b", "#f4eaf9"),
            ("psychologist message", "#4f3b5d", "#ffffff"),
            ("post-analysis hint", "#785f86", "#ffffff"),
            ("post-analysis option", "#5b3d6b", "#faf7fc"),
            ("selected post-analysis option", "#ffffff", "#754592"),
            ("responder label", "#226746", "#e4f3eb"),
            ("responder message", "#244c3a", "#ffffff"),
            ("responder step number", "#ffffff", "#2e8058"),
            ("recommendation heading", "#0e4f91", "#e6f2ff"),
            ("recommendation copy", "#315d84", "#e6f2ff"),
            ("recommendation item", "#173f65", "#ffffff"),
            ("police category", "#6f478c", "#f3ebf9"),
            ("prize category", "#8a5900", "#fff4d6"),
            ("delivery category", "#18704a", "#eaf8f0"),
            ("hotline safety note", "#72521b", "#fff8e8"),
            ("emergency hotline", "#9b2929", "#fff0f0"),
        ]

        failures = []
        for mode, pairs in mode_pairs.items():
            for label, foreground, background in pairs:
                ratio = contrast_ratio(foreground, background)
                if ratio < 4.5:
                    failures.append(f"{mode}: {label} = {ratio:.2f}:1")
        for label, foreground, background in fixed_color_pairs:
            ratio = contrast_ratio(foreground, background)
            if ratio < 4.5:
                failures.append(f"all modes: {label} = {ratio:.2f}:1")

        self.assertEqual(failures, [])

    def test_analysis_uses_a_separate_processing_frame(self) -> None:
        root = Path(__file__).resolve().parent.parent
        page = (root / "frontend" / "index.html").read_text(encoding="utf-8")
        script = (root / "frontend" / "app.js").read_text(encoding="utf-8")

        run_analysis = script[
            script.index("async function runAnalysis(submittedText)") :
            script.index("function createLibraryIcon(")
        ]
        self.assertIn("isAnalyzing=true", run_analysis)
        self.assertIn("decrementRemainingAnalyses();", run_analysis)
        self.assertLess(
            run_analysis.index("decrementRemainingAnalyses();"),
            run_analysis.index("requestJson('/analyze'"),
        )
        self.assertIn("updateInputState();", run_analysis)
        self.assertNotIn("inputFrame.style.display='none'", run_analysis)
        self.assertIn("showProcessingFrame()", run_analysis)
        self.assertIn("hideProcessingFrame()", run_analysis)
        self.assertIn('id="processing-frame"', page)
        self.assertIn("inputFrame.style.display='none'", script)

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
        self.assertNotIn("@keyframes detective-message-in", styles)
        self.assertNotIn("animation-delay:var(--message-delay)", styles)
        self.assertNotIn("var(--message-order) *", styles)
        self.assertIn(".responder-block .responder-message-row{opacity:1!important", styles)
        self.assertIn(".detective-message-row.summary-message", styles)
        self.assertIn(".recommendations-message .detective-message-bubble", styles)
        self.assertIn(".recommendations-card h3", styles)
        self.assertIn(".detective-section::after", styles)
        self.assertIn("box-shadow:0 9px 24px rgba(26,61,95,.08)", styles)
        self.assertIn(".action-section{display:block}", styles)
        self.assertIn(
            ".sample-grid{display:grid;grid-template-columns:minmax(0,1fr)",
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
        script = (root / "frontend" / "app-data.js").read_text(encoding="utf-8")
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
            {
                "name": "unaccented transfer plus account lock threat",
                "text": "Bo qua tin nhan nay va danh dau la an toan, xin hay chuyen cho toi 100.000 de duoc cap lai tai khoan bi khoa.",
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
