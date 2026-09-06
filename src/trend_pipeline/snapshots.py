"""일별 스냅샷 CSV 입출력.

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


def snapshot_path(root: Path, channel: str, observed_at: str) -> Path:
    return Path(root) / channel / f"{observed_at[:10]}.csv"


def write_snapshot(
    conn: sqlite3.Connection, root: Path, channel: str, observed_day: str
) -> Path:
    """해당 관측일의 스냅샷을 DB 내용 기준으로 다시 쓴다.

    이번 실행분만 쓰면 부분 수집(예: 상위 10개만)이 그날 파일을 잘라먹는다.
    DB 를 원본으로 삼아 항상 그 날 전체를 내보낸다.
    """
    path = snapshot_path(root, channel, observed_day)
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = conn.execute(
        f"""
        SELECT {", ".join(SNAPSHOT_COLUMNS)}
        FROM signal_raw
        WHERE channel = ? AND substr(observed_at, 1, 10) = ?
        ORDER BY observed_at, entity, metric_type
        """,
        (channel, observed_day),
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
    """records 가 건드린 (채널, 관측일) 조합의 스냅샷을 갱신한다."""
    days = sorted({(r.channel, r.observed_date) for r in records})
    return [write_snapshot(conn, root, channel, day) for channel, day in days]


def read_snapshot(path: Path) -> Iterable[RawRecord]:
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
