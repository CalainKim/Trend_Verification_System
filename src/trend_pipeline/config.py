"""환경 설정 로딩.

키는 .env 에만 두고 코드나 저장소에 넣지 않는다(.gitignore 처리되어 있다).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, Tuple

ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = ROOT / ".env"


class MissingCredentials(RuntimeError):
    """API 키가 없을 때. 무엇을 해야 하는지까지 알려준다."""


def load_env(path: Optional[Path] = None) -> None:
    """.env 를 읽어 환경변수로 올린다. 이미 설정된 값은 덮어쓰지 않는다."""
    path = path or ENV_PATH
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def naver_credentials() -> Tuple[str, str]:
    """(client_id, client_secret). 없으면 발급 방법을 담아 예외를 낸다."""
    load_env()
    cid = os.environ.get("NAVER_CLIENT_ID", "").strip()
    secret = os.environ.get("NAVER_CLIENT_SECRET", "").strip()
    if not cid or not secret:
        raise MissingCredentials(
            "네이버 API 키가 없다.\n"
            "  1. https://developers.naver.com -> Application -> 애플리케이션 등록\n"
            "  2. 사용 API 에서 '데이터랩 (검색어 트렌드)' 와 '데이터랩 (쇼핑인사이트)' 를 모두 체크\n"
            "  3. 발급받은 값을 프로젝트 루트 .env 에 넣는다 (.env.example 참고)\n"
            "       NAVER_CLIENT_ID=...\n"
            "       NAVER_CLIENT_SECRET=...\n"
            "  4. python scripts/verify_naver_key.py 로 확인"
        )
    return cid, secret
