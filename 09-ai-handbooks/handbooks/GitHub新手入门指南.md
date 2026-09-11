# GitHub 新手入门指南（从零开始）

> 版本：v1.0 · 2026-08-12 · 写给纯新手：不需要任何基础，照着做就行

---

## 一、GitHub 是什么？（大白话版）

GitHub 是**全球最大的代码托管平台**，你可以把它理解为：

- **代码版的"网盘"**：把你的项目代码存到云端，电脑坏了也不怕丢
- **程序员的朋友圈**：全世界的开发者在这里分享、收藏、交流代码
- **免费学习资料库**：几百万个开源项目，随便看、随便学
- **求职作品集**：你的 GitHub 主页就是最好的"技术简历"

注册和使用**完全免费**，英文界面（习惯后很简单）。

---

## 二、为什么要用 GitHub？（给你的理由）

| 场景 | 好处 |
|---|---|
| 备份项目 | 你的代码/作业/项目永不丢失，还能看历史版本 |
| 学习 | 看大佬的开源项目，读源码、抄思路（AI 工具也能直接"读"GitHub 代码） |
| 协作 | 和同学一起写代码，各改各的不冲突 |
| 求职 | 面试官看你的 GitHub = 看你的真实水平 |

---

## 三、注册账号（约 5 分钟）

1. 浏览器打开 **https://github.com** → 点 **Sign up**
2. 依次填：**邮箱** → **密码** → **用户名**
   - ⚠️ 用户名会出现在你的主页链接 `github.com/你的用户名`，选个正式、好记的
3. 完成一个简单的拼图验证（防机器人）
4. 去邮箱点验证链接 → 完成 🎉

---

## 四、核心概念（新手必懂的 8 个词）

| 概念 | 大白话解释 |
|---|---|
| **仓库 Repo** | 一个项目 = 一个仓库（含全部代码和历史版本） |
| **提交 Commit** | 给项目"存一次档"，附一句说明（"改了登录 bug"） |
| **推送 Push** | 把本地的存档上传到 GitHub |
| **拉取 Pull** | 把 GitHub 上的更新下载到本地 |
| **分支 Branch** | 主干旁边开一条"平行线"，随便改不碰主干 |
| **合并请求 PR** | 把分支的改动申请合并进主干（可审查、可讨论） |
| **克隆 Clone** | 把别人的仓库完整复制到本地 |
| **Star / Fork** | 给项目点赞收藏 / 复制一份到自己名下 |

---

## 五、第一次创建仓库并上传代码

### 方式 A：纯网页操作（最简单，推荐新手先试）
1. 登录后点右上角 **+** → **New repository**
2. 填仓库名（如 `my-first-project`）→ 点 **Create repository**
3. 在新页面点 **uploading an existing file**，把文件拖进去 → **Commit changes**
4. 完成！你的项目已经在云端了 ✅

### 方式 B：命令行（正规做法，以后常用）
在你的项目文件夹打开终端：

```bash
cd 你的项目文件夹
git init
git add .
git commit -m "第一次提交"
git branch -M main
git remote add origin https://github.com/你的用户名/仓库名.git
git push -u origin main
```

> 第一次 push 会让你输入 GitHub 用户名和 Token（不是密码，见第八节）。

---

## 六、日常常用命令速查

| 命令 | 作用 |
|---|---|
| `git status` | 看当前有哪些改动 |
| `git add .` | 把所有改动放入"待提交区" |
| `git commit -m "说明"` | 提交存档（带说明） |
| `git push` | 上传到 GitHub |
| `git pull` | 拉取最新版本 |
| `git log --oneline` | 看提交历史 |
| `git clone 网址` | 克隆别人/自己的仓库到本地 |

> 新手期不想记命令？装一个 **GitHub Desktop**（官网免费下载），所有操作都变成点按钮。

---

## 七、安全须知（重要！）

1. **Token 就是"钥匙"**：只在可信的地方使用，别截图发群里；丢了随时去后台撤销重发
2. **不要把密码/API Key 提交进仓库**：用 `.gitignore` 文件排除（`node_modules/`、`.env`、`*.key` 等）
3. **公共仓库 = 所有人都能看**：别放隐私、作业答案、证件信息
4. 好消息：你的 Claude Code 已配好「密钥入库检查」钩子，提交前会自动拦截疑似密钥 ✅

---

## 八、接上你的 AI 工具（Claude Code + Codex）—— 以后想用随时接

等你有账号、有仓库后，可以让 AI 直接操作 GitHub：

1. GitHub → **Settings** → **Developer settings** → **Personal access tokens** → **Fine-grained tokens**
2. **Generate new token**，勾选权限：
   - `Contents` → Read and write
   - `Pull requests` → Read and write
   - `Issues` → Read and write
3. 复制 `github_pat_` 开头的 Token
4. 找 Codex 说一句：**「帮我接 GitHub MCP」**，2 分钟配好两边
5. 之后就可以说：*"帮我把这个项目推上 GitHub"*、*"看看这个仓库的代码结构"*、*"帮我建个 Issue 记录这个 bug"*

---

## 九、新手学习路径建议

1. **今天**：注册账号 + 用网页版建第一个仓库（放个笔记/小项目都行）
2. **本周**：装 GitHub Desktop，把日常文件传上去练手
3. **本月**：逛 3-5 个热门仓库，读 README（比如你用的工具的官方仓库）
4. **进阶**：学命令行 git（上面第六节）、学分支和 PR 协作
5. **高阶**：把 GitHub MCP 接上，让 Claude Code / Codex 帮你管理仓库

---

## 十、资源

- GitHub 注册：https://github.com
- GitHub Desktop 下载：https://desktop.github.com
- GitHub 官方文档（中文）：https://docs.github.com/zh
- 你的 AI 知识库手册：`VSCode+ClaudeCode接DeepSeekV4指南.md`（含 GitHub MCP 接入步骤）
