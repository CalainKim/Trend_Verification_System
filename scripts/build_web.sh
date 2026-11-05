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
# 검사 파일(*.test.mjs)은 빼야 한다. functions/ 아래의 파일은 전부 라우트가
# 되므로 그냥 복사하면 /api/complete.test 가 공개된다.
mkdir -p "$OUT/functions/api"
cp web/functions/api/complete.js "$OUT/functions/api/complete.js"
find "$OUT/functions" -type f | sed "s|^|  |"

# wrangler 는 functions/ 를 실행 위치 기준으로 찾는다. 배포 폴더 안에 있어도
# 바깥에서 돌리면 "No Functions. Shimming..." 을 내고 중계 없이 올라간다.
# 그러면 버튼이 조용히 죽는다. 그래서 설정을 폴더 안에 같이 둔다.
cat > "$OUT/wrangler.jsonc" <<WJ
{
  "name": "trend-monitor",
  "compatibility_date": "2026-11-04",
  "pages_build_output_dir": "."
}
WJ

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
echo "올릴 준비가 됐다. 반드시 폴더 안에서 돌린다"
echo "  cd $OUT && npx wrangler pages deploy ."
echo
echo "바깥에서 'wrangler pages deploy $OUT' 로 돌리면 중계 함수가 빠진 채"
echo "올라가고 심층 검증 버튼이 조용히 죽는다."
