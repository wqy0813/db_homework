"""Regression checks for the full-scale generator's poster coverage."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))
sys.path.insert(0, str(ROOT / 'scripts' / 'data'))

import gen_full_scale  # noqa: E402
from posters import COLLECT_DIR, collected_poster  # noqa: E402


class FullScalePosterTests(unittest.TestCase):
    def test_every_generator_ip_has_a_collected_poster(self):
        missing = []
        for category_id, ips in gen_full_scale.IPS.items():
            for ip in ips:
                poster = collected_poster(ip, category_id, artist=ip)
                if not poster:
                    missing.append((category_id, ip))
        self.assertEqual(missing, [])

    def test_generator_uses_exactly_the_collected_ip_pool(self):
        pairs = [(category_id, ip) for category_id, ips in gen_full_scale.IPS.items() for ip in ips]
        self.assertEqual(len(pairs), 84)
        self.assertEqual(len(set(pairs)), 84)
        self.assertNotIn((1, '方大同'), pairs)
        self.assertIn((1, 'Taylor Swift'), pairs)

    def test_generated_city_station_names_resolve_to_real_posters(self):
        missing = []
        for category_id, ips in gen_full_scale.IPS.items():
            for ip in ips:
                poster = collected_poster(ip + '·上海站', category_id, artist=ip)
                if not poster:
                    missing.append((category_id, ip))
                elif not (COLLECT_DIR / poster[len('/posters/'):]).is_file():
                    missing.append((category_id, ip, poster))
        self.assertEqual(missing, [])


if __name__ == '__main__':
    unittest.main()
