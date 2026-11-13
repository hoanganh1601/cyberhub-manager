"use strict";
// Thông báo trong cổng khách hàng: chuông + badge số chưa đọc ở header, số chưa đọc ở tiêu đề tab,
// và toast gần realtime khi đơn món đổi trạng thái.
//
// Cách hoạt động: cứ 10 giây (chỉ khi tab trình duyệt đang mở) gọi lại /api/portal/notifications,
// so với các thông báo đã thấy; thông báo mới chưa đọc thuộc loại đơn món thì hiện toast.
// Mọi thông báo vẫn do máy chủ ghi trong cùng transaction với đơn; trình duyệt chỉ đọc và hiển thị.

Object.assign(copy, {
  pcMoreNotices: ["thông báo mới khác", "more new notifications"],
});

const PC_NOTIFY_INTERVAL = 10000;
// Loại thông báo được báo bằng toast. Dùng lại tiêu đề của danh sách Thông báo.
// MENU_ORDER_NEW và MENU_ITEM_UNAVAILABLE không báo lại: chính khách vừa thao tác và đã thấy kết quả.
const PC_TOAST_KINDS = {
  MENU_ORDER_PREPARING: "pcOrderPreparing",
  MENU_ORDER_SERVED: "pcOrderServed",
  MENU_ORDER_PAID: "pcOrderPaid",
  MENU_ORDER_REFUNDED: "pcOrderRefunded",
  MENU_ORDER_CANCELLED: "pcOrderCancelled",
  MENU_ORDER_EXPIRING: "pcOrderExpiring",
};

const pcUnreadCount = () => portalUI?.notices?.unread || 0;
const pcBadgeText = (n) => (n > 9 ? "9+" : String(n));
const pcUnreadPrefix = () => (pcUnreadCount() ? `(${pcUnreadCount()}) ` : "");

// Nút chuông ở header; bấm để mở tab Thông báo.
function pcBell() {
  const n = pcUnreadCount();
  const label = `${t("pcNotifications")}${n ? `: ${n} ${t("pcUnread")}` : ""}`;
  return `<button class="btn pc-icon-button pc-bell" id="pc-bell" data-portal="tab" data-tab="notifications" aria-label="${label}" title="${label}">${icon("bell")}${n ? `<b class="pc-count">${pcBadgeText(n)}</b>` : ""}</button>`;
}

// Cập nhật badge và tiêu đề tab tại chỗ, không vẽ lại trang (không làm mất nội dung khách đang nhập).
function pcSyncNoticeBadge() {
  const n = pcUnreadCount();
  const bell = $("#pc-bell");
  if (bell) {
    bell.querySelector(".pc-count")?.remove();
    if (n) bell.insertAdjacentHTML("beforeend", `<b class="pc-count">${pcBadgeText(n)}</b>`);
  }
  const tab = $('.pc-nav-button[data-tab="notifications"]');
  if (tab) {
    tab.querySelector(".pc-count")?.remove();
    if (n) tab.insertAdjacentHTML("beforeend", `<b class="pc-count">${n}</b>`);
  }
  document.title = pcUnreadPrefix() + document.title.replace(/^\(\d+\)\s*/, "");
}

let pcNotifyBusy = false;

async function pcPollNotices() {
  const ui = portalUI, customer = state.customer;
  // Không thăm dò khi chưa tải xong cổng, tab bị ẩn, hoặc đang quay/đặt món/đổi xu để khỏi chen ngang.
  if (!ui || !customer || !ui.notices || document.hidden || pcNotifyBusy || ui.gameBusy || ui.menuBusy) return;
  ui.noticeSeen ??= new Set(ui.notices.items.map((item) => item.key));
  pcNotifyBusy = true;
  try {
    const data = await api("/portal/notifications");
    if (ui !== portalUI || state.customer !== customer) return;
    const fresh = data.items.filter((item) => !item.read && !ui.noticeSeen.has(item.key));
    for (const item of data.items) ui.noticeSeen.add(item.key);
    ui.notices = data;
    pcSyncNoticeBadge();
    const toasts = fresh.filter((item) => PC_TOAST_KINDS[item.kind]);
    for (const item of toasts.slice(0, 3)) toast(`${t(PC_TOAST_KINDS[item.kind])} · ${item.code}`, item.severity === "warning");
    if (toasts.length > 3) toast(`+${toasts.length - 3} ${t("pcMoreNotices")}`);
    // Đang xem Thông báo hoặc Tổng quan thì vẽ lại để danh sách hiện sự kiện mới (trừ khi khách đang nhập liệu).
    if (fresh.length && ["notifications", "home"].includes(ui.tab)
        && !$(".customer-workspace input:focus,.customer-workspace select:focus")) drawCustomerPortal();
  } catch {
    // Lỗi mạng tạm thời: lần thăm dò sau sẽ thử lại, không làm phiền khách.
  } finally {
    pcNotifyBusy = false;
  }
}

setInterval(pcPollNotices, PC_NOTIFY_INTERVAL);
document.addEventListener("visibilitychange", () => { if (!document.hidden) pcPollNotices(); });
