"""Milestones 6 & 7 tests: Static site files, skills, launch.md, donate.md, and plugin manifests."""

from __future__ import annotations

import json
import re
import subprocess
import sys
import unittest

from sar.config import get_hub_root


class TestMilestones6And7SiteAndSkills(unittest.TestCase):
    def test_static_site_and_generated_files_exist(self) -> None:
        hub = get_hub_root()
        self.assertTrue((hub / "site" / "index.html").is_file())
        self.assertTrue((hub / "site" / "styles.css").is_file())
        self.assertTrue((hub / "site" / "app.js").is_file())
        self.assertTrue((hub / "generated" / "global.json").is_file())
        self.assertTrue((hub / "generated" / "index.json").is_file())

    def test_plugin_manifests_and_skills_valid(self) -> None:
        hub = get_hub_root()
        mp = json.loads((hub / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
        pl = json.loads((hub / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        self.assertEqual(mp["name"], "superautoresearch")
        self.assertEqual(pl["name"], "superautoresearch")

        for skill_name in ("new-challenge", "register-repo", "donate"):
            skill_file = hub / "skills" / skill_name / "SKILL.md"
            self.assertTrue(skill_file.is_file(), f"Missing {skill_file}")
            txt = skill_file.read_text(encoding="utf-8")
            self.assertTrue(txt.startswith("---\n"), f"{skill_file} missing YAML frontmatter")
            self.assertIn(f"name: {skill_name}", txt)
            self.assertIn("description:", txt)

    def test_every_sar_command_in_skills_exists_in_help(self) -> None:
        hub = get_hub_root()
        proc = subprocess.run(
            [sys.executable, "-m", "sar", "--help"],
            cwd=str(hub),
            capture_output=True,
            text=True,
            check=True,
        )
        help_txt = proc.stdout

        docs_to_check = [
            hub / "launch.md",
            hub / "donate.md",
            hub / "skills" / "new-challenge" / "SKILL.md",
            hub / "skills" / "register-repo" / "SKILL.md",
            hub / "skills" / "donate" / "SKILL.md",
        ]
        referenced_cmds: set[str] = set()
        for doc in docs_to_check:
            content = doc.read_text(encoding="utf-8")
            for m in re.finditer(r"\bsar\s+([a-z][a-z-]+)\b", content):
                cmd = m.group(1)
                if cmd not in ("TOML", "block", "header", "cli"):
                    referenced_cmds.add(cmd)

        for cmd in referenced_cmds:
            self.assertIn(cmd, help_txt, f"Subcommand 'sar {cmd}' referenced in docs but missing from sar --help")


if __name__ == "__main__":
    unittest.main()
