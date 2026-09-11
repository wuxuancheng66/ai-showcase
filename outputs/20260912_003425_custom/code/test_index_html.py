"""index.html 结构与可访问性回归测试。

仅依赖标准库 ``html.parser`` 与 pytest，不引入任何第三方 HTML 解析器。
覆盖核心路径（文档骨架、元信息、地标、表单可访问名）与异常路径
（未闭合标签、错配闭合、占位链接、缺失可访问名）。
"""

from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Final

import pytest

INDEX_PATH: Final = Path(__file__).with_name("index.html")

#: HTML 规范定义的 void 元素，不需要闭合标签。
VOID_ELEMENTS: Final = frozenset(
    {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
    }
)

#: 交互元素必须带可访问名。
INTERACTIVE_TAGS: Final = frozenset({"button", "a", "input", "iframe"})


class _DocParser(HTMLParser):
    """收集开/闭标签栈与属性，用于结构断言。

    Attributes:
        stack: 尚未闭合的开标签 ``(tag, lineno)``。
        mismatched: 闭合标签与栈顶不匹配的记录 ``(open, close, lineno)``。
        start_tags: 全部开标签 ``(tag, attrs, lineno)``。
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[tuple[str, int]] = []
        self.unclosed: list[tuple[str, int]] = []
        self.mismatched: list[tuple[str, str, int]] = []
        self.start_tags: list[tuple[str, dict[str, str | None], int]] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        self.start_tags.append((tag, dict(attrs), self.getpos()[0]))
        if tag not in VOID_ELEMENTS:
            self.stack.append((tag, self.getpos()[0]))

    def handle_startendtag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        self.start_tags.append((tag, dict(attrs), self.getpos()[0]))

    def handle_endtag(self, tag: str) -> None:
        if tag in VOID_ELEMENTS or not self.stack:
            if not self.stack and tag not in VOID_ELEMENTS:
                self.mismatched.append(("<空栈>", tag, self.getpos()[0]))
            return
        if self.stack[-1][0] == tag:
            self.stack.pop()
            return
        self.mismatched.append((self.stack[-1][0], tag, self.getpos()[0]))
        for idx in range(len(self.stack) - 1, -1, -1):
            if self.stack[idx][0] == tag:
                del self.stack[idx:]
                return


@pytest.fixture(scope="module")
def source() -> str:
    """返回 index.html 的完整文本。"""
    return INDEX_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def doc(source: str) -> _DocParser:
    """返回解析完毕的文档对象，``unclosed`` 已填充。"""
    parser = _DocParser()
    parser.feed(source)
    parser.close()
    parser.unclosed = list(parser.stack)
    return parser


def test_doctype_is_first(source: str) -> None:
    """核心路径：文档必须以 HTML5 DOCTYPE 起始。"""
    assert source.lstrip().startswith("<!DOCTYPE html>")


def test_html_lang_declared(source: str) -> None:
    """核心路径：<html> 必须声明 lang。"""
    assert re.search(r'<html\b[^>]*\blang="zh-CN"', source)


def test_head_meta_complete(source: str) -> None:
    """核心路径：charset / viewport / title / description / author 齐备。"""
    assert '<meta charset="UTF-8">' in source
    assert 'name="viewport"' in source
    assert re.search(r"<title>[^<]+</title>", source)
    assert 'name="description"' in source
    assert 'name="author"' in source


def test_no_unclosed_tags(doc: _DocParser) -> None:
    """异常路径：不得存在未闭合的标签。"""
    assert doc.unclosed == [], f"未闭合标签：{doc.unclosed}"


def test_no_mismatched_tags(doc: _DocParser) -> None:
    """异常路径：不得存在错配的闭合标签。"""
    assert doc.mismatched == [], f"标签错配：{doc.mismatched}"


def test_single_h1_and_heading_order(doc: _DocParser) -> None:
    """核心路径：恰好一个 h1，且 h2 出现在 h1 之后。"""
    headings = [tag for tag, _attrs, _ln in doc.start_tags if re.fullmatch(r"h[1-6]", tag)]
    assert headings.count("h1") == 1
    assert headings.index("h1") < headings.index("h2")


def test_all_images_have_alt(source: str) -> None:
    """异常路径：任何 <img> 都必须有非空 alt（本页预期为 0 张）。"""
    for tag in re.findall(r"<img\b[^>]*>", source):
        assert re.search(r'\balt="[^"]+"', tag), f"缺少 alt：{tag}"


def test_interactive_elements_have_accessible_name(doc: _DocParser) -> None:
    """核心路径：button / iframe / input 必须带 aria-label、title 或可见文本。"""
    for tag, attrs, line in doc.start_tags:
        if tag not in INTERACTIVE_TAGS:
            continue
        if attrs.get("aria-hidden") == "true":
            continue
        has_name = bool(attrs.get("aria-label") or attrs.get("title"))
        if tag == "a":
            has_name = has_name or bool(attrs.get("href"))
        if tag == "input":
            assert attrs.get("aria-label") or attrs.get("id"), f"L{line} input 缺少可访问名"
            continue
        assert has_name, f"L{line} <{tag}> 缺少可访问名"


def test_iframe_has_title(doc: _DocParser) -> None:
    """核心路径：预览 iframe 必须带 title。"""
    iframes = [attrs for tag, attrs, _ln in doc.start_tags if tag == "iframe"]
    assert iframes, "未找到 iframe"
    for attrs in iframes:
        assert attrs.get("title"), "iframe 缺少 title"


def test_no_placeholder_links(source: str) -> None:
    """异常路径：不得出现 href=\"#\" 之类的失效占位链接。"""
    assert 'href="#"' not in source
    assert "href='#'" not in source
    assert "javascript:void(0)" not in source


def test_theme_toggle_is_button_with_label(doc: _DocParser) -> None:
    """核心路径：主题切换控件必须是带 aria-label 的 button。"""
    matches = [
        attrs
        for tag, attrs, _ln in doc.start_tags
        if tag == "button" and attrs.get("id") == "theme"
    ]
    assert matches, "未找到 #theme"
    assert matches[0].get("type") == "button"
    assert matches[0].get("aria-label")


def test_closing_html_tag_is_last(source: str) -> None:
    """核心路径：文档以 </html> 结束。"""
    assert source.rstrip().endswith("</html>")
