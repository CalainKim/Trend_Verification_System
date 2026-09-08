"""네이버 데이터랩 쇼핑인사이트 수집기.

검색어 트렌드가 '관심'을 보여준다면 이쪽은 쇼핑 영역에서의 '클릭'을 보여준다.
검색과 구매 사이의 중간 단계라 서로 독립적인 채널로 쓸 수 있다.

이 저장소에서 가장 중요한 역할은 성별·연령 분해다. 연구계획서의 검증 기준 중
"특정 연령·성별에 국한된 현상은 아닌지"를 판단할 수 있는 유일한 공개 소스다.
전용 엔드포인트가 한 번의 요청으로 그룹별 시계열을 돌려주므로, 필터를 바꿔가며
여러 번 부르는 것보다 정확하다(각 응답이 자기 요청 안에서만 정규화되기 때문).

값의 성격은 검색어 트렌드와 같다. 절대 클릭수가 아니라 상대 지수다.
"""

from __future__ import annotations

from typing import Any, Dict, Iterator, List, Optional, Sequence

from ..models import RawRecord
from .naver_base import NaverCollector

BASE = "/v1/datalab/shopping"
PATHS = {
    "category":           f"{BASE}/categories",
    "category_device":    f"{BASE}/category/device",
    "category_gender":    f"{BASE}/category/gender",
    "category_age":       f"{BASE}/category/age",
    "keyword":            f"{BASE}/category/keywords",
    "keyword_device":     f"{BASE}/category/keyword/device",
    "keyword_gender":     f"{BASE}/category/keyword/gender",
    "keyword_age":        f"{BASE}/category/keyword/age",
}

#: 쇼핑인사이트의 연령 코드. 검색어 트렌드(1~11)와 체계가 다르다. 섞어 쓰면 안 된다.
#: 실제 응답 값은 scripts/verify_naver_key.py 가 확인한다.
AGE_CODES = ("10", "20", "30", "40", "50", "60")

#: 1차 분석 범위(상의)의 네이버 쇼핑 카테고리 코드.
#: 코드는 shopping.naver.com 의 쇼핑인사이트 분야 선택에서 확인해 채운다.
#: 추측해서 넣으면 조용히 엉뚱한 분야를 수집하게 되므로 비워 둔다.
TOPS_CATEGORIES: Dict[str, str] = {}


class NaverShoppingCollector(NaverCollector):
    channel = "naver_shopping"
    earliest_start_date = "2017-08-01"

    # ------------------------------------------------------------ 분야 단위

    def collect_category(
        self,
        categories: Dict[str, Sequence[str]],
        start_date: str,
        end_date: str,
        time_unit: str = "date",
        run_id: Optional[str] = None,
    ) -> Iterator[RawRecord]:
        """분야별 클릭 추이. categories 는 {표시이름: [카테고리코드, ...]}."""
        payload = {
            "startDate": start_date,
            "endDate": end_date,
            "timeUnit": time_unit,
            "category": [{"name": n, "param": list(p)} for n, p in categories.items()],
        }
        yield from self._emit(
            self.post(PATHS["category"], payload),
            metric_type="click_index",
            entity="",
            context={"kind": "category", "time_unit": time_unit,
                     "query_start": start_date, "query_end": end_date},
            run_id=run_id,
        )

    # ---------------------------------------------------------- 키워드 단위

    def collect_keyword(
        self,
        category_code: str,
        keyword_groups: Dict[str, Sequence[str]],
        start_date: str,
        end_date: str,
        time_unit: str = "date",
        run_id: Optional[str] = None,
    ) -> Iterator[RawRecord]:
        """특정 분야 안에서 키워드별 클릭 추이."""
        payload = {
            "startDate": start_date,
            "endDate": end_date,
            "timeUnit": time_unit,
            "category": category_code,
            "keyword": [{"name": n, "param": list(p)} for n, p in keyword_groups.items()],
        }
        yield from self._emit(
            self.post(PATHS["keyword"], payload),
            metric_type="click_index",
            entity="",
            context={"kind": "keyword", "category_code": category_code,
                     "time_unit": time_unit,
                     "query_start": start_date, "query_end": end_date},
            run_id=run_id,
        )

    def collect_keyword_demographics(
        self,
        category_code: str,
        keyword: str,
        start_date: str,
        end_date: str,
        time_unit: str = "date",
        run_id: Optional[str] = None,
    ) -> Iterator[RawRecord]:
        """한 키워드의 성별·연령 분해.

        검증 기준 "특정 연령·성별에 국한된 현상인가"에 직접 답하는 자료다.
        분포가 한쪽으로 쏠려 있으면 확산이 아니라 국소 현상일 가능성을 시사한다.
        """
        for kind, prefix in (("keyword_gender", "gender"), ("keyword_age", "age")):
            payload = {
                "startDate": start_date,
                "endDate": end_date,
                "timeUnit": time_unit,
                "category": category_code,
                "keyword": keyword,
            }
            response = self.post(PATHS[kind], payload)
            for result in self.series(response):
                for point in result.get("data") or []:
                    group = str(point.get("group", ""))
                    yield RawRecord(
                        channel=self.channel,
                        keyword_raw=result.get("title") or keyword,
                        entity=f"{prefix}={group}",
                        metric_type="click_index",
                        metric_value=point["ratio"],
                        observed_at=point["period"],
                        metadata={
                            "kind": kind,
                            "group": group,
                            "category_code": category_code,
                            "time_unit": time_unit,
                            "query_start": start_date,
                            "query_end": end_date,
                            "normalized": True,
                            "note": "요청 안에서 정규화된 상대 지수",
                        },
                        run_id=run_id,
                    )

    # ------------------------------------------------------------------

    def collect(self, **kwargs: Any) -> Iterator[RawRecord]:
        """기본 진입점. 무엇을 수집할지 명시적으로 고르게 한다."""
        raise NotImplementedError(
            "collect_category / collect_keyword / collect_keyword_demographics "
            "중 하나를 골라 호출할 것"
        )

    def _emit(
        self,
        response: Dict[str, Any],
        metric_type: str,
        entity: str,
        context: Dict[str, Any],
        run_id: Optional[str],
    ) -> Iterator[RawRecord]:
        for result in self.series(response):
            title = result.get("title") or ""
            params: List[str] = result.get("keyword") or result.get("category") or []
            for point in result.get("data") or []:
                yield RawRecord(
                    channel=self.channel,
                    keyword_raw=title,
                    entity=entity,
                    metric_type=metric_type,
                    metric_value=point["ratio"],
                    observed_at=point["period"],
                    metadata={**context, "params": params, "normalized": True,
                              "note": "요청 안에서 정규화된 상대 지수"},
                    run_id=run_id,
                )
