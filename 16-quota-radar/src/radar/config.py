"""配置加载：环境变量 + 默认值。凭证只从环境/.env 读取，绝不落库落码。"""

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
DATA_DIR = PROJECT_ROOT / "data"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"

DATA_DIR.mkdir(exist_ok=True)
OUTPUTS_DIR.mkdir(exist_ok=True)

load_dotenv(PROJECT_ROOT / ".env")


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, "") or default)
    except ValueError:
        return default


_HHMM_RE = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")


def _time_env(name: str, default: str) -> str:
    """读取 HH:MM 配置；非法值回退默认，避免错误配置拖垮启动。"""
    value = (os.environ.get(name, "") or default).strip()
    return value if _HHMM_RE.fullmatch(value) else default


def _bool_env(name: str, default: bool = False) -> bool:
    value = (os.environ.get(name, "") or "").strip().lower()
    if not value:
        return default
    return value in {"1", "true", "yes", "on"}


@dataclass
class Settings:
    collect_interval_min: int = field(default_factory=lambda: _int_env("QR_COLLECT_INTERVAL_MIN", 30))
    probe_interval_min: int = field(default_factory=lambda: _int_env("QR_PROBE_INTERVAL_MIN", 1440))
    activity_interval_min: int = field(default_factory=lambda: _int_env("QR_ACTIVITY_INTERVAL_MIN", 60))
    digest_time: str = field(default_factory=lambda: _time_env("QR_DIGEST_TIME", "09:00"))
    daily_time: str = field(default_factory=lambda: _time_env("QR_DAILY_TIME", "07:30"))
    backup_time: str = field(default_factory=lambda: _time_env("QR_BACKUP_TIME", "03:30"))
    port: int = field(default_factory=lambda: min(max(_int_env("QR_PORT", 8000), 1), 65535))

    # 可选管理认证：配置后所有非健康检查页面/API 使用 HTTP Basic Auth。
    # 用户名默认 admin；密码只从环境读取，不写日志、不落库。
    admin_username: str = field(default_factory=lambda: os.environ.get("QR_ADMIN_USER", "admin").strip() or "admin")
    admin_password: str = field(default_factory=lambda: os.environ.get("QR_ADMIN_PASSWORD", "").strip())

    # Web 请求默认不得触发 npm/pip 安装；需要时由管理员显式开启。
    allow_web_install: bool = field(default_factory=lambda: _bool_env("QR_ALLOW_WEB_INSTALL", False))
    allowed_hosts: tuple[str, ...] = field(default_factory=lambda: tuple(
        host.strip() for host in (
            os.environ.get("QR_ALLOWED_HOSTS") or "localhost,127.0.0.1,testserver,[::1]"
        ).split(",") if host.strip()
    ))

    # 邮件通知；四项任一为空 → 日志模式
    smtp_host: str = field(default_factory=lambda: os.environ.get("SMTP_HOST", ""))
    smtp_port: int = field(default_factory=lambda: _int_env("SMTP_PORT", 465))
    smtp_user: str = field(default_factory=lambda: os.environ.get("SMTP_USER", ""))
    smtp_pass: str = field(default_factory=lambda: os.environ.get("SMTP_PASS", ""))
    smtp_to: str = field(default_factory=lambda: os.environ.get("SMTP_TO", ""))

    @property
    def notify_mode(self) -> str:
        if self.smtp_host and self.smtp_user and self.smtp_pass and self.smtp_to:
            return "email"
        return "log"

    @property
    def auth_enabled(self) -> bool:
        return bool(self.admin_password)

    @property
    def digest_parts(self) -> tuple[int, int]:
        hour, minute = self.digest_time.split(":", 1)
        return int(hour), int(minute)

    @property
    def daily_parts(self) -> tuple[int, int]:
        hour, minute = self.daily_time.split(":", 1)
        return int(hour), int(minute)

    @property
    def backup_parts(self) -> tuple[int, int]:
        hour, minute = self.backup_time.split(":", 1)
        return int(hour), int(minute)

    def api_key(self, env_name: str) -> str:
        """按变量名取自有 API key；未配置返回空串。绝不打印 key 内容。"""
        if not env_name:
            return ""
        return os.environ.get(env_name, "").strip()


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reset_settings() -> None:
    """清除进程级配置缓存；测试与热更新配置时使用。"""
    global _settings
    _settings = None


def db_path() -> Path:
    return DATA_DIR / "quotaradar.db"
