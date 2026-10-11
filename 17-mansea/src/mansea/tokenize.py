"""中英文混合分词器（零依赖）。

英文/数字：按 [a-z0-9] 连续段切词，同时把 snake_case / kebab-case / 点分
          形式再拆一层（例如 `netstat`、`x86_64`、`--color=when`）。
中文：按连续汉字串切分，输出 单字 + 二元组（bigram），
      这是没有词典时性价比最高的中文检索方案。
"""

from __future__ import annotations

import re
from collections import Counter

CJK = r"\u4e00-\u9fff\u3400-\u4dbf"

# 先抓出"词素"：英文数字串、单独汉字序列
_WORD_RE = re.compile(rf"[a-z0-9]+(?:[._\-+/][a-z0-9]+)*|[{CJK}]+")

# 英文里常见的无信息量词
STOPWORDS = frozenset(
    """
    a an and are as at be by for from has have if in into is it its of on or
    that the this to was were will with you your s t ve re ll d m
    """.split()
)


def _split_compound(tok: str):
    """把一个复合 token 再拆成更细的子词，用于提高召回。

    `x86_64` -> ['x86_64', 'x86', '64']
    `netstat`-> ['netstat']            （纯字母串不拆）
    """
    out = [tok]
    if len(tok) < 3:
        return out
    parts = [p for p in re.split(r"[._\-+/]", tok) if p]
    if len(parts) > 1:
        out.extend(p for p in parts if len(p) > 1)
    return out


def tokenize(text: str, *, drop_stopwords: bool = True) -> Counter:
    """把一段文本切成词频表。"""
    if not text:
        return Counter()
    low = text.lower()
    counts: Counter = Counter()

    for raw in _WORD_RE.findall(low):
        if "\u4e00" <= raw[0] <= "\u9fff" or "\u3400" <= raw[0] <= "\u4dbf":
            # 中文串：单字 + 二元组
            for ch in raw:
                counts[ch] += 1
            for i in range(len(raw) - 1):
                counts[raw[i : i + 2]] += 1
            continue
        for sub in _split_compound(raw):
            if len(sub) < 2:
                continue
            if drop_stopwords and sub in STOPWORDS:
                continue
            counts[sub] += 1

    return counts


def query_terms(text: str) -> list[str]:
    """查询串 -> 词列表（保留重复用于短语加权，但去重后返回）。"""
    c = tokenize(text)
    return list(c.keys())


if __name__ == "__main__":
    import sys

    print(dict(tokenize(" ".join(sys.argv[1:]) or "tar -xzvf 解压文件 how to compress a folder")))
