const state = { notices: [], group: "all" };
const labels = {
  all: "전체 공고",
  today: "오늘 새로 등록된 공고",
  ulsan_city: "울산시 공고",
  ulsan_districts: "5개 구·군 공고",
  ulsan_education: "교육청 공고",
  nationwide: "전국 공고",
};

function isToday(value) {
  const date = parseKoreanDate(value);
  if (!date) return false;
  const formatter = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Seoul", year: "numeric", month: "2-digit", day: "2-digit",
  });
  return formatter.format(date) === formatter.format(new Date());
}

function parseKoreanDate(value) {
  if (!value) return null;
  const normalized = String(value).replace(" ", "T");
  const parsed = new Date(normalized.includes("+") || normalized.endsWith("Z") ? normalized : `${normalized}+09:00`);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

function dday(deadline) {
  const end = parseKoreanDate(deadline);
  if (!end) return { value: "-", days: 999, expired: false };
  const now = new Date();
  const milliseconds = end.getTime() - now.getTime();
  if (milliseconds < 0) return { value: "마감", days: -1, expired: true };
  const days = Math.ceil(milliseconds / 86400000);
  return { value: days === 0 ? "오늘" : `D-${days}`, days, expired: false };
}

function formatDate(value, withTime = false) {
  const date = parseKoreanDate(value);
  if (!date) return "미정";
  return new Intl.DateTimeFormat("ko-KR", {
    timeZone: "Asia/Seoul",
    month: "long", day: "numeric",
    ...(withTime ? { hour: "2-digit", minute: "2-digit", hour12: false } : {}),
  }).format(date);
}

function formatPrice(value) {
  const amount = Number(value);
  return Number.isFinite(amount) && amount > 0 ? `${amount.toLocaleString("ko-KR")}원` : "금액 미정";
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>'"]/g, char => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;",
  })[char]);
}

function visibleNotices() {
  return state.notices
    .filter(notice => {
      const active = !dday(notice.closedAt).expired;
      const groupMatch = state.group === "all"
        || (state.group === "today" && isToday(notice.publishedAt))
        || notice.matches?.groupIds?.includes(state.group);
      return active && groupMatch;
    })
    .sort((a, b) => {
      const aDate = parseKoreanDate(a.closedAt)?.getTime() ?? Number.MAX_SAFE_INTEGER;
      const bDate = parseKoreanDate(b.closedAt)?.getTime() ?? Number.MAX_SAFE_INTEGER;
      return aDate - bDate;
    });
}

function render() {
  const notices = visibleNotices();
  const list = document.querySelector("#noticeList");
  document.querySelector("#currentLabel").textContent = labels[state.group];
  document.querySelector("#visibleCount").textContent = notices.length;
  document.querySelector("#emptyState").hidden = notices.length !== 0;

  list.innerHTML = notices.map(notice => {
    const due = dday(notice.closedAt);
    const urgency = due.days <= 5 ? "urgent" : due.days <= 10 ? "soon" : "";
    const todayTag = isToday(notice.publishedAt) ? '<span class="tag today-tag">오늘 등록</span>' : '';
    const tags = todayTag + (notice.matches?.labels || []).map(label => `<span class="tag">${escapeHtml(label)}</span>`).join("");
    return `
      <article class="notice-card">
        <div class="dday ${urgency}" aria-label="마감 ${escapeHtml(due.value)}">
          <span>마감</span><strong>${escapeHtml(due.value)}</strong>
        </div>
        <div class="notice-main">
          <div class="meta">${tags}<span class="category">${notice.category === "services" ? "용역" : escapeHtml(notice.category)}</span></div>
          <h3>${escapeHtml(notice.title || "제목 없는 공고")}</h3>
          <div class="details">
            <span><strong>수요기관</strong> ${escapeHtml(notice.demandInstitution || notice.noticeInstitution || "미확인")}</span>
            <span><strong>마감</strong> ${formatDate(notice.closedAt, true)}</span>
            <span><strong>추정금액</strong> ${formatPrice(notice.estimatedPrice)}</span>
          </div>
        </div>
        <a class="view-link" href="${escapeHtml(notice.detailUrl || "https://www.g2b.go.kr/")}" target="_blank" rel="noopener noreferrer">공고 보기</a>
      </article>`;
  }).join("");
}

function updateCounts() {
  const active = state.notices.filter(notice => !dday(notice.closedAt).expired);
  document.querySelector("#count-all").textContent = active.length;
  document.querySelector("#count-today").textContent = active.filter(notice => isToday(notice.publishedAt)).length;
  Object.keys(labels).filter(group => group !== "all").forEach(group => {
    if (group === "today") return;
    const count = active.filter(notice => notice.matches?.groupIds?.includes(group)).length;
    document.querySelector(`#count-${group}`).textContent = count;
  });
}

function bindFilters() {
  document.querySelectorAll(".filter").forEach(button => {
    button.addEventListener("click", () => {
      state.group = button.dataset.group;
      document.querySelectorAll(".filter").forEach(item => {
        const selected = item === button;
        item.classList.toggle("active", selected);
        item.setAttribute("aria-pressed", String(selected));
      });
      render();
    });
  });
}

async function load() {
  document.querySelector("#todayText").textContent = new Intl.DateTimeFormat("ko-KR", {
    timeZone: "Asia/Seoul", year: "numeric", month: "long", day: "numeric", weekday: "short",
  }).format(new Date());
  bindFilters();
  try {
    const response = await fetch("data/bids.json", { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    state.notices = Array.isArray(data.notices) ? data.notices : [];
    const generated = data.meta?.generatedAt ? new Date(data.meta.generatedAt) : null;
    document.querySelector("#syncText").textContent = generated
      ? `최근 수집 ${new Intl.DateTimeFormat("ko-KR", { timeZone: "Asia/Seoul", hour: "2-digit", minute: "2-digit", hour12: false }).format(generated)}`
      : "수집 시간 미확인";
    const sourceBadge = document.querySelector("#sourceBadge");
    const isMock = data.meta?.source === "mock";
    sourceBadge.textContent = isMock ? "모의 데이터" : "나라장터 데이터";
    sourceBadge.classList.toggle("live", !isMock);
    updateCounts();
    render();
  } catch (error) {
    console.error(error);
    document.querySelector("#noticeList").hidden = true;
    document.querySelector("#errorState").hidden = false;
    document.querySelector("#sourceBadge").textContent = "연결 오류";
  }
}

load();
