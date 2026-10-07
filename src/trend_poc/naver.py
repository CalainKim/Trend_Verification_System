"""Request-scoped Naver JSON archives for the small retrospective PoC.

Developers and Cloud credentials use different hosts and headers. A selected
provider is never silently changed, and unsuccessful responses are never saved
as evidence. Archive times record when this program acquired a response, not
when the underlying historical observation first became available.
"""

from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import uuid

import requests


URLS = {
    "developers": {
        "shopping": "https://openapi.naver.com/v1/datalab/shopping/category/keywords",
        "search": "https://openapi.naver.com/v1/datalab/search",
    },
    "cloud": {
        "shopping": "https://naverapihub.apigw.ntruss.com/shopping/v1/category/keywords",
        "search": "https://naverapihub.apigw.ntruss.com/search-trend/v1/search",
    },
}
HEADER_NAMES = {
    "developers": ("X-Naver-Client-Id", "X-Naver-Client-Secret"),
    "cloud": ("X-NCP-APIGW-API-KEY-ID", "X-NCP-APIGW-API-KEY"),
}


class NaverError(RuntimeError):
    """A safe error containing a fixed code, never an HTTP body or credential."""

    def __init__(self, code, message, status=None):
        self.code = code
        self.status = status
        super().__init__(message)


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(value):
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _credentials(root):
    """Parse only literal Naver assignments. Do not expand variables or code."""
    values = {}
    allowed = ("NAVER_CLIENT_ID", "NAVER_CLIENT_SECRET")
    env_path = root / ".env"
    if env_path.is_file():
        try:
            lines = env_path.read_text(encoding="utf-8-sig").splitlines()
        except (OSError, UnicodeError):
            raise NaverError("CREDENTIALS_UNREADABLE", "네이버 인증 설정 파일을 읽을 수 없습니다.") from None
        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            key, value = key.strip(), value.strip()
            if key not in allowed:
                continue
            if value[:1] in ("'", '"'):
                quote = value[0]
                closing = value.find(quote, 1)
                if closing < 0 or (value[closing + 1:].strip() and not value[closing + 1:].strip().startswith("#")):
                    raise NaverError("CREDENTIALS_INVALID", "네이버 인증 설정의 따옴표 형식을 확인하세요.")
                value = value[1:closing]
            else:
                value = value.split(" #", 1)[0].strip()
            values[key] = value
    for key in allowed:
        if key in os.environ:
            values[key] = os.environ[key].strip()
    if not all(values.get(key) for key in allowed):
        raise NaverError("CREDENTIALS_MISSING", "NAVER_CLIENT_ID와 NAVER_CLIENT_SECRET 설정이 필요합니다.")
    return values


def _day(value):
    if not isinstance(value, str):
        raise ValueError("not an ISO date")
    parsed = date.fromisoformat(value)
    if parsed.isoformat() != value:
        raise ValueError("not a full ISO date")
    return parsed


def _payload(channel, keywords, start_date, end_date, *, time_unit="date"):
    if channel not in ("shopping", "search"):
        raise NaverError("INVALID_CHANNEL", "채널은 shopping 또는 search여야 합니다.")
    if time_unit not in ("date", "month"):
        raise NaverError("INVALID_TIME_UNIT", "time_unit은 date 또는 month여야 합니다.")
    if (not isinstance(keywords, list) or not 1 <= len(keywords) <= 5
            or any(not isinstance(word, str) or not word.strip() for word in keywords)):
        raise NaverError("INVALID_KEYWORDS", "비어 있지 않은 키워드 문자열을 목록으로 1~5개 지정하세요.")
    keywords = [word.strip() for word in keywords]
    if len(set(keywords)) != len(keywords):
        raise NaverError("INVALID_KEYWORDS", "중복 키워드는 한 요청에 넣을 수 없습니다.")
    try:
        first, last = _day(start_date), _day(end_date)
        if first > last:
            raise ValueError("reversed date range")
    except (ValueError, TypeError):
        raise NaverError("INVALID_DATES", "시작일과 종료일을 순서에 맞는 YYYY-MM-DD 형식으로 지정하세요.") from None
    if time_unit == "month" and (first.day != 1 or last.day != monthrange(last.year, last.month)[1]):
        raise NaverError("PARTIAL_MONTH_RANGE", "월간 요청은 시작 월의 1일부터 종료 월의 말일까지 지정해야 합니다.")
    payload = {"startDate": start_date, "endDate": end_date, "timeUnit": time_unit, "gender": "m"}
    if channel == "shopping":
        payload.update(category="50000169", ages=["20"],
                       keyword=[{"name": word, "param": [word]} for word in keywords])
    else:
        payload.update(ages=["3", "4"],
                       keywordGroups=[{"groupName": word, "keywords": [word]} for word in keywords])
    return payload


def _validate_response(channel, payload, response):
    """Validate provenance and points without imputing missing days or months."""
    if not isinstance(response, dict) or any(response.get(key) != payload[key]
                                            for key in ("startDate", "endDate", "timeUnit")):
        raise NaverError("RESPONSE_WINDOW_MISMATCH", "응답 기간 또는 집계 단위가 요청과 다릅니다.")
    if channel == "shopping":
        keywords = [group["name"] for group in payload["keyword"]]
        parameter_key = "keyword"
    else:
        keywords = [group["groupName"] for group in payload["keywordGroups"]]
        parameter_key = "keywords"
    results = response.get("results")
    if not isinstance(results, list) or len(results) != len(keywords):
        raise NaverError("RESPONSE_KEYWORD_MISMATCH", "요청한 모든 키워드의 결과를 확인하지 못했습니다.")
    first, last = _day(payload["startDate"]), _day(payload["endDate"])
    if payload["timeUnit"] == "month":
        # Year/month ordinals avoid adding an overflowing month to December and
        # work across leap years without converting monthly indices to days.
        start_month, end_month = first.year * 12 + first.month - 1, last.year * 12 + last.month - 1
        dates = [date(ordinal // 12, ordinal % 12 + 1, 1).isoformat()
                 for ordinal in range(start_month, end_month + 1)]
    else:
        dates = [(first + timedelta(days=offset)).isoformat() for offset in range((last - first).days + 1)]
    requested_dates = set(dates)
    missing, seen_titles = {}, set()
    for result in results:
        if not isinstance(result, dict):
            raise NaverError("RESPONSE_KEYWORD_MISMATCH", "키워드 결과 형식이 올바르지 않습니다.")
        title = result.get("title")
        if (not isinstance(title, str) or title not in keywords or title in seen_titles
                or result.get(parameter_key) != [title] or not isinstance(result.get("data"), list)):
            raise NaverError("RESPONSE_KEYWORD_MISMATCH", "응답 키워드 또는 표현 목록이 요청과 다릅니다.")
        seen_titles.add(title)
        observed = set()
        for point in result["data"]:
            if not isinstance(point, dict):
                raise NaverError("INVALID_OBSERVATION", "응답 관측 행의 형식이 올바르지 않습니다.")
            day, ratio = point.get("period"), point.get("ratio")
            if not isinstance(day, str) or day not in requested_dates or day in observed:
                raise NaverError("INVALID_OBSERVATION_DATE", "응답에 중복 또는 조회 기간·집계 단위에 맞지 않는 관측일이 있습니다.")
            if (isinstance(ratio, bool) or not isinstance(ratio, (int, float))
                    or not math.isfinite(ratio) or not 0 <= ratio <= 100):
                raise NaverError("INVALID_OBSERVATION_RATIO", "응답 지수가 유한한 0~100 수치가 아닙니다.")
            observed.add(day)
        missing[title] = [day for day in dates if day not in observed]
    return missing


def _write_immutable(path, record):
    """Publish a complete JSON file without replacing an existing archive."""
    text = json.dumps(record, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name("." + path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        with temporary.open("x", encoding="utf-8") as target:
            target.write(text)
            target.flush()
            os.fsync(target.fileno())
        # Hard-link publication is atomic and fails if the final path exists.
        os.link(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


class NaverClient:
    def __init__(self, root: Path, provider="developers", session=None):
        if provider not in URLS:
            raise NaverError("INVALID_PROVIDER", "provider는 developers 또는 cloud여야 합니다.")
        self.root = Path(root)
        self.provider = provider
        self.session = session if session is not None else requests.Session()
        self._owns_session = session is None
        # requests' default adapters perform zero retries. Per-call headers avoid
        # leaving secrets in a supplied session or mixing providers' credentials.

    def close(self):
        if self._owns_session:
            self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def _read_cache(self, path, channel, url, payload, request_hash):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
            if (not isinstance(record, dict) or record.get("status") != "complete"
                    or record.get("provider") != self.provider or record.get("channel") != channel
                    or record.get("url") != url or record.get("payload") != payload
                    or record.get("request_sha256") != request_hash
                    or record.get("response_sha256") != _digest(record.get("response"))
                    or record.get("record_sha256") != _digest({key: value for key, value in record.items() if key != "record_sha256"})):
                raise ValueError("cache provenance mismatch")
            if record.get("missing_dates") != _validate_response(channel, payload, record["response"]):
                raise ValueError("cache missing-days mismatch")
            return record
        except (OSError, UnicodeError, ValueError, TypeError, NaverError):
            raise NaverError("INVALID_CACHE", "보존된 요청 파일의 형식 또는 해시가 일치하지 않습니다. 원본을 확인하세요.") from None

    def fetch(self, channel, keywords, start_date, end_date, archive_dir: Path, *, time_unit="date"):
        """Fetch once or return an exact request's validated, immutable cache.

        ``request_sha256`` covers ``{"url": url, "payload": payload}``, so
        provider, channel, population, keywords, aggregation and normalization
        window all participate in the cache key. There is no retry, redirect or
        fallback. Monthly requests require whole calendar months; their retained
        ``missing_dates`` lists missing month-start periods rather than days.
        """
        payload = _payload(channel, keywords, start_date, end_date, time_unit=time_unit)
        url = URLS[self.provider][channel]
        request_hash = _digest({"url": url, "payload": payload})
        archive_dir = Path(archive_dir)
        path = archive_dir / f"{self.provider}-{channel}-{request_hash}.json"
        try:
            if path.exists():
                return self._read_cache(path, channel, url, payload, request_hash)
            values = _credentials(self.root)
            id_header, secret_header = HEADER_NAMES[self.provider]
            headers = {id_header: values["NAVER_CLIENT_ID"], secret_header: values["NAVER_CLIENT_SECRET"],
                       "Content-Type": "application/json"}
            try:
                response = self.session.post(url, data=_canonical(payload).encode("utf-8"),
                                             headers=headers, timeout=(10, 60), allow_redirects=False)
            except Exception:
                raise NaverError("NETWORK_ERROR", "네이버 요청이 연결 또는 통신 오류로 실패했습니다. 자동 재시도하지 않았습니다.") from None
            if response.status_code != 200:
                status = response.status_code if isinstance(response.status_code, int) else None
                raise NaverError("HTTP_ERROR", f"네이버 API 요청이 HTTP {status}로 실패했습니다. 선택한 provider를 확인하세요.", status)
            try:
                raw = response.json()
            except Exception:
                raise NaverError("INVALID_JSON", "네이버 응답을 JSON으로 해석할 수 없습니다.") from None
            missing = _validate_response(channel, payload, raw)
            stamp = _now()
            record = {"id": "naver-" + uuid.uuid4().hex, "channel": channel, "provider": self.provider,
                      "url": url, "payload": payload, "response": raw, "collected_at": stamp,
                      "available_at": stamp, "response_sha256": _digest(raw), "request_sha256": request_hash,
                      "status": "complete", "missing_dates": missing}
            record["record_sha256"] = _digest(record)
            try:
                _write_immutable(path, record)
            except FileExistsError:
                return self._read_cache(path, channel, url, payload, request_hash)
            return record
        except NaverError as error:
            self._record_error(archive_dir, channel, url, request_hash, error)
            raise
        except (OSError, UnicodeError, ValueError, TypeError):
            error = NaverError("ARCHIVE_ERROR", "네이버 원본 응답의 보존 또는 형식 검증을 완료하지 못했습니다.")
            self._record_error(archive_dir, channel, url, request_hash, error)
            raise error from None

    def _record_error(self, archive_dir, channel, url, request_hash, error):
        entry = {"id": "error-" + uuid.uuid4().hex, "status": "failed", "provider": self.provider,
                 "channel": channel, "url": url, "request_sha256": request_hash,
                 "occurred_at": _now(), "code": error.code, "http_status": error.status}
        try:
            _write_immutable(archive_dir / "errors" / (entry["id"] + ".json"), entry)
        except OSError:
            pass  # Keep the original safe exception when error logging also fails.
