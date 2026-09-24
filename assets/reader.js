/* ============================================================
   pyfin_cookbook —— 《项目操作手册》在线阅读器
   进度条 / 滚动定位 / 目录抽屉 / 全文检索 / 图集灯箱 / 章节快捷键
   ============================================================ */
(function () {
  "use strict";

  var NAV_H = 60;
  var body = document.querySelector(".doc-body");
  if (!body) return;

  var heads = [].slice.call(body.querySelectorAll(".doc-chapter, .doc-h2, .doc-h3"));
  var chapters = [].slice.call(body.querySelectorAll(".doc-chapter"));
  var groups = [].slice.call(document.querySelectorAll(".ds-group"));
  var tocGroups = [].slice.call(document.querySelectorAll(".dt-group"));
  var side = document.querySelector(".doc-side");
  var bar = document.querySelector(".readbar i");
  var totop = document.querySelector(".totop");

  function esc(s) { return String(s).replace(/([^\w-])/g, "\\$1"); }

  function headIndex() {
    var line = NAV_H + 92, idx = 0;
    for (var i = 0; i < heads.length; i++) {
      if (heads[i].getBoundingClientRect().top <= line) idx = i;
      else break;
    }
    return idx;
  }

  /* ---------- 1. 进度条 + 回到顶部 ---------- */
  var ticking = false;
  function onFrame() {
    ticking = false;
    var st = window.pageYOffset || document.documentElement.scrollTop;
    if (bar) {
      var max = document.documentElement.scrollHeight - window.innerHeight;
      bar.style.width = (max > 0 ? Math.min(100, Math.max(0, st / max * 100)) : 0) + "%";
    }
    if (totop) totop.classList.toggle("show", st > 700);
    syncSpy();
  }
  function onScroll() {
    if (ticking) return;
    ticking = true;
    requestAnimationFrame(onFrame);
  }

  /* ---------- 2. 滚动定位：左栏高亮 + 右栏切换 ---------- */
  var lastKey = "";
  function syncSpy() {
    if (!heads.length) return;
    var h = heads[headIndex()];
    if (!h) return;
    var ch = h.classList.contains("doc-chapter") ? h : h.closest(".doc-chapter");
    var chId = ch ? ch.id : "";
    var secId = h.classList.contains("doc-chapter") ? "" : h.id;
    var key = chId + "|" + secId;
    if (key === lastKey) return;
    lastKey = key;

    groups.forEach(function (g) {
      var on = g.getAttribute("data-ch") === chId;
      g.classList.toggle("active", on);
      if (on) g.classList.add("open"); else g.classList.remove("open");
    });
    tocGroups.forEach(function (g) {
      g.classList.toggle("on", g.getAttribute("data-ch") === chId);
    });
    document.querySelectorAll(".ds-sub a.on, .dt-list a.on").forEach(function (a) {
      a.classList.remove("on");
    });
    if (secId) {
      [".ds-sub", ".dt-list"].forEach(function (scope) {
        var a = document.querySelector(scope + ' a[href="#' + esc(secId) + '"]');
        if (a) a.classList.add("on");
      });
      var cur = document.querySelector('.ds-sub a[href="#' + esc(secId) + '"]');
      if (cur && side) {
        var r = cur.getBoundingClientRect(), br = side.getBoundingClientRect();
        if (r.top < br.top + 10 || r.bottom > br.bottom - 10) {
          side.scrollTop += r.top - br.top - br.height / 2 + r.height / 2;
        }
      }
    }
  }

  window.addEventListener("scroll", onScroll, { passive: true });
  window.addEventListener("resize", function () { lastKey = ""; onScroll(); });
  /* 懒加载插图会改变版面高度，图片就位后重新定位一次 */
  window.addEventListener("load", function () { lastKey = ""; onScroll(); });
  setTimeout(function () { lastKey = ""; onScroll(); }, 1200);
  setTimeout(function () { lastKey = ""; onScroll(); }, 3000);

  /* ---------- 3. 目录抽屉（窄屏） ---------- */
  var sideTg = document.querySelector(".side-tg");
  if (sideTg && side) {
    sideTg.addEventListener("click", function () { side.classList.toggle("open"); });
    document.addEventListener("click", function (e) {
      if (window.innerWidth > 1000 || !side.classList.contains("open")) return;
      if (side.contains(e.target) || sideTg.contains(e.target)) return;
      side.classList.remove("open");
    });
    side.addEventListener("click", function (e) {
      if (window.innerWidth <= 1000 && e.target.closest("a")) side.classList.remove("open");
    });
  }

  /* ---------- 4. 左栏目录筛选（只筛标题） ---------- */
  var input = document.querySelector("#ds-q");
  var counter = document.querySelector(".ds-search .sc");
  var emptyBox = document.querySelector(".ds-empty");
  var links = [].slice.call(document.querySelectorAll(".ds-ch, .ds-sub a"));

  function norm(s) { return String(s).toLowerCase().replace(/\s+/g, ""); }

  function reset() {
    links.forEach(function (a) { a.classList.remove("fhide"); });
    groups.forEach(function (g) { g.classList.remove("fhide", "open", "active"); });
    if (counter) { counter.textContent = ""; counter.classList.add("hide"); }
    if (emptyBox) emptyBox.style.display = "none";
    lastKey = "";
    onScroll();
  }

  function filter() {
    var q = norm(input.value);
    if (!q) { reset(); return; }
    var hits = 0;
    groups.forEach(function (g) {
      var chA = g.querySelector(".ds-ch");
      var chHit = !!chA && norm(chA.textContent).indexOf(q) >= 0;
      var subHit = 0;
      [].slice.call(g.querySelectorAll(".ds-sub a")).forEach(function (a) {
        var m = norm(a.textContent).indexOf(q) >= 0;
        a.classList.toggle("fhide", !m);
        if (m) subHit++;
      });
      var ok = chHit || subHit > 0;
      g.classList.toggle("fhide", !ok);
      g.classList.toggle("open", ok);
      if (ok) hits += Math.max(subHit, 1);
    });
    if (counter) {
      counter.textContent = String(hits);
      counter.classList.toggle("hide", hits === 0);
    }
    if (emptyBox) emptyBox.style.display = hits ? "none" : "block";
  }

  if (input) {
    var timer = null;
    input.addEventListener("input", function () {
      clearTimeout(timer);
      timer = setTimeout(filter, 90);
    });
    input.addEventListener("keydown", function (e) {
      if (e.key === "Escape") { input.value = ""; reset(); input.blur(); return; }
      if (e.key !== "Enter") return;
      var first = document.querySelector(".ds-sub a:not(.fhide)") ||
                  document.querySelector(".ds-ch:not(.fhide)");
      if (first) {
        var id = (first.getAttribute("href") || "").slice(1);
        if (id) {
          document.querySelectorAll(".ds-search .sc").forEach(function (s) { s.classList.add("hide"); });
          window.location.hash = id;
        }
      }
    });
  }

  /* ---------- 5. 正文全文检索 ---------- */
  var fsBtn = document.querySelector("#fs-btn");
  var fsPanel = document.querySelector("#fs-panel");
  var fsQ = document.querySelector("#fs-q");
  var fsList = document.querySelector("#fs-list");
  var fsN = document.querySelector("#fs-n");
  var fsX = document.querySelector("#fs-x");
  var FS = null;                 /* 首次打开检索面板时按需从正文 DOM 建立 */
  var fsHits = [], fsSel = -1, fsTmr = null;

  function txtEsc(s) {
    return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  function clean(s) { return String(s).replace(/\s+/g, " ").trim(); }

  /* 建立索引：正文各区块都是 <section class="doc-chapter"> 的直接子元素，
     因此按文档顺序遍历一遍即可把「小节标题 → 本节正文」切分出来。
     不额外内嵌索引副本，页面体积不变。 */
  function fsBuild() {
    var roots = [].slice.call(document.querySelectorAll(".doc-body > section.doc-chapter"));
    var out = [];
    var cur = null, curCh = "";
    roots.forEach(function (sec) {
      var blocks = [].slice.call(sec.children);
      blocks.forEach(function (b) {
        var cls = b.className || "";
        if (cls.indexOf("doc-pager") >= 0) return;          /* 上下章翻页不进索引 */
        if (cls.indexOf("ch-head") >= 0) {
          var no = b.querySelector(".ch-no");
          var nm = b.querySelector(".ch-name");
          curCh = clean((no ? no.textContent + "　" : "") + (nm ? nm.textContent : "")) || sec.id;
          cur = { a: sec.id, h: curCh, lvl: 0, c: curCh, t: "", _s: "" };
          out.push(cur);
          return;
        }
        var isH = /doc-h[234]/.test(cls);
        if (isH && b.id) {
          var ht = clean(b.textContent.replace(/¶/g, ""));
          cur = { a: b.id, h: ht, lvl: parseInt(cls.replace(/\D/g, ""), 10) || 2, c: curCh, t: "", _s: "" };
          out.push(cur);
          return;
        }
        if (!cur) return;
        var txt = clean(b.textContent);
        if (txt) cur.t += (cur.t ? " " : "") + txt;
      });
    });
    out.forEach(function (e) { e._s = (e.h + " " + e.t).toLowerCase(); });
    return out;
  }

  function fsOpen(on) {
    if (!fsPanel) return;
    if (on && FS === null) FS = fsBuild();
    fsPanel.hidden = !on;
    if (fsBtn) fsBtn.setAttribute("aria-expanded", on ? "true" : "false");
    if (on && fsQ) { fsQ.focus(); fsQ.select(); }
  }

  /* 片段内高亮：q 已小写 */
  function hi(text, q) {
    var low = String(text).toLowerCase(), out = "", i = 0, k;
    for (;;) {
      k = low.indexOf(q, i);
      if (k < 0) { out += txtEsc(text.slice(i)); break; }
      out += txtEsc(text.slice(i, k)) + "<mark>" + txtEsc(text.slice(k, k + q.length)) + "</mark>";
      i = k + q.length;
    }
    return out;
  }

  function snippet(t, q) {
    var k = String(t).toLowerCase().indexOf(q);
    if (k < 0) return String(t).slice(0, 108);
    var a = Math.max(0, k - 42), b = Math.min(t.length, k + q.length + 64);
    return (a > 0 ? "…" : "") + t.slice(a, b) + (b < t.length ? "…" : "");
  }

  var FS_MAX = 40;

  function fsRender() {
    if (!fsList) return;
    var raw = clean(fsQ.value);
    var q = raw.toLowerCase();
    if (!q) {
      fsHits = []; fsSel = -1;
      fsList.innerHTML = '<div class="fs-meta">在手册<strong>全书正文</strong>中检索，范围含表格、提示框与代码块。'
        + '左栏输入框只筛章节标题。</div>';
      if (fsN) fsN.textContent = "";
      return;
    }
    if (FS === null) FS = fsBuild();
    var all = [];
    for (var i = 0; i < FS.length; i++) {
      var e = FS[i], pos = e._s.indexOf(q);
      if (pos < 0) continue;
      all.push({ e: e, head: e.h.toLowerCase().indexOf(q) >= 0, pos: pos });
    }
    all.sort(function (x, y) { return (y.head - x.head) || (x.pos - y.pos); });
    var total = all.length;
    fsHits = all.slice(0, FS_MAX);
    fsSel = fsHits.length ? 0 : -1;
    if (fsN) fsN.textContent = total ? total + " 处" : "无匹配";
    if (!total) {
      fsList.innerHTML = '<div class="fs-meta">没有找到「' + txtEsc(raw) + '」。换个更短的关键词试试，或用左栏按章翻阅。</div>';
      return;
    }
    var html = "";
    for (var j = 0; j < fsHits.length; j++) {
      var it = fsHits[j], en = it.e, sn = snippet(en.t, q);
      html += '<button class="fs-hit' + (j === fsSel ? " sel" : "") + '" type="button" data-a="' + txtEsc(en.a) + '">'
        + '<span class="fs-crumb">' + txtEsc(en.c) + " · " + (en.lvl === 0 ? "章" : (en.lvl === 2 ? "节" : "小节")) + "</span>"
        + '<span class="fs-h">' + hi(en.h, q) + "</span>"
        + (sn ? '<span class="fs-sn">' + hi(sn, q) + "</span>" : "")
        + "</button>";
    }
    if (total > fsHits.length) {
      html += '<div class="fs-meta">仅显示前 ' + fsHits.length + ' 条，共 ' + total
        + ' 处；补全关键词可缩小范围。</div>';
    }
    fsList.innerHTML = html;
  }

  function fsSelTo(i) {
    var bs = [].slice.call(fsList.querySelectorAll(".fs-hit"));
    bs.forEach(function (b, k) {
      b.classList.toggle("sel", k === i);
      if (k === i && b.scrollIntoView) b.scrollIntoView({ block: "nearest" });
    });
  }

  function fsGo(anchor) {
    if (!anchor) return;
    var el = document.getElementById(anchor);
    if (!el) return;
    fsOpen(false);
    var chEl = el.classList.contains("doc-chapter") ? el : el.closest(".doc-chapter");
    if (chEl && chEl.id) {
      var g = document.querySelector('.ds-group[data-ch="' + chEl.id + '"]');
      if (g) g.classList.add("open");
      var t = document.querySelector('.dt-group[data-ch="' + chEl.id + '"]');
      if (t) t.classList.add("on");
    }
    var top = el.getBoundingClientRect().top + (window.pageYOffset || 0) - NAV_H - 14;
    window.scrollTo({ top: Math.max(0, top), behavior: "auto" });
    if (window.history && window.history.replaceState) window.history.replaceState(null, "", "#" + anchor);
    lastKey = "";
    onScroll();
    document.querySelectorAll(".fs-flash").forEach(function (n) { n.classList.remove("fs-flash"); });
    void el.offsetWidth;
    el.classList.add("fs-flash");
    setTimeout(function () { el.classList.remove("fs-flash"); }, 1900);
  }

  if (fsBtn && fsPanel && fsQ) {
    fsBtn.addEventListener("click", function (e) {
      e.stopPropagation();
      fsOpen(fsPanel.hidden);
    });
    if (fsX) fsX.addEventListener("click", function () { fsOpen(false); fsBtn.focus(); });
    fsList.addEventListener("click", function (e) {
      var b = e.target.closest(".fs-hit");
      if (b) fsGo(b.getAttribute("data-a"));
    });
    fsQ.addEventListener("input", function () {
      clearTimeout(fsTmr);
      fsTmr = setTimeout(fsRender, 110);
    });
    fsQ.addEventListener("keydown", function (e) {
      if (e.key === "Escape") { e.preventDefault(); fsOpen(false); fsBtn.focus(); return; }
      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        if (!fsHits.length) return;
        e.preventDefault();
        fsSel = Math.max(0, Math.min(fsHits.length - 1, fsSel + (e.key === "ArrowDown" ? 1 : -1)));
        fsSelTo(fsSel);
        return;
      }
      if (e.key === "Enter") {
        e.preventDefault();
        if (fsSel < 0) fsSel = 0;
        if (fsHits[fsSel]) fsGo(fsHits[fsSel].e.a);
      }
    });
    document.addEventListener("click", function (e) {
      if (fsPanel.hidden) return;
      if (fsPanel.contains(e.target) || fsBtn.contains(e.target)) return;
      fsOpen(false);
    });
    fsRender();
  }

  /* ---------- 6. 章节快捷键 ---------- */
  function goChapter(delta) {
    if (!chapters.length) return;
    var idx = 0;
    for (var i = 0; i < chapters.length; i++) {
      if (chapters[i].getBoundingClientRect().top <= NAV_H + 92) idx = i;
      else break;
    }
    var t = idx + delta;
    if (t < 0 || t >= chapters.length) return;
    window.location.hash = chapters[t].id;
  }

  document.addEventListener("keydown", function (e) {
    var el = e.target || {};
    var tag = (el.tagName || "").toLowerCase();
    if (tag === "input" || tag === "textarea" || el.isContentEditable) {
      if (e.key === "Escape" && input) { input.value = ""; reset(); input.blur(); }
      return;
    }
    if ((e.ctrlKey || e.metaKey) && String(e.key).toLowerCase() === "k" && fsQ) {
      e.preventDefault(); fsOpen(true); return;
    }
    if (e.key === "/" && fsQ) { e.preventDefault(); fsOpen(true); return; }
    if (e.key === "Escape" && fsPanel && !fsPanel.hidden) { fsOpen(false); return; }
    if (e.altKey && e.key === "ArrowLeft") { e.preventDefault(); goChapter(-1); }
    if (e.altKey && e.key === "ArrowRight") { e.preventDefault(); goChapter(1); }
  });

  /* ---------- 7. 插图灯箱 ---------- */
  var lb = document.createElement("div");
  lb.className = "lb";
  lb.innerHTML = '<button class="lb-x" type="button" aria-label="关闭">'
    + '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round">'
    + '<path d="M18 6 6 18M6 6l12 12"/></svg></button><img alt=""><p class="lb-cap"></p>';
  document.body.appendChild(lb);
  var lbImg = lb.querySelector("img");
  var lbCap = lb.querySelector(".lb-cap");

  function closeLb() {
    lb.classList.remove("on");
    document.body.style.overflow = "";
  }
  document.querySelectorAll(".doc-fig img").forEach(function (img) {
    img.addEventListener("click", function () {
      var fig = img.closest(".doc-fig");
      var cap = fig ? fig.querySelector("figcaption") : null;
      lbImg.src = img.currentSrc || img.src;
      lbCap.textContent = cap ? cap.textContent : (img.alt || "");
      lb.classList.add("on");
      document.body.style.overflow = "hidden";
    });
  });
  lb.addEventListener("click", function (e) { if (e.target !== lbImg) closeLb(); });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && lb.classList.contains("on")) closeLb();
  });

  /* ---------- 8. 回到顶部 ---------- */
  if (totop) {
    totop.addEventListener("click", function () {
      window.scrollTo({ top: 0, behavior: "smooth" });
    });
  }

  /* ---------- 9. 带 hash 进入时先展开对应章 ---------- */
  if (window.location.hash.length > 1) {
    var target = document.getElementById(window.location.hash.slice(1));
    if (target) {
      var chEl = target.classList.contains("doc-chapter") ? target : target.closest(".doc-chapter");
      if (chEl) {
        var g = document.querySelector('.ds-group[data-ch="' + chEl.id + '"]');
        if (g) g.classList.add("open");
        var t = document.querySelector('.dt-group[data-ch="' + chEl.id + '"]');
        if (t) t.classList.add("on");
      }
    }
  }

  onScroll();
})();
