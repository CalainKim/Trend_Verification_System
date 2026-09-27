#!/bin/bash
# 로컬 일일 수집을 launchd 에 등록한다.
#
#   설치   bash scripts/install_local_schedule.sh
#   해제   launchctl unload ~/Library/LaunchAgents/com.trendsignal.collect.plist
#   확인   launchctl list | grep trendsignal
#   로그   tail -f data/collect.log
#
# 노트북이 꺼져 있으면 건너뛴다. 다만 launchd 는 깨어난 뒤 놓친 실행을 한 번
# 따라잡아 주므로 cron 보다 누락이 적다.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLIST="$HOME/Library/LaunchAgents/com.trendsignal.collect.plist"
mkdir -p "$HOME/Library/LaunchAgents"

cat > "$PLIST" <<PLISTEOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.trendsignal.collect</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>$REPO/scripts/collect_and_push.sh</string>
  </array>
  <key>StartCalendarInterval</key>
  <array>
    <dict><key>Hour</key><integer>10</integer><key>Minute</key><integer>0</integer></dict>
    <dict><key>Hour</key><integer>22</integer><key>Minute</key><integer>0</integer></dict>
  </array>
  <key>WorkingDirectory</key><string>$REPO</string>
  <key>StandardOutPath</key><string>$REPO/data/launchd.out.log</string>
  <key>StandardErrorPath</key><string>$REPO/data/launchd.err.log</string>
</dict>
</plist>
PLISTEOF

launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"
echo "등록 완료: $PLIST"
echo "  하루 두 번 (10:00, 22:00) 실행"
launchctl list | grep trendsignal || echo "  (목록에 없으면 load 실패)"
