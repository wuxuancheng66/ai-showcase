"""SEE ALSO 关系图：命中一个命令，顺带把手册自己说"相关"的命令带上来。

为什么要这一层：
词典和 BM25 都是在比"字面像不像"，但 man 手册里有一张**现成的知识图谱** ——
每页末尾的 SEE ALSO 是写手册的人手工标的相关命令。
`ls(1)` 的 SEE ALSO 里写着 `chmod(1) chown(1) stat(1)`，这层关系
用任何字面相似度都推不出来。

主要抬 P@5 / P@10：用户搜"查看文件属性"，就算 top1 不是 stat，
只要 stat 出现在种子命令的邻居里，也能被拉进前五。
"""

from __future__ import annotations

import re
from collections import Counter

# `csh(1), sh(1), curs_terminfo(3X), ttys(5)` —— 渲染后的 man 页里长这样
_SEE = re.compile(r"\b([A-Za-z0-9_][A-Za-z0-9_.+-]{0,30})\(([0-9n][A-Za-z]{0,3})\)")

# SEE ALSO 段之后最多扫这么多字符，再往后就是别的段落了
_WINDOW = 700
# 单篇最多保留多少个邻居。太多会把整张图糊成一片，检索就没意义了。
MAX_NEIGHBORS = 8


def see_also_names(text: str) -> list[tuple[str, str]]:
    """从一篇文档正文里抠出 SEE ALSO 引用的 (命令名, 章节)。"""
    i = (text or "").find("SEE ALSO")
    if i < 0:
        return []
    seg = text[i : i + _WINDOW]
    out: list[tuple[str, str]] = []
    for m in _SEE.finditer(seg):
        out.append((m.group(1).lower(), m.group(2)))
    return out


def build_related(docs: list[dict], cmd2doc: dict[str, int]) -> dict[int, list[tuple[int, float]]]:
    """{doc_id: [(邻居 doc_id, 权重), ...]}

    权重 = 该邻居在 SEE ALSO 里出现的相对频次，归一化到 (0,1]。
    cmd2doc 用建索引时那份（含别名/文件名三级回退），
    否则 `gunzip(1)` 这种只有别名的引用会全部落空。
    """
    graph: dict[int, list[tuple[int, float]]] = {}
    for i, d in enumerate(docs):
        cnt: Counter[int] = Counter()
        for nm, _sec in see_also_names(d.get("text", "")):
            j = cmd2doc.get(nm)
            # 别把自己算成邻居
            if j is not None and j != i:
                cnt[j] += 1
        if not cnt:
            continue
        top = cnt.most_common(MAX_NEIGHBORS)
        hi = top[0][1] or 1
        graph[i] = [(j, round(c / hi, 3)) for j, c in top]
    return graph
