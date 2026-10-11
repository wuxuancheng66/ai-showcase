"""man 手册的 `.so` 重定向别名表 —— 补上被去重丢掉的 220 个命令名。

问题：`/usr/share/man/man1/dirname.1` 的内容只有一行 `.so man1/basename.1`。
它在系统里是**能查的**（`man dirname` 正常打开 basename 那一页），
但第 1 轮采集时按 (标题,章节) 去重，把这类重定向页全丢了。
后果是 `dirname` / `gunzip` / `pgrep` / `umask` / `alias` / `bg` 这些
真实存在的命令，mansea 一个都答不上来。

办法：不去重，改成**记别名**。
扫描所有 `.so` 页，建 `别名 -> 目标文档` 的映射，检索时把别名也当作命令名。
这样既不会出现重复文档（alias 只是指针，不是新文档），又能答对 `dirname`。
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from .ingest import MAN_ROOTS, MAN_SECTIONS

_SO = re.compile(r"^\.so\s+(\S+)")


def scan_redirects() -> dict[str, tuple[str, str]]:
    """扫一遍 man 目录，返回 {别名: (目标命令名, 目标章节)}。

    只处理 `.so` 重定向页（有些是 symlink，已经被 realpath 去重吃掉了，
    这里再扫不到，但那些本身就指向同一篇，无所谓）。
    """
    out: dict[str, tuple[str, str]] = {}
    for root in MAN_ROOTS:
        for sec in MAN_SECTIONS:
            d = Path(root) / f"man{sec}"
            if not d.is_dir():
                continue
            # 硬链接（gunzip.1 和 gzip.1 是同一个 inode）：先建 inode -> 规范名
            inode_of: dict[tuple[int, int], str] = {}
            for p in sorted(d.iterdir()):
                if p.name.startswith("."):
                    continue
                try:
                    st = p.stat()
                except OSError:
                    continue
                stem = _stem(p.name)
                inode_of.setdefault((st.st_dev, st.st_ino), stem)
            for p in sorted(d.iterdir()):
                if p.name.startswith("."):
                    continue
                target: Path | None = None
                # 一半是 `.so` 重定向文件，一半是 symlink（gunzip -> gzip）
                try:
                    with p.open("r", encoding="utf-8", errors="ignore") as f:
                        m = _SO.match(f.readline())
                    if m:
                        target = Path(m.group(1))
                except OSError:
                    pass
                if target is None and p.is_symlink():
                    try:
                        target = Path(os.path.realpath(p))
                    except OSError:
                        target = None
                if target is None:
                    # 硬链接：指向同 inode 的第一个文件
                    try:
                        st = p.stat()
                    except OSError:
                        continue
                    canon = inode_of.get((st.st_dev, st.st_ino))
                    if canon and canon.lower() != _stem(p.name).lower():
                        out[_stem(p.name).lower()] = (canon.lower(), sec)
                    continue
                tsec = target.parent.name.replace("man", "") or sec
                tname = _stem(target.name)
                alias = _stem(p.name)
                if alias and tname and alias.lower() != tname.lower():
                    out[alias.lower()] = (tname.lower(), tsec)
    return out


def _stem(filename: str) -> str:
    """gunzip.1.gz -> gunzip；去掉所有后缀。"""
    name = filename
    while "." in name:
        name = name.rsplit(".", 1)[0]
    return name


def build_alias_map(docs: list[dict]) -> dict[str, int]:
    """{别名小写: 目标文档 id}。

    三级回退，缺一不可：
      1. 目标文件名 —— 文档被去重时留下的是**先出现那个文件**，
         而它的 name 来自页内标题，跟文件名未必一致
         （gunzip.1 排在 gzip.1 前面，留下的文档标题叫 GZIP）
      2. (名字, 章节) 精确匹配
      3. 只按名字匹配
    """
    by_stem: dict[str, int] = {}
    by_ns: dict[tuple[str, str], int] = {}
    by_name: dict[str, int] = {}
    for i, d in enumerate(docs):
        nm = (d.get("name") or "").lower()
        by_ns[(nm, d.get("section", ""))] = i
        by_name.setdefault(nm, i)
        p = d.get("path") or ""
        if p:
            by_stem.setdefault(_stem(Path(p).name).lower(), i)

    out: dict[str, int] = {}
    unresolved = 0
    for alias, (tname, tsec) in scan_redirects().items():
        doc_id = by_stem.get(tname)
        if doc_id is None:
            doc_id = by_ns.get((tname, tsec))
        if doc_id is None:
            doc_id = by_name.get(tname)
        if doc_id is None:
            unresolved += 1
            continue
        if doc_id == by_name.get(tname) and alias in by_name and by_name[alias] == doc_id:
            continue
        out[alias] = doc_id
    if unresolved:
        print(f"[alias] {unresolved} 个别名找不到目标文档（忽略）")
    return out


def alias_names(docs: list[dict]) -> dict[int, list[str]]:
    """反查：{文档 id: [它的所有别名]}，给命令名索引用。"""
    out: dict[int, list[str]] = {}
    for alias, doc_id in build_alias_map(docs).items():
        out.setdefault(doc_id, []).append(alias)
    return out


def cmd_to_doc(docs: list[dict]) -> dict[str, int]:
    """{任意叫法: 文档 id} —— 正名、别名、文件名通吃。给速查表喂索引用。"""
    m: dict[str, int] = {}
    for i, d in enumerate(docs):
        for k in ((d.get("name") or "").lower(), _stem(Path(d.get("path") or "").name).lower()):
            if k:
                m.setdefault(k, i)
        for k in (d.get("keys") or "").lower().split():
            k = k.strip()
            if k and "(" not in k:
                m.setdefault(k, i)
    m.update(build_alias_map(docs))
    return m


if __name__ == "__main__":
    r = scan_redirects()
    print(f"扫描到 {len(r)} 个 .so 重定向")
    for k in ("dirname", "gunzip", "pgrep", "umask", "alias", "bg", "apropos", "zcat"):
        print(f"  {k:10} -> {r.get(k)}")
