"""凭证加密库：Fernet 对称加密，key 落盘 data/secret.key（0600）。

设计原则：明文凭证只存在于内存；磁盘上只有密文与密钥文件；
密钥文件不入 git（data/ 已 ignore）；任何日志不得打印凭证内容。
"""

import json
import logging
import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from radar.config import DATA_DIR

log = logging.getLogger("radar.vault")


class VaultError(RuntimeError):
    pass


class Vault:
    def __init__(self, key_path: Path | None = None, data_path: Path | None = None):
        self.key_path = key_path or (DATA_DIR / "secret.key")
        self.data_path = data_path or (DATA_DIR / "credentials.enc")

    def _fernet(self) -> Fernet:
        if self.key_path.exists():
            key = self.key_path.read_bytes().strip()
        else:
            key = Fernet.generate_key()
            self.key_path.write_bytes(key)
            os.chmod(self.key_path, 0o600)
            log.info("已生成新凭证密钥（0600）")
        return Fernet(key)

    def _load_all(self, fernet: Fernet) -> dict:
        if not self.data_path.exists():
            return {}
        try:
            blob = json.loads(fernet.decrypt(self.data_path.read_bytes()))
            return blob if isinstance(blob, dict) else {}
        except (InvalidToken, ValueError) as exc:
            raise VaultError("凭证库无法解密（密钥不匹配或文件损坏）") from exc

    def set(self, platform: str, credentials: dict) -> None:
        fernet = self._fernet()
        data = self._load_all(fernet)
        data[platform] = credentials
        self.data_path.write_bytes(fernet.encrypt(json.dumps(data, ensure_ascii=False).encode()))
        os.chmod(self.data_path, 0o600)

    def get(self, platform: str) -> dict | None:
        fernet = self._fernet()
        return self._load_all(fernet).get(platform)

    def platforms(self) -> list[str]:
        try:
            fernet = self._fernet()
            return sorted(self._load_all(fernet).keys())
        except VaultError:
            return []

    def delete(self, platform: str) -> bool:
        fernet = self._fernet()
        data = self._load_all(fernet)
        if platform not in data:
            return False
        del data[platform]
        self.data_path.write_bytes(fernet.encrypt(json.dumps(data, ensure_ascii=False).encode()))
        return True
