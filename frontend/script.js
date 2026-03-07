const API_BASE = "";   // relative — always matches the serving host

// ── DOM refs ──────────────────────────────────────────────────────────────────
const searchInput    = document.getElementById("searchInput");
const searchBtn      = document.getElementById("searchBtn");
const digestBtn      = document.getElementById("digestBtn");
const loader         = document.getElementById("loader");
const loaderText     = document.getElementById("loaderText");
const statusFeed     = document.getElementById("statusFeed");
const errorBox       = document.getElementById("errorBox");
const overallSection = document.getElementById("overallSection");
const overallText    = document.getElementById("overallText");
const topicResult    = document.getElementById("topicResult");
const topicCard      = document.getElementById("topicCard");
const categoryGrid   = document.getElementById("categoryGrid");
const gridContainer  = document.getElementById("gridContainer");

// ── Status feed helpers ───────────────────────────────────────────────────────

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

// ── Generic SSE opener ────────────────────────────────────────────────────────

function openStream(url, { onMessage, onError, loaderMsg }) {
  showLoader(loaderMsg || "Fetching live news…");
  clearFeed();

  // Guard: if the server sends "complete" and closes the connection, browsers
  // fire onerror right after. We track completion so we don't show a false
  // "Connection failed" error when the stream ended successfully.
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

// ── Card builder ──────────────────────────────────────────────────────────────

function sentimentClass(s) {
  return "sentiment-" + (["positive","negative","mixed","neutral"].includes(s) ? s : "neutral");
}

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

// ── Topic search ──────────────────────────────────────────────────────────────

function doSearch() {
  const q = searchInput.value.trim();
  if (!q) return;
  resetResults();
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

// ── Full digest ───────────────────────────────────────────────────────────────

digestBtn.addEventListener("click", () => {
  resetResults();
  digestBtn.disabled = true;

  openStream(`${API_BASE}/api/digest/stream`, {
    loaderMsg: "Loading full news digest…",
    onMessage(data, es) {
      if (data.status === "start") {
        loaderText.textContent = `Fetching ${data.total} categories…`;

      } else if (data.status === "fetching") {
        addFeedItem(data.source, "fetching", "fetching…");

      } else if (data.status === "fetched") {
        updateFeedItem(data.source, "done", `${data.count} articles`);

      } else if (data.status === "summarizing") {
        const label = data.source === "Overall Digest"
          ? "Overall Digest"
          : `AI: ${data.source}`;
        loaderText.textContent = `Summarizing ${data.source}…`;
        addFeedItem(label, "summarizing", "summarizing…");

      } else if (data.status === "summarized") {
        updateFeedItem(`AI: ${data.source}`, "summarized", "done ✓", data.sentiment);

      } else if (data.status === "complete") {
        es.close();
        updateFeedItem("Overall Digest", "summarized", "done ✓");
        hideLoader();

        if (data.data.overall_digest) {
          overallText.textContent = data.data.overall_digest;
          overallSection.classList.remove("hidden");
        }
        if (data.data.categories) {
          gridContainer.innerHTML = "";
          for (const [cat, catData] of Object.entries(data.data.categories)) {
            gridContainer.innerHTML += buildCard(cat, catData);
          }
          categoryGrid.classList.remove("hidden");
          categoryGrid.scrollIntoView({ behavior: "smooth", block: "start" });
        }
        digestBtn.disabled = false;
      }
    },
    onError() { digestBtn.disabled = false; },
  });
});

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
  overallSection.classList.add("hidden");
  topicResult.classList.add("hidden");
  categoryGrid.classList.add("hidden");
  errorBox.classList.add("hidden");
  gridContainer.innerHTML = "";
  topicCard.innerHTML = "";
  clearFeed();
}
