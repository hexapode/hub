"""Milestone 2 tests: Templates + `sar new` + `sar verify` + frozen path checks."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from sar.new_challenge import create_challenge
from sar.validate import validate_challenge_repo
from sar.verifiers import verify_submission
from sar.verifiers.lean import is_lean_installed


class TestMilestone2TemplatesAndVerify(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["SAR_SORT_N"] = "15000"

    def test_script_template_baseline_and_wrong_solution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            repo_dir = create_challenge("demo-sort", "script", target_dir=tmp_path, owner="alice")
            validate_challenge_repo(repo_dir)

            # Verify baseline passes
            res = verify_submission(repo_dir, repo_dir / "statement" / "baseline", no_docker=True)
            self.assertEqual(res["status"], "pass", msg=res["log"])
            self.assertIsNotNone(res["value"])

            # Create a deliberately wrong submission
            wrong_dir = repo_dir / "submissions" / "alice-wrong"
            wrong_dir.mkdir(parents=True)
            (wrong_dir / "submission.toml").write_text(
                'schema = 1\ntitle = "Wrong sort"\nauthor = "alice"\nclaimed = 0.01\ndescription = "Returns reversed list"\n',
                encoding="utf-8",
            )
            (wrong_dir / "solution.py").write_text(
                "def sort_integers(data):\n    return [0] * len(data)\n",
                encoding="utf-8",
            )
            wrong_res = verify_submission(repo_dir, wrong_dir, no_docker=True)
            self.assertEqual(wrong_res["status"], "fail")

    def test_general_checks_reject_statement_modification(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_dir = create_challenge("demo-frozen", "script", target_dir=Path(tmp), owner="alice")
            sub_dir = repo_dir / "submissions" / "alice-valid"
            sub_dir.mkdir(parents=True)
            (sub_dir / "submission.toml").write_text(
                'schema = 1\ntitle = "Valid sort"\nauthor = "alice"\nclaimed = 0.01\ndescription = "Built-in sorted"\n',
                encoding="utf-8",
            )
            (sub_dir / "solution.py").write_text(
                "def sort_integers(data):\n    return sorted(data)\n",
                encoding="utf-8",
            )

            # Tamper with statement/README.md
            stmt_readme = repo_dir / "statement" / "README.md"
            stmt_readme.write_text(
                stmt_readme.read_text(encoding="utf-8") + "\nTampered!\n",
                encoding="utf-8",
            )

            res = verify_submission(repo_dir, sub_dir, no_docker=True)
            self.assertEqual(res["status"], "fail")
            self.assertIn("Frozen statement/ or verifier/ files were modified", res["log"])

    def test_manual_template_returns_pending(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_dir = create_challenge("demo-manual", "manual", target_dir=Path(tmp), owner="alice")
            validate_challenge_repo(repo_dir)
            res = verify_submission(repo_dir, repo_dir / "statement" / "baseline")
            self.assertEqual(res["status"], "pending")
            self.assertEqual(res["value"], 10.0)

    def test_lean_template_and_static_guards(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_dir = create_challenge("demo-lean", "lean", target_dir=Path(tmp), owner="alice")
            validate_challenge_repo(repo_dir)

            # Check that redefining Goal or using sorry is rejected even before invoking Lean
            bad_sub = repo_dir / "submissions" / "alice-cheat"
            bad_sub.mkdir(parents=True)
            (bad_sub / "submission.toml").write_text(
                'schema = 1\ntitle = "Cheat"\nauthor = "alice"\nclaimed = 0\ndescription = "Redefines Goal"\n',
                encoding="utf-8",
            )
            (bad_sub / "Submission.lean").write_text(
                "import Statement\ndef Goal (c : Nat) : Prop := True\ntheorem main : Goal 0 := trivial\n",
                encoding="utf-8",
            )
            cheat_res = verify_submission(repo_dir, bad_sub)
            self.assertEqual(cheat_res["status"], "fail")
            self.assertIn("redefine 'Goal'", cheat_res["log"])

            if not is_lean_installed():
                self.skipTest("Lean 4 (lean/lake) is not installed on this machine; skipping live lake build.")

            res = verify_submission(repo_dir, repo_dir / "statement" / "baseline")
            self.assertEqual(res["status"], "pass", msg=res["log"])


if __name__ == "__main__":
    unittest.main()
