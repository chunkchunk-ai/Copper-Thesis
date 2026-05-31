"""
Scoring engine: converts raw price series and news into per-factor and composite scores.

Score range: 0–100 (100 = maximally bullish, 50 = neutral, 0 = maximally bearish).
Logistic squash prevents saturation at high z-scores (avoids the ±2σ cliff of linear clip).

Time horizons are rolling windows applied to live yfinance price history, so all three
horizons (1M / 6M / 1Y) are valid from day one.  The snapshot history in SQLite is only
for charting score evolution over time and computing day-over-day deltas.
"""
from __future__ import annotations

import math
from typing import Optional

import numpy as np
import pandas as pd

from config import (
    FACTOR_WEIGHTS,
    HORIZONS,
    MIN_VALID_SIGNALS,
    SIGNAL_THRESHOLDS,
    SUPPLY_DEFICIT_KEYWORDS,
    ELECTRIFICATION_KEYWORDS,
    AI_DATACENTER_KEYWORDS,
    CHINA_PMI_KEYWORDS,
    ORE_GRADE_KEYWORDS,
    TARIFF_KEYWORDS,
    INFRASTRUCTURE_KEYWORDS,
)


# ── Primitive scoring helpers ─────────────────────────────────────────────────

def _logistic(z: float) -> float:
    """Map z-score to (0, 100) via logistic.  Saturates at z≈±4 rather than ±2."""
    return 100.0 / (1.0 + math.exp(-z))


def _z_score(series: pd.Series, window: int) -> Optional[float]:
    """
    Z-score of the most recent value against the last `window` observations.
    Returns None if there is insufficient data or zero variance.
    """
    if len(series) < window + 1:
        return None
    tail = series.iloc[-window:]
    mean = float(tail.mean())
    std = float(tail.std())
    if std == 0 or math.isnan(std):
        return 0.0
    return (float(series.iloc[-1]) - mean) / std


def momentum_score(series: Optional[pd.Series], window: int) -> Optional[float]:
    """Score based on how far the current value sits above/below its rolling mean."""
    if series is None:
        return None
    z = _z_score(series, window)
    return None if z is None else _logistic(z)


def inverted_momentum_score(series: Optional[pd.Series], window: int) -> Optional[float]:
    """Same as momentum_score but bullish when the value falls (DXY, real yields, USD/CNY)."""
    if series is None:
        return None
    z = _z_score(series, window)
    return None if z is None else _logistic(-z)


def ratio_momentum_score(
    num: Optional[pd.Series],
    denom: Optional[pd.Series],
    window: int,
) -> Optional[float]:
    """Score momentum of num/denom ratio.  Returns None if either series is missing."""
    if num is None or denom is None:
        return None
    idx = num.index.intersection(denom.index)
    if len(idx) < window + 1:
        return None
    ratio = num.loc[idx] / denom.loc[idx].replace(0, np.nan)
    ratio = ratio.dropna()
    return momentum_score(ratio, window)


def news_score(articles: list[dict], keywords: dict[str, list[str]]) -> Optional[float]:
    """
    Polarity score from keyword matching across all articles.
    Returns 50 (neutral) when no keywords match at all.
    """
    if not articles:
        return 50.0

    bull_kw = [k.lower() for k in keywords.get("bullish", [])]
    bear_kw = [k.lower() for k in keywords.get("bearish", [])]

    bullish = 0
    bearish = 0
    for art in articles:
        text = (art.get("title", "") + " " + art.get("description", "")).lower()
        if any(kw in text for kw in bull_kw):
            bullish += 1
        if any(kw in text for kw in bear_kw):
            bearish += 1

    total = bullish + bearish
    if total == 0:
        return 50.0

    net = (bullish - bearish) / total
    return _logistic(net * 2.5)


# ── Factor aggregation ────────────────────────────────────────────────────────

def _factor_score(signals: list[Optional[float]]) -> Optional[float]:
    """
    Mean of valid (non-None) signals.
    Returns None if fewer than MIN_VALID_SIGNALS are available.
    """
    valid = [s for s in signals if s is not None]
    if len(valid) < MIN_VALID_SIGNALS:
        return None
    return float(np.mean(valid))


# ── Main scoring entry point ──────────────────────────────────────────────────

def compute_scores(
    prices: dict[str, object],
    fred: dict[str, object],
    articles: list[dict],
) -> dict:
    """
    Compute per-factor and composite scores for every configured horizon.

    Returns:
        {
            "factor_scores": {"1m": {factor: score|None, ...}, "6m": ..., "1y": ...},
            "composite":     {"1m": score|None, "6m": ..., "1y": ...},
            "signals":       {"1m": "INCREASE"|"HOLD"|"REDUCE"|"INSUFFICIENT DATA", ...},
            "factor_valid":  {factor: bool, ...},   # based on 1M availability
        }
    """
    result: dict = {
        "factor_scores": {},
        "composite": {},
        "signals": {},
        "factor_valid": {},
    }

    p = {k: (v if isinstance(v, pd.Series) else None) for k, v in prices.items()}
    f = {k: (v if isinstance(v, pd.Series) else None) for k, v in fred.items()}

    usd_cny    = f.get("usd_cny")
    real_yield = f.get("real_yield_10y")
    breakeven  = f.get("inflation_breakeven")
    cpi        = f.get("us_cpi")
    pce        = f.get("us_pce")
    indpro     = f.get("us_indpro")
    manuf_emp  = f.get("us_manuf_emp")
    sentiment  = f.get("consumer_sentiment")

    for horizon_key, window in HORIZONS.items():
        fs: dict[str, Optional[float]] = {}

        # ── Factor 1: Structural Supply Deficit ────────────────────────────────
        # Cu/Au ratio, miners ETF, news scans, Cu/Ag ratio, oil (AISC proxy),
        # ore grade / cost news, tariff risk, futures curve backwardation.
        # Raw copper momentum lives in Factor 7 to avoid double-counting.
        fs["supply_deficit"] = _factor_score([
            ratio_momentum_score(p.get("copper"), p.get("gold"), window),
            momentum_score(p.get("copx"), window),
            news_score(articles, SUPPLY_DEFICIT_KEYWORDS),
            ratio_momentum_score(p.get("copper"), p.get("silver"), window),
            momentum_score(p.get("oil"), window),
            news_score(articles, ORE_GRADE_KEYWORDS),
            news_score(articles, TARIFF_KEYWORDS),
            momentum_score(p.get("copper_curve"), window),
        ])

        # ── Factor 2: Global Electrification ──────────────────────────────────
        fs["electrification"] = _factor_score([
            momentum_score(p.get("cper"), window),
            momentum_score(p.get("xlu"), window),
            momentum_score(p.get("copx"), window),
            news_score(articles, ELECTRIFICATION_KEYWORDS),
            news_score(articles, INFRASTRUCTURE_KEYWORDS),
        ])

        # ── Factor 3: AI & Data Center ────────────────────────────────────────
        fs["ai_datacenter"] = _factor_score([
            momentum_score(p.get("vst"), window),
            momentum_score(p.get("ceg"), window),
            momentum_score(p.get("xlk"), window),
            news_score(articles, AI_DATACENTER_KEYWORDS),
        ])

        # ── Factor 4: Global Industrial Demand ────────────────────────────────
        # China-centric but also captures USD/CNY and Cu/Au cross-asset signal.
        fs["global_demand"] = _factor_score([
            momentum_score(p.get("fxi"), window),
            inverted_momentum_score(usd_cny, window),
            ratio_momentum_score(p.get("copper"), p.get("gold"), window),
            news_score(articles, CHINA_PMI_KEYWORDS),
        ])

        # ── Factor 5: Inventory Levels ────────────────────────────────────────
        fs["inventories"] = _factor_score([
            ratio_momentum_score(p.get("cper"), p.get("copx"), window),
            momentum_score(p.get("copper"), min(window, 21)),
        ])

        # ── Factor 6: Macro — Rates, Inflation & Cycle ────────────────────────
        # DXY + real yield (inverted), inflation breakeven + CPI + PCE (rising = bullish
        # for commodities), industrial production + manufacturing employment + consumer
        # sentiment (cycle indicators).
        fs["macro"] = _factor_score([
            inverted_momentum_score(p.get("dxy"), window),
            inverted_momentum_score(real_yield, window),
            ratio_momentum_score(p.get("tip"), p.get("tlt"), window),
            momentum_score(breakeven, window),
            momentum_score(cpi, window),
            momentum_score(pce, window),
            momentum_score(indpro, window),
            momentum_score(manuf_emp, window),
            momentum_score(sentiment, window),
        ])

        # ── Factor 7: Copper Price Dynamics ───────────────────────────────────
        # Copper momentum, miners/copper ratio (true strength: miners outperforming
        # = future demand being priced in), Cu/Au ratio.
        fs["copper_price"] = _factor_score([
            momentum_score(p.get("copper"), window),
            ratio_momentum_score(p.get("copx"), p.get("copper"), window),
            ratio_momentum_score(p.get("copper"), p.get("gold"), window),
        ])

        # ── Composite: re-normalize weights across valid factors only ──────────
        horizon_weights = FACTOR_WEIGHTS[horizon_key]
        valid = {k: v for k, v in fs.items() if v is not None}
        valid_weight_sum = sum(horizon_weights[k] for k in valid)

        if valid and valid_weight_sum > 0:
            composite = sum(v * horizon_weights[k] / valid_weight_sum for k, v in valid.items())
        else:
            composite = None

        result["factor_scores"][horizon_key] = fs
        result["composite"][horizon_key] = round(composite, 1) if composite is not None else None

        if composite is None:
            sig = "INSUFFICIENT DATA"
        elif composite >= SIGNAL_THRESHOLDS["increase"]:
            sig = "INCREASE"
        elif composite < SIGNAL_THRESHOLDS["reduce"]:
            sig = "REDUCE"
        else:
            sig = "HOLD"
        result["signals"][horizon_key] = sig

    result["factor_valid"] = {
        k: result["factor_scores"]["1m"].get(k) is not None
        for k in FACTOR_WEIGHTS["1m"]
    }

    return result
