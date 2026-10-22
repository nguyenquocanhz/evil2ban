/* Màn Chống DDoS — nạp khi mở tới. Số liệu sống mỗi 5 giây, 5 lớp bảo vệ, tự hoàn tác 60 giây. */
(function () {
  "use strict";
  var X, EL, S = { st: "wait", d: null, busy: false, left: 0 }, POLL = null, TICK = null;
  var LAYER_IC = { origin: "globe-lock", syn: "unplug", udp: "radio-tower", icmp: "activity", slow: "hourglass" };
  var LAYER_TH = { syn: ["syn_rate"], udp: ["udp_rate"], icmp: ["icmp_rate"], slow: ["timeout", "conn_per_ip", "req_rate"] };
  var REC = { syn_rate: 60, udp_rate: 200, icmp_rate: 5, conn_per_ip: 30, req_rate: 20, timeout: 10 };
  function t(k, o) { return X.t(k, o); }
  function fmt(n) { return X.fmt(n); }

  // ---------- chữ hiện tại / khuyến nghị ----------
  function curText(l, d) {
    var th = d.th, c = l.cur || {}, on = l.state === "on";
    if (l.key === "origin") return on ? t("dd.c.originOn") : t("dd.c.originOff");
    if (l.key === "syn") return t("dd.c.syn", { b: fmt(c.backlog), r: c.retries }) + " · " + (c.limit ? t("dd.c.synLim", { n: th.syn_rate }) : t("dd.c.synNoLim"));
    if (l.key === "udp") return on ? t("dd.c.udp", { n: fmt(th.udp_rate) }) : t("dd.c.udpOff");
    if (l.key === "icmp") return on ? t("dd.c.icmp", { n: th.icmp_rate }) : t("dd.c.icmpOff");
    return on ? t("dd.c.slow", { t: th.timeout, c: th.conn_per_ip, r: th.req_rate }) : t("dd.c.slowOff");
  }
  function recText(k, d) {
    var th = d.th, o = d.origin || {};
    if (k === "origin") return t("dd.c.originOn") + " · " + (o.ok ? t("dd.c.originOk", { b: o.behind, t: o.total }) : t("dd.c.originBad", { n: (o.direct || []).length, list: (o.direct || []).slice(0, 3).join(", ") }));
    if (k === "syn") return t("dd.c.syn", { b: fmt(4096), r: 2 }) + " · " + t("dd.c.synLim", { n: th.syn_rate });
    if (k === "udp") return t("dd.c.udp", { n: fmt(th.udp_rate) });
    if (k === "icmp") return t("dd.c.icmp", { n: th.icmp_rate });
    return t("dd.c.slow", { t: th.timeout, c: th.conn_per_ip, r: th.req_rate });
  }
  function whatText(keys) {
    return keys.map(function (k) { return k.indexOf("th.") === 0 ? t("dd.th." + k.slice(3)) : t("dd.l." + k); }).join(", ");
  }

  // ---------- khối ----------
  function banner() {
    var d = S.d;
    if (S.st === "wait") return '<div style="min-height:78px"></div>';
    if (S.st === "loading") return '<div class="banner" style="border-color:var(--border);background:var(--surface)" aria-busy="true"><div style="flex:1;display:flex;flex-direction:column;gap:8px">' + X.sk("288px") + X.sk("384px", "12px") + "</div></div>";
    if (S.st === "error") return '<div class="banner err" role="alert"><div class="banner-main"><span class="banner-ico">' + X.ic("circle-alert", "ico-5") + '</span><div><p class="banner-title">' + t("dd.errTitle") + '</p><p class="banner-text">' + t("dd.errText") + '</p></div></div><button type="button" class="btn btn-outline btn-md" data-act="retry">' + t("common.retry") + "</button></div>";
    if (d.pending) return '<div class="banner pend" role="alert"><div class="banner-main"><span class="countdown" id="dd-left">' + S.left + '</span><div><p class="banner-title">' + X.esc(t("dd.pendTitle", { what: whatText(d.pending.changes) })) + '</p><p class="banner-text" id="dd-left-text">' + t("dd.pendText", { s: S.left }) + "</p></div></div>" +
      '<div class="banner-acts"><button type="button" class="btn btn-ghost btn-md" data-act="revert">' + X.ic("undo-2") + t("dd.undo") + '</button><button type="button" class="btn btn-primary btn-md" data-act="confirm">' + t("dd.keep") + "</button></div></div>";
    if (d.attack) {
      var a = d.attack, ips = blockable().slice(0, 5);
      return '<div class="banner err" role="alert"><div class="banner-main"><span class="banner-ico">' + X.ic("shield-alert", "ico-5") + '</span><div><p class="banner-title">' + t("dd.atkTitle", { k: a.kind === "syn" ? "SYN Flood" : "UDP/ICMP Flood" }) + '</p><p class="banner-text">' +
        (a.kind === "syn" ? t("dd.atkTextSyn", { n: fmt(d.syn_recv), ips: fmt(d.ips), b: fmt(d.blocked) }) : t("dd.atkTextUdp", { n: fmt(d.pps), b: fmt(d.blocked) })) + "</p></div></div>" +
        (ips.length ? '<button type="button" class="btn btn-danger btn-md" data-act="block-top">' + X.ic("shield-ban") + t("dd.blockTop", { n: ips.length }) + "</button>" : "") + "</div>";
    }
    var good = d.layers.filter(function (l) { return l.state === "on"; }).length, originOn = d.layers[0].state === "on";
    return '<div class="banner ok" role="status"><div class="banner-main"><span class="banner-ico">' + X.ic("shield-check", "ico-5") + '</span><div><p class="banner-title">' + t("dd.okTitle") + '</p><p class="banner-text">' +
      (good === 5 ? t("dd.allOn") : t("dd.okText", { n: good }) + (originOn ? "" : " " + t("dd.okHint"))) + "</p></div></div></div>";
  }
  function stats() {
    if (S.st === "wait") return '<div class="stats" style="min-height:118px"></div>';
    var d = S.d || {}, sp = d.spark || {}, ctPct = d.conntrack_max ? d.conntrack / d.conntrack_max * 100 : 0;
    var cells = [
      [t("dd.sSyn"), fmt(d.syn_recv), t("dd.sSynSub"), sp.syn, d.attack && d.attack.kind === "syn" ? "danger" : ""],
      [t("dd.sEst"), fmt(d.established), t("dd.sEstSub", { n: fmt(d.ips) }), sp.est, ""],
      [t("dd.sCt"), ctPct.toLocaleString(X.I18N.locale(), { maximumFractionDigits: 1 }) + "%", fmt(d.conntrack) + " / " + fmt(d.conntrack_max), sp.ct, ctPct > 70 ? "warn" : ""],
      [t("dd.sPps"), fmt(d.pps), t("dd.sPpsSub"), sp.pps, d.attack && d.attack.kind === "udp" ? "danger" : ""]
    ];
    return '<div class="stats" id="dd-stats">' + cells.map(function (c) {
      return '<div class="stat"><p class="stat-label trunc">' + c[0] + "</p>" +
        (S.st === "loading" ? '<div style="margin-top:8px" aria-busy="true">' + X.sk("80px", "28px") + "</div>" :
          S.st === "error" ? '<div class="stat-line"><p class="stat-value none">—</p></div>' :
          '<div class="stat-line"><p class="stat-value' + (c[4] ? " " + c[4] : "") + '">' + c[1] + "</p>" + X.spark(c[3]) + "</div>" + '<p class="stat-sub trunc">' + c[2] + "</p>") + "</div>";
    }).join("") + "</div>";
  }
  function layersCard() {
    var d = S.d, allRec = d && d.layers.every(function (l, i) { return d.cfg[l.key] || (l.key === "origin" && !d.origin.ok); }) &&
      Object.keys(REC).every(function (k) { return d.th[k] === REC[k]; });
    var aside = S.st === "data" ? '<button type="button" class="btn btn-primary btn-md" data-act="recommended"' + (allRec || d.pending || S.busy ? " disabled" : "") + ">" + X.ic("wand-sparkles") + t("dd.applyRec") + "</button>" : "";
    var body;
    if (S.st === "wait") body = '<div style="min-height:420px"></div>';
    else if (S.st === "loading") body = X.skRows(5);
    else if (S.st === "error") body = X.errBody();
    else body = '<ul class="layers">' + d.layers.map(function (l) {
      var on = !!d.cfg[l.key], st = l.state, tone = st === "on" ? "ok" : st === "partial" ? "warn" : "";
      return '<li class="layer"><span class="layer-ico">' + X.ic(LAYER_IC[l.key]) + '</span><div class="layer-main">' +
        '<div class="layer-head"><p class="layer-title">' + t("dd.l." + l.key) + "</p>" + X.pill(t("dd.st." + st), tone) + (l.key === "origin" && st !== "on" ? '<span class="muted small">' + t("dd.best") + "</span>" : "") + "</div>" +
        '<p class="layer-desc">' + t("dd.d." + l.key) + "</p>" +
        '<p class="layer-kv">' + (st === "on" ? '<span class="muted">' + t("dd.now") + '</span><span class="mono">' + X.esc(curText(l, d)) + "</span>"
          : '<span class="muted">' + t("dd.cur") + '</span><span class="mono">' + X.esc(curText(l, d)) + '</span><span class="muted">' + t("dd.rec") + '</span><span class="mono strong' + (l.key === "origin" && !d.origin.ok ? " num-warn" : "") + '">' + X.esc(recText(l.key, d)) + "</span>") + "</p></div>" +
        '<div class="layer-side"><button type="button" class="switch" role="switch" aria-checked="' + on + '" aria-label="' + X.esc(t("dd.l." + l.key)) + '" data-layer="' + l.key + '"' + (d.pending || S.busy ? " disabled" : "") + "></button>" +
        (LAYER_TH[l.key] ? '<button type="button" class="link small" data-th="' + l.key + '"' + (d.pending ? " disabled" : "") + ">" + t("dd.editTh") + "</button>" : "") + "</div></li>";
    }).join("") + "</ul>";
    return X.card({ id: "dd-layers", title: t("dd.layers"), sub: t("dd.layersSub"), aside: aside, body: body });
  }
  function kind(r) {
    if (r.port === 22) return t("dd.kSsh");
    if (r.port === 80 || r.port === 443) return t("dd.kWeb");
    return t("dd.kPort", { p: r.port });
  }
  function blockable() { return ((S.d && S.d.top) || []).filter(function (r) { return !r.cf && !r.wl && !r.me; }).map(function (r) { return r.ip; }); }
  function topCard() {
    var d = S.d, rows = (d && d.top) || [];
    var html = '<ul class="rows pb">' + rows.map(function (r) {
      var side = r.cf ? '<span class="skip">' + t("dd.skip") + "</span>" : r.me ? X.pill(t("dd.me"), "ok") : r.wl ? X.pill("whitelist", "") :
        '<button type="button" class="btn btn-danger btn-sm" data-act="ban" data-ip="' + X.esc(r.ip) + '">' + t("bl.block") + "</button>";
      return '<li class="row hov"><div class="row-main">' + X.mono(r.ip) + '<p class="row-sub">' + (r.cf ? "Cloudflare · " : "") + kind(r) + "</p></div>" +
        '<span class="score' + (d.attack ? " num-danger" : "") + '">' + fmt(r.n) + "<small>" + t("dd.conn") + "</small></span>" + side + "</li>";
    }).join("") + "</ul>";
    return X.card({ title: t("dd.top"), sub: t("dd.topSub"), body: S.st === "data" ? (rows.length ? html : X.empty(t("dd.topEmpty"))) : S.st === "error" ? X.errBody() : S.st === "loading" ? X.skRows(5) : '<div style="min-height:180px"></div>' });
  }
  function eventsCard() {
    var list = (S.d && S.d.events) || [];
    var html = '<ul class="rows pb">' + list.map(function (e) {
      var flood = e.type === "ddos-flood";
      return '<li class="row"><span class="ev-ico ' + (flood ? "ban" : "ok") + '">' + X.ic(flood ? "zap" : "shield-ban") + '</span><div class="row-main"><p class="ev-text"><b>' + X.esc(t("ev." + e.type)) + "</b> · " + X.esc(e.detail || "") + '</p><p class="row-sub">' + X.timeLabel(e.ts, true) + "</p></div></li>";
    }).join("") + "</ul>";
    return X.card({ title: t("dd.ev"), body: S.st === "data" ? (list.length ? html : X.empty(t("dd.evEmpty"))) : S.st === "error" ? X.errBody() : S.st === "loading" ? X.skRows(3) : '<div style="min-height:120px"></div>' });
  }
  function render() {
    EL.innerHTML = '<div id="dd-banner">' + banner() + "</div>" + '<div id="dd-stats-wrap">' + stats() + "</div>" +
      '<div class="grid-3"><div class="col span-2" id="dd-left-col">' + layersCard() + '</div><div class="col" id="dd-right-col">' + topCard() + eventsCard() + "</div></div>" +
      '<p class="info-line">' + X.ic("info") + "<span>" + t("dd.note") + "</span></p>";
  }

  // ---------- dữ liệu ----------
  function load(silent) {
    if (!S.d && !silent) X.gate(S, render);
    return X.api("/api/ddos").then(function (d) {
      var hadPend = S.d && S.d.pending;
      S.d = d; S.left = d.pending ? d.pending.left : 0;
      if (hadPend && !d.pending && !S.busy) X.toast(t("dd.autoUndone"), true);
      tickStart();
      if (S.st === "data") render(); else X.settle(S, "data", render);
    }).catch(function (e) { if (!e.auth && !S.d) X.settle(S, "error", render); });
  }
  function tickStart() {
    clearInterval(TICK); TICK = null;
    if (!S.d || !S.d.pending) return;
    TICK = setInterval(function () {
      S.left = Math.max(0, S.left - 1);
      var n = document.getElementById("dd-left"), tx = document.getElementById("dd-left-text");
      if (n) n.textContent = S.left;
      if (tx) tx.textContent = t("dd.pendText", { s: S.left });
      if (S.left <= 0) { clearInterval(TICK); TICK = null; setTimeout(function () { load(true); }, 1500); }
    }, 1000);
  }
  function post(path, body) {
    S.busy = true; render();
    return X.api(path, { method: "POST", body: JSON.stringify(body || {}) }).finally(function () { S.busy = false; });
  }
  function fail(e) {
    if (e.code === "origin_not_ready") {
      var list = String(e.detail || "").split(": ").slice(1).join(": ");
      X.notify("warning", t("dd.originNotReady"), t("dd.originNotReadyText", { list: list }));
    } else if (e.code === "ddos_pending") X.toast(t("dd.pendBusy"), true);
    else X.notify("error", X.errMsg(e));
    load(true);
  }
  function toggle(key) {
    var on = !S.d.cfg[key], layers = {}; layers[key] = on;
    S.d.cfg[key] = on;                        // đổi ngay trên màn, lỗi thì nạp lại
    post("/api/ddos/apply", { layers: layers }).then(function () { load(true); }).catch(fail);
  }
  function recommended() {
    var d = S.d, keys = d.layers.map(function (l) { return l.key; }).filter(function (k) { return !d.cfg[k] && (k !== "origin" || d.origin.ok); });
    var text = t("dd.recText", { what: whatText(keys.length ? keys : ["syn"]) }) + (d.origin.ok ? "" : " " + t("dd.recNoOrigin"));
    var go = function () { post("/api/ddos/recommended").then(function () { load(true); }).catch(fail); };
    if (!window.Swal) return go();
    Swal.fire({ icon: "question", title: t("dd.recTitle"), text: text, showCancelButton: true, confirmButtonText: t("dd.recGo"), cancelButtonText: t("common.cancel"), reverseButtons: true })
      .then(function (r) { if (r.isConfirmed) go(); });
  }
  function editTh(key) {
    var d = S.d, ks = LAYER_TH[key];
    var html = ks.map(function (k) {
      return '<div class="field" style="text-align:left;margin-top:12px"><label for="dd-th-' + k + '">' + t("dd.th." + k) + '</label><input class="input" id="dd-th-' + k + '" type="number" min="1" value="' + d.th[k] + '"></div>';
    }).join("");
    if (!window.Swal) return;
    Swal.fire({ title: t("dd.thTitle", { l: t("dd.l." + key) }), html: html, showCancelButton: true, confirmButtonText: t("dd.thSave"), cancelButtonText: t("common.cancel"), reverseButtons: true,
      preConfirm: function () { var o = {}; ks.forEach(function (k) { o[k] = parseInt(document.getElementById("dd-th-" + k).value, 10) || d.th[k]; }); return o; }
    }).then(function (r) {
      if (!r.isConfirmed) return;
      post("/api/ddos/apply", { th: r.value }).then(function (res) { if (!res.pending) X.toast(t("dd.thSaved")); load(true); }).catch(fail);
    });
  }

  function bind() {
    EL.addEventListener("click", function (e) {
      var sw = e.target.closest("[data-layer]");
      if (sw && !sw.disabled) { toggle(sw.dataset.layer); return; }
      var th = e.target.closest("[data-th]");
      if (th && !th.disabled) { editTh(th.dataset.th); return; }
      var b = e.target.closest("[data-act]"); if (!b) return;
      var a = b.dataset.act;
      if (a === "retry") load();
      else if (a === "recommended") recommended();
      else if (a === "confirm") post("/api/ddos/confirm").then(function () { S.d.pending = null; X.toast(t("dd.kept")); load(true); }).catch(fail);
      else if (a === "revert") post("/api/ddos/revert").then(function () { S.d.pending = null; X.toast(t("dd.undone")); load(true); }).catch(fail);
      else if (a === "ban") X.ban([b.dataset.ip]);
      else if (a === "block-top") X.ban(blockable().slice(0, 5));
    });
  }
  window.E2BPages = window.E2BPages || {};
  window.E2BPages.ddos = {
    show: function (el, ctx) {
      X = ctx;
      if (EL !== el) { EL = el; bind(); }
      render();
      load();
      clearInterval(POLL);
      // số liệu sống: hỏi lại mỗi 5 giây khi đang mở màn này
      POLL = setInterval(function () {
        if (!EL.isConnected || EL.classList.contains("hidden")) { clearInterval(POLL); POLL = null; clearInterval(TICK); TICK = null; return; }
        if (!document.hidden && !S.busy && S.st === "data") load(true);
      }, 5000);
    }
  };
})();
