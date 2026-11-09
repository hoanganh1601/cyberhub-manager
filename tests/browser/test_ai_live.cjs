/* Real authenticated browser/API flow. Local models required at the target app. */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright");

(async () => {
  const base = process.env.RAG_LIVE_URL || "http://127.0.0.1:8059";
  const output = process.env.RAG_SCREENSHOT_DIR || "/tmp/rag-live-browser";
  fs.mkdirSync(output, { recursive: true });
  const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROME_BIN || "/opt/google/chrome/chrome", args: ["--no-sandbox"] });
  const results = [];
  try {
    for (const viewport of [{width:1280,height:720},{width:390,height:844}]) {
      const page = await browser.newPage({ viewport });
      const errors = [];
      page.on("pageerror", error => errors.push(error.message));
      await page.goto(base);
      await page.locator('#login-form [name="username"]').fill("nhanvien01");
      await page.locator('#login-form [name="password"]').fill("demo123");
      await page.locator('#login-form [type="submit"]').click();
      await page.locator('[data-open-chat]').waitFor();
      await page.locator('[data-open-chat]').click();
      const chat = page.locator('#assistant-chat');
      const input = page.locator('#chat-question');
      await input.fill("Cần bao nhiêu số dư để mở phiên?");
      const pending = page.waitForResponse(r => r.url().endsWith('/api/assistant/messages') && r.request().method() === 'POST', {timeout:60000});
      await page.locator('#chat-send').click();
      const response = await pending, data = await response.json();
      assert.equal(response.status(),200,JSON.stringify(data));
      assert.equal(data.grounded,true,JSON.stringify(data));
      assert.deepEqual(Object.keys(response.request().postDataJSON()).sort(),['language','question']);
      assert(response.request().headers()['x-csrf-token']);
      await page.locator('.chat-message.assistant').waitFor();
      assert.equal(await page.locator('.chat-source-card').count(),0);
      assert(!/\[S\d+\]|staff\/.+\.md/.test(await chat.innerText()));
      await page.screenshot({path:path.join(output,`live-chat-${viewport.width}.png`)});
      await page.locator('#review-sources').check();
      await page.locator('.chat-source-card').first().click();
      await page.locator('#source-dialog[open]').waitFor();
      assert((await page.locator('#source-path').innerText()).endsWith('.md'));
      await page.locator('#close-source').click();
      await page.locator('#review-sources').uncheck();
      await chat.getByRole('button',{name:'Hữu ích',exact:true}).click();
      assert.equal(await chat.getByRole('button',{name:'Hữu ích',exact:true}).getAttribute('aria-pressed'),'true');
      await chat.getByRole('button',{name:'EN',exact:true}).click();
      assert.equal(await page.locator('html').getAttribute('lang'),'en');
      assert.equal(await page.locator('#chat-title').textContent(),'CyberHub assistant');
      await chat.getByRole('button',{name:'VI',exact:true}).click();

      async function clear() {
        await page.locator('#new-conversation').click();
        await page.locator('#confirm-reset').click();
        assert.equal(await page.locator('.chat-message').count(),0);
      }
      await clear();
      // Transport errors are injected only for UI-state verification, not model scoring.
      let fail = true;
      await page.route('**/api/assistant/messages',async route => {
        if (fail) { fail=false; await route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({error:{code:'ASSISTANT_UNAVAILABLE'}})}); }
        else await route.continue();
      });
      await input.fill('Tiền bù và tiền khách đưa khác nhau thế nào?');
      await input.press('Enter');
      await page.locator('.chat-error').waitFor();
      await page.screenshot({path:path.join(output,`live-error-${viewport.width}.png`)});
      const retried = page.waitForResponse(r => r.url().endsWith('/api/assistant/messages'), {timeout:60000});
      await page.getByRole('button',{name:'Thử lại',exact:true}).click();
      assert.equal((await retried).status(),200);
      await page.locator('.chat-error').waitFor({state:'detached'});
      assert.equal(await page.locator('.chat-message.user').count(),1);
      await page.unroute('**/api/assistant/messages');
      await clear();
      await page.route('**/api/assistant/messages',route=>route.fulfill({status:429,headers:{'Retry-After':'1'},contentType:'application/json',body:'{"error":{"code":"RATE_LIMITED"}}'}));
      await input.fill('quota'); await input.press('Enter');
      await page.locator('.chat-error').waitFor();
      assert.equal(await page.locator('#chat-send').isDisabled(),true);
      await page.waitForTimeout(2100);
      assert.equal(await page.locator('#chat-send').isDisabled(),false);
      await page.unroute('**/api/assistant/messages');
      await clear();

      const payload = '<img src=x onerror="window.__rag_xss=1"> [S1]';
      await page.route('**/api/assistant/messages',route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({answer:payload,citations:[],grounded:false})}));
      await input.fill(payload); await input.press('Enter');
      await page.locator('.chat-message.assistant').waitFor();
      assert.equal(await page.locator('.chat-message.user .chat-message-text').textContent(),payload);
      assert.equal(await page.locator('#chat-history img').count(),0);
      assert.equal(await page.evaluate(()=>window.__rag_xss),undefined);
      await page.unroute('**/api/assistant/messages');
      await clear();

      // Clear/abort while a reply is pending: late replies must not enter the new conversation.
      await page.route('**/api/assistant/messages',async route=>{
        await new Promise(resolve=>setTimeout(resolve,800));
        try { await route.fulfill({status:200,contentType:'application/json',body:'{"answer":"late","citations":[],"grounded":false}'}); } catch {}
      });
      await input.fill('pending'); await input.press('Enter');
      await page.locator('.chat-loading').waitFor(); await clear();
      await page.waitForTimeout(1100);
      assert.equal(await page.locator('.chat-message').count(),0);
      await page.unroute('**/api/assistant/messages');
      const box = await chat.boundingBox(), form = await page.locator('#chat-form').boundingBox();
      assert(box.x>=0 && box.y>=0 && box.x+box.width<=viewport.width+1 && box.y+box.height<=viewport.height+1);
      assert(form.y+form.height<=viewport.height+1);
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
      assert.equal(await page.evaluate(()=>[...Object.keys(localStorage)].some(k=>/chat|assistant|question/.test(k))),false);
      // Revoke real server session without updating the page; focus must clear old chat.
      const session = await (await page.request.get(`${base}/api/session`)).json();
      assert.equal((await page.request.post(`${base}/api/logout`,{headers:{'X-CSRF-Token':session.csrf_token},data:{}})).status(),200);
      await page.evaluate(()=>window.dispatchEvent(new Event('focus')));
      await page.locator('#login-form').waitFor();
      assert.equal(await page.locator('#assistant-widget').isHidden(),true);
      assert.deepEqual(errors,[]);
      results.push({viewport,real_model_answer:data.answer,request_id:data.request_id,passed:true,javascript_errors:errors.length});
      await page.close();
    }
    console.log(JSON.stringify({mode:'authenticated-local-rag-browser',results},null,2));
  } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
