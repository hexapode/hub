"""Leaderboard generation and README table rendering (§4.4, §6, §7.3)."""

from __future__ import annotations

import datetime
import json
import subprocess
from pathlib import Path
from typing import Any

from sar.toml_compat import TOMLDecodeError, loads
from sar.validate import ValidationError, validate_spec_dict, validate_submission_dict
from sar.verifiers import verify_submission

LEADERBOARD_START_MARKER = "<!-- sar:leaderboard:start -->"
LEADERBOARD_END_MARKER = "<!-- sar:leaderboard:end -->"


def is_improvement(
    candidate: float,
    current_best: float,
    direction: str,
    tolerance: float = 0.0,
) -> bool:
    if direction == "max":
        return candidate > current_best + tolerance
    return candidate < current_best - tolerance


def format_metric_value(value: float, metric: dict[str, Any]) -> str:
    val_str = f"{value:g}" if isinstance(value, (int, float)) else str(value)
    display = metric.get("display")
    unit = metric.get("unit", "")
    if display and "{value}" in display:
        return display.replace("{value}", val_str)
    if unit:
        return f"{val_str} {unit}"
    return val_str


def _get_submission_date(challenge_dir: Path, sub_dir: Path, res_data: dict[str, Any]) -> str:
    if res_data.get("date"):
        return str(res_data["date"])
    # Check git log for submission.toml
    try:
        rel = (sub_dir / "submission.toml").relative_to(challenge_dir).as_posix()
        proc = subprocess.run(
            ["git", "log", "-1", "--format=%cI", "--", rel],
            cwd=str(challenge_dir),
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return proc.stdout.strip()
    except Exception:
        pass
    mtime = (sub_dir / "submission.toml").stat().st_mtime
    return datetime.datetime.fromtimestamp(mtime, tz=datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def _fetch_open_claims_via_gh(challenge_dir: Path) -> list[dict[str, Any]]:
    try:
        proc = subprocess.run(
            [
                "gh",
                "pr",
                "list",
                "--label",
                "sar:claim",
                "--state",
                "open",
                "--json",
                "number,title,author,createdAt,url,headRefName",
            ],
            cwd=str(challenge_dir),
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if proc.returncode != 0 or not proc.stdout.strip():
            return []
        prs = json.loads(proc.stdout)
        claims: list[dict[str, Any]] = []
        for pr in prs:
            author_login = (pr.get("author") or {}).get("login", "unknown")
            claims.append(
                {
                    "id": pr.get("headRefName") or f"{author_login}-pr-{pr.get('number')}",
                    "value": 0.0,
                    "evidence": "claimed",
                    "author": author_login,
                    "pr": int(pr.get("number", 0)),
                    "date": pr.get("createdAt", datetime.datetime.now(datetime.timezone.utc).isoformat()),
                    "url": pr.get("url", ""),
                }
            )
        return claims
    except Exception:
        return []


def render_readme_section(
    leaderboard: dict[str, Any],
    other_submissions: list[dict[str, Any]],
    verifier_type: str = "script",
) -> str:
    metric = leaderboard["metric"]
    baseline = leaderboard["baseline"]
    records = leaderboard.get("records", [])
    claims = leaderboard.get("claims", [])

    evidence_label = "Verified"
    if verifier_type == "lean":
        evidence_label = "Lean verified"
    elif verifier_type == "manual":
        evidence_label = "Human verified"

    lines: list[str] = [
        LEADERBOARD_START_MARKER,
        f"**Baseline:** `{format_metric_value(baseline['value'], metric)}` ({baseline['label']})  ",
        f"**Metric:** {metric['name']} ({'lower is better' if metric['direction'] == 'min' else 'higher is better'})",
        "",
        "| # | Record | Holder | Agent / Model (self-reported) | Evidence | Date | PR |",
        "|---|---|---|---|---|---|---|",
    ]

    if not records:
        lines.append(
            f"| 0 | `{format_metric_value(baseline['value'], metric)}` | Baseline | — | Baseline | — | — |"
        )
    else:
        for idx, rec in enumerate(records, start=1):
            val_fmt = format_metric_value(rec["value"], metric)
            agent_model = " / ".join(filter(None, [rec.get("agent"), rec.get("model")])) or "—"
            ev = evidence_label if rec.get("evidence") == "verified" else "Claimed"
            date_short = str(rec.get("date", ""))[:10]
            pr_num = rec.get("pr")
            pr_url = rec.get("url")
            pr_cell = f"[#{pr_num}]({pr_url})" if pr_num and pr_url else (f"#{pr_num}" if pr_num else "—")
            lines.append(
                f"| {idx} | `{val_fmt}` | @{rec['author']} | {agent_model} | {ev} | {date_short} | {pr_cell} |"
            )

    if claims:
        lines.append("")
        lines.append("### Open Claims")
        lines.append("")
        lines.append("| Submission | Claimed Value | Author | Date | PR |")
        lines.append("|---|---|---|---|---|")
        for cl in claims:
            val_fmt = format_metric_value(cl["value"], metric)
            date_short = str(cl.get("date", ""))[:10]
            pr_num = cl.get("pr")
            pr_cell = f"#{pr_num}" if pr_num else "—"
            lines.append(
                f"| `{cl['id']}` | `{val_fmt}` | @{cl['author']} | {date_short} | {pr_cell} |"
            )

    if other_submissions:
        lines.append("")
        lines.append("### Other accepted submissions")
        lines.append("")
        lines.append("| Submission | Value | Author | Title | Date |")
        lines.append("|---|---|---|---|---|")
        for sub in other_submissions:
            val_fmt = format_metric_value(sub["value"], metric)
            date_short = str(sub.get("date", ""))[:10]
            lines.append(
                f"| `{sub['id']}` | `{val_fmt}` | @{sub['author']} | {sub.get('title', '—')} | {date_short} |"
            )

    lines.append(LEADERBOARD_END_MARKER)
    return "\n".join(lines)


def update_readme_leaderboard(readme_path: Path, rendered_section: str) -> None:
    if not readme_path.is_file():
        return
    content = readme_path.read_text(encoding="utf-8")
    if LEADERBOARD_START_MARKER in content and LEADERBOARD_END_MARKER in content:
        start_idx = content.index(LEADERBOARD_START_MARKER)
        end_idx = content.index(LEADERBOARD_END_MARKER) + len(LEADERBOARD_END_MARKER)
        updated = content[:start_idx] + rendered_section + content[end_idx:]
    else:
        updated = content.rstrip() + "\n\n## Leaderboard\n\n" + rendered_section + "\n"
    readme_path.write_text(updated, encoding="utf-8")


def build_leaderboard(
    challenge_dir: Path,
    fetch_prs: bool = False,
    reverify_missing: bool = True,
) -> dict[str, Any]:
    """Scan `submissions/`, compute the record chain, and write `leaderboard.json` + `README.md`."""
    challenge_dir = challenge_dir.resolve()
    spec_path = challenge_dir / "superautoresearch.toml"
    spec = loads(spec_path.read_text(encoding="utf-8"))
    validate_spec_dict(spec)

    metric = spec["metric"]
    baseline = spec["baseline"]
    vtype = spec["verifier"]["type"]
    tolerance = float(spec["verifier"].get("tolerance", 0.0))
    direction = metric["direction"]

    submissions_root = challenge_dir / "submissions"
    valid_entries: list[dict[str, Any]] = []
    claims: list[dict[str, Any]] = []

    # Preserve existing claims/attempts if present and not overwritten
    existing_lb_path = challenge_dir / "leaderboard.json"
    existing_attempts = 0
    existing_claims: list[dict[str, Any]] = []
    if existing_lb_path.is_file():
        try:
            old_lb = json.loads(existing_lb_path.read_text(encoding="utf-8"))
            existing_attempts = int(old_lb.get("attempts", 0))
            existing_claims = old_lb.get("claims", [])
        except Exception:
            pass

    if submissions_root.is_dir():
        for sub_dir in sorted(p for p in submissions_root.iterdir() if p.is_dir()):
            sub_toml = sub_dir / "submission.toml"
            if not sub_toml.is_file():
                continue
            try:
                sub_meta = loads(sub_toml.read_text(encoding="utf-8"))
                validate_submission_dict(sub_meta)
            except (TOMLDecodeError, ValidationError):
                # Invalid submission.toml -> skip
                continue

            sub_id = sub_dir.name
            author = str(sub_meta["author"])
            if not sub_id.startswith(f"{author}-"):
                continue

            # Check required files
            req_files = spec.get("submission", {}).get("required_files", [])
            if any(not (sub_dir / rf).is_file() for rf in req_files):
                continue

            result_path = sub_dir / ".result.json"
            res_data: dict[str, Any] | None = None
            if result_path.is_file():
                try:
                    res_data = json.loads(result_path.read_text(encoding="utf-8"))
                except Exception:
                    res_data = None
            elif reverify_missing:
                vres = verify_submission(challenge_dir, sub_dir, no_docker=True)
                res_data = {
                    "status": vres["status"],
                    "value": vres["value"],
                    "date": _get_submission_date(challenge_dir, sub_dir, {}),
                }
                if vres["status"] in ("pass", "pending"):
                    try:
                        result_path.write_text(json.dumps(res_data, indent=2) + "\n", encoding="utf-8")
                    except Exception:
                        pass

            if not res_data:
                continue

            status = res_data.get("status")
            val = res_data.get("value")
            if val is None:
                val = sub_meta.get("claimed")
            if val is None:
                continue

            date_str = _get_submission_date(challenge_dir, sub_dir, res_data)

            if status == "pass":
                entry: dict[str, Any] = {
                    "id": sub_id,
                    "title": sub_meta.get("title", sub_id),
                    "value": float(val),
                    "evidence": res_data.get("evidence", "verified"),
                    "author": author,
                    "date": date_str,
                }
                if sub_meta.get("agent"):
                    entry["agent"] = sub_meta["agent"]
                if sub_meta.get("model"):
                    entry["model"] = sub_meta["model"]
                if res_data.get("pr") is not None:
                    entry["pr"] = int(res_data["pr"])
                if res_data.get("commit"):
                    entry["commit"] = str(res_data["commit"])
                if res_data.get("url"):
                    entry["url"] = str(res_data["url"])
                valid_entries.append(entry)
            elif status == "pending":
                claim_entry: dict[str, Any] = {
                    "id": sub_id,
                    "value": float(val),
                    "evidence": "claimed",
                    "author": author,
                    "date": date_str,
                }
                if res_data.get("pr") is not None:
                    claim_entry["pr"] = int(res_data["pr"])
                claims.append(claim_entry)

    # Sort valid passing submissions chronologically by (date, id)
    valid_entries.sort(key=lambda x: (x["date"], x["id"]))

    records: list[dict[str, Any]] = []
    other_submissions: list[dict[str, Any]] = []
    current_best = float(baseline["value"])

    for entry in valid_entries:
        if is_improvement(entry["value"], current_best, direction, tolerance=tolerance):
            current_best = entry["value"]
            rec = {k: v for k, v in entry.items() if k != "title"}
            records.append(rec)
        else:
            other_submissions.append(entry)

    if fetch_prs:
        gh_claims = _fetch_open_claims_via_gh(challenge_dir)
        if gh_claims:
            claims.extend(gh_claims)
    elif not claims and existing_claims:
        claims = existing_claims

    contributors_set = {e["author"] for e in valid_entries} | {c["author"] for c in claims}
    now_iso = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    leaderboard: dict[str, Any] = {
        "schema": 1,
        "slug": spec["slug"],
        "metric": metric,
        "baseline": baseline,
        "records": records,
        "claims": claims,
        "contributors": len(contributors_set),
        "attempts": max(existing_attempts, len(valid_entries) + len(claims)),
        "updated": now_iso,
    }
    if other_submissions:
        leaderboard["other_submissions"] = other_submissions

    (challenge_dir / "leaderboard.json").write_text(
        json.dumps(leaderboard, indent=2) + "\n", encoding="utf-8"
    )

    readme_section = render_readme_section(leaderboard, other_submissions, verifier_type=vtype)
    update_readme_leaderboard(challenge_dir / "README.md", readme_section)

    return leaderboard
