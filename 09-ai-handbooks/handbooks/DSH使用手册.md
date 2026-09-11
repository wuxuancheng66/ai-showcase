# DeepSeek Harness（DSH）使用手册

> 最后更新：2026-08-25（已补充 4 大内置模式详解与精通教程） · 由你的 DSH 智能体现场实测后编写
> 适用环境：macOS（Apple M5）· DSH Desktop · dsh 0.1.1-rc.2

## 目录

9. [梁神模式（liangshen）——两阶段省流模式](#梁神模式liangshen两阶段省流模式)
10. [子代理调度体系](#子代理调度体系)
11. [长期目标（Goal）](#长期目标goal)
12. [Skills 技能](#skills-技能)
13. [权限与沙箱（如何不被打扰）](#权限与沙箱如何不被打扰)
14. [插件市场与已装插件](#插件市场与已装插件)
15. [外部 Agent 调度（Codex / Claude / Kimi）](#外部-agent-调度codex-claude-kimi)
16. [常用命令与斜杠命令](#常用命令与斜杠命令)
17. [会话记录与排错](#会话记录与排错)
18. [智能体的自主调度策略](#智能体的自主调度策略)

---

## 1. DSH 是什么

DeepSeek Harness（DSH）是一个本地的 AI 智能体运行框架 + 图形界面（Web GUI，`http://127.0.0.1:43120`）。它和你平时用的 Claude Code、Codex 不同：

| 特性 | 说明 |
|---|---|
| 模型 | 官方 DeepSeek API（V4 Pro / V4 Flash / V4 Flash Vision） |
| 形态 | 桌面 App（DSH Desktop）+ 浏览器界面 + 命令行 `dsh` |
| 多智能体 | 子代理（subagent）、工作流（workflow）、长线目标（goal）、Ralph 循环 |
| 插件 | cordis 插件体系 + 可视化插件市场（1550+ 插件） |
| 沙箱 | 三级文件沙箱（read-only / workspace-write / danger-full-access） |
| 数据 | 全部存本机 `~/.dsh/`（会话、设置、记忆、预设） |

**核心目录一览**

| 路径 | 用途 |
|---|---|
| `~/.dsh/settings.yaml` | 全局设置（默认模型、默认预设等） |
| `~/.dsh/.agent-presets/` | 你自己的 Agent 预设（模式） |
| `~/.dsh/profiles/{web,desktop,headless}/` | 各运行档的插件与补丁 |
| `~/.dsh/sessions/` | 全部会话日志（zstd 压缩的 JSONL） |
| `~/.dsh/memory/` | 智能体的长期记忆库 |
| `~/.dsh/.credentials.yaml` | API Key 凭据（权限 600，勿外传） |

---

## 2. 模型与成本

DSH 里可用的三个官方模型（全部 100 万 token 上下文）：

| 模型 ID | 定位 | 适用 |
|---|---|---|
| `deepseek-v4-pro` | 贵、强、深度推理 | 架构设计、跨系统改造、需要权衡的重活 |
| `deepseek-v4-flash` | 便宜、快 | 机械重复、单一文件、简单检索、子代理默认 |
| `deepseek-v4-flash-vision-exp` | 带视觉 | 读图、截图分析、OCR |

- 主 Agent 默认模型：设置 → 模型，或在 `~/.dsh/settings.yaml` 的 `agent-default-model` 分节修改。
- 会话中也可以随时切换模型（GUI 模型选择器），切换只影响当前会话。

**省钱要点**

- 子代理默认走 Flash（见下一节"经济模式"）。
- 长会话用 `/compact` 压缩上下文。
- 不要让 Agent 读 `node_modules`、`.git`、缓存等大目录。
- 重活才用 Pro，轻活一律 Flash。

---

## 3. 经济模式：主 Pro · 子 Flash（本机已配置）

2026-08-25 已在本机部署一个自定义 Agent 预设 **「经济模式（主Pro·子Flash）」**，并设为默认。

| 项 | 配置 |
|---|---|
| 预设 ID | `economy-standard` |
| 位置 | `~/.dsh/.agent-presets/economy-standard/`（agent.cordis.yml + preset.yml） |
| 效果 | 主 Agent 用 `deepseek-v4-pro`；所有 `subagent` / `subagent_fork` 派出的子代理默认用 `deepseek-v4-flash`（输出上限 65536 token） |
| 其余能力 | 与内置「标准模式」完全一致 |

- **切换预设**：GUI 设置 → Agent 预设（新会话生效；已开着的会话不受影响）。
- **改回标准模式**：把 `~/.dsh/settings.yaml` 里 `agent-presets.default` 改回 `standard`，或删掉 `economy-standard` 目录。
- **重活子代理例外**：工作流脚本里可以给单个子代理显式指定 `model: 'deepseek-v4-pro'` 覆盖回来。
- 注意：App 更新不会动 `~/.dsh/.agent-presets/` 里的用户预设，安全。

---


## 4. 4 大内置模式：总览与选择

DSH 出厂自带 **4 种 Agent 模式（预设）**，外加你已部署的「经济模式」和社区「梁神模式」。模式决定一个会话里智能体"能看到什么工具、以什么方式干活"。模式与**权限预设**是两回事：权限预设管沙箱和审批（见 §12），模式管工具和干活方式，互相独立。

### 模式对比表

| 模式 | ID | 一句话定位 | 工具形态 | 适合场景 |
|---|---|---|---|---|
| **标准模式** | `standard` | 功能完整的全能编码 Agent | 直接调用全部工具（native） | 日常绝大多数任务（出厂默认） |
| **PTC 模式** | `code` | 用 TypeScript 程序组合多步操作 | 只见 `run_code` + 自动生成的 SDK | 多步骤、要可复现、要精确控制 |
| **极简模式** | `minimal` | 只有 bash + 文件编辑的轻量 Agent | 持久 Shell + str_replace_editor | 快速小活、省 token、少打扰 |
| **创造模式** | `cordis` | 现场造插件 / 自定义预设的模式 | 标准能力 + Cordis 实验工具 | 开发、实验、定制你自己的模式 |
| **经济模式** | `economy-standard` | 主 Pro · 子 Flash 的省钱版标准模式 | 同标准模式（子代理走 Flash） | 你的日常默认（已配置，见 §3） |
| **梁神模式** | `liangshen` | 两阶段：先极简省流、后自动升 PTC 编程（社区） | 阶段1: bash + 编辑器；阶段2: run_code + SDK | 想省钱又想要 PTC 能力的多步编码（见 §9） |

### 怎么切换模式

- **单次会话**：对话输入框上方的模式选择器（如"标准模式"下拉），选了再发第一条消息即可。
- **改默认**：设置 → Agent 预设 → 选择默认；**只对新会话生效**，已开着的会话保持创建时的模式。
- **命令行**：`dsh --profile web` 的默认由 `~/.dsh/settings.yaml` 的 `agent-presets.default` 决定。

### 选择心法（一句话版）

- 不确定 → 标准模式（或你的经济模式）。
- 任务步骤多、想让它"一次规划好再执行" → **PTC 模式**。
- 只是改个小文件、跑条命令 → **极简模式**。
- 想自定义 DSH、造新模式 → **创造模式**。
- 想首轮便宜、后续编程式干活 → **梁神模式**（社区）。

---

## 5. 模式一：标准模式（standard）——全能默认

### 详细介绍

标准模式是 DSH 的出厂默认，功能最完整。智能体直接调用（native schema）以下工具家族：

| 工具族 | 能力 |
|---|---|
| `tool-bash` / `tool-pwsh` | 执行 Shell / PowerShell 命令（macOS 走 bash） |
| `tool-fs` / `tool-fs-search` | 读、写、搜索文件 |
| `tool-jobs` | 后台任务：启动、查看输出、停止 |
| `tool-skill` + `skill-filesystem` | 技能系统：加载与调用 Skills |
| `tool-goal` | 长线目标管理（`/goal`） |
| `planning` | 计划模式：先规划再动手 |
| `delegation` | 子代理体系：subagent / subagent_fork / workflow / ralph |
| `tool-ask-user` | 需要时主动向你提问 |
| `tool-todo` | 任务清单 |
| `tool-web` | 网页搜索与读取 |
| `compaction` | 上下文压缩（`/compact`，长会话省钱） |

### 精通教程

1. **子代理并行**：大任务拆小块 → 直接说"把这个项目拆成 3 个子代理并行做"。经济模式下子代理自动走 Flash，省钱。
2. **计划模式**：复杂任务先"用计划模式列方案，我确认后再执行"，避免它乱冲。
3. **长线目标**：重复性长期任务用 `/goal` 挂起来，跨会话自动推进。
4. **技能复用**：把常用流程写成 Skill，以后一句话调用。
5. **后台任务**：长命令让它放后台跑（`tool-jobs`），边跑边聊别的。
6. **网页检索**：需要最新资料时让它用 `tool-web` 查（注意网络与来源）。

---

## 6. 模式二：PTC 模式（code）——程序化组合

### 详细介绍

PTC = 用编程的方式组合工具。开启后，智能体**看不到几十个工具按钮**，只看到一个 `run_code` 工具 + 一份自动生成的 **TypeScript SDK**；它把多步操作写成一个 TypeScript 程序，一次运行跑完整条流水线。

核心概念（由 `tool-presentation` 决定"模型看到工具的哪种形态"）：

| 形态 | 说明 |
|---|---|
| `native` | 模型直接看到并调用每个工具的 schema（标准/极简等模式默认） |
| `code` | 模型只见 `run_code` + 生成的 TS SDK，只能通过写程序调工具 |
| `both` | 两种都给 |

### 精通教程

1. **什么时候用**：任务步骤多且固定（拉代码 → 改 → 构建 → 测试 → 打包 → 汇报），想要一次成型、结果可复现；或想让模型"想清楚再执行"，而不是一步一停。
2. **怎么引导**：直接说"用代码模式把这件事做成一个程序：……，然后运行"。它会生成 TS 程序并执行 `run_code`。
3. **好处**：程序可复现、可改参数重跑；多步之间不丢上下文；适合流水线类任务。
4. **注意事项**：
   - PTC 需要 Code Runtime（桌面版已内置）；未组装运行时的部署无法使用该模式。
   - 在 `code` 形态下，模型直呼其他工具名会得到 `UNKNOWN_TOOL`——它只能走 SDK。
   - 程序报错时让它"修一下程序再跑"，而不是让它换工具。
5. **进阶**：让程序把结果写入文件、打印结构化输出，方便你事后检查；需要重活时可在程序里指定子代理/模型。

---

## 7. 模式三：极简模式（minimal）——轻快省

### 详细介绍

极简模式只保留两样东西：

- **持久 Shell**（persistent bash）：一个保持状态的长驻终端，连续执行命令，不用每次重开环境。
- **str_replace_editor**：精确的字符串替换式文件编辑器（读文件、改片段、插入、删除）。

没有网页检索、没有 Skills、没有子代理、没有目标管理——工具面最小，上下文开销最低。

### 精通教程

1. **什么时候用**：改一行配置、跑一条命令、快速查个文件——任务小到不值得开全套工具时。
2. **好处**：模型不被工具清单干扰，响应更快、更省 token；持久 Shell 让它不用反复 cd。
3. **技巧**：
   - 让它"先看文件再改"，用 str_replace_editor 做精准修改。
   - 连续操作同一终端时让它复用持久 Shell。
4. **不适用**：需要网页检索、子代理并行、技能、长线目标的任务，请切回标准/经济模式。

---

## 8. 模式四：创造模式（cordis）——造你自己的模式

### 详细介绍

创造模式 = 标准模式的全部能力 + 一套 **Cordis 实验工具**：

| 工具 | 用途 |
|---|---|
| `cordis_inspect` | 只读查看当前运行时的服务、插件、已注册工具、API/事件 |
| `cordis_define` | 在内存里定义一个动态插件包 |
| `cordis_run` | 运行刚定义的包（可注册工具/提示词/监听器） |
| `cordis_stop` / `cordis_undefine` | 停止 / 移除动态包（实验完清理） |

- 动态包**只存在于内存**：不落盘、重启即消失，不会自动转正式插件——适合"先试后装"。
- ⚠️ 沙箱只约束"诚实代码"，不是安全边界：官方提示**像对待 bash 一样慎重使用**。

### 精通教程

1. **复制即创作**：DSH 的预设创作 = "复制现有预设 → 改配置"。你的「经济模式」就是这么来的（复制 standard → 把子代理行改成 Flash）。
2. **自定义一个新模式**（例：做一个"只读咨询模式"）：
   - 复制 `~/.dsh/.agent-presets/standard/` → 新目录 `consultant`；
   - 编辑 `agent.cordis.yml`：去掉 `tool-bash` 行，只留 `tool-fs` / `tool-fs-search` / `tool-web`；
   - 编辑 `preset.yml`：写名称、描述、排序；
   - 设置 → Agent 预设里选它，**新会话**生效。
3. **机制要点（踩坑必看）**：
   - 预设目录权限要收紧：目录 `700`、文件 `600`（防他人/他进程读取）。
   - `cordis.patch.yml` 的 patch 是**顶层键整体替换**（`target[key] = value`）——写 config 必须写全，否则原 config 会被整个抹掉。
   - 已开着的会话不会变，只有新会话用新模式。
4. **现场实验**：想试一个插件又不想装？在创造模式里 `cordis_define` + `cordis_run` 试跑，满意后再正式安装。
5. **安全**：别用创造模式做日常活；实验完记得 `cordis_stop` / `cordis_undefine` 清理，避免动态包残留影响其他会话。

---

## 9. 梁神模式（liangshen）——两阶段省流模式

### 详细介绍

梁神模式是**社区制作**的一个"两阶段"模式（改编自 DSH 内置的极简 + 标准模式，MIT 协议，代码来自开源上游 `xiaobright/dsh-anchored-standard`）。它把"省钱"和"强大"结合到同一个会话里：

| 阶段 | 工具面 | 特点 |
|---|---|---|
| **阶段 1：极简锚定** | 只有 2 个工具：持久 bash + str_replace_editor；提示词只有一行 | 首轮对话极省 token，输出预算还被限制在 1024 token，不加载任何运行时上下文 |
| **阶段 2：自动升级** | 首次有效工具调用 / 首轮回复后，自动切到 **PTC 编程模式**（`run_code` + 自动生成的 TS SDK） | 完整技能目录、工作区说明随之开放，用写程序的方式干重活 |

一句话：**首轮便宜，之后强大**。它先用极简面"锚定"模型、花最小的代价让模型理解任务，再自动解锁 PTC 的完整程序化能力。

> ⚠️ 说明：preset.yml 里那串"双腿一软瘫坐在地 / 原子弹爆炸 / 文言文二进制摩斯电码"是作者的玩笑式描述，实际能力就是上面的两阶段机制。

### 精通教程

1. **什么时候用**：典型的多步编码任务，尤其适合"先让模型用便宜的首轮理解任务，再让它用程序精确执行"。想省 token 又想要 PTC 能力时选它。
2. **怎么用**：设置 → Agent 预设 → 选「梁神模式」，**新会话**生效。无需任何特殊操作，它会自动从阶段 1 升到阶段 2。
3. **特点与注意**：
   - 阶段 1 的编辑器走**宿主文件沙箱**（比内置极简模式更安全，不裸挂本地文件系统）。
   - 它带两个自定义脚本：`tool-bootstrap.mjs`（负责两阶段切换）、`custom-bash.mjs`（Windows 下的 bash 通道，macOS 用不到）；已核对无异常网络/破坏行为。
   - 这是**第三方社区实验模式**，不是官方 4 大模式；升级到阶段 2 后持久 shell 会保留整个会话。
4. **进阶**：阶段 1 的 1024 token 输出上限想改大，可编辑 preset 里的 `bootstrapMaxTokens`（`~/.dsh/.agent-presets/liangshen/agent.cordis.yml`），改完重开新会话生效。

---
## 10. 子代理调度体系

智能体可以自主委派子代理，四种形态：

| 工具 | 用途 | 形态 |
|---|---|---|
| `subagent` | 派一个新上下文的子代理 | 默认后台（可继续对话） |
| `subagent_fork` | 派一个继承当前对话的子代理 | 默认后台（可继续） |
| `workflow` | 大规模扇出（脚本编排多阶段、结构化结果） | 前台脚本 |
| `ralph` | 长线目标的新鲜智能体迭代（每轮全新上下文） | 前台循环 |

配套工具：`list_agents`（查看子代理）、`send_message`（给后台子代理追加任务）、`interrupt_agent`（叫停）、`job_list` / `job_output` / `job_kill`（后台作业管理）。

**调度策略（智能体内部约定）**

1. 先估复杂度：机械重复/单一文件/可并行 → 轻活；架构级/跨系统/需权衡 → 重活。
2. 轻活派 Flash 子代理并行后台跑；重活主 Agent 亲自用 Pro 做。
3. 独立工作同时开工、不互相等待；只有下一步依赖子代理结果时才前台等。
4. 花钱、删文件、force push 等危险操作，必须先问你。

---

## 11. 长期目标（Goal）

长线任务用目标机制：智能体会自动多轮持续推进，直到完成或被阻塞。

- 会话内可持续：跨多次对话继续推进同一目标。
- 每个目标有轮次上限与阻塞上报机制。
- GUI 侧边栏可以看到目标进度。

适用场景：多步改造、跨文件重构、需要多轮迭代的任务。

---

## 12. Skills 技能

技能是任务型指令包，智能体遇到匹配任务时自动加载执行。本机已有：

| 技能 | 用途 |
|---|---|
| `join-meeting` | 让 AI 加入视频会议（Google Meet / Teams / Zoom），语音+视觉出席 |
| `ski` | 语音循环：浮动小部件收音 → Kokoro 本地 TTS 回话 |

技能目录：`~/.agents/skills/`（用户级）。触发方式：直接说"用 xxx 技能"或任务明显匹配时智能体自动加载。

---

## 13. 权限与沙箱（如何不被打扰）

DSH 有三级文件沙箱，每级对应"会不会弹确认"：

| 预设名 | 沙箱 | 审批 | 体验 |
|---|---|---|---|
| `workspace-write`（本机默认） | 会话工作目录内自由读写 | ask | 项目内干活基本不弹窗；跨目录写/删才确认 |
| `danger-full-access` | 不限制文件修改 | never | 永不弹窗，但失去文件保护 |
| `read-only` | 只读 | ask | 最严格 |

- 本机默认保持 `workspace-write`（安全与便利的平衡）。
- **切换方式**：会话内输入 `/permissionPresets danger-full-access`（或 `workspace-write` / `read-only`）；`/permissionPresets`（不带参数）查看当前状态。
- 想改"未来所有新会话"的默认：`~/.dsh/settings.yaml` 加：

  ```yaml
  permission:
    defaultPreset: workspace-write   # 或 danger-full-access / read-only
  ```

- 环境变量 `DSH_PERMISSION_MODE=danger-full-access` 启动时也可以放宽审批策略。
- 智能体的行为约定不变：**危险操作（删文件、格式化、强制推送、花钱）仍会先问你**，与沙箱无关。

---

## 14. 插件市场与已装插件

GUI 里 **设置 → 插件市场** 可以逛装 1550+ 社区插件（一键安装、热启用、卸载）。目录源：`awesome-dsh-plugin.com`。

本机已装（web profile）：

| 插件 | 用途 |
|---|---|
| `dshmarket`（内嵌） | 可视化插件市场本体 |
| `@linxin666/dsh-web-ui-all` | Web UI 全家桶：任务看板、Git 分支图、技能浏览器、会话恢复等 |
| `dsh-at-file` | 输入框 `@文件` 引用 |
| `dsh-balance-plugin` | 查看 API 余额 |
| `dsh-client-auto-continue` | 自动继续 |
| `dsh-memory` | 记忆插件 |
| `dsh-context`（本次新装） | 上下文面板 + `/context` 命令，一眼看上下文占用 |

命令行装插件：`dsh plugin --profile web add <包名>`；卸载 `dsh plugin --profile web remove <包名>`。

社区热门候选（想装就在市场里搜）：

| 插件 | star | 用途 |
|---|---|---|
| dsh-TUI | 2395 | Claude Code 风格全屏终端 UI |
| DSH-better-sidebar | 2736 | 侧边栏工作台（文件/终端/Git/子代理） |
| modlens | 3563 | 给纯文本模型外挂视觉（OCR/版面/语义） |
| dsh-vision-router | 949 | 免费视觉链 + 像素工具 |
| Aegis | 1119 | 软件工程方法包（基线优先、系统化调试） |
| dsh-agent-teams | 913 | 多智能体团队编排 |

---

## 15. 外部 Agent 调度（Codex / Claude / Kimi）

智能体可以用命令行调用你机器上的其他编码 Agent 当外部工人。2026-08-25 实测状态：

| CLI | 状态 | 说明 |
|---|---|---|
| `codex` | ✅ 可用 | 已认证；`codex exec -m deepseek-v4-flash` 可切便宜模型；**琐碎任务也固定烧约 9k token**（系统提示词+插件同步开销），只适合需要它独有能力（浏览器/电脑操作）的重活；需放开沙箱才能跑 |
| `claude` | ✅ 已打通（本次配置） | 把 VS Code 里的 DeepSeek 环境变量同步进了 `~/.claude/settings.json` 的 `env` 块，现在 `claude -p` 直接可用；主模型 `deepseek-v4-pro[1m]`、子代理 `deepseek-v4-flash`（`CLAUDE_CODE_SUBAGENT_MODEL`） |
| `kimi` | ❌ 未登录 | `~/.kimi-code/config.toml` 为空；要使用先跑 `kimi` 登录 |

调用示例：

```bash
claude -p "修一下 src/utils.ts 的类型报错"          # headless 单任务
codex exec -m deepseek-v4-flash "生成单元测试"      # 便宜模型
```

---

## 16. 常用命令与斜杠命令

**命令行**

| 命令 | 用途 |
|---|---|
| `dsh --profile web --dump-config` | 导出当前生效配置（排错用） |
| `dsh plugin --profile web add/remove <包>` | 装/卸插件 |
| `dsh --profile headless "任务"` | 无界面跑一个任务 |
| `dsh web` | 启动 Web GUI |

**会话内斜杠命令**

| 命令 | 用途 |
|---|---|
| `/compact` | 压缩上下文（长会话省钱） |
| `/goal` | 查看/管理长线目标 |
| `/permissionPresets [预设]` | 查看/切换权限预设 |
| `/context`（dsh-context） | 查看上下文占用面板 |
| `/feedback` | 反馈 |

---

## 17. 会话记录与排错

- 所有会话都存在 `~/.dsh/sessions/<工作目录>/<会话id>/session.jsonl.zstd`。
- 查看某会话实际用的模型：

  ```bash
  zstd -d -c ~/.dsh/sessions/<...>/<会话id>/session.jsonl.zstd | head -c 2000
  # 找 request/header 事件里的 model 字段
  ```

- 主会话与每个子代理各有一个独立会话目录；子代理会话的 `session` 事件里有 `parentSession`、`origin: subagent`。
- **验证"经济模式"是否生效**：新开一个会话，派个子代理干点活，然后解压子代理的会话日志看 `request/header` 里 `model` 是否为 `deepseek-v4-flash`。

---

## 18. 智能体的自主调度策略

为了让任务"最优、最经济、高质量"，智能体遵循这套内部策略（已写入长期记忆）：

1. **先估复杂度，再选路**。
2. 轻活 / 机械重复 / 单一文件 / 可并行 → DeepSeek V4 Flash 子代理，并行后台跑。
3. 重活 / 架构级 / 跨系统 / 需要深度权衡 → 主 Agent 用 V4 Pro，或显式指定 Pro 子代理。
4. 并行扇出用 `workflow`（支持每个子代理单独指定 model/provider——经济路由的实现点）；长线目标用 `ralph`；单次委托用 `subagent`。
5. 外部工具按需：Codex 只做它能干的独活（接受 9k token 固定开销）；Claude headless 可做常规编码活。
6. **危险操作（花钱/删文件/force push）必须先问用户**；看不到逐 token 账单，只能策略性省钱。

---

*本手册由 DSH 智能体在 2026-08-25 结合本机实测生成；配置变更后请以 `~/.dsh/` 实际文件为准。*
