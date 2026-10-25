"""Hub sync, external README table parser, and attempt-log parser (§8.2, §8.3)."""

from __future__ import annotations

import datetime
import json
import re
import urllib.request
from pathlib import Path
from typing import Any

from sar.config import DEFAULT_CLAIM_EXPIRY_HOURS, HUB_REPO, get_hub_root
from sar.leaderboard import is_improvement
from sar.toml_compat import TOMLDecodeError, loads
from sar.validate import (
    ValidationError,
    compute_statement_hash,
    validate_leaderboard_dict,
    validate_registry_dict,
    validate_spec_dict,
)

MAX_FETCH_BYTES = 5 * 1024 * 1024  # 5 MB safety limit (§13)


def _parse_iso_datetime(dt_str: str) -> datetime.datetime:
    s = str(dt_str).strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        return dt
    except Exception:
        return datetime.datetime.now(datetime.timezone.utc)


def parse_sar_comment_block(body: str) -> dict[str, Any] | None:
    """Extract and parse a fenced ```sar ... ``` TOML block from a comment body."""
    m = re.search(r"```sar\s*\n(.*?)\n```", body, flags=re.DOTALL)
    if not m:
        return None
    toml_text = m.group(1)
    try:
        data = loads(toml_text)
    except TOMLDecodeError:
        return None
    if not isinstance(data, dict) or data.get("kind") not in ("attempt", "claim", "release"):
        return None
    return data


def format_sar_comment_block(
    kind: str,
    track: str,
    body_text: str = "",
    result: str | None = None,
    agent: str | None = None,
    model: str | None = None,
    budget: str | None = None,
    pr: int | None = None,
) -> str:
    """Format an attempt-log comment with a fenced ```sar TOML header (§8.3)."""
    header_lines = [
        f'kind   = "{kind}"',
        f'track  = "{track}"',
    ]
    if kind == "attempt" and result:
        header_lines.append(f'result = "{result}"')
    if agent:
        header_lines.append(f'agent  = "{agent}"')
    if model:
        header_lines.append(f'model  = "{model}"')
    if budget:
        header_lines.append(f'budget = "{budget}"')
    if pr is not None:
        header_lines.append(f"pr     = {int(pr)}")

    fence = "```sar\n" + "\n".join(header_lines) + "\n```"
    if body_text.strip():
        return fence + "\n" + body_text.strip() + "\n"
    return fence + "\n"


def analyze_attempt_log(
    comments: list[dict[str, Any]],
    tracks: list[dict[str, Any]],
    now: datetime.datetime | None = None,
    expiry_hours: int = DEFAULT_CLAIM_EXPIRY_HOURS,
) -> dict[str, Any]:
    """Parse attempt-log comments and compute attempts count, contributors, and open_tracks.

    Each item in `comments` has `{"author": str, "created_at": str, "body": str}`.
    """
    ref_now = now or datetime.datetime.now(datetime.timezone.utc)
    expiry_delta = datetime.timedelta(hours=expiry_hours)

    attempts_count = 0
    contributors: set[str] = set()
    parsed_events: list[dict[str, Any]] = []

    # Track claim state: track_id -> latest claim event dict
    active_claims: dict[str, dict[str, Any]] = {}

    # Sort comments chronologically
    sorted_comments = sorted(
        comments, key=lambda c: _parse_iso_datetime(str(c.get("created_at", "")))
    )

    for c in sorted_comments:
        body = str(c.get("body", ""))
        header = parse_sar_comment_block(body)
        if not header:
            continue
        author = str(c.get("author", "anonymous"))
        created_dt = _parse_iso_datetime(str(c.get("created_at", ref_now.isoformat())))
        kind = header["kind"]
        track_id = str(header.get("track", ""))

        contributors.add(author)
        event = {
            **header,
            "author": author,
            "created_at": created_dt.isoformat(),
        }
        parsed_events.append(event)

        if kind == "attempt":
            attempts_count += 1
            # An attempt from the same user releases their claim on that track
            existing = active_claims.get(track_id)
            if existing and existing["author"] == author:
                del active_claims[track_id]
        elif kind == "release":
            existing = active_claims.get(track_id)
            if existing and existing["author"] == author:
                del active_claims[track_id]
        elif kind == "claim" and track_id:
            active_claims[track_id] = {
                "track": track_id,
                "author": author,
                "agent": header.get("agent"),
                "model": header.get("model"),
                "claimed_at": created_dt.isoformat(),
                "_dt": created_dt,
            }

    # Filter out claims older than 24h
    valid_claims: dict[str, dict[str, Any]] = {}
    for tid, cl in active_claims.items():
        if ref_now - cl["_dt"] <= expiry_delta:
            clean_cl = {k: v for k, v in cl.items() if k != "_dt"}
            valid_claims[tid] = clean_cl

    open_tracks = [t for t in tracks if t.get("id") not in valid_claims]

    return {
        "attempts": attempts_count,
        "contributors": sorted(contributors),
        "active_claims": list(valid_claims.values()),
        "open_tracks": open_tracks,
        "events": parsed_events,
    }


def _fetch_text_resource(url_or_path: str, base_dir: Path | None = None) -> str:
    if url_or_path.startswith("file://"):
        fpath = Path(url_or_path[len("file://") :])
        if not fpath.is_absolute() and base_dir:
            fpath = (base_dir / fpath).resolve()
        data = fpath.read_bytes()
        if len(data) > MAX_FETCH_BYTES:
            raise ValueError("Resource exceeds maximum allowed size")
        return data.decode("utf-8")

    if not url_or_path.startswith(("http://", "https://")):
        fpath = Path(url_or_path)
        if not fpath.is_absolute() and base_dir:
            fpath = (base_dir / fpath).resolve()
        data = fpath.read_bytes()
        if len(data) > MAX_FETCH_BYTES:
            raise ValueError("Resource exceeds maximum allowed size")
        return data.decode("utf-8")

    req = urllib.request.Request(
        url_or_path,
        headers={"User-Agent": "superautoresearch-sync/0.1"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = resp.read(MAX_FETCH_BYTES + 1)
        if len(data) > MAX_FETCH_BYTES:
            raise ValueError("Remote resource exceeds maximum allowed size")
        return data.decode("utf-8")


def _extract_number(cell_text: str) -> float | None:
    cleaned = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", cell_text)
    cleaned = cleaned.replace("*", "").replace("`", "").strip()
    m = re.search(r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?", cleaned)
    if not m:
        return None
    try:
        return float(m.group(0))
    except ValueError:
        return None


def _extract_link(cell_text: str) -> str | None:
    m = re.search(r"\((https?://[^)\s]+)\)", cell_text)
    return m.group(1) if m else None


def parse_readme_table_records(
    markdown_text: str,
    table_heading: str | None,
    columns: dict[str, str],
    direction: str = "min",
    baseline_val: float | None = None,
) -> list[dict[str, Any]]:
    """Parse a Markdown table from a README into leaderboard record objects."""
    lines = markdown_text.splitlines()
    start_idx = 0
    if table_heading:
        heading_lower = table_heading.strip().lower()
        for idx, ln in enumerate(lines):
            if ln.strip().startswith("#") and heading_lower in ln.strip().lower():
                start_idx = idx + 1
                break

    # Find first markdown table starting at or after start_idx
    header_cells: list[str] = []
    row_start = -1
    for idx in range(start_idx, len(lines) - 1):
        ln = lines[idx].strip()
        next_ln = lines[idx + 1].strip()
        if "|" in ln and "|" in next_ln and re.search(r"\|[\s:-]+\|", next_ln):
            header_cells = [c.strip() for c in ln.strip("|").split("|")]
            row_start = idx + 2
            break

    if not header_cells or row_start < 0:
        raise ValueError(f"Could not find Markdown table (heading={table_heading!r})")

    col_map: dict[str, int] = {}
    for role, col_name in columns.items():
        target = col_name.strip().lower()
        for c_idx, h_name in enumerate(header_cells):
            if target == h_name.lower() or target in h_name.lower():
                col_map[role] = c_idx
                break

    if "value" not in col_map:
        raise ValueError(f"Value column {columns.get('value')!r} not found in {header_cells}")

    raw_rows: list[dict[str, Any]] = []
    for idx in range(row_start, len(lines)):
        ln = lines[idx].strip()
        if not ln.startswith("|") and "|" not in ln:
            if raw_rows:
                break
            continue
        cells = [c.strip() for c in ln.strip("|").split("|")]
        if len(cells) <= col_map["value"]:
            continue

        val = _extract_number(cells[col_map["value"]])
        if val is None:
            continue

        author_raw = (
            cells[col_map["author"]]
            if "author" in col_map and col_map["author"] < len(cells)
            else "contributor"
        )
        author_clean = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", author_raw).lstrip("@").strip()
        author_clean = re.split(r"[,/& ]+", author_clean)[0] or "contributor"

        date_raw = (
            cells[col_map["date"]]
            if "date" in col_map and col_map["date"] < len(cells)
            else "2026-01-01"
        )
        link_cell = (
            cells[col_map["link"]]
            if "link" in col_map and col_map["link"] < len(cells)
            else ""
        )
        url = _extract_link(link_cell) or _extract_link(cells[col_map["value"]]) or ""

        rec_id = f"{author_clean.lower()}-{len(raw_rows) + 1}"
        rec: dict[str, Any] = {
            "id": rec_id,
            "value": val,
            "evidence": "verified",
            "author": author_clean,
            "date": date_raw.strip(),
        }
        if url:
            rec["url"] = url
        raw_rows.append(rec)

    # Filter to strictly improving records if baseline_val is provided
    if baseline_val is not None and raw_rows:
        filtered: list[dict[str, Any]] = []
        best = float(baseline_val)
        for r in raw_rows:
            if is_improvement(r["value"], best, direction):
                best = r["value"]
                filtered.append(r)
        return filtered if filtered else raw_rows

    return raw_rows


def parse_external_records(
    entry: dict[str, Any],
    hub_dir: Path | None = None,
    slug: str | None = None,
) -> list[dict[str, Any]]:
    """Parse records for an external challenge entry."""
    spec = entry["spec"]
    rsrc = spec["records_source"]
    stype = rsrc["type"]
    direction = spec["metric"]["direction"]
    baseline_val = float(spec["baseline"]["value"])

    if stype == "readme-table":
        url = rsrc.get("url")
        if not url:
            raise ValueError("readme-table records_source requires 'url'")
        md_text = _fetch_text_resource(url, base_dir=hub_dir)
        return parse_readme_table_records(
            md_text,
            table_heading=rsrc.get("table_heading"),
            columns=rsrc.get("columns", {"value": "Record", "date": "Date", "author": "Author"}),
            direction=direction,
            baseline_val=baseline_val,
        )

    if stype == "leaderboard-json":
        url = rsrc.get("url")
        if not url:
            raise ValueError("leaderboard-json records_source requires 'url'")
        raw_json = _fetch_text_resource(url, base_dir=hub_dir)
        lb = json.loads(raw_json)
        validate_leaderboard_dict(lb)
        return lb.get("records", [])

    if stype == "hub":
        if not hub_dir or not slug:
            return []
        rec_file = hub_dir / "registry" / f"{slug}.records.toml"
        if not rec_file.is_file():
            return []
        parsed = loads(rec_file.read_text(encoding="utf-8"))
        return parsed.get("records", [])

    raise ValueError(f"Unsupported records_source.type: {stype}")


def _resolve_local_repo_path(entry: dict[str, Any], hub_dir: Path) -> Path | None:
    if entry.get("local_path"):
        p = Path(entry["local_path"])
        return p if p.is_absolute() else (hub_dir / p).resolve()
    repo = str(entry.get("repo", ""))
    if repo.startswith("file://"):
        p = Path(repo[len("file://") :])
        return p if p.is_absolute() else (hub_dir / p).resolve()
    return None


def _compute_best_claim(
    claims: list[dict[str, Any]],
    current_best_val: float,
    direction: str,
) -> dict[str, Any] | None:
    best_cl: dict[str, Any] | None = None
    best_val = current_best_val
    for cl in claims:
        val = cl.get("value")
        if val is None:
            continue
        fval = float(val)
        if is_improvement(fval, best_val, direction):
            best_val = fval
            best_cl = cl
    return best_cl


def sync_single_challenge(
    slug: str,
    entry: dict[str, Any],
    hub_dir: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any] | None]:
    """Sync one registry entry and return (index_item, global_row, challenge_leaderboard)."""
    kind = entry.get("kind", "native")
    repo = str(entry["repo"])
    ref = str(entry.get("ref", "main"))
    repo_url = repo if repo.startswith(("http://", "https://", "file://")) else f"https://github.com/{repo}"
    tags = entry.get("tags", [])
    owners = entry.get("owners", [])
    status = "ok"

    now_iso = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    try:
        validate_registry_dict(entry, slug=slug)
    except ValidationError as exc:
        return (
            {"slug": slug, "repo": repo, "kind": kind, "status": "invalid", "error": str(exc)},
            {
                "slug": slug,
                "title": slug,
                "kind": kind,
                "repo": repo,
                "repo_url": repo_url,
                "tags": tags,
                "verifier_type": "script",
                "metric": {"name": "value", "unit": "", "direction": "min", "scale": "linear"},
                "baseline": {"value": 0.0, "label": "Baseline"},
                "first_record": None,
                "current_best": None,
                "best_claim": None,
                "records_count": 0,
                "contributors": 0,
                "attempts": 0,
                "last_improved": None,
                "status": "invalid",
            },
            None,
        )

    if kind == "native":
        local_repo = _resolve_local_repo_path(entry, hub_dir)
        spec: dict[str, Any] | None = None
        lb: dict[str, Any] | None = None
        comments: list[dict[str, Any]] = []

        if local_repo is not None:
            if not local_repo.is_dir():
                status = "unreachable"
            else:
                try:
                    spec_path = local_repo / "superautoresearch.toml"
                    lb_path = local_repo / "leaderboard.json"
                    spec = loads(spec_path.read_text(encoding="utf-8"))
                    validate_spec_dict(spec)
                    if lb_path.is_file():
                        lb = json.loads(lb_path.read_text(encoding="utf-8"))
                        validate_leaderboard_dict(lb)
                    else:
                        from sar.leaderboard import build_leaderboard

                        lb = build_leaderboard(local_repo, fetch_prs=False)

                    # Check statement_hash
                    expected_hash = entry.get("statement_hash")
                    actual_hash = compute_statement_hash(local_repo)
                    if expected_hash and expected_hash != actual_hash:
                        status = "statement-changed"

                    # Optional local attempt-log fixture: attempt_log.json
                    alog_fixture = local_repo / "attempt_log.json"
                    if alog_fixture.is_file():
                        comments = json.loads(alog_fixture.read_text(encoding="utf-8"))
                except (TOMLDecodeError, ValidationError, KeyError, ValueError) as exc:
                    status = "invalid"
                    return (
                        {"slug": slug, "repo": repo, "kind": kind, "status": "invalid", "error": str(exc)},
                        {
                            "slug": slug,
                            "title": slug,
                            "kind": kind,
                            "repo": repo,
                            "repo_url": repo_url,
                            "tags": tags,
                            "verifier_type": "script",
                            "metric": {"name": "value", "unit": "", "direction": "min", "scale": "linear"},
                            "baseline": {"value": 0.0, "label": "Baseline"},
                            "first_record": None,
                            "current_best": None,
                            "best_claim": None,
                            "records_count": 0,
                            "contributors": 0,
                            "attempts": 0,
                            "last_improved": None,
                            "status": "invalid",
                        },
                        None,
                    )
        else:
            # Try cached challenge JSON in hub/generated/challenges/<slug>.json if offline or remote
            cached_lb_path = hub_dir / "generated" / "challenges" / f"{slug}.json"
            raw_base = f"https://raw.githubusercontent.com/{repo}/{ref}"
            try:
                spec_txt = _fetch_text_resource(f"{raw_base}/superautoresearch.toml")
                lb_txt = _fetch_text_resource(f"{raw_base}/leaderboard.json")
                spec = loads(spec_txt)
                validate_spec_dict(spec)
                lb = json.loads(lb_txt)
                validate_leaderboard_dict(lb)
            except Exception:
                if cached_lb_path.is_file():
                    lb = json.loads(cached_lb_path.read_text(encoding="utf-8"))
                    spec = {
                        "schema": 1,
                        "slug": slug,
                        "title": lb.get("title", slug),
                        "summary": lb.get("summary", ""),
                        "owners": owners,
                        "tags": tags,
                        "metric": lb["metric"],
                        "baseline": lb["baseline"],
                        "verifier": lb.get("verifier", {"type": "script", "runner": "ubuntu-latest"}),
                        "submission": {"required_files": ["solution.py"], "max_size_mb": 20},
                        "tracks": lb.get("tracks", []),
                        "attempt_log": {"issue": lb.get("attempt_log_issue", 1)},
                    }
                else:
                    status = "unreachable"

        if status == "unreachable" or spec is None or lb is None:
            return (
                {"slug": slug, "repo": repo, "kind": kind, "status": status},
                {
                    "slug": slug,
                    "title": slug,
                    "kind": kind,
                    "repo": repo,
                    "repo_url": repo_url,
                    "tags": tags,
                    "verifier_type": "script",
                    "metric": {"name": "value", "unit": "", "direction": "min", "scale": "linear"},
                    "baseline": {"value": 0.0, "label": "Baseline"},
                    "first_record": None,
                    "current_best": None,
                    "best_claim": None,
                    "records_count": 0,
                    "contributors": 0,
                    "attempts": 0,
                    "last_improved": None,
                    "status": status,
                },
                None,
            )

        tracks = spec.get("tracks", [])
        alog_analysis = analyze_attempt_log(comments, tracks)
        records = lb.get("records", [])
        claims = lb.get("claims", [])
        metric = spec["metric"]
        baseline = spec["baseline"]
        vtype = spec["verifier"]["type"]
        issue_num = spec.get("attempt_log", {}).get("issue", 1)

        first_record = records[0] if records else None
        current_best = records[-1] if records else None
        best_val = float(current_best["value"]) if current_best else float(baseline["value"])
        best_claim = _compute_best_claim(claims, best_val, metric["direction"])

        total_attempts = max(int(lb.get("attempts", 0)), alog_analysis["attempts"], len(records))
        total_contributors = max(
            int(lb.get("contributors", 0)),
            len({r["author"] for r in records} | set(alog_analysis["contributors"])),
        )

        index_item = {
            "slug": slug,
            "kind": "native",
            "repo": repo,
            "ref": ref,
            "owners": owners,
            "tags": tags or spec.get("tags", []),
            "title": spec["title"],
            "summary": spec["summary"],
            "metric": metric,
            "baseline": baseline,
            "verifier": spec["verifier"],
            "tracks": tracks,
            "open_tracks": alog_analysis["open_tracks"],
            "active_claims": alog_analysis["active_claims"],
            "repo_url": repo_url,
            "agents_md_url": f"{repo_url}/blob/{ref}/AGENTS.md",
            "attempt_log_url": f"{repo_url}/issues/{issue_num}",
            "status": status,
        }

        global_row = {
            "slug": slug,
            "title": spec["title"],
            "summary": spec["summary"],
            "kind": "native",
            "repo": repo,
            "repo_url": repo_url,
            "tags": tags or spec.get("tags", []),
            "verifier_type": vtype,
            "metric": metric,
            "baseline": baseline,
            "first_record": first_record,
            "current_best": current_best,
            "best_claim": best_claim,
            "records_count": len(records),
            "contributors": total_contributors,
            "attempts": total_attempts,
            "last_improved": current_best["date"] if current_best else None,
            "status": status,
        }

        return index_item, global_row, lb

    # External challenge
    ext_spec = entry["spec"]
    metric = ext_spec["metric"]
    baseline = ext_spec["baseline"]
    vtype = ext_spec["verifier"]["type"]
    tracks = ext_spec.get("tracks", [])

    try:
        records = parse_external_records(entry, hub_dir=hub_dir, slug=slug)
    except Exception:
        status = "unreachable"
        records = []

    first_record = records[0] if records else None
    current_best = records[-1] if records else None

    contributors_count = entry.get(
        "contributors_override", len({r["author"] for r in records})
    )
    attempts_count = entry.get("attempts_override", max(len(records) * 3, len(records)))

    lb_external: dict[str, Any] = {
        "schema": 1,
        "slug": slug,
        "metric": metric,
        "baseline": baseline,
        "records": records,
        "claims": [],
        "contributors": contributors_count,
        "attempts": attempts_count,
        "updated": now_iso,
    }

    discussion_url = entry.get(
        "discussion_url", f"https://github.com/{HUB_REPO}/discussions"
    )

    index_item = {
        "slug": slug,
        "kind": "external",
        "repo": repo,
        "owners": owners,
        "tags": tags,
        "title": ext_spec["title"],
        "summary": ext_spec["summary"],
        "metric": metric,
        "baseline": baseline,
        "verifier": ext_spec["verifier"],
        "submit": ext_spec.get("submit", ""),
        "rules_url": ext_spec.get("rules_url", repo_url),
        "tracks": tracks,
        "open_tracks": tracks,
        "active_claims": [],
        "repo_url": repo_url,
        "agents_md_url": ext_spec.get("rules_url", f"{repo_url}#readme"),
        "attempt_log_url": discussion_url,
        "status": status,
    }

    global_row = {
        "slug": slug,
        "title": ext_spec["title"],
        "summary": ext_spec["summary"],
        "kind": "external",
        "repo": repo,
        "repo_url": repo_url,
        "tags": tags,
        "verifier_type": vtype,
        "metric": metric,
        "baseline": baseline,
        "first_record": first_record,
        "current_best": current_best,
        "best_claim": None,
        "records_count": len(records),
        "contributors": contributors_count,
        "attempts": attempts_count,
        "last_improved": current_best["date"] if current_best else None,
        "status": status,
    }

    return index_item, global_row, lb_external


def sync_hub(hub_dir: Path | None = None, only_slug: str | None = None) -> dict[str, Any]:
    """Run the hub sync across all listed `registry/*.toml` files and write `generated/`."""
    root = (hub_dir or get_hub_root()).resolve()
    registry_dir = root / "registry"
    generated_dir = root / "generated"
    challenges_dir = generated_dir / "challenges"
    challenges_dir.mkdir(parents=True, exist_ok=True)

    index_entries: list[dict[str, Any]] = []
    global_rows: list[dict[str, Any]] = []

    toml_files = sorted(registry_dir.glob("*.toml"))
    for tf in toml_files:
        if tf.name.endswith(".records.toml"):
            continue
        slug = tf.stem
        if only_slug and slug != only_slug:
            continue

        try:
            entry = loads(tf.read_text(encoding="utf-8"))
        except TOMLDecodeError:
            global_rows.append(
                {
                    "slug": slug,
                    "title": slug,
                    "kind": "native",
                    "repo": "",
                    "repo_url": "",
                    "tags": [],
                    "verifier_type": "script",
                    "metric": {"name": "value", "unit": "", "direction": "min", "scale": "linear"},
                    "baseline": {"value": 0.0, "label": "Baseline"},
                    "first_record": None,
                    "current_best": None,
                    "best_claim": None,
                    "records_count": 0,
                    "contributors": 0,
                    "attempts": 0,
                    "last_improved": None,
                    "status": "invalid",
                }
            )
            continue

        if entry.get("listed", True) is False:
            continue

        idx_item, gl_row, lb_data = sync_single_challenge(slug, entry, root)
        index_entries.append(idx_item)
        global_rows.append(gl_row)
        if lb_data is not None:
            target_challenge_file = challenges_dir / f"{slug}.json"
            if target_challenge_file.is_file():
                try:
                    prev = json.loads(target_challenge_file.read_text(encoding="utf-8"))
                    for k in ("title", "summary", "verifier", "tracks"):
                        if k in prev and k not in lb_data:
                            lb_data[k] = prev[k]
                except Exception:
                    pass
            target_challenge_file.write_text(
                json.dumps(lb_data, indent=2, default=str) + "\n", encoding="utf-8"
            )

    now_iso = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    index_payload = {
        "schema": 1,
        "hub": HUB_REPO,
        "updated": now_iso,
        "challenges": index_entries,
    }
    global_payload = {
        "schema": 1,
        "hub": HUB_REPO,
        "updated": now_iso,
        "challenges": global_rows,
    }

    (generated_dir / "index.json").write_text(
        json.dumps(index_payload, indent=2, default=str) + "\n", encoding="utf-8"
    )
    (generated_dir / "global.json").write_text(
        json.dumps(global_payload, indent=2, default=str) + "\n", encoding="utf-8"
    )

    return {"index": index_payload, "global": global_payload}
