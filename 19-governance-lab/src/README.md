# 政策风洞 · 文本分析研究原型

这是起步阶段的个人学习与研究原型。现有代码完成 PDF 文本提取、模型辅助条款摘要及 HTML 报告生成；持续政策雷达和政策推演是后续方向。现阶段没有经过验证的社会模拟器，模型回答不能证明政策因果效果或替代真实调查。

## 运行前

需要 Python 3.10+。公开源码不附政策全文、语料、个人报告或凭据。自行确认输入 PDF 的获取与使用权限，在隔离环境审核并安装 `requirements.txt` 中依赖；本次没有安装依赖、运行模型、付费或验证外部 API。依赖下限用于现有 SDK 接口兼容，不是锁定或审计过的运行环境。

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

将可合法处理的 PDF 放在此目录的 `policy_pdfs/`（可自行创建），提取为 `policy_texts/` 下的 HTML。扫描 PDF 没有 OCR，可能无法提取文字。

```sh
.venv/bin/python scripts/read_pdfs.py
```

## 模型选择

云端默认 DeepSeek，运行前在环境中设置 `DEEPSEEK_API_KEY`。不要把真实密钥放入源码、截图或提交历史。调用云端会向提供方发送输入文本并可能计费，请先检查文本是否适合发送。

本地可使用已自行配置的 LM Studio 兼容接口；先启动自己的本地模型服务，再运行：

```sh
POLICY_MODEL_SOURCE=local .venv/bin/python scripts/model_demo.py
POLICY_MODEL_SOURCE=local .venv/bin/python scripts/policy_pipeline.py
```

本地默认地址为 http://localhost:1234/v1 ，默认模型名在 `scripts/config.py`。可通过 `POLICY_LOCAL_BASE_URL` 与 `POLICY_LOCAL_MODEL` 调整为你自己的服务配置。云端示例 `hello_ai.py` 固定使用 DeepSeek，不跟随本地模型开关。

政策分析脚本从 `policy_texts/` 读取 HTML 或 txt，并生成 `政策分析结果.html`。当前每个文件仅发送前 6000 个字符，长文后半部分可能遗漏，摘要需回到原文核查。脚本尚无批处理重试、预算上限、来源校验与完整错误恢复。若无输入，先运行提取脚本；不要把空输入当成分析完成。

## 公开与验证范围

保留相对项目目录的提取、分析、HTML 输出与模型切换脚本。公开配置仅从环境读取凭据，不访问作者本机隐藏凭据文件。已检查 Python 语法和展示页面；未验证真实模型质量、联网分析或政策预测。本原型产生的文本应标注“AI 辅助生成”，发布前由人复核。许可证未由本次整理新增。
