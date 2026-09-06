"""수집 모듈 공통 인터페이스."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Iterable, List

from ..models import RawRecord


class Collector(ABC):
    """모든 수집기의 기반 클래스.

    구현체가 지켜야 할 것:
      * channel 을 models.CHANNELS 에 등록된 값으로 선언한다.
      * 모든 레코드에 observed_at(지표가 가리키는 시점)을 채운다. 오늘 날짜로 대충
        채우면 역추적 재현이 불가능해진다.
      * 네트워크 호출 사이에는 sleep() 으로 간격을 둔다.
    """

    channel: str = ""
    #: 연속 요청 사이 최소 간격(초)
    min_interval_sec: float = 1.5

    def __init__(self) -> None:
        if not self.channel:
            raise NotImplementedError(f"{type(self).__name__} 이 channel 을 선언하지 않았다")
        self._last_call: float = 0.0

    def sleep(self) -> None:
        """직전 호출로부터 min_interval_sec 가 지나도록 대기한다."""
        elapsed = time.monotonic() - self._last_call
        remaining = self.min_interval_sec - elapsed
        if remaining > 0:
            time.sleep(remaining)
        self._last_call = time.monotonic()

    @abstractmethod
    def collect(self, **kwargs: object) -> Iterable[RawRecord]:
        """수집 결과를 RawRecord 로 내놓는다."""

    def collect_list(self, **kwargs: object) -> List[RawRecord]:
        return list(self.collect(**kwargs))
