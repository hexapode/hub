#!/usr/bin/env bash
# Milestone 8: End-to-end dry run (§14.8)
# 1. Create a script challenge in a temp dir
# 2. Verify the baseline
# 3. Add a better submission & verify it
# 4. Rebuild the leaderboard
# 5. Run `sar register --dry-run`
# 6. Add the generated entry to a temp hub & run `sar sync`
# 7. Assert the new challenge's row appears in `global.json` with the new record as current_best

set -euo pipefail

HUB_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="${HUB_ROOT}:${PYTHONPATH:-}"
export SAR_SORT_N=25000

SAR_BIN="python3 -m sar"
if command -v sar >/dev/null 2>&1; then
  SAR_BIN="sar"
fi

TMP_WORK="$(mktemp -d -t sar-e2e-XXXXXX)"
trap 'rm -rf "$TMP_WORK"' EXIT

echo "[1/7] Creating script challenge 'fast-radix-sort' in $TMP_WORK..."
$SAR_BIN new fast-radix-sort --type script --dir "$TMP_WORK" --title "Fast Radix Sort" --owner alice
CHAL_DIR="$TMP_WORK/fast-radix-sort"

echo "[2/7] Validating challenge and verifying baseline..."
$SAR_BIN validate "$CHAL_DIR"
$SAR_BIN verify "$CHAL_DIR/statement/baseline" --no-docker --json > "$TMP_WORK/baseline_res.json"

echo "[3/7] Adding improved submission 'submissions/alice-timsort-fast'..."
SUB_DIR="$CHAL_DIR/submissions/alice-timsort-fast"
mkdir -p "$SUB_DIR"

cat << 'EOF' > "$SUB_DIR/submission.toml"
schema      = 1
title       = "Optimized C-backed Timsort wrapper"
author      = "alice"
claimed     = 0.005
track       = "radix-sort"
agent       = "Claude Code"
model       = "claude-opus-5-5"
description = """
Replaces manual bottom-up merge loops with direct list.sort() pass.
"""
EOF

cat << 'EOF' > "$SUB_DIR/solution.py"
def sort_integers(data: list[int]) -> list[int]:
    out = list(data)
    out.sort()
    return out
EOF

$SAR_BIN verify "$SUB_DIR" --no-docker --json > "$SUB_DIR/.result.json"

echo "[4/7] Rebuilding challenge leaderboard..."
$SAR_BIN leaderboard "$CHAL_DIR"

echo "[5/7] Running sar register --dry-run..."
$SAR_BIN register "$CHAL_DIR" --dry-run > "$TMP_WORK/register_preview.txt"
grep -q 'repo = "alice/fast-radix-sort"' "$TMP_WORK/register_preview.txt"

echo "[6/7] Setting up temporary hub and running sar sync..."
TEMP_HUB="$TMP_WORK/temp-hub"
mkdir -p "$TEMP_HUB/registry" "$TEMP_HUB/generated"

python3 - "$CHAL_DIR" "$TEMP_HUB/registry/fast-radix-sort.toml" << 'PY'
import sys
from pathlib import Path
from sar.github_ops import build_registration_payload
from sar.toml_compat import dumps

chal_dir = Path(sys.argv[1])
out_toml = Path(sys.argv[2])
payload = build_registration_payload(chal_dir)
entry = payload["entry"]
entry["local_path"] = str(chal_dir)
out_toml.write_text(dumps(entry), encoding="utf-8")
PY

$SAR_BIN sync --hub "$TEMP_HUB"

echo "[7/7] Asserting 'fast-radix-sort' row in global.json has 'alice-timsort-fast' as current_best..."
python3 - "$TEMP_HUB/generated/global.json" << 'PY'
import json, sys

global_data = json.loads(open(sys.argv[1], encoding="utf-8").read())
rows = [r for r in global_data["challenges"] if r["slug"] == "fast-radix-sort"]
assert len(rows) == 1, f"Expected 1 row for fast-radix-sort, got {len(rows)}"
row = rows[0]
assert row["status"] == "ok", f"Expected status='ok', got {row['status']}"
assert row["current_best"] is not None, "Expected non-null current_best"
assert row["current_best"]["id"] == "alice-timsort-fast", f"Unexpected current_best: {row['current_best']}"
assert row["current_best"]["value"] < row["baseline"]["value"], "Expected record to beat baseline"
print(f"SUCCESS: E2E verified! Current best: {row['current_best']['id']} ({row['current_best']['value']}s vs baseline {row['baseline']['value']}s)")
PY
