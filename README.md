# 📰 News Digest

A real-time news aggregator and AI summarizer. Pulls live headlines from **9 sources** and uses Claude AI to summarize what's happening across topics and categories — with sentiment analysis and key bullet points.

Installable as a **PWA** on both iPhone and Android (no App Store needed).

---

## ✨ Features

- 🔍 **Topic Search** — Search any topic and get an instant AI summary
- 📂 **Full Category Digest** — Loads and summarizes all major news categories at once
- 🤖 **AI Summarization** — Powered by Claude (Anthropic) for concise, accurate summaries
- 📊 **Sentiment Analysis** — Each summary is tagged positive / negative / mixed / neutral
- 🔗 **Source Links** — Every summary links back to the original articles
- 📱 **PWA** — Install on iPhone or Android home screen like a native app
- 🌙 **Dark UI** — Clean, responsive dark-theme interface

---

## 📡 News Sources (9 Total)

### Always Active — No Key Needed
| Source | Coverage | Notes |
|--------|----------|-------|
| [Reddit](https://reddit.com) | Trending & viral topics, real-time | Multiple subreddits per category |
| [BBC News RSS](https://bbc.co.uk/news) | World-class journalism, real-time | Per-category feeds |
| [AP News RSS](https://apnews.com) | Global breaking news wire, real-time | Top stories feed |
| [Hacker News](https://news.ycombinator.com) | Tech & startup news, real-time | Top stories, parallel fetch |

### Free API Key Required
| Source | Limit | Sign Up |
|--------|-------|---------|
| [Currents API](https://currentsapi.services) | 600 req/day | [currentsapi.services](https://currentsapi.services) |
| [The Guardian](https://theguardian.com) | Unlimited | [open-platform.theguardian.com](https://open-platform.theguardian.com/access) |
| [NewsData.io](https://newsdata.io) | 200 req/day + built-in sentiment | [newsdata.io](https://newsdata.io) |

### AI-Powered Live Web Search (Optional)
| Source | Limit | Sign Up |
|--------|-------|---------|
| [Gemini 2.0 Flash](https://aistudio.google.com) | **1,500 req/day FREE** — Google Search grounding | [aistudio.google.com/apikey](https://aistudio.google.com/apikey) |
| [Perplexity Sonar](https://perplexity.ai) | Pay-per-use, small free credit on signup | [perplexity.ai/settings/api](https://www.perplexity.ai/settings/api) |

---

## 🛠 Tech Stack

- **Backend** — Python 3.11, Flask, Gunicorn
- **AI Summarization** — Anthropic Claude (`claude-sonnet-4-6`)
- **AI Live Search** — Gemini 2.0 Flash (Google Search grounding) + Perplexity Sonar
- **RSS Parsing** — feedparser
- **Frontend** — Vanilla HTML / CSS / JavaScript
- **PWA** — Web App Manifest + Service Worker
- **Deployment** — Render

---

## 🚀 Getting Started (Local)

### 1. Clone the repo
```bash
git clone https://github.com/1027540JohnsonAniketh/news-digest.git
cd news-digest
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Set up API keys
```bash
cp .env.example .env
```

Edit `.env` and fill in your keys:

```env
# Required
ANTHROPIC_API_KEY=your_key_here

# Free news APIs
CURRENTS_API_KEY=your_key_here
GUARDIAN_API_KEY=your_key_here
NEWSDATA_API_KEY=your_key_here       # newsdata.io

# Optional — AI live search
GEMINI_API_KEY=your_key_here         # aistudio.google.com — 1500 req/day free!
PERPLEXITY_API_KEY=your_key_here     # perplexity.ai
```

> Reddit, BBC RSS, AP News and Hacker News need **no key** — they work out of the box.

### 4. Run the server
```bash
python3.9 app.py
```

### 5. Open in browser
```
http://127.0.0.1:8080
```

---

## 📱 Install as a Mobile App (PWA)

No App Store needed — install directly from your browser.

**iPhone** (Safari only):
1. Open your live URL in **Safari**
2. Tap the **Share** button → **"Add to Home Screen"**
3. Tap **Add** ✅

**Android** (Chrome):
1. Open your live URL in **Chrome**
2. Tap **⋮ menu** → **"Add to Home Screen"** / **"Install App"**
3. Tap **Install** ✅

---

## 🌐 Deploying to Render (Free)

1. Push the repo to GitHub
2. Go to [render.com](https://render.com) → **New Web Service** → connect your repo
3. Render auto-detects settings from `render.yaml`
4. Add your API keys in the **Environment** tab on the Render dashboard:
   - `ANTHROPIC_API_KEY` ← required
   - `CURRENTS_API_KEY`, `GUARDIAN_API_KEY`, `NEWSDATA_API_KEY`
   - `GEMINI_API_KEY`, `PERPLEXITY_API_KEY` ← optional but recommended
5. Click **Deploy**

Your live URL: `https://news-digest-xxxx.onrender.com`

> **Free tier note:** Render spins down after 15 min of inactivity. First visit after idle takes ~30 sec to wake up. Upgrade to **$7/mo Starter** to keep it always on.

---

## 📁 Project Structure

```
news-digest/
├── app.py              # Flask backend & API routes
├── news_fetcher.py     # All 9 news source fetchers
├── summarizer.py       # Claude AI summarization logic
├── requirements.txt    # Python dependencies (incl. feedparser)
├── Procfile            # Render/Heroku start command
├── runtime.txt         # Python version pin (3.11.9)
├── render.yaml         # Render deployment config + env var keys
├── .env.example        # API key template (no real keys)
├── .gitignore          # Keeps .env out of git
├── .claude/
│   └── launch.json     # Claude Code dev server config
└── frontend/
    ├── index.html      # Main UI + PWA meta tags
    ├── style.css       # Dark theme styles
    ├── script.js       # Fetch & render logic
    ├── manifest.json   # PWA manifest
    ├── sw.js           # Service worker (caches shell, live API calls)
    └── icons/
        ├── icon-192.png
        └── icon-512.png
```

---

## 🔌 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Serves the frontend |
| `GET` | `/api/health` | Check server status & key detection |
| `GET` | `/api/topic?q=<topic>` | Fetch & summarize a specific topic |
| `GET` | `/api/digest` | Full digest across all categories |
| `GET` | `/api/articles?q=<topic>` | Raw articles without summarization |

---

## ⚠️ Security Notes

- **Never commit your `.env` file** — it is listed in `.gitignore`
- Use `.env.example` with placeholder values only
- Rotate API keys immediately if accidentally exposed in git history

---

## 📄 License

MIT
