/* Optional real-browser verification; see the step 10/11 report for setup. */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright");

(async () => {
  const base = process.env.RAG_PREVIEW_URL || "http://127.0.0.1:8058";
  const output = process.env.RAG_SCREENSHOT_DIR || "/tmp/cyberhub-rag-preview-screenshots";
  fs.mkdirSync(output, { recursive: true });
  const browser = await chromium.launch({
    headless: true,
    ...(process.env.CHROME_BIN ? { executablePath: process.env.CHROME_BIN } : {}),
    args: ["--no-sandbox"],
  });
  const results = [];
  try {
    for (const viewport of [{ width: 1280, height: 720 }, { width: 390, height: 844 }]) {
      const page = await browser.newPage({ viewport });
      const errors = [], forbidden = [];
      page.on("pageerror", error => errors.push(error.message));
      page.on("console", message => { if (message.type() === "error") errors.push(message.text()); });
      page.on("request", request => {
        if (request.method() !== "GET" || new URL(request.url()).pathname.startsWith("/api/")) {
          forbidden.push(request.url());
        }
      });
      await page.goto(base, { waitUntil: "networkidle" });
      await page.evaluate(() => document.fonts.ready);
      const cdp = await page.context().newCDPSession(page);
      await cdp.send("DOM.enable"); await cdp.send("CSS.enable");
      const root = (await cdp.send("DOM.getDocument")).root.nodeId;
      // Match the original application typography: Space Grotesk display, Inter body.
      for (const [selector, expectedFamily] of [[".preview-main h1", "Space Grotesk"], [".preview-lead", "Inter"]]) {
        const { nodeId } = await cdp.send("DOM.querySelector", { nodeId: root, selector });
        const { fonts } = await cdp.send("CSS.getPlatformFontsForNode", { nodeId });
        assert(fonts.length > 0, `${selector} must render text`);
        assert(fonts.every(font => font.isCustomFont && font.familyName === expectedFamily),
          `${selector} must render Vietnamese entirely in ${expectedFamily}: ${JSON.stringify(fonts)}`);
      }
      await cdp.detach();
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
      await page.screenshot({ path: path.join(output, `app-fonts-${viewport.width}.png`), fullPage: true });
      await page.getByRole("button", { name: "Mở trợ lý", exact: true }).click();
      const chat = page.locator("#assistant-chat");
      await page.locator("#chat-send").click();
      await page.getByText("Vui lòng nhập câu hỏi.", { exact: true }).waitFor();
      await page.getByRole("button", { name: "Tiền bù và tiền khách đưa khác nhau thế nào?", exact: true }).click();
      assert.equal(await page.locator("#chat-send").isDisabled(), true);
      await page.locator(".chat-message.assistant").waitFor();
      assert.equal(await page.locator(".chat-source-card").count(), 0);
      assert(!/\[S\d+\]|staff\/.+\.md|backend/.test(await chat.innerText()));
      await page.screenshot({ path: path.join(output, `chat-${viewport.width}.png`) });
      // Review is an explicit mock display choice, not a role/authentication flag.
      await page.locator("[data-close-chat]").click();
      await page.locator("#review-sources").check();
      await page.getByRole("button", { name: "Mở trợ lý", exact: true }).click();
      await page.locator(".chat-source-card").waitFor();
      assert.match(await chat.innerText(), /\[S1\]/);
      await page.screenshot({ path: path.join(output, `review-${viewport.width}.png`) });
      await page.locator(".chat-source-card").click();
      await page.locator("#source-dialog[open]").waitFor();
      assert.equal(await page.locator("#source-path").textContent(), "staff/payment-process.md");
      await page.locator("#close-source").click();
      await page.locator("[data-close-chat]").click();
      await page.locator("#review-sources").uncheck();
      await page.getByRole("button", { name: "Mở trợ lý", exact: true }).click();
      assert.equal(await page.locator(".chat-source-card").count(), 0);
      assert(!/\[S\d+\]|staff\/.+\.md/.test(await chat.innerText()));
      await page.locator("[data-close-chat]").click();
      await page.locator("#review-sources").check();
      await page.getByRole("button", { name: "Mở trợ lý", exact: true }).click();
      await chat.getByRole("button", { name: "Hữu ích", exact: true }).click();
      assert.equal(await chat.getByRole("button", { name: "Hữu ích", exact: true }).getAttribute("aria-pressed"), "true");
      await chat.getByRole("button", { name: "Chưa hữu ích", exact: true }).click();
      assert.equal(await chat.getByRole("button", { name: "Hữu ích", exact: true }).getAttribute("aria-pressed"), "false");
      await chat.getByRole("button", { name: "EN", exact: true }).click();
      assert.equal(await page.locator("html").getAttribute("lang"), "en");
      await page.getByText("CyberHub assistant", { exact: true }).waitFor();
      await page.locator("#new-conversation").click();
      await page.locator("#cancel-reset").click();
      assert.equal(await page.locator(".chat-message.user").count(), 1);
      await page.locator("#new-conversation").click();
      await page.locator("#confirm-reset").click();

      const input = page.locator("#chat-question");
      await input.fill("What balance is required to start a session?");
      await input.press("Enter");
      await page.locator(".chat-loading").waitFor();
      await page.locator("#new-conversation").click();
      await page.locator("#confirm-reset").click();
      await page.waitForTimeout(650); // Verify the old delayed reply was cancelled.
      assert.equal(await page.locator(".chat-message").count(), 0);

      const payload = '<img src=x onerror="window.__rag_xss=1">';
      await input.fill(payload);
      await input.press("Enter");
      await page.locator(".chat-message.assistant").waitFor();
      assert.equal(await page.locator(".chat-message.user .chat-message-text").textContent(), payload);
      assert.equal(await page.locator("#chat-history img").count(), 0);
      assert.equal(await page.evaluate(() => window.__rag_xss), undefined);
      assert.equal(await page.locator(".chat-source-card").count(), 0);

      await page.locator("#chat-scenario").selectOption("error");
      await input.fill("How does settlement differ from cash received?");
      await input.press("Enter");
      await page.locator(".chat-error").waitFor();
      await page.screenshot({ path: path.join(output, `error-${viewport.width}.png`) });
      const users = await page.locator(".chat-message.user").count();
      await page.locator("#chat-scenario").selectOption("auto");
      await page.getByRole("button", { name: "Try again", exact: true }).click();
      await page.locator(".chat-source-card").waitFor();
      assert.equal(await page.locator(".chat-message.user").count(), users);
      assert.equal(await page.locator(".chat-error").count(), 0);

      await input.fill("First line"); await input.press("Shift+Enter");
      assert.match(await input.inputValue(), /\n/);
      await input.fill("😀".repeat(2000));
      assert.equal(await page.locator("#chat-count").textContent(), "2000");
      await input.fill("");
      await page.evaluate(() => {
        const input = document.getElementById("chat-question");
        input.value = "x".repeat(2001);
        input.dispatchEvent(new Event("input", { bubbles: true }));
      });
      await input.press("Enter");
      await page.getByText("Questions may contain up to 2,000 characters.", { exact: true }).waitFor();
      await input.fill("");
      const bounds = await chat.boundingBox();
      const composer = await page.locator("#chat-form").boundingBox();
      assert(bounds.x >= 0 && bounds.y >= 0 && bounds.x + bounds.width <= viewport.width + 1);
      assert(bounds.y + bounds.height <= viewport.height + 1);
      assert(composer.y + composer.height <= viewport.height + 1);
      assert.equal(await page.evaluate(() => localStorage.length), 0);
      assert.equal((await page.context().cookies()).length, 0);
      assert.deepEqual(forbidden, []);
      assert.deepEqual(errors, []);
      await page.goto(`${base}/?review=1`, { waitUntil: "networkidle" });
      assert.equal(await page.locator("#review-sources").isChecked(), true);
      results.push({ viewport, passed: true, api_requests: forbidden.length, javascript_errors: errors.length });
      await page.close();
    }
    console.log(JSON.stringify({ mode: "browser-only-ui-mock", results }, null, 2));
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
