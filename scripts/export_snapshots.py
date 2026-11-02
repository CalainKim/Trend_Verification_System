#!/usr/bin/env python3
"""DB 에 있는 관측을 전부 스냅샷 CSV 로 내보낸다.

수집기가 스냅샷을 쓰기 전에 모아 둔 자료를 뒤늦게 텍스트로 남길 때 쓴다.
DB 는 저장소에서 제외되므로, 다른 컴퓨터에서 이어서 작업하려면 스냅샷이
git 에 올라가 있어야 한다. 받는 쪽은 clone 한 뒤 아래를 실행한다.

    ./scripts/load_snapshots.py

쓰는 쪽은 이렇게 한다.

    ./scripts/export_snapshots.py                  # 모든 채널
    ./scripts/export_snapshots.py gtrends          # 채널 지정
    ./scripts/export_snapshots.py --db other.sqlite

이미 있는 파일은 DB 내용으로 덮어쓴다. 내용이 같으면 바이트도 같으므로
git 에 변경으로 잡히지 않는다.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from trend_pipeline import snapshots, storage  # noqa: E402


def partitions(conn, channels):
    """(채널, 구간키) 목록을 DB 에서 뽑는다."""
    if not channels:
        channels = [
            r[0] for r in conn.execute("SELECT DISTINCT channel FROM signal_raw ORDER BY 1")
        ]
    found = []
    for channel in channels:
        width = len(snapshots.partition_key(channel, "0000-00-00"))
        keys = conn.execute(
            "SELECT DISTINCT substr(observed_at, 1, ?) FROM signal_raw"
            " WHERE channel = ? ORDER BY 1",
            (width, channel),
        ).fetchall()
        if not keys:
            print(f"경고. 채널 {channel} 에 해당하는 행이 없다")
        found += [(channel, k[0]) for k in keys]
    return found


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("channels", nargs="*", help="내보낼 채널. 비우면 전부")
    ap.add_argument("--db", type=Path, default=None, help="읽을 DB 경로")
    ap.add_argument(
        "--out", type=Path, default=ROOT / "data" / "snapshots", help="스냅샷 디렉터리"
    )
    args = ap.parse_args(argv)

    conn = storage.connect(args.db)
    todo = partitions(conn, args.channels)
    if not todo:
        print("내보낼 것이 없다")
        return 1

    by_channel: dict[str, int] = {}
    for channel, key in todo:
        path = snapshots.write_snapshot(conn, args.out, channel, key)
        # 물리적 줄이 아니라 CSV 레코드를 센다. metadata 는 JSON 문자열이라
        # 줄바꿈이 들어오면 한 레코드가 여러 줄로 쓰인다.
        with path.open(newline="", encoding="utf-8") as fh:
            rows = sum(1 for _ in csv.DictReader(fh))
        by_channel[channel] = by_channel.get(channel, 0) + rows

    print(f"{args.out} 에 내보냈다")
    for channel, rows in sorted(by_channel.items()):
        files = sum(1 for c, _ in todo if c == channel)
        print(f"  {channel:<16} 파일 {files:>4}개   {rows:>7}행")
    print(f"  {'합계':<16} 파일 {len(todo):>4}개   {sum(by_channel.values()):>7}행")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
