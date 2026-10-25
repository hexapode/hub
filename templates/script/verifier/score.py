"""Automated benchmark and correctness verifier for script template."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import random
import sys
import time
from pathlib import Path


def load_submission_module(submission_dir: Path):
    sol_path = submission_dir / "solution.py"
    if not sol_path.is_file():
        raise FileNotFoundError(f"Missing solution.py in {submission_dir}")
    spec = importlib.util.spec_from_file_location("submission_solution", str(sol_path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load module from {sol_path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--submission", required=True, help="Path to submission directory")
    parser.add_argument(
        "--n",
        type=int,
        default=int(os.environ.get("SAR_SORT_N", "50000")),
        help="Number of integers to sort",
    )
    parser.add_argument("--seed", type=int, default=20261025, help="Fixed RNG seed")
    args = parser.parse_args()

    sub_dir = Path(args.submission).resolve()
    try:
        mod = load_submission_module(sub_dir)
    except Exception as exc:
        print(json.dumps({"valid": False, "reason": f"Import error: {exc}"}))
        return 0

    if not hasattr(mod, "sort_integers"):
        print(json.dumps({"valid": False, "reason": "solution.py must define sort_integers(data)"}))
        return 0

    rng = random.Random(args.seed)
    dataset = [rng.getrandbits(32) for _ in range(args.n)]
    expected = sorted(dataset)
    work_copy = list(dataset)

    t0 = time.perf_counter()
    try:
        result = mod.sort_integers(work_copy)
    except Exception as exc:
        print(json.dumps({"valid": False, "reason": f"Runtime exception: {exc}"}))
        return 0
    elapsed = time.perf_counter() - t0

    if not isinstance(result, list) or len(result) != len(expected) or result != expected:
        print(json.dumps({"valid": False, "reason": "Output does not match expected sorted array"}))
        return 0

    print(json.dumps({"valid": True, "value": round(elapsed, 6)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
