"""融合权重搜索 + 各路打分标定。

用法：
    python3 -m mansea.tune            # 网格搜索（只在调参集+留出集上搜）
    python3 -m mansea.tune --calibrate  # 只打印各路参考分（REF_* 的依据）

纪律：**新题集（LABELS_HELD2）不参与搜索**，只用来最后报一次读数。
拿它调参就等于把它也变成调参集，那个数字立刻失效。
"""

from __future__ import annotations

import argparse
import itertools
import statistics as st

from . import engine as engine_mod
from . import rerank as rerank_mod
from .concept import cn_terms
from .engine import Engine
from .evalq import (
    LABELS,
    LABELS_HELD,
    LABELS_HELD2,
    LABELS_HELD3,
    LABELS_HELD4,
    LABELS_HELD5,
    LABELS_HELD6,
)

TRAIN = LABELS + LABELS_HELD

# 重排权重的调参集：**故意用已经污染的前六组**。
# 理由见 PLAN.md —— HELD7 是本轮唯一的干净读数，只能跑两次（基线 / 验收）。
# 拿脏集调出来的数必然偏乐观，这正是最后要看 HELD7 的原因。
RERANK_TRAIN = (
    LABELS + LABELS_HELD + LABELS_HELD2
    + LABELS_HELD3 + LABELS_HELD4 + LABELS_HELD5 + LABELS_HELD6
)


def _names(res) -> list[str]:
    return [r["name"].lower() for r in res]


def score_on(eng: Engine, labels, k: int = 10) -> tuple[float, float, float]:
    p1 = p5 = mrr = 0.0
    for q, gold in labels:
        names = _names(eng.search(q, k))
        hit = next((i for i, nm in enumerate(names) if nm in gold), None)
        if hit is not None:
            mrr += 1.0 / (hit + 1)
            p1 += hit == 0
            p5 += hit < 5
    n = len(labels)
    return p1 / n, p5 / n, mrr / n


def calibrate(eng: Engine, queries: list[str]) -> None:
    tops: dict[str, list[float]] = {"body": [], "head": [], "name": [], "concept": []}
    for q in queries:
        tw = eng.weights_of(q)
        streams = {
            "body": dict((d, s) for s, d in eng.bm.score_stream(tw, topn=400)),
            "head": dict((d, s) for s, d in eng.head.score_stream(tw, topn=400)),
            "name": eng._name_scores(tw),
            "concept": dict((d, s) for s, d in eng.concept.score_stream(cn_terms(q), topn=400))
            if cn_terms(q)
            else {},
        }
        for k, d in streams.items():
            m = max(d.values(), default=0.0)
            if m > 0:
                tops[k].append(m)
    print("各路「本轮最高分」分布（REF_* 取中位数）：")
    for k, v in tops.items():
        v.sort()
        print(
            f"  {k:8} n={len(v):3}  p10={v[int(.1 * len(v))]:8.3f}  "
            f"median={st.median(v):8.3f}  p90={v[int(.9 * len(v)) - 1]:8.3f}  max={v[-1]:8.3f}"
        )


RERANK_KEYS = ("W_RUNNABLE", "W_SHAPE", "W_NOLIB", "W_NODAEMON", "W_NAMEHIT", "W_COV")


def tune_rerank(eng: Engine, rounds: int = 2) -> dict[str, float]:
    """坐标下降：每个权重轮流扫一遍，留让 MRR 最高的值。

    用 MRR 而不是 P@1 当目标 —— P@1 是个阶跃函数，权重微调时它不动，
    梯度全丢了；MRR 能反映"第 3 名提到第 2 名"这种真实进步。
    """
    cur = {k: getattr(rerank_mod, k) for k in RERANK_KEYS}
    grid = [0.0, 0.15, 0.3, 0.45, 0.6, 0.9, 1.2, 1.6]
    best_mrr = score_on(eng, RERANK_TRAIN)[2]
    print(f"起点  MRR {best_mrr:.4f}")
    for rd in range(rounds):
        for k in RERANK_KEYS:
            best_v = cur[k]
            for v in grid:
                cur[k] = v
                setattr(rerank_mod, k, v)
                mrr = score_on(eng, RERANK_TRAIN)[2]
                if mrr > best_mrr + 1e-9:
                    best_mrr, best_v = mrr, v
            cur[k] = best_v
            setattr(rerank_mod, k, best_v)
            print(f"  轮{rd} {k:<12} = {best_v:<5}  MRR {best_mrr:.4f}")
    p1, p5, mrr = score_on(eng, RERANK_TRAIN)
    print(f"调参集（前六组，已污染）  P@1 {p1:.3f} · P@5 {p5:.3f} · MRR {mrr:.3f}")
    print("权重： " + "  ".join(f"{k}={v}" for k, v in cur.items()))
    return cur


FUSION_KEYS = ("W_BODY", "W_HEAD", "W_NAME", "W_CONCEPT", "W_INTENT", "W_SEC")


def tune_joint(eng: Engine, rounds: int = 3) -> None:
    """融合权重 + 重排权重一起做坐标下降。

    为什么现在要回头动融合权重：重排能修的是"噪声页占了第一"，
    修不了"泛泛相关的命令占了第一"（`wc` 压 `uniq`、`cat` 压 `stat`）。
    那类错误是正文 BM25 的锅 —— 长描述里什么词都有，泛词命中就把分拉上去了。
    所以让 head / name 这两路（只看 NAME 行和命令名）说话大声一点，才是正解。
    """
    keys = list(FUSION_KEYS) + list(RERANK_KEYS)
    mods = {k: engine_mod for k in FUSION_KEYS}
    mods.update({k: rerank_mod for k in RERANK_KEYS})
    cur = {k: getattr(mods[k], k) for k in keys}
    grids = {
        **{k: [0.4, 0.8, 1.2, 1.6, 2.0, 2.6] for k in
           ("W_BODY", "W_HEAD", "W_NAME", "W_CONCEPT", "W_INTENT")},
        "W_SEC": [0.0, 0.05, 0.1, 0.2],
        **{k: [0.0, 0.2, 0.4, 0.7, 1.0, 1.5, 2.0] for k in RERANK_KEYS},
    }
    best = score_on(eng, RERANK_TRAIN)[2]
    print(f"起点 MRR {best:.4f}  " + "  ".join(f"{k}={cur[k]}" for k in keys))
    for rd in range(rounds):
        moved = False
        for k in keys:
            bv = cur[k]
            for v in grids[k]:
                if v == cur[k]:
                    continue
                setattr(mods[k], k, v)
                m = score_on(eng, RERANK_TRAIN)[2]
                if m > best + 1e-9:
                    best, bv, moved = m, v, True
            setattr(mods[k], k, bv)
            cur[k] = bv
        p1, p5, mrr = score_on(eng, RERANK_TRAIN)
        print(f"  轮{rd}  MRR {mrr:.4f}  P@1 {p1:.3f}  P@5 {p5:.3f}")
        if not moved:
            break
    print("最终权重：")
    for k in keys:
        print(f"  {mods[k].__name__.split('.')[-1]}.{k} = {cur[k]}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--calibrate", action="store_true")
    ap.add_argument("--rerank", action="store_true", help="坐标下降搜第二阶段重排权重")
    ap.add_argument("--joint", action="store_true", help="融合 + 重排联合坐标下降")
    args = ap.parse_args(argv)

    eng = Engine()
    if args.rerank:
        tune_rerank(eng)
        return 0
    if args.joint:
        tune_joint(eng)
        return 0
    qs = [q for q, _ in LABELS + LABELS_HELD + LABELS_HELD2]
    if args.calibrate:
        calibrate(eng, qs)
        return 0

    grid = {
        "W_BODY": [1.0, 1.3, 1.6],
        "W_HEAD": [0.8, 1.3, 1.8],
        "W_NAME": [0.8, 1.2, 1.6, 2.0],
        "W_CONCEPT": [1.0, 1.5, 2.0, 2.5],
        "W_SEC": [0.1, 0.2, 0.3],
    }
    keys = list(grid)
    best = (((-1.0, -1.0), None, None))
    for combo in itertools.product(*(grid[k] for k in keys)):
        for k, v in zip(keys, combo):
            setattr(engine_mod, k, v)
        p1, p5, mrr = score_on(eng, TRAIN)
        # 先看 MRR，再看 P@1 —— MRR 对"整体排得靠前"更敏感
        key = (round(mrr, 6), round(p1, 6))
        if key > best[0]:
            best = (key, combo, (p1, p5, mrr))

    print(f"搜索了 {len(list(itertools.product(*(grid[k] for k in keys))))} 组权重")
    print("最优（在调参集+留出集上）：")
    for k, v in zip(keys, best[1]):
        print(f"  {k} = {v}")
    p1, p5, mrr = best[2]
    print(f"  训练集  P@1 {p1:.3f} · P@5 {p5:.3f} · MRR {mrr:.3f}")

    for k, v in zip(keys, best[1]):
        setattr(engine_mod, k, v)
    f1, f5, fm = score_on(eng, LABELS_HELD2)
    print(f"  新题集  P@1 {f1:.3f} · P@5 {f5:.3f} · MRR {fm:.3f}   ← 未参与搜索")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
