/* Màn Nhật ký audit — nạp khi mở tới. Ai làm gì, lúc nào, từ IP nào, kết quả ra sao. */
(function () {
  "use strict";
  var X, EL, S = { st: "wait", d: null, group: "", days: 7, q: "", page: 1, per: 10, ddOpen: false };
  var GROUPS = [["", "au.all", "all"], ["login", "au.login", "login"], ["ban", "au.ban", "ban"], ["whitelist", "au.whitelist", "whitelist"], ["settings", "au.settings", "settings"], ["account", "au.account", "account"], ["ddos", "au.ddos", "ddos"]];
  var DAYS = [[1, "au.days1"], [7, "au.days7"], [30, "au.days30"], [90, "au.days90"]];
  var ICON = { "login": ["log-in", "ok"], "login-fail": ["shield-x", "danger"], "logout-all": ["log-out", ""], "ban": ["shield-ban", "danger"], "unban": ["shield-check", "ok"],
    "rate-alert": ["zap", "warn"], "whitelist-add": ["list-checks", "ok"], "whitelist-remove": ["list-checks", ""], "settings": ["settings", ""], "gate-mode": ["globe-lock", ""],
    "password-change": ["user-round", ""], "token-regen": ["user-round", ""], "reset-password": ["user-round", ""], "account-reset": ["user-round", ""] };
  var isIp = function (s) { return /^[0-9a-f.:/]+$/i.test(s || ""); };
  function t(k, o) { return X.t(k, o); }

  function toolbar() {
    var c = (S.d && S.d.counts) || {};
    var curDays = DAYS.filter(function (d) { return d[0] === S.days; })[0];
    return '<div class="filters"><div class="chips"><div class="tabs">' + GROUPS.map(function (g) {
      return '<button type="button" class="tab" data-group="' + g[0] + '" aria-selected="' + (S.group === g[0]) + '">' + t(g[1]) +
        (c[g[2]] != null ? '<span class="n">' + X.fmt(c[g[2]]) + "</span>" : "") + "</button>";
    }).join("") + '</div></div><div class="filter-tools">' +
      '<div class="dd" id="au-dd"><button type="button" class="btn btn-outline dd-btn" data-act="dd" aria-haspopup="listbox" aria-expanded="' + S.ddOpen + '">' + t(curDays[1]) + X.ic("chevron-down", "muted") + "</button>" +
      (S.ddOpen ? '<div class="pop menu" role="listbox">' + DAYS.map(function (d) {
        return '<button type="button" class="menu-item" role="option" data-days="' + d[0] + '" aria-checked="' + (d[0] === S.days) + '">' + X.ic("check", "i-check") + "<span>" + t(d[1]) + "</span></button>";
      }).join("") + "</div>" : "") + "</div>" +
      '<label class="search">' + X.ic("search") + '<input class="input" id="au-q" type="text" autocomplete="off" placeholder="' + t("au.search") + '" value="' + X.esc(S.q) + '"></label>' +
      '<button type="button" class="btn btn-outline" data-act="csv" title="' + t("au.csv") + '">' + X.ic("download") + '<span class="sm-hide">' + t("au.csv") + "</span></button></div></div>";
  }
  function rowHtml(r) {
    var m = ICON[r.type] || ["activity", ""], tone = m[1] === "danger" ? "color:var(--danger)" : m[1] === "ok" ? "color:var(--success)" : m[1] === "warn" ? "color:var(--warning)" : "color:var(--muted)";
    var label = t("ev." + r.type), target = r.ip || r.detail || "", when = X.timeLabel(r.ts, true);
    var targetHtml = target ? (isIp(target) ? X.mono(target) : '<span class="muted">' + X.esc(target) + "</span>") : X.DASH;
    var actor = r.actor_ip ? (isIp(r.actor_ip) ? X.mono(r.actor_ip) : X.esc(r.actor_ip)) : '<span class="muted">' + t("au.server") + "</span>";
    return "<tr><td class=\"sm-cell muted tnum\" style=\"white-space:nowrap\">" + when + "</td>" +
      '<td><span style="display:inline-flex;align-items:center;gap:8px;white-space:nowrap"><span style="' + tone + ';display:inline-flex">' + X.ic(m[0]) + "</span>" + X.esc(label) + "</span>" +
      '<p class="row-sub trunc au-sub" style="padding-left:24px">' + when + (target ? " · " + X.esc(target) : "") + "</p></td>" +
      '<td class="sm-cell trunc" style="max-width:260px">' + targetHtml + (r.ip && r.detail && r.type === "rate-alert" ? '<p class="row-sub">' + X.esc(r.detail) + "</p>" : "") + "</td>" +
      '<td class="md-only">' + actor + "</td>" +
      '<td style="text-align:right">' + (r.result === "fail" ? X.pill(t("au.fail"), "danger") : X.pill(t("au.ok"), "ok")) + "</td></tr>";
  }
  function table() {
    if (S.st === "wait") return '<div style="min-height:420px"></div>';
    if (S.st === "loading") return X.card({ clip: true, body: '<div style="padding-top:20px">' + X.skRows(8) + "</div>" });
    if (S.st === "error") return X.card({ body: X.errBody() });
    var items = S.d.items || [];
    if (!items.length) return X.card({ id: "au-card", body: S.q ? '<p class="empty">' + t("common.noMatch", { q: X.esc(S.q) }) + ' <button type="button" class="link" data-act="clear-q">' + t("common.clearSearch") + "</button></p>" : X.empty(t("au.empty")) });
    return X.card({ id: "au-card", clip: true, body: '<div class="table-wrap"><table class="table au-table"><thead><tr><th class="sm-cell">' + t("au.colTime") + "</th><th>" + t("au.colAct") +
      '</th><th class="sm-cell">' + t("au.colTarget") + '</th><th class="md-only">' + t("au.colActor") + '</th><th style="text-align:right">' + t("au.colRes") + "</th></tr></thead><tbody>" +
      items.map(rowHtml).join("") + "</tbody></table></div>" + X.pagerHtml(S.d.total, S.page, S.per, t("unit.event")) });
  }
  // thanh loc ve mot lan (giu con tro o o tim); du lieu ve chi ve lai bang + so dem
  function render() { EL.innerHTML = '<div id="au-tb">' + toolbar() + '</div><div id="au-tbl">' + table() + "</div>"; }
  function renderTable() {
    var tbl = document.getElementById("au-tbl"); if (!tbl) { render(); return; }
    tbl.innerHTML = table();
    var c = (S.d && S.d.counts) || {};
    GROUPS.forEach(function (g) {
      var b = EL.querySelector('[data-group="' + g[0] + '"]'); if (!b || c[g[2]] == null) return;
      var n = b.querySelector(".n"); if (!n) { n = document.createElement("span"); n.className = "n"; b.appendChild(n); }
      n.textContent = X.fmt(c[g[2]]);
    });
  }
  function renderToolbar() { var tb = document.getElementById("au-tb"); if (tb) tb.innerHTML = toolbar(); else render(); }
  function query(keepOld) {
    if (!S.d) X.gate(S, renderTable); else if (keepOld) X.reloading(document.getElementById("au-card"), true);
    var p = new URLSearchParams({ group: S.group, days: S.days, q: S.q, page: S.page, per: S.per });
    var mine = (S.req = (S.req || 0) + 1);
    X.api("/api/audit?" + p).then(function (d) {
      if (mine !== S.req) return;           // phản hồi cũ về sau thì bỏ
      S.d = d;
      if (S.st === "data") renderTable(); else X.settle(S, "data", renderTable);
    }).catch(function (e) { if (!e.auth) { if (S.d) { X.toast(X.errMsg(e), true); renderTable(); } else X.settle(S, "error", renderTable); } });
  }
  function csv() {
    var p = new URLSearchParams({ group: S.group, days: S.days, q: S.q });
    var tok = localStorage.getItem("e2b_token") || "";
    fetch("/api/audit.csv?" + p, { headers: { Authorization: "Bearer " + tok }, credentials: "same-origin" }).then(function (r) {
      if (!r.ok) throw new Error(); return r.blob();
    }).then(function (b) {
      var a = document.createElement("a"); a.href = URL.createObjectURL(b); a.download = "evil2ban-audit.csv"; a.click();
      setTimeout(function () { URL.revokeObjectURL(a.href); }, 1000);
    }).catch(function () { X.toast(t("common.netFail"), true); });
  }
  var qTimer;
  function bind() {
    EL.addEventListener("click", function (e) {
      var g = e.target.closest("[data-group]");
      if (g) { S.group = g.dataset.group; S.page = 1; EL.querySelectorAll("[data-group]").forEach(function (x) { x.setAttribute("aria-selected", String(x === g)); }); query(true); return; }
      var dd = e.target.closest("[data-days]");
      if (dd) { S.days = +dd.dataset.days; S.page = 1; S.ddOpen = false; renderToolbar(); query(true); return; }
      var b = e.target.closest("[data-act]");
      if (!b) { if (S.ddOpen && !e.target.closest("#au-dd")) { S.ddOpen = false; renderToolbar(); } return; }
      var act = b.dataset.act;
      if (act === "dd") { S.ddOpen = !S.ddOpen; renderToolbar(); }
      else if (act === "page") { S.page = +b.dataset.p; query(true); }
      else if (act === "csv") csv();
      else if (act === "clear-q") { S.q = ""; S.page = 1; var qi = document.getElementById("au-q"); if (qi) qi.value = ""; query(true); }
      else if (act === "retry") query(false);
    });
    EL.addEventListener("input", function (e) {
      if (e.target.id !== "au-q") return;
      S.q = e.target.value.trim(); S.page = 1;
      clearTimeout(qTimer); qTimer = setTimeout(function () { query(true); }, 300);
    });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape" && S.ddOpen) { S.ddOpen = false; renderToolbar(); } });
  }
  window.E2BPages = window.E2BPages || {};
  window.E2BPages.audit = {
    show: function (el, ctx) {
      X = ctx;
      if (EL !== el) { EL = el; bind(); }
      render();
      query(!!S.d);
    }
  };
})();
