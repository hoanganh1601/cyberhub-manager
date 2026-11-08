"use strict";

Object.assign(paths, {
  bell: '<path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4"/>',
  gift: '<rect x="3" y="8" width="18" height="4" rx="1"/><path d="M5 12v9h14v-9M12 8v13M12 8H8a3 3 0 1 1 3-3Zm0 0h4a3 3 0 1 0-3-3Z"/>',
});
Object.assign(copy, {
  pcHome: ["Tổng quan cá nhân", "My overview"],
  pcOffers: ["Ưu đãi dành cho bạn", "Your offers"],
  pcHistory: ["Lịch sử của tôi", "My history"],
  pcNotifications: ["Thông báo", "Notifications"],
  pcHello: ["Chào bạn,", "Welcome,"],
  pcWelcome: ["Một góc riêng để theo dõi trải nghiệm tại CyberHub.", "Your space to keep track of every CyberHub visit."],
  pcDays: ["ngày", "days"],
  pcBalance: ["Số dư khả dụng", "Available balance"],
  pcSpent: ["Chi tiêu trong kỳ", "Spending this period"],
  pcTime: ["Thời gian sử dụng", "Time at CyberHub"],
  pcTopups: ["Tiền đã nạp", "Top-ups"],
  pcPaidOnly: ["Chỉ tính hóa đơn đã thanh toán", "Paid invoices only"],
  pcRealTime: ["Thời gian thực trong kỳ, gồm phiên đang chơi", "Actual time in this period, including live sessions"],
  pcNoBonus: ["Không gồm tiền thưởng và tiền bù thanh toán", "Excludes bonuses and checkout settlements"],
  pcWallet: ["Ví CyberHub của bạn", "Your CyberHub wallet"],
  pcWalletSub: ["Hai số dư, cùng một trải nghiệm.", "Two balances. One seamless experience."],
  pcPolicy: ["Khuyến mãi được trừ trước khi thanh toán, không quy đổi thành tiền mặt. Số dư đang hiển thị chưa trừ phí phiên đang chơi.", "Promotional credit is spent first and cannot be redeemed for cash. The displayed balance does not yet deduct live session charges."],
  pcExplore: ["Khám phá ưu đãi nạp tiền", "Explore top-up offers"],
  pcLive: ["Phiên đang sử dụng", "Your live session"],
  pcNoLive: ["Hẹn bạn ở phiên chơi tiếp theo", "See you at your next session"],
  pcNoLiveSub: ["Phiên đang chơi sẽ xuất hiện tại đây khi nhân viên mở máy cho bạn.", "Your live session appears here once a staff member starts it."],
  pcRemaining: ["Thời gian còn lại ước tính", "Estimated time remaining"],
  pcEstimateNote: ["Phí tạm tính được làm tròn theo phút. Thanh toán cuối cùng được xác nhận tại quầy.", "Estimated charges are rounded by minute. Final checkout is confirmed at the counter."],
  pcTrend: ["Nhịp chi tiêu của bạn", "Your spending pattern"],
  pcChartNote: ["Theo ngày, giờ Việt Nam · Chạm cột để xem chi tiết", "By day, Vietnam time · Select a bar for details"],
  pcUsage: ["Phí sử dụng", "Usage charges"],
  pcBonusUsed: ["Đã dùng từ khuyến mãi", "Paid with promotional credit"],
  pcPrincipalUsed: ["Tiền chính và tiền bù", "Principal and settlement"],
  pcAverage: ["Trung bình mỗi hóa đơn", "Average per invoice"],
  pcInvoices: ["hóa đơn đã thanh toán", "paid invoices"],
  pcNoActivity: ["Chưa có hoạt động trong khoảng thời gian này", "No activity in this period yet"],
  pcNoActivitySub: ["Khi có giao dịch, biểu đồ sẽ giúp bạn theo dõi rõ ràng hơn.", "Your activity will appear here as you use CyberHub."],
  pcLatest: ["Mới nhất dành cho bạn", "Your latest updates"],
  pcViewAll: ["Xem tất cả", "View all"],
  pcOfferIntro: ["Nạp hợp lý, chơi trọn vẹn.", "Top up smart. Enjoy more."],
  pcOfferSub: ["Ưu đãi được tính trên từng lần nạp tại cơ sở đã chọn.", "Offers apply to each individual top-up at the selected store."],
  pcAtCounter: ["Nạp tiền tại quầy", "Top up at the counter"],
  pcQuoteNote: ["Đây là công cụ xem trước. Ưu đãi thực tế được xác định tại thời điểm nhân viên xác nhận nạp tiền. Các lần nạp không cộng dồn để đạt mốc.", "This is a preview. The actual offer is determined when staff confirm the top-up. Separate top-ups do not accumulate towards a tier."],
  pcCalculate: ["Xem quyền lợi", "Preview benefits"],
  pcAmount: ["Số tiền dự định nạp", "Planned top-up"],
  pcCredit: ["Tổng cộng vào ví", "Total wallet credit"],
  pcNext: ["Tăng số tiền lần nạp này thêm", "Increase this top-up by"],
  pcToTier: ["để đạt mốc ưu đãi tiếp theo", "to reach the next offer tier"],
  pcTier: ["Cho lần nạp từ", "For a top-up from"],
  pcUntil: ["Kết thúc", "Ends"],
  pcNoOffers: ["Chưa có ưu đãi đang áp dụng", "No active offers right now"],
  pcNoOffersSub: ["Bạn vẫn có thể nạp tiền tại quầy. Các ưu đãi mới sẽ xuất hiện tại đây.", "You can still top up at the counter. New offers will appear here."],
  pcOnePolicy: ["Mỗi lần nạp áp dụng một mốc cao nhất đủ điều kiện; ưu đãi riêng của cơ sở được ưu tiên nếu cùng mốc.", "Each top-up uses one highest qualifying tier. A store offer takes precedence over a global offer at the same tier."],
  pcHistorySub: ["Tra cứu toàn bộ giao dịch, phiên sử dụng và hóa đơn của bạn.", "Browse all your transactions, sessions and invoices."],
  pcTransactions: ["Giao dịch ví", "Wallet transactions"],
  pcApply: ["Áp dụng bộ lọc", "Apply filters"],
  pcClear: ["Xóa lọc", "Clear"],
  pcFrom: ["Từ ngày", "From date"],
  pcTo: ["Đến ngày", "To date"],
  pcResults: ["kết quả", "results"],
  pcPrevious: ["Trang trước", "Previous page"],
  pcNextPage: ["Trang sau", "Next page"],
  pcPage: ["Trang", "Page"],
  pcHistoryNote: ["Ngày tính theo giờ Việt Nam, bao gồm cả hai ngày đã chọn. Phiên sử dụng lọc theo ngày bắt đầu.", "Dates use Vietnam time and include both selected dates. Sessions are filtered by start date."],
  pcNotifySub: ["Cập nhật giao dịch 30 ngày gần nhất, tối đa 50 thông báo; kèm ưu đãi và cảnh báo hiện tại.", "Updates from the last 30 days, up to 50 notifications, plus current offers and alerts."],
  pcMarkAll: ["Đánh dấu tất cả đã đọc", "Mark all as read"],
  pcMarkRead: ["Đánh dấu đã đọc", "Mark as read"],
  pcUnread: ["Chưa đọc", "Unread"],
  pcRead: ["Đã đọc", "Read"],
  pcAllRead: ["Bạn đã xem hết thông báo", "You're all caught up"],
  pcEmptyNotify: ["Chưa có thông báo mới", "No new notifications"],
  pcTopupDone: ["Nạp tiền thành công", "Top-up completed"],
  pcBonusDone: ["Đã nhận tiền khuyến mãi", "Promotional credit received"],
  pcPaid: ["Hóa đơn đã thanh toán", "Invoice paid"],
  pcVoided: ["Hóa đơn đã hủy", "Invoice voided"],
  pcVoidedNote: ["Không được tính vào chi tiêu đã thanh toán.", "Excluded from paid spending."],
  pcOfferNew: ["Ưu đãi đang áp dụng", "An offer for your next visit"],
  pcSessionLow: ["Phiên chơi sắp hết số dư", "Your session balance is running low"],
  pcSessionDepleted: ["Phiên chơi đã hết số dư", "Your session balance is depleted"],
  pcWalletLow: ["Số dư ví đang thấp", "Your wallet balance is low"],
  pcWalletLowNote: ["Số dư dưới 10.000 VND. Liên hệ quầy nếu bạn cần nạp thêm.", "Your balance is below 10,000 VND. Visit the counter to top up."],
  pcUpdated: ["Đồng bộ lúc", "Synced at"],
  pcAutomatic: ["Tự cập nhật mỗi 30 giây", "Updates every 30 seconds"],
  pcDemo: ["Bạn đang trải nghiệm dữ liệu mẫu; thay đổi chỉ lưu trong phiên demo này.", "You're exploring sample data; changes are saved only in this demo workspace."],
  CANCELLED: ["Đã hủy", "Cancelled"],
});

let portalUI = null;
let portalSequence = 0;
let portalQuoteSequence = 0;

function newPortalUI(account) {
  return {account, tab:"home", days:30, store:null, amount:100000, quote:null,
    chart:"spent", chartDay:null, kind:"transactions", status:"all", from:"", to:"", page:1,
    data:null, notices:null, history:null, unreadOnly:false,
    phase2:null, availabilityStore:null, availabilityCache:{}, p2Busy:false, usageDay:null};
}
const pcDate = value => new Intl.DateTimeFormat(state.lang === "en" ? "en-GB" : "vi-VN",
  {timeZone:"Asia/Ho_Chi_Minh",day:"2-digit",month:"2-digit"}).format(new Date(value+"T00:00:00+07:00"));
const pcEmpty = (title, sub, symbol="chart") => `<div class="pc-empty">${icon(symbol)}<h3>${t(title)}</h3>${sub?`<p>${t(sub)}</p>`:""}</div>`;
const pcButton = (tab, label, symbol) => `<button class="pc-nav-button ${portalUI.tab===tab?"selected":""}" data-portal="tab" data-tab="${tab}" aria-current="${portalUI.tab===tab?"page":"false"}">${icon(symbol)}<span>${t(label)}</span>${tab==="notifications"&&portalUI.notices?.unread?`<b class="pc-count">${portalUI.notices.unread}</b>`:""}</button>`;

async function renderCustomerPortal(silent=false) {
  clearInterval(refreshTimer);
  if(!state.customer)return;
  state.actor=null;
  const customer=state.customer, seq=++portalSequence;
  if(!portalUI || portalUI.account!==customer.account_id)portalUI=newPortalUI(customer.account_id);
  const ui=portalUI;
  if(!ui.data)$("#app").innerHTML=`<div class="pc-loading" role="status"><span class="spinner"></span><p>${t("loading")}</p><div></div><div></div><div></div></div>`;
  try {
    const query=new URLSearchParams({days:ui.days});if(ui.store!==null)query.set("store_id",ui.store);
    const historyQuery=new URLSearchParams({kind:ui.kind,status:ui.status,page:ui.page});
    if(ui.from)historyQuery.set("date_from",ui.from);if(ui.to)historyQuery.set("date_to",ui.to);
    const dashboardRequest=api("/portal/dashboard?"+query).catch(error=>{
      if(error.field_errors?.store_id){ui.store=null;return api("/portal/dashboard?days="+ui.days);}
      throw error;
    });
    const [data,notices,history,phase2]=await Promise.all([
      dashboardRequest,api("/portal/notifications"),
      ui.tab==="history"?api("/portal/history?"+historyQuery):Promise.resolve(null),
      dashboardRequest.then(data=>loadCustomerPhase2(ui,data.stores)),
    ]);
    if(seq!==portalSequence || state.customer!==customer)return;
    if(silent && (ui.p2Busy || ui.tab==="profile"&&ui.profileDirty || ui.tab!=="availability" && $(".customer-workspace input:focus,.customer-workspace select:focus")))return;
    ui.data=data;ui.notices=notices;ui.history=history;ui.store=data.store_id;ui.phase2=phase2;
    if(ui.quote?.promotion && !data.promotions.some(p=>JSON.stringify(p)===JSON.stringify(ui.quote.promotion)))ui.quote=null;
    drawCustomerPortal();
  } catch(error) {
    if(seq!==portalSequence || state.customer!==customer)return;
    if(error.code==="PERMISSION_DENIED"||error.code==="AUTH_REQUIRED") {
      state.customer=null;portalUI=null;renderLogin();
    } else if(!ui.data) {
      $("#app").innerHTML=`<div class="boot">${icon("alert")}<h2>${t("unavailable")}</h2><p>${esc(error.message)}</p><button class="btn primary" data-portal="refresh">${t("retry")}</button><button class="btn" data-p1="portal-logout">${t("logout")}</button></div>`;
    } else if(!silent) {
      const details=Object.values(error.field_errors||{});
      toast(details.length?details.join(" · "):error.message,true);
    }
    if(ui.tab==="availability"&&ui.data&&state.customer){ui.availabilityError=true;drawCustomerPortal();}
  } finally {
    if(seq===portalSequence && state.customer)refreshTimer=setInterval(()=>{
      if(!document.hidden && !ui.p2Busy && !(ui.tab==="profile"&&ui.profileDirty) && (ui.tab==="availability" || !$(".customer-workspace input:focus,.customer-workspace select:focus")))renderCustomerPortal(true);
    },customerPortalRefreshDelay(ui));
  }
}

function drawCustomerPortal() {
  const d=portalUI.data, n=portalUI.notices, tabs={home:"pcHome",offers:"pcOffers",history:"pcHistory",notifications:"pcNotifications",availability:"p2Availability",usage:"p2Usage",profile:"p2Profile"};
  document.title="CyberHub — "+t(tabs[portalUI.tab]);
  $("#app").innerHTML=`<div class="customer-workspace pc-workspace">
    <header class="portal-header pc-header"><a href="/customer" aria-label="CyberHub"><img src="/assets/cyberhub_logo_dark.png" alt="CyberHub Manager"></a>
      <span class="pc-header-caption">${t("customerPortal")}</span><span class="spacer"></span>${langControl()}
      <button class="btn pc-icon-button" data-portal="refresh" aria-label="${t("refresh")}">${icon("refresh")}</button>
      <button class="btn pc-icon-button" data-p1="portal-logout" aria-label="${t("logout")}">${icon("logout")}</button>
    </header>
    <nav class="pc-nav" aria-label="${t("customerPortal")}">${pcButton("home","pcHome","grid")}${pcButton("availability","p2Availability","monitor")}${pcButton("offers","pcOffers","gift")}${pcButton("usage","p2Usage","chart")}${pcButton("history","pcHistory","clock")}${pcButton("notifications","pcNotifications","bell")}${pcButton("profile","p2Profile","users")}</nav>
    <main id="pc-main">${state.mode==="demo"?`<p class="pc-demo">${icon("shield")}${t("pcDemo")}</p>`:""}
      <header class="pc-page-head"><div>${portalUI.tab==="home"?`<p class="pc-eyebrow">CYBERHUB · ${esc(d.wallet.account_code)}</p><h1>${t("pcHello")} <span>${esc(d.profile.full_name)}</span></h1><p>${t("pcWelcome")}</p>`:`<p class="pc-eyebrow">${esc(d.profile.full_name)} · CYBERHUB</p><h1>${t(tabs[portalUI.tab])}</h1><p>${t({offers:"pcOfferSub",history:"pcHistorySub",notifications:"pcNotifySub",availability:"p2AvailabilitySub",usage:"p2UsageSub",profile:"p2ProfileSub"}[portalUI.tab])}</p>`}</div>
        ${["home","usage"].includes(portalUI.tab)?`<div class="segment pc-period" role="group" aria-label="${t("period")}">${[7,30,90].map(days=>`<button data-portal="days" data-days="${days}" class="${portalUI.days===days?"active":""}" aria-pressed="${portalUI.days===days}">${days} ${t("pcDays")}</button>`).join("")}</div>`:`<span class="pc-avatar">${esc(initials(d.profile.full_name))}</span>`}
      </header>
      ${portalUI.tab==="home"?pcHome():portalUI.tab==="offers"?pcOffers():portalUI.tab==="history"?pcHistory():portalUI.tab==="notifications"?pcNotifications():customerPhase2Page()}
    </main><footer class="pc-footer"><span><i class="dot"></i>${t("pcUpdated")} ${dt(portalUI.tab==="availability"?portalUI.phase2?.as_of:d.as_of)}</span><span>${t(portalUI.tab==="availability"?"p2EveryFive":"pcAutomatic")} · Asia/Ho_Chi_Minh</span></footer></div>`;
  const nav=$(".pc-nav"),selected=$(".pc-nav-button.selected");if(nav&&selected)nav.scrollLeft=selected.offsetLeft-nav.offsetLeft-nav.clientWidth/2+selected.clientWidth/2;
  for(const table of document.querySelectorAll('.pc-workspace table')) {
    const headers=[...table.querySelectorAll('th')].map(h=>h.textContent);
    for(const row of table.querySelectorAll('tbody tr')) [...row.children].forEach((cell,index)=>cell.dataset.label=headers[index]);
  }
}

function pcHome() {
  const d=portalUI.data, totals=d.totals, wallet=d.wallet;
  return `<section class="pc-stats" aria-label="${t("pcHome")}">${[
    ["pcBalance",money(wallet.balance),"wallet","cyan",t("cashBalance")+" + "+t("bonusBalance")],
    ["pcSpent",money(totals.spent),"chart","",`${totals.paid_invoices} ${t("pcInvoices")}`],
    ["pcTime",duration(totals.usage_seconds),"clock","",t("pcRealTime")],
    ["pcTopups",money(totals.topped_up),"plus","green",t("pcNoBonus")],
  ].map(([label,value,symbol,color,detail])=>`<article class="pc-stat"><div class="pc-stat-label">${t(label)}${icon(symbol)}</div><strong class="${color}">${value}</strong><small>${detail}</small></article>`).join("")}</section>
    <section class="pc-duo"><article class="pc-wallet pc-card"><header><div><p class="pc-eyebrow">CYBERHUB WALLET</p><h2>${t("pcWallet")}</h2></div>${badge("ACTIVE")}</header><p class="muted">${t("pcWalletSub")}</p><div class="pc-wallet-split"><div><span>${t("cashBalance")}</span><strong>${money(wallet.cash_balance)}</strong></div><div><span>${t("bonusBalance")}</span><strong class="green">${money(wallet.bonus_balance)}</strong></div></div><p class="pc-fine">${icon("shield")}${t("pcPolicy")}</p><button class="btn primary" data-portal="tab" data-tab="offers">${icon("gift")}${t("pcExplore")}${icon("arrow")}</button></article>
      <article class="pc-card pc-live"><header><h2>${t("pcLive")}</h2>${d.active_sessions.length?`<span class="badge green"><i class="dot"></i>LIVE</span>`:""}</header>${d.active_sessions.length?d.active_sessions.map(u=>`<div class="pc-live-machine">${icon("monitor")}<div><h3>${esc(u.machine_code)}</h3><p>${esc(u.store_name)}</p></div><strong>${duration(u.elapsed_seconds)}</strong></div><div class="pc-live-values"><div><span>${t("estimated")}</span><strong>${money(u.estimated_cost)}</strong></div><div><span>${t("projected")}</span><strong class="${u.projected_balance<0?"red":"cyan"}">${money(u.projected_balance)}</strong></div><div><span>${t("pcRemaining")}</span><strong>${u.remaining_minutes} ${t("minute")}</strong></div></div>`).join(""):pcEmpty("pcNoLive","pcNoLiveSub","monitor")}<p class="pc-fine">${t("pcEstimateNote")}</p></article></section>
    <section class="pc-card pc-chart-card"><header><div><h2>${t("pcTrend")}</h2><p class="muted">${t("pcChartNote")}</p></div><div class="segment"><button data-portal="chart" data-series="spent" class="${portalUI.chart==="spent"?"active":""}">${t("pcUsage")}</button><button data-portal="chart" data-series="topped_up" class="${portalUI.chart==="topped_up"?"active":""}">${t("pcTopups")}</button></div></header>${pcChart()}<div class="pc-chart-summary"><div><span>${t("pcBonusUsed")}</span><strong class="green">${money(totals.bonus_spent)}</strong></div><div><span>${t("pcPrincipalUsed")}</span><strong>${money(totals.principal_spent)}</strong></div><div><span>${t("pcAverage")}</span><strong>${money(totals.average_invoice)}</strong></div></div><p class="pc-fine">${t("pcPaidOnly")} · ${pcDate(d.date_from)} – ${pcDate(d.date_to)}</p></section>
    <section class="pc-card"><header><h2>${t("pcLatest")}</h2><button class="btn small" data-portal="tab" data-tab="notifications">${t("pcViewAll")}${icon("arrow")}</button></header>${portalUI.notices.items.length?portalUI.notices.items.slice(0,3).map(x=>pcNotice(x,true)).join(""):pcEmpty("pcEmptyNotify",null,"bell")}</section>`;
}

function pcChart() {
  const data=portalUI.data.chart,key=portalUI.chart,maximum=Math.max(0,...data.map(x=>x[key]));
  if(!maximum)return pcEmpty("pcNoActivity","pcNoActivitySub");
  const narrow=window.matchMedia("(max-width:700px)").matches;
  const width=narrow?360:960,height=240,left=narrow?52:76,base=190,step=(width-left-15)/data.length;
  const selected=data.find(x=>x.day===portalUI.chartDay)||data.findLast(x=>x[key]>0);
  const grid=[0,.5,1].map(r=>`<line x1="${left}" y1="${base-r*156}" x2="${width-15}" y2="${base-r*156}"/><text x="${left-10}" y="${base-r*156+4}" text-anchor="end">${new Intl.NumberFormat(state.lang==="en"?"en-US":"vi-VN",{notation:"compact"}).format(maximum*r)}</text>`).join("");
  const bars=data.map((x,i)=>`<g><rect data-portal="day" data-day="${x.day}" role="button" tabindex="0" aria-label="${esc(pcDate(x.day)+": "+money(x[key]))}" x="${left+i*step+step*.17}" y="${base-Math.max(3,x[key]/maximum*156)}" width="${step*.66}" height="${Math.max(3,x[key]/maximum*156)}" rx="${Math.min(4,step*.1)}" class="${x.day===selected?.day?"selected":""}"><title>${pcDate(x.day)} · ${money(x[key])}</title></rect>${i%Math.ceil(data.length/7)===0||i===data.length-1?`<text x="${left+(i+.5)*step}" y="216" text-anchor="middle">${pcDate(x.day)}</text>`:""}</g>`).join("");
  return `<div class="pc-chart-detail" aria-live="polite"><span>${pcDate(selected.day)}</span><strong>${money(selected[key])}</strong><small>${t(key==="spent"?"pcUsage":"pcTopups")}</small></div><svg class="pc-chart" viewBox="0 0 ${width} ${height}" role="group" aria-label="${t("pcTrend")}">${grid}${bars}</svg>`;
}

function pcOffers() {
  const d=portalUI.data,q=portalUI.quote;
  return `<section class="pc-offer-banner"><div class="pc-offer-icon">${icon("gift")}</div><div><p class="pc-eyebrow">CYBERHUB REWARDS</p><h2>${t("pcOfferIntro")}</h2><p>${t("pcOnePolicy")}</p></div></section>
    <div class="pc-offer-layout"><section class="pc-card"><header><h2>${t("promotions")}</h2></header><label class="pc-field"><span>${t("store")}</span><select id="pc-store" ${d.stores.length?"":"disabled"}>${d.stores.map(s=>`<option value="${s.id}" ${s.id===d.store_id?"selected":""}>${esc(s.code+" · "+s.name)}</option>`).join("")}</select></label><div class="pc-offers">${d.promotions.length?d.promotions.map(p=>`<article class="pc-offer"><div class="pc-offer-percent">+${p.bonus_percent}<span>%</span></div><div><h3>${esc(p.name)}</h3><p>${t("pcTier")} <strong>${money(p.minimum_amount)}</strong></p><small>${t(p.store_id===null?"global":"store")} · ${t("pcUntil")} ${dt(p.ends_at)}</small></div><button class="btn small" data-portal="tier" data-amount="${p.minimum_amount}">${t("pcCalculate")}${icon("arrow")}</button></article>`).join(""):pcEmpty("pcNoOffers","pcNoOffersSub","gift")}</div><p class="pc-fine">${t("bonusNote")}</p></section>
    <section class="pc-card pc-calculator"><header><h2>${t("pcCalculate")}</h2>${icon("wallet")}</header><form id="pc-quote-form"><label class="pc-field"><span>${t("pcAmount")} (VND)</span><input class="input" type="number" name="amount" min="1" max="100000000" step="1" value="${portalUI.amount}" required inputmode="numeric"></label><div class="pc-quick-amounts">${[50000,100000,200000].map(amount=>`<button class="btn small" type="button" data-portal="tier" data-amount="${amount}">${money(amount)}</button>`).join("")}</div><button class="btn primary full" type="submit" ${d.store_id===null?"disabled":""}>${t("pcCalculate")}${icon("arrow")}</button></form><div id="pc-quote-result" aria-live="polite">${q?`<div class="pc-quote-values"><div><span>${t("pcAmount")}</span><strong>${money(q.amount)}</strong></div><div><span>${t("bonusAward")}</span><strong class="green">+${money(q.bonus_amount)}</strong></div><div class="pc-credit"><span>${t("pcCredit")}</span><strong class="cyan">${money(q.credited_total)}</strong></div></div><p class="pc-fine">${esc(q.promotion?.name||t("noPolicy"))}</p>${q.next_tier?`<div class="pc-next-tier">${icon("gift")}<p>${t("pcNext")} <strong>${money(q.amount_to_next)}</strong> ${t("pcToTier")} (${q.next_tier.bonus_percent}%).</p></div>`:""}`:""}</div><p class="pc-fine">${t("pcQuoteNote")}</p><div class="pc-counter">${icon("store")}<span>${t("pcAtCounter")}</span></div></section></div>`;
}

function pcHistory() {
  const ui=portalUI, result=ui.history;
  if(!result)return pcEmpty("loading",null);
  const statuses={transactions:["TOP_UP","PROMOTION","USAGE_PAYMENT","DEBT_SETTLEMENT"],invoices:["PAID","VOID"],sessions:["ACTIVE","COMPLETED","CANCELLED"]};
  const headings=ui.kind==="transactions"?["code","created","type","transactionAmount","paymentMethod","store"]:ui.kind==="invoices"?["invoiceCode","created","store","total","status","actions"]:["code","machine","store","startAt","endAt","status"];
  const rows=result.items.map(x=>{
    const values=ui.kind==="transactions"?[esc(x.code),dt(x.created_at),t(x.type),`<strong class="${x.amount<0?"red":"green"}">${x.amount>0?"+":""}${money(x.amount)}</strong>`,t(x.method),esc(x.store_name||"—")]:ui.kind==="invoices"?[esc(x.code),dt(x.created_at),esc(x.store_name),`<strong>${money(x.usage_cost)}</strong>`,badge(x.status),`<div class="actions"><button class="btn small" data-p1="portal-print" data-id="${x.id}">${t("print")}</button><button class="btn small" data-p1="portal-export" data-id="${x.id}">CSV</button></div>`]:[esc(x.code),esc(x.machine_code),esc(x.store_name),dt(x.started_at),dt(x.ended_at),badge(x.status)];
    return `<tr>${values.map(v=>`<td>${v}</td>`).join("")}</tr>`;
  }).join("");
  const pages=Math.max(1,Math.ceil(result.total/result.page_size));
  return `<section class="pc-card pc-history-card"><div class="pc-history-tabs segment">${["transactions","invoices","sessions"].map(k=>`<button data-portal="history-kind" data-kind="${k}" class="${ui.kind===k?"active":""}">${t({transactions:"pcTransactions",invoices:"myInvoices",sessions:"sessions"}[k])}</button>`).join("")}</div><form id="pc-history-form" class="pc-history-filters"><label class="pc-field"><span>${t("pcFrom")}</span><input class="input" type="date" name="from" value="${ui.from}"></label><label class="pc-field"><span>${t("pcTo")}</span><input class="input" type="date" name="to" value="${ui.to}"></label><label class="pc-field"><span>${t(ui.kind==="transactions"?"type":"status")}</span><select name="status">${["all",...statuses[ui.kind]].map(s=>`<option value="${s}" ${ui.status===s?"selected":""}>${t(statusKey(s))}</option>`).join("")}</select></label><button class="btn primary" type="submit">${t("pcApply")}</button><button class="btn" type="button" data-portal="history-clear">${t("pcClear")}</button></form><p class="pc-fine">${t("pcHistoryNote")}</p><div class="pc-table-wrap">${rows?table(headings,rows):pcEmpty("noResults","pcHistorySub","clock")}</div><footer class="pc-pagination"><span>${result.total} ${t("pcResults")}</span><div><button class="btn small" data-portal="history-page" data-page="${ui.page-1}" aria-label="${t("pcPrevious")}" ${ui.page<=1?"disabled":""}>‹</button><span>${t("pcPage")} ${ui.page} / ${pages}</span><button class="btn small" data-portal="history-page" data-page="${ui.page+1}" aria-label="${t("pcNextPage")}" ${ui.page>=pages?"disabled":""}>›</button></div></footer></section>`;
}

function pcNotice(item,compact=false) {
  const title={TOP_UP:"pcTopupDone",PROMOTION:"pcBonusDone",PAID:"pcPaid",VOID:"pcVoided",OFFER:"pcOfferNew",SESSION_LOW:"pcSessionLow",SESSION_DEPLETED:"pcSessionDepleted",WALLET_LOW:"pcWalletLow"}[item.kind];
  let detail=`${esc(item.code)} · ${money(item.amount)}`;
  if(item.kind==="OFFER")detail=`${esc(item.name)} · +${item.bonus_percent}% · ${t("pcTier")} ${money(item.amount)} · ${esc(item.store_name||t("global"))} · ${t("pcUntil")} ${dt(item.ends_at)}`;
  if(["SESSION_LOW","SESSION_DEPLETED"].includes(item.kind))detail=`${esc(item.code)} · ${t("pcRemaining")}: ${item.remaining_minutes} ${t("minute")} · ${t("projected")}: ${money(item.amount)}`;
  if(item.kind==="WALLET_LOW")detail=t("pcWalletLowNote");
  if(item.kind==="VOID")detail+=" · "+t("pcVoidedNote");
  const symbol=item.severity==="warning"?"alert":item.kind==="OFFER"||item.kind==="PROMOTION"?"gift":item.kind==="TOP_UP"?"wallet":"invoice";
  return `<article class="pc-notice ${item.read?"read":"unread"} ${item.severity}"><div class="pc-notice-icon">${icon(symbol)}</div><div class="pc-notice-copy"><div><h3>${t(title)}</h3>${!item.read?`<span class="pc-unread-dot" aria-label="${t("pcUnread")}"></span>`:""}</div><p>${detail}</p><small>${["SESSION_LOW","SESSION_DEPLETED","WALLET_LOW"].includes(item.kind)?t("pcUpdated")+" ":""}${dt(item.created_at)}</small></div>${!compact&&!item.read?`<button class="btn small pc-read-button" data-portal="read" data-key="${esc(item.key)}" aria-label="${t("pcMarkRead")}: ${t(title)}">${icon("check")}<span>${t("pcMarkRead")}</span></button>`:""}</article>`;
}

function pcNotifications() {
  const n=portalUI.notices,items=portalUI.unreadOnly?n.items.filter(x=>!x.read):n.items;
  return `<section class="pc-card"><header class="pc-notification-controls"><div class="segment"><button data-portal="notice-filter" data-unread="false" class="${!portalUI.unreadOnly?"active":""}">${t("all")} (${n.items.length})</button><button data-portal="notice-filter" data-unread="true" class="${portalUI.unreadOnly?"active":""}">${t("pcUnread")} (${n.unread})</button></div><button class="btn" data-portal="read-all" ${n.unread?"":"disabled"}>${icon("check")}${t("pcMarkAll")}</button></header>${items.length?items.map(x=>pcNotice(x)).join(""):pcEmpty(portalUI.unreadOnly?"pcAllRead":"pcEmptyNotify",null,"bell")}</section>`;
}

async function pcCalculateQuote() {
  const seq=++portalQuoteSequence,ui=portalUI,customer=state.customer, store=ui.store;
  const form=$("#pc-quote-form");if(!form?.reportValidity())return;
  ui.amount=Number(form.elements.amount.value);
  const amount=ui.amount,button=$("button[type=submit]",form);button.disabled=true;
  try {
    const quote=await api("/portal/topup-preview",{method:"POST",body:{store_id:store,amount}});
    if(seq!==portalQuoteSequence||state.customer!==customer||portalUI!==ui||ui.store!==store||ui.amount!==amount)return;
    ui.quote=quote;if(ui.tab==="offers")drawCustomerPortal();
  } catch(error){if(seq===portalQuoteSequence&&state.customer===customer)toast(Object.values(error.field_errors||{}).join(" · ")||error.message,true);}
  finally {if(button.isConnected)button.disabled=false;}
}

document.addEventListener("click",async event=>{
  const button=event.target.closest("[data-portal]");if(!button||button.disabled)return;
  const action=button.dataset.portal;
  if(action==="refresh"){if(portalUI?.tab==="availability")portalUI.availabilityCache={};await renderCustomerPortal();return;}
  if(!portalUI||!state.customer)return;
  try {
    if(action==="tab"){portalUI.tab=button.dataset.tab;await renderCustomerPortal();}
    if(action==="days"){portalUI.days=Number(button.dataset.days);portalUI.chartDay=null;await renderCustomerPortal();}
    if(action==="chart"){portalUI.chart=button.dataset.series;portalUI.chartDay=null;drawCustomerPortal();}
    if(action==="day"){portalUI.chartDay=button.dataset.day;drawCustomerPortal();$(`[data-portal="day"][data-day="${portalUI.chartDay}"]`)?.focus({preventScroll:true});}
    if(action==="tier"){
      portalUI.amount=Number(button.dataset.amount);$("#pc-quote-form input").value=portalUI.amount;await pcCalculateQuote();
    }
    if(action==="history-kind"){portalUI.kind=button.dataset.kind;portalUI.status="all";portalUI.page=1;await renderCustomerPortal();}
    if(action==="history-page"){portalUI.page=Number(button.dataset.page);await renderCustomerPortal();}
    if(action==="history-clear"){portalUI.from="";portalUI.to="";portalUI.status="all";portalUI.page=1;await renderCustomerPortal();}
    if(action==="notice-filter"){portalUI.unreadOnly=button.dataset.unread==="true";drawCustomerPortal();}
    if(action==="read"||action==="read-all"){
      const customer=state.customer,keys=action==="read"?[button.dataset.key]:portalUI.notices.items.filter(x=>!x.read).map(x=>x.key);
      button.disabled=true;await api("/portal/notifications/read",{method:"POST",body:{keys}});
      if(state.customer===customer)await renderCustomerPortal();
    }
  }catch(error){toast(error.message,true);if(button.isConnected)button.disabled=false;}
});
document.addEventListener("submit",async event=>{
  if(event.target.id==="pc-quote-form"){event.preventDefault();await pcCalculateQuote();}
  if(event.target.id==="pc-history-form"){
    event.preventDefault();const form=event.target;
    portalUI.from=form.elements.from.value;portalUI.to=form.elements.to.value;
    portalUI.status=form.elements.status.value;portalUI.page=1;await renderCustomerPortal();
  }
});
document.addEventListener("change",async event=>{
  if(event.target.id==="pc-store"){
    portalUI.store=Number(event.target.value);portalUI.quote=null;++portalQuoteSequence;await renderCustomerPortal();
  }
});
document.addEventListener("input",event=>{
  if(event.target.closest("#pc-quote-form")){
    portalUI.amount=Number(event.target.value);portalUI.quote=null;++portalQuoteSequence;
    $("#pc-quote-result").replaceChildren();
  }
});
document.addEventListener("keydown",event=>{
  if(event.target.matches('[data-portal="day"]')&&["Enter"," "].includes(event.key)){
    event.preventDefault();event.target.dispatchEvent(new MouseEvent("click",{bubbles:true}));
  }
});
window.matchMedia("(max-width:700px)").addEventListener("change",()=>{
  if(state.customer&&portalUI?.data&&portalUI.tab==="home")drawCustomerPortal();
});
