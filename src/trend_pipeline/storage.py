"""SQLite 공통 저장 레이어.

소스별 수집 모듈은 분리하되, 저장은 전부 이 모듈을 통한다.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

from .models import RawRecord, utcnow_iso

DEFAULT_DB_PATH = Path(__file__).resolve().parents[2] / "data" / "signals.sqlite"
_SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


def new_run_id() -> str:
    """한 번의 수집 실행을 묶는 키."""
    return f"{utcnow_iso()}_{uuid.uuid4().hex[:8]}"


def connect(db_path: Optional[Path] = None) -> sqlite3.Connection:
    path = Path(db_path) if db_path is not None else DEFAULT_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(_SCHEMA_PATH.read_text(encoding="utf-8"))
    conn.commit()


def insert_raw(conn: sqlite3.Connection, records: Iterable[RawRecord]) -> int:
    """RawRecord 들을 저장하고 '새로 들어간' 행 수를 반환한다.

    UNIQUE(channel, keyword_raw, entity, metric_type, observed_at) 로 중복을 막으므로
    같은 날 수집기를 두 번 돌려도 안전하다(멱등).
    """
    rows: List[Sequence[object]] = []
    for rec in records:
        rows.append(
            (
                rec.observed_at,
                rec.collected_at,
                rec.channel,
                rec.keyword_raw,
                rec.entity,
                rec.metric_type,
                rec.metric_value,
                json.dumps(rec.metadata, ensure_ascii=False, sort_keys=True),
                rec.run_id,
            )
        )
    if not rows:
        return 0

    before = conn.total_changes
    conn.executemany(
        """
        INSERT OR IGNORE INTO signal_raw
            (observed_at, collected_at, channel, keyword_raw, entity,
             metric_type, metric_value, metadata, run_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    conn.commit()
    return conn.total_changes - before


def channel_coverage(conn: sqlite3.Connection) -> List[sqlite3.Row]:
    """채널별로 몇 건이 어느 기간에 쌓였는지. 수집이 실제로 도는지 확인용."""
    return list(
        conn.execute(
            """
            SELECT channel,
                   COUNT(*)            AS n_rows,
                   COUNT(DISTINCT keyword_raw) AS n_keywords,
                   MIN(observed_at)    AS first_observed,
                   MAX(observed_at)    AS last_observed,
                   MAX(collected_at)   AS last_collected
            FROM signal_raw
            GROUP BY channel
            ORDER BY channel
            """
        )
    )
