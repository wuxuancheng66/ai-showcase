"""第二阶段重排：把「已经在前五」的答案顶到第一。

第 4 轮结束时留下的问题：

    HELD6  P@5 0.818    但  P@1 0.273

答案八成已经捞进前五了，只是排不到第一。融合层（body/head/name/concept/intent）
是个「召回器」，它只管把相关的都捞上来；**把最好的那个挑出来是另一件事**，
需要的是另一种信号 —— 跟"像不像相关"无关，跟"是不是一个真命令"有关。

所以这里加第二级：只对融合分的前 N 名重算一次分，加进四个字段层面的判据。

    1. runnable  这个名字敲得进终端吗（见 binchk.py）
    2. shape     名字长得像命令吗（全小写、短、没有 :: 和驼峰）
    3. nolib     是不是库/模块页（Tcl 命名空间、Perl 模块、后缀里的 5/5.18）
    4. namehit   查询里是不是直接写出了这个命令名

为什么必须分两级而不是全量重算：这四个判据都很"硬"，全量用会把
`zshbuiltins` 这种名字不合规但确实是答案的页直接打死。
只在前 N 名里用，等于"召回器说了这批都相关，现在在它们内部挑最像命令的那个"。

调参：`python3 -m mansea.tune --rerank` 会扫这组权重。
"""

from __future__ import annotations

import re

# 名字"长得像命令"：全小写开头、长度别太离谱、只有 [a-z0-9._-]
_SHAPE_OK = re.compile(r"^[a-z][a-z0-9._+-]{0,13}$")
# 库/模块页：Tcl 命名空间、Perl 模块、带版本号的 perl 脚本
_LIB = re.compile(r"::|^(tcl|tk|itcl|perl|postfix|db_|xslt|ldap|sasl|ssl|ns_)|\d+$", re.I)
# 苹果后台守护进程：驼峰或全大写，结尾是 Agent/Daemon/Service/Helper/Util
_DAEMON = re.compile(r"(Agent|Daemon|Service|Helper|Server|d)$|^[A-Z0-9_]{4,}$")

# 调参：`./run.sh tune --rerank` 只扫重排，`./run.sh tune --joint` 连融合一起扫。
#
# 第 5 轮的结论（跑了敏感度曲线，见 mansea/_sens.py）：
#   runnable 是**唯一真正立住**的特征，0→1.0 有一大段真实爬升，1.0 以上持平。
#   shape    基本平坦（0.3 之后反而微降），留 0.3 是因为它在曲线上不为负。
#   nolib / nodaemon / cov  **被扫成了 0**，一个都没挣到权重。
#      - cov（NAME 行覆盖度）和 head 路高度重合，加了等于重复计分；
#      - nolib 的正则会误伤 `install-info`、`openssl` 这类名字里带数字的；
#      - nodaemon 的 `(...|d)$` 会连 `find`、`sed` 一起打成守护进程 ——
#        这条最危险，幸好曲线一开始就把它压下去了。
#   这三个特征的代码留着没删，但在默认配置里不生效。**
W_RUNNABLE = 1.00  # 敲得出去。0→1.0 实打实涨分，1.0 以上就是平台
W_SHAPE = 0.30     # 名字规整。平坦，留着无害
W_NOLIB = 0.00     # 不是库页 —— 扫成 0，正则误伤太多
W_NODAEMON = 0.00  # 不是苹果守护进程 —— 扫成 0，会把 find/sed 一起打死
W_NAMEHIT = 0.20   # 查询里直接写了命令名。**理论很香，实测有毒**：
                   # 扩展词表里经常会冒出某个命令名（问"回车符"会展开出 tr/cp），
                   # 于是它被当成"用户点名要这个命令"，凭空加了 1.2 分。
                   # 从 1.20 砍到 0.20 就是为了压住这个副作用。
W_COV = 0.00       # NAME 行覆盖度 —— 扫成 0，和 head 路重复

RERANK_N = 30       # 只对前 30 名重排
_RUNNABLE_MISS_PENALTY = 0.0  # 保留为 0：硬惩罚会打死 zshbuiltins，改用不给加分


class Reranker:
    """预计算每篇文档的静态特征，查询时只算查询相关的那两项。"""

    def __init__(self, engine) -> None:
        self.eng = engine
        n = len(engine)
        self.runnable = [0.0] * n
        self.shape = [0.0] * n
        self.nolib = [0.0] * n
        self.nodaemon = [0.0] * n
        self.lowname: list[str] = []
        self.namekeys: list[set[str]] = []

        bins = getattr(engine, "_bins", set())
        for i, meta in enumerate(engine.bm.docs):
            nm = (meta.get("name") or "").lower()
            self.lowname.append(nm)
            keys = set(
                t
                for t in re.split(r"[^a-z0-9]+", (meta.get("_keys") or meta.get("keys") or "").lower())
                if t
            )
            keys.add(nm)
            self.namekeys.append(keys)

            self.runnable[i] = 1.0 if nm in bins else 0.0
            self.shape[i] = 1.0 if _SHAPE_OK.match(nm) else 0.0
            self.nolib[i] = 0.0 if _LIB.search(meta.get("name") or "") else 1.0
            self.nodaemon[i] = 0.0 if _DAEMON.search(meta.get("name") or "") else 1.0

    # ---------- 查询相关特征 ----------
    def _name_hit(self, doc_id: int, qlow: str, qtoks: set[str]) -> float:
        nm = self.lowname[doc_id]
        if not nm:
            return 0.0
        if nm in qtoks:
            return 1.0
        # 查询里出现 `pkill nginx`，命令名 pkill 是独立 token
        if re.search(r"(?<![a-z0-9])" + re.escape(nm) + r"(?![a-z0-9])", qlow):
            return 1.0
        return 0.0

    def _coverage(self, doc_id: int, qtoks: set[str]) -> float:
        """NAME 行 + 标题覆盖了多少查询词。比 BM25 更"讲道理"：不看词频看有没有。"""
        if not qtoks:
            return 0.0
        keys = self.namekeys[doc_id]
        return len(qtoks & keys) / len(qtoks)

    def rerank(
        self,
        scored: list[tuple[float, int]],
        query: str,
        qtoks: set[str],
        w: dict[str, float] | None = None,
    ) -> list[tuple[float, int]]:
        if not scored:
            return scored
        w = w or {}
        wr = w.get("W_RUNNABLE", W_RUNNABLE)
        ws = w.get("W_SHAPE", W_SHAPE)
        wl = w.get("W_NOLIB", W_NOLIB)
        wd = w.get("W_NODAEMON", W_NODAEMON)
        wn = w.get("W_NAMEHIT", W_NAMEHIT)
        wc = w.get("W_COV", W_COV)
        n = w.get("RERANK_N", RERANK_N)

        qlow = query.lower()
        head, tail = scored[:n], scored[n:]
        out = []
        for s, d in head:
            bonus = (
                wr * self.runnable[d]
                + ws * self.shape[d]
                + wl * self.nolib[d]
                + wd * self.nodaemon[d]
                + wn * self._name_hit(d, qlow, qtoks)
                + wc * self._coverage(d, qtoks)
            )
            out.append((s + bonus, d))
        out.sort(reverse=True)
        return out + tail


def feature_report(engine) -> str:
    """给 `./run.sh rerank --report` 用：看看这批特征把语料切成了什么样。"""
    r = Reranker(engine)
    n = len(engine)
    lines = [
        f"语料 {n} 篇",
        f"  runnable  {int(sum(r.runnable)):>5}  ({sum(r.runnable)/n:.1%})",
        f"  shape     {int(sum(r.shape)):>5}  ({sum(r.shape)/n:.1%})",
        f"  notlib    {int(sum(r.nolib)):>5}  ({sum(r.nolib)/n:.1%})",
        f"  nodaemon  {int(sum(r.nodaemon)):>5}  ({sum(r.nodaemon)/n:.1%})",
    ]
    return "\n".join(lines)
