import os
from pathlib import Path
from dotenv import load_dotenv

# Always load .env from the same directory as this file
load_dotenv(dotenv_path=Path(__file__).parent / ".env", override=True)

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

from news_fetcher import fetch_all_news, fetch_by_category
from summarizer import summarize_topic, summarize_all_categories, generate_overall_digest

app = Flask(__name__, static_folder="frontend")
CORS(app)


# ── Static frontend ──────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory("frontend", "index.html")


@app.route("/<path:filename>")
def static_files(filename):
    return send_from_directory("frontend", filename)


# ── API: Full digest (all categories) ────────────────────────────────────────

@app.route("/api/digest", methods=["GET"])
def full_digest():
    """
    Fetches news from all sources across all categories,
    summarizes each, and returns a full digest.
    """
    print("Fetching news by category...")
    grouped = fetch_by_category()

    print("Summarizing all categories...")
    summaries = summarize_all_categories(grouped)

    print("Generating overall digest...")
    overall = generate_overall_digest(summaries)

    return jsonify({
        "overall_digest": overall,
        "categories": summaries,
    })


# ── API: Single topic search ──────────────────────────────────────────────────

@app.route("/api/topic", methods=["GET"])
def topic_search():
    """
    Search for a specific topic and get a summary.
    Query param: ?q=your+topic
    """
    topic = request.args.get("q", "").strip()
    if not topic:
        return jsonify({"error": "Please provide a topic via ?q=your_topic"}), 400

    print(f"Fetching news for topic: {topic}")
    articles = fetch_all_news(topic=topic)

    print(f"Summarizing {len(articles)} articles for '{topic}'...")
    summary = summarize_topic(topic, articles)

    return jsonify({
        "topic": topic,
        **summary,
        "article_count": len(articles),
        "articles": [
            {
                "title": a.get("title", ""),
                "url": a.get("url", ""),
                "source": a.get("source", ""),
                "published": a.get("published", ""),
            }
            for a in articles[:6]
        ],
    })


# ── API: Raw articles (no summarization) ─────────────────────────────────────

@app.route("/api/articles", methods=["GET"])
def raw_articles():
    """
    Returns raw articles for a topic without AI summarization.
    Query param: ?q=your+topic
    """
    topic = request.args.get("q", "").strip() or None
    articles = fetch_all_news(topic=topic)
    return jsonify({"articles": articles, "count": len(articles)})


# ── Health check ─────────────────────────────────────────────────────────────

@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "keys": {
            "currents": bool(os.getenv("CURRENTS_API_KEY")),
            "guardian": bool(os.getenv("GUARDIAN_API_KEY")),
            "anthropic": bool(os.getenv("ANTHROPIC_API_KEY")),
        }
    })


if __name__ == "__main__":
    # debug=True only locally; Render uses gunicorn so this block won't run there
    port = int(os.environ.get("PORT", 8080))
    app.run(debug=True, host="0.0.0.0", port=port)
