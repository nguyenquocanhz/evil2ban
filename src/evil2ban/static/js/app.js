/* Evil2Ban dashboard SPA. Không framework, không CDN. */
(function () {
  "use strict";
  var I18N = window.E2Bi18n;
  var t = function (k, v) { return I18N.t(k, v); };
  var TOKEN = localStorage.getItem("e2b_token") || "";
  // token trên URL (?token=...) từ link in ra khi cài
  var u = new URLSearchParams(location.search);
  if (u.get("token")) { TOKEN = u.get("token"); localStorage.setItem("e2b_token", TOKEN);
    history.replaceState({}, "", location.pathname + location.hash); }

  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) { return ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]); }); }
  function fmt(n) { return n == null ? "—" : Number(n).toLocaleString(I18N.locale()); }
  function pad2(n) { return (n < 10 ? "0" : "") + n; }
  var ic = function (name, cls) { return window.E2BIcon ? E2BIcon(name, cls) : ""; };
  function mono(ip) { return '<span class="mono">' + esc(ip) + "</span>"; }
  var DASH = '<span class="muted">—</span>';

  function api(path, opts) {
    opts = opts || {};
    opts.headers = Object.assign({ "Content-Type": "application/json" }, opts.headers || {});
    if (TOKEN) opts.headers["Authorization"] = "Bearer " + TOKEN;
    opts.credentials = "same-origin";
    return fetch(path, opts).then(function (r) {
      if (r.status === 401 && path !== "/api/login") { showLogin(); throw Object.assign(new Error("unauthorized"), { auth: true, code: "unauthorized" }); }
      return r.json().catch(function () { return {}; }).then(function (j) {
        if (!r.ok) throw Object.assign(new Error(j.detail || r.statusText), { code: j.code, detail: j.detail, status: r.status });
        return j;
      });
    });
  }
  function errMsg(e) { return I18N.err(e && e.code, e && e.detail); }

  // ---------------- thông báo (SweetAlert2) ----------------
  var Toast = (window.Swal && Swal.mixin({
    toast: true, position: "top-end", showConfirmButton: false, timer: 3200, timerProgressBar: true,
    didOpen: function (el) { el.addEventListener("mouseenter", Swal.stopTimer); el.addEventListener("mouseleave", Swal.resumeTimer); }
  })) || null;
  function toast(msg, err) {
    if (Toast) { Toast.fire({ icon: err ? "error" : "success", title: msg }); return; }
    alert(msg);
  }
  function notify(icon, title, text) {
    if (window.Swal) return Swal.fire({ icon: icon, title: title, text: text || "", confirmButtonText: t("common.ok") });
    alert(title + (text ? "\n" + text : ""));
  }
  function confirmDanger(title, text, confirmText) {
    if (!window.Swal) return Promise.resolve(window.confirm(title));
    return Swal.fire({
      icon: "warning", title: title, text: text || "", showCancelButton: true,
      confirmButtonText: confirmText || t("common.ok"), cancelButtonText: t("common.cancel"),
      focusCancel: true, reverseButtons: true, customClass: { confirmButton: "e2b-danger" }
    }).then(function (r) { return !!r.isConfirmed; });
  }

  // ---------------- chữ + icon tĩnh ----------------
  function applyI18n(root) {
    $$("[data-i18n]", root).forEach(function (el) { el.textContent = t(el.dataset.i18n); });
    $$("[data-i18n-ph]", root).forEach(function (el) { el.placeholder = t(el.dataset.i18nPh); });
    $$("[data-i18n-title]", root).forEach(function (el) { el.title = t(el.dataset.i18nTitle); el.setAttribute("aria-label", t(el.dataset.i18nTitle)); });
    $$("[data-lang-seg] button").forEach(function (b) { b.setAttribute("aria-pressed", b.dataset.lang === I18N.lang ? "true" : "false"); });
    $("#lg-foot").textContent = t(location.protocol === "https:" ? "login.footHttps" : "login.foot");
  }
  $$("[data-icon]").forEach(function (el) { el.outerHTML = ic(el.dataset.icon, el.dataset.cls); });

  // ---------------- khối dùng chung ----------------
  function card(o) {
    return '<section class="card' + (o.clip ? " clip" : "") + (o.cls ? " " + o.cls : "") + '"' + (o.id ? ' id="' + o.id + '"' : "") + ">" +
      (o.title ? '<header class="card-head"><div><h2 class="card-title">' + o.title + "</h2>" +
        (o.sub ? '<p class="card-sub">' + o.sub + "</p>" : "") + "</div>" +
        (o.aside ? '<div class="card-aside">' + o.aside + "</div>" : "") + "</header>" : "") +
      (o.body || "") + (o.foot ? '<footer class="card-foot">' + o.foot + "</footer>" : "") + "</section>";
  }
  function sk(w, h) { return '<div class="sk" style="width:' + w + ";height:" + (h || "16px") + '"></div>'; }
  function skRows(n) {
    var out = "";
    for (var i = 0; i < (n || 5); i++) out += '<div class="sk-row">' + sk(i % 2 ? "128px" : "160px") + '<div style="flex:1"></div>' + sk("48px") + "</div>";
    return '<div class="sk-rows" aria-busy="true">' + out + "</div>";
  }
  function errBody() { return '<div class="err-body"><p>' + t("common.loadFail") + '</p><button type="button" class="btn btn-outline btn-md" data-act="retry">' + t("common.retry") + "</button></div>"; }
  function empty(msg) { return '<p class="empty">' + msg + "</p>"; }
  function body(st, html, emptyMsg, isEmpty, rows) {
    if (st === "loading") return skRows(rows);
    if (st === "wait") return '<div style="min-height:' + ((rows || 5) * 32 + 20) + 'px"></div>';
    if (st === "error") return errBody();
    if (isEmpty) return empty(emptyMsg);
    return html;
  }
  function pill(txt, tone) { return '<span class="pill' + (tone ? " " + tone : "") + '">' + esc(txt) + "</span>"; }
  function cbHtml(on, act, ip) {
    return '<button type="button" class="cb" role="checkbox" aria-checked="' + (on ? "true" : "false") + '" data-act="' + act + '"' +
      (ip ? ' data-ip="' + esc(ip) + '"' : "") + ' aria-label="' + t("common.select") + '">' + ic("check") + "</button>";
  }
  function timeLabel(ts, withDay) {
    var d = new Date(ts * 1000), now = new Date(), y = new Date(now); y.setDate(now.getDate() - 1);
    var hm = pad2(d.getHours()) + ":" + pad2(d.getMinutes());
    if (d.toDateString() === now.toDateString()) return withDay ? t("common.today") + " " + hm : hm;
    if (d.toDateString() === y.toDateString()) return t("common.yesterday") + (withDay ? " " + hm : "");
    return pad2(d.getDate()) + "/" + pad2(d.getMonth() + 1) + (withDay ? " " + hm : "");
  }
  function pagerHtml(total, page, per, noun) {
    var pages = Math.max(1, Math.ceil(total / per));
    var from = total ? (page - 1) * per + 1 : 0, to = Math.min(total, page * per);
    var nums = [];
    if (pages <= 7) { for (var i = 1; i <= pages; i++) nums.push(i); }
    else {
      nums.push(1); if (page > 3) nums.push("…");
      for (var j = Math.max(2, page - 1); j <= Math.min(pages - 1, page + 1); j++) nums.push(j);
      if (page < pages - 2) nums.push("…"); nums.push(pages);
    }
    return '<div class="pager"><p>' + t("common.of", { a: fmt(from), b: fmt(to), t: fmt(total), noun: noun }) + '</p><div class="pages">' +
      '<button type="button" class="pg" data-act="page" data-p="' + (page - 1) + '"' + (page <= 1 ? " disabled" : "") + ' aria-label="' + t("common.prev") + '">' + ic("chevron-left") + "</button>" +
      nums.map(function (n) { return n === "…" ? '<span class="pg-gap">…</span>' : '<button type="button" class="pg" data-act="page" data-p="' + n + '"' + (n === page ? ' aria-current="page"' : "") + ">" + n + "</button>"; }).join("") +
      '<button type="button" class="pg" data-act="page" data-p="' + (page + 1) + '"' + (page >= pages ? " disabled" : "") + ' aria-label="' + t("common.next") + '">' + ic("chevron-right") + "</button></div></div>";
  }
  function spark(vals) {
    if (!vals || vals.length < 2) return "";
    var max = Math.max.apply(null, vals), min = Math.min.apply(null, vals), w = 96, h = 28;
    var pts = vals.map(function (v, i) { return (i / (vals.length - 1) * w).toFixed(1) + "," + (h - 2 - (v - min) / ((max - min) || 1) * (h - 4)).toFixed(1); }).join(" ");
    return '<svg class="spark" viewBox="0 0 96 28" preserveAspectRatio="none" aria-hidden="true"><polyline points="' + pts + '"/></svg>';
  }
  // khung chờ: chưa tới 300ms thì chưa vẽ; đã vẽ thì giữ ít nhất 500ms
  function gate(state, render) {
    state.st = "wait"; state.shownAt = 0; render();
    clearTimeout(state.timer);
    state.timer = setTimeout(function () { if (state.st === "wait") { state.st = "loading"; state.shownAt = Date.now(); render(); } }, 300);
  }
  function settle(state, st, render) {
    clearTimeout(state.timer);
    var wait = state.shownAt ? Math.max(0, 500 - (Date.now() - state.shownAt)) : 0;
    setTimeout(function () { state.st = st; state.shownAt = 0; render(); }, wait);
  }
  function reloading(el, on) {
    if (!el) return;
    el.classList.toggle("reloading", on);
    var bar = el.querySelector(":scope > .loadbar");
    if (on && !bar) el.insertAdjacentHTML("afterbegin", '<div class="loadbar" aria-hidden="true"></div>');
    if (!on && bar) bar.remove();
  }

  // ---------------- đăng nhập ----------------
  function showLogin() {
    stopLive();
    $("#app").classList.add("hidden"); $("#login").classList.remove("hidden");
    document.body.classList.remove("menu-open");
    setTimeout(function () { $("#lg-user").focus(); }, 0);
  }
  function showApp() { $("#login").classList.add("hidden"); $("#app").classList.remove("hidden"); }
  function setEye(shown) {
    $("#lg-eye").innerHTML = ic(shown ? "eye-off" : "eye");
    $("#lg-eye").setAttribute("aria-label", t(shown ? "login.hide" : "login.show"));
  }
  $("#lg-eye").addEventListener("click", function () { var p = $("#lg-pass"), shown = p.type === "password"; p.type = shown ? "text" : "password"; setEye(shown); });
  function loginError(msg) {
    var e = $("#lg-err"); e.textContent = msg || ""; e.classList.toggle("hidden", !msg);
    $("#lg-user").classList.toggle("bad", !!msg); $("#lg-pass").classList.toggle("bad", !!msg);
  }
  $("#login-form").addEventListener("submit", function (e) {
    e.preventDefault();
    var user = $("#lg-user").value.trim(), pass = $("#lg-pass").value;
    if (!user || !pass) { loginError(t("login.empty")); return; }
    var btn = $("#lg-submit"); btn.disabled = true; btn.setAttribute("aria-busy", "true");
    btn.innerHTML = ic("loader-circle", "spin") + t("login.busy");
    api("/api/login", { method: "POST", body: JSON.stringify({ username: user, password: pass }) }).then(function (j) {
      TOKEN = j.token; localStorage.setItem("e2b_token", TOKEN); localStorage.setItem("e2b_user", j.username || user);
      loginError(""); $("#lg-pass").value = ""; boot(); toast(t("login.ok"));
    }).catch(function (err) { var m = errMsg(err); loginError(m); toast(m, true); })
      .finally(function () { btn.disabled = false; btn.removeAttribute("aria-busy"); btn.textContent = t("login.submit"); });
  });
  $("#lg-reset").addEventListener("click", function () {
    var user = $("#lg-user").value.trim();
    if (!user) { loginError(t("login.resetNeedUser")); $("#lg-user").focus(); return; }
    confirmDanger(t("login.resetTitle"), t("login.resetText", { u: user }), t("login.resetGo")).then(function (ok) {
      if (!ok) return;
      api("/api/reset-password", { method: "POST", body: JSON.stringify({ username: user }) })
        .then(function () { notify("success", t("login.resetSent"), t("login.resetSentText")); })
        .catch(function (err) { notify("error", errMsg(err)); });
    });
  });
  function logout() {
    fetch("/api/logout", { method: "POST", credentials: "same-origin" }).catch(function () { });
    localStorage.removeItem("e2b_token"); TOKEN = ""; showLogin();
  }
  $("#logout").addEventListener("click", logout);

  // ---------------- ngôn ngữ, sáng/tối ----------------
  function themeMode() { try { return localStorage.getItem("e2b_theme") || "dark"; } catch (e) { return "dark"; } }
  function applyTheme(mode) {
    if (mode) { try { localStorage.setItem("e2b_theme", mode); } catch (e) { } }
    var m = themeMode();
    var eff = m === "system" ? (matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark") : m;
    document.documentElement.dataset.theme = eff;
    var b = $("#theme-btn"); b.innerHTML = ic(eff === "light" ? "moon" : "sun");
    b.title = t("top.theme"); b.setAttribute("aria-label", t("top.theme"));
  }
  matchMedia("(prefers-color-scheme: light)").addEventListener("change", function () { if (themeMode() === "system") applyTheme(); });
  $("#theme-btn").addEventListener("click", function () { applyTheme(document.documentElement.dataset.theme === "light" ? "dark" : "light"); if (VIEW === "settings") route(); });
  document.addEventListener("click", function (e) {
    var b = e.target.closest("[data-lang]"); if (!b || !b.closest("[data-lang-seg]")) return;
    setLang(b.dataset.lang);
  });
  function setLang(l) {
    I18N.set(l); applyI18n(); setEye($("#lg-pass").type !== "password"); renderNav(); applyTheme(); paintSbToggle();
    if (!$("#app").classList.contains("hidden")) { paintHeader(true); paintLive(); route(); }
  }

  // ---------------- sidebar: nhóm +/−, thu gọn ----------------
  var GROUPS = [
    ["nav.group.monitor", [["dashboard", "nav.dashboard", "layout-dashboard"], ["monitor", "nav.monitor", "activity"]]],
    ["nav.group.defense", [["blacklist", "nav.blacklist", "shield-ban", true], ["domains", "nav.domains", "globe-lock"]]],
    ["nav.group.system", [["audit", "nav.audit", "scroll-text"], ["settings", "nav.settings", "settings"]]]
  ];
  function closedGroups() { try { return JSON.parse(localStorage.getItem("e2b_grp") || "[]"); } catch (e) { return []; } }
  function renderNav() {
    var closed = closedGroups(), sus = OV && OV.suspects ? fmt(OV.suspects) : "";
    $("#sb-nav").innerHTML = GROUPS.map(function (g, gi) {
      var isClosed = closed.indexOf(gi) >= 0;
      return '<div class="nav-group' + (isClosed ? " closed" : "") + '" data-grp="' + gi + '">' +
        '<button type="button" class="grp-btn" data-sb-hide aria-expanded="' + !isClosed + '"><span class="sb-fade">' + t(g[0]) + "</span>" +
        '<span class="grp-ico sb-fade">' + ic("minus", "i-minus") + ic("plus", "i-plus") + '</span><span class="sb-dash" aria-hidden="true"></span></button>' +
        '<div class="grp-body"><div class="grp-inner"' + (isClosed ? " inert" : "") + ">" +
        g[1].map(function (it) {
          var count = it[3] && sus;
          return '<a class="nav-link" href="#' + it[0] + '" data-v="' + it[0] + '"' + (VIEW === it[0] ? ' aria-current="page"' : "") +
            ' title="' + esc(t(it[1]) + (count ? " · " + t("nav.suspectsTip", { n: count }) : "")) + '">' + ic(it[2]) +
            '<span class="nav-label sb-fade">' + t(it[1]) + "</span>" +
            (count ? '<span class="nav-count sb-fade" aria-hidden="true">' + count + '</span><span class="sb-dot" aria-hidden="true"></span>' : "") + "</a>";
        }).join("") + "</div></div></div>";
    }).join("");
  }
  $("#sb-nav").addEventListener("click", function (e) {
    var g = e.target.closest(".grp-btn");
    if (g) {
      var wrap = g.closest(".nav-group"), gi = +wrap.dataset.grp, closed = closedGroups(), now = !wrap.classList.contains("closed");
      wrap.classList.toggle("closed", now); g.setAttribute("aria-expanded", String(!now));
      wrap.querySelector(".grp-inner").toggleAttribute("inert", now);
      closed = closed.filter(function (x) { return x !== gi; }); if (now) closed.push(gi);
      localStorage.setItem("e2b_grp", JSON.stringify(closed));
      return;
    }
    if (e.target.closest(".nav-link")) closeMenu();
  });
  function sbCollapsed() { return localStorage.getItem("e2b_sb") === "1"; }
  function paintSbToggle() {
    var c = sbCollapsed(), b = $("#sb-toggle");
    $("#app").classList.toggle("sb-collapsed", c);
    b.innerHTML = ic(c ? "panel-left-open" : "panel-left-close");
    b.setAttribute("aria-expanded", String(!c));
    b.setAttribute("aria-label", t(c ? "sb.expand" : "sb.collapse")); b.title = t(c ? "sb.expand" : "sb.collapse") + " (Ctrl+B)";
  }
  function toggleSidebar() { localStorage.setItem("e2b_sb", sbCollapsed() ? "0" : "1"); paintSbToggle(); }
  $("#sb-toggle").addEventListener("click", toggleSidebar);
  document.addEventListener("keydown", function (e) {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "b" && !$("#app").classList.contains("hidden")) { e.preventDefault(); toggleSidebar(); }
    if (e.key === "Escape") { closeMenu(); closeBell(); }
  });
  function closeMenu() { document.body.classList.remove("menu-open"); }
  $("#burger").addEventListener("click", function () { document.body.classList.add("menu-open"); });
  $("#burger").setAttribute("aria-label", t("menu.open"));
  $("#overlay").addEventListener("click", closeMenu);

  // ---------------- header ----------------
  var OV = null;
  function paintHeader(ok) {
    var name = localStorage.getItem("e2b_user") || t("admin");
    $("#acc-name").textContent = name; $("#acc-avatar").textContent = name.charAt(0).toUpperCase();
    if (OV) { $("#sb-ver").textContent = "v" + OV.version; $("#acc-host").textContent = OV.host; }
    renderNav();
  }

  // ---------------- realtime: SSE, dự phòng hỏi lại 5 giây ----------------
  var LIVE = null, ES = null, POLL = null, gotStream = false;
  function startLive() {
    stopLive();
    if (window.EventSource) {
      gotStream = false;
      ES = new EventSource("/api/stream");
      ES.onmessage = function (ev) { gotStream = true; try { onLive(JSON.parse(ev.data)); } catch (e) { } };
      ES.onerror = function () { setLiveChip(false); if (!gotStream) { stopLive(); startPoll(); } };
      setTimeout(function () { if (!gotStream && ES) { stopLive(); startPoll(); } }, 8000);
    } else startPoll();
  }
  function startPoll() {
    var tick = function () { api("/api/live").then(onLive).catch(function () { setLiveChip(false); }); };
    tick(); POLL = setInterval(function () { if (!document.hidden) tick(); }, 5000);
  }
  function stopLive() { if (ES) { ES.close(); ES = null; } if (POLL) { clearInterval(POLL); POLL = null; } }
  function setLiveChip(on) { $("#live-chip").classList.toggle("off", !on); $("#live-text").textContent = t(on ? "top.live" : "top.offline"); }
  var seenAlert = +(localStorage.getItem("e2b_alert_seen") || 0), toastedAlert = seenAlert;
  function onLive(d) {
    LIVE = d; setLiveChip(true);
    if (OV && d.suspects != null) { OV.suspects = d.suspects; OV.banned_now = d.banned; }
    paintLive();
    var fresh = (d.alerts || []).filter(function (a) { return a.ts > toastedAlert; });
    if (fresh.length) { toastedAlert = fresh[0].ts; alertToast(fresh[0]); }
  }
  function paintLive() {
    if (!LIVE) return;
    var unseen = (LIVE.alerts || []).filter(function (a) { return a.ts > seenAlert; }).length;
    $("#bell-badge").textContent = unseen; $("#bell-badge").classList.toggle("hidden", !unseen);
    $$(".nav-count").forEach(function (n) { if (LIVE.suspects != null) n.textContent = fmt(LIVE.suspects); });
    if (VIEW === "dashboard" && DB.st === "data") paintStats();
    if (!$("#bell-pop").classList.contains("hidden")) renderBell();
  }
  function alertToast(a) {
    if (!window.Swal) return;
    Swal.fire({
      toast: true, position: "bottom-end", icon: "warning", timer: 15000, timerProgressBar: true,
      title: t("alert.title"), html: esc(t("alert.text", { ip: a.ip, rpm: fmt(a.rpm), th: fmt(a.threshold) })),
      showConfirmButton: true, showCancelButton: true, confirmButtonText: t("alert.block"), cancelButtonText: t("alert.ignore"),
      customClass: { confirmButton: "e2b-danger" }
    }).then(function (r) { if (r.isConfirmed) ban([a.ip]); });
  }
  function renderBell() {
    var list = (LIVE && LIVE.alerts) || [];
    $("#bell-pop").innerHTML = '<p class="pop-head">' + t("alert.menu") + "</p>" +
      (list.length ? list.slice(0, 6).map(function (a) {
        return '<div class="pop-item"><span class="ico-tone warn">' + ic("zap") + '</span><div style="flex:1;min-width:0">' + mono(a.ip) +
          '<p class="row-sub">' + t("alert.row", { rpm: fmt(a.rpm), t: timeLabel(a.ts) }) + "</p></div>" +
          '<button type="button" class="btn btn-danger btn-sm" data-act="ban" data-ip="' + esc(a.ip) + '">' + t("bl.block") + "</button></div>";
      }).join("") : empty(t("alert.empty"))) +
      '<div class="pop-foot"><a class="link link-strong" href="#audit">' + t("alert.toAudit") + "</a></div>";
  }
  function closeBell() { $("#bell-pop").classList.add("hidden"); $("#bell-btn").setAttribute("aria-expanded", "false"); }
  $("#bell-btn").addEventListener("click", function () {
    var open = $("#bell-pop").classList.contains("hidden");
    if (!open) { closeBell(); return; }
    renderBell(); $("#bell-pop").classList.remove("hidden"); $("#bell-btn").setAttribute("aria-expanded", "true");
    if (LIVE && LIVE.alerts && LIVE.alerts[0]) { seenAlert = LIVE.alerts[0].ts; localStorage.setItem("e2b_alert_seen", String(seenAlert)); paintLive(); }
  });
  $("#bell-pop").addEventListener("click", function (e) {
    var b = e.target.closest("[data-act=ban]"); if (b) { ban([b.dataset.ip]); closeBell(); }
    if (e.target.closest("a")) closeBell();
  });
  document.addEventListener("click", function (e) { if (!e.target.closest("#bell-wrap")) closeBell(); });

  // ---------------- định tuyến + nạp màn khi cần (lazy load) ----------------
  var VIEWS = { dashboard: "nav.dashboard", monitor: "nav.monitor", blacklist: "nav.blacklist", domains: "nav.domains", audit: "nav.audit", settings: "nav.settings" };
  var LAZY = { domains: 1, audit: 1, settings: 1 };
  var VIEW = "dashboard";
  window.addEventListener("hashchange", route);
  function loadPage(name) {
    window.E2BPages = window.E2BPages || {};
    if (window.E2BPages[name]) return Promise.resolve(window.E2BPages[name]);
    return new Promise(function (res, rej) {
      var s = document.createElement("script");
      s.src = "js/pages/" + name + ".js?v=1.2.2";
      s.onload = function () { res(window.E2BPages[name]); }; s.onerror = rej;
      document.head.appendChild(s);
    });
  }
  function route() {
    var v = (location.hash || "#dashboard").slice(1).split("?")[0];
    if (!VIEWS[v]) v = "dashboard";
    VIEW = v;
    $$(".nav-link").forEach(function (a) { if (a.dataset.v === v) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current"); });
    $$(".view").forEach(function (s) { s.classList.toggle("hidden", s.id !== "view-" + v); });
    $("#title").textContent = t(VIEWS[v]); document.title = t(VIEWS[v]) + " · Evil2Ban";
    if (LAZY[v]) {
      var el = $("#view-" + v);
      if (!el.innerHTML) el.innerHTML = card({ clip: true, body: '<div style="padding-top:20px">' + skRows(6) + "</div>" });
      loadPage(v).then(function (p) { if (VIEW === v) p.show(el, CTX); })
        .catch(function () { el.innerHTML = card({ body: errBody() }); });
      return;
    }
    loadView(false);
  }
  function loadView(force) {
    if (VIEW === "dashboard") loadDashboard(force);
    else if (VIEW === "monitor") loadMonitor(force);
    else if (VIEW === "blacklist") loadBlacklist(force);
    else route();
  }
  function onFail(e, render) { if (!e.auth) render(); }

  // ---------------- TỔNG QUAN ----------------
  var DB = { st: "wait", d: null };
  function loadDashboard(force) {
    if (!DB.d) gate(DB, renderDashboard);
    Promise.all([api("/api/overview"), api("/api/traffic"), api("/api/ssh"), api("/api/events?limit=5")]).then(function (r) {
      OV = r[0]; DB.d = { o: r[0], t: r[1], s: r[2], e: r[3].events || [] };
      paintHeader(true);
      if (DB.st === "data") { if (VIEW === "dashboard") renderDashboard(); } else settle(DB, "data", function () { if (VIEW === "dashboard") renderDashboard(); });
    }).catch(function (e) { onFail(e, function () { settle(DB, DB.d ? "data" : "error", function () { DB.err = true; if (VIEW === "dashboard") renderDashboard(); }); }); });
  }
  function bannerHtml(st, o) {
    if (st === "wait") return "";
    if (st === "loading") return '<div class="banner" style="border-color:var(--border);background:var(--surface)" aria-busy="true"><div style="flex:1;display:flex;flex-direction:column;gap:8px">' + sk("288px") + sk("384px", "12px") + "</div></div>";
    if (st === "error") return '<div class="banner err" role="alert"><div class="banner-main"><span class="banner-ico">' + ic("circle-alert", "ico-5") + '</span><div><p class="banner-title">' + t("dash.errTitle") + '</p><p class="banner-text">' + t("dash.errText") + '</p></div></div><button type="button" class="btn btn-outline btn-md" data-act="retry">' + t("common.retry") + "</button></div>";
    var ab = (LIVE ? LIVE.auto_ban : o.auto_ban) ? t("dash.on") : t("dash.off");
    if (!o.ssh_failed_6h && !o.suspects) return '<div class="banner ok" role="status"><div class="banner-main"><span class="banner-ico">' + ic("shield-check", "ico-5") + '</span><div><p class="banner-title">' + t("dash.calmTitle") + '</p><p class="banner-text">' + t("dash.calmText") + "</p></div></div></div>";
    return '<div class="banner warn" role="status"><div class="banner-main"><span class="banner-ico">' + ic("shield-alert", "ico-5") + '</span><div>' +
      '<p class="banner-title">' + t(o.ssh_failed_6h >= 100 ? "dash.attackTitle" : "dash.scanTitle") + '</p><p class="banner-text">' +
      t("dash.attackText", { ssh: fmt(o.ssh_failed_6h), sus: fmt(o.suspects), ab: ab }) + "</p></div></div>" +
      '<a class="btn btn-outline btn-md" href="#blacklist">' + t("dash.viewSuspects") + "</a></div>";
  }
  function statCells() {
    var d = DB.d, o = d ? d.o : {}, s = d ? d.s : {}, tr = d ? d.t : {}, L = LIVE || {};
    var topSus = tr.suspects && tr.suspects[0], sp = L.spark || {};
    return [
      ["dash.rpm", L.rpm != null ? L.rpm : null, L.warming ? t("dash.rpmWarm") : t("dash.rpmSub"), sp.req],
      ["dash.sshpm", L.ssh_pm != null ? L.ssh_pm : null, t("dash.sshSub", { n: fmt(o.ssh_failed_6h) }), sp.ssh],
      ["dash.banned", L.banned != null ? L.banned : o.banned_now, t("dash.bannedSub", { n: fmt(o.total_banned) }), sp.banned],
      ["dash.suspects", L.suspects != null ? L.suspects : o.suspects, topSus ? t("dash.susSub", { n: fmt(topSus.score) }) : t("dash.susNone"), sp.suspects]
    ];
  }
  function statsHtml(st) {
    if (st === "wait") return '<div class="stats" style="min-height:118px"></div>';
    return '<div class="stats" id="dash-stats">' + statCells().map(function (c, i) {
      return '<div class="stat" data-stat="' + i + '"><p class="stat-label trunc">' + t(c[0]) + "</p>" +
        (st === "loading" ? '<div style="margin-top:8px" aria-busy="true">' + sk("80px", "28px") + "</div>" :
          '<div class="stat-line"><p class="stat-value' + (c[1] == null ? " none" : "") + '">' + fmt(c[1]) + "</p>" + spark(c[3]) + "</div>") +
        (st === "data" ? '<p class="stat-sub trunc">' + c[2] + "</p>" : "") + "</div>";
    }).join("") + "</div>";
  }
  function paintStats() {
    var el = $("#dash-stats"); if (!el) return;
    statCells().forEach(function (c, i) {
      var cell = el.querySelector('[data-stat="' + i + '"]'); if (!cell) return;
      var line = cell.querySelector(".stat-line"), sub = cell.querySelector(".stat-sub");
      if (line) line.innerHTML = '<p class="stat-value' + (c[1] == null ? " none" : "") + '">' + fmt(c[1]) + "</p>" + spark(c[3]);
      if (sub) sub.textContent = c[2];
    });
  }
  function hourChart(st, tr, o) {
    var hours = [], off = -new Date().getTimezoneOffset();
    for (var i = 0; i < 24; i++) hours.push(0);
    ((tr && tr.timeline) || []).forEach(function (p) { hours[Math.floor(((parseInt(p.h, 10) * 60 + off) / 60 % 24 + 24) % 24)] += p.n; });
    var max = Math.max.apply(null, hours), nowH = new Date().getHours(), peakH = hours.indexOf(max);
    var html = '<div class="chart"><div class="bars">' + hours.map(function (v, h) {
      return '<div class="bar-col" title="' + pad2(h) + ":00 · " + fmt(v) + '">' + (h === peakH && max ? '<p class="bar-val">' + fmt(v) + "</p>" : "") +
        '<div class="bar' + (h === nowH ? " now" : "") + '" style="height:' + Math.max(3, Math.round(v / (max || 1) * 100)) + '%"></div></div>';
    }).join("") + '</div><div class="axis">' + hours.map(function (_, h) { return "<span>" + (h % 3 === 0 ? pad2(h) : "") + "</span>"; }).join("") + "</div></div>";
    var b = st === "wait" ? '<div style="min-height:244px"></div>' : st === "loading" ? '<div style="padding:0 20px 20px" aria-busy="true">' + sk("100%", "224px") + "</div>"
      : st === "error" ? errBody() : !max ? '<div class="chart-empty">' + t("dash.chartEmpty") + "</div>" : html;
    return card({ title: t("dash.chart"), sub: t("dash.chartSub"), aside: st === "data" && max ? t("dash.chartPeak", { n: fmt(max), h: pad2(peakH) }) : "", body: b });
  }
  function needCard(st, d) {
    var list = d ? (d.t.suspects || []) : [], total = d ? d.o.suspects : 0;
    var rows = list.slice(0, 6).map(function (r) {
      return '<li class="row hov"><div class="row-main">' + mono(r.ip) + '<p class="row-sub trunc">' + t("dash.needRow", { c404: fmt(r.c404), sens: fmt(r.sensitive) }) + "</p></div>" +
        '<span class="score">' + fmt(r.score) + "<small>" + t("common.points") + "</small></span>" +
        '<button type="button" class="btn btn-danger btn-sm" data-act="ban" data-ip="' + esc(r.ip) + '">' + t("bl.block") + "</button></li>";
    }).join("");
    return card({ title: t("dash.need"), sub: t("dash.needSub"), aside: st === "data" && total ? t("dash.needAside", { n: fmt(total) }) : "",
      body: body(st, '<ul class="rows">' + rows + "</ul>", t("dash.needEmpty"), !list.length, 6),
      foot: st === "data" && list.length ? '<a class="link link-strong" href="#blacklist">' + t("dash.needAll", { n: fmt(total) }) + "</a>" : "" });
  }
  var EV = { "ban": ["shield-x", "ban"], "unban": ["shield-check", "unban"], "whitelist-add": ["shield-check", "ok"], "whitelist-remove": ["shield-alert", "other"],
    "rate-alert": ["zap", "other"], "login": ["log-in", "ok"], "login-fail": ["shield-x", "ban"] };
  function eventsCard(st, list) {
    var rows = (list || []).map(function (e) {
      var m = EV[e.type] || ["activity", "other"], why = e.reason ? t("why." + e.reason) : "";
      if (why === "why." + e.reason) why = e.reason;
      return '<li class="row"><span class="ev-ico ' + m[1] + '">' + ic(m[0]) + "</span>" +
        '<p class="ev-text trunc"><b>' + esc(t("ev." + e.type)) + "</b> " + (e.ip ? mono(e.ip) : "") + (why ? " · " + esc(why) : "") + "</p>" +
        '<span class="ev-time">' + timeLabel(e.ts) + "</span></li>";
    }).join("");
    return card({ title: t("ev.title"), body: body(st, '<ul class="rows pb">' + rows + "</ul>", t("ev.empty"), !(list && list.length), 3) });
  }
  function renderDashboard() {
    var st = DB.st, d = DB.d;
    $("#view-dashboard").innerHTML = bannerHtml(DB.err && d ? "error" : st, d ? d.o : {}) + statsHtml(st) +
      '<div class="grid-3"><div class="col span-2">' + hourChart(st, d && d.t, d && d.o) + eventsCard(st, d && d.e) + "</div>" + needCard(st, d) + "</div>";
    DB.err = false;
  }

  // ---------------- GIÁM SÁT ----------------
  var MN = { st: "wait", d: null };
  function loadWorldMap() {
    if (window.E2BWorldMap || loadWorldMap.p) return;
    loadWorldMap.p = true;
    var sc = document.createElement("script");
    sc.src = "js/worldmap.js?v=1.2.2";
    sc.onload = function () { if (VIEW === "monitor" && MN.st === "data") renderMonitor(); };
    document.head.appendChild(sc);
  }
  function loadMonitor() {
    loadWorldMap();
    if (!MN.d) gate(MN, renderMonitor);
    Promise.all([api("/api/ssh"), api("/api/traffic"), api("/api/events?limit=20")]).then(function (r) {
      MN.d = { s: r[0], t: r[1], e: r[2].events || [] };
      if (MN.st === "data") { if (VIEW === "monitor") renderMonitor(); } else settle(MN, "data", function () { if (VIEW === "monitor") renderMonitor(); });
    }).catch(function (e) { onFail(e, function () { settle(MN, MN.d ? "data" : "error", function () { if (VIEW === "monitor") renderMonitor(); }); }); });
  }
  function rankCard(st, title, sub, rows, o) {
    o = o || {};
    var max = rows.length ? rows[0].n : 1;
    var lis = rows.map(function (r) {
      return '<li class="rank' + (o.act ? " act" : "") + '"><span class="rank-key trunc" title="' + esc(r.k) + '">' + (o.ip ? mono(r.k) + (r.cc ? '<span class="cc">' + esc(r.cc) + "</span>" : "") : esc(r.k)) + "</span>" +
        '<span class="rank-n">' + fmt(r.n) + '<span class="unit">' + (o.unit || t("common.times")) + "</span></span>" +
        (o.act ? '<button type="button" class="btn btn-danger btn-sm" data-act="ban" data-ip="' + esc(r.k) + '">' + t("bl.block") + "</button>" : "") +
        '<div class="track"><div class="fill" style="width:' + Math.max(2, Math.round(r.n / max * 100)) + '%"></div></div></li>';
    }).join("");
    return card({ title: title, sub: sub, body: body(st, '<ul class="rows pb">' + lis + "</ul>", t("mon.empty"), !rows.length, 5) });
  }
  function stackCard(st, tr) {
    function seg(rows, tones) {
      var total = rows.reduce(function (a, r) { return a + r[1]; }, 0) || 1;
      return '<div class="stack">' + rows.map(function (r, i) { return '<span class="seg-' + tones[i] + '" style="width:' + (r[1] / total * 100) + '%" title="' + r[0] + ": " + fmt(r[1]) + '"></span>'; }).join("") + "</div>" +
        '<ul class="legend">' + rows.map(function (r, i) { return '<li><span class="sw sw-' + tones[i] + '"></span>' + r[0] + ' <span class="muted tnum">' + fmt(r[1]) + " · " + Math.round(r[1] / total * 100) + "%</span></li>"; }).join("") + "</ul>";
    }
    var dv = (tr && tr.devices) || {}, sc = (tr && tr.status) || {};
    var devices = [[t("mon.desktop"), dv.desktop || 0], [t("mon.bot"), dv.bot || 0], [t("mon.mobile"), dv.mobile || 0]].sort(function (a, b) { return b[1] - a[1]; });
    var codes = ["2xx", "3xx", "4xx", "5xx"].map(function (k) { return [k, sc[k] || 0]; });
    var tot = codes.reduce(function (a, r) { return a + r[1]; }, 0), p4 = tot ? Math.round((sc["4xx"] || 0) / tot * 100) : 0;
    var html = '<div class="stack-grid"><div><p class="stack-label">' + t("mon.devices") + "</p>" + seg(devices, ["fill", "fill55", "fill25"]) + "</div>" +
      '<div><p class="stack-label">' + t("mon.codes") + "</p>" + seg(codes, ["ok", "fill40", "warn", "danger"]) + "</div></div>";
    return card({ title: t("mon.classify"), sub: p4 > 50 ? t("mon.classify4xx", { p: p4 }) : t("mon.classifySub"), body: body(st, html, t("mon.empty"), !tot, 2) });
  }
  function regionName(cc) {
    try { return new Intl.DisplayNames([I18N.locale()], { type: "region" }).of(cc) || cc; } catch (e) { return cc; }
  }
  function geoCard(st, tr) {
    var cs = (tr && tr.countries) || [], max = cs.length ? cs[0].requests : 0, byCc = {};
    cs.forEach(function (c) { byCc[c.cc] = c; });
    var lvl = function (v) { return v ? Math.max(1, Math.ceil(5 * Math.log(1 + v) / Math.log(1 + max))) : 0; };
    var map = "";
    if (window.E2BWorldMap) {
      var W = window.E2BWorldMap;
      map = '<svg class="worldmap" viewBox="0 0 ' + W.w + " " + W.h + '" role="img" aria-label="' + esc(t("mon.geo")) + '">' +
        Object.keys(W.paths).map(function (cc) {
          var c = byCc[cc];
          return '<path d="' + W.paths[cc] + '" class="geo-' + lvl(c ? c.requests : 0) + '"><title>' +
            esc(regionName(cc) + (c ? ": " + t("mon.geoTip", { r: fmt(c.requests), i: fmt(c.ips) }) : "")) + "</title></path>";
        }).join("") + "</svg>";
    } else map = '<div class="sk" style="width:100%;aspect-ratio:1000/439"></div>';
    var legend = '<div class="geo-legend"><span>' + t("mon.geoLess") + "</span>" + [1, 2, 3, 4, 5].map(function (i) { return '<i class="geo-' + i + '"></i>'; }).join("") + "<span>" + t("mon.geoMore") + "</span></div>";
    var top = cs.slice(0, 8), tmax = top.length ? top[0].requests : 1;
    var list = '<ul class="rows">' + top.map(function (c) {
      return '<li class="rank"><span class="rank-key trunc">' + esc(regionName(c.cc)) + ' <span class="cc">' + c.cc + "</span></span>" +
        '<span class="rank-n">' + fmt(c.requests) + '<span class="unit">' + fmt(c.ips) + " IP</span></span>" +
        '<div class="track"><div class="fill" style="width:' + Math.max(2, Math.round(c.requests / tmax * 100)) + '%"></div></div></li>';
    }).join("") + "</ul>";
    var html = '<div class="geo-grid"><div class="geo-map">' + map + legend + '</div><div class="geo-list">' + list + "</div></div>";
    return card({ title: t("mon.geo"), sub: t("mon.geoSub"), body: body(st, html, t("mon.geoEmpty"), !cs.length, 6),
      foot: '<p class="card-sub" style="margin:0">' + t("mon.geoAttr") + "</p>" });
  }
  function renderMonitor() {
    var st = MN.st, d = MN.d, s = d ? d.s : {}, tr = d ? d.t : {};
    var ssh = (s.top || []).map(function (r) { return { k: r.ip, n: r.n, cc: r.country }; });
    var noCc = ssh.length && ssh.every(function (r) { return !r.cc; });
    $("#view-monitor").innerHTML = geoCard(st, tr) + '<div class="grid-2">' +
      rankCard(st, t("mon.ssh"), t(noCc ? "mon.sshNoCc" : "mon.sshSub"), ssh, { ip: true, act: true }) +
      rankCard(st, t("mon.users"), t("mon.usersSub"), (s.top_users || []).map(function (r) { return { k: r.u, n: r.n }; })) +
      rankCard(st, t("mon.traffic"), t("mon.trafficSub"), (tr.top_traffic || []).map(function (r) { return { k: r.ip, n: r.total, cc: r.country }; }), { ip: true, unit: t("common.requests") }) +
      rankCard(st, t("mon.ua"), t("mon.uaSub"), (tr.top_ua || []).map(function (r) { return { k: r.ua, n: r.n }; }), { unit: t("common.requests") }) +
      "</div>" + stackCard(st, tr) + eventsCard(st, d && d.e);
  }

  // ---------------- CHẶN IP ----------------
  var BL = { st: "wait", d: null, tab: "suspects", q: "", per: 10, page: { suspects: 1, banned: 1, wl: 1 }, sel: { suspects: {}, banned: {} } };
  var TABS = [["suspects", "bl.suspects", "bl.phSus"], ["banned", "bl.banned", "bl.phBan"], ["wl", "bl.wl", "bl.phWl"]];
  function buildBlToolbar() {
    $("#bl-toolbar").innerHTML = '<div class="tabs" role="tablist">' + TABS.map(function (x) {
      return '<button type="button" class="tab" role="tab" data-tab="' + x[0] + '">' + t(x[1]) + '<span class="n" data-n="' + x[0] + '"></span></button>';
    }).join("") + '</div><label class="search">' + ic("search") + '<input class="input" type="text" id="bl-q" autocomplete="off" value="' + esc(BL.q) + '"></label>';
  }
  function paintBlToolbar() {
    if (!$("#bl-q")) buildBlToolbar();
    $$("#bl-toolbar .tab").forEach(function (b) { b.setAttribute("aria-selected", b.dataset.tab === BL.tab ? "true" : "false"); });
    var d = BL.d;
    $$("#bl-toolbar [data-n]").forEach(function (n) { n.textContent = d ? fmt({ suspects: d.suspects.length, banned: d.banned.length, wl: d.wl.length }[n.dataset.n]) : ""; });
    $("#bl-q").placeholder = t(TABS.filter(function (x) { return x[0] === BL.tab; })[0][2]);
    var cf = d ? d.wl.filter(function (w) { return w.source === "cloudflare"; }).length : 0;
    $("#bl-note").innerHTML = d && cf ? ic("shield-check") + "<span><b>" + t("bl.cf", { n: cf }) + "</b> " + t("bl.cfText") + "</span>" : "";
    $("#bl-note").classList.toggle("hidden", !(d && cf));
  }
  $("#bl-toolbar").addEventListener("click", function (e) {
    var b = e.target.closest("[data-tab]"); if (!b || b.dataset.tab === BL.tab) return;
    BL.tab = b.dataset.tab; BL.q = ""; $("#bl-q").value = ""; paintBlToolbar(); renderBlCard();
  });
  $("#bl-toolbar").addEventListener("input", function (e) { if (e.target.id === "bl-q") { BL.q = e.target.value.trim(); BL.page[BL.tab] = 1; renderBlCard(); } });
  function loadBlacklist(force) {
    if (!BL.d) { gate(BL, function () { paintBlToolbar(); renderBlCard(); }); }
    else if (force) reloading($("#bl-card .card"), true);
    Promise.all([api("/api/traffic"), api("/api/banned"), api("/api/whitelist")]).then(function (r) {
      BL.d = { suspects: r[0].suspects || [], banned: r[1].banned || [], jail: r[1].jail || "sshd", wl: r[2].entries || [] };
      ["suspects", "banned"].forEach(function (k) { var keep = {}; BL.d[k].forEach(function (x) { if (BL.sel[k][x.ip]) keep[x.ip] = true; }); BL.sel[k] = keep; });
      var done = function () { paintBlToolbar(); if (VIEW === "blacklist") renderBlCard(); };
      if (BL.st === "data") done(); else settle(BL, "data", done);
    }).catch(function (e) { onFail(e, function () { reloading($("#bl-card .card"), false); if (BL.d) toast(errMsg(e), true); else settle(BL, "error", function () { if (VIEW === "blacklist") renderBlCard(); }); }); });
  }
  function filtered() {
    var q = BL.q.toLowerCase(), d = BL.d; if (!d) return [];
    if (BL.tab === "suspects") return d.suspects.filter(function (r) { return !q || r.ip.indexOf(q) >= 0 || (r.ua || "").toLowerCase().indexOf(q) >= 0; });
    if (BL.tab === "banned") return d.banned.filter(function (r) { return !q || r.ip.indexOf(q) >= 0; });
    return d.wl.filter(function (r) { return !q || r.entry.toLowerCase().indexOf(q) >= 0 || (r.note || "").toLowerCase().indexOf(q) >= 0; });
  }
  function selected(tab) { var s = BL.sel[tab] || {}; return Object.keys(s).filter(function (k) { return s[k]; }); }
  function renderBlCard() {
    var el = $("#bl-card"), st = BL.st;
    if (st !== "data") { el.innerHTML = st === "wait" ? '<div style="min-height:420px"></div>' : card({ clip: true, body: st === "loading" ? '<div style="padding-top:20px">' + skRows(6) + "</div>" : errBody() }); return; }
    var rows = filtered(), tab = BL.tab, per = BL.per, pages = Math.max(1, Math.ceil(rows.length / per));
    BL.page[tab] = Math.min(Math.max(1, BL.page[tab]), pages);
    var page = BL.page[tab], slice = rows.slice((page - 1) * per, page * per);
    var nothing = BL.q ? '<p class="empty">' + t("common.noMatch", { q: esc(BL.q) }) + ' <button type="button" class="link" data-act="clear-q">' + t("common.clearSearch") + "</button></p>" : "";
    var html = "";
    if (tab === "suspects") {
      var sel = selected("suspects"), allOn = slice.length && slice.every(function (r) { return BL.sel.suspects[r.ip]; });
      html = (sel.length ? '<div class="bulk"><span>' + t("common.selected", { n: "<b class=\"tnum\">" + sel.length + "</b>" }) + '</span><button type="button" class="btn btn-danger btn-sm" data-act="bulk-ban">' + ic("shield-ban") + t("bl.blockN", { n: sel.length }) + '</button><button type="button" class="btn btn-ghost btn-sm" data-act="clear-sel">' + t("common.clearSel") + "</button></div>" : "") +
        (rows.length ? '<div class="table-wrap"><table class="table"><thead><tr><th class="cbc">' + cbHtml(allOn, "sel-all") + "</th><th>" + t("bl.colIp") + '</th><th class="num md-only">' + t("bl.col404") + '</th><th class="num md-only">' + t("bl.colSens") + '</th><th class="lg-only">' + t("bl.colType") + '</th><th class="num">' + t("bl.colScore") + '</th><th class="act"></th></tr></thead><tbody>' +
          slice.map(function (r) {
            var on = !!BL.sel.suspects[r.ip];
            return "<tr" + (on ? ' class="sel"' : "") + '><td class="cbc">' + cbHtml(on, "sel", r.ip) + '</td><td class="ua">' + mono(r.ip) + (r.ua ? '<p class="row-sub trunc" title="' + esc(r.ua) + '">' + esc(r.ua) + "</p>" : "") + "</td>" +
              '<td class="num md-only">' + fmt(r.c404) + '</td><td class="num md-only">' + fmt(r.sensitive) + '</td><td class="lg-only">' + (r.scanner_ua ? pill(t("bl.scanner"), "warn") : DASH) + "</td>" +
              '<td class="num strong">' + fmt(r.score) + '</td><td class="act"><button type="button" class="btn btn-danger btn-sm" data-act="ban" data-ip="' + esc(r.ip) + '">' + t("bl.block") + "</button></td></tr>";
          }).join("") + "</tbody></table></div>" + pagerHtml(rows.length, page, per, t("unit.ip")) : nothing || empty(t("bl.emptySus")));
    } else if (tab === "banned") {
      var selB = selected("banned"), allB = slice.length && slice.every(function (r) { return BL.sel.banned[r.ip]; });
      html = (selB.length ? '<div class="bulk"><span>' + t("common.selected", { n: "<b class=\"tnum\">" + selB.length + "</b>" }) + '</span><button type="button" class="btn btn-outline btn-sm" data-act="bulk-unban">' + t("bl.unblockN", { n: selB.length }) + '</button><button type="button" class="btn btn-ghost btn-sm" data-act="clear-sel">' + t("common.clearSel") + "</button></div>" : "") +
        (rows.length ? '<div class="table-wrap"><table class="table"><thead><tr><th class="cbc">' + cbHtml(allB, "sel-all") + "</th><th>" + t("bl.colIp") + '</th><th class="md-only">' + t("bl.colJail") + '</th><th class="act"></th></tr></thead><tbody>' +
          slice.map(function (r) {
            var on = !!BL.sel.banned[r.ip];
            return "<tr" + (on ? ' class="sel"' : "") + '><td class="cbc">' + cbHtml(on, "sel", r.ip) + "</td><td>" + mono(r.ip) + (r.country ? ' <span class="muted">' + esc(r.country) + "</span>" : "") + "</td>" +
              '<td class="md-only muted">' + esc(BL.d.jail) + '</td><td class="act"><button type="button" class="btn btn-outline btn-sm" data-act="unban" data-ip="' + esc(r.ip) + '">' + t("bl.unblock") + "</button></td></tr>";
          }).join("") + "</tbody></table></div>" + pagerHtml(rows.length, page, per, t("unit.ip")) : nothing || empty(t("bl.emptyBan")));
    } else {
      var SRC = { owner: ["bl.srcOwner", "ok"], cloudflare: ["bl.srcCf", ""], system: ["bl.srcSystem", ""] };
      html = '<form class="wl-add" data-act="wl-add-form"><input class="input" id="wl-input" type="text" placeholder="' + t("bl.wlAddPh") + '" autocomplete="off"><button type="submit" class="btn btn-outline">' + ic("plus") + t("bl.add") + "</button></form>" +
        (rows.length ? '<div class="table-wrap"><table class="table"><thead><tr><th>' + t("bl.colEntry") + '</th><th class="md-only">' + t("bl.colKind") + "</th><th>" + t("bl.colSrc") + '</th><th class="md-only">' + t("bl.colNote") + '</th><th class="act"></th></tr></thead><tbody>' +
          slice.map(function (r) {
            var s = SRC[r.source] || [r.source, ""];
            return "<tr><td>" + mono(r.entry) + '</td><td class="md-only muted">' + (r.is_cidr ? "CIDR" : "IP") + "</td><td>" + pill(SRC[r.source] ? t(s[0]) : s[0], s[1]) + '</td><td class="md-only muted trunc">' + (esc(r.note) || "—") + "</td>" +
              '<td class="act">' + (r.source === "owner" ? '<button type="button" class="btn btn-ghost btn-sm" data-act="wl-remove" data-ip="' + esc(r.entry) + '">' + t("bl.remove") + "</button>" : "") + "</td></tr>";
          }).join("") + "</tbody></table></div>" + pagerHtml(rows.length, page, per, t("unit.item")) : nothing || empty(t("bl.emptyWl")));
    }
    el.innerHTML = card({ clip: true, body: html });
  }
  $("#bl-card").addEventListener("submit", function (e) {
    if (!e.target.matches("[data-act=wl-add-form]")) return;
    e.preventDefault();
    var v = $("#wl-input").value.trim(); if (!v) return;
    api("/api/whitelist/add", { method: "POST", body: JSON.stringify({ entry: v, note: "owner" }) })
      .then(function () { toast(t("bl.wlAdded", { x: v })); loadBlacklist(true); }).catch(function (err) { toast(errMsg(err), true); });
  });
  $("#bl-card").addEventListener("click", function (e) {
    var b = e.target.closest("[data-act]"); if (!b) return;
    var act = b.dataset.act, tab = BL.tab, ip = b.dataset.ip;
    if (act === "sel") { BL.sel[tab][ip] = !BL.sel[tab][ip]; renderBlCard(); }
    else if (act === "sel-all") {
      var rows = filtered().slice((BL.page[tab] - 1) * BL.per, BL.page[tab] * BL.per);
      var on = !rows.every(function (r) { return BL.sel[tab][r.ip]; });
      rows.forEach(function (r) { BL.sel[tab][r.ip] = on; }); renderBlCard();
    }
    else if (act === "clear-sel") { BL.sel[tab] = {}; renderBlCard(); }
    else if (act === "bulk-ban") ban(selected("suspects"), function () { BL.sel.suspects = {}; });
    else if (act === "bulk-unban") unban(selected("banned"), function () { BL.sel.banned = {}; });
    else if (act === "page") { BL.page[tab] = parseInt(b.dataset.p, 10); renderBlCard(); }
    else if (act === "clear-q") { BL.q = ""; $("#bl-q").value = ""; renderBlCard(); }
    else if (act === "ban") ban([ip]);
    else if (act === "unban") unban([ip]);
    else if (act === "retry") loadBlacklist(true);
    else if (act === "wl-remove") {
      api("/api/whitelist/remove", { method: "POST", body: JSON.stringify({ entry: ip }) })
        .then(function () { toast(t("bl.wlRemoved", { x: ip })); loadBlacklist(true); }).catch(function (err) { toast(errMsg(err), true); });
    }
  });

  // ---------------- chặn / gỡ chặn (dùng chung mọi màn) ----------------
  function ban(ips, done) {
    if (!ips.length) return;
    confirmDanger(t("bl.confirmTitle", { x: ips.length === 1 ? ips[0] : ips.length + " IP" }), t("bl.confirmText"), t("bl.block")).then(function (yes) {
      if (!yes) return;
      api("/api/ban-bulk", { method: "POST", body: JSON.stringify({ ips: ips }) }).then(function (r) {
        var ok = r.results.filter(function (x) { return x.ok; }).length, bad = r.results.length - ok;
        if (bad && ips.length === 1) toast(I18N.err(r.results[0].code, r.results[0].result), true);
        else toast(t(bad ? "bl.doneBanRej" : "bl.doneBan", { ok: ok, n: ips.length, bad: bad }), bad > 0 && ok === 0);
        if (done) done(); loadView(true);
      }).catch(function (err) { toast(errMsg(err), true); });
    });
  }
  function unban(ips, done) {
    if (!ips.length) return;
    api("/api/unban-bulk", { method: "POST", body: JSON.stringify({ ips: ips }) }).then(function (r) {
      var ok = r.results.filter(function (x) { return x.ok; }).length;
      toast(t("bl.doneUnban", { ok: ok, n: ips.length }), ok === 0);
      if (done) done(); loadView(true);
    }).catch(function (err) { toast(errMsg(err), true); });
  }
  ["#view-dashboard", "#view-monitor"].forEach(function (sel) {
    $(sel).addEventListener("click", function (e) {
      var b = e.target.closest("[data-act]"); if (!b) return;
      if (b.dataset.act === "ban") ban([b.dataset.ip]); else if (b.dataset.act === "retry") loadView(true);
    });
  });

  // làm mới bảng của tổng quan / giám sát mỗi 30 giây (số liệu sống đã đi qua SSE)
  setInterval(function () {
    if ($("#app").classList.contains("hidden") || document.hidden) return;
    if (VIEW === "dashboard") loadDashboard(); else if (VIEW === "monitor") loadMonitor();
  }, 30000);

  // công cụ cho các màn nạp sau (Cài đặt, Nhật ký, Tên miền)
  var CTX = { api: api, t: t, I18N: I18N, esc: esc, fmt: fmt, ic: ic, mono: mono, card: card, sk: sk, skRows: skRows, errBody: errBody,
    empty: empty, pill: pill, pagerHtml: pagerHtml, toast: toast, notify: notify, confirmDanger: confirmDanger, errMsg: errMsg,
    timeLabel: timeLabel, gate: gate, settle: settle, reloading: reloading, ban: ban, logout: logout, applyTheme: applyTheme,
    themeMode: themeMode, setLang: setLang, DASH: DASH };

  // khởi động: thử gọi overview; 401 -> màn đăng nhập
  function boot() {
    api("/api/overview").then(function (o) { OV = o; showApp(); paintHeader(true); paintSbToggle(); route(); startLive(); })
      .catch(function (e) { if (!e.auth) { showApp(); paintHeader(false); paintSbToggle(); route(); startLive(); } });
  }
  applyI18n(); applyTheme(); setEye(false); setLiveChip(false);
  boot();
})();
