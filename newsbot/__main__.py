from __future__ import annotations

import argparse
import datetime as dt
import os
from pathlib import Path

from newsbot.runner import RunOptions, run_pipeline


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m newsbot")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Build and optionally send the daily brief.")
    run_parser.add_argument("--dry-run", action="store_true", help="Render without OpenAI or email send.")
    run_parser.add_argument("--no-send", action="store_true", help="Render and analyze without sending email.")
    run_parser.add_argument("--date", help="Run date in YYYY-MM-DD format.")
    run_parser.add_argument(
        "--max-stories",
        type=int,
        default=int(os.environ.get("MAX_STORIES", "5")),
        help="Maximum story count for the brief.",
    )
    run_parser.add_argument("--config-dir", default="config")
    run_parser.add_argument("--cache-dir", default=".cache/newsbot")

    args = parser.parse_args()
    if args.command == "run":
        run_date = dt.date.fromisoformat(args.date) if args.date else None
        result = run_pipeline(
            RunOptions(
                dry_run=args.dry_run,
                no_send=args.no_send,
                run_date=run_date,
                max_stories=args.max_stories,
                config_dir=Path(args.config_dir),
                cache_dir=Path(args.cache_dir),
            )
        )
        print(result.email.text)
        print(
            f"\nSelected stories: {result.selected_story_count}; "
            f"source articles: {result.article_count}; sent: {result.sent}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
