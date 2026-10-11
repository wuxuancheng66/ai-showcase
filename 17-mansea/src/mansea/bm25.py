"""BM25 检索核心（零依赖，可持久化成单个 JSON）。

倒排表： token -> [[doc_id, tf], ...]
额外保存：doc_len[]、avgdl、df[]
"""

from __future__ import annotations

import json
import math
from collections import Counter
from pathlib import Path

from .tokenize import tokenize

K1 = 1.5
B = 0.75


class BM25:
    def __init__(self) -> None:
        self.docs: list[dict] = []          # 文档元数据（不含正文）
        self.doc_len: list[int] = []
        self.avgdl: float = 0.0
        self.postings: dict[str, list[list[int]]] = {}
        self.df: dict[str, int] = {}

    # ---------- 建库 ----------
    def add(self, meta: dict, text: str) -> int:
        """加入一篇文档，返回 doc_id。meta 里不要放正文。"""
        doc_id = len(self.docs)
        self.docs.append(meta)
        tf = tokenize(text)
        n = sum(tf.values())
        self.doc_len.append(n)
        for tok, c in tf.items():
            self.postings.setdefault(tok, []).append([doc_id, c])
        return doc_id

    def add_terms(self, meta: dict, tf) -> int:
        """直接喂一个词频表（概念层用：中文 bigram 不走默认分词器）。"""
        doc_id = len(self.docs)
        self.docs.append(meta)
        n = 0
        for tok, c in tf.items():
            self.postings.setdefault(tok, []).append([doc_id, int(c) if c > 1 else 1])
            n += c
        self.doc_len.append(int(n))
        return doc_id

    def finalize(self) -> None:
        self.df = {t: len(p) for t, p in self.postings.items()}
        self.avgdl = (sum(self.doc_len) / len(self.doc_len)) if self.doc_len else 0.0

    # ---------- 检索 ----------
    def idf(self, tok: str) -> float:
        n = len(self.docs)
        d = self.df.get(tok, 0)
        return math.log(1 + (n - d + 0.5) / (d + 0.5))

    def score(self, qtf: Counter, *, name_boost: dict[int, float] | None = None) -> list[tuple[float, int]]:
        """对一次查询的 tf 表打分，返回 [(score, doc_id)] 降序。"""
        if not qtf or not self.docs:
            return []
        acc: dict[int, float] = {}
        for tok, qc in qtf.items():
            plist = self.postings.get(tok)
            if not plist:
                continue
            idf = self.idf(tok)
            for doc_id, tf in plist:
                dl = self.doc_len[doc_id]
                denom = tf + K1 * (1 - B + B * dl / (self.avgdl or 1.0))
                acc[doc_id] = acc.get(doc_id, 0.0) + idf * (tf * (K1 + 1)) / denom * (1 + math.log(qc))
        if name_boost:
            for doc_id, b in name_boost.items():
                if doc_id in acc:
                    acc[doc_id] *= 1.0 + b
        return sorted(((s, d) for d, s in acc.items()), reverse=True)

    def score_stream(self, weights: dict[str, float], topn: int = 300) -> list[tuple[float, int]]:
        """加权词表 -> [(score, doc_id)] 降序。

        与 `score()` 的区别：查询侧权重由调用方给定（中文词典的权重直接透传），
        不再用 (1+log(qtf)) 隐式加权。这是第 2 轮引入的核心改动。
        """
        if not weights or not self.docs:
            return []
        avgdl = self.avgdl or 1.0
        acc: dict[int, float] = {}
        for tok, qw in weights.items():
            plist = self.postings.get(tok)
            if not plist:
                continue
            idf = self.idf(tok)
            base = qw * idf * (K1 + 1)
            for doc_id, tf in plist:
                denom = tf + K1 * (1 - B + B * self.doc_len[doc_id] / avgdl)
                acc[doc_id] = acc.get(doc_id, 0.0) + base * tf / denom
        return sorted(((s, d) for d, s in acc.items()), reverse=True)[:topn]

    def _boost(self, qset: set[str], name_boost: float) -> dict[int, float]:
        """文档名/别名命中查询词时的额外加权。

        man 手册场景下 `ls` 应该比一篇正文里顺带提到 ls 的页面排得更前。
        """
        boost: dict[int, float] = {}
        if not name_boost or not qset:
            return boost
        for i, meta in enumerate(self.docs):
            keys = meta.get("_keys") or ""
            if not keys:
                continue
            kt = set(tokenize(keys, drop_stopwords=False))
            hit = len(qset & kt)
            if hit:
                boost[i] = name_boost * hit / max(len(qset), 1)
        return boost

    def search(self, query: str, k: int = 10, *, soft: str = "", soft_w: float = 0.75,
               name_boost: float = 1.2):
        """入口：查询串 -> [(score, doc_id)] 降序。

        soft 是"软查询"—— 由 zh.py 从中文扩展出来的英文词，权重低于原始查询。
        """
        p = tokenize(query)
        s = tokenize(soft) if soft else Counter()
        if not p and not s:
            return []
        boost = self._boost(set(p) | set(s), name_boost)

        acc: dict[int, float] = {}
        for sc, d in self.score(p, name_boost=boost):
            acc[d] = acc.get(d, 0.0) + sc
        if s:
            for sc, d in self.score(s, name_boost=boost):
                acc[d] = acc.get(d, 0.0) + soft_w * sc
        return sorted(((v, kk) for kk, v in acc.items()), reverse=True)[:k]

    # ---------- 持久化 ----------
    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "docs": self.docs,
            "doc_len": self.doc_len,
            "avgdl": self.avgdl,
            "postings": self.postings,
            "df": self.df,
        }
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> "BM25":
        obj = cls()
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        obj.docs = payload["docs"]
        obj.doc_len = payload["doc_len"]
        obj.avgdl = payload["avgdl"]
        obj.postings = payload["postings"]
        obj.df = payload["df"]
        return obj

    def __len__(self) -> int:
        return len(self.docs)
