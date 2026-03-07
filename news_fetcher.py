import os
import requests
import feedparser
from concurrent.futures import ThreadPoolExecutor, as_completed

# ── API Keys ──────────────────────────────────────────────────────────────────
CURRENTS_API_KEY   = os.getenv("CURRENTS_API_KEY")
GUARDIAN_API_KEY   = os.getenv("GUARDIAN_API_KEY")
NEWSDATA_API_KEY   = os.getenv("NEWSDATA_API_KEY")
PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")
GEMINI_API_KEY     = os.getenv("GEMINI_API_KEY")

CATEGORIES = ["technology", "politics", "business", "health", "sports", "science", "entertainment"]

REDDIT_SUBREDDITS = {
    "world news":    "worldnews",
    "technology":    "technology",
    "politics":      "politics",
    "business":      "business",
    "science":       "science",
    "sports":        "sports",
    "entertainment": "entertainment",
}

BBC_FEEDS = {
    "general":       "https://feeds.bbci.co.uk/news/rss.xml",
    "world news":    "https://feeds.bbci.co.uk/news/world/rss.xml",
    "technology":    "https://feeds.bbci.co.uk/news/technology/rss.xml",
    "business":      "https://feeds.bbci.co.uk/news/business/rss.xml",
    "science":       "https://feeds.bbci.co.uk/news/science_and_environment/rss.xml",
    "health":        "https://feeds.bbci.co.uk/news/health/rss.xml",
    "entertainment": "https://feeds.bbci.co.uk/news/entertainment_and_arts/rss.xml",
    "sports":        "https://feeds.bbci.co.uk/sport/rss.xml",
}


# ── 1. Currents API ───────────────────────────────────────────────────────────
def fetch_currents(category=None, language="en", max_articles=8):
    if not CURRENTS_API_KEY:
        return []
    url = "https://api.currentsapi.services/v1/latest-news"
    params = {"apiKey": CURRENTS_API_KEY, "language": language}
    if category:
        params["category"] = category
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        articles = resp.json().get("news", [])
        return [
            {
                "source": "Currents API",
                "title": a.get("title", ""),
                "description": a.get("description", ""),
                "url": a.get("url", ""),
                "published": a.get("published", ""),
                "category": category or "general",
            }
            for a in articles[:max_articles]
        ]
    except Exception as e:
        print(f"[Currents] Error: {e}")
        return []


# ── 2. The Guardian ───────────────────────────────────────────────────────────
def fetch_guardian(topic=None, max_articles=8):
    if not GUARDIAN_API_KEY:
        return []
    url = "https://content.guardianapis.com/search"
    params = {
        "api-key": GUARDIAN_API_KEY,
        "show-fields": "trailText",
        "order-by": "newest",
        "page-size": max_articles,
    }
    if topic:
        params["q"] = topic
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        results = resp.json().get("response", {}).get("results", [])
        return [
            {
                "source": "The Guardian",
                "title": r.get("webTitle", ""),
                "description": r.get("fields", {}).get("trailText", ""),
                "url": r.get("webUrl", ""),
                "published": r.get("webPublicationDate", ""),
                "category": r.get("sectionName", topic or "general"),
            }
            for r in results
        ]
    except Exception as e:
        print(f"[Guardian] Error: {e}")
        return []


# ── 3. Reddit ─────────────────────────────────────────────────────────────────
def fetch_reddit(subreddit="worldnews", limit=8):
    url = f"https://www.reddit.com/r/{subreddit}/hot.json"
    headers = {"User-Agent": "NewsDigestApp/1.0"}
    try:
        resp = requests.get(url, headers=headers, params={"limit": limit}, timeout=10)
        resp.raise_for_status()
        posts = resp.json().get("data", {}).get("children", [])
        return [
            {
                "source": f"Reddit r/{subreddit}",
                "title": p["data"].get("title", ""),
                "description": p["data"].get("selftext", "")[:300] or p["data"].get("title", ""),
                "url": p["data"].get("url", ""),
                "published": "",
                "score": p["data"].get("score", 0),
                "category": subreddit,
            }
            for p in posts
            if not p["data"].get("stickied", False)
        ]
    except Exception as e:
        print(f"[Reddit r/{subreddit}] Error: {e}")
        return []


# ── 4. NewsData.io ────────────────────────────────────────────────────────────
def fetch_newsdata(topic=None, language="en", max_articles=8):
    if not NEWSDATA_API_KEY:
        return []
    url = "https://newsdata.io/api/1/news"
    params = {"apikey": NEWSDATA_API_KEY, "language": language}
    if topic:
        params["q"] = topic
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        results = resp.json().get("results", [])
        return [
            {
                "source": f"NewsData/{r.get('source_id', 'unknown')}",
                "title": r.get("title", ""),
                "description": (r.get("description") or r.get("content") or "")[:300],
                "url": r.get("link", ""),
                "published": r.get("pubDate", ""),
                "category": (r.get("category") or [topic or "general"])[0],
            }
            for r in results[:max_articles]
        ]
    except Exception as e:
        print(f"[NewsData] Error: {e}")
        return []


# ── 5. Hacker News (free, no key) ─────────────────────────────────────────────
def fetch_hackernews(limit=8):
    try:
        ids_resp = requests.get(
            "https://hacker-news.firebaseio.com/v0/topstories.json", timeout=10
        )
        story_ids = ids_resp.json()[:limit]

        def get_story(sid):
            try:
                r = requests.get(
                    f"https://hacker-news.firebaseio.com/v0/item/{sid}.json", timeout=5
                )
                return r.json()
            except Exception:
                return None

        articles = []
        with ThreadPoolExecutor(max_workers=6) as ex:
            futures = {ex.submit(get_story, sid): sid for sid in story_ids}
            for future in as_completed(futures):
                story = future.result()
                if story and story.get("type") == "story" and story.get("title"):
                    articles.append({
                        "source": "Hacker News",
                        "title": story.get("title", ""),
                        "description": story.get("title", ""),
                        "url": story.get("url", f"https://news.ycombinator.com/item?id={story['id']}"),
                        "published": "",
                        "score": story.get("score", 0),
                        "category": "technology",
                    })
        return articles[:limit]
    except Exception as e:
        print(f"[HackerNews] Error: {e}")
        return []


# ── 6. BBC RSS (free, no key) ─────────────────────────────────────────────────
def fetch_bbc_rss(category="general", max_articles=8):
    feed_url = BBC_FEEDS.get(category, BBC_FEEDS["general"])
    try:
        feed = feedparser.parse(feed_url)
        return [
            {
                "source": "BBC News",
                "title": e.get("title", ""),
                "description": e.get("summary", ""),
                "url": e.get("link", ""),
                "published": e.get("published", ""),
                "category": category,
            }
            for e in feed.entries[:max_articles]
        ]
    except Exception as e:
        print(f"[BBC RSS] Error: {e}")
        return []


# ── 7. AP News RSS (free, no key) ─────────────────────────────────────────────
def fetch_ap_rss(max_articles=8):
    try:
        feed = feedparser.parse("https://feeds.apnews.com/rss/apf-topnews")
        return [
            {
                "source": "AP News",
                "title": e.get("title", ""),
                "description": e.get("summary", ""),
                "url": e.get("link", ""),
                "published": e.get("published", ""),
                "category": "world news",
            }
            for e in feed.entries[:max_articles]
        ]
    except Exception as e:
        print(f"[AP News] Error: {e}")
        return []


# ── 8. Perplexity Sonar — live web search ─────────────────────────────────────
def fetch_perplexity(topic=None, max_results=6):
    if not PERPLEXITY_API_KEY:
        return []
    query = (
        f"What are the top 5 latest breaking news headlines about '{topic}' right now? "
        "For each give: title and one-sentence description."
        if topic
        else "What are the top 10 most important world news headlines right now? "
             "For each give: title and one-sentence description."
    )
    try:
        resp = requests.post(
            "https://api.perplexity.ai/chat/completions",
            headers={
                "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "sonar",
                "messages": [
                    {"role": "system", "content": "You are a concise news assistant. Be factual and brief."},
                    {"role": "user", "content": query},
                ],
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        citations = data.get("citations", [])

        articles = []
        lines = [l.strip() for l in content.split("\n") if l.strip() and len(l.strip()) > 20]
        for i, line in enumerate(lines[:max_results]):
            line = line.lstrip("0123456789.*-#• ").strip()
            if not line:
                continue
            articles.append({
                "source": "Perplexity/Sonar",
                "title": line[:120],
                "description": line,
                "url": citations[i] if i < len(citations) else "",
                "published": "",
                "category": topic or "general",
            })
        return articles
    except Exception as e:
        print(f"[Perplexity] Error: {e}")
        return []


# ── 9. Gemini 2.0 Flash + Google Search grounding ────────────────────────────
def fetch_gemini_news(topic=None, max_results=6):
    if not GEMINI_API_KEY:
        return []
    query = (
        f"What are the top 5 latest news headlines about '{topic}' right now? "
        "List as numbered items: title and one sentence summary."
        if topic
        else "What are the top 10 world news headlines right now? "
             "List as numbered items: title and one sentence summary."
    )
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    )
    try:
        resp = requests.post(
            url,
            json={
                "contents": [{"parts": [{"text": query}]}],
                "tools": [{"google_search": {}}],
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        candidate = data["candidates"][0]
        text = candidate["content"]["parts"][0]["text"]

        # Extract grounding source URLs
        grounding = candidate.get("groundingMetadata", {})
        sources = [
            {
                "title": chunk.get("web", {}).get("title", ""),
                "url": chunk.get("web", {}).get("uri", ""),
            }
            for chunk in grounding.get("groundingChunks", [])
        ]

        articles = []
        lines = [l.strip() for l in text.split("\n") if l.strip() and len(l.strip()) > 20]
        for i, line in enumerate(lines[:max_results]):
            line = line.lstrip("0123456789.*-#•** ").strip()
            if not line:
                continue
            src = sources[i] if i < len(sources) else {}
            articles.append({
                "source": "Gemini/Google Search",
                "title": src.get("title") or line[:120],
                "description": line,
                "url": src.get("url", ""),
                "published": "",
                "category": topic or "general",
            })
        return articles
    except Exception as e:
        print(f"[Gemini] Error: {e}")
        return []


# ── Aggregators ───────────────────────────────────────────────────────────────

def fetch_all_news(topic=None):
    """Fetch from all available sources for a given topic."""
    all_articles = []

    all_articles += fetch_currents(category=topic if topic in CATEGORIES else None, max_articles=6)
    all_articles += fetch_guardian(topic=topic, max_articles=6)
    all_articles += fetch_newsdata(topic=topic, max_articles=6)
    all_articles += fetch_bbc_rss(category=topic or "general", max_articles=5)
    all_articles += fetch_ap_rss(max_articles=5)

    subreddit = REDDIT_SUBREDDITS.get(topic, "worldnews") if topic else "worldnews"
    all_articles += fetch_reddit(subreddit=subreddit, limit=6)

    if not topic or topic in ("technology", "science"):
        all_articles += fetch_hackernews(limit=5)

    # AI-powered live search (only runs if keys are set)
    all_articles += fetch_perplexity(topic=topic, max_results=5)
    all_articles += fetch_gemini_news(topic=topic, max_results=5)

    return all_articles


def fetch_by_category():
    """Fetch news grouped by category. Returns { category: [articles] }"""
    grouped = {}

    for category in CATEGORIES:
        articles = []
        articles += fetch_currents(category=category, max_articles=4)
        articles += fetch_guardian(topic=category, max_articles=4)
        articles += fetch_newsdata(topic=category, max_articles=4)
        articles += fetch_bbc_rss(category=category, max_articles=4)
        subreddit = REDDIT_SUBREDDITS.get(category, "news")
        articles += fetch_reddit(subreddit=subreddit, limit=4)
        if category == "technology":
            articles += fetch_hackernews(limit=4)
        grouped[category] = articles

    # World news: richest category — pulls from everything
    grouped["world news"] = (
        fetch_ap_rss(max_articles=6)
        + fetch_bbc_rss(category="world news", max_articles=6)
        + fetch_reddit(subreddit="worldnews", limit=6)
        + fetch_gemini_news(topic="world news today", max_results=4)
        + fetch_perplexity(topic="top world news today", max_results=4)
    )

    return grouped
