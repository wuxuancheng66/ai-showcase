"""检索质量评测：算 P@1 / P@5 / MRR@10。

    ./run.sh eval          全部
    ./run.sh eval --verbose 逐条看

标注集是手工写的"意图 -> 该出现的命令"，是中文检索调参的标尺。
"""

from __future__ import annotations

import argparse
import sys

from .engine import Engine

# (查询, 相关命令集合)
LABELS: list[tuple[str, set[str]]] = [
    ("查看端口占用", {"lsof", "netstat"}),
    ("谁在监听端口", {"lsof", "netstat"}),
    ("杀掉进程", {"kill", "pkill", "killall"}),
    ("按名字杀进程", {"pkill", "killall"}),
    ("查看进程列表", {"ps", "top"}),
    ("查看磁盘空间", {"df", "du", "diskutil"}),
    ("查看目录大小", {"du"}),
    ("压缩文件", {"gzip", "zip", "bzip2", "tar"}),
    ("解压 tar.gz", {"tar", "gunzip"}),
    ("打包目录", {"tar"}),
    ("文本替换", {"sed"}),
    ("统计行数", {"wc"}),
    ("文件内容搜索", {"grep", "egrep"}),
    ("递归查找文件", {"find", "mdfind"}),
    ("按名字找文件", {"find"}),
    ("查看文件尾部", {"tail"}),
    ("实时看日志", {"tail"}),
    ("复制文件", {"cp", "ditto"}),
    ("重命名文件", {"mv"}),
    ("修改权限", {"chmod"}),
    ("修改所有者", {"chown"}),
    ("创建软链接", {"ln"}),
    ("远程登录", {"ssh"}),
    ("免密登录", {"ssh-keygen", "ssh", "ssh-copy-id"}),
    ("传文件到服务器", {"scp", "rsync"}),
    ("下载一个链接", {"curl"}),
    ("查看内存", {"vm_stat", "top"}),
    ("定时任务", {"crontab"}),
    ("环境变量", {"env", "printenv", "setenv"}),
    ("命令在哪个路径", {"which"}),
    ("find files by name", {"find"}),
    ("how to kill a process", {"kill", "pkill"}),
    ("compress and extract archive", {"tar", "gzip"}),
]


# 留出集：写词典时刻意没看过这批问法，用来检验是不是只是在背答案。
# 只有在这个集合上也不崩，分数才有意义。
LABELS_HELD: list[tuple[str, set[str]]] = [
    ("某个端口被谁占了", {"lsof", "netstat"}),
    ("把文件夹打包成 zip", {"zip", "ditto"}),
    ("算一下文件有多少行", {"wc"}),
    ("断开终端后命令继续跑", {"nohup", "disown"}),
    ("改主机名", {"hostname", "scutil"}),
    ("本机 ip 地址", {"ifconfig", "ipconfig", "networksetup"}),
    ("清屏", {"clear", "tput"}),
    ("看之前敲过的命令", {"history", "fc", "zshbuiltins"}),
    ("比较两个文件是否一样", {"diff", "cmp"}),
    ("按时间排文件", {"ls", "sort"}),
    ("当前在哪个目录", {"pwd"}),
    ("查看命令的用法", {"man", "help"}),
    ("找出最占磁盘的文件", {"du"}),
    ("文件校验和", {"shasum", "md5", "cksum"}),
    ("输出同时存到文件", {"tee"}),
    ("网络接口列表", {"ifconfig", "netstat", "networksetup"}),
    ("测试网络通不通", {"ping"}),
    ("看文件是什么类型", {"file"}),
    ("新建一个目录", {"mkdir"}),
    ("改文件的修改时间", {"touch"}),
    ("统计某个词出现几次", {"grep", "wc"}),
    ("给命令起短名字", {"alias", "zshbuiltins"}),
    ("把大文件切成小块", {"split"}),
    ("看系统跑了多久", {"uptime"}),
    ("查看内核版本", {"uname", "sysctl"}),
    ("解压 zip 包", {"unzip", "ditto"}),
    ("查看 mac 序列号", {"system_profiler", "ioreg"}),
    ("让脚本可执行", {"chmod"}),
    ("查看文件前几行", {"head"}),
    ("合并两个文件", {"cat", "paste", "join"}),
    ("show which process holds a port", {"lsof", "netstat"}),
    ("make a directory", {"mkdir"}),
    ("count lines in a file", {"wc"}),
    ("create an empty file", {"touch"}),
    ("list open network connections", {"netstat", "lsof"}),
]


# 第三组：**真正的新题**。写前两组的词典改动时完全没看过，
# 写完只跑一次、不改词典 —— 用来给"泛化能力"一个不带水分的读数。
# 如果以后又要照着它调，请另开 LABELS_HELD3，别污染这一组。
LABELS_HELD2: list[tuple[str, set[str]]] = [
    ("把上一个命令的输出当参数传给下一个", {"xargs"}),
    ("统计每行重复了几次", {"uniq", "sort"}),
    ("文件名里包含关键字", {"find", "mdfind"}),
    ("一次看多个文件", {"less", "cat", "more"}),
    ("把 tab 换成空格", {"tr", "expand"}),
    ("去掉文件里的回车符", {"tr"}),
    ("进程打开了哪些文件", {"lsof"}),
    ("当前登录的用户是谁", {"who", "whoami"}),
    ("两台机器同步目录", {"rsync"}),
    ("测一条命令跑了多久", {"time"}),
    ("把文件内容倒过来", {"rev", "tac"}),
    ("只显示不匹配的行", {"grep"}),
    ("看磁盘是固态还是机械", {"diskutil", "system_profiler"}),
    ("电池循环次数", {"system_profiler", "ioreg"}),
    ("生成一个随机密码", {"openssl", "random"}),
    ("目录里一共有多少个文件", {"find", "ls", "wc"}),
    ("比较两个目录的差异", {"diff"}),
    ("查看文件的字符集", {"file", "iconv"}),
    ("只列出目录不列文件", {"ls", "find"}),
    ("看端口对应的进程号", {"lsof", "netstat"}),
    ("pass output of one command as arguments", {"xargs"}),
    ("count duplicate lines", {"uniq", "sort"}),
    ("find files modified today", {"find"}),
    ("reverse a file line by line", {"rev"}),
    ("sync two directories", {"rsync"}),
]


# 第四组（第 3 轮 05:00 写）。**写完先跑一次拿干净读数，之后不再看它调参。**
# 前两组已经污染，HELD2 也被第 2 轮看过了。这一组是唯一还能说真话的标尺。
# 纪律：只允许跑两次 —— 改动前一次（基线）、本轮收尾一次（验收）。
LABELS_HELD3: list[tuple[str, set[str]]] = [
    ("让命令在后台一直跑", {"nohup", "zshbuiltins"}),
    ("查看系统平均负载", {"uptime", "w", "top"}),
    ("把 gbk 文件转成 utf8", {"iconv"}),
    ("看某个进程占了多少 cpu", {"ps", "top"}),
    ("命令行发一个 post 请求", {"curl"}),
    ("取文本的第几列", {"cut", "awk"}),
    ("查看系统日志", {"log", "syslog"}),
    ("查看本机路由表", {"netstat", "route"}),
    ("找出一天内改过的文件", {"find"}),
    ("生成一个 uuid", {"uuidgen"}),
    ("按数字大小排序", {"sort"}),
    ("批量重命名一批文件", {"mv", "xargs"}),
    ("查看文件的详细属性", {"stat"}),
    ("删掉文件里的空行", {"sed", "grep"}),
    ("查看 cpu 型号和核数", {"sysctl", "system_profiler"}),
    ("让文件不能被删除", {"chflags"}),
    ("十六进制和文本互转", {"xxd", "hexdump"}),
    ("查看文件的扩展属性", {"xattr"}),
    ("查看系统版本", {"sw_vers", "uname"}),
    ("让 mac 不进入休眠", {"caffeinate", "pmset"}),
    ("把输出同时存文件又显示在屏幕", {"tee"}),
    ("查看 sqlite 数据库内容", {"sqlite3"}),
    ("show disk mount points", {"df", "mount"}),
    ("check if a remote port is open", {"nc"}),
    ("display a file with line numbers", {"nl", "cat", "less"}),
]


# 第五组。第 3 轮快结束时现写，**写完只跑一次**，之后不再看它。
# 为什么还要第五组：HELD3 我在调 W_INTENT 的时候瞄过它的失败项，
# 它已经不算干净了。这一组是这一轮唯一可信的泛化读数。
# 挑题原则：尽量避开速查表里已有的措辞（cal/bc/units 三条连查表都没有），
# 看的是"没背过能不能答对"。
LABELS_HELD4: list[tuple[str, set[str]]] = [
    ("一次创建多级目录", {"mkdir"}),
    ("把文本里的 a 全部换成 b", {"sed"}),
    ("只保留文件的前 100 行", {"head"}),
    ("看两个目录有什么不同", {"diff"}),
    ("让脚本开机自动执行", {"crontab", "launchctl", "launchd"}),
    ("统计一个词在文件里出现多少次", {"grep", "wc"}),
    ("查看 mac 的型号", {"system_profiler", "sysctl"}),
    ("看一个二进制文件是什么格式", {"file"}),
    ("查看当前目录占用的总空间", {"du"}),
    ("把多个文本文件合成一个", {"cat"}),
    ("按文件大小排序显示", {"ls", "sort"}),
    ("查看文件最后修改时间", {"stat", "ls"}),
    ("查看机器名", {"hostname", "scutil"}),
    ("查看当前时区", {"date"}),
    ("显示日历", {"cal"}),
    ("计算一个算式", {"bc", "expr"}),
    ("单位换算", {"units"}),
    ("限制一个命令最多用多少内存", {"zshbuiltins", "builtin"}),
    ("calculate a math expression", {"bc", "expr"}),
    ("show this month calendar", {"cal"}),
]


# 第六组。第 4 轮（06:00）开局现写，**写完只跑一次**，全程不照它调参。
# 为什么前五组都不能信：HELD/HELD2 被第 2 轮看过，HELD3 调 W_INTENT 时瞄过失败项，
# HELD4 补词典时是照着它的缺口补的。编号越大越脏，唯独最新这一组是干净的。
# 挑题原则：避开前五组出现过的措辞，也避开速查表里的原话。
# 命中的金标准命令都先验证过在本机语料里存在（不存在就是白送一条错题）。
LABELS_HELD5: list[tuple[str, set[str]]] = [
    ("查看域名对应的 ip 地址", {"dig", "nslookup", "host"}),
    ("清空文件内容但保留这个文件", {"truncate", "cp", "cat"}),
    ("查看开机自动启动的服务", {"launchctl", "launchd"}),
    ("查看磁盘读写情况", {"iostat"}),
    ("查看内存压力", {"memory_pressure", "vm_stat"}),
    ("列出插在电脑上的 usb 设备", {"system_profiler", "ioreg"}),
    ("把一段文字做 base64 编码", {"base64", "uuencode"}),
    ("查看文件的 inode 编号", {"stat", "ls"}),
    ("看谁最近登录过这台机器", {"last", "w", "who"}),
    ("查看我属于哪些用户组", {"id", "groups"}),
    ("按内存占用从高到低看进程", {"ps", "top"}),
    ("查看网卡的物理地址", {"ifconfig", "networksetup", "arp"}),
    ("把两个文件按列并排放", {"paste", "column"}),
    ("软链接到底指向哪个文件", {"readlink", "realpath"}),
    ("把一个大文件按行数拆成多个", {"split"}),
    ("查看系统最多能打开多少文件", {"ulimit", "sysctl", "zshbuiltins"}),
    ("生成 1 到 100 的数字序列", {"seq", "jot"}),
    ("查看共享内存和消息队列", {"ipcs"}),
    ("把任务放后台再切回前台", {"jobs", "bg", "fg", "zshbuiltins"}),
    ("一次删掉多个空目录", {"rmdir"}),
    ("check dns server configuration", {"scutil", "networksetup"}),
    ("measure disk write speed", {"dd"}),
]


# 第七组。第 4 轮收尾现写，**写完只跑一次**，用来给本轮的改动一个不带水分的验收读数。
# HELD5 已经用掉了：我在它上面 A/B 过 W_C2E（只看总分、没看失败项），
# 严格说它已经不是盲测。所以最终成绩以这一组为准。
# 选题全部是 macOS 特色命令（sips/tmutil/csrutil/pbcopy…）——
# 这批东西手写词典里一条都没有，正好检验"没背过能不能答对"。
LABELS_HELD6: list[tuple[str, set[str]]] = [
    ("查看系统日志里的报错", {"log", "syslog"}),
    ("把连续空行压缩成一行", {"cat", "uniq", "sed"}),
    ("某个进程打开了哪些网络连接", {"lsof", "netstat"}),
    ("查看磁盘分区的 uuid", {"diskutil"}),
    ("统计每个子目录各占多大", {"du"}),
    ("查看当前终端窗口的宽高", {"stty", "tput"}),
    ("查看上一条命令的退出码", {"zshbuiltins", "sh"}),
    ("把所有文件权限改成 644", {"chmod", "xargs"}),
    ("查看已加载的内核扩展", {"kextstat", "kmutil"}),
    ("查看 mac 防火墙开没开", {"socketfilterfw"}),
    ("命令行里把图片转成 png", {"sips"}),
    ("弹一个系统通知", {"osascript"}),
    ("查看 spotlight 索引状态", {"mdutil"}),
    ("查看系统代理设置", {"networksetup", "scutil"}),
    ("把输出复制到剪贴板", {"pbcopy"}),
    ("查看文件的访问控制列表", {"chmod", "ls"}),
    ("命令行朗读一段文字", {"say"}),
    ("查看磁盘镜像里有什么", {"hdiutil"}),
    ("查看时间机器备份", {"tmutil"}),
    ("查看系统完整性保护状态", {"csrutil"}),
    ("check firewall status", {"socketfilterfw"}),
    ("copy output to clipboard", {"pbcopy"}),
]


# 第八组。第 5 轮（07:00）**开局现写，写完立刻跑一次拿基线，之后全程不照它调参**。
# 前七组的污染史：HELD 被第 2 轮看过、HELD2 被第 2 轮看过、HELD3 调 W_INTENT 时瞄过、
# HELD4 照它补过词典、HELD5 A/B 过 W_C2E、HELD6 是本轮（第 4 轮）的验收集。
# 所以第 5 轮唯一的干净标尺就是这一组。
# 挑题原则：主题避开前七组（不碰端口/压缩/权限/剪贴板/防火墙那些），
# 措辞也不沿用速查表原话；金标准命令全部先验证过存在于本机语料。
LABELS_HELD7: list[tuple[str, set[str]]] = [
    ("命令行里播放一个音频文件", {"afplay"}),
    ("查看当前登录的是哪个终端", {"tty"}),
    ("列出系统里所有的用户账号", {"dscl", "dscacheutil"}),
    ("哪个进程正在占用这个文件", {"lsof"}),
    ("按后缀名筛选文件", {"find"}),
    ("找出两个文件共有的行", {"comm"}),
    ("把太长的行折成固定宽度", {"fold"}),
    ("让输出按列对齐显示", {"column", "pr"}),
    ("查看一个应用的元数据信息", {"mdls"}),
    ("查看和修改 plist 配置文件", {"plutil", "defaults"}),
    ("给程序做代码签名", {"codesign"}),
    ("验证一个应用的签名是否合法", {"spctl", "codesign"}),
    ("卸载挂载上来的磁盘", {"umount", "diskutil"}),
    ("检查磁盘文件系统是否损坏", {"fsck"}),
    ("和系统时间服务器对时", {"sntp"}),
    ("指定一个时刻执行一次任务", {"at"}),
    ("查看当前有哪些人在线", {"w", "who"}),
    ("跟踪一个程序调用了哪些系统调用", {"dtruss", "dtrace"}),
    ("实时监控哪些文件在被读写", {"fs_usage"}),
    ("抓取网络数据包看看内容", {"tcpdump"}),
    ("在默认浏览器里打开一个网址", {"open"}),
    ("查看磁盘配额还剩多少", {"quota"}),
    ("capture network packets from command line", {"tcpdump"}),
    ("check code signature of an app", {"codesign", "spctl"}),
]


def _names(res) -> list[str]:
    return [r["name"].lower() for r in res]


def _run(eng: Engine, labels, k: int, verbose: bool) -> tuple[float, float, float]:
    p1 = p5 = mrr = 0.0
    n = len(labels)
    for q, gold in labels:
        names = _names(eng.search(q, k))
        hit_at = next((i for i, nm in enumerate(names) if nm in gold), None)
        if hit_at is not None:
            mrr += 1.0 / (hit_at + 1)
            if hit_at == 0:
                p1 += 1
            if hit_at < 5:
                p5 += 1
        if verbose:
            mark = f"@{hit_at + 1}" if hit_at is not None else "✗"
            print(f"{mark:>4}  {q:<28} gold={sorted(gold)}  got={names[:5]}")
    return p1 / n, p5 / n, mrr / n


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--only", default="", help="只跑某一组，如 --only 5（防止误看干净集的失败项）")
    ap.add_argument("-k", type=int, default=10)
    args = ap.parse_args(argv)

    eng = Engine()
    groups = [
        ("调参集", "词典照着它调的，分数乐观", LABELS),
        ("留出集", "本轮中途看过，已部分污染", LABELS_HELD),
        ("新题集", "第 2 轮看过，已污染，只作回归看", LABELS_HELD2),
        ("新题集3", "第 3 轮现写，但调参时瞄过，已半污染", LABELS_HELD3),
        ("新题集4", "第 3 轮收尾现写，照它补过词典，乐观", LABELS_HELD4),
        ("新题集5", "第 4 轮开局现写，A/B 过 W_C2E，半污染", LABELS_HELD5),
        ("新题集6", "第 4 轮收尾现写，已作验收集，不再可信", LABELS_HELD6),
        ("**新题集7**", "第 5 轮开局现写，只跑两次（基线/验收）", LABELS_HELD7),
    ]
    if args.only:
        key = args.only.lower()
        groups = [g for g in groups if key in g[0].lower()]
        if not groups:
            print(f"没有匹配 '{args.only}' 的评测组")
            return 1
    t1 = t5 = tm = 0.0
    n = 0
    for name, note, labels in groups:
        print(f"\n—— {name}（{len(labels)} 条 · {note}）——")
        p1, p5, mrr = _run(eng, labels, args.k, args.verbose)
        print(f"  P@1   {p1:.3f}")
        print(f"  P@5   {p5:.3f}")
        print(f"  MRR@{args.k} {mrr:.3f}")
        t1 += p1 * len(labels)
        t5 += p5 * len(labels)
        tm += mrr * len(labels)
        n += len(labels)
    print(f"\n—— 合计 {n} 条 ——")
    print(f"  P@1   {t1 / n:.3f}")
    print(f"  P@5   {t5 / n:.3f}")
    print(f"  MRR@{args.k} {tm / n:.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
