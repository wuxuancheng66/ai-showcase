// 单文件版路由适配器：让 main.js 在单文件模式下切换区块
window.ZST_SINGLE = true;
window.ZST_SHOW = function (file) {
  var target = document.getElementById("pg-" + file);
  if (!target) return;
  document.querySelectorAll(".pg").forEach(function (s) { s.style.display = "none"; });
  target.style.display = "block";
  document.body.setAttribute("data-page", file);
  document.querySelectorAll(".nav-item").forEach(function (a) { a.classList.toggle("active", a.getAttribute("data-file") === file); });
  window.scrollTo(0, 0);
  var sb = document.querySelector(".sidebar");
  if (sb) sb.classList.remove("open");
};
(function () {
  var sb = document.querySelector(".sidebar"), mb = document.getElementById("menuBtn");
  if (sb && mb) mb.addEventListener("click", function () { sb.classList.toggle("open"); });
  window.addEventListener("hashchange", function () {
    var f = (location.hash || "").replace("#", "") || "index.html";
    if (document.getElementById("pg-" + f)) ZST_SHOW(f);
  });
  var init = (location.hash || "").replace("#", "") || "index.html";
  if (!document.getElementById("pg-" + init)) init = "index.html";
  ZST_SHOW(init);
})();
