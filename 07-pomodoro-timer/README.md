# 🍅 Pomodoro Timer · 桌面番茄钟

![Python](https://img.shields.io/badge/Python-3.x-3776AB?logo=python&logoColor=white)
![Deps](https://img.shields.io/badge/依赖-零（纯tkinter）-success)
![Lines](https://img.shields.io/badge/代码-446行-blue)
![License](https://img.shields.io/badge/License-MIT-informational)

紧凑型桌面番茄钟小组件：**圆形进度环 + 桌面系统通知**，纯 Python tkinter 实现，零第三方依赖。

## ✨ 功能

- 三种模式一键切换（快捷键 `1` / `2` / `3`）；
- `空格` 开始/暂停，`R` 重置，`→` 跳过当前阶段；
- 圆环进度实时渲染；阶段结束时触发 macOS/Windows 系统通知；
- 置顶小窗不挡工作区。

## 🚀 运行

```bash
python3 pomodoro_timer.py    # 无需安装任何依赖
```

macOS 首次运行需在「系统设置 → 通知」中允许 Python 发送通知。

---
作者：吴宣澄 · 2026

## 参数与计时

`python3 pomodoro_timer.py --work 30 --short-break 5 --long-break 20` 自定义分钟数；`--help` 查看说明，`--check` 只检查 Tk 运行库，不打开窗口。计时按单调时钟的截止时间计算，回调延迟不会累积成逐秒漂移；长时间系统休眠的行为取决于平台时钟。需使用包含 tkinter/Tk 的 Python。跳过当前阶段沿用原逻辑，专注阶段会计入完成次数。
