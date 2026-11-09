"use strict";

const $ = (selector, root = document) => root.querySelector(selector);
const copy = {
  dashboard: ["Tổng quan", "Overview"],
  customers: ["Khách hàng", "Customers"],
  machines: ["Quản lý máy", "Machines"],
  invoices: ["Hóa đơn", "Invoices"],
  revenue: ["Doanh thu", "Revenue"],
  login: ["Đăng nhập", "Sign in"],
  logout: ["Đăng xuất", "Sign out"],
  portal: ["CỔNG VẬN HÀNH NHÂN VIÊN", "STAFF OPERATIONS PORTAL"],
  loginSub: [
    "Đăng nhập để tiếp tục quản lý cửa hàng",
    "Sign in to manage your cybercafe",
  ],
  username: ["Tên đăng nhập", "Username"],
  password: ["Mật khẩu", "Password"],
  showPassword: ["Hiện/ẩn mật khẩu", "Show/hide password"],
  ready: ["Hệ thống sẵn sàng", "System ready"],
  demo: ["Chế độ demo", "Demo mode"],
  demoHint: [
    "Dữ liệu demo riêng cho từng phiên đăng nhập, tự mất khi khởi động lại server. Không nhập dữ liệu thật.",
    "Each demo login has its own dataset, cleared on server restart. Do not enter real information.",
  ],
  demoAccounts: [
    "Quản lý: quanly01 · Nhân viên: nhanvien01",
    "Manager: quanly01 · Staff: nhanvien01",
  ],
  demoPassword: ["Mật khẩu demo: demo123", "Demo password: demo123"],
  intro: [
    "Hệ thống quản lý phòng máy chuyên nghiệp",
    "Professional cybercafe management, in one place.",
  ],
  f1: ["Quản lý phiên theo thời gian thực", "Real-time session management"],
  f2: ["Nạp tiền & thanh toán chính xác", "Accurate top-ups & checkout"],
  f3: ["Theo dõi toàn bộ máy trạm", "All your workstations in one place"],
  f4: ["Báo cáo doanh thu rõ ràng", "Clear revenue reporting"],
  enterHint: ["Nhấn Enter để đăng nhập", "Press Enter to sign in"],
  manager: ["QUẢN LÝ", "MANAGER"],
  staff: ["NHÂN VIÊN", "STAFF"],
  admin: ["QUẢN TRỊ", "ADMIN"],
  refresh: ["Làm mới", "Refresh"],
  loading: ["Đang tải dữ liệu…", "Loading data…"],
  processing: ["Đang xử lý…", "Processing…"],
  retry: ["Thử lại", "Try again"],
  unavailable: ["Không thể tải dữ liệu", "Unable to load data"],
  network: [
    "Không thể kết nối máy chủ. Vui lòng thử lại.",
    "Unable to connect to the server. Please try again.",
  ],
  all: ["Tất cả", "All"],
  available: ["Trống", "Available"],
  inUse: ["Đang dùng", "In use"],
  maintenance: ["Bảo trì", "Maintenance"],
  totalMachines: ["Tổng số máy", "Total machines"],
  activeCustomers: ["Khách đang chơi", "Active customers"],
  dashboardSub: [
    "Giám sát máy trạm và phiên sử dụng theo thời gian thực",
    "Monitor workstations and active sessions in real time",
  ],
  customersSub: [
    "Quản lý hồ sơ, tài khoản và số dư khách hàng",
    "Manage customer profiles, accounts and balances",
  ],
  machinesSub: [
    "Cấu hình máy, đơn giá và trạng thái vận hành",
    "Manage workstations, hourly rates and maintenance",
  ],
  invoicesSub: [
    "Tra cứu hóa đơn và lịch sử thanh toán",
    "Browse invoices and payment history",
  ],
  revenueSub: [
    "Theo dõi doanh thu từ hóa đơn đã thanh toán",
    "Track revenue from paid invoices",
  ],
  search: ["Tìm kiếm…", "Search…"],
  machineSearch: ["Tìm mã hoặc tên máy…", "Search machine code or name…"],
  customerSearch: [
    "Tìm mã, tên, số điện thoại, tài khoản…",
    "Search code, name, phone or username…",
  ],
  invoiceSearch: [
    "Tìm mã hóa đơn hoặc khách hàng…",
    "Search invoice code or customer…",
  ],
  noResults: ["Không tìm thấy kết quả", "No matching results"],
  clearFilters: ["Xóa bộ lọc", "Clear filters"],
  selectCustomer: [
    "Chọn một khách hàng để xem chi tiết",
    "Select a customer to view details",
  ],
  selectInvoice: [
    "Chọn một hóa đơn để xem chi tiết",
    "Select an invoice to view details",
  ],
  customer: ["Khách hàng", "Customer"],
  elapsed: ["Thời gian", "Elapsed"],
  estimated: ["Tạm tính", "Estimated cost"],
  projected: ["Số dư dự kiến", "Projected balance"],
  hourly: ["Giá theo giờ", "Hourly rate"],
  perHour: ["/giờ", "/hour"],
  hour: ["giờ", "h"],
  minute: ["phút", "min"],
  open: ["Mở phiên", "Open session"],
  checkout: ["Thanh toán", "Checkout"],
  endMaintenance: ["Kết thúc bảo trì", "End maintenance"],
  startMaintenance: ["Bật bảo trì", "Start maintenance"],
  maintenanceNote: [
    "Tạm ngừng hoạt động để bảo trì",
    "Temporarily unavailable for maintenance",
  ],
  idleNote: ["Sẵn sàng phục vụ", "Ready for your next customer"],
  newCustomer: ["Tạo khách hàng", "Create customer"],
  newMachine: ["Thêm máy", "Add machine"],
  edit: ["Chỉnh sửa", "Edit"],
  save: ["Lưu thay đổi", "Save changes"],
  topup: ["Nạp tiền", "Top up"],
  lock: ["Khóa", "Lock"],
  unlock: ["Mở khóa", "Unlock"],
  archive: ["Ngừng sử dụng", "Archive / delete"],
  active: ["Hoạt động", "Active"],
  inactive: ["Ngừng hoạt động", "Inactive"],
  locked: ["Đã khóa", "Locked"],
  code: ["Mã", "Code"],
  fullName: ["Họ và tên", "Full name"],
  phone: ["Số điện thoại", "Phone number"],
  balance: ["Số dư hiện tại", "Current balance"],
  status: ["Trạng thái", "Status"],
  account: ["Tài khoản", "Account"],
  accountStatus: ["Trạng thái tài khoản", "Account status"],
  customerStatus: ["Trạng thái khách hàng", "Customer status"],
  recentHistory: ["Giao dịch gần đây", "Recent transactions"],
  noHistory: ["Chưa có giao dịch", "No transactions yet"],
  TOP_UP: ["Nạp tiền", "Top-up"],
  USAGE_PAYMENT: ["Phí sử dụng", "Usage payment"],
  DEBT_SETTLEMENT: ["Thanh toán bổ sung", "Settlement"],
  PROMOTION: ["Khuyến mãi", "Promotion"],
  CASH: ["Tiền mặt", "Cash"],
  TRANSFER: ["Chuyển khoản", "Bank transfer"],
  ACCOUNT_BALANCE: ["Số dư tài khoản", "Account balance"],
  accountBalance: ["Số dư tài khoản", "Account balance"],
  cancel: ["Hủy", "Cancel"],
  close: ["Đóng", "Close"],
  confirm: ["Xác nhận", "Confirm"],
  actions: ["Thao tác", "Actions"],
  updated: ["Cập nhật", "Updated"],
  machineName: ["Tên máy", "Machine name"],
  machineCode: ["Mã máy", "Machine code"],
  createNote: [
    "Khách hàng và tài khoản được tạo cùng lúc. Số dư ban đầu: 0 VND.",
    "Customer and account are created together. Opening balance: 0 VND.",
  ],
  autoCode: [
    "Mã được hệ thống tạo sau khi lưu.",
    "Codes are assigned after saving.",
  ],
  passwordHint: [
    "Tối thiểu 6 ký tự, tối đa 72 byte UTF-8.",
    "At least 6 characters; at most 72 UTF-8 bytes.",
  ],
  confirmPassword: ["Xác nhận mật khẩu", "Confirm password"],
  mismatch: ["Mật khẩu xác nhận không khớp.", "Passwords do not match."],
  amount: ["Số tiền nạp", "Top-up amount"],
  amountHint: [
    "Số nguyên từ 1 đến 100.000.000 VND.",
    "Whole amount from 1 to 100,000,000 VND.",
  ],
  paymentMethod: ["Phương thức thanh toán", "Payment method"],
  expectedBalance: ["Số dư dự kiến sau nạp", "Expected balance after top-up"],
  transferNote: [
    "Chỉ xác nhận sau khi kiểm tra đã nhận đủ tiền. Chuyển khoản được nhân viên xác nhận thủ công.",
    "Confirm only after checking that the full payment was received. Staff verify transfers manually.",
  ],
  receivedConfirm: [
    "Tôi đã xác nhận nhận đủ tiền",
    "I have confirmed receipt of the full payment",
  ],
  success: ["Thao tác thành công", "Operation completed successfully"],
  statusLockNote: [
    "Khách hàng sẽ ngừng hoạt động, tài khoản bị khóa. Giữ nguyên số dư, lịch sử và các phiên đang chạy.",
    "The customer becomes inactive and the account is locked. Balance, history and running sessions remain unchanged.",
  ],
  statusUnlockNote: [
    "Khách hàng và tài khoản sẽ hoạt động trở lại. Số dư và lịch sử được giữ nguyên.",
    "Customer and account will become active again. Balance and history remain unchanged.",
  ],
  archiveNote: [
    "Máy có lịch sử sẽ được lưu trữ; máy chưa có lịch sử sẽ bị xóa. Không áp dụng cho máy đang sử dụng.",
    "Machines with history are archived; unused machines are deleted. In-use machines cannot be archived.",
  ],
  maintenanceConfirm: [
    "Xác nhận thay đổi trạng thái bảo trì máy này?",
    "Change maintenance status for this workstation?",
  ],
  chooseCustomer: ["Chọn khách hàng…", "Choose a customer…"],
  preview: ["Kiểm tra điều kiện mở phiên", "Check session eligibility"],
  openAllowed: [
    "Khách hàng đủ điều kiện mở phiên",
    "The customer is eligible to start a session",
  ],
  openBlocked: [
    "Chưa đủ điều kiện mở phiên. Kiểm tra số dư và trạng thái tài khoản.",
    "The customer is not eligible yet. Check balance and account status.",
  ],
  minimumBalance: ["Số dư tối thiểu", "Minimum balance"],
  estimatedTime: ["Thời gian ước tính", "Estimated time"],
  rateSnapshot: [
    "Đơn giá tại thời điểm mở phiên được giữ cho đến khi thanh toán.",
    "The hourly rate at session start is kept until checkout.",
  ],
  checkoutTitle: ["Xác nhận thanh toán", "Confirm checkout"],
  checkoutSub: [
    "Kiểm tra chi phí trước khi kết thúc phiên sử dụng",
    "Review the charges before ending the session",
  ],
  usageCost: ["Chi phí sử dụng", "Usage cost"],
  settlement: ["Cần thanh toán thêm", "Outstanding payment"],
  deducted: ["Thanh toán từ số dư", "Paid from balance"],
  balanceAfter: ["Số dư sau khi kết thúc", "Balance after checkout"],
  cashReceived: ["Tiền khách đưa", "Cash received"],
  change: ["Tiền thừa trả khách", "Change to return"],
  settlementNote: [
    "Chỉ số tiền còn thiếu được dùng để thanh toán. Trả lại tiền thừa cho khách; muốn giữ phần dư trong ví, hãy nạp tiền riêng.",
    "Only the outstanding amount pays for this session. Return any change; keeping extra money in the wallet requires a separate top-up.",
  ],
  noSettlement: [
    "Số dư đủ thanh toán. Phiên kết thúc và máy chuyển về Trống sau khi xác nhận.",
    "The account has sufficient funds. Confirming ends the session and makes the machine available.",
  ],
  receipt: ["Thanh toán thành công", "Payment completed"],
  receiptSub: [
    "Phiên đã kết thúc và hóa đơn đã được tạo",
    "The session has ended and the invoice has been created",
  ],
  invoiceCode: ["Mã hóa đơn", "Invoice code"],
  sessionCode: ["Mã phiên", "Session code"],
  copyCode: ["Sao chép mã", "Copy code"],
  copied: ["Đã sao chép mã hóa đơn", "Invoice code copied"],
  print: ["In biên lai", "Print receipt"],
  from: ["Từ ngày", "From"],
  to: ["Đến ngày", "To"],
  apply: ["Áp dụng", "Apply"],
  PAID: ["Đã thanh toán", "Paid"],
  VOID: ["Đã hủy", "Void"],
  invoiceDetail: ["Chi tiết hóa đơn", "Invoice details"],
  employee: ["Thu ngân", "Cashier"],
  createdAt: ["Ngày tạo", "Created at"],
  startAt: ["Bắt đầu", "Started at"],
  endAt: ["Kết thúc", "Ended at"],
  duration: ["Thời lượng tính phí", "Billed duration"],
  total: ["Tổng cộng", "Total"],
  paidCount: ["Hóa đơn đã thanh toán", "Paid invoices"],
  totalRevenue: ["Tổng doanh thu", "Total revenue"],
  dailyAverage: ["Doanh thu TB/ngày", "Average per day"],
  bestDay: ["Ngày cao nhất", "Best day"],
  revenueDays: ["Ngày có doanh thu", "Days with revenue"],
  revenueDaily: ["Doanh thu theo ngày", "Daily revenue"],
  summary: ["Tổng kết báo cáo", "Report summary"],
  reportNote: [
    "Chỉ cộng phí sử dụng trên hóa đơn PAID. Tiền nạp ví và tiền bù không được cộng lần nữa.",
    "Only usage costs on PAID invoices count as revenue. Top-ups and settlement are not counted again.",
  ],
  reportScope: ["Phạm vi", "Scope"],
  currentStore: ["Cửa hàng hiện tại", "Current store"],
  localTimezone: [
    "Ngày báo cáo: Asia/Ho_Chi_Minh (UTC+7)",
    "Report dates: Asia/Ho_Chi_Minh (UTC+7)",
  ],
  showing: ["Đang hiển thị", "Showing"],
  previous: ["Trang trước", "Previous page"],
  next: ["Trang sau", "Next page"],
  refreshHint: ["Tự làm mới mỗi 15 giây", "Refreshes every 15 seconds"],
  required: [
    "Vui lòng nhập đầy đủ thông tin.",
    "Please complete all required fields.",
  ],
  expired: [
    "Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.",
    "Your session has expired. Please sign in again.",
  ],
  readOnly: ["Chỉ đọc", "Read-only"],
  bootError: [
    "Không thể khởi động ứng dụng",
    "Unable to start the application",
  ],
  passwordClear: [
    "Mật khẩu không được hiển thị hoặc lưu ở trình duyệt.",
    "Passwords are never displayed or saved in the browser.",
  ],
  language: ["Ngôn ngữ", "Language"],
  archiveResult: ["Đã ngừng sử dụng máy", "Workstation removed from operation"],
};
const paths = {
  grid: '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
  users:
    '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2m20 0v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/><circle cx="9" cy="7" r="4"/>',
  monitor:
    '<rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8m-4-4v4"/>',
  invoice: '<path d="M6 3h9l4 4v14H6zM14 3v5h5M9 12h7m-7 4h7"/>',
  chart: '<path d="M3 3v18h18M7 16v-4m5 4V8m5 8V5"/>',
  arrow: '<path d="M5 12h14m-6-6 6 6-6 6"/>',
  logout: '<path d="M9 4H4v16h5m6-13 5 5-5 5m-7-5h12"/>',
  refresh:
    '<path d="M20 7v5h-5M4 17v-5h5m-3-5a7 7 0 0 1 12-1l2 2M4 16l2 2a7 7 0 0 0 12-1"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  check: '<path d="m5 12 4 4L19 6"/>',
  wallet:
    '<path d="M20 8V5H5a2 2 0 0 0 0 4h16v11H5a2 2 0 0 1-2-2V7m18 6h-5v4h5"/>',
  edit: '<path d="m16 3 5 5L9 20H4v-5ZM14 5l5 5"/>',
  lock: '<rect x="5" y="10" width="14" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3m-4 5v2"/>',
  wrench: '<path d="m14 6 4 4 3-3a6 6 0 0 1-8 8l-6 6-4-4 6-6a6 6 0 0 1 8-8z"/>',
  search: '<circle cx="10" cy="10" r="6"/><path d="m15 15 6 6"/>',
  eye: '<path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/>',
  alert: '<path d="m12 3 10 18H2ZM12 9v5m0 3h.01"/>',
  store: '<path d="M3 9h18l-2-6H5zm1 0v12h16V9M9 21v-8h6v8"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  shield: '<path d="m12 2 8 4v6c0 5-8 10-8 10S4 17 4 12V6Zm-4 9 3 3 5-5"/>',
  copy: '<rect x="8" y="8" width="13" height="13" rx="2"/><path d="M16 8V3H3v13h5"/>',
};
const icon = (name) =>
  `<svg class="icon" viewBox="0 0 24 24" aria-hidden="true">${paths[name] || paths.grid}</svg>`;
const esc = (value) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (char) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        char
      ],
  );
function storedLanguage() {
  try {
    return localStorage.getItem("cyberhub-language") === "en" ? "en" : "vi";
  } catch {
    return "vi";
  }
}
const state = {
  lang: storedLanguage(),
  actor: null,
  csrf: "",
  mode: "demo",
  page: "dashboard",
  filter: "all",
  keyword: "",
  selected: null,
  detail: null,
  tablePage: 1,
  items: [],
  machines: [],
  today: "",
  dates: {},
  seq: 0,
  busy: false,
};
let modalContext = null;
let refreshTimer;
const t = (key) => (copy[key] || [key, key])[state.lang === "en" ? 1 : 0];
const money = (value) =>
  `${new Intl.NumberFormat(state.lang === "en" ? "en-US" : "vi-VN").format(Number(value) || 0)} VND`;
const dt = (value) =>
  value
    ? new Intl.DateTimeFormat(state.lang === "en" ? "en-GB" : "vi-VN", {
        timeZone: "Asia/Ho_Chi_Minh",
        dateStyle: "short",
        timeStyle: "short",
      }).format(new Date(value))
    : "—";
const duration = (seconds) => {
  const min = Math.floor(Math.max(0, seconds || 0) / 60);
  return min >= 60
    ? `${Math.floor(min / 60)} ${t("hour")} ${min % 60} ${t("minute")}`
    : `${min} ${t("minute")}`;
};
const initials = (name) =>
  (name || "CH")
    .split(" ")
    .slice(-2)
    .map((part) => part[0])
    .join("")
    .toUpperCase();
const isManager = () => ["MANAGER", "ADMIN"].includes(state.actor?.role);
const statusKey = (value) =>
  ({
    AVAILABLE: "available",
    IN_USE: "inUse",
    MAINTENANCE: "maintenance",
    ACTIVE: "active",
    INACTIVE: "inactive",
    LOCKED: "locked",
  })[value] || value;
function badge(value) {
  const color = ["AVAILABLE", "ACTIVE", "PAID"].includes(value)
    ? "green"
    : ["IN_USE", "LOCKED", "VOID"].includes(value)
      ? "red"
      : value === "MAINTENANCE"
        ? "amber"
        : "";
  return `<span class="badge ${color}"><i class="dot"></i>${esc(t(statusKey(value)))}</span>`;
}
function langControl() {
  return `<div class="segment" role="group" aria-label="${t("language")}">${["vi", "en"].map((lang) => `<button type="button" data-action="language" data-lang="${lang}" class="${state.lang === lang ? "active" : ""}" aria-pressed="${state.lang === lang}">${lang.toUpperCase()}</button>`).join("")}</div>`;
}
function toast(message, error = false) {
  const node = document.createElement("div");
  node.className = `toast${error ? " error" : ""}`;
  node.innerHTML = `${icon(error ? "alert" : "check")}<span>${esc(message)}</span><button aria-label="${t("close")}">×</button>`;
  $("button", node).onclick = () => node.remove();
  $("#notifications").append(node);
  setTimeout(() => node.remove(), 6500);
}
async function api(path, options = {}) {
  const { method = "GET", body } = options;
  let response;
  try {
    response = await fetch(`/api${path}`, {
      method,
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-Token": state.csrf,
        "X-Language": state.lang,
      },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: AbortSignal.timeout(25000),
    });
  } catch {
    throw new Error(t("network"));
  }
  let data;
  try {
    data = await response.json();
  } catch {
    throw new Error(t("network"));
  }
  if (!response.ok) {
    const error = new Error(data.error?.message || t("network"));
    Object.assign(error, data.error || {});
    if (error.code === "AUTH_REQUIRED") {
      state.actor = null;
      closeModal(true);
      renderLogin();
    }
    throw error;
  }
  if (data.csrf_token) state.csrf = data.csrf_token;
  return data;
}
function setLanguage(lang) {
  state.lang = lang === "en" ? "en" : "vi";
  document.documentElement.lang = state.lang;
  try {
    localStorage.setItem("cyberhub-language", state.lang);
  } catch {
    /* Storage is optional. */
  }
  if(state.customer) { renderPortal(); return; }
  if (state.actor) {
    renderShell();
    loadPage();
  } else renderLogin();
}
function renderLogin() {
  state.customer = null;
  clearInterval(refreshTimer);
  document.title = `CyberHub Manager — ${t("login")}`;
  $("#app").innerHTML =
    `<main class="login"><section class="brand-panel"><img class="logo" src="/assets/cyberhub_logo_dark.png" alt="CyberHub Manager"><div class="eyebrow">${esc(t("intro"))}</div><h1>CyberHub <span class="cyan">Manager</span></h1><p>${esc(t("intro"))}</p><div class="features">${["f1", "f2", "f3", "f4"].map((key, i) => `<div class="row">${icon(["monitor", "wallet", "grid", "chart"][i])}${t(key)}</div>`).join("")}</div><div class="brand-foot">© ${new Date().getFullYear()} CyberHub Manager</div></section><section class="login-panel"><div class="login-top"><span class="eyebrow">${t("portal")}</span>${langControl()}</div><form id="login-form" class="login-form"><div><h1>${t("login")}</h1><p class="subtitle">${t("loginSub")}</p></div><label><span>${t("username").toUpperCase()}</span><input class="input" name="username" placeholder="${t("username")}" autocomplete="username" required maxlength="100"></label><label><span>${t("password").toUpperCase()}</span><div class="password-wrap"><input class="input" id="login-password" name="password" type="password" placeholder="${t("password")}" autocomplete="current-password" required maxlength="200"><button type="button" data-action="show-password" aria-label="${t("showPassword")}">${icon("eye")}</button></div></label><div id="login-error" class="error-box" role="alert"></div><button class="btn primary full" type="submit">${t("login")}${icon("arrow")}</button><p class="login-hint">${t("enterHint")}</p>${state.mode === "demo" ? `<div class="demo-note"><strong>${t("demo")}</strong><br>${t("demoAccounts")}<br>${t("demoPassword")}<br><small>${t("demoHint")}</small></div>` : ""}</form><footer class="login-footer"><span class="green">● ${t("ready")}</span><span>${state.mode === "demo" ? t("demo") : "MySQL · HTTPS"}</span></footer></section></main>`;
  installP1Login();
  $("#login-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const button = $("button[type=submit]", form);
    const values = Object.fromEntries(new FormData(form));
    button.disabled = true;
    button.innerHTML = `<span class="spinner"></span>${t("processing")}`;
    $("#login-error").textContent = "";
    try {
      const result = await api("/login", { method: "POST", body: values });
      state.actor = result.actor;
      state.today = result.today;
      state.mode = result.mode;
      form.reset();
      state.page = "dashboard";
      state.selected = null;
      renderShell();
      await loadPage();
    } catch (error) {
      $("#login-error").textContent = error.message;
      $("[name=password]", form).value = "";
      button.disabled = false;
      button.innerHTML = `${t("login")}${icon("arrow")}`;
    }
  });
}
function renderShell() {
  document.title = `CyberHub Manager — ${t(state.page)}`;
  const links = [
    ["dashboard", "grid"],
    ["customers", "users"],
    ...(isManager() ? [["machines", "monitor"]] : []),
    ["invoices", "invoice"],
    ["menu", "utensils"],
    ["vouchers", "ticket"],
    ...(isManager() ? [["revenue", "chart"]] : []),
    ...(isManager() ? [["employees","users"],["promotions","wallet"]] : []),
    ...(state.actor.role === "ADMIN" ? [["stores","store"]] : []),
  ];
  $("#app").innerHTML =
    `<div class="shell"><aside class="sidebar"><div class="brand-link"><img src="/assets/cyberhub_logo_dark.png" alt="CyberHub"><div class="brand-word">CyberHub <span class="cyan">•</span><small>MANAGER · WEB</small></div></div><nav class="nav" aria-label="CyberHub">${links.map(([key, symbol]) => `<button data-action="navigate" data-page="${key}" class="${state.page === key ? "active" : ""}" title="${t(key)}" ${state.page === key ? 'aria-current="page"' : ""}>${icon(symbol)}<span>${t(key)}</span></button>`).join("")}</nav><div class="sidebar-foot"><span class="mode"><i class="dot"></i>${t("ready")}</span><div class="row between"><span>${state.mode === "demo" ? t("demo") : "MySQL"}</span><span>WEB · 1.0</span></div></div></aside><header class="topbar"><div class="store-chip">${icon("store")}${esc(state.actor.store_name)}</div><span class="top-time">${dt(new Date().toISOString())}</span><span class="spacer"></span>${langControl()}<div class="profile"><div class="name">${esc(state.actor.full_name)}<small>${t(state.actor.role === "STAFF" ? "staff" : state.actor.role === "ADMIN" ? "admin" : "manager")}</small></div><div class="avatar">${esc(initials(state.actor.full_name))}</div></div><button class="btn ghost small" data-action="logout" title="${t("logout")}" aria-label="${t("logout")}">${icon("logout")}</button></header><main id="workspace" class="main"></main></div>`;
  clearInterval(refreshTimer);
  installP1Shell();
  refreshTimer = setInterval(() => {
    if (
      state.page === "dashboard" &&
      !$("#modal").open &&
      !document.hidden &&
      !state.busy
    )
      loadPage(true);
  }, 15000);
}
function loading() {
  return `<div class="loading"><span class="spinner"></span>${t("loading")}</div>`;
}
function empty(message = "noResults") {
  return `<div class="empty">${icon("search")}<strong>${t(message)}</strong></div>`;
}
function pageHead(extra = "") {
  return `<header class="page-head"><div><h1>${t(state.page === "dashboard" ? "dashboard" : state.page)}</h1><p>${t(`${state.page}Sub`)}</p></div><div class="actions"><button class="btn small" data-action="refresh">${icon("refresh")}${t("refresh")}</button>${extra}</div></header>`;
}
function pageFooter() {
  return `<footer class="page-footer"><span><span class="cyan">●</span> ${esc(state.actor.store_name)} · ${state.page === "dashboard" ? t("refreshHint") : t("localTimezone")}</span><span>CyberHub Manager · Web</span></footer>`;
}
function metric(label, value, color = "", symbol = "monitor", hint = "") {
  return `<div class="metric"><div class="metric-label">${t(label)}</div>${icon(symbol)}<div class="metric-value ${color}">${esc(value)}</div><small>${esc(hint)}</small></div>`;
}
async function loadPage(silent = false) {
  if (state.page === "revenue" && !isManager()) state.page = "dashboard";
  const seq = ++state.seq;
  const page = state.page;
  if (!state.actor) return;
  if (!silent) $("#workspace").innerHTML = pageHead() + loading();
  try {
    let data;
    if (page === "menu") {
      // Đợt 1: menu + hàng đợi gọi món của cơ sở đang thao tác.
      if (await loadMenuAdmin(seq)) renderPage();
      return;
    }
    if (page === "vouchers") {
      // Đợt 2: tra cứu/xác nhận voucher, danh mục phần thưởng, nhật ký.
      if (await loadVoucherAdmin(seq)) renderPage();
      return;
    }
    if (["employees","promotions","stores"].includes(page)) {
      const [items,stores] = await Promise.all([api(`/${page}`),api('/stores')]);
      if(seq!==state.seq) return;
      state.items=items; state.stores=stores; renderPage(); return;
    }
    if (page === "dashboard" || page === "machines")
      data = await api("/machines");
    else if (page === "customers") data = await api("/customers");
    else {
      const params = new URLSearchParams(state.dates[page] || {});
      if (page === "invoices" && ["PAID", "VOID"].includes(state.filter))
        params.set("status", state.filter);
      data = await api(`/${page}?${params}`);
    }
    if (seq !== state.seq || !state.actor) return;
    state.items = data;
    if (page === "dashboard" || page === "machines") state.machines = data;
    if (page === "customers" && state.selected) {
      try {
        state.detail = await api(`/customers/${state.selected}`);
      } catch {
        state.selected = null;
        state.detail = null;
      }
    } else if (page === "invoices" && state.selected) {
      try {
        state.detail = await api(`/invoices/${state.selected}`);
      } catch {
        state.selected = null;
        state.detail = null;
      }
    }
    if (seq !== state.seq || !state.actor) return;
    renderPage();
  } catch (error) {
    if (seq !== state.seq || !state.actor) return;
    $("#workspace").innerHTML =
      pageHead() +
      `<section class="panel"><div class="empty red">${icon("alert")}<strong>${t("unavailable")}</strong><p>${esc(error.message)}</p><button class="btn primary" data-action="refresh">${t("retry")}</button></div></section>` +
      pageFooter();
  }
}
function renderPage() {
  const previous = document.activeElement;
  const focus = previous?.id;
  const caret =
    typeof previous?.selectionStart === "number"
      ? previous.selectionStart
      : null;
  let html;
  if (state.page === "dashboard") html = dashboard();
  else if (state.page === "customers") html = customersPage();
  else if (state.page === "machines") html = machinesPage();
  else if (state.page === "invoices") html = invoicesPage();
  else if (["employees","promotions","stores"].includes(state.page)) html = managementPage();
  else if (state.page === "menu") html = menuAdminPage();
  else if (state.page === "vouchers") html = voucherAdminPage();
  else if (state.page === "revenue" && isManager()) html = revenuePage();
  else { state.page = "dashboard"; html = dashboard(); }
  $("#workspace").innerHTML = html + pageFooter();
  decorateP1Details();
  installRoomManagement();
  installLoyaltyManagement();
  if (state.page === "menu") wireMenuAdmin();
  if (focus) {
    const node = document.getElementById(focus);
    if (node) {
      node.focus();
      if (caret !== null) node.setSelectionRange(caret, caret);
    }
  }
}
function filteredMachines() {
  return state.items.filter(
    (m) =>
      (state.filter === "all" || m.status === state.filter) &&
      `${m.machine_code} ${m.name}`
        .toLocaleLowerCase()
        .includes(state.keyword.toLocaleLowerCase()),
  );
}
function machineToolbar() {
  return `<div class="toolbar"><input id="local-search" class="input search" placeholder="${t("machineSearch")}" value="${esc(state.keyword)}" aria-label="${t("search")}"><span class="spacer"></span>${["all", "AVAILABLE", "IN_USE", "MAINTENANCE"].map((value) => `<button class="filter-btn ${state.filter === value ? "active" : ""}" data-action="filter" data-filter="${value}">${t(value === "all" ? "all" : statusKey(value))} (${state.items.filter((m) => value === "all" || m.status === value).length})</button>`).join("")}</div>`;
}
function dashboard() {
  const list = filteredMachines();
  const counts = (key) => state.items.filter((m) => m.status === key).length;
  return (
    pageHead() +
    `<div class="metrics">${metric("totalMachines", state.items.length)}${metric("available", counts("AVAILABLE"), "green", "check")}${metric("inUse", counts("IN_USE"), "red", "clock")}${metric("maintenance", counts("MAINTENANCE"), "amber", "wrench")}${metric("activeCustomers", counts("IN_USE"), "cyan", "users")}</div>` +
    machineToolbar() +
    `<div class="machine-grid">${list
      .map((m) => {
        const active = m.active_session;
        return `<article class="machine-card ${esc(m.status)}"><div class="row between"><strong>${esc(m.machine_code)}</strong>${badge(m.status)}</div><p class="machine-name">${esc(m.name)}</p><div class="machine-body">${active ? `<div class="row between"><span class="muted">${t("customer")}</span><strong>${esc(active.session.customer_name)}</strong></div><div class="row between"><span class="muted">${t("elapsed")}</span><span>${duration(active.elapsed_seconds)}</span></div><div class="row between"><span class="muted">${t("estimated")}</span><span class="money">${money(active.estimated_cost)}</span></div><div class="row between"><span class="muted">${t("projected")}</span><span class="money ${active.projected_balance < 0 ? "red" : "green"}">${money(active.projected_balance)}</span></div>` : m.status === "MAINTENANCE" ? `<div class="notice">${t("maintenanceNote")}</div>` : `<p class="muted">${t("idleNote")}</p><div class="row between"><span class="muted">${t("hourly")}</span><span class="money">${money(m.hourly_rate)}${t("perHour")}</span></div>`}</div>${m.status === "AVAILABLE" ? `<button class="btn success full" data-action="open" data-id="${m.machine_id}">${icon("plus")}${t("open")}</button>` : m.status === "IN_USE" ? `<button class="btn danger full" data-action="checkout" data-id="${m.machine_id}">${icon("wallet")}${t("checkout")}</button>` : isManager() ? `<button class="btn warning full" data-action="maintenance" data-id="${m.machine_id}">${icon("check")}${t("endMaintenance")}</button>` : `<button class="btn full" disabled>${t("maintenance")}</button>`}</article>`;
      })
      .join("")}</div>${!list.length ? empty() : ""}`
  );
}
function table(headers, rows) {
  return `<div class="table-wrap"><table><thead><tr>${headers.map((key) => `<th>${t(key)}</th>`).join("")}</tr></thead><tbody>${rows}</tbody></table></div>`;
}
function paginate(items) {
  const size = 10;
  const pages = Math.max(1, Math.ceil(items.length / size));
  state.tablePage = Math.min(Math.max(1, state.tablePage), pages);
  const start = (state.tablePage - 1) * size;
  return {
    rows: items.slice(start, start + size),
    foot: `<div class="table-foot"><span>${t("showing")} ${items.length ? start + 1 : 0}–${Math.min(start + size, items.length)} / ${items.length}</span><div class="pages"><button class="btn small" data-action="previous" ${state.tablePage === 1 ? "disabled" : ""} aria-label="${t("previous")}">‹</button><span>${state.tablePage} / ${pages}</span><button class="btn small" data-action="next" ${state.tablePage === pages ? "disabled" : ""} aria-label="${t("next")}">›</button></div></div>`,
  };
}
function customersPage() {
  const filtered = state.items.filter(
    (c) =>
      (state.filter === "all" || c.customer_status === state.filter) &&
      `${c.customer_code} ${c.full_name} ${c.phone} ${c.username}`
        .toLocaleLowerCase()
        .includes(state.keyword.toLocaleLowerCase()),
  );
  const { rows, foot } = paginate(filtered);
  return (
    pageHead(
      `<button class="btn primary small" data-action="customer-create">${icon("plus")}${t("newCustomer")}</button>`,
    ) +
    `<div class="toolbar"><input id="local-search" class="input search" value="${esc(state.keyword)}" placeholder="${t("customerSearch")}" aria-label="${t("search")}"><span class="spacer"></span>${["all", "ACTIVE", "INACTIVE"].map((value) => `<button class="filter-btn ${state.filter === value ? "active" : ""}" data-action="filter" data-filter="${value}">${t(value === "all" ? "all" : statusKey(value))} (${state.items.filter((c) => value === "all" || c.customer_status === value).length})</button>`).join("")}</div><div class="split"><section class="panel">${rows.length ? table(["code", "fullName", "phone", "username", "accountBalance", "status"], rows.map((c) => `<tr data-select="customer" data-id="${c.customer_id}" class="${state.selected === c.customer_id ? "selected" : ""}" tabindex="0"><td class="table-code">${esc(c.customer_code)}</td><td class="table-name">${esc(c.full_name)}</td><td>${esc(c.phone)}</td><td>${esc(c.username)}</td><td class="money ${c.balance < 0 ? "red" : "green"}">${money(c.balance)}</td><td>${badge(c.customer_status)}</td></tr>`).join("")) : empty()}${foot}</section><aside class="panel detail-panel ${state.detail ? "has-selection" : ""}" id="detail-panel">${customerDetail()}</aside></div>`
  );
}
function kv(key, value) {
  return `<div><span>${t(key)}</span><span>${value}</span></div>`;
}
function customerDetail() {
  if (!state.detail?.customer) return empty("selectCustomer");
  const { customer: c, history } = state.detail;
  const allowed =
    c.customer_status === "ACTIVE" && c.account_status === "ACTIVE";
  return `<div class="panel-body"><div class="detail-identity"><div class="avatar">${esc(initials(c.full_name))}</div><div><strong>${esc(c.full_name)}</strong><small class="cyan">${esc(c.customer_code)}</small></div></div><div class="key-values">${kv("account", esc(c.account_code))}${kv("phone", esc(c.phone))}${kv("username", esc(c.username))}${kv("customerStatus", badge(c.customer_status))}${kv("accountStatus", badge(c.account_status))}</div><div class="balance-box"><p>${t("balance")}</p><strong class="money ${c.balance < 0 ? "red" : "green"}">${money(c.balance)}</strong></div><div class="actions"><button class="btn primary small" data-action="topup" data-id="${c.customer_id}">${icon("plus")}${t("topup")}</button><button class="btn small" data-action="customer-edit" data-id="${c.customer_id}">${icon("edit")}${t("edit")}</button>${isManager() ? `<button class="btn ghost small ${allowed ? "red" : "cyan"}" data-action="customer-status" data-id="${c.customer_id}">${icon("lock")}${t(c.customer_status === "ACTIVE" ? "lock" : "unlock")}</button>` : ""}</div><h3 class="history-title">${t("recentHistory")}</h3>${
    history.length
      ? history
          .slice(0, 8)
          .map(
            (tx) =>
              `<div class="transaction"><div class="row between"><strong>${t(tx.type)}</strong><span class="money ${tx.type === "USAGE_PAYMENT" ? "red" : "green"}">${money(tx.amount)}</span></div><small>${t(tx.method)} · ${esc(tx.employee_name)}</small><br><small>${dt(tx.created_at)}</small></div>`,
          )
          .join("")
      : `<div class="empty" style="min-height:130px">${icon("wallet")}<small>${t("noHistory")}</small></div>`
  }</div>`;
}
function machinesPage() {
  const list = filteredMachines();
  const { rows, foot } = paginate(list);
  return (
    pageHead(
      `<button class="btn primary small" data-action="machine-create">${icon("plus")}${t("newMachine")}</button>`,
    ) +
    machineToolbar() +
    `<section class="panel">${rows.length ? table(["machineCode", "machineName", "status", "hourly", "customer", "actions"], rows.map((m) => `<tr><td class="table-code">${esc(m.machine_code)}</td><td class="table-name">${esc(m.name)}</td><td>${badge(m.status)}</td><td class="money">${money(m.hourly_rate)}</td><td>${esc(m.active_session?.session.customer_name || "—")}</td><td><div class="actions"><button class="btn small" data-action="machine-edit" data-id="${m.machine_id}" title="${t("edit")}">${icon("edit")}</button><button class="btn small" data-action="maintenance" data-id="${m.machine_id}" ${m.status === "IN_USE" ? "disabled" : ""} title="${t(m.status === "MAINTENANCE" ? "endMaintenance" : "startMaintenance")}">${icon("wrench")}</button><button class="btn ghost small red" data-action="machine-archive" data-id="${m.machine_id}" ${m.status === "IN_USE" ? "disabled" : ""} title="${t("archive")}">${icon("lock")}</button></div></td></tr>`).join("")) : empty()}${foot}</section>`
  );
}
function dateToolbar() {
  const values = state.dates[state.page] || {};
  const search =
    state.page === "invoices"
      ? `<input class="input search" name="keyword" value="${esc(values.keyword || "")}" placeholder="${t("invoiceSearch")}" aria-label="${t("invoiceSearch")}">`
      : "";
  return `<form id="date-filter" class="toolbar"><label>${t("from")}<input class="input" type="date" name="date_from" value="${esc(values.date_from || dateOffset(state.page === "revenue" ? -6 : -30))}" required></label><label>${t("to")}<input class="input" type="date" name="date_to" value="${esc(values.date_to || state.today)}" required></label>${search}<button type="submit" class="btn primary small">${t("apply")}</button><button type="button" class="btn ghost small" data-action="clear-dates">${t("clearFilters")}</button><span class="spacer"></span>${state.page === "invoices" ? ["all", "PAID", "VOID"].map((value) => `<button type="button" class="filter-btn ${state.filter === value ? "active" : ""}" data-action="filter" data-filter="${value}">${t(value)}</button>`).join("") : `<span class="badge green">● ${t("PAID")}</span>`}</form>`;
}
function dateOffset(days) {
  const d = new Date(`${state.today}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}
function invoicesPage() {
  const { rows, foot } = paginate(state.items);
  return (
    pageHead() +
    dateToolbar() +
    `<div class="split"><section class="panel">${rows.length ? table(["invoiceCode", "createdAt", "customer", "total", "status"], rows.map((inv) => `<tr data-select="invoice" data-id="${inv.invoice_id}" tabindex="0" class="${state.selected === inv.invoice_id ? "selected" : ""}"><td class="table-code">${esc(inv.invoice_code)}</td><td>${dt(inv.created_at)}</td><td class="table-name">${esc(inv.customer_name)}</td><td class="money">${money(inv.total_amount)}</td><td>${badge(inv.status)}</td></tr>`).join("")) : empty()}${foot}</section><aside class="panel detail-panel ${state.detail ? "has-selection" : ""}">${invoiceDetail()}</aside></div>`
  );
}
function invoiceDetail() {
  if (!state.detail?.invoice) return empty("selectInvoice");
  const detail = state.detail;
  const inv = detail.invoice;
  return `<header class="panel-heading"><h3>${t("invoiceDetail")}</h3>${badge(inv.status)}</header><div class="panel-body stack"><div class="key-values">${kv("invoiceCode", `<span class="cyan">${esc(inv.invoice_code)}</span>`)}${kv("sessionCode", esc(detail.session.session_code))}${kv("createdAt", dt(inv.created_at))}${kv("employee", esc(inv.employee_name))}</div><div class="divider"></div><div class="key-values">${kv("customer", esc(inv.customer_name))}${kv("machines", esc(detail.session.machine_code))}${kv("startAt", dt(detail.session.started_at))}${kv("endAt", dt(detail.ended_at))}${kv("duration", `${detail.billed_minutes} ${t("minute")}`)}${kv("hourly", money(detail.session.hourly_rate))}</div><div class="divider"></div><div class="key-values">${kv("usageCost", money(inv.usage_cost))}${kv("settlement", money(inv.settlement_amount))}${kv("total", `<strong class="cyan">${money(inv.total_amount)}</strong>`)}</div><button class="btn small" data-action="copy-invoice" data-code="${esc(inv.invoice_code)}">${icon("copy")}${t("copyCode")}</button></div>`;
}
function revenuePage() {
  const data = state.items;
  const days = data.days;
  const count =
    (new Date(`${data.date_to}T00:00Z`) -
      new Date(`${data.date_from}T00:00Z`)) /
      86400000 +
    1;
  const best = days.reduce(
    (a, b) => (b.revenue > (a?.revenue || 0) ? b : a),
    null,
  );
  // Display buckets only; the service remains the source of all revenue values.
  const bucketSize = Math.max(1, Math.ceil(count / 18));
  const buckets = [];
  for (let i = 0; i < count; i += bucketSize) {
    const day = new Date(`${data.date_from}T00:00:00Z`);
    day.setUTCDate(day.getUTCDate() + i);
    const left = day.toISOString().slice(0, 10);
    day.setUTCDate(day.getUTCDate() + bucketSize - 1);
    const right = day.toISOString().slice(0, 10);
    buckets.push({
      date: left,
      revenue: days
        .filter((d) => d.date >= left && d.date <= right)
        .reduce((sum, d) => sum + d.revenue, 0),
    });
  }
  const max = Math.max(1, ...buckets.map((d) => d.revenue));
  const { rows, foot } = paginate([...days].reverse());
  return (
    pageHead() +
    dateToolbar() +
    `<div class="metrics">${metric("totalRevenue", money(data.total_revenue), "cyan", "wallet")}${metric("paidCount", data.invoice_count, "", "invoice")}${metric("dailyAverage", money(Math.round(data.total_revenue / count)), "", "chart")}${metric("bestDay", best ? best.date : "—", "", "clock")}${metric("revenueDays", days.length, "green", "check")}</div><div class="revenue-layout"><section class="panel"><header class="panel-heading"><h3>${icon("chart")} ${t("revenueDaily")}</h3><small>${esc(data.date_from)} → ${esc(data.date_to)}</small></header><div class="revenue-chart" role="img" aria-label="${t("revenueDaily")}">${buckets.map((d) => `<div class="bar-column"><div class="bar" style="height:${Math.max(1, (d.revenue / max) * 80)}%" title="${esc(d.date)}: ${money(d.revenue)}"><span>${d.revenue ? new Intl.NumberFormat(state.lang, { notation: "compact" }).format(d.revenue) : ""}</span></div><small>${d.date.slice(5).split("-").reverse().join("/")}</small></div>`).join("")}</div>${rows.length ? table(["createdAt", "paidCount", "revenue"], rows.map((d) => `<tr><td>${esc(d.date)}</td><td>${d.invoice_count}</td><td class="money green">${money(d.revenue)}</td></tr>`).join("")) : empty()}${foot}</section><aside class="panel"><header class="panel-heading"><h3>${t("summary")}</h3></header><div class="mini-summary"><div class="key-values">${kv("reportScope", esc(state.actor.store_name))}${kv("from", esc(data.date_from))}${kv("to", esc(data.date_to))}${kv("paidCount", data.invoice_count)}</div><div class="summary-total"><small>${t("totalRevenue")}</small><p class="money cyan" style="margin-top:8px">${money(data.total_revenue)}</p></div><div class="notice info">${t("reportNote")}</div><small>${t("localTimezone")}</small></div></aside></div>`
  );
}
function field(name, label, value = "", type = "text", extra = "") {
  return `<label ${extra.includes("wide") ? 'class="wide"' : ""}><span>${t(label)} <span class="cyan">*</span></span><input class="input" name="${name}" value="${esc(value)}" type="${type}" ${type === "number" ? 'step="1" min="1"' : ""} ${type === "password" ? 'autocomplete="new-password"' : ""} required><span class="field-error" data-error="${name}"></span></label>`;
}
function modal(
  title,
  subtitle,
  content,
  action,
  context = {},
  button = "confirm",
) {
  modalContext = { action, ...context };
  const dialog = $("#modal");
  if (dialog.open) dialog.close();
  dialog.innerHTML = `<form id="modal-form" novalidate><header class="modal-header"><div><h2 id="modal-title">${t(title)}</h2>${subtitle ? `<small>${t(subtitle)}</small>` : ""}</div><button class="close" type="button" data-action="close-modal" aria-label="${t("close")}">×</button></header><div class="modal-body">${content}<div id="form-error" class="error-box" role="alert"></div></div><footer class="modal-footer"><small>CyberHub Manager</small><button class="btn small" type="button" data-action="close-modal">${t("cancel")}</button><button class="btn primary" id="modal-submit" type="submit">${t(button)}</button></footer></form>`;
  dialog.showModal();
  if(action==="receipt") $(".modal-body",dialog).insertAdjacentHTML("beforeend",`<div class="actions"><button class="btn primary" type="button" data-p1="print" data-id="${context.invoiceId}">${t("print")}</button><button class="btn" type="button" data-p1="export" data-id="${context.invoiceId}">${t("export")}</button></div>`);
  const input = $("input:not([type=checkbox]),select", dialog);
  if (input) setTimeout(() => input.focus(), 60);
}
function closeModal(force = false) {
  if (state.busy && !force) return;
  $("#modal").close();
  modalContext = null;
}
function busyModal(busy) {
  state.busy = busy;
  const dialog = $("#modal");
  for (const el of dialog.querySelectorAll("button,input,select"))
    el.disabled = busy;
  if (busy)
    $("#modal-submit").innerHTML =
      `<span class="spinner"></span>${t("processing")}`;
  else if ($("#modal-submit")) $("#modal-submit").textContent = t("confirm");
}
function formError(error) {
  const node = $("#form-error");
  if (!node) return;
  node.textContent = error.message;
  for (const [key, message] of Object.entries(error.field_errors || {})) {
    const hint = $(
      `[data-error="${key.replace(/[^a-z_]/g, "")}"]`,
      $("#modal"),
    );
    if (hint) {
      hint.textContent = message;
      const input = $(`[name="${key}"]`, $("#modal"));
      if (input) input.setAttribute("aria-invalid", "true");
    }
  }
}
async function selectRow(type, id) {
  try {
    state.selected = id;
    state.detail = await api(
      `/${type === "customer" ? "customers" : "invoices"}/${id}`,
    );
    renderPage();
  } catch (error) {
    toast(error.message, true);
  }
}
async function showCustomerForm(edit = false) {
  const c = edit ? (await api(`/customers/${state.selected}`)).customer : null;
  modal(
    edit ? "edit" : "newCustomer",
    "customersSub",
    `<div class="form-grid">${field("full_name", "fullName", c?.full_name || "")}${field("phone", "phone", c?.phone || "", "tel")}${!edit ? field("username", "username", "", "text", "wide") + field("password", "password", "", "password") + field("confirm_password", "confirmPassword", "", "password") : ""}</div><div class="notice info">${t(edit ? "passwordClear" : "createNote")} ${!edit ? t("autoCode") : ""}</div>`,
    edit ? "customer-edit" : "customer-create",
    { id: c?.customer_id },
    edit ? "save" : "newCustomer",
  );
}
async function showTopup(id, returnOpen = null) {
  const c = (await api(`/customers/${id}`)).customer;
  modal(
    "topup",
    "customersSub",
    `<div class="form-card"><div class="row between"><strong>${esc(c.full_name)}</strong><span class="table-code">${esc(c.customer_code)}</span></div><div class="row between"><small>${t("balance")}</small><strong class="money">${money(c.balance)}</strong></div></div>${field("amount", "amount", "", "number")}<small>${t("amountHint")}</small><div class="quick-amounts">${[10000, 20000, 50000, 100000].map((amount) => `<button class="btn small" type="button" data-action="quick-amount" data-amount="${amount}">${new Intl.NumberFormat(state.lang).format(amount)}</button>`).join("")}</div><label><span>${t("paymentMethod")}</span><select name="method"><option value="CASH">${t("CASH")}</option><option value="TRANSFER">${t("TRANSFER")}</option></select></label><div class="notice info">${t("transferNote")}</div><label class="check-label"><input type="checkbox" name="received"><span>${t("receivedConfirm")}</span></label><div class="form-card row between"><span>${t("expectedBalance")}</span><strong class="money green" id="topup-balance">—</strong></div>`,
    "topup",
    { id, balance: c.balance, returnOpen },
    "topup",
  );
  $("#modal-submit").disabled = true;
  installTopupQuote();
}
function showMachineForm(id) {
  const m = state.machines.find((m) => m.machine_id === id);
  modal(
    m ? "edit" : "newMachine",
    "machinesSub",
    `<div class="form-grid">${!m ? field("code", "machineCode", "", "text", "wide") : ""}${field("name", "machineName", m?.name || "")}${field("hourly_rate", "hourly", m?.hourly_rate || 10000, "number")}</div><div class="notice info">${t("rateSnapshot")}</div>`,
    m ? "machine-edit" : "machine-create",
    { id },
    m ? "save" : "newMachine",
  );
}
async function showOpen(id) {
  const customers = await api("/customers");
  const m = state.machines.find((m) => m.machine_id === id);
  modal(
    "open",
    "preview",
    `<div class="form-card"><div class="row between"><strong>${esc(m.machine_code)} · ${esc(m.name)}</strong>${badge(m.status)}</div><p class="money cyan">${money(m.hourly_rate)}${t("perHour")}</p></div><label><span>${t("customer")}</span><select name="customer_id" id="open-customer"><option value="">${t("chooseCustomer")}</option>${customers.map((c) => `<option value="${c.customer_id}">${esc(c.full_name)} · ${esc(c.phone)} · ${money(c.balance)}</option>`).join("")}</select></label><div id="open-preview" class="notice info">${t("chooseCustomer")}</div><small>${t("rateSnapshot")}</small>`,
    "open",
    { id },
    "open",
  );
  $("#modal-submit").disabled = true;
}
async function updateOpenPreview() {
  const selected = Number($("#open-customer").value);
  const context = modalContext;
  if (!selected) {
    $("#modal-submit").disabled = true;
    return;
  }
  $("#open-preview").innerHTML = loading();
  $("#modal-submit").disabled = true;
  try {
    const p = await api(`/machines/${context.id}/open-preview`, {
      method: "POST",
      body: { customer_id: selected },
    });
    if (
      modalContext !== context ||
      Number($("#open-customer").value) !== selected
    )
      return;
    $("#open-preview").innerHTML =
      `<div class="key-values">${kv("balance", money(p.balance))}${kv("minimumBalance", money(p.minimum_balance))}${kv("estimatedTime", `${p.estimated_minutes} ${t("minute")}`)}</div><p style="margin-top:14px" class="${p.can_open ? "green" : "amber"}">${t(p.can_open ? "openAllowed" : "openBlocked")}</p>${!p.can_open ? `<button type="button" class="btn primary" data-action="topup-for-open" data-id="${selected}">${icon("plus")}${t("topup")}</button>` : ""}`;
    $("#modal-submit").disabled = !p.can_open;
  } catch (error) {
    if (modalContext === context) {
      $("#open-preview").textContent = error.message;
    }
  }
}
async function showCheckout(id, notice = "") {
  const p = await api(`/machines/${id}/checkout-preview`);
  const required = p.settlement_required;
  modal(
    "checkoutTitle",
    "checkoutSub",
    `${notice ? `<div class="notice">${esc(notice)}</div>` : ""}<div class="form-card"><div class="row between"><strong>${esc(p.session.machine_code)} · ${esc(p.session.machine_name)}</strong>${badge("IN_USE")}</div><div class="key-values" style="margin-top:14px">${kv("customer", esc(p.session.customer_name))}${kv("startAt", dt(p.session.started_at))}${kv("duration", `${p.billed_minutes} ${t("minute")}`)}${kv("hourly", money(p.session.hourly_rate))}</div></div><div class="key-values">${kv("usageCost", `<strong>${money(p.usage_cost)}</strong>`)}${kv("bonusUsed",money(p.bonus_used))}${kv("balance", money(p.balance_before))}${kv("settlement", `<strong class="${required ? "red" : "green"}">${money(required)}</strong>`)}${kv("balanceAfter", `<strong class="green">${money(p.projected_balance + required)}</strong>`)}</div>${required ? `<label><span>${t("paymentMethod")}</span><select name="method" id="checkout-method"><option value="CASH">${t("CASH")}</option><option value="TRANSFER">${t("TRANSFER")}</option></select></label><div id="cash-fields">${field("cash_received", "cashReceived", required, "number")}<div class="row between" style="margin-top:12px"><span>${t("change")}</span><strong class="money green" id="cash-change">${money(0)}</strong></div></div><div class="notice info">${t("transferNote")}<br>${t("settlementNote")}</div><label class="check-label"><input type="checkbox" name="received"><span>${t("receivedConfirm")}</span></label>` : `<div class="notice success">${t("noSettlement")}</div>`}`,
    "checkout",
    { id, preview: p },
    "checkout",
  );
  $("#modal-submit").disabled = required > 0;
}
function receipt(result) {
  const d = result.invoice;
  const inv = d.invoice;
  modal(
    "receipt",
    "receiptSub",
    `<div class="receipt-success">${icon("check")}<strong>${t("PAID")}</strong></div><div class="form-card"><div class="key-values">${kv("invoiceCode", `<strong class="cyan">${esc(inv.invoice_code)}</strong>`)}${kv("sessionCode", esc(d.session.session_code))}${kv("machines", esc(d.session.machine_code))}${kv("customer", esc(inv.customer_name))}${kv("employee", esc(inv.employee_name))}${kv("endAt", dt(d.ended_at))}</div></div><div class="key-values">${kv("usageCost", money(inv.usage_cost))}${kv("bonusUsed",money(inv.bonus_used))}${kv("settlement", money(inv.settlement_amount))}${kv("balanceAfter", `<strong class="green">${money(result.balance_after)}</strong>`)}</div><button class="btn" type="button" data-action="copy-invoice" data-code="${esc(inv.invoice_code)}">${icon("copy")}${t("copyCode")}</button>`,
    "receipt",
    {invoiceId:inv.invoice_id},
    "close",
  );
}
function updateModalControls() {
  if (!modalContext || state.busy) return;
  const form = $("#modal-form");
  if (modalContext.action === "topup") {
    const amount = Number(form.elements.amount.value);
    const valid =
      Number.isSafeInteger(amount) && amount > 0 && amount <= 100000000;
    $("#topup-balance").textContent = valid
      ? money(modalContext.balance + amount)
      : "—";
    $("#modal-submit").disabled = !(valid && form.elements.received.checked);
  }
  if (
    modalContext.action === "checkout" &&
    modalContext.preview.settlement_required > 0
  ) {
    const required = modalContext.preview.settlement_required;
    const cash = form.elements.method.value === "CASH";
    const amount = Number(form.elements.cash_received.value);
    $("#cash-fields").hidden = !cash;
    $("#cash-change").textContent = money(Math.max(0, amount - required));
    $("#modal-submit").disabled = !(
      form.elements.received.checked &&
      (!cash || (Number.isSafeInteger(amount) && amount >= required))
    );
  }
}
async function submitModal(event) {
  event.preventDefault();
  if (!modalContext || state.busy) return;
  const context = modalContext;
  const form = event.target;
  const values = Object.fromEntries(new FormData(form));
  if (context.action === "receipt") {
    closeModal();
    return;
  }
  if (
    context.action === "customer-create" &&
    values.password !== values.confirm_password
  ) {
    formError({
      message: t("mismatch"),
      field_errors: { confirm_password: t("mismatch") },
    });
    return;
  }
  if (context.action === "topup" && !form.elements.received.checked) return;
  if(context.action === "management" || context.action === "switch-store") { await submitManagement(context,values); return; }
  if (
    context.action === "checkout" &&
    context.preview.settlement_required > 0 &&
    $("#modal-submit").disabled
  )
    return;
  for (const hint of form.querySelectorAll("[data-error]"))
    hint.textContent = "";
  $("#form-error").textContent = "";
  busyModal(true);
  try {
    let result;
    if (context.action === "customer-create")
      result = await api("/customers", { method: "POST", body: values });
    if (context.action === "customer-edit")
      result = await api(`/customers/${context.id}`, {
        method: "PATCH",
        body: values,
      });
    if (context.action === "topup")
      result = await api(`/customers/${context.id}/topup`, {
        method: "POST",
        body: { amount: Number(values.amount), method: values.method },
      });
    if (
      context.action === "machine-create" ||
      context.action === "machine-edit"
    )
      result = await api(`/machines${context.id ? `/${context.id}` : ""}`, {
        method: context.id ? "PATCH" : "POST",
        body: { ...values, hourly_rate: Number(values.hourly_rate) },
      });
    if (context.action === "open")
      result = await api(`/machines/${context.id}/open`, {
        method: "POST",
        body: { customer_id: Number(values.customer_id) },
      });
    if (context.action === "checkout")
      result = await api(`/machines/${context.id}/checkout`, {
        method: "POST",
        body: {
          settlement_amount: context.preview.settlement_required,
          method: context.preview.settlement_required ? values.method : null,
        },
      });
    if (context.action === "confirm")
      result = await api(context.url, { method: "POST", body: context.body });
    state.busy = false;
    closeModal();
    if (context.action === "customer-create") {
      state.selected = result.customer_id;
      state.filter = "all";
      state.keyword = "";
      state.tablePage = 1;
    }
    await loadPage(true);
    if (context.action === "topup" && context.returnOpen) {
      await showOpen(context.returnOpen.machineId);
      $("#open-customer").value = String(context.id);
      await updateOpenPreview();
    }
    if (context.action === "checkout") receipt(result);
    else toast(t("success"));
  } catch (error) {
    busyModal(false);
    if (!$("#modal").open) return;
    if (
      context.action === "checkout" &&
      ["SETTLEMENT_REQUIRED", "VALIDATION_ERROR", "CONFLICT"].includes(
        error.code,
      )
    ) {
      try {
        await showCheckout(context.id, error.message);
      } catch (refreshError) {
        formError(refreshError);
      }
    } else {
      formError(error);
      updateModalControls();
    }
  }
}
document.addEventListener("submit", (event) => {
  if (event.target.id === "modal-form") submitModal(event);
  if (event.target.id === "date-filter") {
    event.preventDefault();
    state.dates[state.page] = Object.fromEntries(new FormData(event.target));
    state.tablePage = 1;
    loadPage();
  }
});
document.addEventListener("input", (event) => {
  if (event.target.id === "local-search") {
    state.keyword = event.target.value;
    state.tablePage = 1;
    renderPage();
  }
  if (event.target.closest("#modal")) updateModalControls();
});
document.addEventListener("change", (event) => {
  if (event.target.id === "open-customer") updateOpenPreview();
  if (event.target.closest("#modal")) updateModalControls();
});
$("#modal").addEventListener("cancel", (event) => {
  if (state.busy) event.preventDefault();
  else modalContext = null;
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && event.target.matches("tr[data-select]"))
    event.target.click();
});
document.addEventListener("click", async (event) => {
  const row = event.target.closest("[data-select]");
  if (row) {
    await selectRow(row.dataset.select, Number(row.dataset.id));
    return;
  }
  const button = event.target.closest("[data-action]");
  if (!button || button.disabled) return;
  const action = button.dataset.action;
  const id = Number(button.dataset.id);
  try {
    if (action === "language") setLanguage(button.dataset.lang);
    if (action === "show-password") {
      const input = $("#login-password");
      input.type = input.type === "password" ? "text" : "password";
    }
    if (action === "navigate") {
      state.page = button.dataset.page;
      state.keyword = "";
      state.filter = "all";
      state.selected = null;
      state.detail = null;
      state.tablePage = 1;
      renderShell();
      await loadPage();
    }
    if (action === "refresh") await loadPage();
    if (action === "logout") {
      button.disabled = true;
      await api("/logout", { method: "POST", body: {} });
      state.actor = null;
      state.selected = null;
      state.detail = null;
      state.seq++;
      renderLogin();
    }
    if (action === "filter") {
      state.filter = button.dataset.filter;
      state.tablePage = 1;
      state.page === "invoices" ? await loadPage() : renderPage();
    }
    if (action === "previous" || action === "next") {
      state.tablePage += action === "next" ? 1 : -1;
      renderPage();
    }
    if (action === "clear-dates") {
      state.dates[state.page] = {};
      await loadPage();
    }
    if (action === "close-modal") closeModal();
    if (action === "customer-create") await showCustomerForm();
    if (action === "customer-edit") {
      state.selected = id;
      await showCustomerForm(true);
    }
    if (action === "topup") await showTopup(id);
    if (action === "topup-for-open") {
      await showTopup(id, { machineId: modalContext.id });
    }
    if (action === "quick-amount") {
      $("[name=amount]", $("#modal")).value = button.dataset.amount;
      updateModalControls();
    }
    if (action === "machine-create") showMachineForm();
    if (action === "machine-edit") showMachineForm(id);
    if (action === "open") await showOpen(id);
    if (action === "checkout") await showCheckout(id);
    if (action === "customer-status") {
      const c = (await api(`/customers/${id}`)).customer;
      const locking = c.customer_status === "ACTIVE";
      modal(
        locking ? "lock" : "unlock",
        "customersSub",
        `<div class="form-card"><strong>${esc(c.full_name)}</strong><p class="cyan">${esc(c.customer_code)}</p></div><div class="notice ${locking ? "" : "success"}">${t(locking ? "statusLockNote" : "statusUnlockNote")}</div>`,
        "confirm",
        {
          url: `/customers/${id}/status`,
          body: { status: locking ? "INACTIVE" : "ACTIVE" },
        },
      );
    }
    if (action === "maintenance") {
      const m = state.machines.find((m) => m.machine_id === id);
      modal(
        m.status === "MAINTENANCE" ? "endMaintenance" : "startMaintenance",
        "machinesSub",
        `<div class="notice">${esc(m.machine_code)} · ${t("maintenanceConfirm")}</div>`,
        "confirm",
        {
          url: `/machines/${id}/maintenance`,
          body: { enabled: m.status !== "MAINTENANCE" },
        },
      );
    }
    if (action === "machine-archive")
      modal(
        "archive",
        "machinesSub",
        `<div class="notice">${t("archiveNote")}</div>`,
        "confirm",
        { url: `/machines/${id}/archive`, body: {} },
      );
    if (action === "copy-invoice") {
      await navigator.clipboard.writeText(button.dataset.code);
      toast(t("copied"));
    }
  } catch (error) {
    button.disabled = false;
    toast(error.message, true);
  }
});
async function boot() {
  try {
    const data = await api("/session");
    state.actor = data.actor;
    state.customer = data.customer;
    state.today = data.today;
    state.mode = data.mode;
    document.documentElement.lang = state.lang;
    if(state.customer) { await renderPortal(); return; }
    if (state.actor) {
      renderShell();
      await loadPage();
    } else renderLogin();
  } catch (error) {
    $("#app").innerHTML =
      `<div class="boot">${icon("alert")}<h1>${t("bootError")}</h1><p>${esc(error.message)}</p><button class="btn primary" id="boot-retry">${t("retry")}</button></div>`;
    $("#boot-retry").onclick = boot;
  }
}
// All deferred extensions must finish loading before the first API response renders UI.
document.addEventListener("DOMContentLoaded",boot,{once:true});
