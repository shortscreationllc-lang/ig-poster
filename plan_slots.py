#!/usr/bin/env python3
"""Slot planner for the daily IG poster.

Decides which posting slots to run *right now*, with two reliability features
the old file-based slot guard lacked:

  1. CATCH-UP. GitHub cron is best-effort and regularly drops/delays runs. If an
     earlier FEED slot was missed today, the next run that fires posts it. So a
     dropped midday cron is recovered automatically by the afternoon/evening run
     instead of being lost for the day.

  2. STATE-BASED ONCE-PER-DAY. "Did we post slot X today?" lives in
     state.json under state["daily"][YYYYMMDD], written only AFTER a successful
     post. No committed .slotguard files, no manual marking, no push races
     (the workflow serializes runs via `concurrency` and syncs state before
     planning).

Stories are LIVE-ONLY: they are posted only inside their time-of-day window and
never backfilled (a 9pm "good morning" story makes no sense, and stories expire
in 24h anyway). Feed posts ARE backfilled because their content is evergreen.

Usage:
  plan_slots.py --plan       emit one line per slot to run, "KIND|FEED|STORY":
                               FEED  = am | pm | -     (feed slot, - = none)
                               STORY = 1 | 0           (post the story?)
  plan_slots.py --mark KIND  record today's KIND slot as done in state.json

Env overrides:
  FORCE_SLOT  morning|midday|afternoon|evening  workflow_dispatch override —
              ignores time-of-day and done-state and runs that slot's natural
              feed+story.
  NOW_HOUR / NOW_DAY   override current NY hour / YYYYMMDD (testing only).
"""
import json
import os
import sys
from datetime import datetime
from pathlib import Path

try:
    from zoneinfo import ZoneInfo
    NY = ZoneInfo("America/New_York")
except Exception:  # pragma: no cover - fallback if tz database missing
    NY = None

ROOT = Path(__file__).resolve().parent
STATE = ROOT / "state.json"

# kind, NY start hour, feed slot (am/pm/None), has a time-of-day story.
# Stories run twice a day — morning + afternoon. Evening is feed-only (carousel).
SLOTS = [
    ("morning",    8, "am", True),
    ("midday",    12, "am", False),
    ("afternoon", 16, None, True),
    ("evening",   19, "pm", False),
]
# A slot's LIVE window is [start, start + WINDOW_SPAN] hours — slack so a cron
# that fires late (or slips into the next hour) still counts as "in window".
WINDOW_SPAN = 1


def _now():
    dt = datetime.now(NY) if NY else datetime.utcnow()
    day = os.getenv("NOW_DAY") or dt.strftime("%Y%m%d")
    hour_override = os.getenv("NOW_HOUR")
    hour = int(hour_override) if hour_override not in (None, "") else dt.hour
    return day, hour


def read_state():
    return json.loads(STATE.read_text()) if STATE.exists() else {}


def write_state(state):
    STATE.write_text(json.dumps(state, indent=2) + "\n")


def _done_today(state, day):
    return (state.get("daily") or {}).get(day, {})


def plan():
    day, hour = _now()
    done = _done_today(read_state(), day)
    forced = (os.getenv("FORCE_SLOT") or "").strip().lower()
    lines = []
    for kind, start, feed, story in SLOTS:
        if forced:
            if kind != forced:
                continue
            do_feed, do_story = feed, story
        else:
            if hour < start:            # not due yet
                continue
            if done.get(kind):          # already posted today
                continue
            in_window = start <= hour <= start + WINDOW_SPAN
            do_feed = feed              # feed posts catch up any time after due
            do_story = story and in_window   # stories are live-only, never backfilled
            if not do_feed and not do_story:
                continue                # e.g. a missed story-only slot — let it lapse
        lines.append(f"{kind}|{do_feed or '-'}|{1 if do_story else 0}")
    return lines


def mark(kind):
    day, _ = _now()
    state = read_state()
    daily = state.setdefault("daily", {})
    daily.setdefault(day, {})[kind] = True
    # keep only the last few days so state.json doesn't grow forever
    for old in sorted(daily.keys())[:-5]:
        del daily[old]
    write_state(state)
    print(f"marked {day} {kind} done")


def main():
    if "--plan" in sys.argv:
        print("\n".join(plan()))
        return 0
    if "--mark" in sys.argv:
        i = sys.argv.index("--mark")
        if i + 1 >= len(sys.argv):
            print("usage: plan_slots.py --mark KIND", file=sys.stderr)
            return 2
        mark(sys.argv[i + 1])
        return 0
    print("usage: plan_slots.py --plan | --mark KIND", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
