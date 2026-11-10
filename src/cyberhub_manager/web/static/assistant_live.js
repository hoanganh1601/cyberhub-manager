/* Authenticated 5A widget. Only question/language are sent; no canned answers. */
(() => {
  "use strict";
  const root = document.getElementById("assistant-widget");
  if (!root) return;
  const $ = selector => root.querySelector(selector);
  const chat = $("#assistant-chat"), history = $("#chat-history"), input = $("#chat-question");
  const review = $("#review-sources"), reset = $("#reset-dialog"), sourceDialog = $("#source-dialog");
  const modeSelect = $("#assistant-mode");
  const strings = {
    vi: {
      askCyberhub: "Hỏi CyberHub", assistantTitle: "Trợ lý CyberHub", mockLabel: "Hướng dẫn từ tài liệu được phép",
      assistantMode: "Chế độ", modeKnowledge: "Tài liệu", modeAnalytics: "Phân tích", modePersonalized: "Gợi ý cho tôi",
      notice: "AI có thể trả lời sai. Hãy kiểm tra lại thông tin trước khi thao tác; không nhập mật khẩu hoặc dữ liệu khách thật.",
      close: "Đóng", newChat: "＋ Hội thoại mới", reviewSources: "Xem nguồn", questionLabel: "Câu hỏi của bạn",
      placeholder: "Hỏi cách mở phiên, nạp tiền hoặc thanh toán…", keyboard: "Enter gửi · Shift+Enter xuống dòng", send: "Gửi ↑",
      welcome: "Tôi có thể giúp gì?", welcomeBody: "Hỏi về quy trình CyberHub. Tôi chỉ giải thích tài liệu được phép, không thực hiện giao dịch hay đọc số liệu trực tiếp.",
      suggestOpen: "Cần bao nhiêu số dư để mở phiên?", suggestPayment: "Tiền bù và tiền khách đưa khác nhau thế nào?", suggestTopup: "Nạp tiền hỗ trợ phương thức nào?",
      analyticsWelcome: "Phân tích vận hành", analyticsBody: "Số liệu được backend lọc theo vai trò và cơ sở trước khi gửi cho AI.",
      suggestRevenue: "Tóm tắt doanh thu 30 ngày gần đây", suggestAnomaly: "Ngày nào doanh thu thấp bất thường?", suggestPromotion: "Nên chạy khuyến mãi vào thời điểm nào?",
      personalWelcome: "Gợi ý dành cho bạn", personalBody: "Gợi ý từ hạng, điểm, ưu đãi, menu, voucher và xu của chính tài khoản này.",
      suggestFood: "Gợi ý món ăn phù hợp và ưu đãi hiện có", suggestVoucher: "Tôi nên dùng voucher nào?", suggestGame: "Tôi có thể nhận thêm xu hoặc lượt quay thế nào?",
      you: "Bạn", assistant: "CyberHub", loading: "Đang tìm tài liệu và soạn câu trả lời…", required: "Vui lòng nhập câu hỏi.", tooLong: "Câu hỏi tối đa 2.000 ký tự.",
      limit: "Hội thoại đã đủ 20 lượt. Hãy bắt đầu hội thoại mới.", helpful: "Hữu ích", notHelpful: "Chưa hữu ích", feedbackSaved: "Đã ghi nhận trong phiên này",
      retry: "Thử lại", error: "Trợ lý hiện không khả dụng. Vui lòng thử lại sau.", rateLimit: "Đã đạt giới hạn hỏi đáp. Vui lòng thử lại sau", seconds: "giây",
      providerQuota: "Dịch vụ AI đã đạt hạn mức. Vui lòng chờ rồi thử lại hoặc liên hệ quản trị viên.",
      providerConfiguration: "Trợ lý chưa được cấp quyền kết nối AI. Vui lòng liên hệ quản trị viên.",
      sourceButton: "Thông tin nguồn", sampleSource: "Nguồn được hệ thống xác thực theo quyền của bạn", version: "Phiên bản",
      sourceNote: "Nguồn này đã được backend xác thực theo quyền. Với snapshot động, hãy kiểm tra lại màn hình chức năng trước khi thao tác.",
      resetTitle: "Bắt đầu hội thoại mới?", resetDescription: "Xóa hội thoại và phản hồi đang giữ trong bộ nhớ trình duyệt. Câu hỏi không được lưu thành lịch sử trên server.",
      cancel: "Hủy", resetConfirm: "Bắt đầu mới", privacy: "Hội thoại chỉ lưu trong bộ nhớ trình duyệt; phản hồi hữu ích chưa được lưu trên server.",
    },
    en: {
      askCyberhub: "Ask CyberHub", assistantTitle: "CyberHub assistant", mockLabel: "Guidance from authorized documents",
      assistantMode: "Mode", modeKnowledge: "Knowledge", modeAnalytics: "Analytics", modePersonalized: "For me",
      notice: "AI can be wrong. Verify the information before acting; do not enter passwords or real customer data.",
      close: "Close", newChat: "＋ New conversation", reviewSources: "Show sources", questionLabel: "Your question",
      placeholder: "Ask about sessions, top-ups or checkout…", keyboard: "Enter to send · Shift+Enter for a new line", send: "Send ↑",
      welcome: "How can I help?", welcomeBody: "Ask about CyberHub procedures. I explain authorized documents, without performing transactions or reading live figures.",
      suggestOpen: "What balance is required to start a session?", suggestPayment: "How does settlement differ from cash received?", suggestTopup: "Which payment methods are supported for top-ups?",
      analyticsWelcome: "Operations analytics", analyticsBody: "The backend filters figures by role and store before sending them to AI.",
      suggestRevenue: "Summarize revenue for the last 30 days", suggestAnomaly: "Which days had unusually low revenue?", suggestPromotion: "When should we run a promotion?",
      personalWelcome: "Recommendations for you", personalBody: "Suggestions use only this account's membership, offers, menu, vouchers and coins.",
      suggestFood: "Recommend food and an applicable offer", suggestVoucher: "Which voucher should I use?", suggestGame: "How can I earn more coins or spins?",
      you: "You", assistant: "CyberHub", loading: "Finding documents and preparing an answer…", required: "Please enter a question.", tooLong: "Questions may contain up to 2,000 characters.",
      limit: "This conversation has reached 20 turns. Start a new conversation.", helpful: "Helpful", notHelpful: "Not helpful", feedbackSaved: "Recorded for this browser session",
      retry: "Try again", error: "The assistant is unavailable. Please try again later.", rateLimit: "Assistant request limit reached. Try again in", seconds: "seconds",
      providerQuota: "The AI provider quota has been reached. Wait and try again or contact an administrator.",
      providerConfiguration: "The assistant cannot access its AI provider. Please contact an administrator.",
      sourceButton: "Source information", sampleSource: "Source authorized by the system for your account", version: "Version",
      sourceNote: "The backend authorized this source. For live snapshots, verify the feature screen before acting.",
      resetTitle: "Start a new conversation?", resetDescription: "Clear chat and feedback from browser memory. Questions are not saved as server-side conversation history.",
      cancel: "Cancel", resetConfirm: "Start new", privacy: "Chat stays in browser memory; helpfulness feedback is not saved on the server yet.",
    },
  };
  let language = "vi", identity = null, mode = "knowledge", messages = [], busy = false, revision = 0, controller = null, cooldown = 0, lastSessionCheck = 0;
  const t = key => strings[language][key];
  const node = (tag, cls, value) => {
    const el = document.createElement(tag); if (cls) el.className = cls;
    if (value !== undefined) el.textContent = value; return el;
  };
  function principalKey(data) {
    if (data.customer) return `customer:${data.customer.account_id}`;
    if (data.actor) return `employee:${data.actor.employee_id}:${data.actor.role}:${data.actor.store_id}`;
    return null;
  }
  function snapshot() {
    return typeof state === "undefined" ? {} : { actor: state.actor, customer: state.customer };
  }
  function clear() {
    revision++; controller?.abort(); controller = null; busy = false; messages = []; input.value = "";
    $("#chat-validation").textContent = ""; review.checked = false; counts(); render();
    if (sourceDialog.open) sourceDialog.close();
    if (reset.open) reset.close();
  }
  function sync() {
    const next = principalKey(snapshot());
    const nextLanguage = document.documentElement.lang === "en" ? "en" : "vi";
    if (next !== identity) {
      clear(); cooldown = 0; if (chat.open) chat.close(); identity = next; root.hidden = !identity;
    }
    if (language !== nextLanguage) { language = nextLanguage; translate(); }
    if (modeSelect) {
      const view = snapshot(), allowed = view.customer ? ["knowledge", "personalized"] :
        view.actor && ["MANAGER", "ADMIN"].includes(view.actor.role) ? ["knowledge", "analytics"] : ["knowledge"];
      Array.from(modeSelect.options).forEach(option => option.hidden = !allowed.includes(option.value));
      if (!allowed.includes(mode)) { mode = "knowledge"; modeSelect.value = mode; messages = []; render(); }
    }
    if (identity && new URLSearchParams(location.search).get("assistant") === "1" && !root.dataset.opened) {
      root.dataset.opened = "true"; open();
    }
  }
  function counts() { $("#chat-count").textContent = String(Array.from(input.value).length); }
  function translate() {
    root.querySelectorAll("[data-i18n]").forEach(el => { el.textContent = t(el.dataset.i18n); });
    root.querySelectorAll("[data-i18n-aria]").forEach(el => el.setAttribute("aria-label", t(el.dataset.i18nAria)));
    root.querySelectorAll("[data-i18n-placeholder]").forEach(el => el.placeholder = t(el.dataset.i18nPlaceholder));
    root.querySelectorAll("[data-language]").forEach(el => el.setAttribute("aria-pressed", String(el.dataset.language === language)));
    render();
  }
  async function checkSession() {
    lastSessionCheck = Date.now();
    const response = await fetch("/api/session", { credentials: "same-origin", cache: "no-store", signal: AbortSignal.timeout(10000) });
    if ([401, 403].includes(response.status)) { clear(); if (chat.open) chat.close(); root.hidden = true; location.reload(); return null; }
    if (!response.ok) throw new Error("session unavailable");
    const data = await response.json();
    if (!identity || principalKey(data) !== identity) {
      clear(); chat.close(); root.hidden = true; location.reload(); return null;
    }
    return data.csrf_token;
  }
  async function open() {
    sync(); if (!identity || chat.open) return;
    chat.showModal(); document.body.classList.add("assistant-chat-open"); input.focus();
    try { await checkSession(); } catch { $("#chat-validation").textContent = t("error"); }
  }
  function showSource(citation) {
    if (!review.checked) return;
    $("#source-title").textContent = citation.title;
    $("#source-path").textContent = citation.source;
    $("#source-section").textContent = `${citation.section} · ${t("version")} ${citation.version}`;
    $("#source-excerpt").textContent = t("sourceNote"); sourceDialog.showModal();
  }
  function render() {
    history.replaceChildren();
    if (!messages.length) {
      const welcome = node("section", "chat-welcome");
      const welcomeKey = mode === "analytics" ? ["analyticsWelcome", "analyticsBody"] : mode === "personalized" ? ["personalWelcome", "personalBody"] : ["welcome", "welcomeBody"];
      welcome.append(node("h3", "", t(welcomeKey[0])), node("p", "", t(welcomeKey[1])));
      const suggestions = node("div", "chat-suggestions");
      const suggestionKeys = mode === "analytics" ? ["suggestRevenue", "suggestAnomaly", "suggestPromotion"] : mode === "personalized" ? ["suggestFood", "suggestVoucher", "suggestGame"] : ["suggestOpen", "suggestPayment", "suggestTopup"];
      suggestionKeys.forEach(key => {
        const button = node("button", "", t(key)); button.type = "button";
        button.onclick = () => { input.value = t(key); counts(); submit(); }; suggestions.append(button);
      });
      welcome.append(suggestions, node("p", "preview-local", t("privacy"))); history.append(welcome);
    }
    messages.forEach(message => {
      const item = node("article", `chat-message ${message.role}`);
      item.append(node("div", "chat-message-label", t(message.role === "user" ? "you" : "assistant")));
      const content = message.content || (message.errorKey ? t(message.errorKey) : message.retryAt ? `${t("rateLimit")} ${Math.max(1, Math.ceil((message.retryAt - Date.now()) / 1000))} ${t("seconds")}.` : t("error"));
      item.append(node("p", `chat-message-text${message.error ? " chat-error" : ""}`, review.checked || message.role === "user" ? content : content.replace(/\s*\[S\d+\]/g, "")));
      if (review.checked) (message.citations || []).forEach((citation, index) => {
        const button = node("button", "chat-source-card"); button.type = "button";
        button.append(node("strong", "", `[S${index + 1}] ${citation.title}`), node("small", "", `${citation.section} · ${t("sourceButton")}`));
        button.onclick = () => showSource(citation); item.append(button);
      });
      if (message.error) {
        const retry = node("button", "chat-retry", t("retry")); retry.type = "button";
        retry.disabled = busy || Date.now() < cooldown || message !== messages.at(-1);
        retry.onclick = () => { messages.pop(); send(message.question); }; item.append(retry);
      } else if (message.role === "assistant") {
        const feedback = node("div", "chat-feedback");
        ["helpful", "notHelpful"].forEach(rating => {
          const button = node("button", "", t(rating)); button.type = "button";
          button.setAttribute("aria-pressed", String(message.rating === rating));
          button.onclick = () => { message.rating = message.rating === rating ? null : rating; render(); }; feedback.append(button);
        });
        if (message.rating) feedback.append(node("span", "", t("feedbackSaved")));
        item.append(feedback);
      }
      history.append(item);
    });
    if (busy) history.append(node("p", "chat-loading", t("loading")));
    $("#chat-send").disabled = busy || Date.now() < cooldown;
    history.setAttribute("aria-busy", String(busy)); history.scrollTop = history.scrollHeight;
  }
  async function send(question) {
    if (busy || !identity || Date.now() < cooldown) return;
    busy = true; const version = revision, actorKey = identity; render();
    try {
      const csrf = await checkSession();
      if (!csrf || version !== revision) return;
      controller = new AbortController(); const timeout = setTimeout(() => controller?.abort(), 130000);
      let response;
      try {
        response = await fetch("/api/assistant/messages", {
          method: "POST", credentials: "same-origin", signal: controller.signal,
          headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf, "X-Language": language },
          body: JSON.stringify({ question, language, mode, days: 30 }),
        });
      } finally { clearTimeout(timeout); }
      const data = await response.json();
      if (version !== revision || principalKey(snapshot()) !== actorKey) return;
      if ([401, 403].includes(response.status)) { clear(); chat.close(); root.hidden = true; location.reload(); return; }
      if (!response.ok) {
        if (response.status === 429) cooldown = Date.now() + Math.min(86400, Math.max(1, Number(response.headers.get("Retry-After")) || 60)) * 1000;
        const errorKey = { ASSISTANT_QUOTA_EXCEEDED: "providerQuota", ASSISTANT_CONFIGURATION_ERROR: "providerConfiguration" }[data.error?.code];
        messages.push({ role: "assistant", error: true, errorKey, question, retryAt: response.status === 429 ? cooldown : null });
      } else {
        if (typeof data.answer !== "string" || !Array.isArray(data.citations)) throw new Error("invalid response");
        messages.push({ role: "assistant", content: data.answer, citations: data.citations, requestId: data.request_id });
      }
    } catch {
      if (version === revision) messages.push({ role: "assistant", error: true, question });
    } finally {
      if (version === revision) { busy = false; controller = null; render(); input.focus(); }
    }
  }
  function submit() {
    if (busy || Date.now() < cooldown) return;
    sync(); const question = input.value.trim();
    const error = !question ? "required" : Array.from(input.value).length > 2000 ? "tooLong" : messages.filter(m => m.role === "user").length >= 20 ? "limit" : null;
    if (error) { $("#chat-validation").textContent = t(error); return; }
    $("#chat-validation").textContent = ""; messages.push({ role: "user", content: question }); input.value = ""; counts(); send(question);
  }
  $("[data-open-chat]").onclick = open;
  $("[data-close-chat]").onclick = () => chat.close();
  chat.addEventListener("close", () => document.body.classList.remove("assistant-chat-open"));
  $("#chat-form").onsubmit = event => { event.preventDefault(); submit(); };
  input.oninput = counts;
  input.onkeydown = event => { if (event.key === "Enter" && !event.shiftKey && !event.isComposing) { event.preventDefault(); submit(); } };
  review.onchange = render;
  $("#new-conversation").onclick = () => { if (messages.length || busy) reset.showModal(); };
  $("#cancel-reset").onclick = () => reset.close();
  $("#confirm-reset").onclick = () => { reset.close(); clear(); input.focus(); };
  if (modeSelect) modeSelect.onchange = () => { mode = modeSelect.value; clear(); input.focus(); };
  $("#close-source").onclick = () => sourceDialog.close();
  root.querySelectorAll("[data-language]").forEach(button => { button.onclick = () => {
    language = button.dataset.language;
    if (typeof setLanguage === "function") setLanguage(language);
    translate();
  }; });
  new MutationObserver(sync).observe(document.getElementById("app"), { childList: true, subtree: true });
  window.addEventListener("focus", () => { if (chat.open) checkSession().catch(() => {}); });
  setInterval(() => {
    if (chat.open && !document.hidden && Date.now() - lastSessionCheck > 30000) checkSession().catch(() => {});
    if (!busy && cooldown > 0) { render(); if (Date.now() >= cooldown) cooldown = 0; }
  }, 1000);
  translate(); sync();
})();
