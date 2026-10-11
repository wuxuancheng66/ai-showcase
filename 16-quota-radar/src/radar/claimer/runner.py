"""领取执行器：遍历已启用的适配器 → check → claim，异常转事件+通知。"""

import logging

from radar.claimer.base import BaseClaimer, CaptchaRequired, DemoClaimer, HumanRequired
from radar.claimer.vault import Vault
from radar.db import now_iso

log = logging.getLogger("radar.claims")

REGISTRY: list[BaseClaimer] = [DemoClaimer()]


def run_claims(conn, settings, vault: Vault | None = None, registry=None) -> list[dict]:
    vault = vault or Vault()
    results: list[dict] = []
    now = now_iso()

    for claimer in (registry or REGISTRY):
        if not claimer.enabled:
            continue
        if claimer.requires_credentials and claimer.get_credentials() is None:
            log.info("平台 %s 未配置凭证，跳过", claimer.platform)
            continue
        try:
            check = claimer.check()
            if not check.claimable:
                results.append({"platform": claimer.platform, "status": "skipped",
                                "message": check.reason})
                continue
            result = claimer.claim()
            results.append({"platform": claimer.platform, **result.__dict__})
            conn.execute(
                "INSERT INTO changes(kind,target,summary,created_at) VALUES(?,?,?,?)",
                ("activity", claimer.platform, f"「{claimer.platform}」领取结果: {result.status} {result.message}", now),
            )
        except CaptchaRequired as exc:
            results.append({"platform": claimer.platform, "status": "human_required",
                            "message": str(exc)})
            conn.execute(
                "INSERT INTO changes(kind,target,summary,created_at) VALUES(?,?,?,?)",
                ("claim_blocked", claimer.platform,
                 f"「{claimer.platform}」遇到验证码/风控，已自动停止转人工（绝不绕过）: {exc.detail}", now),
            )
            try:
                from radar.notify.emailer import notify
                notify("QuotaRadar 需要人工处理",
                       f"平台「{claimer.platform}」领取时遇到验证码/风控。\n"
                       f"详情: {exc.detail}\n请人工完成领取，自动化已停止以策安全。",
                       settings)
            except Exception:  # noqa: BLE001 — 通知失败不影响事件落库
                log.exception("转人工通知发送失败")
        except HumanRequired as exc:
            results.append({"platform": claimer.platform, "status": "human_required",
                            "message": str(exc)})
            conn.execute(
                "INSERT INTO changes(kind,target,summary,created_at) VALUES(?,?,?,?)",
                ("claim_blocked", claimer.platform, f"「{claimer.platform}」需人工介入: {exc.detail}", now),
            )
        except Exception as exc:  # noqa: BLE001 — 单平台失败不影响其他平台
            log.exception("平台 %s 领取异常", claimer.platform)
            results.append({"platform": claimer.platform, "status": "failed",
                            "message": f"{type(exc).__name__}: {exc}"})

    conn.commit()
    return results
