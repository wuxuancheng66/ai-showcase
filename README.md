# 吴宣澄 · AI 开发者项目展示合集

> 本合集于 2026-09-11 由 AI 全流程整编：扫描本机 AI 配置与 AI 产出的全部项目，
> 筛选出 **11 个有价值/有潜力的成品**，统一补齐文档、转换为网页版说明页后集合于此。
> **原项目均保留在原位置未做任何改动**，本合集内为独立副本。
> 根目录 `index.html` 是集成展示站（零依赖、可离线、支持深浅主题/搜索/内嵌实况预览），
> 也可直接部署到 GitHub Pages / Vercel 作为个人主页的项目集页。

---

## 一、项目导览（11 个）

| # | 项目 | 一句话简介 | 构建工具 | 体验入口 |
|---|------|-----------|----------|----------|
| 01 | [ai-agent-team](01-ai-agent-team/README.html) | 五角色多智能体协作流水线（LangGraph + 审校回流） | ZCode | 文档 · 离线测试 4/4 通过 |
| 02 | [ai-daily-reports](02-ai-daily-reports/README.html) | AI 行业日报自动化产出，32 期连更 | AI 工作流 | [目录页](02-ai-daily-reports/index.html) |
| 03 | [ielts-hub](03-ielts-hub/README.html) | 雅思备考知识站（听说读写 + 三层复盘） | VS Code / AI 辅助 | [打开网站](03-ielts-hub/site/index.html) |
| 04 | [military-hub](04-military-hub/README.html) | 军事理论备考笔记 2026 整合版（1856 题交互学习应用） | Python 流水线 | [打开学习网站](04-military-hub/军事理论备考笔记（2026整合版·交互增强版）.html) |
| 05 | [shuzhi-plan-site](05-shuzhi-plan-site/README.html) | 数智治途 · 大学规划导航站（11+ 页 + 单文件版） | Codex CLI | [打开网站](05-shuzhi-plan-site/site/index.html) |
| 06 | [personal-portfolio](06-personal-portfolio/README.html) | 个人作品集网站（深色玻璃拟态 + 3D 卡片） | VS Code | [打开网站](06-personal-portfolio/index.html) |
| 07 | [pomodoro-timer](07-pomodoro-timer/README.html) | 番茄钟桌面小工具（446 行零依赖） | AI 辅助 | `python3 pomodoro_timer.py` |
| 08 | [ppt-autogen](08-ppt-autogen/README.html) | PPT 自动生成器（python-pptx 实战验证） | AI 辅助 | 见 README |
| 09 | [ai-handbooks](09-ai-handbooks/README.html) | 15 份 AI 工具中文手册 | AI 辅助 | [手册索引](09-ai-handbooks/README.html) |
| 10 | [personal-profile-site](10-personal-profile-site/README.html) | 个人简介网站 · Coze 扣子构建版（含部署二维码） | Coze | [打开网站](10-personal-profile-site/个人简介网站.html) |
| 11 | [wordvault](11-wordvault/README.html) | WordVault 单词本（Coze 生成，216KB 离线背单词） | Coze | [打开应用](11-wordvault/WordVault单词本.html) |

每个项目文件夹内：`README.md`（源）+ `README.html`（网页版，浏览器直开无乱码）。

## 二、本机 AI 配置盘点（2026-09-11）

> 仅列工具与用途，**不含任何 API Key / Token 等敏感信息**。

| 工具 | 用途 | 本机痕迹 | 状态 |
|------|------|----------|------|
| ZCode | 主力编码智能体（本合集由它盘点生成） | `~/.zcode/workspace` | ✅ 活跃 |
| WorkBuddy 5.5.3 | 腾讯 AI 办公台，已接入微信 + 小程序远程通道 | `/Applications` · `~/WorkBuddy` | ✅ 已绑定微信 |
| OpenClaw | 常驻个人 Agent 网关（NVIDIA nemotron 模型） | `~/.openclaw`（git 管理） | ✅ 网关运行中 |
| Codex CLI | 编码代理（数智治途站点即由它构建） | `~/Documents/Codex` | ✅ 活跃 |
| Hermes Agent | 文档/规划类任务代理 | `~/hermes-work` | ✅ 有产出 |
| DSH（豆包桌面） | PPT/文档生成（军理题库流水线所在工作区） | `~/Documents/dsh-workspace` | ✅ 有产出 |
| Kimi | 网页桥接实验 | `~/Documents/kimi` | 🧪 实验 |
| Coze（扣子） | Bot/站点平台 | `~/Coze`（本地云盘当前为空） | ⚠️ 见下注 |
| LM Studio | 本地模型运行时 | `~/Applications` | ✅ 已安装 |
| Cursor / VS Code + Claude Code | AI 编辑器组合 | `/Applications` | ✅ 日常工具 |
| Obsidian | 双链知识库 | `~/Documents/吴宣澄的知识库` | ✅ 在用 |

> **关于 Coze 制作的站点**：「个人简介网站」已收录为项目 10（含 Netlify 部署二维码）。
> 「单词网站」经全盘检索（含 Spotlight 索引）仍未找到独立文件——雅思站的「单词」模块已随项目 03 收录；
> 若你在扣子云端还有独立的单词站点，导出 HTML 放入本文件夹即可，我会按同样标准接入。

## 三、检验记录（2026-09-11 第二轮）

- ✅ **使用数据清理**：军理站副本的本地存储键已隔离（`jl4.` → `scjl4.`，21 处）——副本打开即为全新状态，
  与你真实备考的做题记录/错题本完全分离，互不影响；数智治途副本存储键同步隔离（`zst_` → `zstsc_`，9 处）；
- ✅ 个人简介网站（Coze 导出）核验：无第三方统计脚本、无追踪器、无内嵌使用数据；
- ✅ **隐私泄漏排查（第二轮）**：数智治途站内真实学号已在全部副本中脱敏（26••••••30）；
  全站扫描无手机号/身份证/真实邮箱泄漏（日报中的长数字经查证均为新闻文章 URL 编号）；
  ⚠️ 仍保留的个人信息：姓名（作品集展示主体，属有意展示）与数智治途内的个人规划叙述
  （含政治面貌与入党路线），公开部署前请自行决定是否进一步脱敏；
- ✅ 全合集无 `.DS_Store` / `__pycache__` / 缓存残留；全部 HTML 带 UTF-8 声明；
- ✅ 全部 Python 复制件通过编译校验；展示站与各站点链接经脚本校验全部有效。

## 四、如何展示

1. **快速预览**：双击根目录 `index.html`（支持深浅主题切换、搜索筛选、卡片内嵌实况预览）；
2. **部署为个人主页**：整包推到 GitHub 仓库开启 Pages（或 Vercel/Netlify），`index.html` 即首页；
3. **单独开源某个项目**：每个子文件夹自带 README + LICENSE（MIT），直接 `git init` 推送即可。

---
作者：吴宣澄 · 2026-09 · License: [MIT](LICENSE)
