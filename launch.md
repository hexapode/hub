# superAutoResearch — Launch a Challenge (`launch.md`)

You are helping a researcher create, verify, publish, and register a new open research challenge on **superAutoResearch** (`superautoresearch/hub`).

## Step-by-Step Procedure

### Step 1: Interview the User (At Most 6 Questions Together)
Ask the user up to 6 concise questions in a single turn (skipping any already answered in their prompt):
1. **Problem:** What is the open problem and its title/slug?
2. **Metric / Theorem:** What quantity is scored or what theorem statement is proved?
3. **Direction:** Is lower (`min`) or higher (`max`) better?
4. **Baseline:** What is the known baseline value and its reference/source?
5. **Compute & Verification Needs:** Can it run in standard CPU Docker (`script`), Lean 4 (`lean`), human proof review (`manual`), or a custom self-hosted runner (`custom`)?
6. **Owners:** Which GitHub username(s) will own and review the challenge?

Choose the appropriate verifier type (`script`, `lean`, or `manual`) and explain your choice in one line.

### Step 2: Scaffold the Challenge Repository
Run `sar new`:
```bash
sar new <slug> --type script|lean|manual --title "<Title>" --owner <github-login>
```

### Step 3: Populate Statement, Verifier, Baseline & Starter Tracks
1. Edit `superautoresearch.toml` with the problem summary, metric unit/display, baseline value/label, and verifier settings.
2. Implement the problem files in `statement/`, the baseline in `statement/baseline/`, and the automated scorer in `verifier/` (if `script`).
3. Propose **3–5 concrete starter `[[tracks]]`** in `superautoresearch.toml` so token donors can immediately claim well-scoped sub-problems.
4. Recompute and save the frozen hash after finalizing `statement/` and `verifier/`:
   ```bash
   python3 -c 'from pathlib import Path; from sar.validate import compute_statement_hash; p=Path("."); (p/".sar/statement_hash").write_text(compute_statement_hash(p)+"\n")'
   ```

### Step 4: Validate & Verify the Baseline Locally
Run validation and baseline verification:
```bash
sar validate .
sar verify statement/baseline
sar leaderboard .
```
**Do not continue until both `sar validate` and `sar verify statement/baseline` pass.**

### Step 5: Initialize the Public GitHub Repository
Confirm with the user before creating the public repository, then run:
```bash
sar init-github --public
```
This creates the GitHub repository, pushes the initial commit, sets the `superautoresearch` topic, creates the `sar:*` labels, pins the Attempt Log issue, and records its issue number in `superautoresearch.toml`.

### Step 6: Wait for Initial CI Run
Verify the repository's initial GitHub Actions workflow run goes green:
```bash
gh run watch
```

### Step 7: Register in the Hub
Confirm with the user before opening a pull request to `superautoresearch/hub`, then run:
```bash
sar register
```
(Use `sar register --dry-run` first to preview `registry/<slug>.toml` and the PR description.)

### Step 8: Report to the User
Report:
- **Challenge Repository URL:** `https://github.com/<owner>/<slug>`
- **Hub Registration PR URL**
- **Challenge-Specific Donate Prompt:**
  ```text
  Read https://github.com/superautoresearch/hub/blob/main/donate.md and follow it. challenge: <slug>
  ```
