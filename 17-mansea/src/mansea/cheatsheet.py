"""中文命令速查表 —— 这个项目里"人写的知识"的正式载体。

为什么要有它：
`concept.py` 能把 NAME 行自动译成中文，覆盖全部 2706 篇，但它只会说
man 页自己说过的话。`tr` 的 NAME 行是 "translate characters"，
用户问"去掉回车符"永远匹配不上——这个知识只有人能补。

所以这一层是手工标的，按**命令**组织（命令是有限的），
不是按**问法**组织（问法是无限的）。它同时有两个用途：
1. 直接渲染成 `site/cheatsheet.html`，给人看
2. 反过来喂给检索：把每条意图的中文 bigram 打进对应命令的概念索引

条目格式：(中文意图, 命令, 常用参数, 一句话说明)
"""

from __future__ import annotations

# (意图, 命令, 常用参数, 说明)
CHEATS: list[tuple[str, str, str, str]] = [
    # ---------- 文件 / 目录 ----------
    ("列出目录内容", "ls", "ls -lah", "人可读大小、含隐藏文件"),
    ("只列出目录不列文件", "ls", "ls -d */", "只看子目录"),
    ("按时间排文件", "ls", "ls -lt", "最近修改的在前"),
    ("按大小排文件", "ls", "ls -lS", "最大的在前"),
    ("新建目录", "mkdir", "mkdir -p a/b/c", "-p 递归创建、已存在不报错"),
    ("删除空目录", "rmdir", "rmdir d", "非空目录用 rm -r"),
    ("当前在哪个目录", "pwd", "pwd", "打印当前工作目录"),
    ("切换目录", "cd", "cd ..", ".. 上级，- 回上一次的目录"),
    ("创建空文件 / 改修改时间", "touch", "touch f.txt", "文件不存在就新建"),
    ("复制文件", "cp", "cp -R src dst", "-R 递归复制目录"),
    ("移动 / 重命名", "mv", "mv a b", "同目录内移动即重命名"),
    ("删除文件", "rm", "rm -rf dir", "-rf 强制递归，删了就没了"),
    ("创建软链接", "ln", "ln -s target link", "-s 符号链接"),
    ("查看文件类型", "file", "file f", "不看后缀，看内容魔数"),
    ("查看文件前几行", "head", "head -n 20 f", "默认 10 行"),
    ("查看文件后几行", "tail", "tail -n 20 f", "-f 实时跟随"),
    ("实时跟踪日志", "tail", "tail -f /var/log/system.log", "Ctrl-C 退出"),
    ("分页查看文件", "less", "less f", "空格翻页，q 退出"),
    ("一次看多个文件", "less", "less a.txt b.txt", ":n 下一个文件"),
    ("合并 / 拼接文件", "cat", "cat a b > c", "> 会覆盖，>> 追加"),
    ("分割大文件", "split", "split -l 1000 big part_", "按行切，默认 1000 行"),
    ("按列合并文件", "paste", "paste a b", "横向拼接"),
    ("比较两个文件", "diff", "diff -u a b", "-u 输出统一格式"),
    ("比较文件是否完全一样", "cmp", "cmp a b", "只报第一个不同处"),
    ("清空文件内容", "cp", "cp /dev/null f", "长度变 0 但文件还在"),

    # ---------- 查找 / 搜索 ----------
    ("按名字找文件", "find", "find . -name '*.log'", "-iname 忽略大小写"),
    ("按类型找文件", "find", "find . -type d -maxdepth 2", "-type d 目录 f 文件"),
    ("找最近改过的文件", "find", "find . -mtime -1", "-1 表示一天内"),
    ("找大文件", "find", "find . -size +100M", "+100M 大于 100MB"),
    ("在文件内容里搜索", "grep", "grep -rn 'pat' .", "-r 递归 -n 行号"),
    ("忽略大小写搜索", "grep", "grep -i pat f", "-i 忽略大小写"),
    ("只显示不匹配的行", "grep", "grep -v pat f", "-v 反向匹配"),
    ("用正则搜索", "grep", "grep -E 'a|b' f", "-E 扩展正则"),
    ("Spotlight 搜文件", "mdfind", "mdfind 'kind:pdf 报告'", "走系统索引，快"),
    ("命令在哪个路径", "which", "which python3", "只找 PATH 里的"),
    ("命令相关的所有文件", "whereis", "whereis python3", "含手册、源码"),

    # ---------- 文本处理 ----------
    ("统计行数 / 字数", "wc", "wc -l f", "-l 行 -w 词 -c 字节"),
    ("排序", "sort", "sort -n f", "-n 按数值 -r 倒序"),
    ("去重（相邻行）", "uniq", "sort f | uniq -c", "-c 顺便计数，必须先排序"),
    ("统计重复次数", "uniq", "sort f | uniq -c | sort -rn", "先排序再去重计数"),
    ("取第几列", "awk", "awk '{print $1}'", "$0 整行，$1 第一列"),
    ("按列切分", "cut", "cut -d, -f1", "-d 分隔符 -f 字段"),
    ("文本替换", "sed", "sed -i '' 's/a/b/g' f", "macOS 的 -i 必须带参数"),
    ("字符替换 / 删除", "tr", "tr -d '\\r' < f", "-d 删除指定字符"),
    ("去掉回车符（CRLF→LF）", "tr", "tr -d '\\r' < f > out", "Windows 换行转 Unix"),
    ("把 tab 换成空格", "expand", "expand -t 4 f", "-t 指定 tab 宽度"),
    ("显示行号", "nl", "nl -ba f", "-ba 空行也编号"),
    ("反转每行字符", "rev", "rev f", "逐字符倒过来"),
    ("编码转换", "iconv", "iconv -f GBK -t UTF-8 f", "-f 源 -t 目标"),
    ("查看文件编码 / 字符集", "file", "file -I f", "-I 输出 MIME 与字符集"),
    ("base64 编解码", "base64", "base64 -i f -o out", "-D 解码"),
    ("对齐成表格", "column", "column -t -s, f", "-t 自动对齐"),

    # ---------- 压缩 / 归档 ----------
    ("打包目录", "tar", "tar -czf a.tar.gz dir", "c 创建 z gzip f 文件"),
    ("解包 tar.gz", "tar", "tar -xzf a.tar.gz", "x 解包"),
    ("查看压缩包内容", "tar", "tar -tzf a.tar.gz", "t 列表，不解压"),
    ("gzip 压缩", "gzip", "gzip -k f", "-k 保留原文件"),
    ("gzip 解压", "gunzip", "gunzip f.gz", "等价 gzip -d"),
    ("打 zip 包", "zip", "zip -r a.zip dir", "-r 递归"),
    ("解 zip 包", "unzip", "unzip a.zip", "-l 先看内容"),
    ("macOS 上打 zip（保元数据）", "ditto", "ditto -ck --sequesterRsrc dir a.zip", "保留资源分支"),

    # ---------- 权限 / 属性 ----------
    ("修改权限", "chmod", "chmod 755 f", "u+x 给属主加执行"),
    ("让脚本可执行", "chmod", "chmod +x s.sh", "之后 ./s.sh 就能跑"),
    ("修改所有者", "chown", "chown user:group f", "需要 sudo"),
    ("查看 / 改扩展属性", "xattr", "xattr -l f", "-d 删除某属性"),
    ("隐藏文件（Finder 不可见）", "chflags", "chflags hidden f", "nohidden 取消"),

    # ---------- 进程 ----------
    ("查看进程列表", "ps", "ps aux", "aux 全量 BSD 风格"),
    ("实时看进程", "top", "top -o cpu", "-o 指定排序字段"),
    ("按名字杀进程", "pkill", "pkill -f 'node app'", "-f 匹配整条命令行"),
    ("杀进程（按 PID）", "kill", "kill -9 1234", "-9 强杀，收不回来"),
    ("断开终端后继续跑", "nohup", "nohup cmd &", "输出默认进 nohup.out"),
    ("后台 / 前台切换", "bg", "bg %1", "Ctrl-Z 暂停后 bg 转后台"),
    ("调整进程优先级", "renice", "renice -n 5 -p 1234", "数值越大越谦让"),
    ("以指定优先级启动", "nice", "nice -n 10 cmd", "正值降低优先级"),
    ("命令跑多久", "time", "time cmd", "输出 real/user/sys 三项"),

    # ---------- 系统 ----------
    ("查看磁盘空间", "df", "df -h", "-h 人可读"),
    ("查看目录大小", "du", "du -sh *", "-s 汇总 -h 人可读"),
    ("找最占空间的文件", "du", "du -ah . | sort -rh | head", "组合技"),
    ("查看内存", "vm_stat", "vm_stat", "按页显示，乘 4096 得字节"),
    ("系统跑了多久", "uptime", "uptime", "含 1/5/15 分钟负载"),
    ("内核 / 系统版本", "uname", "uname -a", "-a 全部信息"),
    ("macOS 版本", "sw_vers", "sw_vers", "productVersion 是版本号"),
    ("硬件信息", "system_profiler", "system_profiler SPHardwareDataType", "接 -json 输出 JSON"),
    ("电池循环次数", "system_profiler", "system_profiler SPPowerDataType", "cycle count 一栏"),
    ("序列号", "system_profiler", "system_profiler SPHardwareDataType | grep Serial", "或用 ioreg"),
    ("查看内核参数", "sysctl", "sysctl -a | grep cpu", "改参数要 sudo"),
    ("环境变量", "env", "env | grep PATH", "printenv 看单个"),
    ("读写系统偏好", "defaults", "defaults read com.apple.finder", "改完要 killall"),

    # ---------- 网络 ----------
    ("查看端口占用", "lsof", "lsof -i :8080", "-i 按端口/协议过滤"),
    ("谁在监听端口", "netstat", "netstat -an | grep LISTEN", "macOS 上 -an 常用"),
    ("看本机 IP", "ifconfig", "ifconfig en0", "en0 一般是有线/主无线"),
    ("查看网络接口", "ifconfig", "ifconfig -a", "含所有虚拟网卡"),
    ("测试连通性", "ping", "ping -c 4 host", "-c 限制次数"),
    ("查域名解析", "dig", "dig example.com", "+short 只要结果"),
    ("查路由", "route", "route -n get default", "看默认网关"),
    ("抓包", "tcpdump", "tcpdump -i en0 port 80", "-w 写 pcap 文件"),
    ("下载文件", "curl", "curl -O url", "-L 跟随跳转"),
    ("测网速", "networkquality", "networkquality", "系统自带，测上下行"),

    # ---------- 远程 ----------
    ("远程登录", "ssh", "ssh user@host", "-p 指定端口"),
    ("配免密登录", "ssh-copy-id", "ssh-copy-id user@host", "先 ssh-keygen"),
    ("生成密钥", "ssh-keygen", "ssh-keygen -t ed25519", "ed25519 短且安全"),
    ("传文件到服务器", "scp", "scp f user@host:/tmp", "-r 传目录"),
    ("两台机器同步目录", "rsync", "rsync -avz src/ host:dst/", "-a 保属性 -z 压缩"),
    ("增量备份", "rsync", "rsync -a --delete src/ dst/", "--delete 会删目标端多余的"),

    # ---------- 管道 / 技巧 ----------
    ("把输出当参数传给下一个命令", "xargs", "find . -name '*.log' | xargs rm", "-0 配 -print0 处理空格"),
    ("输出同时存到文件", "tee", "cmd | tee out.log", "屏幕和文件都有"),
    ("清屏", "clear", "clear", "或 Ctrl-L"),
    ("历史命令", "history", "history | grep ssh", "fc 可编辑重跑"),
    ("给命令起别名", "alias", "alias ll='ls -lah'", "写进 ~/.zshrc 才持久"),
    ("重复执行命令", "watch", "watch -n 2 cmd", "macOS 无内置，用 while 循环"),
    ("等待几秒", "sleep", "sleep 5", "脚本里常用"),

    # ---------- 安全 ----------
    ("算校验和", "shasum", "shasum -a 256 f", "md5 用 md5 命令"),
    ("生成随机密码", "openssl", "openssl rand -base64 24", "24 字节约 32 字符"),
    ("钥匙串操作", "security", "security find-generic-password -s name", "系统钥匙串命令行"),
    ("代码签名", "codesign", "codesign -s 'Apple Dev' app", "开发机必备"),
    ("证书查看", "openssl", "openssl x509 -in c.pem -text", "看有效期和颁发者"),

    # ---------- 磁盘 ----------
    ("挂载 / 卸载磁盘", "diskutil", "diskutil list", "unmountDisk 卸载整盘"),
    ("制作镜像", "hdiutil", "hdiutil create -size 1g a.dmg", "也可挂载/转换"),
    ("磁盘读写监控", "iostat", "iostat -w 2", "每 2 秒刷新"),

    # ========== 第 3 轮扩充：文件 / 目录 ==========
    ("取文件名部分", "basename", "basename /a/b/c.txt .txt", "第二个参数可去掉后缀"),
    ("取目录部分", "dirname", "dirname /a/b/c.txt", "只留路径不要文件名"),
    ("取绝对路径", "realpath", "realpath f", "顺带解析符号链接"),
    ("复制目录并保持属性", "cp", "cp -a src dst", "-a 等价 -pR"),
    ("复制时显示进度", "rsync", "rsync -ah --progress src/ dst/", "本地复制也能看进度"),
    ("创建硬链接", "ln", "ln f g", "不加 -s 就是硬链接，不能跨盘"),
    ("批量建多个目录", "mkdir", "mkdir -p dir{1..10}", "花括号展开"),
    ("改文件的修改时间", "touch", "touch -t 202601011200 f", "-t 指定具体时间"),
    ("统计目录里有多少文件", "find", "find . -type f | wc -l", "管道给 wc 计数"),
    ("递归改权限（目录和文件分开）", "chmod", "find . -type d -exec chmod 755 {} +", "目录要 x 才能进"),
    ("改默认权限掩码", "umask", "umask 022", "022 是最常用的值"),
    ("看文件被哪个进程占用", "lsof", "lsof f", "-p 按进程号 -c 按进程名"),
    ("看文件的标志位", "ls", "ls -lO f", "-O 显示 chflags 设的标志"),

    # ========== 查找 / 搜索 ==========
    ("搜索并高亮带行号", "grep", "grep -rn --color pat .", "--color=always 保留颜色"),
    ("看匹配行的上下文", "grep", "grep -C 3 pat f", "-A 后面几行 -B 前面几行"),
    ("只输出匹配到的部分", "grep", "grep -o 'pat' f", "-o 只留匹配串"),
    ("统计匹配了多少行", "grep", "grep -c pat f", "-c 只给个数"),
    ("多关键字任一匹配", "grep", "grep -E 'a|b|c' f", "-E 扩展正则"),
    ("按权限找文件", "find", "find . -perm 644", "-perm 按权限位"),
    ("找到之后执行命令", "find", "find . -name '*.log' -exec rm {} +", "+ 比 \\; 少起进程"),
    ("找到之后直接删", "find", "find . -name '*.tmp' -delete", "-delete 比 -exec rm 快"),
    ("限制查找深度", "find", "find . -maxdepth 2 -name '*.md'", "-maxdepth 限制层数"),
    ("按大小排序看目录", "du", "du -sh * | sort -h", "-h 人可读排序"),
    ("并行跑（xargs 多进程）", "xargs", "xargs -P 4 -I{} cmd {}", "-P 指定并发数"),
    ("处理带空格的文件名", "xargs", "find . -print0 | xargs -0 cmd", "-print0 与 -0 配对"),
    ("秒搜文件名（走索引）", "locate", "locate name", "需先跑 locate.updatedb"),

    # ========== 文本处理 ==========
    ("只看文件中间某几行", "sed", "sed -n '10,20p' f", "-n 关默认输出 p 打印"),
    ("删除指定行", "sed", "sed '3d' f", "3d 删第 3 行，2,5d 删区间"),
    ("awk 按分隔符取列", "awk", "awk -F, '{print $2}' f", "-F 指定分隔符"),
    ("awk 对某一列求和", "awk", "awk '{s+=$1} END{print s}' f", "END 块最后执行"),
    ("awk 按条件过滤行", "awk", "awk '$3 > 100' f", "条件写在花括号外"),
    ("排序并去重", "sort", "sort -u f", "-u 等价 sort | uniq"),
    ("按第几列排序", "sort", "sort -k2,2n f", "-k 指定列 n 按数值"),
    ("只看重复出现的行", "uniq", "uniq -d f", "-d 只输出重复行"),
    ("压缩连续的空行", "tr", "tr -s '\\n' < f", "-s 挤压重复字符"),
    ("大小写互相转换", "tr", "tr 'a-z' 'A-Z' < f", "字符集一一映射"),
    ("按字符位置切", "cut", "cut -c1-10 f", "-c 按字符 -f 按字段"),
    ("把长行折成固定宽度", "fold", "fold -w 80 f", "-w 指定宽度"),
    ("重新排版段落", "fmt", "fmt -w 70 f", "写纯文本时好使"),
    ("去掉行尾空白", "sed", "sed 's/[[:space:]]*$//' f", "清理脏数据"),
    ("去掉注释行和空行", "grep", "grep -vE '^\\s*(#|$)' f", "看配置文件常用"),
    ("十六进制查看文件", "hexdump", "hexdump -C f | head", "-C 带 ASCII 对照"),
    ("十六进制转回文本", "xxd", "xxd -r -p f", "-r 反向 -p 纯 hex"),
    ("处理 json 数据", "jq", "jq '.items[0].name' f.json", "格式化/取值/过滤"),
    ("看 plist 内容", "plutil", "plutil -convert json -o - f.plist", "-o - 输出到屏幕"),
    ("读写 plist 配置", "plistbuddy", "plistbuddy -c 'Print' f.plist", "系统配置文件常用"),
    ("看 sqlite 里有哪些表", "sqlite3", "sqlite3 a.db '.tables'", ".schema 看表结构"),
    ("在 sqlite 里执行 sql", "sqlite3", "sqlite3 -header -column a.db 'select 1'", "输出更整齐"),
    ("看文件有多少字节", "wc", "wc -c f", "-c 字节 -m 字符"),
    ("去掉 Windows 换行符", "sed", "sed 's/\\r$//' f", "等价 tr -d '\\r'"),
    ("找出两个文件共有的行", "comm", "comm -12 a b", "两个文件必须先排序"),
    ("按公共字段合并两个文件", "join", "join a b", "数据库式的 join"),

    # ========== 系统信息 / 监控 ==========
    ("查看 cpu 核数", "sysctl", "sysctl -n hw.ncpu", "-n 只要值不要键名"),
    ("查看内存总量", "sysctl", "sysctl -n hw.memsize", "单位是字节"),
    ("查看 cpu 型号", "sysctl", "sysctl -n machdep.cpu.brand_string", "Intel/Apple 都支持"),
    ("看机器架构", "arch", "arch", "arm64 或 x86_64"),
    ("看负载和登录用户", "w", "w", "首行就是 1/5/15 分钟负载"),
    ("看最近登录记录", "last", "last -10", "读系统登录日志"),
    ("看内核日志", "dmesg", "dmesg | tail", "启动与硬件信息"),
    ("读统一日志（最近一小时）", "log", "log show --last 1h", "--predicate 精确过滤"),
    ("实时看系统日志", "log", "log stream --level info", "Ctrl-C 退出"),
    ("写一条系统日志", "logger", "logger 'hello'", "会进系统日志库"),
    ("看内存压力", "memory_pressure", "memory_pressure", "判断是否吃紧"),
    ("清内存缓存（调试用）", "purge", "purge", "会掉帧，别在生产上跑"),
    ("看每个进程的磁盘 io", "iotop", "iotop -C 3 5", "基于 dtrace"),
    ("看每个进程的网络流量", "nettop", "nettop -m tcp", "按流量排序"),
    ("看文件系统实时访问", "fs_usage", "sudo fs_usage | grep path", "需要 root"),
    ("看进程的系统调用", "dtruss", "sudo dtruss -p 1234", "需 root 且受 SIP 限制"),
    ("看进程的内存分布", "vmmap", "vmmap 1234", "查内存泄漏"),
    ("抓进程的调用栈", "sample", "sample 1234 -f out.txt", "卡死时最有用"),
    ("生成性能采样报告", "spindump", "sudo spindump 1234 5", "需要 root"),
    ("看实时耗电", "powermetrics", "sudo powermetrics --samplers tasks", "需要 root"),
    ("看电源和电池设置", "pmset", "pmset -g", "-g batt 只看电池"),
    ("阻止 mac 休眠", "caffeinate", "caffeinate -dims &", "d 显示器 i 系统 s 睡眠"),
    ("设定时开关机", "pmset", "pmset repeat wakeorpoweron MTWRF 07:00:00", "系统级定时"),
    ("看休眠唤醒历史", "pmset", "pmset -g log", "排查睡不醒"),
    ("查看 / 改主机名", "scutil", "scutil --get HostName", "--set 修改"),
    ("看 DNS 解析配置", "scutil", "scutil --dns", "看解析顺序"),
    ("清 DNS 缓存", "dscacheutil", "dscacheutil -flushcache", "改完 hosts 要清"),
    ("看系统启动项", "launchctl", "launchctl list | grep -v com.apple", "只列非系统的"),
    ("重启一个系统服务", "launchctl", "launchctl kickstart -k gui/$UID/svc", "kickstart 重启"),
    ("看时间机器状态", "tmutil", "tmutil status", "可删本地快照"),
    ("命令行装 pkg", "installer", "sudo installer -pkg a.pkg -target /", "适合自动化"),
    ("查 pkg 装了哪些文件", "pkgutil", "pkgutil --files com.x.y", "--forget 卸载记录"),
    ("查系统更新", "softwareupdate", "softwareupdate -l", "-i -a 全部安装"),
    ("切换 Xcode 路径", "xcode-select", "sudo xcode-select -s /path", "--install 装命令行工具"),
    ("看 Spotlight 索引状态", "mdutil", "mdutil -s /", "-i on/off 开关索引"),
    ("看文件的 Spotlight 元数据", "mdls", "mdls f", "全部 kMDItem 属性"),

    # ========== 网络 ==========
    ("发 post 请求", "curl", "curl -X POST -d 'a=1' url", "-d 表单体"),
    ("发 json 请求", "curl", "curl -H 'Content-Type: application/json' -d '{}' url", "-H 加请求头"),
    ("上传文件", "curl", "curl -F 'file=@a.txt' url", "-F multipart 表单"),
    ("只看响应头", "curl", "curl -I url", "-I 发 HEAD 请求"),
    ("测接口耗时", "curl", "curl -o /dev/null -s -w '%{time_total}' url", "-w 自定义输出"),
    ("断点续传下载", "curl", "curl -C - -O url", "-C - 接着上次下"),
    ("探测远程端口是否开放", "nc", "nc -vz host 80", "-z 只扫描不发数据"),
    ("临时监听一个端口", "nc", "nc -l 9999", "联调时当服务端"),
    ("看路由表", "netstat", "netstat -rn", "-r 路由 -n 不解析域名"),
    ("反查 ip 对应域名", "dig", "dig -x 8.8.8.8", "-x 查 PTR 记录"),
    ("简单查域名", "nslookup", "nslookup example.com", "dig 信息更全"),
    ("查域名注册信息", "whois", "whois example.com", "公开注册信息"),
    ("看局域网 arp 表", "arp", "arp -a", "顺便看邻居设备"),
    ("看当前 wifi 名字", "networksetup", "networksetup -getairportnetwork en0", "当前 SSID"),
    ("列出所有网络服务", "networksetup", "networksetup -listallnetworkservices", "Wi-Fi/以太网等"),
    ("命令行改代理", "networksetup", "networksetup -setwebproxy Wi-Fi 127.0.0.1 8080", "off 关闭"),
    ("查看出口公网 ip", "curl", "curl ifconfig.me", "依赖外部服务"),
    ("SSH 本地端口转发", "ssh", "ssh -L 8080:remote:80 user@host", "-L 本地 -R 远程"),
    ("SFTP 交互传文件", "sftp", "sftp user@host", "put/get 传文件"),
    ("看 SSH 最终生效配置", "ssh", "ssh -G host", "-G 打印合并后的配置"),

    # ========== 进程 / shell ==========
    ("按名字查进程号", "pgrep", "pgrep -f node", "pkill 是它的兄弟"),
    ("看后台任务列表", "zshbuiltins", "jobs -l", "内置命令，man zshbuiltins"),
    ("把后台任务调回前台", "zshbuiltins", "fg %1", "Ctrl-Z 先暂停"),
    ("让任务脱离终端", "zshbuiltins", "disown %1", "配合 & 使用"),
    ("限制资源上限", "zshbuiltins", "ulimit -n 4096", "-n 文件描述符数"),
    ("看上个命令的退出码", "zshbuiltins", "echo $?", "0 表示成功"),
    ("判断命令是内置还是外部", "zshbuiltins", "whence -v cmd", "比 which 更准"),
    ("设置环境变量", "zshbuiltins", "export PATH=$PATH:/new", "export 才传给子进程"),
    ("重新加载 shell 配置", "zshbuiltins", "source ~/.zshrc", "改完配置要 source"),
    ("录制终端会话", "script", "script session.log", "exit 结束录制"),
    ("让管道实时输出", "stdbuf", "stdbuf -oL cmd | tee f", "-oL 改成行缓冲"),
    ("看终端行列数", "stty", "stty size", "脚本里算宽度"),
    ("查终端能力", "tput", "tput cols", "做进度条用"),

    # ========== 安全 / 权限 ==========
    ("锁定文件防止误删", "chflags", "chflags uchg f", "nouchg 解锁"),
    ("算 md5", "md5", "md5 f", "shasum -a 256 更可靠"),
    ("算 crc 校验", "cksum", "cksum f", "简单完整性校验"),
    ("校验程序签名", "codesign", "codesign -vvv -d app", "-d 看签名详情"),
    ("Gatekeeper 检查", "spctl", "spctl -a -vv app", "--add 加白名单"),
    ("看 SIP 状态", "csrutil", "csrutil status", "改要进恢复模式"),
    ("查钥匙串证书", "security", "security find-certificate -a", "系统钥匙串命令行"),
    ("切换用户", "su", "su - user", "带 - 才带环境"),
    ("以管理员执行", "sudo", "sudo cmd", "sudo -i 进 root shell"),
    ("改文件的属组", "chgrp", "chgrp staff f", "chown 也能顺带改组"),
    ("看磁盘加密状态", "fdesetup", "fdesetup status", "FileVault 开关"),

    # ========== macOS 特色 ==========
    ("看图片尺寸信息", "sips", "sips -g pixelWidth f.png", "也能批量改尺寸"),
    ("图片格式转换", "sips", "sips -s format jpeg a.png --out a.jpg", "系统自带免安装"),
    ("看音频信息", "afinfo", "afinfo a.mp3", "时长、码率、声道"),
    ("音频转码", "afconvert", "afconvert -f m4af a.wav a.m4a", "系统自带"),
    ("命令行播放音频", "afplay", "afplay a.mp3", "Ctrl-C 停"),
    ("文本朗读", "say", "say 'hello'", "-v 选音色 -o 存文件"),
    ("发系统通知", "osascript", "osascript -e 'display notification \"hi\"'", "脚本提示用"),
    ("doc / rtf 转 txt", "textutil", "textutil -convert txt a.docx", "也支持 html"),
    ("命令行快速预览", "qlmanage", "qlmanage -p f", "-t 只生成缩略图"),
    ("看系统偏好设置值", "defaults", "defaults read -g", "-g 全局域"),
    ("列出所有偏好域", "defaults", "defaults domains", "逗号分隔输出"),
    ("看本地用户列表", "dscl", "dscl . -list /Users", "目录服务命令行"),

    # ========== 收尾补：HELD4 打出来的空白（这几条 man 页自己说不清）==========
    ("显示日历", "cal", "cal 2026", "-y 整年 -3 前后三个月"),
    ("算一个算式", "bc", "echo '3*7' | bc", "-l 启用小数，bc 是任意精度计算器"),
    ("表达式求值", "expr", "expr 3 + 7", "整数运算，注意运算符两边空格"),
    ("单位换算", "units", "units '1 km' 'mile'", "交互模式直接敲 units"),
    ("查看机器名", "hostname", "hostname", "scutil --get HostName 也行"),
    ("查看当前时区", "date", "date +%Z", "+%z 数值 +%Z 缩写"),
    ("按指定格式输出时间", "date", "date '+%F %T'", "strftime 格式串"),
    ("看文件最后修改时间", "stat", "stat -f '%Sm' f", "%Sm 修改时间 %SB 可读格式"),
    ("把多个文件合成一个", "cat", "cat a b c > all.txt", "顺序按参数给的顺序"),
    ("只保留文件开头若干行", "head", "head -n 100 f > out", "-c 按字节截"),
    ("把 a 全部替换成 b", "sed", "sed 's/a/b/g' f", "g 表示一行内全替换"),
    ("看文件属于什么类型", "file", "file f", "按内容魔数判断，不看后缀"),
    ("看 mac 的具体型号", "sysctl", "sysctl -n hw.model", "如 MacBookPro18,3"),
    ("限制进程的内存上限", "zshbuiltins", "ulimit -v 1048576", "单位 KB，shell 内置"),

    # ========== 第 5 轮补：HELD6 打出来的空白 ==========
    # 纪律：只补 HELD6（已经用过的验收集）暴露的洞，**一条都不补 HELD7 的题** ——
    # HELD7 是本轮唯一的干净读数，照它补词典等于当场把它变成调参集。
    ("把输出复制到剪贴板", "pbcopy", "cmd | pbcopy", "pbpaste 粘贴回来"),
    ("把剪贴板内容取出来", "pbpaste", "pbpaste > f", "常和 pbcopy 配对用"),
    ("软链接指向哪里", "readlink", "readlink link", "只解一层，不递归"),
    ("解析出文件的真实路径", "realpath", "realpath f", "解软链接和 .."),
    ("看共享内存和消息队列", "ipcs", "ipcs -m", "-m 共享内存 -q 消息队列"),
    ("清掉共享内存段", "ipcrm", "ipcrm -M shmkey", "配合 ipcs 用"),
    ("看硬件设备树", "ioreg", "ioreg -l | grep -i usb", "查 usb、电池循环计数"),
    ("查电池循环次数", "ioreg", "ioreg -r -c AppleSmartBattery", "看 CycleCount"),
    ("看防火墙开关", "socketfilterfw", "socketfilterfw --getglobalstate", "应用层防火墙"),
    ("开关防火墙", "socketfilterfw", "sudo socketfilterfw --setglobalstate on", "要 sudo"),
    ("看已加载的内核扩展", "kextstat", "kextstat | grep -v apple", "过滤系统自带"),
    ("管理内核扩展", "kmutil", "kmutil showloaded", "新版 macOS 取代 kextstat"),
]


def by_command() -> dict[str, list[tuple[str, str, str]]]:
    """命令 -> [(意图, 参数, 说明)]"""
    out: dict[str, list[tuple[str, str, str]]] = {}
    for intent, cmd, args, note in CHEATS:
        out.setdefault(cmd, []).append((intent, args, note))
    return out


def intents_of(cmd: str) -> list[str]:
    return [i for i, c, _a, _n in CHEATS if c == cmd]


if __name__ == "__main__":
    print(f"{len(CHEATS)} 条速查，覆盖 {len(by_command())} 个命令")
    for cmd, items in by_command().items():
        print(f"  {cmd:14} {len(items)} 条  例：{items[0][0]}")
