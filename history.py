"""
SQLite-backed snapshot store.
One row per calendar date (INSERT OR REPLACE — last write wins on same day).
Scores are stored as JSON columns; raw price data is intentionally excluded
to keep the DB small.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from datetime import date, datetime, timezone
from typing import Optional

from config import DB_PATH

_initialized = False

_CREATE_SNAPSHOTS_SQL = """
CREATE TABLE IF NOT EXISTS snapshots (
    date            TEXT PRIMARY KEY,
    timestamp_utc   TEXT NOT NULL,
    factor_scores   TEXT NOT NULL,
    composite       TEXT NOT NULL,
    signals         TEXT NOT NULL,
    factor_valid    TEXT NOT NULL
)
"""

_CREATE_IV_SQL = """
CREATE TABLE IF NOT EXISTS iv_snapshots (
    date    TEXT PRIMARY KEY,
    iv_pct  REAL NOT NULL
)
"""

_CREATE_COT_SQL = """
CREATE TABLE IF NOT EXISTS cot_snapshots (
    date        TEXT PRIMARY KEY,
    fetched_utc TEXT NOT NULL,
    data        TEXT NOT NULL
)
"""


def _conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(DB_PATH))
    c.row_factory = sqlite3.Row
    return c


def _init() -> None:
    global _initialized
    if _initialized:
        return
    with closing(_conn()) as c:
        c.execute(_CREATE_SNAPSHOTS_SQL)
        c.execute(_CREATE_IV_SQL)
        c.execute(_CREATE_COT_SQL)
        c.commit()
    _initialized = True


def save_snapshot(scores: dict, snap_date: Optional[date] = None) -> None:
    _init()
    d = (snap_date or date.today()).isoformat()
    with closing(_conn()) as c:
        c.execute(
            """
            INSERT OR REPLACE INTO snapshots
            (date, timestamp_utc, factor_scores, composite, signals, factor_valid)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                d,
                datetime.now(timezone.utc).isoformat(),
                json.dumps(scores.get("factor_scores", {})),
                json.dumps(scores.get("composite", {})),
                json.dumps(scores.get("signals", {})),
                json.dumps(scores.get("factor_valid", {})),
            ),
        )
        c.commit()


def _row_to_dict(row: sqlite3.Row) -> dict:
    return {
        "date":          row["date"],
        "timestamp_utc": row["timestamp_utc"],
        "factor_scores": json.loads(row["factor_scores"]),
        "composite":     json.loads(row["composite"]),
        "signals":       json.loads(row["signals"]),
        "factor_valid":  json.loads(row["factor_valid"]),
    }


def load_today() -> Optional[dict]:
    _init()
    with closing(_conn()) as c:
        row = c.execute(
            "SELECT * FROM snapshots WHERE date = ?", (date.today().isoformat(),)
        ).fetchone()
    return _row_to_dict(row) if row else None


def load_latest() -> Optional[dict]:
    """Most recent snapshot regardless of date — used on weekends."""
    _init()
    with closing(_conn()) as c:
        row = c.execute(
            "SELECT * FROM snapshots ORDER BY date DESC LIMIT 1"
        ).fetchone()
    return _row_to_dict(row) if row else None


def load_previous() -> Optional[dict]:
    """Most recent snapshot strictly before today — used for day-over-day delta."""
    _init()
    today = date.today().isoformat()
    with closing(_conn()) as c:
        row = c.execute(
            "SELECT * FROM snapshots WHERE date < ? ORDER BY date DESC LIMIT 1",
            (today,),
        ).fetchone()
    return _row_to_dict(row) if row else None


def load_history(days: int = 90) -> list[dict]:
    """Return up to `days` snapshots in chronological order (oldest first)."""
    _init()
    with closing(_conn()) as c:
        rows = c.execute(
            "SELECT * FROM snapshots ORDER BY date DESC LIMIT ?", (days,)
        ).fetchall()
    return [_row_to_dict(r) for r in reversed(rows)]


def snapshot_count() -> int:
    _init()
    with closing(_conn()) as c:
        return c.execute("SELECT COUNT(*) FROM snapshots").fetchone()[0]


# ── IV snapshot store ─────────────────────────────────────────────────────────

def save_iv(iv_pct: float, snap_date: Optional[date] = None) -> None:
    _init()
    d = (snap_date or date.today()).isoformat()
    with closing(_conn()) as c:
        c.execute(
            "INSERT OR REPLACE INTO iv_snapshots (date, iv_pct) VALUES (?, ?)",
            (d, iv_pct),
        )
        c.commit()


def load_iv_history(days: int = 252) -> list[dict]:
    """Return up to `days` IV readings in chronological order (oldest first)."""
    _init()
    with closing(_conn()) as c:
        rows = c.execute(
            "SELECT date, iv_pct FROM iv_snapshots ORDER BY date DESC LIMIT ?",
            (days,),
        ).fetchall()
    return [{"date": r[0], "iv_pct": r[1]} for r in reversed(rows)]


def compute_iv_rank(current_iv: float) -> Optional[float]:
    """
    Percentile of current_iv among all stored IV readings (0 = lowest ever, 100 = highest).
    Returns None if fewer than 5 readings are stored (insufficient history).
    """
    _init()
    with closing(_conn()) as c:
        rows = c.execute("SELECT iv_pct FROM iv_snapshots ORDER BY iv_pct").fetchall()
    values = [r[0] for r in rows]
    if len(values) < 5:
        return None
    below = sum(1 for v in values if v < current_iv)
    return round(below / len(values) * 100, 1)


# ── COT snapshot store ────────────────────────────────────────────────────────

def save_cot(cot: dict) -> None:
    _init()
    with closing(_conn()) as c:
        c.execute(
            "INSERT OR REPLACE INTO cot_snapshots (date, fetched_utc, data) VALUES (?, ?, ?)",
            (cot["date"], datetime.now(timezone.utc).isoformat(), json.dumps(cot)),
        )
        c.commit()


def load_cot_latest() -> Optional[dict]:
    """Most recent COT snapshot."""
    _init()
    with closing(_conn()) as c:
        row = c.execute(
            "SELECT data, fetched_utc FROM cot_snapshots ORDER BY date DESC LIMIT 1"
        ).fetchone()
    if not row:
        return None
    d = json.loads(row[0])
    d["fetched_utc"] = row[1]
    return d


def load_cot_history(weeks: int = 52) -> list[dict]:
    """Return up to `weeks` COT snapshots in chronological order (oldest first)."""
    _init()
    with closing(_conn()) as c:
        rows = c.execute(
            "SELECT data FROM cot_snapshots ORDER BY date DESC LIMIT ?", (weeks,)
        ).fetchall()
    return [json.loads(r[0]) for r in reversed(rows)]
