"""화면 연동 데이터가 Trend Monitor 의 계약을 지키는지 본다."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from export_frontend import (  # noqa: E402
    build_ledger, build_p, build_type_skip, pick_weeks, self_attribute, type_of,
)


def _item(name, rank, sale_percent=0, image_url=None):
    return {"name": name, "rank": rank, "brand": "b", "price": 1000,
            "gender": "남", "is_new": False, "sale_percent": sale_percent,
            "image_url": image_url}


class TestTypeOf:
    """유형 분류는 순서가 의미를 가진다. 화면의 TYPE_RULES 와 같아야 한다."""

    def test_first_rule_wins(self):
        # 후드이면서 니트인 상품은 후드로 간다. 규칙 순서가 후드가 먼저다.
        assert type_of("MELLOW KNITTED HOOD_2COLOR") == "후드"
        assert type_of("RELAX HOODED KNIT [ BROWN ]") == "후드"

    def test_english_and_korean(self):
        assert type_of("Vintage Long Sleeve Henley Shirt Navy") == "롱슬리브"
        assert type_of("[스페셜오더] SWEAT SHIRT (5 COLOR)") == "맨투맨"
        assert type_of("Heavyweight Waffle Cotton Underwear Black") == "이너웨어"

    def test_unmatched_is_etc(self):
        assert type_of("알 수 없는 상품") == "기타"


class TestTypeSkip:
    def test_self_referential_attributes(self):
        # 사전 74종 가운데 이름이 곧 유형인 7개만 걸려야 한다.
        for canon in ("긴팔", "니트", "티셔츠", "후드티", "맨투맨", "블라우스", "탑"):
            assert self_attribute(canon), canon
        for canon in ("셔츠", "반팔", "와플", "크루넥", "울", "빈티지", "가디건"):
            assert not self_attribute(canon), canon

    def test_built_from_dictionary(self):
        import extract_attributes as ea

        attrs, _stop, _colors = ea.load_dictionary()
        skip = build_type_skip(attrs)
        # 화면 원본이 막던 셋은 반드시 들어 있어야 한다.
        assert skip["후드"] == ["후드티"]
        assert skip["니트"] == ["니트"]
        assert skip["탑"] == ["탑"]
        # 원본이 놓쳤던 넷도 채워져야 한다.
        assert skip["티셔츠"] == ["티셔츠"]
        assert skip["맨투맨"] == ["맨투맨"]
        assert skip["블라우스"] == ["블라우스"]
        assert skip["롱슬리브"] == ["긴팔"]


class TestLedger:
    """남음 판정은 (기준 - 확인) / (기준 - 감지) >= 0.5 다.

    아래 셋은 화면에 들어 있던 값에서 역산해 확인한 사례다. 판정식을 고치면
    여기서 먼저 깨진다.
    """

    @pytest.mark.parametrize("base, detect, hold, kept", [
        (41, 19, 30, True),    # 상승 22계단, 유지분 11, 11/22 = 0.50 으로 경계값
        (46, 18, 9, True),     # 확인 시점에 더 올랐다
        (27, 15, 32, False),   # 기준보다도 내려갔다
        (90, 65, 84, False),   # TOP100 안이지만 상승분을 거의 잃었다
    ])
    def test_keep_ratio(self, base, detect, hold, kept):
        got = build_ledger({"x": _item("상품", base)},
                           {"x": _item("상품", detect)},
                           {"x": _item("상품", hold)})
        assert got == [["상품", base, detect, hold, kept]]

    def test_dropped_out_of_top100(self):
        # 확인 시점에 목록 밖으로 나가면 순위를 null 로 두고 이탈로 본다.
        got = build_ledger({"x": _item("상품", 60)}, {"x": _item("상품", 6)}, {})
        assert got == [["상품", 60, 6, None, False]]

    def test_small_rise_is_not_a_case(self):
        # 10계단 미만은 감지 대상이 아니다.
        got = build_ledger({"x": _item("상품", 20)},
                           {"x": _item("상품", 12)},
                           {"x": _item("상품", 11)})
        assert got == []

    def test_absent_at_base_is_not_a_case(self):
        # 기준 시점에 없던 상품은 상승폭을 잴 수 없다.
        got = build_ledger({}, {"x": _item("상품", 5)}, {"x": _item("상품", 5)})
        assert got == []


class TestDiscount:
    """할인율은 화면의 필터 3단계(할인 효과)가 쓴다.

    기존 여섯 자리 뒤에 붙여야 한다. 중간에 끼우면 화면이 판매가 자리에서
    할인율을 읽는다.
    """

    def test_appended_as_seventh_field(self):
        import extract_attributes as ea

        attrs, _stop, colors = ea.load_dictionary()
        rows = build_p({"x": _item("와플 티셔츠", 3, sale_percent=24)}, {}, attrs, colors)
        row = rows["와플"][0]
        assert len(row) == 9
        assert row[:6] == [3, None, "b", "와플 티셔츠", 1000, "남"]
        assert row[6] == 24
        assert row[7] is None   # 지난주 TOP100 에 없었으면 비교할 값이 없다

    def test_previous_week_discount_for_comparison(self):
        # 할인 때문에 올랐는지는 지난주와 견줘야 안다. 상시 할인 상품과
        # 이번에 할인을 건 상품을 가르는 값이다.
        import extract_attributes as ea

        attrs, _stop, colors = ea.load_dictionary()
        rows = build_p({"x": _item("와플 티셔츠", 3, sale_percent=40)},
                       {"x": _item("와플 티셔츠", 50, sale_percent=10)},
                       attrs, colors)
        row = rows["와플"][0]
        assert row[6] == 40 and row[7] == 10   # 30%p 더 할인하며 47계단 올랐다

    def test_image_url_gets_a_size_hint(self):
        """사진은 원본이 283KB 다. CDN 이 줄여 주므로 크기를 지정해 받는다."""
        import extract_attributes as ea

        attrs, _stop, colors = ea.load_dictionary()
        rows = build_p(
            {"x": _item("와플 티셔츠", 3, image_url="https://img.29cm.co.kr/item/a.jpg")},
            {}, attrs, colors)
        assert rows["와플"][0][8] == "https://img.29cm.co.kr/item/a.jpg?width=240&format=webp"

    def test_missing_image_stays_none(self):
        # 랭킹에서 빠진 지 오래된 상품은 사진을 못 받는다. 화면에 자리표시자가 있다.
        import extract_attributes as ea

        attrs, _stop, colors = ea.load_dictionary()
        rows = build_p({"x": _item("와플 티셔츠", 3)}, {}, attrs, colors)
        assert rows["와플"][0][8] is None

    def test_zero_discount_is_kept_not_dropped(self):
        # 0 과 None 은 다르다. 0 은 정가 판매를 확인한 것이고 None 은 모른다는 뜻이다.
        import extract_attributes as ea

        attrs, _stop, colors = ea.load_dictionary()
        rows = build_p({"x": _item("와플 티셔츠", 3, sale_percent=0)}, {}, attrs, colors)
        assert rows["와플"][0][6] == 0


class TestPickWeeks:
    def test_nearest_day_when_gap_is_missing(self):
        # 29CM 수집이 하루 빠진 주가 있다. 정확히 7일 전이 없으면 가장 가까운
        # 수집일로 당긴다.
        days = ["2026-10-17", "2026-10-25", "2026-11-01"]
        assert pick_weeks(days, "2026-11-01") == ["2026-10-17", "2026-10-25", "2026-11-01"]

    def test_rejects_day_without_collection(self):
        with pytest.raises(SystemExit):
            pick_weeks(["2026-11-01"], "2026-10-31")

    def test_rejects_when_history_is_too_short(self):
        with pytest.raises(SystemExit):
            pick_weeks(["2026-11-01"], "2026-11-01")


class TestDuplicateDeclarations:
    """화면이 자리표시자로 먼저 선언해 둔 상수를 패치가 지우는지 본다.

    둘 다 남으면 const 중복 선언으로 스크립트가 통째로 죽고 화면이 백지가 된다.
    TYPE_SKIP 에서 한 번, TRACK 에서 또 한 번 났다. 이름을 손으로 관리하면
    다음에 또 난다.

    선언이 여러 줄일 수 있다. TRACK 은 59줄이었다. 한 줄만 지우면 나머지가
    고아로 남아 문법이 깨진다.
    """

    def _patch(self, tmp_path, screen: str, data: str) -> str:
        import patch_design as pd

        src = tmp_path / "screen.html"
        src.write_text(screen, encoding="utf-8")
        old_data = pd.DATA
        pd.DATA = tmp_path / "data.js"
        pd.DATA.write_text(data, encoding="utf-8")
        try:
            return pd.swap_data(src.read_text(encoding="utf-8"))
        finally:
            pd.DATA = old_data

    def test_removes_single_line_declaration(self, tmp_path):
        screen = "const TYPE_SKIP = { 후드: ['후드티'] };\nconst UP = '#cf2d56';\n"
        out = self._patch(tmp_path, screen, 'const TYPE_SKIP = {"후드": ["후드티"]};\n')
        assert out.count("const TYPE_SKIP = ") == 1

    def test_removes_multi_line_declaration(self, tmp_path):
        screen = (
            "const TRACK = {\n"
            "  '후드': { tops: [1, 2] },\n"
            "  '니트': { tops: [3, 4] }\n"
            "};\n"
            "const UP = '#cf2d56';\n"
        )
        out = self._patch(tmp_path, screen, 'const TRACK = {"후드": {}};\n')
        assert out.count("const TRACK = ") == 1
        # 고아 줄이 남으면 안 된다
        assert "'니트'" not in out
        assert out.count("};") == 0 or "tops: [3, 4]" not in out

    def test_keeps_unrelated_declarations(self, tmp_path):
        screen = ("const KEEP = { a: 1 };\nconst TRACK = {\n x: 1\n};\n"
                  "const UP = '#cf2d56';\n")
        out = self._patch(tmp_path, screen, 'const TRACK = {};\n')
        assert "const KEEP = { a: 1 };" in out

    def test_refuses_when_boundary_missing(self, tmp_path):
        import pytest as _pt

        screen = "const TRACK = { x: 1 };\n"   # const UP 이 없다
        with _pt.raises(SystemExit):
            self._patch(tmp_path, screen, 'const TRACK = {};\n')


class TestBrowserShim:
    """파일 하나로 떼어낸 화면이 API 를 직접 부르는 shim.

    키는 파일에 넣지 않는다. 이 파일은 남에게 보내는 것이라 키가 들어가면 받은
    사람 누구나 꺼내 쓸 수 있고 과금은 만든 사람에게 간다.

    생성 코드에 개행을 넣을 때 조심해야 한다. 파이썬 삼중따옴표 안의 이스케이프가
    실제 개행으로 바뀌면 JS 작은따옴표 문자열이 끊겨 SyntaxError 가 난다.
    실제로 한 번 그렇게 깨졌다.
    """

    def _shim(self) -> str:
        import bundle_design as bd

        return bd.BROWSER_SHIM

    def test_no_api_key_in_shim(self):
        import re

        assert not re.search(r"sk-ant-[A-Za-z0-9_-]{20,}", self._shim())

    def test_uses_browser_access_header(self):
        # 이 헤더가 없으면 브라우저에서 CORS 로 막힌다.
        assert "anthropic-dangerous-direct-browser-access" in self._shim()

    def test_no_raw_newline_inside_js_string(self):
        """JS 문자열 리터럴 안에 생 개행이 들어가면 문법이 깨진다.

        따옴표를 세는 방식은 URL 의 // 를 주석으로 오인해서 쓸 수 없다. 여는
        따옴표 뒤에 줄 끝까지 닫는 따옴표가 없는 줄을 직접 찾는다.
        """
        import re

        for line in self._shim().split("\n"):
            # 한 줄 안에서 짝이 맞는 문자열을 먼저 지운다. 남은 따옴표가 있으면
            # 그 문자열이 줄을 넘는다는 뜻이다.
            rest = re.sub(r"'(?:[^'\\]|\\.)*'", "", line)
            rest = re.sub(r'"(?:[^"\\]|\\.)*"', "", rest)
            assert "'" not in rest and '"' not in rest, (
                f"문자열이 줄을 넘는다: {line.strip()[:70]}")

    def test_clears_key_on_rejection(self):
        # 401 이면 저장된 키를 지워야 한다. 안 지우면 틀린 키로 계속 두드린다.
        shim = self._shim()
        assert "401" in shim and "removeItem" in shim

    def test_filters_empty_thinking_blocks(self):
        # Opus 5.5 는 생각 블록을 돌려주는데 본문이 비어 있다. 거르지 않으면
        # 빈 문자열이 앞에 붙는다.
        assert "b.type === 'text'" in self._shim()

    def test_yields_to_claude_design_runtime(self):
        # Claude Design 안에서는 런타임이 넣어 준 것을 써야 한다.
        assert "if (window.claude && window.claude.complete) return;" in self._shim()


class TestStandaloneRuntime:
    def test_refetched_bundle_starts_at_the_real_component(self):
        import re
        import bundle_design as bd

        # The runtime refetches its HTML and finds x-dc with a raw-text regex.
        # Its own error message contains that marker before the real template.
        source = ('<html><head><script src="./support.js"></script></head>'
                  '<body><x-dc><main id="actual-component">본문</main></x-dc>'
                  '</body></html>')
        out, _ = bd.bundle(source, ROOT / "design" / "runtime")
        opening = re.search(r"<x-dc(?:\s[^>]*)?>", out)
        assert opening is not None
        template = out[opening.end():out.rindex("</x-dc>")]
        assert template == '<main id="actual-component">본문</main>'
        assert r"has no \x3cx-dc> block" in out

    def test_screen_dates_follow_exported_snapshot_week(self, tmp_path, monkeypatch):
        import patch_design as pd

        data = tmp_path / "data.js"
        data.write_text(
            'const WEEK = {base: "12/01", detect: "12/08", hold: "12/15", '
            'baseISO: "2026-12-01", holdISO: "2026-12-15", nextISO: "2026-12-22"};\n',
            encoding="utf-8",
        )
        monkeypatch.setattr(pd, "DATA", data)
        out = tmp_path / "patched.html"
        assert pd.main([str(ROOT / "design" / "Trend Monitor v8.dc.html"),
                        "-o", str(out)]) == 0
        html = out.read_text(encoding="utf-8")
        assert 'detect: "12/08", hold: "12/15"' in html
        assert "29CM 상의 TOP100, {{ snapshotRange }}" in html
        assert "snapshotRange: `${WEEK.detect}에서 ${WEEK.hold}`" in html
        assert "snapshotDate: WEEK.holdISO" in html
        assert "29CM {{ snapshotDate }} 기준" in html
        assert "다음 수집 일정 미연결" in html
        assert "time: WEEK.holdISO + ' 관측 기준'" in html
        for stale in ("10/25에서 11/01", "11/01 22:00", "11/08 22:00",
                      "11/01 22:05", "오늘: '2026-11-03'"):
            assert stale not in html


class TestImageDedup:
    """같은 사진이 여러 자리에 나오면 한 번만 담아야 한다.

    상품 하나가 여러 속성에 걸려 P 에 중복으로 들어간다. 자리마다 base64 를
    복사하면 196장이 428장 분량이 되어 파일이 2.5MB 대신 1.1MB 로 줄 것을
    못 줄인다.
    """

    def test_no_remote_images_preserves_return_shape(self):
        import bundle_design as bd

        html = "<html><body>상품 사진 없음</body></html>"
        assert bd.inline_remote_images(html) == (html, 0)

    def test_skip_images_builds_without_network(self, tmp_path, monkeypatch):
        import bundle_design as bd
        import requests

        def blocked(*args, **kwargs):
            raise AssertionError("The offline bundle must not download photos")

        monkeypatch.setattr(requests.Session, "get", blocked)
        url = "https://img.29cm.co.kr/example.webp"
        source, output = tmp_path / "source.html", tmp_path / "output.html"
        source.write_text(
            '<html><head></head><body><script>async function go() {'
            'const text = await window.claude.complete({});}</script>'
            + f'<img src="{url}"><p>{bd.GENERIC_ERRORS[0]}</p></body></html>',
            encoding="utf-8",
        )
        assert bd.main([str(source), "--assets", str(tmp_path),
                        "-o", str(output), "--skip-images"]) == 0
        assert f'<img src="{url}">' in output.read_text(encoding="utf-8")

    def test_shared_photos_are_counted_once(self):
        import json

        data = json.loads(
            (ROOT / "build" / "frontend_data.json").read_text(encoding="utf-8")
        ) if (ROOT / "build" / "frontend_data.json").exists() else None
        if data is None:
            import pytest as _pt

            _pt.skip("내보내기 결과가 없다")
        urls = [r[8] for rows in data["P"].values() for r in rows if r[8]]
        # 중복이 실제로 있다는 것부터 확인한다. 없으면 이 테스트가 무의미하다.
        assert len(urls) > len(set(urls)), "중복이 없어 무엇을 막는지 알 수 없다"

    def test_lookup_script_replaces_placeholders(self):
        import bundle_design as bd

        # 자리표시자를 실제 사진으로 바꾸는 코드가 들어 있어야 한다.
        src = bd.__file__
        body = Path(src).read_text(encoding="utf-8")
        assert "window.__IMG" in body
        assert "img:" in body
        # 새로 그려지는 상품에도 적용돼야 하므로 관찰자가 필요하다.
        assert "MutationObserver" in body


class TestLocalCopyGuard:
    """키를 넣은 사본과 보낼 사본이 섞이면 키가 샌다.

    둘 다 4.5MB 짜리 html 이라 열어 보지 않으면 구분이 안 된다. 그래서 이름으로
    가른다. --embed-key 는 이름에 로컬 이 들어가야만 통한다.
    """

    def _main(self, argv):
        import bundle_design as bd

        return bd.main(argv)

    def test_refuses_name_without_local(self, tmp_path, monkeypatch):
        import pytest as _pt

        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-" + "x" * 30)
        src = tmp_path / "in.html"
        src.write_text("<html><head></head><body></body></html>", encoding="utf-8")
        with _pt.raises(SystemExit) as e:
            self._main([str(src), "--assets", str(tmp_path),
                        "-o", str(tmp_path / "보낼것.html"), "--embed-key"])
        assert "로컬" in str(e.value)

    def test_refuses_without_key(self, tmp_path, monkeypatch):
        import pytest as _pt

        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        src = tmp_path / "in.html"
        src.write_text("<html><head></head><body></body></html>", encoding="utf-8")
        with _pt.raises(SystemExit) as e:
            self._main([str(src), "--assets", str(tmp_path),
                        "-o", str(tmp_path / "로컬.html"), "--embed-key"])
        assert "ANTHROPIC_API_KEY" in str(e.value)

    def test_refuses_malformed_key(self, tmp_path, monkeypatch):
        import pytest as _pt

        monkeypatch.setenv("ANTHROPIC_API_KEY", "not-a-key")
        src = tmp_path / "in.html"
        src.write_text("<html><head></head><body></body></html>", encoding="utf-8")
        with _pt.raises(SystemExit):
            self._main([str(src), "--assets", str(tmp_path),
                        "-o", str(tmp_path / "로컬.html"), "--embed-key"])


class TestInferenceSettings:
    """화면이 부르는 모델과 한도가 채점에 쓴 것과 같아야 한다.

    두 가지로 깨졌다. 화면에 박혀 있던 claude-sonnet-4-5 는 API 에서 사라져
    404 가 났고, 그 다음에는 한도가 모자라 잘렸다. Opus 5.5 는 effort 를 주지
    않으면 알아서 길게 생각하는데 그 생각 분량이 max_tokens 에서 깎인다.
    "유행 찾기" 는 생각에만 3,347 토큰을 쓰다 한도 3,000 에 걸려 본문이 한
    글자도 안 나왔고, 화면은 그걸 JSON 오류로 받아 "다시 실행해 주세요" 만
    적었다. 몇 번을 눌러도 같은 자리에서 멈춘다.
    """

    SCREEN = (
        "const a = await window.claude.complete({ model: 'claude-sonnet-4-5', "
        "max_tokens: 2500, system: S, messages: m });\n"
        "} catch (e) { upd(() => ({ phase: 'error' })); return; }\n"
        "const b = await window.claude.complete({ model: 'claude-sonnet-4-5', "
        "max_tokens: 3000, system: S, messages: m });\n"
        "} catch (e) { upd(() => ({ phase: 'error' })); return; }\n"
        "} catch (e) { upd(() => ({ phase: 'error' })); return; }\n"
        "} catch (e) { upd(() => ({ phase: 'error' })); return; }\n")

    def _fix(self, screen: str):
        import patch_design as pd

        return pd.fix_model(screen)

    def test_replaces_stale_model(self):
        import patch_design as pd

        out, n = self._fix(self.SCREEN)
        assert n == 2
        assert pd.STALE_MODEL not in out
        assert out.count(f"model: '{pd.MODEL}'") == 2

    def test_pins_budget_and_effort(self):
        """한도와 effort 를 둘 다 주어야 한다.

        한도만 올리면 생각이 길어진 날 또 잘리고, effort 만 주면 원래 한도가
        2,500 이라 긴 답에서 잘린다.
        """
        import patch_design as pd

        out, _ = self._fix(self.SCREEN)
        assert out.count(f"max_tokens: {pd.MAX_TOKENS}") == 2
        assert out.count(f"output_config: {{ effort: '{pd.EFFORT}' }}") == 2
        assert "max_tokens: 2500" not in out and "max_tokens: 3000" not in out

    def test_matches_the_scored_settings(self):
        """채점에 쓴 설정과 같아야 한다.

        화면은 검증 기록에 성적을 걸어 둔다. 버튼이 다른 설정으로 부르면
        한 모델의 성적을 걸고 다른 모델을 돌리는 꼴이 된다.
        """
        import re
        from pathlib import Path

        import patch_design as pd

        review = Path(pd.ROOT / "src" / "trend_poc" / "review.py").read_text(
            encoding="utf-8")
        assert f'"max_tokens": {pd.MAX_TOKENS}' in review
        assert f'"effort": "{pd.EFFORT}"' in review
        client = Path(pd.ROOT / "src" / "trend_poc" / "client.py").read_text(
            encoding="utf-8")
        assert re.search(rf'^MODEL = "{re.escape(pd.MODEL)}"$', client, re.M)

    def test_refuses_when_model_name_moved(self):
        import pytest as _pt

        with _pt.raises(SystemExit):
            self._fix("const a = await window.claude.complete({ model: 'other' });")

    def test_refuses_when_catch_count_changed(self):
        """실패를 받는 자리가 넷이 아니면 화면이 바뀐 것이다."""
        import pytest as _pt

        trimmed = "\n".join(self.SCREEN.split("\n")[:4])
        with _pt.raises(SystemExit):
            self._fix(trimmed)

    def test_leaves_a_trace_in_the_console(self):
        out, _ = self._fix(self.SCREEN)
        assert out.count("console.error('추론 실패', e)") == 4


class TestShimSurfacesFailures:
    """shim 이 조용히 실패하면 화면은 "다시 실행해 주세요" 만 적는다.

    부르는 쪽은 전부 catch 로 묶여 있어서, 여기서 이유를 담아 던지지 않으면
    브라우저 콘솔에도 아무것도 안 남는다.
    """

    def _shim(self) -> str:
        import bundle_design as bd

        return bd.BROWSER_SHIM

    def test_sends_effort(self):
        # 안 보내면 모델이 알아서 길게 생각하고 그 분량이 한도에서 깎인다.
        assert "output_config" in self._shim()

    def test_reports_truncation(self):
        # 잘린 본문을 그대로 넘기면 부르는 쪽에서 JSON 오류로 보여 못 찾는다.
        assert "max_tokens" in self._shim() and "잘렸습니다" in self._shim()

    def test_reports_missing_model(self):
        assert "모델을 찾지 못했습니다" in self._shim()


class TestReviewPanelSettings:
    """판정 패널도 채점에 쓴 설정과 같아야 한다.

    패널은 61건을 돌려 verdicts.json 을 만든다. 한도가 모자라면 전부 잘려서
    판정이 하나도 안 쌓이고, 버튼은 0/61 에 머문다.
    """

    def test_same_budget_and_effort_as_the_benchmark(self):
        import bundle_design as bd
        import patch_design as pd

        panel = bd.REVIEW_PANEL
        assert f"max_tokens: {pd.MAX_TOKENS}" in panel
        assert f"output_config: {{ effort: '{pd.EFFORT}' }}" in panel
        assert f"model: '{pd.MODEL}'" in panel
