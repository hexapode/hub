"""Command-line interface for `sar` (§6)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sar import __version__
from sar.github_ops import init_github, post_attempt_or_claim, register_challenge
from sar.leaderboard import build_leaderboard
from sar.new_challenge import create_challenge
from sar.report import generate_pr_report
from sar.sync import sync_hub
from sar.toml_compat import loads
from sar.validate import ValidationError, validate_path
from sar.verifiers import verify_submission


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sar",
        description="superAutoResearch CLI — launch, verify, leaderboard, register, donate, and sync open research challenges.",
    )
    parser.add_argument("--version", action="version", version=f"sar {__version__}")

    subparsers = parser.add_subparsers(dest="command", metavar="<command>")

    # 1. sar new <slug> --type script|lean|manual [--dir PATH] [--title ..]
    p_new = subparsers.add_parser(
        "new",
        help="Scaffold a new challenge repository from templates (_common + type)",
    )
    p_new.add_argument("slug", help="Challenge slug (^[a-z0-9][a-z0-9-]{1,48}$)")
    p_new.add_argument(
        "--type",
        required=True,
        choices=["script", "lean", "manual"],
        dest="vtype",
        help="Verifier template type",
    )
    p_new.add_argument("--dir", default=".", help="Parent directory to create <slug>/ in")
    p_new.add_argument("--title", default=None, help="Human-readable challenge title")
    p_new.add_argument("--owner", default="alice", help="GitHub owner login")

    # 2. sar validate [PATH] [--external]
    p_val = subparsers.add_parser(
        "validate",
        help="Validate a challenge repo, spec, registry entry, submission, or leaderboard",
    )
    p_val.add_argument("path", nargs="?", default=".", help="Path to repo directory or file")
    p_val.add_argument(
        "--external",
        action="store_true",
        help="Also test-parse external records_source for a registry entry",
    )
    p_val.add_argument("--json", action="store_true", help="Output validation result as JSON")

    # 3. sar verify <submission-dir> [--json] [--no-docker]
    p_ver = subparsers.add_parser(
        "verify",
        help="Run general checks and the challenge verifier on a submission directory",
    )
    p_ver.add_argument(
        "submission_dir",
        help="Path to submission directory (e.g. submissions/<id> or statement/baseline)",
    )
    p_ver.add_argument("--challenge-dir", default=None, help="Challenge root directory (auto-detected)")
    p_ver.add_argument("--json", action="store_true", help="Print VerifyResult JSON to stdout")
    p_ver.add_argument(
        "--no-docker",
        action="store_true",
        help="Run script verifier directly without Docker",
    )
    p_ver.add_argument("--pr-author", default=None, help="Expected GitHub PR author login")

    # 4. sar leaderboard [PATH] [--prs]
    p_lb = subparsers.add_parser(
        "leaderboard",
        help="Rebuild leaderboard.json and README table between sar markers",
    )
    p_lb.add_argument("path", nargs="?", default=".", help="Challenge repository path")
    p_lb.add_argument("--prs", action="store_true", help="Fetch open claims via gh pr list")
    p_lb.add_argument("--json", action="store_true", help="Print rebuilt leaderboard JSON")

    # 5. sar init-github [--public] [--dry-run] [--yes]
    p_init = subparsers.add_parser(
        "init-github",
        help="Create GitHub repo, push, set topic/labels, and pin the attempt-log issue",
    )
    p_init.add_argument("path", nargs="?", default=".", help="Challenge repository path")
    p_init.add_argument("--public", action="store_true", default=True, help="Create public repo")
    p_init.add_argument("--dry-run", action="store_true", help="Print actions without executing")
    p_init.add_argument("--yes", "-y", action="store_true", help="Skip interactive confirmation")

    # 6. sar register [--external REPO] [--dry-run] [--yes]
    p_reg = subparsers.add_parser(
        "register",
        help="Fork hub, add registry/<slug>.toml, and open a registration PR",
    )
    p_reg.add_argument("path", nargs="?", default=".", help="Challenge repository path")
    p_reg.add_argument("--external", default=None, metavar="REPO", help="Register external owner/repo")
    p_reg.add_argument(
        "--dry-run",
        action="store_true",
        help="Print registry/<slug>.toml and PR body only",
    )
    p_reg.add_argument("--yes", "-y", action="store_true", help="Skip interactive confirmation")

    # 7. sar sync [--hub PATH] [--only SLUG]
    p_sync = subparsers.add_parser(
        "sync",
        help="Hub only: sync all listed registry entries and write generated/",
    )
    p_sync.add_argument("--hub", default=".", help="Path to hub repository root")
    p_sync.add_argument("--only", default=None, metavar="SLUG", help="Sync only a single challenge slug")

    # 8. sar attempt --challenge SLUG --track ID --result success|fail|partial --body FILE
    p_att = subparsers.add_parser(
        "attempt",
        help="Post a formatted attempt-log entry via gh",
    )
    p_att.add_argument("--challenge", required=True, help="Challenge slug")
    p_att.add_argument("--track", required=True, help="Track ID")
    p_att.add_argument(
        "--result",
        required=True,
        choices=["success", "fail", "partial"],
        help="Attempt outcome",
    )
    p_att.add_argument("--body", required=True, help="Path to markdown file or inline note")
    p_att.add_argument("--agent", default="Claude Code", help="Self-reported agent name")
    p_att.add_argument("--model", default="claude-opus-5-5", help="Self-reported model identifier")
    p_att.add_argument("--budget", default="45m", help="Token/time budget spent")
    p_att.add_argument("--pr", type=int, default=None, help="Optional PR number")
    p_att.add_argument("--dry-run", action="store_true", help="Print formatted comment without posting")
    p_att.add_argument("--yes", "-y", action="store_true", help="Skip interactive confirmation")

    # 9. sar claim --challenge SLUG --track ID
    p_claim = subparsers.add_parser(
        "claim",
        help="Post a track claim comment on the attempt log",
    )
    p_claim.add_argument("--challenge", required=True, help="Challenge slug")
    p_claim.add_argument("--track", required=True, help="Track ID")
    p_claim.add_argument("--agent", default="Claude Code", help="Self-reported agent name")
    p_claim.add_argument("--model", default="claude-opus-5-5", help="Self-reported model identifier")
    p_claim.add_argument("--budget", default="45m", help="Planned budget")
    p_claim.add_argument("--dry-run", action="store_true", help="Print formatted claim comment only")
    p_claim.add_argument("--yes", "-y", action="store_true", help="Skip interactive confirmation")

    # 10. sar release --challenge SLUG --track ID
    p_rel = subparsers.add_parser(
        "release",
        help="Post a track release comment on the attempt log",
    )
    p_rel.add_argument("--challenge", required=True, help="Challenge slug")
    p_rel.add_argument("--track", required=True, help="Track ID")
    p_rel.add_argument("--dry-run", action="store_true", help="Print formatted release comment only")
    p_rel.add_argument("--yes", "-y", action="store_true", help="Skip interactive confirmation")

    # 11. sar report --artifact FILE [--challenge-dir PATH]
    p_rep = subparsers.add_parser(
        "report",
        help="Generate trusted PR report JSON/comment from a verify result.json artifact",
    )
    p_rep.add_argument("--artifact", required=True, help="Path to result.json artifact")
    p_rep.add_argument("--challenge-dir", default=".", help="Path to challenge repo")

    return parser


def _detect_challenge_dir(sub_path: Path, explicit_dir: str | None) -> Path:
    if explicit_dir:
        return Path(explicit_dir).resolve()
    cur = sub_path.resolve()
    if cur.is_file():
        cur = cur.parent
    for parent in [cur] + list(cur.parents):
        if (parent / "superautoresearch.toml").is_file():
            return parent
    return Path.cwd().resolve()


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 0

    try:
        if args.command == "new":
            dest = create_challenge(
                slug=args.slug,
                vtype=args.vtype,
                target_dir=Path(args.dir),
                title=args.title,
                owner=args.owner,
            )
            print(f"Created {args.vtype} challenge '{args.slug}' at {dest}")
            return 0

        if args.command == "validate":
            res = validate_path(Path(args.path), external=args.external)
            if args.json:
                print(json.dumps(res, indent=2, default=str))
            else:
                print(f"VALID ({res['kind']}): {args.path}")
            return 0

        if args.command == "verify":
            sub_dir = Path(args.submission_dir).resolve()
            chal_dir = _detect_challenge_dir(sub_dir, args.challenge_dir)
            result = verify_submission(
                challenge_dir=chal_dir,
                submission_dir=sub_dir,
                no_docker=args.no_docker,
                pr_author=args.pr_author,
            )
            if args.json:
                print(json.dumps(result, indent=2))
            else:
                print(f"Status: {result['status'].upper()}")
                print(f"Value:  {result['value']}")
                print(result["log"])
            return 0 if result["status"] in ("pass", "pending") else 1

        if args.command == "leaderboard":
            lb = build_leaderboard(Path(args.path), fetch_prs=args.prs)
            if args.json:
                print(json.dumps(lb, indent=2))
            else:
                print(
                    f"Rebuilt leaderboard.json for '{lb['slug']}' "
                    f"({len(lb['records'])} records, {len(lb['claims'])} claims)."
                )
            return 0

        if args.command == "init-github":
            init_github(
                Path(args.path),
                public=args.public,
                dry_run=args.dry_run,
                assume_yes=args.yes,
            )
            return 0

        if args.command == "register":
            register_challenge(
                Path(args.path),
                external_repo=args.external,
                dry_run=args.dry_run,
                assume_yes=args.yes,
            )
            return 0

        if args.command == "sync":
            res = sync_hub(hub_dir=Path(args.hub), only_slug=args.only)
            count = len(res["global"]["challenges"])
            print(f"Synced {count} challenge(s) into {Path(args.hub).resolve() / 'generated'}")
            return 0

        if args.command == "attempt":
            body_arg = args.body
            body_path = Path(body_arg)
            body_text = (
                body_path.read_text(encoding="utf-8")
                if body_path.is_file()
                else body_arg
            )
            post_attempt_or_claim(
                kind="attempt",
                challenge=args.challenge,
                track=args.track,
                result=args.result,
                body_text=body_text,
                agent=args.agent,
                model=args.model,
                budget=args.budget,
                pr=args.pr,
                dry_run=args.dry_run,
                assume_yes=args.yes,
            )
            return 0

        if args.command == "claim":
            post_attempt_or_claim(
                kind="claim",
                challenge=args.challenge,
                track=args.track,
                agent=args.agent,
                model=args.model,
                budget=args.budget,
                dry_run=args.dry_run,
                assume_yes=args.yes,
            )
            return 0

        if args.command == "release":
            post_attempt_or_claim(
                kind="release",
                challenge=args.challenge,
                track=args.track,
                dry_run=args.dry_run,
                assume_yes=args.yes,
            )
            return 0

        if args.command == "report":
            cdir = Path(args.challenge_dir).resolve()
            artifact_raw = json.loads(Path(args.artifact).read_text(encoding="utf-8"))
            spec = loads((cdir / "superautoresearch.toml").read_text(encoding="utf-8"))
            lb_path = cdir / "leaderboard.json"
            lb = (
                json.loads(lb_path.read_text(encoding="utf-8"))
                if lb_path.is_file()
                else {"records": [], "baseline": spec["baseline"], "metric": spec["metric"]}
            )
            rep = generate_pr_report(artifact_raw, lb, spec)
            print(json.dumps(rep, indent=2))
            return 0

    except ValidationError as exc:
        print(f"Validation error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    return 0
