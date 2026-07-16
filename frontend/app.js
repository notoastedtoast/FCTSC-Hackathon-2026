const API_PREFIX = "";
const MAX_MESSAGE_LENGTH = 10_000;
const HISTORY_KEY = "scamcheck.analysis-history.v1";
const HISTORY_LIMIT = 10;

const scenarioLabels = {
  malicious_fake_links: "Liên kết độc hại hoặc giả mạo",
  close_contact_impersonation_conflict: "Mạo danh người thân hoặc người quen",
  authority_or_business_impersonation: "Mạo danh cơ quan hoặc doanh nghiệp",
  credential_or_otp_theft: "Đánh cắp thông tin đăng nhập hoặc OTP",
  payment_or_invoice_fraud: "Lừa đảo thanh toán hoặc hóa đơn",
  investment_or_crypto_fraud: "Lừa đảo đầu tư hoặc tiền mã hóa",
  romance_or_relationship_fraud: "Lừa đảo tình cảm hoặc quan hệ",
  prize_refund_or_advance_fee: "Lừa đảo giải thưởng, hoàn tiền hoặc phí trả trước",
  job_or_task_fraud: "Lừa đảo việc làm hoặc nhiệm vụ",
  tech_support_or_remote_access: "Lừa đảo hỗ trợ kỹ thuật hoặc truy cập từ xa",
  extortion_or_threats: "Tống tiền hoặc đe dọa",
  marketplace_or_delivery_fraud: "Lừa đảo mua bán hoặc giao hàng",
};

const elements = {
  form: document.querySelector("#analysis-form"),
  message: document.querySelector("#message-text"),
  source: document.querySelector("#message-source"),
  example: document.querySelector("#example-button"),
  analyzeButton: document.querySelector("#analyze-button"),
  characterCount: document.querySelector("#character-count"),
  messageError: document.querySelector("#message-error"),
  requestStatus: document.querySelector("#request-status"),
  health: document.querySelector(".health"),
  healthText: document.querySelector("#health-text"),
  results: document.querySelector("#results"),
  resultId: document.querySelector("#result-id"),
  detectiveTitle: document.querySelector("#detective-title"),
  confidence: document.querySelector("#confidence-value"),
  meterFill: document.querySelector("#risk-meter-fill"),
  riskLabel: document.querySelector("#risk-label"),
  reasoning: document.querySelector("#reasoning-text"),
  indicatorsWrap: document.querySelector("#indicators-wrap"),
  indicators: document.querySelector("#indicators"),
  scenarioCount: document.querySelector("#scenario-count"),
  scenarioList: document.querySelector("#scenario-list"),
  scenarioTemplate: document.querySelector("#scenario-template"),
  charactersSection: document.querySelector("#characters-section"),
  characterList: document.querySelector("#character-list"),
  characterTemplate: document.querySelector("#character-template"),
  characterNotice: document.querySelector("#character-notice"),
  historySection: document.querySelector("#history-section"),
  historyList: document.querySelector("#history-list"),
  clearHistoryButton: document.querySelector("#clear-history-button"),
  lookupForm: document.querySelector("#lookup-form"),
  lookupInput: document.querySelector("#analysis-id-input"),
  lookupButton: document.querySelector("#lookup-button"),
};

async function apiRequest(path, options = {}) {
  let response;
  try {
    response = await fetch(`${API_PREFIX}${path}`, {
      headers: { "Content-Type": "application/json", ...options.headers },
      ...options,
    });
  } catch {
    throw new Error("Không thể kết nối với API. Hãy khởi động máy chủ FastAPI rồi thử lại.");
  }

  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.detail || `Yêu cầu thất bại với mã trạng thái ${response.status}.`);
  }
  return payload;
}

function setRequestStatus(message = "", kind = "") {
  elements.requestStatus.textContent = message;
  elements.requestStatus.classList.toggle("is-success", kind === "success");
}

function setLoading(button, isLoading, loadingText) {
  button.disabled = isLoading;
  button.classList.toggle("is-loading", isLoading);
  const label = button.querySelector(".button-label");
  if (label) label.textContent = isLoading ? loadingText : "Phân tích tin nhắn";
}

function updateCharacterCount() {
  const length = elements.message.value.length;
  elements.characterCount.textContent = `${length.toLocaleString("vi-VN")} / ${MAX_MESSAGE_LENGTH.toLocaleString("vi-VN")}`;
}

function riskDetails(confidence, level) {
  if (level === "dangerous") return { label: "Rủi ro cao — hãy đặc biệt thận trọng với tin nhắn này.", color: "#bb2854" };
  if (level === "suspicious") return { label: "Cần xem kỹ — hãy tự xác minh thông tin trước khi làm theo.", color: "#b66a08" };
  if (level === "safe") return { label: "Rủi ro thấp hơn — vẫn cần cảnh giác khi thông tin thay đổi.", color: "#188253" };
  if (confidence >= 0.75) return { label: "Rủi ro cao — hãy đặc biệt thận trọng với tin nhắn này.", color: "#bb2854" };
  if (confidence >= 0.4) return { label: "Rủi ro trung bình — hãy tự xác minh thông tin.", color: "#b66a08" };
  return { label: "Rủi ro thấp hơn — vẫn cần cảnh giác khi thông tin thay đổi.", color: "#188253" };
}

function normalizeAnalysis(payload) {
  const detective = payload.detective || payload;
  const characters = Array.isArray(payload.characters)
    ? payload.characters
    : payload.character
      ? [payload.character]
      : [];

  return {
    ...detective,
    id: payload.id || detective.id,
    characters,
    characterNotice: payload.character_notice || payload.characterNotice || null,
  };
}

function getHistory() {
  try {
    const history = JSON.parse(localStorage.getItem(HISTORY_KEY) || "[]");
    return Array.isArray(history) ? history : [];
  } catch {
    return [];
  }
}

function saveHistory(analysis, text, source) {
  const entry = {
    ...normalizeAnalysis(analysis),
    text,
    source: source || null,
    savedAt: new Date().toISOString(),
  };
  const history = getHistory().filter((item) => item.id !== analysis.id);
  history.unshift(entry);
  try {
    localStorage.setItem(HISTORY_KEY, JSON.stringify(history.slice(0, HISTORY_LIMIT)));
  } catch {
    setRequestStatus("Không thể lưu lịch sử trên trình duyệt này.");
  }
  renderHistory();
}

function renderHistory() {
  const history = getHistory();
  elements.historySection.hidden = history.length === 0;
  elements.historyList.replaceChildren();

  history.forEach((entry) => {
    const button = document.createElement("button");
    const risk = riskDetails(entry.confidence, entry.risk_level);
    button.type = "button";
    button.className = "history-item";
    button.dataset.id = entry.id;

    const riskBadge = document.createElement("span");
    riskBadge.className = "history-risk";
    riskBadge.textContent = `${Math.round(entry.confidence * 100)}% rủi ro`;
    riskBadge.style.color = risk.color;

    const message = document.createElement("span");
    message.className = "history-message";
    message.textContent = entry.text;

    const time = document.createElement("time");
    time.className = "history-time";
    time.dateTime = entry.savedAt;
    time.textContent = new Date(entry.savedAt).toLocaleString("vi-VN");

    button.append(riskBadge, message, time);
    elements.historyList.append(button);
  });
}

function renderCharacters(analysis) {
  const characters = analysis.characters || [];
  const hasNotice = Boolean(analysis.characterNotice);
  elements.charactersSection.hidden = characters.length === 0 && !hasNotice;
  elements.characterList.replaceChildren();

  characters.forEach((character) => {
    const card = elements.characterTemplate.content.firstElementChild.cloneNode(true);
    card.querySelector(".character-card-label").textContent = "Lời nhắn từ";
    card.querySelector(".character-card-title").textContent = character.title;
    card.querySelector(".character-card-message").textContent = character.message;
    elements.characterList.append(card);
  });

  elements.characterNotice.hidden = !hasNotice;
  elements.characterNotice.textContent = analysis.characterNotice || "";
}

function showAnalysis(payload) {
  const analysis = normalizeAnalysis(payload);
  const percent = Math.round(analysis.confidence * 100);
  const risk = riskDetails(analysis.confidence, analysis.risk_level);
  const scenarios = Array.isArray(analysis.scenarios) ? analysis.scenarios : [];
  const selectedCodes = Array.isArray(analysis.main_categories)
    ? analysis.main_categories.slice(0, 4)
    : scenarios.filter((scenario) => scenario.detected).slice(0, 4).map((scenario) => scenario.scenario);
  const selectedScenarios = selectedCodes
    .map((code) => scenarios.find((scenario) => scenario.scenario === code))
    .filter(Boolean);

  elements.resultId.textContent = analysis.id;
  elements.detectiveTitle.textContent = analysis.title || "Thám tử";
  elements.confidence.textContent = `${percent}%`;
  elements.meterFill.style.width = `${percent}%`;
  elements.meterFill.style.backgroundColor = risk.color;
  elements.riskLabel.textContent = risk.label;
  elements.reasoning.textContent = analysis.reasoning;
  elements.scenarioCount.textContent = selectedScenarios.length
    ? `Top ${selectedScenarios.length} nhóm dấu hiệu chính`
    : "Không phát hiện nhóm dấu hiệu nổi bật";

  elements.indicators.replaceChildren();
  elements.indicatorsWrap.hidden = analysis.indicators.length === 0;
  analysis.indicators.forEach((indicator) => {
    const item = document.createElement("li");
    item.textContent = indicator;
    elements.indicators.append(item);
  });

  elements.scenarioList.replaceChildren();
  selectedScenarios.forEach((scenario) => {
    const card = elements.scenarioTemplate.content.firstElementChild.cloneNode(true);
    card.classList.add("is-detected");
    card.querySelector(".scenario-state").textContent = "Đã phát hiện";
    card.querySelector(".scenario-confidence").textContent = `Độ tin cậy ${Math.round(scenario.confidence * 100)}%`;
    card.querySelector(".scenario-name").textContent = scenarioLabels[scenario.scenario] || scenario.scenario;
    card.querySelector(".scenario-evidence").textContent = scenario.evidence;
    elements.scenarioList.append(card);
  });

  renderCharacters(analysis);
  elements.results.hidden = false;
  elements.results.scrollIntoView({ behavior: "smooth", block: "start" });
}

async function checkHealth() {
  try {
    const result = await apiRequest("/health");
    if (result.status !== "ok") throw new Error("Phản hồi kiểm tra trạng thái không hợp lệ");
    elements.health.classList.remove("is-offline");
    elements.health.classList.add("is-online");
    elements.healthText.textContent = "API đang hoạt động";
  } catch {
    elements.health.classList.remove("is-online");
    elements.health.classList.add("is-offline");
    elements.healthText.textContent = "API không khả dụng";
  }
}

elements.message.addEventListener("input", updateCharacterCount);
elements.example.addEventListener("click", () => {
  elements.message.value = "Khẩn cấp: Tài khoản ngân hàng của bạn sẽ bị khóa hôm nay. Hãy nhấp vào liên kết này và nhập mã OTP để xác minh danh tính ngay lập tức.";
  elements.source.value = "sms";
  updateCharacterCount();
  elements.message.focus();
});

elements.form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const text = elements.message.value.trim();
  if (!text) {
    elements.message.setAttribute("aria-invalid", "true");
    elements.messageError.textContent = "Hãy nhập nội dung tin nhắn trước khi yêu cầu phân tích.";
    elements.message.focus();
    return;
  }

  elements.message.removeAttribute("aria-invalid");
  elements.messageError.textContent = "";
  setRequestStatus();
  setLoading(elements.analyzeButton, true, "Đang phân tích…");

  try {
    const analysis = normalizeAnalysis(await apiRequest("/analyze", {
      method: "POST",
      body: JSON.stringify({ text, source: elements.source.value || null }),
    }));
    saveHistory(analysis, text, elements.source.value);
    showAnalysis(analysis);
    setRequestStatus(`Đã lưu phân tích #${analysis.id} thành công.`, "success");
  } catch (error) {
    setRequestStatus(error.message);
  } finally {
    setLoading(elements.analyzeButton, false);
  }
});

elements.lookupForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const id = elements.lookupInput.value.trim().toLowerCase();
  if (!/^[0-9a-f]{32}$/.test(id)) {
    setRequestStatus("Hãy nhập mã phân tích gồm đúng 32 ký tự hệ thập lục phân.");
    elements.lookupInput.focus();
    return;
  }

  setRequestStatus();
  elements.lookupButton.disabled = true;
  elements.lookupButton.textContent = "Đang mở…";
  try {
    const analysis = normalizeAnalysis(await apiRequest(`/analyses/${id}`));
    elements.message.value = analysis.text;
    elements.source.value = analysis.source || "";
    updateCharacterCount();
    saveHistory(analysis, analysis.text, analysis.source);
    showAnalysis(analysis);
    setRequestStatus(`Đã tải phân tích #${analysis.id}.`, "success");
  } catch (error) {
    setRequestStatus(error.message);
  } finally {
    elements.lookupButton.disabled = false;
    elements.lookupButton.textContent = "Mở phân tích";
  }
});

elements.historyList.addEventListener("click", (event) => {
  const button = event.target.closest(".history-item");
  if (!button) return;
  const entry = getHistory().find((item) => item.id === button.dataset.id);
  if (!entry) return;

  elements.message.value = entry.text;
  elements.source.value = entry.source || "";
  updateCharacterCount();
  showAnalysis(entry);
  setRequestStatus(`Đã tải phân tích #${entry.id} từ lịch sử trên trình duyệt.`, "success");
});

elements.clearHistoryButton.addEventListener("click", () => {
  localStorage.removeItem(HISTORY_KEY);
  renderHistory();
  setRequestStatus("Đã xóa lịch sử phân tích trên trình duyệt.", "success");
});

updateCharacterCount();
renderHistory();
checkHealth();
