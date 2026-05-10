import datetime as dt
import unittest

from newsbot.evidence import build_evidence_packs
from newsbot.models import Article
from newsbot.profiles import SourceProfiles
from newsbot.story import cluster_articles, fingerprint_article, rank_clusters


class StoryPipelineTests(unittest.TestCase):
    def make_article(self, title, source, url, region="Global", hours_old=2):
        published_at = dt.datetime(2026, 5, 8, 6, 0, tzinfo=dt.UTC) - dt.timedelta(
            hours=hours_old
        )
        return Article(
            title=title,
            url=url,
            source_name=source,
            description="Diplomats said sanctions, energy, and security guarantees are all in play.",
            published_at=published_at,
            region=region,
            author="Diplomatic Desk",
        )

    def test_fingerprint_is_stable_for_similar_titles(self):
        first = self.make_article(
            "UN debates sanctions package after border escalation",
            "Example",
            "https://example.com/a",
        )
        second = self.make_article(
            "UN debates a sanctions package after border escalation!",
            "Other",
            "https://other.test/b",
        )

        self.assertEqual(fingerprint_article(first), fingerprint_article(second))

    def test_cluster_articles_groups_related_titles(self):
        articles = [
            self.make_article(
                "UN debates sanctions package after border escalation",
                "Example",
                "https://example.com/a",
            ),
            self.make_article(
                "Diplomats debate sanctions after border escalation at UN",
                "Other",
                "https://other.test/b",
            ),
            self.make_article(
                "European ministers weigh sanctions after border escalation",
                "Another",
                "https://another.test/d",
            ),
            self.make_article(
                "Pacific island states announce climate finance deal",
                "Third",
                "https://third.test/c",
            ),
        ]

        clusters = cluster_articles(articles)

        sizes = sorted(len(cluster.articles) for cluster in clusters)
        self.assertEqual(sizes, [1, 3])

    def test_cluster_articles_merges_ceasefire_mediation_duplicates(self):
        articles = [
            self.make_article(
                "Trump says Iran reply to US war-ending proposal is totally unacceptable",
                "BBC",
                "https://bbc.com/a",
            ),
            self.make_article(
                "Iran replies to latest US ceasefire plan via Pakistani mediators as drones test truce",
                "Local TV",
                "https://local.example/b",
            ),
        ]

        clusters = cluster_articles(articles)

        self.assertEqual(len(clusters), 1)
        self.assertEqual(len(clusters[0].articles), 2)

    def test_rank_clusters_rewards_source_and_region_diversity(self):
        diverse = cluster_articles(
            [
                self.make_article(
                    "UN debates sanctions package after border escalation",
                    "Example",
                    "https://example.com/a",
                    region="Europe",
                ),
                self.make_article(
                    "Diplomats debate sanctions after border escalation at UN",
                    "Other",
                    "https://other.test/b",
                    region="Middle East",
                ),
                self.make_article(
                    "Security council weighs sanctions after escalation",
                    "Third",
                    "https://third.test/c",
                    region="Africa",
                ),
            ]
        )[0]
        narrow = cluster_articles(
            [
                self.make_article(
                    "One outlet previews local ministerial reshuffle",
                    "Example",
                    "https://example.com/local",
                    region="Europe",
                )
            ]
        )[0]

        ranked = rank_clusters(
            [narrow, diverse],
            weights={
                "article_count": 2.0,
                "domain_diversity": 2.0,
                "region_diversity": 1.5,
                "impact_keywords": 1.0,
                "recency": 1.0,
                "history_penalty": 8.0,
            },
            recent_fingerprints=set(),
            now=dt.datetime(2026, 5, 8, 7, 0, tzinfo=dt.UTC),
        )

        self.assertIs(ranked[0], diverse)
        self.assertGreater(ranked[0].score, ranked[1].score)

    def test_evidence_pack_keeps_source_material_before_analysis_inputs(self):
        profiles = SourceProfiles.from_records(
            [
                {
                    "domain": "example.com",
                    "name": "Example News",
                    "region": "Europe",
                    "source_type": "news",
                    "editorial_profile": "center-left",
                    "political_bias_label": "Center-left",
                    "political_bias_score": -1,
                    "reliability_notes": "Generally reliable; verify numbers.",
                    "warning": "none",
                    "useful_for": ["European political framing"],
                }
            ]
        )
        cluster = cluster_articles(
            [
                self.make_article(
                    "UN debates sanctions package after border escalation",
                    "Example",
                    "https://example.com/a",
                )
            ]
        )[0]

        pack = build_evidence_packs([cluster], profiles)[0]

        self.assertEqual(pack.title, "UN debates sanctions package after border escalation")
        self.assertEqual(pack.sources[0].profile.name, "Example News")
        self.assertIn("Start Here", pack.to_markdown())
        self.assertIn("Source File", pack.to_markdown())
        self.assertIn("By: Diplomatic Desk", pack.to_markdown())
        self.assertIn("Original link: https://example.com/a", pack.to_markdown())
        self.assertIn("Bias: Center-left (-1)", pack.to_markdown())
        self.assertIn("Fact And Claim Check", pack.to_markdown())


if __name__ == "__main__":
    unittest.main()
