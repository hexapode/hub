"""Trusted report workflow logic (§7.2, §13).

Processes untrusted verification artifacts as data only, clamping strings,
escaping Markdown, computing labels, and checking auto-merge eligibility.
"""

from __future__ import annotations

import re
from typing import Any

from sar.leaderboard import format_metric_value, is_improvement

STICKY_COMMENT_MARKER = "<!-- sar:report-sticky -->"
MAX_STRING_LEN = 120
MAX_LOG_CHARS = 2000
MAX_LOG_LINES = 40


def escape_markdown(text: str, max_len: int = MAX_STRING_LEN) -> str:
    """Sanitize untrusted strings for safe inclusion in Markdown tables/comments."""
    cleaned = str(text or "").replace("\r", " ").replace("\n", " ").strip()
    if len(cleaned) > max_len:
        cleaned = cleaned[: max_len - 3] + "..."
    # Escape HTML tags and Markdown control characters
    cleaned = (
        cleaned.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("`", "'")
        .replace("[", "\\[")
        .replace("]", "\\]")
        .replace("|", "\\|")
    )
    return cleaned


def clamp_log_tail(log_text: str) -> str:
    raw = str(log_text or "")
    # Prevent closing the code fence via triple backticks in untrusted output
    safe = raw.replace("```", "'''")
    lines = safe.splitlines()
    if len(lines) > MAX_LOG_LINES:
        lines = ["... (truncated) ..."] + lines[-MAX_LOG_LINES:]
    joined = "\n".join(lines)
    if len(joined) > MAX_LOG_CHARS:
        joined = "... (truncated) ...\n" + joined[-MAX_LOG_CHARS:]
    return joined


def validate_artifact_shape(artifact: Any) -> dict[str, Any]:
    """Validate untrusted result.json artifact structure."""
    if not isinstance(artifact, dict):
        raise ValueError("Artifact root must be a JSON object")
    status = artifact.get("status")
    if status not in ("pass", "fail", "error", "pending"):
        raise ValueError(f"Invalid artifact status: {status!r}")
    val = artifact.get("value")
    if val is not None and (isinstance(val, bool) or not isinstance(val, (int, float))):
        raise ValueError(f"Invalid artifact value: {val!r}")
    log = artifact.get("log", "")
    if not isinstance(log, str):
        raise ValueError("Artifact 'log' must be a string")
    return {
        "status": status,
        "value": float(val) if val is not None else None,
        "log": log,
        "submission_id": str(artifact.get("submission_id", "submission")),
        "pr": artifact.get("pr"),
    }


def generate_pr_report(
    artifact_raw: Any,
    leaderboard: dict[str, Any],
    spec: dict[str, Any],
) -> dict[str, Any]:
    """Generate the PR comment, labels, and auto-merge decision from an artifact."""
    try:
        artifact = validate_artifact_shape(artifact_raw)
    except ValueError as exc:
        return {
            "status": "error",
            "beats_best": False,
            "labels_to_add": ["sar:failed"],
            "labels_to_remove": ["sar:verified"],
            "should_auto_merge": False,
            "comment": (
                f"{STICKY_COMMENT_MARKER}\n"
                f"### superAutoResearch Verification: Error\n\n"
                f"Malformed verification artifact: `{escape_markdown(str(exc))}`"
            ),
        }

    status = artifact["status"]
    measured = artifact["value"]
    sub_id = escape_markdown(artifact["submission_id"])
    metric = spec.get("metric", leaderboard.get("metric", {"name": "value", "direction": "min"}))
    direction = metric.get("direction", "min")
    tolerance = float(spec.get("verifier", {}).get("tolerance", 0.0))

    records = leaderboard.get("records", [])
    baseline_val = float(leaderboard.get("baseline", spec.get("baseline", {"value": 0.0}))["value"])
    current_best = float(records[-1]["value"]) if records else baseline_val

    beats_best = False
    if status == "pass" and measured is not None:
        beats_best = is_improvement(measured, current_best, direction, tolerance=tolerance)

    labels_to_add = ["sar:claim"]
    labels_to_remove: list[str] = []
    if status == "pass":
        labels_to_add.append("sar:verified")
        labels_to_remove.append("sar:failed")
    elif status in ("fail", "error"):
        labels_to_add.append("sar:failed")
        labels_to_remove.append("sar:verified")

    auto_merge_enabled = bool(spec.get("auto_merge", False))
    should_auto_merge = bool(auto_merge_enabled and status == "pass" and beats_best)

    measured_str = format_metric_value(measured, metric) if measured is not None else "—"
    best_str = format_metric_value(current_best, metric)
    beats_str = "Yes (New Record)" if beats_best else "No"
    log_tail = clamp_log_tail(artifact["log"])

    comment = (
        f"{STICKY_COMMENT_MARKER}\n"
        f"### superAutoResearch Verification Report\n\n"
        f"| Field | Value |\n"
        f"|---|---|\n"
        f"| **Submission** | `{sub_id}` |\n"
        f"| **Status** | `{status.upper()}` |\n"
        f"| **Measured Value** | `{escape_markdown(measured_str)}` |\n"
        f"| **Current Best** | `{escape_markdown(best_str)}` |\n"
        f"| **Beats Current Best** | **{beats_str}** |\n\n"
        f"<details>\n<summary>Verifier Log Tail</summary>\n\n"
        f"```text\n{log_tail}\n```\n"
        f"</details>\n"
    )

    return {
        "status": status,
        "measured_value": measured,
        "current_best": current_best,
        "beats_best": beats_best,
        "labels_to_add": labels_to_add,
        "labels_to_remove": labels_to_remove,
        "should_auto_merge": should_auto_merge,
        "comment": comment,
    }
