"""Verifier dispatcher and shared interface (§5)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, TypedDict

from sar.checks import run_general_checks
from sar.toml_compat import loads
from sar.validate import validate_spec_dict


class VerifyResult(TypedDict):
    status: str  # "pass" | "fail" | "error" | "pending"
    value: float | None
    log: str
    details: dict[str, Any]


def parse_timeout_seconds(timeout_str: str) -> int:
    s = timeout_str.strip().lower()
    if s.endswith("ms"):
        return max(1, int(float(s[:-2]) / 1000))
    if s.endswith("s"):
        return int(float(s[:-1]))
    if s.endswith("m"):
        return int(float(s[:-1]) * 60)
    if s.endswith("h"):
        return int(float(s[:-1]) * 3600)
    return int(float(s))


def verify_submission(
    challenge_dir: Path,
    submission_dir: Path,
    no_docker: bool = False,
    pr_author: str | None = None,
) -> VerifyResult:
    """Run general checks and dispatch to the configured verifier backend."""
    challenge_dir = challenge_dir.resolve()
    submission_dir = submission_dir.resolve()

    spec_path = challenge_dir / "superautoresearch.toml"
    if not spec_path.is_file():
        return {
            "status": "error",
            "value": None,
            "log": f"Missing superautoresearch.toml in {challenge_dir}",
            "details": {},
        }

    try:
        spec = loads(spec_path.read_text(encoding="utf-8"))
        validate_spec_dict(spec)
    except Exception as exc:
        return {
            "status": "error",
            "value": None,
            "log": f"Invalid challenge spec: {exc}",
            "details": {},
        }

    ok, sub_meta, check_errors = run_general_checks(
        challenge_dir=challenge_dir,
        submission_dir=submission_dir,
        spec=spec,
        pr_author=pr_author,
    )
    if not ok or sub_meta is None:
        return {
            "status": "fail",
            "value": None,
            "log": "General checks failed:\n" + "\n".join(f"- {e}" for e in check_errors),
            "details": {"errors": check_errors, "stage": "general_checks"},
        }

    claimed_raw = sub_meta.get("claimed")
    claimed = float(claimed_raw) if claimed_raw is not None else None
    vtype = spec["verifier"]["type"]

    if vtype == "script":
        from sar.verifiers.script import verify as verify_script

        return verify_script(challenge_dir, submission_dir, spec, claimed, no_docker=no_docker)
    if vtype == "lean":
        from sar.verifiers.lean import verify as verify_lean

        return verify_lean(challenge_dir, submission_dir, spec, claimed)
    if vtype == "manual":
        from sar.verifiers.manual import verify as verify_manual

        return verify_manual(challenge_dir, submission_dir, spec, claimed)
    if vtype == "custom":
        from sar.verifiers.custom import verify as verify_custom

        return verify_custom(challenge_dir, submission_dir, spec, claimed)

    return {
        "status": "error",
        "value": None,
        "log": f"Unsupported verifier type: {vtype}",
        "details": {},
    }
