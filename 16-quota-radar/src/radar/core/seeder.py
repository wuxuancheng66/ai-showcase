"""种子同步：把 config/*.yaml 的渠道与活动同步进库。

幂等：配置字段随每次启动更新（改 yaml 即生效），
但 status / last_checked / last_ok / content_hash 等运行时状态永不回退。
"""

import logging

import yaml

from radar.config import CONFIG_DIR

log = logging.getLogger("radar.seeder")

_CHANNEL_SQL = """
INSERT INTO channels(id,name,provider,tier,url,kind,requires_key,env_key,probe_type,
                     probe_base_url,probe_model,free_tier_desc,note,status)
VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?, 'unknown')
ON CONFLICT(id) DO UPDATE SET
    name=excluded.name, provider=excluded.provider, tier=excluded.tier, url=excluded.url,
    kind=excluded.kind, requires_key=excluded.requires_key, env_key=excluded.env_key,
    probe_type=excluded.probe_type, probe_base_url=excluded.probe_base_url,
    probe_model=excluded.probe_model, free_tier_desc=excluded.free_tier_desc, note=excluded.note
"""

_ACTIVITY_SQL = """
INSERT INTO activities(id,platform,title,url,kind,note,status)
VALUES(?,?,?,?,?,?, 'pending')
ON CONFLICT(id) DO UPDATE SET
    platform=excluded.platform, title=excluded.title, url=excluded.url,
    kind=excluded.kind, note=excluded.note
"""


def sync_channels(conn) -> int:
    with open(CONFIG_DIR / "channels.yaml", encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh) or {}
    rows = cfg.get("channels") or []
    for c in rows:
        probe = c.get("probe") or {}
        conn.execute(
            _CHANNEL_SQL,
            (
                c["id"], c["name"], c.get("provider"), c.get("tier", "free"), c.get("url"),
                c.get("kind", "api"), 1 if c.get("requires_key") else 0,
                c.get("env_key") or "",
                probe.get("type", "none"), probe.get("base_url"), probe.get("model"),
                c.get("free_tier_desc"), c.get("note"),
            ),
        )
    conn.commit()
    log.info("渠道种子同步 %d 条", len(rows))
    return len(rows)


def sync_activities(conn) -> int:
    with open(CONFIG_DIR / "activities.yaml", encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh) or {}
    rows = cfg.get("activities") or []
    for a in rows:
        conn.execute(
            _ACTIVITY_SQL, (a["id"], a["platform"], a["title"], a.get("url"), a.get("kind"), a.get("note"))
        )
    conn.commit()
    log.info("活动种子同步 %d 条", len(rows))
    return len(rows)


def run_seeders(conn) -> None:
    sync_channels(conn)
    sync_activities(conn)
