"""Manual verifier backend (§5.3)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sar.verifiers import VerifyResult


def verify(
    challenge_dir: Path,
    submission_dir: Path,
    spec: dict[str, Any],
    claimed: float | None,
) -> VerifyResult:
    vcfg = spec.get("verifier", {})
    reviewers = vcfg.get("reviewers") or spec.get("owners", [])
    return {
        "status": "pending",
        "value": float(claimed) if claimed is not None else None,
        "log": (
            f"General checks passed for {submission_dir.name}. "
            f"Awaiting manual review/approval or 'sar:verified' label from: {', '.join(reviewers)}."
        ),
        "details": {
            "reviewers": reviewers,
            "claimed": claimed,
        },
    }
