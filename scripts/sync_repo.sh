#!/usr/bin/env bash
set -euo pipefail

BRANCH="${1:-main}"

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "❌ 当前目录不是 git 仓库"
  exit 1
fi

if ! git remote get-url origin >/dev/null 2>&1; then
  echo "❌ 未配置 origin 远端，请先执行: git remote add origin <repo_url>"
  exit 1
fi

echo "==> fetch origin"
git fetch origin --prune

if git show-ref --verify --quiet "refs/remotes/origin/${BRANCH}"; then
  echo "==> 同步分支 ${BRANCH}"
  git checkout "${BRANCH}" 2>/dev/null || git checkout -b "${BRANCH}" "origin/${BRANCH}"
  git pull --ff-only origin "${BRANCH}"
else
  echo "⚠️ 远端不存在 origin/${BRANCH}，回退到 origin/main"
  git checkout main 2>/dev/null || git checkout -b main origin/main
  git pull --ff-only origin main
fi

echo "✅ 同步完成"
git status -sb
