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
# 판정 파일이 있으면 성적표도 함께 낸다. 없으면 검증 기록 타일이 빈 채로
# 남는다. 화면이 최종 산출물이라 채점 결과가 여기 없으면 채점한 적이 없는
# 것과 같아 보인다.
VERDICTS="${VERDICTS:-runs/benchmark-model-v6/verdicts.json}"
SCORE_ARG=""
if [ -f "$VERDICTS" ]; then
    SCORE_ARG="--verdicts $VERDICTS"
    echo "판정 파일 $VERDICTS 로 성적표를 함께 낸다"
else
    echo "판정 파일이 없어 검증 기록 타일은 빈 채로 둔다 ($VERDICTS)"
fi

if [ -n "$WEEK" ]; then
    $PY scripts/export_frontend.py --json --week "$WEEK" $SCORE_ARG
else
    $PY scripts/export_frontend.py --json $SCORE_ARG
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

# 내 컴퓨터에서 바로 쓸 사본. 키가 들어 있어 남에게 보내면 안 되므로 이름에
# 로컬 을 넣는다. 번들러가 그 글자가 없으면 거부한다. ANTHROPIC_API_KEY 가
# 없으면 이 단계는 건너뛴다.
if [ -f .env ]; then set -a; . ./.env; set +a; fi
LOCAL="build/트렌드 모니터 ($HOLD) 로컬.html"
if [ -n "${ANTHROPIC_API_KEY:-}" ]; then
    echo
    $PY scripts/bundle_design.py "$WORK/patched.html" --assets design/runtime \
        -o "$LOCAL" --embed-key
else
    echo
    echo "ANTHROPIC_API_KEY 가 없어 로컬 사본은 만들지 않았다"
fi

echo
echo "열어 보려면"
echo "  open \"$LOCAL\"        내 컴퓨터용, 키 들어 있음"
echo "  open \"$OUT\"   보낼 것, 키 없음"
