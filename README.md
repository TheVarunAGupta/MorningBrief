# Daily Geopolitics Email Bot

Personal daily geopolitics brief generator. It gathers free news/source signals, ranks story clusters, uses source-first OpenAI analysis, and sends a Gmail email.

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
- `MONTHLY_COST_CAP_GBP`, default `5`

## Configuration

The files in `config/` are JSON-compatible YAML. That keeps runtime dependencies at zero while preserving the planned `.yml` config names.

- `config/sources.yml`: RSS feeds and GDELT queries
- `config/source_profiles.yml`: curated source labels and caveats
- `config/ranking.yml`: story ranking weights

## Daily Schedule

The GitHub Actions workflow has two UTC cron entries and a small Europe/London time gate. That keeps delivery aligned to about `07:30 Europe/London` across daylight saving changes, while manual workflow runs bypass the gate.
