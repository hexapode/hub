"""Central configuration constants for superAutoResearch."""

from pathlib import Path

HUB_REPO = "superautoresearch/hub"
HUB_ORG = HUB_REPO.split("/")[0]
DEFAULT_CLAIM_EXPIRY_HOURS = 24
SLUG_REGEX = r"^[a-z0-9][a-z0-9-]{1,48}$"
MODEL_REGEX = r"^[A-Za-z0-9 ._-]{1,40}$"


def get_hub_root() -> Path:
    """Locate the hub root directory if running from inside the hub."""
    here = Path(__file__).resolve().parent.parent
    if (here / "registry").is_dir() and (here / "templates").is_dir():
        return here
    return Path.cwd()
