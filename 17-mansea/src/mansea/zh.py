"""中文意图 -> 英文检索词 的**带权重**扩展词典。

man 手册全是英文，用中文查必然召回为零。这一层负责把「查看端口占用」
翻译成 `lsof/netstat/port/listen…`，再去查英文语料。

第 2 轮重写的要点：
1. **权重**：`pkill` 之于「按名字杀进程」是答案（3.0），`process` 只是背景词（0.5）。
   旧版一视同仁，导致「文件」→file 这种泛词把无关页顶上来。
2. **短语优先 + 消费匹配**：长的中文短语先匹配并消费掉，避免「按名字杀进程」
   被拆成「文件」「进程」等泛词。
3. 词典规模 ~200 条（第 1 轮 80 条）。

这是纯手工维护的知识表，也是这个项目里最"有人味"的部分：
词典质量直接决定中文检索好不好用。
"""

from __future__ import annotations

import re

# 权重档位，写词条时用它，别直接写魔数
W_ANSWER = 3.0   # 就是这个命令
W_TOPIC = 1.2    # 强相关主题词
W_HINT = 0.5     # 背景/上下文词，用来兜召回

# 中文短语 -> [(英文词, 权重), ...]
Z2E_W: dict[str, list[tuple[str, float]]] = {
    # ================= 宣澄 09:38 批量补录（已校验本机语料存在） =================
    "按行处理": [("awk", W_ANSWER), ("line", W_TOPIC)],
    "按列处理": [("awk", W_ANSWER), ("field", W_TOPIC)],
    "取某一列再算": [("awk", W_ANSWER), ("sum", W_TOPIC)],
    "列对齐": [("column", W_ANSWER), ("table", W_TOPIC)],
    "排成表格": [("column", W_ANSWER), ("table", W_TOPIC)],
    "加行号": [("nl", W_ANSWER), ("number", W_TOPIC)],
    "字符替换": [("tr", W_ANSWER), ("translate", W_TOPIC)],
    "删掉空格": [("tr", W_ANSWER), ("space", W_TOPIC)],
    "大小写转换": [("tr", W_ANSWER), ("upper", W_TOPIC), ("lower", W_TOPIC)],
    "按列合并": [("paste", W_ANSWER), ("merge", W_TOPIC)],
    "两个文件逐行对比": [("comm", W_ANSWER), ("compare", W_TOPIC)],
    "按字段连接": [("join", W_ANSWER), ("field", W_TOPIC)],
    "看二进制内容": [("xxd", W_ANSWER), ("od", W_TOPIC), ("hex", W_TOPIC)],
    "统计字节数": [("wc", W_ANSWER), ("bytes", W_TOPIC)],
    "打开文件": [("open", W_ANSWER)],
    "用默认程序打开": [("open", W_ANSWER), ("default", W_TOPIC)],
    "在访达里打开": [("open", W_ANSWER), ("finder", W_TOPIC)],
    "打开网页": [("open", W_ANSWER), ("url", W_TOPIC)],
    "预览文件": [("qlmanage", W_ANSWER), ("quicklook", W_TOPIC)],
    "word 转文本": [("textutil", W_ANSWER), ("convert", W_TOPIC)],
    "文档格式转换": [("textutil", W_ANSWER), ("convert", W_TOPIC)],
    "查看系统版本": [("sw_vers", W_ANSWER), ("version", W_TOPIC)],
    "查看内核参数": [("sysctl", W_ANSWER), ("kernel", W_TOPIC)],
    "改内核参数": [("sysctl", W_ANSWER), ("kernel", W_TOPIC)],
    "看磁盘列表": [("diskutil", W_ANSWER), ("disk", W_TOPIC)],
    "修复磁盘": [("fsck", W_ANSWER), ("diskutil", W_TOPIC), ("repair", W_TOPIC)],
    "制作 dmg": [("hdiutil", W_ANSWER), ("dmg", W_TOPIC)],
    "挂载 dmg": [("hdiutil", W_ANSWER), ("attach", W_TOPIC)],
    "推出 dmg": [("hdiutil", W_ANSWER), ("detach", W_TOPIC)],
    "造个空文件占地方": [("mkfile", W_ANSWER), ("size", W_TOPIC)],
    "测磁盘速度": [("dd", W_ANSWER), ("benchmark", W_TOPIC)],
    "看 sip 状态": [("csrutil", W_ANSWER), ("integrity", W_TOPIC)],
    "电源设置": [("pmset", W_ANSWER), ("power", W_TOPIC)],
    "定时开关机": [("pmset", W_ANSWER), ("schedule", W_TOPIC)],
    "立刻关机": [("shutdown", W_ANSWER), ("halt", W_TOPIC)],
    "立刻重启": [("reboot", W_ANSWER)],
    "睡眠设置": [("pmset", W_ANSWER), ("sleep", W_TOPIC)],
    "查域名 ip": [("dig", W_ANSWER), ("nslookup", W_TOPIC), ("dns", W_TOPIC)],
    "查域名注册信息": [("whois", W_ANSWER)],
    "追踪网络路径": [("traceroute", W_ANSWER), ("route", W_TOPIC)],
    "下载整个网页": [("curl", W_ANSWER), ("http", W_TOPIC)],
    "批量下载": [("curl", W_ANSWER), ("download", W_TOPIC)],
    "改网络设置": [("networksetup", W_ANSWER), ("network", W_TOPIC)],
    "查 wifi": [("networksetup", W_ANSWER), ("wifi", W_TOPIC)],
    "处理 json": [("jq", W_ANSWER), ("json", W_TOPIC)],
    "解析 json": [("jq", W_ANSWER), ("parse", W_TOPIC)],
    "终端录屏": [("script", W_ANSWER), ("record", W_TOPIC)],
    "录制终端操作": [("script", W_ANSWER), ("typescript", W_TOPIC)],
    "写系统日志": [("logger", W_ANSWER), ("syslog", W_TOPIC)],
    "打印文件": [("lp", W_ANSWER), ("print", W_TOPIC)],
    "看打印队列": [("lpstat", W_ANSWER), ("queue", W_TOPIC)],
    "看内核日志": [("dmesg", W_ANSWER), ("kernel", W_TOPIC)],
    "安装 pkg 包": [("installer", W_ANSWER), ("pkg", W_TOPIC)],
    "查安装包内容": [("pkgutil", W_ANSWER), ("pkg", W_TOPIC)],
    "代码签名": [("codesign", W_ANSWER), ("sign", W_TOPIC)],
    "查证书": [("security", W_ANSWER), ("certificate", W_TOPIC)],
    "看当前时间": [("date", W_ANSWER), ("time", W_TOPIC)],
    "显示日历": [("cal", W_ANSWER), ("calendar", W_TOPIC)],
    "执行脚本文件": [("source", W_ANSWER), ("script", W_TOPIC)],
    "读取用户输入": [("read", W_ANSWER), ("input", W_TOPIC)],
    # ================= 进程 / 性能 =================
    "按名字杀进程": [("pkill", W_ANSWER), ("killall", W_ANSWER), ("name", W_TOPIC), ("pattern", W_HINT)],
    "按名字杀掉进程": [("pkill", W_ANSWER), ("killall", W_ANSWER)],
    "杀掉进程": [("kill", W_ANSWER), ("pkill", W_ANSWER), ("killall", W_ANSWER), ("terminate", W_TOPIC), ("signal", W_TOPIC)],
    "杀进程": [("kill", W_ANSWER), ("pkill", W_ANSWER), ("killall", W_TOPIC)],
    "结束进程": [("kill", W_ANSWER), ("pkill", W_TOPIC), ("terminate", W_TOPIC)],
    "杀掉": [("kill", W_ANSWER), ("terminate", W_TOPIC), ("signal", W_TOPIC), ("pkill", W_TOPIC), ("killall", W_TOPIC)],
    "强制杀": [("kill", W_ANSWER), ("sigkill", W_TOPIC), ("kill", W_TOPIC), ("signal", W_HINT)],
    "进程": [("process", W_TOPIC), ("pid", W_TOPIC), ("ps", W_HINT), ("proc", W_HINT)],
    "进程列表": [("ps", W_ANSWER), ("top", W_TOPIC)],
    "断开终端": [("nohup", W_ANSWER), ("disown", W_TOPIC), ("hangup", W_HINT)],
    "终端关掉": [("nohup", W_ANSWER), ("disown", W_TOPIC)],
    "退出终端": [("nohup", W_ANSWER), ("disown", W_TOPIC)],
    "继续运行": [("nohup", W_ANSWER), ("disown", W_TOPIC), ("background", W_TOPIC)],
    "继续跑": [("nohup", W_ANSWER), ("disown", W_TOPIC)],
    "后台运行": [("nohup", W_ANSWER), ("background", W_TOPIC), ("bg", W_TOPIC), ("ampersand", W_HINT)],
    "后台": [("background", W_TOPIC), ("jobs", W_TOPIC), ("nohup", W_TOPIC), ("daemon", W_HINT), ("bg", W_HINT), ("fg", W_HINT)],
    "前台": [("fg", W_ANSWER), ("foreground", W_TOPIC)],
    "守护进程": [("daemon", W_ANSWER), ("launchd", W_TOPIC), ("launchctl", W_TOPIC)],
    "开机启动": [("launchctl", W_ANSWER), ("launchd", W_ANSWER), ("startup", W_TOPIC), ("boot", W_HINT), ("login", W_HINT)],
    "自启动": [("launchctl", W_ANSWER), ("launchd", W_TOPIC), ("startup", W_TOPIC)],
    "服务": [("service", W_TOPIC), ("daemon", W_TOPIC), ("launchctl", W_TOPIC), ("launchd", W_HINT)],
    "性能": [("performance", W_TOPIC), ("top", W_TOPIC), ("sample", W_HINT), ("profile", W_HINT), ("instruments", W_HINT)],
    "内存": [("memory", W_TOPIC), ("vm_stat", W_ANSWER), ("top", W_TOPIC), ("malloc", W_HINT), ("swap", W_HINT), ("resident", W_HINT)],
    "内存占用": [("vm_stat", W_ANSWER), ("top", W_ANSWER), ("footprint", W_TOPIC), ("memory", W_TOPIC)],
    "占用": [("usage", W_TOPIC), ("used", W_HINT), ("utilization", W_HINT)],
    "CPU": [("cpu", W_TOPIC), ("top", W_TOPIC), ("ps", W_HINT), ("load", W_HINT)],
    "负载": [("load", W_TOPIC), ("uptime", W_ANSWER), ("top", W_TOPIC)],
    "监控": [("monitor", W_TOPIC), ("top", W_TOPIC), ("watch", W_TOPIC), ("trace", W_HINT)],
    "哪个进程": [("lsof", W_ANSWER), ("ps", W_TOPIC), ("top", W_HINT)],

    # ================= 链接 / 剪贴板 / IPC（宣澄 09:33 补录）=================
    "软链接指向哪里": [("readlink", W_ANSWER), ("symlink", W_TOPIC)],
    "看软链接指向": [("readlink", W_ANSWER), ("symlink", W_TOPIC)],
    "链接指向哪里": [("readlink", W_ANSWER), ("realpath", W_TOPIC)],
    "软链接": [("symlink", W_TOPIC), ("ln", W_TOPIC), ("link", W_HINT)],
    "软连接": [("symlink", W_TOPIC), ("ln", W_TOPIC), ("link", W_HINT)],
    "符号链接": [("symlink", W_TOPIC), ("ln", W_TOPIC)],
    "剪贴板": [("pbcopy", W_ANSWER), ("pbpaste", W_ANSWER), ("clipboard", W_TOPIC), ("pasteboard", W_TOPIC)],
    "粘贴板": [("pbcopy", W_ANSWER), ("pbpaste", W_ANSWER), ("clipboard", W_TOPIC)],
    "复制到剪贴板": [("pbcopy", W_ANSWER), ("clipboard", W_TOPIC), ("pasteboard", W_HINT)],
    "拷贝到剪贴板": [("pbcopy", W_ANSWER), ("clipboard", W_TOPIC)],
    "从剪贴板粘贴": [("pbpaste", W_ANSWER), ("clipboard", W_TOPIC)],
    "共享内存": [("ipcs", W_ANSWER), ("shm", W_TOPIC), ("shared", W_TOPIC), ("memory", W_HINT)],
    "看共享内存": [("ipcs", W_ANSWER), ("shmget", W_TOPIC)],
    "消息队列": [("ipcs", W_ANSWER), ("msgget", W_TOPIC)],
    "信号量": [("ipcs", W_ANSWER), ("semget", W_TOPIC)],
    "文件内容": [("grep", W_ANSWER), ("content", W_TOPIC), ("match", W_HINT)],
    "查找文件内容": [("grep", W_ANSWER), ("pattern", W_TOPIC), ("regex", W_TOPIC)],
    "搜索文件内容": [("grep", W_ANSWER), ("egrep", W_TOPIC), ("pattern", W_TOPIC)],
    "搜索文字": [("grep", W_ANSWER), ("pattern", W_TOPIC)],

    # ================= 磁盘 / 文件 =================
    "磁盘空间": [("df", W_ANSWER), ("diskutil", W_ANSWER), ("space", W_TOPIC), ("capacity", W_HINT)],
    "剩余空间": [("df", W_ANSWER), ("diskutil", W_TOPIC), ("free", W_TOPIC)],
    "查看目录大小": [("du", W_ANSWER), ("directory", W_HINT), ("size", W_HINT)],
    "目录大小": [("du", W_ANSWER), ("size", W_TOPIC)],
    "文件大小": [("du", W_ANSWER), ("ls", W_TOPIC), ("stat", W_TOPIC), ("size", W_TOPIC), ("bytes", W_HINT)],
    "占用空间": [("du", W_ANSWER), ("df", W_TOPIC)],
    "磁盘": [("disk", W_TOPIC), ("diskutil", W_TOPIC), ("df", W_TOPIC), ("volume", W_HINT), ("filesystem", W_HINT)],
    "空间": [("space", W_TOPIC), ("df", W_HINT), ("du", W_HINT), ("capacity", W_HINT)],
    "目录树": [("tree", W_ANSWER), ("hierarchy", W_TOPIC), ("directory", W_HINT), ("recursive", W_HINT)],
    "递归查找": [("find", W_ANSWER), ("recursive", W_TOPIC), ("walk", W_HINT)],
    "按名字找文件": [("find", W_ANSWER), ("name", W_TOPIC), ("filename", W_TOPIC), ("locate", W_HINT)],
    "按名字查找": [("find", W_ANSWER), ("name", W_TOPIC)],
    "查找文件": [("find", W_ANSWER), ("locate", W_TOPIC), ("mdfind", W_TOPIC), ("search", W_HINT), ("glob", W_HINT)],
    "搜索文件": [("find", W_ANSWER), ("mdfind", W_ANSWER), ("locate", W_TOPIC), ("search", W_HINT)],
    "找文件": [("find", W_ANSWER), ("locate", W_TOPIC), ("mdfind", W_TOPIC)],
    "递归": [("recursive", W_TOPIC), ("recurse", W_HINT), ("walk", W_HINT), ("depth", W_HINT)],
    "复制": [("copy", W_TOPIC), ("cp", W_ANSWER), ("ditto", W_TOPIC), ("rsync", W_HINT)],
    "拷贝": [("cp", W_ANSWER), ("ditto", W_TOPIC), ("copy", W_TOPIC)],
    "移动": [("mv", W_ANSWER), ("move", W_TOPIC), ("rename", W_HINT)],
    "重命名": [("mv", W_ANSWER), ("rename", W_TOPIC)],
    "改名": [("mv", W_ANSWER), ("rename", W_TOPIC)],
    "删除": [("rm", W_ANSWER), ("remove", W_TOPIC), ("delete", W_TOPIC), ("unlink", W_HINT)],
    "删掉": [("rm", W_ANSWER), ("remove", W_TOPIC)],
    "软链接": [("ln", W_ANSWER), ("symlink", W_TOPIC), ("symbolic", W_TOPIC), ("alias", W_HINT)],
    "符号链接": [("ln", W_ANSWER), ("symlink", W_TOPIC)],
    "硬链接": [("ln", W_ANSWER), ("link", W_TOPIC), ("hard", W_HINT)],
    "修改权限": [("chmod", W_ANSWER), ("permission", W_TOPIC), ("mode", W_TOPIC)],
    "修改所有者": [("chown", W_ANSWER), ("owner", W_TOPIC), ("chgrp", W_HINT)],
    "所有者": [("chown", W_ANSWER), ("owner", W_TOPIC), ("ownership", W_TOPIC)],
    "属主": [("chown", W_ANSWER), ("owner", W_TOPIC)],
    "权限": [("chmod", W_TOPIC), ("permission", W_TOPIC), ("chown", W_TOPIC), ("mode", W_HINT), ("acl", W_HINT)],
    "挂载": [("mount", W_ANSWER), ("diskutil", W_TOPIC), ("umount", W_TOPIC), ("volume", W_HINT)],
    "卸载磁盘": [("umount", W_ANSWER), ("diskutil", W_TOPIC), ("eject", W_TOPIC)],
    "弹出": [("eject", W_ANSWER), ("diskutil", W_TOPIC), ("umount", W_TOPIC)],
    "备份": [("rsync", W_ANSWER), ("backup", W_TOPIC), ("archive", W_HINT), ("dump", W_HINT)],
    "同步": [("rsync", W_ANSWER), ("sync", W_TOPIC), ("mirror", W_HINT)],
    "镜像": [("rsync", W_ANSWER), ("mirror", W_TOPIC), ("hdiutil", W_HINT)],

    # ================= 压缩 / 归档 =================
    "解压": [("tar", W_TOPIC), ("gunzip", W_ANSWER), ("unzip", W_ANSWER), ("extract", W_TOPIC), ("decompress", W_TOPIC), ("untar", W_TOPIC)],
    "解压缩": [("gunzip", W_ANSWER), ("unzip", W_ANSWER), ("extract", W_TOPIC)],
    "压缩": [("gzip", W_ANSWER), ("compress", W_TOPIC), ("bzip2", W_TOPIC), ("zip", W_TOPIC), ("tar", W_HINT)],
    "打包": [("tar", W_ANSWER), ("archive", W_TOPIC), ("package", W_HINT)],
    "归档": [("tar", W_ANSWER), ("archive", W_TOPIC), ("cpio", W_HINT)],
    "压缩包": [("tar", W_TOPIC), ("zip", W_TOPIC), ("gzip", W_TOPIC), ("archive", W_TOPIC)],
    "tar.gz": [("tar", W_ANSWER + 0.5), ("gunzip", W_TOPIC + 0.5), ("gzip", W_HINT + 0.3)],
    "zip 文件": [("zip", W_ANSWER), ("unzip", W_TOPIC)],

    # ================= 查看 / 阅读 =================
    "查看文件内容": [("cat", W_ANSWER), ("less", W_ANSWER), ("head", W_TOPIC), ("tail", W_TOPIC)],
    "查看文件": [("cat", W_ANSWER), ("less", W_TOPIC), ("view", W_TOPIC), ("open", W_HINT)],
    "查看文件尾部": [("tail", W_ANSWER), ("end", W_HINT)],
    "文件尾部": [("tail", W_ANSWER), ("end", W_HINT)],
    "尾部": [("tail", W_ANSWER)],
    "查看文件开头": [("head", W_ANSWER), ("beginning", W_HINT)],
    "文件开头": [("head", W_ANSWER), ("beginning", W_HINT)],
    "开头": [("head", W_ANSWER)],
    "实时看日志": [("tail", W_ANSWER), ("follow", W_ANSWER), ("log", W_TOPIC)],
    "实时日志": [("tail", W_ANSWER), ("follow", W_ANSWER), ("log", W_TOPIC)],
    "实时": [("tail", W_TOPIC), ("follow", W_TOPIC), ("watch", W_TOPIC), ("live", W_HINT)],
    "跟踪日志": [("tail", W_ANSWER), ("follow", W_TOPIC), ("log", W_TOPIC)],
    "分页查看": [("less", W_ANSWER), ("more", W_TOPIC), ("pager", W_TOPIC)],
    "翻页": [("less", W_ANSWER), ("pager", W_TOPIC), ("more", W_HINT)],
    # ⚠️ 下面这几个是"泛名词"，权重必须压低甚至删掉。
    # 第 2 轮留出集上最大的坑：把「文件」映射成 file，结果 `file`（查看文件类型）
    # 靠命令名精确命中，在所有带"文件"二字的查询里都排第一。
    # 教训：词典里越通用的中文词，越容易反噬。
    "查看": [("show", W_HINT), ("display", W_HINT), ("list", W_HINT), ("view", W_HINT)],
    "目录": [("directory", W_HINT), ("folder", W_HINT)],
    "命令": [("command", W_HINT)],
    "命令在哪个路径": [("which", W_ANSWER), ("path", W_TOPIC), ("whereis", W_TOPIC)],
    "在哪个路径": [("which", W_ANSWER), ("path", W_TOPIC)],
    "命令路径": [("which", W_ANSWER), ("path", W_TOPIC)],
    "在哪里": [("which", W_ANSWER), ("whereis", W_TOPIC), ("path", W_HINT)],
    "装在哪个目录": [("which", W_ANSWER), ("whereis", W_TOPIC)],

    # ================= 文本处理 =================
    "文本替换": [("sed", W_ANSWER), ("substitute", W_TOPIC), ("replace", W_TOPIC), ("regex", W_HINT)],
    "批量替换": [("sed", W_ANSWER), ("replace", W_TOPIC), ("substitute", W_TOPIC)],
    "替换": [("sed", W_ANSWER), ("replace", W_TOPIC), ("substitute", W_TOPIC), ("tr", W_HINT)],
    "统计行数": [("wc", W_ANSWER), ("line", W_TOPIC), ("count", W_TOPIC)],
    "行数": [("wc", W_ANSWER), ("lines", W_TOPIC), ("count", W_HINT)],
    "字数": [("wc", W_ANSWER), ("word", W_TOPIC), ("count", W_HINT)],
    "统计": [("wc", W_TOPIC), ("count", W_TOPIC), ("statistics", W_HINT)],
    "去重": [("uniq", W_ANSWER), ("unique", W_TOPIC), ("duplicate", W_HINT)],
    "排序": [("sort", W_ANSWER), ("order", W_HINT)],
    "文件内容搜索": [("grep", W_ANSWER), ("egrep", W_TOPIC), ("pattern", W_TOPIC), ("search", W_HINT)],
    "搜索内容": [("grep", W_ANSWER), ("egrep", W_TOPIC), ("pattern", W_TOPIC), ("match", W_HINT)],
    "内容搜索": [("grep", W_ANSWER), ("egrep", W_TOPIC), ("pattern", W_TOPIC)],
    "全文搜索": [("grep", W_ANSWER), ("recursive", W_TOPIC), ("search", W_TOPIC)],
    "正则": [("grep", W_TOPIC), ("regex", W_ANSWER), ("egrep", W_TOPIC), ("regular", W_TOPIC)],
    "过滤": [("grep", W_ANSWER), ("filter", W_TOPIC), ("awk", W_TOPIC)],
    "提取字段": [("awk", W_ANSWER), ("cut", W_ANSWER), ("field", W_TOPIC)],
    "切分": [("cut", W_ANSWER), ("split", W_TOPIC), ("awk", W_HINT)],
    "编码转换": [("iconv", W_ANSWER), ("encoding", W_TOPIC), ("transcode", W_TOPIC), ("charset", W_TOPIC)],
    "编码": [("iconv", W_ANSWER), ("encoding", W_TOPIC), ("utf", W_HINT), ("charset", W_HINT), ("base64", W_HINT)],
    "转换": [("convert", W_TOPIC), ("transform", W_HINT), ("transcode", W_HINT), ("translate", W_HINT)],
    "对比文件": [("diff", W_ANSWER), ("compare", W_TOPIC)],
    "差异": [("diff", W_ANSWER), ("difference", W_TOPIC), ("compare", W_TOPIC)],
    "打补丁": [("patch", W_ANSWER), ("diff", W_TOPIC)],

    # ================= 网络 =================
    "查看端口占用": [("lsof", W_ANSWER), ("netstat", W_ANSWER), ("port", W_TOPIC), ("listen", W_TOPIC)],
    "端口占用": [("lsof", W_ANSWER), ("netstat", W_ANSWER), ("port", W_TOPIC)],
    "谁在监听端口": [("lsof", W_ANSWER), ("netstat", W_ANSWER), ("listen", W_TOPIC)],
    "端口": [("port", W_TOPIC), ("lsof", W_TOPIC), ("netstat", W_TOPIC), ("socket", W_HINT), ("listen", W_HINT)],
    "监听": [("listen", W_TOPIC), ("lsof", W_TOPIC), ("netstat", W_TOPIC), ("bind", W_HINT)],
    "网络": [("network", W_TOPIC), ("tcp", W_HINT), ("ip", W_HINT), ("socket", W_HINT), ("interface", W_HINT)],
    "连接": [("connection", W_TOPIC), ("connect", W_TOPIC), ("tcp", W_HINT), ("socket", W_HINT)],
    "下载": [("curl", W_ANSWER), ("wget", W_TOPIC), ("download", W_TOPIC), ("fetch", W_TOPIC), ("url", W_HINT)],
    "下载文件": [("curl", W_ANSWER), ("wget", W_TOPIC), ("fetch", W_TOPIC)],
    "上传": [("curl", W_ANSWER), ("scp", W_ANSWER), ("upload", W_TOPIC), ("put", W_HINT)],
    "传文件到服务器": [("scp", W_ANSWER), ("rsync", W_ANSWER), ("sftp", W_TOPIC), ("remote", W_TOPIC)],
    "传文件": [("scp", W_ANSWER), ("rsync", W_TOPIC), ("sftp", W_TOPIC), ("transfer", W_TOPIC)],
    "传到远程": [("scp", W_ANSWER), ("rsync", W_TOPIC)],
    "远程登录": [("ssh", W_ANSWER), ("login", W_TOPIC), ("remote", W_TOPIC)],
    "远程": [("ssh", W_ANSWER), ("remote", W_TOPIC), ("scp", W_TOPIC), ("rsync", W_HINT)],
    "免密登录": [("ssh-keygen", W_ANSWER), ("ssh-copy-id", W_ANSWER), ("ssh", W_TOPIC), ("authorized_keys", W_TOPIC), ("publickey", W_TOPIC)],
    "免密": [("ssh-keygen", W_ANSWER), ("publickey", W_TOPIC), ("authorized_keys", W_TOPIC), ("agent", W_HINT)],
    "密钥": [("ssh-keygen", W_ANSWER), ("key", W_TOPIC), ("publickey", W_TOPIC), ("certificate", W_HINT)],
    "路由": [("route", W_ANSWER), ("netstat", W_TOPIC), ("gateway", W_TOPIC), ("traceroute", W_TOPIC)],
    "防火墙": [("pfctl", W_ANSWER), ("firewall", W_TOPIC), ("pf", W_TOPIC)],
    "域名解析": [("dig", W_ANSWER), ("nslookup", W_ANSWER), ("host", W_TOPIC), ("dns", W_TOPIC), ("resolve", W_TOPIC)],
    "域名": [("dig", W_ANSWER), ("dns", W_TOPIC), ("host", W_TOPIC), ("nslookup", W_TOPIC), ("resolve", W_HINT)],
    "dns": [("dig", W_ANSWER), ("dns", W_TOPIC), ("host", W_TOPIC), ("nslookup", W_TOPIC)],
    "网速": [("networkquality", W_TOPIC), ("bandwidth", W_TOPIC), ("throughput", W_HINT), ("traffic", W_HINT)],
    "抓包": [("tcpdump", W_ANSWER), ("packet", W_TOPIC), ("capture", W_TOPIC), ("sniff", W_TOPIC), ("pcap", W_TOPIC)],
    "ping": [("ping", W_ANSWER), ("icmp", W_TOPIC)],
    "代理": [("proxy", W_TOPIC), ("curl", W_HINT), ("socks", W_HINT)],

    # ================= 系统 / 账户 =================
    "用户": [("user", W_TOPIC), ("account", W_TOPIC), ("id", W_HINT), ("whoami", W_TOPIC), ("su", W_HINT), ("sudo", W_HINT)],
    "切换用户": [("su", W_ANSWER), ("sudo", W_TOPIC), ("login", W_HINT)],
    "管理员": [("sudo", W_ANSWER), ("root", W_TOPIC), ("su", W_TOPIC)],
    "密码": [("passwd", W_ANSWER), ("password", W_TOPIC), ("credential", W_HINT)],
    "钥匙串": [("security", W_ANSWER), ("keychain", W_TOPIC), ("certificate", W_HINT), ("credential", W_HINT)],
    "环境变量": [("env", W_ANSWER), ("printenv", W_TOPIC), ("export", W_TOPIC), ("environment", W_TOPIC), ("variable", W_HINT)],
    "环境变量怎么设": [("export", W_ANSWER), ("env", W_TOPIC), ("setenv", W_TOPIC)],
    "日志": [("log", W_TOPIC), ("syslog", W_TOPIC), ("logger", W_TOPIC), ("show", W_HINT)],
    "系统日志": [("syslog", W_ANSWER), ("log", W_TOPIC), ("show", W_TOPIC)],
    "时间": [("date", W_TOPIC), ("time", W_TOPIC), ("clock", W_HINT)],
    "时区": [("date", W_TOPIC), ("timezone", W_TOPIC), ("tz", W_TOPIC), ("zoneinfo", W_TOPIC)],
    "定时任务": [("crontab", W_ANSWER), ("cron", W_TOPIC), ("periodic", W_HINT), ("at", W_HINT)],
    "计划任务": [("crontab", W_ANSWER), ("cron", W_TOPIC)],
    "定时": [("crontab", W_ANSWER), ("cron", W_TOPIC), ("schedule", W_TOPIC)],
    "关机": [("shutdown", W_ANSWER), ("halt", W_TOPIC), ("power", W_HINT)],
    "重启": [("reboot", W_ANSWER), ("shutdown", W_TOPIC), ("restart", W_TOPIC)],
    "休眠": [("pmset", W_ANSWER), ("sleep", W_TOPIC), ("power", W_HINT)],
    "电池": [("pmset", W_ANSWER), ("battery", W_TOPIC), ("power", W_HINT), ("charge", W_HINT)],
    "蓝牙": [("bluetooth", W_TOPIC), ("blueutil", W_TOPIC)],
    "无线": [("wifi", W_TOPIC), ("airport", W_TOPIC), ("wireless", W_TOPIC), ("network", W_HINT)],
    "wifi": [("airport", W_TOPIC), ("wifi", W_TOPIC), ("wireless", W_TOPIC)],
    "音量": [("volume", W_TOPIC), ("audio", W_TOPIC), ("sound", W_HINT)],
    "截屏": [("screencapture", W_ANSWER), ("screenshot", W_TOPIC), ("capture", W_HINT)],
    "显示器": [("display", W_TOPIC), ("screen", W_TOPIC), ("resolution", W_HINT), ("screens", W_HINT)],
    "分辨率": [("display", W_TOPIC), ("resolution", W_TOPIC), ("screen", W_HINT)],
    "主机名": [("hostname", W_ANSWER), ("scutil", W_TOPIC), ("host", W_TOPIC)],
    "系统信息": [("uname", W_ANSWER), ("sw_vers", W_ANSWER), ("system_profiler", W_TOPIC), ("hostinfo", W_TOPIC)],

    # ================= 开发 =================
    "编译": [("compile", W_TOPIC), ("clang", W_ANSWER), ("cc", W_TOPIC), ("make", W_TOPIC), ("gcc", W_TOPIC)],
    "调试": [("lldb", W_ANSWER), ("gdb", W_TOPIC), ("debug", W_TOPIC), ("breakpoint", W_HINT)],
    "版本": [("version", W_TOPIC), ("revision", W_HINT), ("release", W_HINT)],
    "脚本": [("script", W_TOPIC), ("shell", W_TOPIC), ("sh", W_HINT), ("bash", W_HINT), ("zsh", W_HINT)],
    "签名": [("codesign", W_ANSWER), ("sign", W_TOPIC), ("signature", W_TOPIC)],
    "证书": [("certificate", W_TOPIC), ("security", W_TOPIC), ("openssl", W_TOPIC), ("ssl", W_HINT)],
    "加密": [("openssl", W_ANSWER), ("encrypt", W_TOPIC), ("cipher", W_TOPIC), ("gpg", W_TOPIC)],
    "随机数": [("random", W_TOPIC), ("rand", W_TOPIC), ("urandom", W_TOPIC), ("entropy", W_HINT)],
    "帮助": [("help", W_TOPIC), ("manual", W_TOPIC), ("man", W_TOPIC), ("usage", W_TOPIC), ("synopsis", W_HINT)],
    "怎么用": [("usage", W_TOPIC), ("manual", W_TOPIC), ("help", W_TOPIC), ("synopsis", W_HINT)],
    "用法": [("man", W_ANSWER), ("usage", W_TOPIC), ("help", W_TOPIC)],
    "手册": [("man", W_ANSWER), ("manual", W_TOPIC), ("apropos", W_TOPIC)],
    "管道": [("pipe", W_TOPIC), ("pipeline", W_TOPIC), ("stdout", W_HINT)],
    "重定向": [("redirect", W_TOPIC), ("stdout", W_TOPIC), ("stderr", W_TOPIC), ("tee", W_ANSWER)],
    "退出码": [("exit", W_TOPIC), ("status", W_TOPIC), ("errno", W_HINT)],
    "换行符": [("tr", W_ANSWER), ("newline", W_TOPIC), ("dos2unix", W_TOPIC)],

    # ================= 文件基础（第 2 轮留出集暴露的缺口）=================
    "新建目录": [("mkdir", W_ANSWER)],
    "创建目录": [("mkdir", W_ANSWER)],
    "建目录": [("mkdir", W_ANSWER)],
    "建个目录": [("mkdir", W_ANSWER)],
    "新建文件夹": [("mkdir", W_ANSWER)],
    "删除目录": [("rmdir", W_ANSWER), ("rm", W_TOPIC)],
    "删除空目录": [("rmdir", W_ANSWER)],
    "当前目录": [("pwd", W_ANSWER)],
    "当前路径": [("pwd", W_ANSWER)],
    "在哪个目录": [("pwd", W_ANSWER)],
    "在哪儿": [("pwd", W_ANSWER), ("which", W_TOPIC)],
    "切换目录": [("cd", W_ANSWER)],
    "上级目录": [("cd", W_ANSWER)],
    "上一级": [("cd", W_ANSWER)],
    "回到上一个目录": [("cd", W_ANSWER)],
    "创建空文件": [("touch", W_ANSWER)],
    "新建文件": [("touch", W_ANSWER)],
    "建个文件": [("touch", W_ANSWER)],
    "修改时间": [("touch", W_ANSWER)],
    "改修改时间": [("touch", W_ANSWER)],
    "更新时间戳": [("touch", W_ANSWER)],
    "可执行": [("chmod", W_ANSWER), ("executable", W_TOPIC)],
    "执行权限": [("chmod", W_ANSWER)],
    "加上执行权限": [("chmod", W_ANSWER)],
    "文件类型": [("file", W_ANSWER)],
    "什么类型": [("file", W_ANSWER)],
    "前几行": [("head", W_ANSWER)],
    "头几行": [("head", W_ANSWER)],
    "最前面": [("head", W_ANSWER)],
    "后几行": [("tail", W_ANSWER)],
    "最后几行": [("tail", W_ANSWER)],
    "多少行": [("wc", W_ANSWER), ("line", W_TOPIC)],
    "有几行": [("wc", W_ANSWER)],
    "有多少行": [("wc", W_ANSWER)],
    "合并": [("paste", W_TOPIC), ("join", W_TOPIC), ("cat", W_ANSWER)],
    "合并文件": [("paste", W_ANSWER), ("join", W_ANSWER), ("cat", W_TOPIC)],
    "拼接": [("cat", W_ANSWER), ("paste", W_TOPIC)],
    "拼接文件": [("cat", W_ANSWER), ("paste", W_TOPIC)],
    "分割文件": [("split", W_ANSWER)],
    "切成小块": [("split", W_ANSWER)],
    "切成小份": [("split", W_ANSWER)],
    "拆分": [("split", W_ANSWER), ("csplit", W_TOPIC)],
    "清空文件": [("cp", W_TOPIC), ("truncate", W_ANSWER), ("cat", W_HINT)],
    "隐藏文件": [("ls", W_TOPIC), ("chflags", W_ANSWER)],
    "扩展属性": [("xattr", W_ANSWER)],
    "文件标签": [("xattr", W_ANSWER)],

    # ================= 比较 / 校验 =================
    "是否一样": [("cmp", W_ANSWER), ("diff", W_TOPIC)],
    "一样不一样": [("cmp", W_ANSWER), ("diff", W_TOPIC)],
    "比较文件": [("cmp", W_ANSWER), ("diff", W_TOPIC)],
    "校验和": [("cksum", W_ANSWER), ("shasum", W_TOPIC), ("md5", W_TOPIC)],
    "哈希值": [("shasum", W_ANSWER), ("md5", W_TOPIC)],
    "文件指纹": [("shasum", W_ANSWER), ("md5", W_TOPIC)],
    "算 md5": [("md5", W_ANSWER), ("shasum", W_TOPIC)],

    # ================= 管道 / 终端 =================
    "同时保存输出": [("tee", W_ANSWER)],
    "存到文件": [("tee", W_ANSWER), ("redirect", W_TOPIC)],
    "输出到文件": [("tee", W_ANSWER), ("redirect", W_TOPIC)],
    "保存输出": [("tee", W_ANSWER)],
    "一边看一边存": [("tee", W_ANSWER)],
    "输出到屏幕还要存": [("tee", W_ANSWER)],
    "清屏": [("clear", W_ANSWER), ("tput", W_TOPIC)],
    "清空屏幕": [("clear", W_ANSWER)],
    "清一下屏": [("clear", W_ANSWER)],
    "历史命令": [("history", W_TOPIC), ("fc", W_ANSWER), ("zshbuiltins", W_TOPIC)],
    "敲过的命令": [("history", W_TOPIC), ("fc", W_ANSWER), ("zshbuiltins", W_TOPIC)],
    "以前执行的命令": [("history", W_TOPIC), ("fc", W_ANSWER)],
    "命令别名": [("alias", W_TOPIC), ("zshbuiltins", W_ANSWER)],
    "起别名": [("alias", W_TOPIC), ("zshbuiltins", W_ANSWER)],
    "别名": [("alias", W_TOPIC), ("zshbuiltins", W_ANSWER), ("symlink", W_HINT)],
    "短名字": [("alias", W_TOPIC), ("zshbuiltins", W_ANSWER)],
    "等几秒": [("sleep", W_ANSWER)],
    "等待几秒": [("sleep", W_ANSWER)],
    "延迟执行": [("sleep", W_ANSWER)],

    # ================= 系统信息 =================
    "跑了多久": [("uptime", W_ANSWER)],
    "运行了多久": [("uptime", W_ANSWER)],
    "开机多久": [("uptime", W_ANSWER)],
    "运行时间": [("uptime", W_ANSWER)],
    "内核": [("uname", W_ANSWER), ("sysctl", W_TOPIC)],
    "内核版本": [("uname", W_ANSWER), ("sysctl", W_TOPIC)],
    "系统版本": [("sw_vers", W_ANSWER), ("uname", W_TOPIC)],
    "mac 版本": [("sw_vers", W_ANSWER)],
    "序列号": [("system_profiler", W_ANSWER), ("ioreg", W_TOPIC)],
    "硬件信息": [("system_profiler", W_ANSWER)],
    "本机配置": [("system_profiler", W_ANSWER), ("hostinfo", W_TOPIC)],
    "cpu 核数": [("sysctl", W_ANSWER), ("hostinfo", W_TOPIC), ("hw", W_HINT)],
    "几核": [("sysctl", W_ANSWER), ("hostinfo", W_TOPIC)],
    "架构": [("uname", W_ANSWER), ("arch", W_TOPIC)],
    "默认设置": [("defaults", W_ANSWER)],
    "系统偏好": [("defaults", W_ANSWER)],
    "开机启动项": [("launchctl", W_ANSWER)],

    # ================= 网络（补充）=================
    "ip 地址": [("ifconfig", W_ANSWER), ("ipconfig", W_ANSWER), ("networksetup", W_TOPIC)],
    "ip地址": [("ifconfig", W_ANSWER), ("ipconfig", W_ANSWER), ("networksetup", W_TOPIC)],
    "本机ip": [("ifconfig", W_ANSWER), ("ipconfig", W_ANSWER)],
    "网卡": [("ifconfig", W_ANSWER), ("networksetup", W_TOPIC)],
    "网络接口": [("ifconfig", W_ANSWER), ("networksetup", W_TOPIC)],
    "接口": [("ifconfig", W_TOPIC)],
    "通不通": [("ping", W_ANSWER)],
    "能不能连通": [("ping", W_ANSWER)],
    "连通": [("ping", W_ANSWER)],
    "网络测试": [("ping", W_ANSWER), ("networkquality", W_TOPIC)],
    "mac 地址": [("ifconfig", W_ANSWER), ("arp", W_TOPIC)],
    "网关": [("route", W_ANSWER), ("netstat", W_TOPIC)],
    "dns 服务器": [("scutil", W_ANSWER), ("networksetup", W_TOPIC)],
    "wifi 密码": [("security", W_ANSWER)],

    # ================= 进程（补充）=================
    "暂停进程": [("kill", W_TOPIC), ("suspend", W_TOPIC), ("stop", W_HINT)],
    "继续进程": [("kill", W_TOPIC), ("continue", W_TOPIC)],
    "进程优先级": [("nice", W_ANSWER), ("renice", W_ANSWER)],
    "降低优先级": [("nice", W_ANSWER), ("renice", W_TOPIC)],
    "提高优先级": [("nice", W_ANSWER), ("renice", W_TOPIC)],
    "最耗内存": [("top", W_ANSWER), ("ps", W_TOPIC), ("footprint", W_TOPIC)],
    "占 cpu 最高": [("top", W_ANSWER), ("ps", W_TOPIC)],
    "最多的进程": [("top", W_ANSWER), ("ps", W_TOPIC)],

    # ================= 文本（补充）=================
    "第一列": [("awk", W_ANSWER), ("cut", W_ANSWER)],
    "第几列": [("awk", W_ANSWER), ("cut", W_ANSWER)],
    "按列取": [("awk", W_ANSWER), ("cut", W_ANSWER)],
    "某一列": [("awk", W_ANSWER), ("cut", W_ANSWER)],
    "求和": [("awk", W_ANSWER)],
    "格式化输出": [("awk", W_TOPIC), ("column", W_ANSWER), ("printf", W_TOPIC)],
    "去掉空行": [("grep", W_TOPIC), ("sed", W_ANSWER)],
    "空行": [("grep", W_TOPIC), ("sed", W_TOPIC)],
    "忽略大小写": [("grep", W_ANSWER)],
    "显示行号": [("nl", W_ANSWER), ("grep", W_TOPIC), ("cat", W_HINT)],
    "行号": [("nl", W_ANSWER), ("grep", W_TOPIC)],
    "倒序": [("sort", W_TOPIC), ("rev", W_ANSWER), ("tac", W_TOPIC)],
    "反序": [("sort", W_TOPIC), ("rev", W_ANSWER)],
    "按时间排": [("ls", W_ANSWER), ("sort", W_TOPIC)],
    "按大小排": [("ls", W_ANSWER), ("du", W_TOPIC), ("sort", W_TOPIC)],
    "base64": [("base64", W_ANSWER), ("uuencode", W_TOPIC)],
    "去掉重复行": [("uniq", W_ANSWER), ("sort", W_HINT)],
    "只保留不同": [("uniq", W_ANSWER)],

    # ================= 磁盘（补充）=================
    "最大的文件": [("du", W_ANSWER), ("find", W_TOPIC)],
    "占用最多": [("du", W_ANSWER)],
    "大文件": [("du", W_TOPIC), ("find", W_ANSWER)],
    "磁盘读写": [("iostat", W_ANSWER)],
    "io 性能": [("iostat", W_ANSWER)],
    "挂载点": [("mount", W_ANSWER), ("df", W_TOPIC)],
    "卸载": [("umount", W_ANSWER), ("diskutil", W_TOPIC)],

    # ================= 第 3 轮扩充（配合速查表 262 条）=================
    # ---- 压缩格式：光靠"解压"分不清 gz 和 zip，必须认格式后缀 ----
    "gz": [("gzip", W_ANSWER), ("gunzip", W_TOPIC)],
    "gzip 解压": [("gunzip", W_ANSWER), ("gzip", W_TOPIC)],
    "解压 gz": [("gunzip", W_ANSWER), ("gzip", W_ANSWER)],
    "tar.gz": [("tar", W_ANSWER), ("gzip", W_TOPIC)],
    "zip 包": [("zip", W_ANSWER), ("unzip", W_TOPIC)],
    "解压 zip": [("unzip", W_ANSWER), ("ditto", W_TOPIC)],

    # ---- 进程 ----
    "进程号": [("pgrep", W_ANSWER), ("ps", W_TOPIC), ("pid", W_HINT)],
    "查进程号": [("pgrep", W_ANSWER), ("ps", W_TOPIC)],
    "进程 id": [("pgrep", W_ANSWER), ("ps", W_TOPIC)],
    "平均负载": [("uptime", W_ANSWER), ("w", W_TOPIC), ("top", W_TOPIC)],
    "系统负载": [("uptime", W_ANSWER), ("top", W_TOPIC), ("w", W_TOPIC)],
    "占用 cpu": [("top", W_ANSWER), ("ps", W_TOPIC)],
    "占了多少 cpu": [("top", W_ANSWER), ("ps", W_TOPIC)],
    "调用栈": [("sample", W_ANSWER), ("spindump", W_TOPIC)],
    "卡死": [("sample", W_ANSWER), ("spindump", W_TOPIC), ("kill", W_HINT)],
    "优先级": [("nice", W_ANSWER), ("renice", W_ANSWER)],

    # ---- 目录 / 路径 ----
    "目录部分": [("dirname", W_ANSWER), ("basename", W_TOPIC)],
    "文件名部分": [("basename", W_ANSWER), ("dirname", W_TOPIC)],
    "取目录": [("dirname", W_ANSWER)],
    "绝对路径": [("realpath", W_ANSWER), ("pwd", W_TOPIC)],
    "硬链接": [("ln", W_ANSWER)],
    "软链接": [("ln", W_ANSWER), ("symlink", W_TOPIC)],
    "符号链接": [("ln", W_ANSWER), ("symlink", W_TOPIC)],
    "锁定文件": [("chflags", W_ANSWER), ("uchg", W_HINT)],
    "不能删除": [("chflags", W_ANSWER), ("uchg", W_TOPIC)],
    "标志位": [("chflags", W_ANSWER), ("ls", W_TOPIC)],
    "详细属性": [("stat", W_ANSWER), ("ls", W_TOPIC)],
    "文件属性": [("stat", W_ANSWER), ("xattr", W_TOPIC)],
    "扩展属性": [("xattr", W_ANSWER)],
    "创建时间": [("stat", W_ANSWER), ("touch", W_TOPIC)],

    # ---- 文本 ----
    "空行": [("sed", W_ANSWER), ("grep", W_TOPIC), ("tr", W_HINT)],
    "删掉空行": [("sed", W_ANSWER), ("grep", W_TOPIC)],
    "第几列": [("cut", W_ANSWER), ("awk", W_ANSWER)],
    "按列切": [("cut", W_ANSWER), ("awk", W_TOPIC)],
    "十六进制": [("xxd", W_ANSWER), ("hexdump", W_ANSWER), ("od", W_TOPIC)],
    "hex": [("xxd", W_ANSWER), ("hexdump", W_TOPIC)],
    "json": [("jq", W_ANSWER), ("plutil", W_TOPIC)],
    "plist": [("plutil", W_ANSWER), ("plistbuddy", W_TOPIC), ("defaults", W_TOPIC)],
    "sqlite": [("sqlite3", W_ANSWER)],
    "数据库": [("sqlite3", W_TOPIC)],
    "gbk": [("iconv", W_ANSWER)],
    "utf8": [("iconv", W_ANSWER)],
    "utf-8": [("iconv", W_ANSWER)],
    "乱码": [("iconv", W_ANSWER), ("file", W_TOPIC)],
    "转码": [("iconv", W_ANSWER), ("afconvert", W_TOPIC)],

    # ---- 网络 ----
    "post 请求": [("curl", W_ANSWER)],
    "发请求": [("curl", W_ANSWER)],
    "请求头": [("curl", W_ANSWER)],
    "上传文件": [("curl", W_ANSWER), ("scp", W_TOPIC), ("rsync", W_HINT)],
    "端口是否开放": [("nc", W_ANSWER), ("lsof", W_TOPIC)],
    "端口通不通": [("nc", W_ANSWER), ("ping", W_HINT)],
    "探测端口": [("nc", W_ANSWER)],
    "路由表": [("netstat", W_ANSWER), ("route", W_ANSWER)],
    "网关": [("route", W_ANSWER), ("netstat", W_TOPIC)],
    "arp": [("arp", W_ANSWER)],
    "wifi": [("networksetup", W_ANSWER), ("airport", W_TOPIC)],
    "无线网": [("networksetup", W_ANSWER)],
    "代理": [("networksetup", W_ANSWER), ("curl", W_HINT)],
    "端口转发": [("ssh", W_ANSWER)],
    "公网 ip": [("curl", W_ANSWER)],

    # ---- 系统 ----
    "核数": [("sysctl", W_ANSWER), ("hw", W_HINT)],
    "cpu 型号": [("sysctl", W_ANSWER), ("system_profiler", W_TOPIC)],
    "架构": [("arch", W_ANSWER), ("uname", W_TOPIC)],
    "系统版本": [("sw_vers", W_ANSWER), ("uname", W_ANSWER)],
    "macos 版本": [("sw_vers", W_ANSWER)],
    "休眠": [("pmset", W_ANSWER), ("caffeinate", W_ANSWER)],
    "不休眠": [("caffeinate", W_ANSWER), ("pmset", W_TOPIC)],
    "不进入休眠": [("caffeinate", W_ANSWER), ("pmset", W_TOPIC)],
    "电池": [("pmset", W_ANSWER), ("system_profiler", W_ANSWER), ("ioreg", W_TOPIC)],
    "uuid": [("uuidgen", W_ANSWER)],
    "系统日志": [("log", W_ANSWER), ("syslog", W_ANSWER), ("logger", W_TOPIC)],
    "内核日志": [("dmesg", W_ANSWER)],
    "启动项": [("launchctl", W_ANSWER), ("launchd", W_TOPIC)],
    "重启服务": [("launchctl", W_ANSWER)],
    "安装软件": [("installer", W_ANSWER), ("softwareupdate", W_TOPIC)],
    "系统更新": [("softwareupdate", W_ANSWER)],
    "退出码": [("zshbuiltins", W_ANSWER), ("echo", W_HINT)],
    "退出状态": [("zshbuiltins", W_ANSWER)],
    "内置命令": [("zshbuiltins", W_ANSWER), ("builtin", W_TOPIC)],
    "别名": [("zshbuiltins", W_ANSWER), ("alias", W_TOPIC)],
    "起别名": [("zshbuiltins", W_ANSWER)],
    "环境变量": [("env", W_ANSWER), ("printenv", W_ANSWER), ("zshbuiltins", W_TOPIC)],

    # ---- macOS 特色 ----
    "图片尺寸": [("sips", W_ANSWER)],
    "图片转换": [("sips", W_ANSWER)],
    "缩略图": [("qlmanage", W_ANSWER), ("sips", W_TOPIC)],
    "音频信息": [("afinfo", W_ANSWER)],
    "音频转换": [("afconvert", W_ANSWER)],
    "播放音频": [("afplay", W_ANSWER)],
    "朗读": [("say", W_ANSWER)],
    "通知": [("osascript", W_ANSWER), ("notifyutil", W_TOPIC)],
    "弹窗": [("osascript", W_ANSWER)],
    "ocr": [("shortcuts", W_TOPIC), ("textutil", W_TOPIC)],
}

# 口语词归一（先做一遍替换再做短语匹配）。
# 注意：只删真正的语气填充词。`哪个`/`什么`/`怎么` 不能删——
# 它们本身是词典短语的一部分（"命令在哪个路径"），删了反而匹配不上。
PHRASE_FIX: dict[str, str] = {
    "怎么看": "查看", "怎么查看": "查看", "如何查看": "查看", "怎么看到": "查看",
    "查一下": "查看", "看一下": "查看",
    "怎么杀": "杀掉", "怎么关掉": "杀掉", "怎么删": "删除", "怎么删除": "删除",
    "请问": "", "我想": "", "帮我": "", "一下子": "", "一个": "", "如何": "",
}

# 英文短语 -> 英文词（英文查询时的同义扩展，权重偏低，只做兜底）
E2E_W: dict[str, list[tuple[str, float]]] = {
    "archive": [("tar", W_TOPIC + 0.6), ("cpio", W_HINT)],
    "extract": [("tar", W_TOPIC), ("gunzip", W_TOPIC), ("unzip", W_TOPIC)],
    "compress": [("gzip", W_TOPIC), ("bzip2", W_HINT)],
    "decompress": [("gunzip", W_ANSWER), ("tar", W_TOPIC)],
    "port": [("lsof", W_TOPIC + 0.6), ("netstat", W_TOPIC + 0.6)],
    "listening": [("lsof", W_TOPIC), ("netstat", W_TOPIC)],
    "process": [("ps", W_TOPIC), ("kill", W_HINT), ("top", W_HINT)],
    "terminate": [("kill", W_ANSWER), ("pkill", W_TOPIC)],
    "folder": [("mkdir", W_TOPIC), ("ls", W_HINT)],
    "directory": [("mkdir", W_TOPIC), ("ls", W_TOPIC)],
    "recursive": [("find", W_TOPIC), ("grep", W_HINT)],
    "hostname": [("hostname", W_ANSWER), ("scutil", W_HINT)],
    "symlink": [("ln", W_ANSWER), ("symlink", W_TOPIC)],
    "checksum": [("shasum", W_ANSWER), ("md5", W_TOPIC), ("cksum", W_TOPIC)],
    "passwordless": [("ssh-keygen", W_ANSWER), ("ssh-copy-id", W_TOPIC)],
    "follow": [("tail", W_ANSWER), ("log", W_HINT)],
    "empty": [("touch", W_TOPIC + 0.5)],
    "count": [("wc", W_TOPIC)],
    "lines": [("wc", W_TOPIC)],
    "connections": [("netstat", W_TOPIC + 0.5), ("lsof", W_TOPIC + 0.5)],
    "connection": [("netstat", W_TOPIC)],
    "mount": [("mount", W_ANSWER), ("diskutil", W_HINT)],
    "unmount": [("umount", W_ANSWER)],
    "permission": [("chmod", W_TOPIC)],
    "ownership": [("chown", W_ANSWER)],
    "owner": [("chown", W_ANSWER)],
    "monitor": [("top", W_TOPIC), ("watch", W_TOPIC)],
    "traffic": [("tcpdump", W_TOPIC), ("nettop", W_TOPIC)],
}

_MAX_KEY = max(len(k) for k in Z2E_W)


def _normalize(query: str) -> str:
    q = query.lower().strip()
    for a, b in sorted(PHRASE_FIX.items(), key=lambda kv: -len(kv[0])):
        if a in q:
            q = q.replace(a, b)
    return q


def _match_phrases(q: str) -> list[str]:
    """从左到右最长匹配。

    早期版本是"全局最长优先 + 消费"，出现过 `查看文件尾部` 被
    `查看文件` 抢先切走、结果返回 cat 而不是 tail 的问题。
    改为固定从左到右扫描后，切分结果可预测，词典也好调。
    """
    out: list[str] = []
    i = 0
    n = len(q)
    while i < n:
        hit = ""
        for L in range(min(_MAX_KEY, n - i), 1, -1):
            cand = q[i : i + L]
            if cand in Z2E_W:
                hit = cand
                break
        if hit:
            out.append(hit)
            i += len(hit)
        else:
            i += 1
    return out


def expand_w(query: str) -> dict[str, float]:
    """查询 -> {英文词: 权重}。中英文查询都走这里。"""
    if not query:
        return {}
    q = _normalize(query)
    out: dict[str, float] = {}

    def put(term: str, w: float) -> None:
        if w > out.get(term, 0.0):
            out[term] = w

    for key in _match_phrases(q):
        for term, w in Z2E_W[key]:
            put(term, w)

    # 英文查询的同义兜底（按空格/标点切词）
    for raw in re.split(r"[^a-z0-9._+-]+", q):
        if len(raw) >= 3 and raw in E2E_W:
            for term, w in E2E_W[raw]:
                put(term, w)
    return out


def expand(query: str) -> str:
    """兼容旧接口：返回空格分隔的英文词串（按权重降序）。"""
    w = expand_w(query)
    return " ".join(sorted(w, key=lambda t: -w[t]))


# 旧字段名，供 build_static 等外部引用（纯词表，不带权重）
Z2E: dict[str, list[str]] = {k: [w for w, _ in v] for k, v in Z2E_W.items()}


if __name__ == "__main__":
    import sys

    for s in sys.argv[1:]:
        w = expand_w(s)
        top = ", ".join(f"{t}:{v:g}" for t, v in sorted(w.items(), key=lambda kv: -kv[1])[:12])
        print(f"{s}\n  ->  {top}")
