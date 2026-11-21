"use strict";

function customerAccountMenu() {
  const profile = portalUI.data.profile;
  return `<div class="p3-account-wrap">
    <button class="p3-account-toggle" id="p3-account-toggle" data-p3="account"
      aria-haspopup="menu" aria-expanded="false" aria-controls="p3-account-menu"
      aria-label="${t("p3Account")}"><span class="avatar">${esc(initials(profile.full_name))}</span>
      <span class="p3-avatar-chevron">⌄</span></button>
    <div class="p3-account-menu" id="p3-account-menu" role="menu"
      aria-label="${t("p3Account")}" hidden>
      <div class="p3-menu-person"><div><strong>${esc(profile.full_name)}</strong>
        <small>${esc(profile.username)}</small></div></div>
      <button role="menuitem" data-portal="tab" data-tab="profile">${icon("users")}${t("p3EditProfile")}</button>
      <button role="menuitem" data-p3="security">${icon("lock")}${t("p2Security")}</button>
      <div class="divider"></div>
      <button role="menuitem" data-p1="portal-logout">${icon("logout")}${t("logout")}</button>
    </div>
  </div>`;
}

function closeCustomerAccount(focus = false) {
  if (portalUI) portalUI.accountMenuOpen = false;
  const menu = $("#p3-account-menu");
  const button = $("#p3-account-toggle");
  if (menu) menu.hidden = true;
  button?.setAttribute("aria-expanded", "false");
  if (focus) button?.focus();
}

document.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-p3]");
  if (!button) {
    if (!event.target.closest(".p3-account-wrap")) closeCustomerAccount();
    return;
  }
  if (button.dataset.p3 !== "account") return;
  const menu = $("#p3-account-menu");
  const open = menu.hidden;
  menu.hidden = !open;
  button.setAttribute("aria-expanded", String(open));
  if (portalUI) portalUI.accountMenuOpen = open;
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && $("#p3-account-menu:not([hidden])")) {
    event.preventDefault();
    closeCustomerAccount(true);
  }
});
