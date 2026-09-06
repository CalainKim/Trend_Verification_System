"""저장/누수차단 계층의 핵심 계약 테스트."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from trend_pipeline import export, storage  # noqa: E402
from trend_pipeline.models import RawRecord, RecordError  # noqa: E402


@pytest.fixture()
def conn(tmp_path):
    c = storage.connect(tmp_path / "t.sqlite")
    storage.init_db(c)
    yield c
    c.close()


def _rec(observed_at, value, keyword="발라클라바", channel="naver_datalab"):
    return RawRecord(
        channel=channel,
        keyword_raw=keyword,
        metric_type="search_index",
        metric_value=value,
        observed_at=observed_at,
    )


def test_insert_is_idempotent(conn):
    recs = [_rec("2024-10-01", 10), _rec("2024-10-02", 20)]
    assert storage.insert_raw(conn, recs) == 2
    assert storage.insert_raw(conn, recs) == 0  # 같은 관측치 재삽입은 무시


def test_observed_at_and_collected_at_are_independent(conn):
    """과거 구간을 오늘 소급 수집해도 observed_at 은 과거로 남아야 한다."""
    storage.insert_raw(conn, [_rec("2024-10-01", 10)])
    row = conn.execute("SELECT observed_at, collected_at FROM signal_raw").fetchone()
    assert row["observed_at"] == "2024-10-01"
    assert row["collected_at"] > "2025-01-01"


def test_fetch_before_cut_excludes_boundary_and_after(conn):
    storage.insert_raw(
        conn,
        [_rec("2024-10-01", 1), _rec("2024-10-31", 2), _rec("2024-11-01", 3), _rec("2024-11-15", 4)],
    )
    rows = export.fetch_before_cut(conn, "2024-11-01", ["발라클라바"])
    assert [r["observed_at"] for r in rows] == ["2024-10-01", "2024-10-31"]


def test_assert_no_leakage_raises(conn):
    storage.insert_raw(conn, [_rec("2024-11-15", 4)])
    rows = list(conn.execute("SELECT observed_at FROM signal_raw"))
    with pytest.raises(export.LeakageError):
        export.assert_no_leakage(rows, "2024-11-01")


def test_case_bundle_has_no_label_or_peak(conn, tmp_path):
    storage.insert_raw(
        conn,
        [_rec("2024-10-01", 1), _rec("2024-10-20", 5), _rec("2024-11-20", 99)],
    )
    case = export.TrendCase(
        case_id="case_001_balaclava",
        keyword="발라클라바",
        t_peak="2024-11-29",
        t_cut="2024-11-01",
        label="real",
        label_reason="시즌 넘어서까지 지속",
    )
    out = export.write_case_bundle(conn, case, tmp_path / "cases")
    meta = (out / "meta.json").read_text(encoding="utf-8")
    assert "real" not in meta and "t_peak" not in meta and "2024-11-29" not in meta
    csv_text = (out / "naver_datalab.csv").read_text(encoding="utf-8")
    assert "2024-11-20" not in csv_text  # T_cut 이후 관측치는 빠져야 한다
    assert "2024-10-20" in csv_text


def test_bad_observed_at_rejected():
    with pytest.raises(RecordError):
        _rec("2024-10", 1)


def test_snapshot_is_not_truncated_by_partial_run(conn, tmp_path):
    """부분 수집이 그날 스냅샷을 잘라먹으면 안 된다."""
    from trend_pipeline import snapshots

    full = [_rec("2024-10-01", i, keyword=f"kw{i}") for i in range(10)]
    storage.insert_raw(conn, full)
    snapshots.write_snapshots_for(conn, tmp_path, full)

    partial = full[:2]
    paths = snapshots.write_snapshots_for(conn, tmp_path, partial)
    assert len(paths) == 1
    assert sum(1 for _ in paths[0].read_text(encoding="utf-8").splitlines()) == 11  # header + 10


def test_snapshot_round_trip(conn, tmp_path):
    from trend_pipeline import snapshots

    recs = [_rec("2024-10-01", 1), _rec("2024-10-02", 2)]
    storage.insert_raw(conn, recs)
    path = snapshots.write_snapshot(conn, tmp_path, "naver_datalab", "2024-10-01")
    restored = list(snapshots.read_snapshot(path))
    assert len(restored) == 1
    assert restored[0].observed_at == "2024-10-01"
    assert restored[0].keyword_raw == "발라클라바"
