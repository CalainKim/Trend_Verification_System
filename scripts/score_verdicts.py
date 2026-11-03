#!/usr/bin/env python3
"""판정을 채점한다.

    python scripts/score_verdicts.py --verdicts runs/2026-11-01
    python scripts/score_verdicts.py --baselines          # 기준 전략만 본다
    python scripts/score_verdicts.py --verdicts x --out benchmark/scorecard.md

판정 파일은 세 형태를 받는다.
  1. 디렉터리 안의 <case_id>.json       {"verdict": "WATCH"}
  2. 검증 파트 산출물 result.json       review.verdict 또는 selection.status
  3. 하나의 매핑 파일                   {"<case_id>": "WATCH", ...}

정답 파일은 저장소에 없다. 수집 파트만 가지고 있고, 봉인 해시로 바뀌지
않았음을 확인한다.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from datetime import date
from pathlib import Path
from typing import Dict

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from trend_pipeline import scoring as sc  # noqa: E402
from trend_pipeline.persistence import FADE, PERSIST  # noqa: E402

DEFAULT_BENCH = ROOT / "benchmark"

#: 정답이 없는 쪽에서 채점을 시도할 때 내보내는 안내. 전에는 "정답 파일이
#: 없다, build_persistence_cases.py 로 먼저 만든다" 고만 했다. 그 길은 DB 가
#: 있어야 하고 검증 파트는 DB 를 받지 않으므로, 막힌 길로 안내하는 셈이었다.
HANDOVER = """## 채점은 수집 파트가 한다

판정 {n}건을 {path} 에서 읽었다. 형식은 문제없다.

정답(labels.sealed.json)이 이 저장소에 없어서 여기서는 점수를 낼 수 없다.
일부러 뺀 것이다. 정답을 보면서 판정기를 고치면 성적이 뜻을 잃는다.

판정 파일을 수집 파트에 넘기면 채점해서 성적표를 돌려준다. 여러 파일을
한 덩어리로 만들어 보내면 받는 쪽에서 손댈 것이 없다.

    python scripts/score_verdicts.py --verdicts {path} --pack verdicts.json

아래 기준 전략은 정답 없이도 계산된다. 넘어야 할 선을 미리 보는 용도다."""


def load_labels(bench: Path = DEFAULT_BENCH) -> Dict[str, str]:
    """정답을 읽고 봉인 해시를 확인한다.

    채점이 끝난 뒤 정답을 고치면 어떤 점수든 만들 수 있다. 해시가 맞지
    않으면 채점을 진행하지 않는다.
    """
    sealed, digest = bench / "labels.sealed.json", bench / "labels.digest.txt"
    if not sealed.exists():
        raise SystemExit(f"정답 파일이 없다: {sealed}\n"
                         f"scripts/build_persistence_cases.py 로 먼저 만든다.")
    raw = sealed.read_text(encoding="utf-8")
    if digest.exists():
        stated = digest.read_text(encoding="utf-8").split()[1]
        actual = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        if stated != actual:
            raise SystemExit(
                f"봉인 해시가 맞지 않는다. 정답이 바뀌었다.\n"
                f"  기록 {stated}\n  실제 {actual}")
    return json.loads(raw)["labels"]


def load_digest(bench: Path = DEFAULT_BENCH):
    """봉인 해시 파일에서 건수와 지속 비율만 읽는다.

    정답 파일은 검증 파트에 주지 않는다. 그래도 넘어야 할 선은 알아야
    하므로, 해시 파일에 함께 적어 둔 두 숫자로 기준 전략을 낸다. 이 둘로는
    어느 케이스가 지속인지 알 수 없어 블라인드가 깨지지 않는다.
    """
    f = bench / "labels.digest.txt"
    if not f.exists():
        return None
    out = {}
    for line in f.read_text(encoding="utf-8").splitlines():
        k, _, v = line.partition(" ")
        v = v.strip()
        if k == "n":
            out["n"] = int(v)
        elif k == "base":
            out["persist"] = float(v)
    return out if {"n", "persist"} <= out.keys() else None


def baselines_from_digest(d: dict) -> str:
    """정답 없이 기준 전략을 낸다. 무작위는 기댓값이라 그렇게 적는다."""
    persist, n = d["persist"], d["n"]
    base = max(persist, 1 - persist)
    rows = [("전부 지속", persist), ("전부 소멸", 1 - persist)]
    out = ["## 기준 전략", "",
           f"정답 파일 없이 봉인 해시의 두 숫자로 계산했다 (케이스 {n}건, "
           f"지속 {persist:.1%}).", "",
           "| 전략 | 커버리지 | 정확도 | 기저율 대비 |", "|---|---|---|---|"]
    for name, acc in rows:
        out.append(f"| {name} | 100% | {acc:.1%} | {(acc - base) * 100:+.1f}%p |")
    out.append(f"| 무작위 | 100% | 50.0% (기댓값) | {(0.5 - base) * 100:+.1f}%p |")
    out.append("| 전부 보류 | 0% | - | - |")
    out += ["",
            f"> 넘어야 할 선은 {base:.1%} 다. "
            f"{'전부 소멸' if persist < 0.5 else '전부 지속'}로 찍었을 때 나온다."]
    return "\n".join(out)


#: 정답을 저장소에 두지 않는 벤치마크. 여기 채점하는 것이 제출이다.
SEALED = ("benchmark", "benchmark-index")


def log_submission(bench: Path, verdicts: Path, n: int, acc) -> int:
    """봉인 세트에 채점한 횟수를 남기고 지금이 몇 회차인지 돌려준다.

    홀드아웃은 볼 때마다 닳는다. 열 번 넣고 제일 좋은 것을 고르면 보고하는
    값이 "열 번 중 최댓값" 이라서 실제보다 높다. 막는 방법은 봉인을 더 세게
    하는 것이 아니라 횟수를 적는 것이다. 읽는 사람이 알아서 할인해 본다.

    연습용 벤치마크(정답이 저장소에 있는 것)는 세지 않는다. 그쪽은 마음껏
    돌리라고 열어 둔 것이다.
    """
    if bench.name not in SEALED:
        return 0
    f = bench / "submissions.tsv"
    if not f.exists():
        f.write_text("회차\t날짜\t판정 경로\t건수\t정확도\n", encoding="utf-8")
    rows = [r for r in f.read_text(encoding="utf-8").splitlines()[1:] if r.strip()]
    nth = len(rows) + 1
    shown = "-" if acc is None else f"{acc:.3f}"
    with f.open("a", encoding="utf-8") as fh:
        fh.write(f"{nth}\t{date.today().isoformat()}\t{verdicts}\t{n}\t{shown}\n")
    return nth


def submission_note(nth: int) -> str:
    """회차를 성적표에 적을 문장. 늘어나면 경고를 붙인다."""
    if nth <= 1:
        return f"> 봉인 세트 {nth}회차 제출이다. 아직 홀드아웃이 닳지 않았다"
    s = (f"> 봉인 세트 {nth}회차 제출이다. 같은 문제지를 {nth}번 봤으므로 "
         f"이 숫자는 한 번만 봤을 때보다 높게 나온다")
    if nth >= 5:
        s += ("\n\n> 주의. 5회차를 넘었다. 여러 번 중 제일 좋은 것을 고르는 "
              "셈이 되므로 보고할 때 회차를 반드시 함께 적어야 한다")
    return s


def _verdict_from(obj) -> str:
    """여러 산출물 형식에서 판정 값을 꺼낸다."""
    if isinstance(obj, str):
        return obj
    if not isinstance(obj, dict):
        raise ValueError(f"판정을 읽을 수 없는 형식이다: {type(obj).__name__}")
    for path in (("verdict",), ("result", "verdict"),
                 ("review", "verdict"), ("review", "status"),
                 ("selection", "status"), ("status",)):
        cur = obj
        for key in path:
            if not isinstance(cur, dict) or key not in cur:
                cur = None
                break
            cur = cur[key]
        if isinstance(cur, str) and cur.strip() and cur != "not_run":
            return cur
    raise ValueError(f"판정 값을 찾지 못했다. 본 키: {sorted(obj)[:6]}")


def load_verdicts(path: Path) -> Dict[str, str]:
    if path.is_file():
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise SystemExit("매핑 파일은 {case_id: verdict} 형태여야 한다.")
        return {k: _verdict_from(v) for k, v in data.items()}

    out: Dict[str, str] = {}
    for f in sorted(path.rglob("*.json")):
        if f.name in ("bundle.json", "labels.sealed.json"):
            continue
        try:
            obj = json.loads(f.read_text(encoding="utf-8"))
            cid = obj.get("case_id") if isinstance(obj, dict) else None
            out[cid or f.stem] = _verdict_from(obj)
        except (ValueError, KeyError):
            continue          # 판정이 아닌 파일은 건너뛴다
    if not out:
        raise SystemExit(f"{path} 에서 판정을 찾지 못했다.")
    return out


def render(card: sc.Scorecard, title: str) -> str:
    L = [f"## {title}", ""]
    L.append(f"- 케이스 {card.n_cases}건, 답변 {card.n_answered}건, "
             f"기권 {card.n_abstained}건 (커버리지 {card.coverage:.1%})")
    if card.accuracy is None:
        L.append("- 답한 케이스가 없어 채점할 수 없다")
        # 전부 기권으로 나오는 흔한 원인은 판정이 아니라 case_id 가 안 맞는
        # 것이다. 그 사실은 notes 에 있으니 여기서도 반드시 내보낸다.
        # 빼면 "모델이 전부 기권했다" 로 읽혀서 엉뚱한 곳을 보게 된다.
        for n in card.notes:
            L.append(f"\n> {n}")
        return "\n".join(L)
    L.append(f"- 정확도 {card.accuracy:.1%} "
             f"(95% 신뢰구간 {card.ci[0]:.1%} ~ {card.ci[1]:.1%})")
    L.append(f"- 기저율 전체 {card.base_rate_all:.1%}, "
             f"답한 부분 {card.base_rate_answered:.1%}")
    L.append(f"- 기저율 대비 {card.lift * 100:+.1f}%p")
    L.append(f"- 기저율을 유의하게 넘었나: "
             f"**{'그렇다' if card.beats_base_rate else '아니다'}** "
             f"(신뢰구간 아래끝 {card.ci[0]:.1%} vs 기저율 "
             f"{card.base_rate_answered:.1%})")
    if card.confusion:
        L.append("")
        L.append("| 정답 | 예측 | 건수 |")
        L.append("|---|---|---|")
        for k in sorted(card.confusion):
            t, p = k.split("->")
            L.append(f"| {t} | {p} | {card.confusion[k]} |")
    for n in card.notes:
        L.append(f"\n> {n}")
    return "\n".join(L)


def baselines(labels: Dict[str, str]) -> str:
    """찍기 전략들의 점수. 모델은 이것을 넘어야 뜻이 있다."""
    rng = random.Random(20261029)
    strategies = {
        "전부 지속": {c: PERSIST for c in labels},
        "전부 소멸": {c: FADE for c in labels},
        "무작위 (고정 시드)": {c: rng.choice([PERSIST, FADE]) for c in labels},
        "전부 보류": {c: "HOLD" for c in labels},
    }
    out = ["## 기준 전략", "",
           "모델 성적은 이 값들과 비교해야 뜻이 있다.", "",
           "| 전략 | 커버리지 | 정확도 | 기저율 대비 |", "|---|---|---|---|"]
    for name, v in strategies.items():
        card = sc.score(labels, v)
        acc = f"{card.accuracy:.1%}" if card.accuracy is not None else "-"
        lift = f"{card.lift * 100:+.1f}%p" if card.lift is not None else "-"
        out.append(f"| {name} | {card.coverage:.0%} | {acc} | {lift} |")
    return "\n".join(out)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="판정 채점")
    p.add_argument("--verdicts", default=None, help="판정 파일이나 디렉터리")
    p.add_argument("--benchmark", default=str(DEFAULT_BENCH),
                   help="정답이 있는 벤치마크 경로")
    p.add_argument("--label", default="판정 결과", help="성적표 제목")
    p.add_argument("--baselines", action="store_true", help="기준 전략만 출력")
    p.add_argument("--out", default=None, help="성적표를 쓸 경로")
    p.add_argument("--pack", default=None,
                   help="판정을 {case_id: verdict} 한 덩어리로 묶어 쓸 경로")
    args = p.parse_args(argv)

    if args.pack:
        if not args.verdicts:
            raise SystemExit("--pack 은 --verdicts 와 함께 쓴다.")
        got = load_verdicts(Path(args.verdicts))
        Path(args.pack).write_text(
            json.dumps(got, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8")
        print(f"판정 {len(got)}건을 {args.pack} 에 묶었다. 이 파일을 넘기면 된다.")
        return 0

    bench = Path(args.benchmark)
    sealed = bench / "labels.sealed.json"

    # 정답은 수집 파트만 가진다. 검증 파트가 돌릴 때는 여기로 온다.
    if not sealed.exists():
        d = load_digest(bench)
        if d is None:
            raise SystemExit(f"정답도 봉인 해시도 없다: {bench}")
        parts = [baselines_from_digest(d)]
        if args.verdicts:
            got = load_verdicts(Path(args.verdicts))
            parts.insert(0, HANDOVER.format(n=len(got), path=args.verdicts))
        text = "\n\n".join(parts)
        print(text)
        if args.out:
            Path(args.out).write_text(text + "\n", encoding="utf-8")
            print(f"\n{args.out} 에 저장했다.")
        return 0

    labels = load_labels(bench)
    parts = [baselines(labels)]

    if args.verdicts:
        verdicts = load_verdicts(Path(args.verdicts))
        card = sc.score(labels, verdicts)
        body = render(card, args.label)
        nth = log_submission(bench, Path(args.verdicts),
                             card.n_answered, card.accuracy)
        if nth:
            body += "\n\n" + submission_note(nth)
        parts.insert(0, body)
    elif not args.baselines:
        parts.append("\n판정 경로를 주지 않았다. --verdicts 로 지정한다.")

    text = "\n\n".join(parts)
    print(text)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
        print(f"\n성적표를 {args.out} 에 저장했다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
