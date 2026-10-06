"""Offline transport tests; no test calls a live Naver endpoint."""

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from trend_poc.naver import NaverClient, NaverError, URLS


class FakeResponse:
    def __init__(self, payload, status=200, invalid_json=False):
        self.payload = payload
        self.status_code = status
        self.invalid_json = invalid_json

    @property
    def text(self):
        raise AssertionError("HTTP response body must not be read on errors")

    def json(self):
        if self.invalid_json:
            raise ValueError("DO_NOT_SAVE_SECRET_JSON_ERROR")
        return deepcopy(self.payload)


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
        self.headers = {"User-Agent": "fixture"}

    def post(self, url, **kwargs):
        self.calls.append({"url": url, **kwargs})
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        if callable(response):
            return response(json.loads(kwargs["data"]))
        return response


def response_for(payload):
    response = {key: payload[key] for key in ("startDate", "endDate", "timeUnit")}
    shopping = "keyword" in payload
    words = ([group["name"] for group in payload["keyword"]] if shopping else
             [group["groupName"] for group in payload["keywordGroups"]])
    response["results"] = [
        {"title": word, "keyword" if shopping else "keywords": [word],
         "data": [{"period": payload["startDate"], "ratio": 20},
                  {"period": payload["endDate"], "ratio": 100.0}]}
        for word in words
    ]
    return FakeResponse(response)


@pytest.fixture
def environment(tmp_path, monkeypatch):
    for name in ("NAVER_CLIENT_ID", "NAVER_CLIENT_SECRET"):
        monkeypatch.delenv(name, raising=False)
    (tmp_path / ".env").write_text(
        "# Literal settings only\nNAVER_CLIENT_ID='FIXTURE_PRIVATE_ID'\n"
        'NAVER_CLIENT_SECRET="FIXTURE_PRIVATE_SECRET" # comment\n'
        "UNRELATED_KEY=$(must_never_execute)\n", encoding="utf-8",
    )
    return tmp_path


def fetch(client, directory, channel="shopping", start="2026-04-01", end="2026-04-03", words=None):
    return client.fetch(channel, words or ["럭비티"], start, end, directory)


def digest(value):
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@pytest.mark.parametrize("provider,id_header,secret_header", [
    ("developers", "X-Naver-Client-Id", "X-Naver-Client-Secret"),
    ("cloud", "X-NCP-APIGW-API-KEY-ID", "X-NCP-APIGW-API-KEY"),
])
def test_provider_selects_auth_and_host_without_mutating_session(environment, provider, id_header, secret_header):
    session = FakeSession([response_for])
    client = NaverClient(environment, provider=provider, session=session)
    record = fetch(client, environment / "archive")
    call = session.calls[0]
    assert call["url"] == URLS[provider]["shopping"]
    assert call["headers"] == {id_header: "FIXTURE_PRIVATE_ID", secret_header: "FIXTURE_PRIVATE_SECRET",
                               "Content-Type": "application/json"}
    assert session.headers == {"User-Agent": "fixture"}
    assert call["allow_redirects"] is False and call["timeout"] == (10, 60)
    assert record["payload"] == {
        "startDate": "2026-04-01", "endDate": "2026-04-03", "timeUnit": "date",
        "gender": "m", "ages": ["20"], "category": "50000169",
        "keyword": [{"name": "럭비티", "param": ["럭비티"]}],
    }


def test_raw_response_is_immutable_hashed_and_missing_days_are_not_zeroed(environment):
    session = FakeSession([response_for])
    record = fetch(NaverClient(environment, session=session), environment / "archive", words=["럭비티", "맨투맨"])
    assert record["request_sha256"] == digest({"url": record["url"], "payload": record["payload"]})
    assert record["response_sha256"] == digest(record["response"])
    assert record["response"] == response_for(record["payload"]).payload
    assert record["missing_dates"] == {"럭비티": ["2026-04-02"], "맨투맨": ["2026-04-02"]}
    assert len(record["response"]["results"][0]["data"]) == 2
    assert record["collected_at"] == record["available_at"]
    assert record["status"] == "complete"
    paths = list((environment / "archive").glob("*.json"))
    assert len(paths) == 1
    assert json.loads(paths[0].read_text(encoding="utf-8")) == record
    assert "PRIVATE" not in paths[0].read_text(encoding="utf-8")
    assert not list((environment / "archive").glob("*.tmp"))


def test_search_uses_separate_19_to_29_population_and_keyword_shape(environment):
    session = FakeSession([response_for])
    record = fetch(NaverClient(environment, session=session), environment / "archive", channel="search")
    payload = record["payload"]
    assert payload["gender"] == "m" and payload["ages"] == ["3", "4"]
    assert payload["keywordGroups"] == [{"groupName": "럭비티", "keywords": ["럭비티"]}]
    assert "category" not in payload and "keyword" not in payload
    assert record["response"]["results"][0]["keywords"] == ["럭비티"]


def test_exact_cache_reused_without_credentials_or_reissuing_request(environment):
    session = FakeSession([response_for])
    directory = environment / "archive"
    first = fetch(NaverClient(environment, session=session), directory)
    path = next(directory.glob("*.json"))
    before = path.read_bytes()
    (environment / ".env").unlink()
    second = fetch(NaverClient(environment, session=session), directory)
    assert first == second and len(session.calls) == 1
    assert path.read_bytes() == before


def test_provider_channel_window_and_keywords_never_share_cache(environment):
    session = FakeSession([response_for] * 5)
    directory = environment / "archive"
    developers = NaverClient(environment, session=session)
    records = [fetch(developers, directory), fetch(developers, directory, channel="search"),
               fetch(developers, directory, end="2026-04-04"), fetch(developers, directory, words=["맨투맨"]),
               fetch(NaverClient(environment, provider="cloud", session=session), directory)]
    assert len(session.calls) == 5 and len(list(directory.glob("*.json"))) == 5
    assert len({record["request_sha256"] for record in records}) == 5
    assert len({record["id"] for record in records}) == 5


@pytest.mark.parametrize("status", [301, 302, 400, 401, 403, 429, 500])
def test_http_failures_never_retry_redirect_fallback_or_archive_response(environment, status):
    session = FakeSession([FakeResponse({"error": "FIXTURE_PRIVATE_SECRET"}, status=status)])
    directory = environment / "archive"
    with pytest.raises(NaverError) as caught:
        fetch(NaverClient(environment, session=session), directory)
    assert caught.value.code == "HTTP_ERROR" and caught.value.status == status
    assert len(session.calls) == 1
    assert session.calls[0]["url"].startswith("https://openapi.naver.com/")
    assert session.calls[0]["allow_redirects"] is False
    assert not list(directory.glob("*.json"))
    errors = list((directory / "errors").glob("*.json"))
    assert len(errors) == 1
    assert json.loads(errors[0].read_text(encoding="utf-8"))["status"] == "failed"
    assert "PRIVATE" not in errors[0].read_text(encoding="utf-8") + str(caught.value)


@pytest.mark.parametrize("response,code", [
    (RuntimeError("DO_NOT_SAVE_SECRET_NETWORK_EXCEPTION"), "NETWORK_ERROR"),
    (FakeResponse(None, invalid_json=True), "INVALID_JSON"),
])
def test_exception_messages_are_redacted(environment, response, code):
    session = FakeSession([response])
    directory = environment / "archive"
    with pytest.raises(NaverError) as caught:
        fetch(NaverClient(environment, session=session), directory)
    assert caught.value.code == code and len(session.calls) == 1
    saved = "".join(path.read_text(encoding="utf-8") for path in directory.rglob("*.json"))
    assert "DO_NOT_SAVE" not in saved + str(caught.value)
    assert not list(directory.glob("*.json"))


@pytest.mark.parametrize("mutate,code", [
    (lambda r: r.update(startDate="2026-03-31"), "RESPONSE_WINDOW_MISMATCH"),
    (lambda r: r.update(timeUnit="week"), "RESPONSE_WINDOW_MISMATCH"),
    (lambda r: r["results"][0].update(title="다른 키워드"), "RESPONSE_KEYWORD_MISMATCH"),
    (lambda r: r["results"][0].update(keyword=["럭비티", "럭비셔츠"]), "RESPONSE_KEYWORD_MISMATCH"),
    (lambda r: r["results"].append(deepcopy(r["results"][0])), "RESPONSE_KEYWORD_MISMATCH"),
    (lambda r: r["results"][0]["data"].append({"period": "2026-04-01", "ratio": 1}), "INVALID_OBSERVATION_DATE"),
    (lambda r: r["results"][0]["data"][0].update(period="2026-03-31"), "INVALID_OBSERVATION_DATE"),
    (lambda r: r["results"][0]["data"][0].update(ratio=101), "INVALID_OBSERVATION_RATIO"),
    (lambda r: r["results"][0]["data"][0].update(ratio=-1), "INVALID_OBSERVATION_RATIO"),
    (lambda r: r["results"][0]["data"][0].update(ratio=float("nan")), "INVALID_OBSERVATION_RATIO"),
    (lambda r: r["results"][0]["data"][0].update(ratio=float("inf")), "INVALID_OBSERVATION_RATIO"),
    (lambda r: r["results"][0]["data"][0].update(ratio=True), "INVALID_OBSERVATION_RATIO"),
    (lambda r: r["results"][0]["data"][0].update(ratio="20"), "INVALID_OBSERVATION_RATIO"),
])
def test_invalid_response_never_becomes_successful_evidence(environment, mutate, code):
    def invalid(payload):
        response = response_for(payload)
        mutate(response.payload)
        return response
    directory = environment / "archive"
    session = FakeSession([invalid])
    with pytest.raises(NaverError) as caught:
        fetch(NaverClient(environment, session=session), directory)
    assert caught.value.code == code
    assert not list(directory.glob("*.json"))
    assert len(list((directory / "errors").glob("*.json"))) == 1


def test_empty_data_is_valid_but_all_dates_remain_missing(environment):
    def empty(payload):
        response = response_for(payload)
        response.payload["results"][0]["data"] = []
        return response
    record = fetch(NaverClient(environment, session=FakeSession([empty])), environment / "archive")
    assert record["missing_dates"]["럭비티"] == ["2026-04-01", "2026-04-02", "2026-04-03"]
    assert record["response"]["results"][0]["data"] == []


def test_tampered_cache_is_not_used_or_overwritten(environment):
    session = FakeSession([response_for])
    directory = environment / "archive"
    client = NaverClient(environment, session=session)
    record = fetch(client, directory)
    path = next(directory.glob("*.json"))
    record["response"]["results"][0]["data"][0]["ratio"] = 99
    path.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
    before = path.read_bytes()
    with pytest.raises(NaverError, match="해시") as caught:
        fetch(client, directory)
    assert caught.value.code == "INVALID_CACHE"
    assert len(session.calls) == 1 and path.read_bytes() == before


def test_environment_overrides_literal_file_and_missing_settings_are_safe(environment, monkeypatch):
    monkeypatch.setenv("NAVER_CLIENT_ID", "ENV_ID")
    monkeypatch.setenv("NAVER_CLIENT_SECRET", "ENV_SECRET")
    session = FakeSession([response_for])
    fetch(NaverClient(environment, session=session), environment / "archive")
    assert session.calls[0]["headers"]["X-Naver-Client-Id"] == "ENV_ID"
    monkeypatch.setenv("NAVER_CLIENT_SECRET", "")
    with pytest.raises(NaverError) as caught:
        fetch(NaverClient(environment, session=session), environment / "other")
    assert caught.value.code == "CREDENTIALS_MISSING" and len(session.calls) == 1
    assert "ENV_ID" not in str(caught.value)


@pytest.mark.parametrize("channel,words,start,end", [
    ("unknown", ["럭비티"], "2026-04-01", "2026-04-03"),
    ("shopping", [], "2026-04-01", "2026-04-03"),
    ("shopping", ["럭비티"] * 6, "2026-04-01", "2026-04-03"),
    ("shopping", ["럭비티", " 럭비티 "], "2026-04-01", "2026-04-03"),
    ("shopping", "럭비티", "2026-04-01", "2026-04-03"),
    ("shopping", [" "], "2026-04-01", "2026-04-03"),
    ("shopping", ["럭비티"], "2026-04-04", "2026-04-03"),
    ("shopping", ["럭비티"], "20260401", "2026-04-03"),
])
def test_invalid_requests_fail_before_network(environment, channel, words, start, end):
    session = FakeSession([])
    client = NaverClient(environment, session=session)
    with pytest.raises(NaverError):
        client.fetch(channel, words, start, end, environment / "archive")
    assert session.calls == []


def monthly_response_for(payload):
    response = response_for(payload)
    first, last = payload["startDate"], payload["endDate"][:7] + "-01"
    for series in response.payload["results"]:
        series["data"] = [{"period": first, "ratio": 20.125}]
        if last != first:
            series["data"].append({"period": last, "ratio": 100.0})
    return response


@pytest.mark.parametrize("start,end", [
    ("2024-02-01", "2024-02-29"),  # Leap-year February is a complete month.
    ("2025-02-01", "2025-02-28"),
    ("2025-04-01", "2025-04-30"),
    ("2025-12-01", "2026-01-31"),
])
def test_month_requests_accept_complete_calendar_ranges(environment, start, end):
    session = FakeSession([monthly_response_for])
    record = NaverClient(environment, session=session).fetch(
        "shopping", ["럭비티"], start, end, environment / "archive", time_unit="month",
    )
    assert record["payload"]["timeUnit"] == record["response"]["timeUnit"] == "month"
    assert record["payload"]["startDate"] == start and record["payload"]["endDate"] == end
    assert record["missing_dates"] == {"럭비티": []}
    assert len(session.calls) == 1


@pytest.mark.parametrize("start,end", [
    ("2024-02-01", "2024-02-28"),  # A leap year's last day cannot be omitted.
    ("2025-01-02", "2025-02-28"),
    ("2025-01-01", "2025-02-27"),
    ("2025-04-01", "2025-04-29"),
    ("2025-04-30", "2025-04-30"),
])
def test_month_requests_reject_partial_months_before_network(environment, start, end):
    session = FakeSession([])
    with pytest.raises(NaverError) as caught:
        NaverClient(environment, session=session).fetch(
            "shopping", ["럭비티"], start, end, environment / "archive", time_unit="month",
        )
    assert caught.value.code == "PARTIAL_MONTH_RANGE"
    assert session.calls == []
    assert not (environment / "archive").exists()


@pytest.mark.parametrize("time_unit", ["week", "MONTH", "", None, 1])
def test_unsupported_time_units_fail_before_network(environment, time_unit):
    session = FakeSession([])
    with pytest.raises(NaverError) as caught:
        NaverClient(environment, session=session).fetch(
            "shopping", ["럭비티"], "2025-04-01", "2025-04-30", environment / "archive", time_unit=time_unit,
        )
    assert caught.value.code == "INVALID_TIME_UNIT" and session.calls == []


@pytest.mark.parametrize("provider", ["developers", "cloud"])
@pytest.mark.parametrize("channel,ages", [("shopping", ["20"]), ("search", ["3", "4"])])
def test_monthly_raw_indices_missing_periods_and_demographics_are_preserved(environment, provider, channel, ages):
    session = FakeSession([monthly_response_for])
    client = NaverClient(environment, provider=provider, session=session)
    directory = environment / "archive"
    record = client.fetch(channel, ["럭비티", "맨투맨"], "2023-12-01", "2024-02-29", directory, time_unit="month")
    assert record["missing_dates"] == {"럭비티": ["2024-01-01"], "맨투맨": ["2024-01-01"]}
    assert record["response"] == monthly_response_for(record["payload"]).payload
    assert record["response"]["results"][0]["data"] == [
        {"period": "2023-12-01", "ratio": 20.125}, {"period": "2024-02-01", "ratio": 100.0},
    ]
    assert record["payload"]["gender"] == "m" and record["payload"]["ages"] == ages
    if channel == "shopping":
        assert record["payload"]["category"] == "50000169"
    else:
        assert "category" not in record["payload"]
    assert json.loads(session.calls[0]["data"])["timeUnit"] == "month"
    assert record["response_sha256"] == digest(record["response"])
    assert record["request_sha256"] == digest({"url": record["url"], "payload": record["payload"]})
    assert record["record_sha256"] == digest({key: value for key, value in record.items() if key != "record_sha256"})
    assert json.loads(next(directory.glob("*.json")).read_text(encoding="utf-8")) == record
    assert client.fetch(channel, ["럭비티", "맨투맨"], "2023-12-01", "2024-02-29", directory, time_unit="month") == record
    assert len(session.calls) == 1


@pytest.mark.parametrize("mutate,code", [
    (lambda r: r["results"][0]["data"].append({"period": "2025-04-01", "ratio": 30}), "INVALID_OBSERVATION_DATE"),
    (lambda r: r["results"][0]["data"][0].update(period="2025-04-02"), "INVALID_OBSERVATION_DATE"),
    (lambda r: r["results"][0]["data"][0].update(period="2025-04-30"), "INVALID_OBSERVATION_DATE"),
    (lambda r: r["results"][0]["data"][0].update(period="2025-03-01"), "INVALID_OBSERVATION_DATE"),
    (lambda r: r["results"][0]["data"][0].update(period="2025-04"), "INVALID_OBSERVATION_DATE"),
    (lambda r: r.update(timeUnit="date"), "RESPONSE_WINDOW_MISMATCH"),
    (lambda r: r["results"][0]["data"][0].update(ratio=100.001), "INVALID_OBSERVATION_RATIO"),
    (lambda r: r["results"][0]["data"][0].update(ratio=float("nan")), "INVALID_OBSERVATION_RATIO"),
])
def test_monthly_invalid_periods_or_indices_are_not_archived_as_success(environment, mutate, code):
    def invalid(payload):
        response = monthly_response_for(payload)
        mutate(response.payload)
        return response
    session = FakeSession([invalid])
    directory = environment / "archive"
    with pytest.raises(NaverError) as caught:
        NaverClient(environment, session=session).fetch(
            "shopping", ["럭비티"], "2025-04-01", "2025-04-30", directory, time_unit="month",
        )
    assert caught.value.code == code and len(session.calls) == 1
    assert not list(directory.glob("*.json"))
    assert len(list((directory / "errors").glob("*.json"))) == 1


def test_empty_monthly_series_retains_every_missing_month(environment):
    def empty(payload):
        response = monthly_response_for(payload)
        response.payload["results"][0]["data"] = []
        return response
    session = FakeSession([empty])
    record = NaverClient(environment, session=session).fetch(
        "shopping", ["럭비티"], "2023-12-01", "2024-02-29", environment / "archive", time_unit="month",
    )
    assert record["missing_dates"] == {"럭비티": ["2023-12-01", "2024-01-01", "2024-02-01"]}
    assert record["response"]["results"][0]["data"] == []


def test_daily_and_monthly_requests_have_separate_caches_and_legacy_default_is_unchanged(environment):
    session = FakeSession([response_for, monthly_response_for])
    client = NaverClient(environment, session=session)
    directory = environment / "archive"
    args = ("shopping", ["럭비티"], "2025-04-01", "2025-04-30", directory)
    daily = client.fetch(*args)
    monthly = client.fetch(*args, time_unit="month")
    assert client.fetch(*args, time_unit="date") == daily
    assert client.fetch(*args, time_unit="month") == monthly
    assert len(session.calls) == 2 and len(list(directory.glob("*.json"))) == 2
    assert daily["request_sha256"] != monthly["request_sha256"]
    assert daily["id"] != monthly["id"]
    assert len(daily["missing_dates"]["럭비티"]) == 28
    assert monthly["missing_dates"]["럭비티"] == []
    assert {key: value for key, value in daily["payload"].items() if key != "timeUnit"} == {
        key: value for key, value in monthly["payload"].items() if key != "timeUnit"}
