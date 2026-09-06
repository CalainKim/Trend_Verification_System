#!/usr/bin/env python3
"""스냅샷 CSV 로부터 SQLite 를 재구성한다.

DB 는 언제든 버리고 다시 만들 수 있는 파생물이고, 원본은 data/snapshots 다.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from trend_pipeline import snapshots, storage  # noqa: E402


def main(argv=None) -> int:
    root = Path(argv[0]) if argv else ROOT / "data" / "snapshots"
    conn = storage.connect()
    storage.init_db(conn)
    inserted = snapshots.load_all(conn, root)
    print(f"{root} -> 신규 {inserted}행 적재")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
