/* mansea 前端：即时检索 + 键盘导航 + 全文查看 */
(() => {
  const $ = (id) => document.getElementById(id);
  const q = $("q"), results = $("results"), meta = $("meta"), empty = $("empty");
  const detail = $("detail"), dTitle = $("d-title"), dSub = $("d-sub"), dBody = $("d-body");
  let items = [], sel = -1, timer = null;

  const EXAMPLES = [
    "递归查找文件", "查看端口占用", "压缩解压 tar gz", "进程管理 kill",
    "find files by name", "ssh 免密登录", "磁盘空间", "文本替换 sed",
  ];

  function esc(s) {
    return (s || "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  }

  function renderChips() {
    $("chips").innerHTML = EXAMPLES.map((e) => `<span class="chip">${esc(e)}</span>`).join("");
    $("chips").addEventListener("click", (ev) => {
      if (ev.target.classList.contains("chip")) { q.value = ev.target.textContent; q.focus(); run(); }
    });
  }

  function render(data) {
    items = data.results || [];
    sel = -1;
    if (!items.length) {
      results.innerHTML = "";
      empty.hidden = false;
      empty.textContent = data.query ? `「${data.query}」没有命中。换个说法试试。`
        : "输入关键词开始检索。索引全部来自本机 /usr/share/man，不会联网。";
      meta.textContent = data.query ? "0 条结果" : "";
      return;
    }
    empty.hidden = true;
    meta.textContent = `${data.total} 篇文档 · 命中 ${items.length} 条`;
    results.innerHTML = items.map((r, i) => `
      <li class="res" data-id="${r.id}" data-i="${i}">
        <h3><span class="sec">${esc(r.title)}</span><span class="score">${r.score.toFixed(2)}</span></h3>
        ${r.summary ? `<p class="sum">${esc(r.summary.slice(0, 180))}</p>` : ""}
        ${r.snippet ? `<p class="snip">${r.snippet}</p>` : ""}
      </li>`).join("");
  }

  async function run() {
    const val = q.value.trim();
    if (!val) { render({ results: [], query: "", total: 0 }); return; }
    try {
      const r = await fetch("/api/search?q=" + encodeURIComponent(val) + "&k=20");
      render(await r.json());
    } catch (e) {
      empty.hidden = false;
      empty.innerHTML = "连不上本地服务。请在项目目录执行 <code>./run.sh serve</code> 后再打开本页面。";
    }
  }

  async function open(id) {
    try {
      const r = await fetch("/api/doc?id=" + id);
      const d = await r.json();
      dTitle.textContent = d.title || d.name || "";
      dSub.textContent = [d.source, d.path].filter(Boolean).join(" · ");
      dBody.textContent = d.text || "(空)";
      detail.hidden = false;
      document.body.style.overflow = "hidden";
      dBody.scrollTop = 0;
    } catch (e) { /* ignore */ }
  }
  function close() { detail.hidden = true; document.body.style.overflow = ""; }

  function move(delta) {
    if (!items.length) return;
    sel = (sel + delta + items.length) % items.length;
    [...results.children].forEach((el, i) => el.classList.toggle("sel", i === sel));
    results.children[sel].scrollIntoView({ block: "nearest" });
  }

  q.addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(run, 110); });
  results.addEventListener("click", (ev) => {
    const li = ev.target.closest(".res");
    if (li) open(li.dataset.id);
  });
  $("d-close").addEventListener("click", close);
  document.addEventListener("keydown", (ev) => {
    if (ev.key === "/" && document.activeElement !== q) { ev.preventDefault(); q.focus(); return; }
    if (ev.key === "Escape") { close(); return; }
    if (ev.key === "ArrowDown") { ev.preventDefault(); move(1); return; }
    if (ev.key === "ArrowUp") { ev.preventDefault(); move(-1); return; }
    if (ev.key === "Enter" && sel >= 0 && detail.hidden) { ev.preventDefault(); open(items[sel].id); }
  });

  (async () => {
    try {
      const s = await (await fetch("/api/stats")).json();
      const secs = Object.entries(s.sections).sort((a, b) => b[1] - a[1])
        .map(([k, v]) => `man${k}:${v}`).join("  ");
      $("stats").innerHTML = `${s.docs} 篇 · ${s.terms.toLocaleString()} 词项<br>${secs}`;
      $("src").textContent = "语料：/usr/share/man";
    } catch (e) { $("stats").textContent = "离线模式"; }
  })();

  renderChips();
  q.focus();
})();
