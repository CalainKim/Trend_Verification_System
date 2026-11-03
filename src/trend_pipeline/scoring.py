"""판정을 정답과 맞춰 채점한다.

검증 파트가 번들을 받아 판정을 내면 그것이 기저율보다 나은지를 재야 한다.
정확도만 보고하면 찍은 것과 같은 점수를 성과로 읽게 되므로, 항상 기저율과
함께 낸다.

기권을 따로 세는 이유가 있다. 판정에는 보류가 있고, 보류는 틀린 답이 아니라
답하지 않은 것이다. 보류를 오답으로 세면 신중한 판정이 벌을 받고, 채점에서
빼기만 하면 어려운 건만 골라 보류한 판정이 상을 받는다. 그래서 커버리지와
정확도를 함께 보고하고, 기저율도 답한 부분집합에서 다시 계산한다.

전체 기저율과 답한 부분의 기저율이 크게 다르면 그 자체가 발견이다. 쉬운
쪽에만 답했다는 뜻이기 때문이다.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, Mapping, Optional, Sequence, Tuple

from .persistence import FADE, PERSIST

#: 판정 어휘를 지속 여부 예측으로 옮긴다.
#:
#: 저장소에 세 가지 어휘가 돌아다닌다. verification/verdict.example.json 의
#: 제안값(confirm/hold/reject), src/trend_poc/review.py 가 모델에 요구하는 값
#: (WATCH/HOLD/NOT_SUPPORTED), 그리고 이 모듈의 정답값(persist/fade)이다.
#: 어느 쪽으로 와도 받되 변환 규칙을 한곳에만 둔다.
VERDICT_MAP: Dict[str, Optional[str]] = {
    "WATCH": PERSIST, "NOT_SUPPORTED": FADE, "HOLD": None,
    "confirm": PERSIST, "reject": FADE, "hold": None,
    PERSIST: PERSIST, FADE: FADE,
}


class UnknownVerdict(ValueError):
    """모르는 판정 값. 조용히 버리면 채점이 소리 없이 틀어진다."""


def to_prediction(verdict: str) -> Optional[str]:
    key = verdict.strip()
    if key not in VERDICT_MAP:
        lowered = key.lower()
        if lowered not in VERDICT_MAP:
            raise UnknownVerdict(
                f"모르는 판정 값 {verdict!r}. 쓸 수 있는 값: "
                f"{', '.join(sorted(VERDICT_MAP))}")
        key = lowered
    return VERDICT_MAP[key]


def wilson(k: int, n: int, z: float = 1.96) -> Tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, centre - half), min(1.0, centre + half))


@dataclass
class Scorecard:
    n_cases: int
    n_answered: int
    n_abstained: int
    correct: int
    #: 제일 잘 찍었을 때의 정확도. 전부 지속과 전부 소멸 가운데 높은 쪽이다.
    base_rate_all: Optional[float]
    base_rate_answered: Optional[float]
    accuracy: Optional[float]
    ci: Tuple[float, float]
    #: 지속이 실제로 얼마나 흔한지. 기준이 아니라 문제지의 성질이다.
    persist_rate_all: Optional[float] = None
    persist_rate_answered: Optional[float] = None
    confusion: Dict[str, int] = field(default_factory=dict)
    notes: list = field(default_factory=list)

    @property
    def coverage(self) -> float:
        return self.n_answered / self.n_cases if self.n_cases else 0.0

    @property
    def lift(self) -> Optional[float]:
        if self.accuracy is None or self.base_rate_answered is None:
            return None
        return self.accuracy - self.base_rate_answered

    @property
    def beats_base_rate(self) -> bool:
        """정확도 신뢰구간의 아래끝이 기저율을 넘어야 넘었다고 본다.

        점추정만 비교하면 표본이 작을 때 우연을 성과로 읽는다.
        """
        if self.accuracy is None or self.base_rate_answered is None:
            return False
        return self.ci[0] > self.base_rate_answered


def score(labels: Mapping[str, str],
          verdicts: Mapping[str, str]) -> Scorecard:
    """정답과 판정을 맞춘다.

    labels 에 없는 case_id 가 verdicts 에 있으면 채점하지 않고 note 에 남긴다.
    정답 없는 케이스를 맞혔다고 세면 점수가 부풀려진다.
    """
    notes = []
    unknown = sorted(set(verdicts) - set(labels))
    if unknown:
        notes.append(f"정답에 없는 case_id {len(unknown)}건은 채점에서 뺐다: "
                     f"{', '.join(unknown[:3])}{' 외' if len(unknown) > 3 else ''}")
    missing = sorted(set(labels) - set(verdicts))
    if missing:
        notes.append(f"판정이 오지 않은 케이스 {len(missing)}건은 기권으로 셌다")

    answered: list = []
    abstained = 0
    confusion: Dict[str, int] = {}
    correct = 0
    for cid, truth in labels.items():
        raw = verdicts.get(cid)
        pred = to_prediction(raw) if raw is not None else None
        if pred is None:
            abstained += 1
            continue
        answered.append(truth)
        key = f"{truth}->{pred}"
        confusion[key] = confusion.get(key, 0) + 1
        if pred == truth:
            correct += 1

    n = len(labels)
    n_ans = len(answered)
    # 기저율은 "전부 지속이라고 찍었을 때" 가 아니라 "제일 잘 찍었을 때" 다.
    # 전부 지속만 보면, 지속이 드문 문제지에서 모델이 아무 생각 없이 전부
    # 소멸이라고 찍는 것보다 못하면서도 기저율을 넘었다고 나온다. 실제로
    # 누수를 막고 문제지를 다시 만들자 지속이 40.3% 가 되어, 전부 소멸이
    # 59.7% 로 가장 센 기준이 됐다.
    def _majority(vals) -> Optional[float]:
        vals = list(vals)
        if not vals:
            return None
        share = sum(1 for v in vals if v == PERSIST) / len(vals)
        return max(share, 1 - share)

    base_all = _majority(labels.values())
    base_ans = _majority(answered)
    persist_all = (sum(1 for v in labels.values() if v == PERSIST) / n) if n else None
    persist_ans = (sum(1 for v in answered if v == PERSIST) / n_ans) if n_ans else None
    acc = (correct / n_ans) if n_ans else None

    if persist_ans is not None and base_ans is not None and persist_ans < base_ans:
        notes.append(
            f"답한 부분에서 지속은 {persist_ans:.1%} 뿐이다. 넘어야 할 기준은 "
            f"전부 소멸로 찍었을 때의 {base_ans:.1%} 다")

    if base_all is not None and base_ans is not None and abs(base_ans - base_all) > 0.1:
        notes.append(
            f"답한 부분의 기저율({base_ans:.1%})이 전체({base_all:.1%})와 "
            f"{abs(base_ans - base_all) * 100:.1f}%p 다르다. 쉬운 쪽에만 답했는지 "
            f"확인해야 한다")

    return Scorecard(
        n_cases=n, n_answered=n_ans, n_abstained=abstained, correct=correct,
        base_rate_all=base_all, base_rate_answered=base_ans, accuracy=acc,
        persist_rate_all=persist_all, persist_rate_answered=persist_ans,
        ci=wilson(correct, n_ans), confusion=confusion, notes=notes)
