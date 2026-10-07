import random
import sys
import unittest
from datetime import date, datetime, time, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'data'))

from session_schedule import (ENDED, ON_SALE, PRE_SALE, SOLD_OUT,
                              bucket_for_index, sale_start_for, show_day_for_status)


class SessionScheduleTests(unittest.TestCase):
    def test_status_distribution_order_for_medium_dataset(self):
        total = 65
        statuses = [bucket_for_index(i, total) for i in range(total)]
        counts = {status: statuses.count(status) for status in (PRE_SALE, ON_SALE, SOLD_OUT, ENDED)}

        self.assertLess(counts[ON_SALE], counts[PRE_SALE])
        self.assertLess(counts[PRE_SALE], counts[SOLD_OUT] + counts[ENDED])

    def test_sale_start_is_30_days_before_show_and_ordered_with_show_time(self):
        today = date(2026, 10, 7)
        rng = random.Random(42)
        statuses = [bucket_for_index(i, 65) for i in range(65)]
        sessions = [
            datetime.combine(show_day_for_status(status, today, rng), time(19, 30))
            for status in statuses
        ]
        ordered = sorted((show_time, sale_start_for(show_time)) for show_time in sessions)

        for show_time, sale_start in ordered:
            self.assertEqual(sale_start, show_time - timedelta(days=30))
        self.assertEqual([sale for _, sale in ordered], sorted(sale for _, sale in ordered))


if __name__ == '__main__':
    unittest.main()
