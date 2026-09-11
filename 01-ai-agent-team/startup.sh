#!/usr/bin/env bash
# ============================================================
# AI Agent Team 一键初始化脚本
#   ./startup.sh               # 基础初始化（虚拟环境+依赖+.env）
#   ./startup.sh --with-docker # 同时启动 Redis / ChromaDB 容器
# ============================================================
set -euo pipefail
cd "$(dirname "$0")"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
info() { echo -e "${GREEN}[初始化]${NC} $1"; }
warn() { echo -e "${YELLOW}[提示]${NC} $1"; }
fail() { echo -e "${RED}[错误]${NC} $1"; exit 1; }

# ---- 1. Python 3.10+ 检查（可用 PYTHON=... 指定解释器）----
PY="${PYTHON:-python3}"
command -v "$PY" >/dev/null 2>&1 || fail "未找到 python3，请先安装 Python 3.10+"
"$PY" - <<'EOF' || fail "需要 Python 3.10 及以上版本"
import sys
raise SystemExit(0 if sys.version_info >= (3, 10) else 1)
EOF
info "Python 版本: $("$PY" --version)"

# ---- 2. 创建虚拟环境 ----
if [ ! -d .venv ]; then
  info "创建虚拟环境 .venv ..."
  "$PY" -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
info "虚拟环境: $(python --version) ($(command -v python))"

# ---- 3. 安装依赖（默认源失败时自动切换清华镜像）----
info "安装依赖（可能需要几分钟）..."
if ! pip install --upgrade pip -q; then
  warn "pip 升级失败，尝试清华镜像"
  pip install --upgrade pip -q -i https://pypi.tuna.tsinghua.edu.cn/simple
fi
if ! pip install -r requirements.txt; then
  warn "默认源安装失败，切换清华镜像重试..."
  pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
fi
info "依赖安装完成"

# ---- 4. 初始化 .env（已存在则不覆盖）----
if [ ! -f .env ]; then
  cp .env.example .env
  warn "已生成 .env，请编辑填写 OPENAI_API_KEY 后再运行任务"
else
  info ".env 已存在，跳过"
fi

# ---- 5. 可选：启动 Redis / ChromaDB ----
if [ "${1:-}" = "--with-docker" ]; then
  command -v docker >/dev/null 2>&1 || fail "未安装 Docker，无法启动基础服务"
  info "启动 Redis 与 ChromaDB ..."
  docker compose up -d
  info "服务已启动（redis:6379, chromadb:8000，仅绑定本机）"
  warn "如需启用向量记忆，请在 .env 中设置 CHROMA_HOST=127.0.0.1"
else
  warn "如需启动 Redis/ChromaDB：docker compose up -d 或 ./startup.sh --with-docker"
fi

echo
info "✅ 初始化完成！接下来："
echo "   1) source .venv/bin/activate"
echo "   2) 编辑 .env 填写 OPENAI_API_KEY（可选：TAVILY_API_KEY 开启联网搜索）"
echo "   3) python main.py            # 交互式运行"
echo "      python monitor.py --watch # 监控 Token 与任务进度"
