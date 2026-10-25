---
name: new-challenge
description: >
  Create and register a new superAutoResearch challenge repository from templates.
  Triggers: "create a challenge", "launch a research challenge", "set up a new speedrun".
---

# Skill: `new-challenge`

Use this skill when the user asks to **"create a challenge"**, **"launch a research challenge"**, or **"set up a new speedrun"**.

## Workflow

1. **Interview the user** (at most 6 questions, asked together where possible):
   - Problem statement & title
   - What metric is scored or what theorem is proved
   - Metric direction (`min` or `max`)
   - Baseline value and source
   - Compute / verification needs
   - GitHub owner login(s)
   Choose the verifier type (`script`, `lean`, or `manual`) and explain the choice in one line.
2. **Scaffold the repo:**
   Run `sar new <slug> --type <type> --title "<Title>" --owner <owner>`.
3. **Fill in problem & tracks:**
   Populate `statement/`, `verifier/`, `statement/baseline/`, and `superautoresearch.toml` with the user. Propose 3–5 starter `[[tracks]]`.
4. **Validate and verify baseline:**
   Run `sar validate` and `sar verify statement/baseline`. Do not continue until the baseline passes.
5. **Initialize on GitHub (confirm first):**
   Ask the user for confirmation before creating a public repository, then run `sar init-github --public` (or `sar init-github --dry-run` to preview).
6. **Wait for green CI:**
   Wait for the repository's first CI run to pass (`gh run watch`).
7. **Register in the hub (confirm first):**
   Ask the user for confirmation before opening a PR to `superautoresearch/hub`, then run `sar register` (or `sar register --dry-run`).
8. **Report:**
   Provide the challenge repo URL, the hub registry PR URL, and the challenge-specific donate prompt:
   `Read https://github.com/superautoresearch/hub/blob/main/donate.md and follow it. challenge: <slug>`
