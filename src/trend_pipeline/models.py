"""수집 레코드의 공통 표현.

소스별 수집 모듈은 서로 다른 형식을 읽지만, 저장은 전부 RawRecord 한 종류로 통일한다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional

# 'YYYY-MM-DD' 또는 'YYYY-MM-DDTHH:MM:SS(+09:00)' 형태만 허용한다.
# 앞 10자리가 항상 날짜라서 문자열 비교만으로 T_cut 필터가 성립한다.
_OBSERVED_AT_RE = re.compile(r"^\d{4}-\d{2}-\d{2}([T ]\d{2}:\d{2}(:\d{2})?([+-]\d{2}:\d{2}|Z)?)?$")

#: 채널은 "자료가 어디서 왔나" 다. 운영사가 같으면 한 채널로 묶는다.
#: 29CM 는 무신사 계열이라 commerce_rank 하나에 들어 있다. 코오롱몰과
#: 하이버는 운영사가 달라서 따로 센다.
#:
#: 채널을 쪼개 두는 데는 격리 목적도 있다. persistence 의 질의가 전부
#: `channel = ?` 로 걸리므로, 새 수집 대상을 새 채널에 넣으면 이미 쌓인
#: 자료로 돌아가는 분석이 구조적으로 안 바뀐다. 검증 파트가 commerce_rank
#: 상의 범위로 모델을 학습하는 동안 그 범위를 건드리지 않는 방법이다.
CHANNELS = frozenset(
    {
        "musinsa_rank",
        "naver_datalab",
        "naver_shopping",
        "gtrends",
        "news",
        "commerce_rank",   # 29CM. 무신사 계열이라 무신사와 같은 채널이다
        "kolon_rank",      # 코오롱몰. 2026-11-05 부터
        "hiver_rank",      # 하이버(브랜디 계열). 2026-11-05 부터
    }
)


#: 구글 트렌드 속성. 빈 문자열은 웹 검색이다.
#: youtube 를 쓰면 숏폼 유행이 검색으로 넘어온 흔적을 볼 수 있다.
GTRENDS_PROPS = ("", "youtube", "news", "images", "froogle")


def geo_entity(geo: str, gprop: str = "") -> str:
    """구글 트렌드 레코드의 entity 키를 만든다.

    웹 검색에는 접미사를 붙이지 않는다. 붙이면 이미 쌓인 자료와 키가 달라져
    과거 수집분이 조회에서 통째로 빠진다. 새 속성만 접미사를 받는다.

        geo_entity("KR")             -> 'geo=KR'
        geo_entity("KR", "youtube")  -> 'geo=KR;prop=youtube'
    """
    if gprop not in GTRENDS_PROPS:
        raise ValueError(f"알 수 없는 구글 트렌드 속성: {gprop!r}")
    base = f"geo={geo or 'WORLD'}"
    return f"{base};prop={gprop}" if gprop else base


def utcnow_iso() -> str:
    """지금 시각을 세계 표준시(UTC) 초 단위 문자열로 돌려준다."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class RecordError(ValueError):
    """레코드가 공통 스키마 규약을 어겼을 때."""


@dataclass
class RawRecord:
    """signal_raw 한 행.

    observed_at 은 '지표가 가리키는 시점', collected_at 은 '우리가 가져온 시점'이다.
    역추적 실험에서 데이터 누수를 막는 기준은 언제나 observed_at 이다.
    """

    channel: str
    keyword_raw: str
    metric_type: str
    metric_value: float
    observed_at: str
    entity: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    collected_at: str = field(default_factory=utcnow_iso)
    run_id: Optional[str] = None

    def __post_init__(self) -> None:
        """기록을 만들자마자 필수 칸과 날짜 형식을 검사한다. 잘못된 값은 DB 에 들어가기 전에 막는다."""
        if not self.channel:
            raise RecordError("channel 은 비어 있을 수 없다")
        if self.channel not in CHANNELS:
            raise RecordError(f"알 수 없는 channel: {self.channel!r} (CHANNELS 에 먼저 등록할 것)")
        if not self.keyword_raw:
            raise RecordError("keyword_raw 는 비어 있을 수 없다")
        if not self.metric_type:
            raise RecordError("metric_type 은 비어 있을 수 없다")
        if not _OBSERVED_AT_RE.match(self.observed_at):
            raise RecordError(
                f"observed_at 형식이 잘못됨: {self.observed_at!r} "
                "('YYYY-MM-DD' 또는 ISO8601 datetime 이어야 한다)"
            )
        try:
            self.metric_value = float(self.metric_value)
        except (TypeError, ValueError) as exc:
            raise RecordError(f"metric_value 를 float 로 변환할 수 없음: {self.metric_value!r}") from exc

    @property
    def observed_date(self) -> str:
        """observed_at 의 날짜 부분(YYYY-MM-DD)."""
        return self.observed_at[:10]
