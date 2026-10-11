"""一次性脚本：看融合/重排权重在"脏集"上的敏感度曲线。

用 W_BODY / W_NAMEHIT / W_RUNNABLE 各扫一条曲线，判断联合坐标下降给出的
最优值是**真的在山顶**还是**顶到了网格边界**。边界值通常是过拟合的信号。
这个脚本不进 run.sh，只是第 5 轮调参时用一次。
"""

from __future__ import annotations

import sys

from mansea import engine as E, rerank as R
from mansea.engine import Engine
from mansea.tune import score_on, RERANK_TRAIN
from mansea.evalq import LABELS_HELD6

FUSION = dict(W_BODY=2.6, W_HEAD=0.4, W_NAME=0.8, W_CONCEPT=0.8, W_INTENT=1.6, W_SEC=0.0)
RERANK = dict(W_RUNNABLE=1.0, W_SHAPE=0.3, W_NOLIB=0.0, W_NODAEMON=0.0, W_NAMEHIT=0.2, W_COV=0.0)

for k, v in FUSION.items():
    setattr(E, k, v)
for k, v in RERANK.items():
    setattr(R, k, v)

eng = Engine()


def scan(title: str, mod, key: str, values, reset_to: float) -> None:
    print(f"=== {title} ===")
    for v in values:
        setattr(mod, key, v)
        p1, p5, m = score_on(eng, RERANK_TRAIN)
        b1, b5, bm = score_on(eng, LABELS_HELD6)
        print(
            f"  {key}={v:<5} 脏集 MRR {m:.4f} P@1 {p1:.3f} P@5 {p5:.3f}"
            f"   |  HELD6 MRR {bm:.3f} P@1 {b1:.3f} P@5 {b5:.3f}"
        )
    setattr(mod, key, reset_to)
    print()
    sys.stdout.flush()


scan("W_BODY", E, "W_BODY", [0.8, 1.2, 1.6, 2.0, 2.6, 3.2], 2.6)
scan("W_HEAD", E, "W_HEAD", [0.4, 0.8, 1.2, 1.6, 2.0], 0.4)
scan("W_NAMEHIT", R, "W_NAMEHIT", [0.0, 0.2, 0.6, 1.2, 2.0, 3.0], 0.2)
scan("W_RUNNABLE", R, "W_RUNNABLE", [0.0, 0.5, 1.0, 1.5, 2.0], 1.0)
scan("W_SHAPE", R, "W_SHAPE", [0.0, 0.15, 0.3, 0.6, 1.0], 0.3)
