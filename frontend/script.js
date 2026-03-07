const API_BASE = "";   // relative — always matches the serving host

// ── Category metadata ─────────────────────────────────────────────────────────

const CATEGORY_META = {
  geopolitical:        { emoji: "🌍", label: "Geopolitical",       color: "#e53e3e" },
  finance_economy:     { emoji: "💰", label: "Finance & Economy",  color: "#38a169" },
  markets_crypto:      { emoji: "📈", label: "Markets & Crypto",   color: "#00b5d8" },
  climate_environment: { emoji: "🌡️", label: "Climate & Env",      color: "#2c7a7b" },
  technology_ai:       { emoji: "🤖", label: "Technology & AI",    color: "#3182ce" },
  health_science:      { emoji: "🏥", label: "Health & Science",   color: "#d53f8c" },
  energy_resources:    { emoji: "⚡", label: "Energy & Resources", color: "#dd6b20" },
  politics_policy:     { emoji: "🏛️", label: "Politics & Policy",  color: "#805ad5" },
  innovation_space:    { emoji: "🚀", label: "Innovation & Space", color: "#553c9a" },
  culture_society:     { emoji: "🎭", label: "Culture & Society",  color: "#d69e2e" },
};

const CATEGORY_ORDER = Object.keys(CATEGORY_META);

// ── DOM refs ──────────────────────────────────────────────────────────────────

const searchInput    = document.getElementById("searchInput");
const searchBtn      = document.getElementById("searchBtn");
const loader         = document.getElementById("loader");
const loaderText     = document.getElementById("loaderText");
const statusFeed     = document.getElementById("statusFeed");
const errorBox       = document.getElementById("errorBox");
const heroSection    = document.getElementById("heroSection");
const heroText       = document.getElementById("heroText");
const topicResult    = document.getElementById("topicResult");
const topicCard      = document.getElementById("topicCard");
const categoryGrid   = document.getElementById("categoryGrid");
const gridContainer  = document.getElementById("gridContainer");
const progressBar    = document.getElementById("progressBar");
const progressFill   = document.getElementById("progressFill");
const livePulse      = document.getElementById("livePulse");
const refreshBtn     = document.getElementById("refreshBtn");
const lastUpdated    = document.getElementById("lastUpdated");

// ── Progress bar ──────────────────────────────────────────────────────────────

function startProgress() {
  progressFill.style.width = "0%";
  progressFill.style.transition = "none";
  progressBar.classList.remove("hidden");
  livePulse.classList.remove("hidden");
  refreshBtn.classList.add("spinning");
}

function setProgress(pct) {
  progressFill.style.transition = "width 0.4s ease";
  progressFill.style.width = Math.min(pct, 100) + "%";
}

function completeProgress() {
  setProgress(100);
  setTimeout(() => {
    progressBar.classList.add("hidden");
    livePulse.classList.remove("hidden");  // keep pulse dot visible
    refreshBtn.classList.remove("spinning");
  }, 1200);
}

// ── Skeleton loaders ──────────────────────────────────────────────────────────

function skeletonCardHTML(catKey) {
  const meta = CATEGORY_META[catKey] || { emoji: "○", label: catKey, color: "#4a5568" };
  return `
    <div class="card card-skeleton" data-category="${catKey}" style="--card-accent: ${meta.color}; --card-accent-glow: ${meta.color}33">
      <div class="card-header">
        <div class="card-title-group">
          <span class="skeleton-emoji">${meta.emoji}</span>
          <span class="skeleton-title">${meta.label}</span>
        </div>
      </div>
      <div class="skeleton-line"></div>
      <div class="skeleton-line short"></div>
      <div class="skeleton-line"></div>
      <div class="skeleton-line short"></div>
    </div>`;
}

function renderSkeletons() {
  gridContainer.innerHTML = CATEGORY_ORDER.map(skeletonCardHTML).join("");
}

// ── Card builders ─────────────────────────────────────────────────────────────

function sentimentClass(s) {
  return "sentiment-" + (["positive", "negative", "mixed", "neutral"].includes(s) ? s : "neutral");
}

// Category card for the bento grid
function buildCategoryCard(catKey, data) {
  const meta = CATEGORY_META[catKey] || { emoji: "○", label: catKey, color: "#4a5568" };
  const kpHtml = (data.key_points || []).map(p => `<li>${p}</li>`).join("");
  const artHtml = (data.articles || []).slice(0, 4).map(a => `
    <a class="article-link" href="${a.url}" target="_blank" rel="noopener">
      <span class="source-tag">[${a.source}]</span>${a.title}
    </a>`).join("");

  return `
    <div class="card" data-category="${catKey}"
         style="--card-accent: ${meta.color}; --card-accent-glow: ${meta.color}33">
      <div class="card-header">
        <div class="card-title-group">
          <span class="card-emoji">${meta.emoji}</span>
          <span class="card-title">${meta.label}</span>
        </div>
        <div style="display:flex; align-items:center; gap:0.5rem">
          <span class="sentiment-badge ${sentimentClass(data.sentiment)}">${data.sentiment || "neutral"}</span>
          <span class="article-count-badge">${data.article_count || 0}</span>
        </div>
      </div>
      <p class="card-summary">${data.summary || ""}</p>
      ${kpHtml ? `<ul class="key-points">${kpHtml}</ul>` : ""}
      ${artHtml ? `<div class="article-links"><h4>Related Articles</h4>${artHtml}</div>` : ""}
    </div>`;
}

// Topic search card (simpler, no emoji metadata)
function buildCard(title, data) {
  const kpHtml = (data.key_points || []).map(p => `<li>${p}</li>`).join("");
  const artHtml = (data.articles || []).slice(0, 4).map(a => `
    <a class="article-link" href="${a.url}" target="_blank" rel="noopener">
      <span class="source-tag">[${a.source}]</span>${a.title}
    </a>`).join("");

  return `
    <div class="card">
      <div class="card-header">
        <span class="card-title">${title}</span>
        <span class="sentiment-badge ${sentimentClass(data.sentiment)}">${data.sentiment || "neutral"}</span>
      </div>
      <p class="card-summary">${data.summary || ""}</p>
      ${kpHtml ? `<ul class="key-points">${kpHtml}</ul>` : ""}
      ${artHtml ? `<div class="article-links"><h4>Related Articles</h4>${artHtml}</div>` : ""}
      <p class="article-count">${data.article_count || 0} articles analysed</p>
    </div>`;
}

// ── Live card reveal (skeleton → real) ───────────────────────────────────────

function swapCardInGrid(catKey, data) {
  const existing = gridContainer.querySelector(`[data-category="${catKey}"]`);
  const newHTML = buildCategoryCard(catKey, data);

  if (existing) {
    const temp = document.createElement("div");
    temp.innerHTML = newHTML;
    const newCard = temp.firstElementChild;
    newCard.classList.add("card-reveal");
    existing.replaceWith(newCard);
    // Trigger reflow then add visible class for fade-in
    requestAnimationFrame(() => {
      requestAnimationFrame(() => newCard.classList.add("card-visible"));
    });
  } else {
    // Category not in the grid yet — append
    const temp = document.createElement("div");
    temp.innerHTML = newHTML;
    const newCard = temp.firstElementChild;
    newCard.classList.add("card-reveal");
    gridContainer.appendChild(newCard);
    requestAnimationFrame(() => {
      requestAnimationFrame(() => newCard.classList.add("card-visible"));
    });
  }
}

// ── Auto-load overview ────────────────────────────────────────────────────────

function loadOverview() {
  resetResults();
  startProgress();
  renderSkeletons();
  errorBox.classList.add("hidden");

  let streamCompleted = false;
  const total = CATEGORY_ORDER.length;
  let fetchedCount = 0;
  let summarizedCount = 0;

  const es = new EventSource(`${API_BASE}/api/overview/stream`);

  es.onmessage = (event) => {
    let data;
    try { data = JSON.parse(event.data); } catch { return; }

    if (data.status === "start") {
      // nothing extra needed

    } else if (data.status === "fetching") {
      // noop — skeleton cards already shown

    } else if (data.status === "fetched") {
      fetchedCount++;
      const pct = data.progress != null ? data.progress : Math.round(fetchedCount / total * 50);
      setProgress(pct);

    } else if (data.status === "summarizing") {
      // noop

    } else if (data.status === "summarized" && data.data) {
      summarizedCount++;
      swapCardInGrid(data.source, data.data);
      const pct = data.progress != null ? data.progress : 50 + Math.round(summarizedCount / total * 40);
      setProgress(pct);

    } else if (data.status === "complete") {
      streamCompleted = true;
      es.close();

      // Update hero section with overall digest (strip markdown heading/bold markers)
      if (data.data && data.data.overall_digest) {
        const cleaned = data.data.overall_digest
          .replace(/^#{1,4}\s+.+\n+/m, "")    // remove first heading line
          .replace(/#{1,4}\s+/g, "")           // remove any remaining heading markers
          .replace(/\*\*(.+?)\*\*/g, "$1")     // remove **bold** markers
          .trim();
        heroText.textContent = cleaned;
        heroSection.classList.remove("hidden");
      }

      // Swap any remaining skeletons with final data (fallback)
      if (data.data && data.data.categories) {
        for (const [key, val] of Object.entries(data.data.categories)) {
          const el = gridContainer.querySelector(`[data-category="${key}"]`);
          if (el && el.classList.contains("card-skeleton")) {
            swapCardInGrid(key, val);
          }
        }
      }

      completeProgress();
      lastUpdated.textContent = `Updated ${new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`;
    }
  };

  es.onerror = () => {
    es.close();
    if (!streamCompleted) {
      showError("Connection failed. Is the server running?");
      refreshBtn.classList.remove("spinning");
      livePulse.classList.add("hidden");
      progressBar.classList.add("hidden");
    }
  };
}

// ── Refresh button ────────────────────────────────────────────────────────────

refreshBtn.addEventListener("click", () => {
  if (!refreshBtn.classList.contains("spinning")) {
    loadOverview();
  }
});

// ── Topic search ──────────────────────────────────────────────────────────────

function doSearch() {
  const q = searchInput.value.trim();
  if (!q) return;

  // Hide hero + topic result but keep the grid
  heroSection.classList.add("hidden");
  topicResult.classList.add("hidden");
  errorBox.classList.add("hidden");
  topicCard.innerHTML = "";
  searchBtn.disabled = true;

  openStream(`${API_BASE}/api/topic/stream?q=${encodeURIComponent(q)}`, {
    loaderMsg: `Searching "${q}"…`,
    onMessage(data, es) {
      if (data.status === "fetching") {
        addFeedItem(data.source, "fetching", "fetching…");

      } else if (data.status === "fetched") {
        updateFeedItem(data.source, "done",
          `${data.count} article${data.count !== 1 ? "s" : ""}`);

      } else if (data.status === "error") {
        updateFeedItem(data.source, "error", "unavailable");

      } else if (data.status === "summarizing") {
        loaderText.textContent = "Summarizing with Claude AI…";
        addFeedItem("Claude AI", "summarizing", "summarizing…");

      } else if (data.status === "complete") {
        es.close();
        updateFeedItem("Claude AI", "summarized", "done ✓");
        hideLoader();
        topicCard.innerHTML = buildCard(data.data.topic || q, data.data);
        topicResult.classList.remove("hidden");
        topicResult.scrollIntoView({ behavior: "smooth", block: "start" });
        searchBtn.disabled = false;
      }
    },
    onError() { searchBtn.disabled = false; },
  });
}

searchBtn.addEventListener("click", doSearch);
searchInput.addEventListener("keydown", e => { if (e.key === "Enter") doSearch(); });

// ── Generic SSE opener (for topic search) ─────────────────────────────────────

function openStream(url, { onMessage, onError, loaderMsg }) {
  showLoader(loaderMsg || "Fetching live news…");
  clearFeed();

  let streamCompleted = false;

  const es = new EventSource(url);
  es.onmessage = (event) => {
    let data;
    try { data = JSON.parse(event.data); } catch { return; }
    if (data.status === "complete") streamCompleted = true;
    onMessage(data, es);
  };
  es.onerror = () => {
    es.close();
    if (!streamCompleted) {
      showError("Connection failed. Is the server running?");
      if (onError) onError();
    }
  };
}

// ── Status feed helpers (topic search) ────────────────────────────────────────

function clearFeed() { statusFeed.innerHTML = ""; }

function feedKey(source) {
  return source.toLowerCase().replace(/[^a-z0-9]/g, "-");
}

function sentimentBadge(s) {
  if (!s) return "";
  return `<span class="status-sentiment ss-${s}">${s}</span>`;
}

function feedItemHTML(source, state, detail, sentiment) {
  const icons = {
    fetching:    `<span class="status-icon spin">⟳</span>`,
    done:        `<span class="status-icon">✓</span>`,
    summarizing: `<span class="status-icon spin">✦</span>`,
    summarized:  `<span class="status-icon">✦</span>`,
    error:       `<span class="status-icon">✗</span>`,
  };
  const nameClass = {
    fetching:    "active",
    done:        "done",
    summarizing: "ai",
    summarized:  "ai",
    error:       "error",
  }[state] || "";
  const detailClass = state === "done" ? "ok" : state.startsWith("summar") ? "ai" : "";

  return `
    ${icons[state] || `<span class="status-icon">○</span>`}
    <span class="status-name ${nameClass}">${source}</span>
    ${sentiment ? sentimentBadge(sentiment) : ""}
    <span class="status-detail ${detailClass}">${detail}</span>
  `;
}

function addFeedItem(source, state, detail = "", sentiment = "") {
  const key = feedKey(source);
  if (statusFeed.querySelector(`[data-key="${key}"]`)) {
    updateFeedItem(source, state, detail, sentiment);
    return;
  }
  const el = document.createElement("div");
  el.className = `status-item ${state}`;
  el.dataset.key = key;
  el.innerHTML = feedItemHTML(source, state, detail, sentiment);
  statusFeed.appendChild(el);
  el.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function updateFeedItem(source, state, detail = "", sentiment = "") {
  const key = feedKey(source);
  const el = statusFeed.querySelector(`[data-key="${key}"]`);
  if (!el) { addFeedItem(source, state, detail, sentiment); return; }
  el.className = `status-item ${state}`;
  el.innerHTML = feedItemHTML(source, state, detail, sentiment);
}

// ── Loader helpers ────────────────────────────────────────────────────────────

function showLoader(text = "Fetching and summarizing news…") {
  loaderText.textContent = text;
  loader.classList.remove("hidden");
  errorBox.classList.add("hidden");
}

function hideLoader() { loader.classList.add("hidden"); }

function showError(msg) {
  errorBox.textContent = msg;
  errorBox.classList.remove("hidden");
  hideLoader();
}

// ── Reset ─────────────────────────────────────────────────────────────────────

function resetResults() {
  heroSection.classList.add("hidden");
  topicResult.classList.add("hidden");
  errorBox.classList.add("hidden");
  gridContainer.innerHTML = "";
  topicCard.innerHTML = "";
  clearFeed();
  hideLoader();
}

// ── Auto-load on page open ────────────────────────────────────────────────────

document.addEventListener("DOMContentLoaded", loadOverview);
