from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path
from zoneinfo import ZoneInfo

SUMMER_CRON = "30 6 * * *"
WINTER_CRON = "30 7 * * *"
LONDON = ZoneInfo("Europe/London")


def should_run_delivery(
    event_name: str,
    event_schedule: str,
    now: dt.datetime,
) -> bool:
    if event_name == "workflow_dispatch":
        return True
    if event_name != "schedule":
        return False
    offset = now.astimezone(LONDON).utcoffset()
    if offset == dt.timedelta(hours=1):
        return event_schedule == SUMMER_CRON
    if offset == dt.timedelta(0):
        return event_schedule == WINTER_CRON
    return False


def load_event_schedule(path: Path | None) -> str:
    if path is None or not path.exists():
        return ""
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    return str(payload.get("schedule", ""))


def main() -> int:
    event_name = os.environ.get("GITHUB_EVENT_NAME", "")
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    event_schedule = load_event_schedule(Path(event_path)) if event_path else ""
    now = dt.datetime.now(LONDON)
    should_run = should_run_delivery(event_name, event_schedule, now)
    output_path = os.environ.get("GITHUB_OUTPUT")
    if output_path:
        with open(output_path, "a", encoding="utf-8") as output:
            output.write(f"should_run={'true' if should_run else 'false'}\n")
    print(
        f"Europe/London time is {now:%Y-%m-%d %H:%M}; "
        f"event={event_name}; schedule={event_schedule or 'none'}; "
        f"should_run={should_run}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
