# Daily Geopolitics Email Bot

Personal daily geopolitics brief generator. It gathers free news/source signals, ranks story clusters, uses source-first OpenAI analysis, and sends a Gmail email.

The evidence sections are generated deterministically from collected source metadata. OpenAI is only asked to write the analysis sections, with a `4500` output-token ceiling so the brief has room to finish cleanly.

## Quick Start

Run a no-cost local dry run:

```bash
python3 -m unittest discover -s tests
python3 -m newsbot run --dry-run --no-send --date 2026-05-08 --max-stories 4
```

Dry runs do not call OpenAI and do not send email. If live source collection returns no articles, dry runs use sample articles so the email format can still be inspected.

## GitHub Secrets

Set these repository secrets before enabling the scheduled workflow:

- `OPENAI_API_KEY`
- `GMAIL_USER`
- `GMAIL_APP_PASSWORD`
- `EMAIL_TO`

Optional repository variables:

- `OPENAI_MODEL_DAILY`, default `gpt-5.4-mini`
- `OPENAI_MODEL_DEEP`, default `gpt-5.4`
- `OPENAI_REQUEST_TIMEOUT_SECONDS`, default `240`
- `OPENAI_MAX_RETRIES`, default `2`
- `MONTHLY_COST_CAP_GBP`, default `5`
- `MAX_STORIES`, default `5`

## Configuration

The files in `config/` are JSON-compatible YAML. That keeps runtime dependencies at zero while preserving the planned `.yml` config names.

- `config/sources.yml`: RSS feeds and GDELT queries
- `config/source_profiles.yml`: curated source labels and caveats
- `config/ranking.yml`: story ranking weights

The default RSS set uses 10 reputable global feeds: BBC World, NPR World, PBS NewsHour World, CBC World, France 24 English, Le Monde English, The Hindu International, Channel NewsAsia, Al Jazeera English, and The Guardian World. GDELT remains enabled as a broad discovery layer, especially for wire-service and regional pickup that does not expose a stable public RSS feed.

Source profiles include preset context labels such as `political_bias_label` and `political_bias_score`. The score is a simple editorial-context scale, not a truth score: negative values indicate left/liberal lean, positive values indicate right/conservative lean, and `0` is used for center, institutional, official, wire, mixed, or non-left/right sources.

## Daily Schedule

The GitHub Actions workflow has two UTC cron entries and a small Europe/London time gate. That keeps delivery aligned to about `07:30 Europe/London` across daylight saving changes, while manual workflow runs bypass the gate.
