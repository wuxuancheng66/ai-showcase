"""通知发送：SMTP 邮件优先（纯文本 + HTML 双格式）；未配置或发送失败 → 降级写 outputs/ 文件，永不抛异常中断主流程。"""

import logging
import smtplib
import time
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from radar.config import OUTPUTS_DIR, Settings

log = logging.getLogger("radar.notify")


def _send_email(subject: str, body: str, html_body: str | None, settings: Settings) -> None:
    if html_body:
        msg = MIMEMultipart("alternative")
        msg.attach(MIMEText(body, "plain", "utf-8"))
        msg.attach(MIMEText(html_body, "html", "utf-8"))
    else:
        msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = Header(subject, "utf-8")
    msg["From"] = settings.smtp_user
    msg["To"] = settings.smtp_to

    if settings.smtp_port == 465:
        server = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=20)
    else:
        server = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20)
        try:
            server.starttls()
        except smtplib.SMTPException:
            pass  # 部分内网中继不需要 STARTTLS
    try:
        server.login(settings.smtp_user, settings.smtp_pass)
        server.sendmail(settings.smtp_user, [x.strip() for x in settings.smtp_to.split(",")], msg.as_string())
    finally:
        server.quit()


def notify(subject: str, body: str, settings: Settings, html_body: str | None = None) -> str:
    """发送通知。返回送达方式描述；任何失败都降级为落盘，不抛异常。"""
    if settings.notify_mode == "email":
        try:
            _send_email(subject, body, html_body, settings)
            log.info("邮件已发送: %s", subject)
            return "email"
        except Exception as exc:  # noqa: BLE001 — 通知失败绝不能打断采集主流程
            log.error("邮件发送失败，降级为日志模式: %s", type(exc).__name__)

    path = OUTPUTS_DIR / f"notify_{time.strftime('%Y%m%d_%H%M%S')}.md"
    path.write_text(f"# {subject}\n\n{body}\n", encoding="utf-8")
    log.info("通知已落盘: %s", path.name)
    return f"log:{path.name}"
