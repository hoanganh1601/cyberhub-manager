/* Standalone step-11 mock: no fetch, session, role payload or persistent storage. */
(() => {
  "use strict";
  const text = {
    vi: {
      preview: "BẢN XEM TRƯỚC", pageTitle: "Trợ lý tri thức, ngay trong không gian làm việc.",
      pageLead: "Thử giao diện hỏi đáp có nguồn theo phong cách CyberHub. Đây là bản mô phỏng, chưa kết nối AI, phiên đăng nhập hoặc dữ liệu cửa hàng.",
      open: "Mở trợ lý", local: "Câu hỏi và phản hồi chỉ nằm trong bộ nhớ trình duyệt.",
      reviewSources: "Kiểm tra nguồn (dành cho người review)",
      scenarios: "Ba trạng thái để kiểm tra giao diện", withSource: "Có nguồn tham khảo",
      withSourceDesc: "Hỏi về mở phiên, nạp tiền hoặc tiền bù; xem nguồn và gửi phản hồi.",
      noSource: "Chưa đủ căn cứ", noSourceDesc: "Giữ cuộc hội thoại khi không có tài liệu phù hợp để trả lời.",
      serviceError: "Dịch vụ gián đoạn", serviceErrorDesc: "Hiển thị lỗi dễ hiểu và nút thử lại, không mất câu hỏi đã nhập.",
      try: "Thử trạng thái →", boundaries: "Chỉ giải thích tài liệu. Trợ lý không nạp/trừ tiền, không mở/đóng phiên và không xác nhận giao dịch.",
      askCyberhub: "Hỏi CyberHub", assistantTitle: "Trợ lý CyberHub", mockLabel: "Mô phỏng giao diện · Chưa kết nối AI",
      close: "Đóng", notice: "AI có thể trả lời sai. Hãy kiểm tra lại thông tin trước khi thao tác; không nhập mật khẩu hoặc dữ liệu khách thật.",
      newChat: "＋ Hội thoại mới", scenario: "Kịch bản mẫu", auto: "Tự động", questionLabel: "Câu hỏi của bạn",
      placeholder: "Hỏi cách mở phiên, nạp tiền hoặc thanh toán…", keyboard: "Enter gửi · Shift+Enter xuống dòng", send: "Gửi ↑",
      sampleSource: "Trích đoạn mẫu · Không phải dữ liệu tài khoản hiện tại", resetTitle: "Bắt đầu hội thoại mới?",
      resetDescription: "Tin nhắn và phản hồi mẫu trong hội thoại hiện tại sẽ được xóa khỏi bộ nhớ trình duyệt.",
      cancel: "Hủy", resetConfirm: "Bắt đầu mới", welcome: "Xin chào, tôi có thể giúp gì?",
      welcomeBody: "Thử một câu hỏi về quy trình. Câu trả lời bên dưới là dữ liệu mẫu, không phải AI đang chạy.",
      suggestOpen: "Cần bao nhiêu số dư để mở phiên?", suggestPayment: "Tiền bù và tiền khách đưa khác nhau thế nào?",
      suggestTopup: "Nạp tiền hỗ trợ phương thức nào?", you: "Bạn", mockResponse: "CyberHub · Trả lời mẫu",
      loading: "Đang tạo câu trả lời mẫu…", required: "Vui lòng nhập câu hỏi.",
      tooLong: "Câu hỏi tối đa 2.000 ký tự.", limit: "Phiên mẫu đã đủ 20 lượt. Hãy bắt đầu hội thoại mới.",
      helpful: "Hữu ích", notHelpful: "Chưa hữu ích", feedbackSaved: "Đã ghi nhận trong phiên mẫu", sourceButton: "Xem nguồn mẫu",
      refusal: "Tôi chưa tìm thấy thông tin đã được phê duyệt để trả lời câu hỏi này. Vui lòng liên hệ quản lý hoặc quản trị viên.",
      error: "Trợ lý hiện chưa thể trả lời. Đây là lỗi mô phỏng; bạn có thể thử lại hoặc chọn kịch bản khác.",
      retry: "Thử lại", version: "Phiên bản", resetDone: "Đã bắt đầu hội thoại mới.",
      paymentAnswer: "Khoản bù phải bằng đúng số tiền còn thiếu được hệ thống tính lại khi thanh toán. Tiền khách đưa dư phải xử lý riêng tại quầy, không tự coi là tiền nạp vào ví. [S1]",
      openAnswer: "Cần có số dư tối thiểu đủ 30 phút theo đơn giá máy. Máy, khách hàng và tài khoản phải đủ điều kiện trước khi mở phiên. [S1]",
      topupAnswer: "Nạp tiền hỗ trợ tiền mặt hoặc chuyển khoản theo quy trình ghi nhận tại quầy. Chỉ xác nhận sau khi nhận tiền; trợ lý không thực hiện hoặc xác nhận giao dịch thay nhân viên. [S1]",
      paymentTitle: "Quy trình thanh toán phiên chơi", paymentSection: "Trừ ví và tiền bù",
      paymentExcerpt: "Nếu thiếu, khoản bù phải bằng đúng khoản thiếu backend tính lại khi checkout; nhận bằng CASH hoặc TRANSFER. Nếu không thiếu, không nhập phương thức bù hoặc khoản bù dương.",
      openTitle: "Quy trình vận hành máy và mở phiên", openSection: "Điều kiện mở phiên",
      openExcerpt: "Số dư tối thiểu đủ 30 phút theo đơn giá máy; mức yêu cầu được làm tròn lên đến VND. Đây không phải thu trước phí 30 phút hoặc tự dừng máy sau 30 phút.",
      topupTitle: "Quy trình nạp tiền và áp dụng khuyến mãi", topupSection: "Nhận và xác nhận tiền",
      topupExcerpt: "Nhập số tiền nguyên từ 1 đến 100.000.000 VND và phương thức CASH hoặc TRANSFER. Chỉ xác nhận sau khi nhận tiền theo quy trình quầy. AI không xác nhận đã nhận tiền hoặc thực hiện nạp thay nhân viên.",
    },
    en: {
      preview: "UI PREVIEW", pageTitle: "Knowledge assistance, right in your workspace.",
      pageLead: "Explore a source-backed chat interface in the CyberHub theme. This is a simulation with no AI, authenticated session or store data connected.",
      open: "Open assistant", local: "Questions and feedback stay in browser memory only.",
      reviewSources: "Inspect sources (review mode)",
      scenarios: "Three states to review", withSource: "Sources available",
      withSourceDesc: "Ask about starting a session, top-ups or settlement; review sources and give feedback.",
      noSource: "Insufficient context", noSourceDesc: "Keep the conversation when no suitable approved context is available.",
      serviceError: "Service interruption", serviceErrorDesc: "Show a clear error and a retry action without losing the question.",
      try: "Try this state →", boundaries: "Documentation only. The assistant cannot credit/debit funds, open/close sessions or confirm transactions.",
      askCyberhub: "Ask CyberHub", assistantTitle: "CyberHub assistant", mockLabel: "UI simulation · No AI connected",
      close: "Close", notice: "AI can be wrong. Verify the information before acting; do not enter passwords or real customer data.",
      newChat: "＋ New conversation", scenario: "Mock scenario", auto: "Automatic", questionLabel: "Your question",
      placeholder: "Ask about sessions, top-ups or checkout…", keyboard: "Enter to send · Shift+Enter for a new line", send: "Send ↑",
      sampleSource: "Sample excerpt · Not current account data", resetTitle: "Start a new conversation?",
      resetDescription: "Messages and sample feedback in the current conversation will be removed from browser memory.",
      cancel: "Cancel", resetConfirm: "Start new", welcome: "Hello. How can I help?",
      welcomeBody: "Try a procedure question. Responses below are sample data, not a live AI model.",
      suggestOpen: "What balance is required to start a session?", suggestPayment: "How does settlement differ from cash received?",
      suggestTopup: "Which payment methods are supported for top-ups?", you: "You", mockResponse: "CyberHub · Sample response",
      loading: "Preparing a sample response…", required: "Please enter a question.",
      tooLong: "Questions may contain up to 2,000 characters.", limit: "This sample has reached 20 turns. Start a new conversation.",
      helpful: "Helpful", notHelpful: "Not helpful", feedbackSaved: "Saved for this sample session", sourceButton: "View sample source",
      refusal: "I could not find approved information to answer this question. Please contact a manager or administrator.",
      error: "The assistant cannot answer right now. This is a simulated error; retry or select another scenario.",
      retry: "Try again", version: "Version", resetDone: "A new conversation has started.",
      paymentAnswer: "Settlement must equal the exact shortfall recalculated by the system at checkout. Handle excess cash separately at the counter; do not automatically treat it as a wallet top-up. [S1]",
      openAnswer: "You need enough balance for 30 minutes at the machine rate. The machine, customer and account must be eligible before starting the session. [S1]",
      topupAnswer: "Top-ups support cash or bank transfers recorded at the counter. Confirm only after receiving payment; the assistant cannot perform or confirm a transaction for an employee. [S1]",
      paymentTitle: "Session checkout procedure", paymentSection: "Wallet debit and settlement",
      paymentExcerpt: "If funds are insufficient, settlement must equal the shortfall recalculated by the backend at checkout, using CASH or TRANSFER. If no settlement is needed, do not select a settlement method or enter a positive settlement amount.",
      openTitle: "Machine operation and session opening", openSection: "Opening conditions",
      openExcerpt: "The minimum balance covers 30 minutes at the machine rate, rounded up to VND. This is neither a prepaid 30-minute charge nor automatic shutdown after 30 minutes.",
      topupTitle: "Top-up and promotion procedure", topupSection: "Receiving and confirming payment",
      topupExcerpt: "Enter a whole amount from 1 to 100,000,000 VND and CASH or TRANSFER. Confirm only after receiving payment at the counter. AI cannot confirm receipt or perform a top-up for an employee.",
    },
  };
  const sources = {
    payment: "staff/payment-process.md", open: "staff/machine-operation.md", topup: "staff/top-up-process.md",
  };
  const chat = document.getElementById("assistant-chat");
  const history = document.getElementById("chat-history");
  const input = document.getElementById("chat-question");
  const scenario = document.getElementById("chat-scenario");
  const reset = document.getElementById("reset-dialog");
  const sourceDialog = document.getElementById("source-dialog");
  const sourceReview = document.getElementById("review-sources");
  // Display option for this standalone mock only, never an authorization flag.
  sourceReview.checked = new URLSearchParams(window.location.search).get("review") === "1";
  let language = "vi", messages = [], busy = false, timer = null, revision = 0, activeSource = null;
  const t = key => text[language][key];
  const node = (tag, className, content) => {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (content !== undefined) element.textContent = content;
    return element;
  };
  function announce(key) { document.getElementById("preview-announcement").textContent = t(key); }
  function counts() { document.getElementById("chat-count").textContent = String(Array.from(input.value).length); }
  function openChat() {
    if (!chat.open) chat.showModal();
    input.focus();
  }
  function sourcePreview(kind) {
    if (!sourceReview.checked) return;
    activeSource = kind;
    document.getElementById("source-title").textContent = t(`${kind}Title`);
    document.getElementById("source-path").textContent = sources[kind];
    document.getElementById("source-excerpt").textContent = t(`${kind}Excerpt`);
    document.getElementById("source-section").textContent = `${t(`${kind}Section`)} · ${t("version")} 1`;
    if (!sourceDialog.open) sourceDialog.showModal();
  }
  function render() {
    history.replaceChildren();
    if (!messages.length) {
      const welcome = node("section", "chat-welcome");
      welcome.append(node("h3", "", t("welcome")), node("p", "", t("welcomeBody")));
      const suggestions = node("div", "chat-suggestions");
      ["suggestOpen", "suggestPayment", "suggestTopup"].forEach(key => {
        const button = node("button", "", t(key)); button.type = "button";
        button.addEventListener("click", () => { input.value = t(key); counts(); submit(); });
        suggestions.append(button);
      });
      welcome.append(suggestions); history.append(welcome);
    }
    messages.forEach(message => {
      const article = node("article", `chat-message ${message.role}`);
      article.append(node("div", "chat-message-label", t(message.role === "user" ? "you" : "mockResponse")));
      const answerText = message.role === "user" ? message.content : (
        sourceReview.checked ? t(message.key) : t(message.key).replace(/\s*\[S\d+\]/g, "")
      );
      const body = node("p", "chat-message-text", answerText);
      if (message.key === "error") body.classList.add("chat-error");
      article.append(body);
      if (message.source && sourceReview.checked) {
        const button = node("button", "chat-source-card"); button.type = "button";
        button.append(node("strong", "", `[S1] ${t(`${message.source}Title`)}`), node("small", "", `${sources[message.source]} · ${t("sourceButton")}`));
        button.addEventListener("click", () => sourcePreview(message.source)); article.append(button);
      }
      if (message.key === "error") {
        const retry = node("button", "chat-retry", t("retry")); retry.type = "button"; retry.disabled = busy || message !== messages.at(-1);
        retry.addEventListener("click", () => {
          if (!busy) { messages = messages.filter(item => item !== message); startResponse(message.question); }
        });
        article.append(retry);
      } else if (message.role === "assistant") {
        const feedback = node("div", "chat-feedback");
        ["helpful", "notHelpful"].forEach(rating => {
          const button = node("button", "", t(rating)); button.type = "button";
          button.setAttribute("aria-pressed", String(message.rating === rating));
          button.addEventListener("click", () => { message.rating = message.rating === rating ? null : rating; render(); });
          feedback.append(button);
        });
        if (message.rating) feedback.append(node("span", "", t("feedbackSaved")));
        article.append(feedback);
      }
      history.append(article);
    });
    if (busy) history.append(node("p", "chat-loading", t("loading")));
    document.getElementById("chat-send").disabled = busy;
    history.setAttribute("aria-busy", String(busy));
    history.scrollTop = history.scrollHeight;
  }
  function responseKind(question) {
    if (scenario.value === "refusal") return "refusal";
    if (scenario.value === "error") return "error";
    const normal = question.toLocaleLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/đ/g, "d");
    if (/tien bu|checkout|settlement|cash received|thanh toan/.test(normal)) return "payment";
    if (/mo phien|mo may|start a session|open a session|minimum balance/.test(normal)) return "open";
    if (/nap tien|top.up|payment methods/.test(normal)) return "topup";
    return "refusal";
  }
  function startResponse(question) {
    if (busy) return;
    busy = true; const current = revision; const kind = responseKind(question); render();
    timer = window.setTimeout(() => {
      if (current !== revision) return;
      busy = false; timer = null;
      messages.push({ role: "assistant", key: sources[kind] ? `${kind}Answer` : kind, source: sources[kind] ? kind : null, question, rating: null });
      render(); input.focus();
    }, 450);
  }
  function submit() {
    if (busy) return;
    const question = input.value.trim();
    const validation = document.getElementById("chat-validation");
    if (!question) { validation.textContent = t("required"); return; }
    if (Array.from(input.value).length > 2000) { validation.textContent = t("tooLong"); return; }
    if (messages.filter(item => item.role === "user").length >= 20) { validation.textContent = t("limit"); return; }
    validation.textContent = "";
    messages.push({ role: "user", content: question }); input.value = ""; counts(); startResponse(question);
  }
  function clearConversation() {
    revision += 1;
    if (timer !== null) window.clearTimeout(timer);
    timer = null; busy = false; messages = []; input.value = ""; activeSource = null;
    document.getElementById("chat-validation").textContent = "";
    counts(); render(); announce("resetDone"); input.focus();
  }
  function translate() {
    document.documentElement.lang = language;
    document.querySelectorAll("[data-i18n]").forEach(element => { element.textContent = t(element.dataset.i18n); });
    document.querySelectorAll("[data-i18n-aria]").forEach(element => { element.setAttribute("aria-label", t(element.dataset.i18nAria)); });
    document.querySelectorAll("[data-i18n-placeholder]").forEach(element => { element.placeholder = t(element.dataset.i18nPlaceholder); });
    document.querySelectorAll("[data-language]").forEach(button => { button.setAttribute("aria-pressed", String(button.dataset.language === language)); });
    document.getElementById("chat-validation").textContent = "";
    if (sourceDialog.open && activeSource) sourcePreview(activeSource);
    render();
  }
  document.querySelectorAll("[data-open-chat]").forEach(button => button.addEventListener("click", openChat));
  document.querySelector("[data-close-chat]").addEventListener("click", () => chat.close());
  document.querySelectorAll("[data-language]").forEach(button => button.addEventListener("click", () => { language = button.dataset.language; translate(); }));
  document.querySelectorAll("[data-scenario]").forEach(button => button.addEventListener("click", () => { scenario.value = button.dataset.scenario; openChat(); }));
  document.getElementById("chat-form").addEventListener("submit", event => { event.preventDefault(); submit(); });
  input.addEventListener("input", counts);
  input.addEventListener("keydown", event => {
    if (event.key === "Enter" && !event.shiftKey && !event.isComposing) { event.preventDefault(); submit(); }
  });
  document.getElementById("new-conversation").addEventListener("click", () => { if (messages.length || busy) reset.showModal(); else clearConversation(); });
  document.getElementById("cancel-reset").addEventListener("click", () => reset.close());
  document.getElementById("confirm-reset").addEventListener("click", () => { reset.close(); clearConversation(); });
  document.getElementById("close-source").addEventListener("click", () => sourceDialog.close());
  sourceReview.addEventListener("change", () => {
    if (!sourceReview.checked && sourceDialog.open) sourceDialog.close();
    render();
  });
  translate(); counts();
})();
