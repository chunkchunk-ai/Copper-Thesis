"""
Fetch raw data from yfinance, FRED, and RSS feeds.
Every fetch returns Optional values — callers must handle None.
"""
from __future__ import annotations

import asyncio
import html
import re
import xml.etree.ElementTree as ET
from datetime import date as _date, datetime, timedelta, timezone
from typing import Optional

import httpx
import pandas as pd
import yfinance as yf

from config import RSS_FEEDS, FRED_SERIES, YFINANCE_TICKERS

_NEWS_MAX_AGE_DAYS = 45

# ── yfinance ──────────────────────────────────────────────────────────────────

def _download_one(ticker: str, period: str = "2y") -> Optional[pd.Series]:
    """Return a pd.Series of daily closing prices or None on failure."""
    try:
        df = yf.download(ticker, period=period, auto_adjust=True, progress=False, threads=False)
        if df is None or df.empty:
            return None
        # Handle MultiIndex columns (newer yfinance versions)
        if isinstance(df.columns, pd.MultiIndex):
            if ("Close", ticker) in df.columns:
                close = df[("Close", ticker)].dropna()
            else:
                close = df["Close"].iloc[:, 0].dropna()
        else:
            if "Close" not in df.columns:
                return None
            close = df["Close"].dropna()
        return close if len(close) >= 5 else None
    except Exception:
        return None


def fetch_all_prices() -> dict[str, Optional[pd.Series]]:
    """Fetch closing-price series for all configured tickers plus the futures curve."""
    result = {key: _download_one(ticker) for key, ticker in YFINANCE_TICKERS.items()}
    result["copper_curve"] = fetch_copper_curve()
    return result


def fetch_copper_curve() -> Optional[pd.Series]:
    """
    Front-month / ~3M-deferred copper futures ratio.
    Ratio rising toward and above 1.0 = backwardation = physical tightness = bullish.
    Returns None if the deferred contract can't be fetched.
    """
    _ACTIVE_MONTHS = {3: "H", 5: "K", 7: "N", 9: "U", 12: "Z"}
    active = sorted(_ACTIVE_MONTHS)

    today = _date.today()
    target = today + timedelta(days=90)
    year, month = target.year, target.month
    deferred_m = next((m for m in active if m >= month), active[0])
    if deferred_m < month:
        year += 1
    ticker = f"HG{_ACTIVE_MONTHS[deferred_m]}{str(year)[2:]}.CMX"

    front    = _download_one("HG=F")
    deferred = _download_one(ticker)
    if front is None or deferred is None:
        return None

    idx = front.index.intersection(deferred.index)
    if len(idx) < 10:
        return None
    return (front.loc[idx] / deferred.loc[idx]).dropna()


# ── FRED ──────────────────────────────────────────────────────────────────────

def fetch_fred_data(api_key: str) -> dict[str, Optional[pd.Series]]:
    """Fetch FRED series. Returns empty dict if no api_key provided."""
    if not api_key:
        return {k: None for k in FRED_SERIES}
    try:
        from fredapi import Fred
        fred = Fred(api_key=api_key)
    except Exception:
        return {k: None for k in FRED_SERIES}

    result: dict[str, Optional[pd.Series]] = {}
    for key, series_id in FRED_SERIES.items():
        try:
            s = fred.get_series(series_id, observation_start="2021-01-01")
            result[key] = s.dropna() if s is not None and len(s) > 0 else None
        except Exception:
            result[key] = None
    return result


# ── RSS ───────────────────────────────────────────────────────────────────────

def _clean(text: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", text)).strip()


def _parse_pub_date(item: ET.Element) -> Optional[datetime]:
    """Parse <pubDate> RSS field. Returns None if missing or unparseable."""
    raw = item.findtext("pubDate") or ""
    if not raw:
        return None
    for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S GMT"):
        try:
            dt = datetime.strptime(raw.strip(), fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    return None


async def _fetch_feed(client: httpx.AsyncClient, url: str) -> list[dict]:
    try:
        r = await client.get(url, headers={"User-Agent": "CopperDash/1.0"}, timeout=8.0)
        if r.status_code != 200:
            return []
        root = ET.fromstring(r.content)
        cutoff = datetime.now(timezone.utc) - timedelta(days=_NEWS_MAX_AGE_DAYS)
        items = []
        for item in root.findall(".//item")[:20]:
            pub_dt = _parse_pub_date(item)
            if pub_dt is not None and pub_dt < cutoff:
                continue
            title = _clean(item.findtext("title") or "")
            desc  = _clean(item.findtext("description") or "")
            link  = item.findtext("link") or item.findtext("guid") or ""
            items.append({"title": title, "description": desc, "link": link})
        return items
    except Exception:
        return []


def fetch_copper_iv() -> float | None:
    """
    Fetch ATM implied volatility for FCX (Freeport-McMoRan) as a copper IV proxy.
    Returns annualized IV as a percentage (e.g. 35.2 = 35.2%) or None on failure.

    FCX is used because HG=F futures options are not available via yfinance.
    FCX has high beta to copper price and liquid options.
    """
    try:
        ticker = yf.Ticker("FCX")
        expirations = ticker.options
        if not expirations:
            return None

        # Find nearest expiry ≥ 7 days out (avoids gamma-pinning distortion)
        today_d = _date.today()
        valid = [
            e for e in expirations
            if (datetime.strptime(e, "%Y-%m-%d").date() - today_d).days >= 7
        ]
        if not valid:
            return None
        expiry = valid[0]

        # Get current FCX price
        price_series = _download_one("FCX")
        if price_series is None or price_series.empty:
            return None
        current_price = float(price_series.iloc[-1])

        # Fetch option chain
        chain = ticker.option_chain(expiry)
        calls = chain.calls
        puts  = chain.puts

        ivs: list[float] = []
        for df in (calls, puts):
            if df.empty or "impliedVolatility" not in df.columns or "strike" not in df.columns:
                continue
            # ATM = within 3% of current price
            atm = df[abs(df["strike"] - current_price) / current_price <= 0.03]
            raw = atm["impliedVolatility"].dropna()
            # Filter out zero/garbage values (yfinance occasionally returns 0)
            raw = raw[raw > 0.01]
            ivs.extend(raw.tolist())

        if not ivs:
            return None

        import numpy as np
        return round(float(np.median(ivs)) * 100, 1)  # convert to percentage
    except Exception:
        return None


def fetch_news() -> list[dict]:
    """Return deduplicated article list from all RSS feeds."""
    async def _run():
        async with httpx.AsyncClient(follow_redirects=True) as client:
            results = await asyncio.gather(*[_fetch_feed(client, url) for url in RSS_FEEDS])
        seen: set[str] = set()
        articles: list[dict] = []
        for batch in results:
            for item in batch:
                key = item.get("link") or item.get("title")
                if key and key not in seen:
                    seen.add(key)
                    articles.append(item)
        return articles

    try:
        try:
            asyncio.get_running_loop()
            # Already inside an event loop (e.g. Streamlit) — run in a thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, _run())
                return future.result(timeout=30)
        except RuntimeError:
            # No running loop — safe to call asyncio.run directly
            return asyncio.run(_run())
    except Exception:
        return []
