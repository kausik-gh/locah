"""Run the worker's outbox fan-out, subscribers and automation lane once, for
one business, against the LOCAL acceptance database only.

    DATABASE_URL=postgresql+asyncpg://postgres@localhost:54329/locah_accept \
      .venv/bin/python tools/acceptance/stack/worker_once.py <business_id> [--at 2031-01-10T12:00:00+05:30]
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime

url = os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://postgres@localhost:54329/locah_accept")
if "@localhost:" not in url and "@127.0.0.1:" not in url:
    sys.exit("local databases only")

from platform_testing.phase_b import drain_events, run_automation  # noqa: E402

parser = argparse.ArgumentParser()
parser.add_argument("business_id")
parser.add_argument("--at", help="run automation as if it were this moment (ISO 8601)")
args = parser.parse_args()
events = drain_events(args.business_id)
steps = run_automation(args.business_id, now=datetime.fromisoformat(args.at) if args.at else None)
print(f"deliveries={events} steps={steps}")
