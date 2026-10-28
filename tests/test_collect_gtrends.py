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
