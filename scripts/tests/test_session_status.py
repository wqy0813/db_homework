import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'data'))
from rebalance_status import plan_statuses


class SessionStatusTests(unittest.TestCase):
    now = datetime(2026, 10, 15, 12)

    def session(self, sid, days, sale_days, total=10, sold=0):
        return {'session_id': sid, 'series_id': 1, 'show_id': sid,
                'show_time': self.now + timedelta(days=days),
                'sale_start': self.now + timedelta(days=sale_days),
                'tier_count': int(total > 0), 'total_seats': total,
                'sold_seats': sold, 'remain': total - sold, 'sale_status': 1}

    def test_multiple_cities_can_be_on_sale_independently(self):
        rows = [self.session(1, 5, -1), self.session(2, 7, -23)]
        statuses, groups = plan_statuses(rows, self.now)
        self.assertEqual(statuses, {1: 2, 2: 2})
        self.assertEqual(groups[('series', 1)], {1, 2})

    def test_status_priority_and_sessions_without_tiers(self):
        rows = [self.session(1, -1, -31), self.session(2, 5, -1),
                self.session(3, 60, 30), self.session(4, 60, 30, sold=10),
                self.session(5, 5, -1, sold=10),
                self.session(6, 5, -1, total=0), self.session(7, 60, 30, total=0)]
        self.assertEqual(plan_statuses(rows, self.now)[0],
                         {1: 4, 2: 2, 3: 1, 4: 3, 5: 3, 6: 2, 7: 1})


if __name__ == '__main__':
    unittest.main()
