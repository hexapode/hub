"""General submission checks run before any verifier backend (§5)."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

from sar.toml_compat import TOMLDecodeError, loads
from sar.validate import ValidationError, compute_statement_hash, validate_submission_dict

FROZEN_PREFIXES = ("statement/", "verifier/", ".github/", ".sar/")


def _check_frozen_paths(challenge_dir: Path, is_baseline: bool = False) -> list[str]:
    """Check if frozen paths (statement/, verifier/, .github/, .sar/) were modified."""
    errors: list[str] = []

    # 1. Check against stored baseline hash in .sar/statement_hash if present
    hash_file = challenge_dir / ".sar" / "statement_hash"
    if hash_file.is_file():
        expected_hash = hash_file.read_text(encoding="utf-8").strip()
        current_hash = compute_statement_hash(challenge_dir)
        if expected_hash and current_hash != expected_hash:
            errors.append(
                f"Frozen statement/ or verifier/ files were modified "
                f"(expected {expected_hash}, got {current_hash})"
            )

    # 2. If git repository with at least one commit, check git status / diff
    git_dir = challenge_dir / ".git"
    if git_dir.exists() and not is_baseline:
        try:
            head_check = subprocess.run(
                ["git", "rev-parse", "--verify", "HEAD"],
                cwd=str(challenge_dir),
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            if head_check.returncode == 0:
                proc = subprocess.run(
                    ["git", "status", "--porcelain"],
                    cwd=str(challenge_dir),
                    capture_output=True,
                    text=True,
                    timeout=5,
                    check=False,
                )
                if proc.returncode == 0:
                    changed_submissions: set[str] = set()
                    for line in proc.stdout.splitlines():
                        if len(line) < 4:
                            continue
                        rel_path = line[3:].strip().strip('"')
                        if " -> " in rel_path:
                            rel_path = rel_path.split(" -> ")[-1].strip()
                        if any(
                            rel_path.startswith(fp) or rel_path == fp.rstrip("/")
                            for fp in FROZEN_PREFIXES
                        ):
                            errors.append(f"Submission must not modify frozen path: {rel_path}")
                        if rel_path.startswith("submissions/"):
                            parts = Path(rel_path).parts
                            if len(parts) >= 2:
                                changed_submissions.add(parts[1])
                    if len(changed_submissions) > 1:
                        errors.append(
                            f"PR/working tree touches multiple submission directories: {sorted(changed_submissions)}"
                        )
        except Exception:
            pass

    return errors


def run_general_checks(
    challenge_dir: Path,
    submission_dir: Path,
    spec: dict[str, Any],
    pr_author: str | None = None,
) -> tuple[bool, dict[str, Any] | None, list[str]]:
    """Run general checks (§5) on a submission directory.

    Returns (passed, parsed_submission_toml_or_None, error_messages).
    """
    errors: list[str] = []
    submission_dir = submission_dir.resolve()
    challenge_dir = challenge_dir.resolve()

    if not submission_dir.is_dir():
        return False, None, [f"Submission directory does not exist: {submission_dir}"]

    try:
        rel_sub = submission_dir.relative_to(challenge_dir).as_posix()
    except ValueError:
        rel_sub = submission_dir.name

    is_baseline = rel_sub in ("statement/baseline", "baseline")

    # Check frozen paths
    errors.extend(_check_frozen_paths(challenge_dir, is_baseline=is_baseline))

    # Load and validate submission.toml
    sub_toml_path = submission_dir / "submission.toml"
    parsed_sub: dict[str, Any] | None = None
    if not sub_toml_path.is_file():
        errors.append(f"Missing submission.toml in {rel_sub}")
    else:
        try:
            parsed_sub = loads(sub_toml_path.read_text(encoding="utf-8"))
            validate_submission_dict(parsed_sub)
        except (TOMLDecodeError, ValidationError) as exc:
            errors.append(f"Invalid submission.toml: {exc}")

    # Check <id> starts with <author>- (for regular submissions under submissions/<id>)
    if parsed_sub and not is_baseline:
        sub_id = submission_dir.name
        author = str(parsed_sub.get("author", ""))
        if not sub_id.startswith(f"{author}-"):
            errors.append(
                f"Submission directory id {sub_id!r} must start with '<author>-' ({author + '-'}...)"
            )
        effective_pr_author = pr_author or os.environ.get("SAR_PR_AUTHOR")
        if effective_pr_author and author != effective_pr_author:
            errors.append(
                f"submission.toml author {author!r} does not match PR author {effective_pr_author!r}"
            )
        # Validate track if specified
        track_id = parsed_sub.get("track")
        if track_id:
            valid_tracks = {t["id"] for t in spec.get("tracks", [])}
            if valid_tracks and track_id not in valid_tracks:
                errors.append(f"Unknown track {track_id!r}; valid tracks: {sorted(valid_tracks)}")

    # Check required_files
    sub_spec = spec.get("submission", {})
    req_files = sub_spec.get("required_files", [])
    for req in req_files:
        if not (submission_dir / req).is_file():
            errors.append(f"Missing required submission file: {req}")

    # Check size limit
    max_mb = float(sub_spec.get("max_size_mb", 20))
    total_bytes = sum(
        f.stat().st_size for f in submission_dir.rglob("*") if f.is_file()
    )
    max_bytes = int(max_mb * 1024 * 1024)
    if total_bytes > max_bytes:
        errors.append(
            f"Submission size ({total_bytes / (1024 * 1024):.2f} MB) exceeds max_size_mb ({max_mb} MB)"
        )

    return len(errors) == 0, parsed_sub, errors
