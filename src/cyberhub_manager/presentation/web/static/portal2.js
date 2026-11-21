"use strict";

Object.assign(copy,{
  p2Availability:["Máy trống","Available PCs"],p2Usage:["Sử dụng","Usage insights"],p2Profile:["Hồ sơ","My profile"],
  p2AvailabilitySub:["Chọn cơ sở để xem số máy còn trống theo phòng.","Choose a location to see available PCs by room type."],
  p2UsageSub:["Thời gian thực tế tại CyberHub, phân tích theo ngày và khung giờ.","Your actual time at CyberHub, by day and time of day."],
  p2ProfileSub:["Quản lý thông tin cá nhân và bảo mật tài khoản của bạn.","Manage your personal information and account security."],
  p2EveryFive:["Số máy cập nhật mỗi 5 phút","PC availability updates every 5 minutes"],
  p2NextUpdate:["Lần cập nhật tiếp theo","Next update"],p2SnapshotNote:["Số liệu tại thời điểm cập nhật, có thể thay đổi khi bạn đến cơ sở.","This is a snapshot. Availability may change before you arrive."],
  STANDARD:["Máy thường","Standard PCs"],VIP:["Phòng VIP","VIP room"],
  COUPLE:["Phòng Couple","Couple room"],SUPER_VIP:["Phòng Siêu VIP","Super VIP room"],
  p2RoomDescSTANDARD:["Khu máy phổ thông.","Standard shared PC area."],
  p2RoomDescVIP:["Ít người, nhiều tiện ích chung · khoảng 4–5 máy/phòng.","Quieter room with shared amenities · around 4–5 PCs per room."],
  p2RoomDescCOUPLE:["Dành cho hai người · 2 máy/phòng.","For two people · 2 PCs per room."],
  p2RoomDescSUPER_VIP:["Phòng riêng cho một người · 1 máy/phòng.","Private room for one person · 1 PC per room."],
  p2Available:["máy còn trống","PCs available"],p2Capacity:["Tổng máy loại này","Total PCs in this category"],
  p2HourlyPrice:["Giá mỗi máy / giờ","Price per PC / hour"],
  p2NoCapacity:["Cơ sở chưa có máy thuộc loại phòng này.","This location has no PCs in this room category yet."],
  p2NoStores:["Chưa có cơ sở đang hoạt động","No active locations"],
  p2RoomNote:["Chỉ tính máy đang phục vụ, không có phiên sử dụng và không bảo trì.","Includes active PCs that have no running session and are not under maintenance."],
  p2NoBooking:["Liên hệ quầy tại cơ sở để được sắp xếp máy khi đến.","Visit the location's counter to be assigned a PC on arrival."],
  p2Daily:["Thời gian theo ngày","Time by day"],p2Hours:["Khung giờ quen thuộc","Your usual hours"],
  p2Weekdays:["Nhịp sử dụng trong tuần","Your weekly pattern"],p2Locations:["Cơ sở bạn ghé thăm","Your locations"],
  p2Sessions:["Phiên trong kỳ","Sessions in this period"],p2Average:["Trung bình mỗi phiên","Average session"],
  p2Longest:["Phiên dài nhất trong kỳ","Longest session in period"],p2Machines:["Số máy đã trải nghiệm","PCs used"],
  p2UsageRule:["Tính thời gian thực của phiên đang chơi và đã hoàn tất; chia đúng theo giờ Việt Nam, chỉ lấy phần nằm trong kỳ. Không tính phiên hủy.","Actual time from live and completed sessions, split in Vietnam time and clipped to this period. Cancelled sessions are excluded."],
  p2HourRule:["Tổng thời gian thực sự sử dụng trong mỗi khung giờ, không chỉ đếm giờ bắt đầu phiên.","Actual time spent in each hour, rather than only session start times."],
  p2Mon:["Thứ Hai","Monday"],p2Tue:["Thứ Ba","Tuesday"],p2Wed:["Thứ Tư","Wednesday"],p2Thu:["Thứ Năm","Thursday"],p2Fri:["Thứ Sáu","Friday"],p2Sat:["Thứ Bảy","Saturday"],p2Sun:["Chủ Nhật","Sunday"],
  p2Details:["Thông tin cá nhân","Personal information"],p2Security:["Đổi mật khẩu","Change password"],
  p2MemberSince:["Tham gia từ","Member since"],p2Identity:["Thông tin tài khoản","Account details"],
  p2CurrentPassword:["Mật khẩu hiện tại","Current password"],p2NewPassword:["Mật khẩu mới","New password"],
  p2Confirm:["Xác nhận mật khẩu mới","Confirm new password"],p2SaveProfile:["Lưu hồ sơ","Save profile"],
  p2Saved:["Đã cập nhật hồ sơ","Profile updated"],p2PasswordSaved:["Đã đổi mật khẩu. Các phiên đăng nhập khác đã hết hiệu lực.","Password changed. Other sign-in sessions have been revoked."],
  p2PasswordHint:["Từ 6 ký tự, tối đa 72 byte UTF-8. Dùng mật khẩu khác mật khẩu hiện tại.","At least 6 characters and up to 72 UTF-8 bytes. Choose a different password."],
  p2ConfirmEdit:["Nhập mật khẩu hiện tại để xác nhận thay đổi thông tin.","Enter your current password to confirm profile changes."],
  p2SecurityNote:["Phiên hiện tại được giữ lại sau khi đổi mật khẩu; các phiên khác cần đăng nhập lại.","Your current session stays signed in after a password change; other sessions must sign in again."],
  p2RoomSettings:["Phân phòng máy","PC room categories"],p2RoomSettingsNote:["Chọn phòng cho từng máy. Thay đổi được lưu ngay; máy đang dùng phải kết thúc phiên trước.","Assign each PC to a room category. Changes save immediately; running sessions must finish first."],
  p2RoomFilter:["Loại máy","PC category"],
  p2RoomSaved:["Đã cập nhật loại phòng","Room category updated"],p2ConfirmMismatch:["Xác nhận mật khẩu không khớp","Passwords do not match"],
  p2Stale:["Chưa lấy được cập nhật mới. Vui lòng kiểm tra thời điểm số liệu và thử làm mới.","The latest update could not be loaded. Check the snapshot time and try refreshing."],
});

async function loadCustomerPhase2(ui,stores){
  if(ui.tab==='member')return api('/portal/member?page='+ui.memberPage);
  if(ui.tab==="usage")return api("/portal/usage?days="+ui.days);
  if(ui.tab==="profile")return api("/portal/profile");
  if(ui.tab!=="availability")return null;
  const store=stores.some(s=>s.id===ui.availabilityStore)?ui.availabilityStore:stores[0]?.id;
  if(store===undefined){ui.availabilityStore=null;return null;}
  ui.availabilityStore=store;
  const cached=ui.availabilityCache[store];
  if(cached && Date.now()-cached.fetchedAt<300000)return cached.data;
  const customer=state.customer;
  const data=await api("/portal/availability?store_id="+store);
  if(state.customer===customer){ui.availabilityCache[store]={data,fetchedAt:Date.now()};ui.availabilityError=false;}
  return data;
}
function customerPortalRefreshDelay(ui){
  // Status notifications must refresh promptly even while availability is open.
  return 30000;
}
function customerPhase2Page(){
  if(portalUI.tab==='member')return customerMemberPage();
  return portalUI.tab==="availability"?(portalUI.availabilityError?`<p class="pc-card amber" role="status">${t("p2Stale")}</p>`:"")+p2Availability():portalUI.tab==="usage"?p2Usage():p2Profile();
}
function p2Availability(){
  const d=portalUI.phase2?.store_id===portalUI.availabilityStore?portalUI.phase2:null,stores=portalUI.data.stores;
  if(!stores.length)return `<section class="pc-card">${pcEmpty("p2NoStores",null,"store")}</section>`;
  return `<section class="p2-availability-toolbar pc-card"><label class="pc-field"><span>${t("store")}</span><select id="p2-availability-store">${stores.map(s=>`<option value="${s.id}" ${s.id===portalUI.availabilityStore?"selected":""}>${esc(s.code+" · "+s.name)}</option>`).join("")}</select></label><div class="p2-update-note">${icon("clock")}<div><strong>${t("p2EveryFive")}</strong><p>${t("pcUpdated")}: ${dt(d?.as_of)}</p><p>${t("p2NextUpdate")}: ${dt(d?.next_update_at)}</p></div></div></section>
    <div class="p2-rooms">${(d?.rooms||[]).map(room=>`<article class="pc-card p2-room ${room.room_type.toLowerCase()}"><header><span class="p2-room-icon">${icon(room.room_type==="VIP"||room.room_type==="SUPER_VIP"?"shield":room.room_type==="COUPLE"?"users":"monitor")}</span><span class="badge ${room.room_type==="VIP"||room.room_type==="SUPER_VIP"?"amber":""}">${t(room.room_type)}</span></header><h2>${t(room.room_type)}</h2><p class="p2-room-description">${t("p2RoomDesc"+room.room_type)}</p><div class="p2-room-number ${room.available?"cyan":"muted"}">${room.available}</div><p>${t("p2Available")}</p><div class="p2-room-capacity"><span>${t("p2Capacity")}</span><strong>${room.total}</strong></div>${room.min_hourly_rate!=null?`<div class="p2-room-price"><span>${t("p2HourlyPrice")}</span><strong>${money(room.min_hourly_rate)}${room.max_hourly_rate!==room.min_hourly_rate?` – ${money(room.max_hourly_rate)}`:""}</strong></div>`:""}<meter min="0" max="${Math.max(1,room.total)}" value="${room.available}" aria-label="${t(room.room_type)}: ${room.available} / ${room.total}"></meter>${!room.total?`<p class="pc-fine">${t("p2NoCapacity")}</p>`:""}</article>`).join("")}</div><section class="pc-card p2-availability-note">${icon("store")}<div><h3>${esc(d?.store_name||"")}</h3><p>${t("p2SnapshotNote")}</p><p>${t("p2RoomNote")}</p><strong>${t("p2NoBooking")}</strong></div></section>`;
}

function p2Usage(){
  const d=portalUI.phase2;
  if(!d)return pcEmpty("loading",null);
  const stats=[["pcTime",duration(d.usage_seconds),"clock"],["p2Sessions",d.sessions,"monitor"],["p2Average",duration(d.average_seconds),"chart"],["p2Longest",duration(d.longest_seconds),"clock"]];
  const weekdays=["p2Mon","p2Tue","p2Wed","p2Thu","p2Fri","p2Sat","p2Sun"];
  return `<section class="pc-stats">${stats.map(([label,value,symbol])=>`<article class="pc-stat"><div class="pc-stat-label">${t(label)}${icon(symbol)}</div><strong class="cyan">${value}</strong></article>`).join("")}</section><section class="pc-card"><header><div><h2>${t("p2Daily")}</h2><p class="muted">${pcDate(d.date_from)} – ${pcDate(d.date_to)} · ${t("pcChartNote")}</p></div><span class="badge">${t("p2Machines")}: ${d.machines}</span></header>${p2UsageChart(d.daily)}<p class="pc-fine">${t("p2UsageRule")}</p></section>
    <div class="pc-duo"><section class="pc-card"><header><h2>${t("p2Hours")}</h2></header><div class="p2-hour-grid">${d.hours.map(h=>`<div class="p2-hour ${h.usage_seconds?"used":""}" style="--p2-intensity:${Math.max(.12,h.usage_seconds/Math.max(1,...d.hours.map(x=>x.usage_seconds)))}" tabindex="0" aria-label="${h.hour}:00 – ${h.hour+1}:00: ${duration(h.usage_seconds)}"><span>${String(h.hour).padStart(2,"0")}:00</span><strong>${duration(h.usage_seconds)}</strong></div>`).join("")}</div><p class="pc-fine">${t("p2HourRule")}</p></section><section class="pc-card"><header><h2>${t("p2Weekdays")}</h2></header>${p2RankBars(d.weekdays.map(w=>({name:t(weekdays[w.weekday]),seconds:w.usage_seconds})))}</section></div><section class="pc-card"><header><h2>${t("p2Locations")}</h2></header>${d.stores.length?p2RankBars(d.stores.map(s=>({name:s.store_name,seconds:s.usage_seconds}))):pcEmpty("pcNoActivity","pcNoActivitySub","store")}</section>`;
}
function p2RankBars(items){
  const max=Math.max(1,...items.map(x=>x.seconds));
  return `<div class="p2-ranks">${items.map(x=>`<div><div><span>${esc(x.name)}</span><strong>${duration(x.seconds)}</strong></div><meter min="0" max="${max}" value="${x.seconds}" aria-label="${esc(x.name)}: ${duration(x.seconds)}"></meter></div>`).join("")}</div>`;
}
function p2UsageChart(items){
  const max=Math.max(0,...items.map(x=>x.usage_seconds));
  if(!max)return pcEmpty("pcNoActivity","pcNoActivitySub");
  const selected=items.find(x=>x.day===portalUI.usageDay)||items.findLast(x=>x.usage_seconds>0);
  const width=matchMedia("(max-width:700px)").matches?360:960,left=52,step=(width-left-15)/items.length;
  return `<div class="pc-chart-detail" aria-live="polite"><span>${pcDate(selected.day)}</span><strong>${duration(selected.usage_seconds)}</strong></div><svg class="pc-chart p2-usage-chart" viewBox="0 0 ${width} 240" role="group" aria-label="${t("p2Daily")}">${[0,.5,1].map(r=>`<line x1="${left}" y1="${190-r*156}" x2="${width-15}" y2="${190-r*156}"/><text x="${left-10}" y="${194-r*156}" text-anchor="end">${(max*r/3600).toLocaleString(state.lang==="en"?"en-GB":"vi-VN",{maximumFractionDigits:1})}h</text>`).join("")}${items.map((x,i)=>`<g><rect data-p2="usage-day" data-day="${x.day}" role="button" tabindex="0" aria-label="${pcDate(x.day)}: ${duration(x.usage_seconds)}" x="${left+(i+.17)*step}" y="${190-Math.max(2,x.usage_seconds/max*156)}" width="${step*.66}" height="${Math.max(2,x.usage_seconds/max*156)}" rx="${Math.min(4,step*.1)}" class="${x.day===selected.day?"selected":""}"><title>${pcDate(x.day)} · ${duration(x.usage_seconds)}</title></rect>${i%Math.ceil(items.length/7)===0||i===items.length-1?`<text x="${left+(i+.5)*step}" y="216" text-anchor="middle">${pcDate(x.day)}</text>`:""}</g>`).join("")}</svg>`;
}
function p2Profile(){
  const p=portalUI.phase2;if(!p)return pcEmpty("loading",null);
  const input=(name,label,type="text",value="",attrs="")=>`<label class="pc-field"><span>${t(label)}</span><input class="input" type="${type}" name="${name}" value="${esc(value)}" ${attrs} required></label>`;
  return `<section class="pc-card p2-profile-identity"><div class="pc-avatar">${esc(initials(p.full_name))}</div><div><h2>${esc(p.full_name)}</h2><p class="muted">${esc(p.username)} · ${esc(p.account_code)}</p></div>${badge(p.account_status)}<div class="p2-account-meta"><span>${t("code")}: <strong>${esc(p.customer_code)}</strong></span>${p.member_since?`<span>${t("p2MemberSince")}: <strong>${dt(p.member_since)}</strong></span>`:""}</div></section><div class="pc-duo p2-profile-forms"><section class="pc-card"><header><h2>${t("p2Details")}</h2>${icon("users")}</header><form id="p2-profile-form">${input("full_name","fullName","text",p.full_name,'autocomplete="name" minlength="2" maxlength="100"')}${input("phone","phone","tel",p.phone,'autocomplete="tel" pattern="0[0-9]{9}" maxlength="10" inputmode="numeric"')}${input("current_password","p2CurrentPassword","password","",'autocomplete="current-password"')}<p class="pc-fine">${t("p2ConfirmEdit")}</p><p class="p2-form-error" role="alert"></p><button class="btn primary full" type="submit">${icon("check")}${t("p2SaveProfile")}</button></form></section><section class="pc-card"><header><h2>${t("p2Security")}</h2>${icon("lock")}</header><form id="p2-password-form">${input("current_password","p2CurrentPassword","password","",'autocomplete="current-password"')}${input("new_password","p2NewPassword","password","",'autocomplete="new-password" minlength="6" maxlength="72"')}${input("confirmation","p2Confirm","password","",'autocomplete="new-password" minlength="6" maxlength="72"')}<p class="pc-fine">${t("p2PasswordHint")}</p><p class="p2-form-error" role="alert"></p><button class="btn primary full" type="submit">${icon("lock")}${t("p2Security")}</button></form><p class="pc-fine p2-security-note">${icon("shield")}${t("p2SecurityNote")}</p></section></div>`;
}

document.addEventListener("change",async event=>{
  if(event.target.id==="p2-availability-store"){
    portalUI.availabilityStore=Number(event.target.value);await renderCustomerPortal();
  }
});
document.addEventListener("click",event=>{
  const target=event.target.closest('[data-p2="usage-day"]');if(!target||!portalUI)return;
  portalUI.usageDay=target.dataset.day;drawCustomerPortal();
  $(`[data-p2="usage-day"][data-day="${portalUI.usageDay}"]`)?.focus({preventScroll:true});
});
document.addEventListener("keydown",event=>{
  if(event.target.matches('[data-p2="usage-day"]')&&["Enter"," "].includes(event.key)){
    event.preventDefault();event.target.dispatchEvent(new MouseEvent("click",{bubbles:true}));
  }
});
document.addEventListener("submit",async event=>{
  const form=event.target;
  if(!["p2-profile-form","p2-password-form"].includes(form.id))return;
  event.preventDefault();if(portalUI.p2Busy||!form.reportValidity())return;
  const values=Object.fromEntries(new FormData(form)),password=form.id==="p2-password-form";
  const errorBox=$(".p2-form-error",form);errorBox.textContent="";
  if(password&&values.new_password!==values.confirmation){errorBox.textContent=t("p2ConfirmMismatch");return;}
  const ui=portalUI,customer=state.customer;ui.p2Busy=true;
  const button=$("button[type=submit]",form);button.disabled=true;
  try{
    const result=await api(password?"/portal/password":"/portal/profile",{method:password?"POST":"PATCH",body:values});
    if(state.customer!==customer)return;
    state.customer=password?result.customer:{...state.customer,full_name:result.full_name};
    ++portalSequence;ui.p2Busy=false;ui.profileDirty=false;form.reset();await renderCustomerPortal();toast(t(password?"p2PasswordSaved":"p2Saved"));
  }catch(error){errorBox.textContent=Object.values(error.field_errors||{}).join(" · ")||error.message;}
  finally{ui.p2Busy=false;if(button.isConnected)button.disabled=false;}
});
document.addEventListener("input",event=>{
  if(event.target.closest("#p2-profile-form,#p2-password-form")&&portalUI)portalUI.profileDirty=true;
});
document.addEventListener("visibilitychange",()=>{
  if(!document.hidden&&state.customer&&portalUI?.tab==="availability"){
    const cached=portalUI.availabilityCache[portalUI.availabilityStore];
    if(!cached||Date.now()-cached.fetchedAt>=300000)renderCustomerPortal(true);
  }
});
matchMedia("(max-width:700px)").addEventListener("change",()=>{
  if(state.customer&&portalUI?.data&&portalUI.tab==="usage")drawCustomerPortal();
});

function installRoomManagement(){
  if(state.page!=="machines"||!isManager())return;
  const actions=$(".page-head .actions");if(!actions)return;
  const button=document.createElement("button");button.className="btn small";button.dataset.roomSettings="true";
  button.innerHTML=icon("grid")+esc(t("p2RoomSettings"));button.onclick=showRoomManagement;actions.append(button);
}
async function showRoomManagement(){
  try{
    const rooms=await api("/machine-rooms");
    const dialog=document.createElement("dialog");dialog.className="p2-room-dialog";
    dialog.setAttribute("aria-labelledby","p2-room-title");
    dialog.innerHTML=`<header><h2 id="p2-room-title">${t("p2RoomSettings")}</h2><button class="btn small" data-room-close aria-label="${t("close")}">×</button></header><p>${t("p2RoomSettingsNote")}</p><div class="p2-room-settings">${rooms.map(m=>`<label><span><strong>${esc(m.machine_code)}</strong> · ${esc(m.name)}<small>${t(statusKey(m.status))}</small></span><select data-room-machine="${m.machine_id}" data-original="${m.room_type}" ${m.status==="IN_USE"?"disabled":""}>${["STANDARD","VIP","COUPLE","SUPER_VIP"].map(k=>`<option value="${k}" ${k===m.room_type?"selected":""}>${t(k)}</option>`).join("")}</select></label>`).join("")}</div>`;
    const feedback=document.createElement("p");feedback.className="p2-room-feedback";feedback.setAttribute("role","status");feedback.setAttribute("aria-live","polite");dialog.append(feedback);
    document.body.append(dialog);dialog.addEventListener("close",()=>{dialog.remove();loadPage(true);},{once:true});
    $("[data-room-close]",dialog).onclick=()=>dialog.close();
    dialog.addEventListener("change",async event=>{
      const select=event.target;if(!select.dataset.roomMachine)return;select.disabled=true;
      try{await api(`/machines/${select.dataset.roomMachine}/room-type`,{method:"PATCH",body:{room_type:select.value}});select.dataset.original=select.value;feedback.textContent=t("p2RoomSaved");feedback.className="p2-room-feedback green";}
      catch(error){select.value=select.dataset.original;feedback.textContent=error.message;feedback.className="p2-room-feedback red";}finally{select.disabled=false;}
    });dialog.showModal();
  }catch(error){toast(error.message,true);}
}
