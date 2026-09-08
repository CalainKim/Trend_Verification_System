#!/usr/bin/env python3
"""네이버 API 키 확인 및 실제 제약 실측.

    python scripts/verify_naver_key.py

문서로만 알고 있는 값(조회 가능한 가장 이른 날짜, 연령 코드 체계 등)을
추측해서 코드에 박아두면 조용히 틀린다. 실제로 호출해서 확인한다.
"""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from trend_pipeline import config  # noqa: E402
from trend_pipeline.collectors.naver_base import NaverApiError  # noqa: E402
from trend_pipeline.collectors.naver_datalab import NaverDataLabCollector  # noqa: E402
from trend_pipeline.collectors.naver_shopping import (  # noqa: E402
    TOPS_CATEGORIES,
    NaverShoppingCollector,
)

OK, FAIL, SKIP = "  [OK]  ", "  [실패]", "  [보류]"


def probe_earliest(collector, make_call, floor=date(2007, 1, 1), ceil=None) -> str:
    """조회가 허용되는 가장 이른 날짜를 이분 탐색으로 찾는다."""
    ceil = ceil or date.today() - timedelta(days=30)
    lo, hi = floor, ceil
    while (hi - lo).days > 1:
        mid = lo + (hi - lo) // 2
        try:
            make_call(mid.isoformat())
            hi = mid          # 성공 -> 더 이른 날짜도 되는지
        except NaverApiError:
            lo = mid          # 실패 -> 더 늦은 날짜로
    return hi.isoformat()


def main() -> int:
    print("네이버 오픈 API 확인\n" + "─" * 60)

    try:
        cid, secret = config.naver_credentials()
    except config.MissingCredentials as exc:
        print(FAIL, "키가 설정되지 않았다.\n")
        print(exc)
        return 1
    print(OK, f"키 로드됨 (Client ID {cid[:4]}{'*' * max(0, len(cid) - 4)})")

    end = date.today() - timedelta(days=2)
    start = end - timedelta(days=14)

    # --- 검색어 트렌드 -------------------------------------------------
    search = NaverDataLabCollector(cid, secret)
    try:
        rows = list(
            search.collect({"티셔츠": ["티셔츠"]}, start.isoformat(), end.isoformat())
        )
        print(OK, f"검색어 트렌드 응답 {len(rows)}행 "
                  f"({rows[0].observed_at} ~ {rows[-1].observed_at})")
        print("       값 예시:", [round(r.metric_value, 1) for r in rows[:5]],
              "(요청 안에서 최댓값 100 으로 정규화된 상대 지수)")
    except NaverApiError as exc:
        print(FAIL, f"검색어 트렌드 호출 실패: {exc}")
        print("       개발자센터에서 '데이터랩 (검색어 트렌드)' 사용 API 가 등록됐는지 확인할 것")
        return 1

    earliest = probe_earliest(
        search,
        lambda d: list(search.collect({"t": ["티셔츠"]}, d, d, time_unit="month")),
    )
    print(OK, f"조회 가능한 가장 이른 날짜: {earliest}"
              f"  (코드 상수 earliest_start_date = {search.earliest_start_date})")

    # 연령 분해가 실제로 어떤 코드를 받는지
    try:
        seg = list(search.collect({"티셔츠": ["티셔츠"]}, start.isoformat(),
                                  end.isoformat(), gender="f", ages=["4", "5"]))
        print(OK, f"성별·연령 필터 동작 확인 ({len(seg)}행, entity={seg[0].entity})")
    except NaverApiError as exc:
        print(FAIL, f"성별·연령 필터 실패: {exc}")

    # --- 쇼핑인사이트 ---------------------------------------------------
    shopping = NaverShoppingCollector(cid, secret)
    if not TOPS_CATEGORIES:
        print(SKIP, "쇼핑인사이트 미확인 - 카테고리 코드가 비어 있다.")
        print("       shopping.naver.com 쇼핑인사이트에서 상의 분야 코드를 확인해")
        print("       collectors/naver_shopping.py 의 TOPS_CATEGORIES 에 넣을 것")
        print("       (datalab robots.txt 가 자동 조회를 막으므로 수동 확인한다)")
        return 0

    code = next(iter(TOPS_CATEGORIES))
    try:
        rows = list(shopping.collect_category({"상의": [code]},
                                              start.isoformat(), end.isoformat()))
        print(OK, f"쇼핑인사이트 분야 클릭 추이 {len(rows)}행")
    except NaverApiError as exc:
        print(FAIL, f"쇼핑인사이트 호출 실패: {exc}")
        print("       '데이터랩 (쇼핑인사이트)' 사용 API 가 등록됐는지 확인할 것")
        return 1

    try:
        demo = list(shopping.collect_keyword_demographics(
            code, "티셔츠", start.isoformat(), end.isoformat()))
        groups = sorted({r.entity for r in demo})
        print(OK, f"성별·연령 분해 {len(demo)}행")
        print("       실제 그룹:", groups)
    except NaverApiError as exc:
        print(FAIL, f"성별·연령 분해 실패: {exc}")

    print("\n확인 완료. 실측값이 코드 상수와 다르면 상수를 고칠 것.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
