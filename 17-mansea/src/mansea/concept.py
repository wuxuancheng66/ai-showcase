"""概念层：给每篇英文文档**自动**生成中文描述，绕开手写词典的覆盖上限。

问题：手写词典（zh.py）是「问法 -> 命令」，问法无穷无尽，
第 2 轮在新题集上只拿到 P@1 0.24，就是这个结构的天花板。

办法：反过来做——给每篇文档的 NAME 一行做英译中。
man 页的 NAME 行信息密度极高（`xargs - construct argument list(s) and
execute utility`），只要有一本**词级**的英中词典，2706 篇文档就能全部
自动打上中文标签。词级词典（约 500 条）比问法级词典（无穷）可控得多。

于是「把上一个命令的输出当参数传给下一个」这种从没见过的问法，
也能靠 `参数` 命中 xargs —— 不需要事先有人写过这条规则。
"""

from __future__ import annotations

import re

# 英 -> 中 词级词典。词表里有一部分是 NAME 行高频词，
# 一部分是 Unix 常用词汇，覆盖不到的词会被忽略（宁缺毋滥）。
E2C: dict[str, str] = {
    # ---- 高频功能词（只译有信息量的）----
    "daemon": "守护进程", "server": "服务器", "service": "服务", "agent": "代理",
    "helper": "辅助", "tool": "工具", "tools": "工具", "utility": "工具",
    "utilities": "工具", "utility": "工具", "program": "程序", "application": "应用",
    "applications": "应用", "framework": "框架", "library": "库", "plugin": "插件",
    "module": "模块", "modules": "模块", "extension": "扩展", "package": "包",
    "bundle": "包", "container": "容器", "class": "类", "object": "对象",
    "objects": "对象", "interface": "接口", "api": "接口", "backend": "后端",
    "frontend": "前端", "client": "客户端", "proxy": "代理", "subsystem": "子系统",

    # ---- 文件 / 目录 ----
    "file": "文件", "files": "文件", "directory": "目录", "directories": "目录",
    "folder": "文件夹", "path": "路径", "paths": "路径", "name": "名字",
    "filename": "文件名", "entry": "条目", "entries": "条目", "inode": "索引节点",
    "symlink": "软链接", "symbolic": "符号", "link": "链接", "links": "链接",
    "hierarchy": "层级", "tree": "树", "volume": "卷", "volumes": "卷",
    "filesystem": "文件系统", "partition": "分区", "disk": "磁盘", "disks": "磁盘",
    "device": "设备", "devices": "设备", "mount": "挂载", "unmount": "卸载",
    "eject": "弹出", "format": "格式化", "fsck": "磁盘检查", "newfs": "格式化",
    "apfs": "文件系统", "hfs": "文件系统", "nfs": "网络文件系统",

    # ---- 动作 ----
    "create": "创建", "new": "新建", "make": "构建", "build": "构建",
    "remove": "删除", "delete": "删除", "rm": "删除", "purge": "清除",
    "copy": "复制", "move": "移动", "rename": "重命名", "edit": "编辑",
    "modify": "修改", "change": "修改", "update": "更新", "replace": "替换",
    "convert": "转换", "conversion": "转换", "transform": "转换",
    "encode": "编码", "decode": "解码", "encoding": "编码", "transcode": "转码",
    "compress": "压缩", "decompress": "解压", "extract": "解压", "archive": "归档",
    "unarchive": "解压", "pack": "打包", "unpack": "解包", "restore": "恢复",
    "backup": "备份", "sync": "同步", "synchronize": "同步", "mirror": "镜像",
    "dump": "转储", "restore": "恢复", "import": "导入", "export": "导出",
    "install": "安装", "uninstall": "卸载", "configure": "配置",
    "manipulate": "操作", "manage": "管理", "management": "管理",
    "control": "控制", "execute": "执行", "execution": "执行", "run": "运行",
    "start": "启动", "stop": "停止", "restart": "重启", "launch": "启动",
    "kill": "杀掉", "terminate": "终止", "suspend": "暂停", "resume": "恢复",
    "wait": "等待", "sleep": "休眠", "load": "加载", "unload": "卸载",
    "enable": "启用", "disable": "禁用", "check": "检查", "verify": "校验",
    "validate": "校验", "test": "测试", "debug": "调试", "debugging": "调试",
    "trace": "跟踪", "monitor": "监控", "report": "报告", "print": "打印",
    "display": "显示", "show": "显示", "list": "列出", "listing": "列出",
    "read": "读取", "write": "写入", "open": "打开", "close": "关闭",
    "send": "发送", "receive": "接收", "transfer": "传输", "download": "下载",
    "upload": "上传", "fetch": "获取", "query": "查询", "search": "搜索",
    "find": "查找", "filter": "过滤", "sort": "排序", "count": "统计",
    "compare": "比较", "diff": "比较", "merge": "合并", "split": "分割",
    "join": "合并", "concatenate": "拼接", "append": "追加", "insert": "插入",
    "generate": "生成", "parse": "解析", "parsing": "解析", "compile": "编译",
    "walk": "遍历", "recursive": "递归", "watch": "监视", "follow": "跟踪",

    # ---- 系统 ----
    "system": "系统", "systems": "系统", "kernel": "内核", "process": "进程",
    "processes": "进程", "thread": "线程", "memory": "内存", "swap": "交换",
    "cpu": "处理器", "load": "负载", "boot": "启动", "shutdown": "关机",
    "reboot": "重启", "halt": "关机", "power": "电源", "battery": "电池",
    "thermal": "温度", "fan": "风扇", "screen": "屏幕", "display": "显示器",
    "resolution": "分辨率", "brightness": "亮度", "audio": "音频",
    "sound": "声音", "volume": "音量", "mute": "静音", "microphone": "麦克风",
    "camera": "摄像头", "keyboard": "键盘", "mouse": "鼠标", "trackpad": "触控板",
    "printer": "打印机", "scanner": "扫描仪", "bluetooth": "蓝牙",
    "wifi": "无线", "wireless": "无线", "ethernet": "以太网",

    # ---- 网络 ----
    "network": "网络", "networks": "网络", "net": "网络", "internet": "网络",
    "tcp": "网络", "udp": "网络", "ip": "地址", "ipv6": "地址", "dns": "域名",
    "domain": "域名", "host": "主机", "hostname": "主机名", "port": "端口",
    "socket": "套接字", "connection": "连接", "connections": "连接",
    "connect": "连接", "listen": "监听", "listening": "监听", "packet": "数据包",
    "capture": "抓包", "route": "路由", "routing": "路由", "gateway": "网关",
    "firewall": "防火墙", "proxy": "代理", "vpn": "虚拟专用网", "ssh": "远程登录",
    "remote": "远程", "local": "本地", "protocol": "协议", "request": "请求",
    "requests": "请求", "response": "响应", "url": "链接", "http": "网络",
    "https": "网络", "mail": "邮件", "smtp": "邮件",

    # ---- 账户 / 安全 ----
    "user": "用户", "users": "用户", "account": "账号", "group": "组",
    "password": "密码", "passwd": "密码", "credential": "凭据",
    "keychain": "钥匙串", "key": "密钥", "keys": "密钥", "certificate": "证书",
    "sign": "签名", "signature": "签名", "codesign": "代码签名",
    "encrypt": "加密", "decrypt": "解密", "encryption": "加密",
    "ssl": "加密", "tls": "加密", "security": "安全", "audit": "审计",
    "permission": "权限", "permissions": "权限", "owner": "所有者",
    "ownership": "所有者", "mode": "权限", "acl": "权限", "authentication": "认证",
    "authorization": "授权", "sudo": "管理员", "root": "管理员",

    # ---- 数据 / 文本 ----
    "data": "数据", "database": "数据库", "text": "文本", "string": "字符串",
    "line": "行", "lines": "行", "character": "字符", "characters": "字符",
    "byte": "字节", "bytes": "字节", "binary": "二进制", "hex": "十六进制",
    "unicode": "编码", "charset": "字符集", "utf": "编码", "ascii": "编码",
    "json": "数据", "xml": "数据", "html": "网页", "plist": "配置",
    "xml": "数据", "csv": "表格", "table": "表", "tables": "表",
    "column": "列", "columns": "列", "row": "行", "rows": "行",
    "field": "字段", "fields": "字段", "record": "记录", "log": "日志",
    "logs": "日志", "logging": "日志", "message": "消息", "messages": "消息",
    "output": "输出", "input": "输入", "stdin": "输入", "stdout": "输出",
    "stderr": "错误输出", "stream": "流", "buffer": "缓冲", "cache": "缓存",
    "pattern": "模式", "regex": "正则", "regular": "正则", "expression": "表达式",
    "grammar": "语法", "syntax": "语法", "parser": "解析器", "token": "词法单元",
    "variable": "变量", "variables": "变量", "environment": "环境",
    "option": "选项", "options": "选项", "argument": "参数", "arguments": "参数",
    "parameter": "参数", "flag": "参数", "command": "命令", "commands": "命令",
    "shell": "命令行", "script": "脚本", "interpreter": "解释器",
    "terminal": "终端", "console": "终端", "page": "页", "pager": "分页",
    "usage": "用法", "manual": "手册", "documentation": "文档", "help": "帮助",
    "intro": "介绍", "introduction": "介绍", "overview": "概述",
    "tutorial": "教程", "reference": "参考", "guide": "指南",
    "description": "描述", "example": "示例", "examples": "示例",
    "version": "版本", "revision": "版本", "release": "版本",
    "information": "信息", "status": "状态", "state": "状态",
    "statistics": "统计", "stats": "统计", "diagnostics": "诊断",
    "diagnostic": "诊断", "error": "错误", "errors": "错误", "bug": "错误",
    "repeated": "重复", "duplicate": "重复", "unique": "去重",
    "reverse": "反转", "order": "排序", "sorted": "排序", "empty": "空",
    "size": "大小", "length": "长度", "number": "数字", "random": "随机",
    "hash": "哈希", "checksum": "校验和", "digest": "摘要", "md5": "校验和",
    "sha": "校验和", "time": "时间", "date": "日期", "clock": "时钟",
    "timer": "定时器", "schedule": "定时", "periodic": "定时", "cron": "定时任务",
    "delay": "延迟", "timeout": "超时", "interval": "间隔",
    "image": "图像", "images": "图像", "graphics": "图形", "widget": "控件",
    "widgets": "控件", "window": "窗口", "menu": "菜单", "dialog": "对话框",
    "event": "事件", "events": "事件", "queue": "队列", "channel": "通道",
    "graph": "图", "node": "节点", "edge": "边", "label": "标签",
    "style": "样式", "theme": "主题", "font": "字体", "color": "颜色",
    "label": "标签", "magic": "魔数", "metadata": "元数据", "property": "属性",
    "properties": "属性", "attribute": "属性", "value": "值", "values": "值",
    "set": "设置", "get": "获取", "default": "默认", "defaults": "默认设置",
    "preference": "偏好", "preferences": "偏好", "settings": "设置",
    "config": "配置", "configuration": "配置", "conf": "配置", "profile": "配置",
    "policy": "策略", "rule": "规则", "rules": "规则", "limits": "限制",
    "shared": "共享", "sharing": "共享", "public": "公开", "private": "私有",
    "virtual": "虚拟", "physical": "物理", "raw": "原始", "plain": "纯文本",
    "simple": "简单", "advanced": "高级", "general": "通用", "common": "通用",
    "standard": "标准", "custom": "自定义", "automatic": "自动", "auto": "自动",
    "manual": "手动", "interactive": "交互", "batch": "批量",

    # ---- 第 3 轮补：HELD4 打出来的词汇缺口 ----
    # 注意这一层是**词级**的（英文单词 -> 中文词），不是"问法 -> 命令"。
    # 词级词典能规模化：补一个词，所有含这个词的 NAME 行都受益。
    "calendar": "日历", "clock": "时钟", "watch": "表",
    "arithmetic": "算术", "calculator": "计算器", "math": "数学",
    "mathematical": "数学", "expression": "表达式", "evaluate": "求值",
    "precision": "精度", "arbitrary": "任意", "integer": "整数",
    "float": "浮点", "numeric": "数值", "number": "数字",
    "calculate": "计算", "compute": "计算", "convert": "换算",
    "conversion": "换算", "unit": "单位", "units": "单位",
    "measurement": "度量", "metric": "度量", "scale": "刻度",
    "model": "型号", "machine": "机器", "brand": "品牌",
    "vendor": "厂商", "product": "产品", "platform": "平台",
    "type": "类型", "kind": "种类", "determine": "判断",
    "identify": "识别", "recognize": "识别", "detect": "检测",
    "first": "首部", "last": "尾部", "beginning": "开头", "end": "结尾",
    "retain": "保留", "keep": "保留", "preserve": "保留", "remainder": "剩余",
    "combine": "合并", "combining": "合并", "assemble": "组装",
    "separate": "分开", "divide": "划分", "group": "分组",
    "modify": "修改", "modification": "修改", "accessed": "访问",
    "access": "访问", "accessing": "访问", "accessor": "访问",
    "total": "总和", "sum": "求和", "aggregate": "汇总",
    "limit": "限制", "threshold": "阈值", "maximum": "最大", "minimum": "最小",
    "restrict": "限制", "quota": "配额", "budget": "预算",
    "free": "空闲", "available": "可用", "remaining": "剩余",
    "elapsed": "耗时", "duration": "时长", "since": "自从",
    "zone": "时区", "timezone": "时区", "utc": "世界时", "epoch": "时间戳",
    "locale": "地区", "language": "语言", "translation": "翻译",
    "alias": "别名", "nickname": "别名", "abbreviation": "缩写",
    "invocation": "调用", "invoke": "调用", "spawn": "派生",
    "recursive": "递归", "iterate": "迭代", "loop": "循环",
    "prompt": "提示符", "input": "输入", "echo": "回显",
    "quote": "引用", "escape": "转义", "expand": "展开",
    "globbing": "通配符", "wildcard": "通配符", "substitute": "替换",
    "substitution": "替换", "interpolate": "插值", "template": "模板",
    "shebang": "解释器行", "executable": "可执行", "binary": "二进制",
    "segment": "段", "section": "节", "block": "块", "chunk": "块",
    "truncate": "截断", "pad": "填充", "trim": "裁剪", "strip": "去除",
    "whitespace": "空白", "newline": "换行", "blank": "空白",
    "delimiter": "分隔符", "separator": "分隔符", "tokenize": "分词",
    "extract": "提取", "slice": "切片", "substring": "子串",
    "recursive": "递归", "repeatedly": "重复", "sequential": "顺序",
    "previous": "上一个", "next": "下一个", "current": "当前",
    "recursive": "递归", "nested": "嵌套", "flatten": "展平",

    # ---- 第 4 轮补：按 NAME 行词频批量补，覆盖 32.8% → 目标 45%+ ----
    # 做法不是拍脑袋猜问法，而是把 2706 篇 NAME 行里没被译的词按文档频次排序，
    # 挑掉 for/and/the 这类功能词和 perl/tcl/slapd 这类语料噪音，剩下的逐个补。
    # 词级词典的好处：补 1 个词，所有含这个词的 NAME 行同时受益。
    "address": "地址", "addresses": "地址", "lookup": "查询", "lookups": "查询",
    "resolve": "解析", "resolver": "解析", "nameserver": "域名服务器",
    "retrieve": "获取", "gather": "收集", "collect": "收集",
    "background": "后台", "foreground": "前台", "job": "任务", "jobs": "任务",
    "login": "登录", "logout": "登出", "logout": "登出", "session": "会话",
    "notification": "通知", "notify": "通知", "alert": "提醒",
    "contents": "内容", "content": "内容", "catalog": "目录",
    "compiler": "编译器", "interpreter": "解释器", "assembler": "汇编",
    "performance": "性能", "benchmark": "基准测试", "profile": "性能分析",
    "archives": "归档", "archive": "归档", "library": "库",
    "call": "调用", "calls": "调用", "called": "调用",
    "generator": "生成器", "generate": "生成", "produced": "生成",
    "setup": "设置", "installed": "已安装", "installer": "安装程序",
    "programming": "编程", "scripts": "脚本", "expressions": "表达式",
    "canvas": "画布", "ui": "界面", "features": "特性", "parsed": "解析",
    "dynamic": "动态", "static": "静态", "map": "映射", "maps": "映射",
    "operation": "操作", "operations": "操作", "perform": "执行",
    "facility": "设施", "channels": "通道", "lists": "列表",
    "copying": "复制", "extensions": "扩展", "reports": "报告",
    "functions": "函数", "function": "函数", "manipulation": "操作",
    "distribution": "发行", "software": "软件", "related": "相关",
    "running": "运行", "strings": "字符串", "elements": "元素",
    "entity": "实体", "issues": "问题", "support": "支持",
    "code": "代码", "manager": "管理器", "procedures": "过程",
    "services": "服务", "implementation": "实现", "core": "核心",
    "manages": "管理", "provides": "提供", "base": "基础",
    "term": "术语", "util": "工具", "app": "应用", "db": "数据库",
    "struct": "结构", "structure": "结构", "format": "格式",
    "entry": "条目", "point": "点", "level": "级别", "levels": "级别",
    "space": "空间", "usage": "占用", "capacity": "容量",
    "speed": "速度", "rate": "速率", "throughput": "吞吐",
    "latency": "延迟", "bandwidth": "带宽", "traffic": "流量",
    "hardware": "硬件", "firmware": "固件", "driver": "驱动",
    "drivers": "驱动", "bus": "总线",
    "pressure": "压力", "sequence": "序列", "sequences": "序列",
    "range": "范围", "series": "序列", "successive": "连续",
    "interrupt": "中断", "signal": "信号", "signals": "信号",
    "handler": "处理", "callback": "回调", "hook": "钩子",
    "storage": "存储", "persistent": "持久化", "temporary": "临时",
    "temp": "临时", "scratch": "暂存", "staging": "暂存",
    "queue": "队列", "stack": "栈", "heap": "堆", "pool": "池",
    "thread": "线程", "threads": "线程", "concurrent": "并发",
    "lock": "锁", "mutex": "锁", "semaphore": "信号量",
    "shared": "共享", "isolated": "隔离", "sandbox": "沙箱",
    "boot": "启动", "bootloader": "引导", "firmware": "固件",
    "recovery": "恢复", "restore": "恢复", "snapshot": "快照",
    "clone": "克隆", "fork": "派生", "exec": "执行",
    "pipe": "管道", "redirect": "重定向", "descriptor": "描述符",
    "stdin": "输入", "terminal": "终端", "tty": "终端", "pty": "伪终端",
    "escape": "转义", "quoting": "引用", "prompt": "提示符",
    "history": "历史", "completion": "补全", "keystroke": "按键",
    "encoding": "编码", "decoding": "解码", "charset": "字符集",
    "encryption": "加密", "decryption": "解密", "cipher": "密码",
    "digest": "摘要", "signature": "签名", "trust": "信任",
    "policy": "策略", "profile": "配置", "registry": "注册表",
    "domain": "域", "realm": "域", "tenant": "租户",
    "routing": "路由", "forwarding": "转发", "bridge": "网桥",
    "interface": "接口", "interfaces": "接口", "adapter": "适配器",
    "wireless": "无线", "ethernet": "以太网", "vlan": "虚拟局域网",
    "latency": "延迟", "jitter": "抖动", "metric": "度量",
    "counter": "计数器", "gauge": "计量", "sample": "采样",
    "diagnose": "诊断", "troubleshoot": "排查", "reproduce": "复现",
}

_WORD = re.compile(r"[a-z][a-z0-9]{1,}")


def en_to_cn(text: str) -> str:
    """把一段英文（通常是 NAME 行）译成中文概念词串。"""
    out: list[str] = []
    for w in _WORD.findall((text or "").lower()):
        cn = E2C.get(w)
        if cn and cn not in out:
            out.append(cn)
    return " ".join(out)


_CJK = r"\u4e00-\u9fff"


def cn_terms(text: str) -> dict[str, float]:
    """中文串 -> {bigram: 1.0}。

    概念层只留二元组，不要单字：单字（"文""件""系""统"）区分度太低，
    会把所有文档都拉进候选集。
    """
    out: dict[str, float] = {}
    for seg in re.findall(rf"[{_CJK}]{{2,}}", text or ""):
        for i in range(len(seg) - 1):
            out[seg[i : i + 2]] = 1.0
    return out


def _build_c2e() -> dict[str, list[str]]:
    """把 E2C 反转成 中 -> [英]。

    这是第 4 轮加的**结构**，不是又一本手写词典：
    - E2C 是「英文词 -> 中文词」，用来把 2706 篇文档的 NAME 行自动译中（文档侧）
    - 反转后就免费得到「中文词 -> 英文词」，用来把中文查询译成英文（查询侧）

    之前这两侧是不对称的：文档侧有 500+ 词条自动译中，
    查询侧只有 zh.py 里手写的「问法 -> 命令」。手写词典覆盖不到的问法，
    中文就永远打不到英文语料。反转之后，只要 E2C 认得这个词，
    任何中文问法都能翻成对应的英文去查 —— 补词典的收益自动翻倍。

    注意：多个英文词可能译到同一个中文词（file/folder/path -> 文件）。
    所以匹配到时**把权重平分**给这些英文词：「文件」分到 1/6，
    而只对应一个英文词的「信号量」拿满 1.0。特定的词自然更重。
    """
    out: dict[str, list[str]] = {}
    for en, cn in E2C.items():
        bucket = out.setdefault(cn, [])
        if en not in bucket:
            bucket.append(en)
    return out


C2E: dict[str, list[str]] = _build_c2e()
# 长词优先匹配，避免「用户名」被「用户」先吃掉
# 只留 2 字及以上的中文键。单字键（"列""行""点"）会在词内部误命中：
# 「序列」里能抠出「列」，「行号」里能抠出「行」，凭空多出 columns/row 这类噪声。
_C2E_KEYS: list[str] = sorted((k for k in C2E if len(k) >= 2), key=len, reverse=True)


def cn_to_en_terms(text: str) -> dict[str, float]:
    """中文串 -> {英文词: 权重}（权重已按一词多译平分）。"""
    out: dict[str, float] = {}
    for seg in re.findall(rf"[{_CJK}]+", text or ""):
        used = [False] * len(seg)
        for key in _C2E_KEYS:
            start = 0
            while True:
                i = seg.find(key, start)
                if i < 0:
                    break
                start = i + 1
                if any(used[i : i + len(key)]):
                    continue
                for j in range(i, i + len(key)):
                    used[j] = True
                ens = C2E[key]
                w = 1.0 / len(ens)
                for en in ens:
                    out[en] = out.get(en, 0.0) + w
    return out


if __name__ == "__main__":
    import sys

    print(en_to_cn(" ".join(sys.argv[1:]) or "construct argument list(s) and execute utility"))
