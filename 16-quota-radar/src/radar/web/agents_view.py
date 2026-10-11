"""本机 agent 板块：每个 agent 一个详情页 = 使用手册（去旧补新）+ 额度/预测 + 故障排查。"""

import os
import re
from pathlib import Path
from urllib.parse import urlsplit

import yaml
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from radar.config import get_settings
from radar.core import ledger
from radar.core.fleet import fleet_inventory
from radar.agent_catalog import get_agent as catalog_get_agent
from radar.agent_catalog import list_agents as catalog_list_agents
from radar.web.deps import get_db

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")


def _kb_dir() -> Path:
    raw = os.environ.get("QR_KB_DIR", str(Path(__file__).resolve().parents[2] / "manuals"))
    for cand in (Path(raw), Path("/host/kb")):
        if cand.is_dir():
            return cand
    return Path(raw)


def _manual_path(name: str) -> Path | None:
    """把配置中的手册名限制在知识库目录内，并拒绝符号链接逃逸。"""
    if not name or Path(name).name != name or Path(name).suffix.lower() != ".md":
        return None
    base = _kb_dir().resolve()
    candidate = (base / name).resolve()
    if not candidate.is_relative_to(base) or not candidate.is_file():
        return None
    return candidate


def _safe_link(url: str) -> str:
    try:
        parsed = urlsplit(url)
    except ValueError:
        return "#"
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return "#"
    return url


def load_registry() -> list[dict]:
    with open(Path(__file__).resolve().parent.parent.parent / "config" / "manuals.yaml",
              encoding="utf-8") as fh:
        return (yaml.safe_load(fh) or {}).get("agents") or []


def _md_to_html(md_text: str) -> str:
    """轻量 Markdown 渲染（标题/粗体/列表/代码/链接），不引入重依赖。"""
    import html as h

    out, in_code = [], False
    for line in md_text.splitlines():
        if line.strip().startswith("```"):
            out.append("</pre>" if in_code else "<pre>")
            in_code = not in_code
            continue
        if in_code:
            out.append(h.escape(line))
            continue
        s = h.escape(line)
        s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
        s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
        s = re.sub(
            r"\[(.+?)\]\((.+?)\)",
            lambda m: f'<a href="{h.escape(_safe_link(h.unescape(m.group(2))))}" rel="noopener noreferrer">{m.group(1)}</a>',
            s,
        )
        if re.match(r"^###\s", s):
            out.append(f"<h3>{s[4:]}</h3>")
        elif re.match(r"^##\s", s):
            out.append(f"<h2>{s[3:]}</h2>")
        elif re.match(r"^#\s", s):
            out.append(f"<h1>{s[2:]}</h1>")
        elif re.match(r"^[-*]\s", s):
            out.append(f"• {s[2:]}")
        elif re.match(r"^\d+\.\s", s):
            out.append(s)
        else:
            out.append(f"{s}<br>")
    text = "\n".join(out)
    # 相邻列表行合并成 ul
    text = re.sub(r"(?:• .*\n)+", lambda m: "<ul>" + "".join(
        f"<li>{ln[2:]}</li>" for ln in m.group(0).strip().split("\n")) + "</ul>\n", text)
    return text


def _fleet_entry(conn, name_keywords: list[str]) -> dict | None:
    inv = fleet_inventory(conn, get_settings())
    for group in ("paid", "free"):
        for e in inv[group]:
            if any(kw in e["name"] for kw in name_keywords):
                return e
    return None


def _manual_entry(key: str) -> dict:
    registry = load_registry()
    return next((a for a in registry if a["key"] == key), {})


def _cards(conn) -> list[dict]:
    from radar.monitoring import latest_metrics, metric_for, refresh_local
    refresh_local(conn)
    metrics = latest_metrics(conn)
    cards = []
    for agent in catalog_list_agents(conn):
        manual = _manual_entry(agent.get("manual_key") or agent["id"])
        manuals = [m for m in manual.get("manuals", []) if _manual_path(m)]
        entry = _fleet_entry(conn, manual.get("platforms", agent.get("aliases", [])))
        metric = metric_for(agent, metrics)
        cards.append({**agent, "manuals": manuals, "entry": entry, "metric": metric})
    return cards


@router.get("/agents", response_class=HTMLResponse)
def agents_page(request: Request, conn=Depends(get_db)):
    return templates.TemplateResponse(request, "agents.html", {"cards": _cards(conn)})


@router.get("/agents/{key}", response_class=HTMLResponse)
def agent_detail(request: Request, key: str, conn=Depends(get_db)):
    agent = catalog_get_agent(key, conn)
    if not agent:
        raise HTTPException(404, "未知 agent")
    manual = _manual_entry(agent.get("manual_key") or key)
    manual_html, manual_files = "", []
    for m in manual.get("manuals", []):
        f = _manual_path(m)
        if f:
            manual_files.append(m)
            manual_html += _md_to_html(f.read_text(encoding="utf-8"))
    entry = _fleet_entry(conn, manual.get("platforms", agent.get("aliases", [])))
    from radar.monitoring import latest_metrics, metric_for, refresh_local
    refresh_local(conn)
    metric = metric_for(agent, latest_metrics(conn))
    channel_id = manual.get("channel_id") or key
    usage = [dict(r) for r in conn.execute(
        "SELECT * FROM usage_log WHERE channel_id=? OR channel_id=? ORDER BY id DESC LIMIT 10",
        (key, channel_id))]
    balance = ledger.balance(conn, channel_id)
    fc = ledger.forecast(conn, channel_id) if balance else {"days_left": None}
    return templates.TemplateResponse(request, "agent_detail.html", {
        "agent": agent, "key": key, "manual_html": manual_html, "manual_files": manual_files,
        "entry": entry, "usage": usage, "balance": balance, "forecast": fc, "metric": metric,
        "manual_key": manual.get("key"),
    })
