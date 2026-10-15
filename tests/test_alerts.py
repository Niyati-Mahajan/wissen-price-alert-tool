import json
import os
import tempfile
import unittest
from datetime import date

from alerts import InputError, find_alerts, load_prices, load_rules


class PriceAlertTests(unittest.TestCase):
    def test_level_below_fires_only_on_crossing(self):
        prices = {"INFY": [
            (date(2026, 9, 1), 1520.5),
            (date(2026, 9, 2), 1534.1),
            (date(2026, 9, 3), 1498.0),
            (date(2026, 9, 4), 1480.0),
        ]}
        rules = [{"id": "r1", "instrument": "INFY", "type": "level",
                  "direction": "below", "level": 1500}]
        self.assertEqual(find_alerts(prices, rules), [
            "2026-09-03\tr1\tINFY\tlevel below 1500"
        ])

    def test_level_above_fires_on_crossing(self):
        prices = {"ABC": [
            (date(2026, 1, 1), 9.0),
            (date(2026, 1, 2), 10.0),
            (date(2026, 1, 3), 11.0),
        ]}
        rules = [{"id": "a", "instrument": "ABC", "type": "level",
                  "direction": "above", "level": 10}]
        self.assertEqual(find_alerts(prices, rules), [
            "2026-01-03\ta\tABC\tlevel above 10"
        ])

    def test_no_level_alert_without_previous_day(self):
        prices = {"ABC": [(date(2026, 1, 1), 5.0)]}
        rules = [{"id": "a", "instrument": "ABC", "type": "level",
                  "direction": "below", "level": 10}]
        self.assertEqual(find_alerts(prices, rules), [])

    def test_ma_cross_above(self):
        # short=2, long=3. The short average moves from below to above the long average.
        prices = {"ABC": [
            (date(2026, 1, 1), 5.0),
            (date(2026, 1, 2), 4.0),
            (date(2026, 1, 3), 3.0),
            (date(2026, 1, 4), 8.0),
            (date(2026, 1, 5), 10.0),
        ]}
        rules = [{"id": "m1", "instrument": "ABC", "type": "ma_cross",
                  "short": 2, "long": 3, "direction": "above"}]
        self.assertEqual(find_alerts(prices, rules), [
            "2026-01-04\tm1\tABC\tma_cross 2/3 above"
        ])

    def test_ma_needs_full_windows(self):
        prices = {"ABC": [
            (date(2026, 1, 1), 1.0),
            (date(2026, 1, 2), 2.0),
            (date(2026, 1, 3), 3.0),
        ]}
        rules = [{"id": "m1", "instrument": "ABC", "type": "ma_cross",
                  "short": 2, "long": 4, "direction": "above"}]
        self.assertEqual(find_alerts(prices, rules), [])

    def test_dates_and_rule_ids_sort_output(self):
        prices = {"ABC": [
            (date(2026, 1, 1), 12.0),
            (date(2026, 1, 2), 8.0),
            (date(2026, 1, 3), 12.0),
        ]}
        rules = [
            {"id": "z", "instrument": "ABC", "type": "level", "direction": "below", "level": 10},
            {"id": "a", "instrument": "ABC", "type": "level", "direction": "above", "level": 10},
        ]
        result = find_alerts(prices, rules)
        self.assertEqual(result, [
            "2026-01-02\tz\tABC\tlevel below 10",
            "2026-01-03\ta\tABC\tlevel above 10",
        ])

    def test_unknown_instrument_is_ignored(self):
        prices = {"ABC": [(date(2026, 1, 1), 1.0), (date(2026, 1, 2), 2.0)]}
        rules = [{"id": "x", "instrument": "MISSING", "type": "level",
                  "direction": "above", "level": 1}]
        self.assertEqual(find_alerts(prices, rules), [])

    def test_csv_sorts_dates(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "prices.csv")
            with open(path, "w", encoding="utf-8") as f:
                f.write("date,instrument,close\n2026-01-02,ABC,12\n2026-01-01,ABC,8\n")
            prices = load_prices(path)
            self.assertEqual([x[0] for x in prices["ABC"]],
                             [date(2026, 1, 1), date(2026, 1, 2)])

    def test_duplicate_instrument_day_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "prices.csv")
            with open(path, "w", encoding="utf-8") as f:
                f.write("date,instrument,close\n2026-01-01,ABC,12\n2026-01-01,ABC,13\n")
            with self.assertRaises(InputError):
                load_prices(path)

    def test_invalid_direction_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "rules.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump([{"id": "x", "instrument": "ABC", "type": "level",
                            "direction": "sideways", "level": 10}], f)
            with self.assertRaises(InputError):
                load_rules(path)

    def test_short_must_be_less_than_long(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "rules.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump([{"id": "x", "instrument": "ABC", "type": "ma_cross",
                            "direction": "above", "short": 5, "long": 5}], f)
            with self.assertRaises(InputError):
                load_rules(path)

    def test_invalid_json_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "rules.json")
            with open(path, "w", encoding="utf-8") as f:
                f.write("{broken")
            with self.assertRaises(InputError):
                load_rules(path)


if __name__ == "__main__":
    unittest.main()
