# Price Alert Tool

## Requirements and run

Requires Python 3.9+; no third-party packages are needed.

```bash
python alerts.py prices.csv rules.json
```

On Windows, use `py alerts.py prices.csv rules.json` if `python` is not recognized. Replace the sample input files with your own files using the formats below.

## Input formats

`prices.csv` has one row per instrument per trading day:

```csv
date,instrument,close
2026-09-01,INFY,1520.50
2026-09-02,INFY,1534.10
```

`rules.json` is an array of rules. A level rule needs `id`, `instrument`, `type: "level"`, `direction` (`"above"` or `"below"`), and numeric `level`. A moving-average rule uses `type: "ma_cross"`, positive integer `short` and `long` windows (`short < long`), and a direction.

## Behaviour and assumptions

- Dates are parsed as ISO dates and sorted independently for each instrument.
- A level alert fires only when the close moves from at-or-below the level to above it, or from at-or-above the level to below it. The first available day cannot trigger a level crossing because there is no previous close.
- Moving averages are simple moving averages of closing prices. A full window is required for each average; a crossover fires only when the short average changes from at-or-below the long average to above it, or vice versa for `below`.
- Missing instruments produce no alerts. Duplicate instrument/date rows, malformed input, invalid rules, and duplicate rule IDs produce a readable error.
- Output is sorted by date, then rule ID. No output is printed if no alert fires.

## Tests

Run all tests from this folder:

```bash
python -m unittest discover -s tests -v
```

The tests cover threshold crossings, avoiding repeated alerts, moving-average window warm-up and crossover behaviour, sorting, missing instruments, out-of-order dates, duplicate rows, and invalid rules/JSON.

## AI assistance and verification

I used ChatGPT to help draft the implementation and test ideas. During verification, the first version of one CSV test accidentally wrote the literal characters `\\n` instead of actual line breaks, so the CSV parser correctly rejected the test input. I fixed the test fixture and reran the suite; all 12 tests passed. I also checked that a moving-average alert compares the relationship on consecutive days, rather than firing repeatedly just because the short average remains above the long average.

Review the code and tests yourself before submission; be prepared to explain the crossover conditions and why dates are sorted before calculations.
