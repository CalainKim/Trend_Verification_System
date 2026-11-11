"""구글 트렌드 증분 수집 검증. 네트워크를 쓰지 않는다.

한도가 빠듯한 채널이라 어떤 속성을 몇 개나 받을지가 중요하다. 이미 받은 것을
다시 받으면 한도만 쓰고 새 자료는 없다. 상한을 잘못 세면 창이 열려 있는데도
일찍 멈추거나, 반대로 한도를 넘겨 다음 창까지 늦춘다.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import collect_gtrends as cg  # noqa: E402
from trend_pipeline import storage  # noqa: E402
from trend_pipeline.collectors.gtrends import GoogleTrendsUnavailable  # noqa: E402
from trend_pipeline.models import RawRecord  # noqa: E402


@pytest.fixture()
def db(tmp_path):
    p = tmp_path / "g.sqlite"
    c = storage.connect(p)
    storage.init_db(c)
    yield p, c
    c.close()


def seed(conn, keyword, gprop=""):
    ent = f"geo=KR;prop={gprop}" if gprop else "geo=KR"
    storage.insert_raw(conn, [
        RawRecord(channel="gtrends", keyword_raw=keyword, entity=ent,
                  metric_type="search_index", metric_value=50.0,
                  observed_at="2026-01-01")])


def test_already_have_separates_props(db):
    _, conn = db
    seed(conn, "헨리넥")                     # 웹
    seed(conn, "와플", gprop="youtube")      # 유튜브
    assert cg.already_have(conn, "gtrends", "") == {"헨리넥"}
    assert cg.already_have(conn, "gtrends", "youtube") == {"와플"}


class FakeCollector:
    """collect 가 호출된 속성을 기록한다. 네트워크를 쓰지 않는다."""
    min_interval_sec = 0.0

    def __init__(self, fail_after=None):
        self.seen = []
        self.fail_after = fail_after

    def collect(self, keywords, start, end, geos=(), keywords_by_geo=None,
                candidate=None, run_id=None, gprop=""):
        self.seen.append((candidate, gprop))
        if self.fail_after is not None and len(self.seen) > self.fail_after:
            raise GoogleTrendsUnavailable("429 code 429")
        return iter(())


def run(monkeypatch, db, argv, fake):
    path, _ = db
    monkeypatch.setattr(cg, "GoogleTrendsCollector", lambda *a, **k: fake)
    cg.main(["--db", str(path), "--start", "2022-01-01"] + argv)


def test_max_new_caps_attempted_keywords(monkeypatch, db):
    """창이 열려 있어도 상한만큼만 받는다."""
    fake = FakeCollector()
    run(monkeypatch, db, ["--limit", "74", "--props", "web",
                          "--missing-only", "--max-new", "3"], fake)
    assert len(fake.seen) == 3


def test_missing_only_skips_collected(monkeypatch, db):
    _, conn = db
    terms = cg.load_terms(None)
    for t in terms[:4]:
        seed(conn, t["ko"])
    fake = FakeCollector()
    run(monkeypatch, db, ["--limit", "74", "--props", "web",
                          "--missing-only", "--max-new", "3"], fake)
    done = {t["ko"] for t in terms[:4]}
    assert len(fake.seen) == 3
    assert not ({c for c, _ in fake.seen} & done)


def test_stop_on_block_halts_immediately(monkeypatch, db):
    """429 를 만나면 남은 속성을 두드리지 않는다. 풀리는 시점만 늦춘다."""
    fake = FakeCollector(fail_after=2)
    run(monkeypatch, db, ["--limit", "74", "--props", "web",
                          "--missing-only", "--max-new", "20",
                          "--stop-on-block"], fake)
    assert len(fake.seen) == 3        # 두 번 성공하고 세 번째에서 멈춘다


def test_without_stop_on_block_keeps_going(monkeypatch, db):
    fake = FakeCollector(fail_after=1)
    run(monkeypatch, db, ["--limit", "74", "--props", "web",
                          "--missing-only", "--max-new", "5"], fake)
    assert len(fake.seen) == 5


def test_max_new_counts_keywords_not_requests(monkeypatch, db):
    """속성 하나에 속성값이 둘이면 호출은 둘이지만 상한은 하나로 센다."""
    fake = FakeCollector()
    run(monkeypatch, db, ["--limit", "74", "--props", "web", "youtube",
                          "--missing-only", "--max-new", "2"], fake)
    assert len({c for c, _ in fake.seen}) == 2
    assert len(fake.seen) == 4


# ---------------------------------------------------------------- 새 주 갱신 (2026-11-11)
# 처음 채우기만 있던 탓에 시계열이 2026-10-25 에서 멈췄고, 화면은 최신 주의 기준일까지
# 검색 자료가 없다며 모든 상품을 "검색 교차에서 걸러짐" 으로 떨어뜨렸다.

def seed_at(conn, keyword, observed_at, value=50.0, geo="KR"):
    storage.insert_raw(conn, [
        RawRecord(channel="gtrends", keyword_raw=keyword, entity=f"geo={geo}",
                  metric_type="search_index", metric_value=value,
                  observed_at=observed_at)])


def test_fresh_terms_picks_only_recent(db):
    _, conn = db
    seed_at(conn, "기모", "2026-10-25")      # 17일 전
    seed_at(conn, "니트", "2026-11-08")      # 3일 전
    assert cg.fresh_terms(conn, "gtrends", "", 9, "2026-11-11") == {"니트"}


class RecCollector(FakeCollector):
    """새 창으로 받은 값을 돌려준다. fail 이면 한도에 걸린다."""

    def __init__(self, fail=False):
        super().__init__()
        self.fail = fail

    def collect(self, keywords, start, end, geos=(), keywords_by_geo=None,
                candidate=None, run_id=None, gprop=""):
        self.seen.append((candidate, gprop))
        if self.fail:
            raise GoogleTrendsUnavailable("429 code 429")
        return iter([RawRecord(channel="gtrends", keyword_raw=candidate, entity="geo=KR",
                               metric_type="search_index", metric_value=99.0,
                               observed_at=d) for d in ("2026-10-25", "2026-11-01")])


def kr_rows(conn, kw):
    return conn.execute("SELECT observed_at, metric_value FROM signal_raw WHERE keyword_raw=? "
                        "ORDER BY observed_at", (kw,)).fetchall()


def test_stale_refresh_replaces_whole_series(monkeypatch, db, tmp_path):
    _, conn = db
    seed_at(conn, "기모", "2021-12-26", 10.0)   # 옛 눈금, 새 창이 닿지 않는 해
    seed_at(conn, "기모", "2026-10-25", 40.0)
    fake = RecCollector()
    run(monkeypatch, db, ["--limit", "74", "--geos", "KR", "--stale-days", "9", "--replace",
                          "--end", "2026-11-11", "--snapshot-dir", str(tmp_path / "snap")], fake)
    rows = [tuple(r) for r in kr_rows(conn, "기모")]
    # 옛 눈금 행은 하나도 남지 않고 새 창의 값만 남는다
    assert rows == [("2026-10-25", 99.0), ("2026-11-01", 99.0)]
    # 새 창이 닿지 않은 2021 년 CSV 도 다시 써서 옛 행이 파일에 남지 않는다
    y2021 = (tmp_path / "snap" / "gtrends" / "2021.csv").read_text(encoding="utf-8")
    assert "기모" not in y2021


def test_refresh_keeps_data_when_blocked(monkeypatch, db):
    """받다가 한도에 걸리면 아무것도 지우지 않는다."""
    _, conn = db
    seed_at(conn, "기모", "2026-10-25", 40.0)
    run(monkeypatch, db, ["--limit", "74", "--geos", "KR", "--stale-days", "9", "--replace",
                          "--end", "2026-11-11", "--stop-on-block", "--snapshot-dir", ""],
        RecCollector(fail=True))
    assert [tuple(r) for r in kr_rows(conn, "기모")] == [("2026-10-25", 40.0)]


def test_fresh_terms_are_not_requested_again(monkeypatch, db):
    _, conn = db
    seed_at(conn, "기모", "2026-11-08")
    fake = RecCollector()
    run(monkeypatch, db, ["--limit", "74", "--geos", "KR", "--stale-days", "9", "--replace",
                          "--end", "2026-11-11", "--snapshot-dir", ""], fake)
    assert ("기모", "") not in fake.seen


def test_stale_days_requires_replace(monkeypatch, db):
    path, _ = db
    monkeypatch.setattr(cg, "GoogleTrendsCollector", lambda *a, **k: RecCollector())
    assert cg.main(["--db", str(path), "--stale-days", "9"]) == 2


def test_hourly_threshold_keeps_just_refreshed_terms_fresh(db):
    """방금 받은 속성은 다음 시간에 다시 받지 않아야 한다.

    받을 수 있는 마지막 완성 주는 오늘보다 7일에서 13일 전이다. 수요일 11-11 에
    받으면 마지막 주는 11-01(10일 전)이다. 문턱이 이보다 짧으면 같은 속성만 매시간
    다시 받고 뒤쪽 속성에는 차례가 오지 않는다.
    """
    _, conn = db
    seed_at(conn, "티셔츠", "2026-11-01")    # 방금 갱신
    seed_at(conn, "기모", "2026-10-25")      # 아직 옛 자료
    sh = (ROOT / "scripts" / "collect_gtrends_hourly.sh").read_text(encoding="utf-8")
    import re
    days = int(re.search(r"GTRENDS_STALE_DAYS:-(\d+)", sh).group(1))
    for today in ("2026-11-11", "2026-11-14"):    # 수요일, 토요일
        fresh = cg.fresh_terms(conn, "gtrends", "", days, today)
        assert "티셔츠" in fresh, (days, today)
        assert "기모" not in fresh, (days, today)
