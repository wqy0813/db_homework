import sys
import unittest
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'backend'))
from api.admin import _parse_positive_price, _parse_positive_seats
from api.orders import _parse_ticket_count


class AdminValidationTests(unittest.TestCase):
    def test_prices_cannot_round_to_zero(self):
        for value in ('0.001', '0.004', 0, -1, 'NaN', 'Infinity', True):
            with self.subTest(value=value):
                self.assertIsNone(_parse_positive_price(value))
        self.assertEqual(_parse_positive_price('0.01'), Decimal('0.01'))
        self.assertEqual(_parse_positive_price('680.00'), Decimal('680.00'))

    def test_ticket_inventory_must_be_a_positive_integer(self):
        for value in (True, False, 0, -1, 1.5, '1.5', None):
            with self.subTest(value=value):
                self.assertIsNone(_parse_positive_seats(value))
        self.assertEqual(_parse_positive_seats(1600), 1600)

    def test_purchase_count_rejects_invalid_types_without_raising(self):
        for value in (True, False, 0, 7, -1, 1.5, '\u00b2', 'abc', [], {}, None):
            with self.subTest(value=value):
                self.assertIsNone(_parse_ticket_count(value))
        self.assertEqual(_parse_ticket_count('6'), 6)


if __name__ == '__main__':
    unittest.main()
