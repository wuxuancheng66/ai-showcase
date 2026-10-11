"""AI 日报生成：官方/权威信源优先，来源分级、来源链接与雷达数据并重。"""

import html as html_mod
import logging
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlsplit

from radar.config import OUTPUTS_DIR
from radar.db import kv_set, now_iso

log = logging.getLogger("radar.daily_report")

_GRADE_NAME = {"🟢": "官方公告", "🔵": "权威媒体", "🟡": "行业媒体", "⚪": "转载/聚合"}
_GRADE_RANK = {"🟢": 0, "🔵": 1, "🟡": 2, "⚪": 3}

_CSS = """
:root{--bg:#f3f6fb;--card:#fff;--ink:#172033;--muted:#667085;--line:#e4e9f2;--accent:#2563eb;--official:#087f5b;--auth:#175cd3;--industry:#a15c00;--aggregate:#667085}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at 8% 0%,#e8f0ff 0,transparent 30rem),var(--bg);color:var(--ink);font-family:"PingFang SC","Hiragino Sans GB","Microsoft YaHei",-apple-system,BlinkMacSystemFont,sans-serif;line-height:1.7}.wrap{max-width:960px;margin:0 auto;padding:28px 18px 48px}header{background:linear-gradient(135deg,#13213f,#234b8f 58%,#0f766e);color:#fff;border-radius:22px;padding:34px 30px;box-shadow:0 18px 50px rgba(20,45,90,.18)}header .eyebrow{font-size:13px;letter-spacing:.16em;text-transform:uppercase;opacity:.78;margin-bottom:10px}header h1{font-size:clamp(28px,5vw,46px);line-height:1.1;margin:0 0 10px;letter-spacing:-.03em}header p{margin:0;opacity:.9;max-width:720px}.legend{margin:18px 0 24px;padding:14px 18px;background:rgba(255,255,255,.82);border:1px solid var(--line);border-radius:14px;color:var(--muted);font-size:13.5px}.legend b{color:var(--ink)}section{margin-top:30px}h2{font-size:21px;margin:0 0 14px;padding-bottom:10px;border-bottom:2px solid var(--line)}.card{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:18px 20px;margin-bottom:12px;box-shadow:0 5px 18px rgba(24,42,80,.055)}.headline{display:grid;grid-template-columns:54px minmax(0,1fr);gap:16px;border-left:4px solid var(--accent)}.compact{border-left:3px solid #d8e2f3}.rank{width:48px;height:48px;border-radius:14px;display:grid;place-items:center;background:#eaf1ff;color:#1d4ed8;font-weight:800;font-size:17px}h3{font-size:18px;line-height:1.45;margin:1px 0 8px}h4{font-size:16px;line-height:1.5;margin:0 0 7px}p{margin:0;color:#475467;font-size:14.5px}.source{margin-top:10px;color:var(--muted);font-size:12.5px;word-break:break-word}.source a{color:var(--accent);text-decoration:none}.source a:hover{text-decoration:underline}.badge{display:inline-block;margin-left:5px;padding:2px 8px;border-radius:999px;font-size:11px;font-weight:700;vertical-align:2px;white-space:nowrap}.badge.official{background:#e6f7f1;color:var(--official)}.badge.auth{background:#e8f1ff;color:var(--auth)}.badge.industry{background:#fff3db;color:var(--industry)}.badge.aggregate{background:#eef1f5;color:var(--aggregate)}.radar-list{margin:0;padding-left:20px;color:#475467}.radar-list li{margin:6px 0}table{width:100%;border-collapse:separate;border-spacing:0;background:#fff;border:1px solid var(--line);border-radius:14px;overflow:hidden;font-size:13.5px}th,td{padding:11px 13px;text-align:left;vertical-align:top;border-bottom:1px solid var(--line)}th{background:#f7f9fc;color:#344054;font-weight:700}tr:last-child td{border-bottom:0}.note{margin-top:14px;color:var(--muted);font-size:12.5px}footer{margin-top:28px;padding-top:16px;border-top:1px solid var(--line);color:var(--muted);font-size:12.5px;text-align:center}@media(max-width:640px){.wrap{padding:16px 12px 34px}header{padding:26px 20px;border-radius:18px}.headline{grid-template-columns:1fr}.rank{width:38px;height:38px;border-radius:10px;font-size:14px}th,td{padding:9px 8px}table{font-size:12.5px}}
"""


def _esc(value) -> str:
    return html_mod.escape(str(value))


def _badge(grade: str) -> str:
    css = {"🟢": "official", "🔵": "auth", "🟡": "industry", "⚪": "aggregate"}.get(grade, "aggregate")
    return f'<span class="badge {css}">{_GRADE_NAME.get(grade, "其他")}</span>'


def _safe_external_url(value) -> str:
    url = str(value or "").strip()
    try:
        parsed = urlsplit(url)
    except ValueError:
        return ""
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    return url


def _source(item: dict) -> str:
    url = _safe_external_url(item.get("url"))
    if not url:
        return ""
    return (f'<div class="source">来源：<a href="{_esc(url)}" target="_blank" rel="noopener">'
            f'{_esc(item.get("source") or "原始来源")}</a></div>')


def _news_item_html(idx: int, item: dict, headline: bool = False) -> str:
    title = _esc(item.get("title") or "")
    summary = item.get("summary") or ""
    body = f'<p>{_esc(summary[:260])}</p>' if summary else ""
    if headline:
        return (f'<article class="card headline"><div class="rank">{idx:02d}</div><div>'
                f'<h3>{title} {_badge(item.get("grade", "⚪"))}</h3>{body}{_source(item)}</div></article>')
    return (f'<article class="card compact"><h4>{title} {_badge(item.get("grade", "⚪"))}</h4>'
            f'{body}{_source(item)}</article>')


def _radar_stats(conn) -> dict:
    day_ago = (datetime.now().astimezone() - timedelta(days=1)).isoformat(timespec="seconds")
    counts = {r["kind"]: r["c"] for r in conn.execute(
        "SELECT kind, COUNT(*) c FROM changes WHERE created_at>=? GROUP BY kind", (day_ago,)).fetchall()}
    price_moves = [dict(r) for r in conn.execute(
        "SELECT summary FROM changes WHERE kind IN ('price_drop','price_rise') "
        "AND created_at>=? ORDER BY id DESC LIMIT 5", (day_ago,)).fetchall()]
    new_free = [dict(r) for r in conn.execute(
        "SELECT summary FROM changes WHERE kind='new_free_model' AND created_at>=? "
        "ORDER BY id DESC LIMIT 5", (day_ago,)).fetchall()]
    chan_bad = [dict(r) for r in conn.execute(
        "SELECT name, status FROM channels WHERE status IN ('error','limited')").fetchall()]
    return {"counts": counts, "price_moves": price_moves, "new_free": new_free, "chan_bad": chan_bad}


def build_report(conn, news: dict) -> str:
    today = time.strftime("%Y 年 %m 月 %d 日")
    valid = [item for item in news.get("items", []) if _safe_external_url(item.get("url"))]
    head, body = valid[:2], valid[2:14]
    stats = _radar_stats(conn)

    h = [
        f"<!DOCTYPE html><html lang='zh-CN'><head><meta charset='utf-8'>"
        f"<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>AI行业每日快报 {today}</title><style>{_CSS}</style></head><body><div class='wrap'>",
        f"<header><div class='eyebrow'>QuotaRadar · AI Industry Daily Brief</div>"
        f"<h1>AI 行业每日快报</h1><p>{today} · 官方公告与权威媒体优先。每条信息均附来源网址，未能验证的条目不进入正式榜单。</p></header>",
        f"<div class='legend'><b>信源说明：</b>每条新闻均附来源网址。分级：{_badge('🟢')} 官方公告 "
        f"{_badge('🔵')} 权威媒体 {_badge('🟡')} 行业媒体 {_badge('⚪')} 转载/聚合。弱信源与旧闻会被剔除或降级。</div>",
        "<section><h2>今日头条</h2>",
    ]
    if head:
        h.extend(_news_item_html(i + 1, item, headline=True) for i, item in enumerate(head))
    else:
        h.append("<div class='card'>今日暂无通过验证的头条新闻。</div>")
    h.append("</section><section><h2>行业动态</h2>")
    if body:
        h.extend(_news_item_html(i + 3, item) for i, item in enumerate(body))
    else:
        h.append("<div class='card'>暂无其他通过验证的行业动态。</div>")
    h.append("</section><section><h2>数据与观点</h2><article class='card'><ul class='radar-list'>")
    total_changes = sum(stats["counts"].values())
    h.append(f"<li>近 24 小时本机雷达捕获模型、价格与渠道变化 <b>{total_changes}</b> 条。</li>")
    for pm in stats["price_moves"][:3]:
        h.append(f"<li>{_esc(pm['summary'])}</li>")
    for nf in stats["new_free"][:2]:
        h.append(f"<li>{_esc(nf['summary'])}</li>")
    for cb in stats["chan_bad"][:2]:
        h.append(f"<li>渠道 {_esc(cb['name'])} 当前状态：{_esc(cb['status'])}</li>")
    if total_changes == 0 and not stats["price_moves"]:
        h.append("<li>近 24 小时无显著变化。</li>")
    h.append("</ul></article></section><section><h2>信源质量评估</h2>")
    h.append("<table><thead><tr><th>信源</th><th>等级</th><th>状态</th></tr></thead><tbody>")
    for source in news.get("sources", []):
        mark = "抓取成功" if source.get("ok") else "抓取失败，已跳过"
        h.append(f"<tr><td>{_esc(source['name'])}</td><td>{_badge(source.get('grade', '⚪'))}</td>"
                 f"<td>{mark}；入选 {int(source.get('count') or 0)} 条</td></tr>")
    h.append("</tbody></table><p class='note'>所有正式条目必须包含来源网址。官方公告优先，权威媒体其次；行业媒体仅作补充，旧闻和无法验证内容自动过滤。</p></section>")
    h.append(f"<footer>生成时间：{now_iso()} · QuotaRadar AI 信息平台</footer></div></body></html>")
    return "".join(h)


def generate_daily(conn) -> dict:
    """生成今日日报：写入日报文件夹 + outputs + kv。返回写入路径。"""
    from radar.daily.news import fetch_news
    news = fetch_news()
    html = build_report(conn, news)
    report_dir = Path(os.environ.get(
        "QR_REPORT_DIR", str(Path.home() / "Documents" / "AI_Daily_Reports")))
    try:
        report_dir.mkdir(parents=True, exist_ok=True)
        out = report_dir / f"AI日报_{time.strftime('%Y-%m-%d')}.html"
        out.write_text(html, encoding="utf-8")
        saved = str(out)
    except OSError as exc:
        log.warning("日报目录不可写，仅落 outputs: %s", exc)
        saved = ""
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUTS_DIR / "ai_daily_latest.html").write_text(html, encoding="utf-8")
    kv_set(conn, "ai_daily_at", now_iso())
    kv_set(conn, "ai_daily_items", str(len([x for x in news.get("items", []) if x.get("url")])))
    log.info("AI 日报生成完成: %s", saved or "outputs")
    return {"saved": saved, "items": len([x for x in news.get("items", []) if x.get("url")])}
