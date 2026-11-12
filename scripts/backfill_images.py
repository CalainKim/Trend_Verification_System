#!/usr/bin/env python3
"""기존 수집분에 상품 사진 주소를 채운다.

수집기가 imageUrl 을 버리고 있어서 지난 기록에는 사진 주소가 없다. 29CM 랭킹
API 를 다시 불러 item_no 로 맞춰 메타데이터에 넣는다. 수집기는 고쳤으므로
다음 수집부터는 이 스크립트가 필요 없다.

    ./scripts/backfill_images.py --dry-run     무엇이 바뀔지만 본다
    ./scripts/backfill_images.py

랭킹 API 는 지금 순위에 있는 상품만 준다. 그때는 TOP100 이었지만 지금 빠진
상품은 사진을 못 받는다. 화면에 자리표시자가 있으므로 빈 채로 둔다.

메타데이터의 다른 값은 건드리지 않는다. image_url 이 이미 있으면 넘어간다.
"""

from __future__ import annotations

import argparse
import html as htmllib
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from trend_pipeline import storage  # noqa: E402
from trend_pipeline.collectors.cm29_rank import (  # noqa: E402
    IMAGE_CDN, Cm29RankCollector, TOPS_CATEGORY_CODES,
)


def fetch_image_map(collector) -> dict:
    """지금 랭킹에 있는 상품의 item_no 에서 사진 주소로 가는 표."""
    out = {}
    # 카테고리 코드가 이미 남성 상의와 여성 상의로 갈려 있다. gender 를 함께
    # 주면 400 이 온다.
    for code in TOPS_CATEGORY_CODES:
        try:
            items = collector.fetch_items(code, "ONE_DAY", max_items=100)
        except Exception as exc:
            print(f"  {code} 조회 실패: {exc}")
            continue
        for it in items:
            u, no = it.get("imageUrl"), it.get("itemNo")
            if u and no is not None:
                out[int(no)] = IMAGE_CDN + u
    return out


OG_IMAGE = re.compile(r'<meta property="og:image" content="([^"]+)"')


def fetch_from_product_page(item_no: int, session) -> str | None:
    """상품 페이지의 og:image. 랭킹에서 빠진 상품은 이 길밖에 없다.

    페이지 하나가 400KB 라 느리다. 쿼리는 떼고 돌려준다. 화면에서 ?width=160 을
    붙여 쓰므로 원본 주소만 있으면 된다.
    """
    try:
        r = session.get(f"https://product.29cm.co.kr/catalog/{item_no}",
                        headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
    except Exception:
        return None
    if r.status_code != 200:
        return None
    m = OG_IMAGE.search(r.text)
    if not m:
        return None
    return htmllib.unescape(m.group(1)).split("?")[0]


def main(argv=None) -> int:
    """사진 주소가 빠진 상품을 찾아 채운다. 명령줄 인자로 범위와 속도를 정한다."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", type=Path, default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--pages", action="store_true",
                    help="랭킹에 없는 상품은 상품 페이지에서 찾는다. 느리다")
    ap.add_argument("--only", nargs="*", default=None,
                    help="이 관측일의 상품만 채운다. 보여 줄 주만 채울 때 쓴다")
    ap.add_argument("--interval", type=float, default=0.7,
                    help="상품 페이지 요청 사이 간격(초)")
    args = ap.parse_args(argv)

    conn = storage.connect(args.db)
    sql = "SELECT id, metadata FROM signal_raw WHERE channel = 'commerce_rank'"
    params: tuple = ()
    if args.only:
        marks = ",".join("?" * len(args.only))
        sql += f" AND substr(observed_at, 1, 10) IN ({marks})"
        params = tuple(args.only)
        print(f"관측일 {', '.join(args.only)} 만 본다")
    rows = conn.execute(sql, params).fetchall()
    need = []
    for rid, meta in rows:
        m = json.loads(meta)
        if m.get("image_url") or m.get("item_no") is None:
            continue
        need.append((rid, m))
    print(f"commerce_rank {len(rows)}행 가운데 사진 주소가 없는 행 {len(need)}개")
    if not need:
        return 0

    items = {m["item_no"] for _, m in need}
    print(f"서로 다른 상품 {len(items)}개\n")

    print("29CM 랭킹을 다시 조회한다")
    image = fetch_image_map(Cm29RankCollector())
    print(f"  사진 주소를 받은 상품 {len(image)}개")

    missing = sorted(items - set(image))
    if args.pages and missing:
        import requests

        print(f"\n랭킹에 없는 상품 {len(missing)}개를 상품 페이지에서 찾는다")
        s = requests.Session()
        found = 0
        for i, no in enumerate(missing, 1):
            u = fetch_from_product_page(no, s)
            if u:
                image[no] = u
                found += 1
            if i % 20 == 0 or i == len(missing):
                print(f"  {i}/{len(missing)}  찾음 {found}개")
            time.sleep(args.interval)

    hit = [(rid, m) for rid, m in need if m["item_no"] in image]
    covered = {m["item_no"] for _, m in hit}
    print(f"\n  맞춰진 상품 {len(covered)}개 / {len(items)}개 "
          f"({len(covered) / len(items) * 100:.0f}%)")
    print(f"  채울 행 {len(hit)}개")
    if args.dry_run:
        print("\n--dry-run 이라 쓰지 않았다")
        return 0

    for rid, m in hit:
        m["image_url"] = image[m["item_no"]]
        conn.execute("UPDATE signal_raw SET metadata = ? WHERE id = ?",
                     (json.dumps(m, ensure_ascii=False), rid))
    conn.commit()
    print(f"\n{len(hit)}행에 사진 주소를 넣었다")
    print("스냅샷도 다시 내보내야 한다: ./scripts/export_snapshots.py commerce_rank")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
