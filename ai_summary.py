"""
AI analyst summary via Groq (free tier — Llama-3.3-70b-versatile).
Same model used by the Jarvis/Friday agent. Reuse your existing GROQ_API_KEY.
Falls back gracefully if the key is absent or the call fails.
"""
from __future__ import annotations

import json
from typing import Optional

from groq import Groq

from config import FACTOR_LABELS, FACTOR_WEIGHTS, THESIS_BREAKS

_THESIS_CONTEXT = """You are an expert commodity analyst tracking a structured 7-factor copper investment thesis.

THESIS STATEMENT:
"Copper is the bottleneck metal of electrification. Demand from AI, data centers, grid expansion, EVs, and industrial electrification is growing faster than global mine supply can respond due to declining ore grades, permitting constraints, and decade-long development timelines."

THE SEVEN FACTORS (1M weight shown; supply deficit rises to 36% at 1Y as structural thesis dominates):
""" + "\n".join(
    f"  {i+1}. {FACTOR_LABELS[k]} ({int(FACTOR_WEIGHTS['1m'][k]*100)}% weight at 1M)"
    for i, k in enumerate(FACTOR_LABELS)
) + """

SCORING SCALE: 0–100 per factor and composite (100 = maximally bullish, 50 = neutral, 0 = maximally bearish).
COMPOSITE SIGNALS: INCREASE (≥62), HOLD (42–61), REDUCE (<42).

TIME HORIZONS TRACKED:
  - 1-Month  (21 trading days): short-term momentum
  - 6-Month  (126 trading days): medium-term trend
  - 1-Year   (252 trading days): long-term structural position

THESIS BREAK CONDITIONS (watch for these):
""" + "\n".join(f"  • {b}" for b in THESIS_BREAKS) + """

SUPPLY CONTEXT:
Copper mine development timelines are 8–15 years from discovery to production.
Supply cannot respond quickly even if prices spike. This structural inelasticity
is the core asymmetry underlying the bull thesis.

DEMAND DRIVERS THAT MATTER MOST:
  • AI data centers: second-order effect is grid upgrades (transformers, substations, transmission)
  • Grid replacement: aging US/EU grid requires copper-intensive overhaul
  • EV adoption: EVs use 3–4× more copper than ICE vehicles
  • Ore grade decline: miners must process more rock for the same output each cycle
"""

_USER_TEMPLATE = """Analyze the copper thesis data below and write a 3–5 sentence analyst brief for the portfolio manager.

Cover:
1. Overall direction since yesterday (or "first reading" if no prior data) and magnitude
2. The 1–2 factors that moved most and why the market signal implies this
3. The divergence between short-term (1M) and long-term (1Y) signals, if meaningful
4. The most important thesis risk to watch given today's readings

Rules:
• Be specific with numbers (e.g., "supply deficit factor fell from 74 to 68")
• No bullet points, no headers — flowing analyst prose only
• Write as if briefing a PM 5 minutes before market open
• If a factor shows "null" it means insufficient signal data — mention this briefly if material

TODAY'S SNAPSHOT:
{today_json}

PRIOR SNAPSHOT (date: {prior_date}):
{prior_json}

30-DAY COMPOSITE TREND (1M horizon, oldest→newest):
{trend_json}
"""


def generate_summary(
    today: dict,
    previous: Optional[dict],
    trend: list[dict],
    api_key: str,
) -> str:
    if not api_key:
        return "Set GROQ_API_KEY in .env to enable AI summaries."

    today_payload = {
        "composite":        today.get("composite"),
        "signals":          today.get("signals"),
        "factor_scores_1m": today.get("factor_scores", {}).get("1m"),
        "factor_scores_6m": today.get("factor_scores", {}).get("6m"),
        "factor_scores_1y": today.get("factor_scores", {}).get("1y"),
    }

    if previous:
        prior_payload = {
            "composite":        previous.get("composite"),
            "signals":          previous.get("signals"),
            "factor_scores_1m": previous.get("factor_scores", {}).get("1m"),
        }
        prior_date = previous.get("date", "unknown")
    else:
        prior_payload = None
        prior_date = "none"

    trend_points = [
        {"date": r["date"], "composite_1m": r["composite"].get("1m")}
        for r in (trend or [])[-30:]
    ]

    user_msg = _USER_TEMPLATE.format(
        today_json=json.dumps(today_payload, indent=2),
        prior_date=prior_date,
        prior_json=json.dumps(prior_payload, indent=2) if prior_payload else "No prior snapshot available.",
        trend_json=json.dumps(trend_points),
    )

    try:
        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            max_tokens=450,
            messages=[
                {"role": "system", "content": _THESIS_CONTEXT},
                {"role": "user",   "content": user_msg},
            ],
        )
        return response.choices[0].message.content.strip()
    except Exception as exc:
        return f"Summary unavailable: {exc}"
