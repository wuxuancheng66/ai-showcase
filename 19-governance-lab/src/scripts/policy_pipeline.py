# -*- coding: utf-8 -*-
# 第 4.2 节 第 3 步：批量分析政策文本 → 生成 政策分析结果.html
# 自动使用 config.py 里选择的模型（云端 DeepSeek / 本地 LM Studio）

import html as html_lib
import re
from pathlib import Path
from openai import OpenAI
import config
import html_output

ROOT = Path(__file__).parent.parent
TEXT_DIR = ROOT / "policy_texts"
OUT_FILE = ROOT / "政策分析结果.html"

base_url, api_key, model = config.get_config()
source = "本地模型" if api_key == "lm-studio" else "云端模型"
print(f"本次使用：{source}（{model}）\n")

SYSTEM_PROMPT = (
    "你是政策分析专家。请从政策文本中提取："
    "1) 文件主题 2) 核心目标 3) 关键条款（3-5条）4) 主要实施手段 "
    "5) 可能的难点。用中文回答，分点列出。"
)


def html_to_text(raw: str) -> str:
    """从 read_pdfs 生成的 HTML 中提取正文。"""
    m = re.search(r"<pre>(.*?)</pre>", raw, re.DOTALL)
    if m:
        return html_lib.unescape(m.group(1))
    return re.sub(r"<[^>]+>", "", raw)


def load_policy_text(path: Path) -> str:
    if path.suffix.lower() == ".html":
        return html_to_text(path.read_text(encoding="utf-8"))
    return path.read_text(encoding="utf-8")


client = OpenAI(api_key=api_key, base_url=base_url)

inputs = sorted(list(TEXT_DIR.glob("*.html")) + list(TEXT_DIR.glob("*.txt")))
if not inputs:
    print("⚠️  policy_texts 文件夹里没有 HTML/txt 文件，请先运行 read_pdfs.py 提取文本。")
    raise SystemExit

results = {}
for src_path in inputs:
    text = load_policy_text(src_path)[:6000]
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
        temperature=0.3,
    )
    results[src_path.stem] = resp.choices[0].message.content
    print(f"完成：{src_path.stem}")

sections = []
for name, analysis in results.items():
    sections.append(
        f'<div class="section"><h2>{html_output.escape(name)}</h2>'
        f'{html_output.text_to_html(analysis)}</div>'
    )

body = (
    html_output.meta_block({"模型源": source, "模型": model, "分析文件数": str(len(results))})
    + "\n".join(sections)
)
html_output.save_html(OUT_FILE, "政策分析结果", body)
print(f"\n全部完成！结果已保存到：{OUT_FILE}")
