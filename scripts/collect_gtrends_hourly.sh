#!/usr/bin/env bash
# 구글 트렌드를 조금씩 모은다. launchd 가 한 시간마다 부른다.
#
#   수동 실행   bash scripts/collect_gtrends_hourly.sh
#   로그        tail -f data/gtrends.log
#
# 한 번에 많이 받으려 하면 안 된다. 2026-10-28 실측으로 연속 24회쯤에서
# IP 단위로 막히고 몇 시간 뒤에 풀린다. 그래서 한 번에 세 속성만 받고,
# 막히면 재시도하지 않고 바로 끝낸다. 계속 두드리면 풀리는 시점만 늦춘다.
#
# 이미 받은 속성은 건너뛰므로 몇 번을 돌려도 같은 것을 다시 받지 않는다.
# 다 채운 뒤에는 마지막 주가 오래된 속성부터 새 주를 받는다(갱신 단계).
set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"
PY=./.venv/bin/python
LOG="$REPO/data/gtrends.log"

#: 한 번에 받을 속성 수. 지역이 셋이므로 요청은 이 값의 세 배다.
#: 실측 한도가 연속 24회쯤이라 8 개(24회)로 둔다. 창이 열려 있으면 한도까지
#: 받고, 막혀 있으면 첫 요청에서 끝난다.
BATCH="${GTRENDS_BATCH:-8}"

say() { printf '%s  %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" >> "$LOG"; }

say "시작 (배치 $BATCH)"

out=$($PY scripts/collect_gtrends.py \
        --limit 74 --props web --start 2022-01-01 \
        --missing-only --stop-on-block --max-attempts 1 \
        --max-new "$BATCH" 2>&1 \
      | tail -$((BATCH * 2 + 8)))
echo "$out" | sed 's/^/    /' >> "$LOG"

if echo "$out" | grep -q "한도에 걸려"; then
    say "한도에 걸렸다. 다음 시간에 이어 받는다"
    exit 0
fi

# 남은 속성이 없으면 사전의 웹 수집이 끝난 것이다. 그때부터 유튜브를 받는다.
remaining=$($PY - <<'EOF' 2>/dev/null
import sys
sys.path.insert(0, "src"); sys.path.insert(0, "scripts")
from trend_pipeline import storage
import collect_gtrends as cg
conn = storage.connect(None)
have = cg.already_have(conn, "gtrends", "")
print(len([t for t in cg.load_terms(None) if t["ko"] not in have]))
EOF
)
say "웹에 남은 속성 ${remaining:-?}개"

# 처음 채우기가 끝났으면 새 주를 덧붙인다. 이 단계가 없어서 2026-10-25 에서 멈춘 채
# 2주를 보냈고, 화면은 모든 상품을 "검색 교차에서 걸러짐" 으로 떨어뜨렸다.
# 마지막 주가 13일보다 오래된 속성만, 한 번에 BATCH 개씩 다시 받는다.
#
# 13일인 이유: 주간 값에는 그 주의 일요일 날짜가 붙고, 진행 중인 주는 수집기가 버린다.
# 그래서 받을 수 있는 마지막 완성 주는 언제나 오늘보다 7일에서 13일 전이다. 문턱을
# 그보다 짧게 잡으면 방금 받은 속성도 오래됐다고 보아 매시간 같은 것만 다시 받고,
# 뒤쪽 속성에는 차례가 오지 않는다. 2026-11-11 에 9일로 잡았다가 바로 확인했다.
#
# 구글 트렌드는
# 요청 창마다 눈금을 다시 맞추므로 덧붙이지 않고 그 속성을 통째로 바꾼다(--replace).
if [ "${remaining:-1}" = "0" ]; then
    out=$($PY scripts/collect_gtrends.py \
            --limit 74 --props web --start 2022-01-01 \
            --stale-days "${GTRENDS_STALE_DAYS:-13}" --replace \
            --stop-on-block --max-attempts 1 --max-new "$BATCH" 2>&1 \
          | tail -$((BATCH * 3 + 8)))
    echo "$out" | sed 's/^/    /' >> "$LOG"
    if echo "$out" | grep -q "한도에 걸려"; then
        say "갱신 중 한도에 걸렸다. 다음 시간에 이어 받는다"
        say "끝"
        exit 0
    fi
fi

if [ "${remaining:-1}" = "0" ]; then
    say "웹 수집 완료. 유튜브로 넘어간다"
    $PY scripts/collect_gtrends.py \
        --limit 74 --props youtube --start 2022-01-01 \
        --missing-only --stop-on-block --max-attempts 1 2>&1 \
      | head -12 | sed 's/^/    /' >> "$LOG"
fi

say "끝"
