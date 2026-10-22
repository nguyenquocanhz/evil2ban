/* Màn Cài đặt — nạp khi mở tới. Mỗi dòng tự lưu, hiện "Đã lưu" cạnh chỗ vừa đổi. */
(function () {
  "use strict";
  var X, S = { st: "wait", set: null, acc: null, tab: "account", restart: false };
  var TABS = ["account", "detect", "notify", "access", "ui"];
  try { S.tab = localStorage.getItem("e2b_set_tab") || "account"; } catch (e) { }
  if (TABS.indexOf(S.tab) < 0) S.tab = "account";

  function v(k) { return S.set && S.set[k] ? S.set[k].value : ""; }
  function isSet(k) { return S.set && S.set[k] && S.set[k].set; }
  function on(k) { return v(k) === "1"; }
  function t(k, o) { return X.t(k, o); }

  // ---------- dòng ----------
  function row(label, ctl, desc, id) {
    return '<div class="set-row"' + (id ? ' id="row-' + id + '"' : "") + '><div class="set-label"><span>' + label + '</span><span class="saved-slot"></span></div>' +
      '<div class="set-ctl">' + ctl + (desc ? '<p class="set-desc">' + desc + "</p>" : "") + "</div></div>";
  }
  function roRow(label, val, action, desc) {
    return '<div class="set-row"><div class="set-label"><span>' + label + '</span></div><div class="set-ro"><div style="min-width:0"><div class="set-ro-val">' + val + "</div>" +
      (desc ? '<p class="set-desc">' + desc + "</p>" : "") + "</div>" + (action ? '<div style="flex-shrink:0">' + action + "</div>" : "") + "</div></div>";
  }
  function section(title, rows, danger) {
    return '<section class="set-section' + (danger ? " danger" : "") + '"><h2 class="set-title">' + title + '</h2><div class="set-box">' + rows.join("") + "</div></section>";
  }
  function sw(key) {
    return '<div class="inline" style="min-height:40px"><button type="button" class="switch" role="switch" aria-checked="' + on(key) + '" data-key="' + key + '"></button>' +
      '<span class="set-desc">' + t(on(key) ? "common.on" : "common.off") + "</span></div>";
  }
  function inp(key, cls, ph, type) {
    var secret = S.set && S.set[key] && S.set[key].secret;
    return '<input class="input ' + (cls || "") + '" data-key="' + key + '" type="' + (type || (secret ? "password" : "text")) + '" autocomplete="off" spellcheck="false" value="' +
      X.esc(secret ? "" : v(key)) + '" placeholder="' + X.esc(secret ? (isSet(key) ? "••••••••••••" : t("set.secretUnset")) : (ph || "")) + '">';
  }
  function segHtml(name, opts, cur) {
    return '<div class="seg" data-seg="' + name + '">' + opts.map(function (o) {
      return '<button type="button" data-val="' + o[0] + '" aria-pressed="' + (o[0] === cur) + '">' + (o[2] ? X.ic(o[2]) : "") + o[1] + "</button>";
    }).join("") + "</div>";
  }
  function testBtn(ch, disabled) {
    return '<div class="inline"><button type="button" class="btn btn-outline btn-md" data-test="' + ch + '"' + (disabled ? " disabled" : "") + ">" + X.ic("send") + t("set.test") + "</button></div>";
  }

  // ---------- từng tab ----------
  function tabAccount() {
    var a = S.acc || {}, ll = a.last_login;
    var last = ll ? X.timeLabel(ll.ts, true) + " · " + X.mono(ll.ip || "?") : t("common.never");
    var ua = ll && ll.ua ? browserOf(ll.ua) : "";
    var link = a.public_url ? '<span class="mono" style="overflow-wrap:anywhere">' + X.esc(a.public_url) + "/?token=••••••••••" + X.esc(a.token_hint) + "</span>" : '<span class="muted">' + t("set.linkNoUrl") + "</span>";
    return section(t("set.accInfo"), [
      roRow(t("set.username"), X.mono(a.username || "—"), "", t("set.usernameDesc")),
      roRow(t("set.lastLogin"), last, "", ua),
      roRow(t("set.password"), a.password_changed ? t("set.pwChanged", { t: X.timeLabel(a.password_changed, true) }) : t("set.pwNever"),
        '<button type="button" class="btn btn-outline" data-act="pw">' + t("set.changePw") + "</button>"),
      row(t("set.email"), inp("mail.admin_email", "", "ten@email.com", "email"), t("set.emailDesc"))
    ]) + section(t("set.link"), [
      roRow(t("set.linkLabel"), link, a.public_url ? '<button type="button" class="btn btn-outline" data-act="copy-link">' + X.ic("copy") + t("common.copy") + "</button>" : "", t("set.linkDesc"))
    ]) + section(t("set.danger"), [
      roRow(t("set.regen"), t("set.regenDesc"), '<button type="button" class="btn btn-danger" data-act="regen">' + t("set.regenGo") + "</button>"),
      roRow(t("set.logoutAll"), t("set.logoutAllDesc"), '<button type="button" class="btn btn-danger" data-act="logout-all">' + t("set.logoutAllGo") + "</button>")
    ], true);
  }
  function tabDetect() {
    return section(t("set.autoBlock"), [
      row(t("set.autoban"), sw("detect.autoban"), t("set.autobanDesc")),
      row(t("set.th404"), '<div class="inline"><div class="w-num">' + inp("detect.autoban_404", "", "40", "number") + '</div><span class="set-desc">' + t("set.th404Unit") + "</span></div>")
    ]) + section(t("set.rate"), [
      row(t("set.rateTh"), '<div class="inline"><div class="w-num">' + inp("detect.rate_alert", "", "120", "number") + '</div><span class="set-desc">' + t("set.rateUnit") + "</span></div>", t("set.rateDesc")),
      row(t("set.onRate"), sw("notify.on_rate"), t("set.onRateDesc"))
    ]) + section(t("set.webBlock"), [
      row(t("set.webBlockRow"), sw("web.block"), S.gate ? t("set.webBlockDesc") : t("set.webGateMissing"))
    ]) + section(t("set.logSrc"), [
      row(t("set.jail"), '<div class="w-mid">' + inp("detect.jail") + "</div>"),
      row(t("set.logDir"), inp("detect.log_dir", "mono-input")),
      row(t("set.tail"), '<div class="w-num">' + inp("detect.tail_lines", "", "4000", "number") + "</div>", t("set.tailDesc")),
      row(t("set.geoip"), sw("detect.geoip"))
    ]);
  }
  function tabNotify() {
    var tg = isSet("notify.telegram_bot_token") && v("notify.telegram_admin_id");
    return section(t("set.channels"), [
      row("Telegram", sw("notify.telegram_on") + '<div class="inline" style="flex-wrap:nowrap"><div style="flex:1;min-width:0">' + inp("notify.telegram_bot_token", "mono-input") + '</div><div class="w-mid">' + inp("notify.telegram_admin_id", "", t("set.tgChat")) + "</div></div>" + testBtn("telegram", !tg),
        isSet("notify.telegram_bot_token") ? t("set.secretSet") : ""),
      row("Slack", sw("notify.slack_on") + inp("notify.slack_webhook", "mono-input", "https://hooks.slack.com/services/…") + testBtn("slack", !isSet("notify.slack_webhook")),
        isSet("notify.slack_webhook") ? t("set.secretSet") : t("set.slackDesc")),
      row("Discord", sw("notify.discord_on") + inp("notify.discord_webhook", "mono-input", "https://discord.com/api/webhooks/…") + testBtn("discord", !isSet("notify.discord_webhook")),
        isSet("notify.discord_webhook") ? t("set.secretSet") : t("set.discordDesc"))
    ]) + section(t("set.sendWhen"), [
      row(t("set.onBan"), sw("notify.on_ban"), t("set.onBanDesc")),
      row(t("set.onRate"), sw("notify.on_rate"), t("set.onRateDesc")),
      row(t("set.onLogin"), sw("notify.on_login_fail"), t("set.onLoginDesc")),
      row(t("set.onDdos"), sw("notify.on_ddos"), t("set.onDdosDesc")),
      row(t("set.onSettings"), sw("notify.on_settings"))
    ]) + section(t("set.mail"), [
      row(t("set.smtp"), '<div class="inline" style="flex-wrap:nowrap"><div style="flex:1;min-width:0">' + inp("mail.smtp_host") + '</div><div class="w-num">' + inp("mail.smtp_port", "", "587", "number") + "</div></div>"),
      row(t("set.gmail"), inp("mail.smtp_user", "", "ten@gmail.com", "email")),
      row(t("set.appPw"), inp("mail.smtp_pass"), t("set.appPwDesc"))
    ]);
  }
  function tabAccess() {
    var a = S.acc || {};
    return section(t("set.accessTitle"), [
      row(t("set.publicUrl"), inp("server.public_url", "", "https://e2b.ten-mien-cua-ban", "url"), t("set.publicUrlDesc")),
      row(t("set.listen"), '<div class="inline" style="flex-wrap:nowrap"><div style="width:160px">' + inp("server.host", "mono-input") + '</div><span class="muted">:</span><div class="w-num">' + inp("server.port", "mono-input", "8793", "number") + "</div></div>", t("set.listenDesc")),
      a.server_ip ? roRow("IP public", X.mono(a.server_ip), '<button type="button" class="btn btn-outline" data-act="copy-ssh">' + X.ic("copy") + "SSH tunnel</button>") : ""
    ]);
  }
  function tabUi() {
    return section(t("set.ui"), [
      row(t("set.theme"), segHtml("theme", [["light", t("set.themeLight"), "sun"], ["dark", t("set.themeDark"), "moon"], ["system", t("set.themeSystem"), "monitor"]], X.themeMode()), t("set.themeDesc")),
      row(t("set.lang"), segHtml("lang", [["vi", "Tiếng Việt"], ["en", "English"]], X.I18N.lang))
    ]);
  }
  function browserOf(ua) {
    var b = /Edg\//.test(ua) ? "Edge" : /Chrome\//.test(ua) ? "Chrome" : /Firefox\//.test(ua) ? "Firefox" : /Safari\//.test(ua) ? "Safari" : "";
    var os = /Windows/.test(ua) ? "Windows" : /Android/.test(ua) ? "Android" : /iPhone|iPad/.test(ua) ? "iOS" : /Mac OS/.test(ua) ? "macOS" : /Linux/.test(ua) ? "Linux" : "";
    return [b, os].filter(Boolean).join(X.I18N.lang === "en" ? " on " : " trên ");
  }

  // ---------- vẽ ----------
  var EL;
  function render() {
    var tabs = '<div class="utabs-wrap"><nav class="utabs">' + TABS.map(function (k) {
      return '<a class="utab" href="#settings" data-tab="' + k + '"' + (S.tab === k ? ' aria-current="page"' : "") + ">" + t("set.tab." + k) + "</a>";
    }).join("") + "</nav></div>";
    var restart = S.restart ? '<div class="banner warn" role="status"><div class="banner-main"><span class="banner-ico">' + X.ic("refresh-cw", "ico-5") + '</span><div><p class="banner-title">' + t("set.restartNeed") + '</p></div></div><button type="button" class="btn btn-outline btn-md" data-act="restart">' + t("set.restart") + "</button></div>" : "";
    var body;
    if (S.st === "wait") body = '<div style="min-height:320px"></div>';
    else if (S.st === "loading") body = '<section class="set-section"><div class="set-box" aria-busy="true">' + [1, 2, 3].map(function () { return '<div class="set-row">' + X.sk("112px") + X.sk("100%", "40px") + "</div>"; }).join("") + "</div></section>";
    else if (S.st === "error") body = X.card({ body: X.errBody() });
    else body = { account: tabAccount, detect: tabDetect, notify: tabNotify, access: tabAccess, ui: tabUi }[S.tab]();
    EL.innerHTML = '<div class="settings">' + tabs + restart + body + "</div>";
  }
  function flashSaved(el) {
    var r = el.closest(".set-row"); if (!r) return;
    var slot = r.querySelector(".saved-slot"); if (!slot) return;
    slot.innerHTML = '<span class="saved">' + X.ic("check") + t("common.saved") + "</span>";
    clearTimeout(slot._t); slot._t = setTimeout(function () { slot.innerHTML = ""; }, 2500);
  }
  function save(data, el) {
    return X.api("/api/settings", { method: "POST", body: JSON.stringify(data) }).then(function (r) {
      Object.keys(data).forEach(function (k) { if (S.set[k]) { if (!S.set[k].secret) S.set[k].value = String(data[k]); S.set[k].set = !!String(data[k]); } });
      if (r.restart) { S.restart = true; render(); }
      else if (el) flashSaved(el);
      return r;
    }).catch(function (e) { X.toast(X.errMsg(e), true); render(); throw e; });
  }
  function load() {
    if (!S.set) X.gate(S, render);
    Promise.all([X.api("/api/settings"), X.api("/api/account")]).then(function (r) {
      S.set = r[0].settings; S.acc = r[1]; S.gate = r[0].web_gate_installed;
      if (S.st === "data") render(); else X.settle(S, "data", render);
    }).catch(function (e) { if (!e.auth) X.settle(S, S.set ? "data" : "error", render); });
  }
  function copy(text) {
    (navigator.clipboard ? navigator.clipboard.writeText(text) : Promise.reject()).then(function () { X.toast(t("common.copied")); })
      .catch(function () { window.prompt(t("common.copy"), text); });
  }

  // ---------- sự kiện ----------
  function bind() {
    EL.addEventListener("click", function (e) {
      var tab = e.target.closest("[data-tab]");
      if (tab) { e.preventDefault(); S.tab = tab.dataset.tab; try { localStorage.setItem("e2b_set_tab", S.tab); } catch (x) { } render(); return; }
      var s = e.target.closest(".switch");
      if (s) {
        var nv = s.getAttribute("aria-checked") !== "true", d = {}; d[s.dataset.key] = nv ? "1" : "0";
        s.setAttribute("aria-checked", String(nv)); s.nextElementSibling.textContent = t(nv ? "common.on" : "common.off");
        save(d, s); return;
      }
      var sg = e.target.closest("[data-seg] button");
      if (sg) {
        var name = sg.parentElement.dataset.seg;
        if (name === "theme") { X.applyTheme(sg.dataset.val); render(); }
        else if (name === "lang") X.setLang(sg.dataset.val);
        return;
      }
      var tb = e.target.closest("[data-test]");
      if (tb) {
        tb.disabled = true;
        X.api("/api/notify/test", { method: "POST", body: JSON.stringify({ channel: tb.dataset.test }) })
          .then(function () { X.toast(t("set.testOk", { c: tb.dataset.test })); }).catch(function (er) { X.toast(X.errMsg(er), true); })
          .finally(function () { tb.disabled = false; });
        return;
      }
      var b = e.target.closest("[data-act]"); if (!b) return;
      var act = b.dataset.act;
      if (act === "retry") load();
      else if (act === "copy-link") X.api("/api/account/link").then(function (r) { copy(r.link); });
      else if (act === "copy-ssh") copy("ssh -N -L " + (S.acc.port || 8793) + ":127.0.0.1:" + (S.acc.port || 8793) + " root@" + S.acc.server_ip);
      else if (act === "pw") changePw();
      else if (act === "regen") X.confirmDanger(t("set.regenConfirm"), t("set.regenDesc"), t("set.regenGo")).then(function (ok) {
        if (!ok) return;
        X.api("/api/account/token", { method: "POST" }).then(function (r) {
          window.Swal && Swal.fire({ icon: "success", title: t("set.regenDone"), html: '<p style="margin:0 0 12px">' + X.esc(t("set.regenDoneText")) + '</p><input class="input mono-input" readonly value="' + X.esc(r.link) + '" onclick="this.select()">',
            confirmButtonText: t("common.copy") }).then(function (x) { if (x.isConfirmed) copy(r.link); });
          load();
        }).catch(function (er) { X.toast(X.errMsg(er), true); });
      });
      else if (act === "logout-all") X.confirmDanger(t("set.logoutAll") + "?", t("set.logoutAllDesc"), t("set.logoutAllGo")).then(function (ok) {
        if (ok) X.api("/api/account/logout-all", { method: "POST" }).then(function () { X.logout(); }).catch(function (er) { X.toast(X.errMsg(er), true); });
      });
      else if (act === "restart") X.api("/api/restart", { method: "POST" }).then(function () {
        X.toast(t("set.restartDone")); S.restart = false;
        var tries = 0, iv = setInterval(function () {
          fetch("/api/health").then(function (r) { if (r.ok && ++tries > 1) { clearInterval(iv); location.reload(); } }).catch(function () { });
        }, 1500);
      });
    });
    // ô nhập: lưu khi rời ô hoặc Enter (ô bí mật để trống = giữ nguyên)
    EL.addEventListener("change", function (e) {
      var i = e.target.closest("input[data-key]"); if (!i) return;
      var secret = S.set[i.dataset.key] && S.set[i.dataset.key].secret;
      if (secret && !i.value) return;
      var d = {}; d[i.dataset.key] = i.value.trim();
      save(d, i).then(function () { if (secret) { i.value = ""; i.placeholder = "••••••••••••"; } }).catch(function () { });
    });
    EL.addEventListener("keydown", function (e) { if (e.key === "Enter" && e.target.matches("input[data-key]")) e.target.blur(); });
  }
  function changePw() {
    if (!window.Swal) return;
    Swal.fire({
      title: t("set.changePw"), showCancelButton: true, confirmButtonText: t("set.changePw"), cancelButtonText: t("common.cancel"), focusConfirm: false,
      html: '<div class="form" style="text-align:left"><div class="field"><label>' + t("set.pwCurrent") + '</label><input id="pw-cur" class="input" type="password" autocomplete="current-password"></div>' +
        '<div class="field"><label>' + t("set.pwNew") + '</label><input id="pw-new" class="input" type="password" autocomplete="new-password" minlength="12"></div></div>',
      preConfirm: function () {
        var cur = document.getElementById("pw-cur").value, nw = document.getElementById("pw-new").value;
        if (nw.length < 12) { Swal.showValidationMessage(X.I18N.err("password_too_short")); return false; }
        return X.api("/api/account/password", { method: "POST", body: JSON.stringify({ current: cur, new: nw }) })
          .catch(function (er) { Swal.showValidationMessage(X.errMsg(er)); return false; });
      }
    }).then(function (r) { if (r.isConfirmed) { X.toast(t("set.pwDone")); load(); } });
  }

  window.E2BPages = window.E2BPages || {};
  window.E2BPages.settings = {
    show: function (el, ctx) {
      X = ctx;
      if (EL !== el) { EL = el; bind(); }
      if (S.set) render();
      load();
    }
  };
})();
