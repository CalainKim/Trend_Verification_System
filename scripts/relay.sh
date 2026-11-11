#!/usr/bin/env bash
# 심층 검증(Claude API) 스위치. 평소에는 닫아 두고 시연할 때만 연다.
#
#   ./scripts/relay.sh open 2h                 지금부터 2시간 연다 (90m 처럼 분도 된다)
#   ./scripts/relay.sh open 2026-11-12T16:00   이 시각까지 연다 (한국 시각)
#   ./scripts/relay.sh close                   바로 닫는다
#
# 하는 일은 둘이다. Cloudflare 비밀값 RELAY_OPEN_UNTIL 에 마감 시각을 넣고,
# 그 값이 반영되도록 다시 배포한다. 중계(complete.js)는 마감 시각이 지나면
# 저절로 닫으므로 닫는 것을 잊어도 돈이 계속 나가지 않는다.
set -euo pipefail
cd "$(dirname "$0")/.."

PROJECT="trend-monitor"
usage() { sed -n '2,7p' "$0" | sed 's/^# \{0,1\}//'; }

case "${1:-}" in
  open)
    [ -n "${2:-}" ] || { usage; exit 2; }
    UNTIL=$(python3 - "$2" <<'PY'
import re, sys
from datetime import datetime, timedelta, timezone
KST = timezone(timedelta(hours=9))
a = sys.argv[1]
m = re.fullmatch(r"(\d+)\s*([hm])", a)
if m:
    n, unit = int(m.group(1)), m.group(2)
    until = datetime.now(timezone.utc) + (timedelta(hours=n) if unit == "h" else timedelta(minutes=n))
else:
    try:
        until = datetime.fromisoformat(a)
    except ValueError:
        sys.exit(f"시각을 읽지 못했다: {a}  예) 2h, 90m, 2026-11-12T16:00")
    if until.tzinfo is None:
        until = until.replace(tzinfo=KST)
if until <= datetime.now(timezone.utc):
    sys.exit("이미 지난 시각이다")
if until - datetime.now(timezone.utc) > timedelta(hours=12):
    sys.exit("12시간보다 길게 열지 않는다. 미팅마다 다시 연다")
print(until.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
PY
)
    ;;
  close)
    UNTIL="closed"
    ;;
  *)
    usage; exit 2 ;;
esac

echo "### 1. 마감 시각을 넣는다"
printf '%s' "$UNTIL" | npx wrangler pages secret put RELAY_OPEN_UNTIL --project-name "$PROJECT" >/dev/null
echo "  RELAY_OPEN_UNTIL = $UNTIL"

echo "### 2. 반영되도록 다시 배포한다"
# 빌드가 막혀도(검색 자료 점검 등) 멈추지 않는다. 멈추면 위에서 바꾼 비밀값이 반영되지
# 않아 close 를 했는데도 열린 채로 남는다. build_web.sh 는 막힐 때 지난 빌드를 남기므로
# 그것을 그대로 다시 올린다.
if ! ./scripts/build_web.sh >/dev/null; then
  echo "  새로 빌드하지 못해 지난 빌드를 그대로 다시 올린다"
  echo "  (검색 자료 점검에 걸렸다면 WEEK=<확인일> 을 앞에 붙여 다시 돌리면 그 주로 만든다)"
fi
[ -f build/web/index.html ] || { echo "  올릴 빌드가 없다. ./scripts/build_web.sh 를 먼저 돌린다"; exit 1; }
(cd build/web && npx wrangler pages deploy . --project-name "$PROJECT" --branch main --commit-dirty=true 2>&1 | grep -E "Deployment complete|ERROR" || true)

if [ "$UNTIL" = "closed" ]; then
  echo "닫았다. 심층 검증 버튼은 '지금 닫혀 있습니다' 를 보여 준다"
else
  KST=$(python3 -c "from datetime import datetime,timezone,timedelta; print(datetime.strptime('$UNTIL','%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc).astimezone(timezone(timedelta(hours=9))).strftime('%m월 %d일 %H:%M'))")
  echo "열었다. 한국 시각 $KST 에 저절로 닫힌다"
fi
