# PPT 自动生成器 · python-pptx 模板

用 Python、python-pptx 和 Pillow 生成 16 页可编辑演示文稿。此仓库保留原有竞选模板，并提供无需私人素材的演示模式；占位图清楚标记为 DEMO。

## 运行

环境需要 `python-pptx` 与 `Pillow`。核验依赖来源和版本后，在自己的 Python 环境中安装；本次优化未自动安装任何依赖。

```bash
python build_ppt.py --help
python build_ppt.py --demo --output demo.pptx
python build_ppt.py --materials ./data/materials --masked ./data/masked --assets ./data/assets --output ./presentation.pptx
```

`--check` 检查素材但不生成 PPT；`--demo --check` 确认演示模式不需要私人素材。`--work-dir` 设置图片处理目录，`--font` 设置设备已安装的字体。普通无参数运行沿用原本本机素材与输出位置；素材缺失时会明确报错并提示演示模式。

## 素材结构

完整文件名与使用说明见 [使用说明](usage.html)。私人照片、聊天截图和原作业数据不随仓库分发。`构建说明.md` 是早期误收录的军事理论产品说明，保留以便追溯；它不是本生成器的构建说明。

作者：吴宣澄。输出为原生 PPTX，可在 PowerPoint、WPS 或 Keynote 中继续编辑。
