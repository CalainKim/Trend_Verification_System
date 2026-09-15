#!/usr/bin/env python3
"""수집된 아이템을 임베딩해 벡터 색인을 만든다.

    python scripts/build_index.py              # 새로 들어온 것만 색인
    python scripts/build_index.py --cluster    # 색인 후 동의어 클러스터링까지

일별 수집(Actions)에는 넣지 않는다. 모델이 1GB 가 넘어 매일 내려받으면 낭비이고,
색인은 수집만큼 자주 갱신할 필요가 없다. 필요할 때 로컬에서 돌린다.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from trend_pipeline import clustering, embeddings, storage, vectorstore  # noqa: E402


def collect_texts(conn, channel=None):
    """색인 대상. 채널별로 텍스트의 의미가 다르다.

      commerce_rank  상품명
      naver_*        검색어 / 키워드 그룹명
    """
    sql = """
        SELECT keyword_raw, channel, MIN(entity) AS entity
        FROM signal_raw
        WHERE TRIM(keyword_raw) <> ''
    """
    params = []
    if channel:
        sql += " AND channel = ?"
        params.append(channel)
    sql += " GROUP BY keyword_raw, channel ORDER BY keyword_raw"
    return [(r["keyword_raw"], r["channel"], r["entity"] or "") for r in conn.execute(sql, params)]


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="벡터 색인 생성")
    p.add_argument("--db", default=None)
    p.add_argument("--channel", default=None, help="특정 채널만")
    p.add_argument("--cluster", action="store_true", help="색인 후 동의어 클러스터링")
    p.add_argument("--threshold", type=float, default=clustering.DEFAULT_THRESHOLD)
    p.add_argument("--model", default=embeddings.DEFAULT_MODEL)
    args = p.parse_args(argv)

    conn = storage.connect(Path(args.db) if args.db else None)
    storage.init_db(conn)
    vectorstore.init(conn)

    rows = collect_texts(conn, args.channel)
    print(f"색인 대상 {len(rows)}건 (이미 색인된 것은 건너뛴다)")
    added = vectorstore.index_texts(conn, rows, model_name=args.model)
    print(f"신규 색인 {added}건 · 누적 {vectorstore.count(conn)}건")

    if not args.cluster:
        return 0

    print(f"\n동의어 클러스터링 (임계값 {args.threshold})")
    clusters = clustering.cluster_texts(conn, threshold=args.threshold, channel=args.channel,
                                        model_name=args.model)
    multi = [c for c in clusters if c.size > 1]
    print(f"후보 {len(clusters)}개 · 그중 둘 이상이 묶인 것 {len(multi)}개")
    for c in multi[:15]:
        print(f"  [{c.size}] {c.canonical}")
        for m in c.members:
            if m != c.canonical:
                print(f"        {m}")
    saved = clustering.save_clusters(conn, clusters)
    print(f"\nsignal_candidate 에 {saved}개 기록")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
