"""生成离线单文件版 site/offline.html。

把所有文档的「名称 + 别名 + 一行说明 + 摘要片段」和中文扩展词典内联进一个
HTML，双击即可用，不需要起服务。代价是只能检索标题/摘要层（全文检索请用
`./run.sh serve`）。
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from .cheatsheet import CHEATS
from .concept import en_to_cn
from .ingest import read_jsonl
from .zh import Z2E

ROOT = Path(__file__).resolve().parent.parent
_CJK = re.compile(r"[\u4e00-\u9fff]")


def _excerpt(text: str, n: int = 520) -> str:
    """从正文里截一段有用的（跳过标题和 NAME 行）。"""
    if not text:
        return ""
    body = re.sub(r"\s+", " ", text)
    i = body.find("DESCRIPTION")
    start = i + 11 if i > 0 else min(120, len(body))
    return body[start : start + n].strip()


def _load_cmd2doc() -> dict[str, int]:
    """命令的任何叫法 -> 文档 id。用别名解析，gunzip/dirname 才不会漏。"""
    p = ROOT / "data" / "cmd2doc.json"
    if p.exists():
        import json

        return {k: int(v) for k, v in json.loads(p.read_text(encoding="utf-8")).items()}
    return {}


_CMD2DOC = _load_cmd2doc()
# 文档 id -> [(意图, 命令, 常用写法, 说明)]，按文档归组（不是按命令名）
_CHEAT_BY_DOC: dict[int, list[tuple[str, str, str, str]]] = {}
for _i, _c, _a, _n in CHEATS:
    _did = _CMD2DOC.get(_c.lower())
    if _did is not None:
        _CHEAT_BY_DOC.setdefault(_did, []).append((_i, _c, _a, _n))


def _concept_of(d: dict, doc_id: int) -> str:
    """文档的中文概念串：NAME 行自动译中 + 速查表手工意图。"""
    parts = [en_to_cn(f"{d.get('name', '')} {d.get('summary', '')}")]
    for intent, _c, _a, note in _CHEAT_BY_DOC.get(doc_id, ()):
        parts.append(f"{intent} {note}")
    return " ".join(parts)


_RELATED_TITLES: dict[int, list[str]] = {}


def _related_names(docs_src: list[dict]) -> dict[int, list[str]]:
    p = ROOT / "data" / "related.json"
    if not p.exists():
        return {}
    import json

    raw = json.loads(p.read_text(encoding="utf-8"))
    out: dict[int, list[str]] = {}
    for k, nbs in raw.items():
        names = []
        for nb, _w in nbs:
            nb = int(nb)
            if 0 <= nb < len(docs_src):
                nm = docs_src[nb].get("title") or docs_src[nb].get("name")
                if nm and nm not in names:
                    names.append(nm)
        out[int(k)] = names[:5]
    return out


def build(out_path: str | Path = ROOT / "site" / "offline.html") -> Path:
    docs_src = read_jsonl(str(ROOT / "data" / "docs.jsonl"))
    _RELATED_TITLES.update(_related_names(docs_src))
    slim = []
    for d in docs_src:
        slim.append(
            {
                "n": d.get("name", ""),
                "s": d.get("section", ""),
                "t": d.get("title", ""),
                "m": (d.get("summary") or "")[:220],
                "k": d.get("keys", ""),
                "c": _concept_of(d, len(slim)),
                "u": [f"{a}  # {n}" for _i, _c, a, n in _CHEAT_BY_DOC.get(len(slim), ())][:3],
                "e": _excerpt(d.get("text", "")),
                # SEE ALSO 相关命令。拿去改排序是负收益（见 engine.W_RELATED 注释），
                # 但当导航很好用：看完 ls 告诉你还有 chmod/chown/stat。
                "r": [n for n in _RELATED_TITLES.get(len(slim), ())][:5],
            }
        )

    payload = json.dumps({"docs": slim, "z2e": Z2E}, ensure_ascii=False, separators=(",", ":"))
    # 防止正文里的 "</" 提前闭合 <script>
    payload = payload.replace("</", "<\\/")
    html = TEMPLATE.replace("/*__DATA__*/", payload)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"[static] 写出 {out}（{len(html)/1024/1024:.2f} MB，{len(slim)} 篇）")
    return out


TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>mansea 离线版 · 本地手册检索</title>
<style>
:root{--bg:#f7f8fa;--panel:#fff;--text:#1a1d21;--muted:#6b7280;--line:#e3e6ea;--accent:#2563eb;--accent-soft:#e8efff;--mark:#ffe08a;--mark-text:#4a3200}
@media(prefers-color-scheme:dark){:root{--bg:#0f1115;--panel:#171a20;--text:#e6e8ec;--muted:#9aa3af;--line:#262b33;--accent:#6ea8fe;--accent-soft:#1c2740;--mark:#6b5a1a;--mark-text:#ffe9b0}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font:15px/1.6 -apple-system,"PingFang SC","Helvetica Neue",Arial,sans-serif;-webkit-font-smoothing:antialiased}
.wrap{max-width:940px;margin:0 auto;padding:26px 18px 60px}
header{display:flex;justify-content:space-between;align-items:center;gap:14px;margin-bottom:18px}
h1{margin:0;font-size:18px}
.sub{margin:2px 0 0;font-size:12.5px;color:var(--muted)}
.badge{font-size:12px;color:var(--muted);text-align:right;font-variant-numeric:tabular-nums}
#q{width:100%;padding:13px 15px;font-size:16px;font-family:inherit;color:var(--text);background:var(--panel);border:1px solid var(--line);border-radius:12px;outline:none}
#q:focus{border-color:var(--accent);box-shadow:0 0 0 3px var(--accent-soft)}
.chips{display:flex;flex-wrap:wrap;gap:8px;margin:13px 0 2px}
.chip{font-size:12.5px;padding:5px 11px;border-radius:999px;cursor:pointer;border:1px solid var(--line);background:var(--panel);color:var(--muted)}
.chip:hover{color:var(--accent);border-color:var(--accent)}
.rel{margin-top:8px;font-size:12.5px;color:var(--muted);display:flex;flex-wrap:wrap;gap:6px;align-items:center}
.rel .chip{padding:2px 9px;font-size:12px}
.meta{font-size:12.5px;color:var(--muted);margin:14px 2px 10px;min-height:18px}
.res{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:13px 15px;margin-bottom:9px}
.res h3{margin:0 0 4px;font:15px ui-monospace,Menlo,monospace}
.res h3 .sec{color:var(--accent)}
.res .sc{float:right;font-size:11.5px;color:var(--muted)}
.res p{margin:0 0 5px;font-size:13.5px}
.res .ex{color:var(--muted);font-size:13px}
.res .use{margin:6px 0 0;padding:6px 0 6px 18px;list-style:none;border-left:2px solid var(--accent)}
.res .use li{font:12.5px ui-monospace,Menlo,monospace;color:var(--code);word-break:break-all;padding:1px 0}
mark{background:var(--mark);color:var(--mark-text);border-radius:3px;padding:0 2px}
.empty{text-align:center;color:var(--muted);font-size:13.5px;padding:44px 10px}
footer{margin-top:30px;padding-top:13px;border-top:1px solid var(--line);font-size:12px;color:var(--muted);display:flex;justify-content:space-between}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <div><h1>mansea · 离线版</h1><p class="sub">本机 man 手册检索 · 双击即用 · 不联网 · <a href="cheatsheet.html">命令速查 →</a></p></div>
    <div class="badge" id="badge"></div>
  </header>
  <input id="q" type="search" autocomplete="off" placeholder="例如：查看端口占用 / 压缩解压 / 杀掉进程 / find files by name">
  <div class="chips" id="chips"></div>
  <div class="meta" id="meta"></div>
  <div id="out"><div class="empty">输入关键词开始检索。离线版只检索标题与说明；全文检索请运行 <code>./run.sh serve</code></div></div>
  <footer><span>mansea · 澈造的本地检索引擎</span><span id="cnt"></span></footer>
</div>
<script>
const DATA = /*__DATA__*/;
const $ = id => document.getElementById(id);
const esc = s => (s||'').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const EX = ["查看端口占用","压缩解压","杀掉进程","磁盘空间","文本替换","ssh 免密登录","递归查找文件","查看文件内容"];

function tok(s){
  s = (s||'').toLowerCase();
  const out = [];
  const re = /[a-z0-9]+(?:[._\-+][a-z0-9]+)*|[\u4e00-\u9fff]+/g;
  let m;
  while ((m = re.exec(s))) {
    const w = m[0];
    if (/[\u4e00-\u9fff]/.test(w[0])) {
      for (const ch of w) out.push(ch);
      for (let i=0;i<w.length-1;i++) out.push(w.slice(i,i+2));
    } else if (w.length>1) out.push(w);
  }
  return out;
}
function expand(q){
  let out=[], seen=new Set();
  for (const k of Object.keys(DATA.z2e).sort((a,b)=>b.length-a.length))
    if (q.includes(k)) for (const w of DATA.z2e[k]) if(!seen.has(w)){seen.add(w);out.push(w);}
  return out.join(' ');
}
// cn = 中文概念串（NAME 行译中 + 速查表手工标注），离线版靠它支持中文
let IDX = DATA.docs.map((d,i)=>({i, sec:(d.s||''), name:(d.n||'').toLowerCase(), keys:(d.k||'').toLowerCase(),
                                 sum:(d.m||'').toLowerCase(), cn:(d.c||'').toLowerCase(), ex:(d.e||'').toLowerCase()}));
function bigrams(s){ const out=new Set(); const seg=(s||'').match(/[\u4e00-\u9fff]{2,}/g)||[];
  for(const w of seg) for(let i=0;i<w.length-1;i++) out.add(w.slice(i,i+2)); return [...out]; }
function hl(t, terms){
  let o = esc(t);
  [...new Set(terms.filter(t=>t.length>1))].sort((a,b)=>b.length-a.length).forEach(t=>{
    o = o.replace(new RegExp(esc(t).replace(/[.*+?^${}()|[\]\\]/g,'\\$&'),'gi'), m=>`<mark>${m}</mark>`);
  });
  return o;
}
function run(){
  const q = $('q').value.trim();
  if(!q){ $('out').innerHTML = '<div class="empty">输入关键词开始检索。</div>'; $('meta').textContent=''; return; }
  const soft = expand(q);
  let terms = [...new Set(tok(q))];
  const softTerms = [...new Set(tok(soft))];
  const cnTerms = bigrams(q);
  $('meta').textContent = (soft||cnTerms.length) ? ('展开词：' + (soft||cnTerms.join(' '))) : '';
  const scored = [];
  for (const d of IDX){
    let sc = 0;
    const hit = (t) => {
      if (d.name === t) return 30;          // 命令名完全等于查询词，最强信号
      if (d.name.startsWith(t)) return 12;
      if (d.name.includes(t)) return 6;
      if (d.keys.includes(t)) return 4;
      if (d.sum.includes(t)) return 3;
      if (d.ex.includes(t)) return 1;
      return 0;
    };
    for (const t of terms) sc += hit(t);
    for (const t of softTerms) sc += hit(t) * 0.5;
    // 中文：拿查询的 bigram 去打中文概念串（这层和 ./run.sh serve 的 concept 路一致）
    for (const b of cnTerms) { if (d.cn.includes(b)) sc += 6; else if (d.sum.includes(b)) sc += 1; }
    if (d.sec === '1') sc += 2;              // 用户命令优先于 Tcl/Perl 手册
    else if (d.sec === '8') sc += 1;
    if (sc>0) scored.push([sc, d.i]);
  }
  scored.sort((a,b)=>b[0]-a[0]);
  const top = scored.slice(0,25);
  if(!top.length){ $('out').innerHTML = '<div class="empty">没有命中。换个说法试试。</div>'; return; }
  $('out').innerHTML = top.map(([sc,i])=>{
    const d = DATA.docs[i];
    return `<div class="res"><h3><span class="sec">${esc(d.t)}</span><span class="sc">${sc.toFixed(1)}</span></h3>
      <p>${hl(d.m||'', terms.concat(softTerms))}</p>
      ${(d.u&&d.u.length)?`<ul class="use">${d.u.map(x=>`<li>${esc(x)}</li>`).join('')}</ul>`:''}
      ${d.e?`<p class="ex">${hl(d.e.slice(0,240), terms.concat(softTerms))}…</p>`:''}
      ${(d.r&&d.r.length)?`<p class="rel">相关：${d.r.map(x=>`<span class="chip rel-chip">${esc(x)}</span>`).join(' ')}</p>`:''}</div>`;
  }).join('');
}
$('chips').innerHTML = EX.map(e=>`<span class="chip">${esc(e)}</span>`).join('');
$('chips').onclick = e => { if(e.target.classList.contains('chip')){ $('q').value = e.target.textContent; run(); } };
// 相关命令芯片：点一下直接把那个命令名塞进搜索框（SEE ALSO 图的展示用法）
$('out').onclick = e => { if(e.target.classList.contains('rel-chip')){ $('q').value = e.target.textContent; run(); window.scrollTo(0,0); } };
$('q').addEventListener('input', run);
$('badge').textContent = DATA.docs.length + ' 篇已内嵌';
$('cnt').textContent = '语料：/usr/share/man';
$('q').focus();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    build()
