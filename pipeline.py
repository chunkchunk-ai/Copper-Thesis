"""
Shared pipeline: fetch → score → save → summarize.
Called by both app.py (Streamlit) and run_daily.py (headless).
"""
from __future__ import annotations

import os
from datetime import date
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

from data_fetcher import fetch_all_prices, fetch_fred_data, fetch_news, fetch_copper_iv
from scorer import compute_scores
from history import (
    save_snapshot, load_latest, load_previous, load_history,
    save_iv, load_iv_history, compute_iv_rank,
)
from ai_summary import generate_summary


def is_trading_day(d: Optional[date] = None) -> bool:
    """Monday–Friday only.  Does not account for exchange holidays."""
    return (d or date.today()).weekday() < 5


def run(skip_weekend: bool = True, with_summary: bool = True) -> dict:
    """
    Execute the full pipeline and return a result dict.

    Keys:
        skipped     bool
        reason      str (when skipped)
        today       dict  — today's computed scores
        previous    dict|None
        history     list[dict]
        summary     str|None
        fetch_date  str  (ISO date)
        is_fresh    bool  — True when we actually fetched new data
    """
    today = date.today()

    if skip_weekend and not is_trading_day(today):
        # Load cached data from DB so the dashboard still works on weekends
        latest  = load_latest()
        history = load_history(90)
        return {
            "skipped":    True,
            "reason":     f"Weekend — showing most recent trading-day snapshot ({latest['date'] if latest else 'none'})",
            "today":      latest,
            "previous":   load_previous(),
            "history":    history,
            "summary":    None,
            "iv_data":    {"current": None, "rank": None, "history": load_iv_history(252)},
            "fetch_date": today.isoformat(),
            "is_fresh":   False,
        }

    fred_key      = os.environ.get("FRED_API_KEY", "")
    groq_key = os.environ.get("GROQ_API_KEY", "")

    prices   = fetch_all_prices()
    fred     = fetch_fred_data(fred_key)
    articles = fetch_news()

    scores = compute_scores(prices, fred, articles)
    save_snapshot(scores)

    # Options IV (FCX proxy for copper volatility)
    iv_current = fetch_copper_iv()
    if iv_current is not None:
        save_iv(iv_current)
    iv_history = load_iv_history(252)
    iv_rank    = compute_iv_rank(iv_current) if iv_current is not None else None

    previous = load_previous()
    history  = load_history(90)

    summary = None
    if with_summary and groq_key:
        summary = generate_summary(scores, previous, history, groq_key)

    return {
        "skipped":    False,
        "today":      scores,
        "previous":   previous,
        "history":    history,
        "summary":    summary,
        "iv_data":    {"current": iv_current, "rank": iv_rank, "history": iv_history},
        "fetch_date": today.isoformat(),
        "is_fresh":   True,
    }
