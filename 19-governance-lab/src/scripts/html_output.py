# -*- coding: utf-8 -*-
"""各脚本共用的 HTML 输出工具。"""

import html
from datetime import datetime


STYLE = """
body { font-family: -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif;
       max-width: 900px; margin: 40px auto; padding: 0 24px; line-height: 1.7; color: #222; }
h1 { border-bottom: 2px solid #2563eb; padding-bottom: 8px; }
h2 { color: #1e40af; margin-top: 2em; }
.meta { background: #f1f5f9; padding: 12px 16px; border-radius: 8px; font-size: 0.95em; }
.meta p { margin: 4px 0; }
.content { margin-top: 24px; }
.content p { margin: 0.8em 0; }
.content pre { background: #f8fafc; padding: 16px; border-radius: 8px;
               overflow-x: auto; white-space: pre-wrap; word-break: break-word; }
.section { border-left: 4px solid #93c5fd; padding-left: 16px; margin: 24px 0; }
footer { margin-top: 48px; color: #64748b; font-size: 0.85em; }
"""


def escape(text: str) -> str:
    return html.escape(text or "")


def text_to_html(text: str) -> str:
    """纯文本转 HTML 段落。"""
    parts = []
    for block in (text or "").split("\n\n"):
        block = block.strip()
        if not block:
            continue
        inner = "<br>\n".join(escape(line) for line in block.split("\n"))
        parts.append(f"<p>{inner}</p>")
    return "\n".join(parts) if parts else "<p></p>"


def meta_block(items: dict) -> str:
    rows = "".join(f"<p><strong>{escape(k)}：</strong>{escape(v)}</p>" for k, v in items.items())
    return f'<div class="meta">{rows}</div>'


def wrap_page(title: str, body_html: str) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)}</title>
  <style>{STYLE}</style>
</head>
<body>
  <h1>{escape(title)}</h1>
  {body_html}
  <footer>生成时间：{now}</footer>
</body>
</html>
"""


def save_html(path, title: str, body_html: str) -> None:
    path.write_text(wrap_page(title, body_html), encoding="utf-8")
