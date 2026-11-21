"use strict";
// Đợt 2 — "Voucher của tôi" trong cổng khách hàng. Khách chỉ xem và đưa mã cho nhân viên;
// việc xác nhận sử dụng luôn do nhân viên làm ở backend.

Object.assign(paths, {
  ticket: '<path d="M3 8a2 2 0 0 0 2-2h14a2 2 0 0 0 2 2v2a2 2 0 0 0 0 4v2a2 2 0 0 0-2 2H5a2 2 0 0 0-2-2v-2a2 2 0 0 0 0-4Z"/><path d="M14 6v12" stroke-dasharray="2 2"/>',
});
Object.assign(copy, {
  dot2Vouchers: ["Voucher của tôi", "My vouchers"],
  dot2VouchersSub: ["Đưa mã cho nhân viên khi dùng. Voucher không quy đổi thành tiền mặt.", "Show the code to staff when you use it. Vouchers have no cash value."],
  dot2TypeFOOD_DISCOUNT: ["Giảm giá đồ ăn", "Food discount"],
  dot2TypeFREE_DRINK: ["Tặng đồ uống", "Free drink"],
  dot2TypePLAYTIME_CREDIT: ["Cộng giờ chơi", "Playtime credit"],
  dot2TypeMEMBER_POINTS: ["Điểm thành viên", "Member points"],
  dot2StateACTIVE: ["Còn hạn", "Active"],
  dot2StateEXPIRED: ["Hết hạn", "Expired"],
  dot2StateUSED: ["Đã dùng", "Used"],
  dot2StateREVOKED: ["Đã khóa", "Locked"],
  dot2Expires: ["Hạn dùng", "Expires"],
  dot2UsedAt: ["Đã dùng lúc", "Used at"],
  dot2MinOrder: ["Đơn tối thiểu", "Minimum order"],
  dot2AllStores: ["Mọi cơ sở", "All stores"],
  dot2OnlyAt: ["Chỉ tại", "Only at"],
  dot2Points: ["điểm", "points"],
  dot2Empty: ["Bạn chưa có voucher nào", "You have no vouchers yet"],
  dot2EmptySub: ["Voucher từ chương trình ưu đãi và trò chơi sẽ xuất hiện ở đây.", "Vouchers from promotions and games will appear here."],
  dot2ShowStaff: ["Đưa mã này cho nhân viên", "Show this code to staff"],
  dot2HowFOOD_DISCOUNT: ["Trừ vào tiền món khi nhân viên thu tại quầy", "Deducted from your food order at the counter"],
  dot2HowFREE_DRINK: ["Áp vào một yêu cầu gọi món có đồ uống", "Applied to a food order with a drink"],
  dot2HowPLAYTIME_CREDIT: ["Cộng vào số dư khuyến mãi, dùng trả giờ chơi", "Added to your promotional balance for playtime"],
  dot2HowMEMBER_POINTS: ["Cộng vào điểm thành viên", "Added to your member points"],
});

const dot2Value = (v) => v.reward_type === "MEMBER_POINTS" ? `+${v.value} ${t("dot2Points")}` : money(v.value);
const dot2Code = (code) => code.length > 6 ? `${code.slice(0, 2)}-${code.slice(2, 6)}-${code.slice(6)}` : code;

// Được drawCustomerPortal() gọi khi tab = "vouchers".
function customerVoucherPage() {
  const ui = portalUI;
  if (!ui.vouchersLoading && (!ui.vouchers || Date.now() - (ui.vouchersAt || 0) > 30000)) loadCustomerVouchers();
  return `<div id="dot2-root">${dot2Body()}</div>`;
}

async function loadCustomerVouchers() {
  const ui = portalUI;
  ui.vouchersLoading = true;
  try {
    const data = await api("/portal/vouchers");
    if (ui !== portalUI) return;
    ui.vouchers = data;
    ui.vouchersError = null;
  } catch (error) {
    if (ui !== portalUI) return;
    ui.vouchersError = error.message;
  } finally {
    ui.vouchersAt = Date.now();
    ui.vouchersLoading = false;
    if (ui === portalUI && ui.tab === "vouchers") {
      const root = $("#dot2-root");
      if (root) root.innerHTML = dot2Body();
    }
  }
}

function dot2Body() {
  const ui = portalUI, d = ui.vouchers;
  if (!d) {
    return ui.vouchersError
      ? `<section class="pc-card"><div class="pc-empty">${icon("alert")}<h3>${t("unavailable")}</h3><p>${esc(ui.vouchersError)}</p></div></section>`
      : `<section class="pc-card"><div class="pc-loading" role="status"><span class="spinner"></span><p>${t("loading")}</p></div></section>`;
  }
  if (!d.items.length) return `<section class="pc-card">${pcEmpty("dot2Empty", "dot2EmptySub", "ticket")}</section>`;
  return `<div class="dot2-grid">${d.items.map(dot2Card).join("")}</div>`;
}

function dot2Card(v) {
  const active = v.state === "ACTIVE";
  const scope = v.store_name ? `${t("dot2OnlyAt")} ${esc(v.store_name)}` : t("dot2AllStores");
  return `<article class="dot2-ticket ${v.state}">
      <div class="dot2-stub"><span class="dot2-value">${dot2Value(v)}</span><small>${t("dot2Type" + v.reward_type)}</small></div>
      <div class="dot2-body">
        <header><h3>${esc(v.name)}</h3><span class="dot2-state ${v.state}">${t("dot2State" + v.state)}</span></header>
        <p class="muted">${t("dot2How" + v.reward_type)}</p>
        <ul class="dot2-terms">
          <li>${icon("store")} ${scope}</li>
          ${v.min_order_amount ? `<li>${icon("cart")} ${t("dot2MinOrder")} ${money(v.min_order_amount)}</li>` : ""}
          <li>${icon("clock")} ${v.state === "USED" && v.used_at ? `${t("dot2UsedAt")} ${dt(v.used_at)}` : `${t("dot2Expires")} ${dt(v.expires_at)}`}</li>
        </ul>
        ${active ? `<div class="dot2-code"><small>${t("dot2ShowStaff")}</small><strong>${esc(dot2Code(v.code))}</strong></div>` : ""}
      </div>
    </article>`;
}
