/* Evil2Ban dashboard SPA. Khong framework, khong CDN. */
(function () {
  "use strict";
  var TOKEN = localStorage.getItem("e2b_token") || "";
  // token tren URL (?token=...) tu link in ra khi cai
  var u = new URLSearchParams(location.search);
  if (u.get("token")) { TOKEN = u.get("token"); localStorage.setItem("e2b_token", TOKEN);
    history.replaceState({}, "", location.pathname); }

  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  function el(tag, cls, html) { var e = document.createElement(tag); if (cls) e.className = cls; if (html != null) e.innerHTML = html; return e; }
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) { return ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]); }); }

  function api(path, opts) {
    opts = opts || {};
    opts.headers = Object.assign({ "Content-Type": "application/json" }, opts.headers || {});
    if (TOKEN) opts.headers["Authorization"] = "Bearer " + TOKEN;
    return fetch(path, opts).then(function (r) {
      if (r.status === 401) { showLogin(); throw new Error("unauthorized"); }
      return r.json().then(function (j) { if (!r.ok) throw Object.assign(new Error(j.detail || r.statusText), { detail: j.detail }); return j; });
    });
  }
  function toast(msg, err) {
    var t = el("div", "toast" + (err ? " err" : ""), esc(msg)); document.body.appendChild(t);
    setTimeout(function () { t.remove(); }, 3500);
  }

  // ---------------- login ----------------
  function showLogin() { $("#login").classList.remove("hidden"); }
  function hideLogin() { $("#login").classList.add("hidden"); }
  $("#login-form").addEventListener("submit", function (e) {
    e.preventDefault();
    var body = JSON.stringify({ username: $("#lg-user").value, password: $("#lg-pass").value });
    fetch("/api/login", { method: "POST", headers: { "Content-Type": "application/json" }, body: body })
      .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }); })
      .then(function (x) {
        if (!x.ok) { $("#lg-err").textContent = x.j.detail || "Dang nhap that bai"; return; }
        TOKEN = x.j.token; localStorage.setItem("e2b_token", TOKEN);
        $("#lg-err").textContent = ""; hideLogin(); route();
      }).catch(function () { $("#lg-err").textContent = "Loi ket noi"; });
  });
  $("#lg-reset").addEventListener("click", function () {
    var user = $("#lg-user").value;
    fetch("/api/reset-password", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ username: user }) })
      .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }); })
      .then(function (x) { $("#lg-err").textContent = x.ok ? "Da gui mat khau moi qua email." : (x.j.detail || "Loi"); });
  });
  $("#logout").addEventListener("click", function () { localStorage.removeItem("e2b_token"); TOKEN = ""; showLogin(); });

  // ---------------- routing ----------------
  var VIEWS = ["dashboard", "monitor", "blacklist"];
  function go(v) { location.hash = v; }
  window.addEventListener("hashchange", route);
  function route() {
    var v = (location.hash || "#dashboard").slice(1);
    if (VIEWS.indexOf(v) < 0) v = "dashboard";
    $$(".nav button").forEach(function (b) { b.classList.toggle("active", b.dataset.v === v); });
    $$(".view").forEach(function (s) { s.classList.toggle("hidden", s.id !== "view-" + v); });
    $("#title").textContent = { dashboard: "Dashboard", monitor: "Monitor", blacklist: "Blacklist IP" }[v];
    if (v === "dashboard") loadDashboard();
    if (v === "monitor") loadMonitor();
    if (v === "blacklist") loadBlacklist();
  }
  $$(".nav button").forEach(function (b) { b.addEventListener("click", function () { go(b.dataset.v); }); });

  // ---------------- dashboard ----------------
  function stat(label, value, sub, cls) {
    return '<div class="card stat ' + (cls || "") + '"><div class="label">' + label +
      '</div><div class="value">' + value + '</div>' + (sub ? '<div class="sub">' + sub + '</div>' : '') + '</div>';
  }
  function loadDashboard() {
    api("/api/overview").then(function (o) {
      $("#meta").textContent = o.host + " · " + o.ts + " · v" + o.version + (o.auto_ban ? " · AUTO-BAN ON" : " · auto-ban off");
      $("#stats").innerHTML =
        stat("Dang chan", o.banned_now, "jail sshd", o.banned_now ? "alert" : "") +
        stat("Tong da chan", o.total_banned, "luy ke") +
        stat("SSH that bai 6h", o.ssh_failed_6h, "brute-force", o.ssh_failed_6h > 50 ? "warn" : "") +
        stat("Request (mau)", o.requests, (o.cdn_hidden || 0) + " sau CDN") +
        stat("IP that", o.unique_ips, "ngoai Cloudflare") +
        stat("Nghi van", o.suspects, "scan/404", o.suspects ? "warn" : "");
    }).catch(function () { });
    loadChart();
  }

  var chartState = { gran: "daily", metric: "requests", type: "line" };
  function loadChart() {
    var path = chartState.gran === "daily" ? "/api/series/daily?days=30&metric=" : "/api/series/monthly?months=12&metric=";
    api(path + chartState.metric).then(function (s) {
      var cv = $("#chart");
      var labels = s.line.map(function (p) { return p.t; });
      if (chartState.type === "candles") {
        E2BChart.render(cv, { type: "candles", labels: labels, ohlc: s.candles.map(function (c) { return { o: c.o, h: c.h, l: c.l, c: c.c }; }) });
      } else {
        E2BChart.render(cv, { type: chartState.type, labels: labels, data: s.line.map(function (p) { return p.v; }) });
      }
    }).catch(function () { });
  }
  $$("#chart-type button").forEach(function (b) {
    b.addEventListener("click", function () {
      chartState.type = b.dataset.t; segActivate("#chart-type", b); loadChart();
    });
  });
  $$("#chart-gran button").forEach(function (b) {
    b.addEventListener("click", function () { chartState.gran = b.dataset.g; segActivate("#chart-gran", b); loadChart(); });
  });
  $("#chart-metric").addEventListener("change", function () { chartState.metric = this.value; loadChart(); });
  function segActivate(sel, btn) { $$(sel + " button").forEach(function (x) { x.classList.remove("active"); }); btn.classList.add("active"); }

  // ---------------- monitor ----------------
  function rowsTable(cols, rows, render) {
    var t = "<table><thead><tr>" + cols.map(function (c) { return "<th>" + c + "</th>"; }).join("") + "</tr></thead><tbody>";
    t += rows.map(render).join("") || ('<tr><td colspan="' + cols.length + '" style="color:var(--muted)">—</td></tr>');
    return t + "</tbody></table>";
  }
  function loadMonitor() {
    api("/api/ssh").then(function (s) {
      $("#mon-ssh").innerHTML = rowsTable(["IP", "Nuoc", "Lan sai"], s.top, function (r) {
        return '<tr><td class="ip">' + esc(r.ip) + '</td><td>' + esc(r.country || "") + '</td><td>' + r.n + '</td></tr>';
      });
      $("#mon-users").innerHTML = rowsTable(["User bi thu", "Lan"], s.top_users, function (r) {
        return "<tr><td>" + esc(r.u) + "</td><td>" + r.n + "</td></tr>";
      });
    }).catch(function () { });
    api("/api/traffic").then(function (a) {
      $("#mon-traffic").innerHTML = rowsTable(["IP", "Nuoc", "Request"], a.top_traffic, function (r) {
        return '<tr><td class="ip">' + esc(r.ip) + '</td><td>' + esc(r.country || "") + '</td><td>' + r.total + '</td></tr>';
      });
      $("#mon-ua").innerHTML = rowsTable(["User-Agent", "Lan"], a.top_ua, function (r) {
        return "<tr><td>" + esc(r.ua) + "</td><td>" + r.n + "</td></tr>";
      });
      var dv = a.devices || {};
      $("#mon-dev").innerHTML = '<span class="tag">desktop ' + (dv.desktop || 0) + '</span> <span class="tag">mobile ' + (dv.mobile || 0) + '</span> <span class="tag">bot ' + (dv.bot || 0) + '</span>';
      var stx = Object.keys(a.status || {}).map(function (k) { return '<span class="tag">' + k + " " + a.status[k] + "</span>"; }).join(" ");
      $("#mon-status").innerHTML = stx || "—";
    }).catch(function () { });
    api("/api/events?limit=60").then(function (e) {
      $("#mon-events").innerHTML = rowsTable(["Thoi gian", "Loai", "IP", "Ly do"], e.events, function (r) {
        var d = new Date(r.ts * 1000).toISOString().replace("T", " ").slice(0, 19);
        var cls = r.type === "ban" ? "red" : r.type === "unban" ? "grn" : "";
        return '<tr><td>' + d + '</td><td><span class="tag ' + cls + '">' + esc(r.type) + '</span></td><td class="ip">' + esc(r.ip || "") + '</td><td>' + esc(r.reason || "") + '</td></tr>';
      });
    }).catch(function () { });
  }

  // ---------------- blacklist ----------------
  var blState = { banned: [], suspects: [], wl: [], q: "", page: 1, per: 12, sel: {} };
  function loadBlacklist() {
    Promise.all([api("/api/banned"), api("/api/traffic"), api("/api/whitelist")]).then(function (res) {
      blState.banned = res[0].banned || [];
      blState.suspects = res[1].suspects || [];
      blState.wl = res[2].entries || [];
      renderBlacklist(); renderSuspects(); renderWL();
    }).catch(function () { });
  }
  $("#bl-search").addEventListener("input", function () { blState.q = this.value.trim(); blState.page = 1; renderBlacklist(); });

  function filteredBanned() {
    var q = blState.q.toLowerCase();
    return blState.banned.filter(function (r) { return !q || r.ip.toLowerCase().indexOf(q) >= 0 || (r.country || "").toLowerCase().indexOf(q) >= 0; });
  }
  function renderBlacklist() {
    var rows = filteredBanned();
    var pages = Math.max(1, Math.ceil(rows.length / blState.per));
    blState.page = Math.min(blState.page, pages);
    var start = (blState.page - 1) * blState.per;
    var slice = rows.slice(start, start + blState.per);
    var selCount = Object.keys(blState.sel).filter(function (k) { return blState.sel[k]; }).length;
    $("#bl-bulk").innerHTML = selCount
      ? '<b>' + selCount + '</b> da chon <button class="btn ok sm" id="bl-unban-sel">Go chan hang loat</button> <button class="btn sm" id="bl-clear-sel">Bo chon</button>'
      : '<span style="color:var(--muted)">Chon IP de thao tac hang loat. Tong dang chan: <b>' + blState.banned.length + '</b></span>';
    var t = '<table><thead><tr><th style="width:36px"><input type="checkbox" class="checkbox" id="bl-all"></th><th>IP</th><th>Nuoc</th><th></th></tr></thead><tbody>';
    t += slice.map(function (r) {
      return '<tr><td><input type="checkbox" class="checkbox bl-cb" data-ip="' + esc(r.ip) + '"' + (blState.sel[r.ip] ? " checked" : "") + '></td>' +
        '<td class="ip">' + esc(r.ip) + '</td><td>' + esc(r.country || "") + '</td>' +
        '<td><button class="btn ok sm" data-unban="' + esc(r.ip) + '">Go chan</button></td></tr>';
    }).join("") || '<tr><td colspan="4" style="color:var(--muted)">Khong co IP nao bi chan.</td></tr>';
    t += "</tbody></table>";
    $("#bl-table").innerHTML = t;
    $("#bl-pager").innerHTML = 'Trang ' + blState.page + "/" + pages +
      ' <button class="btn sm" id="bl-prev"' + (blState.page <= 1 ? " disabled" : "") + '>‹</button>' +
      ' <button class="btn sm" id="bl-next"' + (blState.page >= pages ? " disabled" : "") + '>›</button>';
    wireBlacklist();
  }
  function wireBlacklist() {
    var prev = $("#bl-prev"), next = $("#bl-next");
    if (prev) prev.onclick = function () { blState.page--; renderBlacklist(); };
    if (next) next.onclick = function () { blState.page++; renderBlacklist(); };
    var all = $("#bl-all");
    if (all) all.onchange = function () { $$(".bl-cb").forEach(function (cb) { cb.checked = all.checked; blState.sel[cb.dataset.ip] = all.checked; }); renderBlacklist(); };
    $$(".bl-cb").forEach(function (cb) { cb.onchange = function () { blState.sel[cb.dataset.ip] = cb.checked; renderBlacklist(); }; });
    $$("[data-unban]").forEach(function (b) { b.onclick = function () { unban([b.dataset.unban]); }; });
    var us = $("#bl-unban-sel"); if (us) us.onclick = function () { unban(Object.keys(blState.sel).filter(function (k) { return blState.sel[k]; })); };
    var cs = $("#bl-clear-sel"); if (cs) cs.onclick = function () { blState.sel = {}; renderBlacklist(); };
  }
  function unban(ips) {
    if (!ips.length) return;
    api("/api/unban-bulk", { method: "POST", body: JSON.stringify({ ips: ips }) }).then(function (r) {
      var ok = r.results.filter(function (x) { return x.ok; }).length;
      toast("Da go chan " + ok + "/" + ips.length + " IP"); blState.sel = {}; loadBlacklist();
    }).catch(function (e) { toast(e.message, true); });
  }
  function ban(ips) {
    if (!ips.length) return;
    api("/api/ban-bulk", { method: "POST", body: JSON.stringify({ ips: ips }) }).then(function (r) {
      var ok = r.results.filter(function (x) { return x.ok; }).length;
      var bad = r.results.filter(function (x) { return !x.ok; });
      toast("Da chan " + ok + "/" + ips.length + " IP" + (bad.length ? " (" + bad.length + " bi tu choi)" : ""), bad.length > 0 && ok === 0);
      loadBlacklist();
    }).catch(function (e) { toast(e.message, true); });
  }

  var suState = { sel: {} };
  function renderSuspects() {
    var selCount = Object.keys(suState.sel).filter(function (k) { return suState.sel[k]; }).length;
    $("#su-bulk").innerHTML = selCount ? '<b>' + selCount + '</b> da chon <button class="btn danger sm" id="su-ban-sel">Chan hang loat</button>' : '<span style="color:var(--muted)">IP nghi van tu phan tich log (da loai Cloudflare + whitelist).</span>';
    var t = '<table><thead><tr><th style="width:36px"></th><th>IP</th><th>Nuoc</th><th>404</th><th>Scan</th><th>Nhay cam</th><th>Diem</th><th>User-Agent</th><th></th></tr></thead><tbody>';
    t += blState.suspects.map(function (r) {
      return '<tr><td><input type="checkbox" class="checkbox su-cb" data-ip="' + esc(r.ip) + '"' + (suState.sel[r.ip] ? " checked" : "") + '></td>' +
        '<td class="ip">' + esc(r.ip) + '</td><td>' + esc(r.country || "") + '</td><td>' + r.c404 + '</td>' +
        '<td>' + (r.scanner_ua ? '<span class="tag red">yes</span>' : '-') + '</td><td>' + r.sensitive + '</td>' +
        '<td><b>' + r.score + '</b></td><td style="max-width:260px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">' + esc(r.ua) + '</td>' +
        '<td><button class="btn danger sm" data-ban="' + esc(r.ip) + '">Chan</button></td></tr>';
    }).join("") || '<tr><td colspan="9" style="color:var(--muted)">Khong co IP nghi van.</td></tr>';
    $("#su-table").innerHTML = t + "</tbody></table>";
    $$(".su-cb").forEach(function (cb) { cb.onchange = function () { suState.sel[cb.dataset.ip] = cb.checked; renderSuspects(); }; });
    $$("[data-ban]").forEach(function (b) { b.onclick = function () { ban([b.dataset.ban]); }; });
    var bs = $("#su-ban-sel"); if (bs) bs.onclick = function () { ban(Object.keys(suState.sel).filter(function (k) { return suState.sel[k]; })); suState.sel = {}; };
  }
  function renderWL() {
    var t = '<table><thead><tr><th>Entry</th><th>Loai</th><th>Nguon</th><th>Ghi chu</th><th></th></tr></thead><tbody>';
    t += blState.wl.map(function (r) {
      var cf = r.source === "cloudflare";
      return '<tr><td class="ip">' + esc(r.entry) + '</td><td>' + (r.is_cidr ? "CIDR" : "IP") + '</td>' +
        '<td><span class="tag ' + (cf ? "cf" : r.source === "owner" ? "grn" : "") + '">' + esc(r.source) + '</span></td>' +
        '<td>' + esc(r.note || "") + '</td><td>' + (r.source === "owner" ? '<button class="btn sm" data-wlrm="' + esc(r.entry) + '">Xoa</button>' : '') + '</td></tr>';
    }).join("");
    $("#wl-table").innerHTML = t + "</tbody></table>";
    $$("[data-wlrm]").forEach(function (b) {
      b.onclick = function () {
        api("/api/whitelist/remove", { method: "POST", body: JSON.stringify({ entry: b.dataset.wlrm }) })
          .then(function () { toast("Da xoa khoi whitelist"); loadBlacklist(); }).catch(function (e) { toast(e.message, true); });
      };
    });
  }
  $("#wl-add").addEventListener("click", function () {
    var v = $("#wl-input").value.trim(); if (!v) return;
    api("/api/whitelist/add", { method: "POST", body: JSON.stringify({ entry: v, note: "owner" }) })
      .then(function () { $("#wl-input").value = ""; toast("Da them vao whitelist"); loadBlacklist(); })
      .catch(function (e) { toast(e.message, true); });
  });

  // auto-refresh dashboard/monitor moi 20s
  setInterval(function () {
    var v = (location.hash || "#dashboard").slice(1);
    if (v === "dashboard") loadDashboard();
    else if (v === "monitor") loadMonitor();
  }, 20000);

  // khoi dong: thu goi overview; 401 -> login
  api("/api/overview").then(function () { hideLogin(); route(); }).catch(function () { route(); });
})();
