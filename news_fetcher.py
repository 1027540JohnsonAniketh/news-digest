import os
import requests


CURRENTS_API_KEY = os.getenv("CURRENTS_API_KEY")
GUARDIAN_API_KEY = os.getenv("GUARDIAN_API_KEY")

CATEGORIES = ["technology", "politics", "business", "health", "sports", "science", "entertainment"]

REDDIT_SUBREDDITS = {
    "world news": "worldnews",
    "technology": "technology",
    "politics": "politics",
    "business": "business",
    "science": "science",
    "sports": "sports",
    "entertainment": "entertainment",
}


def fetch_currents(category=None, language="en", max_articles=10):
    """Fetch real-time headlines from Currents API."""
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


def fetch_guardian(topic=None, max_articles=10):
    """Fetch real-time articles from The Guardian API."""
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


def fetch_reddit(subreddit="worldnews", limit=10):
    """Fetch trending posts from Reddit (no API key required)."""
    url = f"https://www.reddit.com/r/{subreddit}/hot.json"
    headers = {"User-Agent": "NewsDigestApp/1.0"}
    params = {"limit": limit}

    try:
        resp = requests.get(url, headers=headers, params=params, timeout=10)
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


def fetch_all_news(topic=None):
    """
    Fetch from all three sources and return combined results.
    If topic is given, target that topic specifically.
    """
    all_articles = []

    # Currents: fetch by category or general
    currents_category = topic if topic in CATEGORIES else None
    all_articles += fetch_currents(category=currents_category, max_articles=8)

    # Guardian: search by topic keyword
    all_articles += fetch_guardian(topic=topic, max_articles=8)

    # Reddit: pick matching subreddit or fall back to worldnews
    subreddit = REDDIT_SUBREDDITS.get(topic, "worldnews") if topic else "worldnews"
    all_articles += fetch_reddit(subreddit=subreddit, limit=8)

    return all_articles


def fetch_by_category():
    """
    Fetch news grouped by category from all sources.
    Returns a dict: { category: [articles] }
    """
    grouped = {}

    for category in CATEGORIES:
        articles = []
        articles += fetch_currents(category=category, max_articles=5)
        articles += fetch_guardian(topic=category, max_articles=5)
        subreddit = REDDIT_SUBREDDITS.get(category, "news")
        articles += fetch_reddit(subreddit=subreddit, limit=5)
        grouped[category] = articles

    # Also grab general world news
    grouped["world news"] = fetch_reddit(subreddit="worldnews", limit=8)

    return grouped
