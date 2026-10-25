"""Validation logic for challenge repos, registry entries, submissions, and leaderboards."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from sar.config import SLUG_REGEX
from sar.schema_validator import SchemaValidationError, validate_against_schema
from sar.toml_compat import TOMLDecodeError, loads


class ValidationError(ValueError):
    """Raised when validation of a challenge repo or file fails."""


IGNORED_HASH_PARTS = {"__pycache__", ".lake", "build", ".DS_Store", ".result.json"}


def compute_statement_hash(challenge_dir: Path) -> str:
    """Compute deterministic sha256 hash of statement/ and verifier/ directories."""
    h = hashlib.sha256()
    for folder_name in ("statement", "verifier"):
        folder = challenge_dir / folder_name
        if not folder.exists():
            continue
        files = sorted(p for p in folder.rglob("*") if p.is_file())
        for fpath in files:
            rel = fpath.relative_to(challenge_dir).as_posix()
            if any(part in IGNORED_HASH_PARTS for part in fpath.parts):
                continue
            if fpath.name.endswith(".pyc") or fpath.name.endswith(".olean"):
                continue
            h.update(rel.encode("utf-8"))
            h.update(b"\0")
            h.update(fpath.read_bytes())
            h.update(b"\0")
    return f"sha256:{h.hexdigest()}"


def validate_spec_dict(spec: dict[str, Any]) -> None:
    """Validate a parsed superautoresearch.toml dictionary."""
    try:
        validate_against_schema(spec, "challenge_spec")
    except SchemaValidationError as exc:
        raise ValidationError(f"Spec schema error: {exc}") from exc

    # Ensure track IDs are unique
    tracks = spec.get("tracks", [])
    seen_ids: set[str] = set()
    for t in tracks:
        tid = t["id"]
        if tid in seen_ids:
            raise ValidationError(f"Duplicate track id: {tid!r}")
        seen_ids.add(tid)

    # Check verifier-specific required keys
    v = spec.get("verifier", {})
    vtype = v.get("type")
    if vtype == "script":
        if not v.get("command"):
            raise ValidationError("script verifier requires 'command'")
    elif vtype == "lean":
        if not v.get("statement") or not v.get("theorem_name"):
            raise ValidationError("lean verifier requires 'statement' and 'theorem_name'")
    elif vtype == "custom":
        if not v.get("command"):
            raise ValidationError("custom verifier requires 'command'")


def validate_registry_dict(entry: dict[str, Any], slug: str | None = None) -> None:
    """Validate a parsed registry/<slug>.toml dictionary."""
    if slug is not None and not re.match(SLUG_REGEX, slug):
        raise ValidationError(f"Invalid registry slug {slug!r}; must match {SLUG_REGEX}")

    try:
        validate_against_schema(entry, "registry_entry")
    except SchemaValidationError as exc:
        raise ValidationError(f"Registry entry schema error: {exc}") from exc

    if entry.get("kind") == "external":
        spec = entry.get("spec")
        if not spec:
            raise ValidationError("External registry entry must include [spec]")
        tracks = spec.get("tracks", [])
        seen_ids: set[str] = set()
        for t in tracks:
            tid = t["id"]
            if tid in seen_ids:
                raise ValidationError(f"Duplicate track id in external spec: {tid!r}")
            seen_ids.add(tid)


def validate_submission_dict(sub: dict[str, Any]) -> None:
    """Validate a parsed submission.toml dictionary."""
    try:
        validate_against_schema(sub, "submission")
    except SchemaValidationError as exc:
        raise ValidationError(f"Submission schema error: {exc}") from exc


def validate_leaderboard_dict(lb: dict[str, Any]) -> None:
    """Validate a parsed leaderboard.json dictionary."""
    try:
        validate_against_schema(lb, "leaderboard")
    except SchemaValidationError as exc:
        raise ValidationError(f"Leaderboard schema error: {exc}") from exc


def validate_challenge_repo(challenge_dir: Path) -> dict[str, Any]:
    """Validate a full challenge repository directory and return its parsed spec."""
    spec_file = challenge_dir / "superautoresearch.toml"
    if not spec_file.is_file():
        raise ValidationError(f"Missing superautoresearch.toml in {challenge_dir}")

    try:
        spec = loads(spec_file.read_text(encoding="utf-8"))
    except TOMLDecodeError as exc:
        raise ValidationError(f"Invalid TOML in superautoresearch.toml: {exc}") from exc

    validate_spec_dict(spec)

    required_dirs = ["statement", "verifier", "submissions", ".github/workflows"]
    for d in required_dirs:
        if not (challenge_dir / d).is_dir():
            raise ValidationError(f"Missing required directory: {d}")

    required_workflows = ["verify.yml", "report.yml", "leaderboard.yml"]
    for wf in required_workflows:
        if not (challenge_dir / ".github" / "workflows" / wf).is_file():
            raise ValidationError(f"Missing required workflow: .github/workflows/{wf}")

    if not (challenge_dir / "README.md").is_file():
        raise ValidationError("Missing README.md")
    if not (challenge_dir / "AGENTS.md").is_file():
        raise ValidationError("Missing AGENTS.md")

    return spec


def validate_path(target: Path, external: bool = False) -> dict[str, Any]:
    """Validate a challenge directory, registry file, submission file, or leaderboard file."""
    if target.is_dir():
        spec = validate_challenge_repo(target)
        return {"ok": True, "kind": "challenge_repo", "slug": spec["slug"], "spec": spec}

    if not target.is_file():
        raise ValidationError(f"Target path does not exist: {target}")

    if target.suffix == ".json":
        try:
            data = json.loads(target.read_text(encoding="utf-8"))
        except Exception as exc:
            raise ValidationError(f"Invalid JSON in {target}: {exc}") from exc
        validate_leaderboard_dict(data)
        return {"ok": True, "kind": "leaderboard", "slug": data.get("slug")}

    if target.suffix == ".toml":
        try:
            data = loads(target.read_text(encoding="utf-8"))
        except TOMLDecodeError as exc:
            raise ValidationError(f"Invalid TOML in {target}: {exc}") from exc

        if target.name == "superautoresearch.toml":
            validate_spec_dict(data)
            return {"ok": True, "kind": "challenge_spec", "slug": data.get("slug")}
        if target.name == "submission.toml":
            validate_submission_dict(data)
            return {"ok": True, "kind": "submission", "author": data.get("author")}

        slug = target.stem
        validate_registry_dict(data, slug=slug)
        result: dict[str, Any] = {"ok": True, "kind": "registry_entry", "slug": slug, "entry": data}
        if external or data.get("kind") == "external":
            from sar.sync import parse_external_records

            records = parse_external_records(data, hub_dir=target.parent.parent)
            result["parsed_records_count"] = len(records)
        return result

    raise ValidationError(f"Unsupported file type for validation: {target}")
