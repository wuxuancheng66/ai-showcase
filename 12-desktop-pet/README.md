# 12 · desktop pet 桌面伙伴 · macOS 移植版

> 上游开源项目：[xunguangzlj-cloud/desktop-pet-community](https://github.com/xunguangzlj-cloud/desktop-pet-community) v4.0.1-preview.1（MIT 许可）
> 本文件夹为 **macOS arm64 移植构建 + 适配优化版**，2026-10-10 由 ZCode（AI）在本机完成构建与验证。

---

## 一、这是什么

一款 Electron 桌面宠物应用：桌面上常驻一只可拖拽的 Hoodie Cat（连帽衫猫），支持接入 AI 大模型对话、
人设系统（Markdown / SKILL.md 蒸馏导入）、AI 编程工具工作联动、喝水/久坐/番茄钟等提醒插件，
并内置共创平台离线快照（117 件桌宠作品 + 24 件插件可直接导入）。

上游官方只发布了 Windows x64 便携包；本版本补上了 **macOS Apple Silicon（arm64）** 构建。

## 二、安装与运行

> **分享状态（2026-10-11）**：已回馈上游——
> PR：https://github.com/xunguangzlj-cloud/desktop-pet-community/pull/2 （源码改动 + 实测报告）
> 成品 Release：https://github.com/wuxuancheng66/desktop-pet-community/releases/tag/v4.0.1-mac-arm64 （dmg/zip 可直接下载）


| 文件 | 用途 |
|------|------|
| `desktop-pet-4.0.1-mac-arm64.dmg`（868 MB） | 标准安装包，双击挂载后拖入「应用程序」 |
| `desktop-pet-4.0.1-mac-arm64.zip`（861 MB） | 便携版，解压即用 |

- 适用于 macOS 13+ / Apple Silicon（M 系列芯片）
- 应用为 **ad-hoc 签名**（无开发者证书），首次打开若提示"无法验证"：
  右键应用 →「打开」，或在「系统设置 → 隐私与安全性」点「仍要打开」
- 体积说明：其中约 850 MB 是刻意内置的**离线作品库**（桌宠广场全量内容，离线可浏览可导入），
  应用本体约 100 MB；Electron 框架与作品库均为上游设计的一部分

## 三、快速上手

1. 启动后桌宠出现在屏幕右下角，菜单栏出现托盘图标
2. 双击桌宠 → 呼出对话输入框
3. 托盘菜单 / 右键桌宠 →「打开控制中心」→「宠物大脑」→ 添加 AI 服务
   （内置 DeepSeek / OpenAI / Anthropic / OpenRouter / Ollama / LM Studio 模板）
4. 「人设个性」导入 Markdown 或 SKILL.md 人设包
5. 「共创网站」浏览离线作品库，一键导入社区桌宠与插件

## 四、macOS 移植与优化内容（本版本工作）

上游代码本身具备跨平台抽象（macOS 窗口追踪 / Dock 显隐 / 权限降级策略均已预留），
但从未在 macOS 上构建发布。本版本完成：

| 项目 | 内容 |
|------|------|
| ✅ 首次 Mac 构建 | pnpm monorepo 全量构建 + electron-builder dmg/zip（arm64） |
| ✅ 全功能实测 | 启动/渲染/托盘/隐藏显示/控制中心 9 个页面/DeepSeek 真实对话闭环（615ms 响应） |
| ✅ 修复 | `before-quit` 监听器超 10 上限的内存泄漏误报（`app.setMaxListeners(50)`） |
| ✅ 瘦身 | 剔除 sharp(@img) 中 Linux/Windows 平台原生二进制（-67 MB 纯浪费体积） |
| ✅ 回归验证 | 打包环境内 sharp 原生模块加载与图片编码测试通过 |

移植过程中的关键判断（保留上游设计，不做破坏性修改）：
- `use-mock-keychain` 保留——避免 ad-hoc 签名应用反复弹钥匙串授权框
- 离线作品库全量保留——与 Windows 官方便携包对等的产品体验
- 共创网站 dev 模式指向线上站、打包模式用本地离线快照，均为上游既有逻辑

## 五、已知限制（诚实声明）

- 语音对话功能未在 Mac 上深度验证（涉及麦克风权限与 TTS 服务接入）
- 屏幕活跃窗口追踪（"桌宠看电脑"类联动）需要 macOS「屏幕录制」权限，
  未授权时应用自动降级，不采集任何内容
- 未做公证（notarization），首次打开需要手动放行；如需分发给他人，
  建议后续申请 Apple 开发者账号补签名公证
- x86_64 Intel Mac 不在本包支持范围（上游与本人均为 arm64 优先）

## 六、AI 参与声明（红线标注）

- 本文件夹内的 macOS 构建、测试、优化与文档 **由 AI（ZCode, GLM 模型）完成**，
  上游应用的全部功能代码归 desktop-pet-community 贡献者所有（MIT）
- 构建环境：macOS 27 arm64 / Node 24.18 / pnpm 11.0.8 / Electron 42
- 构建源码与完整过程保留在本地工作区（可追溯）

## 七、本地路径

- 构建产物：本文件夹
- 源码与构建现场：`~/.zcode/workspace/default/desktop-pet-community/`
- 运行数据：`~/Library/Application Support/desktop-pet/`
