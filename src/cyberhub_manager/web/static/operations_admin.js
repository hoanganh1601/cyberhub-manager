"use strict";

Object.assign(copy, {
  shifts:["Ca làm việc & két tiền","Shifts & cash drawer"],
  shiftsSub:["Mở ca, ghi thu chi, kiểm đếm và đối chiếu cuối ca","Open, reconcile and close cash shifts"],
  maintenanceOps:["Sự cố & bảo trì","Incidents & maintenance"],
  maintenanceOpsSub:["Theo dõi đầy đủ vòng đời sửa chữa máy","Track the complete machine repair lifecycle"],
  procurement:["Nhà cung cấp & nhập hàng","Suppliers & purchasing"],
  procurementSub:["Đề nghị, duyệt, đặt mua, nhận hàng và công nợ","Request, approve, receive and settle supplier purchases"],
  openShift:["Mở ca","Open shift"], closeShift:["Kiểm đếm cuối ca","Reconcile shift"],
  addExpense:["Ghi khoản chi/hoàn","Record expense/refund"], openingCash:["Tiền đầu ca","Opening cash"],
  countedCash:["Tiền mặt kiểm đếm","Counted cash"], expectedCash:["Tiền mặt dự kiến","Expected cash"],
  variance:["Chênh lệch","Variance"], shiftEmployee:["Nhân viên","Employee"],
  reportIncident:["Báo sự cố","Report incident"], incidentCode:["Mã sự cố","Incident"],
  severity:["Mức độ","Severity"], assignee:["Người xử lý","Assignee"], transition:["Cập nhật","Update"],
  suppliers:["Nhà cung cấp","Suppliers"], newSupplier:["Thêm nhà cung cấp","Add supplier"],
  purchaseRequests:["Đề nghị nhập","Purchase requests"], newRequest:["Tạo đề nghị","New request"],
  purchaseOrders:["Đơn mua hàng","Purchase orders"], payables:["Công nợ","Payables"],
  createOrder:["Tạo đơn mua","Create purchase order"], receiveGoods:["Nhận hàng","Receive goods"],
  reviewDifference:["Xác nhận chênh lệch","Review variance"], reason:["Lý do","Reason"],
  title:["Tiêu đề","Title"], description:["Mô tả","Description"],
  paymentTerms:["Hạn thanh toán (ngày)","Payment terms (days)"], quantity:["Số lượng","Quantity"],
  unitCost:["Đơn giá nhập","Unit cost"], accepted:["Nhận đủ","Accepted"], damaged:["Hỏng","Damaged"],
  missing:["Thiếu","Missing"], supplier:["Nhà cung cấp","Supplier"], dueDate:["Hạn trả","Due date"],
  payableAmount:["Số tiền nợ","Payable amount"], pay:["Thanh toán","Pay"],
});

async function loadBusinessAdmin(page, seq){
  let data;
  if(page === "shifts") data = await api("/shifts");
  if(page === "maintenanceOps") {
    const result = await Promise.all([api("/maintenance"), api("/machines")]);
    data=result[0]; data.machines=result[1];
  }
  if(page === "procurement") data = await api("/procurement");
  if(seq !== state.seq) return false;
  state.business=data; state.items=data; return true;
}

function businessAdminPage(){
  if(state.page === "shifts") return shiftPage();
  if(state.page === "maintenanceOps") return maintenancePage();
  return procurementPage();
}

function shiftPage(){
  const d=state.business, active=d.active;
  const extra=active
    ? `<button class="btn" data-business="shift-entry">${icon("wallet")}${t("addExpense")}</button><button class="btn primary" data-business="shift-close">${icon("check")}${t("closeShift")}</button>`
    : `<button class="btn primary" data-business="shift-open">${icon("plus")}${t("openShift")}</button>`;
  const totals=active ? shiftTotals(active,d.entries||[]) : null;
  const metrics=active ? `<div class="metrics">${metric("openingCash",money(active.opening_cash),"cyan","wallet")}${metric("expectedCash",money(totals.expected),"green","wallet")}${metric("CASH",money(totals.cashIn),"","wallet")}${metric("TRANSFER",money(totals.transferIn),"","wallet")}</div>` : `<div class="notice info">${t("openShift")}</div>`;
  const rows=(d.shifts||[]).map(s=>`<tr><td class="table-code">${esc(s.code)}</td><td>${esc(s.employee_name)}</td><td>${badge(s.status)}</td><td class="money">${money(s.opening_cash)}</td><td class="money">${s.expected_cash==null?"—":money(s.expected_cash)}</td><td class="money ${s.variance?"red":"green"}">${s.variance==null?"—":money(s.variance)}</td><td>${s.status==="PENDING_REVIEW"&&d.can_review?`<button class="btn small" data-business="shift-review" data-id="${s.id}">${t("reviewDifference")}</button>`:"—"}</td></tr>`).join("");
  return pageHead(extra)+metrics+`<section class="panel">${table(["code","shiftEmployee","status","openingCash","expectedCash","variance","actions"],rows)}</section>`;
}

function shiftTotals(shift,entries){let cashIn=0,cashOut=0,transferIn=0;for(const x of entries){const incoming=["RECEIPT","ADJUSTMENT_IN"].includes(x.kind);if(x.payment_method==="CASH") incoming?cashIn+=x.amount:cashOut+=x.amount;else if(incoming) transferIn+=x.amount;}return {cashIn,cashOut,transferIn,expected:shift.opening_cash+cashIn-cashOut};}

function maintenancePage(){
  const d=state.business;
  const rows=(d.incidents||[]).map(x=>`<tr><td class="table-code">${esc(x.code)}</td><td>${esc(x.machine_code)}</td><td>${badge(x.severity)}</td><td>${badge(x.status)}</td><td>${esc(x.assignee_name||"—")}</td><td>${dt(x.reported_at)}</td><td><button class="btn small" data-business="incident-transition" data-id="${x.id}">${t("transition")}</button></td></tr>`).join("");
  return pageHead(`<button class="btn primary" data-business="incident-report">${icon("plus")}${t("reportIncident")}</button>`)+`<section class="panel">${rows?table(["incidentCode","machineCode","severity","status","assignee","updated","actions"],rows):empty()}</section>`;
}

function procurementPage(){
  const d=state.business;
  const suppliers=(d.suppliers||[]).map(x=>`<tr><td class="table-code">${esc(x.code)}</td><td>${esc(x.name)}</td><td>${esc(x.phone||"—")}</td><td>${x.payment_terms_days}</td></tr>`).join("");
  const requests=(d.requests||[]).map(x=>`<tr><td class="table-code">${esc(x.code)}</td><td>${esc(x.requester_name)}</td><td>${badge(x.status)}</td><td>${esc(x.reason)}</td><td>${x.status==="PENDING"&&d.can_approve?`<button class="btn small" data-business="request-decision" data-id="${x.id}">${t("confirm")}</button>`:x.status==="APPROVED"&&d.can_approve?`<button class="btn small" data-business="order-create" data-id="${x.id}">${t("createOrder")}</button>`:"—"}</td></tr>`).join("");
  const orders=(d.orders||[]).map(x=>`<tr><td class="table-code">${esc(x.code)}</td><td>${esc(x.supplier_name)}</td><td>${badge(x.status)}</td><td class="money">${money(x.total_amount)}</td><td>${["OPEN","PARTIALLY_RECEIVED"].includes(x.status)&&d.can_receive?`<button class="btn small" data-business="goods-receive" data-id="${x.id}">${t("receiveGoods")}</button>`:"—"}</td></tr>`).join("");
  const payables=(d.payables||[]).map(x=>`<tr><td>${esc(x.receipt_code)}</td><td>${esc(x.supplier_name)}</td><td class="money">${money(x.amount)}</td><td>${esc(x.due_date)}</td><td>${badge(x.status)}</td><td>${x.status==="UNPAID"&&d.can_pay?`<button class="btn small" data-business="payable-pay" data-id="${x.id}">${t("pay")}</button>`:"—"}</td></tr>`).join("");
  const actions=`${d.can_manage_suppliers?`<button class="btn" data-business="supplier-new">${t("newSupplier")}</button>`:""}<button class="btn primary" data-business="request-new">${t("newRequest")}</button>`;
  return `<div class="procurement-page">${pageHead(actions)}<div class="procurement-grid"><section class="panel"><header class="panel-heading"><h3>${t("suppliers")}</h3></header>${suppliers?table(["code","supplier","phone","paymentTerms"],suppliers):empty()}</section><section class="panel"><header class="panel-heading"><h3>${t("purchaseRequests")}</h3></header>${requests?table(["code","shiftEmployee","status","reason","actions"],requests):empty()}</section><section class="panel"><header class="panel-heading"><h3>${t("purchaseOrders")}</h3></header>${orders?table(["code","supplier","status","amount","actions"],orders):empty()}</section><section class="panel"><header class="panel-heading"><h3>${t("payables")}</h3></header>${payables?table(["code","supplier","payableAmount","dueDate","status","actions"],payables):empty()}</section></div></div>`;
}

function businessModal(kind,title,content,extra={}){ modal(title,"",content,"business",{business:kind,...extra}); }
function selectHtml(name,options){return `<label><span>${t(name)}</span><select class="input" name="${name}" required>${options}</select></label>`;}
function numberHtml(name,label,value=0,min=0){return `<label><span>${t(label)} <span class="cyan">*</span></span><input class="input" name="${name}" value="${value}" type="number" step="1" min="${min}" required><span class="field-error" data-error="${name}"></span></label>`;}
function optionalHtml(name,label,type="text"){return `<label><span>${t(label)}</span><input class="input" name="${name}" type="${type}"><span class="field-error" data-error="${name}"></span></label>`;}

document.addEventListener("click",event=>{
  const b=event.target.closest("[data-business]"); if(!b)return;
  const kind=b.dataset.business,id=Number(b.dataset.id||0),d=state.business;
  if(kind==="shift-open") businessModal(kind,"openShift",numberHtml("opening_cash","openingCash"));
  if(kind==="shift-close") businessModal(kind,"closeShift",numberHtml("counted_cash","countedCash"));
  if(kind==="shift-entry") businessModal(kind,"addExpense",selectHtml("kind",`<option value="EXPENSE">EXPENSE</option><option value="REFUND">REFUND</option>`)+selectHtml("payment_method",`<option value="CASH">${t("CASH")}</option><option value="TRANSFER">${t("TRANSFER")}</option>`)+field("amount","amount","","number")+field("note","reason"));
  if(kind==="shift-review") businessModal(kind,"reviewDifference",field("note","reason"),{id});
  if(kind==="incident-report") businessModal(kind,"reportIncident",selectHtml("machine_id",(d.machines||[]).map(x=>`<option value="${x.machine_id}">${esc(x.machine_code)} · ${esc(x.name)}</option>`).join(""))+selectHtml("severity",["LOW","MEDIUM","HIGH","CRITICAL"].map(x=>`<option>${x}</option>`).join(""))+field("title","title")+`<label class="wide"><span>${t("description")}</span><textarea class="input" name="description" required></textarea></label>`);
  if(kind==="incident-transition") showIncidentTransition(id);
  if(kind==="supplier-new") businessModal(kind,"newSupplier",field("code","code")+field("name","supplier")+optionalHtml("phone","phone")+optionalHtml("email","email","email")+optionalHtml("address","address")+numberHtml("payment_terms_days","paymentTerms"));
  if(kind==="request-new") businessModal(kind,"newRequest",field("reason","reason")+selectHtml("ingredient_id",(d.ingredients||[]).map(x=>`<option value="${x.id}">${esc(x.name)} (${esc(x.unit)})</option>`).join(""))+field("quantity","quantity","","number"));
  if(kind==="request-decision") businessModal(kind,"confirm",selectHtml("approve",`<option value="true">APPROVE</option><option value="false">REJECT</option>`),{id});
  if(kind==="order-create") showOrderCreate(id);
  if(kind==="goods-receive") showGoodsReceive(id);
  if(kind==="payable-pay") businessModal(kind,"pay",selectHtml("method",`<option value="CASH">${t("CASH")}</option><option value="TRANSFER">${t("TRANSFER")}</option>`),{id});
});

function showIncidentTransition(id){const x=state.business.incidents.find(v=>v.id===id);let targets=[];if(x.status==="REPORTED")targets=["ASSIGNED","CANCELLED"];if(x.status==="ASSIGNED")targets=["IN_PROGRESS","CANCELLED"];if(x.status==="IN_PROGRESS")targets=["COMPLETED","WAITING_PARTS"];if(x.status==="WAITING_PARTS")targets=["COMPLETED","IN_PROGRESS"];if(x.status==="COMPLETED")targets=["VERIFIED","IN_PROGRESS"];let html=selectHtml("status",targets.map(v=>`<option>${v}</option>`).join(""));if(x.status==="REPORTED"&&state.business.can_manage)html+=selectHtml("assigned_to",state.business.employees.map(e=>`<option value="${e.id}">${esc(e.full_name)}</option>`).join(""));html+=field("note","reason");if(targets.includes("COMPLETED"))html+=field("resolution","description")+numberHtml("labor_cost","amount")+optionalHtml("part_name","title")+numberHtml("part_quantity","quantity",1,1)+numberHtml("part_unit_cost","unitCost");businessModal("incident-transition","transition",html,{id});}
function showOrderCreate(id){const r=state.business.requests.find(x=>x.id===id);const costs=r.lines.map(x=>`<label><span>${esc(x.ingredient_name)} · ${x.quantity} ${esc(x.unit)}</span><input class="input" name="cost_${x.ingredient_id}" type="number" min="1" required></label>`).join("");businessModal("order-create","createOrder",selectHtml("supplier_id",state.business.suppliers.filter(x=>x.is_active).map(x=>`<option value="${x.id}">${esc(x.name)}</option>`).join(""))+costs,{id});}
function showGoodsReceive(id){const o=state.business.orders.find(x=>x.id===id);const lines=o.lines.map(x=>{const remaining=x.quantity-x.received_quantity-x.damaged_quantity;return `<fieldset><legend>${esc(x.ingredient_name)} · còn ${remaining}</legend><input name="accepted_${x.ingredient_id}" class="input" type="number" min="0" value="${remaining}"><input name="damaged_${x.ingredient_id}" class="input" type="number" min="0" value="0"><input name="missing_${x.ingredient_id}" class="input" type="number" min="0" value="0"></fieldset>`}).join("");businessModal("goods-receive","receiveGoods",lines+field("note","reason"),{id});}

async function submitBusinessModal(context,values){
  busyModal(true);
  try{
    let url,method="POST",payload={...values};
    if(context.business==="shift-open"){url="/shifts/open";payload.opening_cash=Number(values.opening_cash);}
    if(context.business==="shift-close"){url="/shifts/close";payload.counted_cash=Number(values.counted_cash);}
    if(context.business==="shift-entry"){url="/shifts/entries";payload.amount=Number(values.amount);}
    if(context.business==="shift-review")url=`/shifts/${context.id}/review`;
    if(context.business==="incident-report"){url="/maintenance";payload.machine_id=Number(values.machine_id);}
    if(context.business==="incident-transition"){url=`/maintenance/${context.id}/transition`;payload.assigned_to=values.assigned_to?Number(values.assigned_to):null;payload.labor_cost=Number(values.labor_cost||0);payload.parts=values.part_name?[{name:values.part_name,quantity:Number(values.part_quantity),unit_cost:Number(values.part_unit_cost)}]:[];}
    if(context.business==="supplier-new"){url="/procurement/suppliers";payload.payment_terms_days=Number(values.payment_terms_days);payload.is_active=true;}
    if(context.business==="request-new"){url="/procurement/requests";payload={reason:values.reason,lines:[{ingredient_id:Number(values.ingredient_id),quantity:Number(values.quantity)}]};}
    if(context.business==="request-decision"){url=`/procurement/requests/${context.id}/decision`;payload={approve:values.approve==="true"};}
    if(context.business==="order-create"){const r=state.business.requests.find(x=>x.id===context.id);url="/procurement/orders";payload={request_id:context.id,supplier_id:Number(values.supplier_id),expected_at:null,lines:r.lines.map(x=>({ingredient_id:x.ingredient_id,quantity:x.quantity,unit_cost:Number(values[`cost_${x.ingredient_id}`])}))};}
    if(context.business==="goods-receive"){const o=state.business.orders.find(x=>x.id===context.id);url=`/procurement/orders/${context.id}/receipts`;payload={request_id:crypto.randomUUID(),note:values.note||"",lines:o.lines.filter(x=>x.received_quantity+x.damaged_quantity<x.quantity).map(x=>({ingredient_id:x.ingredient_id,accepted_quantity:Number(values[`accepted_${x.ingredient_id}`]||0),damaged_quantity:Number(values[`damaged_${x.ingredient_id}`]||0),missing_quantity:Number(values[`missing_${x.ingredient_id}`]||0)}))};}
    if(context.business==="payable-pay"){url=`/procurement/payables/${context.id}/pay`;payload={method:values.method};}
    await api(url,{method,body:payload}); state.busy=false;closeModal(true);await loadPage(true);toast(t("success"));
  }catch(error){busyModal(false);formError(error);}
}
