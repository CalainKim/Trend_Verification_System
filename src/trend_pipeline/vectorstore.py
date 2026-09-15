"""sqlite-vec 기반 벡터 검색.

수집한 아이템(상품명·키워드)을 임베딩해 두고 유사도로 찾는다. 두 가지에 쓴다.

  1. 동의어·유사 표현 클러스터링
     '발라클라바'와 'balaclava' 처럼 표기만 다른 것을 하나의 후보로 묶는다.
     계획서의 '임베딩 기반 유사도 계산' 단계에 해당한다.

  2. 후보 -> 실제 수집 아이템 되찾기
     검증 단계가 어떤 후보를 확정하더라도, 그것이 우리가 실제로 수집한
     어떤 상품을 가리키는지 연결되어야 결과가 쓸모 있어진다.

벡터는 signal_raw 와 같은 DB 파일에 둔다. 별도 저장소를 쓰면 스냅샷에서
DB 를 재구성할 때 둘이 어긋난다.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

from . import embeddings

#: 이 값 미만이면 "맞는 것이 없다"로 본다. 하한선이 없으면 벡터 검색은 언제나
#: 가장 가까운 무언가를 돌려주므로, 관련 없는 상품이 그럴듯한 점수로 올라온다.
#: 실측 예: 29CM 에 럭비 셔츠가 없는데도 "럭비티" 검색에 블라우스가 0.79 로 나왔다.
MIN_SIMILARITY = 0.80

VEC_TABLE = "item_vec"
META_TABLE = "item_text"


class VecExtensionUnavailable(RuntimeError):
    """sqlite-vec 확장을 올리지 못했을 때."""


def enable(conn: sqlite3.Connection) -> None:
    """연결에 sqlite-vec 확장을 올린다. 연결마다 한 번씩 필요하다."""
    try:
        import sqlite_vec
    except ImportError as exc:  # pragma: no cover
        raise VecExtensionUnavailable("sqlite-vec 가 설치되지 않았다: pip install sqlite-vec") from exc
    try:
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)
    except (AttributeError, sqlite3.OperationalError) as exc:
        raise VecExtensionUnavailable(
            "이 파이썬의 sqlite3 가 확장 로딩을 지원하지 않는다. "
            "확장 로딩이 켜진 파이썬(예: Homebrew python3.12)을 쓸 것"
        ) from exc


def init(conn: sqlite3.Connection, dim: int = embeddings.EMBED_DIM) -> None:
    enable(conn)
    conn.execute(
        f"CREATE VIRTUAL TABLE IF NOT EXISTS {VEC_TABLE} USING vec0(embedding float[{dim}])"
    )
    # 가상 테이블에는 rowid 와 벡터만 두고, 본문은 일반 테이블에 둔다.
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {META_TABLE} (
            rowid        INTEGER PRIMARY KEY,
            text         TEXT NOT NULL UNIQUE,
            channel      TEXT NOT NULL,
            entity       TEXT NOT NULL DEFAULT '',
            model        TEXT NOT NULL,
            embedded_at  TEXT NOT NULL
        )
        """
    )
    conn.commit()


@dataclass(frozen=True)
class Hit:
    text: str
    channel: str
    entity: str
    distance: float

    @property
    def similarity(self) -> float:
        """정규화된 벡터의 L2 거리를 0~1 유사도로. 1 이면 같은 방향."""
        return 1.0 - (self.distance ** 2) / 2.0


def index_texts(
    conn: sqlite3.Connection,
    rows: Sequence[Tuple[str, str, str]],
    model_name: str = embeddings.DEFAULT_MODEL,
    batch_size: int = 64,
) -> int:
    """rows 는 (text, channel, entity). 이미 색인된 텍스트는 건너뛴다."""
    from .models import utcnow_iso

    fresh = [
        r for r in rows
        if conn.execute(f"SELECT 1 FROM {META_TABLE} WHERE text = ?", (r[0],)).fetchone() is None
    ]
    # 같은 배치 안의 중복도 제거
    seen, unique = set(), []
    for r in fresh:
        if r[0] not in seen:
            seen.add(r[0])
            unique.append(r)
    if not unique:
        return 0

    now = utcnow_iso()
    for start in range(0, len(unique), batch_size):
        chunk = unique[start:start + batch_size]
        # 임베딩은 정규화된 이름으로 한다. 프로모션 태그와 품번이 남아 있으면
        # 그것들이 유사도를 지배해 서로 다른 품목이 묶인다. 원문은 그대로 저장한다.
        vectors = embeddings.encode_passages(
            [embeddings.normalize_for_embedding(c[0]) for c in chunk], model_name
        )
        for (text, channel, entity), vector in zip(chunk, vectors):
            cur = conn.execute(
                f"INSERT INTO {META_TABLE}(text, channel, entity, model, embedded_at) "
                f"VALUES (?,?,?,?,?)",
                (text, channel, entity, model_name, now),
            )
            conn.execute(
                f"INSERT INTO {VEC_TABLE}(rowid, embedding) VALUES (?,?)",
                (cur.lastrowid, embeddings.pack(vector)),
            )
        conn.commit()
    return len(unique)


def search(
    conn: sqlite3.Connection,
    query: str,
    limit: int = 10,
    channel: Optional[str] = None,
    model_name: str = embeddings.DEFAULT_MODEL,
    min_similarity: Optional[float] = MIN_SIMILARITY,
) -> List[Hit]:
    """질의와 유사한 수집 아이템을 가까운 순으로.

    min_similarity 미만은 버린다. 결과가 비는 것은 정상이며 "우리가 수집한
    범위에 해당하는 상품이 없다"는 뜻이다. 억지로 채우면 판정이 오염된다.
    """
    vector = embeddings.encode_query(embeddings.normalize_for_embedding(query), model_name)
    return search_vector(conn, vector, limit, channel, min_similarity)


def search_vector(
    conn: sqlite3.Connection,
    vector: Sequence[float],
    limit: int = 10,
    channel: Optional[str] = None,
    min_similarity: Optional[float] = None,
) -> List[Hit]:
    # 채널로 걸러야 하면 넉넉히 받아서 거른다. vec0 는 MATCH 와 일반 조건을
    # 함께 쓰는 데 제약이 있어 후처리하는 편이 안전하다.
    k = limit * 5 if channel else limit
    rows = conn.execute(
        f"""
        SELECT m.text, m.channel, m.entity, v.distance
        FROM {VEC_TABLE} v JOIN {META_TABLE} m ON m.rowid = v.rowid
        WHERE v.embedding MATCH ? AND k = ?
        ORDER BY v.distance
        """,
        (embeddings.pack(vector), k),
    ).fetchall()
    hits = [Hit(r[0], r[1], r[2], r[3]) for r in rows]
    if channel:
        hits = [h for h in hits if h.channel == channel]
    if min_similarity is not None:
        hits = [h for h in hits if h.similarity >= min_similarity]
    return hits[:limit]


def count(conn: sqlite3.Connection) -> int:
    return conn.execute(f"SELECT COUNT(*) FROM {META_TABLE}").fetchone()[0]
