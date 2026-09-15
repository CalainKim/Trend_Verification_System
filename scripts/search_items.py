#!/usr/bin/env python3
"""수집한 아이템을 유사도로 검색한다.

    python scripts/search_items.py "발라클라바"
    python scripts/search_items.py "오버핏 반팔" --limit 5 --channel commerce_rank

검증 단계가 어떤 후보를 확정하더라도, 그것이 우리가 실제로 수집한 어떤 상품을
가리키는지 연결되어야 결과가 쓸모 있어진다. 그 연결을 담당한다.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from trend_pipeline import storage, vectorstore  # noqa: E402


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="수집 아이템 유사도 검색")
    p.add_argument("query")
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--channel", default=None)
    p.add_argument("--db", default=None)
    args = p.parse_args(argv)

    conn = storage.connect(Path(args.db) if args.db else None)
    vectorstore.init(conn)
    if vectorstore.count(conn) == 0:
        print("색인이 비어 있다. 먼저 python scripts/build_index.py 를 실행할 것.")
        return 1

    hits = vectorstore.search(conn, args.query, limit=args.limit, channel=args.channel)
    print(f'"{args.query}" 와 가까운 수집 아이템\n')
    for n, h in enumerate(hits, 1):
        print(f"  {n:>2}. {h.similarity:.3f}  [{h.channel}]  {h.text}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
