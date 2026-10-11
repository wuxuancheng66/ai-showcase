"""领取框架基类与安全边界。

红线（写进基类文档，所有适配器必须遵守）：
1. 仅操作用户自有账号；
2. 遇到验证码/风控 → 抛 CaptchaRequired，由框架记录事件并通知人工，绝不尝试绕过；
3. 无法自动完成的步骤 → 抛 HumanRequired，转半自动提醒；
4. 领取频率保守（调度默认 4 小时一轮）。
"""

from dataclasses import dataclass


@dataclass
class ClaimCheck:
    claimable: bool
    reason: str = ""


@dataclass
class ClaimResult:
    status: str      # claimed / already / skipped / failed
    message: str = ""


class CaptchaRequired(Exception):
    """平台出现验证码/风控，必须停止并转人工。"""

    def __init__(self, platform: str, detail: str = ""):
        super().__init__(f"{platform} 需要人工处理: {detail}")
        self.platform = platform
        self.detail = detail


class HumanRequired(Exception):
    """流程里有自动化做不了的步骤，转半自动。"""

    def __init__(self, platform: str, detail: str = ""):
        super().__init__(f"{platform} 需要人工介入: {detail}")
        self.platform = platform
        self.detail = detail


class BaseClaimer:
    """平台领取适配器基类。子类实现 check/claim；凭证经 Vault 获取。

    requires_credentials=False 的适配器（如无需登录的公开活动）可免凭证运行。
    """

    platform: str = "base"
    enabled: bool = False
    requires_credentials: bool = True

    def __init__(self, vault=None):
        self.vault = vault

    def get_credentials(self) -> dict | None:
        return self.vault.get(self.platform) if self.vault else None

    def check(self) -> ClaimCheck:
        raise NotImplementedError

    def claim(self) -> ClaimResult:
        raise NotImplementedError


class DemoClaimer(BaseClaimer):
    """参考适配器：演示完整接入路径，默认禁用，用于测试与开发参照。"""

    platform = "demo"
    description = "模拟平台：check 恒可领，claim 返回成功"
    requires_credentials = False

    def check(self) -> ClaimCheck:
        return ClaimCheck(claimable=True, reason="演示渠道恒可领")

    def claim(self) -> ClaimResult:
        return ClaimResult(status="claimed", message="模拟领取成功（DemoClaimer）")
