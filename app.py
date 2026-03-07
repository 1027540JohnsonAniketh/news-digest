import os
import json
from pathlib import Path
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


# ── API: Full digest — batch (kept for backward compat) ───────────────────────

@app.route("/api/digest", methods=["GET"])
def full_digest():
    grouped = fetch_by_category()
    summaries = summarize_all_categories(grouped)
    overall = generate_overall_digest(summaries)
    return jsonify({"overall_digest": overall, "categories": summaries})


# ── API: Shared SSE generator ─────────────────────────────────────────────────

def _overview_generator():
    """SSE generator for the full overview stream.
    Yields per-category fetch status, per-category summarized data (for live
    card reveals), then the final overall digest.
    """
    categories_to_process = CATEGORIES
    total = len(categories_to_process)
    yield sse({"status": "start", "total": total})

    grouped = {}

    # ── Phase 1: Fetch per category ───────────────────────────────────────────
    for i, category in enumerate(categories_to_process):
        yield sse({"status": "fetching", "source": category})

        articles = []
        articles += fetch_currents(category=CURRENTS_CATEGORY_MAP.get(category), max_articles=4)
        articles += fetch_guardian(topic=CATEGORY_GUARDIAN_QUERIES.get(category, category), max_articles=4)
        articles += fetch_newsdata(topic=CATEGORY_NEWSDATA_QUERIES.get(category, category), max_articles=4)
        articles += fetch_bbc_rss(category=category, max_articles=4)
        articles += fetch_reddit(subreddit=REDDIT_SUBREDDITS.get(category, "news"), limit=4)
        if category in ("technology_ai", "innovation_space"):
            articles += fetch_hackernews(limit=4)
        if category in ("geopolitical", "politics_policy"):
            articles += fetch_ap_rss(max_articles=4)
        articles += fetch_gemini_news(topic=category, max_results=4)
        articles += fetch_perplexity(topic=category, max_results=4)

        grouped[category] = articles
        yield sse({
            "status": "fetched",
            "source": category,
            "count": len(articles),
            "progress": round((i + 1) / total * 50),   # 0–50% during fetch phase
        })

    # ── Phase 2: Summarize per category (with live data for card reveals) ─────
    summaries = {}
    for i, (category, articles) in enumerate(grouped.items()):
        yield sse({"status": "summarizing", "source": category})
        summary_data = summarize_topic(category, articles)
        cat_summary = {
            **summary_data,
            "article_count": len(articles),
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
        summaries[category] = cat_summary

        # Send per-category data immediately so JS can swap skeleton → real card
        yield sse({
            "status": "summarized",
            "source": category,
            "sentiment": summary_data.get("sentiment", "neutral"),
            "data": cat_summary,                        # ← live card reveal payload
            "progress": 50 + round((i + 1) / total * 40),  # 50–90% during summarize phase
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
