# PPT 自动生成器 · python-pptx 构建流水线

![Python](https://img.shields.io/badge/Python-3.x-3776AB?logo=python&logoColor=white)
![Lib](https://img.shields.io/badge/python--pptx-%20-Python?logo=python&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-informational)

**代码即幻灯片**：用 python-pptx + PIL 以纯代码批量生成分模块 PPT——版式、配色、图片裁切、
中英混排全部程序化控制，一次编写、秒级重建整套演示文稿。

> 实战产出：已用于生成真实课堂演示文件（作业数据出于隐私未随仓库分发，见下方"数据接口"）。

## ✨ 亮点

- **确定性排版**：相较手动拖拽，代码生成的版式 100% 一致、可版本管理；
- **图片自动处理**：PIL 预处理（裁切/缩放）后嵌入，不再手动调图；
- **原生 pptx 输出**：生成的文件可继续用 PowerPoint/WPS/Keynote 手工微调。

## 🚀 使用

```bash
pip install python-pptx pillow
python build_ppt.py
```

## 📁 数据接口

脚本从 `data/` 目录读取图片与文本素材（本仓库未附带数据，目录结构见 `构建说明.md`）。
接入你自己的素材后即可一键重建。

---
作者：吴宣澄 · 2026-09
