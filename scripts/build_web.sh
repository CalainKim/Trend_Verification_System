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

# 실제 자료를 먼저 내보내고 점검한다. 배포 폴더를 지우기 전에 해야 막혔을 때 지난 빌드가 남는다
VERDICTS="${VERDICTS:-runs/benchmark-model-v6/verdicts.json}"
SCORE_ARG=""
[ -f "$VERDICTS" ] && SCORE_ARG="--verdicts $VERDICTS"
# 주를 고를 수 있다. 검색 수집이 늦어 최신 주의 기준일까지 검색 자료가 없으면
# 모든 상품이 "검색 교차에서 걸러짐" 이 된다. 그때는 자료가 다 있는 주로 만든다.
#   WEEK=2026-11-03 ./scripts/build_web.sh
WEEK_ARG=""
[ -n "${WEEK:-}" ] && WEEK_ARG="--week $WEEK"
./.venv/bin/python scripts/export_frontend.py --json $WEEK_ARG $SCORE_ARG
# 검색 자료가 기준일까지 없는 속성이 많으면 화면 대부분이 "검색 교차에서 걸러짐" 이 된다.
# 2026-11-11 에 아무 경고 없이 그런 화면이 올라갔다. 절반이 안 되면 멈추고 고칠 길을 알려 준다.
# 그래도 올려야 하면 ALLOW_STALE_SEARCH=1 을 붙인다.
./.venv/bin/python - <<'PYCHK' || [ "${ALLOW_STALE_SEARCH:-}" = "1" ] || exit 1
import json, sys
d = json.load(open("build/frontend_data.json", encoding="utf-8"))
w, G = d["WEEK"], d["G"]
ok = sum(1 for v in G.values() if v["last"] >= w["baseISO"])
last = max((v["last"] for v in G.values()), default="?")
print(f"  검색 자료 점검: 기준일 {w['baseISO']} 까지 있는 속성 {ok}/{len(G)} (가장 최근 {last})")
if ok * 2 < len(G):
    print("  멈춘다. 이대로면 대부분의 상품이 검색 교차에서 걸러진다")
    print("  구글 트렌드 갱신을 기다리거나 (data/gtrends.log), 자료가 다 있는 주로 만든다")
    print(f"    예: WEEK=<확인일> ./scripts/build_web.sh   지금 주의 확인일은 {w['holdISO']}")
    sys.exit(1)
PYCHK

rm -rf "$OUT"
mkdir -p "$OUT"

echo "### 1. 시안을 중계판으로 묶는다 (/app/)"
# 첫 화면(/)은 랜딩이고 모니터는 /app/ 에 둔다. 중계 주소는 /api/complete
# 절대경로라 모니터 위치가 바뀌어도 그대로 닿는다.
mkdir -p "$OUT/app"
# 실제 수집 자료와 상품 사진을 시안에 끼워 넣은 뒤 묶는다. build_viewer.sh 와 같은 순서다.
# 이 두 단계를 건너뛰면 시안 원본의 예시 자료로 올라가고 상품 사진 칸이 모두 빈다.
# 2026-11-11 운영에서 옷 사진이 안 뜨던 원인이다.
WORK="build/.web"
mkdir -p "$WORK"
./.venv/bin/python scripts/patch_design.py "$SRC" -o "$WORK/patched.html"
./.venv/bin/python scripts/bundle_design.py "$WORK/patched.html" \
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
# 로그인 화면 아래 "Inside Trend Monitor" 가 쓰는 실제 모니터 화면 다섯 장
cp -R "$LANDING/assets/monitor" "$OUT/assets/monitor"
# 홈 화면 앱(PWA). 서비스 워커는 범위가 사이트 전체가 되도록 맨 위에 둔다
cp "$LANDING/manifest.webmanifest" "$LANDING/sw.js" "$LANDING/offline.html" "$OUT/"
cp -R "$LANDING/assets/pwa" "$OUT/assets/pwa"
# 서비스 워커를 브라우저가 오래 기억하면 고친 것이 늦게 퍼진다. 매번 새로 묻게 한다
cat > "$OUT/_headers" <<'HD'
/sw.js
  Cache-Control: no-cache
/manifest.webmanifest
  Content-Type: application/manifest+json
  Cache-Control: no-cache
HD
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
