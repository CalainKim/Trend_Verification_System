"""Google Trends 수집기.

계획서의 "유행은 해외에서 한국으로 넘어온다"는 경험적 가설을 검증하는 채널이다.
가설을 전제로 쓰지 않고, 실제로 해외가 선행했는지를 자료로 확인한다.

접근 방식
    공식 API 가 없어 pytrends(비공식)를 쓴다. 첫 요청이 자주 429 로 막히는데,
    쿠키를 받는 워밍업 단계가 불안정해서다. 재시도하면 대체로 통과한다.
    2026-09-29 실측: 1회차 429, 2회차 성공(93행).

robots.txt (2026-09-29 확인)
    trends.google.com 은 /explore? 와 /trends/explore? 만 차단한다.
    이는 웹 UI 의 질의 URL 이고, pytrends 가 쓰는 /trends/api/... 는
    차단 대상이 아니다. 무신사·데이터랩과 달리 전면 차단이 아니다.

값의 성격
    네이버와 마찬가지로 요청 안에서 최댓값 100 으로 정규화된 상대 지수다.
    지역이 다르면 요청도 다르므로 값의 크기는 비교할 수 없다. 선행 여부는
    크기가 아니라 시점으로 판단한다(features.lead_lag 참고).
"""

from __future__ import annotations

import time
from typing import Dict, Iterator, List, Optional, Sequence

from ..models import RawRecord
from .base import Collector

#: 비교할 지역. 빈 문자열은 전세계.
KOREA = "KR"
DEFAULT_GEOS = (KOREA, "US", "")

GEO_NAMES = {"KR": "한국", "US": "미국", "": "전세계", "JP": "일본", "GB": "영국"}

#: 첫 요청이 429 로 막히는 일이 잦다. 쿠키 워밍업이 불안정한 탓이라 재시도하면
#: 대체로 통과한다. 한 번 실패했다고 채널을 포기하면 안 된다.
MAX_ATTEMPTS = 4
RETRY_BACKOFF_SEC = 5.0


class GoogleTrendsUnavailable(RuntimeError):
    """재시도 후에도 응답을 받지 못했을 때."""


class GoogleTrendsCollector(Collector):
    channel = "gtrends"

    #: 구글은 공식 한도를 밝히지 않는다. 넉넉히 둔다.
    min_interval_sec = 3.0

    def __init__(
        self,
        hl: str = "ko-KR",
        tz: int = 540,
        min_interval_sec: Optional[float] = None,
        max_attempts: int = MAX_ATTEMPTS,
    ) -> None:
        super().__init__()
        if min_interval_sec is not None:
            self.min_interval_sec = min_interval_sec
        self.hl, self.tz = hl, tz
        self.max_attempts = max_attempts
        self._client = None

    def _fresh_client(self):
        from pytrends.request import TrendReq

        # 재시도마다 새 세션을 만든다. 막힌 세션을 계속 쓰면 같은 결과가 나온다.
        return TrendReq(hl=self.hl, tz=self.tz, timeout=(10, 30), retries=0)

    def _fetch(self, keywords: Sequence[str], timeframe: str, geo: str):
        """구글이 응답할 때까지 재시도한다. 빈 결과는 재시도하지 않는다.

        빈 결과는 실패가 아니라 "이 지역에서 측정할 만한 검색량이 없다"는
        유효한 답이다. 한국어 키워드를 미국에서 조회하면 당연히 비어 있다.
        이를 오류로 취급하면 재시도만 반복하면서 진짜 발견을 가린다.
        """
        last = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                self.sleep()
                client = self._fresh_client()
                client.build_payload(list(keywords), timeframe=timeframe, geo=geo)
                frame = client.interest_over_time()
                return frame if frame is not None else None
            except Exception as exc:       # pytrends 는 예외 종류가 일정하지 않다
                last = f"{type(exc).__name__}: {exc}"
            if attempt < self.max_attempts:
                time.sleep(RETRY_BACKOFF_SEC * attempt)
        raise GoogleTrendsUnavailable(
            f"{self.max_attempts}회 시도 후에도 응답을 받지 못했다 "
            f"(geo={geo or 'WORLD'}): {last}"
        )

    def collect(
        self,
        keywords: Sequence[str],
        start_date: str,
        end_date: str,
        geos: Sequence[str] = DEFAULT_GEOS,
        keywords_by_geo: Optional[Dict[str, Sequence[str]]] = None,
        candidate: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> Iterator[RawRecord]:
        """지역별 관심도 시계열. entity 에 지역을 남겨 구분한다.

        keywords_by_geo 로 지역마다 다른 단어를 줄 수 있다. 해외 선행을 보려면
        필요하다. 한국어 키워드는 해외에서 검색량이 구조적으로 0이라 같은 단어로
        조회하면 빈 결과만 나온다.

            collect(["맨투맨"], ..., keywords_by_geo={"US": ["sweatshirt"]})

        이때 keyword_raw 에는 질의어가 아니라 **후보**(맨투맨)를 넣는다.
        질의어를 정체성으로 쓰면 지역마다 다른 이름으로 저장되어 지역 간
        결합이 깨진다. 실제 질의어는 metadata.query_term 에 남긴다.
        """
        label = candidate or (keywords[0] if keywords else "")
        timeframe = f"{start_date} {end_date}"
        for geo in geos:
            terms = list((keywords_by_geo or {}).get(geo, keywords))
            frame = self._fetch(terms, timeframe, geo)
            if frame is None or frame.empty:
                continue      # 이 지역에는 측정할 만한 검색량이 없다
            for stamp, row in frame.iterrows():
                if bool(row.get("isPartial", False)):
                    continue      # 마지막 구간은 집계가 안 끝나 값이 낮게 나온다
                for keyword in terms:
                    if keyword not in row:
                        continue
                    yield RawRecord(
                        channel=self.channel,
                        keyword_raw=label,
                        entity=f"geo={geo or 'WORLD'}",
                        metric_type="search_index",
                        metric_value=float(row[keyword]),
                        observed_at=stamp.date().isoformat(),
                        metadata={
                            "geo": geo or "WORLD",
                            "geo_name": GEO_NAMES.get(geo, geo or "전세계"),
                            "query_start": start_date,
                            "query_end": end_date,
                            "query_term": keyword,
                            "normalized": True,
                            "note": "요청 안에서 최댓값 100 으로 정규화된 상대 지수. "
                                    "지역이 다르면 값의 크기는 비교할 수 없다",
                        },
                        run_id=run_id,
                    )
