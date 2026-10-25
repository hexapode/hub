"""`sar new` implementation: scaffold a new challenge repository from templates."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from sar.config import HUB_REPO, SLUG_REGEX, get_hub_root
from sar.leaderboard import build_leaderboard
from sar.validate import ValidationError, compute_statement_hash

TEMPLATE_VERSION = "1"
TEXT_EXTENSIONS = {".toml", ".md", ".yml", ".yaml", ".py", ".lean", ".sh", ".json", ".txt", ""}


def _slug_to_title(slug: str) -> str:
    return " ".join(word.capitalize() for word in slug.split("-"))


def _render_placeholders(text: str, context: dict[str, str]) -> str:
    out = text
    for k, v in context.items():
        out = out.replace("{{" + k + "}}", v)
    return out


def _copy_and_render_tree(src_dir: Path, dst_dir: Path, context: dict[str, str]) -> None:
    for item in src_dir.rglob("*"):
        rel = item.relative_to(src_dir)
        target = dst_dir / rel
        if item.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        if item.suffix in TEXT_EXTENSIONS or item.name in ("CODEOWNERS", "lean-toolchain"):
            try:
                raw = item.read_text(encoding="utf-8")
                rendered = _render_placeholders(raw, context)
                target.write_text(rendered, encoding="utf-8")
                continue
            except UnicodeDecodeError:
                pass
        shutil.copy2(item, target)


def create_challenge(
    slug: str,
    vtype: str,
    target_dir: Path | None = None,
    title: str | None = None,
    owner: str = "alice",
    hub: str = HUB_REPO,
    hub_root: Path | None = None,
) -> Path:
    """Create a new challenge repository from `templates/_common` and `templates/<vtype>`."""
    if not re.match(SLUG_REGEX, slug):
        raise ValidationError(f"Invalid challenge slug {slug!r}; must match {SLUG_REGEX}")
    if vtype not in ("script", "lean", "manual"):
        raise ValidationError(f"Invalid template type {vtype!r}; must be script, lean, or manual")

    root = hub_root or get_hub_root()
    templates_dir = root / "templates"
    common_dir = templates_dir / "_common"
    type_dir = templates_dir / vtype

    if not common_dir.is_dir() or not type_dir.is_dir():
        raise FileNotFoundError(f"Templates not found in {templates_dir}")

    base_dir = (target_dir or Path.cwd()).resolve()
    dest = base_dir / slug
    if dest.exists() and any(dest.iterdir()):
        raise FileExistsError(f"Destination directory already exists and is not empty: {dest}")

    dest.mkdir(parents=True, exist_ok=True)

    context = {
        "slug": slug,
        "title": title or _slug_to_title(slug),
        "owner": owner,
        "hub": hub,
        "template_version": f"{vtype}@{TEMPLATE_VERSION}",
    }

    _copy_and_render_tree(common_dir, dest, context)
    _copy_and_render_tree(type_dir, dest, context)

    # Ensure required directories exist
    (dest / "submissions").mkdir(parents=True, exist_ok=True)
    (dest / "submissions" / ".gitkeep").write_text("", encoding="utf-8")
    (dest / "verifier").mkdir(parents=True, exist_ok=True)
    (dest / "statement").mkdir(parents=True, exist_ok=True)

    # Vendor `sar` package into `.sar/sar` so CI does not depend on hub
    sar_pkg_src = Path(__file__).resolve().parent
    vendor_dir = dest / ".sar" / "sar"
    if vendor_dir.exists():
        shutil.rmtree(vendor_dir)
    shutil.copytree(
        sar_pkg_src,
        vendor_dir,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )

    # Record initial statement_hash
    stmt_hash = compute_statement_hash(dest)
    (dest / ".sar" / "statement_hash").write_text(stmt_hash + "\n", encoding="utf-8")

    # Build initial leaderboard.json & README table
    build_leaderboard(dest, fetch_prs=False)

    # Initialize git repo
    try:
        subprocess.run(
            ["git", "init", "-q"],
            cwd=str(dest),
            capture_output=True,
            timeout=10,
            check=False,
        )
    except Exception:
        pass

    return dest
