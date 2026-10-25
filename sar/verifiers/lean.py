"""Lean 4 verifier backend (§5.2)."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from sar.verifiers import VerifyResult, parse_timeout_seconds

DEFAULT_ALLOWED_AXIOMS = ["propext", "Classical.choice", "Quot.sound"]


def is_lean_installed() -> bool:
    elan_bin = Path.home() / ".elan" / "bin"
    path_env = os.environ.get("PATH", "")
    if elan_bin.is_dir() and str(elan_bin) not in path_env:
        os.environ["PATH"] = f"{elan_bin}:{path_env}"
    return bool(shutil.which("lean") and shutil.which("lake"))


def _check_forbidden_redefinitions(submission_code: str) -> str | None:
    """Reject submissions that attempt to redefine Goal, Statement, or axioms."""
    stripped_lines = []
    in_block = False
    for line in submission_code.splitlines():
        s = line.strip()
        if s.startswith("/-"):
            in_block = True
        if not in_block and not s.startswith("--"):
            stripped_lines.append(s)
        if "-/" in s:
            in_block = False
    cleaned = "\n".join(stripped_lines)

    if re.search(r"\b(def|abbrev|theorem|lemma|axiom|opaque)\s+Goal\b", cleaned):
        return "Submission.lean must not redefine 'Goal'"
    if re.search(r"\bnamespace\s+Statement\b", cleaned):
        return "Submission.lean must not reopen or redefine 'namespace Statement'"
    if re.search(r"\baxiom\s+", cleaned):
        return "Submission.lean must not declare custom axioms"
    if re.search(r"\bsorry\b", cleaned):
        return "Submission.lean contains 'sorry'"
    return None


def _format_lean_literal(claimed: float | int, value_type: str) -> str:
    if value_type in ("Nat", "Int"):
        return str(int(claimed))
    return str(claimed)


def verify(
    challenge_dir: Path,
    submission_dir: Path,
    spec: dict[str, Any],
    claimed: float | None,
) -> VerifyResult:
    vcfg = spec["verifier"]
    allowed_axioms = set(vcfg.get("allowed_axioms", DEFAULT_ALLOWED_AXIOMS))
    theorem_name = vcfg.get("theorem_name", "Submission.main")
    value_type = vcfg.get("value_type", "Nat")
    timeout_sec = parse_timeout_seconds(vcfg.get("timeout", "30m"))

    sub_lean_path = submission_dir / "Submission.lean"
    if not sub_lean_path.is_file():
        return {
            "status": "fail",
            "value": None,
            "log": "Missing Submission.lean in submission directory.",
            "details": {},
        }

    sub_code = sub_lean_path.read_text(encoding="utf-8")
    redef_err = _check_forbidden_redefinitions(sub_code)
    if redef_err:
        return {
            "status": "fail",
            "value": None,
            "log": f"Lean static check failed: {redef_err}",
            "details": {"reason": redef_err},
        }

    if claimed is None:
        return {
            "status": "fail",
            "value": None,
            "log": "Missing 'claimed' bound in submission.toml.",
            "details": {},
        }

    literal = _format_lean_literal(claimed, value_type)
    check_lean_content = (
        "import Statement\n"
        "import Submission\n\n"
        f"theorem __sar_check : Statement.Goal ({literal}) := {theorem_name}\n"
        "#print axioms __sar_check\n"
    )

    if not is_lean_installed():
        return {
            "status": "error",
            "value": None,
            "log": "SKIP/ERROR: Lean 4 (lean/lake) is not installed on this machine.",
            "details": {
                "lean_installed": False,
                "generated_check_lean": check_lean_content,
            },
        }

    with tempfile.TemporaryDirectory(prefix="sar-lean-") as tmpdir:
        tmp_path = Path(tmpdir)
        stmt_dir = challenge_dir / "statement"
        for item in stmt_dir.iterdir():
            if item.name == "baseline":
                continue
            dest = tmp_path / item.name
            if item.is_dir():
                shutil.copytree(item, dest)
            else:
                shutil.copy2(item, dest)

        shutil.copy2(sub_lean_path, tmp_path / "Submission.lean")
        (tmp_path / "Check.lean").write_text(check_lean_content, encoding="utf-8")

        build_proc = subprocess.run(
            ["lake", "build"],
            cwd=str(tmp_path),
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            check=False,
        )
        if build_proc.returncode != 0:
            return {
                "status": "fail",
                "value": None,
                "log": f"lake build failed:\n{build_proc.stdout}\n{build_proc.stderr}",
                "details": {"exit_code": build_proc.returncode},
            }

        check_proc = subprocess.run(
            ["lake", "env", "lean", "Check.lean"],
            cwd=str(tmp_path),
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            check=False,
        )
        output = (check_proc.stdout or "") + "\n" + (check_proc.stderr or "")
        if check_proc.returncode != 0:
            return {
                "status": "fail",
                "value": None,
                "log": f"lake env lean Check.lean failed:\n{output.strip()}",
                "details": {"exit_code": check_proc.returncode},
            }

        # Parse printed axioms: `'__sar_check' depends on axioms: [propext, ...]`
        used_axioms: list[str] = []
        m = re.search(r"depends on axioms:\s*\[([^\]]*)\]", output)
        if m:
            used_axioms = [a.strip() for a in m.group(1).split(",") if a.strip()]

        disallowed = [a for a in used_axioms if a not in allowed_axioms]
        if disallowed:
            return {
                "status": "fail",
                "value": None,
                "log": f"Proof uses disallowed axioms: {disallowed}\nFull output:\n{output.strip()}",
                "details": {"used_axioms": used_axioms, "disallowed_axioms": disallowed},
            }

        return {
            "status": "pass",
            "value": float(claimed),
            "log": f"Lean proof verified for Goal ({literal}).\nAxioms used: {used_axioms}\n{output.strip()}",
            "details": {"used_axioms": used_axioms, "claimed": claimed},
        }
