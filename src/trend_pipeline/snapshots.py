"""스냅샷 CSV 입출력.

크롤링 데이터는 소급 수집이 불가능하므로 원본을 텍스트로도 남긴다.
SQLite 는 이 스냅샷들로부터 언제든 재구성할 수 있는 파생물로 취급한다.
"""

from __future__ import annotations

import csv
import json
import sqlite3
from pathlib import Path
from typing import Iterable, List, Sequence

from .models import RawRecord

SNAPSHOT_COLUMNS = (
    "observed_at",
    "collected_at",
    "channel",
    "keyword_raw",
    "entity",
    "metric_type",
    "metric_value",
    "metadata",
    "run_id",
)

# 한 번의 수집이 담는 기간이 채널마다 다르다. 29CM 은 그 시점의 순위만 주므로
# 관측일 하나가 파일 하나가 된다. 구글 트렌드와 네이버는 한 번 요청하면 몇 년치
# 시계열이 돌아오므로 같은 방식으로 쪼개면 네 줄짜리 파일이 1,095개 생긴다.
# 이 채널은 연도로 묶는다. 지난 연도는 더 바뀌지 않으므로 수집할 때마다 올해
# 파일만 갱신되고, git 이 다시 저장하는 양도 그만큼만 늘어난다.
HISTORY_CHANNELS = frozenset({"gtrends", "naver_datalab", "naver_shopping"})


def partition_key(channel: str, observed_at: str) -> str:
    """이 관측이 들어갈 스냅샷 파일의 이름에서 확장자를 뗀 부분."""
    return observed_at[:4] if channel in HISTORY_CHANNELS else observed_at[:10]


def snapshot_path(root: Path, channel: str, observed_at: str) -> Path:
    """채널과 날짜로 스냅샷 CSV 파일 경로를 정한다."""
    return Path(root) / channel / f"{partition_key(channel, observed_at)}.csv"


def write_snapshot(
    conn: sqlite3.Connection, root: Path, channel: str, observed_at: str
) -> Path:
    """해당 관측이 속한 구간의 스냅샷을 DB 내용 기준으로 다시 쓴다.

    이번 실행분만 쓰면 부분 수집(예: 상위 10개만)이 그 파일을 잘라먹는다.
    DB 를 원본으로 삼아 항상 그 구간 전체를 내보낸다.

    keyword_raw 는 정렬 키의 맨 뒤에 둔다. 29CM 은 앞의 세 열로 행이 하나로
    정해지지만 구글 트렌드는 같은 날 같은 지역에 키워드가 55개 들어 있어서
    순서가 정해지지 않는다. 순서가 흔들리면 내용이 같은데도 git 에 변경으로
    잡히므로 마지막 열로 묶어 둔다. 앞에 두면 29CM 기존 파일의 행 순서가
    전부 바뀐다.
    """
    key = partition_key(channel, observed_at)
    path = Path(root) / channel / f"{key}.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = conn.execute(
        f"""
        SELECT {", ".join(SNAPSHOT_COLUMNS)}
        FROM signal_raw
        WHERE channel = ? AND substr(observed_at, 1, ?) = ?
        ORDER BY observed_at, entity, metric_type, keyword_raw
        """,
        (channel, len(key), key),
    ).fetchall()
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(SNAPSHOT_COLUMNS)
        for row in rows:
            writer.writerow([row[c] for c in SNAPSHOT_COLUMNS])
    return path


def write_snapshots_for(
    conn: sqlite3.Connection, root: Path, records: Sequence[RawRecord]
) -> List[Path]:
    """records 가 건드린 (채널, 구간) 조합의 스냅샷을 갱신한다."""
    keys = sorted(
        {(r.channel, partition_key(r.channel, r.observed_date)) for r in records}
    )
    return [write_snapshot(conn, root, channel, key) for channel, key in keys]


def read_snapshot(path: Path) -> Iterable[RawRecord]:
    """스냅샷 CSV 한 개를 읽어 원천 기록(RawRecord)을 하나씩 돌려준다."""
    with Path(path).open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            yield RawRecord(
                channel=row["channel"],
                keyword_raw=row["keyword_raw"],
                entity=row["entity"],
                metric_type=row["metric_type"],
                metric_value=float(row["metric_value"]),
                observed_at=row["observed_at"],
                metadata=json.loads(row["metadata"] or "{}"),
                collected_at=row["collected_at"],
                run_id=row["run_id"] or None,
            )


def load_all(conn: sqlite3.Connection, root: Path) -> int:
    """스냅샷 디렉터리 전체를 DB 로 재적재하고 새로 들어간 행 수를 반환한다."""
    from . import storage

    total = 0
    for path in sorted(Path(root).rglob("*.csv")):
        total += storage.insert_raw(conn, list(read_snapshot(path)))
    return total
