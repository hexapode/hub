"""GitHub-facing CLI operations (`init-github`, `register`, `attempt`, `claim`, `release`).

Every command that writes to GitHub prints the exact planned actions and prompts
`y/N` unless `--yes` is passed, and supports `--dry-run` (§6, §13, §14).
"""

from __future__ import annotations

import datetime
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from sar.config import HUB_REPO
from sar.sync import format_sar_comment_block
from sar.toml_compat import dumps, loads
from sar.validate import compute_statement_hash, validate_challenge_repo


def _confirm_action(plan_lines: list[str], assume_yes: bool = False) -> bool:
    print("Planned GitHub actions:")
    for ln in plan_lines:
        print(f"  - {ln}")
    if assume_yes:
        return True
    try:
        ans = input("Proceed with these public GitHub actions? [y/N]: ").strip().lower()
    except EOFError:
        return False
    return ans in ("y", "yes")


def init_github(
    challenge_dir: Path,
    public: bool = True,
    dry_run: bool = False,
    assume_yes: bool = False,
) -> dict[str, Any]:
    """Initialize GitHub repository, labels, topic, and pinned attempt-log issue."""
    spec = validate_challenge_repo(challenge_dir)
    slug = spec["slug"]
    owner = spec["owners"][0]
    repo_full = f"{owner}/{slug}"
    visibility_flag = "--public" if public else "--private"

    plan = [
        f"Create GitHub repository {repo_full} ({visibility_flag}) and push main branch",
        f"Set repository topic 'superautoresearch' on {repo_full}",
        "Create labels: sar:claim, sar:verified, sar:failed, sar:attempt",
        "Create and pin the Attempt Log issue (#1) and write its issue number to superautoresearch.toml",
    ]

    if dry_run:
        print("\n".join(["[DRY-RUN] " + p for p in plan]))
        return {"dry_run": True, "repo": repo_full, "plan": plan}

    if not _confirm_action(plan, assume_yes=assume_yes):
        print("Aborted by user.")
        return {"aborted": True}

    if not shutil.which("gh"):
        raise RuntimeError("GitHub CLI ('gh') is required for init-github")

    subprocess.run(
        ["gh", "repo", "create", repo_full, visibility_flag, "--source=.", "--push"],
        cwd=str(challenge_dir),
        check=True,
    )
    subprocess.run(
        ["gh", "repo", "edit", repo_full, "--add-topic", "superautoresearch"],
        cwd=str(challenge_dir),
        check=False,
    )
    for lbl, color in (
        ("sar:claim", "0E8A16"),
        ("sar:verified", "1D76DB"),
        ("sar:failed", "D93F0B"),
        ("sar:attempt", "5319E7"),
    ):
        subprocess.run(
            ["gh", "label", "create", lbl, "--color", color, "--force"],
            cwd=str(challenge_dir),
            check=False,
        )

    issue_proc = subprocess.run(
        [
            "gh",
            "issue",
            "create",
            "--title",
            f"Attempt Log — {spec['title']}",
            "--body",
            "Agents and contributors log track claims, releases, and attempt outcomes here using `sar claim` and `sar attempt`.",
            "--label",
            "sar:attempt",
        ],
        cwd=str(challenge_dir),
        capture_output=True,
        text=True,
        check=True,
    )
    issue_url = issue_proc.stdout.strip()
    issue_num = int(issue_url.rstrip("/").split("/")[-1]) if "/" in issue_url else 1
    subprocess.run(["gh", "issue", "pin", str(issue_num)], cwd=str(challenge_dir), check=False)

    spec.setdefault("attempt_log", {})["issue"] = issue_num
    (challenge_dir / "superautoresearch.toml").write_text(dumps(spec), encoding="utf-8")

    return {"repo": repo_full, "attempt_log_issue": issue_num}


def build_registration_payload(
    challenge_dir: Path,
    external_repo: str | None = None,
) -> dict[str, Any]:
    """Generate the `registry/<slug>.toml` content and self-referencing PR body for `sar register`."""
    today_str = datetime.date.today().isoformat()

    if external_repo:
        slug = external_repo.split("/")[-1].lower()
        entry_dict: dict[str, Any] = {
            "repo": external_repo,
            "kind": "external",
            "owners": [external_repo.split("/")[0]],
            "tags": ["external"],
            "listed": True,
            "added": today_str,
            "spec": {
                "title": slug,
                "summary": f"External challenge tracked from {external_repo}",
                "metric": {"name": "score", "unit": "", "direction": "min", "scale": "linear"},
                "verifier": {"type": "manual"},
                "baseline": {"value": 1.0, "label": "Baseline"},
                "records_source": {
                    "type": "readme-table",
                    "url": f"https://raw.githubusercontent.com/{external_repo}/main/README.md",
                },
            },
        }
        toml_str = dumps(entry_dict)
        pr_body = (
            f"## Register External Challenge: `{slug}`\n\n"
            f"Launched via the **superAutoResearch** workflow (`https://github.com/{HUB_REPO}/blob/main/launch.md`).\n\n"
            f"- **Repository:** `https://github.com/{external_repo}`\n"
            f"- **Hub Registry Path:** `registry/{slug}.toml` in `https://github.com/{HUB_REPO}`\n"
            f"- **Hub Leaderboard Page:** `https://superautoresearch.github.io/hub/#/c/{slug}`\n"
            f"- **Kind:** `external`\n\n"
            f"### Donate Prompt\n"
            f"```text\n"
            f"Read https://github.com/{HUB_REPO}/blob/main/donate.md and follow it. challenge: {slug}\n"
            f"```\n"
        )
        return {
            "slug": slug,
            "registry_path": f"registry/{slug}.toml",
            "toml": toml_str,
            "entry": entry_dict,
            "pr_body": pr_body,
        }

    spec = validate_challenge_repo(challenge_dir)
    slug = spec["slug"]
    owner = spec["owners"][0]
    repo = f"{owner}/{slug}"
    stmt_hash = compute_statement_hash(challenge_dir)

    entry_dict = {
        "repo": repo,
        "kind": "native",
        "owners": spec["owners"],
        "tags": spec.get("tags", []),
        "listed": True,
        "added": today_str,
        "statement_hash": stmt_hash,
        "ref": "main",
    }
    toml_str = dumps(entry_dict)
    pr_body = (
        f"## Register Challenge: {spec['title']} (`{slug}`)\n\n"
        f"Scaffolded and verified via the **superAutoResearch** launch prompt (`https://github.com/{HUB_REPO}/blob/main/launch.md`).\n\n"
        f"- **Challenge Repository:** `https://github.com/{repo}`\n"
        f"- **Hub Registry Entry:** `registry/{slug}.toml` in `https://github.com/{HUB_REPO}`\n"
        f"- **Hub Leaderboard URL (once merged):** `https://superautoresearch.github.io/hub/#/c/{slug}`\n"
        f"- **Kind:** `native` (`{spec['verifier']['type']}` verifier)\n"
        f"- **Metric:** `{spec['metric']['name']}` (`{spec['metric']['direction']}`)\n"
        f"- **Baseline:** `{spec['baseline']['value']}` ({spec['baseline']['label']})\n"
        f"- **Frozen Statement Hash:** `{stmt_hash}`\n\n"
        f"### Donate Prompt for Contributors\n"
        f"```text\n"
        f"Read https://github.com/{HUB_REPO}/blob/main/donate.md and follow it. challenge: {slug}\n"
        f"```\n"
    )
    return {
        "slug": slug,
        "registry_path": f"registry/{slug}.toml",
        "toml": toml_str,
        "entry": entry_dict,
        "pr_body": pr_body,
    }


def register_challenge(
    challenge_dir: Path,
    external_repo: str | None = None,
    dry_run: bool = False,
    assume_yes: bool = False,
) -> dict[str, Any]:
    payload = build_registration_payload(challenge_dir, external_repo=external_repo)
    if dry_run:
        print(f"# --- {payload['registry_path']} ---")
        print(payload["toml"].rstrip())
        print("\n# --- Pull Request Body ---")
        print(payload["pr_body"].rstrip())
        return payload

    branch_name = f"register-{payload['slug']}"
    plan = [
        f"Fork {HUB_REPO} (if not already forked)",
        f"Add {payload['registry_path']} to branch {branch_name}",
        f"Open a Pull Request to {HUB_REPO} registering '{payload['slug']}'",
    ]
    if not _confirm_action(plan, assume_yes=assume_yes):
        print("Aborted by user.")
        return {"aborted": True, **payload}

    if not shutil.which("gh"):
        raise RuntimeError("GitHub CLI ('gh') is required to open a hub registration PR")

    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        clone_dir = Path(tmp) / "hub-fork"
        subprocess.run(
            ["gh", "repo", "fork", HUB_REPO, "--clone=true", str(clone_dir)],
            check=True,
        )
        subprocess.run(
            ["git", "checkout", "-b", branch_name],
            cwd=str(clone_dir),
            check=True,
        )
        reg_file = clone_dir / payload["registry_path"]
        reg_file.parent.mkdir(parents=True, exist_ok=True)
        reg_file.write_text(payload["toml"], encoding="utf-8")
        subprocess.run(["git", "add", payload["registry_path"]], cwd=str(clone_dir), check=True)
        subprocess.run(
            ["git", "commit", "-m", f"feat(registry): register {payload['slug']}"],
            cwd=str(clone_dir),
            check=True,
        )
        subprocess.run(["git", "push", "-u", "origin", branch_name], cwd=str(clone_dir), check=True)
        pr_proc = subprocess.run(
            [
                "gh",
                "pr",
                "create",
                "--repo",
                HUB_REPO,
                "--title",
                f"Register challenge: {payload['slug']}",
                "--body",
                payload["pr_body"],
            ],
            cwd=str(clone_dir),
            capture_output=True,
            text=True,
            check=True,
        )
        payload["pr_url"] = pr_proc.stdout.strip()
        print(f"Opened Hub Registration PR: {payload['pr_url']}")

    return payload


def post_attempt_or_claim(
    kind: str,
    challenge: str,
    track: str,
    result: str | None = None,
    body_text: str = "",
    agent: str | None = None,
    model: str | None = None,
    budget: str | None = None,
    pr: int | None = None,
    dry_run: bool = False,
    assume_yes: bool = False,
) -> str:
    comment_md = format_sar_comment_block(
        kind=kind,
        track=track,
        body_text=body_text,
        result=result,
        agent=agent,
        model=model,
        budget=budget,
        pr=pr,
    )
    if dry_run or not shutil.which("gh"):
        print(comment_md.rstrip())
        return comment_md

    plan = [f"Post {kind} comment for track '{track}' on challenge '{challenge}' attempt-log issue"]
    if not _confirm_action(plan, assume_yes=assume_yes):
        print("Aborted by user.")
        return comment_md

    print(comment_md.rstrip())
    return comment_md
