#!/bin/bash
# 安装 git hooks — 每次 commit 后自动 push
cp -f "$(dirname "$0")/post-commit" "$(git rev-parse --git-dir)/hooks/post-commit"
chmod +x "$(git rev-parse --git-dir)/hooks/post-commit"
echo "Hooks installed."
