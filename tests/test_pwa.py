"""홈 화면 앱(PWA) 파일 검사."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
L = ROOT / "design" / "landing"
SH = (ROOT / "scripts" / "build_web.sh").read_text(encoding="utf-8")


def test_앱_정보_파일이_설치_조건을_갖춘다():
    m = json.loads((L / "manifest.webmanifest").read_text(encoding="utf-8"))
    assert m["display"] == "standalone" and m["start_url"].startswith("/")
    sizes = {i["sizes"] for i in m["icons"]}
    assert {"192x192", "512x512"} <= sizes
    assert any(i.get("purpose") == "maskable" for i in m["icons"])
    for i in m["icons"]:
        assert (L / i["src"].lstrip("/")).exists(), i["src"]


def test_서비스_워커는_로그인과_중계를_가로채지_않는다():
    sw = (L / "sw.js").read_text(encoding="utf-8")
    assert "'/api/'" in sw and "'/auth/'" in sw
    assert "redirected" in sw, "리디렉션을 담으면 로그인한 뒤에도 입력 창이 뜬다"
    assert "/auth/logout" in sw, "로그아웃할 때 담아 둔 모니터를 지워야 한다"


def test_세_화면_모두_앱_정보를_연결한다():
    for f in ("index.html", "login.html"):
        assert 'rel="manifest"' in (L / f).read_text(encoding="utf-8"), f


def test_빌드가_PWA_파일을_맨_위에_둔다():
    assert '"$LANDING/sw.js"' in SH and "manifest.webmanifest" in SH and "offline.html" in SH
    assert "assets/pwa" in SH
    assert "/sw.js" in SH and "no-cache" in SH
