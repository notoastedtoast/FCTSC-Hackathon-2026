const form = document.querySelector("#analysis-form");
const analyzeButton = document.querySelector("#analyze-button");
const formStatus = document.querySelector("#form-status");
const results = document.querySelector("#results");
const riskBadge = document.querySelector("#risk-badge");
const detectiveReasoning = document.querySelector("#detective-reasoning");
const detectiveIndicators = document.querySelector("#detective-indicators");
const detectiveActions = document.querySelector("#detective-actions");
const psychologyMessage = document.querySelector("#psychology-message");

const riskLabels = {
  safe: "An toàn",
  suspicious: "Nghi ngờ",
  dangerous: "Nguy hiểm",
};

function replaceList(list, values, emptyText) {
  list.replaceChildren();
  const items = values.length ? values : [emptyText];
  for (const value of items) {
    const item = document.createElement("li");
    item.textContent = value;
    list.append(item);
  }
}

function renderAnalysis(payload) {
  const detective = payload.detective;
  riskBadge.textContent = riskLabels[detective.risk_level] ?? detective.risk_level;
  riskBadge.dataset.risk = detective.risk_level;
  detectiveReasoning.textContent = detective.reasoning;

  const indicators = detective.indicator_evidence?.length
    ? detective.indicator_evidence.map(
        (item) => `${item.label}: “${item.excerpt}”`,
      )
    : detective.indicators ?? [];
  replaceList(detectiveIndicators, indicators, "Chưa thấy dấu hiệu cụ thể.");
  replaceList(detectiveActions, detective.actions ?? [], "Tự kiểm tra qua kênh chính thức.");

  if (payload.character) {
    psychologyMessage.textContent = payload.character.message;
  } else if (payload.character_notice) {
    psychologyMessage.textContent = payload.character_notice;
  } else {
    psychologyMessage.textContent =
      "Tin được đánh giá an toàn nên bước Cô tâm lý không được kích hoạt.";
  }

  results.hidden = false;
  results.scrollIntoView({ behavior: "smooth", block: "start" });
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const text = document.querySelector("#message").value;
  const source = document.querySelector("#source").value;
  analyzeButton.disabled = true;
  formStatus.textContent =
    "Thám tử đang phân tích. Cô tâm lý sẽ chờ kết luận trước khi được gọi...";

  try {
    const response = await fetch("/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, ...(source ? { source } : {}) }),
    });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.detail || "Không thể kiểm tra tin nhắn lúc này.");
    }
    renderAnalysis(payload);
    formStatus.textContent = "Đã hoàn tất hai bước kiểm tra cần thiết.";
  } catch (error) {
    formStatus.textContent = error.message || "Không thể kết nối tới máy chủ.";
  } finally {
    analyzeButton.disabled = false;
  }
});

const libraryGrid = document.querySelector("#library-grid");
const libraryStatus = document.querySelector("#library-status");
const filters = document.querySelector("#library-filters");
const dialog = document.querySelector("#scam-dialog");
const closeDialog = document.querySelector("#dialog-close");
let library = [];
let activeFilter = "all";

function fillDialog(entry) {
  document.querySelector("#dialog-group").textContent = entry.group_label;
  document.querySelector("#dialog-title").textContent = entry.title;
  document.querySelector("#dialog-summary").textContent = entry.summary;
  replaceList(document.querySelector("#dialog-signs"), entry.signs, "Chưa có dữ liệu.");
  replaceList(document.querySelector("#dialog-actions"), entry.actions, "Dừng lại và xác minh.");
  dialog.showModal();
}

function renderLibrary() {
  libraryGrid.replaceChildren();
  const visible = library.filter(
    (entry) => activeFilter === "all" || entry.group === activeFilter,
  );

  for (const entry of visible) {
    const card = document.createElement("button");
    card.type = "button";
    card.className = "library-card";
    card.addEventListener("click", () => fillDialog(entry));

    const group = document.createElement("span");
    group.className = "library-card-group";
    group.textContent = entry.group_label;
    const title = document.createElement("strong");
    title.textContent = entry.title;
    const summary = document.createElement("span");
    summary.textContent = entry.summary;
    const action = document.createElement("span");
    action.className = "library-card-action";
    action.textContent = "Xem chi tiết →";
    card.append(group, title, summary, action);
    libraryGrid.append(card);
  }

  libraryStatus.textContent = `Đang hiển thị ${visible.length} kiểu lừa đảo.`;
}

filters.addEventListener("click", (event) => {
  const button = event.target.closest("[data-filter]");
  if (!button) return;
  activeFilter = button.dataset.filter;
  for (const filterButton of filters.querySelectorAll("[data-filter]")) {
    const isActive = filterButton === button;
    filterButton.classList.toggle("is-active", isActive);
    filterButton.setAttribute("aria-pressed", String(isActive));
  }
  renderLibrary();
});

closeDialog.addEventListener("click", () => dialog.close());
dialog.addEventListener("click", (event) => {
  if (event.target === dialog) dialog.close();
});

fetch("/scam-library.json")
  .then((response) => {
    if (!response.ok) throw new Error("Không tải được thư viện.");
    return response.json();
  })
  .then((entries) => {
    library = entries;
    renderLibrary();
  })
  .catch(() => {
    libraryStatus.textContent = "Thư viện tạm thời chưa tải được. Bác thử lại sau nhé.";
  });
