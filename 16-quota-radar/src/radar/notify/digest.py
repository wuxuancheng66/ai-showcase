"""每日简报与变更通知。首轮采集静默；邮件发纯文本 + 排版 HTML 双格式。"""

import html as html_mod
import logging
import time
from datetime import datetime, timedelta

from radar.core.evaluator import recommend
from radar.db import connect, init_db, kv_get, kv_set, now_iso

log = logging.getLogger("radar.digest")

# 高价值事件才推送；new_model 只在简报里滚动展示
PUSH_KINDS = {"price_drop", "price_rise", "new_free_model", "free_removed",
              "channel_status", "source_error", "source_recovered", "activity", "claim_blocked"}

_KIND_LABEL = {
    "price_drop": "降价", "price_rise": "涨价", "new_free_model": "新免费模型",
    "free_removed": "免费取消", "channel_status": "渠道状态", "source_error": "源故障",
    "source_recovered": "源恢复", "activity": "活动更新", "claim_blocked": "需人工",
}


def _collect_sections(conn) -> dict:
    """一次性取简报所需全部数据，供纯文本与 HTML 两种渲染共用。"""
    recs = {}
    for scene, n in (("free", 5), ("chat", 5), ("bulk", 3)):
        try:
            recs[scene] = recommend(conn, scene, top_n=n)
        except Exception:
            recs[scene] = []

    since = (datetime.now() - timedelta(hours=24)).isoformat(timespec="seconds")
    changes = [dict(r) for r in conn.execute(
        "SELECT kind, summary FROM changes WHERE created_at>=? AND kind!='new_model' "
        "ORDER BY created_at DESC LIMIT 30", (since,)).fetchall()]
    channels = [dict(r) for r in conn.execute(
        "SELECT name, tier, status, last_checked FROM channels "
        "WHERE status!='unknown' ORDER BY status, name").fetchall()]
    activities = [dict(r) for r in conn.execute(
        "SELECT platform, title, url FROM activities WHERE status='pending' LIMIT 10").fetchall()]
    return {"free": recs["free"], "chat": recs["chat"], "bulk": recs["bulk"],
            "changes": changes, "channels": channels, "activities": activities}


def _fmt_price(r: dict) -> str:
    return "免费" if r["free"] else f"${r['blended_price']}/1M"


def _ctx(r: dict) -> str:
    return f"{r['context_len'] // 1000}k" if r["context_len"] else "—"


def build_digest(conn) -> str:
    s = _collect_sections(conn)
    today = time.strftime("%Y-%m-%d")
    lines = [f"# QuotaRadar 每日简报 {today}", ""]

    def ranking(title, rows, cols):
        lines.append(f"## {title}")
        if not rows:
            lines.append("- （暂无数据，等待首轮采集）")
        for i, r in enumerate(rows, 1):
            cells = [f"{r['model_id']}（{r['source']}）"] + [c(r) for c in cols]
            lines.append(f"{i}. " + "｜".join(str(c) for c in cells))
        lines.append("")

    ranking("🎁 免费模型榜", s["free"],
            [lambda r: f"能力 {r['capability_score']:.0f}", lambda r: f"上下文 {_ctx(r)}"])
    ranking("💰 性价比榜（日常对话）", s["chat"],
            [lambda r: f"能力 {r['capability_score']:.0f}", lambda r: f"混合价 {_fmt_price(r)}",
             lambda r: f"指数 {r['value_index']}"])
    ranking("📦 批量处理最便宜", s["bulk"],
            [lambda r: f"混合价 {_fmt_price(r)}", lambda r: f"能力 {r['capability_score']:.0f}"])

    lines.append("## 🔄 近 24h 变更（不含普通新模型）")
    if s["changes"]:
        lines.extend(f"- [{_KIND_LABEL.get(c['kind'], c['kind'])}] {c['summary']}" for c in s["changes"])
    else:
        lines.append("- 无")
    lines.append("")

    lines.append("## 📡 渠道状态（已验证）")
    if s["channels"]:
        lines.extend(
            f"- {c['name']}：{c['status']}（{c['tier']}，验证于 {(c['last_checked'] or '')[:16]}）"
            for c in s["channels"])
    else:
        lines.append("- 暂无已验证渠道（配置 .env 中的 key 后自动探活）")
    lines.append("")

    lines.append("## 🎫 待领取活动")
    if s["activities"]:
        lines.extend(f"- {a['platform']}｜{a['title']}（{a['url']}）" for a in s["activities"])
    else:
        lines.append("- 无待办")

    lines.append("")
    lines.append("> 免费渠道信息以「最后验证时间」为准，未验证渠道请勿当作可用依据。")
    return "\n".join(lines)


# ---------- HTML 渲染（邮件客户端友好：表格布局 + 内联样式） ----------

_CSS_WRAP = ("font-family:-apple-system,'PingFang SC','Microsoft YaHei',sans-serif;"
             "max-width:640px;margin:0 auto;background:#f5f7fb;color:#1c2333;"
             "border:1px solid #e3e8f2;border-radius:12px;overflow:hidden")
_CSS_HEAD = ("background:#0f1420;color:#fff;padding:18px 24px;font-size:18px;font-weight:700")
_CSS_HEAD_SUB = ("color:#8b96ad;font-size:12px;font-weight:400;margin-top:4px")
_CSS_SEC = ("margin:0;padding:20px 24px 4px;font-size:15px;font-weight:700;color:#0f1420")
_CSS_TABLE = "width:100%;border-collapse:collapse;font-size:13px"
_CSS_TH = ("text-align:left;padding:6px 8px;color:#8b96ad;font-weight:500;"
           "border-bottom:1px solid #e3e8f2")
_CSS_TD = "padding:6px 8px;border-bottom:1px solid #eef1f7"
_CSS_BAD = ("display:inline-block;padding:1px 8px;border-radius:9px;font-size:11px;"
            "background:#eef4ff;color:#2f6bff")
_CSS_BADGE = {"降价": "background:#e5f7ee;color:#1d9e63", "新免费模型": "background:#e5f7ee;color:#1d9e63",
              "涨价": "background:#fdecec;color:#d64545", "免费取消": "background:#fdecec;color:#d64545",
              "源故障": "background:#fdecec;color:#d64545", "需人工": "background:#fdecec;color:#d64545",
              "渠道状态": "background:#fdf3e0;color:#b97f16", "活动更新": "background:#fdf3e0;color:#b97f16"}
_CSS_FOOT = ("padding:16px 24px;color:#8b96ad;font-size:11px;border-top:1px solid #eef1f7;"
             "margin-top:12px")


def _esc(t) -> str:
    return html_mod.escape(str(t))


def _table(headers, rows_builder) -> str:
    th = "".join(f'<th style="{_CSS_TH}">{_esc(h)}</th>' for h in headers)
    trs = "".join(rows_builder)
    return (f'<table style="{_CSS_TABLE}"><tr>{th}</tr>'
            + (trs or f'<tr><td style="{_CSS_TD};color:#8b96ad">暂无数据，等待首轮采集</td></tr>')
            + "</table>")


def build_digest_html(conn) -> str:
    s = _collect_sections(conn)
    today = time.strftime("%Y-%m-%d")
    h = ['<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8"></head>',
         '<body style="margin:0;padding:16px;background:#eef1f7">',
         f'<div style="{_CSS_WRAP}">',
         f'<div style="{_CSS_HEAD}">🎯 QuotaRadar 每日简报'
         f'<div style="{_CSS_HEAD_SUB}">{today} · AI 额度雷达 · 自动生成</div></div>']

    def model_ranking(title, rows, headers, cell_fns):
        h.append(f'<div style="{_CSS_SEC}">{title}</div>')

        def builder():
            for i, r in enumerate(rows, 1):
                tds = "".join(
                    f'<td style="{_CSS_TD}">{cell(r)}</td>' for cell in cell_fns)
                yield (f'<tr><td style="{_CSS_TD};color:#8b96ad">{i}</td>'
                       f'<td style="{_CSS_TD};font-weight:600">{_esc(r["model_id"])}</td>{tds}</tr>')
        h.append(_table(["#", "模型"] + headers, builder()))

    model_ranking("🎁 免费模型榜", s["free"], ["能力", "上下文"],
                  [lambda r: f'<b style="color:#1d9e63">{r["capability_score"]:.0f}</b>',
                   lambda r: _ctx(r)])
    model_ranking("💰 性价比榜（日常对话）", s["chat"], ["能力", "混合价", "指数"],
                  [lambda r: f'{r["capability_score"]:.0f}',
                   lambda r: f'<b>${r["blended_price"]}</b>/1M',
                   lambda r: f'<b style="color:#2f6bff">{r["value_index"]}</b>'])
    model_ranking("📦 批量处理最便宜", s["bulk"], ["混合价", "能力"],
                  [lambda r: f'<b>${r["blended_price"]}</b>/1M',
                   lambda r: f'{r["capability_score"]:.0f}'])

    h.append(f'<div style="{_CSS_SEC}">🔄 近 24h 变更</div>')
    if s["changes"]:
        def change_rows():
            for c in s["changes"][:15]:
                label = _KIND_LABEL.get(c["kind"], c["kind"])
                style = _CSS_BADGE.get(label, "")
                yield (f'<tr><td style="{_CSS_TD};white-space:nowrap">'
                       f'<span style="{_CSS_BAD};{style}">{_esc(label)}</span></td>'
                       f'<td style="{_CSS_TD}">{_esc(c["summary"])}</td></tr>')
        h.append(_table(["类型", "内容"], change_rows()))
    else:
        h.append(_table(["类型", "内容"], iter([])))

    h.append(f'<div style="{_CSS_SEC}">📡 渠道状态（已验证）</div>')

    def chan_rows():
        for c in s["channels"]:
            color = {"ok": "#1d9e63", "limited": "#b97f16"}.get(c["status"], "#d64545")
            yield (f'<tr><td style="{_CSS_TD};font-weight:600">{_esc(c["name"])}</td>'
                   f'<td style="{_CSS_TD};color:{color};font-weight:700">{_esc(c["status"])}</td>'
                   f'<td style="{_CSS_TD};color:#8b96ad">{_esc((c["last_checked"] or "")[:16])}</td></tr>')
    h.append(_table(["渠道", "状态", "最后验证"], chan_rows()))

    h.append(f'<div style="{_CSS_SEC}">🎫 待领取活动</div>')

    def act_rows():
        for a in s["activities"]:
            yield (f'<tr><td style="{_CSS_TD};font-weight:600">{_esc(a["platform"])}</td>'
                   f'<td style="{_CSS_TD}">{_esc(a["title"])} '
                   f'<a href="{_esc(a["url"])}" style="color:#2f6bff">去领取 →</a></td></tr>')
    h.append(_table(["平台", "操作"], act_rows()))

    h.append(f'<div style="{_CSS_FOOT}">免费渠道信息以「最后验证时间」为准 · '
             f'<a href="http://localhost:8000" style="color:#2f6bff">打开仪表盘</a></div>')
    h.append("</div></body></html>")
    return "".join(h)


def _alert_html(pending: list[dict]) -> str:
    rows = "".join(
        f'<tr><td style="{_CSS_TD};white-space:nowrap">'
        f'<span style="{_CSS_BAD};{_CSS_BADGE.get(_KIND_LABEL.get(c["kind"], c["kind"]), "")}">'
        f'{_esc(_KIND_LABEL.get(c["kind"], c["kind"]))}</span></td>'
        f'<td style="{_CSS_TD}">{_esc(c["summary"])}</td></tr>'
        for c in pending)
    return ('<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8"></head>'
            '<body style="margin:0;padding:16px;background:#eef1f7">'
            f'<div style="{_CSS_WRAP}">'
            f'<div style="{_CSS_HEAD}">🔔 QuotaRadar 变更提醒'
            f'<div style="{_CSS_HEAD_SUB}">{time.strftime("%Y-%m-%d %H:%M")} · 共 {len(pending)} 条</div></div>'
            f'<div style="{_CSS_SEC}">值得关注的变更</div>'
            f'<table style="{_CSS_TABLE}"><tr><th style="{_CSS_TH}">类型</th>'
            f'<th style="{_CSS_TH}">内容</th></tr>{rows}</table>'
            f'<div style="{_CSS_FOOT}"><a href="http://localhost:8000" style="color:#2f6bff">打开仪表盘查看详情</a></div>'
            f'</div></body></html>')


def handle_changes(conn, changes: list[dict], settings) -> str:
    """采集后调用：首轮静默；此后高价值变更**不再单独发信**，
    统一并入每日 09:00 简报（邮件频率 = 1 天 1 封）。
    仅「转人工」类安全告警（claim_blocked）保留即时邮件。
    返回送达方式描述。"""
    if not changes:
        return "no_changes"

    if not kv_get(conn, "first_collect_done"):
        conn.execute("UPDATE changes SET notified=1")
        conn.commit()
        kv_set(conn, "first_collect_done", now_iso())
        log.info("首轮采集静默处理 %d 条事件", len(changes))
        return "silent_first_run"

    pending = [c for c in changes if c["kind"] in PUSH_KINDS]
    if not pending:
        return "only_low_value"

    # 并入每日简报：标记为已通知，简报的「近 24h 变更」板块会完整呈现
    conn.execute(
        "UPDATE changes SET notified=1 WHERE notified=0 AND kind IN "
        "('price_drop','price_rise','new_free_model','free_removed','channel_status',"
        "'source_error','source_recovered','activity')")
    conn.commit()
    log.info("%d 条变更并入每日简报（不再单独发信）", len(pending))
    return "queued_for_digest"


def job_digest(conn=None) -> str:
    """生成简报并送达；同时落盘 outputs/ 供仪表盘展示。"""
    own = conn is None
    if own:
        init_db()
        conn = connect()
    try:
        body = build_digest(conn)
        html_body = build_digest_html(conn)
        from radar.config import OUTPUTS_DIR
        (OUTPUTS_DIR / "latest_digest.md").write_text(body, encoding="utf-8")
        (OUTPUTS_DIR / "latest_digest.html").write_text(html_body, encoding="utf-8")
        from radar.notify.emailer import notify
        from radar.config import get_settings
        return notify(f"QuotaRadar 每日简报 {time.strftime('%m-%d')}", body, get_settings(),
                      html_body=html_body)
    finally:
        if own:
            conn.close()
