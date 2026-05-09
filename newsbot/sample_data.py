from __future__ import annotations

import datetime as dt

from newsbot.models import Article


def sample_articles(run_date: dt.date) -> list[Article]:
    base = dt.datetime.combine(run_date, dt.time(6, 0), tzinfo=dt.UTC)
    return [
        Article(
            title="UN diplomats debate sanctions package after border escalation",
            url="https://news.un.org/en/story/sample-sanctions",
            source_name="UN News",
            description="Diplomats discuss sanctions, border security, and energy exposure after a regional escalation.",
            published_at=base,
            region="Global",
        ),
        Article(
            title="European ministers weigh sanctions after border escalation",
            url="https://www.bbc.co.uk/news/world-sample-sanctions",
            source_name="BBC News",
            description="European officials say any sanctions package would need to account for energy markets and alliance unity.",
            published_at=base - dt.timedelta(hours=1),
            region="Europe",
        ),
        Article(
            title="Regional governments warn sanctions after border escalation could disrupt food and fuel trade",
            url="https://www.aljazeera.com/news/sample-sanctions",
            source_name="Al Jazeera",
            description="Regional governments argue that sanctions could spill into fuel, shipping, and food costs.",
            published_at=base - dt.timedelta(hours=2),
            region="Middle East",
        ),
        Article(
            title="Pacific states press for climate security financing deal",
            url="https://www.reuters.com/world/sample-climate-security",
            source_name="Reuters",
            description="Island states frame climate finance as a security issue tied to migration, infrastructure, and regional influence.",
            published_at=base - dt.timedelta(hours=3),
            region="Oceania",
        ),
        Article(
            title="African Union mediators push ceasefire talks as mineral exports stall",
            url="https://www.africanews.com/sample-ceasefire-minerals",
            source_name="Africanews",
            description="Mediators link ceasefire talks to export corridors, mining revenue, and outside security backing.",
            published_at=base - dt.timedelta(hours=4),
            region="Africa",
        ),
    ]
