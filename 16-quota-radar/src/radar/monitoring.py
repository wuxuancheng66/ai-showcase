"""本地额度与 Token 监测：只采集可验证数据，不读取或输出密钥值。"""

import json
import logging
import re
import sqlite3
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

import httpx

from radar.agent_catalog import AGENT_SPECS, list_agents
from radar.config import get_settings
from radar.db import now_iso

log = logging.getLogger("radar.monitoring")
_lock = threading.Lock()

_CODEX_USAGE_RE = re.compile(r"total_usage_tokens=(\d+)")
_CODEX_LIMIT_RE = re.compile(r"auto_compact_scope_limit=Some\((\d+)\)")
_CODEX_TURN_RE = re.compile(r"turn_id=([A-Za-z0-9-]+)")
_TERMINAL_AGENT_HINTS = {"Codex CLI", "Claude Code", "Hermes Agent", "OpenClaw"}


def _host_paths(*parts: str) -> list[Path]:
    relative = Path(*parts)
    return [Path.home() / relative, Path("/host") / relative]


def _first_existing(*parts: str) -> Path | None:
    for path in _host_paths(*parts):
        if path.exists():
            return path
    return None


def _record(subject: str, name: str, source: str, status: str = "ok", **kwargs) -> dict:
    item = {
        "subject": subject,
        "name": name,
        "source": source,
        "status": status,
        "input_tokens": None,
        "output_tokens": None,
        "cache_tokens": None,
        "used_tokens": None,
        "limit_tokens": None,
        "balance_value": None,
        "balance_unit": None,
        "daily_burn": None,
        "days_left": None,
        "cost_usd": None,
        "confidence": 0.7,
        "detail": "",
    }
    item.update(kwargs)
    return item


def _monitor_codex() -> dict | None:
    db = _first_existing(".codex", "logs_2.sqlite")
    if not db:
        return None
    cutoff = int(time.time() - 7 * 86400)
    try:
        conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        rows = conn.execute(
            "SELECT ts, feedback_log_body FROM logs "
            "WHERE ts>=? AND feedback_log_body LIKE '%post sampling token usage%' "
            "ORDER BY ts DESC LIMIT 1200",
            (cutoff,),
        ).fetchall()
        conn.close()
    except (OSError, sqlite3.Error):
        return None

    turns: dict[str, int] = {}
    limits: list[int] = []
    for _ts, body in rows:
        body = body or ""
        turn = _CODEX_TURN_RE.search(body)
        total = _CODEX_USAGE_RE.search(body)
        limit = _CODEX_LIMIT_RE.search(body)
        if turn and total:
            turns[turn.group(1)] = max(turns.get(turn.group(1), 0), int(total.group(1)))
        if limit:
            limits.append(int(limit.group(1)))
    if not turns:
        return _record(
            "codex", "Codex CLI", "local_logs", "detected", confidence=0.8,
            detail="已检测到本机运行日志，暂未发现 Token 统计记录",
        )
    used = sum(turns.values())
    return _record(
        "codex", "Codex CLI", "local_logs", "ok",
        used_tokens=used,
        limit_tokens=max(limits) if limits else None,
        daily_burn=round(used / 7, 1),
        confidence=0.82,
        detail="来自 Codex 本地日志；统计近 7 日上下文 Token，不代表订阅剩余额度",
    )


def _monitor_hermes() -> dict | None:
    db = _first_existing(".hermes", "state.db")
    if not db:
        return None
    cutoff = time.time() - 7 * 86400
    try:
        conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        row = conn.execute(
            "SELECT COALESCE(SUM(input_tokens),0) input_tokens, "
            "COALESCE(SUM(output_tokens),0) output_tokens, "
            "COALESCE(SUM(cache_read_tokens),0) cache_tokens, "
            "COALESCE(SUM(estimated_cost_usd),0) estimated_cost, "
            "COUNT(*) sessions FROM sessions WHERE started_at>=?",
            (cutoff,),
        ).fetchone()
        conn.close()
    except (OSError, sqlite3.Error):
        return None
    input_tokens, output_tokens, cache_tokens, cost, sessions = row
    used = int(input_tokens or 0) + int(output_tokens or 0)
    return _record(
        "hermes", "Hermes Agent", "local_state", "ok" if sessions else "detected",
        input_tokens=int(input_tokens or 0),
        output_tokens=int(output_tokens or 0),
        cache_tokens=int(cache_tokens or 0),
        used_tokens=used,
        daily_burn=round(used / 7, 1),
        cost_usd=round(float(cost or 0), 6),
        confidence=0.9,
        detail="来自 Hermes 本地会话统计；余额需由模型平台另行提供",
    )


def _monitor_claude() -> dict | None:
    root = _first_existing(".claude", "projects")
    if not root:
        return None
    cutoff = time.time() - 7 * 86400
    input_tokens = output_tokens = cache_tokens = 0
    found = False
    for path in root.glob("*/*.jsonl"):
        try:
            if path.stat().st_mtime < cutoff:
                continue
            for line in path.open(encoding="utf-8", errors="ignore"):
                try:
                    data = json.loads(line)
                except (TypeError, ValueError):
                    continue
                usage = ((data.get("message") or {}).get("usage") or data.get("usage") or {})
                if not isinstance(usage, dict) or not usage:
                    continue
                found = True
                input_tokens += int(usage.get("input_tokens") or 0)
                output_tokens += int(usage.get("output_tokens") or 0)
                cache_tokens += int(usage.get("cache_read_input_tokens") or 0)
                cache_tokens += int(usage.get("cache_creation_input_tokens") or 0)
        except OSError:
            continue
    if not found:
        return _record(
            "claude-code", "Claude Code", "local_logs", "detected", confidence=0.78,
            detail="已检测到 Claude Code 登录态，暂未发现 Token 统计记录",
        )
    used = input_tokens + output_tokens
    return _record(
        "claude-code", "Claude Code", "local_logs", "ok",
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_tokens=cache_tokens,
        used_tokens=used,
        daily_burn=round(used / 7, 1),
        confidence=0.86,
        detail="来自 Claude Code 本地会话日志；订阅额度由客户端管理，网页不读取密码或凭证",
    )


def _monitor_agent_presence(conn) -> list[dict]:
    records = []
    for agent in list_agents(conn):
        if not agent.get("detected"):
            continue
        subject = agent["id"]
        if subject in {"codex", "hermes", "claude-code"}:
            continue
        records.append(_record(
            subject, agent["name"], "local_presence", "detected",
            confidence=0.92,
            detail=(
                "已检测到本机安装或登录态；支持电脑操作"
                if agent.get("computer_control") else
                "已检测到本机安装或登录态"
            ),
        ))
    return records


def _provider_balances(settings) -> list[dict]:
    records = []
    adapters = [
        ("openrouter-free", "OpenRouter 免费模型", "OPENROUTER_API_KEY",
         "https://openrouter.ai/api/v1/credits", "openrouter"),
        ("deepseek", "DeepSeek API", "DEEPSEEK_API_KEY",
         "https://api.deepseek.com/user/balance", "deepseek"),
    ]
    for subject, name, env_name, url, kind in adapters:
        key = settings.api_key(env_name)
        if not key:
            continue
        try:
            response = httpx.get(
                url, headers={"Authorization": f"Bearer {key}"}, timeout=15,
                follow_redirects=True,
            )
            if response.status_code != 200:
                records.append(_record(
                    subject, name, "provider_api", "error", confidence=0.95,
                    detail=f"余额接口返回 HTTP {response.status_code}",
                ))
                continue
            data = response.json()
            if kind == "openrouter":
                payload = data.get("data") or data
                total = float(payload.get("total_credits") or 0)
                used_usd = float(payload.get("total_usage") or 0)
                records.append(_record(
                    subject, name, "provider_api", "ok",
                    balance_value=round(total - used_usd, 6),
                    balance_unit="USD",
                    cost_usd=round(used_usd, 6),
                    limit_tokens=None,
                    confidence=1.0,
                    detail="OpenRouter 官方 credits 接口",
                ))
            else:
                infos = data.get("balance_infos") or []
                info = infos[0] if infos else {}
                balance = float(info.get("total_balance") or 0)
                records.append(_record(
                    subject, name, "provider_api", "ok",
                    balance_value=balance,
                    balance_unit=info.get("currency") or "CNY",
                    confidence=1.0,
                    detail="DeepSeek 官方余额接口",
                ))
        except (httpx.HTTPError, TypeError, ValueError) as exc:
            log.warning("余额监测失败 %s: %s", subject, type(exc).__name__)
            records.append(_record(
                subject, name, "provider_api", "error", confidence=0.8,
                detail=f"余额接口请求失败（{type(exc).__name__}）",
            ))
    return records


def _enrich_forecast(conn, record: dict) -> dict:
    if record.get("balance_value") is None:
        return record
    rows = conn.execute(
        "SELECT balance_value,captured_at FROM monitor_snapshots "
        "WHERE subject=? AND balance_value IS NOT NULL ORDER BY id DESC LIMIT 20",
        (record["subject"],),
    ).fetchall()
    previous = None
    new_time = datetime.fromisoformat(record["captured_at"])
    for candidate in rows:
        try:
            old_time = datetime.fromisoformat(candidate["captured_at"])
        except (TypeError, ValueError):
            continue
        if (new_time - old_time).total_seconds() >= 3600:
            previous = candidate
            break
    if not previous:
        return record
    try:
        old_value = float(previous["balance_value"])
    except (TypeError, ValueError):
        return record
    consumed = old_value - float(record["balance_value"])
    if consumed <= 0:
        return record
    days = max((new_time - old_time).total_seconds() / 86400, 1 / 24)
    daily = consumed / days
    record["daily_burn"] = round(daily, 6)
    record["days_left"] = round(float(record["balance_value"]) / daily, 1) if daily > 0 else None
    return record


def _save(conn, records: list[dict]) -> None:
    for record in records:
        record["captured_at"] = now_iso()
        record = _enrich_forecast(conn, record)
        conn.execute(
            "INSERT INTO monitor_snapshots(subject,name,source,status,input_tokens,output_tokens,"
            "cache_tokens,used_tokens,limit_tokens,balance_value,balance_unit,daily_burn,days_left,"
            "cost_usd,confidence,detail,captured_at) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                record["subject"], record["name"], record["source"], record["status"],
                record.get("input_tokens"), record.get("output_tokens"), record.get("cache_tokens"),
                record.get("used_tokens"), record.get("limit_tokens"), record.get("balance_value"),
                record.get("balance_unit"), record.get("daily_burn"), record.get("days_left"),
                record.get("cost_usd"), record.get("confidence", 0.5), record.get("detail"),
                record["captured_at"],
            ),
        )
    conn.commit()


def refresh_local(conn, force: bool = False, max_age_seconds: int = 120) -> bool:
    """刷新本地 Token/运行状态。快速、无网络，适合页面打开时调用。"""
    row = conn.execute("SELECT value FROM kv WHERE key='monitor_local_at'").fetchone()
    if row and not force:
        try:
            age = (datetime.now().astimezone() - datetime.fromisoformat(row["value"])).total_seconds()
            if age < max_age_seconds:
                return False
        except ValueError:
            pass
    if not _lock.acquire(blocking=False):
        return False
    try:
        records = []
        for adapter in (_monitor_codex, _monitor_hermes, _monitor_claude):
            try:
                item = adapter()
            except Exception as exc:  # noqa: BLE001 — 单个监测器失败不影响其他来源
                log.warning("本地监测失败 %s: %s", adapter.__name__, type(exc).__name__)
                item = None
            if item:
                records.append(item)
        records.extend(_monitor_agent_presence(conn))
        _save(conn, records)
        conn.execute(
            "INSERT INTO kv(key,value) VALUES('monitor_local_at',?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (now_iso(),),
        )
        conn.commit()
        return True
    finally:
        _lock.release()


def refresh_providers(conn, force: bool = False, max_age_seconds: int = 900) -> bool:
    """刷新有官方余额接口的渠道；未配置 key 的渠道自动跳过。"""
    if not force:
        row = conn.execute("SELECT value FROM kv WHERE key='monitor_provider_at'").fetchone()
        if row:
            try:
                age = (datetime.now().astimezone() - datetime.fromisoformat(row["value"])).total_seconds()
                if age < max_age_seconds:
                    return False
            except ValueError:
                pass
    try:
        records = _provider_balances(get_settings())
    except Exception as exc:  # noqa: BLE001
        log.warning("渠道余额监测失败: %s", type(exc).__name__)
        return False
    _save(conn, records)
    conn.execute(
        "INSERT INTO kv(key,value) VALUES('monitor_provider_at',?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (now_iso(),),
    )
    conn.commit()
    return True


def latest_metrics(conn) -> dict[str, dict]:
    rows = conn.execute(
        "SELECT m.* FROM monitor_snapshots m JOIN ("
        "SELECT subject,MAX(id) id FROM monitor_snapshots GROUP BY subject"
        ") x ON m.id=x.id"
    ).fetchall()
    return {row["subject"]: dict(row) for row in rows}


def _metric_aliases() -> dict[str, str]:
    aliases = {}
    for spec in AGENT_SPECS:
        for key in [spec["id"], spec["name"], *spec.get("aliases", [])]:
            aliases[str(key).lower()] = spec["id"]
    return aliases


def metric_for(entry: dict, metrics: dict[str, dict]) -> dict | None:
    aliases = _metric_aliases()
    candidates = [entry.get("id"), entry.get("name")]
    for key in candidates:
        if not key:
            continue
        if key in metrics:
            return metrics[key]
        subject = aliases.get(str(key).lower())
        if subject and subject in metrics:
            return metrics[subject]
    return None


def decorate_entry(entry: dict, metric: dict | None) -> dict:
    if not metric:
        entry.update({
            "monitor_source": None, "monitor_status": None,
            "balance_value": None, "balance_unit": None,
            "input_tokens": None, "output_tokens": None, "cache_tokens": None,
            "used_tokens": None, "limit_tokens": None,
            "last_monitored": None, "monitor_detail": None, "confidence": None,
        })
        return entry
    entry.update({
        "monitor_source": metric.get("source"),
        "monitor_status": metric.get("status"),
        "balance_value": metric.get("balance_value"),
        "balance_unit": metric.get("balance_unit"),
        "input_tokens": metric.get("input_tokens"),
        "output_tokens": metric.get("output_tokens"),
        "cache_tokens": metric.get("cache_tokens"),
        "used_tokens": metric.get("used_tokens"),
        "limit_tokens": metric.get("limit_tokens"),
        "daily_burn": metric.get("daily_burn") if metric.get("daily_burn") is not None else entry.get("daily_burn"),
        "days_left": metric.get("days_left") if metric.get("days_left") is not None else entry.get("days_left"),
        "last_monitored": metric.get("captured_at"),
        "monitor_detail": metric.get("detail"),
        "confidence": metric.get("confidence"),
    })
    return entry


def summary(conn) -> dict:
    metrics = list(latest_metrics(conn).values())
    total_tokens = sum(int(m.get("used_tokens") or 0) for m in metrics)
    balance_count = sum(1 for m in metrics if m.get("balance_value") is not None)
    return {
        "monitored": len(metrics),
        "token_used_7d": total_tokens,
        "balance_count": balance_count,
        "last_at": max((m.get("captured_at") or "" for m in metrics), default=""),
    }
