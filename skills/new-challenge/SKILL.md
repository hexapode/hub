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
2. **Scaffold the repo from `templates/`:**
   Copy `templates/_common/` and `templates/<type>/` into `<slug>/` as described in [`launch.md`](../../launch.md).
3. **Fill in problem & tracks:**
   Populate `statement/`, `verifier/`, `statement/baseline/`, and `superautoresearch.toml` with the user, including self-referencing links to `superautoresearch/hub`. Propose 3–5 starter `[[tracks]]`.
4. **Verify baseline locally:**
   Run the verifier (`python3 verifier/score.py statement/baseline` or `lake build`). Do not continue until the baseline passes.
5. **Publish on GitHub (confirm first):**
   Ask the user for confirmation before creating a public repository, then create `<owner>/<slug>` via `gh repo create --public --source=. --push` and open the pinned Attempt Log issue.
6. **Wait for green CI:**
   Wait for the repository's first CI run to pass (`gh run watch`).
7. **Register in `superautoresearch/hub` (confirm first):**
   Ask the user for confirmation before opening a PR to `superautoresearch/hub`, then add `registry/<slug>.toml` on a fork branch and run `gh pr create --repo superautoresearch/hub`.
8. **Report:**
   Provide the challenge repo URL, the hub registry PR URL, and the challenge-specific donate prompt:
   `Read https://github.com/superautoresearch/hub/blob/main/donate.md and follow it. challenge: <slug>`
