"""랜딩을 / 에, 모니터를 /app/ 에 두는 배포 구성을 지킨다."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SH = (ROOT / "scripts" / "build_web.sh").read_text(encoding="utf-8")
LANDING = ROOT / "design" / "landing" / "index.html"


def test_모니터는_app_아래로_묶는다():
    assert '-o "$OUT/app/index.html"' in SH, "모니터가 /app/ 이 아닌 곳으로 나간다"


def test_랜딩이_첫_화면이다():
    assert 'cp "$LANDING/index.html" "$OUT/index.html"' in SH, "랜딩이 / 에 들어가지 않는다"


def test_랜딩_버튼은_모니터로_간다():
    html = LANDING.read_text(encoding="utf-8")
    assert 'href="app/"' in html, "트렌드 모니터 열기 버튼이 /app/ 으로 가지 않는다"


def test_랜딩에_가운데점이_없다():
    html = LANDING.read_text(encoding="utf-8")
    assert chr(0xB7) not in html, "랜딩에 가운데점이 남아 있다"


def test_중계_주소는_절대경로다():
    """모니터를 /app/ 으로 옮겨도 중계에 닿으려면 상대경로이면 안 된다."""
    src = (ROOT / "scripts" / "bundle_design.py").read_text(encoding="utf-8")
    assert 'RELAY_ENDPOINT = "/api/complete"' in src
