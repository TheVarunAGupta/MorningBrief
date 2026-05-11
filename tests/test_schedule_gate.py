import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path
from zoneinfo import ZoneInfo

from newsbot.schedule import (
    SUMMER_CRON,
    WINTER_CRON,
    load_event_schedule,
    should_run_delivery,
)


class ScheduleGateTests(unittest.TestCase):
    def test_manual_runs_always_pass_gate(self):
        now = dt.datetime(2026, 5, 11, 11, 6, tzinfo=ZoneInfo("Europe/London"))

        self.assertTrue(should_run_delivery("workflow_dispatch", "", now))

    def test_summer_cron_passes_even_when_github_starts_late(self):
        now = dt.datetime(2026, 5, 11, 11, 6, tzinfo=ZoneInfo("Europe/London"))

        self.assertTrue(should_run_delivery("schedule", SUMMER_CRON, now))
        self.assertFalse(should_run_delivery("schedule", WINTER_CRON, now))

    def test_winter_cron_passes_in_gmt(self):
        now = dt.datetime(2026, 1, 11, 9, 6, tzinfo=ZoneInfo("Europe/London"))

        self.assertTrue(should_run_delivery("schedule", WINTER_CRON, now))
        self.assertFalse(should_run_delivery("schedule", SUMMER_CRON, now))

    def test_load_event_schedule_reads_github_event_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "event.json"
            path.write_text(json.dumps({"schedule": SUMMER_CRON}), encoding="utf-8")

            self.assertEqual(load_event_schedule(path), SUMMER_CRON)


if __name__ == "__main__":
    unittest.main()
