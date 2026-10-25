"""Script verifier backend (§5.1)."""

from __future__ import annotations

import json
import shutil
import statistics
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from sar.verifiers import VerifyResult, parse_timeout_seconds


def _aggregate_values(values: list[float], mode: str) -> float:
    if mode == "mean":
        return float(statistics.mean(values))
    if mode == "min":
        return float(min(values))
    if mode == "max":
        return float(max(values))
    return float(statistics.median(values))


def _docker_available() -> bool:
    if not shutil.which("docker"):
        return False
    try:
        res = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        return res.returncode == 0
    except Exception:
        return False


def _rewrite_local_command(cmd: str, challenge_dir: Path, submission_dir: Path) -> str:
    rewritten = cmd.replace("/submission", str(submission_dir)).replace(
        "/challenge", str(challenge_dir)
    )
    for rel_prefix in ("verifier/", "statement/"):
        rewritten = rewritten.replace(f" {rel_prefix}", f" {challenge_dir}/{rel_prefix}")
        if rewritten.startswith(rel_prefix):
            rewritten = f"{challenge_dir}/{rewritten}"
    if rewritten.startswith("python "):
        rewritten = f"{sys.executable} " + rewritten[len("python ") :]
    elif rewritten.startswith("python3 "):
        rewritten = f"{sys.executable} " + rewritten[len("python3 ") :]
    return rewritten


def verify(
    challenge_dir: Path,
    submission_dir: Path,
    spec: dict[str, Any],
    claimed: float | None,
    no_docker: bool = False,
) -> VerifyResult:
    vcfg = spec["verifier"]
    command = vcfg["command"]
    repeats = int(vcfg.get("repeats", 3))
    aggregate_mode = vcfg.get("aggregate", "median")
    tolerance = float(vcfg.get("tolerance", 0.0))
    timeout_sec = parse_timeout_seconds(vcfg.get("timeout", "30m"))
    image = vcfg.get("image", "python:3.12-slim")
    network = bool(vcfg.get("network", False))

    use_docker = (not no_docker) and _docker_available()
    logs: list[str] = []
    if not use_docker:
        logs.append(
            "WARNING: Running script verifier directly without Docker (--no-docker or Docker unavailable)."
        )

    measured_values: list[float] = []

    for run_idx in range(1, repeats + 1):
        with tempfile.TemporaryDirectory(prefix=f"sar-script-{run_idx}-") as tmpdir:
            if use_docker:
                net_flag = "bridge" if network else "none"
                exec_cmd = [
                    "docker",
                    "run",
                    "--rm",
                    f"--network={net_flag}",
                    "--cpus=2",
                    "--memory=2g",
                    "-v",
                    f"{challenge_dir}:/challenge:ro",
                    "-v",
                    f"{submission_dir}:/submission:ro",
                    "-w",
                    "/tmp",
                    image,
                    "sh",
                    "-c",
                    f"cp -r /challenge/verifier /tmp/verifier 2>/dev/null || true; "
                    f"cp -r /challenge/statement /tmp/statement 2>/dev/null || true; "
                    f"{command}",
                ]
                proc = subprocess.run(
                    exec_cmd,
                    cwd=tmpdir,
                    capture_output=True,
                    text=True,
                    timeout=timeout_sec,
                    check=False,
                )
            else:
                local_cmd = _rewrite_local_command(command, challenge_dir, submission_dir)
                proc = subprocess.run(
                    local_cmd,
                    shell=True,
                    cwd=tmpdir,
                    capture_output=True,
                    text=True,
                    timeout=timeout_sec,
                    check=False,
                )

            run_output = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
            logs.append(f"--- Run {run_idx}/{repeats} (exit {proc.returncode}) ---\n{run_output.strip()}")

            if proc.returncode != 0:
                return {
                    "status": "fail",
                    "value": None,
                    "log": "\n".join(logs),
                    "details": {"run": run_idx, "exit_code": proc.returncode},
                }

            stdout_lines = [ln.strip() for ln in (proc.stdout or "").splitlines() if ln.strip()]
            if not stdout_lines:
                return {
                    "status": "fail",
                    "value": None,
                    "log": "\n".join(logs) + "\nError: Verifier produced no stdout JSON line.",
                    "details": {"run": run_idx},
                }

            last_line = stdout_lines[-1]
            try:
                payload = json.loads(last_line)
            except Exception as exc:
                return {
                    "status": "fail",
                    "value": None,
                    "log": "\n".join(logs) + f"\nError parsing final JSON line {last_line!r}: {exc}",
                    "details": {"run": run_idx, "last_line": last_line},
                }

            if payload.get("valid") is False:
                reason = payload.get("reason", "Submission marked invalid by verifier")
                return {
                    "status": "fail",
                    "value": None,
                    "log": "\n".join(logs) + f"\nInvalid submission: {reason}",
                    "details": {"run": run_idx, "reason": reason},
                }

            if "value" not in payload or not isinstance(payload["value"], (int, float)):
                return {
                    "status": "fail",
                    "value": None,
                    "log": "\n".join(logs) + f"\nMissing numeric 'value' in verifier output: {payload}",
                    "details": {"run": run_idx, "payload": payload},
                }

            measured_values.append(float(payload["value"]))

    agg_val = round(_aggregate_values(measured_values, aggregate_mode), 6)
    details: dict[str, Any] = {
        "repeats": repeats,
        "aggregate": aggregate_mode,
        "runs": measured_values,
        "claimed": claimed,
        "measured": agg_val,
        "used_docker": use_docker,
    }

    if claimed is not None:
        diff = abs(agg_val - claimed)
        rel_diff = diff / max(abs(claimed), 1e-9)
        if rel_diff > 0.01 and diff > tolerance:
            details["claim_discrepancy"] = True
            logs.append(
                f"NOTE: Claimed value ({claimed}) differs from measured ({agg_val}); using measured value."
            )

    logs.append(f"PASS: Measured {aggregate_mode} = {agg_val}")
    return {
        "status": "pass",
        "value": agg_val,
        "log": "\n".join(logs),
        "details": details,
    }
