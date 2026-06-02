"""
Shared pipeline: fetch → score → save → summarize.
Called by both app.py (Streamlit) and run_daily.py (headless).
"""
from __future__ import annotations

import concurrent.futures
import os
from datetime import date, datetime, timezone, timedelta
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

from data_fetcher import fetch_all_prices, fetch_fred_data, fetch_news, fetch_copper_iv
from scorer import compute_scores
from history import (
    save_snapshot, load_latest, load_previous, load_history,
    save_iv, load_iv_history, compute_iv_rank,
    save_cot, load_cot_latest, load_cot_history,
)
from ai_summary import generate_summary
from market_analyst import (
    fetch_world_markets, fetch_cot_copper, fetch_spy_gamma,
    generate_market_implications, generate_world_market_brief,
)


def is_trading_day(d: Optional[date] = None) -> bool:
    """Monday–Friday only.  Does not account for exchange holidays."""
    return (d or date.today()).weekday() < 5


def _cot_is_stale(cot: dict) -> bool:
    """True if the COT data was fetched more than 7 days ago."""
    fetched = cot.get("fetched_utc")
    if not fetched:
        return True
    try:
        dt = datetime.fromisoformat(fetched)
        return (datetime.now(timezone.utc) - dt) > timedelta(days=7)
    except (ValueError, TypeError):
        return True


def run(skip_weekend: bool = True, with_summary: bool = True) -> dict:
    """
    Execute the full pipeline and return a result dict.

    Keys:
        skipped             bool
        reason              str (when skipped)
        today               dict  — today's computed scores
        previous            dict|None
        history             list[dict]
        summary             str|None
        iv_data             dict
        world_markets       dict
        gamma_data          dict|None
        cot_data            dict|None
        cot_history         list[dict]
        market_implications str|None
        world_brief         str|None
        fetch_date          str  (ISO date)
        is_fresh            bool
    """
    today = date.today()

    if skip_weekend and not is_trading_day(today):
        latest = load_latest()
        cot_latest = load_cot_latest()
        return {
            "skipped":             True,
            "reason":              f"Weekend — showing most recent trading-day snapshot ({latest['date'] if latest else 'none'})",
            "today":               latest,
            "previous":            load_previous(),
            "history":             load_history(90),
            "summary":             None,
            "iv_data":             {"current": None, "rank": None, "history": load_iv_history(252)},
            "world_markets":       fetch_world_markets(),
            "gamma_data":          None,
            "cot_data":            cot_latest,
            "cot_history":         load_cot_history(52),
            "market_implications": None,
            "world_brief":         None,
            "fetch_date":          today.isoformat(),
            "is_fresh":            False,
        }

    fred_key = os.environ.get("FRED_API_KEY", "")
    groq_key = os.environ.get("GROQ_API_KEY", "")

    # ── Parallel fetches (independent of each other) ──────────────────────────
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        f_prices      = pool.submit(fetch_all_prices)
        f_fred        = pool.submit(fetch_fred_data, fred_key)
        f_news        = pool.submit(fetch_news)
        f_iv          = pool.submit(fetch_copper_iv)
        f_world       = pool.submit(fetch_world_markets)
        f_gamma       = pool.submit(fetch_spy_gamma)

    prices   = f_prices.result()
    fred     = f_fred.result()
    articles = f_news.result()
    iv_current = f_iv.result()
    world_markets = f_world.result()
    gamma_data    = f_gamma.result()

    # ── COT: only refetch if stale (weekly data) ──────────────────────────────
    cot_data = load_cot_latest()
    if cot_data is None or _cot_is_stale(cot_data):
        fresh_cot = fetch_cot_copper()
        if fresh_cot:
            save_cot(fresh_cot)
            cot_data = fresh_cot

    # ── Score + persist ───────────────────────────────────────────────────────
    scores = compute_scores(prices, fred, articles)
    save_snapshot(scores)

    if iv_current is not None:
        save_iv(iv_current)
    iv_history = load_iv_history(252)
    iv_rank    = compute_iv_rank(iv_current) if iv_current is not None else None

    previous = load_previous()
    history  = load_history(90)

    # ── AI briefs ─────────────────────────────────────────────────────────────
    summary              = None
    market_implications  = None
    world_brief          = None

    if with_summary and groq_key:
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            f_summary      = pool.submit(generate_summary, scores, previous, history, groq_key)
            f_implications = pool.submit(generate_market_implications, scores, world_markets, groq_key)
            f_world_brief  = pool.submit(generate_world_market_brief, world_markets, articles, groq_key)

        summary             = f_summary.result()
        market_implications = f_implications.result()
        world_brief         = f_world_brief.result()

    return {
        "skipped":             False,
        "today":               scores,
        "previous":            previous,
        "history":             history,
        "summary":             summary,
        "iv_data":             {"current": iv_current, "rank": iv_rank, "history": iv_history},
        "world_markets":       world_markets,
        "gamma_data":          gamma_data,
        "cot_data":            cot_data,
        "cot_history":         load_cot_history(52),
        "market_implications": market_implications,
        "world_brief":         world_brief,
        "fetch_date":          today.isoformat(),
        "is_fresh":            True,
    }
