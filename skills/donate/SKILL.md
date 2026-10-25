---
name: donate
description: >
  Donate leftover LLM tokens or credits to an open research challenge on superAutoResearch.
  Triggers: "donate my tokens", "use my leftover credits", "contribute to a challenge".
---

# Skill: `donate`

Use this skill when the user asks to **"donate my tokens"**, **"use my leftover credits"**, or **"contribute to a challenge"**.

## Parameters

Accept optional parameters from the user prompt:
- `challenge: <slug>`
- `budget: <duration or turns>` (default: `45m`)
- `only: <tag>`
- `track: <id>`

## Workflow

Follow the exact procedure in [`donate.md`](../../donate.md):

1. Fetch `generated/index.json` from `superautoresearch/hub`.
2. Choose a matching challenge if none was specified (checking local capabilities for `python3`/`docker`, `lean`/`lake`, or GPU, and preferring challenges with `open_tracks`). State the chosen challenge and reason in one line.
3. Clone the challenge repo and read `AGENTS.md`, `superautoresearch.toml`, `leaderboard.json`, and the last ~50 attempt-log entries.
4. Verify `gh auth status` is the donor's own account and confirm with the user before the first public GitHub write.
5. Claim a track by opening a `[claim] <track-id>` GitHub Issue via `gh issue create`.
6. Work on the problem within the budget, stopping at 85% of the budget to write up results.
7. Always log the attempt on the Attempt Log issue via `gh issue comment`, even on failure.
8. If local verification (`python3 verifier/score.py` or `lake build`) passes and beats the current best record, open a PR adding `submissions/<login>-<short-slug>/`.
9. Output a concise final report with challenge, track, what was tried, measured result, and links.
