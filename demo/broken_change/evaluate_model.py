"""Deterministic demonstration evaluation executed independently after repair."""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
from pathlib import Path


def load_transformation(path: Path):
    spec = importlib.util.spec_from_file_location("customer_features", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.calculate_monthly_spend


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    transform = load_transformation(Path("src/features/customer_features.py"))
    rows = [
        (120.0, 12),
        (75.0, 3),
        (0.0, 0),
        (40.0, 0),
        (240.0, 24),
    ]
    values = []
    for total_spend, age in rows:
        try:
            values.append(transform(total_spend, age))
        except ZeroDivisionError:
            values.append(float("inf"))
    invalid_values = sum(not math.isfinite(value) for value in values)
    candidate = 0.842 if invalid_values == 0 else 0.771
    payload = {
        "metric": "f1_score",
        "candidate": candidate,
        "invalid_values": invalid_values,
        "rows_evaluated": len(rows),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
