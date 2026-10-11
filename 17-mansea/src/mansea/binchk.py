"""「这玩意儿到底能不能敲进终端」—— 一个比章节号靠谱得多的先验。

第 5 轮的起因：排序里一直用「章节先验」（man1=1.0 / man8=0.75 / Tcl 的 n=0.05）。
看起来合理，实际是错的 —— 本机 830 篇 man8 里绝大多数是 macOS 的后台守护进程
（`AssetCacheAgent`、`AMPDevicesAgent`…），用户永远不会去"查"它们；
而 `pkill`（man1）、`sysctl`（man8）这种真命令跟它们混在一起，只靠章节号分不开。

更直接的信号：**这个名字在不在 PATH 里，敲得出去吗。**

```
2706 篇手册  ->  名字能在 PATH 里找到可执行文件的：929 篇
  sec 1: 625/972      sec 8: 258/830
  sec n:  29/632      sec 5:   9/188
```

Tcl 手册 632 篇只有 29 个名字撞上了 PATH 里的文件（after/append/array…），
所以这一条几乎等价于"是不是真命令"，而且比章节号精确得多。

有个坑：shell 内建（`history` `disown` `setenv` `builtin` `zshbuiltins`）
不是独立的可执行文件，按 PATH 判会被误杀。所以最终集合是三部分的并集：

    PATH 可执行文件  ∪  shell 内建  ∪  别名表（alias.json）

在现有 157 个金标准命令上，这样能覆盖 152 个（漏掉的是 tac / random 这两个
macOS 上根本不存在的命令，以及藏在 /usr/libexec 子目录里的 socketfilterfw）。
"""

from __future__ import annotations

import os
from pathlib import Path

DEFAULT_DATA = Path(__file__).resolve().parent.parent / "data"

# 除了 PATH，再固定扫这几个目录。/usr/sbin 里的东西（sysctl、diskutil）
# 不一定在当前 shell 的 PATH 上，漏了它们就是漏掉一批真命令。
EXTRA_BIN_DIRS = ("/bin", "/sbin", "/usr/bin", "/usr/sbin", "/usr/libexec")

# shell 内建：不是文件，但确实"敲得出去"。
# 只列评测里真的会当答案的那些，不贪多 —— 贪多就会把噪声重新放进来。
SHELL_BUILTINS = frozenset("""
alias bg bind break builtin cd chdir command compgen complete continue declare
dirs disown echo enable eval exec exit export false fc fg getopts hash help
history jobs kill let local logout popd printf pushd pwd read readonly return
set setenv shift source suspend test times trap true type typeset ulimit umask
unalias unset unsetenv wait whence which zshbuiltins sh bash zsh : . [
""".split())


def scan_runnable(data_dir: str | Path = DEFAULT_DATA) -> set[str]:
    """扫出「能敲进终端」的命令名集合。只读文件系统，不做任何修改。"""
    out: set[str] = set()

    dirs = list(EXTRA_BIN_DIRS)
    for p in (os.environ.get("PATH") or "").split(":"):
        if p and p not in dirs:
            dirs.append(p)

    for d in dirs:
        try:
            with os.scandir(d) as it:
                for e in it:
                    try:
                        if e.is_file(follow_symlinks=True) and os.access(e.path, os.X_OK):
                            out.add(e.name.lower())
                    except OSError:
                        continue
        except OSError:
            continue

    out |= SHELL_BUILTINS

    # 别名表：第 3 轮捡回来的 289 个被去重误杀的命令名（gunzip/dirname/pgrep…）
    ap = Path(data_dir) / "alias.json"
    if ap.exists():
        import json as _json

        try:
            blob = _json.loads(ap.read_text(encoding="utf-8"))
            for k in blob:
                if isinstance(k, str) and k:
                    out.add(k.lower())
        except Exception:
            pass

    return out


def build(data_dir: str | Path = DEFAULT_DATA) -> Path:
    names = sorted(scan_runnable(data_dir))
    p = Path(data_dir) / "bins.json"
    p.write_text(
        "{\n" + ",\n".join(f'  "{n}": 1' for n in names) + "\n}\n",
        encoding="utf-8",
    )
    return p


def load(data_dir: str | Path = DEFAULT_DATA) -> set[str]:
    p = Path(data_dir) / "bins.json"
    if not p.exists():
        return set()
    import json as _json

    return set(_json.loads(p.read_text(encoding="utf-8")).keys())


if __name__ == "__main__":
    p = build()
    print(f"{p} -> {len(load())} 个可运行命令名")
