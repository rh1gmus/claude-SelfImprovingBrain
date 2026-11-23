# Git (RULE)
- The repo is owned and committed by `<OWNER>` (the non-root user that owns the repo). Claude Code runs as root, so run EVERY git command for brain through `<BRAIN_DIR>/scripts/bgit <args>` (e.g. `bgit add -A`, `bgit commit ...`, `bgit push`). [R-019]
  Never run `git` on brain directly as root. [R-020]
  Never add a `safe.directory` exception for brain. [R-021]
- At session start, the SessionStart hook runs `scripts/brain-check.sh`. It makes sure brain is a git repo with `origin` set, pulls fast-forward changes on `main`, returns to `main` once a `brain/` branch is merged, and warns about local commits on `main`.
  If it reports a problem, fix it before any other brain edits. [R-022]
  If the hook did not run, run the script yourself. [R-023]
- claude_brain must always be a git repo with `origin = <REMOTE_URL>` (your brain repo). [R-024]
  `main` is protected on GitHub: never push to it. [R-025]
- Do brain work on a branch `brain/<slug>` (`bgit switch -c`). [R-026]
  Commit at the end of the task, one logical change per commit. [R-027]
  Never leave changes uncommitted at session end. [R-028]
- After every commit, run `bgit push -u origin HEAD`. [R-029]
  Then tell the maintainer the branch is ready to merge on GitHub. Only the maintainer merges. [R-030]
  If the push fails, report it; don't retry in a loop. [R-031]
- Commit message format (enforced by `hooks/commit-msg`): [R-032]
  ```
  <area>: <what changed, imperative, at least 4 words>

  Why: <the reason or expected benefit>
  Trigger: <what prompted it: project, task, observation>
  ```
  `<area>` is one of: rules, instructions, agents, hooks, scripts, templates, docs.
- Vague subjects ("update", "fixes", "changes", "wip") are rejected. [R-033]
- Never `--no-verify`. [R-034]
  Never amend pushed commits. [R-035]
  Never force-push. [R-036]
