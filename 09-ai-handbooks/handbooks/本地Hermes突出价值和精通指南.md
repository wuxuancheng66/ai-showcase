# 本地 Hermes Agent：突出价值与精通指南

> 版本：v1.1 · 2026-08-12 · 基于你本机部署情况与官方最新资料整理
>
> **版本记录**
> - v1.1（2026-08-12）：Hermes 已升级 v0.18.2 → **v0.19.0**；会话数据库（state.db）等权限收紧为仅本人可读（600）。
> - v1.0（2026-08-11）：初版发布。

---

## 一、Hermes Agent 是什么

Hermes Agent 是 **Nous Research**（AI 安全与能力研究机构）推出的**开源自主 AI 智能体**，2026 年 2 月发布，MIT 协议。它不是一个绑在 IDE 里的编程助手，也不是套壳聊天机器人——它**常驻在你自己的机器/服务器上**，记住学到的东西，运行越久越强。

一句话：**它是你的私人 AI 管家/数字员工，数据完全在你手里。**

---

## 二、本地部署的突出价值

### 1. 数据主权与隐私（最大优势）
- **所有数据留在本机**：对话、记忆、技能、状态全部存在 `~/.hermes`，不上传第三方。
- **零遥测、零跟踪、零云锁定**：官方明确无遥测，代码可审计、可复刻。
- 你的 `.env`/`auth.json` 权限为 `600`，只有你自己可读。

### 2. 模型无关，成本可控
- 任意接主流 API：DeepSeek、OpenAI、Ollama 本地模型、OpenRouter 等。
- 你当前用 **DeepSeek v4-pro**（`api.deepseek.com`），性价比极高。
- 也可接本地模型（LM Studio / Ollama），完全离线运行。

### 3. 自我进化（Closed Learning Loop）
- **持久记忆**：跨会话记住项目、偏好、上下文，重启不丢。
- **技能自改进**：从复杂任务中自动沉淀可复用技能，越用越强。
- **定期回顾机制**：Agent 主动整理记忆并提醒。

### 4. 自主执行与调度
- **计划任务**：内置 cron，支持日报、备份、周审计等无人值守任务。
- **并行子代理**：派生子代理并行处理多个工作流。
- 多平台消息网关：可接到 Telegram / Discord / Slack / WhatsApp。

### 5. 部署灵活
- 最低 1 核 1G 即可运行；支持本地、Docker、SSH、Singularity 等六种后端。
- 你当前用 **local 终端后端**，配合 **tirith 沙箱** 隔离危险操作。

---

## 三、你本机的部署现状（已核验）

| 项目 | 现状 | 评价 |
|---|---|---|
| 安装位置 | `/opt/homebrew/bin/hermes`（pip 安装 hermes-agent） | ✅ |
| 版本 | **v0.19.0**（2026.7.20，已升级） | ✅ 最新版 |
| 默认模型 | `deepseek-v4-pro`（base_url: api.deepseek.com/v1） | ✅ |
| 密钥存储 | `~/.hermes/.env`（权限 600） | ✅ 安全 |
| 危险命令拦截 | `rm -rf / dd / format / mkfs` 等已拦截 | ✅ |
| 文件系统限制 | 仅允许读写 `~/hermes-work` | ✅ |
| 操作确认 | `confirmation: required`（每次执行需你确认） | ✅ |
| 沙箱 | tirith 沙箱（docker/singularity 后端可用） | ✅ |

**已执行（2026-08-11）**：`pip install --upgrade hermes-agent` 已升级到 **v0.19.0**；同时将 `state.db`、`state.db-wal/shm`、`.hermes_history` 权限收紧为 `600`（仅本人可读）。

---

## 四、精通指南：从入门到熟练

### 4.1 核心概念速览
| 概念 | 说明 | 位置 |
|---|---|---|
| 会话 (session) | 一次对话/任务的完整记录 | `~/.hermes/sessions` |
| 记忆 (memory) | 跨会话持久化的事实与偏好 | `~/.hermes/memories` |
| 技能 (skill) | 可复用的能力包（SKILL.md） | `~/.hermes/skills` |
| 计划任务 (cron) | 定时自动执行 | `~/.hermes/cron` |
| 子代理 (delegation) | 并行派生子任务 | 会话内触发 |
| 钩子 (hooks) | 事件触发脚本 | `~/.hermes/hooks` |

### 4.2 常用命令
```bash
hermes                 # 进入交互式对话
hermes "你的问题"       # 单次提问
hermes auth            # 配置/查看模型平台认证
hermes update          # 更新到最新版
hermes --version       # 查看版本
hermes sessions list   # 查看历史会话
hermes skills list     # 查看已装技能
```

### 4.3 关键配置项（`~/.hermes/config.yaml`）
```yaml
model:
  default: deepseek-v4-pro      # 主模型
  provider: deepseek
  base_url: https://api.deepseek.com/v1
agent:
  max_turns: 150                # 单任务最大轮数
terminal:
  backend: local                # 本地终端后端
  blocked_commands: rm -rf,dd,format,mkfs,del /f /s /q   # 危险命令黑名单
filesystem:
  allowed_paths: /Users/wuxuancheng/hermes-work  # 只允许操作该目录
  read_only: false
confirmation:
  required: true                # 关键操作需你确认
```

### 4.4 进阶玩法
1. **让它当"数字员工"**：把重复性工作（整理资料、转格式、生成日报）交给它，配好 cron 定时执行。
2. **技能沉淀**：遇到好流程，让它把方法固化成 skill，下次一句话复用。
3. **多模型分工**：主模型用 pro 做复杂推理，简单任务可切 flash 省钱。
4. **安全隔离**：需要执行危险命令时用 Docker/SSH 后端隔离，别用 local 裸跑。

---

## 五、大神使用案例（2026 年最新）

- **全链路本地化部署**：国内开发者将 Hermes 与 DeepSeek 组合，实现"私有化 AI 智能体"，长期运行沉淀经验技能（阿里云开发者社区 2026-05）。
- **低配服务器常驻**：社区验证 1 核 1G VPS 即可常驻运行，配合 Telegram 网关远程指挥（IT 之家 2026-06）。
- **知识库迁移**：用 html-to-markdown 技能批量把网页/导出 HTML 转 Markdown 导入 Obsidian（你已装此技能）。
- **PDF 中文 OCR**：扫描版 PDF 用 pdf-ocr 技能（tesseract + chi_sim）提取中文文本（你已装此技能）。

---

## 六、安全红线（务必遵守）

1. **保持更新**：落后版本及时 `hermes update`。
2. **密钥管理**：`~/.hermes/.env` 和 `auth.json` 保持 `600` 权限，不要提交到 git。
3. **权限最小化**：`allowed_paths` 保持只指向工作目录；危险命令黑名单不要删。
4. **确认机制**：保持 `confirmation: required = true`，别为了省事关闭。
5. **远程访问**：若开启 API 服务（API_SERVER），务必加密钥认证，不要 0.0.0.0 裸奔。

---

*资料来源：NousResearch/hermes-agent 官方仓库、hermes-agent.org、阿里云/腾讯云开发者社区 2026 年教程。*
