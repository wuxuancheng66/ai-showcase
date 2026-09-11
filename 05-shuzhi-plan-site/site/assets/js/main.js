/* =========================================================
   数智治途 · 全站脚本 main.js（v3）
   - 导航注入 / 主题 / 折叠 / 标签页 / 打卡(localStorage) / 思维导图
   - 课程地图 / 全站搜索(⌘K) / 绩点计算器 / 课程路线图 / 进度仪表盘
   - 路由无关：多页面版与单文件版共用本脚本（ZST_SINGLE）
   ========================================================= */
(function () {
  "use strict";

  /* ---------- 课程快速索引（供全站搜索） ---------- */
var COURSE_QUICK = [
    { n: "大学英语", c: "FL1199" },
    { n: "习近平新时代中国特色社会主义思想概论", c: "MAR123" },
    { n: "体育", c: "PE101" },
    { n: "军事课", c: "PUB121" },
    { n: "心理健康教育（上）", c: "PUB1601" },
    { n: "国家安全教育", c: "PUB1991" },
    { n: "新时代实践教育 2（形势与政策）", c: "MAR126" },
    { n: "劳动教育", c: "PUB178" },
    { n: "人工智能导论（人文社科）", c: "DCS1013" },
    { n: "英语学术交流", c: "FL1200" },
    { n: "大学生思想文化素养", c: "MAR124" },
    { n: "新时代实践教育 1（走在前列的广东实践）", c: "MAR125" },
    { n: "四史", c: "MAR130" },
    { n: "体育", c: "PE102" },
    { n: "心理健康教育（下）", c: "PUB1602" },
    { n: "马克思主义基本原理", c: "MAR228" },
    { n: "体育", c: "PE201" },
    { n: "中国共产党历史与理论", c: "MAR229" },
    { n: "体育", c: "PE202" },
    { n: "体育", c: "PE305" },
    { n: "体育", c: "PE302" },
    { n: "艺术与审美课", c: "" },
    { n: "经济学基础", c: "GOV105" },
    { n: "理解数字时代：智能体与公共管理", c: "GOV131" },
    { n: "宪法与行政法", c: "GOV106" },
    { n: "社会科学研究方法", c: "GOV108" },
    { n: "数字治理概论", c: "GOV1501" },
    { n: "Python基础与数据分析", c: "GOV161" },
    { n: "数字治理与伦理", c: "GOV2104" },
    { n: "行政组织学", c: "GOV247" },
    { n: "智慧城市管理", c: "GOV2501" },
    { n: "社会科学与人工智能治理", c: "GOV2502" },
    { n: "计量统计与分析", c: "GOV2330" },
    { n: "公共部门人力资源管理", c: "GOV246" },
    { n: "公共政策导论", c: "GOV249" },
    { n: "人工智能原理", c: "GOV2601" },
    { n: "AI+数字治理", c: "GOV3019" },
    { n: "公共预算学", c: "GOV349" },
    { n: "数字平台与政府规制", c: "GOV3500" },
    { n: "公共管理大数据分析", c: "GOV3502" },
    { n: "数字经济", c: "GOV3503" },
    { n: "数据可视化与空间分析", c: "GOV3501" },
    { n: "计算社会科学", c: "GOV3504" },
    { n: "科研与创新训练", c: "GOV3002" },
    { n: "专业实习", c: "GOV463" },
    { n: "毕业论文", c: "GOV494" },
    { n: "政治学原理", c: "GOV101" },
    { n: "行政管理学", c: "GOV103" },
    { n: "高等数学三（I）", c: "MA193" },
    { n: "中国政府与政治", c: "GOV104" },
    { n: "高等数学三（II）", c: "MA194" },
    { n: "概率统计（经管类）", c: "MA183" },
    { n: "数字战略管理", c: "GOV2508" },
    { n: "制度经济学", c: "GOV272" },
    { n: "公共财务管理", c: "GOV259" },
    { n: "区域科技创新", c: "GOV3001" },
    { n: "数字时代的社会组织管理", c: "GOV3025" },
    { n: "数字化协同治理", c: "GOV3505" },
    { n: "廉政与治理", c: "GOV388" },
    { n: "公共财政与税收", c: "GOV3009" },
    { n: "福利国家政治经济学", c: "GOV352" },
    { n: "政治社会学", c: "GOV364" },
    { n: "国家发展", c: "GOV445" },
    { n: "社会政策导论", c: "GOV248" },
    { n: "卫生经济与政策", c: "GOV437" },
    { n: "应急管理", c: "GOV281" },
    { n: "认知科学与公共政策", c: "GOV3007" },
    { n: "住房政策", c: "GOV317" },
    { n: "教育政策", c: "GOV321" },
    { n: "公共政策评估", c: "GOV3507" },
    { n: "比较社会政策", c: "GOV353" },
    { n: "养老政策", c: "GOV354" },
    { n: "劳工政策", c: "GOV319" },
    { n: "科技政策", c: "GOV348" },
    { n: "数据预测与决策模拟", c: "GOV3506" },
    { n: "家庭政策", c: "GOV382" },
    { n: "城市分析学", c: "GOV2510" },
    { n: "土地资源管理", c: "GOV327" },
    { n: "社会福利服务", c: "GOV323" },
    { n: "智能交通治理导论", c: "GOV3509" },
    { n: "比较城市治理", c: "GOV355" },
    { n: "城市规划", c: "GOV325" },
    { n: "中国社会转型与国家治理", c: "GOV350" },
    { n: "智慧社区治理", c: "GOV3508" },
    { n: "数字化时代下的城市公用事业发展", c: "GOV3510" },
    { n: "城市与房地产经济", c: "GOV392" },
    { n: "区域公共管理", c: "GOV419" },
    { n: "中国社保制度改革", c: "GOV398" },
    { n: "公共管理经典与前沿", c: "GOV5217" },
    { n: "政治理论专题研究", c: "GOV5222" },
    { n: "伦理分析与公共政策", c: "GOV6734" },
    { n: "高级统计", c: "GOV5114" },
    { n: "高级政策分析", c: "GOV6749" },
    { n: "田野调查方法", c: "SA123" },
    { n: "传播数据分析基础", c: "CD256" },
    { n: "博弈论", c: "GOV287" },
    { n: "科研训练与创新实践", c: "GOV3017" },
    { n: "实验公共管理", c: "GOV3550" },
    { n: "数据库原理及应用（含实验）", c: "GP2185" }
  ];

  /* ---------- 页面索引 ---------- */
  var PAGE_INDEX = [
    ["首页", "index.html", "数智治途 · 大学规划站", "🏠", "总览 欢迎 个人档案"],
    ["四年路线图与思维导图", "guihua-daxue.html", "宏观规划 · 大一至大四主线", "🗺️", "里程碑 时间轴 路线"],
    ["专业深度解读", "zhuanye-jiedu.html", "培养方案 11 条毕业要求解读", "📖", "培养方案 毕业要求 课程体系 培养路径"],
    ["学分与选课政策", "xuefen-zhengce.html", "145.5 学分拆解 · 绩点计算器", "🧮", "学分 绩点 GPA 计算器 选课 综测 奖学金"],
    ["大一选课清单", "xuanke-dayi.html", "大一选修课清单 · 口碑情报 · 学期安排", "🎯", "选课 公选 水课 艺术 体育 习概 田野调查 口碑"],
    ["课程地图 · 99 门课", "kecheng-ditu.html", "按类别/模块/学年筛选搜索", "🗂️", "课程 课表 专业核心 通识 选修 模块"],
    ["大一行动手册", "xingdong-dayi.html", "2026.9–2027.7 逐月行动", "1️⃣", "四级 六级 英语 军训 班委 入团 高数 Python 大一"],
    ["大二行动手册", "xingdong-daer.html", "2027.9–2028.7 逐月行动", "2️⃣", "六级 雅思 科研 大创 竞赛 大二"],
    ["大三行动手册", "xingdong-dasan.html", "2028.9–2029.7 逐月行动", "3️⃣", "夏令营 保研资格 荣誉 科研训练 大三"],
    ["大四行动手册", "xingdong-dasi.html", "2029.9–2030.6 逐月行动", "4️⃣", "毕业论文 专业实习 行测 申论 本研贯通 大四"],
    ["入团 · 青马 · 入党", "mubiao-ruzheng.html", "党团目标专区", "🚩", "入团 青马 入党 积极分子 思想汇报 党团"],
    ["竞选班长", "mubiao-banzhang.html", "班委目标专区", "👨‍🏫", "班长 班委 竞选 学生干部 辅导员"],
    ["保研之路", "mubiao-baoyan.html", "推免全流程 · 绩点策略", "🎓", "推免 保研 夏令营 九推 绩点排名 加分"],
    ["荣誉学士学位", "mubiao-rongyu.html", "18 学分荣誉课 · 绩点 3.5", "🏅", "荣誉学士 荣誉课程 本研贯通 18学分"],
    ["中央选调（研究生主攻）", "mubiao-diaoxuan.html", "本科练手 · 研究生主攻", "🏛️", "选调 央选 公务员 国考 行测 申论"],
    ["资源推荐", "ziyuan-tuijian.html", "编程/AI/治理/教材/竞赛", "📚", "资源 工具 教材 网站 公众号 Python AI"],
    ["专业知识库", "zhishi-kuku.html", "核心概念 · 理论 · 方法", "🧠", "数字政府 数据治理 算法治理 智慧城市 概念"],
    ["竞赛与科研", "jingsai-keyan.html", "竞赛日历 · 科研路线", "🔬", "竞赛 挑战杯 大创 科研 课题组 调研"],
    ["AI 工具箱", "gongju-xiang.html", "提示词 · 学习工作流", "🤖", "AI 提示词 ChatGPT DeepSeek 学习"],
    ["里程碑与复盘", "fupan-licheng.html", "四年里程碑 · 复盘模板", "📊", "复盘 里程碑 进度 目标管理 月度"],
    ["关于本站", "guanyu.html", "使用指南 · 资料来源", "ℹ️", "关于 使用指南 帮助 免责"]
  ];

  /* ---------- 导航配置（唯一） ---------- */
  var NAV = [
    { sec: "起步", items: [
      { file: "index.html", label: "首页", ico: "🏠" }
    ]},
    { sec: "宏观规划", items: [
      { file: "guihua-daxue.html", label: "四年路线图与思维导图", ico: "🗺️" }
    ]},
    { sec: "专业与课程", items: [
      { file: "zhuanye-jiedu.html", label: "专业深度解读", ico: "📖" },
      { file: "xuefen-zhengce.html", label: "学分与选课政策", ico: "🧮" },
      { file: "xuanke-dayi.html", label: "大一选课清单", ico: "🎯" },
      { file: "kecheng-ditu.html", label: "课程地图 · 99门课", ico: "🗂️" }
    ]},
    { sec: "行动手册", items: [
      { file: "xingdong-dayi.html", label: "大一行动手册", ico: "1️⃣" },
      { file: "xingdong-daer.html", label: "大二行动手册", ico: "2️⃣" },
      { file: "xingdong-dasan.html", label: "大三行动手册", ico: "3️⃣" },
      { file: "xingdong-dasi.html", label: "大四行动手册", ico: "4️⃣" }
    ]},
    { sec: "目标专区", items: [
      { file: "mubiao-ruzheng.html", label: "入团 · 青马 · 入党", ico: "🚩" },
      { file: "mubiao-banzhang.html", label: "竞选班长", ico: "👨‍🏫" },
      { file: "mubiao-baoyan.html", label: "保研之路", ico: "🎓" },
      { file: "mubiao-rongyu.html", label: "荣誉学士学位", ico: "🏅" },
      { file: "mubiao-diaoxuan.html", label: "中央选调（研究生主攻）", ico: "🏛️" }
    ]},
    { sec: "资源与工具", items: [
      { file: "ziyuan-tuijian.html", label: "资源推荐", ico: "📚" },
      { file: "zhishi-kuku.html", label: "专业知识库", ico: "🧠" },
      { file: "jingsai-keyan.html", label: "竞赛与科研", ico: "🔬" },
      { file: "gongju-xiang.html", label: "AI 工具箱", ico: "🤖" }
    ]},
    { sec: "复盘与关于", items: [
      { file: "fupan-licheng.html", label: "里程碑与复盘", ico: "📊" },
      { file: "guanyu.html", label: "关于本站", ico: "ℹ️" }
    ]}
  ];


  /* ---------- 注入侧边导航（路由无关） ---------- */
  function buildNav() {
    var navEl = document.getElementById("site-nav");
    if (!navEl) return;
    var html = '<a class="nav-item search-trigger" href="#" data-search-trigger style="margin-bottom:6px"><span class="ico">🔍</span>全站搜索<span style="margin-left:auto;font-size:.7em;color:var(--ink-faint)">⌘K</span></a>';
    NAV.forEach(function (group) {
      html += '<div class="nav-sec">' + group.sec + "</div>";
      group.items.forEach(function (p) {
        var active = document.body.getAttribute("data-page") === p.file ? " active" : "";
        var href = (window.ZST_SINGLE ? "#" : "") + p.file;
        html += '<a class="nav-item' + active + '" href="' + href + '" data-file="' + p.file + '"><span class="ico">' + p.ico + "</span>" + p.label + "</a>";
      });
    });
    navEl.innerHTML = html;
    // 单文件版：拦截站内 .html 链接
    if (window.ZST_SINGLE) {
      document.addEventListener("click", function (e) {
        var a = e.target.closest("a[href]");
        if (!a) return;
        var h = a.getAttribute("href") || "";
        if (h.indexOf(".html") > 0 && h.charAt(0) !== "#") {
          e.preventDefault();
          window.ZST_SHOW(h);
        }
      });
    }
  }


  /* ---------- 移动端侧栏 ---------- */
  function setupMobileSidebar() {
    var sidebar = document.querySelector(".sidebar");
    var btn = document.getElementById("menuBtn");
    if (!sidebar || !btn) return;
    btn.addEventListener("click", function () { sidebar.classList.toggle("open"); });
    sidebar.addEventListener("click", function (e) {
      if (e.target.closest(".nav-item")) sidebar.classList.remove("open");
    });
  }

  /* ---------- 主题切换 ---------- */
  function setupTheme() {
    var btn = document.getElementById("themeBtn");
    if (!btn) return;
    var saved = localStorage.getItem("zst_theme");
    if (saved) document.documentElement.setAttribute("data-theme", saved);
    btn.textContent = document.documentElement.getAttribute("data-theme") === "dark" ? "☀️" : "🌙";
    btn.addEventListener("click", function () {
      var cur = document.documentElement.getAttribute("data-theme");
      var next = cur === "dark" ? "light" : "dark";
      document.documentElement.setAttribute("data-theme", next);
      localStorage.setItem("zst_theme", next);
      btn.textContent = next === "dark" ? "☀️" : "🌙";
    });
  }

  /* ---------- 返回顶部 ---------- */
  function setupBackTop() {
    var btn = document.getElementById("backTop");
    if (!btn) return;
    window.addEventListener("scroll", function () {
      btn.style.display = window.scrollY > 400 ? "block" : "none";
    });
    btn.addEventListener("click", function () { window.scrollTo({ top: 0, behavior: "smooth" }); });
  }

  /* ---------- 折叠面板 ---------- */
  function setupAccordion() {
    document.querySelectorAll(".accordion").forEach(function (acc) {
      var head = acc.querySelector(".acc-head");
      if (!head) return;
      if (acc.classList.contains("open")) acc.querySelector(".acc-body").style.display = "block";
      head.addEventListener("click", function () {
        acc.classList.toggle("open");
        var body = acc.querySelector(".acc-body");
        body.style.display = acc.classList.contains("open") ? "block" : "none";
      });
    });
  }

  /* ---------- 标签页 ---------- */
  function setupTabs() {
    document.querySelectorAll(".tabs").forEach(function (tabs) {
      var btns = tabs.querySelectorAll(".tab-btn");
      var panels = tabs.querySelectorAll(".tab-panel");
      btns.forEach(function (b, i) {
        b.addEventListener("click", function () {
          btns.forEach(function (x) { x.classList.remove("active"); });
          panels.forEach(function (x) { x.classList.remove("active"); });
          b.classList.add("active");
          if (panels[i]) panels[i].classList.add("active");
        });
      });
    });
  }

  /* ---------- 打卡清单（localStorage + 进度元数据） ---------- */
  function setupChecklist() {
    document.querySelectorAll(".checklist").forEach(function (list) {
      var dk = list.getAttribute("data-key") || "";
      var key = "zst_cl_" + dk;
      function syncMeta() {
        if (!dk) return;
        var total = list.querySelectorAll("input[type=checkbox]").length;
        var done = list.querySelectorAll("input[type=checkbox]:checked").length;
        localStorage.setItem("zst_meta_" + dk + "_total", total);
        localStorage.setItem("zst_meta_" + dk + "_done", done);
      }
      list.querySelectorAll("input[type=checkbox]").forEach(function (cb) {
        var saved = localStorage.getItem(key + "_" + cb.value);
        if (saved === "1") { cb.checked = true; cb.closest("li").classList.add("done"); }
        cb.addEventListener("change", function () {
          if (cb.checked) { cb.closest("li").classList.add("done"); localStorage.setItem(key + "_" + cb.value, "1"); }
          else { cb.closest("li").classList.remove("done"); localStorage.removeItem(key + "_" + cb.value); }
          updateProgress(list);
          syncMeta();
        });
      });
      updateProgress(list);
      syncMeta();
    });
  }
  function updateProgress(list) {
    var bar = list.parentElement.querySelector(".progress > div");
    var lbl = list.parentElement.querySelector(".progress-label span:last-child");
    var cbs = list.querySelectorAll("input[type=checkbox]");
    var done = list.querySelectorAll("input[type=checkbox]:checked").length;
    if (bar && cbs.length) bar.style.width = Math.round(done / cbs.length * 100) + "%";
    if (lbl) lbl.textContent = done + "/" + cbs.length;
  }

  /* ---------- 思维导图折叠 ---------- */
  function setupMindmap() {
    document.querySelectorAll(".mindmap .mm-node").forEach(function (node) {
      node.addEventListener("click", function (e) {
        e.stopPropagation();
        var li = node.closest("li");
        if (li) {
          li.classList.toggle("collapsed");
          var t = node.querySelector(".mm-toggle");
          if (t) t.textContent = li.classList.contains("collapsed") ? "▶" : "▼";
        }
      });
    });
  }

  /* ---------- 课程地图（kecheng-ditu.html） ---------- */
  function setupCourseMap() {
    var container = document.getElementById("courseList");
    if (!container) return;
    var data = (window.COURSES || []).slice();
    var chips = document.querySelectorAll(".filter-chip");
    var search = document.getElementById("courseSearch");
    var curFilter = "all";
    try {
      var qs = new URLSearchParams(window.location.search).get("q");
      if (qs && search) search.value = qs;
    } catch (e) {}

    function groupLabel(section) {
      if (section.indexOf("1.1") === 0) return "公共必修课";
      if (section.indexOf("1.2") === 0) return "学分必修";
      if (section.indexOf("2.1") === 0) return "专业核心课";
      if (section.indexOf("2.2") === 0) return "实践课";
      if (section.indexOf("2.3") === 0 && !data[0]) return "通识/选修";
      if (section.indexOf("2.3.1") === 0) return "通识平台课";
      if (section.indexOf("2.3.2") === 0) return "专业选修课";
      return section;
    }

    function render() {
      var q = search ? search.value.trim().toLowerCase() : "";
      var list = data.filter(function (c) {
        if (curFilter === "通识平台课") {
          if (!(c.section === "2.3 通识课" && !c.module)) return false;
        } else if (curFilter !== "all" && c.module !== curFilter && c.section !== curFilter && groupLabel(c.section) !== curFilter && c.semester !== curFilter) return false;
        if (q && !(c.name.toLowerCase().indexOf(q) >= 0 || (c.code || "").toLowerCase().indexOf(q) >= 0 || (c.teacher || "").toLowerCase().indexOf(q) >= 0)) return false;
        return true;
      });
      var html = "";
      list.forEach(function (c) {
        var badge = c.module ? c.module.replace(/^2\.3\.2\.\d\s*/, "").replace(/模块$/, "") : groupLabel(c.section);
        var badgeCls = c.section.indexOf("2.3.2") === 0 ? "blue" : c.section.indexOf("2.1") === 0 ? "green" : c.section.indexOf("1.1") === 0 ? "gray" : c.section.indexOf("2.2") === 0 ? "amber" : "green";
        html += '<div class="card" style="margin-bottom:12px">';
        html += '<div style="display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap;align-items:center">';
        html += '<div><strong>' + c.name + '</strong> <span class="badge ' + badgeCls + '">' + badge + "</span></div>";
        html += '<div style="font-size:.85em;color:var(--muted)">' + (c.code || "") + " · " + c.credits + "学分 · " + c.semester + "</div></div>";
        html += '<div style="font-size:.85em;color:var(--muted);margin-top:6px">负责人：' + (c.teacher || "—") + " ｜ 学时：" + (c.hours || "—") + "</div>";
        html += "</div>";
      });
      container.innerHTML = html || '<div class="callout info">没有找到匹配的课程，换个关键词试试～</div>';
    }

    chips.forEach(function (chip) {
      chip.addEventListener("click", function () {
        chips.forEach(function (x) { x.classList.remove("active"); });
        chip.classList.add("active");
        curFilter = chip.getAttribute("data-filter");
        render();
      });
    });
    if (search) search.addEventListener("input", render);
    render();
  }



  /* ---------- 全站搜索（⌘K / Ctrl+K / /） ---------- */
  function setupSearchPalette() {
    var overlay = document.createElement("div");
    overlay.className = "search-overlay";
    overlay.id = "searchOverlay";
    overlay.innerHTML =
      '<div class="search-panel" role="dialog" aria-label="全站搜索">' +
      '<div class="sp-head"><span>🔍</span><input type="text" placeholder="搜索页面、课程、关键词…（↑↓ 选择，Enter 跳转）" aria-label="搜索"><span class="kbd">ESC</span></div>' +
      '<div class="search-list"></div></div>';
    document.body.appendChild(overlay);
    var input = overlay.querySelector("input");
    var list = overlay.querySelector(".search-list");
    var idx = [];
    PAGE_INDEX.forEach(function (p) {
      idx.push({ type: "page", ico: p[3], title: p[0], sub: p[2], file: p[1], kw: (p[0] + " " + p[2] + " " + (p[4] || "")).toLowerCase() });
    });
    COURSE_QUICK.forEach(function (c) {
      idx.push({ type: "course", ico: "📘", title: c.n, sub: c.c ? "课程编码 " + c.c : "数字公共治理课程", file: "kecheng-ditu.html", kw: (c.n + " " + (c.c || "")).toLowerCase() });
    });
    var items = [], active = -1;
    function open() { overlay.classList.add("open"); input.value = ""; render(""); input.focus(); active = -1; }
    function close() { overlay.classList.remove("open"); }
    function render(q) {
      q = (q || "").trim().toLowerCase();
      items = q ? idx.filter(function (i) { return i.kw.indexOf(q) >= 0; }) : idx.slice(0, 12);
      active = -1;
      if (!items.length) { list.innerHTML = '<div class="search-empty">没有找到匹配内容，换个关键词试试（可搜 99 门课程）</div>'; return; }
      list.innerHTML = items.map(function (it, i) {
        return '<div class="search-item' + (i === active ? " active" : "") + '" data-i="' + i + '"><span class="si-ico">' + it.ico + '</span><span><div class="si-title">' + it.title + '</div><div class="si-sub">' + it.sub + "</div></span></div>";
      }).join("");
    }
    function mark() {
      var els = list.querySelectorAll(".search-item");
      els.forEach(function (el, i) { el.classList.toggle("active", i === active); });
      if (els[active]) els[active].scrollIntoView({ block: "nearest" });
    }
    function goto(i) {
      if (i < 0 || i >= items.length) return;
      var it = items[i];
      close();
      if (window.ZST_SINGLE && window.ZST_SHOW) {
        window.ZST_SHOW(it.file);
        if (it.type === "course") {
          setTimeout(function () {
            var s = document.getElementById("courseSearch");
            if (s) { s.value = it.title; s.dispatchEvent(new Event("input")); }
          }, 60);
        }
      } else {
        if (it.type === "course") window.location.href = it.file + "?q=" + encodeURIComponent(it.title);
        else window.location.href = it.file;
      }
    }
    list.addEventListener("click", function (e) { var el = e.target.closest(".search-item"); if (el) goto(+el.getAttribute("data-i")); });
    input.addEventListener("input", function () { render(input.value); });
    input.addEventListener("keydown", function (e) {
      if (e.key === "ArrowDown") { e.preventDefault(); active = Math.min(active + 1, items.length - 1); mark(); }
      else if (e.key === "ArrowUp") { e.preventDefault(); active = Math.max(active - 1, 0); mark(); }
      else if (e.key === "Enter") { e.preventDefault(); goto(active >= 0 ? active : 0); }
      else if (e.key === "Escape") { close(); }
    });
    overlay.addEventListener("click", function (e) { if (e.target === overlay) close(); });
    document.addEventListener("keydown", function (e) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); open(); }
      if (e.key === "/" && document.activeElement && document.activeElement.tagName !== "INPUT" && document.activeElement.tagName !== "TEXTAREA") { e.preventDefault(); open(); }
    });
    document.querySelectorAll("[data-search-trigger]").forEach(function (t) {
      t.addEventListener("click", function (e) { e.preventDefault(); open(); });
    });
  }

  /* ---------- 绩点计算器 ---------- */
  function setupGpaCalc() {
    var wrap = document.getElementById("gpaCalc");
    if (!wrap) return;
    var tbody = wrap.querySelector("tbody");
    var numEl = wrap.querySelector(".gr-num");
    var tipEl = wrap.querySelector(".gr-tip");
    function esc(s) { var d = document.createElement("div"); d.textContent = s; return d.innerHTML; }
    function defaults() {
      return [
        { name: "高等数学三（I）", credit: 4, score: 88 },
        { name: "大学英语", credit: 2, score: 85 },
        { name: "政治学原理", credit: 3, score: 86 },
        { name: "行政管理学", credit: 3, score: 87 },
        { name: "经济学基础", credit: 3, score: 85 },
        { name: "习近平新时代中国特色社会主义思想概论", credit: 3, score: 84 },
        { name: "军事课", credit: 4, score: 85 },
        { name: "体育", credit: 1, score: 90 }
      ];
    }
    var rows;
    try { rows = JSON.parse(localStorage.getItem("zst_gpa_rows") || "[]"); } catch (e) { rows = []; }
    if (!rows.length) rows = defaults();
    function read() {
      rows = [];
      tbody.querySelectorAll("tr").forEach(function (tr) {
        var name = (tr.querySelector("[data-gpa-name]").value || "").trim();
        var credit = parseFloat(tr.querySelector("[data-gpa-credit]").value) || 0;
        var score = parseFloat(tr.querySelector("[data-gpa-score]").value);
        if (name || credit > 0 || score) rows.push({ name: name || "未命名课程", credit: credit, score: isNaN(score) ? 0 : score });
      });
    }
    function render() {
      tbody.innerHTML = "";
      rows.forEach(function (r, i) {
        var tr = document.createElement("tr");
        tr.innerHTML = '<td><input data-gpa-name value="' + esc(r.name) + '" placeholder="课程名称"></td>' +
          '<td style="width:86px"><input data-gpa-credit type="number" step="0.5" min="0" max="30" value="' + r.credit + '"></td>' +
          '<td style="width:86px"><input data-gpa-score type="number" min="0" max="100" value="' + r.score + '"></td>' +
          '<td style="width:40px;text-align:center"><button class="del" data-gpa-del="' + i + '" aria-label="删除">✕</button></td>';
        tbody.appendChild(tr);
      });
      compute();
    }
    function compute() {
      read();
      var total = 0, sum = 0;
      rows.forEach(function (r) { var g = (r.score - 50) / 10; if (g < 0) g = 0; total += r.credit; sum += g * r.credit; });
      var gpa = total > 0 ? sum / total : 0;
      numEl.textContent = gpa.toFixed(3);
      tipEl.className = "gr-tip" + (gpa >= 3.8 ? " good" : (gpa >= 3.5 ? "" : " warn"));
      tipEl.innerHTML = gpa >= 3.8 ? "🎯 已达冲刺线 3.8：保研 + 荣誉学士双保险" :
        (gpa >= 3.5 ? "✅ 已过 3.5 安全线：稳扎稳打，向 3.8 冲刺" :
          "⚠️ 距 3.5 还差 " + (3.5 - gpa).toFixed(3) + "：优先把高学分课程（高数/英语/专业课）分数提上去");
      localStorage.setItem("zst_gpa_rows", JSON.stringify(rows));
    }
    tbody.addEventListener("input", compute);
    tbody.addEventListener("click", function (e) {
      var b = e.target.closest("[data-gpa-del]");
      if (b) { read(); rows.splice(+b.getAttribute("data-gpa-del"), 1); render(); }
    });
    var add = wrap.querySelector("[data-gpa-add]");
    var clr = wrap.querySelector("[data-gpa-clear]");
    var demo = wrap.querySelector("[data-gpa-demo]");
    if (add) add.addEventListener("click", function () { read(); rows.push({ name: "", credit: 2, score: 80 }); render(); });
    if (clr) clr.addEventListener("click", function () { rows = []; render(); });
    if (demo) demo.addEventListener("click", function () { rows = defaults(); render(); });
    render();
  }

  /* ---------- 四年课程路线图（课程地图页） ---------- */
  function setupRoadmap() {
    var el = document.getElementById("courseRoadmap");
    if (!el) return;
    var data = window.COURSES || [];
    if (!data.length) { el.innerHTML = '<div class="callout info">课程数据加载中…</div>'; return; }
    var semMap = {};
    var order = ["大一上", "大一下", "大二上", "大二下", "大三上", "大三下", "大四上", "大四下"];
    function esc(s) { var d = document.createElement("div"); d.textContent = s; return d.innerHTML; }
    data.forEach(function (c) {
      var s = c.semester;
      if (order.indexOf(s) < 0) s = s.indexOf("大一") === 0 ? "大一上" : s.indexOf("大二") === 0 ? "大二上" : s.indexOf("大三") === 0 ? "大三上" : "大四上";
      (semMap[s] = semMap[s] || []).push(c);
    });
    var years = [["大一", ["大一上", "大一下"]], ["大二", ["大二上", "大二下"]], ["大三", ["大三上", "大三下"]], ["大四", ["大四上", "大四下"]]];
    var html = "";
    years.forEach(function (y) {
      html += '<div class="roadmap-year"><div class="ry-label">' + y[0] + "</div>";
      y[1].forEach(function (sem) {
        var list = semMap[sem] || [];
        html += '<div class="roadmap-sem"><div class="rs-title">' + sem + " · " + list.length + " 门</div><div class=\"roadmap-chips\">";
        list.forEach(function (c) {
          var cls = c.section.indexOf("1.") === 0 ? "pub" : c.section.indexOf("2.1") === 0 ? "core" : c.section.indexOf("2.2") === 0 ? "prac" : c.section.indexOf("2.3.1") === 0 ? "base" : "elec";
          html += '<span class="r-chip ' + cls + '" data-course="' + esc(c.name) + '" title="' + esc(c.name) + "（" + c.credits + " 学分）\">" + esc(c.name) + "</span>";
        });
        html += "</div></div>";
      });
      html += "</div>";
    });
    el.innerHTML = html;
    el.addEventListener("click", function (e) {
      var chip = e.target.closest(".r-chip");
      if (!chip) return;
      var name = chip.getAttribute("data-course");
      var search = document.getElementById("courseSearch");
      if (search) { search.value = name; search.dispatchEvent(new Event("input")); }
      var listEl = document.getElementById("courseList");
      if (listEl) listEl.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  }

  /* ---------- 首页目标进度仪表盘 ---------- */
  function setupDashboard() {
    var el = document.getElementById("progressDashboard");
    if (!el) return;
    var cats = [
      { label: "大一行动", ico: "1️⃣", keys: ["dayi-actions"] },
      { label: "大二行动", ico: "2️⃣", keys: ["daer-actions"] },
      { label: "大三行动", ico: "3️⃣", keys: ["dasan-actions"] },
      { label: "大四行动", ico: "4️⃣", keys: ["dasi-actions", "dasi-finish"] },
      { label: "入党 · 青马 · 班长", ico: "🚩", keys: ["rz-actions", "bz-actions"] },
      { label: "保研 · 荣誉学士", ico: "🎓", keys: ["by-actions", "ry-actions"] },
      { label: "央选（研究生主攻）", ico: "🏛️", keys: ["dx-actions"] },
      { label: "竞赛科研", ico: "🔬", keys: ["js-actions"] },
      { label: "资源启动", ico: "📚", keys: ["zy-actions"] }
    ];
    var grand = { done: 0, total: 0 };
    var html = "";
    cats.forEach(function (c) {
      var done = 0, total = 0;
      c.keys.forEach(function (k) {
        done += parseInt(localStorage.getItem("zst_meta_" + k + "_done") || "0", 10);
        total += parseInt(localStorage.getItem("zst_meta_" + k + "_total") || "0", 10);
      });
      grand.done += done; grand.total += total;
      var pct = total > 0 ? Math.round(done / total * 100) : 0;
      html += '<div class="dash-card"><div class="dc-title">' + c.ico + " " + c.label + '</div><div class="dc-sub">' + done + "/" + total + ' 项</div><div class="progress"><div style="width:' + pct + '%"></div></div><div class="progress-label"><span>完成度</span><span>' + pct + "%</span></div></div>";
    });
    var gp = grand.total > 0 ? Math.round(grand.done / grand.total * 100) : 0;
    var ghtml = '<div class="dash-card dash-overall"><div class="dc-title">🎯 四年目标总进度</div><div class="dc-sub">' + grand.done + "/" + grand.total + ' 项行动 · 到各页面打卡后自动汇总</div><div class="progress"><div style="width:' + gp + '%"></div></div><div class="progress-label"><span>总完成度</span><span>' + gp + "%</span></div></div>";
    el.innerHTML = ghtml + html;
  }

  /* ---------- 初始化 ---------- */
  document.addEventListener("DOMContentLoaded", function () {
    buildNav();
    setupMobileSidebar();
    setupTheme();
    setupBackTop();
    setupAccordion();
    setupTabs();
    setupChecklist();
    setupMindmap();
    setupCourseMap();
    setupSearchPalette();
    setupGpaCalc();
    setupRoadmap();
    setupDashboard();
    var yr = document.getElementById("year");
    if (yr) yr.textContent = new Date().getFullYear();
  });
})();
