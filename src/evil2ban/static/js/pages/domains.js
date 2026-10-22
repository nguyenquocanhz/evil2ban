/* Màn Tên miền (DomainGate) — nạp khi mở tới. Số liệu và cổng chặn theo từng site. */
(function () {
  "use strict";
  var X, EL, S = { st: "wait", d: null, filter: "all", q: "", page: 1, per: 12, menu: null, detail: null };
  var FILTERS = [["all", "dom.all"], ["attacked", "dom.attacked"], ["chan", "dom.gateOn"], ["tat", "dom.gateOff"]];
  var MODES = ["chan", "giam-sat", "tat"];
  function t(k, o) { return X.t(k, o); }

  function list() {
    var q = S.q.toLowerCase();
    return (S.d || []).filter(function (d) {
      if (q && d.domain.indexOf(q) < 0) return false;
      if (S.filter === "attacked") return d.suspects > 0;
      if (S.filter === "chan" || S.filter === "tat") return d.mode === S.filter;
      return true;
    });
  }
  function counts() {
    var d = S.d || [];
    return { all: d.length, attacked: d.filter(function (x) { return x.suspects > 0; }).length,
      chan: d.filter(function (x) { return x.mode === "chan"; }).length, tat: d.filter(function (x) { return x.mode === "tat"; }).length };
  }
  function toolbar() {
    return '<div class="filters"><div class="chips"><div class="tabs">' + FILTERS.map(function (f) {
      return '<button type="button" class="tab" data-filter="' + f[0] + '" aria-selected="' + (S.filter === f[0]) + '">' + t(f[1]) + '<span class="n" data-cnt="' + f[0] + '"></span></button>';
    }).join("") + '</div></div><div class="filter-tools"><label class="search">' + X.ic("search") +
      '<input class="input" id="dom-q" type="text" autocomplete="off" placeholder="' + t("dom.search") + '" value="' + X.esc(S.q) + '"></label></div></div>' +
      '<p class="info-line">' + X.ic("info") + "<span>" + t("dom.note") + "</span></p>";
  }
  function modeBtn(d) {
    return '<div class="dd right"><button type="button" class="mode-btn" data-mode-for="' + X.esc(d.domain) + '" aria-haspopup="menu" aria-expanded="' + (S.menu === d.domain) + '">' +
      '<span class="mode-dot ' + d.mode + '"></span>' + t("dom.mode." + d.mode) + X.ic("chevron-down", "muted") + "</button>" +
      (S.menu === d.domain ? '<div class="pop menu" role="menu">' + MODES.map(function (m) {
        return '<button type="button" class="menu-item" role="menuitemradio" aria-checked="' + (d.mode === m) + '" data-set-mode="' + m + '" data-domain="' + X.esc(d.domain) + '">' +
          X.ic("check", "i-check") + "<span>" + t("dom.mode." + m) + '<span class="menu-desc">' + t("dom.modeDesc." + m) + "</span></span></button>";
      }).join("") + "</div>" : "") + "</div>";
  }
  function table() {
    if (S.st === "wait") return '<div style="min-height:480px"></div>';
    if (S.st === "loading") return X.card({ clip: true, body: '<div style="padding-top:20px">' + X.skRows(8) + "</div>" });
    if (S.st === "error") return X.card({ body: X.errBody() });
    var rows = list(), pages = Math.max(1, Math.ceil(rows.length / S.per));
    S.page = Math.min(Math.max(1, S.page), pages);
    var slice = rows.slice((S.page - 1) * S.per, S.page * S.per), max = Math.max.apply(null, (S.d || []).map(function (d) { return d.requests; }).concat([1]));
    if (!rows.length) return X.card({ id: "dom-card", body: S.q ? '<p class="empty">' + t("common.noMatch", { q: X.esc(S.q) }) + ' <button type="button" class="link" data-act="clear-q">' + t("common.clearSearch") + "</button></p>" : X.empty(t("dom.empty")) });
    var sample = (S.d[0] && S.d[0].sample) ? Math.max.apply(null, S.d.map(function (d) { return d.sample || 0; })) : 0;
    return X.card({ id: "dom-card", clip: true, body: '<div class="table-wrap"><table class="table"><thead><tr><th>' + t("dom.colDomain") + '</th><th class="num">' + t("dom.colReq") +
      '</th><th class="num md-only">' + t("dom.col404") + '</th><th class="num">' + t("dom.colSus") + "</th><th>" + t("dom.colGate") + '</th><th class="act lg-only"></th></tr></thead><tbody>' +
      slice.map(function (d) {
        return '<tr><td class="tall"><div class="dom-cell"><span class="dom-badge">' + X.esc(d.domain.charAt(0)) + '</span><div style="min-width:0"><p class="dom-name trunc">' + X.esc(d.domain) +
          '</p><div class="dom-bar"><span style="width:' + Math.max(2, Math.round(d.requests / max * 100)) + '%"></span></div></div></div></td>' +
          '<td class="num">' + X.fmt(d.requests) + '</td><td class="num md-only">' + X.fmt(d.c404) + "</td>" +
          '<td class="num">' + (d.suspects ? '<span class="' + (d.suspects >= 5 ? "num-warn" : "strong") + '">' + X.fmt(d.suspects) + "</span>" : '<span class="muted">0</span>') + "</td>" +
          "<td>" + modeBtn(d) + "</td>" +
          '<td class="act lg-only"><button type="button" class="btn btn-ghost btn-sm" data-detail="' + X.esc(d.domain) + '">' + t("common.details") + X.ic("chevron-right") + "</button></td></tr>";
      }).join("") + "</tbody></table></div>" + X.pagerHtml(rows.length, S.page, S.per, t("unit.domain")),
      foot: sample ? '<p class="card-sub" style="margin:0">' + t("dom.sample", { n: X.fmt(sample) }) + "</p>" : "" });
  }
  function render() { EL.innerHTML = '<div id="dom-tb">' + toolbar() + '</div><div id="dom-tbl">' + table() + "</div>"; paintCounts(); }
  function renderTable() { var el = document.getElementById("dom-tbl"); if (!el) return render(); el.innerHTML = table(); paintCounts(); placeMenu(); }
  // menu nam trong bang (khung cuon ngang + bo goc cat mat) -> dat co dinh theo vi tri nut
  function placeMenu() {
    if (!S.menu) return;
    var btn = EL.querySelector('[data-mode-for="' + S.menu.replace(/"/g, '\\"') + '"]'), pop = btn && btn.parentElement.querySelector(".pop");
    if (!btn || !pop) return;
    var r = btn.getBoundingClientRect();
    pop.style.position = "fixed"; pop.style.left = "auto"; pop.style.minWidth = "0"; pop.style.width = "260px";
    pop.style.right = Math.max(8, innerWidth - r.right) + "px";
    var below = r.bottom + 6, h = pop.offsetHeight;
    pop.style.top = (below + h > innerHeight - 8 ? Math.max(8, r.top - 6 - h) : below) + "px";
  }
  function paintCounts() {
    if (!S.d) return; var c = counts();
    EL.querySelectorAll("[data-cnt]").forEach(function (n) { n.textContent = X.fmt(c[n.dataset.cnt]); });
  }
  function load(keep) {
    if (!S.d) X.gate(S, renderTable); else if (keep) X.reloading(document.getElementById("dom-card"), true);
    X.api("/api/domains").then(function (r) {
      S.d = r.domains || [];
      if (S.st === "data") renderTable(); else X.settle(S, "data", renderTable);
    }).catch(function (e) { if (!e.auth) { if (S.d) { X.toast(X.errMsg(e), true); renderTable(); } else X.settle(S, "error", renderTable); } });
  }
  function setMode(domain, mode) {
    var d = (S.d || []).filter(function (x) { return x.domain === domain; })[0], old = d && d.mode;
    if (d) d.mode = mode; S.menu = null; renderTable();               // đổi ngay trên màn, lỗi thì trả lại
    return X.api("/api/domains/mode", { method: "POST", body: JSON.stringify({ domain: domain, mode: mode }) })
      .then(function () { X.toast(t("dom.saved", { d: domain, m: t("dom.mode." + mode) })); })
      .catch(function (e) { if (d) d.mode = old; renderTable(); X.toast(X.errMsg(e), true); });
  }

  // ---------- panel chi tiết ----------
  function openDetail(domain) {
    closeDetail(true);
    document.body.insertAdjacentHTML("beforeend", '<div class="sheet-overlay" id="dom-ov"></div><aside class="sheet" id="dom-sheet" role="dialog" aria-modal="true" aria-label="' + t("dom.detail") + '">' +
      '<div class="sheet-head"><p class="card-title trunc">' + X.esc(domain) + '</p><button type="button" class="icon-btn" data-close aria-label="' + t("common.close") + '" style="border:0;background:none">' + X.ic("x") + "</button></div>" +
      '<div class="sheet-body" id="dom-sheet-body">' + X.skRows(5) + "</div></aside>");
    requestAnimationFrame(function () { document.getElementById("dom-ov").classList.add("open"); document.getElementById("dom-sheet").classList.add("open"); });
    document.getElementById("dom-ov").addEventListener("click", function () { closeDetail(); });
    document.getElementById("dom-sheet").addEventListener("click", onSheetClick);
    X.api("/api/domains/detail?domain=" + encodeURIComponent(domain)).then(function (d) { S.detail = d; paintDetail(); })
      .catch(function (e) { document.getElementById("dom-sheet-body").innerHTML = X.errBody(); });
  }
  function paintDetail() {
    var d = S.detail, b = document.getElementById("dom-sheet-body"); if (!b) return;
    b.innerHTML = '<dl class="kv"><div><dt>' + t("dom.colReq") + "</dt><dd>" + X.fmt(d.requests) + "</dd></div><div><dt>" + t("dom.col404") + "</dt><dd>" + X.fmt(d.c404) +
      "</dd></div><div><dt>" + t("dom.colSus") + "</dt><dd>" + X.fmt(d.suspects) + "</dd></div></dl>" +
      '<div class="field"><label>' + t("dom.colGate") + '</label><div class="seg">' + MODES.map(function (m) { return '<button type="button" data-sheet-mode="' + m + '" aria-pressed="' + (d.mode === m) + '">' + t("dom.mode." + m) + "</button>"; }).join("") + "</div>" +
      '<p class="set-desc">' + t("dom.modeDesc." + d.mode) + "</p></div>" +
      '<div class="field"><label for="dom-th">' + t("dom.threshold") + '</label><div class="inline"><div class="w-num"><input class="input" id="dom-th" type="number" min="1" value="' + d.threshold + '"></div><span class="saved-slot"></span></div></div>' +
      "<div><p class=\"set-title\" style=\"padding:0 0 8px\">" + t("dom.top") + "</p>" +
      (d.top && d.top.length ? '<ul class="rows" style="margin:0 -20px">' + d.top.map(function (s) {
        return '<li class="row hov"><div class="row-main">' + X.mono(s.ip) + '<p class="row-sub trunc">' + t("dash.needRow", { c404: X.fmt(s.c404), sens: X.fmt(s.sensitive) }) + "</p></div>" +
          '<span class="score">' + X.fmt(s.score) + "<small>" + t("common.points") + "</small></span>" +
          '<button type="button" class="btn btn-danger btn-sm" data-ban="' + X.esc(s.ip) + '">' + t("bl.block") + "</button></li>";
      }).join("") + "</ul>" : X.empty(t("dom.topEmpty"))) + "</div>";
    var th = document.getElementById("dom-th");
    th.addEventListener("change", function () {
      X.api("/api/domains/threshold", { method: "POST", body: JSON.stringify({ domain: d.domain, threshold: +th.value }) }).then(function (r) {
        d.threshold = r.threshold; var slot = th.closest(".inline").querySelector(".saved-slot");
        slot.innerHTML = '<span class="saved">' + X.ic("check") + t("common.saved") + "</span>"; setTimeout(function () { slot.innerHTML = ""; }, 2500);
      }).catch(function (e) { th.value = d.threshold; X.toast(X.errMsg(e), true); });
    });
  }
  function onSheetClick(e) {
    if (e.target.closest("[data-close]")) return closeDetail();
    var m = e.target.closest("[data-sheet-mode]");
    if (m) { var d = S.detail; setMode(d.domain, m.dataset.sheetMode).then(function () { d.mode = m.dataset.sheetMode; paintDetail(); }); return; }
    var b = e.target.closest("[data-ban]"); if (b) X.ban([b.dataset.ban]);
  }
  function closeDetail(now) {
    var ov = document.getElementById("dom-ov"), sh = document.getElementById("dom-sheet");
    if (!sh) return;
    if (now) { ov.remove(); sh.remove(); return; }
    ov.classList.remove("open"); sh.classList.remove("open");
    setTimeout(function () { ov.remove(); sh.remove(); }, 360);
  }

  var qTimer;
  function bind() {
    EL.addEventListener("click", function (e) {
      var f = e.target.closest("[data-filter]");
      if (f) { S.filter = f.dataset.filter; S.page = 1; EL.querySelectorAll("[data-filter]").forEach(function (x) { x.setAttribute("aria-selected", String(x === f)); }); renderTable(); return; }
      var mb = e.target.closest("[data-mode-for]");
      if (mb) { S.menu = S.menu === mb.dataset.modeFor ? null : mb.dataset.modeFor; renderTable(); return; }
      var sm = e.target.closest("[data-set-mode]");
      if (sm) { setMode(sm.dataset.domain, sm.dataset.setMode); return; }
      var dt = e.target.closest("[data-detail]");
      if (dt) { openDetail(dt.dataset.detail); return; }
      var b = e.target.closest("[data-act]");
      if (b && b.dataset.act === "page") { S.page = +b.dataset.p; renderTable(); return; }
      if (b && b.dataset.act === "retry") { load(false); return; }
      if (b && b.dataset.act === "clear-q") { S.q = ""; var qi = document.getElementById("dom-q"); if (qi) qi.value = ""; renderTable(); return; }
      if (S.menu && !e.target.closest(".dd")) { S.menu = null; renderTable(); }
    });
    EL.addEventListener("input", function (e) {
      if (e.target.id !== "dom-q") return;
      clearTimeout(qTimer); var v = e.target.value.trim();
      qTimer = setTimeout(function () { S.q = v; S.page = 1; renderTable(); }, 150);
    });
    addEventListener("scroll", function () { if (S.menu) { S.menu = null; renderTable(); } }, true);
    document.addEventListener("keydown", function (e) {
      if (e.key !== "Escape") return;
      if (document.getElementById("dom-sheet")) closeDetail();
      else if (S.menu) { S.menu = null; renderTable(); }
    });
  }
  window.E2BPages = window.E2BPages || {};
  window.E2BPages.domains = {
    show: function (el, ctx) {
      X = ctx;
      if (EL !== el) { EL = el; bind(); }
      render();
      load(!!S.d);
    }
  };
})();
