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

    def test_unknown_sources_are_marked_honestly(self):
        profiles = SourceProfiles.from_records([])

        profile = profiles.lookup("https://unknown.example/news")

        self.assertFalse(profile.known)
        self.assertEqual(profile.name, "Unknown source")
        self.assertEqual(profile.editorial_profile, "unknown")


if __name__ == "__main__":
    unittest.main()
