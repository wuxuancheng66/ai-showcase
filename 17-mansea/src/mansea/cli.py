"""mansea 命令行入口。

    python3 -m mansea.cli build            # 采集 man 手册 + 建索引
    python3 -m mansea.cli search "查询"    # 搜索
    python3 -m mansea.cli show 123         # 查看全文
    python3 -m mansea.cli serve            # 起本地网页服务
"""

from __future__ import annotations

import argparse
import math
import sys
import time
from pathlib import Path

from . import bm25 as bm25_mod
from .alias import _stem, alias_names, build_alias_map, cmd_to_doc
from .bm25 import BM25
from .cheatsheet import CHEATS
from .concept import cn_terms, en_to_cn
from .engine import DEFAULT_DATA, Engine
from .ingest import ingest_dir, ingest_man, read_jsonl, write_jsonl
from .related import build_related

ROOT = Path(__file__).resolve().parent.parent


def cmd_build(args: argparse.Namespace) -> int:
    t0 = time.time()
    docs_path = ROOT / "data" / "docs.jsonl"

    if args.reuse and docs_path.exists():
        # 语料不变、只重建索引（调排序参数时用它，省掉 18s 的 man 渲染）
        docs = read_jsonl(str(docs_path))
        print(f"[build] 复用已有语料 {len(docs)} 篇", file=sys.stderr)
    else:
        docs = ingest_man(limit=args.limit, workers=args.workers)
        if args.include:
            for d in args.include:
                docs.extend(ingest_dir(d))
        for i, d in enumerate(docs):
            d["id"] = i
        write_jsonl(docs, str(docs_path))

    # 别名表：`.so` 重定向 / symlink / 硬链接丢掉的 289 个命令名，全靠它找回来
    alias_rev = alias_names(docs)          # {doc_id: [别名]}
    c2d = cmd_to_doc(docs)                 # {任意叫法: doc_id}
    # 速查表意图 -> 文档（含 gunzip/dirname 这类只有别名没有独立文档的）
    cheat_by_doc: dict[int, list[str]] = {}
    for _intent, cmd, _args, note in CHEATS:
        did = c2d.get(cmd.lower())
        if did is not None:
            cheat_by_doc.setdefault(did, []).append(f"{_intent} {note}")

    def meta_of(d: dict, i: int) -> dict:
        return {
            "name": d.get("name", ""),
            "section": d.get("section", ""),
            "title": d.get("title", ""),
            "summary": d.get("summary", ""),
            "source": d.get("source", ""),
            "path": d.get("path", ""),
            "_keys": d.get("keys", "") + " " + " ".join(alias_rev.get(i, ())),
        }

    bm = BM25()
    hd = BM25()
    cp = BM25()
    it = BM25()          # 只装**人写的**速查表意图，和自动译中的概念层分开
    intent_store: dict[str, list[str]] = {}
    bigram_df: dict[str, int] = {}
    for i, d in enumerate(docs):
        text = d.get("text", "")
        keys = d.get("keys", "") + " " + " ".join(alias_rev.get(i, ()))
        summary = d.get("summary", "")
        meta = meta_of(d, i)
        bm.add(meta, (keys + " ") * 3 + text)
        # 标题层：命令名/别名/NAME 一行，独立于全文建索引，用于字段加权
        hd.add(meta, (keys + " ") * 3 + (summary + " ") * 2 + title_hint(d))
        # 概念层：把 NAME 行自动译成中文，让中文查询能命中没写进词典的文档
        cp.add_terms(meta, concept_terms(d))
        # 意图层：速查表里人写的中文意图。精度远高于自动翻译，单独一路打分。
        iterms = intent_terms(cheat_by_doc.get(i, ()))
        if iterms:
            intent_store[str(i)] = sorted(iterms)
        for t in concept_terms(d):
            bigram_df[t] = bigram_df.get(t, 0) + 1
    bm.finalize()
    hd.finalize()
    cp.finalize()
    it.finalize()
    # 二元组的稀有度按**全部 2706 篇**的概念词算，不是按 166 条意图算。
    # 意图集太小，在它上面算 IDF 会把「文件」当成稀有词（见 engine.__init__ 注释）。
    n_docs = max(1, len(docs))
    bigram_idf = {
        t: math.log(1 + (n_docs - df + 0.5) / (df + 0.5)) for t, df in bigram_df.items()
    }
    (ROOT / "data" / "intent_terms.json").write_text(
        __import__("json").dumps(
            {"docs": intent_store, "idf": {k: round(v, 4) for k, v in bigram_idf.items()}},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    bm.save(ROOT / "data" / "index.json")
    hd.save(ROOT / "data" / "head.json")
    cp.save(ROOT / "data" / "concept.json")
    it.save(ROOT / "data" / "intent.json")
    (ROOT / "data" / "alias.json").write_text(
        __import__("json").dumps(build_alias_map(docs), ensure_ascii=False), encoding="utf-8"
    )
    # 命令的**任何叫法**（正名/别名/文件名）-> 文档 id，给 ask 用
    (ROOT / "data" / "cmd2doc.json").write_text(
        __import__("json").dumps(c2d, ensure_ascii=False), encoding="utf-8"
    )
    # SEE ALSO 关系图：手册作者手工标的"相关命令"，字面相似度推不出来的那部分
    rel = build_related(docs, c2d)
    (ROOT / "data" / "related.json").write_text(
        __import__("json").dumps({str(k): v for k, v in rel.items()}, ensure_ascii=False),
        encoding="utf-8",
    )
    n_edge = sum(len(v) for v in rel.values())
    print(f"[build] SEE ALSO 关系图：{len(rel)} 篇有邻居，共 {n_edge} 条边")

    # 「敲得进终端」的名字集合，重排层的 runnable 特征要用（见 binchk.py）
    from .binchk import build as build_bins

    bins = build_bins(ROOT / "data")
    print(f"[build] 可运行命令名：{len(bins and __import__('json').loads(bins.read_text(encoding='utf-8')))} 个")

    dt = time.time() - t0
    print(f"[build] 完成：{len(bm)} 篇文档，全文索引 {len(bm.postings)} 词项，"
          f"标题索引 {len(hd.postings)} 词项，耗时 {dt:.1f}s")
    print(f"[build] 索引文件：{ROOT / 'data' / 'index.json'} + head.json")
    return 0


def concept_terms(d: dict) -> dict[str, float]:
    """文档 -> 中文概念词频表：NAME 行自动译中，覆盖广但精度一般。"""
    src = f"{d.get('name', '')} {d.get('summary', '')}"
    return cn_terms(en_to_cn(src))


def intent_terms(cheat_intents: list[str]) -> dict[str, float]:
    """文档 -> **人写的**中文意图词频表。

    为什么要和 concept_terms 分开：自动译中只能复述 man 页说过的话，
    覆盖 2706 篇；速查表只有 262 条但每条都是人确认过的知识
    （`tr` 的 NAME 行是 "translate characters"，永远答不了"去掉回车符"）。
    挤在同一路里，高精度信号会被大量的低精度命中稀释。
    """
    tf: dict[str, float] = {}
    for s in cheat_intents:
        for t in cn_terms(s):
            tf[t] = tf.get(t, 0.0) + 1.0
    return tf


def title_hint(d: dict) -> str:
    """章节号也参与标题层匹配，让 `man 1` 这类查询有信号。"""
    return f"{d.get('section', '')} {d.get('source', '')}"


def _color(s: str, code: str) -> str:
    if not sys.stdout.isatty():
        return s
    return f"\033[{code}m{s}\033[0m"


def cmd_search(args: argparse.Namespace) -> int:
    eng = Engine(DEFAULT_DATA)
    q = " ".join(args.query)
    t0 = time.time()
    res = eng.search(q, args.k)
    dt = (time.time() - t0) * 1000
    if not res:
        print("没有命中。换个说法试试。")
        return 1
    print(f"{len(eng)} 篇文档 · {dt:.1f}ms · 命中 {len(res)} 条\n")
    for i, r in enumerate(res, 1):
        head = f"{i:>2}. {r['title']}"
        print(_color(head, "1;36") + f"   [{r['score']:.2f}]")
        if r["summary"]:
            print(f"    {r['summary'][:150]}")
        if r["snippet"]:
            print(f"    {r['snippet'][:200]}")
        print()
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    eng = Engine(DEFAULT_DATA)
    d = eng.doc(args.id)
    if not d:
        print(f"没有 id={args.id} 的文档")
        return 1
    print(d.get("text", ""))
    return 0


def cmd_ask(args: argparse.Namespace) -> int:
    """问一句人话，直接给一条可以复制去终端执行的命令。

    和 search 的区别：search 给的是"哪篇手册可能相关"，
    ask 给的是"这条命令你直接敲"——命中速查表时带常用参数，
    没命中就退回手册的 NAME 行。检索是手段，可执行才是目的。
    """
    eng = Engine(DEFAULT_DATA)
    q = " ".join(args.query)
    res = eng.search(q, 5)
    if not res:
        print("没找到相关的命令。换个说法试试。")
        return 1

    c2d = _load_cmd_map(eng)
    cn = cn_terms(q)
    idf = _load_bigram_idf()

    # 按**文档**归组，不是按命令名：gunzip/dirname/pgrep 这些只有别名、
    # 没有独立文档的条目，按名字永远取不到（第 3 轮踩到的坑）。
    by_doc: dict[int, list[tuple[str, str, str, str]]] = {}
    for e in CHEATS:
        did = c2d.get(e[1].lower())
        if did is not None:
            by_doc.setdefault(did, []).append(e)

    for r in res:
        entries = by_doc.get(r["id"], [])
        if not entries:
            continue
        # 在候选命令自己的速查条目里，挑和问法最贴的那条。
        # 按二元组稀有度加权：光数个数的话，「文件」这种泛词会和「回车」一样重，
        # 于是「解压 gz 文件」挑中「gzip 压缩」而不是解压。
        def fit(e) -> float:
            return sum(idf.get(t, 4.0) for t in set(cn_terms(e[0])) & set(cn))

        best = max(entries, key=fit)
        intent, cmd, cmdargs, note = best
        print(_color(f"$ {cmdargs}", "1;32"))
        print(f"  {note}")
        print(f"  来自 {r['title']} · 匹配意图「{intent}」")
        if args.more:
            for it2, _c, a2, n2 in entries:
                if it2 != intent:
                    print(f"    也可以：{a2}   # {n2}")
        return 0

    # 没有速查条目：退回手册的 NAME 行 + SYNOPSIS
    r = res[0]
    print(_color(f"$ man {r['name']}", "1;33") + "   （速查表里还没有这条，先看手册）")
    print(f"  {r['summary'][:160]}")
    syn = _synopsis(eng.text_of(r["id"]))
    if syn:
        print(f"  {syn[:200]}")
    return 0


def _load_cmd_map(eng) -> dict[str, int]:
    """命令的**任何叫法** -> 文档 id（正名 / `.so` 别名 / 文件名）。

    少了文件名这一项，`gunzip` 就永远取不到：它的手册页是 gzip.1 的硬链接，
    去重后留下的文档名字叫 GZIP，而 gunzip.1 恰好排在 gzip.1 前面被当成正名。
    """
    out: dict[str, int] = {}
    for i, nm in enumerate(eng._names):
        if nm:
            out.setdefault(nm, i)
    for fn, key in (("cmd2doc.json", None), ("alias.json", None)):
        p = DEFAULT_DATA / fn
        if p.exists():
            import json as _json

            out.update({k: int(v) for k, v in _json.loads(p.read_text(encoding="utf-8")).items()})
    for i, meta in enumerate(eng.bm.docs):
        stem = _stem(Path(meta.get("path") or "").name).lower()
        if stem:
            out.setdefault(stem, i)
    return out


def _load_bigram_idf() -> dict[str, float]:
    """复用建索引时算好的二元组稀有度（全语料 2706 篇口径）。"""
    p = DEFAULT_DATA / "intent_terms.json"
    if not p.exists():
        return {}
    import json as _json

    return _json.loads(p.read_text(encoding="utf-8")).get("idf", {})


def _synopsis(text: str) -> str:
    """从渲染后的 man 页里抠出 SYNOPSIS 那一段。"""
    lines = text.split("\n")
    try:
        i = next(k for k, ln in enumerate(lines[:40]) if ln.strip() == "SYNOPSIS")
    except StopIteration:
        return ""
    buf: list[str] = []
    for ln in lines[i + 1 : i + 10]:
        s = ln.strip()
        if not s:
            if buf:
                break
            continue
        if s in {"DESCRIPTION", "NAME", "OPTIONS"}:
            break
        buf.append(s)
    return " ".join(buf)


def cmd_related(args: argparse.Namespace) -> int:
    """给一个命令，列出手册自己说"相关"的命令（SEE ALSO 图）。"""
    eng = Engine(DEFAULT_DATA)
    q = " ".join(args.query).lower()
    did = _load_cmd_map(eng).get(q)
    if did is None:
        res = eng.search(" ".join(args.query), 1)
        did = res[0]["id"] if res else None
    if did is None:
        print(f"没找到命令 {q}")
        return 1
    meta = eng.bm.docs[did]
    nbs = eng.related_of(did, args.k)
    print(_color(f"{meta.get('title', '')} —— SEE ALSO {len(nbs)} 条", "1;36"))
    if not nbs:
        print("  这篇手册没有 SEE ALSO 段，或引用的页面不在语料里。")
        return 0
    for r in nbs:
        print(f"  · {r['title']:<28} {r['summary'][:70]}")
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    from .server import run_server

    return run_server(port=args.port, data_dir=str(DEFAULT_DATA))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="mansea", description="澈的本地知识检索引擎")
    sub = p.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build", help="采集语料并建立索引")
    b.add_argument("--limit", type=int, default=None, help="只取前 N 个 man 页面（调试用）")
    b.add_argument("--workers", type=int, default=8)
    b.add_argument("--include", nargs="*", default=[], help="额外收录的本地文档目录")
    b.add_argument("--reuse", action="store_true", help="复用 data/docs.jsonl，只重建索引")
    b.set_defaults(func=cmd_build)

    s = sub.add_parser("search", help="搜索")
    s.add_argument("query", nargs="+")
    s.add_argument("-k", type=int, default=10)
    s.set_defaults(func=cmd_search)

    sh = sub.add_parser("show", help="查看全文")
    sh.add_argument("id", type=int)
    sh.set_defaults(func=cmd_show)

    a = sub.add_parser("ask", help="问一句人话，直接给可执行的命令")
    a.add_argument("query", nargs="+")
    a.add_argument("--more", action="store_true", help="顺带列出该命令的其他常用写法")
    a.set_defaults(func=cmd_ask)

    rl = sub.add_parser("related", help="列出某命令的 SEE ALSO 相关命令")
    rl.add_argument("query", nargs="+")
    rl.add_argument("-k", type=int, default=8)
    rl.set_defaults(func=cmd_related)

    sv = sub.add_parser("serve", help="启动本地网页端")
    sv.add_argument("--port", type=int, default=8733)
    sv.set_defaults(func=cmd_serve)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
