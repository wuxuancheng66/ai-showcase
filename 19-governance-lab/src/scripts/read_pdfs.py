# -*- coding: utf-8 -*-
# 第 4.2 节 第 2 步：批量读取 PDF → 转成 HTML
# 用法：把政策 PDF 放进 AI治理练习/policy_pdfs 文件夹，然后运行本脚本

from pathlib import Path
from pypdf import PdfReader
import html_output

ROOT = Path(__file__).parent.parent
folder = ROOT / "policy_pdfs"
out = ROOT / "policy_texts"
out.mkdir(exist_ok=True)

pdfs = sorted(folder.glob("*.pdf"))
if not pdfs:
    print("⚠️  policy_pdfs 文件夹里没有 PDF，请先把政策文件放进去，再运行本脚本。")
    raise SystemExit

for pdf_path in pdfs:
    reader = PdfReader(str(pdf_path))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    html_path = out / f"{pdf_path.stem}.html"
    body = (
        html_output.meta_block({"来源 PDF": pdf_path.name, "字数": str(len(text))})
        + f'<div class="content"><h2>提取正文</h2><pre>{html_output.escape(text)}</pre></div>'
    )
    html_output.save_html(html_path, f"政策文本 — {pdf_path.stem}", body)
    print(f"已提取：{pdf_path.name} → {html_path.name}，共 {len(text)} 字")

print(f"\n完成！共处理 {len(pdfs)} 份 PDF，HTML 已保存到 policy_texts 文件夹。")
