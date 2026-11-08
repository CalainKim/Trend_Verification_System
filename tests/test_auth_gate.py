"""비밀번호 게이트(web/functions/_middleware.js 와 auth/) 검사.

본체는 node 로 돌리는 web/functions/auth.test.mjs 다. 저장소의 검사 진입점을
pytest 하나로 두려고 여기서 감싼다. node 가 없으면 건너뛴다.

막는 자리는 화면이 아니라 서버다. 화면에서 막으면 주소를 직접 치거나 소스를
보고 넘어갈 수 있고, /api 는 API 키로 돈이 드는 호출이라 특히 그렇다.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TEST_MJS = ROOT / "web" / "functions" / "auth.test.mjs"
SH = (ROOT / "scripts" / "build_web.sh").read_text(encoding="utf-8")


@pytest.mark.skipif(shutil.which("node") is None, reason="node 가 없다")
def test_비밀번호_게이트():
    r = subprocess.run(["node", str(TEST_MJS)], capture_output=True,
                       text=True, cwd=ROOT, timeout=60)
    assert r.returncode == 0, f"node 검사 실패\n{r.stdout}\n{r.stderr}"
    assert "실패 0" in r.stdout, r.stdout


def test_게이트_파일이_배포_폴더로_간다():
    """게이트를 빠뜨리고 올리면 /app 과 /api 가 열린 채 배포된다."""
    for f in ("_middleware.js", "_shared/session.js", "auth/login.js", "auth/logout.js"):
        assert f"web/functions/{f}" in SH, f"build_web.sh 가 {f} 를 복사하지 않는다"


def test_검사_파일은_배포_폴더로_가지_않는다():
    """functions/ 아래 파일은 경로가 될 수 있다. 검사 파일을 올리지 않는다."""
    assert "auth.test.mjs" not in SH


def test_입력_창이_배포_폴더로_간다():
    assert 'login.html' in SH, "build_web.sh 가 login.html 을 복사하지 않는다"


def test_비밀값_파일이_배포_폴더에_있으면_멈춘다():
    """wrangler pages dev 는 폴더 안의 .dev.vars 를 /.dev.vars 로 내준다.

    2026-11-08 에 실제로 확인했다. 그 폴더를 그대로 올리면 비밀번호와 키가
    공개된다. 빌드 스크립트가 이 검사를 들고 있어야 한다.
    """
    assert ".dev.vars" in SH and "exit 1" in SH.split(".dev.vars")[-1][:400]
