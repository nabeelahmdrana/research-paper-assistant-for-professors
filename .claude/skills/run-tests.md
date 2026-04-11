---
name: run-tests
description: Run all test suites for the project. Runs frontend Jest tests and backend pytest tests. Reports pass/fail status for each. Use after completing any phase before pushing to GitHub.
---

Run the full test suite for the Research Paper Assistant project.

## Steps

1. **Frontend tests** (if frontend/ exists and has tests):
```bash
cd frontend && npm test -- --watchAll=false --passWithNoTests
```

2. **Backend tests** (if backend/ exists):
```bash
cd backend && python -m pytest tests/ -v --tb=short
```

3. **Report results:**
- List which tests passed
- List which tests failed with the error message
- If any tests fail, do NOT push to GitHub — fix the failures first

## Pass Criteria
- All tests pass (exit code 0)
- No skipped tests that should be running

## On Failure
Report the failing test name, the error, and which file/function caused it. Ask the relevant agent (frontend or backend) to fix the issue.
