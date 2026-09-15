"""NAVER API HUB 공통 계층 (데이터랩 검색어 트렌드 · 쇼핑인사이트).

데이터랩 API 는 developers.naver.com 이 아니라 네이버 클라우드 플랫폼의
NAVER API HUB 를 통해 제공된다. 그래서 인증 헤더가 X-Naver-Client-* 가 아니라
X-NCP-APIGW-* 이고 호스트도 openapi.naver.com 이 아니다. 예전 방식으로 부르면
키가 멀쩡해도 401 이 난다.

경로는 실제 호출로 확인했다(2026-09-15). 문서에 전체 경로가 나와 있지 않아
추측하면 404 만 돌아온다.

두 API 는 인증 방식과 응답 구조가 같아서 HTTP 계층을 공유한다.

중요 - 값의 성격:
  두 API 모두 절대량이 아니라 **요청 안에서 정규화된 상대 지수**를 돌려준다.
  조회 구간의 최댓값이 100 이 되도록 스케일된 값이므로,
  요청이 다르면 값을 직접 비교할 수 없다. 서로 다른 케이스의 지수를 그대로
  비교하면 잘못된 결론이 나온다. 비교가 필요하면 같은 요청 안에 함께 넣거나,
  변화율·기울기처럼 스케일에 영향받지 않는 형태로 바꿔서 써야 한다.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

import requests

from .base import Collector

API_HOST = "https://naverapihub.apigw.ntruss.com"


class NaverApiError(RuntimeError):
    def __init__(self, status: int, body: str, path: str):
        self.status, self.body, self.path = status, body, path
        super().__init__(f"네이버 API 실패 [{status}] {path}: {body[:300]}")


class NaverCollector(Collector):
    """인증·요청·오류 처리를 담당하는 기반 클래스."""

    #: 조회 가능한 가장 이른 날짜. API 가 실제로 거절하는 경계는
    #: scripts/verify_naver_key.py 가 실측해서 확인한다.
    earliest_start_date: str = "2016-01-01"

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        min_interval_sec: float = 0.3,
        timeout_sec: float = 20.0,
        session: Optional[requests.Session] = None,
    ) -> None:
        super().__init__()
        self.min_interval_sec = min_interval_sec
        self.timeout_sec = timeout_sec
        self.session = session or requests.Session()
        self.session.headers.update(
            {
                "X-NCP-APIGW-API-KEY-ID": client_id,
                "X-NCP-APIGW-API-KEY": client_secret,
                "Content-Type": "application/json",
            }
        )

    def post(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        self.sleep()
        resp = self.session.post(
            API_HOST + path,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            timeout=self.timeout_sec,
        )
        if resp.status_code != 200:
            raise NaverApiError(resp.status_code, resp.text, path)
        return resp.json()

    @staticmethod
    def series(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        """응답에서 결과 묶음을 꺼낸다. 두 API 가 같은 모양을 쓴다."""
        return payload.get("results") or []
