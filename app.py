"""
Copper Thesis Dashboard — Streamlit UI.
Run: python -m streamlit run copper/app.py
"""
from __future__ import annotations

import os
import sys
from datetime import date, datetime

import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(__file__))
load_dotenv()

from config import FACTOR_LABELS, FACTOR_WEIGHTS, SIGNAL_THRESHOLDS, THESIS_BREAKS
from history import (
    load_today, load_latest, load_previous, load_history, snapshot_count,
    load_iv_history, compute_iv_rank,
    load_cot_latest, load_cot_history,
)
from pipeline import run
from data_fetcher import _download_one

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Cu — Copper Thesis",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Design system ─────────────────────────────────────────────────────────────
_BG        = "#0b0d11"
_PANEL     = "#131620"
_PANEL2    = "#1a1d27"
_BORDER    = "#252830"
_TXT       = "#d4d8e8"
_TXT2      = "#6b7080"
_TXT3      = "#454a58"
_GREEN     = "#4f9960"
_AMBER     = "#c4942a"
_RED       = "#9e4040"
_BLUE      = "#4a7fc4"
_TEAL      = "#3a8a7a"
_GOLD      = "#c4a040"
_PURPLE    = "#7060aa"
_COPPER    = "#b87333"

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

html, body, [class*="css"] {{
  font-family: 'Inter', sans-serif;
}}
.stApp {{
  background: {_BG};
  color: {_TXT};
}}
.block-container {{
  padding: 1.2rem 1.8rem 2rem 1.8rem;
  max-width: 1600px;
}}

/* Hide Streamlit chrome */
#MainMenu, footer, header {{ visibility: hidden; }}
.stDeployButton {{ display: none; }}
[data-testid="stDecoration"] {{ display: none; }}

/* Divider */
hr {{
  border: none;
  border-top: 1px solid {_BORDER};
  margin: 0.75rem 0;
}}

/* ── Panel card ── */
.panel {{
  background: {_PANEL};
  border: 1px solid {_BORDER};
  border-radius: 6px;
  padding: 14px 18px;
  margin-bottom: 8px;
}}
.panel-sm {{
  background: {_PANEL};
  border: 1px solid {_BORDER};
  border-radius: 6px;
  padding: 10px 14px;
  margin-bottom: 6px;
}}
.panel-header {{
  color: {_TXT2};
  font-size: 0.68rem;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  margin-bottom: 8px;
  border-bottom: 1px solid {_BORDER};
  padding-bottom: 6px;
}}

/* ── Signal badges ── */
.badge {{
  display: inline-block;
  padding: 3px 10px;
  border-radius: 3px;
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.1em;
  font-family: 'JetBrains Mono', monospace;
}}
.badge-increase {{ background: {_GREEN}22; color: {_GREEN}; border: 1px solid {_GREEN}55; }}
.badge-hold     {{ background: {_AMBER}22; color: {_AMBER}; border: 1px solid {_AMBER}55; }}
.badge-reduce   {{ background: {_RED}22;   color: {_RED};   border: 1px solid {_RED}55;   }}
.badge-unknown  {{ background: {_TXT3}22;  color: {_TXT2};  border: 1px solid {_BORDER};  }}

/* ── Score display ── */
.score-xl {{
  font-size: 2.4rem;
  font-weight: 700;
  font-family: 'JetBrains Mono', monospace;
  letter-spacing: -0.02em;
  line-height: 1;
}}
.score-lg {{
  font-size: 1.6rem;
  font-weight: 600;
  font-family: 'JetBrains Mono', monospace;
  line-height: 1;
}}
.score-unit {{
  font-size: 0.78rem;
  color: {_TXT3};
  font-weight: 400;
  margin-left: 3px;
}}

/* ── Delta chips ── */
.delta-up   {{ color: {_GREEN}; font-size: 0.8rem; font-family: 'JetBrains Mono', monospace; }}
.delta-dn   {{ color: {_RED};   font-size: 0.8rem; font-family: 'JetBrains Mono', monospace; }}
.delta-flat {{ color: {_TXT3};  font-size: 0.8rem; font-family: 'JetBrains Mono', monospace; }}

/* ── Factor table ── */
.ftable {{
  width: 100%;
  border-collapse: collapse;
  font-size: 0.8rem;
}}
.ftable th {{
  color: {_TXT2};
  font-size: 0.68rem;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  padding: 6px 10px;
  border-bottom: 1px solid {_BORDER};
  text-align: left;
}}
.ftable td {{
  padding: 7px 10px;
  color: {_TXT};
  border-bottom: 1px solid {_BORDER}66;
  vertical-align: middle;
}}
.ftable tr:last-child td {{ border-bottom: none; }}
.ftable tr:hover td {{ background: {_PANEL2}; }}
.ftable .num {{
  font-family: 'JetBrains Mono', monospace;
  text-align: right;
}}
.ftable .wt {{
  color: {_TXT2};
  font-size: 0.72rem;
}}
.bar-wrap {{
  display: inline-block;
  width: 48px;
  height: 4px;
  background: {_BORDER};
  border-radius: 2px;
  vertical-align: middle;
  margin-left: 6px;
}}
.bar-fill {{
  height: 4px;
  border-radius: 2px;
  background: {_BLUE};
}}

/* ── Summary panel ── */
.summary-text {{
  font-size: 0.84rem;
  line-height: 1.65;
  color: {_TXT};
  font-style: italic;
}}

/* ── Status strip ── */
.status-strip {{
  display: flex;
  gap: 18px;
  align-items: center;
  font-size: 0.74rem;
  color: {_TXT2};
  padding: 6px 0 10px 0;
}}
.status-dot {{
  width: 6px; height: 6px;
  border-radius: 50%;
  display: inline-block;
  margin-right: 5px;
  vertical-align: middle;
}}
.dot-live   {{ background: {_GREEN}; }}
.dot-cached {{ background: {_AMBER}; }}
.dot-skip   {{ background: {_TXT3}; }}

/* ── Thesis break list ── */
.tbreak-item {{
  display: flex;
  align-items: flex-start;
  gap: 8px;
  font-size: 0.78rem;
  color: {_TXT2};
  padding: 5px 0;
  border-bottom: 1px solid {_BORDER}44;
}}
.tbreak-item:last-child {{ border-bottom: none; }}
.tbreak-icon {{ color: {_AMBER}; flex-shrink: 0; font-size: 0.72rem; margin-top: 1px; }}

/* ── Horizon mini-card ── */
.hz-card {{
  background: {_PANEL};
  border: 1px solid {_BORDER};
  border-radius: 6px;
  padding: 12px 16px;
  margin-bottom: 8px;
  text-align: center;
}}
.hz-label {{
  font-size: 0.68rem;
  font-weight: 600;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: {_TXT2};
  margin-bottom: 8px;
}}

/* ── Dataframe overrides ── */
[data-testid="stDataFrame"] {{
  background: {_PANEL} !important;
}}

/* ── Tab styling ── */
[data-testid="stTabs"] > div:first-child {{
  border-bottom: 1px solid {_BORDER};
  gap: 0;
}}
button[data-baseweb="tab"] {{
  background: transparent !important;
  color: {_TXT2} !important;
  font-size: 0.78rem !important;
  font-weight: 500 !important;
  letter-spacing: 0.04em !important;
  padding: 8px 18px !important;
  border-bottom: 2px solid transparent !important;
}}
button[data-baseweb="tab"][aria-selected="true"] {{
  color: {_TXT} !important;
  border-bottom: 2px solid {_COPPER} !important;
}}
</style>
""", unsafe_allow_html=True)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _badge(sig: str) -> str:
    cls = {
        "INCREASE": "badge-increase",
        "HOLD":     "badge-hold",
        "REDUCE":   "badge-reduce",
    }.get(sig, "badge-unknown")
    return f'<span class="badge {cls}">{sig}</span>'


def _delta(v: float | None, precision: int = 1) -> str:
    if v is None:
        return '<span class="delta-flat">—</span>'
    if v > 0.3:
        return f'<span class="delta-up">▲ +{v:.{precision}f}</span>'
    if v < -0.3:
        return f'<span class="delta-dn">▼ {v:.{precision}f}</span>'
    return f'<span class="delta-flat">─ {abs(v):.{precision}f}</span>'


def _score(v: float | None, decimals: int = 0) -> str:
    return f"{v:.{decimals}f}" if v is not None else "—"


def _bar(score: float | None, color: str = _BLUE) -> str:
    if score is None:
        return ""
    pct = int(max(0, min(100, score)))
    return (f'<span class="bar-wrap"><span class="bar-fill" '
            f'style="width:{pct}%;background:{color}"></span></span>')


def _sig_color(sig: str) -> str:
    return {"INCREASE": _GREEN, "HOLD": _AMBER, "REDUCE": _RED}.get(sig, _TXT3)


def _chg_color(v: float | None, invert: bool = False) -> str:
    if v is None:
        return _TXT2
    positive_color = _RED if invert else _GREEN
    negative_color = _GREEN if invert else _RED
    if v > 0.05:
        return positive_color
    if v < -0.05:
        return negative_color
    return _TXT2


def _fmt_chg(v: float | None, invert: bool = False) -> str:
    if v is None:
        return f'<span style="color:{_TXT2}">—</span>'
    color = _chg_color(v, invert)
    arrow = "▲" if v > 0.05 else ("▼" if v < -0.05 else "─")
    return f'<span style="color:{color}">{arrow} {v:+.2f}%</span>'


# ── Session-state data loading ────────────────────────────────────────────────

def _load_from_db() -> dict:
    snap    = load_today() or load_latest()
    iv_hist = load_iv_history(252)
    iv_cur  = iv_hist[-1]["iv_pct"] if iv_hist else None
    iv_rank = compute_iv_rank(iv_cur) if iv_cur is not None else None
    return {
        "today":               snap,
        "previous":            load_previous(),
        "history":             load_history(90),
        "summary":             None,
        "iv_data":             {"current": iv_cur, "rank": iv_rank, "history": iv_hist},
        "world_markets":       None,
        "gamma_data":          None,
        "cot_data":            load_cot_latest(),
        "cot_history":         load_cot_history(52),
        "market_implications": None,
        "world_brief":         None,
        "fetch_date":          snap["date"] if snap else date.today().isoformat(),
        "is_fresh":            False,
        "from_cache":          True,
    }


_REFRESH_PASSWORD = os.environ.get("REFRESH_PASSWORD", "")


def _auto_refresh_needed() -> bool:
    """True if no today snapshot exists and it's a weekday at or after noon local time."""
    if load_today() is not None:
        return False
    now = datetime.now()
    return now.weekday() < 5 and now.hour >= 12


if "data" not in st.session_state:
    db_snap = load_today() or load_latest()
    if db_snap:
        st.session_state["data"] = _load_from_db()
        st.session_state["needs_refresh"] = _auto_refresh_needed() and not _REFRESH_PASSWORD
    else:
        st.session_state["data"] = None
        st.session_state["needs_refresh"] = True


# ── Header bar ────────────────────────────────────────────────────────────────
c_left, c_right = st.columns([7, 1])
with c_left:
    st.markdown(
        '<span style="font-size:1.35rem;font-weight:700;letter-spacing:-0.01em">Cu</span>'
        '<span style="font-size:1.35rem;font-weight:300;color:#6b7080"> · Copper Thesis</span>',
        unsafe_allow_html=True,
    )

with c_right:
    if _REFRESH_PASSWORD:
        pwd_input = st.text_input("", placeholder="password", type="password",
                                  label_visibility="collapsed", key="refresh_pwd")
        refresh_clicked = st.button("⟳ Refresh", use_container_width=True)
        refresh_allowed = refresh_clicked and (pwd_input == _REFRESH_PASSWORD)
        if refresh_clicked and not refresh_allowed:
            st.error("Wrong password.")
    else:
        refresh_clicked = st.button("⟳ Refresh", use_container_width=True)
        refresh_allowed = refresh_clicked

if refresh_allowed or st.session_state.get("needs_refresh"):
    with st.spinner("Fetching — ~30s…"):
        try:
            st.session_state["data"] = run(skip_weekend=False)
        except Exception as exc:
            st.error(f"Refresh failed: {exc} — showing cached data.")
            st.session_state["data"] = _load_from_db()
        finally:
            st.session_state["needs_refresh"] = False
    st.rerun()

data = st.session_state["data"]

if data is None:
    st.markdown(
        f'<div class="panel" style="color:{_TXT2}">No data yet — click <b>⟳ Refresh</b> to run the pipeline.</div>',
        unsafe_allow_html=True,
    )
    st.stop()

# ── Unpack ────────────────────────────────────────────────────────────────────
today         = data.get("today") or {}
previous      = data.get("previous")
history       = data.get("history", [])
summary       = data.get("summary")
skipped       = data.get("skipped", False)
fetch_dt      = data.get("fetch_date", "")
is_fresh      = data.get("is_fresh", False)
from_cache    = data.get("from_cache", False)
world_markets = data.get("world_markets") or {}
gamma_data    = data.get("gamma_data")
cot_data      = data.get("cot_data")
cot_hist      = data.get("cot_history") or []
mkt_impl      = data.get("market_implications")
world_brief   = data.get("world_brief")

if not today:
    st.markdown(
        f'<div class="panel" style="color:{_TXT2}">No snapshot data — click <b>⟳ Refresh</b>.</div>',
        unsafe_allow_html=True,
    )
    st.stop()

# ── Status strip ──────────────────────────────────────────────────────────────
dot_cls   = "dot-cached" if from_cache else ("dot-skip" if skipped else "dot-live")
dot_label = "cached"     if from_cache else ("skipped"  if skipped else "live")
snap_n    = snapshot_count()
snap_txt  = f"{snap_n} snapshots" if snap_n else ""
st.markdown(
    f'<div class="status-strip">'
    f'<span><span class="status-dot {dot_cls}"></span>{dot_label}</span>'
    f'<span>as of {fetch_dt}</span>'
    f'{"<span>" + snap_txt + "</span>" if snap_txt else ""}'
    f'{"<span style=\'color:#c4942a\'>" + data.get("reason","") + "</span>" if skipped else ""}'
    f'</div>',
    unsafe_allow_html=True,
)

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_copper, tab_implications, tab_world = st.tabs([
    "  Copper  ",
    "  Market Implications  ",
    "  World Markets  ",
])


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1 — COPPER THESIS
# ═══════════════════════════════════════════════════════════════════════════════
with tab_copper:

    # ── Top row: Overall signal + three horizon cards ─────────────────────────
    sig_1m  = today.get("signals", {}).get("1m", "—")
    comp_1m = today.get("composite", {}).get("1m")
    prev_1m = (previous or {}).get("composite", {}).get("1m")
    d_1m    = (comp_1m - prev_1m) if (comp_1m is not None and prev_1m is not None) else None

    col_main, col_1m, col_6m, col_1y = st.columns([2.4, 1, 1, 1])

    with col_main:
        sc = _sig_color(sig_1m)
        st.markdown(f"""
        <div class="panel" style="padding:18px 22px">
          <div class="panel-header" style="margin-bottom:10px">PRIMARY SIGNAL · 1-MONTH</div>
          <div style="display:flex;align-items:baseline;gap:14px;flex-wrap:wrap">
            <span class="score-xl" style="color:{sc}">{_score(comp_1m)}</span>
            <span class="score-unit">/100</span>
            {_badge(sig_1m)}
            <span style="margin-left:4px">{_delta(d_1m)}</span>
          </div>
          <div style="color:{_TXT2};font-size:0.72rem;margin-top:8px">
            INCREASE ≥ {SIGNAL_THRESHOLDS["increase"]:.0f} &nbsp;·&nbsp;
            REDUCE &lt; {SIGNAL_THRESHOLDS["reduce"]:.0f} &nbsp;·&nbsp;
            primary horizon is 1-month
          </div>
        </div>
        """, unsafe_allow_html=True)

    for col, (hk, hl) in zip([col_1m, col_6m, col_1y], [("1m","1M"),("6m","6M"),("1y","1Y")]):
        sc_v = today.get("composite", {}).get(hk)
        sig  = today.get("signals", {}).get(hk, "—")
        p_v  = (previous or {}).get("composite", {}).get(hk)
        dv   = (sc_v - p_v) if (sc_v is not None and p_v is not None) else None
        c    = _sig_color(sig)
        with col:
            st.markdown(f"""
            <div class="hz-card">
              <div class="hz-label">{hl}</div>
              <div class="score-lg" style="color:{c}">{_score(sc_v)}<span class="score-unit">/100</span></div>
              <div style="margin:5px 0">{_badge(sig)}</div>
              <div>{_delta(dv)}</div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("<hr>", unsafe_allow_html=True)

    # ── Factor breakdown ──────────────────────────────────────────────────────
    st.markdown('<div class="panel-header" style="font-size:0.68rem;font-weight:600;letter-spacing:0.08em;color:#6b7080;text-transform:uppercase;margin-bottom:8px">Factor Breakdown</div>', unsafe_allow_html=True)

    prev_fs = (previous or {}).get("factor_scores", {})
    rows_html = ""
    for fk, flabel in FACTOR_LABELS.items():
        s1m = (today.get("factor_scores") or {}).get("1m", {}).get(fk)
        s6m = (today.get("factor_scores") or {}).get("6m", {}).get(fk)
        s1y = (today.get("factor_scores") or {}).get("1y", {}).get(fk)
        p1m = prev_fs.get("1m", {}).get(fk)
        dv  = (s1m - p1m) if (s1m is not None and p1m is not None) else None

        bar_color = _BLUE
        if s1m is not None:
            if s1m >= SIGNAL_THRESHOLDS["increase"]:
                bar_color = _GREEN
            elif s1m < SIGNAL_THRESHOLDS["reduce"]:
                bar_color = _RED

        rows_html += f"""
        <tr>
          <td>{flabel}</td>
          <td class="wt">{int(FACTOR_WEIGHTS['1m'][fk]*100)}%</td>
          <td class="num">{_score(s1m)}{_bar(s1m, bar_color)}</td>
          <td class="num">{_score(s6m)}</td>
          <td class="num">{_score(s1y)}</td>
          <td class="num">{_delta(dv)}</td>
        </tr>"""

    st.markdown(f"""
    <div class="panel" style="padding:0;overflow:hidden">
    <table class="ftable">
      <thead>
        <tr>
          <th style="width:32%">Factor</th>
          <th style="width:6%">Wt</th>
          <th style="width:16%;text-align:right">1M</th>
          <th style="width:12%;text-align:right">6M</th>
          <th style="width:12%;text-align:right">1Y</th>
          <th style="width:12%;text-align:right">Δ 1M</th>
        </tr>
      </thead>
      <tbody>{rows_html}</tbody>
    </table>
    </div>
    """, unsafe_allow_html=True)
    st.markdown(
        f'<div style="font-size:0.68rem;color:{_TXT2};margin-top:4px;padding-left:2px">'
        f'Weights shown for 1M horizon · Supply Deficit rises to 26% (6M) and 36% (1Y) · '
        f'Inventories falls to 10% (6M) and 5% (1Y)</div>',
        unsafe_allow_html=True,
    )

    st.markdown("<hr>", unsafe_allow_html=True)

    # ── AI analyst brief ──────────────────────────────────────────────────────
    st.markdown('<div class="panel-header" style="font-size:0.68rem;font-weight:600;letter-spacing:0.08em;color:#6b7080;text-transform:uppercase;margin-bottom:8px">AI Analyst Brief</div>', unsafe_allow_html=True)

    if summary:
        st.markdown(f'<div class="panel"><p class="summary-text">{summary}</p></div>', unsafe_allow_html=True)
    elif not os.environ.get("GROQ_API_KEY"):
        st.markdown(f'<div class="panel-sm" style="color:{_TXT2}">Add <code>GROQ_API_KEY</code> to <code>.env</code> to enable AI summaries.</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="panel-sm" style="color:{_TXT2}">Summary generated on Refresh — click <b>⟳ Refresh</b> to trigger.</div>', unsafe_allow_html=True)

    st.markdown("<hr>", unsafe_allow_html=True)

    # ── Historical composite chart ─────────────────────────────────────────────
    st.markdown('<div class="panel-header" style="font-size:0.68rem;font-weight:600;letter-spacing:0.08em;color:#6b7080;text-transform:uppercase;margin-bottom:8px">Composite History · 90-Day</div>', unsafe_allow_html=True)

    if len(history) >= 2:
        dates = [r["date"] for r in history]
        fig = go.Figure()
        palette = [("1m", _BLUE, "1-Month"), ("6m", _TEAL, "6-Month"), ("1y", _GOLD, "1-Year")]
        for hk, color, label in palette:
            vals = [r["composite"].get(hk) for r in history]
            fig.add_trace(go.Scatter(
                x=dates, y=vals, mode="lines",
                name=label,
                line=dict(color=color, width=1.5),
                connectgaps=True,
            ))
        fig.add_hline(
            y=SIGNAL_THRESHOLDS["increase"], line_dash="dot",
            line_color=_GREEN, opacity=0.4,
            annotation_text="INCREASE", annotation_position="right",
            annotation_font=dict(size=9, color=_GREEN),
        )
        fig.add_hline(
            y=SIGNAL_THRESHOLDS["reduce"], line_dash="dot",
            line_color=_RED, opacity=0.4,
            annotation_text="REDUCE", annotation_position="right",
            annotation_font=dict(size=9, color=_RED),
        )
        fig.update_layout(
            plot_bgcolor=_PANEL, paper_bgcolor=_PANEL,
            font=dict(family="Inter", color=_TXT2, size=11),
            yaxis=dict(range=[0, 100], title=None, gridcolor=_BORDER, zeroline=False,
                       tickfont=dict(size=10, color=_TXT2)),
            xaxis=dict(gridcolor=_BORDER, zeroline=False, tickfont=dict(size=10, color=_TXT2)),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
                        font=dict(size=10), bgcolor="rgba(0,0,0,0)"),
            margin=dict(l=8, r=60, t=12, b=8),
            height=280,
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.markdown(f'<div class="panel-sm" style="color:{_TXT2}">Chart appears after 2+ daily snapshots.</div>', unsafe_allow_html=True)

    st.markdown("<hr>", unsafe_allow_html=True)

    # ── Bottom row: Thesis breaks + Market Signals ────────────────────────────
    col_breaks, col_signals = st.columns([1, 1.6])

    with col_breaks:
        breaks_html = "".join(
            f'<div class="tbreak-item"><span class="tbreak-icon">▶</span><span>{b}</span></div>'
            for b in THESIS_BREAKS
        )
        st.markdown(f"""
        <div class="panel" style="height:100%">
          <div class="panel-header">Thesis Break Conditions</div>
          {breaks_html}
        </div>
        """, unsafe_allow_html=True)

    with col_signals:
        iv_col, ratio_col = st.columns(2)

        # ── Options IV ────────────────────────────────────────────────────────
        with iv_col:
            iv_data    = data.get("iv_data") or {}
            iv_current = iv_data.get("current")
            iv_rank    = iv_data.get("rank")
            iv_hist    = iv_data.get("history") or []

            if iv_rank is not None:
                if iv_rank >= 75:
                    iv_label, iv_col_c = "ELEVATED", _RED
                elif iv_rank < 25:
                    iv_label, iv_col_c = "COMPRESSED", _GREEN
                else:
                    iv_label, iv_col_c = "NORMAL", _AMBER
                rank_str = f"{iv_rank:.0f}th pct"
            else:
                iv_label, iv_col_c = "BUILDING", _TXT2
                rank_str = "< 5 readings"

            iv_val_str = f"{iv_current:.1f}%" if iv_current is not None else "—"

            st.markdown(f"""
            <div class="panel">
              <div class="panel-header">Options IV · FCX Proxy</div>
              <div style="display:flex;align-items:baseline;gap:10px">
                <span class="score-lg" style="color:{_TXT}">{iv_val_str}</span>
                <span style="font-size:0.68rem;color:{_TXT2}">annualized</span>
              </div>
              <div style="margin-top:6px">
                <span style="color:{iv_col_c};font-size:0.78rem;font-weight:600">{iv_label}</span>
                <span style="color:{_TXT2};font-size:0.72rem;margin-left:8px">{rank_str}</span>
              </div>
            </div>
            """, unsafe_allow_html=True)

            if len(iv_hist) >= 2:
                iv_fig = go.Figure()
                iv_fig.add_trace(go.Scatter(
                    x=[r["date"] for r in iv_hist],
                    y=[r["iv_pct"] for r in iv_hist],
                    mode="lines",
                    line=dict(color=_PURPLE, width=1.5),
                    fill="tozeroy",
                    fillcolor="rgba(112,96,170,0.09)",
                ))
                iv_fig.update_layout(
                    plot_bgcolor=_PANEL, paper_bgcolor=_PANEL,
                    font=dict(color=_TXT2, size=10),
                    yaxis=dict(title=None, gridcolor=_BORDER, zeroline=False),
                    xaxis=dict(gridcolor=_BORDER, zeroline=False),
                    margin=dict(l=4, r=4, t=4, b=4),
                    height=150, showlegend=False,
                )
                st.plotly_chart(iv_fig, use_container_width=True)
            else:
                st.markdown(f'<div style="color:{_TXT2};font-size:0.72rem;padding:6px 0">Chart builds after more daily readings.</div>', unsafe_allow_html=True)

        # ── Cu/Ag Ratio ───────────────────────────────────────────────────────
        with ratio_col:
            @st.cache_data(ttl=3600)
            def _get_cu_ag():
                cu = _download_one("HG=F", period="2y")
                ag = _download_one("SI=F", period="2y")
                if cu is None or ag is None:
                    return None
                idx = cu.index.intersection(ag.index)
                if len(idx) < 5:
                    return None
                ratio = (cu.loc[idx] / ag.loc[idx]).dropna()
                return ratio

            ratio_s = _get_cu_ag()

            def _pct_vs(series, n_days: int) -> str:
                if series is None or len(series) <= n_days:
                    return "—"
                past = float(series.iloc[-n_days])
                if past == 0:
                    return "—"
                chg = (float(series.iloc[-1]) - past) / past * 100
                if chg > 0.05:
                    return f'<span style="color:{_GREEN}">▲ {abs(chg):.1f}%</span>'
                if chg < -0.05:
                    return f'<span style="color:{_RED}">▼ {abs(chg):.1f}%</span>'
                return f'<span style="color:{_TXT2}">─ {abs(chg):.1f}%</span>'

            if ratio_s is not None and len(ratio_s) >= 2:
                cur  = float(ratio_s.iloc[-1])
                d30  = _pct_vs(ratio_s, 21)
                d180 = _pct_vs(ratio_s, 126)
                d252 = _pct_vs(ratio_s, 252)

                st.markdown(f"""
                <div class="panel">
                  <div class="panel-header">Cu / Ag Ratio</div>
                  <div style="display:flex;align-items:baseline;gap:10px">
                    <span class="score-lg" style="color:{_TXT}">{cur:.4f}</span>
                    <span style="font-size:0.68rem;color:{_TXT2}">Cu·lb / Ag·oz</span>
                  </div>
                  <div style="margin-top:6px;font-size:0.75rem;display:flex;gap:14px;flex-wrap:wrap">
                    <span style="color:{_TXT2}">1M {d30}</span>
                    <span style="color:{_TXT2}">6M {d180}</span>
                    <span style="color:{_TXT2}">1Y {d252}</span>
                  </div>
                  <div style="color:{_TXT2};font-size:0.68rem;margin-top:4px">Rising = copper outperforming silver</div>
                </div>
                """, unsafe_allow_html=True)

                ratio_90 = ratio_s.iloc[-90:]
                r_fig = go.Figure()
                r_fig.add_trace(go.Scatter(
                    x=ratio_90.index.strftime("%Y-%m-%d").tolist(),
                    y=ratio_90.tolist(),
                    mode="lines",
                    line=dict(color=_COPPER, width=1.5),
                    fill="tozeroy",
                    fillcolor="rgba(184,115,51,0.09)",
                ))
                r_fig.update_layout(
                    plot_bgcolor=_PANEL, paper_bgcolor=_PANEL,
                    font=dict(color=_TXT2, size=10),
                    yaxis=dict(title=None, gridcolor=_BORDER, zeroline=False),
                    xaxis=dict(gridcolor=_BORDER, zeroline=False),
                    margin=dict(l=4, r=4, t=4, b=4),
                    height=150, showlegend=False,
                )
                st.plotly_chart(r_fig, use_container_width=True)
            else:
                st.markdown(f'<div class="panel" style="color:{_TXT2};font-size:0.8rem">Cu/Ag ratio unavailable — will load on next Refresh.</div>', unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2 — MARKET IMPLICATIONS
# ═══════════════════════════════════════════════════════════════════════════════
with tab_implications:

    # Copper signal context strip
    comp = today.get("composite", {})
    sigs = today.get("signals", {})
    sig_strips = "  ·  ".join(
        f'{hl}: {_score(comp.get(hk))} — {sigs.get(hk, "—")}'
        for hk, hl in [("1m", "1M"), ("6m", "6M"), ("1y", "1Y")]
    )
    st.markdown(
        f'<div style="font-size:0.72rem;color:{_TXT2};padding:6px 0 12px 0">'
        f'Copper signal context &nbsp;·&nbsp; {sig_strips}</div>',
        unsafe_allow_html=True,
    )

    st.markdown('<div class="panel-header" style="font-size:0.68rem;font-weight:600;letter-spacing:0.08em;color:#6b7080;text-transform:uppercase;margin-bottom:8px">Cross-Asset Market Implications · AI Analysis (DeepSeek-R1)</div>', unsafe_allow_html=True)

    if mkt_impl:
        st.markdown(f'<div class="panel"><p class="summary-text">{mkt_impl}</p></div>', unsafe_allow_html=True)
    elif not os.environ.get("GROQ_API_KEY"):
        st.markdown(f'<div class="panel-sm" style="color:{_TXT2}">Add <code>GROQ_API_KEY</code> to enable cross-asset analysis.</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="panel-sm" style="color:{_TXT2}">Analysis generated on Refresh — click <b>⟳ Refresh</b> to trigger.</div>', unsafe_allow_html=True)

    st.markdown(
        f'<div style="font-size:0.68rem;color:{_TXT3};margin-top:8px;font-style:italic">'
        f'Analysis uses DeepSeek-R1-Distill-Llama-70B (chain-of-thought reasoning) via Groq. '
        f'Not financial advice.</div>',
        unsafe_allow_html=True,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 3 — WORLD MARKETS
# ═══════════════════════════════════════════════════════════════════════════════
with tab_world:

    # ── Row 1: Global market grid ─────────────────────────────────────────────
    st.markdown('<div class="panel-header" style="font-size:0.68rem;font-weight:600;letter-spacing:0.08em;color:#6b7080;text-transform:uppercase;margin-bottom:8px">Global Markets</div>', unsafe_allow_html=True)

    if world_markets:
        mkt_rows = ""
        for name, m in world_markets.items():
            is_vix = name == "VIX"
            price  = m.get("price")
            price_str = f"{price:,.2f}" if price is not None else "—"

            mkt_rows += f"""
            <tr>
              <td style="font-weight:500">{name}</td>
              <td class="num">{price_str}</td>
              <td class="num">{_fmt_chg(m.get('chg_1d_pct'), invert=is_vix)}</td>
              <td class="num">{_fmt_chg(m.get('chg_1m_pct'), invert=is_vix)}</td>
              <td class="num">{_fmt_chg(m.get('chg_1y_pct'), invert=is_vix)}</td>
            </tr>"""

        st.markdown(f"""
        <div class="panel" style="padding:0;overflow:hidden">
        <table class="ftable">
          <thead>
            <tr>
              <th style="width:22%">Market</th>
              <th style="width:16%;text-align:right">Price</th>
              <th style="width:16%;text-align:right">1D %</th>
              <th style="width:16%;text-align:right">1M %</th>
              <th style="width:16%;text-align:right">1Y %</th>
            </tr>
          </thead>
          <tbody>{mkt_rows}</tbody>
        </table>
        </div>
        """, unsafe_allow_html=True)
        st.markdown(
            f'<div style="font-size:0.68rem;color:{_TXT2};margin-top:4px">VIX coloring inverted — rising VIX = elevated risk = shown red.</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(f'<div class="panel-sm" style="color:{_TXT2}">World market data loads on Refresh.</div>', unsafe_allow_html=True)

    st.markdown("<hr>", unsafe_allow_html=True)

    # ── Row 2: World Brief + Gamma ────────────────────────────────────────────
    col_brief, col_gamma = st.columns([1.4, 1])

    # ── World Market AI Brief ─────────────────────────────────────────────────
    with col_brief:
        st.markdown('<div class="panel-header" style="font-size:0.68rem;font-weight:600;letter-spacing:0.08em;color:#6b7080;text-transform:uppercase;margin-bottom:8px">World Market Analyst · Central Banks &amp; Macro</div>', unsafe_allow_html=True)

        if world_brief:
            st.markdown(f'<div class="panel"><p class="summary-text">{world_brief}</p></div>', unsafe_allow_html=True)
        elif not os.environ.get("GROQ_API_KEY"):
            st.markdown(f'<div class="panel-sm" style="color:{_TXT2}">Add <code>GROQ_API_KEY</code> to enable world market analysis.</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="panel-sm" style="color:{_TXT2}">World brief generated on Refresh.</div>', unsafe_allow_html=True)

    # ── SPY Dealer Gamma ──────────────────────────────────────────────────────
    with col_gamma:
        st.markdown('<div class="panel-header" style="font-size:0.68rem;font-weight:600;letter-spacing:0.08em;color:#6b7080;text-transform:uppercase;margin-bottom:8px">SPY Dealer Gamma (GEX)</div>', unsafe_allow_html=True)

        if gamma_data:
            regime      = gamma_data.get("regime", "—")
            net_gex     = gamma_data.get("net_gex")
            call_gex    = gamma_data.get("call_gex")
            put_gex     = gamma_data.get("put_gex")
            gflip       = gamma_data.get("gamma_flip")
            spot        = gamma_data.get("spot")
            top_strikes = gamma_data.get("top_strikes") or []
            strike_gex  = gamma_data.get("strike_gex") or []

            regime_color = _GREEN if regime == "LONG GAMMA" else _RED
            gflip_str    = f"${gflip:,.2f}" if gflip else "—"
            spot_str     = f"${spot:,.2f}" if spot else "—"

            walls = "  ·  ".join(
                f'${s["strike"]:,.0f}' for s in top_strikes[:5]
            ) if top_strikes else "—"

            st.markdown(f"""
            <div class="panel">
              <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">
                <span style="color:{regime_color};font-size:0.85rem;font-weight:700">{regime}</span>
                <span style="color:{_TXT2};font-size:0.72rem">SPY @ {spot_str}</span>
              </div>
              <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;font-size:0.78rem">
                <div>
                  <div style="color:{_TXT2};font-size:0.68rem">Net GEX</div>
                  <div style="font-family:'JetBrains Mono',monospace;color:{regime_color}">${net_gex:+,.1f}M</div>
                </div>
                <div>
                  <div style="color:{_TXT2};font-size:0.68rem">Gamma Flip</div>
                  <div style="font-family:'JetBrains Mono',monospace;color:{_TXT}">{gflip_str}</div>
                </div>
                <div>
                  <div style="color:{_TXT2};font-size:0.68rem">Call GEX</div>
                  <div style="font-family:'JetBrains Mono',monospace;color:{_GREEN}">${call_gex:+,.1f}M</div>
                </div>
                <div>
                  <div style="color:{_TXT2};font-size:0.68rem">Put GEX</div>
                  <div style="font-family:'JetBrains Mono',monospace;color:{_RED}">${put_gex:+,.1f}M</div>
                </div>
              </div>
              <div style="margin-top:8px;font-size:0.68rem;color:{_TXT2}">Top walls: {walls}</div>
            </div>
            """, unsafe_allow_html=True)

            if strike_gex:
                strikes = [s["strike"] for s in strike_gex]
                gex_vals = [s["gex"] for s in strike_gex]
                colors   = [_GREEN if v >= 0 else _RED for v in gex_vals]

                gex_fig = go.Figure()
                gex_fig.add_trace(go.Bar(
                    x=strikes,
                    y=gex_vals,
                    marker_color=colors,
                    marker_line_width=0,
                    name="GEX",
                ))
                if spot:
                    gex_fig.add_vline(x=spot, line_dash="solid", line_color=_AMBER,
                                      line_width=1.5, opacity=0.8,
                                      annotation_text="spot", annotation_position="top",
                                      annotation_font=dict(size=9, color=_AMBER))
                if gflip:
                    gex_fig.add_vline(x=gflip, line_dash="dot", line_color=_TXT2,
                                      line_width=1, opacity=0.6,
                                      annotation_text="flip", annotation_position="top right",
                                      annotation_font=dict(size=9, color=_TXT2))
                gex_fig.update_layout(
                    plot_bgcolor=_PANEL, paper_bgcolor=_PANEL,
                    font=dict(color=_TXT2, size=10),
                    yaxis=dict(title="GEX ($M)", gridcolor=_BORDER, zeroline=True,
                               zerolinecolor=_BORDER, zerolinewidth=1),
                    xaxis=dict(title="Strike", gridcolor=_BORDER, zeroline=False),
                    margin=dict(l=8, r=8, t=8, b=8),
                    height=200, showlegend=False,
                    bargap=0.1,
                )
                st.plotly_chart(gex_fig, use_container_width=True)

            st.markdown(
                f'<div style="font-size:0.68rem;color:{_TXT3}">Black-Scholes gamma from yfinance IV. Front 4 expirations. Approximate — not a substitute for institutional GEX data.</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f'<div class="panel-sm" style="color:{_TXT2}">Gamma data loads on Refresh. Requires SPY options chain from yfinance.</div>',
                unsafe_allow_html=True,
            )

    st.markdown("<hr>", unsafe_allow_html=True)

    # ── Row 3: COT Data ───────────────────────────────────────────────────────
    st.markdown('<div class="panel-header" style="font-size:0.68rem;font-weight:600;letter-spacing:0.08em;color:#6b7080;text-transform:uppercase;margin-bottom:8px">Copper COT · CFTC Commitment of Traders</div>', unsafe_allow_html=True)

    if cot_data:
        report_date = cot_data.get("date", "—")
        oi          = cot_data.get("open_interest", 0)
        spec_net    = cot_data.get("spec_net", 0)
        spec_chg    = cot_data.get("spec_net_chg", 0)
        comm_net    = cot_data.get("comm_net", 0)

        spec_color = _GREEN if spec_net > 0 else _RED
        chg_color  = _GREEN if spec_chg > 0 else (_RED if spec_chg < 0 else _TXT2)
        chg_arrow  = "▲" if spec_chg > 0 else ("▼" if spec_chg < 0 else "─")

        st.markdown(f"""
        <div class="panel">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
            <span style="font-size:0.78rem;color:{_TXT}">Report date: {report_date}</span>
            <span style="font-size:0.68rem;color:{_TXT2}">Updated weekly (Fridays)</span>
          </div>
          <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px">
            <div>
              <div style="color:{_TXT2};font-size:0.68rem;text-transform:uppercase;letter-spacing:0.06em">Open Interest</div>
              <div style="font-family:'JetBrains Mono',monospace;font-size:1.1rem;color:{_TXT};margin-top:4px">{oi:,}</div>
            </div>
            <div>
              <div style="color:{_TXT2};font-size:0.68rem;text-transform:uppercase;letter-spacing:0.06em">Net Spec Position</div>
              <div style="font-family:'JetBrains Mono',monospace;font-size:1.1rem;color:{spec_color};margin-top:4px">{spec_net:+,}</div>
            </div>
            <div>
              <div style="color:{_TXT2};font-size:0.68rem;text-transform:uppercase;letter-spacing:0.06em">Spec Δ WoW</div>
              <div style="font-family:'JetBrains Mono',monospace;font-size:1.1rem;color:{chg_color};margin-top:4px">{chg_arrow} {spec_chg:+,}</div>
            </div>
            <div>
              <div style="color:{_TXT2};font-size:0.68rem;text-transform:uppercase;letter-spacing:0.06em">Net Commercial</div>
              <div style="font-family:'JetBrains Mono',monospace;font-size:1.1rem;color:{_TXT};margin-top:4px">{comm_net:+,}</div>
            </div>
          </div>
        </div>
        """, unsafe_allow_html=True)

        if len(cot_hist) >= 2:
            cot_dates = [r.get("date", "") for r in cot_hist]
            cot_specs = [r.get("spec_net", 0) for r in cot_hist]
            cot_fig = go.Figure()
            cot_fig.add_trace(go.Scatter(
                x=cot_dates, y=cot_specs,
                mode="lines+markers",
                line=dict(color=_COPPER, width=1.5),
                marker=dict(size=3, color=_COPPER),
                fill="tozeroy",
                fillcolor="rgba(184,115,51,0.07)",
                name="Net Spec Position",
            ))
            cot_fig.add_hline(y=0, line_color=_BORDER, line_width=1)
            cot_fig.update_layout(
                plot_bgcolor=_PANEL, paper_bgcolor=_PANEL,
                font=dict(color=_TXT2, size=10),
                yaxis=dict(title="Contracts", gridcolor=_BORDER, zeroline=False,
                           tickfont=dict(size=10, color=_TXT2)),
                xaxis=dict(gridcolor=_BORDER, zeroline=False,
                           tickfont=dict(size=10, color=_TXT2)),
                margin=dict(l=8, r=8, t=8, b=8),
                height=220, showlegend=False,
            )
            st.plotly_chart(cot_fig, use_container_width=True)

        st.markdown(
            f'<div style="font-size:0.68rem;color:{_TXT2};margin-top:4px">'
            f'Speculators net long = bullish positioning · '
            f'Commercials net short = hedging production (normal) · '
            f'Extreme spec longs = crowded trade, watch for reversal</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(f'<div class="panel-sm" style="color:{_TXT2}">COT data loads on Refresh. Published weekly by CFTC every Friday.</div>', unsafe_allow_html=True)
