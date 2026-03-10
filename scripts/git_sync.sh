#!/usr/bin/env bash
# git_sync.sh — Commit and push generated QNA files to the remote repository.
# Usage:  bash scripts/git_sync.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

echo "📂 Working in: $REPO_ROOT"

# Stage all generated QNA files (PDFs + Markdown intermediates + images)
git add Subjects/**/*_QNA.pdf Subjects/**/*_QNA.md Subjects/**/assets/* 2>/dev/null || true

# Check if there are changes to commit
if git diff --cached --quiet; then
    echo "✅ Nothing new to commit."
    exit 0
fi

# Build a commit message listing new files
NEW_FILES=$(git diff --cached --name-only)
TIMESTAMP=$(date '+%Y-%m-%d %H:%M')
COMMIT_MSG="chore(auto): generated QNA notes — $TIMESTAMP

Files:
$NEW_FILES"

git commit -m "$COMMIT_MSG"
echo "📤 Pushing to remote …"
git push

echo "✅ Sync complete."
