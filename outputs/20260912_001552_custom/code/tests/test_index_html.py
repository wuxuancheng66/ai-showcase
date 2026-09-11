"""index.html 的结构完整性与可访问性回归测试。

仅依赖标准库 ``html.parser`` 与 pytest，可在仓库根目录直接运行::

    pytest tests/test_index_html.py -q

测试项对应完善方案中的修复措施：M1（骨架 / lang）、M2（charset / viewport）、
M3（SEO 元信息）、M4（语义地标）、M5（图片 alt / 外链 rel）、M6（表单 label 与校验）、
M7（无内联样式与内联事件）、M8（无占位内容）、M9（重复 ID / 失效锚点）。
"""

from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Final

import pytest

INDEX_PATH: Final[Path] = Path(__file__).resolve().parents[1] / "index.html"

_TEXT_TAGS: Final[frozenset[str]] = frozenset(
    {"title", "h1", "h2", "h3", "h4", "h5", "h6", "label", "summary", "button", "a"}
)
_LABELLABLE_TAGS: Final[frozenset[str]] = frozenset({"input", "select", "textarea"})
_NON_TEXT_INPUT_TYPES: Final[frozenset[str]] = frozenset(
    {"hidden", "submit", "button", "reset", "image"}
)
_LANDMARK_TAGS: Final[frozenset[str]] = frozenset({"header", "main", "nav", "footer", "aside"})
_PLACEHOLDER_TOKENS: Final[tuple[str, ...]] = (
    "lorem",
    "ipsum",
    "todo",
    "fixme",
    "xxx",
    'href="#"',
    "example.com",
)
_DOCTYPE_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"\A(?:\s+|<!--.*?-->)*<!DOCTYPE\s+html\s*>", re.IGNORECASE | re.DOTALL
)
_HEADING_PATTERN: Final[re.Pattern[str]] = re.compile(r"h[1-6]")
_LANG_PATTERN: Final[re.Pattern[str]] = re.compile(r"[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*")


class HtmlAudit(HTMLParser):
    """抽取结构 / 可访问性事实的最小 HTML 解析器。

    只收集测试需要的事实，不构建完整 DOM，避免引入第三方解析依赖。

    Attributes:
        html_attrs: ``<html>`` 元素的属性表。
        ids: 文档中出现的全部 ``id`` 值（含重复项）。
        texts: ``(标签名, 起始标签属性, 去空白后的文本)`` 三元组列表。
        metas: 全部 ``<meta>`` 元素的属性表。
        links: 全部 ``<a>`` 元素的属性表。
        images: 全部 ``<img>`` 元素的属性表。
        controls: ``(标签名, 属性表)`` 形式的表单控件列表。
        sections: 全部 ``<section>`` 元素的属性表。
        landmarks: 地标标签名的出现序列。
        inline_events: 采集到的内联事件属性（如 ``<button onclick>``）。
        style_attrs: 采集到的内联 ``style`` 属性所在标签。
        scripts: 全部 ``<script>`` 元素的属性表。
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.html_attrs: dict[str, str] = {}
        self.ids: list[str] = []
        self.texts: list[tuple[str, dict[str, str], str]] = []
        self.metas: list[dict[str, str]] = []
        self.links: list[dict[str, str]] = []
        self.images: list[dict[str, str]] = []
        self.controls: list[tuple[str, dict[str, str]]] = []
        self.sections: list[dict[str, str]] = []
        self.landmarks: list[str] = []
        self.inline_events: list[str] = []
        self.style_attrs: list[str] = []
        self.scripts: list[dict[str, str]] = []
        self._stack: list[dict[str, Any]] = []

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """把自闭合标签（如 ``<meta />``）与普通开始标签统一处理。"""
        self.handle_starttag(tag, attrs)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """记录开始标签上的结构事实。"""
        data = {name.lower(): (value or "") for name, value in attrs}

        if tag == "html":
            self.html_attrs = data
        if data.get("id"):
            self.ids.append(data["id"])
        for name in data:
            if name.startswith("on"):
                self.inline_events.append(f"<{tag} {name}>")
        if "style" in data:
            self.style_attrs.append(f"<{tag}>")

        if tag == "meta":
            self.metas.append(data)
        elif tag == "a":
            self.links.append(data)
        elif tag == "img":
            self.images.append(data)
        elif tag in _LABELLABLE_TAGS:
            self.controls.append((tag, data))
        elif tag == "section":
            self.sections.append(data)
        elif tag == "script":
            self.scripts.append(data)

        if tag in _LANDMARK_TAGS:
            self.landmarks.append(tag)

        if tag in _TEXT_TAGS:
            self._stack.append({"tag": tag, "attrs": data, "chunks": []})

    def handle_endtag(self, tag: str) -> None:
        """闭合文本类标签时汇总其文本内容。"""
        for index in range(len(self._stack) - 1, -1, -1):
            frame = self._stack[index]
            if frame["tag"] != tag:
                continue
            del self._stack[index:]
            text = " ".join("".join(frame["chunks"]).split())
            self.texts.append((tag, frame["attrs"], text))
            return

    def handle_data(self, data: str) -> None:
        """把文本片段追加到所有处于打开状态的文本类标签。"""
        for frame in self._stack:
            frame["chunks"].append(data)


@pytest.fixture(scope="module")
def raw_html() -> str:
    """返回 index.html 的原始文本。"""
    assert INDEX_PATH.is_file(), f"未找到待测文件：{INDEX_PATH}"
    return INDEX_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def audit(raw_html: str) -> HtmlAudit:
    """解析 index.html，返回结构事实集合。"""
    parser = HtmlAudit()
    parser.feed(raw_html)
    parser.close()
    return parser


def headings(audit: HtmlAudit) -> list[tuple[int, str]]:
    """返回按文档顺序排列的 ``(层级, 文本)`` 标题列表。"""
    return [
        (int(tag[1]), text)
        for tag, _attrs, text in audit.texts
        if _HEADING_PATTERN.fullmatch(tag)
    ]


# --------------------------------------------------------------------------- #
# M1：文档骨架
# --------------------------------------------------------------------------- #
def test_doctype_is_first_significant_token(raw_html: str) -> None:
    """``<!DOCTYPE html>`` 之前只允许空白或注释，否则会进入怪异模式。"""
    assert _DOCTYPE_PATTERN.match(raw_html), "DOCTYPE 缺失，或其前存在非注释内容"


def test_html_lang_is_declared(audit: HtmlAudit) -> None:
    """``<html>`` 必须声明合法的 BCP 47 语言标签。"""
    lang = audit.html_attrs.get("lang", "")
    assert lang, "<html> 缺少 lang 属性"
    assert _LANG_PATTERN.fullmatch(lang), f"lang 取值不合法：{lang!r}"


# --------------------------------------------------------------------------- #
# M2：charset 与 viewport
# --------------------------------------------------------------------------- #
def test_charset_declared_before_title(raw_html: str, audit: HtmlAudit) -> None:
    """``<meta charset>`` 必须存在且位于 ``<title>`` 之前。"""
    charsets = [meta for meta in audit.metas if "charset" in meta]
    assert len(charsets) == 1, "charset 声明缺失或重复"
    assert charsets[0]["charset"].lower() == "utf-8"
    lowered = raw_html.lower()
    assert lowered.index("<meta charset") < lowered.index("<title")


def test_viewport_keeps_zoom_available(audit: HtmlAudit) -> None:
    """viewport 必须自适应设备宽度，且不得禁用用户缩放（WCAG 1.4.4）。"""
    viewports = [meta for meta in audit.metas if meta.get("name", "").lower() == "viewport"]
    assert len(viewports) == 1, "viewport 声明缺失或重复"

    content = viewports[0].get("content", "").lower()
    assert "width=device-width" in content
    assert "initial-scale=1" in content
    assert "user-scalable=no" not in content, "禁止了用户缩放"
    assert "maximum-scale" not in content, "限制了用户缩放上限"


# --------------------------------------------------------------------------- #
# M3：SEO 元信息
# --------------------------------------------------------------------------- #
def test_title_is_present_and_unique(audit: HtmlAudit) -> None:
    """页面必须有且仅有一个非空标题。"""
    titles = [text for tag, _attrs, text in audit.texts if tag == "title"]
    assert len(titles) == 1, f"``<title>`` 数量异常：{len(titles)}"
    assert titles[0], "``<title>`` 内容为空"


def test_seo_meta_is_complete(audit: HtmlAudit) -> None:
    """description 与 og 系列元信息必须齐备且非空。"""
    metas = {
        meta.get("name") or meta.get("property"): meta.get("content", "")
        for meta in audit.metas
    }
    for key in ("description", "og:type", "og:title", "og:description", "og:locale"):
        assert metas.get(key), f"缺少元信息：{key}"


# --------------------------------------------------------------------------- #
# M4：语义地标与标题层级
# --------------------------------------------------------------------------- #
def test_landmarks_are_present_and_unique(audit: HtmlAudit) -> None:
    """页面上必须有且仅有一个 ``main``，并具备页头、页脚与导航地标。"""
    assert audit.landmarks.count("main") == 1, "``<main>`` 必须且只能出现一次"
    assert audit.landmarks.count("header") >= 1
    assert audit.landmarks.count("footer") >= 1
    assert audit.landmarks.count("nav") >= 1


def test_sections_have_accessible_names(audit: HtmlAudit) -> None:
    """每个 ``<section>`` 都要有可访问名称，且引用的 id 真实存在。"""
    id_set = set(audit.ids)
    assert audit.sections, "页面没有使用 ``<section>`` 划分区块"
    for section in audit.sections:
        assert section.get("aria-label") or section.get("aria-labelledby"), (
            "<section> 缺少 aria-label / aria-labelledby"
        )
        for token in section.get("aria-labelledby", "").split():
            assert token in id_set, f"aria-labelledby 指向不存在的 id：{token}"


def test_heading_hierarchy(audit: HtmlAudit) -> None:
    """标题必须唯一 h1，且层级不得跳级。"""
    levels = [level for level, _text in headings(audit)]
    assert levels, "页面没有任何标题"
    assert levels.count(1) == 1, f"``<h1>`` 数量应为 1，实际为 {levels.count(1)}"
    assert levels[0] == 1, "首个标题必须是 ``<h1>``"
    for previous, current in zip(levels, levels[1:]):
        assert current - previous <= 1, f"标题层级由 h{previous} 跳到 h{current}"


def test_skip_link_points_to_main(audit: HtmlAudit) -> None:
    """第一个链接应为指向主内容的跳转链接。"""
    assert audit.links, "页面没有任何链接"
    first = audit.links[0]
    assert first.get("href") == "#main", "首个链接不是跳转到 #main 的跳转链接"
    assert "skip-link" in first.get("class", "")


# --------------------------------------------------------------------------- #
# M5：图片与外链
# --------------------------------------------------------------------------- #
def test_images_declare_alt(audit: HtmlAudit) -> None:
    """每张图片都必须显式声明 alt（装饰性图片使用空值）。"""
    assert audit.images, "页面没有图片，若确实无图请删除本测试"
    for image in audit.images:
        assert "alt" in image, f"<img src={image.get('src')}> 缺少 alt 属性"


def test_blank_targets_are_hardened(audit: HtmlAudit) -> None:
    """``target="_blank"`` 的外链必须带 noopener 与 noreferrer。"""
    for link in audit.links:
        if link.get("target") != "_blank":
            continue
        rel = set(link.get("rel", "").lower().split())
        assert {"noopener", "noreferrer"} <= rel, (
            f"外链缺少 rel 保护：{link.get('href')}"
        )


def test_in_page_anchors_resolve(audit: HtmlAudit) -> None:
    """站内锚点必须指向真实存在的元素，且不得使用 ``href="#"`` 占位。"""
    id_set = set(audit.ids)
    for link in audit.links:
        href = link.get("href", "")
        if not href.startswith("#"):
            continue
        assert href != "#", "存在占位链接 href=\"#\""
        assert href[1:] in id_set, f"锚点 {href} 没有对应元素"


def test_links_have_accessible_names(audit: HtmlAudit) -> None:
    """每个链接都要有可读文本或 aria-label。"""
    for tag, attrs, text in audit.texts:
        if tag != "a":
            continue
        assert text or attrs.get("aria-label"), (
            f"链接 {attrs.get('href')} 没有可访问名称"
        )


# --------------------------------------------------------------------------- #
# M6：表单可访问性
# --------------------------------------------------------------------------- #
def test_form_controls_have_labels(audit: HtmlAudit) -> None:
    """每个可输入的控件都必须通过 ``<label for>`` 关联。"""
    label_targets = {
        attrs.get("for")
        for tag, attrs, _text in audit.texts
        if tag == "label" and attrs.get("for")
    }
    assert audit.controls, "页面没有表单控件"
    for tag, control in audit.controls:
        if control.get("type", "").lower() in _NON_TEXT_INPUT_TYPES:
            continue
        control_id = control.get("id", "")
        assert control_id, f"<{tag}> 缺少 id，无法与 <label> 关联"
        assert control_id in label_targets, f"<{tag} id={control_id}> 没有对应的 <label for>"


def test_describedby_references_exist(audit: HtmlAudit) -> None:
    """控件的 aria-describedby 必须指向真实存在的元素。"""
    id_set = set(audit.ids)
    for tag, control in audit.controls:
        for token in control.get("aria-describedby", "").split():
            assert token in id_set, (
                f"<{tag} id={control.get('id')}> 的 aria-describedby 指向不存在的 id：{token}"
            )


# --------------------------------------------------------------------------- #
# M7：无内联样式与内联事件
# --------------------------------------------------------------------------- #
def test_no_inline_style_or_event_handlers(audit: HtmlAudit) -> None:
    """不得出现内联 ``style`` 属性与 ``on*`` 事件属性（便于启用 CSP）。"""
    assert not audit.style_attrs, f"存在内联 style 属性：{audit.style_attrs}"
    assert not audit.inline_events, f"存在内联事件属性：{audit.inline_events}"


def test_scripts_are_external_and_deferred(raw_html: str, audit: HtmlAudit) -> None:
    """脚本必须外置并以 defer/async 加载，不得内联执行。"""
    assert audit.scripts, "页面没有脚本"
    for script in audit.scripts:
        assert script.get("src"), "存在内联 <script>，应抽取为外部文件"
        assert "defer" in script or "async" in script, "外部脚本缺少 defer/async"
    assert not re.search(r"<script(?![^>]*\bsrc=)", raw_html, re.IGNORECASE)


# --------------------------------------------------------------------------- #
# M8 / M9：内容与结构异常
# --------------------------------------------------------------------------- #
def test_no_placeholder_content(raw_html: str) -> None:
    """不得残留占位文案、占位链接或测试域名。"""
    lowered = raw_html.lower()
    for token in _PLACEHOLDER_TOKENS:
        assert token not in lowered, f"发现占位内容：{token}"


def test_ids_are_unique(audit: HtmlAudit) -> None:
    """全文档 id 必须唯一，避免锚点与 ``label for`` 指向错误元素。"""
    duplicates = sorted({value for value in audit.ids if audit.ids.count(value) > 1})
    assert not duplicates, f"存在重复 id：{duplicates}"
