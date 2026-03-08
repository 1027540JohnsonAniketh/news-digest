"""
market_data.py — Real-time market data via Yahoo Finance (yfinance).

Provides:
  • get_market_strip()      → major global indices for the scrolling ticker tape
  • get_category_etfs(cat) → sector ETF data per World Pulse category
  • get_all_market_data()  → combined snapshot (strip + all categories)

All results are cached for 30 s so repeated page loads / auto-refresh don't
hammer Yahoo Finance. Market data is never cached beyond 30 s because prices
update continuously during trading hours.
"""

import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import yfinance as yf

# ── Short TTL cache (30 s — much shorter than news cache) ────────────────────
_MARKET_CACHE: dict = {}
_MARKET_TTL   = 30   # seconds

def _market_cached(key: str, fn):
    now = time.time()
    if key in _MARKET_CACHE:
        expires_at, result = _MARKET_CACHE[key]
        if now < expires_at:
            return result
    result = fn()
    _MARKET_CACHE[key] = (now + _MARKET_TTL, result)
    return result


# ── Global indices strip ──────────────────────────────────────────────────────
# Shown as a scrolling ticker tape across the top of the page.
MARKET_STRIP_TICKERS = [
    ("^GSPC",    "S&P 500"),
    ("^IXIC",    "NASDAQ"),
    ("^DJI",     "Dow Jones"),
    ("^VIX",     "VIX"),
    ("GLD",      "Gold"),
    ("BTC-USD",  "Bitcoin"),
    ("ETH-USD",  "Ethereum"),
    ("^TNX",     "10Y Yield"),
    ("CL=F",     "Crude Oil"),
    ("EURUSD=X", "EUR/USD"),
    ("JPY=X",    "USD/JPY"),
    ("^FTSE",    "FTSE 100"),
    ("^N225",    "Nikkei 225"),
]

# ── Category → Sector ETF mapping ────────────────────────────────────────────
# Two ETFs per category: the primary sector ETF + a specific popular ticker.
CATEGORY_ETFS = {
    "geopolitical":        [("SPY",     "S&P 500"),    ("GLD",   "Gold")],
    "finance_economy":     [("XLF",     "Financials"), ("TLT",   "T-Bonds")],
    "markets_crypto":      [("QQQ",     "NASDAQ"),     ("BTC-USD","Bitcoin")],
    "climate_environment": [("ICLN",    "Clean Nrg"),  ("XOP",   "Oil & Gas")],
    "technology_ai":       [("XLK",     "Tech"),       ("NVDA",  "NVIDIA")],
    "health_science":      [("XLV",     "Healthcare"), ("IBB",   "Biotech")],
    "energy_resources":    [("XLE",     "Energy"),     ("USO",   "Oil Fund")],
    "politics_policy":     [("SPY",     "S&P 500"),    ("^VIX",  "Volatility")],
    "innovation_space":    [("ARKK",    "ARK Innov"),  ("RKLB",  "Rocket Lab")],
    "culture_society":     [("XLY",     "Cons Disc"),  ("NFLX",  "Netflix")],
}


# ── Single-ticker fetcher ─────────────────────────────────────────────────────

def _fetch_one(symbol: str, label: str) -> dict:
    """Fetch price + daily change % for one ticker via yfinance.fast_info."""
    try:
        fi = yf.Ticker(symbol).fast_info
        price = fi.last_price
        prev  = fi.previous_close

        if price is None or prev is None or prev == 0:
            return _empty(symbol, label, "no data")

        change_pct = ((price - prev) / prev) * 100

        # Format price: crypto/indices may be very large or very small
        if price >= 1000:
            price_str = f"{price:,.0f}"
        elif price >= 10:
            price_str = f"{price:.2f}"
        else:
            price_str = f"{price:.4f}"

        return {
            "symbol":     symbol,
            "label":      label,
            "price":      round(price, 4),
            "price_str":  price_str,
            "change_pct": round(change_pct, 2),
            "direction":  "up" if change_pct >= 0 else "down",
            "error":      None,
        }
    except Exception as e:
        print(f"[Market] Error fetching {symbol}: {e}")
        return _empty(symbol, label, str(e))


def _empty(symbol: str, label: str, reason: str) -> dict:
    return {
        "symbol":     symbol,
        "label":      label,
        "price":      None,
        "price_str":  "—",
        "change_pct": None,
        "direction":  "flat",
        "error":      reason,
    }


def _fetch_batch(tickers: list[tuple]) -> list[dict]:
    """Fetch a list of (symbol, label) tuples concurrently."""
    with ThreadPoolExecutor(max_workers=min(len(tickers), 12)) as ex:
        futures = {ex.submit(_fetch_one, sym, lbl): (sym, lbl)
                   for sym, lbl in tickers}
        results = []
        for fut in as_completed(futures, timeout=15):
            try:
                results.append(fut.result())
            except Exception:
                sym, lbl = futures[fut]
                results.append(_empty(sym, lbl, "timeout"))

    # Restore original order
    order = {sym: i for i, (sym, _) in enumerate(tickers)}
    results.sort(key=lambda x: order.get(x["symbol"], 99))
    return results


# ── Public API ────────────────────────────────────────────────────────────────

def get_market_strip() -> list[dict]:
    """Return live data for all global indices (the scrolling ticker strip)."""
    return _market_cached(
        "strip",
        lambda: _fetch_batch(MARKET_STRIP_TICKERS)
    )


def get_category_etfs(category: str) -> list[dict]:
    """Return live ETF data for the two tickers mapped to `category`."""
    tickers = CATEGORY_ETFS.get(category, [])
    if not tickers:
        return []
    return _market_cached(
        f"cat:{category}",
        lambda: _fetch_batch(tickers)
    )


def get_all_market_data() -> dict:
    """Return strip + per-category ETF data in one combined snapshot."""
    from news_fetcher import CATEGORIES  # avoid circular import at module load

    def _fetch():
        # Run strip + all 10 category fetches concurrently
        strip_future = None
        cat_futures  = {}

        with ThreadPoolExecutor(max_workers=12) as ex:
            strip_future = ex.submit(get_market_strip)
            cat_futures  = {ex.submit(get_category_etfs, cat): cat
                            for cat in CATEGORIES}

            strip = strip_future.result(timeout=20)
            categories = {}
            for fut in as_completed(cat_futures, timeout=20):
                cat = cat_futures[fut]
                try:
                    categories[cat] = fut.result()
                except Exception:
                    categories[cat] = []

        return {"strip": strip, "categories": categories}

    return _market_cached("all", _fetch)
