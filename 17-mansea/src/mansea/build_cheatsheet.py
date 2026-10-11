"""把 cheatsheet.py 渲染成 site/cheatsheet.html（单文件、双击即用、不联网）。

和 offline.html 的区别：这个页面不检索，是**人写的知识**，
按场景分组，可以直接当命令速查手册翻。
"""

from __future__ import annotations

import html
import json
from pathlib import Path

from .cheatsheet import CHEATS

ROOT = Path(__file__).resolve().parent.parent

# 场景分组：按"意图"里的关键词归类，纯展示用
GROUPS: list[tuple[str, list[str]]] = [
    ("文件与目录", ["目录", "文件", "链接", "类型", "行", "分页", "合并", "拼接", "分割", "比较", "清空", "排文件"]),
    ("查找与搜索", ["找", "搜索", "路径", "哪个"]),
    ("文本处理", ["统计", "排序", "去重", "重复", "列", "替换", "删除", "回车", "tab", "行号", "反转", "编码", "字符集", "base64", "表格"]),
    ("压缩与归档", ["打包", "解包", "压缩", "解压", "zip", "gzip", "tar"]),
    ("权限与属性", ["权限", "可执行", "所有者", "扩展属性", "隐藏"]),
    ("进程", ["进程", "杀", "后台", "前台", "优先级", "跑多久"]),
    ("系统信息", ["磁盘", "内存", "系统", "内核", "版本", "硬件", "电池", "序列号", "环境变量", "偏好", "接口", "空间", "大小", "读写"]),
    ("网络", ["端口", "监听", "ip", "连通", "域名", "路由", "抓包", "下载", "网速"]),
    ("远程与同步", ["远程", "免密", "密钥", "传文件", "同步", "备份"]),
    ("管道与技巧", ["参数", "输出", "清屏", "历史", "别名", "重复执行", "等待"]),
    ("安全", ["校验和", "随机密码", "钥匙串", "签名", "证书"]),
]


def _group_of(intent: str) -> str:
    for name, kws in GROUPS:
        if any(k in intent for k in kws):
            return name
    return "其他"


def build(out_path: str | Path = ROOT / "site" / "cheatsheet.html") -> Path:
    items = []
    for intent, cmd, args, note in CHEATS:
        items.append({"i": intent, "c": cmd, "a": args, "n": note, "g": _group_of(intent)})

    payload = json.dumps({"items": items}, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    page = TEMPLATE.replace("/*__DATA__*/", payload)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    print(f"[cheatsheet] 写出 {out}（{len(page)/1024:.0f} KB，{len(items)} 条 / "
          f"{len({i['c'] for i in items})} 个命令）")
    return out


TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>mansea 命令速查 · 中文找命令</title>
<style>
:root{--bg:#f7f8fa;--panel:#fff;--text:#1a1d21;--muted:#6b7280;--line:#e3e6ea;--accent:#2563eb;--accent-soft:#e8efff;--code:#0f172a;--code-bg:#f1f5f9;--mark:#ffe08a;--mark-text:#4a3200}
@media(prefers-color-scheme:dark){:root{--bg:#0f1115;--panel:#171a20;--text:#e6e8ec;--muted:#9aa3af;--line:#262b33;--accent:#6ea8fe;--accent-soft:#1c2740;--code:#e6e8ec;--code-bg:#11151c;--mark:#6b5a1a;--mark-text:#ffe9b0}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font:15px/1.6 -apple-system,"PingFang SC","Helvetica Neue",Arial,sans-serif;-webkit-font-smoothing:antialiased}
.wrap{max-width:960px;margin:0 auto;padding:24px 18px 64px}
header{margin-bottom:16px}
h1{margin:0;font-size:19px}
.sub{margin:3px 0 0;font-size:12.5px;color:var(--muted)}
#q{width:100%;padding:12px 14px;font-size:16px;font-family:inherit;color:var(--text);background:var(--panel);border:1px solid var(--line);border-radius:12px;outline:none;margin-top:14px}
#q:focus{border-color:var(--accent);box-shadow:0 0 0 3px var(--accent-soft)}
.meta{font-size:12.5px;color:var(--muted);margin:12px 2px}
.grp{margin:22px 0 0}
.grp h2{font-size:13px;color:var(--muted);font-weight:600;margin:0 0 8px;letter-spacing:.04em}
.row{display:grid;grid-template-columns:minmax(180px,1.1fr) minmax(150px,1fr);gap:4px 14px;background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:10px 13px;margin-bottom:7px}
.row .intent{font-size:14px}
.row .cmd{font:13px ui-monospace,Menlo,monospace;color:var(--accent);word-break:break-all}
.row .args{grid-column:1;background:var(--code-bg);color:var(--code);font:12.5px ui-monospace,Menlo,monospace;padding:5px 8px;border-radius:6px;overflow-x:auto;white-space:nowrap}
.row .note{grid-column:2;font-size:12.5px;color:var(--muted)}
.row:nth-child(odd){}
mark{background:var(--mark);color:var(--mark-text);border-radius:3px;padding:0 2px}
.empty{text-align:center;color:var(--muted);padding:40px}
footer{margin-top:28px;padding-top:12px;border-top:1px solid var(--line);font-size:12px;color:var(--muted);display:flex;justify-content:space-between}
@media(max-width:640px){.row{grid-template-columns:1fr}.row .args,.row .note{grid-column:1}}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>mansea · 命令速查</h1>
    <p class="sub">用中文说需求，直接给命令和常用参数 · 双击即用 · 不联网</p>
  </header>
  <input id="q" type="search" autocomplete="off" placeholder="搜索：端口 / 压缩 / 杀进程 / 同步 / 行号 …">
  <div class="meta" id="meta"></div>
  <div id="out"></div>
  <footer><span>mansea · 澈造</span><span id="cnt"></span></footer>
</div>
<script>
const DATA = /*__DATA__*/;
const $ = id => document.getElementById(id);
const esc = s => (s||'').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const hl = (t, q) => { let o = esc(t); if(q){ o = o.replace(new RegExp(q.replace(/[.*+?^${}()|[\]\\]/g,'\\$&'),'gi'), m=>`<mark>${m}</mark>`); } return o; };

function render(){
  const q = $('q').value.trim();
  const lq = q.toLowerCase();
  const hit = DATA.items.filter(it => !lq || (it.i+' '+it.c+' '+it.a+' '+it.n).toLowerCase().includes(lq));
  $('meta').textContent = q ? `命中 ${hit.length} 条` : `共 ${DATA.items.length} 条速查 · ${new Set(DATA.items.map(i=>i.c)).size} 个命令`;
  if(!hit.length){ $('out').innerHTML = '<div class="empty">没有命中。</div>'; return; }
  const groups = {};
  hit.forEach(it => (groups[it.g] = groups[it.g] || []).push(it));
  $('out').innerHTML = Object.keys(groups).map(g =>
    `<div class="grp"><h2>${esc(g).toUpperCase()}</h2>` + groups[g].map(it =>
      `<div class="row"><div class="intent">${hl(it.i, q)}</div><div class="cmd">${hl(it.c, q)}</div>`+
      `<div class="args">${hl(it.a, q)}</div><div class="note">${hl(it.n, q)}</div></div>`
    ).join('') + '</div>'
  ).join('');
}
$('q').addEventListener('input', render);
$('cnt').textContent = '语料：本机 man 手册';
render();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    build()
