"use strict";
// Both workspaces use the same authenticated, CSRF-protected business APIs.
Object.assign(copy, {
  type:["Loại giao dịch","Transaction type"], COMPLETED:["Đã hoàn tất","Completed"],
  transactionAmount:["Số tiền","Amount"], machine:["Máy","Machine"],
  employees:["Nhân viên","Employees"], promotions:["Khuyến mãi","Promotions"], stores:["Cơ sở","Stores"],
  employeesSub:["Tài khoản, vai trò và quyền truy cập theo cơ sở","Accounts, roles and store access"],
  promotionsSub:["Thưởng theo mốc nạp · chỉ áp dụng một chính sách phù hợp nhất","Top-up rewards · one highest qualifying tier per payment"],
  storesSub:["Quản lý địa điểm và phạm vi vận hành","Manage locations and operating scope"],
  addNew:["Thêm mới","Add new"], store:["Cơ sở","Store"], address:["Địa chỉ","Address"],
  role:["Vai trò","Role"], name:["Tên","Name"], minimum_amount:["Mốc nạp tối thiểu","Minimum top-up"],
  bonus_percent:["Tỷ lệ thưởng (%)","Bonus (%)"], starts_at:["Bắt đầu (giờ Việt Nam)","Starts (Vietnam time)"],
  ends_at:["Kết thúc (giờ Việt Nam)","Ends (Vietnam time)"], is_active:["Kích hoạt","Enabled"],
  global:["Toàn hệ thống","All stores"], on:["Bật","On"], off:["Tắt","Off"],
  cashBalance:["Số dư chính","Principal balance"], bonusBalance:["Số dư khuyến mãi","Promotional balance"],
  bonusUsed:["Khuyến mãi đã sử dụng","Promotional credit used"], bonusAward:["Tiền khuyến mãi","Promotional credit"],
  bonusNote:["Khuyến mãi được dùng trước, không quy đổi thành tiền mặt.","Promotional credit is spent first and cannot be redeemed for cash."],
  noPolicy:["Không có chính sách phù hợp","No qualifying promotion"], PROMOTION:["Khuyến mãi","Promotion"],
  switchStore:["Chuyển cơ sở","Switch store"], export:["Xuất file","Export"], print:["In / Lưu PDF","Print / Save PDF"],
  customerPortal:["Không gian khách hàng","Customer workspace"], customerLink:["Khách hàng · Xem số dư","Customer · View my wallet"],
  customerSub:["Số dư, lịch sử sử dụng và hóa đơn của riêng bạn","Your wallet, usage history and invoices"],
  staffLink:["Về cổng nhân viên","Staff sign in"], sessions:["Phiên sử dụng","Usage sessions"],
  transactions:["Giao dịch gần đây","Recent transactions"], myInvoices:["Hóa đơn của tôi","My invoices"],
  created:["Thời gian","Time"], policyName:["Tên chính sách","Policy name"], scope:["Phạm vi","Scope"],
  period:["Thời gian áp dụng","Validity"], newPassword:["Mật khẩu mới (để trống để giữ nguyên)","New password (leave blank to keep)"],
  manageNote:["Mọi thay đổi được kiểm tra quyền và lưu lịch sử quản trị.","Changes are authorized and recorded in the administration audit."],
  demoAccounts:["Admin: admin01 · Giám đốc: giamdoc01 · Quản lý: quanly01 · Bếp: bep01","Admin: admin01 · Director: giamdoc01 · Manager: quanly01 · Kitchen: bep01"],
  resetPassword:["Đặt lại mật khẩu","Reset password"], temporaryPassword:["Mật khẩu tạm","Temporary password"],
  confirmPassword:["Xác nhận mật khẩu","Confirm password"], currentPassword:["Mật khẩu hiện tại","Current password"],
  changePassword:["Đổi mật khẩu","Change password"], passwordChangeRequired:["Bạn đang dùng mật khẩu tạm. Hãy đổi mật khẩu trước khi tiếp tục.","You are using a temporary password. Change it before continuing."],
  passwordResetNote:["Tất cả phiên cũ sẽ hết hiệu lực. Người dùng phải đổi mật khẩu tạm ở lần đăng nhập kế tiếp.","All existing sessions will be revoked. The user must change the temporary password at the next sign-in."],
  passwordResetDone:["Đã đặt lại mật khẩu và thu hồi các phiên cũ.","Password reset and old sessions revoked."],
  passwordPending:["Chờ đổi mật khẩu","Password change required"], generateTemporary:["Tạo mật khẩu tạm","Generate temporary password"],
  registerAccount:["Đăng ký tài khoản","Create account"], registerTitle:["Tạo tài khoản khách hàng","Create customer account"],
  registerSub:["Tài khoản mới có số dư 0đ. Bạn có thể nạp tiền tại quầy sau khi đăng ký.","New accounts start with a zero balance. You can top up at the counter after registration."],
  registerSuccess:["Đăng ký thành công","Account created"], confirmation:["Xác nhận mật khẩu","Confirm password"],
});
const managementKinds = ["employees","promotions","stores"];
const customerRoute = () => document.body.dataset.customerPortal === "true";
function installP1Login() {
  const form=$("#login-form");
  const link=document.createElement("a"); link.className="cyan login-hint";
  link.href=customerRoute()?"/":"/customer";link.textContent=t(customerRoute()?"staffLink":"customerLink");form.append(link);
  if(!customerRoute()) return;
  $(".login-top .eyebrow").textContent=t("customerPortal");$(".subtitle",form).textContent=t("customerSub");
  const register=document.createElement("button");register.type="button";register.className="btn full";register.dataset.p1="register";register.textContent=t("registerAccount");form.insertBefore(register,link);
  if(state.mode==="mysql"){
  }
  const demo=$(".demo-note",form);if(demo)demo.textContent=t("demo")+" · nguyenvanan / demo123";
  form.addEventListener("submit",async event=>{
    event.preventDefault();event.stopImmediatePropagation();
    const button=$("button[type=submit]",form);button.disabled=true;
    try {const data=await api("/login",{method:"POST",body:{...Object.fromEntries(new FormData(form)),kind:"customer"}});
      state.customer=data.customer;state.actor=null;await renderPortal();
    }catch(error){$("#login-error").textContent=error.message;button.disabled=false;}
  },true);
}
function showCustomerRegistration(){
  modal("registerTitle","registerSub",`<div class="form-grid">${field("full_name","fullName","")}${field("phone","phone","")}${field("username","username","")}${field("password","password","","password")}${field("confirmation","confirmation","","password")}</div><div class="notice info">${t("registerSub")}</div>`,"customer-register",{},"registerAccount");
  $("[name=full_name]",$("#modal")).setAttribute("autocomplete","name");
  $("[name=phone]",$("#modal")).setAttribute("autocomplete","tel");
  $("[name=username]",$("#modal")).setAttribute("autocomplete","username");
  for(const input of $("#modal").querySelectorAll('[type="password"]'))input.setAttribute("autocomplete","new-password");
}
function installP1Shell() {
  if(!hasPermission("switch_store") && !(state.rbacPolicy==="separated"&&state.actor?.role==="MANAGER"))return;
  const chip=$(".store-chip");chip.tabIndex=0;chip.role="button";chip.title=t("switchStore");
  chip.addEventListener("click",showStoreSwitch);
  chip.addEventListener("keydown",event=>{if(event.key==="Enter"||event.key===" "){event.preventDefault();showStoreSwitch();}});
}
function selectField(name,label,options,value){
  return `<label><span>${t(label)}</span><select name="${name}">${options.map(([key,text])=>`<option value="${esc(String(key))}" ${String(key)===String(value)?"selected":""}>${esc(text)}</option>`).join("")}</select><span class="field-error" data-error="${name}"></span></label>`;
}
function managementPage(){
  const kind=state.page;const query=state.keyword.toLocaleLowerCase();
  const all=state.items;const items=all.filter(item=>Object.values(item).join(" ").toLocaleLowerCase().includes(query));
  const storeName=id=>(state.stores||[]).find(s=>s.id===id)?.code||t("global");
  const headings=kind==="employees"?["fullName","username","role","store","status"]:kind==="stores"?["code","name","address","status"]:["policyName","minimum_amount","bonus_percent","period","scope","status"];
  const rows=items.map(item=>{
    const vals=kind==="employees"?[esc(item.full_name),esc(item.username),t(item.role.toLowerCase()),esc(storeName(item.store_id)),`${badge(item.status)}${item.credential_update_required?`<small class="amber">${t("passwordPending")}</small>`:""}`]:kind==="stores"?[esc(item.code),esc(item.name),esc(item.address),badge(item.status)]:[`${esc(item.name)}<br><small>${esc(item.code)}</small>`,money(item.minimum_amount),item.bonus_percent+"%",`${dt(item.starts_at)}<br>${dt(item.ends_at)}`,esc(storeName(item.store_id)),t(item.is_active?"on":"off")];
    const editable=kind==="employees" ? (hasPermission("manage_employee_credentials") || hasPermission("manage_employees") && item.role!=="ADMIN" && (state.actor.role==="DIRECTOR" || item.role==="STAFF")) : kind==="stores" ? hasPermission("manage_stores") : hasPermission("manage_promotions") && (hasPermission("switch_store") || item.store_id===state.actor.store_id);
    const reset=kind==="employees"&&hasPermission("manage_employee_credentials")&&item.id!==state.actor.employee_id?`<button class="btn small" data-p1="reset-password" data-id="${item.id}">${icon("lock")}${t("resetPassword")}</button>`:"";
    const assignment=kind==="employees"&&state.mode==="mysql"&&state.rbacPolicy==="separated"&&item.role==="MANAGER"&&hasPermission("manage_employee_credentials")?`<button class="btn small" data-p1="manager-assignment" data-id="${item.id}">${state.lang==="vi"?"Cơ sở được giao":"Store access"}</button>`:"";
    return `<tr>${vals.map(v=>`<td>${v}</td>`).join("")}<td><div class="actions"><button class="btn small" data-p1="edit" data-id="${item.id}" ${editable?"":"disabled"}>${icon("edit")}${t("edit")}</button>${reset}${assignment}</div></td></tr>`;
  }).join("");
  const mayCreate = kind!=="employees" || state.rbacPolicy!=="separated" || hasPermission("manage_employee_credentials");
  const profileButton = kind==="employees"&&state.mode==="mysql"&&state.rbacPolicy==="separated"&&hasPermission("manage_employees")
    ? `<button class="btn" data-p1="profile-new">${icon("plus")}${state.lang==="vi"?"Hồ sơ nhân sự":"Personnel profile"}</button>` : "";
  const pendingProfiles = kind==="employees"&&state.mode==="mysql"&&state.rbacPolicy==="separated"
    ? `<section class="panel"><header class="panel-heading"><h3>${state.lang==="vi"?"Hồ sơ nhân sự":"Personnel profiles"}</h3></header>${(state.employeeProfiles||[]).length?table(["code","fullName","store","status","actions"],(state.employeeProfiles||[]).map(p=>`<tr><td>${esc(p.code)}</td><td>${esc(p.full_name)}</td><td>${esc(storeName(p.home_store_id))}</td><td>${badge(p.employment_status)}</td><td>${hasPermission("manage_employees")?`<button class="btn small" data-p1="profile-edit" data-id="${p.id}">${t("edit")}</button>`:"—"}</td></tr>`).join("")):empty()}</section>` : "";
  return pageHead(profileButton+(mayCreate?`<button class="btn primary" data-p1="new">${icon("plus")}${t("addNew")}</button>`:""))+
    `<section class="metrics">${metric("total",String(all.length),"cyan","chart")}${metric("active",String(all.filter(x=>x.status?x.status==="ACTIVE":x.is_active).length),"green","check")}</section><div class="toolbar"><input id="local-search" class="input search" value="${esc(state.keyword)}" placeholder="${t("search")}"><span class="spacer"></span><small>${t("manageNote")}</small></div><section class="panel">${items.length?table([...headings,"actions"],rows):empty()}</section>${pendingProfiles}`;
}
function vietnamInput(value){return new Date(new Date(value).getTime()+7*3600000).toISOString().slice(0,16);}
function showManagement(item=null){
  const kind=state.page, admin=state.actor.role==="ADMIN";
  const separated=state.rbacPolicy==="separated";
  const stores=(state.stores||[]).filter(x=>x.status==="ACTIVE").map(s=>[s.id,s.code+" · "+s.name]);
  const status=()=>selectField("status","status",["ACTIVE","INACTIVE",...(kind==="employees"?["LOCKED"]:[])].map(v=>[v,t(statusKey(v))]),item?.status||"ACTIVE");
  let content;
  if(kind==="stores") content=field("code","code",item?.code||"")+field("name","name",item?.name||"")+field("address","address",item?.address||"")+status();
  else if(kind==="employees") {
    const credentials=hasPermission("manage_employee_credentials");
    const hidden=(name,value)=>`<input type="hidden" name="${name}" value="${esc(String(value))}">`;
    if(separated && item && credentials) content=field("username","username",item.username)+selectField("role","role",["ADMIN","DIRECTOR","MANAGER","STAFF","KITCHEN"].map(v=>[v,t(v.toLowerCase())]),item.role)+status()+hidden("full_name",item.full_name)+hidden("store_id",item.store_id);
    else if(separated && !item && credentials && state.mode==="mysql"){
      const pending=(state.employeeProfiles||[]).filter(p=>!p.employee_id&&p.employment_status==="ACTIVE");
      if(!pending.length){toast(state.lang==="vi"?"Cần tạo hồ sơ nhân sự trước khi cấp tài khoản":"Create a personnel profile first",true);return;}
      const first=pending[0];
      content=selectField("profile_id","fullName",pending.map(p=>[p.id,`${p.full_name} · ${storeName(p.home_store_id)}`]),first.id)
        +hidden("full_name",first.full_name)+hidden("store_id",first.home_store_id)
        +field("username","username","")+selectField("role","role",["ADMIN","DIRECTOR","MANAGER","STAFF","KITCHEN"].map(v=>[v,t(v.toLowerCase())]),"STAFF")+status()+field("password","password","","password");
    }
    else if(separated && item) content=field("full_name","fullName",item.full_name)+(state.actor.role==="DIRECTOR"?selectField("store_id","store",stores,item.store_id):hidden("store_id",item.store_id))+hidden("username",item.username)+hidden("role",item.role)+hidden("status",item.status);
    else content=field("full_name","fullName",item?.full_name||"")+field("username","username",item?.username||"")+selectField("store_id","store",stores,item?.store_id||state.actor.store_id)+selectField("role","role",(credentials?["ADMIN","DIRECTOR","MANAGER","STAFF","KITCHEN"]:["STAFF"]).map(v=>[v,t(v.toLowerCase())]),item?.role||"STAFF")+status()+(item?"":field("password","password","","password"));
  }
  else content=field("code","code",item?.code||"")+field("name","policyName",item?.name||"")+selectField("store_id","scope",hasPermission("switch_store")?[["",t("global")],...stores]:stores,item?item.store_id??"":state.actor.store_id)+field("minimum_amount","minimum_amount",item?.minimum_amount||100000,"number")+field("bonus_percent","bonus_percent",item?.bonus_percent??5,"number")+selectField("is_active","is_active",[["true",t("on")],["false",t("off")]],String(item?.is_active??true))+field("starts_at","starts_at",vietnamInput(item?.starts_at||Date.now()-60000),"datetime-local")+field("ends_at","ends_at",vietnamInput(item?.ends_at||Date.now()+30*86400000),"datetime-local");
  modal(kind,`${kind}Sub`,`<div class="form-grid">${content}</div><div class="notice info">${t(kind==="promotions"?"bonusNote":"manageNote")}</div>`,"management",{kind,id:item?.id},"save");
  if(kind==="promotions")$("[name=bonus_percent]",$("#modal")).min="0";
}
function showEmployeeProfile(profile=null){
  const stores=(state.stores||[]).filter(s=>s.status==="ACTIVE").map(s=>[s.id,s.code+" · "+s.name]);
  const content=field("full_name","fullName",profile?.full_name||"")
    +selectField("store_id","store",stores,profile?.home_store_id||state.actor.store_id)
    +selectField("employment_status","status",[["ACTIVE",t("active")],["INACTIVE",t("inactive")]],profile?.employment_status||"ACTIVE");
  modal("employees","employeesSub",`<div class="form-grid">${content}</div>`,"employee-profile",{id:profile?.id},"save");
}
async function showManagerAssignment(item){
  try{
    const assigned=await api(`/employees/${item.id}/store-assignments`);
    const stores=(state.stores||[]).filter(s=>s.status==="ACTIVE"&&s.id!==item.store_id);
    if(!stores.length){toast(state.lang==="vi"?"Chưa có cơ sở phụ":"No additional store",true);return;}
    const content=`<p>${esc(item.full_name)} · ${esc(item.username)}</p>`
      +`<p>${state.lang==="vi"?"Đã giao":"Assigned"}: ${esc(stores.filter(s=>assigned.includes(s.id)).map(s=>s.name).join(", ")||"—")}</p>`
      +selectField("store_id","store",stores.map(s=>[s.id,s.code+" · "+s.name]),stores[0].id)
      +selectField("enabled","status",[["true",state.lang==="vi"?"Giao quyền":"Grant"],["false",state.lang==="vi"?"Thu hồi":"Revoke"]],"true");
    modal("employees","employeesSub",`<div class="form-grid">${content}</div>`,"manager-assignment",{id:item.id},"save");
  }catch(error){toast(error.message,true);}
}
async function showStoreSwitch(){
  try{const stores=(await api("/stores")).filter(s=>s.status==="ACTIVE");
    modal("switchStore","storesSub",selectField("store_id","store",stores.map(s=>[s.id,s.code+" · "+s.name]),state.actor.store_id),"switch-store");
  }catch(error){toast(error.message,true);}
}
async function submitManagement(context,values){
  busyModal(true);
  try{
    if(context.action==="employee-profile"){
      values.store_id=Number(values.store_id);
      await api(`/employee-profiles${context.id?`/${context.id}`:""}`,{method:context.id?"PATCH":"POST",body:values});
      state.busy=false;closeModal();await loadPage();toast(t("success"));return;
    }
    if(context.action==="manager-assignment"){
      await api(`/employees/${context.id}/store-assignments`,{method:"POST",body:{store_id:Number(values.store_id),enabled:values.enabled==="true"}});
      state.busy=false;closeModal();await loadPage();toast(t("success"));return;
    }
    if(context.action==="reset-password"){
      await api(`/employees/${context.id}/reset-password`,{method:"POST",body:values});
      state.busy=false;closeModal();await loadPage();toast(t("passwordResetDone"));return;
    }
    if(context.action==="switch-store"){
      state.actor=(await api("/store/switch",{method:"POST",body:{store_id:Number(values.store_id)}})).actor;
      state.selected=null;state.detail=null;state.items=[];state.machines=[];state.filter="all";state.keyword="";state.tablePage=1;state.seq++;
      state.busy=false;closeModal();renderShell();await loadPage();return;
    }
    if(context.kind==="employees"){
      values.store_id=Number(values.store_id);
      if(values.profile_id)values.profile_id=Number(values.profile_id);
    }
    if(context.kind==="promotions"){
      values.store_id=values.store_id?Number(values.store_id):null;
      for(const key of ["minimum_amount","bonus_percent"])values[key]=Number(values[key]);
      values.is_active=values.is_active==="true";
      for(const key of ["starts_at","ends_at"]){
        if(!values[key])throw new Error(t("invalidDate"));values[key]=values[key]+":00+07:00";
      }
    }
    await api(`/${context.kind}${context.id?`/${context.id}`:""}`,{method:context.id?"PATCH":"POST",body:values});
    state.busy=false;closeModal();await loadPage();toast(t("success"));
  }catch(error){busyModal(false);formError(error);}
}
function showPasswordReset(item){
  modal("resetPassword","",`<div class="form-card"><strong>${esc(item.full_name)}</strong><p>${esc(item.username)} · ${t(item.role.toLowerCase())}</p></div><div class="form-grid">${field("temporary_password","temporaryPassword","","password")}${field("confirm_password","confirmPassword","","password")}</div><button class="btn small" type="button" data-p1="generate-temp">${icon("lock")}${t("generateTemporary")}</button><div class="notice info">${t("passwordResetNote")}</div>`,"reset-password",{id:item.id},"resetPassword");
}
function generateTemporaryPassword(){
  const alphabet="ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789!@#$%";
  const bytes=crypto.getRandomValues(new Uint8Array(16));
  const value=Array.from(bytes,n=>alphabet[n%alphabet.length]).join("");
  for(const name of ["temporary_password","confirm_password"]){const input=$(`[name=${name}]`,$("#modal"));input.value=value;input.type="text";}
  updateModalControls();
}
async function exportInvoice(id,format="html",download=false,portal=false){
  // Open synchronously so the print tab is allowed by browser popup controls.
  const tab=download?null:window.open("about:blank","_blank");
  try{
    const response=await fetch(`/api/${portal?"portal/":""}invoices/${id}/export?format=${format}&download=${download?1:0}`,{headers:{"X-Language":state.lang},credentials:"same-origin"});
    if(!response.ok)throw new Error((await response.json()).error.message);
    const blob=await response.blob(),url=URL.createObjectURL(blob);
    if(download){const link=document.createElement("a");link.href=url;link.download=`invoice-${id}.${format}`;link.click();}
    else if(tab){tab.opener=null;tab.location.href=url;}else{const link=document.createElement("a");link.href=url;link.target="_blank";link.click();}
    setTimeout(()=>URL.revokeObjectURL(url),60000);
  }catch(error){tab?.close();toast(error.message,true);}
}
function decorateP1Details(){
  if(state.page==="customers"&&state.detail?.customer){
    const c=state.detail.customer;const box=$(".balance-box");
    if(box)box.insertAdjacentHTML("beforeend",`<div class="key-values">${kv("cashBalance",money(c.cash_balance))}${kv("bonusBalance",`<span class="cyan">${money(c.bonus_balance)}</span>`)}</div><small>${t("bonusNote")}</small>`);
  }
  if(state.page==="invoices"&&state.detail?.invoice){
    const inv=state.detail.invoice;$(".detail-panel .panel-body")?.insertAdjacentHTML("beforeend",`<div class="key-values">${kv("bonusUsed",money(inv.bonus_used))}</div><div class="actions"><button class="btn primary small" data-p1="print" data-id="${inv.invoice_id}">${t("print")}</button><button class="btn small" data-p1="export" data-id="${inv.invoice_id}">${t("export")}</button></div>`);
  }
}
let quoteSeq=0,quoteTimer;
function installTopupQuote(){
  $("#topup-balance")?.parentElement.insertAdjacentHTML("afterend",`<div id="bonus-quote" class="notice info">${t("bonusNote")}</div>`);
}
function queueTopupQuote(){
  if(modalContext?.action!=="topup")return;
  const context=modalContext,amount=Number($("[name=amount]",$("#modal")).value),seq=++quoteSeq;
  clearTimeout(quoteTimer);
  if(!Number.isSafeInteger(amount)||amount<1||amount>100000000)return;
  quoteTimer=setTimeout(async()=>{try{
    const q=await api(`/customers/${context.id}/topup-preview`,{method:"POST",body:{amount}});
    if(seq!==quoteSeq||modalContext!==context)return;
    $("#bonus-quote").textContent=t("bonusAward")+": "+money(q.bonus_amount)+" · "+(q.promotion?.name||t("noPolicy"))+". "+t("bonusNote");
    $("#topup-balance").textContent=money(context.balance+amount+q.bonus_amount);
  }catch(error){if(seq===quoteSeq&&modalContext===context)$("#bonus-quote").textContent=error.message;}},250);
}
async function renderPortal(){
  return renderCustomerPortal();
}
document.addEventListener("click",async event=>{
  const button=event.target.closest("[data-p1]");if(!button||button.disabled)return;
  const id=Number(button.dataset.id),action=button.dataset.p1;
  if(action==="new")showManagement();
  if(action==="profile-new")showEmployeeProfile();
  if(action==="profile-edit")showEmployeeProfile((state.employeeProfiles||[]).find(x=>x.id===id));
  if(action==="manager-assignment")showManagerAssignment(state.items.find(x=>x.id===id));
  if(action==="edit")showManagement(state.items.find(x=>x.id===id));
  if(action==="reset-password")showPasswordReset(state.items.find(x=>x.id===id));
  if(action==="generate-temp")generateTemporaryPassword();
  if(action==="register")showCustomerRegistration();
  if(["print","export","portal-print","portal-export"].includes(action))exportInvoice(id,action.endsWith("export")?"csv":"html",action.endsWith("export"),action.startsWith("portal-"));
  if(action==="portal-refresh")renderPortal();
  if(action==="portal-logout"){try{await api("/logout",{method:"POST"});state.customer=null;renderLogin();}catch(error){toast(error.message,true);}}
  if(event.target.closest('[data-action="quick-amount"]'))queueTopupQuote();
});
document.addEventListener("change",event=>{
  if(event.target.name!=="profile_id"||modalContext?.kind!=="employees")return;
  const selected=(state.employeeProfiles||[]).find(p=>p.id===Number(event.target.value));
  if(!selected)return;
  $("[name=full_name]",$("#modal")).value=selected.full_name;
  $("[name=store_id]",$("#modal")).value=String(selected.home_store_id);
});
document.addEventListener("input",event=>{if(event.target.name==="amount")queueTopupQuote();});
document.addEventListener("change",event=>{if(event.target.name==="received")queueTopupQuote();});
document.addEventListener("click",event=>{if(event.target.closest('[data-action="quick-amount"]'))queueTopupQuote();});
