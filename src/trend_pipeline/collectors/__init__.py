"""소스별 수집 모듈.

각 소스는 데이터 형식·수집 주기·노이즈 특성이 다르므로 모듈을 분리해서 구현하고,
반환값만 공통 RawRecord 로 통일한다.
"""

from .base import Collector

__all__ = ["Collector"]
