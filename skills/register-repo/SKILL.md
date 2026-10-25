---
name: register-repo
description: >
  Register an existing public GitHub repository as an external challenge in the superAutoResearch hub.
  Triggers: "register this repo", "add <repo> to the hub", "list an existing challenge".
---

# Skill: `register-repo`

Use this skill when the user asks to **"register this repo"**, **"add <repo> to the hub"**, or **"list an existing challenge"**.

## Workflow

1. **Inspect the target repository:**
   Read the target repository's `README.md`, `CONTRIBUTING.md`, and recent merged pull requests to identify the objective, metric, baseline, submission rules, and record history format.
2. **Draft the registry entry & test-parse records:**
   Create `registry/<slug>.toml` with `kind = "external"`, inline `[spec]`, and `[spec.records_source]` (`type = "readme-table"`, `"leaderboard-json"`, or `"hub"`).
   Verify the schema and record parser with:
   ```bash
   sar validate registry/<slug>.toml --external
   ```
3. **Confirm & open the registration PR:**
   Show the generated `registry/<slug>.toml` entry and parsed records preview to the user. After confirming with the user, run:
   ```bash
   sar register --external <owner/repo>
   ```
   (or `sar register --external <owner/repo> --dry-run` to preview without pushing).
   Report the resulting hub Pull Request URL.
