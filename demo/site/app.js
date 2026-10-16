/* OTT Compliance Events Pipeline: static demo.
 * Reads data/fixture.json (exported by demo/export_fixture.py from the real
 * Python pipeline) and renders filters, charts, a rule simulator and a
 * drill-down table. No network calls besides loading that file. */
(function () {
  "use strict";

  var MARKETS = {
    US: "United States", DE: "Germany", FR: "France", EU: "EU (unspecified)",
    CA: "Canada", BR: "Brazil", JP: "Japan", CN: "China", TH: "Thailand",
    ZA: "South Africa", AU: "Australia", TR: "Turkey", SG: "Singapore",
    IT: "Italy", ES: "Spain", NL: "Netherlands", IE: "Ireland",
  };
  var RISK_COLORS = { low: "var(--neutral)", medium: "var(--warning)", high: "var(--critical)" };
  var RISK_LABELS = { low: "Low", medium: "Medium", high: "High" };
  var DSR_STATUS = [
    { key: "on_time", label: "On time", color: "var(--good)" },
    { key: "at_risk", label: "At risk", color: "var(--warning)", light: true },
    { key: "breached", label: "Breached", color: "var(--critical)" },
    { key: "no_rule", label: "No rule pack", color: "var(--neutral)", light: true },
  ];
  var ACTION_LABELS = { consent: "Consent", ad_targeting: "Ad targeting" };
  var RULE_FLAG = /(^eu_privacy_violation$|^multi_country_violation$|_consent_violation$|_ad_targeting_violation$|^auth_or_playback_error$)/;
  var PAGE_SIZE = 20;

  var DATA = null;
  var RULES = null;
  var state = { region: "", reg: "", risk: "", search: "", type: "", flaggedOnly: false, sort: "ts", dir: "desc", page: 0, open: null };

  var $ = function (id) { return document.getElementById(id); };
  function esc(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function fmt(n) { return n.toLocaleString("en-US"); }
  function pct(a, b) { return b ? Math.round((a / b) * 1000) / 10 : 0; }
  function market(code) { return MARKETS[code] || code; }
  function regsFor(region) { return RULES.region_regulations[region] || []; }
  function consentModel(region) {
    var regs = regsFor(region);
    if (!regs.length) return "No rule pack";
    var req = RULES.requirements[regs[0]] || {};
    return regs.join(", ") + (req.consent_required ? ", opt-in" : ", opt-out");
  }
  function requiresConsent(region) {
    return regsFor(region).some(function (r) { return (RULES.requirements[r] || {}).consent_required; });
  }
  function shortTime(ts) { return ts.slice(5, 16).replace("T", " "); }

  /* ---------- tooltip ---------- */
  var tip;
  function showTip(html, ev) {
    tip.innerHTML = html;
    tip.hidden = false;
    var x = ev.clientX + 14, y = ev.clientY + 14;
    var r = tip.getBoundingClientRect();
    if (x + r.width > window.innerWidth - 8) x = ev.clientX - r.width - 14;
    if (y + r.height > window.innerHeight - 8) y = ev.clientY - r.height - 14;
    tip.style.left = Math.max(8, x) + "px";
    tip.style.top = Math.max(8, y) + "px";
  }
  function hideTip() { tip.hidden = true; }
  function bindTip(el, htmlFn) {
    el.addEventListener("mousemove", function (e) { showTip(htmlFn(), e); });
    el.addEventListener("mouseleave", hideTip);
  }

  /* ---------- rule port (mirrors src/app/regulations.py) ---------- */
  function checkViolation(action, reg, d) {
    var req = RULES.requirements[reg] || {};
    var violation = false, reason = "";
    if (action === "consent") {
      if (req.consent_required) {
        violation = !d.has_explicit_consent;
        reason = "Explicit consent required but not obtained";
      }
    } else if (action === "ad_targeting") {
      if (req.honor_opt_out_signals) {
        violation = !!d.gpc_signal && !!d.targeted_ad;
        reason = "Targeted ad served despite a Global Privacy Control opt-out signal";
      } else if (req.consent_required) {
        violation = !!d.targeted_ad && !d.has_explicit_consent;
        reason = "Targeted ad served without consent";
      }
    }
    return { violation: violation, reason: reason, regulation: reg, action: action };
  }

  /* The regulation-layer part of evaluate_compliance() in compliance_rules.py.
   * Behavioral signals (anomaly model, network graph, time windows) run only
   * in Python, so the score here is a partial score. */
  function evaluateRules(ev) {
    var flags = [], score = 0;
    if (["error", "login_failed", "token_refresh_failed"].indexOf(ev.type) >= 0) {
      flags.push("auth_or_playback_error");
      score += 3;
    }
    if (ev.is_eu && !ev.consent) {
      flags.push("eu_privacy_violation");
      score += 5;
    }
    var regs = regsFor(ev.region);
    var action = RULES.event_actions[ev.type] || null;
    var violations = [];
    regs.forEach(function (reg) {
      if (!action) return;
      var r = checkViolation(action, reg, {
        has_explicit_consent: ev.consent, is_eu: ev.is_eu, gpc_signal: ev.gpc, targeted_ad: ev.targeted,
      });
      if (r.violation) violations.push(r);
    });
    if (violations.length) {
      flags.push("multi_country_violation");
      violations.forEach(function (v) { flags.push(v.regulation.toLowerCase() + "_" + v.action + "_violation"); });
      score += violations.length * 5;
    }
    if (ev.plan === "premium") score = Math.max(0, score - 1);
    else if (ev.plan === "basic") score += 1;
    return { flags: flags, score: score, violations: violations, regs: regs };
  }

  function ruleFlags(flags) { return flags.filter(function (f) { return RULE_FLAG.test(f); }).sort().join("|"); }

  /* ---------- filtering ---------- */
  function matchMarket(region, regs) {
    if (state.region && region !== state.region) return false;
    if (state.reg === "__none") return regs.length === 0;
    if (state.reg && regs.indexOf(state.reg) < 0) return false;
    return true;
  }
  function filteredEvents() {
    return DATA.events.filter(function (e) {
      if (!matchMarket(e.region, e.regs)) return false;
      if (state.risk && e.risk !== state.risk) return false;
      return true;
    });
  }
  function filteredDsr() {
    return DATA.deletion_requests.filter(function (d) { return matchMarket(d.region, d.regulations); });
  }

  /* ---------- KPIs ---------- */
  function renderKpis(evs, dsr) {
    var optIn = evs.filter(function (e) { return requiresConsent(e.region); });
    var withConsent = optIn.filter(function (e) { return e.consent; }).length;
    var violEvents = evs.filter(function (e) { return e.violations.length; });
    var findings = violEvents.reduce(function (a, e) { return a + e.violations.length; }, 0);
    var high = evs.filter(function (e) { return e.risk === "high"; }).length;
    var medium = evs.filter(function (e) { return e.risk === "medium"; }).length;
    var breached = dsr.filter(function (d) { return d.status === "breached"; }).length;
    var atRisk = dsr.filter(function (d) { return d.status === "at_risk"; }).length;
    var tiles = [
      { label: "Events processed", value: fmt(evs.length), sub: "of " + fmt(DATA.events.length) + " in the run" },
      { label: "Consent coverage", value: optIn.length ? pct(withConsent, optIn.length) + "%" : "n/a", sub: "in opt-in markets (" + fmt(optIn.length) + " events)" },
      { label: "Events with violations", value: fmt(violEvents.length), sub: fmt(findings) + " statutory findings" },
      { label: "High-risk events", value: fmt(high), sub: fmt(medium) + " medium" },
      { label: "Deletion SLA breached", value: fmt(breached), sub: fmt(atRisk) + " at risk, " + fmt(dsr.length) + " requests" },
    ];
    $("kpis").innerHTML = tiles.map(function (t) {
      return '<div class="kpi"><div class="label">' + esc(t.label) + '</div><div class="value">' + esc(t.value) +
        '</div><div class="sub">' + esc(t.sub) + "</div></div>";
    }).join("");
  }

  /* ---------- volume chart (SVG stacked columns) ---------- */
  function renderVolume(evs) {
    var host = $("chart-volume");
    var by = {};
    evs.forEach(function (e) {
      var b = by[e.region] || (by[e.region] = { low: 0, medium: 0, high: 0, total: 0 });
      b[e.risk] += 1; b.total += 1;
    });
    var regions = Object.keys(by).sort(function (a, b) { return by[b].total - by[a].total; });
    if (!regions.length) { host.innerHTML = '<p class="note">No events match these filters.</p>'; return; }
    var W = Math.max(320, host.clientWidth || 640), H = 220;
    var m = { t: 18, r: 8, b: 30, l: 34 };
    var iw = W - m.l - m.r, ih = H - m.t - m.b;
    var max = Math.max.apply(null, regions.map(function (r) { return by[r].total; }));
    var step = niceStep(max);
    var top = Math.ceil(max / step) * step;
    var y = function (v) { return m.t + ih - (v / top) * ih; };
    var band = iw / regions.length;
    var bw = Math.min(56, band * 0.62);
    var svg = ['<svg viewBox="0 0 ' + W + " " + H + '" role="img" aria-label="Event volume by market, stacked by risk level">'];
    svg.push('<g class="axis">');
    for (var v = 0; v <= top; v += step) {
      svg.push('<line x1="' + m.l + '" x2="' + (W - m.r) + '" y1="' + y(v) + '" y2="' + y(v) + '"/>');
      svg.push('<text x="' + (m.l - 6) + '" y="' + (y(v) + 4) + '" text-anchor="end">' + v + "</text>");
    }
    svg.push("</g>");
    regions.forEach(function (r, i) {
      var b = by[r];
      var x = m.l + band * i + (band - bw) / 2;
      var acc = 0;
      svg.push('<g class="col" data-region="' + r + '">');
      svg.push('<rect x="' + (m.l + band * i) + '" y="' + m.t + '" width="' + band + '" height="' + ih + '" fill="transparent"/>');
      ["low", "medium", "high"].forEach(function (k, idx, arr) {
        if (!b[k]) return;
        var y0 = y(acc), y1 = y(acc + b[k]);
        var h = Math.max(1, y0 - y1 - (acc > 0 ? 2 : 0));
        var isTop = arr.slice(idx + 1).every(function (kk) { return !b[kk]; });
        var rx = isTop ? 4 : 0;
        svg.push(segPath(x, y1, bw, h, rx, RISK_COLORS[k]));
        acc += b[k];
      });
      svg.push('<text class="total" x="' + (x + bw / 2) + '" y="' + (y(b.total) - 6) + '" text-anchor="middle">' + b.total + "</text>");
      svg.push('<text class="xlab" x="' + (x + bw / 2) + '" y="' + (H - 10) + '" text-anchor="middle">' + r + "</text>");
      svg.push("</g>");
    });
    svg.push("</svg>");
    host.innerHTML = svg.join("");
    host.querySelectorAll(".col").forEach(function (g) {
      var r = g.getAttribute("data-region"), b = by[r];
      bindTip(g, function () {
        return "<b>" + esc(market(r)) + "</b> (" + esc(consentModel(r)) + ")<br>" + b.total + " events<br>" +
          ["high", "medium", "low"].map(function (k) {
            return '<i style="background:' + RISK_COLORS[k] + '"></i>' + RISK_LABELS[k] + ": " + b[k];
          }).join("<br>");
      });
    });
  }
  function niceStep(max) {
    var raw = max / 4, p = Math.pow(10, Math.floor(Math.log10(Math.max(1, raw))));
    var n = raw / p;
    return (n <= 1 ? 1 : n <= 2 ? 2 : n <= 5 ? 5 : 10) * p;
  }
  /* A bar segment with only the top corners rounded (data end), flat at the base. */
  function segPath(x, y, w, h, r, fill) {
    r = Math.min(r, h, w / 2);
    var d = "M" + x + "," + (y + h) + "V" + (y + r) + (r ? "Q" + x + "," + y + " " + (x + r) + "," + y : "") +
      "H" + (x + w - r) + (r ? "Q" + (x + w) + "," + y + " " + (x + w) + "," + (y + r) : "") + "V" + (y + h) + "Z";
    return '<path class="seg" d="' + d + '" fill="' + fill + '"/>';
  }

  /* ---------- horizontal bar helpers ---------- */
  function hrow(name, sub, parts, total, valText, tipHtml, empty) {
    var row = document.createElement("div");
    row.className = "hrow" + (empty ? " empty" : "");
    var bars = parts.map(function (p) {
      var w = total ? (p.value / total) * 100 : 0;
      return w > 0 ? '<b style="width:' + w + "%;background:" + p.color + '"></b>' : "";
    }).join("");
    row.innerHTML = '<div class="name">' + esc(name) + (sub ? "<small>" + esc(sub) + "</small>" : "") +
      '</div><div class="track">' + bars + '</div><div class="val">' + esc(valText) + "</div>";
    if (tipHtml) bindTip(row, function () { return tipHtml; });
    return row;
  }

  function renderConsent(evs) {
    var host = $("chart-consent");
    host.innerHTML = "";
    var by = {};
    evs.forEach(function (e) {
      var b = by[e.region] || (by[e.region] = { n: 0, c: 0 });
      b.n += 1; if (e.consent) b.c += 1;
    });
    var regions = Object.keys(by).sort(function (a, b) { return pct(by[a].c, by[a].n) - pct(by[b].c, by[b].n); });
    if (!regions.length) { host.innerHTML = '<p class="note">No events match these filters.</p>'; return; }
    regions.forEach(function (r) {
      var b = by[r], p = pct(b.c, b.n);
      var optIn = requiresConsent(r);
      host.appendChild(hrow(
        market(r), consentModel(r),
        [{ value: b.c, color: optIn ? "var(--accent)" : "var(--accent-2)" }], b.n, p + "%",
        "<b>" + esc(market(r)) + "</b><br>" + b.c + " of " + b.n + " events with consent<br>" +
          (optIn ? "Consent required before processing" : regsFor(r).length ? "Opt-out regime: consent not required" : "No regulation configured for this market")
      ));
    });
    var note = document.createElement("p");
    note.className = "note";
    note.textContent = "Dark bars: markets where the rule pack requires opt-in consent. Light bars: opt-out or unconfigured markets.";
    host.appendChild(note);
  }

  function renderViolations(evs) {
    var host = $("chart-violations");
    host.innerHTML = "";
    var regs = {};
    evs.forEach(function (e) { e.regs.forEach(function (r) { regs[r] = regs[r] || { consent: 0, ad_targeting: 0, checked: 0 }; regs[r].checked += 1; }); });
    evs.forEach(function (e) { e.violations.forEach(function (v) { regs[v.regulation][v.action] += 1; }); });
    var names = Object.keys(regs).sort(function (a, b) {
      return (regs[b].consent + regs[b].ad_targeting) - (regs[a].consent + regs[a].ad_targeting);
    });
    var max = Math.max.apply(null, names.map(function (n) { return regs[n].consent + regs[n].ad_targeting; }).concat([1]));
    names.forEach(function (n) {
      var r = regs[n], total = r.consent + r.ad_targeting;
      var markets = Object.keys(RULES.region_regulations).filter(function (k) { return RULES.region_regulations[k].indexOf(n) >= 0; });
      var marketLabel = markets.length > 3 ? "EU and member states" : markets.map(market).join(", ");
      var row = hrow(n, marketLabel, [
        { value: r.consent, color: "var(--accent)" },
        { value: r.ad_targeting, color: "var(--accent-2)" },
      ], max, String(total),
      "<b>" + esc(n) + "</b> (" + esc(marketLabel) + ")<br>" + r.checked + " events checked<br>" +
        '<i style="background:var(--accent)"></i>Consent: ' + r.consent + '<br><i style="background:var(--accent-2)"></i>Ad targeting: ' + r.ad_targeting,
      total === 0);
      host.appendChild(row);
    });
    var unchecked = evs.filter(function (e) { return !e.regs.length; });
    if (unchecked.length) {
      var mk = Array.from(new Set(unchecked.map(function (e) { return e.region; }))).join(", ");
      host.appendChild(hrow("No rule pack", mk, [], 1, "n/a",
        "<b>No rule pack</b><br>" + unchecked.length + " events from " + esc(mk) + " were not checked against any regulation. The gap is shown on purpose.", true));
    }
    if (!names.length && !unchecked.length) host.innerHTML = '<p class="note">No events match these filters.</p>';
  }

  /* ---------- deletion requests ---------- */
  function renderDsr(dsr) {
    var counts = {};
    DSR_STATUS.forEach(function (s) { counts[s.key] = 0; });
    dsr.forEach(function (d) { counts[d.status] += 1; });
    var bar = $("dsr-bar");
    bar.setAttribute("aria-label", DSR_STATUS.map(function (s) { return s.label + " " + counts[s.key]; }).join(", "));
    bar.innerHTML = DSR_STATUS.map(function (s) {
      var w = dsr.length ? (counts[s.key] / dsr.length) * 100 : 0;
      return w ? '<b class="' + (s.light ? "light" : "") + '" data-k="' + s.key + '" style="width:' + w + "%;background:" + s.color + '">' + (w > 6 ? counts[s.key] : "") + "</b>" : "";
    }).join("");
    bar.querySelectorAll("b").forEach(function (b) {
      var s = DSR_STATUS.filter(function (x) { return x.key === b.getAttribute("data-k"); })[0];
      bindTip(b, function () { return "<b>" + s.label + "</b><br>" + counts[s.key] + " of " + dsr.length + " requests (" + pct(counts[s.key], dsr.length) + "%)"; });
    });
    $("dsr-legend").innerHTML = DSR_STATUS.map(function (s) {
      return '<span><i style="background:' + s.color + '"></i>' + s.label + " " + counts[s.key] + "</span>";
    }).join("");

    var host = $("dsr-by-reg");
    host.innerHTML = "";
    var by = {};
    dsr.forEach(function (d) {
      var k = d.regulations.length ? d.regulations.join(", ") : "None";
      var b = by[k] || (by[k] = { n: 0, markets: {} });
      DSR_STATUS.forEach(function (s) { b[s.key] = b[s.key] || 0; });
      b[d.status] += 1; b.n += 1; b.markets[d.region] = 1;
    });
    Object.keys(by).sort(function (a, b) { return by[b].n - by[a].n; }).forEach(function (k) {
      var b = by[k];
      var mk = Object.keys(b.markets).join(", ");
      host.appendChild(hrow(k, mk, DSR_STATUS.map(function (s) { return { value: b[s.key], color: s.color }; }), b.n, String(b.n),
        "<b>" + esc(k) + "</b> (" + esc(mk) + ")<br>" + DSR_STATUS.map(function (s) {
          return '<i style="background:' + s.color + '"></i>' + s.label + ": " + b[s.key];
        }).join("<br>")));
    });

    var attention = dsr.filter(function (d) { return d.status === "breached" || d.status === "at_risk"; })
      .sort(function (a, b) {
        if (a.state !== b.state) return a.state === "open" ? -1 : 1;
        return b.elapsed_days - a.elapsed_days;
      });
    $("dsr-list").innerHTML = attention.length ? attention.map(function (d) {
      var label = d.status === "breached" ? "Breached" : "At risk";
      var detail = d.state === "open" ? "open, " + market(d.region) : "closed late, " + market(d.region);
      return '<li><span class="pill ' + d.status + '">' + label + '</span><span class="who">' + esc(d.id) + " " + esc(d.user_id) +
        "<small>" + esc(d.regulations.join(", ") || "no rule pack") + ", " + esc(detail) + '</small></span><span class="days">' +
        Math.floor(d.elapsed_days) + " / " + d.deadline_days + "d</span></li>";
    }).join("") : '<li class="muted">Nothing breached or at risk for this filter.</li>';
  }

  /* ---------- table ---------- */
  function tableRows(evs) {
    var q = state.search.trim().toLowerCase();
    var rows = evs.filter(function (e) {
      if (state.type && e.type !== state.type) return false;
      if (state.flaggedOnly && !e.violations.length) return false;
      if (!q) return true;
      return (e.id + " " + e.user + " " + e.content + " " + e.region + " " + e.flags.join(" ")).toLowerCase().indexOf(q) >= 0;
    });
    var key = state.sort, dir = state.dir === "asc" ? 1 : -1;
    var rank = { low: 0, medium: 1, high: 2 };
    rows.sort(function (a, b) {
      var va = a[key], vb = b[key];
      if (key === "risk") { va = rank[va]; vb = rank[vb]; }
      if (va < vb) return -dir;
      if (va > vb) return dir;
      return a.id < b.id ? 1 : -1;
    });
    return rows;
  }

  function renderTable(evs) {
    var rows = tableRows(evs);
    var pages = Math.max(1, Math.ceil(rows.length / PAGE_SIZE));
    state.page = Math.min(state.page, pages - 1);
    var slice = rows.slice(state.page * PAGE_SIZE, (state.page + 1) * PAGE_SIZE);
    $("t-count").textContent = fmt(rows.length) + " events";
    $("t-page").textContent = "Page " + (state.page + 1) + " of " + pages;
    $("t-prev").disabled = state.page === 0;
    $("t-next").disabled = state.page >= pages - 1;
    document.querySelectorAll(".events th[data-sort]").forEach(function (th) {
      if (th.getAttribute("data-sort") === state.sort) th.setAttribute("data-dir", state.dir);
      else th.removeAttribute("data-dir");
    });
    if (!slice.length) {
      $("t-body").innerHTML = '<tr><td colspan="8" class="muted">No events match.</td></tr>';
      return;
    }
    $("t-body").innerHTML = slice.map(function (e) {
      var flags = e.flags.length ? e.flags.map(function (f) {
        return '<span class="flag' + (/_violation$/.test(f) ? " reg" : "") + '">' + esc(f) + "</span>";
      }).join("") : '<span class="muted">none</span>';
      var html = '<tr class="row" data-id="' + esc(e.id) + '" tabindex="0" aria-expanded="' + (state.open === e.id) + '">' +
        '<td class="mono">' + esc(shortTime(e.ts)) + '</td><td class="mono">' + esc(e.id) + "</td><td>" + esc(e.region) +
        '</td><td class="mono">' + esc(e.type) + "</td><td>" + (e.consent ? "Yes" : "<b>No</b>") +
        '</td><td class="num">' + e.score.toFixed(1) + '</td><td><span class="pill ' + e.risk + '">' + RISK_LABELS[e.risk] +
        "</span></td><td>" + flags + "</td></tr>";
      if (state.open === e.id) html += detailRow(e);
      return html;
    }).join("");
  }

  function detailRow(e) {
    var viol = e.violations.length ? "<ul>" + e.violations.map(function (v) {
      return "<li><b>" + esc(v.regulation) + "</b> " + esc(ACTION_LABELS[v.action] || v.action) + ": " + esc(v.reason) + "</li>";
    }).join("") + "</ul>" : '<span class="muted">No statutory violations</span>';
    var items = [
      ["Subscriber", e.user], ["Device", e.device], ["Title", e.content], ["Plan", e.plan || "n/a"],
      ["Market", market(e.region) + " (" + consentModel(e.region) + ")"],
      ["Signals", "consent " + (e.consent ? "yes" : "no") + ", GPC " + (e.gpc ? "on" : "off") + ", targeted " + (e.targeted ? "yes" : "no")],
      ["Timestamp", e.ts], ["Pipeline score", e.score + " (" + e.risk + ")"],
    ];
    return '<tr class="detail"><td colspan="8"><dl class="detail-grid">' + items.map(function (i) {
      return "<div><dt>" + esc(i[0]) + "</dt><dd>" + esc(i[1]) + "</dd></div>";
    }).join("") + '</dl><div style="margin-top:10px"><b>Regulation findings</b><div class="small">'  + viol + "</div></div></td></tr>";
  }

  /* ---------- simulator ---------- */
  function simEvent() {
    var region = $("s-region").value;
    var type = $("s-type").value;
    return {
      region: region, type: type, plan: $("s-plan").value,
      is_eu: regsFor(region).indexOf("GDPR") >= 0,
      consent: $("s-consent").checked,
      targeted: type === "ad_impression" && $("s-targeted").checked,
      gpc: $("s-gpc").checked,
    };
  }
  function syncSimControls() {
    var ad = $("s-type").value === "ad_impression";
    $("s-targeted").disabled = !ad;
    $("s-targeted").parentElement.style.opacity = ad ? 1 : 0.5;
  }
  function runSim() {
    var ev = simEvent();
    var r = evaluateRules(ev);
    var out = $("sim-out");
    var hit = r.violations.length > 0 || r.flags.indexOf("eu_privacy_violation") >= 0;
    var level = r.score >= 8 ? "high" : r.score >= 5 ? "medium" : "low";
    out.className = "sim-out " + (hit ? "flagged" : "clean");
    var rulesLine = r.regs.length ? "Checked against " + r.regs.join(", ") + " (" + consentModel(ev.region) + ")." :
      "No rule pack is configured for " + market(ev.region) + ", so no regulation check runs. This is the coverage gap the dashboard surfaces.";
    var html = '<div class="verdict"><span class="pill ' + (hit ? "high" : "low") + '">' + (hit ? "Violation flagged" : "No violation") + "</span></div>";
    html += '<p class="small" style="margin:4px 0">' + esc(rulesLine) + "</p>";
    if (r.violations.length) {
      html += "<ul>" + r.violations.map(function (v) { return "<li><b>" + esc(v.regulation) + "</b>: " + esc(v.reason) + "</li>"; }).join("") + "</ul>";
    }
    html += '<div style="margin-top:8px">' + (r.flags.length ? r.flags.map(function (f) {
      return '<span class="flag' + (/_violation$/.test(f) ? " reg" : "") + '">' + esc(f) + "</span>";
    }).join("") : '<span class="muted small">No flags</span>') + "</div>";
    html += '<p class="score">Rule-layer score <b>' + r.score + '</b>, indicative level <span class="pill ' + level + '">' + RISK_LABELS[level] +
      "</span> at the default high threshold of 8.0. The full pipeline adds behavioral signals and adapts the threshold by hour, segment and market.</p>";
    out.innerHTML = html;
  }
  function preset(p) {
    if (p === "gdpr") {
      $("s-region").value = "DE"; $("s-type").value = "play"; $("s-consent").checked = false;
      $("s-gpc").checked = false; $("s-targeted").checked = false; $("s-plan").value = "basic";
    } else {
      $("s-region").value = "US"; $("s-type").value = "ad_impression"; $("s-consent").checked = true;
      $("s-gpc").checked = true; $("s-targeted").checked = true; $("s-plan").value = "basic";
    }
    syncSimControls();
    runSim();
  }

  /* ---------- replay + parity ---------- */
  var replayTimer = null;
  function parity() {
    var agree = 0;
    DATA.events.forEach(function (e) { if (ruleFlags(evaluateRules(e).flags) === ruleFlags(e.flags)) agree += 1; });
    $("parity").textContent = "Browser rule port agrees with the Python pipeline's rule flags on " + agree + " of " +
      DATA.events.length + " recorded events.";
  }
  function stopReplay() {
    clearInterval(replayTimer); replayTimer = null;
    $("replay-btn").textContent = "Replay events";
  }
  function startReplay() {
    var evs = filteredEvents().slice().sort(function (a, b) { return a.ts < b.ts ? -1 : a.ts > b.ts ? 1 : 0; });
    var ticker = $("ticker");
    ticker.innerHTML = "";
    var i = 0, flagged = 0;
    $("replay-btn").textContent = "Stop";
    replayTimer = setInterval(function () {
      if (i >= evs.length) { stopReplay(); return; }
      var e = evs[i++];
      var r = evaluateRules(e);
      var hit = r.violations.length > 0 || r.flags.indexOf("eu_privacy_violation") >= 0;
      if (hit) flagged += 1;
      var li = document.createElement("li");
      li.className = hit ? "hit" : "";
      li.innerHTML = '<span class="id">' + esc(e.id) + "</span><span>" + esc(e.region) + '</span><span class="mono small">' + esc(e.type) +
        (e.consent ? "" : ", no consent") + (e.gpc ? ", GPC" : "") + '</span><span class="flags">' +
        (hit ? r.flags.filter(function (f) { return /_violation$/.test(f) && f !== "multi_country_violation"; }).map(function (f) {
          return '<span class="flag reg">' + esc(f) + "</span>";
        }).join("") : '<span class="muted small">pass</span>') + "</span>";
      ticker.insertBefore(li, ticker.firstChild);
      while (ticker.children.length > 7) ticker.removeChild(ticker.lastChild);
      $("parity").textContent = "Replayed " + i + " of " + evs.length + " events, " + flagged + " flagged by the rule port.";
    }, 140);
  }

  /* ---------- wiring ---------- */
  function renderAll() {
    var evs = filteredEvents();
    var dsr = filteredDsr();
    renderKpis(evs, dsr);
    renderVolume(evs);
    renderConsent(evs);
    renderViolations(evs);
    renderDsr(dsr);
    renderTable(evs);
  }

  function fillSelect(el, items) {
    items.forEach(function (it) {
      var o = document.createElement("option");
      o.value = it[0]; o.textContent = it[1];
      el.appendChild(o);
    });
  }

  function init(data) {
    DATA = data;
    RULES = data.rules;
    tip = $("tooltip");
    var meta = data.meta;
    $("meta").innerHTML = [
      ["Generated", meta.generated_at.replace("T", " ").replace("Z", " UTC")],
      ["Events", meta.events_processed + " processed of " + meta.events_sent + " sent"],
      ["Deletion requests", String(data.deletion_requests.length)],
      ["Seed", String(meta.seed)],
    ].map(function (r) { return "<dt>" + esc(r[0]) + "</dt><dd>" + esc(r[1]) + "</dd>"; }).join("");
    $("atrisk-days").textContent = meta.at_risk_window_days;
    $("vol-legend").innerHTML = ["high", "medium", "low"].map(function (k) {
      return '<span><i style="background:' + RISK_COLORS[k] + '"></i>' + RISK_LABELS[k] + " risk</span>";
    }).join("");
    $("viol-legend").innerHTML = '<span><i style="background:var(--accent)"></i>Consent rule</span>' +
      '<span><i style="background:var(--accent-2)"></i>Ad targeting rule</span>';

    var regions = Array.from(new Set(data.events.map(function (e) { return e.region; }))).sort();
    fillSelect($("f-region"), regions.map(function (r) { return [r, r + " " + market(r)]; }));
    var regs = Array.from(new Set(data.events.reduce(function (a, e) { return a.concat(e.regs); }, []))).sort();
    fillSelect($("f-reg"), regs.map(function (r) { return [r, r]; }).concat([["__none", "None configured"]]));
    var types = Array.from(new Set(data.events.map(function (e) { return e.type; }))).sort();
    fillSelect($("t-type"), types.map(function (t) { return [t, t]; }));
    fillSelect($("s-region"), regions.map(function (r) { return [r, r + " " + market(r) + " (" + consentModel(r) + ")"]; }));

    $("f-region").addEventListener("change", function (e) { state.region = e.target.value; state.page = 0; renderAll(); });
    $("f-reg").addEventListener("change", function (e) { state.reg = e.target.value; state.page = 0; renderAll(); });
    $("f-risk").addEventListener("change", function (e) { state.risk = e.target.value; state.page = 0; renderAll(); });
    $("f-reset").addEventListener("click", function () {
      state.region = state.reg = state.risk = state.search = state.type = "";
      state.flaggedOnly = false; state.page = 0;
      $("f-region").value = $("f-reg").value = $("f-risk").value = $("t-search").value = $("t-type").value = "";
      $("t-flagged").checked = false;
      renderAll();
    });
    $("t-search").addEventListener("input", function (e) { state.search = e.target.value; state.page = 0; renderTable(filteredEvents()); });
    $("t-type").addEventListener("change", function (e) { state.type = e.target.value; state.page = 0; renderTable(filteredEvents()); });
    $("t-flagged").addEventListener("change", function (e) { state.flaggedOnly = e.target.checked; state.page = 0; renderTable(filteredEvents()); });
    $("t-prev").addEventListener("click", function () { state.page -= 1; renderTable(filteredEvents()); });
    $("t-next").addEventListener("click", function () { state.page += 1; renderTable(filteredEvents()); });
    document.querySelectorAll(".events th[data-sort]").forEach(function (th) {
      th.addEventListener("click", function () {
        var k = th.getAttribute("data-sort");
        if (state.sort === k) state.dir = state.dir === "asc" ? "desc" : "asc";
        else { state.sort = k; state.dir = k === "ts" || k === "score" || k === "risk" ? "desc" : "asc"; }
        renderTable(filteredEvents());
      });
    });
    function toggleRow(tr) {
      var id = tr.getAttribute("data-id");
      state.open = state.open === id ? null : id;
      renderTable(filteredEvents());
    }
    $("t-body").addEventListener("click", function (e) {
      var tr = e.target.closest("tr.row");
      if (tr) toggleRow(tr);
    });
    $("t-body").addEventListener("keydown", function (e) {
      var tr = e.target.closest("tr.row");
      if (tr && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); toggleRow(tr); }
    });

    $("sim-form").addEventListener("submit", function (e) { e.preventDefault(); runSim(); });
    $("s-type").addEventListener("change", syncSimControls);
    $("s-preset-gdpr").addEventListener("click", function () { preset("gdpr"); });
    $("s-preset-ccpa").addEventListener("click", function () { preset("ccpa"); });
    $("replay-btn").addEventListener("click", function () { if (replayTimer) stopReplay(); else startReplay(); });
    $("s-region").value = "DE";
    $("s-consent").checked = true;
    syncSimControls();
    parity();

    var resizeTimer;
    window.addEventListener("resize", function () {
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(function () { renderVolume(filteredEvents()); }, 120);
    });
    renderAll();
  }

  fetch("data/fixture.json")
    .then(function (r) {
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.json();
    })
    .then(init)
    .catch(function (err) {
      document.querySelector("main").insertAdjacentHTML("afterbegin",
        '<p class="card">Could not load data/fixture.json (' + esc(err.message) + "). Serve this folder over HTTP to view the demo.</p>");
    });
})();
