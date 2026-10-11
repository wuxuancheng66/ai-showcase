#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""班长竞选 PPT 生成器 — 吴宣澄 (2026)"""
import os
import argparse
from pathlib import Path
from PIL import Image, ImageDraw
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
from pptx.oxml.ns import qn

# ---------------- 设计系统 ----------------
PAPER   = "F8F6F1"   # 暖纸底
INK     = "1F2733"   # 深墨
BODY    = "4A5260"   # 正文灰
MUTED   = "8A919E"   # 弱化灰
GOLD    = "C29A3B"   # 金（主强调）
GOLD_D  = "A67F26"   # 深金
GOLD_L  = "E9DFC6"   # 浅金（幽灵数字）
LINE    = "E5DFD2"   # 分隔线
NAVY    = "22344A"   # 深蓝（资本板块）
TEAL    = "2E6E65"   # 青玉（辅助）
WHITE   = "FFFFFF"

FONT = "微软雅黑"
SW, SH = 13.333, 7.5
MX = 0.8                     # 左右边距
CW = SW - 2*MX               # 内容宽

MAT = os.path.expanduser("~/Desktop/班长竞选素材")
TMP = os.path.expanduser("~/Documents/dsh-workspace/tmp_ppt")
MASK = os.path.expanduser("~/Documents/dsh-workspace/masked")
ASSETS = os.path.expanduser("~/Documents/dsh-workspace/assets")
OUTPUT = os.path.expanduser("~/Desktop/班长竞选PPT.pptx")

prs = Presentation()
prs.slide_width  = Inches(SW)
prs.slide_height = Inches(SH)
BLANK = prs.slide_layouts[6]

def C(h): return RGBColor.from_string(h)

def new_slide(bg=PAPER):
    s = prs.slides.add_slide(BLANK)
    s.background.fill.solid()
    s.background.fill.fore_color.rgb = C(bg)
    return s

def _set_font(run, size, bold, color, italic=False, spc=None):
    f = run.font
    f.name = FONT
    f.size = Pt(size)
    f.bold = bold
    f.italic = italic
    f.color.rgb = C(color)
    rPr = run._r.get_or_add_rPr()
    for tag in ("a:ea", "a:cs"):
        e = rPr.find(qn(tag))
        if e is None:
            e = rPr.makeelement(qn(tag), {}); rPr.append(e)
        e.set("typeface", FONT)
    if spc is not None:
        rPr.set("spc", str(spc))

def tb(slide, x, y, w, h, anchor=MSO_ANCHOR.TOP):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = box.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    return tf

def para(tf, first=False):
    p = tf.paragraphs[0] if first else tf.add_paragraph()
    return p

def run(p, text, size=16, bold=False, color=BODY, italic=False, spc=None):
    r = p.add_run(); r.text = text
    _set_font(r, size, bold, color, italic, spc)
    return r

def rect(slide, x, y, w, h, fill, line=None, shape=MSO_SHAPE.RECTANGLE, radius=None, lw=0.75):
    sp = slide.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    if fill is None:
        sp.fill.background()
    else:
        sp.fill.solid(); sp.fill.fore_color.rgb = C(fill)
    if line is None:
        sp.line.fill.background()
    else:
        sp.line.color.rgb = C(line); sp.line.width = Pt(lw)
    sp.shadow.inherit = False
    if radius is not None and shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        try: sp.adjustments[0] = radius
        except Exception: pass
    return sp

# 顶部页眉（小标 + 主标题 + 金色短线）
def header(slide, eyebrow, title, accent=GOLD, tsize=32, sub=None):
    tf = tb(slide, MX, 0.5, CW, 1.9)
    p = para(tf, True); p.alignment = PP_ALIGN.LEFT
    run(p, eyebrow, 12.5, True, accent, spc=140)
    if title:
        p = para(tf); p.alignment = PP_ALIGN.LEFT; p.space_before = Pt(8)
        run(p, title, tsize, True, INK, spc=40)
    rect(slide, MX, 1.72, 0.62, 0.045, accent)
    if sub:
        tf2 = tb(slide, MX, 1.88, CW, 0.4)
        p2 = para(tf2, True)
        run(p2, sub, 13, False, MUTED)

def footer(slide, idx, total=16):
    tf = tb(slide, SW-1.4, SH-0.5, 0.9, 0.3, MSO_ANCHOR.BOTTOM)
    p = para(tf, True); p.alignment = PP_ALIGN.RIGHT
    run(p, f"{idx:02d} / {total}", 10, False, MUTED)

# ---------------- 图片预处理：裁剪为统一 3:4 ----------------
def prep_images(paths, key):
    out = []
    for i, p in enumerate(paths):
        im = Image.open(p).convert("RGB")
        w, h = im.size
        target_h = int(w * 4 / 3)          # 3:4 => h = w*4/3
        if h > target_h:
            # 太矮胖的竖图：顶部裁剪（保留顶部关键信息）
            im = im.crop((0, 0, w, target_h))
        elif h < target_h:
            # 偏方的图：上下居中（少量留白裁掉宽度）
            tw = int(h * 3 / 4)
            left = (w - tw) // 2
            im = im.crop((left, 0, left + tw, h))
        # 缩小到合理尺寸，控制体积
        im = im.resize((900, 1200), Image.LANCZOS)
        dst = os.path.join(TMP, f"{key}_{i}.jpg")
        im.save(dst, quality=88)
        out.append(dst)
    return out

def place_grid(slide, imgs, x, y, w, h, cols, rows, gap=0.18):
    cw = (w - (cols-1)*gap) / cols
    ch = cw * 4 / 3
    if rows*ch + (rows-1)*gap > h:
        ch = (h - (rows-1)*gap) / rows
        cw = ch * 3 / 4
    total_w = cols*cw + (cols-1)*gap
    total_h = rows*ch + (rows-1)*gap
    x0 = x + (w - total_w)/2
    y0 = y + (h - total_h)/2
    for i, im in enumerate(imgs):
        r, c = divmod(i, cols)
        px = x0 + c*(cw+gap); py = y0 + r*(ch+gap)
        slide.shapes.add_picture(im, Inches(px), Inches(py), Inches(cw), Inches(ch))

def stat_card(slide, x, y, w, h, big, big_color, label, label_color=BODY):
    rect(slide, x, y, w, h, WHITE, line=LINE, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.06)
    tf = tb(slide, x+0.1, y+0.16, w-0.2, h-0.32, MSO_ANCHOR.MIDDLE)
    p = para(tf, True); p.alignment = PP_ALIGN.CENTER
    run(p, big, 24, True, big_color)
    p = para(tf); p.alignment = PP_ALIGN.CENTER; p.space_before = Pt(4)
    run(p, label, 11.5, False, label_color)

# ============================================================
# S1 封面
# ============================================================
def s_cover():
    s = new_slide(INK)
    # 右侧金色装饰圆环
    ring = rect(s, 9.6, -2.6, 6.4, 6.4, None, line=GOLD, shape=MSO_SHAPE.OVAL)
    ring2 = rect(s, 10.6, -1.6, 4.4, 4.4, None, line=GOLD, shape=MSO_SHAPE.OVAL)
    # 金色细条
    rect(s, MX, 5.05, 1.1, 0.05, GOLD)
    tf = tb(s, MX, 2.15, 7.5, 2.7)
    p = para(tf, True)
    run(p, "2026 · 班级竞选", 14, True, GOLD, spc=150)
    p = para(tf); p.space_before = Pt(18)
    run(p, "竞选班长", 66, True, WHITE, spc=40)
    p = para(tf); p.space_before = Pt(14)
    run(p, "吴宣澄 · 数字公共治理专业", 18, False, "C7CDD6")
    tf = tb(s, MX, 5.4, 7.5, 0.8)
    p = para(tf, True)
    run(p, "态度 · 资本 · 承诺", 13, True, GOLD, spc=140)

# ============================================================
# S2 目录
# ============================================================
def s_toc():
    s = new_slide()
    header(s, "CONTENTS", "目录")
    items = [
        ("01", "态度", "关键词句 · 职责 · 素材例证", GOLD),
        ("02", "资本", "技能 · 十大工作流 · 团队优势", NAVY),
        ("03", "承诺", "五大承诺 · 说到做到", TEAL),
    ]
    cw = (CW - 2*0.35)/3
    for i, (num, t, d, ac) in enumerate(items):
        x = MX + i*(cw+0.35)
        y = 2.45
        rect(s, x, y, cw, 3.0, WHITE, line=LINE, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.05)
        tf = tb(s, x+0.3, y+0.32, cw-0.6, 2.4)
        p = para(tf, True)
        run(p, num, 40, True, ac)
        p = para(tf); p.space_before = Pt(8)
        run(p, t, 26, True, INK)
        p = para(tf); p.space_before = Pt(10)
        run(p, d, 12.5, False, MUTED)
        rect(s, x+0.3, y+2.6, 0.5, 0.045, ac)
    footer(s, 2)

# ============================================================
# S3 / S8 / S14 板块分隔页
# ============================================================
def s_divider(num, title, sub, en, accent, slide_no):
    s = new_slide()
    # 幽灵大数字
    tf = tb(s, SW-6.2, -0.9, 5.6, 3.6)
    p = para(tf, True); p.alignment = PP_ALIGN.RIGHT
    run(p, num, 210, True, "EFE9DB")
    tf = tb(s, MX, 2.9, 9.0, 2.0)
    p = para(tf, True)
    run(p, en, 13, True, accent, spc=150)
    p = para(tf); p.space_before = Pt(14)
    run(p, title, 58, True, INK, spc=40)
    p = para(tf); p.space_before = Pt(14)
    run(p, sub, 16, False, BODY)
    rect(s, MX, 4.85, 1.0, 0.05, accent)
    footer(s, slide_no)

# ============================================================
# S4 态度关键词
# ============================================================
def s_attitude():
    s = new_slide()
    header(s, "01 · 态度", "我的态度", tsize=34, sub="三个关键词，概括我做事的原则。")
    words = [
        ("注重整体", "把班级当成一个整体，凡事从全局出发，不搞小圈子、不偏不倚。"),
        ("服务集体", "把服务放在第一位，少计较个人得失，多为集体多想一步。"),
        ("关心个体", "关注每一位同学，一个都不能少，让每个人都被看见。"),
    ]
    cw = (CW - 2*0.35)/3
    for i, (t, d) in enumerate(words):
        x = MX + i*(cw+0.35)
        y = 2.55
        rect(s, x, y, cw, 3.5, WHITE, line=LINE, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.05)
        # 序号圆点
        dot = rect(s, x+0.35, y+0.4, 0.42, 0.42, GOLD, shape=MSO_SHAPE.OVAL)
        tfd = tb(s, x+0.35, y+0.4, 0.42, 0.42, MSO_ANCHOR.MIDDLE)
        pd = para(tfd, True); pd.alignment = PP_ALIGN.CENTER
        run(pd, str(i+1), 15, True, WHITE)
        tf = tb(s, x+0.35, y+1.05, cw-0.7, 2.2)
        p = para(tf, True)
        run(p, t, 23, True, INK)
        p = para(tf); p.space_before = Pt(12)
        run(p, d, 12.5, False, BODY)
        rect(s, x+0.35, y+3.02, 0.5, 0.045, GOLD)
    footer(s, 4)

# ============================================================
# S5 职责
# ============================================================
def s_duty():
    s = new_slide()
    header(s, "01 · 态度", "班长的职责", tsize=34, sub="四个词，说清班长要做什么。")
    duties = [
        ("服务", "为同学排忧解难，做大家最靠谱的后盾"),
        ("组织", "统筹班级事务，让每件事都有条不紊"),
        ("协调", "平衡各方诉求，让矛盾化解在萌芽"),
        ("沟通", "上下信息畅通，让老师同学无缝衔接"),
    ]
    cw = (CW - 3*0.35)/4
    for i, (t, d) in enumerate(duties):
        x = MX + i*(cw+0.35)
        y = 2.6
        rect(s, x, y, cw, 3.4, WHITE, line=LINE, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.06)
        tf = tb(s, x, y+0.5, cw, 0.9, MSO_ANCHOR.MIDDLE)
        p = para(tf, True); p.alignment = PP_ALIGN.CENTER
        run(p, t, 30, True, GOLD)
        rect(s, x+cw/2-0.25, y+1.55, 0.5, 0.045, GOLD)
        tf = tb(s, x+0.28, y+1.85, cw-0.56, 1.3, MSO_ANCHOR.TOP)
        p = para(tf, True); p.alignment = PP_ALIGN.CENTER
        run(p, d, 12.5, False, BODY)
    # 底部一句
    tf = tb(s, MX, 6.45, CW, 0.5, MSO_ANCHOR.MIDDLE)
    p = para(tf, True); p.alignment = PP_ALIGN.CENTER
    run(p, "服务 · 组织 · 协调 · 沟通 —— 这四个词，就是我对班长这份工作的理解。", 13.5, False, MUTED)
    footer(s, 5)

# ============================================================
# S6 素材例证 01 —— 手机工作使用时间
# ============================================================
def _evidence_header(s, eyebrow, title, stat_runs):
    tf = tb(s, MX, 0.45, CW, 1.05)
    p = para(tf, True)
    run(p, eyebrow, 12, True, GOLD, spc=140)
    p = para(tf); p.space_before = Pt(6)
    run(p, title, 28, True, INK, spc=40)
    rect(s, MX, 1.56, 0.55, 0.045, GOLD)
    tf = tb(s, MX, 1.68, CW, 0.4)
    p = para(tf, True)
    for txt, sz, bd, col in stat_runs:
        run(p, txt, sz, bd, col)

def s_evidence_time():
    s = new_slide()
    _evidence_header(s, "01 · 态度 · 素材例证", "用时间证明投入",
        [("军训期间连续记录 ", 13, False, BODY), ("19+ 天", 13.5, True, GOLD),
         ("  ·  日均 ", 13, False, BODY), ("10h+", 13.5, True, INK),
         (" 手机在线  ·  微信沟通 ", 13, False, BODY), ("6h+", 13.5, True, TEAL)])
    A = ["IMG_5582.jpg","IMG_5584.jpg","IMG_5586.jpg","IMG_5588.jpg","IMG_5590.jpg","IMG_5591.jpg",
         "IMG_5593.jpg","IMG_5595.jpg","IMG_5597.jpg","IMG_5599.jpg","IMG_5601.jpg","IMG_5602.jpg"]
    imgs = prep_images([os.path.join(MAT, f) for f in A], "time")
    place_grid(s, imgs, MX, 2.18, CW, 4.85, 6, 2, gap=0.14)
    footer(s, 6)

# ============================================================
# S7 素材例证 02 —— 消息传达 · 组织沟通
# ============================================================
def s_evidence_chat():
    s = new_slide()
    _evidence_header(s, "01 · 态度 · 素材例证", "用行动证明沟通",
        [("个体协调 · 班群通知 ", 13, False, BODY), ("事事有回应", 13.5, True, TEAL),
         ("  ·  消息传达 ", 13, False, BODY), ("条条有传达", 13.5, True, NAVY),
         ("  ·  组织沟通 ", 13, False, BODY), ("不断线", 13.5, True, GOLD)])
    # MASK 由命令行配置，旧路径仍作为默认值。
    B = [os.path.join(MASK,"masked_120.jpg"), os.path.join(MASK,"masked_121.jpg"),
         os.path.join(MASK,"masked_123.jpg"), os.path.join(MASK,"masked_124.jpg"),
         os.path.join(MAT,"IMG_5603.jpg"), os.path.join(MAT,"IMG_5604.jpg"),
         os.path.join(MAT,"IMG_5605.jpg"), os.path.join(MAT,"IMG_5607.jpg"),
         os.path.join(MAT,"IMG_5608.jpg"), os.path.join(MAT,"IMG_5610.jpg"),
         os.path.join(MAT,"IMG_5611.jpg"), os.path.join(MAT,"IMG_5612.jpg")]
    imgs = prep_images(B, "chat")
    place_grid(s, imgs, MX, 2.18, CW, 4.85, 6, 2, gap=0.14)
    footer(s, 7)

# ============================================================
# S9 技能01 Raft Agent Team
# ============================================================
def s_skill1():
    s = new_slide()
    header(s, "02 · 资本", "技能 01 · Raft 搭建 Agent Team", accent=NAVY, tsize=30)
    assets = ASSETS
    rw = 3.9
    L = CW - rw - 0.3
    tf = tb(s, MX, 2.4, L, 1.2)
    p = para(tf, True)
    run(p, "用 Raft 框架，搭建多智能体协作团队", 23, True, INK)
    p = para(tf); p.space_before = Pt(10)
    run(p, "让多个 AI 智能体各司其职、协同配合，自动完成复杂任务。", 14, False, BODY)
    feats = [
        ("规划 · 执行 · 审查", "多角色分工，各司其职"),
        ("自动拆解 · 编排", "复杂任务自动跑通全流程"),
        ("质量 · 效率兼得", "团队化产出，又快又好"),
    ]
    y = 3.7
    for t, d in feats:
        rect(s, MX, y, L, 0.95, WHITE, line=LINE, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.12)
        rect(s, MX+0.22, y+0.28, 0.09, 0.4, NAVY)
        tf = tb(s, MX+0.5, y+0.1, L-0.7, 0.75, MSO_ANCHOR.MIDDLE)
        p = para(tf, True)
        run(p, t, 14.5, True, NAVY)
        run(p, "　" + d, 12.5, False, BODY)
        y += 1.1
    rh = rw * 1050 / 900
    s.shapes.add_picture(os.path.join(assets, "raft_card.png"), Inches(MX+L+0.3), Inches(2.4), Inches(rw), Inches(rh))
    footer(s, 9)

# ============================================================
# S10 技能02 各大 Agent 平台
# ============================================================
def s_skill2():
    s = new_slide()
    header(s, "02 · 资本", "技能 02 · 熟练驾驭各大 Agent 平台", accent=NAVY, tsize=30)
    assets = ASSETS
    rw = 3.9
    L = CW - rw - 0.3
    tf = tb(s, MX, 2.4, L, 1.4)
    p = para(tf, True)
    run(p, "常用 AI 平台与工具", 23, True, INK)
    p = para(tf); p.space_before = Pt(8)
    run(p, "DeepSeek Harness · Z Code · Kimi K3 · codexGPT · Hermes · OpenClaw", 13.5, True, NAVY)
    p = para(tf); p.space_before = Pt(8)
    run(p, "熟练调用各大 AI 平台，处理班级事务的生产效率可达常人的数十倍。", 14, False, BODY)
    platforms = ["DeepSeek Harness", "Z Code", "Kimi K3", "codexGPT", "Hermes", "OpenClaw"]
    cols = 2
    cw = (L - 0.3)/cols
    for i, t in enumerate(platforms):
        r, c = divmod(i, cols)
        x = MX + c*(cw+0.3); y = 3.85 + r*0.95
        rect(s, x, y, cw, 0.8, WHITE, line=LINE, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.14)
        tf = tb(s, x, y, cw, 0.8, MSO_ANCHOR.MIDDLE)
        p = para(tf, True); p.alignment = PP_ALIGN.CENTER
        run(p, t, 14.5, True, INK)
    tf = tb(s, MX, 6.72, L, 0.5, MSO_ANCHOR.MIDDLE)
    p = para(tf, True)
    run(p, "可应用于信息整理、通知传达、活动组织等日常班务。", 13, False, MUTED)
    rh = rw * 1050 / 900
    s.shapes.add_picture(os.path.join(assets, "dsh_card.png"), Inches(MX+L+0.3), Inches(2.4), Inches(rw), Inches(rh))
    footer(s, 10)

# ============================================================
# S11/S12 技能03 十大工作流
# ============================================================
FLOWS = [
    ("通知台账助手", "杂乱通知自动整理成台账，事项、截止、负责人一目了然，绝不漏事。"),
    ("群公告生成器", "长通知一键变三行友好公告，重点标红、行动项清晰。"),
    ("材料收集统计器", "接龙问卷自动汇总名单，谁交了、谁没交、催交话术一并备好。"),
    ("考勤汇总助手", "每日点名自动生成周报月报，缺勤异常名单自动标出。"),
    ("班级活动策划官", "给主题和预算，自动产出完整策划案：流程、分工、物资、预案。"),
    ("班务周报生成器", "一周台账加大事记，自动生成周日周报，一键发群。"),
    ("沟通话术顾问", "催材料、批假、调解、拒请求，给出得体有效的分层话术。"),
    ("评优公示与班务总结", "原始记录自动生成公示与学期总结，规则公开、过程留痕。"),
    ("排期与提醒管家", "所有截止时间自动排进日历，提前提醒，再也不会忘。"),
    ("竞选复盘与素材库", "做过的事自动沉淀为复盘与竞选数据，每一份付出有据可查。"),
]

def _flow_slide(flows, idx, slide_no):
    s = new_slide()
    if idx == 0:
        header(s, "02 · 资本", "技能 03 · 班长十大工作流", accent=NAVY, tsize=30,
               sub="把班长的日常工作，拆成十条 AI 工作流，随取随用，高效运转。")
    else:
        header(s, "02 · 资本", "班长十大工作流（续）", accent=NAVY, tsize=30)
    assets = ASSETS
    if idx == 0:
        rw = 3.9
        L = CW - rw - 0.3
        ch = 0.82
        gapy = 0.08
        y0 = 2.42
        for i, (t, d) in enumerate(flows):
            y = y0 + i*(ch+gapy)
            rect(s, MX, y, L, ch, WHITE, line=LINE, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.12)
            rect(s, MX+0.18, y+0.19, 0.44, 0.44, NAVY, shape=MSO_SHAPE.OVAL)
            tf = tb(s, MX+0.18, y+0.19, 0.44, 0.44, MSO_ANCHOR.MIDDLE)
            p = para(tf, True); p.alignment = PP_ALIGN.CENTER
            run(p, str(idx*5 + i + 1), 12.5, True, WHITE)
            tf = tb(s, MX+0.78, y+0.05, L-0.95, ch-0.1, MSO_ANCHOR.MIDDLE)
            p = para(tf, True)
            run(p, t, 13.5, True, INK)
            run(p, "　" + d, 11, False, BODY)
        rh = rw * 1050 / 900
        s.shapes.add_picture(os.path.join(assets, "codex_card.png"), Inches(MX+L+0.3), Inches(2.42), Inches(rw), Inches(rh))
    else:
        cw = CW
        ch = 0.8
        gapy = 0.1
        y0 = 2.44
        for i, (t, d) in enumerate(flows):
            y = y0 + i*(ch+gapy)
            rect(s, MX, y, cw, ch, WHITE, line=LINE, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.12)
            rect(s, MX+0.2, y+0.17, 0.46, 0.46, NAVY, shape=MSO_SHAPE.OVAL)
            tf = tb(s, MX+0.2, y+0.17, 0.46, 0.46, MSO_ANCHOR.MIDDLE)
            p = para(tf, True); p.alignment = PP_ALIGN.CENTER
            run(p, str(idx*5 + i + 1), 13, True, WHITE)
            tf = tb(s, MX+0.84, y+0.06, cw-1.05, ch-0.12, MSO_ANCHOR.MIDDLE)
            p = para(tf, True)
            run(p, t, 14.5, True, INK)
            run(p, "　" + d, 12, False, BODY)
    footer(s, slide_no)

# ============================================================
# S13 小结
# ============================================================
def s_summary():
    s = new_slide(INK)
    rect(s, MX, 2.15, 0.9, 0.05, GOLD)
    tf = tb(s, MX, 1.4, CW, 0.5)
    p = para(tf, True)
    run(p, "02 · 资本 · 小结", 13, True, GOLD, spc=140)
    tf = tb(s, MX, 2.45, CW, 2.6)
    p = para(tf, True)
    run(p, "选我当班长，", 40, True, WHITE)
    p = para(tf); p.space_before = Pt(6)
    run(p, "不再是一个人在为你们服务，", 40, True, WHITE)
    p = para(tf); p.space_before = Pt(6)
    run(p, "而是一个", 40, True, WHITE)
    run(p, " 高效的专业团队 ", 40, True, GOLD)
    run(p, "在为你们服务。", 40, True, WHITE)
    tf = tb(s, MX, 5.6, CW, 0.8)
    p = para(tf, True)
    run(p, "这个「团队」，就是前两页的十项 AI 工作流。", 15, False, "C7CDD6")
    footer(s, 13)

# ============================================================
# S15 承诺
# ============================================================
def s_promise():
    s = new_slide()
    header(s, "03 · 承诺", "我的五大承诺", accent=TEAL, tsize=34, sub="说到做到，用结果说话。")
    promises = [
        ("组建班委群", "当选后立即组建正式班委群，明确各班委分工与工作协调。"),
        ("信息传达", "信息传达力求准确、及时、完整，不让任何一位同学掉队。"),
        ("民主决策", "重大活动在合适情况下，多用群投票、问卷星等方式征集大家意见。"),
        ("班级活动", "在不影响学习作息的前提下，积极举办有意义的班级活动。"),
        ("每周总结", "每周日发布一次本周总结与下周规划，让班级运行透明有序。"),
    ]
    n = len(promises)
    cw = CW
    ch = 0.8
    gapy = 0.14
    y0 = 2.45
    for i, (t, d) in enumerate(promises):
        y = y0 + i*(ch+gapy)
        rect(s, MX, y, cw, ch, WHITE, line=LINE, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.1)
        rect(s, MX+0.22, y+0.22, 0.44, 0.44, TEAL, shape=MSO_SHAPE.OVAL)
        tf = tb(s, MX+0.22, y+0.22, 0.44, 0.44, MSO_ANCHOR.MIDDLE)
        p = para(tf, True); p.alignment = PP_ALIGN.CENTER
        run(p, str(i+1), 14, True, WHITE)
        tf = tb(s, MX+0.9, y+0.12, cw-1.15, ch-0.24, MSO_ANCHOR.MIDDLE)
        p = para(tf, True)
        run(p, t, 15.5, True, INK)
        run(p, "　" + d, 13, False, BODY)
    footer(s, 15)

# ============================================================
# S16 结尾
# ============================================================
def s_end():
    s = new_slide(INK)
    ring = rect(s, -2.2, -2.6, 6.0, 6.0, None, line=GOLD, shape=MSO_SHAPE.OVAL)
    ring2 = rect(s, -1.2, -1.6, 4.0, 4.0, None, line=GOLD, shape=MSO_SHAPE.OVAL)
    tf = tb(s, MX, 2.5, CW, 2.6)
    p = para(tf, True); p.alignment = PP_ALIGN.CENTER
    run(p, "谢谢聆听", 56, True, WHITE, spc=40)
    p = para(tf); p.space_before = Pt(16); p.alignment = PP_ALIGN.CENTER
    run(p, "请投我一票", 26, True, GOLD, spc=60)
    p = para(tf); p.space_before = Pt(18); p.alignment = PP_ALIGN.CENTER
    run(p, "吴宣澄 · 数字公共治理专业 · 2026", 14, False, "C7CDD6")
    rect(s, SW/2-0.55, 5.4, 1.1, 0.05, GOLD)

# ============================================================
def build():
    global prs, BLANK
    prs = Presentation()
    prs.slide_width = Inches(SW)
    prs.slide_height = Inches(SH)
    BLANK = prs.slide_layouts[6]
    os.makedirs(TMP, exist_ok=True)
    s_cover()
    s_toc()
    # 态度
    s_divider("01", "态度", "态度与职责", "ATTITUDE", GOLD, 3)
    s_attitude()
    s_duty()
    s_evidence_time()
    s_evidence_chat()
    # 资本
    s_divider("02", "资本", "能力与优势", "CAPITAL", NAVY, 8)
    s_skill1()
    s_skill2()
    _flow_slide(FLOWS[:5], 0, 11)
    _flow_slide(FLOWS[5:], 1, 12)
    s_summary()
    # 承诺
    s_divider("03", "承诺", "说到做到", "PROMISE", TEAL, 14)
    s_promise()
    s_end()

    out = OUTPUT
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    prs.save(out)
    print("SAVED:", out, "slides:", len(prs.slides._sldIdLst))

MATERIAL_NAMES = ["IMG_5582.jpg","IMG_5584.jpg","IMG_5586.jpg","IMG_5588.jpg","IMG_5590.jpg","IMG_5591.jpg","IMG_5593.jpg","IMG_5595.jpg","IMG_5597.jpg","IMG_5599.jpg","IMG_5601.jpg","IMG_5602.jpg","IMG_5603.jpg","IMG_5604.jpg","IMG_5605.jpg","IMG_5607.jpg","IMG_5608.jpg","IMG_5610.jpg","IMG_5611.jpg","IMG_5612.jpg"]
MASKED_NAMES = ["masked_120.jpg","masked_121.jpg","masked_123.jpg","masked_124.jpg"]
ASSET_NAMES = ["raft_card.png","dsh_card.png","codex_card.png"]


def required_inputs():
    return [Path(MAT)/n for n in MATERIAL_NAMES] + [Path(MASK)/n for n in MASKED_NAMES] + [Path(ASSETS)/n for n in ASSET_NAMES]


def prepare_demo():
    global MAT, MASK, ASSETS
    root=Path(TMP)/"demo-inputs"
    MAT=str(root/"materials");MASK=str(root/"masked");ASSETS=str(root/"assets")
    for i,p in enumerate(required_inputs(),1):
        p.parent.mkdir(parents=True,exist_ok=True)
        image=Image.new("RGB",(600,800) if p.suffix==".jpg" else (900,600),"#22344a")
        draw=ImageDraw.Draw(image)
        draw.rectangle((30,30,image.width-30,image.height-30),outline="#c29a3b",width=4)
        draw.text((55,80),"DEMO / IMAGE "+str(i),fill="#f8f6f1",font_size=28)
        draw.text((55,130),"Generated placeholder - no private photos",fill="#c7cdd6",font_size=18)
        image.save(p)


def main():
    global MAT, MASK, ASSETS, TMP, OUTPUT, FONT
    parser=argparse.ArgumentParser(description="16页竞选演示模板生成器；可使用私人素材或无需素材的演示模式")
    parser.add_argument("--materials",default=MAT,help="20张 IMG_*.jpg 素材目录，默认沿用原本本机位置")
    parser.add_argument("--masked",default=MASK,help="4张已脱敏截图目录")
    parser.add_argument("--assets",default=ASSETS,help="raft_card/dsh_card/codex_card 图片目录")
    parser.add_argument("--work-dir",default=str(Path.cwd()/"build-assets"),help="图片处理工作目录")
    parser.add_argument("--output",default=None,help="输出PPTX路径；演示默认当前目录demo.pptx，普通默认原Desktop位置")
    parser.add_argument("--font",default=FONT,help="字体名称，应选目标设备已安装字体")
    parser.add_argument("--demo",action="store_true",help="使用生成的占位图，不读取私人素材")
    parser.add_argument("--check",action="store_true",help="只检查素材是否齐全，不生成PPT")
    args=parser.parse_args()
    MAT=str(Path(args.materials).expanduser());MASK=str(Path(args.masked).expanduser());ASSETS=str(Path(args.assets).expanduser())
    TMP=str(Path(args.work_dir).expanduser());FONT=args.font
    OUTPUT=str(Path(args.output).expanduser()) if args.output else (str(Path.cwd()/"demo.pptx") if args.demo else OUTPUT)
    if args.demo and not args.check:
        prepare_demo()
    missing=[p.name for p in required_inputs() if not p.is_file()]
    if args.check and args.demo:
        print("演示模式会自动生成占位图，无需私人素材。")
        return 0
    if missing:
        parser.error("缺少素材："+", ".join(missing)+"。可配置素材路径，或使用 --demo。")
    if args.check:
        print("素材齐全，共 "+str(len(required_inputs()))+" 个文件。")
        return 0
    build()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
