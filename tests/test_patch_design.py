"""시안에 글자로 박힌 기준 비율을 지금 값으로 바꾸는 자리를 지킨다.

이 숫자는 교수님과 무신사 앞에 뜨고 모델에게도 그대로 넘어간다. 조용히
틀리면 아무도 모른다. 특히 "기준보다 낮습니다" 같은 단정은 숫자만 갈아
끼우면 거짓말이 되므로 비교까지 다시 해야 한다.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import patch_design  # noqa: E402


#: 시안에서 기준 비율을 적어 둔 다섯 자리를 그대로 옮긴 것이다. 시안이
#: 바뀌면 이 토막도 같이 바꿔야 하고, 그때 patch_design 도 같이 봐야 한다.
SRC = (
    "기준 비율(전부 유지한다고 했을 때 54.1%, 최근 40.0%)과 비교해 판단한다.\n"
    "기준비율: '29CM에서 10계단 이상 오른 상품이 7일 뒤 상승분 절반 이상 "
    "유지한 비율 54.1% (최근 확인분 25건 중 10건, 40.0%)',\n"
    "기준비율: '29CM에서 10계단 이상 오른 상품이 7일 뒤 상승분 절반 이상 "
    "유지한 비율 54.1%',\n"
    "'최근 확인분 유지 비율은 40.0%로 기준 비율 54.1%보다 낮습니다.'\n"
    "<span>25건 중 10건 남음 (40.0%)</span>\n"
    "ledgerStepCounts: ['25건', String(0) + '건'],\n"
)


def write_data(tmp: Path, base_rate: float, base_side: str,
               ledger: list) -> Path:
    """export_frontend.py 가 내는 모양대로 최소한만 적어 둔다."""
    f = tmp / "frontend_data.js"
    f.write_text(
        "const SCORE = " + json.dumps(
            {"base_rate": base_rate, "base_side": base_side},
            ensure_ascii=False) + ";\n"
        "const LEDGER = " + json.dumps(ledger, ensure_ascii=False) + ";\n",
        encoding="utf-8")
    return f


class TestBaseRateSwap(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.tmp = Path(tempfile.mkdtemp())
        self._orig = patch_design.DATA

    def tearDown(self):
        patch_design.DATA = self._orig

    def use(self, base_rate, base_side, ledger):
        patch_design.DATA = write_data(self.tmp, base_rate, base_side, ledger)
        return patch_design.fix_base_rate(SRC)

    def test_소멸이_많으면_유지_비율은_뒤집어_쓴다(self):
        # 기저율 59.7% 는 "전부 소멸" 쪽 값이다. 화면이 말하는 유지 비율은
        # 그 반대편이라 40.3% 가 되어야 한다. 59.7% 를 그대로 쓰면 모델이
        # 넘어야 할 바가 19.4%p 높아진다.
        out, note = self.use(0.597, "fade", [["a", 40, 10, 10, True]])
        self.assertIn("유지한 비율 40.3%", out)
        self.assertNotIn("59.7%", out)
        self.assertIn("40.3%", note)

    def test_지속이_많으면_그대로_쓴다(self):
        out, _ = self.use(0.62, "persist", [["a", 40, 10, 10, True]])
        self.assertIn("유지한 비율 62.0%", out)

    def test_최근이_기준보다_높으면_높습니다로_바꾼다(self):
        # 시안에는 "낮습니다" 라고 단정돼 있다. 34건 중 14건(41.2%)은
        # 40.3% 보다 높으므로 숫자만 갈면 거짓말이 된다.
        ledger = [["x", 40, 10, 10, True]] * 14 + [["y", 40, 10, 99, False]] * 20
        out, _ = self.use(0.597, "fade", ledger)
        self.assertIn("41.2%로 기준 비율 40.3%보다 높습니다.", out)
        self.assertNotIn("보다 낮습니다", out)

    def test_최근이_기준보다_낮으면_낮습니다를_지킨다(self):
        ledger = [["x", 40, 10, 10, True]] * 2 + [["y", 40, 10, 99, False]] * 8
        out, _ = self.use(0.597, "fade", ledger)
        self.assertIn("20.0%로 기준 비율 40.3%보다 낮습니다.", out)

    def test_같으면_같습니다로_쓴다(self):
        ledger = [["x", 40, 10, 10, True]] * 4 + [["y", 40, 10, 99, False]] * 6
        out, _ = self.use(0.6, "persist", ledger)
        self.assertIn("40.0%로 기준 비율 60.0%보다 낮습니다.", out)
        out2, _ = self.use(0.4, "persist", ledger)
        self.assertIn("40.0%로 기준 비율 40.0%보다 같습니다.", out2)

    def test_장부_머리말의_건수도_같이_바꾼다(self):
        # 머리말만 옛 수로 남으면 한 화면에 25건과 34건이 같이 보인다.
        ledger = [["x", 40, 10, 10, True]] * 14 + [["y", 40, 10, 99, False]] * 20
        out, _ = self.use(0.597, "fade", ledger)
        self.assertIn(">34건 중 14건 남음 (41.2%)<", out)
        self.assertNotIn("25건 중 10건", out)
        self.assertIn("ledgerStepCounts: [LEDGER.length + '건', ", out)

    def test_바꿀_글이_없으면_멈춘다(self):
        patch_design.DATA = write_data(self.tmp, 0.597, "fade",
                                       [["a", 40, 10, 10, True]])
        with self.assertRaises(SystemExit):
            patch_design.fix_base_rate("기준 비율에 대해 아무 말도 없는 화면")

    def test_성적표가_없으면_멈춘다(self):
        # --verdicts 없이 내보내면 SCORE 가 null 이 된다. 그대로 두면 옛
        # 숫자가 화면에 남으므로 조용히 넘어가면 안 된다.
        f = self.tmp / "frontend_data.js"
        f.write_text("const SCORE = null;\nconst LEDGER = [];\n",
                     encoding="utf-8")
        patch_design.DATA = f
        with self.assertRaises(SystemExit):
            patch_design.fix_base_rate(SRC)


if __name__ == "__main__":
    unittest.main()
