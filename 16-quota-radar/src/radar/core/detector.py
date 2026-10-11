"""变更检测：对比采集快照与库内状态，产出人类可读变更事件。"""

import logging

from radar.db import now_iso

log = logging.getLogger("radar.detector")

_PRICE_EPSILON = 1e-6


def detect_and_upsert(conn, models: list[dict], now: str | None = None) -> list[dict]:
    """逐模型与库内对比：新模型 / 价格变动 / 免费状态变化 / 上下文变化。

    更新 models 表、写 price_history（仅价格变化或首次入库时），
    返回变更事件列表（供通知器消费）。调用方负责 commit。
    """
    now = now or now_iso()
    changes: list[dict] = []

    def record(kind: str, target: str, summary: str, field: str | None = None,
               old: str | None = None, new: str | None = None) -> None:
        changes.append({
            "kind": kind, "target": target, "field": field,
            "old_value": old, "new_value": new, "summary": summary,
        })
        conn.execute(
            "INSERT INTO changes(kind,target,field,old_value,new_value,summary,created_at) "
            "VALUES(?,?,?,?,?,?,?)",
            (kind, target, field, old, new, summary, now),
        )

    for m in models:
        row = conn.execute("SELECT * FROM models WHERE key=?", (m["key"],)).fetchone()

        if row is None:
            kind = "new_free_model" if m["free"] else "new_model"
            summary = f"发现新模型 {m['model_id']}（来源 {m['source']}）"
            if m["free"]:
                summary += "，免费"
            record(kind, m["key"], summary)
            conn.execute(
                "INSERT INTO models(key,provider,model_id,display_name,input_price,output_price,"
                "context_len,free,capability_score,scenario_flags,source,updated_at) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    m["key"], m["provider"], m["model_id"], m.get("display_name"),
                    m["input_price"], m["output_price"], m.get("context_len"),
                    m["free"], m.get("capability_score"), m.get("scenario_flags"),
                    m["source"], now,
                ),
            )
            conn.execute(
                "INSERT INTO price_history(model_key,input_price,output_price,captured_at) VALUES(?,?,?,?)",
                (m["key"], m["input_price"], m["output_price"], now),
            )
            continue

        model_changed = False
        updates: dict = {"updated_at": now, "capability_score": m.get("capability_score"),
                         "scenario_flags": m.get("scenario_flags"), "source": m["source"]}

        for field, label in (("input_price", "输入价"), ("output_price", "输出价")):
            old, new = row[field], m.get(field)
            if old == new:
                continue
            if old is None or new is None:
                kind = "price_unknown" if new is None else "price_available"
                change = f"{old if old is not None else '未知'} → {new if new is not None else '未知'}"
            else:
                if abs(old - new) < _PRICE_EPSILON:
                    continue
                kind = "price_drop" if new < old else "price_rise"
                direction = "↓" if new < old else "↑"
                change = f"{old} → {new} USD/1M {direction}"
            record(
                kind, m["key"],
                f"{row['display_name'] or row['model_id']} {label} {change}",
                field=field,
                old=None if old is None else str(old),
                new=None if new is None else str(new),
            )
            updates[field] = new
            model_changed = True

        if bool(row["free"]) != bool(m.get("free")):
            kind = "new_free_model" if m["free"] else "free_removed"
            if m["free"]:
                summary = f"{row['display_name'] or row['model_id']} 转为免费"
            else:
                summary = f"{row['display_name'] or row['model_id']} 不再免费（{row['input_price']}→{m.get('input_price')} USD/1M）"
            record(kind, m["key"], summary)
            updates["free"] = m["free"]
            model_changed = True

        old_ctx, new_ctx = row["context_len"], m.get("context_len")
        if old_ctx != new_ctx:
            change = f"{old_ctx if old_ctx is not None else '未知'} → {new_ctx if new_ctx is not None else '未知'}"
            record(
                "context_change", m["key"],
                f"{row['display_name'] or row['model_id']} 上下文 {change}",
                old=None if old_ctx is None else str(old_ctx),
                new=None if new_ctx is None else str(new_ctx),
            )
            updates["context_len"] = new_ctx
            model_changed = True

        old_score, new_score = row["capability_score"], m.get("capability_score")
        score_changed = (
            old_score != new_score
            if old_score is None or new_score is None
            else abs(old_score - new_score) >= 0.01
        )
        flags_changed = row["scenario_flags"] != m.get("scenario_flags")
        if model_changed or row["source"] != m["source"] or score_changed or flags_changed:
            sets = ", ".join(f"{k}=?" for k in updates)
            conn.execute(f"UPDATE models SET {sets} WHERE key=?", (*updates.values(), m["key"]))

    # 价格历史：只为价格有变的模型补记
    price_changed_keys = {
        c["target"] for c in changes
        if c["kind"] in ("price_drop", "price_rise", "price_unknown", "price_available")
    }
    for key in sorted(price_changed_keys):
        m = next(x for x in models if x["key"] == key)
        conn.execute(
            "INSERT INTO price_history(model_key,input_price,output_price,captured_at) VALUES(?,?,?,?)",
            (m["key"], m["input_price"], m["output_price"], now),
        )

    conn.commit()
    log.info("检测到 %d 个变更", len(changes))
    return changes
