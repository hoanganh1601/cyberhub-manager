"use strict";
// Đợt 4 — Quảng cáo nhận thưởng trong tab Vòng quay. Luôn tự nguyện: đóng lúc nào cũng được,
// không chặn chức năng nào. Đồng hồ đếm ngược ở đây chỉ để hiển thị; máy chủ tự đo thời lượng
// và chỉ cộng thưởng khi token còn hiệu lực và đã đủ thời gian.

Object.assign(copy, {
  dot4AdLabel: ["Quảng cáo", "Advertisement"],
  dot4Card: ["Xem quảng cáo nhận thưởng", "Watch an ad for a reward"],
  dot4CardSub: ["Không bắt buộc. Xem hết quảng cáo của CyberHub để nhận thêm phần thưởng.", "Optional. Watch a CyberHub ad to the end for an extra reward."],
  dot4RewardEXTRA_SPIN: ["+{n} lượt quay", "+{n} spin(s)"],
  dot4RewardCOINS: ["+{n} xu", "+{n} coins"],
  dot4Remaining: ["Còn {n} lần hôm nay", "{n} left today"],
  dot4Watch: ["Xem quảng cáo", "Watch ad"],
  dot4Claim: ["Nhận thưởng", "Claim reward"],
  dot4Close: ["Đóng (không nhận thưởng)", "Close (no reward)"],
  dot4Wait: ["Còn {n} giây", "{n}s left"],
  dot4Ready: ["Đã xem xong — bấm Nhận thưởng", "Done — tap Claim reward"],
  dot4Granted: ["Đã nhận thưởng", "Reward received"],
  dot4Network: ["Phần thưởng được cộng sau khi nhà cung cấp quảng cáo xác nhận.", "The reward is added after the ad provider confirms."],
  dot4Off: ["Chương trình quảng cáo đang tạm dừng", "Ad rewards are paused"],
  dot4Done: ["Bạn đã nhận đủ thưởng quảng cáo hôm nay", "You've collected all ad rewards today"],
});

const dot4Reward = (type, amount) => t("dot4Reward" + type).replace("{n}", amount);

// Được dot3Body() chèn vào tab Vòng quay.
function dot4AdCard() {
  const ads = portalUI?.ads;
  if (!ads) return "";
  const state_ = !ads.enabled ? "dot4Off" : ads.remaining ? "" : "dot4Done";
  return `<section class="pc-card dot4-card">
      <header><div><span class="dot4-tag">${t("dot4AdLabel")}</span><h2>${t("dot4Card")}</h2></div><strong class="dot4-reward">${dot4Reward(ads.reward_type, ads.reward_amount)}</strong></header>
      <p class="muted">${t("dot4CardSub")}</p>
      <div class="dot4-row"><small>${state_ ? t(state_) : t("dot4Remaining").replace("{n}", ads.remaining)}</small>
        <button class="btn primary" data-ad="start" ${state_ || portalUI.gameBusy ? "disabled" : ""}>${t("dot4Watch")}</button></div>
    </section>`;
}

let dot4Timer = null;

function dot4Dialog() {
  let dialog = $("#dot4-ad");
  if (!dialog) {
    dialog = document.createElement("dialog");
    dialog.id = "dot4-ad";
    dialog.className = "dot4-dialog";
    dialog.addEventListener("cancel", () => clearInterval(dot4Timer)); // phím Esc = đóng, không nhận thưởng
    document.body.append(dialog);
  }
  return dialog;
}

async function dot4Start() {
  const ui = portalUI;
  if (!ui || ui.adBusy) return;
  ui.adBusy = true;
  try {
    const ad = await api("/portal/ads/start", { method: "POST", body: {} });
    dot4Show(ad);
  } catch (error) {
    toast(error.message, true);
    ui.gameAt = 0;
    await loadCustomerGame();
  } finally {
    ui.adBusy = false;
  }
}

function dot4Show(ad) {
  const dialog = dot4Dialog();
  // +1 giây đệm: đồng hồ trình duyệt bắt đầu sau khi máy chủ đã ghi thời điểm cấp token.
  let left = ad.duration_seconds + 1;
  const network = ad.provider === "NETWORK";
  dialog.innerHTML = `<div class="dot4-ad" role="document">
      <header><span class="dot4-tag">${t("dot4AdLabel")} · CyberHub</span><button class="close" type="button" data-ad="close" aria-label="${t("dot4Close")}">×</button></header>
      <div class="dot4-creative"><img src="/assets/cyberhub_logo_dark.png" alt="CyberHub"><h2>${esc(ad.creative.title)}</h2><p>${esc(ad.creative.body)}</p>${ad.creative.cta ? `<span class="dot4-cta">${esc(ad.creative.cta)} ›</span>` : ""}</div>
      <div class="dot4-progress"><i id="dot4-bar" style="width:0%"></i></div>
      <p class="dot4-status" id="dot4-status">${network ? t("dot4Network") : t("dot4Wait").replace("{n}", left)}</p>
      <footer><button class="btn small" type="button" data-ad="close">${t("dot4Close")}</button>
        ${network ? "" : `<button class="btn primary" type="button" data-ad="claim" data-token="${ad.token}" disabled>${t("dot4Claim")} · ${dot4Reward(ad.reward_type, ad.reward_amount)}</button>`}</footer>
    </div>`;
  dialog.showModal();
  clearInterval(dot4Timer);
  const total = left;
  dot4Timer = setInterval(() => {
    left -= 1;
    const bar = $("#dot4-bar"), status = $("#dot4-status"), claim = $('[data-ad="claim"]');
    if (bar) bar.style.width = `${Math.min(100, ((total - left) / total) * 100)}%`;
    if (left <= 0) {
      clearInterval(dot4Timer);
      if (status && !network) status.textContent = t("dot4Ready");
      if (claim) claim.disabled = false;
    } else if (status && !network) {
      status.textContent = t("dot4Wait").replace("{n}", left);
    }
  }, 1000);
}

async function dot4Claim(button) {
  button.disabled = true;
  try {
    const result = await api("/portal/ads/complete", { method: "POST", body: { token: button.dataset.token } });
    $("#dot4-ad")?.close();
    toast(`${t("dot4Granted")}: ${dot4Reward(result.reward_type, result.reward_amount)}`);
  } catch (error) {
    $("#dot4-ad")?.close();
    toast(error.message, true);
  } finally {
    clearInterval(dot4Timer);
    if (portalUI) {
      portalUI.gameAt = 0;
      await loadCustomerGame();
    }
  }
}

document.addEventListener("click", (event) => {
  const button = event.target.closest("[data-ad]");
  if (!button || button.disabled) return;
  const action = button.dataset.ad;
  if (action === "start") dot4Start();
  if (action === "close") { clearInterval(dot4Timer); $("#dot4-ad")?.close(); }
  if (action === "claim") dot4Claim(button);
});
