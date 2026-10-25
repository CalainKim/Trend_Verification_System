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

HOST="recommend-api.29cm.co.kr"

echo "=== $(date '+%Y-%m-%d %H:%M:%S') 수집 시작 ==="

# launchd 는 놓친 일정을 깨어날 때 실행한다. 그런데 깨어난 직후에는
# 와이파이가 아직 안 붙어 있어 이름 해석부터 실패한다. 2026-10-17 은
# 10 시와 22 시 실행이 모두 NameResolutionError 로 죽어 하루가 통째로
# 비었고, 같은 원인으로 10/05 10/07 10/08 10/13 도 하루 두 번 중 한 번을
# 잃었다.
#
# 그래서 요청 전에 이름이 풀릴 때까지 기다린다. 재시도하는 대상이
# 29CM 요청이 아니라 전제 조건이므로 서버에 추가 부담을 주지 않는다.
# 해석기는 venv 의 파이썬을 쓴다. host 나 dig 의 설치 여부에 기대지
# 않기 위해서다.
wait_for_dns() {
    local i
    for i in $(seq 1 15); do
        if ./.venv/bin/python -c "import socket; socket.getaddrinfo('$HOST', 443)" 2>/dev/null; then
            [ "$i" -gt 1 ] && echo "네트워크 연결까지 $((i * 20))초 대기함"
            return 0
        fi
        sleep 20
    done
    return 1
}

if ! wait_for_dns; then
    echo "5분을 기다려도 $HOST 이름 해석이 안 됨. 네트워크 없음으로 판단하고 종료한다."
    exit 1
fi

# 일시적 오류까지 덮기 위해 수집 자체도 두 번까지 더 시도한다.
# 중복 행은 signal_raw 의 UNIQUE 제약이 걸러내므로 재시도해도 안전하다.
collected=0
for attempt in 1 2 3; do
    if ./.venv/bin/python scripts/collect_daily.py; then
        collected=1
        break
    fi
    if [ "$attempt" -lt 3 ]; then
        echo "수집 실패 ($attempt/3). 2분 뒤 재시도한다."
        sleep 120
    fi
done

if [ "$collected" -ne 1 ]; then
    echo "수집 실패. 다음 실행에서 재시도한다."
    exit 1
fi

./.venv/bin/python scripts/build_dashboard.py || true
./.venv/bin/python scripts/build_case_dashboard.py || true

git add data/snapshots docs
if git diff --staged --quiet; then
    echo "변경 없음"
else
    git commit -q -m "chore(data): 29CM 랭킹 스냅샷 $(date +%Y-%m-%d)"
    git push -q origin main && echo "푸시 완료" || echo "푸시 실패 (다음 실행에서 함께 올라간다)"
fi
echo "=== 완료 ==="
