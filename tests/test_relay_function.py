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


def test_배포_폴더에_검사_파일이_안_들어간다():
    """functions/ 아래 파일은 전부 라우트가 된다.

    폴더를 통째로 복사하면 complete.test.mjs 가 /api/complete.test 로 공개된다.
    빌드 스크립트가 .js 만 집어 가는지 확인한다.
    """
    sh = (ROOT / "scripts" / "build_web.sh").read_text(encoding="utf-8")
    assert "cp -R web/functions" not in sh, "functions 를 통째로 복사하면 검사 파일까지 올라간다"
    assert "complete.js" in sh, "중계 함수를 집어 가지 않는다"


def test_배포는_폴더_안에서_돌리게_되어_있다():
    """wrangler 는 functions/ 를 실행 위치 기준으로 찾는다.

    바깥에서 돌리면 "No Functions. Shimming..." 을 내고 중계 없이 올라가며,
    화면은 뜨는데 심층 검증 버튼만 조용히 죽는다. 안내 문구가 사라지면
    다음 사람이 같은 함정에 빠진다.
    """
    sh = (ROOT / "scripts" / "build_web.sh").read_text(encoding="utf-8")
    assert "cd $OUT" in sh or "cd build/web" in sh, "폴더 안에서 돌리라는 안내가 없다"


def test_저장소_루트에_wrangler_설정을_두지_않는다():
    """루트 설정은 docs/ 를 올리는 사고로 이어졌다.

    wrangler pages project create 가 자동 생성한 설정이 assets.directory 를
    docs 로 잡았고, docs/ 에는 저장소에서 제외한 로컬 파일이 있다.
    """
    for name in ("wrangler.jsonc", "wrangler.json", "wrangler.toml"):
        assert not (ROOT / name).exists(), (
            f"{name} 이 루트에 있다. 무엇을 올리는지 확인하고 build/web 안으로 옮겨라")


def test_중계는_평소에_닫혀_있다():
    """심층 검증은 시연 때만 연다. 스위치 검사가 키 검사보다 먼저여야 한다.

    닫혀 있을 때 Anthropic 에 요청이 나가면 막은 의미가 없다.
    """
    src = (ROOT / "web" / "functions" / "api" / "complete.js").read_text(encoding="utf-8")
    assert "RELAY_OPEN_UNTIL" in src
    assert src.index("relayOpen(env)") < src.index("if (!env.ANTHROPIC_API_KEY)")


def test_여닫는_스크립트가_있다():
    sh = (ROOT / "scripts" / "relay.sh").read_text(encoding="utf-8")
    assert "RELAY_OPEN_UNTIL" in sh and "open" in sh and "close" in sh
    assert "12시간" in sh, "오래 열어 두는 것을 막는 상한이 빠졌다"
