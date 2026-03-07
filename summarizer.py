import os
from pathlib import Path
import anthropic
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent / ".env", override=True)

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


def _build_articles_text(articles):
    """Format a list of articles into plain text for the prompt."""
    lines = []
    for i, a in enumerate(articles, 1):
        title = a.get("title", "").strip()
        desc = a.get("description", "").strip()
        source = a.get("source", "")
        if title:
            lines.append(f"{i}. [{source}] {title}")
            if desc and desc != title:
                lines.append(f"   {desc[:300]}")
    return "\n".join(lines)


def summarize_topic(topic, articles):
    """
    Summarize what is happening around a given topic
    based on the provided list of articles.
    Returns a dict with keys: summary, key_points, sentiment
    """
    if not articles:
        return {
            "summary": "No articles found for this topic.",
            "key_points": [],
            "sentiment": "neutral",
        }

    articles_text = _build_articles_text(articles)

    prompt = f"""You are a news analyst. Below are recent news headlines and descriptions about "{topic}".

{articles_text}

Please provide:
1. A concise 3-4 sentence summary of what is happening around this topic right now.
2. 4-5 bullet point key takeaways.
3. The overall sentiment of the news: positive, negative, mixed, or neutral.

Respond in this exact JSON format:
{{
  "summary": "...",
  "key_points": ["...", "...", "...", "..."],
  "sentiment": "positive|negative|mixed|neutral"
}}"""

    try:
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        import json
        text = message.content[0].text.strip()
        # Extract JSON if wrapped in markdown code block
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text.strip())
    except Exception as e:
        print(f"[Summarizer] Error for topic '{topic}': {e}")
        return {
            "summary": "Summary unavailable at this time.",
            "key_points": [],
            "sentiment": "neutral",
        }


def summarize_all_categories(grouped_articles):
    """
    Takes a dict of { category: [articles] } and returns
    { category: { summary, key_points, sentiment, article_count, articles } }
    """
    results = {}
    for category, articles in grouped_articles.items():
        print(f"  Summarizing: {category} ({len(articles)} articles)...")
        summary_data = summarize_topic(category, articles)
        results[category] = {
            **summary_data,
            "article_count": len(articles),
            "articles": [
                {
                    "title": a.get("title", ""),
                    "url": a.get("url", ""),
                    "source": a.get("source", ""),
                    "published": a.get("published", ""),
                }
                for a in articles[:5]  # Return top 5 article links
            ],
        }
    return results


def generate_overall_digest(category_summaries):
    """
    Generate one overall digest summarizing all categories together.
    """
    if not category_summaries:
        return "No news data available."

    topic_lines = []
    for cat, data in category_summaries.items():
        topic_lines.append(f"- {cat.upper()}: {data.get('summary', '')}")

    combined = "\n".join(topic_lines)

    prompt = f"""You are a news digest editor. Here are summaries from multiple news categories today:

{combined}

Write a 4-5 sentence overall digest that gives the reader a high-level picture of what is happening in the world today. Be concise and informative."""

    try:
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text.strip()
    except Exception as e:
        print(f"[Summarizer] Overall digest error: {e}")
        return "Overall digest unavailable."
