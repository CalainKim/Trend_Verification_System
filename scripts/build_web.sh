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

echo "### 1. 시안을 중계판으로 묶는다 (/app/)"
# 첫 화면(/)은 랜딩이고 모니터는 /app/ 에 둔다. 중계 주소는 /api/complete
# 절대경로라 모니터 위치가 바뀌어도 그대로 닿는다.
mkdir -p "$OUT/app"
./.venv/bin/python scripts/bundle_design.py "$SRC" \
    --assets design/runtime --relay -o "$OUT/app/index.html"
# 랜딩과 같은 무신사 색감. 원본은 다시 받아오는 파일이라 여기서 덧씌운다
./.venv/bin/python scripts/apply_monitor_theme.py "$OUT/app/index.html"

echo
echo "### 1-1. 랜딩을 붙인다 (/)"
LANDING="design/landing"
cp "$LANDING/index.html" "$OUT/index.html"
# 비밀번호 입력 창. Pages 가 /login 으로 내준다
cp "$LANDING/login.html" "$OUT/login.html"
mkdir -p "$OUT/assets/fonts"
cp "$LANDING/assets/musinsa-logo.png" "$OUT/assets/"
cp -R "$LANDING/assets/brands" "$OUT/assets/brands"
cp -R "$LANDING/assets/stack" "$OUT/assets/stack"
# 글꼴은 V9 디자인 시스템 것을 그대로 쓴다. 랜딩은 이 경로를 두 번째로 찾는다
cp design/runtime/_ds/trendcheck-design-system-*/assets/fonts/PretendardVariable.woff2 "$OUT/assets/fonts/"
# 첫 화면 3D 영상. 없으면 랜딩이 캔버스 장면으로 대신 돌기 때문에 멈추지 않고 알리기만 한다
if ls "$LANDING"/assets/hero/*.mp4 >/dev/null 2>&1; then
    cp -R "$LANDING/assets/hero" "$OUT/assets/hero"
    find "$OUT/assets/hero" -name '*.mp4' | sed "s|^|  |"
else
    echo "  첫 화면 영상이 없다. 캔버스 장면으로 대신 보인다"
fi

echo
echo "### 2. 중계 함수와 비밀번호 게이트를 복사한다"
# 검사 파일(*.test.mjs)은 빼야 한다. functions/ 아래의 파일은 전부 라우트가
# 되므로 그냥 복사하면 /api/complete.test 가 공개된다. 그래서 하나씩 집는다.
#
# 게이트(_middleware.js)를 빠뜨리면 /app 과 /api 가 열린 채 올라간다.
# 아래에서 다시 확인한다.
mkdir -p "$OUT/functions/api" "$OUT/functions/auth" "$OUT/functions/_shared"
cp web/functions/api/complete.js "$OUT/functions/api/complete.js"
cp web/functions/_middleware.js "$OUT/functions/_middleware.js"
cp web/functions/_shared/session.js "$OUT/functions/_shared/session.js"
cp web/functions/auth/login.js "$OUT/functions/auth/login.js"
cp web/functions/auth/logout.js "$OUT/functions/auth/logout.js"
find "$OUT/functions" -type f | sed "s|^|  |"
if [ ! -f "$OUT/functions/_middleware.js" ]; then
    echo "  멈춘다. 비밀번호 게이트가 빠졌다"
    exit 1
fi

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
# 로컬 시험용 비밀값 파일이 배포 폴더에 있으면 /.dev.vars 로 그대로 내려받아진다.
# 2026-11-08 wrangler pages dev 로 확인했다. 로컬 시험은 --binding 으로 넣는다.
if find "$OUT" -name '.dev.vars*' -o -name '.env*' | grep -q .; then
    echo "  멈춘다. 배포 폴더에 비밀값 파일이 있다"
    find "$OUT" -name '.dev.vars*' -o -name '.env*'
    exit 1
fi
echo "  비밀값 파일 없음"

echo
du -sh "$OUT"
echo
echo "올릴 준비가 됐다. 반드시 폴더 안에서 돌린다"
echo "  cd $OUT && npx wrangler pages deploy ."
echo
echo "바깥에서 'wrangler pages deploy $OUT' 로 돌리면 중계 함수가 빠진 채"
echo "올라가고 심층 검증 버튼이 조용히 죽는다."
