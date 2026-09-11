"""共享记忆（Memory）接口规范与实现。

三层设计：
* 短期记忆：LangGraph 的 AgentState（一次任务内共享，见 core/state.py）；
* 长期记忆：本模块的 :class:`SharedMemory`，跨任务沉淀知识；
* 后端可插拔：配置 CHROMA_HOST 时用 ChromaDB 向量检索，
  否则降级为本地 JSON 文件 + 关键词打分，保证零依赖也能跑。

接口规范（所有实现必须遵守）：
    write(agent, key, content, tags=None) -> None   # 写入/更新一条记忆
    read(key) -> Optional[str]                      # 按键读取
    search(query, top_k=5) -> List[dict]            # 语义/关键词检索
    snapshot() -> Dict[str, dict]                   # 全量快照（调试用）
"""
from __future__ import annotations

import json
import logging
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("agent_team.memory")

__all__ = ["SharedMemory", "InMemorySharedMemory", "ChromaSharedMemory", "create_memory"]


class SharedMemory:
    """长期记忆基类（接口规范）。"""

    def write(self, agent: str, key: str, content: str, tags: Optional[List[str]] = None) -> None:
        raise NotImplementedError

    def read(self, key: str) -> Optional[str]:
        raise NotImplementedError

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def snapshot(self) -> Dict[str, Dict[str, Any]]:
        raise NotImplementedError


class InMemorySharedMemory(SharedMemory):
    """本地文件记忆：零依赖，按关键词重合度检索，进程内缓存 + JSON 落盘。"""

    def __init__(self, persist_path: Optional[os.PathLike] = "logs/memory.json") -> None:
        self._path = Path(persist_path) if persist_path else None
        self._store: Dict[str, Dict[str, Any]] = {}
        if self._path is not None and self._path.exists():
            try:
                self._store = json.loads(self._path.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001 损坏的缓存文件不阻塞主流程
                logger.warning("记忆文件损坏，已重置: %s", self._path)

    def _persist(self) -> None:
        if self._path is None:
            return
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(
                json.dumps(self._store, ensure_ascii=False, indent=1), encoding="utf-8"
            )
        except OSError as exc:
            logger.warning("记忆落盘失败: %s", exc)

    def write(self, agent: str, key: str, content: str, tags: Optional[List[str]] = None) -> None:
        self._store[key] = {
            "agent": agent,
            "content": content,
            "tags": tags or [],
            "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        self._persist()

    def read(self, key: str) -> Optional[str]:
        item = self._store.get(key)
        return item["content"] if item else None

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        tokens = [t for t in query.lower().split() if len(t) > 1]
        scored: List[Dict[str, Any]] = []
        for key, item in self._store.items():
            blob = f"{key} {item['content']}".lower()
            score = sum(blob.count(t) for t in tokens)
            if score > 0:
                scored.append({"key": key, "agent": item["agent"], "score": score,
                               "content": item["content"][:2000]})
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]

    def snapshot(self) -> Dict[str, Dict[str, Any]]:
        return dict(self._store)


class ChromaSharedMemory(SharedMemory):
    """ChromaDB 向量记忆：语义检索，需要 CHROMA_HOST 指向运行中的 Chroma 服务。"""

    def __init__(self, host: str, port: int, collection: str = "agent_memory") -> None:
        from chromadb import HttpClient  # 延迟导入：未安装 chromadb 时可降级

        self._client = HttpClient(host=host, port=port)
        self._col = self._client.get_or_create_collection(collection)

    def write(self, agent: str, key: str, content: str, tags: Optional[List[str]] = None) -> None:
        self._col.upsert(
            ids=[key],
            documents=[content],
            metadatas=[{"agent": agent, "tags": ",".join(tags or [])}],
        )

    def read(self, key: str) -> Optional[str]:
        res = self._col.get(ids=[key])
        docs = res.get("documents") or []
        return docs[0] if docs else None

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        if not self._col.count():
            return []
        res = self._col.query(query_texts=[query], n_results=min(top_k, self._col.count()))
        out: List[Dict[str, Any]] = []
        for key, doc, meta, dist in zip(
            res["ids"][0], res["documents"][0], res["metadatas"][0], res["distances"][0]
        ):
            out.append({"key": key, "agent": meta.get("agent", ""), "score": -dist,
                        "content": doc[:2000]})
        return out

    def snapshot(self) -> Dict[str, Dict[str, Any]]:
        res = self._col.get(include=["documents", "metadatas"])
        return {
            key: {"agent": (meta or {}).get("agent", ""), "content": doc}
            for key, doc, meta in zip(res["ids"], res["documents"], res["metadatas"])
        }


def create_memory(env: Optional[Dict[str, str]] = None) -> SharedMemory:
    """记忆工厂：优先 ChromaDB（已配置且可用），否则降级本地文件记忆。"""
    env = dict(env or os.environ)
    host = env.get("CHROMA_HOST", "").strip()
    if host:
        try:
            mem = ChromaSharedMemory(host, int(env.get("CHROMA_PORT", "8000")))
            logger.info("长期记忆后端: ChromaDB (%s:%s)", host, env.get("CHROMA_PORT", "8000"))
            return mem
        except Exception as exc:  # noqa: BLE001
            logger.warning("ChromaDB 连接失败（%s），降级为本地文件记忆", exc)
    logger.info("长期记忆后端: 本地 JSON 文件 (logs/memory.json)")
    return InMemorySharedMemory(persist_path="logs/memory.json")
