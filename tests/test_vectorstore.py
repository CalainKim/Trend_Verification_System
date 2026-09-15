"""벡터 저장·검색·클러스터링 검증.

임베딩 모델은 쓰지 않는다. 1GB 넘는 모델을 받아야 돌아가는 테스트는
CI 에서도 로컬에서도 부담이라, 결정적인 가짜 인코더로 대체한다.
여기서 확인할 것은 모델 품질이 아니라 저장·검색·묶기 규약이다.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from trend_pipeline import clustering, embeddings, storage, vectorstore  # noqa: E402

DIM = 8


def fake_vector(text: str):
    """텍스트마다 결정적인 단위 벡터.

    글자 구성이 겹칠수록 가까워진다. 앞 N글자만 보면 접미사만 다른 두 이름이
    완전히 같은 벡터가 되어버려 검색 순위와 임계값을 검증할 수 없다.
    """
    v = [0.0] * DIM
    for ch in text:
        v[ord(ch) % DIM] += 1.0
    norm = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / norm for x in v]


@pytest.fixture()
def conn(tmp_path, monkeypatch):
    monkeypatch.setattr(embeddings, "encode_passages",
                        lambda texts, model_name=None: [fake_vector(t) for t in texts])
    monkeypatch.setattr(embeddings, "encode_query",
                        lambda text, model_name=None: fake_vector(text))
    c = storage.connect(tmp_path / "v.sqlite")
    storage.init_db(c)
    vectorstore.init(c, dim=DIM)
    yield c
    c.close()


ROWS = [
    ("발라클라바 니트 비니", "commerce_rank", "29cm:1"),
    ("발라클라바 니트 비니 2color", "commerce_rank", "29cm:2"),
    ("오버핏 반팔 티셔츠", "commerce_rank", "29cm:3"),
    ("발라클라바", "naver_datalab", ""),
]


def test_index_and_count(conn):
    assert vectorstore.index_texts(conn, ROWS) == 4
    assert vectorstore.count(conn) == 4


def test_index_is_idempotent(conn):
    vectorstore.index_texts(conn, ROWS)
    assert vectorstore.index_texts(conn, ROWS) == 0   # 이미 색인된 것은 건너뛴다
    assert vectorstore.count(conn) == 4


def test_duplicate_texts_in_one_batch_indexed_once(conn):
    dup = [("같은 이름", "commerce_rank", "a"), ("같은 이름", "commerce_rank", "b")]
    assert vectorstore.index_texts(conn, dup) == 1


def test_search_returns_nearest_first(conn):
    vectorstore.index_texts(conn, ROWS)
    hits = vectorstore.search(conn, "발라클라바 니트 비니", limit=4)
    assert hits[0].text == "발라클라바 니트 비니"
    assert hits[0].similarity > hits[-1].similarity
    assert all(0.0 <= h.similarity <= 1.0 for h in hits)


def test_search_can_filter_by_channel(conn):
    vectorstore.index_texts(conn, ROWS)
    hits = vectorstore.search(conn, "발라클라바", limit=5, channel="naver_datalab")
    assert hits and all(h.channel == "naver_datalab" for h in hits)


def test_similarity_of_identical_text_is_one(conn):
    vectorstore.index_texts(conn, [("동일 문자열", "commerce_rank", "")])
    hit = vectorstore.search(conn, "동일 문자열", limit=1)[0]
    assert hit.similarity == pytest.approx(1.0, abs=1e-5)


def test_clustering_respects_threshold(conn):
    """임계값이 묶임 여부를 실제로 가른다.

    특정 숫자를 박아두면 인코더가 바뀔 때 의미 없이 깨진다. 두 유사 항목의
    실제 유사도를 먼저 구하고, 그 값의 위아래로 임계값을 움직여 확인한다.
    """
    vectorstore.index_texts(conn, ROWS)
    pair = next(h for h in vectorstore.search(conn, "발라클라바 니트 비니", limit=4)
                if h.text == "발라클라바 니트 비니 2color")
    assert pair.similarity < 0.999, "두 이름이 구분되지 않으면 이 테스트가 무의미하다"

    tight = clustering.cluster_texts(conn, threshold=pair.similarity + 0.005)
    loose = clustering.cluster_texts(conn, threshold=pair.similarity - 0.005)
    assert max(c.size for c in tight) < max(c.size for c in loose)


def test_clustering_extremes(conn):
    vectorstore.index_texts(conn, ROWS)
    assert all(c.size == 1 for c in clustering.cluster_texts(conn, threshold=1.01))
    everything = clustering.cluster_texts(conn, threshold=0.0)
    assert len(everything) == 1 and everything[0].size == 4


def test_save_clusters_writes_candidates(conn):
    from trend_pipeline.models import RawRecord

    storage.insert_raw(conn, [
        RawRecord(channel="commerce_rank", keyword_raw="발라클라바 니트 비니",
                  entity="29cm:1", metric_type="rank", metric_value=3,
                  observed_at="2026-09-10T09:00:00+09:00"),
    ])
    vectorstore.index_texts(conn, ROWS)
    clusters = clustering.cluster_texts(conn, threshold=0.99)
    assert clustering.save_clusters(conn, clusters) == len(clusters)

    n = conn.execute("SELECT COUNT(*) FROM signal_candidate").fetchone()[0]
    assert n == len(clusters)
    # 원시 레코드와의 연결이 생겨야 후보에서 실제 수집분으로 되돌아갈 수 있다
    linked = conn.execute("SELECT COUNT(*) FROM candidate_keyword_map").fetchone()[0]
    assert linked >= 1


def test_pick_canonical_prefers_clean_name():
    assert clustering.pick_canonical([
        "[29CM 단독] 제인 루즈 티셔츠 (3col)_2GFUTS06",
        "제인 루즈 티셔츠",
    ]) == "제인 루즈 티셔츠"
