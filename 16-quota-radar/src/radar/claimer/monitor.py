"""活动页监控（半自动领取的核心）：内容哈希变化 → 提醒人工去领。"""

import hashlib
import logging

import httpx

from radar.collectors.http import USER_AGENT
from radar.db import now_iso

log = logging.getLogger("radar.activities")

_TIMEOUT = 20.0


def _hash_page(body: str) -> str:
    return hashlib.sha256(body[:200_000].encode("utf-8", "ignore")).hexdigest()[:16]


def check_activities(conn) -> list[dict]:
    """抓取各活动页，哈希变化即生成提醒事件。首轮只登记基线，不报警。"""
    changes: list[dict] = []
    now = now_iso()
    rows = conn.execute(
        "SELECT * FROM activities WHERE url IS NOT NULL AND status='pending'").fetchall()

    for row in rows:
        try:
            resp = httpx.get(row["url"], headers={"User-Agent": USER_AGENT},
                             timeout=_TIMEOUT, follow_redirects=True)
            if resp.status_code >= 400:
                log.warning("活动页 %s HTTP %d", row["id"], resp.status_code)
                continue
        except httpx.HTTPError as exc:
            log.warning("活动页抓取失败 %s: %s", row["id"], type(exc).__name__)
            continue

        digest = _hash_page(resp.text)
        old = row["content_hash"]
        conn.execute(
            "UPDATE activities SET content_hash=?, last_seen=? WHERE id=?",
            (digest, now, row["id"]),
        )
        if old and old != digest:
            changes.append({
                "kind": "activity", "target": row["id"],
                "summary": f"{row['platform']}「{row['title']}」页面有更新，可能有新活动可领，请人工查看: {row['url']}",
            })
            conn.execute(
                "INSERT INTO changes(kind,target,summary,created_at) VALUES(?,?,?,?)",
                ("activity", row["id"], changes[-1]["summary"], now),
            )

    conn.commit()
    log.info("活动页检查完成: %d 个页面, %d 条更新", len(rows), len(changes))
    return changes


def mark_done(conn, activity_id: str) -> bool:
    """人工领取完成后在仪表盘标记。"""
    cur = conn.execute(
        "UPDATE activities SET status='done', done_at=? WHERE id=?",
        (now_iso(), activity_id),
    )
    conn.commit()
    return cur.rowcount > 0
