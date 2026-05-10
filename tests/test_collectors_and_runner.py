import datetime as dt
import tempfile
import unittest
from pathlib import Path

from newsbot.config import load_json_config
from newsbot.runner import RunOptions, run_pipeline
from newsbot.sources import build_gdelt_url, parse_gdelt_articles, parse_rss_feed


class CollectorsAndRunnerTests(unittest.TestCase):
    def test_load_json_compatible_yml(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "source_profiles.yml"
            path.write_text('{"source_profiles": [{"domain": "example.com"}]}', encoding="utf-8")

            loaded = load_json_config(path)

        self.assertEqual(loaded["source_profiles"][0]["domain"], "example.com")

    def test_parse_rss_feed_extracts_articles(self):
        xml = """<?xml version="1.0"?>
        <rss><channel>
          <item>
            <title>UN debates sanctions package</title>
            <link>https://example.com/story</link>
            <author>Diplomatic Correspondent</author>
            <description>Diplomats cite energy markets.</description>
            <pubDate>Fri, 08 May 2026 06:00:00 GMT</pubDate>
          </item>
        </channel></rss>
        """

        articles = parse_rss_feed(
            xml.encode("utf-8"),
            {"name": "Example Feed", "region": "Global"},
        )

        self.assertEqual(len(articles), 1)
        self.assertEqual(articles[0].title, "UN debates sanctions package")
        self.assertEqual(articles[0].author, "Diplomatic Correspondent")
        self.assertEqual(articles[0].published_at, dt.datetime(2026, 5, 8, 6, 0, tzinfo=dt.UTC))

    def test_gdelt_url_encodes_query(self):
        url = build_gdelt_url({"query": "sanctions diplomacy", "timespan": "24h", "max_records": 10})

        self.assertIn("query=sanctions+diplomacy", url)
        self.assertIn("maxrecords=10", url)

    def test_parse_gdelt_articles_extracts_domain_source(self):
        payload = {
            "articles": [
                {
                    "title": "Diplomats debate new sanctions package",
                    "url": "https://example.com/world",
                    "sourceCountry": "US",
                    "seendate": "20260508T060000Z",
                    "domain": "example.com",
                }
            ]
        }

        articles = parse_gdelt_articles(payload, source_name="GDELT", region="Global")

        self.assertEqual(articles[0].source_name, "example.com")
        self.assertEqual(articles[0].author, "Not listed")
        self.assertEqual(articles[0].published_at, dt.datetime(2026, 5, 8, 6, 0, tzinfo=dt.UTC))

    def test_dry_run_pipeline_uses_sample_articles_when_collection_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_dir = root / "config"
            config_dir.mkdir()
            (config_dir / "sources.yml").write_text(
                '{"rss_feeds": [], "gdelt_queries": []}',
                encoding="utf-8",
            )
            (config_dir / "source_profiles.yml").write_text(
                '{"source_profiles": []}',
                encoding="utf-8",
            )
            (config_dir / "ranking.yml").write_text(
                '{"ranking": {"article_count": 2, "domain_diversity": 2, "region_diversity": 1, "impact_keywords": 1, "recency": 1, "history_penalty": 8}}',
                encoding="utf-8",
            )

            result = run_pipeline(
                RunOptions(
                    dry_run=True,
                    no_send=True,
                    run_date=dt.date(2026, 5, 8),
                    max_stories=4,
                    config_dir=config_dir,
                    cache_dir=root / "cache",
                )
            )

        self.assertGreaterEqual(result.selected_story_count, 1)
        self.assertIn("Start Here", result.email.text)
        self.assertIn("Source File", result.email.text)
        self.assertFalse(result.sent)


if __name__ == "__main__":
    unittest.main()
