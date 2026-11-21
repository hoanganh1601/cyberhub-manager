"use strict";
// Đợt 1 — Trang "Menu" cho nhân viên: hàng đợi gọi món (mọi nhân viên), còn/hết món (mọi nhân viên),
// thêm/sửa/ẩn món, nhóm món, giá, ảnh, thứ tự và lịch sử (MANAGER/ADMIN, backend kiểm tra lại quyền).

Object.assign(paths, {
  utensils: '<path d="M7 3v8M4 3v5a3 3 0 0 0 6 0V3M7 11v10M17 3c-2.2 0-3 2.5-3 5.5V13h3v8"/>',
});
Object.assign(copy, {
  menu: ["Menu đồ ăn", "Food menu"],
  menuSub: ["Yêu cầu gọi món từ khách đang chơi và danh mục món của cơ sở", "Orders from players and this store's menu"],
  dot1Queue: ["Yêu cầu gọi món", "Incoming orders"],
  dot1NoOrders: ["Không có đơn ở trạng thái này", "No orders in this status"],
  dot1AllOrders: ["Tất cả", "All"],
  dot1StatusNEW: ["Mới", "New"],
  dot1StatusPREPARING: ["Đang chuẩn bị", "Preparing"],
  dot1StatusSERVED: ["Đã phục vụ", "Served"],
  dot1StatusPAID: ["Đã thanh toán", "Paid"],
  dot1StatusREFUNDED: ["Đã hoàn tiền", "Refunded"],
  posRequestReversal: ["Đề xuất hủy/hoàn", "Request cancellation/refund"],
  posPendingReversals: ["Yêu cầu hủy/hoàn chờ duyệt", "Pending cancellations/refunds"],
  posApproveReversal: ["Duyệt", "Approve"],
  posRejectReversal: ["Từ chối", "Reject"],
  posDisposition: ["Xử lý nguyên liệu", "Ingredient handling"],
  posReason: ["Lý do bắt buộc", "Required reason"],
  posRestock: ["Nhập trả kho", "Return to stock"],
  posWaste: ["Ghi hao hụt", "Record waste"],
  posRefundConfirmed: ["Tôi đã hoàn tiền cho khách", "I have returned the money"],
  posRefundReference: ["Mã giao dịch hoàn tiền", "Refund transaction reference"],
  dot1StatusCANCELLED: ["Đã hủy", "Cancelled"],
  dot1HoldUntil: ["Giữ tồn đến", "Stock held until"],
  dot1ExpiredAutomatically: ["Tự hủy do hết thời gian giữ", "Automatically cancelled when hold expired"],
  dot1StartPreparing: ["Bắt đầu chuẩn bị", "Start preparing"],
  dot1Catalog: ["Danh mục món", "Menu items"],
  dot1NewCategory: ["Nhóm món", "Category"],
  dot1NewItem: ["Thêm món", "Add item"],
  dot1EditItem: ["Sửa món", "Edit item"],
  dot1EditCategory: ["Nhóm món", "Category"],
  dot1Served: ["Đã phục vụ", "Served"],
  dot1Pay: ["Thanh toán", "Pay"],
  dot1PaymentMethod: ["Phương thức thanh toán", "Payment method"],
  dot1Discount: ["Ưu đãi / khuy?n m?i", "Promotion"],
  dot1AmountDue: ["Cần thu", "Amount due"],
  dot1Cash: ["Tiền mặt", "Cash"],
  dot1Transfer: ["Chuyển khoản", "Transfer"],
  dot1Cancel: ["Hủy", "Cancel"],
  dot1Available: ["Còn món", "Available"],
  dot1Unavailable: ["Hết món", "Sold out"],
  dot1Hidden: ["Đang ẩn", "Hidden"],
  dot1Visible: ["Hiển thị cho khách", "Visible to customers"],
  dot1CategoryOff: ["Nhóm đang tắt", "Category disabled"],
  dot1Price: ["Giá (VND)", "Price (VND)"],
  dot1Description: ["Mô tả ngắn", "Short description"],
  dot1Sort: ["Thứ tự hiển thị", "Display order"],
  dot1PageLabel: ["Trang menu", "Menu page"],
  dot1UploadImage: ["Tải ảnh", "Upload image"],
  dot1NoHistory: ["Chưa có thay đổi", "No changes yet"],
  dot1Saved: ["Đã lưu", "Saved"],
  dot1Active: ["Đang dùng", "Active"],
  dot1Seat2: ["Máy", "Seat"],
  dot1FieldCREATE: ["Tạo món", "Created"], dot1FieldNAME: ["Tên", "Name"], dot1FieldCATEGORY: ["Nhóm", "Category"],
  dot1FieldPRICE: ["Giá", "Price"], dot1FieldAVAILABLE: ["Còn món", "Available"], dot1FieldVISIBLE: ["Hiển thị", "Visible"],
  dot1FieldIMAGE: ["Ảnh", "Image"],
  dot1ConfirmCancel: ["Hủy yêu cầu gọi món này?", "Cancel this order?"],
  dot1SortTip: ["Thứ tự cùng hàng trăm nằm chung một nhóm nhỏ trên bảng menu (vd. 0–99 là nhóm đầu, 100–199 có vạch ngăn bên trên).", "Items with the same hundreds in display order share a sub-group on the menu board (e.g. 0–99, then 100–199 below a divider)."],
  dot1CancelReason: ["Lý do hủy sau khi chuẩn bị", "Reason for cancelling after preparation"],
  posPromotions: ["Khuyến mãi POS", "POS promotions"],
  posPromoCode: ["Mã ưu đãi", "Promotion code"],
  posPromoKind: ["Quy tắc", "Rule"],
  posPromoValue: ["Giá trị (VND hoặc %)", "Value (VND or %)"],
  posPromoItem: ["Món áp dụng", "Eligible item"],
  posPromoStarts: ["Bắt đầu", "Starts"],
  posPromoEnds: ["Kết thúc", "Ends"],
  posPromoNew: ["Thêm ưu đãi", "Add promotion"],
  posPromoBOGO: ["Mua 3 trả 2", "Buy 3 pay 2"],
  posPromoPLAY_DRINK: ["Giảm nước khi đang chơi", "Play and drink"],
});

let dot1AdminTimer = null;

async function loadMenuAdmin(seq) {
  const [menu, orders, reversals, promotions] = await Promise.all([
    api("/menu"), api("/menu/orders?status=ALL"),
    ["STAFF", "MANAGER", "ADMIN"].includes(state.actor.role) ? api("/menu/reversals") : Promise.resolve([]),
    ["MANAGER", "ADMIN"].includes(state.actor.role) ? api("/menu/promotions") : Promise.resolve([]),
  ]);
  if (seq !== state.seq || state.page !== "menu") return false;
  state.menuAdmin = menu;
  state.menuOrders = orders;
  state.menuInventory = null;
  state.menuReversals = reversals;
  state.menuPromotions = promotions;
  return true;
}

function menuAdminPage() {
  const d = state.menuAdmin, orders = state.menuOrders || [];
  if (!d) return pageHead() + loading();
  const extra = d.can_manage
    ? `<button class="btn small" data-menuadmin="category">${icon("plus")}${t("dot1NewCategory")}</button><button class="btn primary small" data-menuadmin="item">${icon("plus")}${t("dot1NewItem")}</button>`
    : "";
  const filter = state.menuOrderFilter || "ALL";
  const visible = filter === "ALL" ? orders : orders.filter(o => o.status === filter);
  return pageHead(extra) + `<div class="dot1-admin">
      <section class="panel"><header class="panel-heading"><h3>${icon("bell")} ${t("dot1Queue")}</h3><span class="badge amber">${visible.length}</span></header>
        <div class="dot1-order-filters">${["ALL","NEW","PREPARING","SERVED","PAID","REFUNDED","CANCELLED"].map(s => `<button class="filter-btn ${filter === s ? "active" : ""}" data-menuadmin="order-filter" data-status="${s}">${t(s === "ALL" ? "dot1AllOrders" : "dot1Status" + s)} <span>${s === "ALL" ? orders.length : orders.filter(o => o.status === s).length}</span></button>`).join("")}</div>
        ${visible.length ? visible.map(dot1OrderCard).join("") : empty("dot1NoOrders")}</section>
      ${state.menuReversals?.length ? `<section class="panel"><header class="panel-heading"><h3>${t("posPendingReversals")}</h3></header>${state.menuReversals.map(r => `<article class="dot1-order"><strong>${esc(orders.find(o=>o.id===r.order_id)?.code || String(r.order_id))}</strong><p>${esc(r.reason)} · ${t(r.disposition === "RESTOCK" ? "posRestock" : "posWaste")}</p>${isManager() && r.requested_by !== state.actor.employee_id ? `<div class="actions"><button class="btn small primary" data-menuadmin="approve-reversal" data-id="${r.order_id}">${t("posApproveReversal")}</button><button class="btn small" data-menuadmin="reject-reversal" data-id="${r.order_id}">${t("posRejectReversal")}</button></div>` : ""}</article>`).join("")}</section>` : ""}
      <section class="panel"><header class="panel-heading"><h3>${icon("utensils")} ${t("dot1Catalog")}</h3></header>${dot1CatalogTable(d)}</section>
      ${d.can_manage ? dot1PromotionPanel() : ""}
    </div>`;
}

function dot1PromotionPanel() {
  const promos = state.menuPromotions || [];
  return `<section class="panel"><header class="panel-heading"><h3>${t("posPromotions")}</h3><button class="btn small primary" data-menuadmin="promotion">${t("posPromoNew")}</button></header>
    ${promos.length ? promos.map(p => `<article class="dot1-order"><strong>${esc(p.code)}</strong> · ${t("posPromo"+p.kind)}
      <span class="badge">${p.is_active ? t("dot1Active") : t("dot1Hidden")}</span>
      <p>${esc(state.menuAdmin.items.find(i=>i.id===p.item_id)?.name || p.item_id)} - ${p.kind === "BOGO" ? t("posPromoBOGO") : money(p.value)}
      · ${dt(p.starts_at)} → ${dt(p.ends_at)}</p><button class="btn small" data-menuadmin="promotion" data-id="${p.id}">${t("edit")}</button></article>`).join("") : empty()}
    </section>`;
}

function dot1OrderCard(order) {
  const capabilities = state.menuAdmin || {};
  const action = order.status === "NEW" && capabilities.can_prepare
    ? `<button class="btn small primary" data-menuadmin="prepare-order" data-id="${order.id}">${t("dot1StartPreparing")}</button>`
    : order.status === "PREPARING" && capabilities.can_serve
      ? `<button class="btn small primary" data-menuadmin="serve-order" data-id="${order.id}">${t("dot1Served")}</button>`
      : order.status === "SERVED" && capabilities.can_collect_payment
        ? `<button class="btn small primary" data-menuadmin="pay-order" data-id="${order.id}">${t("dot1Pay")}</button>`
        : "";
  const status = `<span class="dot1-status ${order.status}">${t("dot1Status" + order.status)}</span>`;
  return `<article class="dot1-order"><header><span><strong>${esc(order.machine_code)}</strong> · ${esc(order.customer_name)}</span><small>${dt(order.created_at)}</small></header>
      <div class="dot1-order-meta">${status}${order.payment_method ? `<span>${t("dot1" + (order.payment_method === "CASH" ? "Cash" : "Transfer"))}</span>` : ""}</div>
      <ul>${order.lines.map((l) => `<li>${l.quantity} × ${esc(l.item_name)} — ${money(l.unit_price * l.quantity)}</li>`).join("")}</ul>
      ${order.status === "NEW" && order.reservation_expires_at ? `<p class="note">${t("dot1HoldUntil")}: ${dt(order.reservation_expires_at)}</p>` : ""}
      ${order.cancel_reason === "AUTO_EXPIRED" ? `<p class="note">${t("dot1ExpiredAutomatically")}</p>` : ""}
      ${order.note ? `<p class="note">“${esc(order.note)}”</p>` : ""}
      <div class="actions"><span class="spacer">${t("dot1Total")}: <b>${money(order.total_amount)}</b>${order.discount_amount ? `<br>${t("dot1Discount")}: -${money(order.discount_amount)}<br>${t("dot1AmountDue")}: <b>${money(order.total_amount - order.discount_amount)}</b>` : ""}</span>
        ${capabilities.can_cancel && ["NEW","PREPARING"].includes(order.status) ? `<button class="btn small" data-menuadmin="cancel-order" data-id="${order.id}">${t("dot1Cancel")}</button>` : ""}
        ${["STAFF","MANAGER","ADMIN"].includes(state.actor.role) && ["SERVED","PAID"].includes(order.status) && !(state.menuReversals || []).some(r=>r.order_id===order.id) ? `<button class="btn small" data-menuadmin="request-reversal" data-id="${order.id}">${t("posRequestReversal")}</button>` : ""}
        ${action}</div>
    </article>`;
}

function dot1CatalogTable(d) {
  const pageName = (page) => t(page === "FOOD" ? "dot1Food" : "dot1Drink");
  const categories = [...d.categories].sort((a, b) => a.page.localeCompare(b.page) || a.sort_order - b.sort_order || a.id - b.id);
  const rows = categories.map((c) => {
    const items = d.items.filter((i) => i.category_id === c.id).sort((a, b) => a.sort_order - b.sort_order || a.id - b.id);
    const head = `<tr class="dot1-category-row"><td colspan="4">${pageName(c.page)} · ${esc(c.name)} ${c.is_active ? "" : `<span class="badge red">${t("dot1CategoryOff")}</span>`}
        ${d.can_manage ? `<button class="btn ghost small" data-menuadmin="category" data-id="${c.id}">${icon("edit")}${t("edit")}</button>` : ""}</td></tr>`;
    return head + items.map((item) => `<tr>
        <td><strong>${esc(item.name)}</strong>${item.is_visible ? "" : ` <span class="badge">${t("dot1Hidden")}</span>`}<br><small class="muted">${esc(item.description)}</small></td>
        <td class="money">${money(item.price)}</td>
        <td>${d.can_set_availability ? `<button class="btn small ${item.is_available ? "" : "danger"}" data-menuadmin="toggle" data-id="${item.id}" data-available="${!item.is_available}" title="${t(item.is_available ? "dot1Unavailable" : "dot1Available")}">${t(item.is_available ? "dot1Available" : "dot1Unavailable")}</button>` : t(item.is_available ? "dot1Available" : "dot1Unavailable")}</td>
        <td>${d.can_manage ? `<button class="btn ghost small" data-menuadmin="item" data-id="${item.id}">${t("edit")}</button>` : ""}</td>
      </tr>`).join("");
  }).join("");
  return rows ? table(["name", "dot1Price", "status", ""], rows) : empty();
}

// ----- Hộp thoại riêng (không dùng #modal để không đụng luồng submit chung) ------------
function dot1Dialog(title, body, onSubmit, submitLabel = "save") {
  let dialog = $("#dot1-dialog");
  if (!dialog) {
    dialog = document.createElement("dialog");
    dialog.id = "dot1-dialog";
    document.body.append(dialog);
  }
  dialog.innerHTML = `<form id="dot1-form" novalidate><header class="modal-header"><div><h2>${t(title)}</h2></div><button class="close" type="button" data-menuadmin="close" aria-label="${t("close")}">×</button></header>
      <div class="modal-body">${body}<div id="dot1-form-error" class="error-box" role="alert"></div></div>
      <footer class="modal-footer"><small>CyberHub Manager</small><button class="btn small" type="button" data-menuadmin="close">${t("cancel")}</button>${onSubmit ? `<button class="btn primary" type="submit">${t(submitLabel)}</button>` : ""}</footer></form>`;
  const form = $("#dot1-form", dialog);
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!onSubmit) return;
    const button = $("button[type=submit]", form);
    button.disabled = true;
    for (const node of form.querySelectorAll("[data-error]")) node.textContent = "";
    $("#dot1-form-error", form).textContent = "";
    try {
      await onSubmit(form);
      dialog.close();
      toast(t("dot1Saved"));
      await loadPage(true);
    } catch (error) {
      const errors = error.field_errors || {};
      let shown = false;
      for (const [key, message] of Object.entries(errors)) {
        const target = form.querySelector(`[data-error="${key}"]`);
        if (target) { target.textContent = message; shown = true; }
      }
      if (!shown) $("#dot1-form-error", form).textContent = Object.values(errors).join(" · ") || error.message;
      button.disabled = false;
    }
  });
  dialog.showModal();
  setTimeout(() => form.querySelector("input,select")?.focus(), 50);
}

const dot1Input = (name, label, value, type = "text", attrs = "") =>
  `<label><span>${t(label)}</span><input class="input" name="${name}" type="${type}" value="${esc(value ?? "")}" ${attrs}><span class="field-error" data-error="${name}"></span></label>`;
const dot1Check = (name, label, checked) =>
  `<label class="dot1-check"><input type="checkbox" name="${name}" ${checked ? "checked" : ""}><span>${t(label)}</span></label>`;

function dot1PromotionForm(id) {
  const promo = (state.menuPromotions || []).find(p => p.id === Number(id));
  const localValue = (date) => {
    const value = new Date(date);
    return new Date(value.getTime() - value.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
  };
  const now = Date.now();
  const option = (value, label, selected) => `<option value="${value}" ${selected ? "selected" : ""}>${label}</option>`;
  dot1Dialog("posPromotions", `<div class="form-grid">
    ${dot1Input("code", "posPromoCode", promo?.code || "", "text", 'maxlength="30" required')}
    <label><span>${t("posPromoKind")}</span><select class="input" name="kind">${["PLAY_DRINK","BOGO"].map(k=>option(k,t("posPromo"+k),promo?.kind===k)).join("")}</select></label>
    <label><span>${t("posPromoItem")}</span><select class="input" name="item_id">${option("","—",!promo?.item_id)}${state.menuAdmin.items.map(i=>option(i.id,esc(i.name),promo?.item_id===i.id)).join("")}</select></label>
    ${dot1Input("value", "posPromoValue", promo?.value ?? 5000, "number", 'min="1" step="1" required')}
    ${dot1Input("starts_at", "posPromoStarts", localValue(promo?.starts_at || now), "datetime-local", "required")}
    ${dot1Input("ends_at", "posPromoEnds", localValue(promo?.ends_at || now + 365*86400000), "datetime-local", "required")}
    ${dot1Check("is_active", "dot1Active", promo ? promo.is_active : true)}
    <p class="dot1-tip">${t("posPromoBOGO")}: ${t("posPromoValue")} = 1.</p>
  </div>`, async (form) => {
    const kind = form.elements.kind.value;
    await api(promo ? `/menu/promotions/${promo.id}` : "/menu/promotions", {
      method: promo ? "PATCH" : "POST", body: {
        code: form.elements.code.value, kind,
        item_id: Number(form.elements.item_id.value) || null,
        value: Number(form.elements.value.value),
        starts_at: new Date(form.elements.starts_at.value).toISOString(),
        ends_at: new Date(form.elements.ends_at.value).toISOString(),
        is_active: form.elements.is_active.checked,
      }
    });
  });
}

function dot1CategoryForm(id) {
  const c = id ? state.menuAdmin.categories.find((x) => x.id === Number(id)) : null;
  dot1Dialog("dot1EditCategory", `<div class="form-grid">
      ${dot1Input("name", "name", c?.name, "text", 'maxlength="60" required')}
      <label><span>${t("dot1PageLabel")}</span><select class="input" name="page"><option value="FOOD" ${c?.page !== "DRINK" ? "selected" : ""}>${t("dot1Food")}</option><option value="DRINK" ${c?.page === "DRINK" ? "selected" : ""}>${t("dot1Drink")}</option></select><span class="field-error" data-error="page"></span></label>
      ${dot1Input("sort_order", "dot1Sort", c?.sort_order ?? 0, "number", 'min="0" max="9999" step="1"')}
      ${dot1Check("is_active", "dot1Active", c ? c.is_active : true)}
    </div>`, async (form) => {
    const body = { name: form.elements.name.value, page: form.elements.page.value,
      sort_order: Number(form.elements.sort_order.value), is_active: form.elements.is_active.checked };
    await api(c ? `/menu/categories/${c.id}` : "/menu/categories", { method: c ? "PATCH" : "POST", body });
  });
}

function dot1ItemForm(id) {
  const d = state.menuAdmin, item = id ? d.items.find((x) => x.id === Number(id)) : null;
  if (!d.categories.length) { dot1CategoryForm(); return; }
  const options = d.categories.map((c) => `<option value="${c.id}" ${item?.category_id === c.id ? "selected" : ""}>${t(c.page === "FOOD" ? "dot1Food" : "dot1Drink")} · ${esc(c.name)}</option>`).join("");
  dot1Dialog(item ? "dot1EditItem" : "dot1NewItem", `<div class="form-grid">
      ${dot1Input("name", "name", item?.name, "text", 'maxlength="80" required')}
      <label><span>${t("dot1NewCategory")}</span><select class="input" name="category_id">${options}</select><span class="field-error" data-error="category_id"></span></label>
      ${dot1Input("price", "dot1Price", item?.price ?? 25000, "number", 'min="1000" max="10000000" step="1000"')}
      ${dot1Input("sort_order", "dot1Sort", item?.sort_order ?? 0, "number", 'min="0" max="9999" step="1"')}
      <p class="dot1-tip">${t("dot1SortTip")}</p>
      <label class="wide"><span>${t("dot1Description")}</span><input class="input" name="description" maxlength="200" value="${esc(item?.description || "")}"><span class="field-error" data-error="description"></span></label>
      ${dot1Check("is_visible", "dot1Visible", item ? item.is_visible : true)}
      ${dot1Check("is_available", "dot1Available", item ? item.is_available : true)}
    </div>`, async (form) => {
    const body = { name: form.elements.name.value, category_id: Number(form.elements.category_id.value),
      price: Number(form.elements.price.value), sort_order: Number(form.elements.sort_order.value),
      description: form.elements.description.value, is_visible: form.elements.is_visible.checked,
      is_available: form.elements.is_available.checked };
    await api(item ? `/menu/items/${item.id}` : "/menu/items", { method: item ? "PATCH" : "POST", body });
  });
}

document.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-menuadmin]");
  if (!button || button.disabled) return;
  const action = button.dataset.menuadmin, id = button.dataset.id;
  if (action === "close") { $("#dot1-dialog")?.close(); return; }
  if (state.page !== "menu" || !state.menuAdmin) return;
  try {
    if (action === "category" && state.menuAdmin.can_manage) dot1CategoryForm(id);
    if (action === "promotion" && state.menuAdmin.can_manage) dot1PromotionForm(id);
    if (action === "order-filter") { state.menuOrderFilter = button.dataset.status; renderPage(); return; }
    if (action === "item" && state.menuAdmin.can_manage) dot1ItemForm(id);
    if (action === "toggle" && state.menuAdmin.can_set_availability) {
      button.disabled = true;
      await api(`/menu/items/${id}/availability`, { method: "POST", body: { available: button.dataset.available === "true" } });
      await loadPage(true);
    }
    if (action === "prepare-order" || action === "serve-order" || action === "cancel-order") {
      const allowed = {
        "prepare-order": state.menuAdmin.can_prepare,
        "serve-order": state.menuAdmin.can_serve,
        "cancel-order": state.menuAdmin.can_cancel,
      };
      if (!allowed[action]) return;
      const order = (state.menuOrders || []).find((item) => item.id === Number(id));
      if (action === "cancel-order" && order?.status === "PREPARING") {
        dot1Dialog("dot1Cancel", `<div class="form-grid">${dot1Input("reason", "dot1CancelReason", "", "text", 'maxlength="255" required')}</div>`, async (form) => {
          await api(`/menu/orders/${id}/status`, { method: "POST", body: {
            status: "CANCELLED", reason: form.elements.reason.value,
          } });
        }, "dot1Cancel");
        return;
      }
      if (action === "cancel-order" && !confirm(t("dot1ConfirmCancel"))) return;
      button.disabled = true;
      await api(`/menu/orders/${id}/status`, { method: "POST", body: { status: action === "prepare-order" ? "PREPARING" : action === "serve-order" ? "SERVED" : "CANCELLED" } });
      await loadPage(true);
    }
    if (action === "pay-order" && state.menuAdmin.can_collect_payment) {
      const order = (state.menuOrders || []).find(item => item.id === Number(id));
      dot1Dialog("dot1Pay", `<div class="form-grid"><label><span>${t("dot1PaymentMethod")}</span><select class="input" name="method"><option value="CASH">${t("dot1Cash")}</option><option value="TRANSFER">${t("dot1Transfer")}</option></select></label></div><div class="notice info">${t("dot1Total")}: ${money(order?.total_amount || 0)}${order?.discount_amount ? `<br>${t("dot1Discount")}: -${money(order.discount_amount)}` : ""}<br>${t("dot1AmountDue")}: <strong>${money((order?.total_amount || 0) - (order?.discount_amount || 0))}</strong></div>`, async (form) => {
        await api(`/menu/orders/${id}/payment`, { method: "POST", body: { method: form.elements.method.value } });
      }, "dot1Pay");
    }
    if (action === "request-reversal" && ["STAFF","MANAGER","ADMIN"].includes(state.actor.role)) {
      dot1Dialog("posRequestReversal", `<div class="form-grid">${dot1Input("reason", "posReason", "", "text", 'minlength="5" maxlength="255" required')}<label><span>${t("posDisposition")}</span><select class="input" name="disposition"><option value="WASTE">${t("posWaste")}</option><option value="RESTOCK">${t("posRestock")}</option></select></label></div>`, async (form) => {
        await api(`/menu/orders/${id}/reversal`, {method:"POST", body:{reason:form.elements.reason.value, disposition:form.elements.disposition.value}});
      }, "posRequestReversal");
    }
    if (action === "reject-reversal" && isManager()) {
      if (!confirm(t("posRejectReversal"))) return;
      button.disabled = true;
      await api(`/menu/orders/${id}/reversal/decision`, {method:"POST", body:{approve:false}});
      await loadPage(true);
    }
    if (action === "approve-reversal" && isManager()) {
      const order = (state.menuOrders || []).find(item => item.id === Number(id));
      const refund = order?.status === "PAID";
      dot1Dialog("posApproveReversal", refund ? `<div class="notice info">${t("dot1AmountDue")}: ${money(order.total_amount-order.discount_amount)}</div><div class="form-grid">${dot1Check("refund_confirmed","posRefundConfirmed",false)}<label><span>${t("dot1PaymentMethod")}</span><select class="input" name="refund_method"><option value="CASH">${t("dot1Cash")}</option><option value="TRANSFER">${t("dot1Transfer")}</option></select></label>${dot1Input("refund_reference","posRefundReference","","text",'maxlength="100"')}</div>` : `<p>${t("posDisposition")}: ${t((state.menuReversals||[]).find(r=>r.order_id===Number(id))?.disposition === "RESTOCK" ? "posRestock" : "posWaste")}</p>`, async (form) => {
        await api(`/menu/orders/${id}/reversal/decision`, {method:"POST", body:{approve:true, refund_confirmed:refund ? form.elements.refund_confirmed.checked : false, refund_method:refund ? form.elements.refund_method.value : null, refund_reference:refund ? form.elements.refund_reference.value : null}});
      }, "posApproveReversal");
    }
  } catch (error) {
    button.disabled = false;
    const details = Object.values(error.field_errors || {});
    toast(details.length ? details.join(" · ") : error.message, true);
    if (error.code === "CONFLICT") await loadPage(true);
  }
});

// Được renderPage() gọi sau khi vẽ trang menu: tự làm mới hàng đợi mỗi 20 giây.
function wireMenuAdmin() {
  clearInterval(dot1AdminTimer);
  dot1AdminTimer = setInterval(() => {
    if (state.page !== "menu" || !state.actor) { clearInterval(dot1AdminTimer); return; }
    if (document.hidden || $("#dot1-dialog")?.open) return;
    loadPage(true);
  }, 20000);

}
