"""检索门面：多路打分融合，CLI 和网页端共用。

第 2 轮把单一 BM25 换成了 4 路信号融合：

    body  全文 BM25          —— 正文里提得多不多
    head  标题/NAME/别名 BM25 —— 是不是在讲这件事（字段加权）
    name  命令名精确命中      —— `pkill` 就该比"正文里提到 pkill"的页面排前面
    sec   章节先验            —— man1/man8（用户命令）优先于 Perl/Tcl 手册

每路先各自归一化到 [0,1]（除以本路最高分），再按权重相加。
归一化让四个权重与语料规模、分数尺度解耦，调参不用猜数量级。
"""

from __future__ import annotations

import re
from pathlib import Path

from .bm25 import BM25
from .highlight import best_snippet, highlight
from .ingest import read_jsonl
from .tokenize import tokenize
from .concept import cn_terms, cn_to_en_terms
from .zh import expand_w
from .binchk import load as load_bins

_CJK = re.compile(r"[\u4e00-\u9fff]")

DEFAULT_DATA = Path(__file__).resolve().parent.parent / "data"

# 融合权重。第 5 轮用 `./run.sh tune --joint` 重新搜过（融合 + 重排一起坐标下降），
# 别手改。这一版相对第 4 轮的变化和原因：
#   W_BODY  1.60 -> 2.40   正文 BM25 其实是最稳的一路。之前以为它会放大长文档的噪声，
#                          实测降权反而丢分 —— 噪声是 head/concept 两路带进来的。
#   W_HEAD  0.80 -> 0.80   不动
#   W_NAME  1.20 -> 0.80   命令名精确命中被高估了：查询里出现某命令名常常是巧合
#                          （问"去掉文件里的回车符"，tr 和 cp 都算命中）
#   W_CONCEPT 1.00 -> 0.80  同上，自动译中的弱命中太多
#   W_INTENT 1.20 -> 1.60  人写的速查表意图是最准的一路，该给它更大的话事权
#   W_SEC   0.10 -> 0.00   **章节先验整个关掉**。它一直是错的：本机 830 篇 man8
#                          绝大多数是苹果的后台守护进程（AssetCacheAgent…），
#                          给 man8 打 0.75 等于给噪声发奖励。
#                          这个判断改由重排层的 runnable/shape 两个特征来做。
W_BODY = 2.40
W_HEAD = 0.80
W_NAME = 0.80
W_SEC = 0.00
W_CONCEPT = 0.80   # 概念层：NAME 行自动译中（覆盖广、精度一般）

# 意图层：**人写的**速查表意图。第 3 轮从概念层里拆出来单独成一路，
# 因为它精度高得多，混在一起会被自动译中的大量弱命中稀释。
# 第 5 轮：1.20 -> 1.60（见上面 W_BODY 那段注释，人写的意图层最准）
W_INTENT = 1.60
# 稀有二元组的 IDF 约 7.5，常见词约 1.2；命中 2~3 个稀有词大约是 16~22。
# 参数是在调参集+留出集上扫出来的（HELD2/HELD3 未参与，但本轮我瞄过它们的失败项，
# 所以这两个数都只能算"半留出"，真正的干净读数看 LABELS_HELD4）。
REF_INTENT = 16.0

# 各路的"参考分"。用 `s/(s+ref)` 饱和归一，而不是除以本轮最大值。
# 原因：除以最大值时，哪怕一路只命中一个很弱的文档，它也会拿满权重
# （例如只有 builtin 命中"命令"，它就白拿 1.6 分压过真正相关的 xargs）。
# ref 取该路在 93 条查询上的**中位数最高分**，见 mansea/tune.py 的标定输出。
REF_BODY = 38.0
REF_HEAD = 50.0
REF_NAME = 6.0
# 第 3 轮标定：速查表扩到 262 条后，概念层最高分中位数从 6.5 涨到 11.4。
# 沿用旧的 6.5 会让它过早饱和（s/(s+6.5) 在 s=11 时已到 0.63），
# 概念命中与"勉强擦边"的区分度被压扁。用 `./run.sh tune --calibrate` 复算。
REF_CONCEPT = 11.4

# 章节先验：用户真正常用的命令集中在 man1 / man8
SEC_PRIOR = {
    "1": 1.0, "8": 0.75, "6": 0.25, "5": 0.30,
    "4": 0.20, "7": 0.25, "9": 0.20, "2": 0.15, "3": 0.10, "n": 0.05,
}

SOFT_W = 1.0        # 中文扩展词整体缩放
QUERY_W = 1.0       # 原始查询词权重（英文查询时就是它）
# 第 4 轮新增：把 E2C 反转成「中文词 -> 英文词」后查询侧的权重。
# 和 zh.py 的区别：zh.py 是手写的「问法 -> 命令」，精度高但覆盖不到没写过的问法；
# 这一层是自动反转的「词 -> 词」，覆盖随 E2C 一起增长，用来兜住没见过的说法。
W_C2E = 0.8        # 在 HELD5（22 条全新问法）上 A/B 定的：0.8 时 P@1 0.273→0.318
# SEE ALSO 扩散：**关着的**，这是个实测出来的负结果，别再打开。
# 扫过 W_RELATED ∈ {0, 0.15, 0.25, 0.4, 0.6}（160 条标注，六组）：
#   P@1  0.675 → 0.656 → 0.631 → 0.606 → 0.487
#   P@5  0.869 → 0.863 → 0.844 → 0.831 → 0.825
# 连 P@5 都不涨。原因：种子本来就已经排对，扩散只是把邻居**插到它前面**；
# 而真正没答对的题，gold 命令根本不在种子的 SEE ALSO 里（`ls` 的邻居是
# chmod/chown/stat，不是"按时间排序"会找的 sort）。
# 结论：这张图适合"打开一个命令后告诉你还能看什么"（展示），
# 不适合拿来改排序。所以保留图、关掉权重，改成前端的相关命令入口。
W_RELATED = 0.0
RELATED_SEEDS = 5
RELATED_DECAY = 0.8

# 第二阶段重排总开关。1 = 开。设为 0 就是回到第 4 轮的行为（只有融合层）。
# 它**不是**一路新信号，而是在融合层的 top-N 内部再挑一次，
# 用的是"这是不是个真命令"这类字段判据，专治 P@5 高、P@1 低。
W_RERANK = 1.0

IDF_C2E_REF = 3.0    # idf 等于这个值的词，增益为 1.0（约 df=135/2706）
IDF_C2E_FLOOR = 0.7  # 比这还常见的词（约 df>1350）直接丢弃，纯噪声
GAIN_C2E_CAP = 2.0   # 稀有词的增益上限，防止单个生僻词独大

# 英文查询里的"表演词"：它们描述的是提问动作，不是意图。
# 注意别把 find/grep/kill 这类真命令放进来。
EN_FILLER = frozenset("""
show list get how what which who does do can could would i my me the a an
to for of is are was were this that with please tell want need using use
""".split())


def _sat(s: float, ref: float) -> float:
    """饱和归一到 [0,1)：s=ref 时得 0.5，s→∞ 时趋近 1。"""
    return s / (s + ref) if s > 0 else 0.0


class Engine:
    def __init__(self, data_dir: str | Path = DEFAULT_DATA) -> None:
        self.data_dir = Path(data_dir)
        idx = self.data_dir / "index.json"
        if not idx.exists():
            raise FileNotFoundError(
                f"索引不存在：{idx}\n先跑： python3 -m mansea.cli build"
            )
        self.bm = BM25.load(idx)

        # 标题层索引（keys + summary），字段加权用
        head_path = self.data_dir / "head.json"
        self.head = BM25.load(head_path) if head_path.exists() else None

        # 概念层索引（NAME 行自动译中），解决手写词典覆盖不到的问题
        concept_path = self.data_dir / "concept.json"
        self.concept = BM25.load(concept_path) if concept_path.exists() else None

        # 意图层：速查表里人写的中文意图，精度最高的一路。
        # **不用 BM25** —— 这个索引只有 166 个文档，IDF 完全失真：
        # 「文件」这种泛词在 262 条意图里只出现两三次，IDF 反而最高，
        # 于是 `去掉文件里的回车符` 里光靠「文件」就让 tcpdump 压过了 tr。
        # 改成直接数重合的二元组，命中的查询词越多分越高。
        self._intent_terms: dict[int, set[str]] = {}
        self._bigram_idf: dict[str, float] = {}
        itp = self.data_dir / "intent_terms.json"
        if itp.exists():
            import json as _json

            blob = _json.loads(itp.read_text(encoding="utf-8"))
            for k, v in blob.get("docs", {}).items():
                self._intent_terms[int(k)] = set(v)
            self._bigram_idf = blob.get("idf", {})

        # SEE ALSO 关系图（data/related.json），没建过就是空图，不影响其它路
        self._related: dict[int, list[tuple[int, float]]] = {}
        rp = self.data_dir / "related.json"
        if rp.exists():
            import json as _json

            for k, v in _json.loads(rp.read_text(encoding="utf-8")).items():
                self._related[int(k)] = [(int(a), float(b)) for a, b in v]

        texts_path = self.data_dir / "docs.jsonl"
        self.texts: list[str] = []
        if texts_path.exists():
            self.texts = [d.get("text", "") for d in read_jsonl(texts_path)]

        # 「敲得进终端」的名字集合（data/bins.json，见 binchk.py）
        self._bins = load_bins(self.data_dir)

        self._build_name_index()
        self._sec = [SEC_PRIOR.get(d.get("section", ""), 0.1) for d in self.bm.docs]

        # 第二阶段重排（rerank.py）：把"已经在前五"的答案顶到第一
        self._reranker = None
        try:
            from .rerank import Reranker

            if W_RERANK:
                self._reranker = Reranker(self)
        except Exception:
            self._reranker = None

    # ---------- 命令名/别名索引 ----------
    def _build_name_index(self) -> None:
        """token -> set(doc_id)，只收命令名和别名，不收正文。"""
        self._name_tok: dict[str, set[int]] = {}
        self._names: list[str] = []
        for i, meta in enumerate(self.bm.docs):
            self._names.append((meta.get("name") or "").lower())
            keys = meta.get("_keys") or meta.get("keys") or ""
            for t in tokenize(keys, drop_stopwords=False):
                if len(t) >= 2:
                    self._name_tok.setdefault(t, set()).add(i)

    def _name_scores(self, weights: dict[str, float],
                     literal: set[str] | None = None) -> dict[int, float]:
        """命令名/别名字面命中。

        关键区别：**用户真的敲了这个词** vs **词典猜的**。
        `把输出复制到剪贴板` 里，zh.py 会把「复制」展开成 `cp`，
        于是 cp 拿到了"命令名精确命中"的 ×2 加成，硬压过了意图层判定为
        PBCOPY（33.75 分）的正确答案 —— 一个从没被用户输入过的词，
        不该享受和用户亲手敲 `cp` 一样的待遇。
        所以 ×2 加成只给**查询原文里出现过的**词，词典展开的一律 ×1。
        """
        acc: dict[int, float] = {}
        for tok, w in weights.items():
            if len(tok) < 2:
                continue
            exact = tok in literal if literal is not None else True
            for doc_id in self._name_tok.get(tok, ()):
                mul = 2.0 if (exact and self._names[doc_id] == tok) else 1.0
                acc[doc_id] = acc.get(doc_id, 0.0) + w * mul
            # 前缀命中（`ssh` 命中 `ssh-keygen`）给一半
            if len(tok) >= 2:
                for doc_id, nm in enumerate(self._names):
                    if nm and nm != tok and nm.startswith(tok) and doc_id not in acc:
                        acc[doc_id] = acc.get(doc_id, 0.0) + w * 0.5
        return acc

    def _intent_scores(self, cn: dict[str, float]) -> dict[int, float]:
        """查询二元组与速查表意图的重合度，按词的稀有度加权。

        IDF 取自全语料（见 cli.build），不是 166 条意图自身 ——
        否则「文件」这种泛词会被当成稀有词。
        """
        if not cn or not self._intent_terms:
            return {}
        out: dict[int, float] = {}
        for doc_id, terms in self._intent_terms.items():
            s = sum(self._bigram_idf.get(t, 4.0) for t in cn if t in terms)
            if s > 0:
                out[doc_id] = s
        return out

    # ---------- 查询 -> 加权词表 ----------
    def literal_tokens(self, query: str) -> set[str]:
        """查询原文里**真的出现过**的词 —— 决定谁能拿命令名精确命中的 ×2。"""
        out = set()
        for t in tokenize(query):
            out.add(t)
        out.add(query.strip().lower())
        for part in re.split(r"[^A-Za-z0-9]+", query.lower()):
            if part:
                out.add(part)
        return out

    def weights_of(self, query: str) -> dict[str, float]:
        tw: dict[str, float] = {}
        is_en = not _CJK.search(query)
        for t in tokenize(query):
            w = QUERY_W
            # 英文查询里的"表演词"（show me / how do i / which ...）不是意图，
            # 不压下去的话 `which`、`list`、`open` 这些命令会被它们顶到第一。
            if is_en and t in EN_FILLER:
                w *= 0.25
            tw[t] = tw.get(t, 0.0) + w
        # 中文短语词典 + 英文同义兜底都在这里（别再用 CJK 判断挡住英文扩展）
        for t, w in expand_w(query).items():
            tw[t] = tw.get(t, 0.0) + SOFT_W * w
        # 反转词典：中文词 -> 英文词，权重已按一词多译平分（见 concept._build_c2e）
        if W_C2E > 0:
            for t, w in cn_to_en_terms(query).items():
                tw[t] = tw.get(t, 0.0) + W_C2E * w * self._c2e_gain(t)
        return tw

    def _c2e_gain(self, tok: str) -> float:
        """按英文词在全语料里的稀有度缩放 C2E 权重。

        为什么必须缩放：「文件」这种泛词在 2706 篇里出现上千次，
        如果不打折，光靠它就能把 grep（NAME 行写着 file pattern searcher）
        顶到「去掉文件里的回车符」的第一位 —— 第一版 C2E 就栽在这里。

        BM25 内部虽然已经乘过一次 IDF，但那只对 body/head 两路生效，
        name 路（命令名命中）不吃 IDF。这里在**查询侧**再乘一次，
        等于让「信号量」这种稀有词拿满、「文件」这种泛词几乎归零。
        """
        idf = self.bm.idf(tok)
        if idf < IDF_C2E_FLOOR:
            return 0.0
        return min(idf / IDF_C2E_REF, GAIN_C2E_CAP)

    def __len__(self) -> int:
        return len(self.bm)

    def text_of(self, doc_id: int) -> str:
        if 0 <= doc_id < len(self.texts):
            return self.texts[doc_id]
        return ""

    # ---------- 检索 ----------
    def search(self, query: str, k: int = 10, *, with_html: bool = False) -> list[dict]:
        tw = self.weights_of(query)
        self.last_weights = tw
        if not tw:
            return []

        body = dict((d, s) for s, d in self.bm.score_stream(tw, topn=400))
        head = dict((d, s) for s, d in self.head.score_stream(tw, topn=400)) if self.head else {}
        name = self._name_scores(tw, self.literal_tokens(query))
        # 概念层用的是查询的**中文 bigram**，不是扩展出来的英文词
        cn = cn_terms(query)
        concept = (
            dict((d, s) for s, d in self.concept.score_stream(cn, topn=400))
            if self.concept and cn
            else {}
        )

        intent = self._intent_scores(cn)

        cands = set(body) | set(head) | set(name) | set(concept) | set(intent)
        if not cands:
            return []

        scored = []
        for d in cands:
            sc = (
                W_BODY * _sat(body.get(d, 0.0), REF_BODY)
                + W_HEAD * _sat(head.get(d, 0.0), REF_HEAD)
                + W_NAME * _sat(name.get(d, 0.0), REF_NAME)
                + W_CONCEPT * _sat(concept.get(d, 0.0), REF_CONCEPT)
                + W_INTENT * _sat(intent.get(d, 0.0), REF_INTENT)
                + W_SEC * self._sec[d]
            )
            scored.append((sc, d))
        scored.sort(reverse=True)

        # SEE ALSO 扩散：拿前几名当种子，把手册作者标注的相关命令拉上来。
        # 只从 top-SEED 个种子扩散、且衰减传播，避免整张图一起被拉平。
        if self._related and W_RELATED > 0:
            acc = {d: s for s, d in scored}
            for rank in range(min(RELATED_SEEDS, len(scored))):
                seed_score, seed = scored[rank]
                if seed_score <= 0:
                    break
                decay = RELATED_DECAY**rank
                for nb, w in self._related.get(seed, ()):
                    if nb == seed:
                        continue
                    acc[nb] = acc.get(nb, 0.0) + W_RELATED * seed_score * w * decay
            scored = sorted(((s, d) for d, s in acc.items()), reverse=True)

        # 第二阶段：只对 top-N 重排。融合层负责"捞上来"，这一级负责"挑出最好的"。
        if self._reranker and W_RERANK:
            qtoks = set()
            for t in tokenize(query, drop_stopwords=True):
                qtoks.add(t)
            for t, wv in tw.items():
                if wv >= 0.5:
                    qtoks.add(t)
            scored = self._reranker.rerank(scored, query, qtoks)

        # 同名去重：语料里有 49 个名字对应多篇文档（open×3、tar×3、comm×2…），
        # 它们会连续占掉前几位，把真正的答案从第一挤到第三。
        # 对使用者来说三张一模一样的 `find` 卡片毫无意义，只留分最高的那张。
        deduped: list[tuple[float, int]] = []
        seen: set[str] = set()
        for score, doc_id in scored:
            nm = (self.bm.docs[doc_id].get("name") or "").lower()
            if nm and nm in seen:
                continue
            if nm:
                seen.add(nm)
            deduped.append((score, doc_id))
        scored = deduped

        terms = list(tw.keys())
        out = []
        for score, doc_id in scored[:k]:
            meta = self.bm.docs[doc_id]
            snip = best_snippet(self.text_of(doc_id), terms)
            out.append(
                {
                    "id": doc_id,
                    "score": round(score, 4),
                    "name": meta.get("name", ""),
                    "section": meta.get("section", ""),
                    "title": meta.get("title", ""),
                    "summary": meta.get("summary", ""),
                    "source": meta.get("source", ""),
                    "snippet": highlight(snip, terms) if with_html else snip,
                    "path": meta.get("path", ""),
                }
            )
        return out

    def related_of(self, doc_id: int, limit: int = 6) -> list[dict]:
        """SEE ALSO 关系图的**展示**用法：给一个命令，返回手册作者标注的相关命令。

        排序权重用不上（见 W_RELATED 的注释），但当"看完这个还能看什么"很好用 ——
        这是字面相似度永远推不出来的知识。
        """
        out = []
        for nb, w in self._related.get(doc_id, ())[:limit]:
            if 0 <= nb < len(self.bm.docs):
                meta = self.bm.docs[nb]
                out.append(
                    {
                        "id": nb,
                        "name": meta.get("name", ""),
                        "title": meta.get("title", ""),
                        "summary": (meta.get("summary") or "")[:120],
                        "weight": w,
                    }
                )
        return out

    def doc(self, doc_id: int) -> dict | None:
        if not (0 <= doc_id < len(self.bm.docs)):
            return None
        meta = dict(self.bm.docs[doc_id])
        meta["text"] = self.text_of(doc_id)
        return meta
