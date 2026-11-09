"use strict";
// Đợt 3 — Trang "Trò chơi" cho nhân viên: thống kê hôm nay, cấu hình vòng quay (ADMIN),
// ví game bị khóa và mở khóa (MANAGER/ADMIN), lượt quay gần đây. Backend kiểm tra lại mọi quyền.

Object.assign(copy, {
  games: ["Trò chơi", "Games"],
  gamesSub: ["Vòng quay, xu game và ví bị khóa do bất thường", "Lucky wheel, game coins and locked wallets"],
  dot3Sessions: ["Lượt quay hôm nay", "Spins today"],
  dot3Players: ["Người chơi", "Players"],
  dot3Awarded: ["Xu đã phát", "Coins awarded"],
  dot3Spent: ["Xu đã đổi", "Coins swapped"],
  dot3VoucherCount: ["Voucher từ xu", "Vouchers from coins"],
  dot3Config: ["Cấu hình vòng quay", "Wheel settings"],
  dot3EditConfig: ["Sửa cấu hình", "Edit settings"],
  dot3DailyLimit: ["Lượt chơi mỗi ngày", "Spins per day"],
  dot3Interval: ["Cách nhau tối thiểu (giây)", "Minimum gap (seconds)"],
  dot3Expected: ["Xu kỳ vọng mỗi lượt", "Expected coins per spin"],
  dot3Prize: ["Ô thưởng", "Prize"],
  dot3Weight: ["Tỉ lệ", "Weight"],
  dot3Chance: ["Xác suất", "Chance"],
  dot3PrizesHelp: ["Mỗi dòng một ô: nhãn | số xu | tỉ lệ (vd. 10 xu | 10 | 25)", "One prize per line: label | coins | weight (e.g. 10 coins | 10 | 25)"],
  dot3LockedWallets: ["Ví game bị khóa", "Locked game wallets"],
  dot3NoLocked: ["Không có ví nào bị khóa", "No locked wallets"],
  dot3Unlock: ["Mở khóa", "Unlock"],
  dot3Lock: ["Khóa", "Lock"],
  dot3LockReason: ["Lý do khóa ví game", "Reason for locking"],
  dot3Recent: ["Lượt quay gần đây", "Recent spins"],
  dot3AutoLockNote: ["Ví tự khóa khi bị chặn {n} lần/ngày (hết lượt hoặc quay quá nhanh).", "Wallets auto-lock after {n} blocked attempts per day (limit reached or too fast)."],
});

async function loadGameAdmin(seq) {
  const data = await api("/games");
  if (seq !== state.seq || state.page !== "games") return false;
  state.gameAdmin = data;
  return true;
}

function gameAdminPage() {
  const d = state.gameAdmin;
  if (!d) return pageHead() + loading();
  const s = d.stats, game = d.game, total = game.prizes.reduce((sum, p) => sum + p.weight, 0);
  const prizes = game.prizes.map((p) => `<tr><td>${esc(p.label)}</td><td>${p.coins}</td><td>${p.weight}</td><td>${total ? ((p.weight * 100) / total).toFixed(1) : 0}%</td></tr>`).join("");
  const locked = d.locked.length
    ? table(["dot2Customer", "dot3Coins", "dot2Reason", "dot2When", ""], d.locked.map((w) => `<tr><td>${esc(w.customer_name)}</td><td>${w.balance}</td><td><small>${esc(w.locked_reason || "")}</small></td><td>${dt(w.locked_at)}</td>
        <td>${d.can_manage ? `<button class="btn small primary" data-gameadmin="unlock" data-id="${w.account_id}">${t("dot3Unlock")}</button>` : ""}</td></tr>`).join(""))
    : empty("dot3NoLocked");
  const recent = d.recent.length
    ? table(["dot2When", "dot2Customer", "dot3Prize", "dot3Coins", ""], d.recent.map((r) => `<tr><td>${dt(r.created_at)}</td><td>${esc(r.customer_name)}</td><td>${esc(r.prize_label)}</td><td>${r.coins}</td>
        <td>${d.can_manage ? `<button class="btn ghost small" data-gameadmin="lock" data-id="${r.account_id}">${t("dot3Lock")}</button>` : ""}</td></tr>`).join(""))
    : empty("dot3NoHistory");
  return pageHead(d.can_configure ? `<button class="btn primary small" data-gameadmin="config">${t("dot3EditConfig")}</button>` : "") + `
    <div class="metrics">${metric("dot3Sessions", s.sessions, "cyan", "wheel")}${metric("dot3Players", s.players, "", "users")}${metric("dot3Awarded", s.coins_awarded, "green", "coin")}${metric("dot3Spent", s.coins_redeemed, "", "coin")}${metric("dot3VoucherCount", s.vouchers, "", "ticket")}</div>
    <div class="dot3-admin">
      <section class="panel"><header class="panel-heading"><h3>${icon("wheel")} ${t("dot3Config")} · ${esc(game.name)}</h3>${badge(game.is_active ? "ACTIVE" : "INACTIVE")}</header>
        <div class="panel-body dot3-config-meta">
          <div class="key-values">${kv("dot3DailyLimit", game.daily_limit)}${kv("dot3Interval", game.min_interval_seconds)}${kv("dot3Expected", game.expected_coins)}</div>
        </div>
        ${table(["dot3Prize", "dot3Coins", "dot3Weight", "dot3Chance"], prizes)}
        <div class="panel-body dot3-config-note">
          <p class="notice info">${t("dot3AutoLockNote").replace("{n}", d.suspicious_limit)}</p>
        </div></section>
      <section class="panel"><header class="panel-heading"><h3>${icon("shield")} ${t("dot3LockedWallets")}</h3><span class="badge red">${d.locked.length}</span></header>${locked}</section>
    </div>
    <section class="panel"><header class="panel-heading"><h3>${icon("clock")} ${t("dot3Recent")}</h3></header>${recent}</section>`;
}

function dot3ConfigForm() {
  const game = state.gameAdmin.game;
  const lines = game.prizes.map((p) => `${p.label} | ${p.coins} | ${p.weight}`).join("\n");
  dot1Dialog("dot3Config", `<div class="form-grid">
      ${dot1Input("daily_limit", "dot3DailyLimit", game.daily_limit, "number", 'min="1" max="20" step="1"')}
      ${dot1Input("min_interval_seconds", "dot3Interval", game.min_interval_seconds, "number", 'min="1" max="60" step="1"')}
      ${dot1Check("is_active", "dot1Active", game.is_active)}
      <label class="wide"><span>${t("dot3PrizesHelp")}</span><textarea class="input" name="prizes" rows="8">${esc(lines)}</textarea><span class="field-error" data-error="prizes"></span></label>
    </div>`, async (form) => {
    const prizes = form.elements.prizes.value.split("\n").map((line) => line.trim()).filter(Boolean).map((line) => {
      const [label, coins, weight] = line.split("|").map((part) => part.trim());
      return { label, coins: Number(coins), weight: Number(weight) };
    });
    await api("/games", { method: "PUT", body: {
      daily_limit: Number(form.elements.daily_limit.value), min_interval_seconds: Number(form.elements.min_interval_seconds.value),
      is_active: form.elements.is_active.checked, prizes } });
  });
}

document.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-gameadmin]");
  if (!button || button.disabled || state.page !== "games") return;
  const action = button.dataset.gameadmin, id = Number(button.dataset.id);
  try {
    if (action === "config") dot3ConfigForm();
    if (action === "unlock") {
      button.disabled = true;
      await api(`/games/wallets/${id}/lock`, { method: "POST", body: { locked: false } });
      await loadPage(true);
    }
    if (action === "lock") {
      const reason = prompt(t("dot3LockReason"));
      if (!reason) return;
      await api(`/games/wallets/${id}/lock`, { method: "POST", body: { locked: true, reason } });
      await loadPage(true);
    }
  } catch (error) {
    button.disabled = false;
    toast(Object.values(error.field_errors || {}).join(" · ") || error.message, true);
  }
});
