"""Evaluate checked-in adversarial candidates without loading a cleanup model."""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from .validate import validate_llm_output

DEFAULT_CORPUS = Path(__file__).resolve().parents[3] / "tests" / "cleanup_adversarial.jsonl"


def load_cases(path=DEFAULT_CORPUS):
    cases, seen = [], set()
    with Path(path).open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            if (not isinstance(row, dict) or any(not isinstance(row.get(key), str) or not row[key]
                    for key in ("id", "category", "input", "candidate")) or row["id"] in seen
                    or row.get("mode", "balanced") not in ("balanced", "aggressive")):
                raise ValueError("Invalid or duplicate adversarial corpus row")
            seen.add(row["id"])
            cases.append(row)
    if not cases:
        raise ValueError("Adversarial corpus is empty")
    return cases


def evaluate(cases):
    totals, caught, reasons, missed = Counter(), Counter(), Counter(), []
    for row in cases:
        category = row["category"]
        totals[category] += 1
        result = validate_llm_output(row["input"], row["candidate"], mode=row.get("mode", "balanced"),
                                     glossary=row.get("glossary", ()))
        reasons[result.reason] += 1
        if result.ok:
            missed.append(row["id"])
        else:
            caught[category] += 1
    total = totals.total()
    return {"total": total, "caught": caught.total(), "catch_rate": 100 * caught.total() / max(1, total),
            "missed_ids": missed, "by_category": {key: {"total": value, "caught": caught[key]}
                                                   for key, value in sorted(totals.items())},
            "reasons": dict(sorted(reasons.items()))}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--min-catch-rate", type=float, default=100)
    parser.add_argument("--min-cases", type=int, default=100)
    args = parser.parse_args(argv)
    if not 0 <= args.min_catch_rate <= 100 or args.min_cases < 1:
        parser.error("threshold must be 0–100 and minimum case count must be positive")
    report = evaluate(load_cases(args.corpus))
    sys.stdout.write(json.dumps(report, ensure_ascii=True) + "\n")
    return 0 if report["total"] >= args.min_cases and report["catch_rate"] >= args.min_catch_rate else 1


if __name__ == "__main__":
    raise SystemExit(main())
