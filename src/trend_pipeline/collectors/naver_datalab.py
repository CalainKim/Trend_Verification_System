"""네이버 데이터랩 통합검색어 트렌드 수집기.

국내 관심도의 메인 지표. 과거 구간을 소급 조회할 수 있어 트랙 A(역추적)의
중심 소스다.

값은 절대 검색량이 아니라 요청 안에서 정규화된 상대 지수다(naver_base 참고).
성별·연령 분해는 필터를 바꿔 요청을 나눠 보내는 방식이라, 각 분해 결과도
자기 요청 안에서만 상대값이다. 분해 결과끼리 비율을 비교하려면 한 번의 요청에
넣을 수 없으므로 주의해야 한다.
"""

from __future__ import annotations

from typing import Any, Dict, Iterator, List, Optional, Sequence

from ..models import RawRecord
from .naver_base import NaverCollector

PATH = "/v1/datalab/search"

TIME_UNITS = ("date", "week", "month")
DEVICES = (None, "pc", "mo")
GENDERS = (None, "m", "f")

#: 검색어 트렌드의 연령 코드. 쇼핑인사이트와 체계가 다르므로 섞어 쓰면 안 된다.
#: 실제 경계는 scripts/verify_naver_key.py 가 응답으로 확인한다.
AGE_CODES = {
    "1": "0-12", "2": "13-18", "3": "19-24", "4": "25-29", "5": "30-34",
    "6": "35-39", "7": "40-44", "8": "45-49", "9": "50-54", "10": "55-59",
    "11": "60+",
}

MAX_KEYWORD_GROUPS = 5
MAX_KEYWORDS_PER_GROUP = 20


class NaverDataLabCollector(NaverCollector):
    channel = "naver_datalab"

    def collect(
        self,
        keyword_groups: Dict[str, Sequence[str]],
        start_date: str,
        end_date: str,
        time_unit: str = "date",
        device: Optional[str] = None,
        gender: Optional[str] = None,
        ages: Optional[Sequence[str]] = None,
        run_id: Optional[str] = None,
    ) -> Iterator[RawRecord]:
        """keyword_groups 는 {대표어: [동의어, ...]}.

        하나의 그룹은 그 안의 표현들을 합산한 하나의 시계열이 된다.
        '발라클라바'와 '바라클라바'처럼 표기만 다른 경우 같은 그룹에 넣는다.
        """
        if time_unit not in TIME_UNITS:
            raise ValueError(f"time_unit 은 {TIME_UNITS} 중 하나여야 한다: {time_unit!r}")
        if not keyword_groups:
            raise ValueError("keyword_groups 가 비어 있다")
        if len(keyword_groups) > MAX_KEYWORD_GROUPS:
            raise ValueError(
                f"한 요청에 키워드 그룹은 최대 {MAX_KEYWORD_GROUPS}개다 "
                f"(요청: {len(keyword_groups)}개). 나눠서 호출할 것."
            )
        for name, words in keyword_groups.items():
            if not words:
                raise ValueError(f"그룹 {name!r} 에 키워드가 없다")
            if len(words) > MAX_KEYWORDS_PER_GROUP:
                raise ValueError(
                    f"그룹 {name!r} 의 키워드가 {len(words)}개다 "
                    f"(최대 {MAX_KEYWORDS_PER_GROUP}개)"
                )

        payload: Dict[str, Any] = {
            "startDate": start_date,
            "endDate": end_date,
            "timeUnit": time_unit,
            "keywordGroups": [
                {"groupName": name, "keywords": list(words)}
                for name, words in keyword_groups.items()
            ],
        }
        if device:
            payload["device"] = device
        if gender:
            payload["gender"] = gender
        if ages:
            payload["ages"] = list(ages)

        # 분해 조건을 entity 에 남겨야 전체 시계열과 구분되어 저장된다.
        entity = segment_key(device=device, gender=gender, ages=ages)
        response = self.post(PATH, payload)

        for result in self.series(response):
            group_name = result.get("title") or ""
            keywords: List[str] = result.get("keywords") or []
            for point in result.get("data") or []:
                yield RawRecord(
                    channel=self.channel,
                    keyword_raw=group_name,
                    entity=entity,
                    metric_type="search_index",
                    metric_value=point["ratio"],
                    observed_at=point["period"],
                    metadata={
                        "keywords": keywords,
                        "time_unit": time_unit,
                        "device": device,
                        "gender": gender,
                        "ages": list(ages) if ages else None,
                        "query_start": start_date,
                        "query_end": end_date,
                        "normalized": True,
                        "note": "요청 안에서 최댓값 100 으로 정규화된 상대 지수",
                    },
                    run_id=run_id,
                )


def segment_key(
    device: Optional[str] = None,
    gender: Optional[str] = None,
    ages: Optional[Sequence[str]] = None,
) -> str:
    """분해 조건을 나타내는 entity 키. 조건이 없으면 빈 문자열(전체)."""
    parts = []
    if device:
        parts.append(f"device={device}")
    if gender:
        parts.append(f"gender={gender}")
    if ages:
        parts.append("ages=" + "+".join(ages))
    return ";".join(parts)
