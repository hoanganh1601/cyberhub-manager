"use strict";
// Đợt 2 — Trang "Voucher" cho nhân viên: tra cứu + xác nhận sử dụng (mọi nhân viên),
// danh mục phần thưởng, phát và khóa voucher (MANAGER/ADMIN). Backend kiểm tra lại mọi quyền/điều kiện.
// Dùng lại hộp thoại dot1Dialog/dot1Input/dot1Check của menu_admin.js.

Object.assign(copy, {
  vouchers: ["Voucher", "Vouchers"],
  vouchersSub: ["Xác nhận voucher khách dùng, phát thưởng và theo dõi lịch sử", "Confirm customer vouchers, issue rewards and review history"],
  dot2Redeem: ["Xác nhận voucher", "Confirm a voucher"],
  dot2CodeLabel: ["Mã voucher khách đưa", "Voucher code from customer"],
  dot2Lookup: ["Tra cứu", "Look up"],
  dot2Owner: ["Chủ voucher", "Owner"],
  dot2Verify: ["Đã hỏi tên/SĐT và xác minh đúng khách", "I verified the customer's name/phone"],
  dot2ChooseOrder: ["Áp vào yêu cầu gọi món", "Apply to food order"],
  dot2NoOrder: ["Khách chưa có yêu cầu gọi món tại cơ sở này", "No food order from this customer here"],
  dot2Confirm: ["Xác nhận sử dụng", "Confirm use"],
  dot2Revoke: ["Khóa voucher", "Lock voucher"],
  dot2RevokeReason: ["Lý do khóa voucher", "Reason for locking"],
  dot2NotHere: ["Voucher không áp dụng tại cơ sở này", "Not valid at this store"],
  dot2Catalog: ["Danh mục phần thưởng", "Reward catalog"],
  dot2NewReward: ["Phần thưởng", "Reward"],
  dot2Issue: ["Phát voucher", "Issue voucher"],
  dot2Events: ["Nhật ký voucher", "Voucher log"],
  dot2NoEvents: ["Chưa có hoạt động", "No activity yet"],
  dot2Value: ["Giá trị (VND hoặc điểm)", "Value (VND or points)"],
  dot2ValidDays: ["Số ngày hiệu lực", "Valid days"],
  dot2CoinCost: ["Giá đổi bằng xu game (để trống nếu không bán)", "Game coin price (blank = not for sale)"],
  dot2AllStoresCheck: ["Áp dụng mọi cơ sở (chỉ quản trị viên)", "All stores (admin only)"],
  dot2Customer: ["Khách hàng", "Customer"],
  dot2Applied: ["Đã xác nhận voucher", "Voucher confirmed"],
  dot2Discount: ["Giảm khi thu tiền món", "Discount at the counter"],
  dot2BonusAdded: ["Đã cộng vào số dư khuyến mãi", "Added to promotional balance"],
  dot2PointsAdded: ["Đã cộng điểm thành viên", "Member points added"],
  dot2Issued: ["Đã phát voucher", "Voucher issued"],
  dot2ActISSUE: ["Phát hành", "Issued"], dot2ActREDEEM: ["Sử dụng", "Redeemed"],
  dot2ActREVOKE: ["Khóa", "Locked"], dot2ActREJECT: ["Từ chối", "Rejected"],
  dot2Type: ["Loại", "Type"], dot2Scope: ["Phạm vi", "Scope"], dot2When: ["Thời điểm", "When"],
  dot2Code2: ["Mã", "Code"], dot2Action: ["Hoạt động", "Action"], dot2Reason: ["Chi tiết", "Details"],
  dot2Staff: ["Nhân viên", "Staff"],
});

async function loadVoucherAdmin(seq) {
  const data = await api("/vouchers");
  if (seq !== state.seq || state.page !== "vouchers") return false;
  state.voucherAdmin = data;
  return true;
}

function voucherAdminPage() {
  const d = state.voucherAdmin;
  if (!d) return pageHead() + loading();
  const extra = d.can_manage
    ? `<button class="btn small" data-voucher="reward">${icon("plus")}${t("dot2NewReward")}</button><button class="btn primary small" data-voucher="issue">${icon("plus")}${t("dot2Issue")}</button>`
    : "";
  return pageHead(extra) + `<div class="dot2-admin">
      <section class="panel"><header class="panel-heading"><h3>${icon("ticket")} ${t("dot2Redeem")}</h3></header>
        <form id="dot2-lookup" class="dot2-lookup"><label><span>${t("dot2CodeLabel")}</span><input class="input" name="code" maxlength="24" autocomplete="off" placeholder="CH-XXXX-XXXX" value="${esc(state.voucherCode || "")}"></label><button class="btn primary" type="submit">${t("dot2Lookup")}</button></form>
        <div id="dot2-lookup-result">${dot2LookupResult()}</div>
      </section>
      <div class="dot2-side">
        ${d.can_manage ? `<section class="panel"><header class="panel-heading"><h3>${icon("gift")} ${t("dot2Catalog")}</h3></header>${dot2CatalogTable(d.catalog)}</section>` : ""}
        <section class="panel"><header class="panel-heading"><h3>${icon("clock")} ${t("dot2Events")}</h3></header>${dot2EventsTable(d.events)}</section>
      </div>
    </div>`;
}

function dot2LookupResult() {
  const r = state.voucherLookup;
  if (!r) return "";
  const v = r.voucher, active = v.state === "ACTIVE", food = ["FOOD_DISCOUNT", "FREE_DRINK"].includes(v.reward_type);
  const orders = food
    ? (r.orders.length
      ? `<label><span>${t("dot2ChooseOrder")}</span><select class="input" id="dot2-order">${r.orders.map((o) => `<option value="${o.id}">${esc(o.code)} · ${esc(o.machine_code)} · ${money(o.total_amount)}</option>`).join("")}</select></label>`
      : `<p class="notice warn">${t("dot2NoOrder")}</p>`)
    : "";
  const can = active && r.applies_here && (!food || r.orders.length);
  return `<article class="dot2-ticket ${v.state} compact">
      <div class="dot2-stub"><span class="dot2-value">${dot2Value(v)}</span><small>${t("dot2Type" + v.reward_type)}</small></div>
      <div class="dot2-body"><header><h3>${esc(v.name)}</h3><span class="dot2-state ${v.state}">${t("dot2State" + v.state)}</span></header>
        <div class="key-values">${kv("dot2Owner", esc(v.customer_name))}${kv("dot2Code2", esc(dot2Code(v.code)))}${kv("dot2Expires", dt(v.expires_at))}${v.min_order_amount ? kv("dot2MinOrder", money(v.min_order_amount)) : ""}${kv("dot2Scope", v.store_name ? esc(v.store_name) : t("dot2AllStores"))}</div>
        ${r.applies_here ? "" : `<p class="notice warn">${t("dot2NotHere")}</p>`}
      </div></article>
    ${active ? `<div class="dot2-confirm">${orders}
      <label class="dot1-check"><input type="checkbox" id="dot2-verified"><span>${t("dot2Verify")}</span></label>
      <div class="actions">${state.voucherAdmin?.can_manage ? `<button class="btn small danger" data-voucher="revoke" data-id="${v.id}">${t("dot2Revoke")}</button>` : ""}
        <button class="btn primary" data-voucher="redeem" data-customer="${v.customer_id}" ${can ? "" : "disabled"}>${t("dot2Confirm")}</button></div></div>` : ""}`;
}

function dot2CatalogTable(items) {
  if (!items.length) return empty();
  const rows = items.map((c) => `<tr><td><strong>${esc(c.name)}</strong><br><small class="muted">${esc(c.code)}</small></td>
      <td>${t("dot2Type" + c.reward_type)}</td><td class="money">${c.reward_type === "MEMBER_POINTS" ? `${c.value} ${t("dot2Points")}` : money(c.value)}</td>
      <td>${c.valid_days} ${t("pcDays")}</td><td>${badge(c.is_active ? "ACTIVE" : "INACTIVE")}</td>
      <td><button class="btn ghost small" data-voucher="reward" data-id="${c.id}">${t("edit")}</button></td></tr>`).join("");
  return table(["name", "dot2Type", "dot2Value", "dot2ValidDays", "status", ""], rows);
}

function dot2EventsTable(events) {
  if (!events.length) return empty("dot2NoEvents");
  const rows = events.map((e) => `<tr class="${e.action === "REJECT" ? "dot2-reject" : ""}"><td>${dt(e.created_at)}</td>
      <td>${t("dot2Act" + e.action)}</td><td>${e.voucher_code ? esc(dot2Code(e.voucher_code)) : "—"}</td>
      <td>${esc(e.employee_name || "—")}</td><td><small>${esc(e.reason)}</small></td></tr>`).join("");
  return table(["dot2When", "dot2Action", "dot2Code2", "dot2Staff", "dot2Reason"], rows);
}

function dot2RewardForm(id) {
  const d = state.voucherAdmin, c = id ? d.catalog.find((x) => x.id === Number(id)) : null;
  const types = ["FOOD_DISCOUNT", "FREE_DRINK", "PLAYTIME_CREDIT", "MEMBER_POINTS"];
  dot1Dialog("dot2NewReward", `<div class="form-grid">
      ${dot1Input("code", "dot2Code2", c?.code, "text", 'maxlength="20" required')}
      ${dot1Input("name", "name", c?.name, "text", 'maxlength="80" required')}
      <label><span>${t("dot2Type")}</span><select class="input" name="reward_type">${types.map((x) => `<option value="${x}" ${c?.reward_type === x ? "selected" : ""}>${t("dot2Type" + x)}</option>`).join("")}</select><span class="field-error" data-error="reward_type"></span></label>
      ${dot1Input("value", "dot2Value", c?.value ?? 10000, "number", 'min="1" step="1"')}
      ${dot1Input("min_order_amount", "dot2MinOrder", c?.min_order_amount ?? 0, "number", 'min="0" step="1000"')}
      ${dot1Input("valid_days", "dot2ValidDays", c?.valid_days ?? 30, "number", 'min="1" max="365" step="1"')}
      ${dot1Input("coin_cost", "dot2CoinCost", c?.coin_cost ?? "", "number", 'min="1" step="1"')}
      ${dot1Check("is_active", "dot1Active", c ? c.is_active : true)}
      ${d.is_admin ? dot1Check("all_stores", "dot2AllStoresCheck", c ? c.store_id === null : false) : ""}
    </div>`, async (form) => {
    const f = form.elements, coin = f.coin_cost.value.trim();
    const body = { code: f.code.value, name: f.name.value, reward_type: f.reward_type.value, value: Number(f.value.value),
      min_order_amount: Number(f.min_order_amount.value), valid_days: Number(f.valid_days.value),
      coin_cost: coin === "" ? null : Number(coin), is_active: f.is_active.checked, all_stores: f.all_stores?.checked ?? false };
    await api(c ? `/rewards/${c.id}` : "/rewards", { method: c ? "PATCH" : "POST", body });
  });
}

async function dot2IssueForm() {
  const d = state.voucherAdmin, customers = await api("/customers");
  const rewards = d.catalog.filter((c) => c.is_active);
  dot1Dialog("dot2Issue", `<div class="form-grid">
      <label class="wide"><span>${t("dot2NewReward")}</span><select class="input" name="catalog_id">${rewards.map((c) => `<option value="${c.id}">${esc(c.name)}</option>`).join("")}</select><span class="field-error" data-error="catalog_id"></span></label>
      <label class="wide"><span>${t("dot2Customer")}</span><select class="input" name="customer_id">${customers.map((c) => `<option value="${c.customer_id ?? c.id}">${esc(c.full_name)} · ${esc(c.phone || "")}</option>`).join("")}</select><span class="field-error" data-error="customer_id"></span></label>
    </div>`, async (form) => {
    const voucher = await api("/vouchers/issue", { method: "POST",
      body: { catalog_id: Number(form.elements.catalog_id.value), customer_id: Number(form.elements.customer_id.value) } });
    toast(`${t("dot2Issued")}: ${dot2Code(voucher.code)}`);
  }, "dot2Issue");
}

async function dot2DoLookup(code) {
  state.voucherCode = code;
  try {
    state.voucherLookup = await api(`/vouchers/lookup?code=${encodeURIComponent(code)}`);
  } catch (error) {
    state.voucherLookup = null;
    toast(Object.values(error.field_errors || {}).join(" · ") || error.message, true);
  }
  const box = $("#dot2-lookup-result");
  if (box) box.innerHTML = dot2LookupResult();
}

document.addEventListener("submit", (event) => {
  if (event.target.id !== "dot2-lookup") return;
  event.preventDefault();
  const code = event.target.elements.code.value.trim();
  if (code) dot2DoLookup(code);
});

document.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-voucher]");
  if (!button || button.disabled || state.page !== "vouchers") return;
  const action = button.dataset.voucher;
  try {
    if (action === "reward") dot2RewardForm(button.dataset.id);
    if (action === "issue") await dot2IssueForm();
    if (action === "redeem") {
      if (!$("#dot2-verified")?.checked) { $("#dot2-verified")?.focus(); return; }
      button.disabled = true;
      const order = $("#dot2-order")?.value;
      const result = await api("/vouchers/redeem", { method: "POST", body: {
        code: state.voucherCode, customer_id: Number(button.dataset.customer), order_id: order ? Number(order) : null } });
      const detail = result.discount ? `${t("dot2Discount")}: ${money(result.discount)}`
        : result.bonus_credited ? `${t("dot2BonusAdded")}: ${money(result.bonus_credited)}`
        : `${t("dot2PointsAdded")}: +${result.points_granted}`;
      toast(`${t("dot2Applied")} · ${detail}`);
      await dot2DoLookup(state.voucherCode);
      await loadPage(true);
    }
    if (action === "revoke") {
      const reason = prompt(t("dot2RevokeReason"));
      if (!reason) return;
      await api(`/vouchers/${button.dataset.id}/revoke`, { method: "POST", body: { reason } });
      await dot2DoLookup(state.voucherCode);
      await loadPage(true);
    }
  } catch (error) {
    button.disabled = false;
    toast(Object.values(error.field_errors || {}).join(" · ") || error.message, true);
    if (state.voucherCode && action === "redeem") await loadPage(true);
  }
});
