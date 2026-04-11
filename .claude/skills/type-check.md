---
name: type-check
description: Run TypeScript compiler and import validation checks on the frontend. Catches type errors, invalid imports, and missing module declarations. Use after any frontend changes.
---

Run TypeScript type checking and import validation on the frontend.

## Steps

1. **TypeScript compiler check** (no emit — type check only):
```bash
cd frontend && npx tsc --noEmit
```

2. **Check for invalid or missing imports**:
```bash
cd frontend && npm run build 2>&1 | grep -E "Cannot find module|Module not found|Type error"
```

3. **Check for unused exports** (informational):
```bash
cd frontend && npx tsc --noEmit --strict 2>&1 | head -50
```

## What Gets Caught
- Missing type definitions
- `import` of a module that does not exist
- Type mismatches between API response shapes and TypeScript interfaces
- Missing `return` types on functions
- Calling functions with wrong argument types

## Pass Criteria
- `tsc --noEmit` exits with 0 errors
- `npm run build` succeeds (no type errors block the build)

## Common Issues and Fixes
- `Cannot find module 'X'` → install the missing package or fix the import path
- `Type 'undefined' is not assignable to type 'string'` → add null check or update the type
- `Property 'X' does not exist on type 'Y'` → update the interface or fix the usage

## On Failure
List each error with file path and line number. Assign to the frontend agent to fix before proceeding.
