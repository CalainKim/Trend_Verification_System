#!/bin/bash
# 로컬 일일 수집. launchd 가 이 스크립트를 부른다.
#
# 29CM 가 클라우드 IP 를 막아 GitHub Actions 에서는 수집이 안 된다.
# 가정 네트워크에서 돌려야 200 이 온다.
set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO" || exit 1
LOG="$REPO/data/collect.log"
exec >> "$LOG" 2>&1

echo "=== $(date '+%Y-%m-%d %H:%M:%S') 수집 시작 ==="

if ! ./.venv/bin/python scripts/collect_daily.py; then
    echo "수집 실패. 다음 실행에서 재시도한다."
    exit 1
fi

./.venv/bin/python scripts/build_dashboard.py || true

git add data/snapshots docs
if git diff --staged --quiet; then
    echo "변경 없음"
else
    git commit -q -m "chore(data): 29CM 랭킹 스냅샷 $(date +%Y-%m-%d)"
    git push -q origin main && echo "푸시 완료" || echo "푸시 실패 (다음 실행에서 함께 올라간다)"
fi
echo "=== 완료 ==="
