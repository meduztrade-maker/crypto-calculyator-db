"use strict";

/* ============================================================
   Telegram WebApp bootstrap
   ============================================================ */
const tg = window.Telegram ? window.Telegram.WebApp : null;
if (tg) {
  tg.ready();
  tg.expand();
  try {
    tg.setHeaderColor("#0b0f14");
    tg.setBackgroundColor("#0b0f14");
  } catch (e) { /* older client, ignore */ }
}
const INIT_DATA = tg ? tg.initData : "";

/* ============================================================
   API helper
   ============================================================ */
async function api(path, { method = "GET", body = null, isForm = false } = {}) {
  const headers = { "X-Telegram-Init-Data": INIT_DATA };
  let payload = body;
  if (body && !isForm) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }
  const res = await fetch(path, { method, headers, body: payload });
  let data = null;
  try { data = await res.json(); } catch (e) { /* empty body */ }
  if (!res.ok) {
    const msg = (data && data.detail) ? data.detail : `Xatolik (${res.status})`;
    throw new Error(msg);
  }
  return data;
}

/* ============================================================
   Small formatting helpers (mirror bot/utils/formatting.py's dec_str)
   ============================================================ */
function n(v) { return v === null || v === undefined ? 0 : parseFloat(v); }

function fmtDec(v) {
  const num = n(v);
  if (Number.isInteger(num)) return String(num);
  return String(Math.round(num * 10000) / 10000);
}
function fmtR(v) {
  const num = n(v);
  const sign = num > 0 ? "+" : "";
  return `${sign}${fmtDec(num)}R`;
}
function fmtSigned(v) {
  const num = n(v);
  return num >= 0 ? `+${fmtDec(num)}` : fmtDec(num);
}

function toast(msg, type = "") {
  const el = document.getElementById("toast");
  el.textContent = msg;
  el.className = "toast show" + (type ? " " + type : "");
  clearTimeout(toast._t);
  toast._t = setTimeout(() => { el.className = "toast"; }, 2600);
}

function haptic(style = "light") {
  if (tg && tg.HapticFeedback) {
    try { tg.HapticFeedback.impactOccurred(style); } catch (e) {}
  }
}

/* ============================================================
   Bottom sheet
   ============================================================ */
const sheetEl = document.getElementById("sheet");
const sheetBackdrop = document.getElementById("sheetBackdrop");
const sheetContent = document.getElementById("sheetContent");
let activeInterval = null;

function openSheet(html) {
  clearInterval(activeInterval);
  activeInterval = null;
  sheetContent.innerHTML = html;
  sheetEl.classList.add("open");
  sheetBackdrop.classList.add("open");
}
function closeSheet() {
  clearInterval(activeInterval);
  activeInterval = null;
  sheetEl.classList.remove("open");
  sheetBackdrop.classList.remove("open");
  setTimeout(() => { sheetContent.innerHTML = ""; }, 200);
}
sheetBackdrop.addEventListener("click", closeSheet);

/* ============================================================
   Navigation (tabs + screens)
   ============================================================ */
const screens = ["dashboard", "trades", "reports", "alerts", "settings"];
let state = {
  tradesSub: "pending",
  reportsPeriod: "daily",
  me: null,
};

function showScreen(name, opts = {}) {
  screens.forEach((s) => {
    document.getElementById("screen-" + s).classList.toggle("active", s === name);
  });
  document.querySelectorAll(".tab").forEach((t) => {
    t.classList.toggle("active", t.dataset.nav === name);
  });
  if (name === "trades") {
    if (opts.sub) setTradesSub(opts.sub);
    else loadTrades();
  }
  if (name === "reports") loadReports();
  if (name === "alerts") loadAlerts();
  if (name === "dashboard") loadDashboard();
  if (name === "settings") loadSettings();
}

document.querySelectorAll("[data-nav]").forEach((el) => {
  el.addEventListener("click", () => showScreen(el.dataset.nav, { sub: el.dataset.sub }));
});

/* ============================================================
   DASHBOARD
   ============================================================ */
async function loadDashboard() {
  try {
    const [stats, pending, active, alerts] = await Promise.all([
      api("/api/stats?period=daily"),
      api("/api/trades/pending"),
      api("/api/trades/active"),
      api("/api/alerts"),
    ]);

    const heroR = document.getElementById("heroR");
    heroR.textContent = fmtR(stats.total_r);
    heroR.className = "hero-r " + (n(stats.total_r) >= 0 ? "pos" : "neg");
    document.getElementById("heroSub").textContent = `${stats.total_trades} trade · ${fmtDec(stats.win_rate)}% win rate`;

    document.getElementById("qPendingCount").textContent = pending.length;
    document.getElementById("qActiveCount").textContent = active.length;

    const alertsBox = document.getElementById("dashAlerts");
    if (alerts.length === 0) {
      alertsBox.innerHTML = "";
    } else {
      alertsBox.innerHTML = `<div class="section-title">FAOL ALERTLAR</div>` +
        alerts.slice(0, 3).map(alertItemHtml).join("");
    }
  } catch (e) {
    toast(e.message, "error");
  }
}

/* ============================================================
   TRADES
   ============================================================ */
document.querySelectorAll("#tradesSegmented .seg-btn").forEach((btn) => {
  btn.addEventListener("click", () => setTradesSub(btn.dataset.sub));
});

function setTradesSub(sub) {
  state.tradesSub = sub;
  document.querySelectorAll("#tradesSegmented .seg-btn").forEach((b) => {
    b.classList.toggle("active", b.dataset.sub === sub);
  });
  loadTrades();
}

async function loadTrades() {
  const list = document.getElementById("tradesList");
  list.innerHTML = "";
  try {
    const path = state.tradesSub === "recent" ? "/api/trades/recent?limit=5" : `/api/trades/${state.tradesSub}`;
    const trades = await api(path);
    if (trades.length === 0) {
      list.innerHTML = `<div class="empty-state">Bu bo'limda trade yo'q</div>`;
      return;
    }
    list.innerHTML = trades.map((t) => tradeItemHtml(t, state.tradesSub)).join("");
    list.querySelectorAll(".list-item").forEach((el) => {
      el.addEventListener("click", () => openTradeDetail(parseInt(el.dataset.id), state.tradesSub));
    });
  } catch (e) {
    toast(e.message, "error");
  }
}

function statusIcon(status) {
  return { PENDING: "⏳", ACTIVE: "🟢", CLOSED: "✅", MISSED: "⚪", CANCELLED: "⚪" }[status] || "•";
}

function tradeItemHtml(t, mode) {
  let dotClass = "gray", rightText = "", rightClass = "gray";
  if (mode === "pending") {
    dotClass = "gray";
    rightText = `${fmtDec(t.risk_percent)}% risk`;
  } else if (mode === "active") {
    dotClass = "green";
    rightText = `Entry ${fmtDec(t.entry_price)}`;
  } else {
    if (t.status === "CLOSED") {
      dotClass = t.result_type === "SL" ? "red" : (n(t.result_rr) > 0 ? "green" : "gray");
      rightClass = dotClass;
      rightText = t.result_type === "SL" ? "SL" : fmtR(t.result_rr);
    } else {
      dotClass = "gray";
      rightText = t.status;
    }
  }
  return `<div class="list-item" data-id="${t.id}">
    <div class="li-left">
      <span class="li-dot ${dotClass}"></span>
      <div class="li-main">
        <div class="li-title">${t.coin} ${t.direction === "LONG" ? "🟢" : "🔴"}</div>
        <div class="li-sub">${statusIcon(t.status)} ${t.status}</div>
      </div>
    </div>
    <div class="li-right ${rightClass}">${rightText}</div>
  </div>`;
}

async function openTradeDetail(id, mode) {
  try {
    const trades = await api(mode === "recent" ? "/api/trades/recent?limit=5" : `/api/trades/${mode}`);
    const t = trades.find((x) => x.id === id);
    if (!t) { toast("Trade topilmadi", "error"); return; }

    let actionsHtml = "";
    if (mode === "pending") {
      actionsHtml = `
        <button class="primary-btn" data-act="activate">🟢 Activate</button>
        <button class="btn-small full-w" data-act="miss">⚪ Missed / Cancel</button>
        <button class="btn-small full-w danger" data-act="delete">🗑 Delete</button>`;
    } else if (mode === "active") {
      actionsHtml = `
        <div class="btn-row">
          <button class="btn-small" data-act="sl">🛑 SL</button>
          <button class="btn-small" data-act="bu">🟡 B/U</button>
          <button class="btn-small" data-act="tp">🟢 TP</button>
        </div>`;
    } else {
      actionsHtml = `<button class="btn-small full-w danger" data-act="force-delete">🗑 Butunlay o'chirish</button>`;
    }

    openSheet(`
      <div class="sheet-title">${t.coin} ${t.direction === "LONG" ? "🟢 LONG" : "🔴 SHORT"}</div>
      <div class="card">
        <div class="card-row"><span class="card-row-label">Status</span><span class="card-row-value">${statusIcon(t.status)} ${t.status}</span></div>
        <div class="card-row"><span class="card-row-label">Entry</span><span class="card-row-value">${fmtDec(t.entry_price)}</span></div>
        <div class="card-row"><span class="card-row-label">SL</span><span class="card-row-value">${fmtDec(t.stop_loss_price)}</span></div>
        <div class="card-row"><span class="card-row-label">Risk</span><span class="card-row-value">${fmtDec(t.risk_percent)}%</span></div>
        ${t.result_type ? `<div class="card-row"><span class="card-row-label">Natija</span><span class="card-row-value">${t.result_type} (${fmtR(t.result_rr)})</span></div>` : ""}
      </div>
      ${actionsHtml}
    `);

    sheetContent.querySelectorAll("[data-act]").forEach((btn) => {
      btn.addEventListener("click", () => handleTradeAction(t, btn.dataset.act));
    });
  } catch (e) {
    toast(e.message, "error");
  }
}

async function handleTradeAction(t, act) {
  haptic();
  try {
    if (act === "activate") {
      await api(`/api/trades/${t.id}/activate`, { method: "POST" });
      toast("✅ Active qilindi", "success");
      closeSheet(); loadTrades();
    } else if (act === "miss") {
      await api(`/api/trades/${t.id}/miss`, { method: "POST" });
      toast("⚪ Missed deb belgilandi");
      closeSheet(); loadTrades();
    } else if (act === "delete") {
      await api(`/api/trades/${t.id}`, { method: "DELETE" });
      toast("🗑 O'chirildi");
      closeSheet(); loadTrades();
    } else if (act === "force-delete") {
      await api(`/api/trades/${t.id}?force=true`, { method: "DELETE" });
      toast("🗑 O'chirildi");
      closeSheet(); loadTrades();
    } else if (act === "sl") {
      openCloseSheet(t, "SL");
    } else if (act === "bu") {
      openCloseSheet(t, "BU");
    } else if (act === "tp") {
      openCloseSheet(t, "TP");
    }
  } catch (e) {
    toast(e.message, "error");
  }
}

function openCloseSheet(t, kind) {
  const presets = kind === "BU"
    ? ["0.5", "0.75", "1", "1.5", "2", "2.5", "3", "4", "5"]
    : ["1", "1.5", "2", "2.5", "3", "4", "5", "6", "8", "10"];
  const needsRR = kind !== "SL";
  const label = { SL: "🛑 SL", BU: "🟡 B/U", TP: "🟢 TP" }[kind];

  openSheet(`
    <div class="sheet-title">${label} — ${t.coin}</div>
    ${needsRR ? `
      <div class="field">
        <label class="field-label">RR qiymati</label>
        <div class="pill-row" id="rrPills">
          ${presets.map((p) => `<button class="pill" data-rr="${p}">${p}R</button>`).join("")}
        </div>
        <input type="number" step="0.01" inputmode="decimal" class="field-input" id="rrCustom" placeholder="Yoki qo'lda kiriting" style="margin-top:10px">
      </div>` : `<div class="hint-text">Natija: -1R</div>`}
    <div class="field">
      <label class="field-label">📸 Screenshot (ixtiyoriy)</label>
      <div class="upload-box" id="uploadBox">Rasm tanlash uchun bosing</div>
      <input type="file" accept="image/*" id="fileInput" style="display:none">
    </div>
    <button class="primary-btn" id="confirmCloseBtn">Tasdiqlash</button>
  `);

  let selectedRR = needsRR ? null : "-1";
  let fileId = null;

  if (needsRR) {
    sheetContent.querySelectorAll("#rrPills .pill").forEach((p) => {
      p.addEventListener("click", () => {
        sheetContent.querySelectorAll("#rrPills .pill").forEach((x) => x.classList.remove("selected"));
        p.classList.add("selected");
        selectedRR = p.dataset.rr;
        sheetContent.querySelector("#rrCustom").value = "";
      });
    });
    sheetContent.querySelector("#rrCustom").addEventListener("input", (e) => {
      sheetContent.querySelectorAll("#rrPills .pill").forEach((x) => x.classList.remove("selected"));
      selectedRR = e.target.value;
    });
  }

  setupUpload(sheetContent.querySelector("#uploadBox"), sheetContent.querySelector("#fileInput"), (fid) => { fileId = fid; });

  sheetContent.querySelector("#confirmCloseBtn").addEventListener("click", async () => {
    if (needsRR && (!selectedRR || isNaN(parseFloat(selectedRR)))) {
      toast("RR qiymatini kiriting", "error"); return;
    }
    try {
      await api(`/api/trades/${t.id}/close`, {
        method: "POST",
        body: { result_type: kind, rr: needsRR ? selectedRR : "-1", screenshot_file_id: fileId },
      });
      toast(`✅ ${label} bilan yopildi`, "success");
      closeSheet(); loadTrades(); loadDashboard();
    } catch (e) {
      toast(e.message, "error");
    }
  });
}

function setupUpload(box, input, onDone) {
  box.addEventListener("click", () => input.click());
  input.addEventListener("change", async () => {
    const file = input.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      box.classList.add("has-image");
      box.innerHTML = `<img src="${reader.result}">`;
    };
    reader.readAsDataURL(file);

    try {
      const form = new FormData();
      form.append("file", file);
      const res = await api("/api/upload", { method: "POST", body: form, isForm: true });
      onDone(res.file_id);
    } catch (e) {
      toast("Rasm yuklanmadi: " + e.message, "error");
    }
  });
}

/* ---- Add trade ---- */
document.querySelectorAll('[data-action="add-trade"]').forEach((el) => el.addEventListener("click", openAddTradeSheet));

function openAddTradeSheet() {
  const riskPresets = ["0.5", "1", "1.5", "2", "2.5", "3"];
  openSheet(`
    <div class="sheet-title">➕ Trade qo'shish</div>
    <div class="field">
      <label class="field-label">Coin</label>
      <input type="text" class="field-input" id="tCoin" placeholder="BTCUSDT" autocapitalize="characters">
    </div>
    <div class="field">
      <label class="field-label">Yo'nalish</label>
      <div class="pill-row">
        <button class="pill green" data-dir="LONG">🟢 LONG</button>
        <button class="pill red" data-dir="SHORT">🔴 SHORT</button>
      </div>
    </div>
    <div class="field">
      <label class="field-label">Risk %</label>
      <div class="pill-row" id="riskPills">
        ${riskPresets.map((p) => `<button class="pill" data-risk="${p}">${p}%</button>`).join("")}
      </div>
      <input type="number" step="0.01" inputmode="decimal" class="field-input" id="riskCustom" placeholder="Yoki qo'lda kiriting" style="margin-top:10px">
    </div>
    <div class="field">
      <label class="field-label">Entry narxi</label>
      <input type="number" step="any" inputmode="decimal" class="field-input" id="tEntry" placeholder="105000">
    </div>
    <div class="field">
      <label class="field-label">Stop Loss narxi</label>
      <input type="number" step="any" inputmode="decimal" class="field-input" id="tSL" placeholder="103500">
    </div>
    <div class="field">
      <label class="field-label">📸 Screenshot (ixtiyoriy)</label>
      <div class="upload-box" id="uploadBox">Rasm tanlash uchun bosing</div>
      <input type="file" accept="image/*" id="fileInput" style="display:none">
    </div>
    <button class="primary-btn" id="createTradeBtn">Pending sifatida yaratish</button>
  `);

  let direction = null, risk = null, fileId = null;

  sheetContent.querySelectorAll("[data-dir]").forEach((p) => {
    p.addEventListener("click", () => {
      sheetContent.querySelectorAll("[data-dir]").forEach((x) => x.classList.remove("selected"));
      p.classList.add("selected");
      direction = p.dataset.dir;
    });
  });
  sheetContent.querySelectorAll("#riskPills .pill").forEach((p) => {
    p.addEventListener("click", () => {
      sheetContent.querySelectorAll("#riskPills .pill").forEach((x) => x.classList.remove("selected"));
      p.classList.add("selected");
      risk = p.dataset.risk;
      sheetContent.querySelector("#riskCustom").value = "";
    });
  });
  sheetContent.querySelector("#riskCustom").addEventListener("input", (e) => {
    sheetContent.querySelectorAll("#riskPills .pill").forEach((x) => x.classList.remove("selected"));
    risk = e.target.value;
  });

  setupUpload(sheetContent.querySelector("#uploadBox"), sheetContent.querySelector("#fileInput"), (fid) => { fileId = fid; });

  sheetContent.querySelector("#createTradeBtn").addEventListener("click", async () => {
    const coin = sheetContent.querySelector("#tCoin").value.trim().toUpperCase();
    const entry = sheetContent.querySelector("#tEntry").value;
    const sl = sheetContent.querySelector("#tSL").value;
    if (!coin) { toast("Coin nomini kiriting", "error"); return; }
    if (!direction) { toast("Yo'nalishni tanlang", "error"); return; }
    if (!risk || isNaN(parseFloat(risk))) { toast("Risk foizini kiriting", "error"); return; }
    if (!entry || !sl) { toast("Entry va SL narxini kiriting", "error"); return; }

    try {
      await api("/api/trades", {
        method: "POST",
        body: { coin, direction, risk_percent: risk, entry_price: entry, stop_loss_price: sl, screenshot_file_id: fileId },
      });
      toast("✅ Pending trade yaratildi", "success");
      closeSheet();
      showScreen("trades", { sub: "pending" });
    } catch (e) {
      toast(e.message, "error");
    }
  });
}

/* ============================================================
   REPORTS
   ============================================================ */
document.querySelectorAll("#reportsSegmented .seg-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    state.reportsPeriod = btn.dataset.period;
    document.querySelectorAll("#reportsSegmented .seg-btn").forEach((b) => b.classList.toggle("active", b === btn));
    document.getElementById("customDateRow").classList.toggle("hidden", state.reportsPeriod !== "custom");
    if (state.reportsPeriod !== "custom") loadReports();
  });
});
document.getElementById("customApply").addEventListener("click", loadReports);

let equityChart = null;

async function loadReports() {
  try {
    let url = `/api/stats?period=${state.reportsPeriod}`;
    if (state.reportsPeriod === "custom") {
      const s = document.getElementById("customStart").value;
      const e = document.getElementById("customEnd").value;
      if (!s || !e) return;
      const toDMY = (iso) => { const [y, m, d] = iso.split("-"); return `${d}.${m}.${y}`; };
      url += `&start=${toDMY(s)}&end=${toDMY(e)}`;
    }
    const stats = await api(url);
    renderReport(stats);
  } catch (e) {
    toast(e.message, "error");
  }
}

function renderReport(stats) {
  document.getElementById("repLabel").textContent = stats.period_label;
  const repR = document.getElementById("repR");
  repR.textContent = fmtR(stats.total_r);
  repR.className = "hero-r " + (n(stats.total_r) >= 0 ? "pos" : "neg");
  document.getElementById("repSub").textContent = `${stats.total_trades} trade · ${fmtDec(stats.win_rate)}% win rate`;

  const streakEl = document.getElementById("repStreak");
  if (stats.streak_count > 0 && stats.streak_kind !== "be" && stats.streak_kind !== "none") {
    streakEl.classList.remove("hidden");
    streakEl.className = "streak-badge " + stats.streak_kind;
    streakEl.textContent = `${stats.streak_count} ${stats.streak_kind === "win" ? "g'alaba" : "zarar"} ketma-ket`;
  } else {
    streakEl.classList.add("hidden");
  }

  // Equity curve chart
  const equityCanvas = document.getElementById("equityChart");
  if (typeof Chart === "undefined") {
    if (equityCanvas) {
      equityCanvas.replaceWith(
        Object.assign(document.createElement("div"), { className: "empty-state", textContent: "Grafik yuklanmadi" })
      );
    }
  } else {
  const ctx = equityCanvas.getContext("2d");
  const values = [0, ...stats.equity_curve.map(n)];
  const positive = values[values.length - 1] >= 0;
  const lineColor = positive ? "#2ecc71" : "#ef4444";
  const fillColor = positive ? "rgba(46,204,113,0.18)" : "rgba(239,68,68,0.18)";

  if (equityChart) equityChart.destroy();
  equityChart = new Chart(ctx, {
    type: "line",
    data: {
      labels: values.map((_, i) => i),
      datasets: [{
        data: values,
        borderColor: lineColor,
        backgroundColor: fillColor,
        borderWidth: 3,
        fill: true,
        tension: 0.35,
        pointRadius: values.length <= 40 ? 3 : 0,
        pointBackgroundColor: lineColor,
      }],
    },
    options: {
      responsive: true,
      plugins: { legend: { display: false }, tooltip: { callbacks: { label: (c) => `${fmtSigned(c.parsed.y)}R` } } },
      scales: {
        x: { display: false },
        y: {
          grid: { color: "#212a35" },
          ticks: { color: "#8b96a5", font: { size: 11 } },
        },
      },
    },
  });
  }

  // Stat chips
  const pf = stats.profit_factor !== null && stats.profit_factor !== undefined ? fmtDec(stats.profit_factor) : "∞";
  const dd = n(stats.max_drawdown);
  const best = stats.best_trade ? (stats.best_trade.result_type === "SL" ? "SL" : fmtR(stats.best_trade.result_rr)) : "-";
  const chips = [
    ["Win Rate", `${fmtDec(stats.win_rate)}%`, ""],
    ["Average RR", `${fmtDec(stats.average_rr)}R`, ""],
    ["Profit Factor", pf, ""],
    ["Max Drawdown", dd > 0 ? `-${fmtDec(dd)}R` : "0R", dd > 0 ? "red" : ""],
    ["Eng yaxshi", best, "green"],
    ["Trades", String(stats.total_trades), ""],
  ];
  document.getElementById("statGrid").innerHTML = chips.map(([label, value, cls]) =>
    `<div class="stat-chip"><div class="stat-chip-label">${label}</div><div class="stat-chip-value ${cls}">${value}</div></div>`
  ).join("");

  // Composition bar
  const total = Math.max(stats.wins + stats.losses + stats.breakeven, 1);
  document.getElementById("compBar").innerHTML = `
    <div style="width:${(stats.wins / total) * 100}%; background:#2ecc71"></div>
    <div style="width:${(stats.breakeven / total) * 100}%; background:#8b96a5"></div>
    <div style="width:${(stats.losses / total) * 100}%; background:#ef4444"></div>`;
  document.getElementById("compLegend").innerHTML = `
    <span><span class="leg-dot" style="background:#2ecc71"></span>${stats.wins} Win</span>
    <span><span class="leg-dot" style="background:#8b96a5"></span>${stats.breakeven} B/U</span>
    <span><span class="leg-dot" style="background:#ef4444"></span>${stats.losses} Loss</span>`;

  // Coins list
  const coinsList = document.getElementById("coinsList");
  if (stats.coins.length === 0) {
    coinsList.innerHTML = `<div class="empty-state">Yopilgan trade yo'q</div>`;
  } else {
    coinsList.innerHTML = stats.coins.map((c) => {
      const isLoss = c.result_type === "SL";
      const isWin = !isLoss && n(c.result_rr) > 0;
      const dot = isLoss ? "red" : (isWin ? "green" : "gray");
      const text = isLoss ? "SL" : fmtR(c.result_rr);
      return `<div class="list-item">
        <div class="li-left"><span class="li-dot ${dot}"></span><div class="li-main"><div class="li-title">${c.coin}</div></div></div>
        <div class="li-right ${dot}">${text}</div>
      </div>`;
    }).join("");
  }
}

/* ============================================================
   ALERTS
   ============================================================ */
function alertItemHtml(a) {
  const isUp = a.direction === "ABOVE";
  return `<div class="list-item" data-alert-id="${a.id}">
    <div class="li-left">
      <span class="li-dot ${isUp ? "green" : "red"}"></span>
      <div class="li-main">
        <div class="li-title">${isUp ? "⬆️" : "⬇️"} ${a.coin} → ${fmtDec(a.target_price)}</div>
        <div class="li-sub">qo'yilganda: ${fmtDec(a.price_at_creation)}</div>
      </div>
    </div>
    <button class="btn-small" data-cancel-alert="${a.id}" style="flex:none">❌</button>
  </div>`;
}

let lastAlerts = [];

async function loadAlerts() {
  const list = document.getElementById("alertsList");
  try {
    const alerts = await api("/api/alerts");
    lastAlerts = alerts;
    if (alerts.length === 0) {
      list.innerHTML = `<div class="empty-state">Hozircha faol alert yo'q</div>`;
    } else {
      list.innerHTML = alerts.map(alertItemHtml).join("");
      list.querySelectorAll(".list-item").forEach((row) => {
        row.addEventListener("click", () => {
          const a = lastAlerts.find((x) => x.id === parseInt(row.dataset.alertId));
          if (a) openAlertChartSheet(a);
        });
      });
      list.querySelectorAll("[data-cancel-alert]").forEach((btn) => {
        btn.addEventListener("click", async (ev) => {
          ev.stopPropagation();
          try {
            await api(`/api/alerts/${btn.dataset.cancelAlert}/cancel`, { method: "POST" });
            toast("❌ Bekor qilindi");
            loadAlerts();
          } catch (e) { toast(e.message, "error"); }
        });
      });
    }
  } catch (e) {
    toast(e.message, "error");
  }
}

/* ---- Alert detail: live minimalist price chart ---- */

async function openAlertChartSheet(alert) {
  const isUp = alert.direction === "ABOVE";
  const dirColor = isUp ? "#26c6b0" : "#ef6a5f";
  openSheet(`
    <div class="chart-header">
      <div>
        <div class="chart-header-coin">${alert.coin}</div>
        <div class="chart-header-dir" style="color:${dirColor}">${isUp ? "▲ ABOVE" : "▼ BELOW"} <span id="intervalLabel">1s</span></div>
      </div>
      <div class="chart-header-right">
        <div class="chart-header-pct" id="alertPct" style="color:${dirColor}">…</div>
        <div class="chart-header-price" id="alertLivePrice">…</div>
      </div>
    </div>
    <div class="mini-chart-wrap">
      <canvas id="alertChart" height="150"></canvas>
    </div>
    <div class="interval-row" id="intervalRow">
      <button class="pill small" data-int="15m">15m</button>
      <button class="pill small selected" data-int="1h">1s</button>
      <button class="pill small" data-int="4h">4s</button>
      <button class="pill small" data-int="1d">1k</button>
    </div>
    <button class="btn-small full-w danger" data-cancel-alert="${alert.id}">❌ Alertni bekor qilish</button>
  `);

  sheetContent.querySelector("[data-cancel-alert]").addEventListener("click", async () => {
    try {
      await api(`/api/alerts/${alert.id}/cancel`, { method: "POST" });
      toast("❌ Bekor qilindi");
      closeSheet(); loadAlerts();
    } catch (e) { toast(e.message, "error"); }
  });

  let interval = "1h";
  const intervalLabels = { "15m": "15m", "1h": "1s", "4h": "4s", "1d": "1k" };
  sheetContent.querySelectorAll("#intervalRow .pill").forEach((p) => {
    p.addEventListener("click", () => {
      sheetContent.querySelectorAll("#intervalRow .pill").forEach((x) => x.classList.remove("selected"));
      p.classList.add("selected");
      interval = p.dataset.int;
      document.getElementById("intervalLabel").textContent = intervalLabels[interval];
      refreshAlertChart(alert, interval);
    });
  });

  await refreshAlertChart(alert, interval);
  requestAnimationFrame(() => refreshAlertChart(alert, interval)); // re-measure once layout has settled
  clearInterval(activeInterval);
  activeInterval = setInterval(() => refreshAlertChart(alert, interval), 8000);
}

async function refreshAlertChart(alert, interval) {
  try {
    const data = await api(`/api/alerts/chart/${alert.coin}?interval=${interval}&limit=96`);
    const current = n(data.current_price);
    const target = n(alert.target_price);
    const pct = current !== 0 ? ((target - current) / current) * 100 : 0;

    const priceEl = document.getElementById("alertLivePrice");
    if (priceEl) priceEl.textContent = formatPriceForChart(current);
    const pctEl = document.getElementById("alertPct");
    if (pctEl) pctEl.textContent = `${pct >= 0 ? "+" : ""}${pct.toFixed(2)}% to target`;

    const canvas = document.getElementById("alertChart");
    if (!canvas) return;
    drawCandlestickChart(canvas, data.candles, target, current);
  } catch (e) {
    /* silent — a transient price-feed hiccup shouldn't spam toasts every 8s */
  }
}

/* Minimalist hand-drawn candlestick chart (no external chart lib needed) —
   bullish = lavender/purple, bearish = black w/ a thin outline so it still
   reads against the dark app background, matching the requested palette. */
const CANDLE_BULL = "#26c6b0";
const CANDLE_BEAR = "#ef6a5f";

function formatPriceForChart(v) {
  const abs = Math.abs(v);
  let decimals = 2;
  if (abs >= 1000) decimals = 0;
  else if (abs >= 100) decimals = 1;
  else if (abs >= 1) decimals = 2;
  else if (abs >= 0.01) decimals = 4;
  else decimals = 6;
  return v.toLocaleString("en-US", { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}

function drawCandlestickChart(canvas, candles, targetPrice, currentPrice) {
  if (!candles || candles.length === 0) return;
  const dpr = window.devicePixelRatio || 1;
  const cssWidth = canvas.clientWidth || 320;
  const cssHeight = parseInt(canvas.getAttribute("height"), 10) || 260;
  canvas.style.width = cssWidth + "px";
  canvas.style.height = cssHeight + "px";
  canvas.width = Math.round(cssWidth * dpr);
  canvas.height = Math.round(cssHeight * dpr);
  const ctx = canvas.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, cssWidth, cssHeight);

  const highs = candles.map((c) => n(c.h));
  const lows = candles.map((c) => n(c.l));
  const current = currentPrice !== undefined ? currentPrice : n(candles[candles.length - 1].c);
  let vmax = Math.max(...highs, targetPrice, current);
  let vmin = Math.min(...lows, targetPrice, current);
  const pad = (vmax - vmin) * 0.14 || Math.max(vmax * 0.01, 1);
  vmax += pad; vmin -= pad;
  const span = (vmax - vmin) || 1;

  const axisFont = "10px -apple-system, sans-serif";
  ctx.font = axisFont;
  const axisW = Math.max(ctx.measureText(formatPriceForChart(vmax)).width, ctx.measureText(formatPriceForChart(vmin)).width) + 16;

  const padX = 2, padY = 8;
  const chartW = cssWidth - padX * 2 - axisW;
  const chartH = cssHeight - padY * 2;
  const count = candles.length;
  const slotW = chartW / count;
  const bodyW = Math.max(Math.min(slotW * 0.62, 8), 1.5);

  const yFor = (v) => padY + chartH - ((v - vmin) / span) * chartH;

  // Horizontal gridlines + price labels (right axis)
  const gridLevels = 5;
  ctx.textBaseline = "middle";
  ctx.textAlign = "left";
  for (let i = 0; i <= gridLevels; i++) {
    const gv = vmin + (span * i) / gridLevels;
    const gy = yFor(gv);
    ctx.strokeStyle = "rgba(139,150,165,0.14)";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(padX, gy);
    ctx.lineTo(padX + chartW, gy);
    ctx.stroke();
    ctx.fillStyle = "#6b7686";
    ctx.font = axisFont;
    ctx.fillText(formatPriceForChart(gv), padX + chartW + 8, gy);
  }

  // Candles
  candles.forEach((c, i) => {
    const o = n(c.o), h = n(c.h), l = n(c.l), cl = n(c.c);
    const cx = padX + slotW * (i + 0.5);
    const bull = cl >= o;
    const color = bull ? CANDLE_BULL : CANDLE_BEAR;

    ctx.strokeStyle = color;
    ctx.lineWidth = 1.3;
    ctx.beginPath();
    ctx.moveTo(cx, yFor(h));
    ctx.lineTo(cx, yFor(l));
    ctx.stroke();

    const yTop = yFor(Math.max(o, cl));
    const yBot = yFor(Math.min(o, cl));
    const bodyH = Math.max(yBot - yTop, 1.5);
    ctx.fillStyle = color;
    ctx.fillRect(cx - bodyW / 2, yTop, bodyW, bodyH);
  });

  // Target reference line — dotted, colored by direction, labeled
  const targetUp = targetPrice >= current;
  const targetColor = targetUp ? CANDLE_BULL : CANDLE_BEAR;
  ctx.setLineDash([1, 4]);
  ctx.lineCap = "round";
  ctx.strokeStyle = targetColor;
  ctx.lineWidth = 1.5;
  const ty = yFor(targetPrice);
  ctx.beginPath();
  ctx.moveTo(padX, ty);
  ctx.lineTo(padX + chartW, ty);
  ctx.stroke();
  ctx.setLineDash([]);
  drawPricePill(ctx, padX + chartW + 8, ty, formatPriceForChart(targetPrice), targetColor, "#06120f");

  // Current price reference — thin dashed neutral line, labeled
  ctx.setLineDash([6, 4]);
  ctx.strokeStyle = "#c7d0dc";
  ctx.lineWidth = 1;
  const py = yFor(current);
  ctx.beginPath();
  ctx.moveTo(padX, py);
  ctx.lineTo(padX + chartW, py);
  ctx.stroke();
  ctx.setLineDash([]);
  drawPricePill(ctx, padX + chartW + 8, py, formatPriceForChart(current), "#2a3140", "#e7edf3");
}

function drawPricePill(ctx, x, y, text, bg, fg) {
  ctx.font = "700 10px -apple-system, sans-serif";
  const tw = ctx.measureText(text).width;
  const w = tw + 8, h = 15;
  let yy = y - h / 2;
  ctx.fillStyle = bg;
  if (ctx.roundRect) {
    ctx.beginPath();
    ctx.roundRect(x, yy, w, h, 5);
    ctx.fill();
  } else {
    ctx.fillRect(x, yy, w, h);
  }
  ctx.fillStyle = fg;
  ctx.textAlign = "left";
  ctx.textBaseline = "middle";
  ctx.fillText(text, x + 4, y + 0.5);
}

document.getElementById("addAlertBtn").addEventListener("click", () => {
  openSheet(`
    <div class="sheet-title">🔔 Yangi alert</div>
    <div class="field">
      <label class="field-label">Coin</label>
      <input type="text" class="field-input" id="aCoin" placeholder="BTCUSDT yoki BTC" autocapitalize="characters">
    </div>
    <div class="field">
      <label class="field-label">Maqsadli narx</label>
      <input type="number" step="any" inputmode="decimal" class="field-input" id="aPrice" placeholder="112000">
    </div>
    <div class="hint-text">Narx joriy narxdan yuqori bo'lsa ⬆️, past bo'lsa ⬇️ yo'nalish avtomatik aniqlanadi.</div>
    <button class="primary-btn" id="createAlertBtn" style="margin-top:14px">Alert qo'yish</button>
  `);
  sheetContent.querySelector("#createAlertBtn").addEventListener("click", async () => {
    const coin = sheetContent.querySelector("#aCoin").value.trim();
    const price = sheetContent.querySelector("#aPrice").value;
    if (!coin || !price) { toast("Coin va narxni kiriting", "error"); return; }
    try {
      await api("/api/alerts", { method: "POST", body: { coin, target_price: price } });
      toast("✅ Alert qo'yildi", "success");
      closeSheet(); loadAlerts();
    } catch (e) {
      toast(e.message, "error");
    }
  });
});

/* ============================================================
   SETTINGS
   ============================================================ */
async function loadSettings() {
  try {
    const me = await api("/api/me");
    state.me = me;
    document.getElementById("marginValue").textContent = `$${fmtDec(me.margin)}`;
    document.getElementById("adminPanel").classList.toggle("hidden", !me.is_admin);
    document.getElementById("userChip").textContent = me.username ? "@" + me.username : "";
  } catch (e) {
    toast(e.message, "error");
  }
}

document.getElementById("changeMarginBtn").addEventListener("click", () => {
  openSheet(`
    <div class="sheet-title">💵 Marginni o'zgartirish</div>
    <div class="field">
      <label class="field-label">Yangi margin ($)</label>
      <input type="number" step="any" inputmode="decimal" class="field-input" id="newMargin" placeholder="500">
    </div>
    <button class="primary-btn" id="saveMarginBtn">Saqlash</button>
  `);
  sheetContent.querySelector("#saveMarginBtn").addEventListener("click", async () => {
    const val = sheetContent.querySelector("#newMargin").value;
    if (!val) { toast("Qiymat kiriting", "error"); return; }
    try {
      await api("/api/settings/margin", { method: "POST", body: { margin: val } });
      toast("✅ Margin saqlandi", "success");
      closeSheet(); loadSettings();
    } catch (e) {
      toast(e.message, "error");
    }
  });
});

document.getElementById("backupNowBtn").addEventListener("click", async () => {
  toast("☁️ Backup boshlandi...");
  try {
    const res = await api("/api/settings/backup/now", { method: "POST" });
    toast(res.status === "SUCCESS" ? "✅ Backup muvaffaqiyatli" : "❌ Backup muvaffaqiyatsiz", res.status === "SUCCESS" ? "success" : "error");
  } catch (e) { toast(e.message, "error"); }
});

document.getElementById("backupLastBtn").addEventListener("click", async () => {
  try {
    const b = await api("/api/settings/backup/last");
    const el = document.getElementById("backupStatus");
    if (!b) { el.textContent = "Hali backup qilinmagan."; return; }
    const d = new Date(b.created_at);
    el.textContent = `🕐 ${d.toLocaleString("uz-UZ")} — ${b.backup_type} — ${b.status}`;
  } catch (e) { toast(e.message, "error"); }
});

document.getElementById("restoreBtn").addEventListener("click", () => {
  openSheet(`
    <div class="sheet-title">⚠️ Restore</div>
    <p class="hint-text">Restore qilish barcha current database ma'lumotlarini backup bilan almashtirishi mumkin. Davom etasizmi?</p>
    <button class="primary-btn" id="confirmRestoreBtn" style="margin-top:10px">✅ Ha, Restore</button>
    <button class="btn-small full-w" id="cancelRestoreBtn">❌ Bekor qilish</button>
  `);
  sheetContent.querySelector("#cancelRestoreBtn").addEventListener("click", closeSheet);
  sheetContent.querySelector("#confirmRestoreBtn").addEventListener("click", async () => {
    toast("🔄 Restore boshlandi...");
    try {
      await api("/api/settings/backup/restore", { method: "POST" });
      toast("✅ Restore muvaffaqiyatli", "success");
      closeSheet();
    } catch (e) {
      toast(e.message, "error");
    }
  });
});

/* ============================================================
   Init
   ============================================================ */
loadDashboard();
