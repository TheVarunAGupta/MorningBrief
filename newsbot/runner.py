from __future__ import annotations

import datetime as dt
import os
from dataclasses import dataclass
from pathlib import Path

from newsbot.ai import DeterministicBriefGenerator, OpenAIBriefGenerator
from newsbot.cache import load_recent_fingerprints, save_recent_fingerprints
from newsbot.config import load_config_dir
from newsbot.emailer import RenderedEmail, render_email, send_email
from newsbot.evidence import EvidencePack, build_evidence_packs
from newsbot.profiles import SourceProfiles
from newsbot.sample_data import sample_articles
from newsbot.sources import collect_articles
from newsbot.story import cluster_articles, rank_clusters


@dataclass(frozen=True)
class RunOptions:
    dry_run: bool = False
    no_send: bool = False
    run_date: dt.date | None = None
    max_stories: int = 5
    config_dir: Path = Path("config")
    cache_dir: Path = Path(".cache/newsbot")


@dataclass(frozen=True)
class RunResult:
    email: RenderedEmail
    selected_story_count: int
    article_count: int
    sent: bool


def run_pipeline(options: RunOptions) -> RunResult:
    run_date = options.run_date or dt.date.today()
    sources_config, profiles_config, ranking_config = load_config_dir(options.config_dir)
    profiles = SourceProfiles.from_records(
        list(profiles_config.get("source_profiles", []))
    )
    articles = collect_articles(sources_config)
    if not articles and options.dry_run:
        articles = sample_articles(run_date)
    if not articles:
        raise RuntimeError("No source articles collected.")

    recent_fingerprints = load_recent_fingerprints(options.cache_dir)
    clusters = cluster_articles(articles)
    ranked = rank_clusters(
        clusters,
        weights=dict(ranking_config.get("ranking", {})),
        recent_fingerprints=recent_fingerprints,
        now=dt.datetime.combine(run_date, dt.time(7, 30), tzinfo=dt.UTC),
    )
    selected, packs = select_story_packs(ranked, profiles, options.max_stories)
    if not selected:
        raise RuntimeError("No email-worthy story clusters selected.")

    if options.dry_run:
        analysis = DeterministicBriefGenerator().generate(packs, run_date.isoformat())
    else:
        analysis = OpenAIBriefGenerator(
            daily_model=os.environ.get("OPENAI_MODEL_DAILY", "gpt-5.4-mini"),
            deep_model=os.environ.get("OPENAI_MODEL_DEEP", "gpt-5.4"),
            monthly_cap_gbp=float(os.environ.get("MONTHLY_COST_CAP_GBP", "5")),
            monthly_spend_gbp=float(os.environ.get("MONTHLY_SPEND_GBP", "0")),
        ).generate(packs, run_date.isoformat())

    rendered = render_email(analysis, run_date)
    sent = False
    if not options.dry_run and not options.no_send:
        send_email(rendered)
        sent = True
        save_recent_fingerprints(
            options.cache_dir,
            recent_fingerprints | {cluster.fingerprint for cluster in selected},
        )
    elif not options.dry_run:
        save_recent_fingerprints(
            options.cache_dir,
            recent_fingerprints | {cluster.fingerprint for cluster in selected},
        )

    return RunResult(
        email=rendered,
        selected_story_count=len(selected),
        article_count=len(articles),
        sent=sent,
    )


def select_story_packs(
    ranked_clusters: list,
    profiles: SourceProfiles,
    max_stories: int,
) -> tuple[list, list[EvidencePack]]:
    packs = build_evidence_packs(ranked_clusters, profiles)
    selected_clusters = []
    selected_packs = []
    for cluster, pack in zip(ranked_clusters, packs):
        if evidence_quality_score(pack) <= 0:
            continue
        selected_clusters.append(cluster)
        selected_packs.append(pack)
        if len(selected_packs) >= max_stories:
            break
    return selected_clusters, selected_packs


def evidence_quality_score(pack: EvidencePack) -> int:
    score = 0
    for source in pack.sources:
        if source.profile.known:
            score += 2
        if bool(source.description):
            score += 1
    if not pack.sources:
        return 0
    if pack.summary == "Feed metadata did not provide a substantive summary.":
        score -= 1
    return max(score, 0)
