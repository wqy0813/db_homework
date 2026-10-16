"""Regression checks for database generators' collected poster URLs."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))
sys.path.insert(0, str(ROOT / 'scripts' / 'data'))

from poster_assets import POSTER_URLS, poster_assets_for  # noqa: E402
from posters import COLLECT_DIR  # noqa: E402


class PosterAssetTests(unittest.TestCase):
    def test_known_show_uses_its_collected_poster(self):
        poster, gallery = poster_assets_for('话剧《雷雨》', 2, count=3)

        self.assertEqual(poster, '/posters/A/series_003_poster.jpg')
        self.assertEqual(gallery[0], poster)
        self.assertEqual(len(gallery), 3)
        self.assertEqual(len(set(gallery)), 3)

    def test_unmatched_show_falls_back_to_existing_collected_files(self):
        poster, gallery = poster_assets_for('未收集的测试演出', 999, count=4, offset=7)

        self.assertIn(poster, POSTER_URLS)
        self.assertEqual(gallery[0], poster)
        self.assertEqual(len(gallery), 4)
        self.assertEqual(len(set(gallery)), 4)
        for url in gallery:
            relative = url[len('/posters/'):]
            group, filename = relative.split('/', 1)
            self.assertTrue((COLLECT_DIR / group / filename).is_file(), url)


if __name__ == '__main__':
    unittest.main()
