"""Milestone 3 tests: `sar leaderboard` with 4 merged submissions (2 records, 1 non-improving, 1 invalid)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from sar.leaderboard import build_leaderboard
from sar.new_challenge import create_challenge


class TestMilestone3Leaderboard(unittest.TestCase):
    def test_leaderboard_with_four_merged_submissions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_dir = create_challenge("sort-bench", "script", target_dir=Path(tmp), owner="alice")
            subs_dir = repo_dir / "submissions"

            # Baseline is 0.2500 (direction = min)
            # 1. Record #1: bob-first-improvement (0.1800 at T1)
            s1 = subs_dir / "bob-first-improvement"
            s1.mkdir(parents=True)
            (s1 / "submission.toml").write_text(
                'schema = 1\ntitle = "Chunked merge 128"\nauthor = "bob"\nclaimed = 0.18\nagent = "Claude Code"\nmodel = "claude-opus-5-5"\ndescription = "First improvement"\n',
                encoding="utf-8",
            )
            (s1 / "solution.py").write_text("def sort_integers(d): return sorted(d)\n", encoding="utf-8")
            (s1 / ".result.json").write_text(
                json.dumps({"status": "pass", "value": 0.18, "date": "2026-10-10T10:00:00Z", "pr": 2}),
                encoding="utf-8",
            )

            # 2. Non-improving accepted submission: carol-slower-variant (0.2100 at T2, worse than 0.18)
            s2 = subs_dir / "carol-slower-variant"
            s2.mkdir(parents=True)
            (s2 / "submission.toml").write_text(
                'schema = 1\ntitle = "Alternative heap sort"\nauthor = "carol"\nclaimed = 0.21\ndescription = "Valid but slower than 0.18"\n',
                encoding="utf-8",
            )
            (s2 / "solution.py").write_text("def sort_integers(d): return sorted(d)\n", encoding="utf-8")
            (s2 / ".result.json").write_text(
                json.dumps({"status": "pass", "value": 0.21, "date": "2026-10-12T10:00:00Z", "pr": 3}),
                encoding="utf-8",
            )

            # 3. Record #2: dave-radix-pass (0.0450 at T3, beats 0.18)
            s3 = subs_dir / "dave-radix-pass"
            s3.mkdir(parents=True)
            (s3 / "submission.toml").write_text(
                'schema = 1\ntitle = "Radix 256 sort"\nauthor = "dave"\nclaimed = 0.045\nagent = "Codex"\nmodel = "gpt-5"\ndescription = "Beats 0.18"\n',
                encoding="utf-8",
            )
            (s3 / "solution.py").write_text("def sort_integers(d): return sorted(d)\n", encoding="utf-8")
            (s3 / ".result.json").write_text(
                json.dumps({"status": "pass", "value": 0.045, "date": "2026-10-15T10:00:00Z", "pr": 5}),
                encoding="utf-8",
            )

            # 4. Invalid submission: eve-broken (missing required fields / failed result)
            s4 = subs_dir / "eve-broken"
            s4.mkdir(parents=True)
            (s4 / "submission.toml").write_text(
                'schema = 1\ntitle = "Broken"\n',  # invalid schema
                encoding="utf-8",
            )

            lb = build_leaderboard(repo_dir, fetch_prs=False, reverify_missing=False)

            # Assert exactly 2 records in chronological order
            self.assertEqual(len(lb["records"]), 2)
            self.assertEqual(lb["records"][0]["id"], "bob-first-improvement")
            self.assertEqual(lb["records"][0]["value"], 0.18)
            self.assertEqual(lb["records"][1]["id"], "dave-radix-pass")
            self.assertEqual(lb["records"][1]["value"], 0.045)

            # Assert 3 contributors (bob, carol, dave; eve excluded)
            self.assertEqual(lb["contributors"], 3)

            # Assert README contains both records and "Other accepted submissions" with carol-slower-variant
            readme_txt = (repo_dir / "README.md").read_text(encoding="utf-8")
            self.assertIn("@bob", readme_txt)
            self.assertIn("@dave", readme_txt)
            self.assertIn("### Other accepted submissions", readme_txt)
            self.assertIn("carol-slower-variant", readme_txt)
            self.assertNotIn("eve-broken", readme_txt)


if __name__ == "__main__":
    unittest.main()
