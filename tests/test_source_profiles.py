import unittest

from newsbot.profiles import SourceProfiles


class SourceProfileTests(unittest.TestCase):
    def test_lookup_matches_exact_and_subdomains(self):
        profiles = SourceProfiles.from_records(
            [
                {
                    "domain": "example.com",
                    "name": "Example News",
                    "region": "Global",
                    "source_type": "news",
                    "editorial_profile": "centrist",
                    "political_bias_label": "Center",
                    "political_bias_score": 0,
                    "reliability_notes": "Usually factual; check opinion pieces.",
                    "warning": "none",
                    "useful_for": ["wire-style summary"],
                }
            ]
        )

        exact = profiles.lookup("https://example.com/world/story")
        subdomain = profiles.lookup("https://www.example.com/world/story")

        self.assertTrue(exact.known)
        self.assertTrue(subdomain.known)
        self.assertEqual(exact.name, "Example News")
        self.assertEqual(subdomain.domain, "example.com")
        self.assertEqual(exact.political_bias_label, "Center")
        self.assertEqual(exact.political_bias_score, 0)
        self.assertEqual(exact.bias_score_display(), "0")

    def test_unknown_sources_are_marked_honestly(self):
        profiles = SourceProfiles.from_records([])

        profile = profiles.lookup("https://unknown.example/news")

        self.assertFalse(profile.known)
        self.assertEqual(profile.name, "Unknown source")
        self.assertEqual(profile.editorial_profile, "unknown")
        self.assertEqual(profile.political_bias_label, "Unknown")
        self.assertEqual(profile.political_bias_score, 0)
        self.assertEqual(profile.bias_score_display(), "0")


if __name__ == "__main__":
    unittest.main()
