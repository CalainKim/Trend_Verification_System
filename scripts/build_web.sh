#!/usr/bin/env bash
# 웹 배포판을 만든다. Cloudflare Pages 에 올릴 폴더 하나가 나온다.
#
#   ./scripts/build_web.sh
#   npx wrangler pages deploy build/web --project-name trend-monitor
#
# 키는 이 폴더에 들어가지 않는다. 화면은 같은 출처의 /api/complete 를 부르고,
# 키는 Cloudflare 환경변수에만 둔다. 내 컴퓨터에서 바로 쓰는 사본은 이것이
# 아니라 bundle_design.py --embed-key 로 따로 만든다.
set -euo pipefail
cd "$(dirname "$0")/.."

SRC="design/Trend Monitor v9.dc.html"
OUT="build/web"

rm -rf "$OUT"
mkdir -p "$OUT"

echo "### 1. 시안을 중계판으로 묶는다"
./.venv/bin/python scripts/bundle_design.py "$SRC" \
    --assets design/runtime --relay -o "$OUT/index.html"

echo
echo "### 2. 중계 함수를 복사한다"
cp -R web/functions "$OUT/functions"
find "$OUT/functions" -type f | sed "s|^|  |"

echo
echo "### 3. 키가 섞여 들어갔는지 확인한다"
# 배포 폴더에 키가 있으면 올리는 순간 되돌릴 수 없다. 올리기 전에 막는다.
#
# sk-ant- 만 찾으면 안내 문구("sk-ant- 로 시작합니다")에도 걸려서 멀쩡한
# 빌드가 멈춘다. 실제 키 모양, 즉 뒤에 20자 이상이 붙은 것만 잡는다.
KEYPAT='sk-ant-[A-Za-z0-9_-]{20,}'
if grep -rlE "$KEYPAT" "$OUT" 2>/dev/null | grep -q .; then
    echo "  멈춘다. 배포 폴더에 API 키가 들어 있다"
    grep -rlE "$KEYPAT" "$OUT"
    exit 1
fi
echo "  키 없음"

echo
du -sh "$OUT"
echo
echo "올릴 준비가 됐다. 다음 명령으로 배포한다"
echo "  npx wrangler pages deploy $OUT --project-name trend-monitor"
