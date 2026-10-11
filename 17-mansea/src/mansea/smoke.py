"""冒烟测试：不依赖网络，验证管线从头到尾是通的。

    python3 -m mansea.smoke
"""

from __future__ import annotations

import sys
import time

from .engine import Engine
from .tokenize import tokenize
from .zh import expand

# (查询, 期望出现在前 N 名里的文档名)
CASES: list[tuple[str, list[str], int]] = [
    ("查看端口占用", ["lsof", "netstat"], 5),
    ("杀掉进程", ["pkill", "kill", "killall"], 5),
    ("磁盘空间", ["df", "du", "diskutil"], 5),
    ("压缩解压", ["tar", "gzip"], 5),
    ("文本替换", ["sed"], 10),
    ("递归查找文件", ["find", "mdfind"], 8),
    ("find files by name", ["find"], 3),
    ("how to kill a process", ["kill"], 5),
    ("ssh 免密登录", ["ssh", "ssh-keygen", "sshd"], 10),
    ("查看文件内容", ["cat", "less", "head", "tail"], 10),
    # 第 3 轮新增：`.so` 别名（这 4 个命令以前一个都答不上来）
    ("dirname", ["basename"], 1),
    ("gunzip", ["gzip"], 1),
    ("pgrep", ["pkill"], 3),
    ("umask", ["builtin"], 3),
    # 意图层：人写进速查表、但 man 页自己没说过的问法
    ("去掉文件里的回车符", ["tr"], 3),
    ("按名字查进程号", ["pkill"], 3),
]

# ask 的用例：(问法, 输出里必须出现的命令名)
ASK_CASES: list[tuple[str, str]] = [
    ("怎么把文件按列切开", "cut"),
    ("去掉文件里的回车符", "tr"),
    ("让 mac 不休眠", "caffeinate"),
    ("解压 gz 文件", "gunzip"),
]


def main() -> int:
    t0 = time.time()
    eng = Engine()
    load_ms = (time.time() - t0) * 1000
    print(f"索引载入 {len(eng)} 篇，{load_ms:.0f}ms\n")

    # 分词器自身
    assert tokenize("tar -xzvf")["tar"] == 1, "基本英文分词坏了"
    assert "端口" in dict(tokenize("端口占用")), "中文分词坏了"
    assert "port" in expand("查看端口占用"), "中文扩展坏了"
    print("✓ 分词 / 中文扩展 自检通过\n")

    passed = 0
    for q, expect, topn in CASES:
        res = eng.search(q, topn)
        names = [r["name"].lower() for r in res]
        hit = [e for e in expect if any(e == n or n.startswith(e) for n in names)]
        ok = bool(hit)
        passed += ok
        flag = "✓" if ok else "✗"
        print(f"{flag} {q:<24} 期望 {expect}  top{topn}: {names[:5]}")
    print(f"\n{passed}/{len(CASES)} 通过")

    if ASK_CASES:
        from .cli import cmd_ask

        class _A:
            pass

        import io
        import contextlib

        ap = 0
        for q, want in ASK_CASES:
            a = _A()
            a.query = q.split()
            a.more = False
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                cmd_ask(a)
            out = buf.getvalue()
            ok = want in out.split("\n")[0]
            ap += ok
            print(f"{'✓' if ok else '✗'} ask {q:<20} 期望 {want:10} 得到 {out.splitlines()[0][:48]}")
        print(f"\n{ap}/{len(ASK_CASES)} ask 通过")
        passed = passed + ap

    total = len(CASES) + len(ASK_CASES)
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
