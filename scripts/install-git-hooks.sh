#!/bin/sh
# One-time setup: installs the tracked hooks in githooks/ into this local
# clone's .git/hooks/. Git doesn't version .git/hooks itself, so this needs
# to be re-run after every fresh clone.
set -e
repo_root=$(git rev-parse --show-toplevel)
cp "$repo_root/githooks/pre-commit" "$repo_root/.git/hooks/pre-commit"
chmod +x "$repo_root/.git/hooks/pre-commit"
echo "Installed pre-commit hook (blocks commits containing .env or key-shaped strings)."
