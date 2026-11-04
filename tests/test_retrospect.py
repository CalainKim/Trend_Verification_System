"""회고 자료 검증.

회고는 벤치마크와 같은 자료를 반대로 쓴다. 벤치마크는 확인 구간을 가리고
회고는 펼친다. 그래서 틀리면 블라인드가 깨지는 쪽으로 틀린다.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def _mod(name: str):
    spec = importlib.util.spec_from_file_location(
        name, ROOT / "scripts" / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class TestOnlyTheOpenBenchmark:
    """봉인한 벤치마크로 회고를 만들면 안 된다.

    화면에 정답이 그려지고, 그 화면을 저장소에 올리는 순간 검증 파트가
    보면 안 되는 것이 흘러 나간다. 오류가 나지 않아 발견이 어려우므로
    경로를 인자로 받지 않고 상수로 박았다. 그 상수가 바뀌지 않았는지 센다.
    """

    def test_points_at_the_open_benchmark(self):
        assert _mod("build_retrospect").OPEN_BENCH.name == "benchmark-index-long"

    def test_that_benchmark_really_is_open(self):
        """정답이 저장소에 있어야 공개다. 없으면 봉인한 것을 쓰는 셈이다."""
        import subprocess
        out = subprocess.run(
            ["git", "ls-files", "benchmark-index-long/labels.sealed.json"],
            cwd=ROOT, capture_output=True, text=True).stdout
        assert out.strip(), "공개 벤치마크인데 정답이 추적되지 않는다"

    def test_takes_no_benchmark_argument(self):
        """인자로 받으면 실수로 봉인한 것을 가리킬 수 있다."""
        mod = _mod("build_retrospect")
        with pytest.raises(SystemExit):
            mod.main(["--benchmark", "benchmark"])


class TestCurveKeepsGaps:
    """관측이 없는 주를 빼면 선이 이어져서 없는 추세가 보인다."""

    def test_missing_week_becomes_none(self):
        curve = _mod("build_retrospect").curve(
            {"2022-01-02": 10.0, "2022-01-16": 20.0},
            ["2022-01-02", "2022-01-09", "2022-01-16"])
        assert [p["v"] for p in curve] == [10.0, None, 20.0]

    def test_keeps_every_requested_day(self):
        curve = _mod("build_retrospect").curve({}, ["2022-01-02", "2022-01-09"])
        assert [p["d"] for p in curve] == ["2022-01-02", "2022-01-09"]


class TestDesignMockIsSafeToPaste:
    """디자인용 사본은 붙여넣을 수 있어야 하고 양극단을 담아야 한다."""

    @pytest.fixture
    def mock(self):
        f = ROOT / "docs" / "design" / "retrospect-mock.json"
        if not f.exists():
            pytest.skip("디자인 목업이 없다")
        return json.loads(f.read_text(encoding="utf-8"))

    def test_small_enough_to_paste(self, mock):
        size = (ROOT / "docs/design/retrospect-mock.json").stat().st_size
        assert size < 120_000, f"{size}바이트는 붙여넣기에 크다"

    def test_spans_easy_and_hard_moments(self, mock):
        rates = [m["persist_rate"] for m in mock["moments"]]
        assert max(rates) - min(rates) > 0.4, "양극단이 안 들어 있다"

    def test_says_how_many_rows_were_dropped(self, mock):
        for m in mock["moments"]:
            assert "_note_rows" in m, "줄인 사본이라는 사실이 적혀 있어야 한다"

    def test_every_row_carries_its_outcome(self, mock):
        """결과가 없으면 가리고 펼치는 화면을 만들 수 없다."""
        for m in mock["moments"]:
            for r in m["rows"]:
                assert r["outcome"] in ("persist", "fade")
                assert "after" in r and "before" in r


class TestViewRefusesBrokenData:
    def test_rejects_a_script_tag_in_the_data(self, tmp_path):
        """자료 안의 </script 는 화면을 통째로 죽인다."""
        f = tmp_path / "d.json"
        f.write_text(json.dumps(
            {"moments": [{"t_cut": "2022-01-01", "rows": [],
                          "_x": "</script>"}]}), encoding="utf-8")
        with pytest.raises(SystemExit):
            _mod("build_retrospect_view").main(
                ["--data", str(f), "-o", str(tmp_path / "o.html")])
