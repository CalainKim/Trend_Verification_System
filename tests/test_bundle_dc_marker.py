"""한 파일로 묶은 모니터에서 런타임이 자기 코드를 화면으로 읽지 않게 한다.

런타임(support.js)은 페이지 원문에서 처음 나오는 <x-dc> 를 화면의 시작으로
읽는다. 런타임을 페이지에 심으면 그 코드 속 오류 문구의 <x-dc> 가 진짜 표시
보다 앞에 놓여, 화면에 런타임 코드가 글자로 찍혔다 (2026-11-08 확인).
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("bundle_design", ROOT / "scripts" / "bundle_design.py")
bd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bd)


def test_심는_스크립트에서_표시_글자를_숨긴다():
    js = 'const m = /<x-dc(?:\\s[^>]*)?>/.exec(src); src.lastIndexOf("</x-dc>"); "has no <x-dc> block"'
    out = bd.hide_dc_markers(js)
    assert "<x-dc" not in out and "</x-dc" not in out
    # \x3c 는 자바스크립트 안에서 < 와 같다. 바뀐 자리만 그 글자다
    assert out.count("\\x3cx-dc") == 2 and out.count("\\x3c/x-dc") == 1


def test_script_태그로_감쌀_때도_숨긴다():
    out = bd._script('console.error("has no <x-dc> block")')
    assert "<x-dc" not in out


def test_런타임_원본에는_표시_글자가_있다():
    """원본에 이 글자가 없어졌다면 위의 처리가 왜 필요한지 다시 확인한다."""
    src = (ROOT / "design" / "runtime" / "support.js").read_text(encoding="utf-8")
    assert re.search(r"<x-dc", src)


def test_묶은_결과에는_진짜_표시가_하나뿐이다():
    built = ROOT / "build" / "web" / "app" / "index.html"
    if not built.exists():
        import pytest
        pytest.skip("build/web 이 없다. ./scripts/build_web.sh 를 먼저 돌린다")
    html = built.read_text(encoding="utf-8")
    assert len(re.findall(r"<x-dc[\s>]", html)) == 1
