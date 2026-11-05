"""중계 함수(web/functions/api/complete.js)의 방어 논리 검사.

본체는 node 로 돌리는 web/functions/api/complete.test.mjs 다. 여기서 감싸는
이유는 저장소의 검사 진입점을 pytest 하나로 유지하기 위해서다. node 가 없는
환경에서는 건너뛴다.

중계가 막아야 하는 것은 호출 횟수가 아니라 호출 내용이다. 비밀번호로 사람을
걸러도 들어온 사람이 화면을 고쳐 비싼 모델이나 큰 max_tokens 를 보낼 수 있다.
그 경로를 막는지 확인한다.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TEST_MJS = ROOT / "web" / "functions" / "api" / "complete.test.mjs"


@pytest.mark.skipif(shutil.which("node") is None, reason="node 가 없다")
def test_중계_함수_방어_논리():
    assert TEST_MJS.exists(), f"{TEST_MJS} 가 없다"
    r = subprocess.run(["node", str(TEST_MJS)], capture_output=True,
                       text=True, cwd=ROOT, timeout=60)
    assert r.returncode == 0, f"node 검사 실패\n{r.stdout}\n{r.stderr}"
    assert "실패 0" in r.stdout, r.stdout


def test_배포_폴더에_키가_들어가지_않는다():
    """빌드 스크립트가 키 검사를 반드시 들고 있어야 한다.

    이 검사를 지우면 키가 섞인 폴더를 올려도 아무도 막지 않는다. 배포는
    되돌릴 수 없으므로 스크립트에서 이 단계가 사라지는 것을 테스트로 잡는다.
    """
    sh = (ROOT / "scripts" / "build_web.sh").read_text(encoding="utf-8")
    assert "sk-ant-" in sh, "build_web.sh 에서 키 검사가 사라졌다"
    assert "exit 1" in sh, "키를 찾아도 멈추지 않는다"
    # 뒤에 20자 이상을 요구해야 한다. sk-ant- 만 찾으면 shim 의 안내 문구
    # ("sk-ant- 로 시작합니다") 에도 걸려서 멀쩡한 빌드가 멈춘다.
    assert "{20,}" in sh, "키 검사가 안내 문구에도 걸리는 느슨한 패턴이다"


def test_키_검사_패턴이_실제_키만_잡는다(tmp_path):
    """잡아야 할 것과 잡으면 안 되는 것을 둘 다 확인한다."""
    import re

    sh = (ROOT / "scripts" / "build_web.sh").read_text(encoding="utf-8")
    m = re.search(r"KEYPAT='([^']+)'", sh)
    assert m, "build_web.sh 에서 키 패턴을 찾지 못했다"
    pat = re.compile(m.group(1))
    assert pat.search("sk-ant-api03-" + "A" * 24), "실제 키 모양을 놓친다"
    assert not pat.search("sk-ant- 로 시작합니다"), "안내 문구를 헛잡는다"


def test_중계판에는_키를_심을_수_없다():
    """--relay 와 --embed-key 를 같이 주면 멈춰야 한다."""
    src = (ROOT / "scripts" / "bundle_design.py").read_text(encoding="utf-8")
    assert "args.relay and args.embed_key" in src
