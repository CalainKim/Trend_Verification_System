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

CHANNELS = frozenset(
    {"musinsa_rank", "naver_datalab", "naver_shopping", "gtrends", "news", "commerce_rank"}
)


def utcnow_iso() -> str:
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
