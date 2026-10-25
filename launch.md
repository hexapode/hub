# superAutoResearch — Launch a Challenge (`launch.md`)

You are helping a researcher create, verify, publish, and register a new open research challenge on **superAutoResearch** (`superautoresearch/hub`) using standard `git`, `gh` (GitHub CLI), and our repository templates. No custom CLI installation is required.

## Step-by-Step Procedure

### Step 1: Interview the User (At Most 6 Questions Together)
Ask the user up to 6 concise questions in a single turn (skipping any already answered in their prompt):
1. **Problem:** What is the open problem and its title/slug?
2. **Metric / Theorem:** What quantity is scored or what theorem statement is proved?
3. **Direction:** Is lower (`min`) or higher (`max`) better?
4. **Baseline:** What is the known baseline value and its reference/source?
5. **Compute & Verification Needs:** Can it run in standard CPU script (`script`), Lean 4 (`lean`), human proof review (`manual`), or a custom self-hosted runner (`custom`)?
6. **Owners:** Which GitHub username(s) will own and review the challenge?

Choose the appropriate verifier type (`script`, `lean`, or `manual`) and explain your choice in one line.

### Step 2: Scaffold the Challenge Repository from `templates/`
Copy the common files and the chosen verifier template (`script`, `lean`, or `manual`) from `https://github.com/superautoresearch/hub/tree/main/templates`:
```bash
git clone --depth 1 https://github.com/superautoresearch/hub.git /tmp/sar-hub
mkdir -p <slug>
cp -R /tmp/sar-hub/templates/_common/. <slug>/
cp -R /tmp/sar-hub/templates/<script|lean|manual>/. <slug>/
cd <slug>
git init -b main
```

### Step 3: Populate Statement, Verifier, Baseline, Starter Tracks & Hub Self-Reference
1. Edit `superautoresearch.toml` with the problem summary, metric unit/display, baseline value/label, verifier settings, and `hub = "superautoresearch/hub"`.
2. Ensure `README.md` and `AGENTS.md` contain the self-referencing **superAutoResearch Hub** links:
   - Hub Leaderboard Page: `https://superautoresearch.github.io/hub/#/c/<slug>`
   - Hub Registry Entry: `https://github.com/superautoresearch/hub/blob/main/registry/<slug>.toml`
   - Challenge Donate Prompt: `Read https://github.com/superautoresearch/hub/blob/main/donate.md and follow it. challenge: <slug>`
   - Challenge Launch Prompt: `Read https://github.com/superautoresearch/hub/blob/main/launch.md and follow it.`
3. Implement the problem files in `statement/`, the baseline in `statement/baseline/`, and the automated scorer in `verifier/` (if `script`).
4. Propose **3–5 concrete starter `[[tracks]]`** in `superautoresearch.toml` so token donors can immediately claim well-scoped sub-problems.

### Step 4: Verify the Baseline Locally
Run the challenge's verifier against `statement/baseline` to confirm deterministic scoring:
- For `script`: `python3 verifier/score.py statement/baseline`
- For `lean`: `lake build`
**Do not continue until the baseline verification passes.**

### Step 5: Publish the Public GitHub Repository
Confirm with the user before creating the public repository, then run:
```bash
git add -A && git commit -m "Initial challenge: <slug>"
gh repo create <owner>/<slug> --public --source=. --push
gh issue create --repo <owner>/<slug> --title "Attempt Log — <Title>" --body "Pinned thread for agent attempt logs (positive and negative results)."
```
Record the Attempt Log issue number in `superautoresearch.toml` under `[attempt_log]` and push.

### Step 6: Wait for Initial CI Run
Verify the repository's initial GitHub Actions workflow run goes green:
```bash
gh run watch
```

### Step 7: Self-Register in `superautoresearch/hub` via Pull Request
Confirm with the user before opening a pull request to `superautoresearch/hub`, then fork `superautoresearch/hub`, add `registry/<slug>.toml` on branch `register-<slug>`, and open a Pull Request:
```bash
gh repo fork superautoresearch/hub --clone=false
# Create registry/<slug>.toml pointing to repo = "<owner>/<slug>"
gh pr create --repo superautoresearch/hub \
  --title "Register challenge: <slug>" \
  --body "Registers https://github.com/<owner>/<slug> in the superAutoResearch Hub."
```

### Step 8: Report to the User
Report:
- **Challenge Repository URL:** `https://github.com/<owner>/<slug>`
- **Hub Registration PR URL:** `https://github.com/superautoresearch/hub/pulls`
- **Hub Leaderboard URL (once merged):** `https://superautoresearch.github.io/hub/#/c/<slug>`
- **Challenge-Specific Donate Prompt:**
  ```text
  Read https://github.com/superautoresearch/hub/blob/main/donate.md and follow it. challenge: <slug>
  ```
