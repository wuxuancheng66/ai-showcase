# VS Code + Claude Code 插件接入 DeepSeek V4：突出价值、独特优势与高阶玩法

> 版本：v1.3 · 2026-08-12 · 依据 DeepSeek 官方文档、Claude Code 官方文档与 2026 年社区实践整理
>
> **版本记录**
> - v1.3（2026-08-12）：GitHub MCP 暂缓接入（用户暂无 GitHub 账号，已移除占位配置并记录接入步骤备用）；高阶玩法同步迁移到 Codex（AGENTS.md 规矩、MCP、Skills、子代理）。
> - v1.2（2026-08-12）：已按高阶玩法落地配置——新增全局 `~/.claude/CLAUDE.md`（项目规矩记忆）+ 3 个安全 Hooks（危险命令拦截、密钥入库检查、会话结束提醒）。
> - v1.1（2026-08-12）：新增「独特优势」与「高阶玩法」两大章节；确认本机已通过 VS Code 插件环境变量接入 DeepSeek V4。
> - v1.0（2026-08-11）：初版发布（基础配置方法）。

---

## 一、这套组合的突出价值

| 维度 | 价值 |
|---|---|
| **编程体验** | Claude Code 是顶级的 AI 编程代理（终端 + VS Code 插件），擅长多文件、长任务、自动改代码 |
| **模型成本** | DeepSeek V4 价格仅为同级闭源模型的几分之一，1M 超长上下文 |
| **数据可控** | 通过你自己的 DeepSeek API Key 直连，不经第三方中转 |
| **可视化切换** | 配合 cc-switch 可在 Claude/DeepSeek/其他供应商间一键切换 |
| **中文友好** | DeepSeek 中文能力出色，国内网络直连无墙 |

### DeepSeek V4 模型速览（2026-08 最新定价）
| 模型 ID | 用途建议 | 输入（缓存命中） | 输入（未命中） | 输出 | 上下文 |
|---|---|---|---|---|---|
| `deepseek-v4-flash[1m]` | 日常/轻量/子任务 | 约 0.02 元/百万 token | 约 1 元/百万 token | 约 2 元/百万 token | 1M |
| `deepseek-v4-pro[1m]` | 复杂推理/主力 | 约 0.025–1 元/百万 token | 约 6–12 元/百万 token | 约 12–24 元/百万 token | 1M |

> 定价随官方调整，以 [DeepSeek 开放平台](https://platform.deepseek.com) 实时价格为准。

---

## 二、Claude Code 的独特优势（2026 年横评结论）

与 Codex CLI、Cursor、Gemini CLI 等横向对比后，Claude Code 的核心差异化优势：

| 优势 | 说明 |
|---|---|
| **自主性天花板最高** | 终端优先 + 完整 shell 访问 + 长链路多文件任务，能"放手"执行复杂工程任务 |
| **工程感完整** | 不是 IDE 补全工具，而是能接手真实任务的"终端同事"：读代码库、改多文件、跑测试、看报错迭代 |
| **代码质量敏感型首选** | 社区横评：对代码质量要求高选 Claude Code；它的指令遵循和长链路推理稳定 |
| **上下文大** | 原生 200K 上下文（配合 DeepSeek 1M 更从容），比 Codex CLI 128K 更宽裕 |
| **扩展体系最成熟** | CLAUDE.md / Skills / Subagents / Hooks / MCP 五件套，能把它从"助手"变成"编排器" |
| **模型无关** | 官方支持任何 Anthropic 兼容端点 → 国内用户可直接接 DeepSeek V4，成本降一个量级 |

**一句话**：Claude Code 是"终端里的完整工程 Agent"，DeepSeek V4 是"性价比极高的推理引擎"，两者组合 = 顶级体验 + 白菜价。

---

## 三、你的本机配置（已核验）

你已经在 **VS Code 的 Claude Code 插件设置**（`claudeCode.environmentVariables`）中接好 DeepSeek：

| 变量 | 值 | 说明 |
|---|---|---|
| ANTHROPIC_BASE_URL | https://api.deepseek.com/anthropic | DeepSeek 官方 Anthropic 兼容端点 |
| ANTHROPIC_AUTH_TOKEN | 你的 DeepSeek Key | 已配置 ✅ |
| ANTHROPIC_MODEL | deepseek-v4-pro[1m] | 主模型（1M 上下文） |
| ANTHROPIC_DEFAULT_HAIKU_MODEL | deepseek-v4-flash | 轻量模型 |
| CLAUDE_CODE_SUBAGENT_MODEL | deepseek-v4-flash | **子代理已路由到 flash（省钱关键！）** |
| CLAUDE_CODE_EFFORT_LEVEL | max | 推理力度拉满 |

这套配置是 2026 年社区公认的「省钱但好用」标准模板 ✅

### 已落地的高阶配置（2026-08-12 新增）
| 项目 | 位置 | 作用 |
|---|---|---|
| 全局 CLAUDE.md | `~/.claude/CLAUDE.md` | 每次会话自动读取：中文回复、模型成本意识、危险操作先询问、知识库位置等规矩 |
| Hooks 危险命令拦截 | `~/.claude/hooks/guard_destructive.py` | 自动拦截 `rm -rf /`、`git reset --hard`、强制推送、格式化磁盘等高危命令 |
| Hooks 密钥入库检查 | `~/.claude/hooks/check_secrets.py` | `git commit/push` 前自动扫描暂存区，发现 API Key/密码即阻止 |
| Hooks 会话结束提醒 | `~/.claude/hooks/session_summary.py` | 会话结束时提醒：提交改动、沉淀技能、规划下一步 |

---

## 四、高阶玩法（从"会用到用好"）

### 玩法 1：CLAUDE.md —— 让 Agent 记住你的项目规矩
- 在项目根目录建 `CLAUDE.md`，写清项目结构、代码风格、常用命令、禁区。
- Claude Code 每次开工自动读取 → 少解释、少跑偏。
- **省钱点**：稳定的 CLAUDE.md 前缀会命中 DeepSeek 缓存命中价（输入低至 0.02 元/百万），长会话越跑越省。

### 玩法 2：Skills —— 把常用流程固化成技能
- 目录：`.claude/skills/<名字>/SKILL.md`（Markdown + YAML 头）。
- 定义好描述后，任务匹配时**自动触发**，也可用 `/技能名` 手动调用。
- 例：代码审查技能、发布流程技能、文档生成技能。2026 年起斜杠命令已并入 Skills，统一心智模型。

### 玩法 3：Subagents 子代理 —— 并行干活（你已配好省钱路由）
- 用子代理把大任务拆给隔离上下文并行处理，主 Agent 收拢结果。
- 关键省钱配置（你已设置）：`CLAUDE_CODE_SUBAGENT_MODEL=deepseek-v4-flash`
  → 子任务全部走 flash，主任务继续用 pro，多 Agent 并行时账单可降 4 倍。
- 进阶：配合 Hooks 让子代理自动触发（如 `SubagentStart` 事件）。

### 玩法 4：Hooks —— 生命周期自动化
- 在 `~/.claude/settings.json` 或项目级配置里定义钩子：
  - `PreToolUse` / `PostToolUse`：工具调用前后自动跑脚本（格式化、测试、安全检查）
  - `Stop`：会话结束自动收尾
  - `SubagentStart`：子代理启动时注入上下文
- 例：每次改完代码自动跑 `ruff format` + `pytest`；提交前自动过一遍密钥扫描。
- Hooks 是本地脚本，不走模型 API，**不增加 token 成本**。

### 玩法 5：MCP —— 连接外部世界
- 通过 MCP 服务器把 Claude Code 接到 GitHub、数据库、浏览器、内网服务等。
- 配置文件：`~/.claude/settings.json` 的 `mcpServers` 段，或 `/mcp` 命令管理。
- 例：接 context7 查库文档、接 GitHub 提 PR、接本地 Postgres 查数据。
- **原则**：CLAUDE.md → Skills → Hooks → 确实需要时才加 MCP，别一上来堆一堆。
- **待接入**：先注册 GitHub 账号 → 生成 Fine-grained Token（勾选 Contents / Pull requests / Issues 读写）→ 写入 `~/.claude/settings.json` 和 `~/.codex/config.toml` 的 `mcp_servers.github`（命令 `npx -y @modelcontextprotocol/server-github`），即可让两个工具管理仓库/PR/Issue。

### 玩法 6：Plan Mode —— 先计划后动手
- 复杂任务先进入计划模式，让 Agent 先出方案再执行，避免瞎改。
- 配合 `/review` 让 Agent 做代码审查，适合合并前的质量闸门。

### 玩法 7：多 Agent 并行 + 无头自动化
- 开多个会话/终端并行处理不同模块；配合 GitHub Actions 或 CI 做无人值守任务。
- 社区案例：5 个 Agent 并行跑，每天成本约 1.5 元（得益于子代理走 flash + 缓存命中）。

### 玩法 8：常用斜杠命令速查
| 命令 | 作用 |
|---|---|
| `/init` | 初始化 CLAUDE.md |
| `/memory` | 管理长期记忆 |
| `/review` | 代码审查 |
| `/compact` | 压缩上下文（省钱） |
| `/clear` | 清空当前会话 |
| `/permissions` | 管理权限模式 |
| `/mcp` | 管理 MCP 连接 |

---

## 五、成本控制手册（重要）

1. **缓存命中**：CLAUDE.md 稳定前缀 + 长会话复用 → 输入价可低至 0.02 元/百万。
2. **子代理走 flash**：`CLAUDE_CODE_SUBAGENT_MODEL=deepseek-v4-flash`（你已设置 ✅）。
3. **轻任务用 flash**：改 `ANTHROPIC_MODEL` 或会话内切换。
4. **控制上下文**：`/compact` 压缩、`.claudeignore` 排除大目录、别让 Agent 读 node_modules。
5. **设 max_turns / 权限模式**：避免失控长跑。
6. **不用时别留一堆会话**：多 Agent 并行是利器，但记得收尾。

---

## 六、常见问题

| 问题 | 解法 |
|---|---|
| 提示需要 Anthropic 登录 | 确认 VS Code 设置 `claudeCode.environmentVariables` 已生效；新会话生效 |
| 401/认证失败 | 检查 `ANTHROPIC_AUTH_TOKEN`、平台余额 |
| 模型名报错 | 用官方 ID 如 `deepseek-v4-pro[1m]` |
| 切换后不生效 | 新会话生效；旧会话重开 |
| 想对比 Claude 官方 | 用 cc-switch 一键切回，两边互不干扰 |

---

## 七、资料来源
- DeepSeek 官方 API 文档、deepseek-ai/awesome-deepseek-agent
- Claude Code 官方文档（code.claude.com，2026-08）
- 2026 年横评：Claude Code vs Codex vs Cursor（ofox.ai、cosmicjs 等）
- 社区实践：子代理路由 DeepSeek V4-Flash、多 Agent 并行成本优化（腾讯云、OSChina 2026-05/06）
