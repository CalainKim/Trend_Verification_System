#!/usr/bin/env bash
# 보여 줄 파일 하나를 만든다.
#
#   ./scripts/build_viewer.sh                  최신 주
#   ./scripts/build_viewer.sh 2026-11-01       주 지정
#
# 결과는 build/트렌드 모니터 (날짜).html 이다. 서버도 설치도 필요 없이
# 더블클릭하면 열린다. 검증 파트에 보내거나 미팅에서 열 때 쓴다.
#
# 재료가 전부 저장소에 있으므로 clone 만 하면 어디서든 다시 만들 수 있다.
# 화면 원본은 design/ 에 사본으로 두었고, 고치는 자리는 Claude Design 이다.
# 거기서 새로 폴리싱했으면 design/ 의 사본을 바꾸고 이 스크립트를 다시 돌린다.
set -euo pipefail
cd "$(dirname "$0")/.."
PY=./.venv/bin/python
SRC="design/Trend Monitor v8.dc.html"
WORK=build/.viewer
mkdir -p "$WORK"

WEEK="${1:-}"
if [ -n "$WEEK" ]; then
    $PY scripts/export_frontend.py --json --week "$WEEK"
else
    $PY scripts/export_frontend.py --json
fi

# 내보내기가 기준으로 삼은 확인 날짜를 그대로 파일 이름에 쓴다. 손으로 적으면
# 데이터와 이름이 어긋난다.
HOLD=$($PY -c "import json;print(json.load(open('build/frontend_data.json'))['weeks'][2])" 2>/dev/null \
       || grep -o '확인 [0-9-]*' build/frontend_data.js | head -1 | cut -d' ' -f2)
OUT="build/트렌드 모니터 ($HOLD).html"

echo
$PY scripts/patch_design.py "$SRC" -o "$WORK/patched.html"
echo
$PY scripts/bundle_design.py "$WORK/patched.html" --assets design/runtime -o "$OUT"
echo
echo "열어 보려면"
echo "  open \"$OUT\""
