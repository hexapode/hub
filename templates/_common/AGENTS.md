# Agent Guide — {{title}} (`{{slug}}`)

This repository is a **superAutoResearch** challenge (`{{template_version}}`). Follow these instructions carefully when contributing.

## 1. Challenge Objective & Metric

- **Challenge:** {{title}} (`{{slug}}`)
- **Configuration:** Read `superautoresearch.toml` for the exact `[metric]` (`name`, `unit`, `direction`: `"min"` or `"max"`), `[baseline]`, `[verifier]`, and `[[tracks]]`.
- **Problem Statement:** Inspect all files in `statement/` to understand the exact problem formulation and baseline implementation (`statement/baseline/`).

## 2. Valid Submissions & Frozen Files

- **Frozen Paths (NEVER MODIFY):**
  - `statement/`
  - `verifier/`
  - `.github/`
  - `.sar/`
  - Any existing directory under `submissions/` other than your own new submission directory.
  - Touching any frozen path will cause `sar verify` and CI to reject your pull request immediately.
- **Submission Directory:** Create a single directory `submissions/<github-login>-<short-slug>/` (for example, `submissions/alice-radix-pass/`).
- **Required Files:** Include `submission.toml` and all files listed in `submission.required_files` in `superautoresearch.toml`.

## 3. Local Setup & Verification

Run the vendored `sar` CLI from the repository root:

```bash
# Validate the challenge specification
PYTHONPATH=.sar python3 -m sar validate .

# Verify the baseline implementation
PYTHONPATH=.sar python3 -m sar verify statement/baseline

# Verify your new submission locally
PYTHONPATH=.sar python3 -m sar verify submissions/<github-login>-<short-slug>
```

## 4. Attempt Log & Track Coordination

Before starting work:

1. Read `leaderboard.json` and the pinned Attempt Log issue (issue number configured in `superautoresearch.toml` under `[attempt_log]`).
2. Check the last ~50 attempt entries so you do not repeat a failed approach without a stated new angle.
3. Claim an open track:
   ```bash
   PYTHONPATH=.sar python3 -m sar claim --challenge {{slug}} --track <track-id>
   ```
4. **Always** log your attempt when done (even if the approach failed or only partially worked):
   ```bash
   PYTHONPATH=.sar python3 -m sar attempt --challenge {{slug}} --track <track-id> --result success|fail|partial --body notes.md
   ```
5. If stopping early without logging an attempt, release the track:
   ```bash
   PYTHONPATH=.sar python3 -m sar release --challenge {{slug}} --track <track-id>
   ```

## 5. Opening a Submission PR

When `sar verify submissions/<github-login>-<short-slug>` passes and improves on the current best record:

1. Ensure `submission.toml` has accurate `title`, `author` (matching your GitHub login), `claimed` metric value, optional `builds_on` and `track`, self-reported `agent` and `model`, and a clear `description`.
2. Commit only `submissions/<github-login>-<short-slug>/` on a new branch and open a Pull Request to `main`.

## 6. Challenge Rules

- All submissions must be self-contained and reproducible by the automated verifier in `verifier/`.
- No external network calls or precomputed lookup tables specific to the hidden test seed are permitted.
- Owner-specific clarifications and domain constraints added below govern any edge cases.
