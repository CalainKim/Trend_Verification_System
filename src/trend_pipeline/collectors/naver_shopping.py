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
from .naver_base import NaverCollector, segment_key

BASE = "/shopping/v1"
#: 쇼핑인사이트는 키워드 그룹 하나에 표현을 하나만 받는다. 검색어 트렌드가
#: 한 그룹에 동의어를 최대 20개까지 묶어 합산해 주는 것과 다르다. 여러 개를 넣으면
#: 400 "should NOT have more than 1 items" 가 난다. 동의어는 그룹을 나눠서 보내고,
#: 합산이 필요하면 받은 뒤에 우리가 합친다.
MAX_PARAMS_PER_KEYWORD = 1

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
#: 2026-09-15 실제 응답으로 확인한 값이다.
AGE_CODES = ("10", "20", "30", "40", "50", "60")
GENDER_CODES = ("f", "m")
DEVICE_CODES = ("pc", "mo")

#: 1차 MVP 대상. 쇼핑인사이트는 10년 단위라 코드 하나면 된다(검색어 트렌드는 5세 단위).
TWENTIES = ("20",)

#: 성별과 연령을 함께 지정하면 교차 조건이 적용된다. 2026-09-27 실측 확인:
#: 여성의류>티셔츠에서 남성+20대(11일) / 여성+20대(58일) / 남성+30대(37일) /
#: 20대만(59일)이 모두 다른 시계열이었다.
#:
#: 주의: 좁힐수록 응답 일수가 급격히 줄어든다. 클릭이 없는 날은 행 자체가
#: 빠져서 오므로, "0 클릭"과 "데이터 없음"이 구분되지 않는다. 조회 구간과 실제
#: 반환 일수를 메타데이터에 남겨 다운스트림이 커버리지를 알 수 있게 한다.
SUPPORTS_CROSS_FILTER = True

#: 상위 분야 코드. 실제 호출로 확인했다.
FASHION_CLOTHING = "50000000"

#: 1차 분석 범위(상의)의 네이버 쇼핑 카테고리 코드.
#: datalab 쇼핑인사이트에서 분야를 고를 때 나가는 요청의 cid 로 확인한다.
#: 추측해서 넣으면 조용히 엉뚱한 분야를 수집하게 되므로, 확인한 것만 넣는다.
#: 50000169 는 조회한 일별 지수가 웹 화면의 티셔츠 차트와 일치함을 대조해 확인했다.
#: 50000167 은 성별 분포로 확인했다. 여성 69.5 / 남성 2.2 로 50000169(남성 44.1 /
#: 여성 15.3)와 정확히 거울상이다.
TOPS_CATEGORIES: Dict[str, str] = {
    "50000167": "패션의류>여성의류>티셔츠",
    "50000169": "패션의류>남성의류>티셔츠",
}

#: 1차 분석 범위의 키워드.
#: 네이버 분류에는 '후드티'나 '맨투맨'이 별도 분야로 없다. 티셔츠 분야 안에
#: 들어 있어서 분야 코드가 아니라 키워드로 조회한다. 같은 요청(50000169) 안에서
#: 비교했을 때 후드티 37.1 / 반팔티 30.4 / 맨투맨 22.9 로 강하게 잡히는 반면,
#: 별도 분야인 니트는 3.0 에 그쳐 이 분류를 확인했다 (2026-08-14~09-14).
TOPS_KEYWORDS: Dict[str, list] = {
    "티셔츠": ["티셔츠", "반팔티", "긴팔티"],
    "후드티": ["후드티", "후드집업"],
    "맨투맨": ["맨투맨", "스웨트셔츠"],
}


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

    def collect_category_demographics(
        self,
        category_code: str,
        start_date: str,
        end_date: str,
        time_unit: str = "date",
        run_id: Optional[str] = None,
    ) -> Iterator[RawRecord]:
        """분야 전체의 성별·연령 분포. 키워드 쏠림을 재는 기준선이다.

        네이버쇼핑은 어느 키워드를 보든 40대가 최다로 나온다. 채널 이용자층이
        그렇기 때문이지 키워드의 특성이 아니다. 키워드 분포를 그대로 읽으면
        모든 키워드가 '40대 트렌드'가 된다.

        분야 전체 분포를 따로 받아 기준선으로 두고, 키워드 분포를 그 대비로
        읽어야 "이 키워드가 어느 연령에 기대 이상으로 쏠렸는가"를 말할 수 있다.
        keyword_raw 에는 분야 코드를 넣어 키워드 행과 구분한다.
        """
        for kind, prefix in (("category_gender", "gender"), ("category_age", "age")):
            payload = {
                "startDate": start_date,
                "endDate": end_date,
                "timeUnit": time_unit,
                "category": category_code,
            }
            response = self.post(PATHS[kind], payload)
            for result in self.series(response):
                points = result.get("data") or []
                for point in points:
                    group = str(point.get("group", ""))
                    yield RawRecord(
                        channel=self.channel,
                        keyword_raw=f"category:{category_code}",
                        entity=f"{prefix}={group}",
                        metric_type="click_index",
                        metric_value=point["ratio"],
                        observed_at=point["period"],
                        metadata={
                            "kind": kind,
                            "role": "baseline",
                            "group": group,
                            "category_code": category_code,
                            "category_name": TOPS_CATEGORIES.get(category_code, ""),
                            "time_unit": time_unit,
                            "query_start": start_date,
                            "query_end": end_date,
                            "returned_days": len(points),
                            "normalized": True,
                            "note": "분야 전체 기준선. 키워드 분포를 이 대비로 읽는다",
                        },
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
        device: Optional[str] = None,
        gender: Optional[str] = None,
        ages: Optional[Sequence[str]] = None,
        run_id: Optional[str] = None,
    ) -> Iterator[RawRecord]:
        """특정 분야 안에서 키워드별 클릭 추이.

        한 그룹에 표현을 하나만 넣을 수 있다(MAX_PARAMS_PER_KEYWORD).
        같은 요청 안의 그룹끼리는 정규화 기준이 같아 서로 비교할 수 있다.
        """
        for name, params in keyword_groups.items():
            if len(params) != MAX_PARAMS_PER_KEYWORD:
                raise ValueError(
                    f"쇼핑인사이트는 키워드 그룹당 표현 1개만 받는다 "
                    f"(그룹 {name!r} 에 {len(params)}개). 검색어 트렌드와 다르다. "
                    f"동의어는 그룹을 나눠서 보낼 것: "
                    f"{{'{name}': ['{params[0] if params else ''}'], ...}}"
                )
        if ages:
            unknown = [a for a in ages if a not in AGE_CODES]
            if unknown:
                raise ValueError(
                    f"쇼핑인사이트 연령 코드가 아니다: {unknown}. "
                    f"{AGE_CODES} 중에서 쓸 것. 검색어 트렌드(1~11)와 체계가 다르다."
                )
        if gender and gender not in GENDER_CODES:
            raise ValueError(f"gender 는 {GENDER_CODES} 중 하나여야 한다: {gender!r}")

        payload: Dict[str, Any] = {
            "startDate": start_date,
            "endDate": end_date,
            "timeUnit": time_unit,
            "category": category_code,
            "keyword": [{"name": n, "param": list(p)} for n, p in keyword_groups.items()],
        }
        if device:
            payload["device"] = device
        if gender:
            payload["gender"] = gender
        if ages:
            payload["ages"] = list(ages)

        yield from self._emit(
            self.post(PATHS["keyword"], payload),
            metric_type="click_index",
            entity=segment_key(device=device, gender=gender, ages=ages),
            context={"kind": "keyword", "category_code": category_code,
                     "time_unit": time_unit, "device": device,
                     "gender": gender, "ages": list(ages) if ages else None,
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
            points = result.get("data") or []
            # 클릭이 없는 날은 응답에서 빠진다. 조회 구간 대비 몇 일이 왔는지
            # 남겨야 다운스트림이 "0 클릭"과 "데이터 없음"을 구분할 수 있다.
            context = {**context, "returned_days": len(points)}
            for point in points:
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
