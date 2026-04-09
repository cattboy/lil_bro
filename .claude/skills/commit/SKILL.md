 ---
 name: commit
 description: |
   Stage all changes and commit with a rich conventional commit message, automatically enriched with GitHub context (linked issues, open PRs). Uses the gh CLI to detect issue numbers from the branch name, check for an open PR, and scan open issues for relevance. Asks smart clarifying questions only when the diff is ambiguous or spans multiple concerns — stays silent when context is clear.

   Use this skill whenever the user says /commit, "commit my changes", "commit this", "commit everything", "make a commit", or any variation. IMPORTANT: trigger this skill even if the user doesn't say "gh" or "GitHub" — it handles standard commits too.
 compatibility: requires git, gh CLI
 ---

## Workflow

Run Steps 1–2 in parallel, then analyze, then ask (if needed), then commit.

---

## Step 1 — Stage and diff

```bash
git add .
git diff --cached --stat
git diff --cached
```

Keep the full diff in context. The stat gives you the scope at a glance.

---

## Step 2 — Gather GitHub context (run in parallel with Step 1)

```bash
# Branch name
git rev-parse --abbrev-ref HEAD

# Open PR on this branch (if any)
gh pr view --json number,title,body 2>/dev/null

# Recent commits — for message style reference
git log --oneline -5
```

**Parse the branch name** for issue numbers. Match these patterns:
- `feature/123-description`, `fix/456`, `123-some-desc`, `GH-123`, `issue-789`

If a number is found, fetch the issue:
```bash
gh issue view <number> --json title,body,labels 2>/dev/null
```

If **no** issue number is in the branch name **and** the diff looks like a feature or fix (not a pure style/chore), fetch recent open issues to check relevance:
```bash
gh issue list --limit 8 --state open --json number,title,labels 2>/dev/null
```

Scan the issue titles against the diff's changed files/symbols. If one clearly matches (e.g. issue title mentions "thermal gate" and the diff edits `thermal_gate.py`), treat it as the linked issue.

---

## Step 3 — Decide whether to ask questions

Ask at most **2** clarifying questions — and only when they'd meaningfully change the commit message. Skip questions entirely when:

- An issue or PR was found and its title explains the purpose of the diff
- The diff is small and focused (≤3 files, single clear purpose)
- The branch name itself is descriptive enough to infer intent
- Recent commit messages already establish clear context for this work stream

**Ask when:**
- The diff touches 3+ distinct modules with no unifying theme and no GitHub context was found
- The change purpose is genuinely unclear from the diff alone (would produce a vague message like `refactor(misc): various changes`)
- The diff mixes concerns that could be separate commits (e.g., a bug fix alongside a doc update alongside a refactor)

**Question options** — choose the 1–2 most useful:
- **"What's the main goal of this change?"** — when purpose is ambiguous
- **"Is this related to a specific GitHub issue?"** — when no issue was detected but the change looks purposeful
- **"These changes touch [X] and [Y] — should I commit them together or as separate commits?"** — when concerns are clearly mixed

Wait for the user to answer before continuing.

---

## Step 4 — Generate the commit message

Build a conventional commit:

```
type(scope): subject line (~50 chars, lowercase, imperative)

Optional body — only include if the "why" needs explaining, context
from an issue is worth preserving, or there are genuinely multiple
distinct changes worth listing.

closes #123
```

**Choosing type:** `feat`, `fix`, `refactor`, `docs`, `test`, `perf`, `style`, `chore`

**Issue reference rules:**
- `closes #X` — the issue is fully resolved by this commit
- `refs #X` — the commit is partial progress toward the issue
- Omit entirely if no issue is confirmed (don't guess)

**Body:** keep it short or omit. Include it when:
- The subject alone won't tell a future reader *why* the change was made
- There's a non-obvious constraint or trade-off worth noting
- A linked issue title adds meaningful context that doesn't fit the subject

**Style:** match the tone of the 5 most recent commits in this repo.

---

## Step 5 — Commit (no confirmation needed)

```bash
git commit -m "$(cat <<'EOF'
type(scope): subject

Optional body here.

closes #123
EOF
)"
```

Report the resulting commit hash and message to the user on success. On failure (hook rejection, nothing staged, merge conflict) report the error clearly with the suggested next step.

---

## Examples

**Branch `fix/789-thermal-crash`, small diff in `thermal_gate.py`**
→ gh finds issue #789: "Thermal gate crashes when LHM returns no sensors"
→ No questions (diff is focused, issue found)
→ `fix(thermal): handle missing LHM sensor data gracefully (closes #789)`

**Branch `refactor/priority-1-improvements`, diff across 6 files in pipeline + display**
→ No issue number in branch, no PR open
→ Open issues scanned — no clear match
→ Ask: "What's the main goal across these changes? And is this tied to a GitHub issue?"
→ User: "Display detection cleanup and thermal phase stability — not an issue"
→ `refactor(pipeline): clean up display detection and thermal phase logic`

**Branch `main`, small one-liner fix in `spec_dumper.py`**
→ No issue, no PR, but diff is tiny and obviously a typo fix
→ No questions (diff is self-evident)
→ `fix(spec): correct typo in GPU name extraction`
