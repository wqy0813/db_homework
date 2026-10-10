"""Regression checks for name-based posters after database IDs change."""
import hashlib
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'backend'))
from app import app
from posters import COLLECT_DIR, collected_poster, resolve_poster


class CollectedPosterTests(unittest.TestCase):
    def test_seed_and_renumbered_names(self):
        cases = [
            ('周杰伦《嘉年华》世界巡回演唱会', 1, '/posters/D/series_069_poster.jpg'),
            ('周杰伦·鞍山站', 1, '/posters/D/series_069_poster.jpg'),
            ('张学友《60+》巡回演唱会', 1, '/posters/C/series_072_poster.jpg'),
            ('话剧《雷雨》', 2, '/posters/A/series_003_poster.jpg'),
            ('CBA 常规赛：广东宏远 vs 辽宁本钢', 3, '/posters/B/series_004_poster.jpg'),
            ('莫奈沉浸展·上海站', 5, '/posters/C/series_006_poster.jpg'),
            ('teamLab无界·台州站', 5, '/posters/A/series_054_poster.jpg'),
            ('久石让音乐会·武汉站', 6, '/posters/B/series_059_poster.jpeg'),
            ('猫·吉林站', 2, '/posters/C/series_105_poster.jpg'),
            ('威尼斯商人·武汉站', 2, '/posters/B/show_030_poster.jpg'),
        ]
        for name, category, url in cases:
            with self.subTest(name=name):
                self.assertEqual(collected_poster(name, category), url)

    def test_unrelated_show_is_not_assigned_old_id_30_poster(self):
        self.assertIsNone(collected_poster('奥特曼·临沂站', 4))
        self.assertIsNone(collected_poster('小猫儿童剧', 4))
        self.assertIsNone(collected_poster('猫', 4))
        self.assertIsNone(resolve_poster('奥特曼·临沂站', 4, '/img/full/p.jpg'))

    def test_custom_posters_are_preserved(self):
        for url in ['/static/img/uploads/custom.jpg', 'https://example.com/poster.jpg']:
            self.assertEqual(resolve_poster('话剧《雷雨》', 2, url), url)

    def test_removed_legacy_local_paths_are_not_returned(self):
        for url in ['/static/img/concert1.jpg', '/static/img/posters/1.jpg', '/img/full/p.jpg']:
            with self.subTest(url=url):
                self.assertIsNone(resolve_poster('未收集的演出', 1, url))

    def test_route_returns_original_bytes(self):
        client = app.test_client()
        for relative in ['A/series_003_poster.jpg', 'B/series_038_poster.png',
                         'B/series_059_poster.jpeg', 'D/series_069_poster.jpg']:
            response = client.get('/posters/' + relative)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.mimetype.startswith('image/'))
            self.assertEqual(hashlib.sha256(response.data).digest(),
                             hashlib.sha256((COLLECT_DIR / relative).read_bytes()).digest())
            response.close()

    def test_route_rejects_documents_and_unknown_groups(self):
        client = app.test_client()
        for url in ['/posters/A/sources.csv', '/posters/E/series_003_poster.jpg',
                    '/posters/AB/series_003_poster.jpg']:
            self.assertEqual(client.get(url).status_code, 404)


if __name__ == '__main__':
    unittest.main()
