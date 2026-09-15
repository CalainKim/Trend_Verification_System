"""동의어·유사 표현 클러스터링.

'발라클라바' / '바라클라바' / 'balaclava' 처럼 표현만 다른 것을 하나의 후보로
묶는다. 흩어진 채로 두면 각각은 신호가 약해 보여서 진짜 시그널을 놓친다.

임계값은 연구 결과를 좌우하는 값이다. 낮추면 서로 다른 상품이 한 후보로 뭉치고,
높이면 같은 것이 갈라진다. 기본값은 출발점일 뿐이고, 실제 데이터로 확인해서
조정한 근거를 남겨야 한다.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

from . import embeddings, vectorstore
from .models import utcnow_iso

#: 이 값 이상이면 같은 후보로 본다. 실측으로 조정할 대상이다.
DEFAULT_THRESHOLD = 0.92


@dataclass
class Cluster:
    canonical: str
    members: List[str] = field(default_factory=list)
    channels: List[str] = field(default_factory=list)

    @property
    def size(self) -> int:
        return len(self.members)


class _UnionFind:
    def __init__(self, n: int):
        self.parent = list(range(n))

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra


def cluster_texts(
    conn: sqlite3.Connection,
    threshold: float = DEFAULT_THRESHOLD,
    neighbors: int = 20,
    channel: Optional[str] = None,
    model_name: str = embeddings.DEFAULT_MODEL,
) -> List[Cluster]:
    """색인된 텍스트를 유사도로 묶는다.

    각 텍스트의 이웃만 보고 이어붙이므로(전수 비교가 아니라) 건수가 늘어도
    비용이 급증하지 않는다.
    """
    rows = conn.execute(
        f"SELECT rowid, text, channel FROM {vectorstore.META_TABLE}"
        + (" WHERE channel = ?" if channel else "")
        + " ORDER BY rowid",
        (channel,) if channel else (),
    ).fetchall()
    if not rows:
        return []

    index_of = {r[0]: i for i, r in enumerate(rows)}
    uf = _UnionFind(len(rows))

    for rowid, text, _ in rows:
        blob = conn.execute(
            f"SELECT embedding FROM {vectorstore.VEC_TABLE} WHERE rowid = ?", (rowid,)
        ).fetchone()
        if blob is None:
            continue
        vector = embeddings.unpack(blob[0])
        for hit in vectorstore.search_vector(conn, vector, limit=neighbors, channel=channel):
            if hit.similarity < threshold or hit.text == text:
                continue
            other = conn.execute(
                f"SELECT rowid FROM {vectorstore.META_TABLE} WHERE text = ?", (hit.text,)
            ).fetchone()
            if other and other[0] in index_of:
                uf.union(index_of[rowid], index_of[other[0]])

    groups: Dict[int, List[tuple]] = {}
    for rowid, text, ch in rows:
        groups.setdefault(uf.find(index_of[rowid]), []).append((text, ch))

    clusters = []
    for members in groups.values():
        texts = [m[0] for m in members]
        clusters.append(
            Cluster(
                canonical=pick_canonical(texts),
                members=sorted(texts),
                channels=sorted({m[1] for m in members}),
            )
        )
    clusters.sort(key=lambda c: (-c.size, c.canonical))
    return clusters


def pick_canonical(texts: Sequence[str]) -> str:
    """대표 표현. 짧고 단순한 쪽을 고른다.

    상품명에는 '[29CM 단독]', '(3color)' 같은 수식이 붙는다. 대표로는 군더더기가
    적은 쪽이 읽기 좋다.
    """
    def noise(t: str) -> int:
        return sum(t.count(c) for c in "[]()/_") + t.count("  ")

    return min(texts, key=lambda t: (noise(t), len(t), t))


def save_clusters(
    conn: sqlite3.Connection, clusters: Sequence[Cluster], replace: bool = True
) -> int:
    """signal_candidate 에 기록한다. 원시 레코드와의 연결도 함께 만든다."""
    if replace:
        conn.execute("DELETE FROM candidate_keyword_map")
        conn.execute("DELETE FROM signal_candidate")

    now = utcnow_iso()
    saved = 0
    for n, cluster in enumerate(clusters, start=1):
        candidate_id = f"cand_{n:05d}"
        first = conn.execute(
            "SELECT MIN(observed_at) FROM signal_raw WHERE keyword_raw IN "
            f"({','.join('?' * len(cluster.members))})",
            cluster.members,
        ).fetchone()[0]
        conn.execute(
            "INSERT INTO signal_candidate"
            "(candidate_id, canonical_keyword, first_detected_at, created_at, notes) "
            "VALUES (?,?,?,?,?)",
            (candidate_id, cluster.canonical, first or now, now,
             f"members={cluster.size} channels={','.join(cluster.channels)}"),
        )
        for raw_id, in conn.execute(
            "SELECT id FROM signal_raw WHERE keyword_raw IN "
            f"({','.join('?' * len(cluster.members))})",
            cluster.members,
        ).fetchall():
            conn.execute(
                "INSERT OR IGNORE INTO candidate_keyword_map"
                "(candidate_id, signal_raw_id, similarity) VALUES (?,?,?)",
                (candidate_id, raw_id, None),
            )
        saved += 1
    conn.commit()
    return saved
