"""本机扫描器：发现电脑上配置过哪些 AI 平台（凭变量名指纹，绝不读取/存储/显示密钥值）。

三层能力：
1. scan()      —— 扫描已知配置位置，返回 {平台: 发现位置列表}，只含变量名与文件路径；
2. sync_local()—— 把发现结果写入 kv + 自动把"有可领活动的平台"登记进活动中心；
3. import_keys()—— 可选：把发现的 key 追加进本产品 .env（供探活使用），值不落日志不进对话。

隐私红线：任何返回结构、日志、kv 中都不包含密钥值；import_keys 直接写文件，不回显。
"""

import json
import logging
import os
import re
from pathlib import Path

import yaml

from radar.config import CONFIG_DIR, PROJECT_ROOT
from radar.db import kv_set, now_iso

log = logging.getLogger("radar.local_scan")

# 扫描范围：工作区项目、shell 配置、常见 agent/CLI 配置目录（浅层）。
# /host/* 是容器内对宿主机家目录相关路径的只读挂载（见 docker-compose.yml）；
# 宿主机直跑时 /host 不存在，自动跳过。
SCAN_FILES = [".env", ".env.local", ".zshrc", ".zprofile", ".bash_profile", ".profile",
              "/host/.zshrc", "/host/.zprofile", "/host/.bash_profile"]
SCAN_DIRS = [
    "~/.zcode/workspace",
    "~/.claude",
    "~/.cursor",
    "~/.codex",
    "~/.qwen",
    "~/.gemini",
    "~/.kimi",
    "/host/.zcode/workspace",
    "/host/.claude",
    "/host/.cursor",
    "/host/.codex",
    "/host/.qwen",
    "/host/.gemini",
    "/host/.kimi",
]
_DIR_PATTERNS = ["**/.env", "**/.env.local", "**/*.env", "**/agent_config*.yaml", "**/mcp*.json"]
_MAX_FILE_BYTES = 1_000_000

# 变量名里只要带这些片段就值得识别平台；值永远不进结果
_NAME_RE = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]{2,64})\s*=")
_JSON_NAME_RE = re.compile(r'"([A-Za-z][A-Za-z0-9_]{2,64})"\s*:')


def _load_platform_index() -> list[dict]:
    with open(CONFIG_DIR / "platforms.yaml", encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh) or {}
    return cfg.get("platforms") or []


def _match_platform(var_name: str, index: list[dict]) -> dict | None:
    upper = var_name.upper()
    for p in index:
        if any(sig in upper for sig in (p.get("match") or [])):
            return p
    return None


def _candidate_files() -> list[Path]:
    files: list[Path] = []
    home = Path.home()
    for d in SCAN_DIRS:
        base = Path(os.path.expanduser(d))
        if not base.exists():
            continue
        if base.is_file():
            files.append(base)
            continue
        for pat in _DIR_PATTERNS:
            for f in base.glob(pat):
                if f.is_file() and f.stat().st_size <= _MAX_FILE_BYTES:
                    files.append(f)
    for name in SCAN_FILES:
        f = home / name
        if f.is_file() and f.stat().st_size <= _MAX_FILE_BYTES:
            files.append(f)
    # 去重
    seen, uniq = set(), []
    for f in files:
        r = f.resolve()
        if r not in seen:
            seen.add(r)
            uniq.append(f)
    return uniq


def _extract_names(text: str) -> list[str]:
    names: list[str] = []
    for line in text.splitlines():
        m = _NAME_RE.match(line)
        if m:
            names.append(m.group(1))
            continue
        for m in _JSON_NAME_RE.finditer(line):
            names.append(m.group(1))
    return names


# CLI 工具登录态指纹：凭证文件存在即视为已配置（只检查存在性，绝不读取内容）。
CLI_TOOLS = [
    {"name": "Codex CLI", "paths": ["~/.codex/auth.json", "/host/.codex/auth.json"],
     "claim_desc": "登录态即订阅/免费额度，随 plan 周期刷新"},
    {"name": "Claude Code", "paths": ["~/.claude.json", "~/.claude/.credentials.json",
                                      "/host/.claude.json", "/host/.claude/.credentials.json"],
     "claim_desc": "订阅额度（Pro/Max），每 5 小时窗口刷新"},
    {"name": "Gemini CLI", "paths": ["~/.gemini/oauth_creds.json", "/host/.gemini/oauth_creds.json"],
     "claim_desc": "个人账号免费约 1000 请求/天（登录即领）"},
    {"name": "Qwen Code", "paths": ["~/.qwen/oauth_creds.json", "/host/.qwen/oauth_creds.json"],
     "claim_desc": "免费约 2000 请求/天（登录即领）"},
    {"name": "gcloud 应用凭证",
     "paths": ["~/.config/gcloud/application_default_credentials.json",
               "/host/.config/gcloud/application_default_credentials.json"],
     "claim_desc": "应用默认凭证（ADC）已配置"},
    {"name": "ZCode", "paths": ["~/.zcode", "/host/.zcode"],
     "claim_desc": "当前 AI 编码工具登录态"},
    {"name": "Cursor", "paths": ["~/.cursor", "/host/.cursor"],
     "claim_desc": "订阅额度随账期刷新"},
    {"name": "VS Code + Claude Code 插件",
     "paths": ["~/.vscode/extensions/anthropic.claude-code*",
               "/host/.vscode/extensions/anthropic.claude-code*"],
     "claim_desc": "Claude 订阅额度（Pro/Max），随会话窗口刷新", "glob": True},
    {"name": "Hermes Agent（终端版）",
     "paths": ["~/.hermes", "/opt/homebrew/bin/hermes", "~/.local/bin/hermes",
               "/host/.hermes", "/host/.local/bin/hermes"],
     "claim_desc": "本地部署的终端 agent（额度随其配置的模型账号）"},
]


def scan_cli() -> dict:
    """检测 CLI 工具登录态。支持 glob 通配（如 VS Code 扩展目录）。只检查存在性。"""
    found: dict[str, dict] = {}
    for tool in CLI_TOOLS:
        hits = []
        for p in tool["paths"]:
            f = Path(os.path.expanduser(p))
            if tool.get("glob"):
                parent = f.parent
                if parent.is_dir() and any(parent.glob(f.name)):
                    hits.append(str(parent))
            elif f.exists():
                hits.append(str(f))
        if hits:
            found[tool["name"]] = {
                "locations": hits,
                "vars": ["<登录态凭证文件>"],
                "console": None,
                "claim": None,
                "claim_desc": tool["claim_desc"],
                "env_key": None,
            }
    return found


# 桌面应用扫描：识别 /Applications 里已安装的 AI 相关应用（只读应用名，不进应用内部）
APP_DIRS = ["/Applications", os.path.expanduser("~/Applications"),
            "/host/Applications", "/host/HomeApplications"]


def scan_apps(index: list[dict]) -> dict:
    """扫描已安装桌面应用，按 platforms.yaml 的 apps 字段匹配平台。"""
    found: dict[str, dict] = {}
    app_names: list[tuple[Path, str]] = []
    seen = set()
    for d in APP_DIRS:
        base = Path(d)
        if not base.is_dir():
            continue
        for f in base.glob("*.app"):
            if f.resolve() in seen:
                continue
            seen.add(f.resolve())
            app_names.append((f, f.stem))
    for p in index:
        apps = p.get("apps") or []
        if not apps:
            continue
        hits = []
        for f, stem in app_names:
            for app in apps:
                if app.lower() in stem.lower():
                    loc = str(f)
                    if loc not in hits:
                        hits.append(loc)
        if hits:
            name = p["name"]
            entry = found.setdefault(name, {
                "locations": [], "vars": ["<桌面应用>"],
                "console": p.get("console"), "claim": p.get("claim"),
                "claim_desc": p.get("claim_desc"), "env_key": p.get("env_key"),
            })
            entry["locations"].extend(h for h in hits if h not in entry["locations"])
    return found


def scan() -> dict:
    """扫描本机：环境变量指纹 + CLI 登录态。结果永不含密钥值。"""
    index = _load_platform_index()
    found: dict[str, dict] = {}
    for f in _candidate_files():
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for name in _extract_names(text):
            p = _match_platform(name, index)
            if not p:
                continue
            entry = found.setdefault(
                p["name"],
                {
                    "locations": [],
                    "vars": [],
                    "console": p.get("console"),
                    "claim": p.get("claim"),
                    "claim_desc": p.get("claim_desc"),
                    "env_key": p.get("env_key"),
                },
            )
            loc = str(f)
            if loc not in entry["locations"]:
                entry["locations"].append(loc)
            if name not in entry["vars"]:
                entry["vars"].append(name)

    for name, info in scan_cli().items():
        if name in found:
            found[name]["locations"].extend(
                loc for loc in info["locations"] if loc not in found[name]["locations"])
            found[name]["claim_desc"] = info["claim_desc"]
        else:
            found[name] = info

    for name, info in scan_apps(index).items():
        if name in found:
            found[name]["locations"].extend(
                loc for loc in info["locations"] if loc not in found[name]["locations"])
            found[name]["claim_desc"] = info["claim_desc"] or found[name]["claim_desc"]
        else:
            found[name] = info

    log.info("本机扫描完成: 发现 %d 个平台", len(found))
    return found


def sync_local(conn) -> dict:
    """扫描 + 登记：结果写 kv；有可领活动的平台自动进活动中心（id 前缀 local-）。"""
    result = scan()
    kv_set(conn, "local_scan", json.dumps(result, ensure_ascii=False))
    kv_set(conn, "local_scan_at", now_iso())

    added = []
    for name, info in result.items():
        if not info.get("claim"):
            continue
        aid = f"local-{name}"
        exists = conn.execute("SELECT 1 FROM activities WHERE id=?", (aid,)).fetchone()
        conn.execute(
            "INSERT INTO activities(id,platform,title,url,kind,note,status) "
            "VALUES(?,?,?,?,?,?,'pending') "
            "ON CONFLICT(id) DO UPDATE SET title=excluded.title, url=excluded.url, note=excluded.note",
            (aid, name, info.get("claim_desc") or "可领额度入口", info["claim"], "local",
             f"本机发现（配置于 {len(info['locations'])} 处），定期提醒检查"),
        )
        if not exists:
            added.append(name)
    conn.commit()
    result["added_activities"] = added
    return result


def import_keys(env_path: Path | None = None) -> int:
    """把本机发现的 key 追加进本产品 .env（同名变量已存在则跳过）。

    值直接从原文件读、写入 .env，不经过日志/返回值/对话。返回新增个数。
    """
    env_path = env_path or (PROJECT_ROOT / ".env")
    index = _load_platform_index()

    # 本产品 .env 已有的变量名（不读值）
    existing: set[str] = set()
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            m = _NAME_RE.match(line)
            if m:
                existing.add(m.group(1).upper())

    wanted: dict[str, list[str]] = {}  # env_key -> 匹配的变量名片段
    for p in index:
        if p.get("env_key") and p["env_key"].upper() not in existing:
            wanted[p["env_key"].upper()] = p["match"]

    if not wanted:
        return 0

    appended = 0
    lines_to_append: list[str] = []
    for f in _candidate_files():
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for line in text.splitlines():
            m = _NAME_RE.match(line)
            if not m:
                continue
            var_upper = m.group(1).upper()
            if var_upper in wanted and var_upper not in existing:
                # 原行含值；直接搬运整行（值仍不显示），变量名归一为目标 env_key
                value = line.split("=", 1)[1].strip().strip('"').strip("'")
                if not value or value.startswith("你的") or "paste" in value.lower():
                    continue
                lines_to_append.append(f"{var_upper}={value}")
                existing.add(var_upper)
                appended += 1

    if lines_to_append:
        with open(env_path, "a", encoding="utf-8") as fh:
            fh.write("\n# ==== 本机扫描自动导入（来源：其他项目配置）====\n")
            fh.write("\n".join(lines_to_append) + "\n")
    log.info("导入 %d 个 key 到 .env（值不显示）", appended)
    return appended
