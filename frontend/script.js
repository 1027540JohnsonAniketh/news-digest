// Use relative URLs so it always matches whatever host/port the page is served from
const API_BASE = "";

// ── DOM refs ──────────────────────────────────────────────────────────────────
const searchInput   = document.getElementById("searchInput");
const searchBtn     = document.getElementById("searchBtn");
const digestBtn     = document.getElementById("digestBtn");
const loader        = document.getElementById("loader");
const loaderText    = document.getElementById("loaderText");
const errorBox      = document.getElementById("errorBox");
const overallSection = document.getElementById("overallSection");
const overallText   = document.getElementById("overallText");
const topicResult   = document.getElementById("topicResult");
const topicCard     = document.getElementById("topicCard");
const categoryGrid  = document.getElementById("categoryGrid");
const gridContainer = document.getElementById("gridContainer");

// ── Helpers ───────────────────────────────────────────────────────────────────
function showLoader(text = "Fetching and summarizing news...") {
  loaderText.textContent = text;
  loader.classList.remove("hidden");
  errorBox.classList.add("hidden");
}

function hideLoader() {
  loader.classList.add("hidden");
}

function showError(msg) {
  errorBox.textContent = msg;
  errorBox.classList.remove("hidden");
  hideLoader();
}

function sentimentClass(s) {
  const map = { positive: "positive", negative: "negative", mixed: "mixed", neutral: "neutral" };
  return "sentiment-" + (map[s] || "neutral");
}

function buildCard(title, data) {
  const keyPointsHtml = (data.key_points || [])
    .map(p => `<li>${p}</li>`)
    .join("");

  const articlesHtml = (data.articles || [])
    .slice(0, 4)
    .map(a => `
      <a class="article-link" href="${a.url}" target="_blank" rel="noopener">
        <span class="source-tag">[${a.source}]</span>${a.title}
      </a>`)
    .join("");

  return `
    <div class="card">
      <div class="card-header">
        <span class="card-title">${title}</span>
        <span class="sentiment-badge ${sentimentClass(data.sentiment)}">${data.sentiment || "neutral"}</span>
      </div>
      <p class="card-summary">${data.summary || ""}</p>
      ${keyPointsHtml ? `<ul class="key-points">${keyPointsHtml}</ul>` : ""}
      ${articlesHtml ? `
        <div class="article-links">
          <h4>Related Articles</h4>
          ${articlesHtml}
        </div>` : ""}
      <p class="article-count">${data.article_count || 0} articles analysed</p>
    </div>`;
}

// ── Full digest ───────────────────────────────────────────────────────────────
digestBtn.addEventListener("click", async () => {
  resetResults();
  showLoader("Fetching news from all sources... this takes about 30 seconds.");
  digestBtn.disabled = true;

  try {
    const res = await fetch(`${API_BASE}/api/digest`);
    if (!res.ok) throw new Error(`Server error ${res.status}`);
    const data = await res.json();

    hideLoader();

    // Overall digest
    if (data.overall_digest) {
      overallText.textContent = data.overall_digest;
      overallSection.classList.remove("hidden");
    }

    // Category cards
    if (data.categories) {
      gridContainer.innerHTML = "";
      for (const [cat, catData] of Object.entries(data.categories)) {
        gridContainer.innerHTML += buildCard(cat, catData);
      }
      categoryGrid.classList.remove("hidden");
    }
  } catch (err) {
    showError("Failed to load digest. Is the server running? Error: " + err.message);
  } finally {
    digestBtn.disabled = false;
  }
});

// ── Topic search ──────────────────────────────────────────────────────────────
async function doSearch() {
  const q = searchInput.value.trim();
  if (!q) return;

  resetResults();
  showLoader(`Searching for "${q}" and summarizing...`);
  searchBtn.disabled = true;

  try {
    const res = await fetch(`${API_BASE}/api/topic?q=${encodeURIComponent(q)}`);
    if (!res.ok) throw new Error(`Server error ${res.status}`);
    const data = await res.json();

    hideLoader();
    topicCard.innerHTML = buildCard(data.topic || q, data);
    topicResult.classList.remove("hidden");
  } catch (err) {
    showError("Search failed. Is the server running? Error: " + err.message);
  } finally {
    searchBtn.disabled = false;
  }
}

searchBtn.addEventListener("click", doSearch);
searchInput.addEventListener("keydown", e => { if (e.key === "Enter") doSearch(); });

// ── Reset ─────────────────────────────────────────────────────────────────────
function resetResults() {
  overallSection.classList.add("hidden");
  topicResult.classList.add("hidden");
  categoryGrid.classList.add("hidden");
  errorBox.classList.add("hidden");
  gridContainer.innerHTML = "";
  topicCard.innerHTML = "";
}
