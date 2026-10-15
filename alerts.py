#!/usr/bin/env python3
"""Command-line price alert tool. Uses only the Python standard library."""

import argparse
import csv
import json
import math
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path


class InputError(ValueError):
    """Raised when an input file is invalid."""


def load_prices(path):
    """Return {instrument: [(date, close), ...]} sorted by date."""
    prices = defaultdict(list)
    seen = set()

    try:
        with open(path, "r", newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            required = {"date", "instrument", "close"}
            if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
                raise InputError("Prices CSV must contain date,instrument,close columns.")

            for line_number, row in enumerate(reader, start=2):
                try:
                    day_text = (row.get("date") or "").strip()
                    instrument = (row.get("instrument") or "").strip()
                    close_text = (row.get("close") or "").strip()
                    if not day_text or not instrument or not close_text:
                        raise InputError(f"Line {line_number}: date, instrument, and close are required.")
                    day = date.fromisoformat(day_text)
                    close = float(close_text)
                    if not math.isfinite(close):
                        raise InputError(f"Line {line_number}: close must be a finite number.")
                except (ValueError, TypeError) as exc:
                    if isinstance(exc, InputError):
                        raise
                    raise InputError(f"Line {line_number}: invalid date or close value.") from exc

                key = (instrument, day)
                if key in seen:
                    raise InputError(
                        f"Line {line_number}: duplicate price for {instrument} on {day.isoformat()}."
                    )
                seen.add(key)
                prices[instrument].append((day, close))
    except OSError as exc:
        raise InputError(f"Cannot read prices file: {exc}") from exc

    for instrument in prices:
        prices[instrument].sort(key=lambda item: item[0])
    return dict(prices)


def load_rules(path):
    """Load and validate alert rules from a JSON array."""
    try:
        with open(path, "r", encoding="utf-8") as handle:
            rules = json.load(handle)
    except OSError as exc:
        raise InputError(f"Cannot read rules file: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise InputError(f"Rules file is not valid JSON: {exc}") from exc

    if not isinstance(rules, list):
        raise InputError("Rules JSON must be an array of rule objects.")

    ids = set()
    for index, rule in enumerate(rules):
        label = f"Rule at index {index}"
        if not isinstance(rule, dict):
            raise InputError(f"{label} must be an object.")
        rule_id = rule.get("id")
        instrument = rule.get("instrument")
        kind = rule.get("type")
        direction = rule.get("direction")
        if not isinstance(rule_id, str) or not rule_id.strip():
            raise InputError(f"{label}: id must be a non-empty string.")
        if rule_id in ids:
            raise InputError(f"Duplicate rule id: {rule_id}.")
        ids.add(rule_id)
        if not isinstance(instrument, str) or not instrument.strip():
            raise InputError(f"Rule {rule_id}: instrument must be a non-empty string.")
        if direction not in {"above", "below"}:
            raise InputError(f"Rule {rule_id}: direction must be 'above' or 'below'.")

        if kind == "level":
            level = rule.get("level")
            if isinstance(level, bool) or not isinstance(level, (int, float)) or not math.isfinite(level):
                raise InputError(f"Rule {rule_id}: level must be a finite number.")
        elif kind == "ma_cross":
            short = rule.get("short")
            long = rule.get("long")
            if (isinstance(short, bool) or not isinstance(short, int) or short < 1 or
                    isinstance(long, bool) or not isinstance(long, int) or long < 1):
                raise InputError(f"Rule {rule_id}: short and long must be positive integers.")
            if short >= long:
                raise InputError(f"Rule {rule_id}: short must be less than long.")
        else:
            raise InputError(f"Rule {rule_id}: type must be 'level' or 'ma_cross'.")

    return rules


def find_alerts(prices, rules):
    """Evaluate rules and return (day, rule_id, output_line) tuples."""
    alerts = []

    for rule in rules:
        instrument = rule["instrument"]
        series = prices.get(instrument, [])
        if len(series) < 2:
            continue

        rule_id = rule["id"]
        direction = rule["direction"]

        if rule["type"] == "level":
            level = float(rule["level"])
            for index in range(1, len(series)):
                previous_close = series[index - 1][1]
                current_day, current_close = series[index]
                crossed = (
                    previous_close <= level and current_close > level
                    if direction == "above"
                    else previous_close >= level and current_close < level
                )
                if crossed:
                    description = f"level {direction} {rule['level']}"
                    alerts.append((
                        current_day, rule_id,
                        f"{current_day.isoformat()}\t{rule_id}\t{instrument}\t{description}"
                    ))
        else:
            short_window = rule["short"]
            long_window = rule["long"]
            closes = [close for _, close in series]
            short_ma = [None] * len(closes)
            long_ma = [None] * len(closes)

            short_sum = 0.0
            long_sum = 0.0
            for index, close in enumerate(closes):
                short_sum += close
                long_sum += close
                if index >= short_window:
                    short_sum -= closes[index - short_window]
                if index >= long_window:
                    long_sum -= closes[index - long_window]
                if index >= short_window - 1:
                    short_ma[index] = short_sum / short_window
                if index >= long_window - 1:
                    long_ma[index] = long_sum / long_window

            for index in range(1, len(series)):
                if (short_ma[index] is None or long_ma[index] is None or
                        short_ma[index - 1] is None or long_ma[index - 1] is None):
                    continue
                previous_short, previous_long = short_ma[index - 1], long_ma[index - 1]
                current_short, current_long = short_ma[index], long_ma[index]
                crossed = (
                    previous_short <= previous_long and current_short > current_long
                    if direction == "above"
                    else previous_short >= previous_long and current_short < current_long
                )
                if crossed:
                    current_day = series[index][0]
                    description = f"ma_cross {short_window}/{long_window} {direction}"
                    alerts.append((
                        current_day, rule_id,
                        f"{current_day.isoformat()}\t{rule_id}\t{instrument}\t{description}"
                    ))

    alerts.sort(key=lambda item: (item[0], item[1]))
    return [item[2] for item in alerts]


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Evaluate price alert rules from a CSV price file and JSON rules file."
    )
    parser.add_argument("prices_csv", help="CSV with date,instrument,close columns")
    parser.add_argument("rules_json", help="JSON array of alert rules")
    args = parser.parse_args(argv)

    try:
        prices = load_prices(args.prices_csv)
        rules = load_rules(args.rules_json)
        for line in find_alerts(prices, rules):
            print(line)
    except InputError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
