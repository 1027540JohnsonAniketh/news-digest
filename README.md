# 📰 News Digest

A real-time news aggregator and AI summarizer. Pulls live headlines from multiple sources and uses Claude AI to summarize what's happening across topics and categories — with sentiment analysis and key bullet points.

---

## ✨ Features

- 🔍 **Topic Search** — Search any topic and get an instant AI summary
- 📂 **Full Category Digest** — Loads and summarizes all major news categories at once
- 🤖 **AI Summarization** — Powered by Claude (Anthropic) for concise, accurate summaries
- 📊 **Sentiment Analysis** — Each summary is tagged positive / negative / mixed / neutral
- 🔗 **Source Links** — Every summary links back to the original articles
- 🌙 **Dark UI** — Clean, responsive dark-theme interface

---

## 📡 News Sources

| Source | Coverage | Cost |
|--------|----------|------|
| [Currents API](https://currentsapi.services) | 80,000+ global sources, real-time | Free tier (600 req/day) |
| [The Guardian API](https://open-platform.theguardian.com) | Quality journalism, real-time | Free |
| [Reddit API](https://www.reddit.com/dev/api/) | Trending & viral topics, real-time | Free, no key needed |

---

## 🛠 Tech Stack

- **Backend** — Python 3.9, Flask, Gunicorn
- **AI** — Anthropic Claude (`claude-sonnet-4-6`)
- **Frontend** — Vanilla HTML / CSS / JavaScript
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
CURRENTS_API_KEY=your_currents_api_key_here
GUARDIAN_API_KEY=your_guardian_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here
```

| Key | Where to get it |
|-----|----------------|
| `CURRENTS_API_KEY` | [currentsapi.services](https://currentsapi.services) — free signup |
| `GUARDIAN_API_KEY` | [open-platform.theguardian.com/access](https://open-platform.theguardian.com/access) — free |
| `ANTHROPIC_API_KEY` | [console.anthropic.com](https://console.anthropic.com) — pay-as-you-go |

### 4. Run the server
```bash
python3.9 app.py
```

### 5. Open in browser
```
http://127.0.0.1:8080
```

---

## 🌐 Deploying to Render

1. Push the repo to GitHub
2. Go to [render.com](https://render.com) → **New Web Service** → connect your repo
3. Render auto-detects settings from `render.yaml`
4. Add your 3 API keys in the **Environment** tab on the Render dashboard
5. Click **Deploy** — your live URL will be `https://news-digest.onrender.com`

> **Note:** Render's free tier sleeps after 15 min of inactivity. First request after idle takes ~30 seconds.

---

## 📁 Project Structure

```
news-digest/
├── app.py              # Flask backend & API routes
├── news_fetcher.py     # Fetches from Currents, Guardian & Reddit
├── summarizer.py       # Claude AI summarization logic
├── requirements.txt    # Python dependencies
├── Procfile            # Render/Heroku start command
├── runtime.txt         # Python version pin
├── render.yaml         # Render deployment config
├── .env.example        # API key template (no real keys)
├── .gitignore          # Keeps .env out of git
└── frontend/
    ├── index.html      # Main UI
    ├── style.css       # Dark theme styles
    └── script.js       # Fetch & render logic
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
- Use `.env.example` with placeholder values for documentation
- Rotate API keys immediately if accidentally exposed in git history

---

## 📄 License

MIT
