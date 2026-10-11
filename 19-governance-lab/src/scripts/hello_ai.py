# -*- coding: utf-8 -*-
# 你的第一个 AI 脚本：让 AI 回答一个问题
# 使用前：通过 DEEPSEEK_API_KEY 环境变量提供自己的密钥。

import os
from pathlib import Path
from openai import OpenAI
import html_output

ROOT = Path(__file__).parent.parent
OUT_FILE = ROOT / "hello_ai.html"

# ===== 第 1 步：从环境变量读取密钥，不写入源码 =====
API_KEY = os.environ.get("DEEPSEEK_API_KEY", "").strip()

# ===== 第 2 步：接口地址（DeepSeek 的固定地址，一般不用改） =====
BASE_URL = "https://api.deepseek.com"

QUESTION = "用三句话解释什么是数字政府。"

if not API_KEY:
    print("⚠️  没有找到 DeepSeek 密钥。")
    print("请在终端执行：export DEEPSEEK_API_KEY=你的密钥")
    raise SystemExit

client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

resp = client.chat.completions.create(
    model="deepseek-chat",
    messages=[
        {"role": "system", "content": "你是数字公共治理专业的助教。"},
        {"role": "user", "content": QUESTION},
    ]
)

answer = resp.choices[0].message.content
body = (
    html_output.meta_block({"模型": "deepseek-chat", "问题": QUESTION})
    + f'<div class="content"><h2>AI 的回答</h2>{html_output.text_to_html(answer)}</div>'
)
html_output.save_html(OUT_FILE, "Hello AI — 数字政府简介", body)

print(f"已生成 HTML 报告：{OUT_FILE}")
