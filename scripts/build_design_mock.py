"""화면 시안용 실제 데이터를 뽑는다 (docs/design/mock-data.json).

속성별 커머스 신호: 29CM 상의 TOP100 의 최신 스냅샷과 7일 전 스냅샷을 비교한다.
속성별 검색 신호: 구글 트렌드 한국/미국 주간 지수 최근 26주.
지속성 기록: 2주 전 -> 1주 전에 10계단 이상 오른 상품이 지금 상승분 절반을 지켰는지.

    python scripts/build_design_mock.py              docs/design/mock-data.json 을 덮어쓴다
    python scripts/build_design_mock.py <경로>       다른 곳에 쓴다
"""
from __future__ import annotations

import json
import sqlite3
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))
from extract_attributes import extract, load_dictionary  # noqa: E402
from trend_pipeline.persistence import KEEP_RATIO, MIN_RISE  # noqa: E402

DB = ROOT / "data" / "signals.sqlite"
OUT = ROOT / "docs" / "design" / "mock-data.json"
GT_ATTRS = ["탑", "크루넥", "와플", "터틀넥", "후드티", "니트", "모크넥", "스카프", "울", "빈티지",
            "가디건", "기모", "하프집업", "집업"]


def daily_runs(c):
    return dict(c.execute("""select substr(observed_at,1,10), max(observed_at) from signal_raw
                             where channel='commerce_rank' and metric_type='rank' group by 1"""))


def rank_snapshot(c, ts):
    """상품별 최고 순위 (같은 상품이 남녀 랭킹에 함께 오르면 높은 쪽)."""
    out = {}
    for name, ent, rank, meta in c.execute("""select keyword_raw, entity, metric_value, metadata from signal_raw
            where channel='commerce_rank' and metric_type='rank' and observed_at=?""", (ts,)):
        item = ent.split("@")[0]
        m = json.loads(meta)
        if item not in out or rank < out[item]["rank"]:
            out[item] = {"name": name, "rank": rank, "brand": m.get("brand_kor") or m.get("brand_eng"),
                         "list": m.get("ranking_category_name"), "price": m.get("sale_price"),
                         "sale": m.get("sale_percent"), "sold_out": m.get("sold_out")}
    return out


def nearest_on_or_before(runs, day):
    days = [d for d in runs if d <= day.isoformat()]
    return runs[max(days)]


def commerce_attributes(c, runs):
    attrs, colors, _ = load_dictionary()
    last_day = date.fromisoformat(max(runs))
    now_ts = runs[max(runs)]
    prev_ts = nearest_on_or_before(runs, last_day - timedelta(days=7))
    now, prev = rank_snapshot(c, now_ts), rank_snapshot(c, prev_ts)

    def by_attr(snap):
        out = defaultdict(list)
        for item, v in snap.items():
            for h in extract(v["name"], attrs, colors):
                out[h["canonical"]].append(item)
        return out

    cur, old = by_attr(now), by_attr(prev)
    rows = []
    for a, items in cur.items():
        moves = [prev[i]["rank"] - now[i]["rank"] for i in items if i in prev]
        products = sorted(({"id": i, **now[i], "prev_rank": prev.get(i, {}).get("rank")} for i in items),
                          key=lambda x: x["rank"])
        rows.append({"attr": a, "count_now": len(items), "count_prev": len(old.get(a, [])),
                     "new_entries": sum(i not in prev for i in items),
                     "avg_move": round(sum(moves) / len(moves), 1) if moves else None,
                     "products": products[:8]})
    rows.sort(key=lambda r: r["count_now"] - r["count_prev"], reverse=True)
    return {"snapshot_now": now_ts, "snapshot_prev": prev_ts, "attributes": rows[:25]}


def gtrends(c):
    def series(kw, geo):
        return c.execute("""select observed_at, metric_value from signal_raw where channel='gtrends'
                            and keyword_raw=? and entity=? order by observed_at""", (kw, f"geo={geo}")).fetchall()

    out = {}
    for a in GT_ATTRS:
        kr = series(a, "KR")
        if len(kr) < 8:
            continue
        last_month = kr[-1][0][5:7]
        last_year = str(int(kr[-1][0][:4]) - 1)
        yoy = [v for d, v in kr if d[:4] == last_year and d[5:7] == last_month]
        out[a] = {"last_date": kr[-1][0],
                  "kr_4w": round(sum(v for _, v in kr[-4:]) / 4, 1),
                  "kr_prev4w": round(sum(v for _, v in kr[-8:-4]) / 4, 1),
                  "kr_yoy_same_month": round(sum(yoy) / len(yoy), 1) if yoy else None,
                  "kr_26w": [v for _, v in kr[-26:]],
                  "us_26w": [v for _, v in series(a, "US")[-26:]],
                  "dates_26w": [d for d, _ in kr[-26:]]}
    return out


def persistence_track(c, runs):
    """2주 전 -> 1주 전 10계단 이상 상승, 지금 상승분 절반 이상 유지했는지. 순위는 (상품, 랭킹 목록) 단위."""
    last_day = date.fromisoformat(max(runs))

    def snap(day):
        ts = nearest_on_or_before(runs, day)
        return {tuple((ent.split("@") + [""])[:2]): (rank, name) for name, ent, rank in c.execute(
            """select keyword_raw, entity, metric_value from signal_raw
               where channel='commerce_rank' and metric_type='rank' and observed_at=?""", (ts,))}

    a, b, d = (snap(last_day - timedelta(days=n)) for n in (14, 7, 0))
    rose = [(k, a[k][0], b[k][0]) for k in b
            if k in a and a[k][0] - b[k][0] >= MIN_RISE]
    recs = []
    for k, r0, r1 in rose:
        r2 = d.get(k, (None,))[0]
        held = r2 is not None and (r0 - r2) >= (r0 - r1) * KEEP_RATIO
        recs.append({"name": b[k][1], "r0": r0, "r1": r1, "r2": r2, "held": held})
    return {"rose": len(rose), "held": sum(r["held"] for r in recs), "examples": recs[:12]}


def base_rate_29cm():
    """커머스 벤치마크의 기저율. 봉인 파일에서 읽는다.

    손으로 적어 두면 벤치마크를 다시 만들 때 시안 쪽만 옛 숫자로 남는다.
    """
    digest = ROOT / "benchmark" / "labels.digest.txt"
    if not digest.exists():
        print(f"경고. {digest} 가 없어 기저율을 넣지 못했다. "
              f"./scripts/build_all_benchmarks.sh 를 먼저 돌려라")
        return None
    for line in digest.read_text(encoding="utf-8").splitlines():
        if line.startswith("base"):
            return round(float(line.split()[1]), 3)
    return None


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    out = Path(argv[0]) if argv else OUT
    c = sqlite3.connect(DB)
    runs = daily_runs(c)
    data = {
        "_note": f"{date.today()} data/signals.sqlite 에서 추출한 실제 값. commerce=29CM 상의 랭킹 TOP100, "
                 "gtrends=구글 트렌드 주간 지수(0~100, 요청 내 상대값). gtrends 의 0.0 은 결측으로 취급.",
        "commerce": commerce_attributes(c, runs),
        "gtrends": gtrends(c),
        "persistence_track": persistence_track(c, runs),
        "benchmark_base_rate": {"29cm_7d": base_rate_29cm()},
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    t = data["persistence_track"]
    print(f"{out}  속성 {len(data['commerce']['attributes'])}개, "
          f"검색 {len(data['gtrends'])}개, 지속 {t['held']}/{t['rose']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
