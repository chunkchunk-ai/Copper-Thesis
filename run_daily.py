"""
Headless daily runner — designed for Windows Task Scheduler at 8 AM weekdays.

Usage:
    python copper/run_daily.py

Outputs a brief to stdout (capture with Task Scheduler action logging).
Exits with code 0 on success, 1 on unrecoverable error.
"""
from __future__ import annotations

import sys
import os
from datetime import date

sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv()

from pipeline import run, is_trading_day


def main() -> int:
    today = date.today()
    print(f"[{today.isoformat()}] Copper thesis pipeline starting…")

    if not is_trading_day(today):
        print(f"[{today.isoformat()}] Weekend — skipping fetch. No snapshot written.")
        return 0

    try:
        result = run(skip_weekend=False, with_summary=True)
    except Exception as exc:
        print(f"[ERROR] Pipeline failed: {exc}", file=sys.stderr)
        return 1

    today_snap = result.get("today", {})
    composite  = today_snap.get("composite", {})
    signals    = today_snap.get("signals", {})

    print(f"  1M composite: {composite.get('1m', 'N/A')}  →  {signals.get('1m', 'N/A')}")
    print(f"  6M composite: {composite.get('6m', 'N/A')}  →  {signals.get('6m', 'N/A')}")
    print(f"  1Y composite: {composite.get('1y', 'N/A')}  →  {signals.get('1y', 'N/A')}")

    if result.get("summary"):
        print("\n--- AI Brief ---")
        print(result["summary"])

    print(f"\n[{today.isoformat()}] Done. Snapshot saved to DB.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
