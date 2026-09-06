"""검증 단계로 데이터를 내보내는 계층.

여기가 데이터 누수를 막는 마지막 관문이다. 수집 단계에서 이미 걸렀더라도
내보내기 직전에 observed_at < T_cut 을 명시적으로 한 번 더 검증한다
(계획서 '코딩 시 지켜야 할 것' 2번).
"""

from __future__ import annotations

import csv
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

_EXPORT_COLUMNS = (
    "observed_at",
    "channel",
    "keyword_raw",
    "entity",
    "metric_type",
    "metric_value",
    "metadata",
)


class LeakageError(RuntimeError):
    """T_cut 이후 데이터가 산출물에 섞이려 할 때."""


@dataclass(frozen=True)
class TrendCase:
    case_id: str
    keyword: str
    t_peak: str      # 'YYYY-MM-DD'
    t_cut: str       # 'YYYY-MM-DD', 통상 t_peak - 4주
    label: str       # 'real' | 'noise'  -- 산출물에 절대 포함하지 않는다
    label_reason: str = ""


def fetch_before_cut(
    conn: sqlite3.Connection,
    t_cut: str,
    keywords: Sequence[str],
    channel: Optional[str] = None,
) -> List[sqlite3.Row]:
    """T_cut '미만'(경계 제외) 관측치만 조회한다."""
    if not keywords:
        return []
    placeholders = ",".join("?" for _ in keywords)
    sql = f"""
        SELECT {", ".join(_EXPORT_COLUMNS)}
        FROM signal_raw
        WHERE observed_at < ?
          AND keyword_raw IN ({placeholders})
    """
    params: List[object] = [t_cut, *keywords]
    if channel is not None:
        sql += " AND channel = ?"
        params.append(channel)
    sql += " ORDER BY channel, keyword_raw, observed_at"
    return list(conn.execute(sql, params))


def assert_no_leakage(rows: Iterable[sqlite3.Row], t_cut: str) -> None:
    """내보내기 직전 재검증. 한 건이라도 T_cut 이후면 전체를 중단시킨다."""
    offenders = [r["observed_at"] for r in rows if r["observed_at"] >= t_cut]
    if offenders:
        raise LeakageError(
            f"T_cut={t_cut} 이후 관측치 {len(offenders)}건이 산출물에 포함되려 했다. "
            f"예: {sorted(set(offenders))[:5]}"
        )


def write_case_bundle(
    conn: sqlite3.Connection,
    case: TrendCase,
    out_root: Path,
    keywords: Optional[Sequence[str]] = None,
) -> Path:
    """케이스 폴더를 만든다.

    meta.json 에는 label 을 쓰지 않는다. 정답은 수집 담당자만 DB(trend_case)에 보관하고,
    검증팀에 전달되는 폴더는 블라인드 상태여야 한다.
    """
    keywords = list(keywords) if keywords else [case.keyword]
    case_dir = Path(out_root) / case.case_id
    case_dir.mkdir(parents=True, exist_ok=True)

    rows = fetch_before_cut(conn, case.t_cut, keywords)
    assert_no_leakage(rows, case.t_cut)

    by_channel: dict = {}
    for row in rows:
        by_channel.setdefault(row["channel"], []).append(row)

    for channel, channel_rows in by_channel.items():
        with (case_dir / f"{channel}.csv").open("w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(_EXPORT_COLUMNS)
            for row in channel_rows:
                writer.writerow([row[c] for c in _EXPORT_COLUMNS])

    meta = {
        "case_id": case.case_id,
        "keyword": case.keyword,
        "keywords_included": keywords,
        "t_cut": case.t_cut,
        "channels": sorted(by_channel),
        "row_counts": {ch: len(rs) for ch, rs in sorted(by_channel.items())},
        "note": "T_cut 이전 관측치만 포함. 정답 라벨과 T_peak 은 의도적으로 제외했다.",
    }
    (case_dir / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return case_dir
