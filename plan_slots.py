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
  plan_slots.py --plan       emit one line per slot, "KIND|MEDIA|FEED|STORY":
                               MEDIA = reel | post | -
                               FEED  = am | pm | -   (only when MEDIA == post)
                               STORY = 1 | 0         (post the story?)
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

# kind, NY start hour, media, feed-slot, story.
#   media : "reel" (animated video) | "post" (image) | None
#   feed  : am | pm | "auto" | None  (only used when media == "post")
#   story : post the morning story this slot?
# Daily lineup = 3 Reels + 1 image post + 1 story:
#   morning  ~8:37a : Reel + story
#   midday   ~12:37p: Reel
#   afternoon~4:37p : image post (auto-alternates single card / carousel by day)
#   evening  ~7:37p : Reel
SLOTS = [
    ("morning",    8, "reel", None,   True),
    ("midday",    12, "reel", None,   False),
    ("afternoon", 16, "post", "auto", False),
    ("evening",   19, "reel", None,   False),
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
    """Emit one line per slot to run: "KIND|MEDIA|FEED|STORY".
      MEDIA = reel | post | -
      FEED  = am | pm | -   (only meaningful when MEDIA == post)
      STORY = 1 | 0
    Reels and posts catch up if missed earlier today; stories are window-only."""
    day, hour = _now()
    done = _done_today(read_state(), day)
    forced = (os.getenv("FORCE_SLOT") or "").strip().lower()
    lines = []
    for kind, start, media, feed, story in SLOTS:
        if forced:
            if kind != forced:
                continue
            do_media, do_feed, do_story = media, feed, story
        else:
            if hour < start:            # not due yet
                continue
            if done.get(kind):          # already posted today
                continue
            in_window = start <= hour <= start + WINDOW_SPAN
            do_media = media            # reels/posts catch up any time after due
            do_feed = feed
            do_story = story and in_window   # stories are live-only, never backfilled
            if not do_media and not do_story:
                continue                # a missed story-only slot — let it lapse
        # resolve the auto feed (alternate single card / carousel by day parity)
        if do_media == "post" and do_feed == "auto":
            do_feed = "pm" if int(day) % 2 == 0 else "am"
        feed_out = do_feed if (do_media == "post" and do_feed) else "-"
        lines.append(f"{kind}|{do_media or '-'}|{feed_out}|{1 if do_story else 0}")
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
