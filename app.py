import os
import json
import threading
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv

# Always load .env from the same directory as this file
load_dotenv(dotenv_path=Path(__file__).parent / ".env", override=True)

from flask import Flask, jsonify, request, send_from_directory, Response, stream_with_context
from flask_cors import CORS

from news_fetcher import (
    fetch_all_news, fetch_by_category,
    fetch_currents, fetch_guardian, fetch_reddit,
    fetch_newsdata, fetch_hackernews, fetch_bbc_rss,
    fetch_ap_rss, fetch_perplexity, fetch_gemini_news,
    CATEGORIES, REDDIT_SUBREDDITS,
    CURRENTS_CATEGORY_MAP,
    CATEGORY_GUARDIAN_QUERIES, CATEGORY_NEWSDATA_QUERIES,
    CATEGORY_GEMINI_QUERIES, CATEGORY_PERPLEXITY_QUERIES,
)
from summarizer import summarize_topic, summarize_all_categories, generate_overall_digest

app = Flask(__name__, static_folder="frontend")
CORS(app)


# ── Helpers ───────────────────────────────────────────────────────────────────

def sse(data: dict) -> str:
    """Format a dict as an SSE message."""
    return f"data: {json.dumps(data)}\n\n"


# ── Static frontend ───────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory("frontend", "index.html")


@app.route("/<path:filename>")
def static_files(filename):
    return send_from_directory("frontend", filename)


# ── Startup cache pre-warm ────────────────────────────────────────────────────
# Runs once in a background daemon thread right after gunicorn starts the worker.
# This populates the 5-min TTL cache for all 10 categories so that the very
# first user who hits the page gets near-instant results instead of a cold fetch.

def _prewarm_cache():
    import time
    time.sleep(6)  # let gunicorn finish booting before hammering external APIs
    print("[PreWarm] Starting background cache warm-up for all categories…")
    for cat in CATEGORIES:
        try:
            _fetch_category_articles(cat)
            print(f"[PreWarm] ✓ {cat}")
        except Exception as exc:
            print(f"[PreWarm] ✗ {cat}: {exc}")
    print("[PreWarm] Done — all categories cached.")

threading.Thread(target=_prewarm_cache, daemon=True).start()


# ── API: Full digest — batch (kept for backward compat) ───────────────────────

@app.route("/api/digest", methods=["GET"])
def full_digest():
    grouped = fetch_by_category()
    summaries = summarize_all_categories(grouped)
    overall = generate_overall_digest(summaries)
    return jsonify({"overall_digest": overall, "categories": summaries})


# ── Per-category parallel fetcher ────────────────────────────────────────────

def _fetch_category_articles(category: str) -> list:
    """Fetch all news sources for one category concurrently.
    Uses a thread pool so 7-9 HTTP calls run in parallel instead of serially.
    Reduces per-category fetch time from ~18 s → ~3-5 s.
    """
    fetchers = [
        lambda: fetch_currents(category=CURRENTS_CATEGORY_MAP.get(category), max_articles=3),
        lambda: fetch_guardian(topic=CATEGORY_GUARDIAN_QUERIES.get(category, category), max_articles=3),
        lambda: fetch_newsdata(topic=CATEGORY_NEWSDATA_QUERIES.get(category, category), max_articles=3),
        lambda: fetch_bbc_rss(category=category, max_articles=3),
        lambda: fetch_reddit(subreddit=REDDIT_SUBREDDITS.get(category, "news"), limit=3),
        lambda: fetch_gemini_news(topic=category, max_results=3),
        lambda: fetch_perplexity(topic=category, max_results=3),
    ]
    if category in ("technology_ai", "innovation_space"):
        fetchers.append(lambda: fetch_hackernews(limit=3))
    if category in ("geopolitical", "politics_policy"):
        fetchers.append(lambda: fetch_ap_rss(max_articles=3))

    articles: list = []
    with ThreadPoolExecutor(max_workers=len(fetchers)) as ex:
        futures = [ex.submit(fn) for fn in fetchers]
        for fut in as_completed(futures, timeout=25):
            try:
                articles.extend(fut.result() or [])
            except Exception:
                pass
    return articles


# ── Per-category parallel summarizer ─────────────────────────────────────────

def _dedup_articles(articles: list, max_keep: int = 12) -> list:
    """Remove near-duplicate articles (same title prefix) and cap the list.
    Sending fewer tokens to Claude reduces latency without losing coverage.
    """
    seen: set = set()
    unique: list = []
    for a in articles:
        # Use first 50 chars of lowercased title as dedup key
        key = a.get("title", "")[:50].lower().strip()
        if key and key not in seen:
            seen.add(key)
            unique.append(a)
    return unique[:max_keep]


def _summarize_category(category: str, articles: list) -> dict:
    """Build the full cat_summary dict for one category.
    Deduplicates + trims articles before the Claude call to reduce prompt
    tokens and therefore API latency.
    """
    trimmed = _dedup_articles(articles)
    summary_data = summarize_topic(category, trimmed)
    return {
        **summary_data,
        "article_count": len(articles),  # report original count, not trimmed
        "articles": [
            {
                "title": a.get("title", ""),
                "url": a.get("url", ""),
                "source": a.get("source", ""),
                "published": a.get("published", ""),
            }
            for a in articles[:5]
        ],
    }


# ── API: Shared SSE generator ─────────────────────────────────────────────────

def _overview_generator():
    """SSE generator — fully parallelised for speed:
    • Phase 1: all 10 category fetches run concurrently (5 at a time);
      each category itself fans out its 7-9 sources in a nested pool.
    • Phase 2: Claude summaries run 3-at-a-time to respect rate limits.
    Expected wall-clock: ~10 s fetch + ~35 s summarise = ~45 s total
    (vs ~3-5 min with the old serial approach).
    """
    total = len(CATEGORIES)
    yield sse({"status": "start", "total": total})

    # ── Phase 1: Fetch all categories concurrently ────────────────────────────
    grouped: dict = {}
    fetched_count = 0

    with ThreadPoolExecutor(max_workers=10) as pool:   # all 10 categories at once
        cat_futures = {pool.submit(_fetch_category_articles, cat): cat for cat in CATEGORIES}
        for fut in as_completed(cat_futures):
            cat = cat_futures[fut]
            try:
                articles = fut.result()
            except Exception:
                articles = []
            grouped[cat] = articles
            fetched_count += 1
            yield sse({
                "status": "fetched",
                "source": cat,
                "count": len(articles),
                "progress": round(fetched_count / total * 50),  # 0–50%
            })

    # ── Phase 2: Summarize all categories (3 concurrent Claude calls) ─────────
    summaries: dict = {}
    summarized_count = 0

    with ThreadPoolExecutor(max_workers=5) as pool:   # Haiku handles 5 parallel calls fine
        sum_futures = {
            pool.submit(_summarize_category, cat, grouped.get(cat, [])): cat
            for cat in CATEGORIES
        }
        for fut in as_completed(sum_futures):
            cat = sum_futures[fut]
            summarized_count += 1
            try:
                cat_summary = fut.result()
            except Exception:
                cat_summary = {
                    "summary": "", "key_points": [], "sentiment": "neutral",
                    "article_count": 0, "articles": [],
                }
            summaries[cat] = cat_summary
            yield sse({
                "status": "summarized",
                "source": cat,
                "sentiment": cat_summary.get("sentiment", "neutral"),
                "data": cat_summary,                           # ← live card reveal
                "progress": 50 + round(summarized_count / total * 40),  # 50–90%
            })

    # ── Phase 3: Overall digest ───────────────────────────────────────────────
    yield sse({"status": "summarizing", "source": "Overall Digest"})
    overall = generate_overall_digest(summaries)
    yield sse({
        "status": "complete",
        "data": {"overall_digest": overall, "categories": summaries},
    })


# ── API: Overview / Digest — streaming SSE ────────────────────────────────────

@app.route("/api/digest/stream", methods=["GET"])
def digest_stream():
    return Response(
        stream_with_context(_overview_generator()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


@app.route("/api/overview/stream", methods=["GET"])
def overview_stream():
    """Alias for digest_stream — cleaner URL semantics for the auto-load dashboard."""
    return Response(
        stream_with_context(_overview_generator()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


# ── API: Topic search — batch (kept for backward compat) ──────────────────────

@app.route("/api/topic", methods=["GET"])
def topic_search():
    topic = request.args.get("q", "").strip()
    if not topic:
        return jsonify({"error": "Please provide a topic via ?q=your_topic"}), 400
    articles = fetch_all_news(topic=topic)
    summary = summarize_topic(topic, articles)
    return jsonify({
        "topic": topic,
        **summary,
        "article_count": len(articles),
        "articles": [
            {"title": a.get("title", ""), "url": a.get("url", ""),
             "source": a.get("source", ""), "published": a.get("published", "")}
            for a in articles[:6]
        ],
    })


# ── API: Topic search — streaming SSE ────────────────────────────────────────

@app.route("/api/topic/stream", methods=["GET"])
def topic_stream():
    topic = request.args.get("q", "").strip()
    if not topic:
        return jsonify({"error": "Please provide ?q=topic"}), 400

    def generate():
        all_articles = []

        source_fetchers = [
            ("Currents API",  lambda: fetch_currents(category=CURRENTS_CATEGORY_MAP.get(topic), max_articles=6)),
            ("The Guardian",  lambda: fetch_guardian(topic=CATEGORY_GUARDIAN_QUERIES.get(topic, topic), max_articles=6)),
            ("NewsData.io",   lambda: fetch_newsdata(topic=CATEGORY_NEWSDATA_QUERIES.get(topic, topic), max_articles=6)),
            ("BBC News",      lambda: fetch_bbc_rss(category=topic or "general", max_articles=5)),
            ("AP News",       lambda: fetch_ap_rss(max_articles=5)),
            ("Reddit",        lambda: fetch_reddit(subreddit=REDDIT_SUBREDDITS.get(topic, "worldnews"), limit=6)),
            ("Hacker News",   lambda: fetch_hackernews(limit=5) if topic in ("technology_ai", "innovation_space") else []),
            ("Perplexity",    lambda: fetch_perplexity(topic=topic, max_results=5)),
            ("Gemini Search", lambda: fetch_gemini_news(topic=topic, max_results=5)),
        ]

        for source_name, fetch_fn in source_fetchers:
            yield sse({"status": "fetching", "source": source_name})
            try:
                articles = fetch_fn()
                all_articles.extend(articles)
                yield sse({"status": "fetched", "source": source_name, "count": len(articles)})
            except Exception as e:
                yield sse({"status": "error", "source": source_name, "error": str(e)})

        yield sse({"status": "summarizing", "source": "Claude AI"})
        summary = summarize_topic(topic, all_articles)
        yield sse({
            "status": "complete",
            "data": {
                "topic": topic,
                **summary,
                "article_count": len(all_articles),
                "articles": [
                    {"title": a.get("title", ""), "url": a.get("url", ""),
                     "source": a.get("source", ""), "published": a.get("published", "")}
                    for a in all_articles[:6]
                ],
            },
        })

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


# ── API: Raw articles ─────────────────────────────────────────────────────────

@app.route("/api/articles", methods=["GET"])
def raw_articles():
    topic = request.args.get("q", "").strip() or None
    articles = fetch_all_news(topic=topic)
    return jsonify({"articles": articles, "count": len(articles)})


# ── Health check ──────────────────────────────────────────────────────────────

@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "keys": {
            "currents":   bool(os.getenv("CURRENTS_API_KEY")),
            "guardian":   bool(os.getenv("GUARDIAN_API_KEY")),
            "anthropic":  bool(os.getenv("ANTHROPIC_API_KEY")),
            "newsdata":   bool(os.getenv("NEWSDATA_API_KEY")),
            "perplexity": bool(os.getenv("PERPLEXITY_API_KEY")),
            "gemini":     bool(os.getenv("GEMINI_API_KEY")),
        },
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    # use_reloader=False so autoPort works correctly with the Claude preview tool
    app.run(debug=True, host="0.0.0.0", port=port, use_reloader=False)
