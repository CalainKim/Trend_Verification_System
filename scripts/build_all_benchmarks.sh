#!/usr/bin/env bash
# 세 벤치마크를 같은 설정으로 다시 만든다.
#
#   ./scripts/build_all_benchmarks.sh
#
# 키워드를 더 수집한 뒤 이 스크립트만 돌리면 케이스가 늘어난다. 창 구성은
# 2026-10-29 에 고정했다. 확인 기간을 바꾸면 기저율이 달라져서 이전 성적과
# 비교할 수 없으므로, 바꿀 때는 이 파일을 고치고 이유를 커밋에 남긴다.
set -euo pipefail
cd "$(dirname "$0")/.."
PY=./.venv/bin/python

echo "### 1. 커머스 (29CM 순위, 확인 7일)"
# 수집이 29일뿐이라 창을 길게 잡을 수 없다. 수집이 쌓이면 늘린다.
$PY scripts/build_persistence_cases.py \
    --base 7 --detect 7 --hold 7 --step 21 --out benchmark

echo
echo "### 2. 검색 지수 주 벤치마크 (한국, 확인 28일)"
# 무신사가 말한 문제는 재고 확보 대응이고 시계가 며칠에서 몇 주다.
# 28일 확인이 그 시계와 맞고, 독립 창이 25개라 표본도 가장 많이 나온다.
$PY scripts/build_persistence_cases.py --source index \
    --base 4 --detect 2 --hold 4 --step 10 \
    --entities geo=KR --out benchmark-index

echo
echo "### 3. 검색 지수 보조 벤치마크 (3개 지역, 확인 84일)"
# 발주 판단에 쓰려면 더 긴 지평이 필요하다. 한국만으로는 독립 창이 10개뿐이라
# 표본이 모자라서 세 지역을 함께 쓴다. 같은 키워드의 다른 지역은 완전히
# 독립이 아니므로 성적표에 그 사실을 함께 적는다.
$PY scripts/build_persistence_cases.py --source index \
    --base 8 --detect 4 --hold 12 --step 24 \
    --entities geo=KR geo=US geo=WORLD --out benchmark-index-long

echo
echo "### 기준 전략"
for b in benchmark benchmark-index benchmark-index-long; do
    echo "--- $b ---"
    $PY scripts/score_verdicts.py --benchmark "$b" --baselines | tail -7
done
