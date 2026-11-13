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
  dot1Discount: ["Ưu đãi / voucher", "Promotion / voucher"],
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
  dot1Image: ["Ảnh", "Image"],
  dot1UploadImage: ["Tải ảnh", "Upload image"],
  dot1History: ["Lịch sử", "History"],
  dot1NoHistory: ["Chưa có thay đổi", "No changes yet"],
  dot1Saved: ["Đã lưu", "Saved"],
  dot1Active: ["Đang dùng", "Active"],
  dot1Seat2: ["Máy", "Seat"],
  dot1FieldCREATE: ["Tạo món", "Created"], dot1FieldNAME: ["Tên", "Name"], dot1FieldCATEGORY: ["Nhóm", "Category"],
  dot1FieldPRICE: ["Giá", "Price"], dot1FieldAVAILABLE: ["Còn món", "Available"], dot1FieldVISIBLE: ["Hiển thị", "Visible"],
  dot1FieldIMAGE: ["Ảnh", "Image"],
  dot1ConfirmCancel: ["Hủy yêu cầu gọi món này?", "Cancel this order?"],
  dot1SortTip: ["Thứ tự cùng hàng trăm nằm chung một nhóm nhỏ trên bảng menu (vd. 0–99 là nhóm đầu, 100–199 có vạch ngăn bên trên).", "Items with the same hundreds in display order share a sub-group on the menu board (e.g. 0–99, then 100–199 below a divider)."],
  invTitle: ["Kho nguyên liệu", "Ingredient stock"],
  invAdd: ["Thêm nguyên liệu", "Add ingredient"],
  invReceive: ["Nhập kho", "Receive stock"],
  invRecipe: ["Công thức", "Recipe"],
  invUnit: ["Đơn vị", "Unit"],
  invOnHand: ["Tồn thực", "On hand"],
  invReserved: ["Đã giữ", "Reserved"],
  invAvailable: ["Khả dụng", "Available"],
  invReorder: ["Ngưỡng cảnh báo", "Reorder point"],
  invQuantity: ["Số lượng", "Quantity"],
  invReference: ["Mã chứng từ", "Reference"],
  invNote: ["Ghi chú", "Note"],
  invTrack: ["Quản lý tồn theo công thức", "Track stock by recipe"],
  invEmpty: ["Chưa có nguyên liệu", "No ingredients yet"],
  invLow: ["Sắp hết", "Low stock"],
  invDemoNotice: ["Demo: sổ kho chưa được mô phỏng. Kiểm thử tồn kho trên MySQL.", "Demo: stock ledger is not simulated. Validate inventory with MySQL."],
  invCancelReason: ["Lý do hủy sau khi chuẩn bị", "Reason for cancelling after preparation"],
  invIssue: ["Xuất kho", "Issue stock"],
  invReturn: ["Trả kho", "Return stock"],
  invCount: ["Kiểm kê", "Count stock"],
  invCounted: ["Số đếm thực tế", "Counted on hand"],
  invCountRequests: ["Phiếu kiểm kê chờ duyệt", "Pending stock counts"],
  invApprove: ["Duyệt", "Approve"],
  invReject: ["Từ chối", "Reject"],
  invReason: ["Lý do", "Reason"],
  invCountStale: ["Tồn đã thay đổi thì phải kiểm kê lại trước khi duyệt.", "Recount if stock has changed before approval."],
  invConfirmApprove: ["Duyệt chênh lệch kiểm kê và cập nhật tồn kho?", "Approve the count difference and update stock?"],
  invConfirmReject: ["Từ chối phiếu kiểm kê này?", "Reject this stock count?"],
  posPromotions: ["Khuyến mãi POS", "POS promotions"],
  posPromoCode: ["Mã ưu đãi", "Promotion code"],
  posPromoKind: ["Quy tắc", "Rule"],
  posPromoValue: ["Giá trị (VND hoặc %)", "Value (VND or %)"],
  posPromoItem: ["Món áp dụng", "Eligible item"],
  posPromoTier: ["Hạng tối thiểu", "Minimum tier"],
  posPromoStarts: ["Bắt đầu", "Starts"],
  posPromoEnds: ["Kết thúc", "Ends"],
  posPromoNew: ["Thêm ưu đãi", "Add promotion"],
  posPromoBOGO: ["Mua 3 trả 2", "Buy 3 pay 2"],
  posPromoPLAY_DRINK: ["Giảm nước khi đang chơi", "Play and drink"],
  posPromoTIER_PERCENT: ["Giảm theo hạng", "Tier discount"],
});

Object.assign(copy, {
  kqTitle: ["Hàng đợi bếp", "Kitchen queue"],
  kqSub: ["Đơn khách gọi: nhận đơn, chuẩn bị và báo đã phục vụ", "Customer orders: start, prepare and mark served"],
  kqWaiting: ["Chờ chuẩn bị", "Waiting"],
  kqPreparing: ["Đang chuẩn bị", "Preparing"],
  kqNoWaiting: ["Không có đơn đang chờ", "No orders waiting"],
  kqNoPreparing: ["Không có đơn đang chuẩn bị", "Nothing in preparation"],
  kqWaited: ["Đã chờ {n} phút", "Waiting {n} min"],
  kqJustNow: ["Vừa nhận", "Just received"],
  ivTitle: ["Kho nguyên liệu", "Ingredient stock"],
  ivSub: ["Tồn kho, cảnh báo sắp hết, nhập và xuất kho", "Stock levels, low-stock alerts, receiving and issuing"],
  ivKpiItems: ["Nguyên liệu đang dùng", "Active ingredients"],
  ivKpiLow: ["Sắp hết", "Low stock"],
  ivKpiOut: ["Hết hàng", "Out of stock"],
  ivKpiReserved: ["Đang giữ cho đơn", "Reserved for orders"],
  ivAlerts: ["Cảnh báo sắp hết", "Low-stock alerts"],
  ivNoAlerts: ["Không có nguyên liệu nào sắp hết", "Nothing is running low"],
});

// Bếp và Thủ kho dùng chung route "menu" nhưng thấy tiêu đề riêng (sidebar, tiêu đề trang, tab trình duyệt).
// Dùng getter nên không phải sửa app.js; có setter để script khác gán copy.menu vẫn không lỗi.
const ROLE_PAGE_COPY = {
  KITCHEN: { menu: copy.kqTitle, menuSub: copy.kqSub },
  INVENTORY: { menu: copy.ivTitle, menuSub: copy.ivSub },
};
for (const key of ["menu", "menuSub"]) {
  let generic = copy[key];
  Object.defineProperty(copy, key, {
    configurable: true,
    enumerable: true,
    get: () => ROLE_PAGE_COPY[state.actor?.role]?.[key] || generic,
    set: (value) => { generic = value; },
  });
}

let dot1AdminTimer = null;

// Bếp chỉ cần đơn đang chờ và đang chuẩn bị.
async function dot1KitchenOrders() {
  const [waiting, preparing] = await Promise.all([api("/menu/orders?status=NEW"), api("/menu/orders?status=PREPARING")]);
  return [...waiting, ...preparing];
}

async function loadMenuAdmin(seq) {
  const role = state.actor.role, kitchen = role === "KITCHEN", stock = role === "INVENTORY";
  // Mỗi vai trò chỉ tải dữ liệu của chính mình: Bếp không tải kho/hoàn hủy/khuyến mãi, Thủ kho không tải đơn.
  const [menu, orders, inventory, reversals, promotions] = await Promise.all([
    api("/menu"),
    stock ? Promise.resolve([]) : kitchen ? dot1KitchenOrders() : api("/menu/orders?status=ALL"),
    kitchen ? Promise.resolve(null) : api("/inventory"),
    ["STAFF", "MANAGER", "ADMIN"].includes(role) ? api("/menu/reversals") : Promise.resolve([]),
    ["MANAGER", "ADMIN"].includes(role) ? api("/menu/promotions") : Promise.resolve([]),
  ]);
  if (seq !== state.seq || state.page !== "menu") return false;
  state.menuAdmin = menu;
  state.menuOrders = orders;
  state.menuInventory = inventory;
  state.menuReversals = reversals;
  state.menuPromotions = promotions;
  return true;
}

function menuAdminPage() {
  const d = state.menuAdmin, orders = state.menuOrders || [];
  if (!d) return pageHead() + loading();
  if (state.actor.role === "KITCHEN") return dot1KitchenPage();
  if (state.actor.role === "INVENTORY") return dot1StockPage();
  const extra = d.can_manage
    ? `<button class="btn small" data-menuadmin="category">${icon("plus")}${t("dot1NewCategory")}</button><button class="btn primary small" data-menuadmin="item">${icon("plus")}${t("dot1NewItem")}</button>`
    : "";
  const filter = state.menuOrderFilter || "ALL";
  const visible = filter === "ALL" ? orders : orders.filter(o => o.status === filter);
  return pageHead(extra) + `${state.mode === "demo" ? `<div class="notice info">${t("invDemoNotice")}</div>` : ""}<div class="dot1-admin">
      <section class="panel"><header class="panel-heading"><h3>${icon("bell")} ${t("dot1Queue")}</h3><span class="badge amber">${visible.length}</span></header>
        <div class="dot1-order-filters">${["ALL","NEW","PREPARING","SERVED","PAID","REFUNDED","CANCELLED"].map(s => `<button class="filter-btn ${filter === s ? "active" : ""}" data-menuadmin="order-filter" data-status="${s}">${t(s === "ALL" ? "dot1AllOrders" : "dot1Status" + s)} <span>${s === "ALL" ? orders.length : orders.filter(o => o.status === s).length}</span></button>`).join("")}</div>
        ${visible.length ? visible.map(dot1OrderCard).join("") : empty("dot1NoOrders")}</section>
      ${state.menuReversals?.length ? `<section class="panel"><header class="panel-heading"><h3>${t("posPendingReversals")}</h3></header>${state.menuReversals.map(r => `<article class="dot1-order"><strong>${esc(orders.find(o=>o.id===r.order_id)?.code || String(r.order_id))}</strong><p>${esc(r.reason)} · ${t(r.disposition === "RESTOCK" ? "posRestock" : "posWaste")}</p>${isManager() && r.requested_by !== state.actor.employee_id ? `<div class="actions"><button class="btn small primary" data-menuadmin="approve-reversal" data-id="${r.order_id}">${t("posApproveReversal")}</button><button class="btn small" data-menuadmin="reject-reversal" data-id="${r.order_id}">${t("posRejectReversal")}</button></div>` : ""}</article>`).join("")}</section>` : ""}
      <section class="panel"><header class="panel-heading"><h3>${icon("utensils")} ${t("dot1Catalog")}</h3></header>${dot1CatalogTable(d)}</section>
      ${d.can_manage ? dot1PromotionPanel() : ""}
      ${state.menuInventory?.enabled ? dot1InventoryPanel(state.menuInventory) : ""}
    </div>`;
}

// ----- Giao diện riêng cho Bếp ----------------------------------------------------------
function dot1KitchenPage() {
  const orders = (state.menuOrders || []).slice().sort((a, b) => new Date(a.created_at) - new Date(b.created_at));
  const column = (titleKey, emptyKey, list, tone) => `<section class="panel"><header class="panel-heading"><h3>${t(titleKey)}</h3><span class="badge ${tone}">${list.length}</span></header>${list.length ? list.map(dot1KitchenCard).join("") : empty(emptyKey)}</section>`;
  return pageHead() + `<div class="dot1-kitchen">${column("kqWaiting", "kqNoWaiting", orders.filter((o) => o.status === "NEW"), "amber")}${column("kqPreparing", "kqNoPreparing", orders.filter((o) => o.status === "PREPARING"), "cyan")}</div>`;
}

// Thẻ đơn của bếp: chỉ máy, món, ghi chú và đúng một nút; không hiện giá, thanh toán, hủy hay hoàn tiền.
function dot1KitchenCard(order) {
  const can = state.menuAdmin || {};
  const minutes = Math.max(0, Math.floor((Date.now() - new Date(order.created_at).getTime()) / 60000));
  const action = order.status === "NEW" && can.can_prepare
    ? `<button class="btn primary" data-menuadmin="prepare-order" data-id="${order.id}">${t("dot1StartPreparing")}</button>`
    : order.status === "PREPARING" && can.can_serve
      ? `<button class="btn primary" data-menuadmin="serve-order" data-id="${order.id}">${t("dot1Served")}</button>`
      : "";
  return `<article class="dot1-order dot1-kitchen-card ${minutes >= 10 ? "late" : ""}">
      <header><span><strong>${esc(order.machine_code)}</strong> · ${esc(order.code)}</span><small>${minutes < 1 ? t("kqJustNow") : t("kqWaited").replace("{n}", minutes)}</small></header>
      <ul>${order.lines.map((l) => `<li><b>${l.quantity}×</b> ${esc(l.item_name)}</li>`).join("")}</ul>
      ${order.note ? `<p class="note">“${esc(order.note)}”</p>` : ""}
      <div class="actions">${action}</div>
    </article>`;
}

// ----- Giao diện riêng cho Thủ kho -----------------------------------------------------
function dot1StockPage() {
  const inv = state.menuInventory;
  if (!inv?.enabled) return pageHead() + `<div class="notice info">${t("invDemoNotice")}</div>`;
  const active = inv.ingredients.filter((i) => i.is_active);
  const low = active.filter((i) => i.available <= i.reorder_point);
  const out = active.filter((i) => i.available <= 0);
  const reserved = active.reduce((sum, i) => sum + i.reserved, 0);
  const alerts = low.length
    ? table(["name", "invAvailable", "invReorder", ""], low.map((i) => `<tr>
        <td><strong>${esc(i.name)}</strong><br><small>${esc(i.code)} · ${esc(i.unit)}</small></td>
        <td class="${i.available <= 0 ? "red" : "amber"}">${i.available}</td><td>${i.reorder_point}</td>
        <td>${inv.can_receive ? `<button class="btn small primary" data-menuadmin="receive" data-id="${i.id}">${t("invReceive")}</button>` : ""}</td></tr>`).join(""))
    : empty("ivNoAlerts");
  return pageHead() + `<div class="metrics dot1-stock-metrics">${metric("ivKpiItems", active.length, "cyan", "utensils")}${metric("ivKpiLow", low.length, low.length ? "amber" : "green", "alert")}${metric("ivKpiOut", out.length, out.length ? "red" : "green", "alert")}${metric("ivKpiReserved", reserved, "", "clock")}</div>
    <section class="panel"><header class="panel-heading"><h3>${icon("alert")} ${t("ivAlerts")}</h3><span class="badge ${low.length ? "amber" : "green"}">${low.length}</span></header>${alerts}</section>
    ${dot1InventoryPanel(inv)}`;
}

function dot1PromotionPanel() {
  const promos = state.menuPromotions || [];
  return `<section class="panel"><header class="panel-heading"><h3>${t("posPromotions")}</h3><button class="btn small primary" data-menuadmin="promotion">${t("posPromoNew")}</button></header>
    ${promos.length ? promos.map(p => `<article class="dot1-order"><strong>${esc(p.code)}</strong> · ${t("posPromo"+p.kind)}
      <span class="badge">${p.is_active ? t("dot1Active") : t("dot1Hidden")}</span>
      <p>${p.kind === "TIER_PERCENT" ? `${esc(p.minimum_tier)} · ${p.value}%` : `${esc(state.menuAdmin.items.find(i=>i.id===p.item_id)?.name || p.item_id)} · ${p.kind === "BOGO" ? t("posPromoBOGO") : money(p.value)}`}
      · ${dt(p.starts_at)} → ${dt(p.ends_at)}</p><button class="btn small" data-menuadmin="promotion" data-id="${p.id}">${t("edit")}</button></article>`).join("") : empty()}
    </section>`;
}

function dot1InventoryPanel(inventory) {
  const actions = inventory.can_configure
    ? `<button class="btn primary small" data-menuadmin="ingredient">${t("invAdd")}</button>` : "";
  const rows = inventory.ingredients.map((i) => `<tr>
    <td><strong>${esc(i.name)}</strong><br><small>${esc(i.code)} · ${esc(i.unit)}</small></td>
    <td>${i.on_hand}</td><td>${i.reserved}</td>
    <td>${i.available}${i.available <= i.reorder_point ? ` <span class="badge amber">${t("invLow")}</span>` : ""}</td>
    <td>${i.reorder_point}</td>
    <td><div class="actions">
      ${inventory.can_receive ? `<button class="btn small" data-menuadmin="receive" data-id="${i.id}">${t("invReceive")}</button>` : ""}
      ${inventory.can_issue ? `<button class="btn small" data-menuadmin="issue" data-id="${i.id}">${t("invIssue")}</button><button class="btn small" data-menuadmin="return" data-id="${i.id}">${t("invReturn")}</button>` : ""}
      ${inventory.can_count ? `<button class="btn small" data-menuadmin="count" data-id="${i.id}">${t("invCount")}</button>` : ""}
    </div></td>
  </tr>`).join("");
  const recipeButtons = inventory.can_configure
    ? state.menuAdmin.items.map((item) => `<button class="btn small" data-menuadmin="recipe" data-id="${item.id}">${t("invRecipe")}: ${esc(item.name)}</button>`).join(" ") : "";
  const byId = new Map(inventory.ingredients.map((i) => [i.id, i]));
  const pending = (inventory.counts || []).filter((c) => c.status === "PENDING");
  const countRows = pending.map((c) => `<tr><td>${esc(byId.get(c.ingredient_id)?.name || c.ingredient_id)}</td>
    <td>${c.expected_on_hand} → ${c.counted_on_hand}</td><td>${esc(c.reason)}</td>
    <td>${inventory.can_approve && c.proposed_by !== inventory.actor_id ? `<div class="actions"><button class="btn small" data-menuadmin="approve-count" data-id="${c.id}">${t("invApprove")}</button><button class="btn small" data-menuadmin="reject-count" data-id="${c.id}">${t("invReject")}</button></div>` : ""}</td></tr>`).join("");
  return `<section class="panel"><header class="panel-heading"><h3>${t("invTitle")}</h3>${actions}</header>
    ${rows ? table(["name", "invOnHand", "invReserved", "invAvailable", "invReorder", ""], rows) : empty("invEmpty")}
    ${countRows ? `<h4>${t("invCountRequests")}</h4>${table(["name", "invCounted", "invReason", ""], countRows)}<p class="dot1-tip">${t("invCountStale")}</p>` : ""}
    <div class="actions">${recipeButtons}</div></section>`;
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
    const head = `<tr class="dot1-category-row"><td colspan="5">${pageName(c.page)} · ${esc(c.name)} ${c.is_active ? "" : `<span class="badge red">${t("dot1CategoryOff")}</span>`}
        ${d.can_manage ? `<button class="btn ghost small" data-menuadmin="category" data-id="${c.id}">${icon("edit")}${t("edit")}</button>` : ""}</td></tr>`;
    return head + items.map((item) => `<tr>
        <td>${item.image_version ? `<img class="dot1-thumb" src="/api/menu/items/${item.id}/image?v=${encodeURIComponent(item.image_version)}" alt="">` : `<span class="dot1-thumb">${esc(item.name.slice(0, 1).toUpperCase())}</span>`}</td>
        <td><strong>${esc(item.name)}</strong>${item.is_visible ? "" : ` <span class="badge">${t("dot1Hidden")}</span>`}<br><small class="muted">${esc(item.description)}</small></td>
        <td class="money">${money(item.price)}</td>
        <td>${d.can_set_availability ? `<button class="btn small ${item.is_available ? "" : "danger"}" data-menuadmin="toggle" data-id="${item.id}" data-available="${!item.is_available}" title="${t(item.is_available ? "dot1Unavailable" : "dot1Available")}">${t(item.is_available ? "dot1Available" : "dot1Unavailable")}</button>` : t(item.is_available ? "dot1Available" : "dot1Unavailable")}</td>
        <td>${d.can_manage ? `<div class="actions"><button class="btn ghost small" data-menuadmin="item" data-id="${item.id}">${t("edit")}</button><button class="btn ghost small" data-menuadmin="image" data-id="${item.id}">${t("dot1UploadImage")}</button><button class="btn ghost small" data-menuadmin="history" data-id="${item.id}">${t("dot1History")}</button></div>` : ""}</td>
      </tr>`).join("");
  }).join("");
  return rows ? table(["dot1Image", "name", "dot1Price", "status", ""], rows) : empty();
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
    <label><span>${t("posPromoKind")}</span><select class="input" name="kind">${["PLAY_DRINK","BOGO","TIER_PERCENT"].map(k=>option(k,t("posPromo"+k),promo?.kind===k)).join("")}</select></label>
    <label><span>${t("posPromoItem")}</span><select class="input" name="item_id">${option("","—",!promo?.item_id)}${state.menuAdmin.items.map(i=>option(i.id,esc(i.name),promo?.item_id===i.id)).join("")}</select></label>
    ${dot1Input("value", "posPromoValue", promo?.value ?? 5000, "number", 'min="1" step="1" required')}
    <label><span>${t("posPromoTier")}</span><select class="input" name="minimum_tier">${option("","—",!promo?.minimum_tier)}${["BRONZE","SILVER","GOLD","PLATINUM"].map(k=>option(k,k,promo?.minimum_tier===k)).join("")}</select></label>
    ${dot1Input("starts_at", "posPromoStarts", localValue(promo?.starts_at || now), "datetime-local", "required")}
    ${dot1Input("ends_at", "posPromoEnds", localValue(promo?.ends_at || now + 365*86400000), "datetime-local", "required")}
    ${dot1Check("is_active", "dot1Active", promo ? promo.is_active : true)}
    <p class="dot1-tip">${t("posPromoBOGO")}: ${t("posPromoValue")} = 1. ${t("posPromoTIER_PERCENT")}: %.</p>
  </div>`, async (form) => {
    const kind = form.elements.kind.value;
    await api(promo ? `/menu/promotions/${promo.id}` : "/menu/promotions", {
      method: promo ? "PATCH" : "POST", body: {
        code: form.elements.code.value, kind,
        item_id: kind === "TIER_PERCENT" ? null : Number(form.elements.item_id.value) || null,
        value: Number(form.elements.value.value),
        minimum_tier: kind === "TIER_PERCENT" ? form.elements.minimum_tier.value || null : null,
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

function dot1IngredientForm() {
  dot1Dialog("invAdd", `<div class="form-grid">
    ${dot1Input("name", "name", "", "text", 'maxlength="100" required')}
    <label><span>${t("invUnit")}</span><select class="input" name="unit"><option value="g">g</option><option value="ml">ml</option><option value="each">${t("invUnit")} · 1</option></select></label>
    ${dot1Input("reorder_point", "invReorder", 0, "number", 'min="0" step="1" required')}
  </div>`, async (form) => {
    await api("/inventory/ingredients", { method: "POST", body: {
      name: form.elements.name.value, unit: form.elements.unit.value,
      reorder_point: Number(form.elements.reorder_point.value),
    } });
  }, "invAdd");
}

function dot1ReceiveForm(id) {
  const ingredient = state.menuInventory.ingredients.find((i) => i.id === Number(id));
  if (!ingredient) return;
  const requestId = dot1RequestId();
  dot1Dialog("invReceive", `<p>${esc(ingredient.name)} · ${esc(ingredient.unit)}</p><div class="form-grid">
    ${dot1Input("quantity", "invQuantity", "", "number", 'min="1" step="1" required')}
    ${dot1Input("reference_code", "invReference", "", "text", 'maxlength="60" required')}
    ${dot1Input("note", "invNote", "", "text", 'maxlength="255"')}
  </div>`, async (form) => {
    await api(`/inventory/ingredients/${id}/receipts`, { method: "POST", body: {
      quantity: Number(form.elements.quantity.value),
      reference_code: form.elements.reference_code.value,
      note: form.elements.note.value,
      request_id: requestId,
    } });
  }, "invReceive");
}

function dot1MovementForm(id, kind) {
  const ingredient = state.menuInventory.ingredients.find((i) => i.id === Number(id));
  if (!ingredient) return;
  const requestId = dot1RequestId();
  const title = kind === "ISSUE" ? "invIssue" : "invReturn";
  dot1Dialog(title, `<p>${esc(ingredient.name)} · ${esc(ingredient.unit)}</p><div class="form-grid">
    ${dot1Input("quantity", "invQuantity", "", "number", 'min="1" step="1" required')}
    ${dot1Input("reference_code", "invReference", "", "text", 'maxlength="60" required')}
    ${dot1Input("note", "invNote", "", "text", 'maxlength="255" required')}
  </div>`, async (form) => {
    await api(`/inventory/ingredients/${id}/movements`, { method: "POST", body: {
      kind, quantity: Number(form.elements.quantity.value),
      reference_code: form.elements.reference_code.value,
      note: form.elements.note.value, request_id: requestId,
    } });
  }, title);
}

function dot1CountForm(id) {
  const ingredient = state.menuInventory.ingredients.find((i) => i.id === Number(id));
  if (!ingredient) return;
  const requestId = dot1RequestId();
  dot1Dialog("invCount", `<p>${esc(ingredient.name)} · ${esc(ingredient.unit)}</p><div class="form-grid">
    ${dot1Input("counted_on_hand", "invCounted", ingredient.on_hand, "number", 'min="0" step="1" required')}
    ${dot1Input("reason", "invReason", "", "text", 'maxlength="255" required')}
  </div>`, async (form) => {
    await api(`/inventory/ingredients/${id}/counts`, { method: "POST", body: {
      counted_on_hand: Number(form.elements.counted_on_hand.value),
      reason: form.elements.reason.value, request_id: requestId,
    } });
  }, "invCount");
}

function dot1RequestId() {
  const bytes = new Uint8Array(16);
  crypto.getRandomValues(bytes);
  bytes[6] = (bytes[6] & 15) | 64;
  bytes[8] = (bytes[8] & 63) | 128;
  const hex = Array.from(bytes, (value) => value.toString(16).padStart(2, "0")).join("");
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

function dot1RecipeForm(id) {
  const inventory = state.menuInventory;
  const item = state.menuAdmin.items.find((i) => i.id === Number(id));
  if (!item) return;
  const parts = inventory.recipes.find((r) => r.item_id === item.id)?.parts || [];
  const quantities = new Map(parts.map((p) => [p.ingredient_id, p.quantity_per_unit]));
  const ingredientRows = inventory.ingredients.filter((i) => i.is_active).map((i) => `
    <label class="dot1-check"><input type="checkbox" data-ingredient="${i.id}" ${quantities.has(i.id) ? "checked" : ""}>
      <span>${esc(i.name)} (${esc(i.unit)})</span></label>
    <input class="input" type="number" data-quantity="${i.id}" min="1" step="1" value="${quantities.get(i.id) || 1}">`).join("");
  dot1Dialog("invRecipe", `<p>${esc(item.name)}</p>
    ${dot1Check("track_stock", "invTrack", Boolean(inventory.tracking[item.id]))}
    <div class="form-grid">${ingredientRows || t("invEmpty")}</div>
    <span class="field-error" data-error="parts"></span>`, async (form) => {
    const selected = [...form.querySelectorAll("[data-ingredient]:checked")];
    const body = {
      track_stock: form.elements.track_stock.checked,
      parts: selected.map((node) => ({
        ingredient_id: Number(node.dataset.ingredient),
        quantity_per_unit: Number(form.querySelector(`[data-quantity="${node.dataset.ingredient}"]`).value),
      })),
    };
    await api(`/inventory/items/${id}/recipe`, { method: "PUT", body });
  }, "save");
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

function dot1ImageForm(id) {
  dot1Dialog("dot1UploadImage", `<label><span>${t("dot1Image")} (JPEG, PNG, WebP · ≤ 2 MB)</span><input class="input" type="file" name="image" accept="image/jpeg,image/png,image/webp" required><span class="field-error" data-error="image"></span></label>`,
    async (form) => {
      const file = form.elements.image.files[0];
      if (!file) throw Object.assign(new Error(t("dot1UploadImage")), { field_errors: { image: t("dot1UploadImage") } });
      const data = new FormData();
      data.append("image", file);
      // Không dùng api(): request multipart, không đặt Content-Type JSON.
      const response = await fetch(`/api/menu/items/${id}/image`, {
        method: "POST", credentials: "same-origin", body: data,
        headers: { "X-CSRF-Token": state.csrf, "X-Language": state.lang },
      });
      const result = await response.json().catch(() => ({}));
      if (!response.ok) throw Object.assign(new Error(result.error?.message || t("network")), result.error || {});
    }, "dot1UploadImage");
}

async function dot1HistoryDialog(id) {
  const history = await api(`/menu/items/${id}/history`);
  const label = (value) => value === "True" ? "✓" : value === "False" ? "✗" : esc(value ?? "—");
  dot1Dialog("dot1History", history.length
    ? `<ul class="dot1-history">${history.map((h) => `<li><strong>${t("dot1Field" + h.field)}</strong>: ${label(h.old_value)} → ${label(h.new_value)}<br><small class="muted">${esc(h.employee_name)} · ${dt(h.created_at)}</small></li>`).join("")}</ul>`
    : empty("dot1NoHistory"), null);
}

// ----- Sự kiện ------------------------------------------------------------------------
document.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-menuadmin]");
  if (!button || button.disabled) return;
  const action = button.dataset.menuadmin, id = button.dataset.id;
  if (action === "close") { $("#dot1-dialog")?.close(); return; }
  if (state.page !== "menu" || !state.menuAdmin) return;
  try {
    if (action === "category" && state.menuAdmin.can_manage) dot1CategoryForm(id);
    if (action === "promotion" && state.menuAdmin.can_manage) dot1PromotionForm(id);
    if (action === "ingredient" && state.menuInventory?.can_configure) dot1IngredientForm();
    if (action === "receive" && state.menuInventory?.can_receive) dot1ReceiveForm(id);
    if (action === "issue" && state.menuInventory?.can_issue) dot1MovementForm(id, "ISSUE");
    if (action === "return" && state.menuInventory?.can_issue) dot1MovementForm(id, "RETURN");
    if (action === "count" && state.menuInventory?.can_count) dot1CountForm(id);
    if (["approve-count", "reject-count"].includes(action) && state.menuInventory?.can_approve) {
      if (!confirm(t(action === "approve-count" ? "invConfirmApprove" : "invConfirmReject"))) return;
      button.disabled = true;
      await api(`/inventory/counts/${id}/decision`, { method: "POST", body: { approve: action === "approve-count" } });
      await loadPage(true);
    }
    if (action === "recipe" && state.menuInventory?.can_configure) dot1RecipeForm(id);
    if (action === "order-filter") { state.menuOrderFilter = button.dataset.status; renderPage(); return; }
    if (action === "item" && state.menuAdmin.can_manage) dot1ItemForm(id);
    if (action === "image" && state.menuAdmin.can_manage) dot1ImageForm(id);
    if (action === "history" && state.menuAdmin.can_manage) await dot1HistoryDialog(id);
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
        dot1Dialog("dot1Cancel", `<div class="form-grid">${dot1Input("reason", "invCancelReason", "", "text", 'maxlength="255" required')}</div>`, async (form) => {
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
  }, state.actor.role === "KITCHEN" ? 10000 : 20000); // bếp cần thấy đơn mới nhanh hơn
  for (const img of document.querySelectorAll("img.dot1-thumb")) {
    img.addEventListener("error", () => { const span = document.createElement("span"); span.className = "dot1-thumb"; span.textContent = "?"; img.replaceWith(span); }, { once: true });
  }
}
