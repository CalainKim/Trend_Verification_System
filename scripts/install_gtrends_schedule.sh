#!/usr/bin/env bash
# 구글 트렌드 수집을 한 시간마다 돌리도록 launchd 에 등록한다.
#
#   설치   bash scripts/install_gtrends_schedule.sh
#   해제   launchctl unload ~/Library/LaunchAgents/com.trendsignal.gtrends.plist
#   확인   launchctl list | grep trendsignal
#   로그   tail -f data/gtrends.log
#
# 29CM 일일 수집(com.trendsignal.collect)과 별개 작업이다. 둘 다 등록해도
# 서로 간섭하지 않는다.
#
# 한 시간마다 도는 이유가 있다. 구글은 연속 24회쯤 받으면 IP 단위로 막고
# 몇 시간 뒤에 푼다. 언제 풀리는지 알 수 없으므로 자주 두드려서 열린 창을
# 잡는 편이 낫다. 막혀 있으면 2초 만에 끝나므로 헛도는 비용이 거의 없다.
#
# 노트북이 잠들면 건너뛴다. 깨어난 뒤 놓친 실행을 한 번 따라잡는다.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLIST="$HOME/Library/LaunchAgents/com.trendsignal.gtrends.plist"
mkdir -p "$HOME/Library/LaunchAgents"

cat > "$PLIST" <<PLISTEOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.trendsignal.gtrends</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>$REPO/scripts/collect_gtrends_hourly.sh</string>
  </array>
  <key>StartCalendarInterval</key>
  <dict><key>Minute</key><integer>17</integer></dict>
  <key>WorkingDirectory</key><string>$REPO</string>
  <key>StandardOutPath</key><string>$REPO/data/gtrends.out.log</string>
  <key>StandardErrorPath</key><string>$REPO/data/gtrends.err.log</string>
</dict>
</plist>
PLISTEOF

launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"
echo "등록 완료: $PLIST"
echo "  매시 17분에 실행한다"
echo "  한 번에 속성 8개까지 (지역 3곳이므로 요청 24회)"
echo
launchctl list | grep trendsignal || echo "  (목록에 없으면 load 실패)"
echo
echo "진행 상황은 이렇게 본다"
echo "  tail -f $REPO/data/gtrends.log"
echo "  ./.venv/bin/python scripts/collect_gtrends.py --plan --limit 74"
