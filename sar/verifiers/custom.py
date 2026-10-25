"""Custom verifier backend (§5.4)."""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from sar.verifiers import VerifyResult, parse_timeout_seconds
from sar.verifiers.script import _rewrite_local_command


def verify(
    challenge_dir: Path,
    submission_dir: Path,
    spec: dict[str, Any],
    claimed: float | None,
) -> VerifyResult:
    vcfg = spec["verifier"]
    command = vcfg["command"]
    timeout_sec = parse_timeout_seconds(vcfg.get("timeout", "30m"))
    local_cmd = _rewrite_local_command(command, challenge_dir, submission_dir)

    with tempfile.TemporaryDirectory(prefix="sar-custom-") as tmpdir:
        proc = subprocess.run(
            local_cmd,
            shell=True,
            cwd=tmpdir,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            check=False,
        )
        output = ((proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")).strip()
        if proc.returncode != 0:
            return {
                "status": "fail",
                "value": None,
                "log": f"Custom verifier failed (exit {proc.returncode}):\n{output}",
                "details": {"exit_code": proc.returncode},
            }

        lines = [ln.strip() for ln in (proc.stdout or "").splitlines() if ln.strip()]
        if not lines:
            return {
                "status": "fail",
                "value": None,
                "log": "Custom verifier produced no JSON output on stdout.",
                "details": {},
            }
        try:
            payload = json.loads(lines[-1])
        except Exception as exc:
            return {
                "status": "fail",
                "value": None,
                "log": f"Invalid JSON on final stdout line: {exc}\n{output}",
                "details": {},
            }

        if payload.get("valid") is False:
            return {
                "status": "fail",
                "value": None,
                "log": f"Submission invalid: {payload.get('reason', 'unspecified')}",
                "details": payload,
            }

        val = float(payload["value"])
        return {
            "status": "pass",
            "value": val,
            "log": output,
            "details": {"measured": val, "claimed": claimed},
        }
