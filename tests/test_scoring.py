"""판정 채점 검증.

채점기는 틀리기 쉬운 자리가 몇 군데 있다. 보류를 오답으로 세면 신중한 판정이
벌을 받고, 채점에서 빼기만 하면 쉬운 것만 골라 답한 판정이 상을 받는다.
정확도 100% 가 성과가 아닐 수 있다는 것을 숫자로 잡아야 한다.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from trend_pipeline import scoring as sc  # noqa: E402
from trend_pipeline.persistence import FADE, PERSIST  # noqa: E402


@pytest.fixture()
def labels():
    #  지속 6건, 소멸 4건
    return {f"c{i}": (PERSIST if i < 6 else FADE) for i in range(10)}


# ------------------------------------------------------------ 어휘 변환

def test_accepts_all_three_vocabularies():
    """저장소에 판정 어휘가 세 가지 돌아다닌다. 어느 쪽으로 와도 받는다."""
    assert sc.to_prediction("WATCH") == PERSIST
    assert sc.to_prediction("NOT_SUPPORTED") == FADE
    assert sc.to_prediction("confirm") == PERSIST
    assert sc.to_prediction("reject") == FADE
    assert sc.to_prediction(PERSIST) == PERSIST


def test_hold_is_abstention_not_a_prediction():
    assert sc.to_prediction("HOLD") is None
    assert sc.to_prediction("hold") is None


def test_unknown_verdict_raises():
    """조용히 버리면 채점이 소리 없이 틀어진다."""
    with pytest.raises(sc.UnknownVerdict):
        sc.to_prediction("MAYBE")


# ------------------------------------------------------------ 기권 처리

def test_abstention_is_not_counted_wrong(labels):
    """보류는 틀린 답이 아니라 답하지 않은 것이다."""
    card = sc.score(labels, {c: "HOLD" for c in labels})
    assert card.n_abstained == 10
    assert card.n_answered == 0
    assert card.accuracy is None
    assert card.coverage == 0.0


def test_missing_verdict_counts_as_abstention(labels):
    card = sc.score(labels, {"c0": "WATCH"})
    assert card.n_answered == 1
    assert card.n_abstained == 9
    assert any("오지 않은" in n for n in card.notes)


def test_answering_only_easy_cases_does_not_beat_base_rate(labels):
    """정답이 지속인 것만 골라 답하면 정확도는 100% 지만 성과가 아니다.

    답한 부분집합의 기저율도 100% 라서 기저율을 넘지 못한다.
    """
    cherry = {c: ("WATCH" if v == PERSIST else "HOLD") for c, v in labels.items()}
    card = sc.score(labels, cherry)
    assert card.accuracy == 1.0
    assert card.base_rate_answered == 1.0
    assert not card.beats_base_rate
    assert any("쉬운 쪽" in n for n in card.notes)


# ------------------------------------------------------------ 기저율 비교

def test_always_persist_equals_base_rate(labels):
    card = sc.score(labels, {c: "WATCH" for c in labels})
    assert card.accuracy == pytest.approx(0.6)
    assert card.base_rate_all == pytest.approx(0.6)
    assert card.lift == pytest.approx(0.0)
    assert not card.beats_base_rate


def test_perfect_verdicts_beat_base_rate():
    labels = {f"c{i}": (PERSIST if i < 30 else FADE) for i in range(60)}
    perfect = {c: ("WATCH" if v == PERSIST else "NOT_SUPPORTED")
               for c, v in labels.items()}
    card = sc.score(labels, perfect)
    assert card.accuracy == 1.0
    assert card.beats_base_rate


def test_small_sample_does_not_claim_significance():
    """표본이 작으면 점추정이 높아도 유의하다고 말하면 안 된다."""
    labels = {"a": PERSIST, "b": FADE, "c": PERSIST}
    card = sc.score(labels, {"a": "WATCH", "b": "NOT_SUPPORTED", "c": "WATCH"})
    assert card.accuracy == 1.0
    assert not card.beats_base_rate      # 3건으로는 아무것도 주장할 수 없다


# ------------------------------------------------------------ 집계 무결성

def test_unknown_case_ids_are_excluded(labels):
    """정답 없는 케이스를 맞혔다고 세면 점수가 부풀려진다."""
    card = sc.score(labels, {**{c: "WATCH" for c in labels}, "없는것": "WATCH"})
    assert card.n_cases == 10
    assert card.n_answered == 10
    assert any("정답에 없는" in n for n in card.notes)


def test_confusion_matrix_adds_up(labels):
    mixed = {"c0": "WATCH", "c1": "NOT_SUPPORTED", "c6": "WATCH",
             "c7": "NOT_SUPPORTED"}
    card = sc.score(labels, mixed)
    assert sum(card.confusion.values()) == card.n_answered == 4
    assert card.confusion[f"{PERSIST}->{PERSIST}"] == 1
    assert card.confusion[f"{PERSIST}->{FADE}"] == 1
    assert card.confusion[f"{FADE}->{PERSIST}"] == 1
    assert card.confusion[f"{FADE}->{FADE}"] == 1
    assert card.correct == 2


class TestBaseRateIsTheBestGuess:
    """넘어야 할 기준은 전부 지속이 아니라 제일 잘 찍었을 때다.

    전부 지속만 기준으로 두면, 지속이 드문 문제지에서 모델이 아무 생각 없이
    전부 소멸이라고 찍는 것보다 못하면서도 기저율을 넘었다고 나온다. 누수를
    막고 문제지를 다시 만들자 지속이 40.3% 가 되어 이 구멍이 실제로 열렸다.
    전부 소멸이 59.7% 인데 기저율은 40.3% 로 찍히고 있었다.
    """

    def _labels(self, n_persist, n_fade):
        d = {f"p{i}": sc.PERSIST for i in range(n_persist)}
        d.update({f"f{i}": sc.FADE for i in range(n_fade)})
        return d

    def test_uses_the_bigger_side(self):
        labels = self._labels(4, 6)              # 지속 40%, 소멸 60%
        card = sc.score(labels, {k: sc.PERSIST for k in labels})
        assert card.base_rate_all == pytest.approx(0.6)
        assert card.persist_rate_all == pytest.approx(0.4)

    def test_always_fade_cannot_beat_the_base_rate(self):
        """전부 소멸로 찍는 판정기가 기준을 넘으면 기준이 틀린 것이다."""
        labels = self._labels(4, 6)
        card = sc.score(labels, {k: sc.FADE for k in labels})
        assert card.accuracy == pytest.approx(0.6)
        assert not card.beats_base_rate

    def test_always_persist_cannot_beat_it_either(self):
        labels = self._labels(6, 4)
        card = sc.score(labels, {k: sc.PERSIST for k in labels})
        assert not card.beats_base_rate

    def test_says_which_side_is_the_bar(self):
        labels = self._labels(4, 6)
        card = sc.score(labels, {k: sc.PERSIST for k in labels})
        assert any("전부 소멸" in n for n in card.notes)


class TestAllAbstainedStillExplainsWhy:
    """전부 기권으로 나왔을 때 원인을 숨기지 않는다.

    흔한 원인은 모델이 기권한 것이 아니라 case_id 가 안 맞는 것이다.
    판정 폴더를 그대로 넘기면 파일 이름이 review.json 이라 키가 'review' 로
    잡히고, 정답과 한 건도 겹치지 않아 139건 전부 기권으로 집계된다.
    성적표가 그 사실을 적지 않으면 모델을 의심하며 엉뚱한 곳을 보게 된다.
    """

    def _render(self, verdicts):
        import importlib.util
        root = Path(__file__).resolve().parents[1]
        spec = importlib.util.spec_from_file_location(
            "score_verdicts", root / "scripts" / "score_verdicts.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        labels = {f"c{i}": PERSIST for i in range(5)}
        return mod.render(sc.score(labels, verdicts), "판정 결과")

    def test_names_the_unmatched_id(self):
        out = self._render({"review": PERSIST})
        assert "채점할 수 없다" in out
        assert "review" in out

    def test_says_how_many_got_no_verdict(self):
        out = self._render({"review": PERSIST})
        assert "판정이 오지 않은 케이스 5건" in out


class TestVerificationPartCanRunWithoutLabels:
    """정답 없이도 넘어야 할 선은 보여야 한다.

    정답은 블라인드 때문에 저장소에 없다. 그런데 기준 전략까지 막히면 검증
    파트는 자기 성적이 찍기보다 나은지조차 알 수 없다. 봉인 해시에 건수와
    지속 비율이 함께 적혀 있어 그 둘로 계산한다. 어느 케이스가 지속인지는
    알 수 없으므로 블라인드는 유지된다.
    """

    def _mod(self):
        import importlib.util
        root = Path(__file__).resolve().parents[1]
        spec = importlib.util.spec_from_file_location(
            "score_verdicts", root / "scripts" / "score_verdicts.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_digest_alone_gives_the_bar(self):
        out = self._mod().baselines_from_digest({"n": 139, "persist": 0.4029})
        assert "59.7%" in out
        assert "전부 소멸로 찍었을 때" in out

    def test_names_persist_when_persist_is_the_majority(self):
        out = self._mod().baselines_from_digest({"n": 61, "persist": 0.541})
        assert "54.1%" in out
        assert "전부 지속로 찍었을 때" in out

    def test_random_is_marked_as_an_expectation(self):
        """정답이 없으면 고정 시드 무작위의 실제 점수를 낼 수 없다."""
        out = self._mod().baselines_from_digest({"n": 139, "persist": 0.4029})
        assert "기댓값" in out


class TestResultVerdictShapeIsRead:
    """review.py 가 쓰는 result.verdict 를 채점기가 읽어야 한다.

    화이트리스트에 이 경로가 빠져 있었다. 그래서 판정 출력 원본을 그대로
    넘기면 "판정을 찾지 못했다" 가 났다.
    """

    def test_reads_nested_result(self):
        import importlib.util
        root = Path(__file__).resolve().parents[1]
        spec = importlib.util.spec_from_file_location(
            "score_verdicts", root / "scripts" / "score_verdicts.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        assert mod._verdict_from({"result": {"verdict": "WATCH"}}) == "WATCH"


class TestSealedSetSubmissionsAreCounted:
    """봉인 세트에 몇 번 채점했는지 남긴다.

    홀드아웃은 볼 때마다 닳는다. 열 번 넣고 제일 좋은 것을 고르면 보고하는
    값이 "열 번 중 최댓값" 이라서 실제보다 높다. 봉인을 더 세게 해서 막을
    수 없고, 횟수를 적어 읽는 사람이 할인해 보게 하는 것이 맞다.

    정답을 저장소에 둔 연습용 벤치마크는 세지 않는다. 마음껏 돌리라고
    열어 둔 것이라 세면 쓸 수 없게 된다.
    """

    def _mod(self):
        import importlib.util
        root = Path(__file__).resolve().parents[1]
        spec = importlib.util.spec_from_file_location(
            "score_verdicts", root / "scripts" / "score_verdicts.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_counts_up_on_a_sealed_set(self, tmp_path):
        mod = self._mod()
        bench = tmp_path / "benchmark"
        bench.mkdir()
        first = mod.log_submission(bench, Path("a.json"), 95, 0.779)
        second = mod.log_submission(bench, Path("b.json"), 95, 0.801)
        assert (first, second) == (1, 2)
        rows = (bench / "submissions.tsv").read_text(encoding="utf-8").splitlines()
        assert len(rows) == 3           # 머리글 한 줄 + 제출 두 줄
        assert "0.801" in rows[2]

    def test_does_not_count_an_open_set(self, tmp_path):
        mod = self._mod()
        bench = tmp_path / "benchmark-index-long"
        bench.mkdir()
        assert mod.log_submission(bench, Path("a.json"), 300, 0.7) == 0
        assert not (bench / "submissions.tsv").exists()

    def test_records_an_unscorable_run(self, tmp_path):
        """전부 기권이어도 봉인 세트를 본 것은 본 것이다."""
        mod = self._mod()
        bench = tmp_path / "benchmark"
        bench.mkdir()
        assert mod.log_submission(bench, Path("a.json"), 0, None) == 1
        assert "\t-\n" in (bench / "submissions.tsv").read_text(encoding="utf-8")

    def test_first_submission_says_nothing_is_spent(self):
        assert "닳지 않았다" in self._mod().submission_note(1)

    def test_later_submission_warns_the_number_is_optimistic(self):
        note = self._mod().submission_note(3)
        assert "3번" in note and "높게" in note

    def test_fifth_submission_adds_a_louder_warning(self):
        assert "5회차를 넘었다" in self._mod().submission_note(5)
