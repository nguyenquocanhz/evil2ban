/* charts.js — bieu do canvas sieu nhe, khong phu thuoc (line / bars / candlestick).
   API: E2BChart.render(canvasEl, {type:'line'|'bars'|'candles', ...}) */
(function (global) {
  "use strict";
  var CSS = getComputedStyle(document.documentElement);
  function v(n, f) { return (CSS.getPropertyValue(n) || "").trim() || f; }
  var COL = {
    grid: "#26262c", axis: "#8b8b94", fg: "#e7e7ea",
    line: v("--accent2", "#4993e0"), bar: v("--accent2", "#4993e0"),
    up: v("--ok", "#30a46c"), down: v("--accent", "#e5484d"),
  };
  var PAD = { l: 48, r: 14, t: 14, b: 34 };

  function setup(cv) {
    var dpr = global.devicePixelRatio || 1;
    var w = cv.clientWidth, h = cv.clientHeight;
    cv.width = w * dpr; cv.height = h * dpr;
    var ctx = cv.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    return { ctx: ctx, w: w, h: h };
  }
  function niceMax(m) {
    if (m <= 0) return 1;
    var p = Math.pow(10, Math.floor(Math.log10(m)));
    var r = m / p;
    var s = r <= 1 ? 1 : r <= 2 ? 2 : r <= 5 ? 5 : 10;
    return s * p;
  }
  function fmt(n) {
    if (n >= 1e6) return (n / 1e6).toFixed(1) + "M";
    if (n >= 1e3) return (n / 1e3).toFixed(1) + "k";
    return "" + n;
  }

  function axes(ctx, w, h, maxV, labels, opts) {
    var x0 = PAD.l, y0 = h - PAD.b, x1 = w - PAD.r, y1 = PAD.t;
    ctx.font = "11px ui-monospace,Menlo,monospace";
    ctx.textBaseline = "middle";
    // grid + y labels
    var steps = 4;
    for (var i = 0; i <= steps; i++) {
      var yy = y0 - (y0 - y1) * (i / steps);
      ctx.strokeStyle = COL.grid; ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(x0, yy); ctx.lineTo(x1, yy); ctx.stroke();
      ctx.fillStyle = COL.axis; ctx.textAlign = "right";
      ctx.fillText(fmt(Math.round(maxV * i / steps)), x0 - 8, yy);
    }
    // x labels (thua ra de khong chong)
    var n = labels.length;
    var every = Math.max(1, Math.ceil(n / (opts.xticks || 8)));
    ctx.textAlign = "center"; ctx.fillStyle = COL.axis;
    for (var j = 0; j < n; j++) {
      if (j % every !== 0 && j !== n - 1) continue;
      var xx = x0 + (x1 - x0) * (n === 1 ? 0.5 : j / (n - 1));
      var lab = labels[j]; lab = lab.length > 7 ? lab.slice(5) : lab;
      ctx.fillText(lab, xx, y0 + 16);
    }
    return { x0: x0, y0: y0, x1: x1, y1: y1 };
  }

  function render(cv, o) {
    var s = setup(cv), ctx = s.ctx, w = s.w, h = s.h;
    ctx.clearRect(0, 0, w, h);
    var labels = o.labels || [];
    if (!labels.length) {
      ctx.fillStyle = COL.axis; ctx.font = "13px sans-serif";
      ctx.textAlign = "center"; ctx.textBaseline = "middle";
      ctx.fillText(o.empty || "Chua co du lieu", w / 2, h / 2);
      return;
    }
    var maxV;
    if (o.type === "candles") {
      maxV = 0; o.ohlc.forEach(function (c) { if (c.h > maxV) maxV = c.h; });
    } else {
      maxV = Math.max.apply(null, o.data);
    }
    maxV = niceMax(maxV);
    var g = axes(ctx, w, h, maxV, labels, o);
    var n = labels.length;
    function px(i) { return g.x0 + (g.x1 - g.x0) * (n === 1 ? 0.5 : i / (n - 1)); }
    function py(val) { return g.y0 - (g.y0 - g.y1) * (val / maxV); }

    if (o.type === "line") {
      // vung fill mo
      ctx.beginPath();
      o.data.forEach(function (d, i) { i ? ctx.lineTo(px(i), py(d)) : ctx.moveTo(px(i), py(d)); });
      ctx.lineTo(px(n - 1), g.y0); ctx.lineTo(px(0), g.y0); ctx.closePath();
      var grad = ctx.createLinearGradient(0, g.y1, 0, g.y0);
      grad.addColorStop(0, COL.line + "44"); grad.addColorStop(1, COL.line + "00");
      ctx.fillStyle = grad; ctx.fill();
      // duong
      ctx.strokeStyle = COL.line; ctx.lineWidth = 2; ctx.lineJoin = "round";
      ctx.beginPath();
      o.data.forEach(function (d, i) { i ? ctx.lineTo(px(i), py(d)) : ctx.moveTo(px(i), py(d)); });
      ctx.stroke();
      o.data.forEach(function (d, i) {
        ctx.fillStyle = COL.line; ctx.beginPath();
        ctx.arc(px(i), py(d), 2.2, 0, 7); ctx.fill();
      });
    } else if (o.type === "bars") {
      var bw = Math.max(2, (g.x1 - g.x0) / n * 0.62);
      o.data.forEach(function (d, i) {
        var x = px(i), y = py(d);
        ctx.fillStyle = o.color || COL.bar;
        ctx.fillRect(x - bw / 2, y, bw, g.y0 - y);
      });
    } else if (o.type === "candles") {
      var cw = Math.max(2, (g.x1 - g.x0) / n * 0.5);
      o.ohlc.forEach(function (c, i) {
        var x = px(i), up = c.c >= c.o;
        var col = up ? COL.up : COL.down;
        ctx.strokeStyle = col; ctx.fillStyle = col; ctx.lineWidth = 1;
        ctx.beginPath(); ctx.moveTo(x, py(c.h)); ctx.lineTo(x, py(c.l)); ctx.stroke();
        var yO = py(c.o), yC = py(c.c);
        var top = Math.min(yO, yC), bh = Math.max(1, Math.abs(yC - yO));
        ctx.fillRect(x - cw / 2, top, cw, bh);
      });
    }

    // hover tooltip
    attachHover(cv, o, g, px, maxV);
  }

  function attachHover(cv, o, g, px, maxV) {
    var wrap = cv.parentNode;
    var tip = wrap.querySelector(".chart-tip");
    if (!tip) { tip = document.createElement("div"); tip.className = "chart-tip hidden"; wrap.appendChild(tip); }
    var n = o.labels.length;
    cv.onmousemove = function (e) {
      var rect = cv.getBoundingClientRect();
      var mx = e.clientX - rect.left;
      var best = 0, bd = 1e9;
      for (var i = 0; i < n; i++) { var d = Math.abs(px(i) - mx); if (d < bd) { bd = d; best = i; } }
      var txt;
      if (o.type === "candles") {
        var c = o.ohlc[best];
        txt = o.labels[best] + " · O" + c.o + " H" + c.h + " L" + c.l + " C" + c.c;
      } else {
        txt = o.labels[best] + " · " + o.data[best];
      }
      tip.textContent = txt;
      tip.style.left = px(best) + "px";
      tip.style.top = (g.y1 + 4) + "px";
      tip.classList.remove("hidden");
    };
    cv.onmouseleave = function () { tip.classList.add("hidden"); };
  }

  global.E2BChart = { render: render };
})(window);
