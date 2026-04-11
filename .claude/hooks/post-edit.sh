#!/bin/bash
# Hook: runs after code files are edited
# Triggered by: PostToolUse (Edit, Write)
# Purpose: auto-lint and type-check on save

FILE="$1"

# Only run on relevant file types
if [[ "$FILE" == *.ts || "$FILE" == *.tsx ]]; then
  echo "--- TypeScript lint check ---"
  cd "$(git rev-parse --show-toplevel)/frontend" 2>/dev/null || exit 0
  npx eslint "$FILE" --max-warnings=0 2>&1 | tail -20
fi

if [[ "$FILE" == *.py ]]; then
  echo "--- Python lint check ---"
  cd "$(git rev-parse --show-toplevel)/backend" 2>/dev/null || exit 0
  ruff check "$FILE" 2>&1 | tail -20
fi
