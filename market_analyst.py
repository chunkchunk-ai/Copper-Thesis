"""
World market data, dealer gamma (GEX), CFTC COT, and cross-asset AI briefs.
All fetch functions return None on failure - callers must handle gracefully.
"""
from __future__ import annotations

import concurrent.futures
import io
import json
import math
import re
from datetime import date, datetime, timedelta, timezone
from typing import Optional

import httpx
import numpy as np
import pandas as pd

from config import (
    COT_URL,
    COT_COPPER_NAME,
    CENTRAL_BANK_KEYWORDS,
    WORLD_MARKET_TICKERS,
    FACTOR_LABELS,
)
from data_fetcher import _download_one


# ── World market prices ───────────────────────────────────────────────────────

def _pct_change(series: pd.Series, bars: int) -> Optional[float]:
    if series is None or len(series) < bars + 1:
        return None
    old = float(series.iloc[-(bars + 1)])
    new = float(series.iloc[-1])
    if old == 0:
        return None
    return round((new - old) / old * 100, 2)


def _fetch_one_market(name: str, ticker: str) -> dict:
    series = _download_one(ticker, period="2y")
    if series is None or series.empty:
        return {"name": name, "ticker": ticker, "price": None,
                "chg_1d_pct": None, "chg_1m_pct": None, "chg_1y_pct": None}
    return {
        "name":       name,
        "ticker":     ticker,
        "price":      round(float(series.iloc[-1]), 2),
        "chg_1d_pct": _pct_change(series, 1),
        "chg_1m_pct": _pct_change(series, 21),
        "chg_1y_pct": _pct_change(series, 252),
    }


def fetch_world_markets() -> dict[str, dict]:
    """Fetch all world market indices in parallel. Returns {name: market_dict}."""
    results: dict[str, dict] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        futures = {
            pool.submit(_fetch_one_market, name, ticker): name
            for name, ticker in WORLD_MARKET_TICKERS.items()
        }
        for fut in concurrent.futures.as_completed(futures):
            data = fut.result()
            results[data["name"]] = data
    # Return in original order
    return {name: results[name] for name in WORLD_MARKET_TICKERS if name in results}


# ── CFTC COT data ─────────────────────────────────────────────────────────────

def fetch_cot_copper() -> Optional[dict]:
    """
    Download CFTC Legacy COT (futures only) and extract the copper row.
    Returns None on any fetch/parse failure.
    """
    try:
        r = httpx.get(COT_URL, timeout=15.0, headers={"User-Agent": "CopperDash/1.0"})
        if r.status_code != 200:
            return None

        # Parse comma-delimited with pandas
        df = pd.read_csv(io.StringIO(r.text), low_memory=False)
        df.columns = [c.strip() for c in df.columns]

        # Find the copper row - market name column varies by year
        name_col = next(
            (c for c in df.columns if "market" in c.lower() and "exchange" in c.lower()),
            df.columns[0],
        )
        mask = df[name_col].astype(str).str.contains(COT_COPPER_NAME, case=False, na=False)
        copper_rows = df[mask]
        if copper_rows.empty:
            return None

        row = copper_rows.iloc[0]

        def _int(col: str) -> int:
            # Prefer exact (case-insensitive) match; fall back to substring containment.
            target = col.lower()
            exact = next((c for c in df.columns if c.lower() == target), None)
            candidates = [exact] if exact else [c for c in df.columns if target in c.lower()]
            for c in candidates:
                try:
                    return int(str(row[c]).replace(",", ""))
                except (ValueError, TypeError):
                    pass
            return 0

        def _date_str() -> str:
            for c in df.columns:
                if "report_date" in c.lower() or ("date" in c.lower() and "as_mm" in c.lower()):
                    raw = str(row[c]).strip()
                    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m-%d-%Y"):
                        try:
                            return datetime.strptime(raw, fmt).date().isoformat()
                        except ValueError:
                            continue
            return date.today().isoformat()

        spec_long  = _int("noncomm_positions_long_all")
        spec_short = _int("noncomm_positions_short_all")
        comm_long  = _int("comm_positions_long_all")
        comm_short = _int("comm_positions_short_all")
        oi         = _int("open_interest_all")
        chg        = (_int("change_in_noncomm_positions_long_all")
                      - _int("change_in_noncomm_positions_short_all"))

        return {
            "date":          _date_str(),
            "open_interest": oi,
            "spec_long":     spec_long,
            "spec_short":    spec_short,
            "spec_net":      spec_long - spec_short,
            "comm_long":     comm_long,
            "comm_short":    comm_short,
            "comm_net":      comm_long - comm_short,
            "spec_net_chg":  chg,
        }
    except Exception:
        return None


# ── SPY Dealer Gamma (GEX) ────────────────────────────────────────────────────

def _bs_gamma(S: float, K: float, T: float, r: float, sigma: float) -> float:
    """Black-Scholes gamma (identical for calls and puts)."""
    if T <= 0 or sigma <= 0.001 or S <= 0 or K <= 0:
        return 0.0
    try:
        d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
        return math.exp(-0.5 * d1 ** 2) / (math.sqrt(2 * math.pi) * S * sigma * math.sqrt(T))
    except (ValueError, ZeroDivisionError):
        return 0.0


def fetch_spy_gamma() -> Optional[dict]:
    """
    Compute approximate SPY dealer GEX from yfinance options chain.
    Uses Black-Scholes gamma computed from implied volatility (numpy only, no extra deps).
    Front 4 expirations: 2 nearest weeklies + 2 nearest monthlies.

    Formula: GEX_per_strike = gamma × OI × 100 × spot² × 0.01
    Calls: positive (dealers short calls → long gamma)
    Puts:  negative (dealers short puts → short gamma on downside)
    """
    try:
        import yfinance as yf

        ticker = yf.Ticker("SPY")
        expirations = ticker.options
        if not expirations:
            return None

        price_series = _download_one("SPY")
        if price_series is None or price_series.empty:
            return None
        spot = float(price_series.iloc[-1])
        today_d = date.today()

        # Select front 4: nearest 2 weeklies (any expiry) + next 2 monthly expiries
        # Monthly = expiry on a Friday of week 3 (approx: day 15–21)
        valid_expiries = [
            e for e in expirations
            if (datetime.strptime(e, "%Y-%m-%d").date() - today_d).days >= 1
        ]
        if not valid_expiries:
            return None

        def _is_monthly(e: str) -> bool:
            d = datetime.strptime(e, "%Y-%m-%d").date()
            return 15 <= d.day <= 21 and d.weekday() == 4  # 3rd Friday approx

        weeklies  = valid_expiries[:4]
        monthlies = [e for e in valid_expiries if _is_monthly(e)][:2]
        selected  = list(dict.fromkeys(weeklies[:2] + monthlies))[:4]
        if not selected:
            selected = valid_expiries[:4]

        r_rate = 0.045  # risk-free rate proxy
        strike_gex: dict[float, float] = {}

        for expiry in selected:
            T = (datetime.strptime(expiry, "%Y-%m-%d").date() - today_d).days / 365.0
            if T <= 0:
                continue
            try:
                chain = ticker.option_chain(expiry)
            except Exception:
                continue

            for df, sign in ((chain.calls, 1.0), (chain.puts, -1.0)):
                if df.empty:
                    continue
                for _, opt in df.iterrows():
                    K      = float(opt.get("strike", 0) or 0)
                    oi     = float(opt.get("openInterest") or 0)
                    vol    = float(opt.get("volume") or 0)
                    iv     = float(opt.get("impliedVolatility") or 0)
                    # NaN guard: NaN is truthy so `or 0` doesn't catch yfinance NaNs.
                    if K != K or oi != oi: oi = 0.0
                    if vol != vol: vol = 0.0
                    if iv != iv: iv = 0.0
                    # yfinance/Yahoo frequently returns 0 openInterest for SPY
                    # (especially puts and near-dated expiries). Fall back to
                    # today's volume as a dealer-exposure proxy when OI is missing.
                    contracts = oi if oi > 0 else vol
                    # Cap pathological IVs (deep ITM/OTM yfinance often reports >5.0)
                    if K <= 0 or contracts <= 0 or iv <= 0.01 or iv > 3.0:
                        continue
                    gamma  = _bs_gamma(spot, K, T, r_rate, iv)
                    if gamma != gamma:  # NaN guard on gamma output
                        continue
                    gex    = sign * gamma * contracts * 100.0 * (spot ** 2) * 0.01
                    strike_gex[K] = strike_gex.get(K, 0.0) + gex

        if not strike_gex:
            return None

        # Filter to ±10% of spot for display
        lo, hi = spot * 0.90, spot * 1.10
        display_gex = {k: v for k, v in strike_gex.items() if lo <= k <= hi}

        strikes_sorted = sorted(strike_gex.keys())
        cumulative     = 0.0
        gamma_flip     = None
        for k in strikes_sorted:
            prev = cumulative
            cumulative += strike_gex[k]
            if prev < 0 <= cumulative or prev > 0 >= cumulative:
                gamma_flip = k

        net_gex  = sum(strike_gex.values()) / 1e6
        call_gex = sum(v for v in strike_gex.values() if v > 0) / 1e6
        put_gex  = sum(v for v in strike_gex.values() if v < 0) / 1e6

        top_strikes = sorted(display_gex.items(), key=lambda x: abs(x[1]), reverse=True)[:5]

        strike_gex_list = [
            {"strike": k, "gex": round(v / 1e6, 3)}
            for k, v in sorted(display_gex.items())
        ]

        return {
            "net_gex":    round(net_gex, 2),
            "call_gex":   round(call_gex, 2),
            "put_gex":    round(put_gex, 2),
            "gamma_flip": round(gamma_flip, 2) if gamma_flip else None,
            "spot":       round(spot, 2),
            "regime":     "LONG GAMMA" if net_gex >= 0 else "SHORT GAMMA",
            "top_strikes": [{"strike": k, "gex": round(v / 1e6, 3)} for k, v in top_strikes],
            "strike_gex":  strike_gex_list,
        }
    except Exception:
        return None


# ── AI cross-asset analysis ───────────────────────────────────────────────────

def _strip_think(text: str) -> str:
    """Remove DeepSeek-R1 chain-of-thought <think>...</think> tags."""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


def _world_market_table(world_markets: dict) -> str:
    lines = ["Market          | 1D %   | 1M %   | 1Y %"]
    lines.append("-" * 45)
    for name, m in world_markets.items():
        def _fmt(v):
            return f"{v:+.1f}%" if v is not None else "n/a"
        lines.append(f"{name:<16}| {_fmt(m.get('chg_1d_pct')):<7}| {_fmt(m.get('chg_1m_pct')):<7}| {_fmt(m.get('chg_1y_pct'))}")
    return "\n".join(lines)


def _filter_cb_articles(articles: list[dict]) -> list[str]:
    """Return headlines mentioning central bank keywords."""
    cb_terms = [
        "federal reserve", "fed ", "ecb", "bank of japan", "boj", "pboc",
        "bank of england", "boe", "central bank", "interest rate", "monetary policy",
        "powell", "lagarde", "ueda", "inflation",
    ]
    headlines = []
    for art in articles:
        text = (art.get("title", "") + " " + art.get("description", "")).lower()
        if any(t in text for t in cb_terms):
            headlines.append(art.get("title", "").strip())
    return headlines[:20]


def generate_market_implications(
    copper_data: dict,
    world_markets: dict,
    groq_key: str,
) -> str:
    if not groq_key:
        return "Set GROQ_API_KEY to enable Market Implications analysis."
    try:
        from groq import Groq

        composite  = copper_data.get("composite", {})
        signals    = copper_data.get("signals", {})
        fs_1m      = copper_data.get("factor_scores", {}).get("1m", {})

        # Top 2 factors by score deviation from 50
        top_factors = sorted(
            [(k, v) for k, v in fs_1m.items() if v is not None],
            key=lambda x: abs(x[1] - 50), reverse=True
        )[:2]
        top_factor_text = "; ".join(
            f"{FACTOR_LABELS.get(k, k)} = {v:.0f}" for k, v in top_factors
        )

        vix_entry  = world_markets.get("VIX", {})
        vix_level  = vix_entry.get("price")
        mkt_table  = _world_market_table({k: v for k, v in world_markets.items() if k != "VIX"})

        system_prompt = (
            "You are a senior cross-asset macro analyst. You understand how copper - "
            "as the leading industrial metal - signals broader economic conditions. "
            "Your job is to reason from a copper thesis signal to second-order market implications "
            "across equities, bonds, FX, commodities, and emerging markets. "
            "Be specific with directional language. Write flowing analyst prose - no bullets, no headers."
        )

        user_msg = f"""Copper thesis scores today:
1M composite: {composite.get('1m')} → {signals.get('1m')}
6M composite: {composite.get('6m')} → {signals.get('6m')}
1Y composite: {composite.get('1y')} → {signals.get('1y')}
Top moving factors: {top_factor_text}
VIX: {vix_level}

World market performance:
{mkt_table}

Write a 4–6 sentence analyst note covering:
1. What today's copper signal implies for industrial and cyclical equities
2. Bond market and real yield implications
3. FX / USD effects
4. The commodity complex (oil, gold, silver, miners)
5. Emerging market read-through
6. One key risk or divergence to watch

Rules: specific numbers, flowing prose, no headers or bullets, write as if briefing a PM before market open."""

        client = Groq(api_key=groq_key)
        resp = client.chat.completions.create(
            model="deepseek-r1-distill-llama-70b",
            max_tokens=500,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_msg},
            ],
        )
        return _strip_think(resp.choices[0].message.content.strip())
    except Exception as exc:
        return f"Market implications unavailable: {exc}"


def generate_world_market_brief(
    world_markets: dict,
    articles: list[dict],
    groq_key: str,
) -> str:
    if not groq_key:
        return "Set GROQ_API_KEY to enable World Market analysis."
    try:
        from groq import Groq

        mkt_table  = _world_market_table(world_markets)
        cb_headlines = _filter_cb_articles(articles)
        headlines_text = "\n".join(f"- {h}" for h in cb_headlines) if cb_headlines else "No central bank headlines available."

        system_prompt = (
            "You are a global macro strategist. You monitor equity, FX, and rates markets "
            "across all major regions and track central bank policy divergence. "
            "Write concise, insight-dense analyst prose - no bullets, no headers."
        )

        user_msg = f"""World market performance today:
{mkt_table}

Recent central bank / macro headlines:
{headlines_text}

Write a 4–6 sentence global macro brief covering:
1. Which regions are outperforming or underperforming and the likely driver
2. Central bank policy divergence (Fed vs ECB vs BoJ vs PBoC) based on headlines
3. Whether global risk appetite is expanding or contracting
4. One macro theme or risk to watch this week

Rules: flowing analyst prose, no bullets or headers, specific and opinionated."""

        client = Groq(api_key=groq_key)
        resp = client.chat.completions.create(
            model="deepseek-r1-distill-llama-70b",
            max_tokens=450,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_msg},
            ],
        )
        return _strip_think(resp.choices[0].message.content.strip())
    except Exception as exc:
        return f"World market brief unavailable: {exc}"
