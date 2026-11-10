"use strict";
// Đợt 4 — Trang "Quảng cáo" cho nhân viên: thống kê 7 ngày (lượt cấp, hợp lệ, từ chối, hết hạn,
// phần thưởng đã cấp), cấu hình + nội dung quảng cáo (ADMIN), sự kiện gần đây.

Object.assign(copy, {
  ads: ["Quảng cáo", "Ads"],
  adsSub: ["Quảng cáo nhận thưởng tự nguyện: lượt xem, lượt hợp lệ và phần thưởng đã cấp", "Opt-in rewarded ads: views, valid completions and rewards granted"],
  dot4Stats: ["Thống kê 7 ngày", "Last 7 days"],
  dot4Day: ["Ngày", "Day"],
  dot4Issued: ["Lượt mở", "Started"],
  dot4Completed: ["Hợp lệ", "Valid"],
  dot4Rejected: ["Từ chối", "Rejected"],
  dot4Expired: ["Hết hạn", "Expired"],
  dot4Spins: ["Lượt quay đã cấp", "Spins granted"],
  dot4CoinsGranted: ["Xu đã cấp", "Coins granted"],
  dot4Settings: ["Cấu hình", "Settings"],
  dot4Mode: ["Chế độ", "Mode"],
  dot4ModeHOUSE: ["Quảng cáo nội bộ (máy chủ đo thời lượng)", "House ads (server-timed)"],
  dot4ModeNETWORK: ["Mạng quảng cáo (xác minh phía máy chủ)", "Ad network (server-side verification)"],
  dot4Cap: ["Thưởng tối đa mỗi ngày", "Daily reward cap"],
  dot4RewardType: ["Loại thưởng", "Reward type"],
  dot4RewardTypeEXTRA_SPIN: ["Thêm lượt quay", "Extra spins"],
  dot4RewardTypeCOINS: ["Xu game", "Game coins"],
  dot4Amount: ["Số lượng", "Amount"],
  dot4Enabled: ["Bật chương trình", "Enabled"],
  dot4EditSettings: ["Sửa cấu hình", "Edit settings"],
  dot4Creatives: ["Nội dung quảng cáo", "Ad creatives"],
  dot4NoCreatives: ["Chưa có nội dung quảng cáo.", "No ad creatives yet."],
  dot4NewCreative: ["Nội dung mới", "New creative"],
  dot4Title: ["Tiêu đề", "Title"],
  dot4Body: ["Nội dung", "Body"],
  dot4Cta: ["Lời kêu gọi", "Call to action"],
  dot4Duration: ["Thời lượng (giây)", "Duration (s)"],
  dot4Recent: ["Sự kiện gần đây", "Recent events"],
  dot4NoRecent: ["Chưa có sự kiện quảng cáo nào.", "No ad events yet."],
  dot4NetworkReady: ["Đã cấu hình khóa xác minh cho mạng quảng cáo", "Ad network verification key configured"],
  dot4NetworkMissing: ["Chưa có CYBERHUB_AD_SSV_SECRET: chỉ dùng được quảng cáo nội bộ", "No CYBERHUB_AD_SSV_SECRET: house ads only"],
  dot4Policy: ["Quảng cáo luôn tự nguyện, có nhãn rõ ràng và không chặn chức năng nào. Không cam kết doanh thu từ quảng cáo.", "Ads are always optional, clearly labelled and never block features. No ad revenue is promised."],
  dot4StatusISSUED: ["Đang xem", "Watching"], dot4StatusCOMPLETED: ["Hợp lệ", "Valid"], dot4StatusREJECTED: ["Từ chối", "Rejected"],
});

async function loadAdAdmin(seq) {
  const data = await api("/ads");
  if (seq !== state.seq || state.page !== "ads") return false;
  state.adAdmin = data;
  return true;
}

function adAdminPage() {
  const d = state.adAdmin;
  if (!d) return pageHead() + loading();
  const s = d.settings;
  const totals = d.stats.reduce((sum, r) => ({ issued: sum.issued + r.issued, completed: sum.completed + r.completed,
    rejected: sum.rejected + r.rejected + r.expired }), { issued: 0, completed: 0, rejected: 0 });
  const stats = d.stats.length
    ? table(["dot4Day", "dot4Issued", "dot4Completed", "dot4Rejected", "dot4Expired", "dot4Spins", "dot4CoinsGranted"],
      d.stats.map((r) => `<tr><td>${esc(r.day)}</td><td>${r.issued}</td><td class="green">${r.completed}</td><td class="red">${r.rejected}</td><td>${r.expired}</td><td>${r.spins}</td><td>${r.coins}</td></tr>`).join(""))
    : empty();
  const creatives = d.creatives.length
    ? table(["code", "dot4Title", "dot4Duration", "status", ""], d.creatives.map((c) => `<tr><td>${esc(c.code)}</td><td>${esc(c.title)}</td><td>${c.duration_seconds}</td><td>${badge(c.is_active ? "ACTIVE" : "INACTIVE")}</td>
        <td>${d.can_configure ? `<button class="btn ghost small" data-adadmin="creative" data-id="${c.id}">${t("edit")}</button>` : ""}</td></tr>`).join(""))
    : `<div class="dot4-empty">${icon("monitor")}<p>${t("dot4NoCreatives")}</p>${d.can_configure ? `<button class="btn small" data-adadmin="creative">${icon("plus")}${t("dot4NewCreative")}</button>` : ""}</div>`;
  const recent = d.recent.length
    ? table(["dot2When", "dot2Customer", "dot4RewardType", "status", "dot2Reason"], d.recent.map((e) => `<tr><td>${dt(e.issued_at)}</td><td>${esc(e.customer_name)}</td><td>${dot4Reward(e.reward_type, e.reward_amount)}</td>
        <td>${t("dot4Status" + e.status)}</td><td><small>${esc(e.reject_reason || "")}</small></td></tr>`).join(""))
    : `<div class="dot4-empty">${icon("clock")}<p>${t("dot4NoRecent")}</p></div>`;
  const extra = d.can_configure
    ? `<button class="btn small" data-adadmin="creative">${icon("plus")}${t("dot4NewCreative")}</button><button class="btn primary small" data-adadmin="settings">${t("dot4EditSettings")}</button>`
    : "";
  return pageHead(extra) + `
    <div class="metrics">${metric("dot4Issued", totals.issued, "cyan", "monitor")}${metric("dot4Completed", totals.completed, "green", "check")}${metric("dot4Rejected", totals.rejected, "", "alert")}</div>
    <div class="dot4-admin">
      <section class="panel"><header class="panel-heading"><h3>${icon("chart")} ${t("dot4Stats")}</h3></header>${stats}</section>
      <section class="panel"><header class="panel-heading"><h3>${t("dot4Settings")}</h3>${badge(s.enabled ? "ACTIVE" : "INACTIVE")}</header>
        <div class="key-values dot4-config-summary">${kv("dot4Mode", t("dot4Mode" + s.mode))}${kv("dot4Cap", s.daily_cap)}${kv("dot4RewardType", dot4Reward(s.reward_type, s.reward_amount))}</div>
        <div class="dot4-config-notes">
          <p class="notice ${d.network_ready ? "success" : "info"}">${t(d.network_ready ? "dot4NetworkReady" : "dot4NetworkMissing")}</p>
          <p class="notice info">${t("dot4Policy")}</p>
        </div></section>
    </div>
    <section class="panel"><header class="panel-heading"><h3>${t("dot4Creatives")}</h3></header>${creatives}</section>
    <section class="panel"><header class="panel-heading"><h3>${icon("clock")} ${t("dot4Recent")}</h3></header>${recent}</section>`;
}

function dot4SettingsForm() {
  const s = state.adAdmin.settings;
  dot1Dialog("dot4Settings", `<div class="form-grid">
      <label class="wide"><span>${t("dot4Mode")}</span><select class="input" name="mode">${["HOUSE", "NETWORK"].map((m) => `<option value="${m}" ${s.mode === m ? "selected" : ""}>${t("dot4Mode" + m)}</option>`).join("")}</select><span class="field-error" data-error="mode"></span></label>
      ${dot1Input("daily_cap", "dot4Cap", s.daily_cap, "number", 'min="1" max="10" step="1"')}
      <label><span>${t("dot4RewardType")}</span><select class="input" name="reward_type">${["EXTRA_SPIN", "COINS"].map((r) => `<option value="${r}" ${s.reward_type === r ? "selected" : ""}>${t("dot4RewardType" + r)}</option>`).join("")}</select></label>
      ${dot1Input("reward_amount", "dot4Amount", s.reward_amount, "number", 'min="1" max="100" step="1"')}
      ${dot1Check("enabled", "dot4Enabled", s.enabled)}
    </div>`, async (form) => {
    const f = form.elements;
    await api("/ads/settings", { method: "PUT", body: { mode: f.mode.value, daily_cap: Number(f.daily_cap.value),
      reward_type: f.reward_type.value, reward_amount: Number(f.reward_amount.value), enabled: f.enabled.checked } });
  });
}

function dot4CreativeForm(id) {
  const c = id ? state.adAdmin.creatives.find((x) => x.id === Number(id)) : null;
  dot1Dialog("dot4NewCreative", `<div class="form-grid">
      ${dot1Input("code", "code", c?.code, "text", 'maxlength="20" required')}
      ${dot1Input("duration_seconds", "dot4Duration", c?.duration_seconds ?? 15, "number", 'min="5" max="60" step="1"')}
      <label class="wide"><span>${t("dot4Title")}</span><input class="input" name="title" maxlength="80" value="${esc(c?.title || "")}"><span class="field-error" data-error="title"></span></label>
      <label class="wide"><span>${t("dot4Body")}</span><textarea class="input" name="body" maxlength="300" rows="3">${esc(c?.body || "")}</textarea><span class="field-error" data-error="body"></span></label>
      ${dot1Input("cta", "dot4Cta", c?.cta || "", "text", 'maxlength="40"')}
      ${dot1Check("is_active", "dot1Active", c ? c.is_active : true)}
    </div>`, async (form) => {
    const f = form.elements;
    const body = { code: f.code.value, title: f.title.value, body: f.body.value, cta: f.cta.value,
      duration_seconds: Number(f.duration_seconds.value), is_active: f.is_active.checked };
    await api(c ? `/ads/creatives/${c.id}` : "/ads/creatives", { method: c ? "PATCH" : "POST", body });
  });
}

document.addEventListener("click", (event) => {
  const button = event.target.closest("[data-adadmin]");
  if (!button || button.disabled || state.page !== "ads" || !state.adAdmin) return;
  if (button.dataset.adadmin === "settings") dot4SettingsForm();
  if (button.dataset.adadmin === "creative") dot4CreativeForm(button.dataset.id);
});
