---
name: smoke
description: Quick end-to-end smoke test for the full stack. Verifies the frontend builds without errors, the backend starts and returns a healthy response, and a sample research query completes successfully. Use before demos, after merges, or whenever you want a fast confidence check that nothing is broken.
---

Run a fast smoke test across frontend, backend, and the research pipeline.

## Steps

### 1. Frontend build check
```bash
cd frontend && npm run build 2>&1 | tail -20
```
Pass criteria: exits with code 0, no TypeScript or webpack errors.

### 2. Backend import check
```bash
cd backend && python -c "from app.main import app; print('Backend imports OK')"
```
Pass criteria: prints `Backend imports OK` with no import errors.

### 3. Backend health endpoint
Start the server in the background, hit the health endpoint, then stop it:
```bash
cd backend && uvicorn app.main:app --host 127.0.0.1 --port 8765 &
SERVER_PID=$!
sleep 3
curl -sf http://127.0.0.1:8765/health && echo "Health OK" || echo "Health FAILED"
kill $SERVER_PID 2>/dev/null
```
Pass criteria: returns HTTP 200 with `Health OK`.

### 4. Minimal query smoke test (backend unit-level)
```bash
cd backend && python -m pytest tests/ -v -k "smoke or health or import" --tb=short -q
```
Pass criteria: any smoke/health tests pass; no errors on collection.

### 5. Frontend lint (fast, no full test run)
```bash
cd frontend && npm run lint -- --max-warnings 0
```
Pass criteria: zero errors, zero warnings.

---

## Commit smoke (pre-commit quick check)
Run this before committing to catch obvious breakage:
```bash
cd backend && ruff check app/ --select E,F --quiet && echo "Ruff OK"
cd frontend && npm run type-check 2>&1 | tail -5
```
Pass criteria: `Ruff OK` + TypeScript exits with 0 errors.

---

## Pass / Fail Summary

Report results as a table:

| Check | Result | Notes |
|---|---|---|
| Frontend build | PASS / FAIL | error message if failed |
| Backend imports | PASS / FAIL | |
| Health endpoint | PASS / FAIL | |
| Backend tests (smoke) | PASS / FAIL | |
| Frontend lint | PASS / FAIL | |

If **any check fails**, do NOT proceed with a demo or push. Fix the failure and re-run `/smoke`.
