#!/bin/bash
# 대시보드를 로컬 브라우저로 연다.
#
#   bash scripts/serve.sh
#
# 화면을 최신 데이터로 다시 만들고 http://localhost:8765 로 띄운다.
# 종료는 Ctrl+C.
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"

PY="./.venv/bin/python"
[ -x "$PY" ] || PY="python3"

echo "화면 생성 중..."
"$PY" scripts/build_dashboard.py
"$PY" scripts/build_case_dashboard.py

PORT=8765
echo
echo "  수집 현황   http://localhost:$PORT/index.html"
echo "  케이스 분석 http://localhost:$PORT/cases.html"
echo
command -v open >/dev/null && (sleep 1 && open "http://localhost:$PORT/index.html") &
exec "$PY" -m http.server "$PORT" --directory docs
