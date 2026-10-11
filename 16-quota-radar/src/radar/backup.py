"""SQLite 一致性备份与完整性校验。"""

import hashlib
import os
import sqlite3
from datetime import datetime
from pathlib import Path

from radar.config import OUTPUTS_DIR
from radar.db import connect, db_path

BACKUP_DIR = OUTPUTS_DIR / "backups"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _backup_path(destination_dir: Path) -> Path:
    stamp = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")
    path = destination_dir / f"quotaradar_{stamp}.db"
    counter = 1
    while path.exists():
        path = destination_dir / f"quotaradar_{stamp}_{counter}.db"
        counter += 1
    return path


def create_backup(conn: sqlite3.Connection | None = None,
                  destination_dir: Path | None = None,
                  note: str = "manual") -> dict:
    """创建一致性快照，并在落盘前执行 SQLite quick_check。

    使用 SQLite 在线备份 API，允许采集/探活任务继续写入，不会复制处于 WAL
    中间态的半成品数据库。备份是增量产品资产，不做自动删除。
    """
    destination = Path(destination_dir or BACKUP_DIR)
    destination.mkdir(parents=True, exist_ok=True)
    final_path = _backup_path(destination)
    tmp_path = final_path.with_suffix(".db.tmp")
    own_conn = conn is None
    source = conn or connect(db_path())
    target = sqlite3.connect(tmp_path)
    try:
        source.backup(target)
        check = target.execute("PRAGMA quick_check(1)").fetchone()
        if not check or check[0] != "ok":
            raise RuntimeError(f"备份完整性检查失败: {check[0] if check else 'empty result'}")
        target.commit()
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise
    finally:
        target.close()
        if own_conn:
            source.close()

    os.replace(tmp_path, final_path)
    stat = final_path.stat()
    return {
        "name": final_path.name,
        "path": str(final_path),
        "size_bytes": stat.st_size,
        "created_at": datetime.fromtimestamp(stat.st_mtime).astimezone().isoformat(timespec="seconds"),
        "sha256": _sha256(final_path),
        "integrity": "ok",
        "note": note,
    }


def list_backups(destination_dir: Path | None = None, limit: int = 20) -> list[dict]:
    """列出已有备份，只读文件元数据，不改动任何备份。"""
    destination = Path(destination_dir or BACKUP_DIR)
    if not destination.exists():
        return []
    rows: list[dict] = []
    paths = sorted(destination.glob("quotaradar_*.db"), key=lambda p: p.stat().st_mtime, reverse=True)
    for path in paths[: max(1, min(limit, 200))]:
        stat = path.stat()
        rows.append({
            "name": path.name,
            "path": str(path),
            "size_bytes": stat.st_size,
            "created_at": datetime.fromtimestamp(stat.st_mtime).astimezone().isoformat(timespec="seconds"),
        })
    return rows

