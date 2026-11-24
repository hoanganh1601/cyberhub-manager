"use strict";
// Menu dạng sách lật trong cổng khách hàng.
// Mỗi nhóm món là một cột có nhãn tiêu đề; trong nhóm, các món chia "nhóm nhỏ" theo hàng trăm
// của sort_order (0-99, 100-199, ...) và được ngăn bằng vạch kẻ.
// Giá/trạng thái món do backend quyết định; trình duyệt chỉ gửi mã món + số lượng khi đặt.

Object.assign(paths, {
  utensils: '<path d="M7 3v8M4 3v5a3 3 0 0 0 6 0V3M7 11v10M17 3c-2.2 0-3 2.5-3 5.5V13h3v8"/>',
  cart: '<circle cx="9" cy="20" r="1.5"/><circle cx="18" cy="20" r="1.5"/><path d="M3 4h2l2.5 11h11l2-8H6.5"/>',
});
Object.assign(copy, {
  dot1Menu: ["Menu đồ ăn", "Food menu"],
  dot1MenuSub: ["Lật trang để xem món và gọi món tới máy bạn đang ngồi", "Flip through the menu and order to your seat"],
  dot1Food: ["Món ăn", "Food"],
  dot1Drink: ["Đồ uống", "Drinks"],
  dot1Page: ["Trang", "Page"],
  dot1Prev: ["Trang trước", "Previous"],
  dot1Next: ["Trang sau", "Next"],
  dot1SoldOut: ["Hết", "Sold out"],
  dot1Add: ["Chọn", "Add"],
  dot1Cart: ["Món đã chọn", "Your order"],
  dot1CartEmpty: ["Chưa chọn món nào. Bấm + bên cạnh món để chọn.", "Nothing selected yet. Tap + next to an item."],
  dot1Note: ["Ghi chú cho nhân viên", "Note for staff"],
  dot1NotePlaceholder: ["Ví dụ: ít đá, không hành", "e.g. less ice, no onion"],
  dot1Order: ["Đặt món", "Place order"],
  dot1Sending: ["Đang gửi…", "Sending…"],
  dot1PayAtCounter: ["Nhân viên mang món tới máy và thu tiền tại quầy. Số dư tài khoản không bị trừ.", "Staff bring your order to your seat; pay at the counter. Your balance is not charged."],
  dot1NeedSession: ["Bạn cần đang chơi tại cơ sở này để gọi món. Vẫn có thể xem menu.", "Start a session at this store to order. You can still browse."],
  dot1Seat: ["Giao tới máy", "Deliver to"],
  dot1Ordered: ["Đã gửi yêu cầu gọi món", "Your order has been sent"],
  dot1Recent: ["Yêu cầu gần đây", "Recent orders"],
  dot1Total: ["Tạm tính", "Subtotal"],
  dot1Unit: ["Đơn vị: VND", "Prices in VND"],
  dot1ViewCart: ["Xem món đã chọn", "View order"],
  dot1Items: ["món", "items"],
  dot1EmptyMenu: ["Trang này chưa có món", "No items on this page yet"],
  dot1StNEW: ["Đang chờ", "Pending"],
  dot1StPREPARING: ["Đang chuẩn bị", "Preparing"],
  dot1StSERVED: ["Đã phục vụ", "Served"],
  dot1StPAID: ["Đã thanh toán", "Paid"],
  dot1StCANCELLED: ["Đã hủy", "Cancelled"],
  dot1Swipe: ["Vuốt hoặc dùng phím ← → để lật trang", "Swipe or use ← → to turn pages"],
  dot1BlankLeaf: ["Khám phá các món ở trang bên cạnh", "Explore the menu on the facing page"],
});

const DOT1_MAX_QTY = 20;
const DOT1_STALE_MS = 30000;

function dot1State() {
  const ui = portalUI;
  ui.menuCart ??= {};
  ui.menuPage ??= 0;
  ui.menuNote ??= "";
  return ui;
}
const dot1Items = (data) => data.pages.flatMap((p) => p.categories.flatMap((g) => g.items));
const dot1PageName = (page) => t(page === "FOOD" ? "dot1Food" : "dot1Drink");
const dot1Mobile = () => matchMedia("(max-width: 900px)").matches;
// Mỗi tờ chứa tối đa hai nhóm món; mỗi mục FOOD/DRINK kết thúc ở ranh giới một cặp trang.
function dot1Leaves(data) {
  const leaves = [];
  for (const section of data.pages) {
    const groups = section.categories;
    const sectionLeaves = [];
    for (let i = 0; i < groups.length; i += 2) {
      sectionLeaves.push({ page: section.page, categories: groups.slice(i, i + 2) });
    }
    if (!sectionLeaves.length) sectionLeaves.push({ page: section.page, categories: [] });
    if (sectionLeaves.length % 2) sectionLeaves.push({ page: section.page, categories: [], blank: true });
    leaves.push(...sectionLeaves);
  }
  return leaves;
}
function dot1VisiblePage(index, count, mobile = dot1Mobile()) {
  const bounded = Math.max(0, Math.min(Number.isInteger(index) ? index : 0, count - 1));
  return mobile ? bounded : bounded - bounded % 2;
}
function dot1Spread(leaves, start, mobile = dot1Mobile()) {
  const shown = mobile ? [start] : [start, start + 1];
  return `<div class="dot1-spread">${shown.filter(i => leaves[i]).map(i => dot1Sheet(leaves[i], i)).join("")}</div>`;
}
// Giá trên bảng menu: chỉ số, không ký hiệu tiền (đơn vị ghi ở đầu trang).
const dot1Price = (value) => new Intl.NumberFormat(state.lang === "en" ? "en-US" : "vi-VN").format(value);

// Được drawCustomerPortal() gọi khi tab = "menu".
function customerMenuPage() {
  const ui = dot1State();
  if (!ui.menuLoading && (!ui.menu || Date.now() - (ui.menuLoadedAt || 0) > DOT1_STALE_MS)) loadCustomerMenu();
  return `<div id="dot1-menu-root">${dot1Body()}</div>`;
}

async function loadCustomerMenu() {
  const ui = dot1State();
  ui.menuLoading = true;
  try {
    const query = ui.menuStore ? `?store_id=${encodeURIComponent(ui.menuStore)}` : "";
    const data = await api("/portal/menu" + query);
    if (ui !== portalUI) return;
    ui.menu = data;
    ui.menuStore = data.store_id;
    ui.menuLoadedAt = Date.now();
    ui.menuError = null;
    ui.menuPage = Math.min(ui.menuPage, Math.max(0, dot1Leaves(data).length - 1));
    // Bỏ khỏi giỏ những món vừa hết hoặc bị ẩn để không gửi yêu cầu chắc chắn bị từ chối.
    const orderable = new Set(dot1Items(data).filter((i) => i.is_available).map((i) => String(i.id)));
    for (const id of Object.keys(ui.menuCart)) if (!orderable.has(id)) delete ui.menuCart[id];
  } catch (error) {
    if (ui !== portalUI) return;
    if (error.field_errors?.store_id) ui.menuStore = null;
    ui.menuError = error.message;
    ui.menuLoadedAt = Date.now();
  } finally {
    ui.menuLoading = false;
    if (ui === portalUI && ui.tab === "menu") dot1Redraw();
  }
}

function dot1Redraw() {
  const root = $("#dot1-menu-root");
  if (!root) return;
  dot1FlipToken++;
  dot1FlipBusy = false;
  root.innerHTML = dot1Body();
  wireMenu();
}

function dot1CartLines() {
  const ui = portalUI, items = dot1Items(ui.menu);
  return Object.entries(ui.menuCart)
    .map(([id, qty]) => ({ item: items.find((i) => i.id === Number(id)), qty }))
    .filter((line) => line.item);
}

function dot1Body() {
  const ui = dot1State(), d = ui.menu;
  if (!d) {
    return ui.menuError
      ? `<section class="pc-card"><div class="pc-empty">${icon("alert")}<h3>${t("unavailable")}</h3><p>${esc(ui.menuError)}</p><button class="btn primary" data-menu="reload">${t("retry")}</button></div></section>`
      : `<section class="pc-card"><div class="pc-loading" role="status"><span class="spinner"></span><p>${t("loading")}</p></div></section>`;
  }
  const leaves = dot1Leaves(d), mobile = dot1Mobile();
  const page = dot1VisiblePage(ui.menuPage, leaves.length, mobile);
  const step = mobile ? 1 : 2;
  const section = leaves[page]?.page;
  const lines = dot1CartLines();
  const count = lines.reduce((n, l) => n + l.qty, 0);
  const total = lines.reduce((sum, l) => sum + l.item.price * l.qty, 0);
  const stores = d.stores.length > 1
    ? `<label class="pc-field"><span>${t("store")}</span><select id="dot1-store">${d.stores.map((s) => `<option value="${s.id}" ${s.id === d.store_id ? "selected" : ""}>${esc(s.name)}</option>`).join("")}</select></label>`
    : "";
  const summary = count
    ? `<button class="dot1-summary" data-menu="to-cart">${icon("cart")}<span>${count} ${t("dot1Items")} · <b>${money(total)}</b></span><span class="cyan">${t("dot1ViewCart")} ›</span></button>`
    : "";
  return `<div class="dot1-layout">
      <div class="dot1-toolbar">
        <div class="dot1-book-tabs segment" role="tablist">${d.pages.map(p => { const i = leaves.findIndex(leaf => leaf.page === p.page); return `<button role="tab" aria-selected="${section === p.page}" class="${section === p.page ? "active" : ""}" data-menu="page" data-page="${i}">${dot1PageName(p.page)}</button>`; }).join("")}</div>
        <span class="spacer"></span>${stores}${summary}
      </div>
      <section class="dot1-book" aria-label="${t("dot1Menu")}">
        <div class="dot1-stage" id="dot1-stage">${dot1Spread(leaves, page, mobile)}</div>
        <footer class="dot1-book-nav"><button class="btn small" data-menu="flip" data-dir="-1" ${page === 0 ? "disabled" : ""}>‹ ${t("dot1Prev")}</button><span>${t("dot1Page")} ${mobile ? page + 1 : `${page + 1}–${Math.min(page + 2, leaves.length)}`}/${leaves.length} · <small>${t("dot1Swipe")}</small></span><button class="btn small" data-menu="flip" data-dir="1" ${page + step >= leaves.length ? "disabled" : ""}>${t("dot1Next")} ›</button></footer>
      </section>
      ${dot1Cart(lines, total)}
    </div>`;
}

// Một trang menu dạng bảng: chữ "menu" + logo, các cột nhóm món, dải ảnh món ở chân trang.
function dot1Sheet(p, index) {
  const columns = p.categories.map((g) => {
    const groups = [];
    let last = null;
    for (const item of g.items) {
      const key = Math.floor(item.sort_order / 100);
      if (key !== last) { groups.push([]); last = key; }
      groups[groups.length - 1].push(item);
    }
    return `<section class="dot1-col"><h3 class="dot1-pill">${esc(g.category.name)}</h3>${groups.map((rows) => `<ul class="dot1-rows">${rows.map(dot1Row).join("")}</ul>`).join("")}</section>`;
  }).join("");
  const photos = p.categories.flatMap((g) => g.items).filter((i) => i.image_version).slice(0, 5);
  return `<article class="dot1-sheet dot1-board" data-index="${index}">
      <header class="dot1-board-head">
        <div class="dot1-brand"><span class="dot1-word">menu</span><img src="/assets/cyberhub_logo_dark.png" alt="CyberHub"></div>
        <div class="dot1-board-title"><p class="pc-eyebrow">CYBERHUB · ${t("dot1Page")} ${index + 1}</p><h2>${dot1PageName(p.page)}</h2><small>${t("dot1Unit")}</small></div>
      </header>
      ${columns ? `<div class="dot1-columns">${columns}</div>` : `<div class="dot1-blank">${icon("utensils")}<p>${t(p.blank ? "dot1BlankLeaf" : "dot1EmptyMenu")}</p></div>`}
      ${photos.length ? `<div class="dot1-photos">${photos.map((i) => `<figure><img src="/api/portal/menu/items/${i.id}/image?v=${encodeURIComponent(i.image_version)}" alt="${esc(i.name)}" loading="lazy"><figcaption>${esc(i.name)}</figcaption></figure>`).join("")}</div>` : ""}
      <footer class="dot1-sheet-foot">— ${index + 1} —</footer>
    </article>`;
}

// Một dòng "tên ........ giá [+]" trên bảng menu.
function dot1Row(item) {
  const ui = portalUI, qty = ui.menuCart[item.id] || 0, canOrder = ui.menu.can_order;
  let control;
  if (!item.is_available) control = `<span class="dot1-sold">${t("dot1SoldOut")}</span>`;
  else if (qty) control = `<span class="dot1-stepper" role="group" aria-label="${esc(item.name)}"><button data-menu="dec" data-id="${item.id}" aria-label="-">−</button><span>${qty}</span><button data-menu="inc" data-id="${item.id}" aria-label="+" ${qty >= DOT1_MAX_QTY ? "disabled" : ""}>+</button></span>`;
  else control = `<button class="dot1-add" data-menu="inc" data-id="${item.id}" aria-label="${t("dot1Add")} ${esc(item.name)}" ${canOrder ? "" : "disabled"}>+</button>`;
  return `<li class="dot1-row ${item.is_available ? "" : "sold-out"} ${qty ? "picked" : ""}">
      <span class="dot1-name">${esc(item.name)}${item.description ? `<small>${esc(item.description)}</small>` : ""}</span>
      <span class="dot1-leader" aria-hidden="true"></span>
      <span class="dot1-price">${dot1Price(item.price)}</span>
      <span class="dot1-control">${control}</span>
    </li>`;
}

function dot1Cart(lines, total) {
  const ui = portalUI, d = ui.menu;
  const ready = d.can_order && lines.length && !ui.menuBusy;
  const recent = d.orders.length
    ? `<div class="dot1-recent"><h3>${t("dot1Recent")}</h3><ul>${d.orders.map((o) => `<li><span>${esc(o.code)} · ${o.lines.reduce((n, l) => n + l.quantity, 0)} ${t("dot1Items")}</span><span>${money(o.total_amount)} <b class="dot1-status ${o.status}">${t("dot1St" + o.status)}</b></span></li>`).join("")}</ul></div>`
    : "";
  return `<aside class="pc-card dot1-cart" id="dot1-cart">
      <header><h2>${icon("cart")} ${t("dot1Cart")}</h2>${d.session ? `<span class="dot1-seat">${t("dot1Seat")} <b>${esc(d.session.machine_code)}</b></span>` : ""}</header>
      <div class="dot1-cart-grid">
        <div>${lines.length
          ? `<ul class="dot1-lines">${lines.map((l) => `<li><span>${esc(l.item.name)} × ${l.qty}</span><strong>${money(l.item.price * l.qty)}</strong></li>`).join("")}</ul><div class="dot1-total"><span>${t("dot1Total")}</span><strong>${money(total)}</strong></div>`
          : `<p class="muted">${t("dot1CartEmpty")}</p>`}</div>
        <div>
          <label class="pc-field"><span>${t("dot1Note")}</span><input class="input" id="dot1-note" maxlength="200" placeholder="${t("dot1NotePlaceholder")}" value="${esc(ui.menuNote)}" ${d.can_order ? "" : "disabled"}></label>
          <p class="dot1-hint ${d.can_order ? "" : "warn"}">${t(d.can_order ? "dot1PayAtCounter" : "dot1NeedSession")}</p>
          <button class="btn primary full" data-menu="order" ${ready ? "" : "disabled"}>${ui.menuBusy ? t("dot1Sending") : t("dot1Order")}</button>
        </div>
      </div>
      ${recent}
    </aside>`;
}

// ----- Lật trang ---------------------------------------------------------------
let dot1FlipToken = 0;
let dot1FlipBusy = false;
function flipMenu(to) {
  const ui = portalUI, d = ui?.menu;
  if (!d || dot1FlipBusy) return;
  const leaves = dot1Leaves(d), mobile = dot1Mobile();
  const from = dot1VisiblePage(ui.menuPage, leaves.length, mobile);
  const target = dot1VisiblePage(to, leaves.length, mobile);
  if (target === from || to < 0 || to >= leaves.length) return;
  ui.menuPage = target;
  const stage = $("#dot1-stage");
  const current = stage?.querySelector(".dot1-spread");
  const step = mobile ? 1 : 2;
  stage?.scrollIntoView({ block: "start", behavior: "auto" });
  if (!current || Math.abs(target - from) !== step || matchMedia("(prefers-reduced-motion: reduce)").matches) {
    dot1Redraw();
    return;
  }
  dot1FlipBusy = true;
  const next = document.createElement("div");
  next.innerHTML = dot1Spread(leaves, target, mobile);
  const incoming = next.firstElementChild;
  incoming.classList.add("entering");
  incoming.setAttribute("aria-hidden", "true");
  stage.append(incoming);
  stage.style.height = `${Math.max(current.offsetHeight, incoming.offsetHeight)}px`;
  const forward = target > from;
  const front = current.children[mobile ? 0 : forward ? 1 : 0];
  const back = incoming.children[mobile ? 0 : forward ? 0 : 1];
  const leaf = document.createElement("div");
  leaf.className = `dot1-turn-leaf ${forward ? "forward" : "backward"}`;
  const frontFace = document.createElement("div"), backFace = document.createElement("div");
  frontFace.className = "dot1-turn-front";
  backFace.className = "dot1-turn-back-face";
  frontFace.append(front.cloneNode(true));
  backFace.append(back.cloneNode(true));
  leaf.append(frontFace, backFace);
  stage.append(leaf);
  current.classList.add("leaving");
  stage.classList.add("turning");
  const token = ++dot1FlipToken;
  const done = () => { if (token === dot1FlipToken) dot1Redraw(); };
  leaf.addEventListener("animationend", done, { once: true });
  leaf.classList.add("animate");
  setTimeout(done, 950); // phòng khi trình duyệt không bắn animationend
}

// Gắn sự kiện sau mỗi lần vẽ: ảnh lỗi thì bỏ khỏi dải ảnh; vuốt trên điện thoại.
function wireMenu() {
  for (const img of document.querySelectorAll(".dot1-photos img")) {
    const drop = () => img.closest("figure")?.remove();
    if (img.complete && img.naturalWidth === 0) drop();
    else img.addEventListener("error", drop, { once: true });
  }
  const stage = $("#dot1-stage");
  if (!stage || stage.dataset.wired) return;
  stage.dataset.wired = "1";
  let startX = null, startY = null;
  stage.addEventListener("pointerdown", (event) => {
    if (event.pointerType === "mouse") return;
    startX = event.clientX; startY = event.clientY;
  });
  stage.addEventListener("pointerup", (event) => {
    if (startX === null) return;
    const dx = event.clientX - startX, dy = event.clientY - startY;
    startX = null;
    if (Math.abs(dx) > 60 && Math.abs(dx) > Math.abs(dy) * 1.5) flipMenu(portalUI.menuPage + (dx < 0 ? 1 : -1) * (dot1Mobile() ? 1 : 2));
  });
  stage.addEventListener("pointercancel", () => { startX = null; });
}

async function submitMenuOrder() {
  const ui = portalUI;
  if (!ui?.menu || ui.menuBusy) return;
  const lines = Object.entries(ui.menuCart).map(([id, quantity]) => ({ item_id: Number(id), quantity }));
  if (!lines.length) return;
  ui.menuBusy = true;
  dot1Redraw();
  try {
    await api("/portal/menu/orders", { method: "POST", body: { lines, note: ui.menuNote || "" } });
    ui.menuCart = {};
    ui.menuNote = "";
    toast(t("dot1Ordered"));
  } catch (error) {
    const details = Object.values(error.field_errors || {});
    toast(details.length ? details.join(" · ") : error.message, true);
  } finally {
    ui.menuBusy = false;
    ui.menuLoadedAt = 0;
    await loadCustomerMenu();
  }
}

document.addEventListener("click", (event) => {
  const button = event.target.closest("[data-menu]");
  if (!button || button.disabled || !portalUI?.menu && button.dataset.menu !== "reload") return;
  const ui = dot1State(), action = button.dataset.menu, id = button.dataset.id;
  if (action === "reload") { ui.menuLoadedAt = 0; loadCustomerMenu(); }
  if (action === "page") flipMenu(Number(button.dataset.page));
  if (action === "flip") flipMenu(ui.menuPage + Number(button.dataset.dir) * (dot1Mobile() ? 1 : 2));
  if (action === "inc") { ui.menuCart[id] = Math.min(DOT1_MAX_QTY, (ui.menuCart[id] || 0) + 1); dot1Redraw(); }
  if (action === "dec") { const qty = (ui.menuCart[id] || 0) - 1; if (qty > 0) ui.menuCart[id] = qty; else delete ui.menuCart[id]; dot1Redraw(); }
  if (action === "to-cart") $("#dot1-cart")?.scrollIntoView({ behavior: "smooth", block: "start" });
  if (action === "order") submitMenuOrder();
});
document.addEventListener("change", (event) => {
  if (event.target.id !== "dot1-store" || !portalUI) return;
  const ui = dot1State();
  ui.menuStore = Number(event.target.value);
  ui.menuCart = {};
  ui.menuPage = 0;
  ui.menuLoadedAt = 0;
  loadCustomerMenu();
});
document.addEventListener("input", (event) => {
  if (event.target.id === "dot1-note" && portalUI) portalUI.menuNote = event.target.value.slice(0, 200);
});
document.addEventListener("keydown", (event) => {
  if (portalUI?.tab !== "menu" || !portalUI.menu || event.target.closest("input,select,textarea")) return;
  if (event.key === "ArrowRight") flipMenu(portalUI.menuPage + (dot1Mobile() ? 1 : 2));
  if (event.key === "ArrowLeft") flipMenu(portalUI.menuPage - (dot1Mobile() ? 1 : 2));
});
matchMedia("(max-width: 900px)").addEventListener("change", () => {
  if (portalUI?.tab === "menu" && portalUI.menu) dot1Redraw();
});
