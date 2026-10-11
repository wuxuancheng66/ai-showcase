# -*- coding: utf-8 -*-
# 演示脚本：通过"模型配置中心"选模型，问 AI 一个问题
# 使用前：1) 设置 DEEPSEEK_API_KEY 环境变量；2) 本地模型需先打开 LM Studio 服务器

from pathlib import Path
from openai import OpenAI
import config
import html_output

ROOT = Path(__file__).parent.parent
OUT_FILE = ROOT / "model_demo.html"

base_url, api_key, model = config.get_config()
source = "本地 LM Studio" if api_key == "lm-studio" else "云端 DeepSeek"
question = "用一句话介绍你自己，并说明你适合帮什么忙。"

client = OpenAI(api_key=api_key, base_url=base_url)

resp = client.chat.completions.create(
    model=model,
    messages=[
        {"role": "system", "content": "你是数字公共治理专业的助教。"},
        {"role": "user", "content": question},
    ]
)

answer = resp.choices[0].message.content
body = (
    html_output.meta_block({"模型源": source, "模型": model, "问题": question})
    + f'<div class="content"><h2>AI 的回答</h2>{html_output.text_to_html(answer)}</div>'
)
html_output.save_html(OUT_FILE, "模型演示 — 助教自我介绍", body)

print(f"已生成 HTML 报告：{OUT_FILE}")
