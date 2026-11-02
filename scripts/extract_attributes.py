#!/usr/bin/env python3
"""상품명에서 속성 키워드를 뽑는다.

    python scripts/extract_attributes.py              # 추출하고 품질 보고
    python scripts/extract_attributes.py --out data/attribute_map.csv
    python scripts/extract_attributes.py --unmatched  # 사전에 없는 토큰만 본다

왜 필요한가. 29CM 은 "( Waffle ) 루즈핏 와플 헨리넥 긴팔티" 처럼 개별 상품을
가리키고, 네이버 데이터랩은 "헨리넥" 처럼 품목 키워드를 받는다. 지금은 두
채널의 키가 서로 다른 문자열이어서 교차 검증할 후보가 3개뿐이다. 상품명을
속성으로 쪼개면 커머스에서 발견한 것을 데이터랩으로 역추적할 수 있다.

여기서는 판정하지 않는다. 어떤 속성이 관측됐는가만 낸다.
사전은 data/attributes.yml 에 있고 사람이 검수한다.
"""

from __future__ import annotations

import argparse
import csv
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

import yaml

ROOT = Path(__file__).resolve().parents[1]
DICT_PATH = ROOT / "data" / "attributes.yml"
DB_PATH = ROOT / "data" / "signals.sqlite"

HANGUL = r"가-힣"

# 속성 뒤에 붙어도 같은 뜻을 유지하는 품목 접미사.
# 롱슬리브티, 반팔티셔츠처럼 한국어는 속성과 품목을 붙여 쓴다.
KO_SUFFIX = ("티", "셔츠", "탑", "톱", "니트", "원피스", "가디건", "블라우스", "집업")


def compile_variant(variant: str) -> re.Pattern:
    """표기 변형 하나를 정규식으로 만든다.

    띄어쓰기는 붙임표나 밑줄로도 쓰이므로 흡수한다. half zip 이 half-zip 과
    halfzip 을 모두 잡아야 한다.

    경계 처리를 언어별로 나눈 이유가 있다. 영어는 \b 로 충분하지만 한글에는
    \b 가 동작하지 않아서, 울(wool)이 서울에 걸리고 티가 티타늄에 걸린다.
    그래서 앞에 한글 음절이 붙으면 다른 단어의 일부로 본다.

    다만 뒤쪽은 막으면 안 된다. 롱슬리브티는 롱슬리브로 잡혀야 하는데
    뒤를 모두 막으면 티 때문에 통째로 빠진다. 품목 접미사만 열어 둔다.

    영어는 복수형을 함께 받는다. long sleeve 와 long sleeves 를 따로
    적게 하면 빠뜨린 쪽이 조용히 집계에서 사라진다.
    """
    parts = [re.escape(p) for p in variant.split()]
    body = r"[\s\-_/]*".join(parts)
    if re.search(f"[{HANGUL}]", variant):
        tail = f"(?![{HANGUL}])"
        if len(variant) >= 2:
            allow = "|".join(KO_SUFFIX)
            tail = f"(?:(?![{HANGUL}])|(?={allow}))"
        return re.compile(f"(?<![{HANGUL}]){body}{tail}")
    plural = "s?" if variant[-1].isalpha() else ""
    return re.compile(rf"(?<![a-z0-9]){body}{plural}(?![a-z0-9])", re.I)


def _words(lines) -> set:
    out = set()
    for line in lines or []:
        out.update(w.strip().lower() for w in line.split(",") if w.strip())
    return out


def load_dictionary(path: Path = DICT_PATH) -> Tuple[List[dict], set, set]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    attrs = []
    for a in raw["attributes"]:
        attrs.append({
            "canonical": a["canonical"],
            "group": a["group"],
            "no_color_after": bool(a.get("not_followed_by_color", False)),
            "patterns": [(v, compile_variant(v))
                         for v in sorted(a["variants"], key=len, reverse=True)],
        })
    buckets = raw.get("stopwords", {})
    colors = _words(buckets.get("color"))
    stop = set()
    for bucket in buckets.values():
        stop |= _words(bucket)
    return attrs, stop, colors


def clean(name: str) -> str:
    """상품명에서 속성과 무관한 표기를 걷어낸다.

    대괄호 머리말(27%), 차수 표기(7%), 품번, 색상 수 표기(15%)가 주된 노이즈다.
    괄호는 안에 신호가 섞여 있어서(( Waffle )) 통째로 버리지 않고 괄호만 벗긴다.
    """
    s = re.sub(r"\[[^\]]*\]", " ", name)
    s = re.sub(r"\d+\s*차|재입고|단독|예약발송", " ", s)
    s = re.sub(r"[A-Z]{2,}\d{4,}[A-Z0-9]*", " ", s)
    s = re.sub(r"\d{6,}[-\d]*", " ", s)
    s = re.sub(r"\b(FW|SS|AW)\s*\d{2}\b", " ", s, flags=re.I)
    s = re.sub(r"\d+\s*colors?", " ", s, flags=re.I)
    s = re.sub(r"[()\[\]*\"'&+#:,]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def followed_by_color(text: str, pos: int, colors: set) -> bool:
    """매칭 바로 뒤의 토큰이 색상인지 본다."""
    nxt = re.match(r"[\s\-_/]+([^\s\-_/]+)", text[pos:])
    return bool(nxt) and nxt.group(1).strip(".,").lower() in colors


def extract(name: str, attrs: List[dict], colors: set) -> List[dict]:
    text = clean(name)
    out = []
    for a in attrs:
        for variant, pat in a["patterns"]:
            m = pat.search(text)
            if not m:
                continue
            if a["no_color_after"] and followed_by_color(text, m.end(), colors):
                continue
            out.append({"canonical": a["canonical"], "group": a["group"],
                        "matched": variant, "pattern": pat})
            break
    return out


def leftover_tokens(name: str, hits: List[dict], stop: set) -> List[str]:
    """사전에 걸리지 않고 남은 토큰. 사전을 보강할 후보다."""
    text = clean(name).lower()
    for h in hits:
        # 원문 문자열이 아니라 정규식으로 지운다. mock-neck 처럼 붙임표가
        # 섞인 매칭은 변형 문자열("mock neck")로는 지워지지 않아서
        # 남은 토큰 보고에 허수가 쌓인다.
        text = h["pattern"].sub(" ", text)
    out = []
    for t in re.split(r"[\s\-_/]+", text):
        t = t.strip(".")
        if len(t) < 2 or t in stop or t.isdigit():
            continue
        out.append(t)
    return out


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="상품명에서 속성 키워드 추출")
    p.add_argument("--db", default=str(DB_PATH))
    p.add_argument("--out", default=None, help="상품별 속성 매핑 CSV 경로")
    p.add_argument("--unmatched", action="store_true",
                   help="사전에 없는 토큰 상위만 출력")
    p.add_argument("--top", type=int, default=40)
    args = p.parse_args(argv)

    attrs, stop, colors = load_dictionary()
    conn = sqlite3.connect(args.db)
    names = [r[0] for r in conn.execute(
        "SELECT DISTINCT keyword_raw FROM signal_raw WHERE channel='commerce_rank'")]

    per_attr: Counter = Counter()
    per_group: Dict[str, set] = defaultdict(set)
    rows: List[Tuple[str, str, str, str]] = []
    unmatched_names: List[str] = []
    tail: Counter = Counter()

    for name in names:
        hits = extract(name, attrs, colors)
        if not hits:
            unmatched_names.append(name)
        for h in hits:
            per_attr[h["canonical"]] += 1
            per_group[h["group"]].add(name)
            rows.append((name, h["canonical"], h["group"], h["matched"]))
        tail.update(leftover_tokens(name, hits, stop))

    if args.unmatched:
        print(f"=== 사전에 없는 토큰 상위 {args.top} ===")
        for t, n in tail.most_common(args.top):
            print(f"  {n:>4}  {t}")
        print(f"\n=== 속성이 하나도 안 잡힌 상품 {len(unmatched_names)}개 중 15개 ===")
        for n in unmatched_names[:15]:
            print(f"  {n[:66]}")
        return 0

    matched = len(names) - len(unmatched_names)
    print(f"상품 {len(names)}개, 사전 속성 {len(attrs)}개")
    print(f"속성이 1개 이상 잡힌 상품: {matched}개 ({matched/len(names)*100:.1f}%)\n")

    print("=== 속성군별 커버리지 ===")
    for g, s in sorted(per_group.items(), key=lambda kv: -len(kv[1])):
        print(f"  {g:8s} {len(s):>5}개 상품 ({len(s)/len(names)*100:>5.1f}%)")

    print(f"\n=== 속성별 상품 수 상위 {args.top} (데이터랩 질의 후보) ===")
    for i, (k, n) in enumerate(per_attr.most_common(args.top), 1):
        print(f"  {i:>2}. {k:<12} {n:>5}개 상품")

    if args.out:
        out = Path(args.out)
        with out.open("w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["product_name", "attribute", "group", "matched_variant"])
            w.writerows(rows)
        print(f"\n매핑 {len(rows)}건을 {out} 에 저장했다.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
