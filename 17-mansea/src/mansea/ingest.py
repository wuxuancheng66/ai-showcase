"""语料采集：把本机 man 手册 / 本地 Markdown 文本转成统一格式的 JSONL。

输出字段：
    id, source, name, section, title, summary, keys, text, path
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

MAN_ROOTS = ["/usr/share/man"]
MAN_SECTIONS = ["1", "4", "5", "6", "7", "8", "9", "n"]

_OVERSTRIKE = re.compile(r".\x08")
_BLANKS = re.compile(r"\n{3,}")
_HEADER = re.compile(r"^([A-Za-z0-9_@.+\-:]+)\(([0-9a-z]+)\)")

# man 页里常见的大写小节标题
_SECTION_NAMES = {
    "NAME", "SYNOPSIS", "DESCRIPTION", "OVERVIEW", "EXAMPLES", "OPTIONS",
    "EXIT STATUS", "SEE ALSO", "BUGS", "HISTORY", "AUTHORS", "FILES",
    "ENVIRONMENT", "DIAGNOSTICS", "NOTES", "RETURN VALUE", "USAGE",
    "COMMANDS", "INTRODUCTION", "STANDARDS", "CAVEATS", "WARNING",
}


def strip_overstrike(s: str) -> str:
    """去掉 groff 用 `X\\bX` / `_\\bX` 表示的粗体下划线控制符。"""
    return _BLANKS.sub("\n\n", _OVERSTRIKE.sub("", s)).strip()


def render_man(path: str, timeout: int = 20) -> str:
    env = dict(os.environ, MANPAGER="cat", MANWIDTH="100", LC_ALL="C", LANG="C")
    try:
        r = subprocess.run(
            ["man", path], capture_output=True, env=env, text=True, timeout=timeout
        )
    except (subprocess.TimeoutExpired, OSError):
        return ""
    return strip_overstrike(r.stdout)


def parse_man(text: str, fallback_name: str, section: str) -> tuple[str, str, str]:
    """从渲染后的 man 页里抽出 (name, title, summary)。"""
    lines = text.split("\n")
    name, sec = fallback_name, section
    for ln in lines[:5]:
        m = _HEADER.match(ln.strip())
        if m:
            name, sec = m.group(1), m.group(2)
            break
    title = f"{name}({sec})"

    # NAME 小节：跳到 "NAME" 之后，直到下一个小节标题
    summary = ""
    try:
        i = next(k for k, ln in enumerate(lines[:40]) if ln.strip() == "NAME")
    except StopIteration:
        i = -1
    if i >= 0:
        buf = []
        for ln in lines[i + 1 : i + 12]:
            s = ln.strip()
            if s in _SECTION_NAMES or _HEADER.match(s):
                break
            if s:
                buf.append(s)
        summary = " ".join(buf)
        summary = re.sub(r"\s+", " ", summary).strip()
    return name, title, summary


def _aliases_from_summary(summary: str) -> list[str]:
    """NAME 行 `grep, egrep, fgrep - file pattern searcher` -> 别名列表。"""
    if not summary:
        return []
    head = summary.split(" - ")[0].split(" -- ")[0]
    return [a.strip() for a in head.split(",") if a.strip()]


def collect_man_files() -> list[tuple[str, str]]:
    """返回 [(文件路径, 章节号)]，按 realpath 去重。"""
    seen: set[str] = set()
    out: list[tuple[str, str]] = []
    for root in MAN_ROOTS:
        for sec in MAN_SECTIONS:
            d = Path(root) / f"man{sec}"
            if not d.is_dir():
                continue
            for p in sorted(d.iterdir()):
                if p.name.startswith("."):
                    continue
                try:
                    rp = os.path.realpath(p)
                except OSError:
                    continue
                if rp in seen:
                    continue
                seen.add(rp)
                out.append((str(p), sec))
    return out


def ingest_man(limit: int | None = None, workers: int = 8) -> list[dict]:
    files = collect_man_files()
    if limit:
        files = files[:limit]
    print(f"[ingest] 发现 {len(files)} 个 man 页面，开始渲染…", file=sys.stderr)

    def work(item):
        path, sec = item
        base = Path(path).name
        stem = base.split(".")[0]
        text = render_man(path)
        if len(text) < 80:
            return None
        name, title, summary = parse_man(text, stem, sec)
        aliases = _aliases_from_summary(summary)
        keys = " ".join([name] + aliases + [f"{name}({sec})"])
        return {
            "source": "man",
            "name": name,
            "section": sec,
            "title": title,
            "summary": summary[:400],
            "keys": keys,
            "text": text,
            "path": path,
        }

    docs: list[dict] = []
    seen_titles: set[str] = set()
    dropped = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for r in ex.map(work, files):
            if not r:
                continue
            # gunzip.1 / zcat.1 都是 `.so man1/gzip.1` 的重定向页，
            # 渲染后标题相同 —— 按 (标题, 章节) 去重，只留第一个。
            key = f"{r['title']}|{r['section']}"
            if key in seen_titles:
                dropped += 1
                continue
            seen_titles.add(key)
            r["id"] = len(docs)
            docs.append(r)
    print(f"[ingest] 成功采集 {len(docs)} 篇（去重丢弃 {dropped} 篇重复/重定向页）", file=sys.stderr)
    return docs


def ingest_dir(root: str, exts=(".md", ".markdown", ".txt")) -> list[dict]:
    """通用：把一个目录里的 Markdown/文本文件收进语料。"""
    root_p = Path(root)
    docs: list[dict] = []
    for p in sorted(root_p.rglob("*")):
        if p.suffix.lower() not in exts or not p.is_file():
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if len(text.strip()) < 10:
            continue
        first = next((l for l in text.split("\n") if l.strip()), p.stem).lstrip("# ").strip()
        docs.append(
            {
                "source": "file",
                "name": p.name,
                "section": "doc",
                "title": p.name,
                "summary": first[:400],
                "keys": f"{p.name} {p.stem}",
                "text": text,
                "path": str(p),
            }
        )
    for i, d in enumerate(docs):
        d["id"] = i
    print(f"[ingest] 从 {root} 采集 {len(docs)} 篇文档", file=sys.stderr)
    return docs


def write_jsonl(docs: list[dict], path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for d in docs:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")
    print(f"[ingest] 写入 {path}（{len(docs)} 条）", file=sys.stderr)


def read_jsonl(path: str) -> list[dict]:
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out
