"use strict";
// Đợt 3 — Vòng quay may mắn và ví xu trong cổng khách hàng.
// Trình duyệt KHÔNG quyết định kết quả: bấm quay chỉ gửi POST rỗng, máy chủ bốc thăm và trả ô trúng;
// vòng quay chỉ chạy hiệu ứng tới đúng ô đó.

Object.assign(paths, {
  wheel: '<circle cx="12" cy="12" r="9"/><path d="M12 3v18M3 12h18M5.6 5.6l12.8 12.8M18.4 5.6 5.6 18.4"/>',
  coin: '<circle cx="12" cy="12" r="8"/><path d="M12 8v8M9.5 9.5h3.5a1.5 1.5 0 0 1 0 3h-2a1.5 1.5 0 0 0 0 3h3.5"/>',
});
Object.assign(copy, {
  dot3Game: ["Vòng quay", "Lucky wheel"],
  dot3GameSub: ["Quay mỗi ngày để nhận xu, đổi xu lấy voucher. Xu không phải tiền và không quy đổi tiền mặt.", "Spin daily for coins and swap coins for vouchers. Coins are not money and have no cash value."],
  dot3Spin: ["Quay", "Spin"],
  dot3Spinning: ["Đang quay…", "Spinning…"],
  dot3SpinsLeft: ["Lượt còn lại hôm nay", "Spins left today"],
  dot3Coins: ["Xu của bạn", "Your coins"],
  dot3CoinUnit: ["xu", "coins"],
  dot3NoSpins: ["Hết lượt hôm nay, quay lại vào ngày mai nhé!", "No spins left today. Come back tomorrow!"],
  dot3Paused: ["Trò chơi đang tạm dừng", "The game is paused"],
  dot3Locked: ["Tài khoản trò chơi đang bị khóa", "Your game account is locked"],
  dot3Won: ["Bạn nhận được", "You won"],
  dot3NoLuck: ["Chúc bạn may mắn lần sau!", "Better luck next time!"],
  dot3Shop: ["Đổi xu lấy voucher", "Swap coins for vouchers"],
  dot3Redeem: ["Đổi", "Swap"],
  dot3NotEnough: ["Chưa đủ xu", "Not enough coins"],
  dot3Redeemed: ["Đã đổi voucher! Xem trong tab Voucher của tôi.", "Voucher added! See My vouchers."],
  dot3History: ["Lượt quay gần đây", "Recent spins"],
  dot3Ledger: ["Biến động xu", "Coin activity"],
  dot3NoHistory: ["Chưa có lượt quay nào", "No spins yet"],
  dot3ReasonPLAY: ["Quay thưởng", "Spin reward"],
  dot3ReasonREDEEM: ["Đổi voucher", "Voucher swap"],
  dot3ReasonAD: ["Xem quảng cáo", "Ad reward"],
  dot3ReasonADJUST: ["Điều chỉnh", "Adjustment"],
  dot3Rules: ["Mỗi ngày {n} lượt (giờ Việt Nam). Kết quả do hệ thống quyết định. Thao tác bất thường có thể khiến tài khoản trò chơi bị tạm khóa.", "{n} spins per day (Vietnam time). Results are decided by the server. Abnormal activity may lock your game account."],
});

const DOT3_SPIN_MS = 4200;
const DOT3_COLORS = ["#05c4ef", "#16213a", "#f5a400", "#1b2b45", "#10b981", "#22192f", "#8b5cf6", "#1e2a3c"];

function customerGamePage() {
  const ui = portalUI;
  if (!ui.gameLoading && !ui.gameBusy && (!ui.game || Date.now() - (ui.gameAt || 0) > 30000)) loadCustomerGame();
  return `<div id="dot3-root">${dot3Body()}</div>`;
}

async function loadCustomerGame() {
  const ui = portalUI;
  ui.gameLoading = true;
  try {
    const data = await api("/portal/game");
    if (ui !== portalUI) return;
    ui.game = data;
    ui.gameError = null;
  } catch (error) {
    if (ui !== portalUI) return;
    ui.gameError = error.message;
  } finally {
    ui.gameAt = Date.now();
    ui.gameLoading = false;
    if (ui === portalUI && ui.tab === "game" && !ui.gameBusy) dot3Redraw();
  }
}

function dot3Redraw() {
  const root = $("#dot3-root");
  if (root) root.innerHTML = dot3Body();
}

function dot3Wheel(prizes, rotation) {
  const n = prizes.length, seg = 360 / n, r = 150, c = 160;
  const point = (deg) => {
    const rad = ((deg - 90) * Math.PI) / 180;
    return [c + r * Math.cos(rad), c + r * Math.sin(rad)];
  };
  const slices = prizes.map((p, i) => {
    const [x1, y1] = point(i * seg), [x2, y2] = point((i + 1) * seg);
    const mid = (i + 0.5) * seg;
    return `<g><path d="M${c},${c} L${x1.toFixed(2)},${y1.toFixed(2)} A${r},${r} 0 ${seg > 180 ? 1 : 0} 1 ${x2.toFixed(2)},${y2.toFixed(2)} Z" fill="${DOT3_COLORS[i % DOT3_COLORS.length]}" stroke="#0b101b" stroke-width="2"/>
      <text x="${c}" y="${c - r + 34}" transform="rotate(${mid} ${c} ${c})" text-anchor="middle" class="dot3-slice-label">${esc(p.label)}</text></g>`;
  }).join("");
  return `<div class="dot3-wheel"><span class="dot3-pointer" aria-hidden="true"></span>
      <svg viewBox="0 0 320 320" role="img" aria-label="${t("dot3Game")}"><g id="dot3-rotor" class="dot3-rotor" style="transform:rotate(${rotation}deg)">${slices}</g>
      <circle cx="160" cy="160" r="26" fill="#0b101b" stroke="#f5a400" stroke-width="3"/><text x="160" y="166" text-anchor="middle" class="dot3-hub">CH</text></svg></div>`;
}

function dot3Body() {
  const ui = portalUI, d = ui.game;
  if (!d) {
    return ui.gameError
      ? `<section class="pc-card"><div class="pc-empty">${icon("alert")}<h3>${t("unavailable")}</h3><p>${esc(ui.gameError)}</p></div></section>`
      : `<section class="pc-card"><div class="pc-loading" role="status"><span class="spinner"></span><p>${t("loading")}</p></div></section>`;
  }
  ui.wheelRotation ??= 0;
  const blocked = !d.game.is_active ? "dot3Paused" : d.wallet.is_locked ? "dot3Locked" : d.spins_left ? "" : "dot3NoSpins";
  const canSpin = !blocked && !ui.gameBusy;
  const shop = d.shop.map((s) => {
    const enough = d.wallet.balance >= s.coin_cost && !d.wallet.is_locked;
    return `<li class="dot3-shop-item"><div><strong>${esc(s.name)}</strong><small>${t("dot2Type" + s.reward_type)} · ${s.valid_days} ${t("pcDays")}${s.store_name ? ` · ${esc(s.store_name)}` : ""}</small></div>
        <button class="btn small ${enough ? "primary" : ""}" data-game="redeem" data-id="${s.id}" ${enough && !ui.gameBusy ? "" : "disabled"} title="${enough ? "" : t("dot3NotEnough")}">${icon("coin")}${s.coin_cost}</button></li>`;
  }).join("");
  const history = d.history.length
    ? `<ul class="dot3-list">${d.history.map((h) => `<li><span>${esc(h.prize_label)}</span><small>${dt(h.created_at)}</small></li>`).join("")}</ul>`
    : `<p class="muted">${t("dot3NoHistory")}</p>`;
  const ledger = d.ledger.length
    ? `<ul class="dot3-list">${d.ledger.map((e) => `<li><span>${t("dot3Reason" + e.reason)}</span><b class="${e.delta > 0 ? "green" : "red"}">${e.delta > 0 ? "+" : ""}${e.delta}</b></li>`).join("")}</ul>`
    : `<p class="muted">${t("dot3NoHistory")}</p>`;
  return `<div class="dot3-layout">
      <section class="pc-card dot3-stage">
        ${dot3Wheel(d.game.prizes, ui.wheelRotation)}
        <div class="dot3-controls">
          <div class="dot3-stat"><small>${t("dot3SpinsLeft")}</small><strong>${d.spins_left}/${d.game.daily_limit}</strong></div>
          <button class="btn primary dot3-spin" data-game="spin" ${canSpin ? "" : "disabled"}>${icon("wheel")}${ui.gameBusy ? t("dot3Spinning") : t("dot3Spin")}</button>
          <div class="dot3-stat"><small>${t("dot3Coins")}</small><strong class="gold">${icon("coin")}${d.wallet.balance}</strong></div>
        </div>
        ${blocked ? `<p class="dot3-blocked">${t(blocked)}${d.wallet.is_locked && d.wallet.locked_reason ? ` — ${esc(d.wallet.locked_reason)}` : ""}</p>` : ""}
        <p class="dot3-rules">${t("dot3Rules").replace("{n}", d.game.daily_limit)}</p>
      </section>
      <section class="pc-card"><header><h2>${icon("ticket")} ${t("dot3Shop")}</h2></header>${d.shop.length ? `<ul class="dot3-shop">${shop}</ul>` : `<p class="muted">—</p>`}</section>
      <section class="pc-card dot3-two"><div><h3>${t("dot3History")}</h3>${history}</div><div><h3>${t("dot3Ledger")}</h3>${ledger}</div></section>
    </div>`;
}

async function dot3Spin() {
  const ui = portalUI;
  if (!ui?.game || ui.gameBusy) return;
  ui.gameBusy = true;
  ui.p2Busy = true; // cổng khách không tự làm mới giữa lúc quay
  dot3Redraw();
  try {
    const result = await api("/portal/game/spin", { method: "POST", body: {} });
    const n = ui.game.game.prizes.length, seg = 360 / n;
    const index = ui.game.game.prizes.findIndex((p) => p.index === result.prize_index);
    // Ô trúng dừng dưới kim (đỉnh): xoay thêm 5 vòng + phần còn thiếu, lệch nhẹ trong ô cho tự nhiên.
    const jitter = (Math.random() - 0.5) * seg * 0.5;
    const target = (360 - (Math.max(0, index) + 0.5) * seg + jitter + 360) % 360;
    const current = ((ui.wheelRotation % 360) + 360) % 360;
    ui.wheelRotation += 1800 + ((target - current + 360) % 360);
    const rotor = $("#dot3-rotor");
    if (rotor && !matchMedia("(prefers-reduced-motion: reduce)").matches) {
      rotor.classList.add("spinning");
      rotor.style.transform = `rotate(${ui.wheelRotation}deg)`;
      await new Promise((resolve) => setTimeout(resolve, DOT3_SPIN_MS));
    }
    toast(result.coins ? `${t("dot3Won")} ${result.coins} ${t("dot3CoinUnit")} 🎉` : t("dot3NoLuck"));
  } catch (error) {
    toast(error.message, true);
  } finally {
    ui.gameBusy = false;
    ui.p2Busy = false;
    ui.gameAt = 0;
    await loadCustomerGame();
  }
}

async function dot3Redeem(catalogId) {
  const ui = portalUI;
  if (!ui?.game || ui.gameBusy) return;
  // Giữ cùng khóa khi thử lại sau lỗi mạng để không bị trừ xu hai lần.
  ui.redeemKey = ui.redeemKey?.catalog === catalogId ? ui.redeemKey : { catalog: catalogId, key: crypto.randomUUID() };
  ui.gameBusy = true;
  ui.p2Busy = true;
  dot3Redraw();
  try {
    await api("/portal/game/redeem", { method: "POST", body: { catalog_id: catalogId, request_key: ui.redeemKey.key } });
    ui.redeemKey = null;
    ui.vouchersAt = 0; // tab Voucher tải lại lần sau
    toast(t("dot3Redeemed"));
  } catch (error) {
    if (error.code) ui.redeemKey = null; // lỗi nghiệp vụ: lần sau dùng khóa mới
    toast(Object.values(error.field_errors || {}).join(" · ") || error.message, true);
  } finally {
    ui.gameBusy = false;
    ui.p2Busy = false;
    ui.gameAt = 0;
    await loadCustomerGame();
  }
}

document.addEventListener("click", (event) => {
  const button = event.target.closest("[data-game]");
  if (!button || button.disabled || !portalUI) return;
  if (button.dataset.game === "spin") dot3Spin();
  if (button.dataset.game === "redeem") dot3Redeem(Number(button.dataset.id));
});
