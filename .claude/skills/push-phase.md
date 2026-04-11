---
name: push-phase
description: Commit and push the current phase work to GitHub. Runs tests, linting, and type checks first. Only pushes if all checks pass. Use after each development phase is complete and reviewed.
---

Commit and push the completed phase to GitHub.

## Pre-push Checklist (run all of these first)
1. `/run-tests` — all tests must pass
2. `/lint` — no linting errors
3. `/type-check` — no TypeScript errors

If any check fails, STOP. Fix the issues before pushing.

## Commit Steps

1. **Stage changes:**
```bash
git add -p  # Review each change before staging
```

2. **Write a commit message following this format:**
```
feat(phase-N): <short description>

- <bullet: what was added>
- <bullet: what was added>
- <bullet: what was changed>

Phase N complete. Tests pass. Ready for review.
```

3. **Commit and push:**
```bash
git commit -m "..."
git push origin main
```

## Branch Strategy
- `main` branch: stable, phase-complete code only
- Each phase is committed directly to main after all checks pass
- Tag each phase: `git tag phase-N-complete && git push origin --tags`

## After Pushing
Report the commit hash and GitHub URL to team-lead. Update `docs/AGENT_WORKFLOW.md` to mark the phase as complete.
