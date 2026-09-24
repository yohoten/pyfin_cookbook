/* pyfin_cookbook 站点脚本：主题切换 / 代码复制 / 滚动显现 / 手册阅读器 */
(function () {
  "use strict";

  /* ---------- 主题切换 ---------- */
  function applyTheme(t) {
    document.documentElement.setAttribute("data-theme", t);
    try { localStorage.setItem("pf-theme", t); } catch (e) { /* ignore */ }
  }
  document.querySelectorAll("[data-theme-toggle]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var cur = document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light";
      applyTheme(cur === "dark" ? "light" : "dark");
    });
  });

  /* ---------- 代码复制 ---------- */
  document.querySelectorAll(".copy-btn").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var scope = btn.closest(".code-wrap") || btn.parentElement;
      var pre = scope.querySelector("pre");
      var text = pre ? pre.innerText : "";
      var done = function () {
        var old = btn.innerHTML;
        btn.innerHTML = "&#10003; 已复制";
        btn.classList.add("ok");
        setTimeout(function () { btn.innerHTML = old; btn.classList.remove("ok"); }, 1600);
      };
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(done, function () { fallbackCopy(text, done); });
      } else { fallbackCopy(text, done); }
    });
  });
  function fallbackCopy(text, done) {
    var ta = document.createElement("textarea");
    ta.value = text; ta.style.position = "fixed"; ta.style.opacity = "0";
    document.body.appendChild(ta); ta.select();
    try { document.execCommand("copy"); } catch (e) { /* ignore */ }
    document.body.removeChild(ta); done();
  }

  /* ---------- 滚动显现 ---------- */
  if ("IntersectionObserver" in window && !window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (en.isIntersecting) { en.target.classList.add("in"); io.unobserve(en.target); }
      });
    }, { threshold: 0.08 });
    document.querySelectorAll(".reveal").forEach(function (el) { io.observe(el); });
  } else {
    document.querySelectorAll(".reveal").forEach(function (el) { el.classList.add("in"); });
  }
  /* 兜底：3 秒后强制显现，避免任何极端情况下内容保持隐藏 */
  setTimeout(function () {
    document.querySelectorAll(".reveal:not(.in)").forEach(function (el) { el.classList.add("in"); });
  }, 3000);

  /* ---------- 课件手风琴：仅允许展开一个（保持页面紧凑） ---------- */
  var cwAll = document.querySelectorAll(".cw-chapter");
  cwAll.forEach(function (d) {
    d.addEventListener("toggle", function () {
      if (d.open) {
        cwAll.forEach(function (o) { if (o !== d) o.open = false; });
      }
    });
  });
})();
