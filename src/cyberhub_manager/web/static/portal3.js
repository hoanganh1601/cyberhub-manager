"use strict";
Object.assign(paths,{camera:'<path d="M4 6h4l2-3h4l2 3h4v15H4z"/><circle cx="12" cy="13" r="4"/>'});
Object.assign(copy,{
  BRONZE:['Đồng','Bronze'],SILVER:['Bạc','Silver'],GOLD:['Vàng','Gold'],PLATINUM:['Kim cương','Diamond'],
  p3Account:['Menu tài khoản','Account menu'],p3EditProfile:['Chỉnh sửa hồ sơ','Edit profile'],
  p3Avatar:['Cập nhật ảnh đại diện','Update profile photo'],p3AvatarSub:['Ảnh sẽ được căn giữa và lưu ở dạng vuông.','Your image will be centered and saved as a square.'],
  p3ChooseImage:['Chọn ảnh từ thiết bị','Choose an image'],p3ImageHint:['JPEG, PNG hoặc WebP tĩnh · Tối đa 2 MB, 16 triệu điểm ảnh','Static JPEG, PNG or WebP · Up to 2 MB and 16 megapixels'],
  p3SaveImage:['Lưu ảnh đại diện','Save photo'],p3RemoveImage:['Xóa ảnh hiện tại','Remove current photo'],
  p3ImageSaved:['Đã cập nhật ảnh đại diện','Profile photo updated'],p3ImageRemoved:['Đã xóa ảnh đại diện','Profile photo removed'],
  p3Member:['Thành viên','Membership'],p3MemberSub:['Tích điểm từ trải nghiệm, nhận ưu đãi phù hợp với bạn.','Earn points from your visits and discover offers for you.'],
  p3Points:['Điểm tích lũy','Reward points'],p3Spend:['Chi tiêu xét hạng','Qualifying spend'],
  p3CurrentTier:['Hạng hiện tại','Current tier'],p3NextTier:['Hạng tiếp theo','Next tier'],p3Remaining:['Chi tiêu hợp lệ còn lại','Remaining qualifying spend'],
  p3Highest:['Bạn đã đạt hạng cao nhất','You have reached the highest tier'],
  p3PointsRule:['Mỗi hóa đơn đã thanh toán: phần phí trả bằng tiền chính/tiền bù được tính điểm, làm tròn xuống. Tiền nạp và phần khuyến mãi không tính điểm.','For each paid invoice: earn points on charges paid with principal or settlement, rounded down. Top-ups and promotional credit do not earn points.'],
  p3NoCash:['Điểm không phải số dư ví và chưa quy đổi thành tiền.','Points are separate from your wallet and cannot be redeemed for money.'],
  p3Voids:['Hóa đơn hủy không tính điểm hoặc chi tiêu xét hạng.','Voided invoices do not count towards points or tier spend.'],
  p3EarnRate:['Chi tiêu hợp lệ / 1 điểm','Qualifying spend / 1 point'],p3Paused:['Đang tạm dừng tích điểm cho hóa đơn mới','Point earning is paused for new invoices'],
  p3RuleVersion:['Phiên bản quy tắc','Rule version'],p3PointHistory:['Lịch sử ghi nhận điểm','Point history'],
  p3EffectivePoints:['Điểm được tính','Counted points'],p3InvoiceRule:['Quy tắc tại thời điểm hóa đơn','Rule at checkout'],
  p3Personal:['Ưu đãi dành riêng','Personalized offer'],p3MinTier:['Hạng tối thiểu','Minimum tier'],p3MinPoints:['Điểm tối thiểu','Minimum points'],
  p3CustomerTarget:['Dành riêng cho khách hàng','Specific customer'],p3AllEligible:['Tất cả khách đủ điều kiện','All eligible customers'],
  p3AudienceNote:['Ưu đãi được xét theo hạng, điểm và đối tượng tại thời điểm nạp tiền; mỗi lần nạp chỉ áp dụng một chính sách.','Eligibility is checked by tier, points and audience at top-up time; only one policy applies per top-up.'],
  p3PointsEligibility:['Điểm dùng để xét điều kiện ưu đãi, không bị trừ khi nhận ưu đãi.','Points determine offer eligibility and are not deducted when an offer is applied.'],
  p3Policy:['Cấu hình thành viên','Membership settings'],p3PolicySub:['Điểm của hóa đơn cũ giữ nguyên; mốc hạng mới áp dụng cho chi tiêu hợp lệ hiện có.','Existing invoice points stay unchanged; new tier thresholds apply to current qualifying spend.'],
  p3Enabled:['Tích điểm cho hóa đơn mới','Earn points on new invoices'],unit_amount:['Số VND hợp lệ / 1 điểm','Qualifying VND per point'],
  silver_spend:['Mốc hạng Bạc (VND)','Silver threshold (VND)'],gold_spend:['Mốc hạng Vàng (VND)','Gold threshold (VND)'],platinum_spend:['Mốc hạng Kim cương (VND)','Diamond threshold (VND)'],
  p3PolicySaved:['Đã cập nhật cấu hình thành viên','Membership settings updated'],p3PhotoPreview:['Xem trước ảnh đại diện','Profile photo preview'],
});

function customerAvatar(className=''){
  const d=portalUI.data;
  return `<span class="p3-avatar ${className}" data-tier="${d.member.tier}">${d.avatar_version?`<img src="/api/portal/avatar?v=${encodeURIComponent(d.avatar_version)}" alt="${esc(d.profile.full_name)}" data-customer-avatar>`:`<span>${esc(initials(d.profile.full_name))}</span>`}</span>`;
}
function customerAccountMenu(){
  const d=portalUI.data;
  return `<div class="p3-account-wrap"><button class="p3-account-toggle" id="p3-account-toggle" data-p3="account" aria-haspopup="menu" aria-expanded="false" aria-controls="p3-account-menu" aria-label="${t('p3Account')}">${customerAvatar()}<span class="p3-avatar-chevron">⌄</span></button><div class="p3-account-menu" id="p3-account-menu" role="menu" aria-label="${t('p3Account')}" hidden><div class="p3-menu-person">${customerAvatar()}<div><strong>${esc(d.profile.full_name)}</strong><small>${esc(d.profile.username)} · ${t(d.member.tier)}</small></div></div><button role="menuitem" data-portal="tab" data-tab="profile">${icon('users')}${t('p3EditProfile')}</button><button role="menuitem" data-p3="avatar">${icon('camera')}${t('p3Avatar')}</button><button role="menuitem" data-portal="tab" data-tab="member">${icon('shield')}${t('p3Member')}<span class="p3-menu-points">${d.member.points} ${t('p3Points')}</span></button><button role="menuitem" data-p3="security">${icon('lock')}${t('p2Security')}</button><div class="divider"></div><button role="menuitem" data-p1="portal-logout">${icon('logout')}${t('logout')}</button></div></div>`;
}
function closeCustomerAccount(focus=false){
  if(portalUI)portalUI.accountMenuOpen=false;
  const menu=$('#p3-account-menu'),button=$('#p3-account-toggle');if(menu)menu.hidden=true;
  if(button){button.setAttribute('aria-expanded','false');if(focus)button.focus();}
}
function decorateCustomerMembership(){
  const d=portalUI.data,m=d.member;
  if(portalUI.accountMenuOpen){$('#p3-account-menu').hidden=false;$('#p3-account-toggle').setAttribute('aria-expanded','true');}
  if(portalUI.tab==='profile'){
    const avatar=$('.p2-profile-identity .pc-avatar');
    if(avatar)avatar.outerHTML=`<button class="p3-profile-avatar" data-p3="avatar" aria-label="${t('p3Avatar')}">${customerAvatar('large')}<span class="p3-avatar-edit">${icon('camera')}</span></button>`;
  }
  if(portalUI.tab==='home')$('.pc-stats')?.insertAdjacentHTML('afterend',`<section class="pc-card p3-member-teaser"><span class="p3-tier-icon" data-tier="${m.tier}">${icon('shield')}</span><div><h3>${t('p3Member')} · ${t(m.tier)}</h3><p>${m.points.toLocaleString(state.lang==='en'?'en-US':'vi-VN')} ${t('p3Points')} · ${money(m.eligible_spend)} ${t('p3Spend')}</p></div><button class="btn small" data-portal="tab" data-tab="member">${t('pcViewAll')}${icon('arrow')}</button></section>`);
  if(portalUI.tab==='offers'){
    $('.pc-offers')?.insertAdjacentHTML('afterend',`<p class="pc-fine">${t('p3PointsEligibility')}</p>`);
    document.querySelectorAll('.pc-offer').forEach((node,i)=>{
      const p=d.promotions[i];if(p&&(p.minimum_tier!=='BRONZE'||p.minimum_points>0||p.target_customer_id!==null))node.querySelector('h3')?.insertAdjacentHTML('afterend',`<span class="badge cyan">${t('p3Personal')} · ${t(p.minimum_tier)} · ${p.minimum_points} ${t('p3Points')}</span>`);
    });
  }
}
function customerMemberPage(){
  const m=portalUI.phase2;if(!m)return pcEmpty('loading',null);
  const history=m.history,pages=Math.max(1,Math.ceil(history.total/history.page_size));
  return `<section class="p3-member-hero pc-card" data-tier="${m.tier}"><div><p class="pc-eyebrow">CYBERHUB MEMBERSHIP</p><h2>${t('p3CurrentTier')} · ${t(m.tier)}</h2><p>${t('p3MemberSub')}</p></div><div class="p3-hero-points"><strong>${m.points.toLocaleString(state.lang==='en'?'en-US':'vi-VN')}</strong><span>${t('p3Points')}</span></div></section><div class="pc-duo"><section class="pc-card"><header><h2>${t('p3Spend')}</h2>${icon('chart')}</header><strong class="p3-spend-value cyan">${money(m.eligible_spend)}</strong>${m.next_tier?`<div class="p3-tier-progress"><div><span>${t('p3NextTier')} · ${t(m.next_tier)}</span><strong>${m.progress_percent}%</strong></div><progress max="100" value="${m.progress_percent}" aria-label="${t('p3NextTier')}"></progress><p>${t('p3Remaining')}: <strong>${money(m.remaining_spend)}</strong></p></div>`:`<p class="green p3-tier-progress">${t('p3Highest')}</p>`}<button class="btn primary" data-portal="tab" data-tab="offers">${icon('gift')}${t('pcOffers')}${icon('arrow')}</button></section><section class="pc-card"><header><h2>${t('p3EarnRate')}</h2>${icon('shield')}</header><strong class="p3-spend-value">${money(m.unit_amount)}</strong><p class="pc-fine">${t('p3PointsRule')}</p><p class="pc-fine">${t('p3NoCash')}</p><p class="pc-fine">${t('p3Voids')}</p>${!m.enabled?`<p class="amber">${t('p3Paused')}</p>`:''}</section></div><section class="p3-tier-list">${m.tiers.map(tier=>`<article class="pc-card ${tier.tier===m.tier?'selected':''}" data-tier="${tier.tier}"><span class="p3-tier-icon">${icon('shield')}</span><h3>${t(tier.tier)}</h3><strong>${money(tier.minimum_spend)}</strong>${tier.tier===m.tier?`<small class="cyan">${t('p3CurrentTier')}</small>`:''}</article>`).join('')}</section><section class="pc-card"><header><h2>${t('p3PointHistory')}</h2><small>${history.total} ${t('pcResults')}</small></header><div class="pc-table-wrap">${history.items.length?table(['invoiceCode','created','p3Spend','p3EffectivePoints','p3InvoiceRule','status'],history.items.map(x=>`<tr><td>${esc(x.code)}</td><td>${dt(x.created_at)}</td><td>${money(x.eligible_amount)}</td><td class="${x.status==='PAID'?'green':'muted'}"><strong>${x.status==='PAID'?'+':''}${x.effective_points}</strong>${x.status==='VOID'?` <del>+${x.points}</del>`:''}</td><td>${money(x.unit_amount)} / 1 · v${x.rule_version}</td><td>${badge(x.status)}</td></tr>`).join('')):pcEmpty('pcNoActivity','pcNoActivitySub')}</div><footer class="pc-pagination"><span>${t('p3Voids')}</span><div><button class="btn small" data-p3="member-page" data-page="${history.page-1}" ${history.page<=1?'disabled':''} aria-label="${t('pcPrevious')}">‹</button><span>${history.page} / ${pages}</span><button class="btn small" data-p3="member-page" data-page="${history.page+1}" ${history.page>=pages?'disabled':''} aria-label="${t('pcNextPage')}">›</button></div></footer></section>`;
}

async function showAvatarEditor(){
  closeCustomerAccount();const owner=state.customer;portalUI.p2Busy=true;
  const dialog=document.createElement('dialog');dialog.className='p3-avatar-dialog';dialog.setAttribute('aria-labelledby','p3-avatar-title');
  dialog.innerHTML=`<header><h2 id="p3-avatar-title">${t('p3Avatar')}</h2><button class="btn small" data-avatar-close aria-label="${t('close')}">×</button></header><p class="muted">${t('p3AvatarSub')}</p><div class="p3-photo-preview" aria-label="${t('p3PhotoPreview')}">${customerAvatar('preview')}</div><label class="btn p3-file-label">${icon('camera')}${t('p3ChooseImage')}<input type="file" id="p3-avatar-file" accept="image/jpeg,image/png,image/webp"></label><p class="pc-fine">${t('p3ImageHint')}</p><p class="p3-avatar-error" role="alert"></p><footer><button class="btn ghost red" data-avatar-remove ${portalUI.data.avatar_version?'':'disabled'}>${t('p3RemoveImage')}</button><button class="btn primary" data-avatar-save disabled>${t('p3SaveImage')}</button></footer>`;
  document.body.append(dialog);let file=null,busy=false,selection=0;
  const error=$('.p3-avatar-error',dialog),save=$('[data-avatar-save]',dialog),remove=$('[data-avatar-remove]',dialog),input=$('#p3-avatar-file',dialog);
  dialog.addEventListener('close',()=>{if(portalUI)portalUI.p2Busy=false;dialog.remove();$('#p3-account-toggle')?.focus();},{once:true});
  $('[data-avatar-close]',dialog).onclick=()=>{if(!busy)dialog.close();};
  dialog.addEventListener('cancel',event=>{if(busy)event.preventDefault();});
  input.onchange=()=>{const seq=++selection;file=input.files[0]||null;error.textContent='';save.disabled=true;
    if(!file)return;
    if(file.size>2*1024*1024||!['image/jpeg','image/png','image/webp'].includes(file.type)){file=null;error.textContent=t('p3ImageHint');return;}
    const reader=new FileReader();reader.onload=()=>{if(seq!==selection||!dialog.isConnected)return;const img=document.createElement('img');img.alt=t('p3PhotoPreview');img.src=reader.result;$('.p3-photo-preview',dialog).replaceChildren(img);save.disabled=false;};reader.onerror=()=>{file=null;error.textContent=t('unavailable');};reader.readAsDataURL(file);
  };
  async function commit(deleting){
    if(busy||(!deleting&&!file))return;busy=true;save.disabled=true;remove.disabled=true;input.disabled=true;error.textContent='';
    try{
      if(deleting)await api('/portal/avatar',{method:'DELETE'});
      else {const form=new FormData();form.append('avatar',file);const response=await fetch('/api/portal/avatar',{method:'POST',credentials:'same-origin',headers:{'X-CSRF-Token':state.csrf,'X-Language':state.lang},body:form,signal:AbortSignal.timeout(25000)});const data=await response.json();if(!response.ok)throw Object.assign(new Error(data.error?.message||t('network')),data.error||{});}
      if(state.customer!==owner){dialog.close();return;}
      await renderCustomerPortal();dialog.close();toast(t(deleting?'p3ImageRemoved':'p3ImageSaved'));
    }catch(e){if(['PERMISSION_DENIED','AUTH_REQUIRED'].includes(e.code)){dialog.close();state.customer=null;renderLogin();return;}error.textContent=Object.values(e.field_errors||{}).join(' · ')||e.message;}
    finally{busy=false;if(dialog.isConnected){save.disabled=!file;remove.disabled=!portalUI?.data.avatar_version;input.disabled=false;}}
  }
  save.onclick=()=>commit(false);remove.onclick=()=>commit(true);dialog.showModal();
}
document.addEventListener('click',async event=>{
  const button=event.target.closest('[data-p3]');if(!button||button.disabled){if(!event.target.closest('.p3-account-wrap')||event.target.closest('[role=menuitem]'))closeCustomerAccount();return;}
  const action=button.dataset.p3;
  if(action==='account'){const menu=$('#p3-account-menu'),open=menu.hidden;portalUI.accountMenuOpen=open;menu.hidden=!open;button.setAttribute('aria-expanded',String(open));return;}
  if(action==='avatar')showAvatarEditor();
  if(action==='security'){closeCustomerAccount();portalUI.tab='profile';await renderCustomerPortal();$('#p2-password-form')?.scrollIntoView({behavior:'smooth',block:'center'});$('#p2-password-form [name=current_password]')?.focus({preventScroll:true});}
  if(action==='member-page'){portalUI.memberPage=Number(button.dataset.page);await renderCustomerPortal();}
});
document.addEventListener('keydown',event=>{
  const menu=$('#p3-account-menu');if(!menu||menu.hidden)return;
  if(event.key==='Escape'){event.preventDefault();closeCustomerAccount(true);return;}
  if(['ArrowDown','ArrowUp','Home','End'].includes(event.key)){event.preventDefault();const items=[...menu.querySelectorAll('[role=menuitem]')];let i=items.indexOf(document.activeElement);i=event.key==='Home'?0:event.key==='End'?items.length-1:(i+(event.key==='ArrowDown'?1:-1)+items.length)%items.length;items[i].focus();}
});
document.addEventListener('error',event=>{if(event.target.matches?.('[data-customer-avatar]')){const fallback=document.createElement('span');fallback.textContent=initials(state.customer?.full_name);event.target.replaceWith(fallback);}},true);

function installLoyaltyManagement(){
  if(state.page!=='promotions'||state.actor?.role!=='ADMIN')return;
  const actions=$('.page-head .actions');if(!actions)return;
  const button=document.createElement('button');button.className='btn small';button.innerHTML=icon('shield')+esc(t('p3Policy'));button.dataset.loyaltySettings='true';button.onclick=showLoyaltySettings;actions.append(button);
}
async function showLoyaltySettings(){
  try{
    const settings=await api('/loyalty/settings');const dialog=document.createElement('dialog');dialog.className='p3-settings-dialog';
    dialog.setAttribute('aria-labelledby','p3-settings-title');
    dialog.innerHTML=`<header><h2 id="p3-settings-title">${t('p3Policy')}</h2><button class="btn small" data-policy-close aria-label="${t('close')}">×</button></header><p class="pc-fine">${t('p3PolicySub')}</p><form id="p3-settings-form"><label class="check-label"><input type="checkbox" name="enabled" ${settings.enabled?'checked':''}>${t('p3Enabled')}</label>${['unit_amount','silver_spend','gold_spend','platinum_spend'].map(k=>`<label class="pc-field"><span>${t(k)}</span><input class="input" type="number" name="${k}" min="1" max="1000000000000" step="1" value="${settings[k]}" required></label>`).join('')}<p class="p3-avatar-error" role="alert"></p><button class="btn primary full" type="submit">${t('save')}</button></form>`;
    document.body.append(dialog);dialog.addEventListener('close',()=>dialog.remove(),{once:true});$('[data-policy-close]',dialog).onclick=()=>dialog.close();
    $('#p3-settings-form',dialog).onsubmit=async event=>{event.preventDefault();const form=event.target,button=$('button[type=submit]',form),error=$('.p3-avatar-error',form);button.disabled=true;error.textContent='';try{const values=Object.fromEntries(new FormData(form));for(const k of ['unit_amount','silver_spend','gold_spend','platinum_spend'])values[k]=Number(values[k]);values.enabled=form.elements.enabled.checked;values.version=settings.version;await api('/loyalty/settings',{method:'PUT',body:values});dialog.close();toast(t('p3PolicySaved'));}catch(e){error.textContent=Object.values(e.field_errors||{}).join(' · ')||e.message;}finally{button.disabled=false;}};
    dialog.showModal();
  }catch(e){toast(e.message,true);}
}
async function installPromotionAudience(item){
  const context=modalContext,grid=$('.form-grid',$('#modal'));if(!grid)return;
  const initialTargets=[['',t('p3AllEligible')],...(item?.target_customer_id?[[item.target_customer_id,'#'+item.target_customer_id]]:[])];
  grid.insertAdjacentHTML('beforeend',selectField('minimum_tier','p3MinTier',['BRONZE','SILVER','GOLD','PLATINUM'].map(k=>[k,t(k)]),item?.minimum_tier||'BRONZE')+field('minimum_points','p3MinPoints',item?.minimum_points||0,'number')+selectField('target_customer_id','p3CustomerTarget',initialTargets,item?.target_customer_id||'')+`<p class="pc-fine wide">${t('p3AudienceNote')}</p>`);
  $('[name=minimum_points]',$('#modal')).min='0';
  try{const customers=await api('/customers');if(modalContext!==context)return;const select=$('[name=target_customer_id]',$('#modal')),selected=select.value;select.innerHTML=`<option value="">${t('p3AllEligible')}</option>`+customers.map(c=>`<option value="${c.customer_id}">${esc(c.customer_code+' · '+c.full_name)}</option>`).join('');if(selected&&!customers.some(c=>String(c.customer_id)===selected)){const option=document.createElement('option');option.value=selected;option.textContent='#'+selected;select.append(option);}select.value=selected;}
  catch(e){if(modalContext===context)formError(e);}
}
