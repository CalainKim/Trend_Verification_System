"""모니터에 랜딩과 같은 무신사 색감을 입히는 단계(scripts/apply_monitor_theme.py) 검사."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("theme", ROOT / "scripts" / "apply_monitor_theme.py")
theme = importlib.util.module_from_spec(spec)
spec.loader.exec_module(theme)

SAMPLE = ('<html><head><style>:root{--color-primary:#f54e00}</style></head><body>'
          '<div style="background:#F3F1EC;color:#26251e;border:1px solid rgba(38,37,30,0.12)">x</div>'
          '<script>const UP = "#cf2d56"</script></body></html>')


def test_주황과_따뜻한_회색이_남지_않는다():
    out, _ = theme.apply(SAMPLE)
    for c in ("#f54e00", "#f3f1ec", "#26251e", "rgba(38,37,30,", "#cf2d56"):
        assert c not in out.lower(), c


def test_토큰을_다시_정의한다():
    out, stats = theme.apply(SAMPLE)
    assert theme.MARK in out and stats["css"] == 1
    assert "--color-primary:#111111" in out
    assert "--color-semantic-success:#245eff" in out


def test_두_번_돌려도_한_번만_들어간다():
    once, _ = theme.apply(SAMPLE)
    twice, stats = theme.apply(once)
    assert twice == once and stats["css"] == 0


def test_빌드_스크립트가_테마를_입힌다():
    sh = (ROOT / "scripts" / "build_web.sh").read_text(encoding="utf-8")
    assert "apply_monitor_theme.py" in sh
