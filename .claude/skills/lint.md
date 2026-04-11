---
name: lint
description: Run linters on both frontend and backend code. Runs ESLint for TypeScript/Next.js and Ruff for Python. Fix any issues found before proceeding. Use after writing code in any phase.
---

Run linters across the entire codebase.

## Steps

1. **Frontend linting** (if frontend/ exists):
```bash
cd frontend && npm run lint
```

2. **Backend linting** (if backend/ exists):
```bash
cd backend && ruff check app/ --fix
```

3. **Backend formatting check**:
```bash
cd backend && ruff format app/ --check
```

## What Gets Checked
- **ESLint:** Unused variables, missing dependencies in useEffect, React rules
- **Ruff:** PEP8, unused imports, bare except clauses, f-string issues, type annotation style

## Auto-fix
- `ruff check --fix` will auto-fix safe issues
- For ESLint, some issues require manual fixes — report them clearly

## Pass Criteria
- `npm run lint` exits with 0 errors (warnings are acceptable but should be reviewed)
- `ruff check` exits with 0 issues

## On Failure
List each linting error with file path and line number. Fix them before marking the phase complete.
