"""Milestone 4 tests: Challenge workflows and `sar/report.py` untrusted artifact handling."""

from __future__ import annotations

import shutil
import subprocess
import unittest
from pathlib import Path

from sar.config import get_hub_root
from sar.report import generate_pr_report


class TestMilestone4WorkflowsAndReport(unittest.TestCase):
    def test_workflows_exist_and_have_least_privilege(self) -> None:
        hub = get_hub_root()
        wf_dir = hub / "templates" / "_common" / ".github" / "workflows"
        for name in ("verify.yml", "report.yml", "leaderboard.yml"):
            p = wf_dir / name
            self.assertTrue(p.is_file(), f"Missing {p}")

        verify_txt = (wf_dir / "verify.yml").read_text(encoding="utf-8")
        self.assertIn("contents: read", verify_txt)
        self.assertNotIn("pull_request_target", verify_txt)

        report_txt = (wf_dir / "report.yml").read_text(encoding="utf-8")
        self.assertIn("workflow_run", report_txt)
        self.assertIn("pull-requests: write", report_txt)

        if shutil.which("actionlint"):
            proc = subprocess.run(
                ["actionlint", str(wf_dir / "verify.yml"), str(wf_dir / "report.yml"), str(wf_dir / "leaderboard.yml")],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stdout + proc.stderr)

    def test_report_logic_on_fixture_artifacts(self) -> None:
        spec = {
            "metric": {"name": "runtime", "unit": "s", "direction": "min"},
            "baseline": {"value": 0.25, "label": "Baseline"},
            "verifier": {"type": "script", "tolerance": 0.001},
            "auto_merge": False,
        }
        leaderboard = {
            "metric": spec["metric"],
            "baseline": spec["baseline"],
            "records": [{"id": "bob-rec", "value": 0.15, "author": "bob", "date": "2026-10-10"}],
        }

        # 1. Passing record that beats 0.15
        pass_artifact = {
            "status": "pass",
            "value": 0.08,
            "submission_id": "alice-fast<script>",
            "log": "Run 1 ok\n```injected fence```\nPASS",
        }
        rep1 = generate_pr_report(pass_artifact, leaderboard, spec)
        self.assertTrue(rep1["beats_best"])
        self.assertIn("sar:verified", rep1["labels_to_add"])
        self.assertFalse(rep1["should_auto_merge"])  # auto_merge is False by default
        # Verify HTML/Markdown injection was escaped
        self.assertNotIn("<script>", rep1["comment"])
        self.assertIn("&lt;script&gt;", rep1["comment"])

        # 2. Same with auto_merge = True
        spec_auto = dict(spec, auto_merge=True)
        rep2 = generate_pr_report(pass_artifact, leaderboard, spec_auto)
        self.assertTrue(rep2["should_auto_merge"])

        # 3. Failing artifact
        fail_artifact = {
            "status": "fail",
            "value": None,
            "submission_id": "dave-bad",
            "log": "AssertionError: wrong output",
        }
        rep3 = generate_pr_report(fail_artifact, leaderboard, spec_auto)
        self.assertFalse(rep3["beats_best"])
        self.assertIn("sar:failed", rep3["labels_to_add"])
        self.assertFalse(rep3["should_auto_merge"])

        # 4. Malformed artifact
        rep4 = generate_pr_report({"status": "hacked", "value": "not-a-number"}, leaderboard, spec)
        self.assertEqual(rep4["status"], "error")
        self.assertIn("sar:failed", rep4["labels_to_add"])


if __name__ == "__main__":
    unittest.main()
