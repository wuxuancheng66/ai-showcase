# PPT 自动生成器 · python-pptx 模板

用 Python、python-pptx 和 Pillow 生成 16 页可编辑演示文稿。此仓库保留原有竞选模板，并提供无需私人素材的演示模式；占位图清楚标记为 DEMO。

## 运行

环境需要 `python-pptx` 与 `Pillow`。核验依赖来源和版本后，在自己的 Python 环境中安装；本次优化未自动安装任何依赖。

```bash
python build_ppt.py --help
python build_ppt.py --demo --output demo.pptx
python build_ppt.py --materials ./data/materials --masked ./data/masked --assets ./data/assets --output ./presentation.pptx
```

`--check` 检查素材但不生成 PPT；`--demo --check` 确认演示模式不需要私人素材。`--work-dir` 设置图片处理目录，`--font` 设置设备已安装的字体。普通模式从当前目录的materials、masked、assets读取素材，默认输出到当前目录presentation.pptx；素材缺失时会明确报错并提示演示模式。

## 素材结构

完整文件名与使用说明见 [使用说明](usage.html)。私人照片、聊天截图和原作业数据不随仓库分发。`构建说明.md` 是早期误收录的军事理论产品说明，保留以便追溯；它不是本生成器的构建说明。

作者：吴宣澄。输出为原生 PPTX，可在 PowerPoint、WPS 或 Keynote 中继续编辑。

## 通用模板与人物信息

这是固定16页结构的竞选演示模板，不是任意文本自动生成幻灯片的服务。默认生成内容不包含作者姓名、专业或私人素材路径。用`--presenter "演示者姓名" --affiliation "单位或班级" --year "年份"`填写自己的信息；素材默认从当前目录materials、masked、assets读取，也可继续用原有参数指定。`--demo`使用合成占位图。模板中的态度、职责、工具场景与承诺是示例，正式使用前应按真实经历改写。
