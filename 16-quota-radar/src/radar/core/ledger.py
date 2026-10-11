"""额度台账：记录额度的获得（+）与消耗（−），按近期日均消耗做燃尽预测。"""

from datetime import datetime, timedelta

from radar.db import now_iso


def record(conn, tokens: int, channel_id: str | None = None, model_key: str | None = None,
           note: str | None = None) -> int:
    """tokens>0 = 获得额度（如签到赠送）；tokens<0 = 消耗。"""
    if tokens == 0:
        raise ValueError("tokens 不能为 0（正数=获得，负数=消耗）")
    cur = conn.execute(
        "INSERT INTO usage_log(channel_id,model_key,tokens,note,recorded_at) VALUES(?,?,?,?,?)",
        (channel_id, model_key, tokens, note, now_iso()),
    )
    conn.commit()
    return cur.lastrowid


def balance(conn, channel_id: str | None = None) -> int:
    if channel_id:
        row = conn.execute("SELECT COALESCE(SUM(tokens),0) s FROM usage_log WHERE channel_id=?",
                           (channel_id,)).fetchone()
    else:
        row = conn.execute("SELECT COALESCE(SUM(tokens),0) s FROM usage_log").fetchone()
    return int(row["s"])


def forecast(conn, channel_id: str | None = None, days: int = 7) -> dict:
    """近 N 天日均消耗 → 预计可用天数。无消耗记录时返回 days_left=None。"""
    since = (datetime.now().astimezone() - timedelta(days=days)).isoformat(timespec="seconds")
    if channel_id:
        row = conn.execute(
            "SELECT COALESCE(SUM(tokens),0) s FROM usage_log "
            "WHERE tokens<0 AND channel_id=? AND recorded_at>=?", (channel_id, since)).fetchone()
    else:
        row = conn.execute(
            "SELECT COALESCE(SUM(tokens),0) s FROM usage_log "
            "WHERE tokens<0 AND recorded_at>=?", (since,)).fetchone()
    burned = -int(row["s"])
    daily_avg = burned / days
    bal = balance(conn, channel_id)
    if daily_avg <= 0:
        return {"balance": bal, "daily_burn": 0.0, "days_left": None}
    return {
        "balance": bal,
        "daily_burn": round(daily_avg, 1),
        "days_left": round(bal / daily_avg, 1),
    }
