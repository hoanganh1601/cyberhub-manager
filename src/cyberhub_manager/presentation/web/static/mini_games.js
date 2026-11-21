"use strict";

// Game Center: điểm số chỉ điều khiển trải nghiệm trên trình duyệt. Khi hoàn thành,
// máy chủ vẫn tự bốc phần thưởng và áp hạn mức lượt/ngày; client không gửi số xu.
Object.assign(copy, {
  gameCenter: ["Game Center", "Game Center"],
  gameCenterSub: ["Chơi mini-game, nhận xu máy chủ và đổi phần thưởng. Điểm trong game không phải tiền.", "Play mini-games, earn server-issued coins and redeem rewards. In-game scores are not money."],
  gamePlay: ["Chơi ngay", "Play now"], gameFeatured: ["Nổi bật", "Featured"],
  gameInternal: ["CyberHub", "CyberHub"], gameSponsored: ["Được tài trợ", "Sponsored"],
  gameReward: ["Có thưởng", "Rewarded"], gameInstructions: ["Hướng dẫn", "How to play"],
  gameScore: ["Điểm", "Score"], gameGoal: ["Mục tiêu", "Goal"], gameRestart: ["Chơi lại", "Restart"],
  gameClaim: ["Nhận thưởng", "Claim reward"], gameCompleted: ["Hoàn thành! Bạn đã mở khóa một lượt nhận thưởng.", "Completed! You unlocked one reward draw."],
  gameServerReward: ["Xu do máy chủ quyết định và bị giới hạn theo lượt trong ngày.", "Coins are server-decided and limited by daily plays."],
  game2048Help: ["Dùng phím mũi tên hoặc vuốt để ghép ô. Đạt ô 128 để hoàn thành.", "Use arrow keys or swipe to merge tiles. Reach 128 to finish."],
  gameSnakeHelp: ["Điều khiển rắn ăn 5 mục tiêu. Không chạm tường hoặc chính mình.", "Guide the snake to eat 5 targets. Avoid walls and yourself."],
  gameMemoryHelp: ["Lật và ghép đủ 6 cặp biểu tượng.", "Reveal and match all 6 icon pairs."],
});

const DOT3_MINI_GAMES = [
  {code:"wheel", name:"Vòng quay may mắn", icon:"🎡", color:"rgba(5,196,239,.16)", help:"Quay thưởng mỗi ngày", wheel:true, featured:true},
  {code:"2048", name:"Cyber 2048", icon:"🔢", color:"rgba(139,92,246,.18)", help:"Ghép số, chinh phục ô 128", featured:true},
  {code:"snake", name:"Snake Arena", icon:"🐍", color:"rgba(16,185,129,.16)", help:"Săn mục tiêu trong đấu trường"},
  {code:"memory", name:"Puzzle ký ức", icon:"🧩", color:"rgba(245,164,0,.16)", help:"Ghép cặp biểu tượng CyberHub"},
  {code:"bubble", name:"Bubble Blast", icon:"🫧", color:"rgba(14,165,233,.16)", help:"Đối tác có thể thuê vị trí game", sponsored:true, disabled:true},
  {code:"candy", name:"Candy Match", icon:"🍬", color:"rgba(244,63,94,.16)", help:"Vị trí game tài trợ sắp mở", sponsored:true, disabled:true},
];

function dot3MiniHub(data) {
  const policy = new Map((data.catalog || []).map(game => [game.code, game]));
  const games = DOT3_MINI_GAMES.map(game => ({...game, ...(policy.get(game.code) || {})}));
  const cards = games.map(g => `<article class="dot3-game-card ${g.featured ? "featured" : ""}" style="--game-color:${g.color}">
    <div class="dot3-game-art" aria-hidden="true">${g.icon}</div><div class="dot3-game-meta">
      <span class="dot3-chip live">${!g.active || g.disabled ? "Sắp mở" : t("gameReward")}</span>
      <span class="dot3-chip ${g.sponsored ? "sponsor" : ""}">${t(g.sponsored ? "gameSponsored" : "gameInternal")}</span>
      ${g.featured ? `<span class="dot3-chip">${t("gameFeatured")}</span>` : ""}</div>
    <h3>${esc(g.name)}</h3><p>${esc(g.help)}</p>
    <button class="btn ${g.featured ? "primary" : ""}" data-mini-open="${g.code}" ${!g.active || g.disabled ? "disabled" : ""}>${t("gamePlay")}</button>
  </article>`).join("");
  return `<section class="dot3-center"><div class="dot3-center-head"><div><h2>${t("gameCenter")}</h2><p>${t("gameCenterSub")}</p></div>
    <div class="dot3-wallet-pill">${icon("coin")} ${data.wallet.balance} ${t("dot3CoinUnit")}</div></div><div class="dot3-game-grid">${cards}</div></section>`;
}

let miniCleanup = null;
function closeMiniGame() { if (miniCleanup) miniCleanup(); miniCleanup = null; $("#dot3-mini-layer")?.remove(); }
function miniShell(game, help) {
  closeMiniGame();
  document.body.insertAdjacentHTML("beforeend", `<div class="dot3-mini-layer" id="dot3-mini-layer"><section class="dot3-mini-shell" role="dialog" aria-modal="true">
    <header class="dot3-mini-head"><div class="dot3-game-art" style="--game-color:${game.color}">${game.icon}</div><div><h2>${esc(game.name)}</h2><p>${t(help)}</p></div><button class="btn ghost" data-mini-close aria-label="Đóng">×</button></header>
    <div class="dot3-mini-body"><div class="dot3-mini-status"><span id="mini-score">${t("gameScore")}: 0</span><span>${t("gameServerReward")}</span></div><div id="mini-stage"></div><div id="mini-message"></div><div class="dot3-mini-actions" id="mini-actions"></div></div>
  </section></div>`);
}
function miniWin() {
  const message = $("#mini-message"), actions = $("#mini-actions");
  if (message) message.innerHTML = `<div class="notice success">${t("gameCompleted")}</div>`;
  if (actions) actions.innerHTML = `<button class="btn primary" data-mini-claim>${icon("coin")}${t("gameClaim")}</button>`;
}
async function claimMiniReward() {
  const button = $("[data-mini-claim]"); if (!button || button.disabled) return;
  button.disabled = true;
  try {
    const result = await api("/portal/game/spin", {method:"POST", body:{}});
    toast(result.coins ? `${t("dot3Won")} ${result.coins} ${t("dot3CoinUnit")} 🎉` : t("dot3NoLuck"));
    closeMiniGame(); portalUI.gameAt = 0; await loadCustomerGame();
  } catch (error) { button.disabled = false; toast(error.message, true); }
}

function add2048(board) {
  const empty = []; board.forEach((v,i) => {if(!v) empty.push(i);});
  if (empty.length) board[empty[Math.floor(Math.random()*empty.length)]] = Math.random()<.9 ? 2 : 4;
}
function start2048(game) {
  miniShell(game,"game2048Help"); let board=Array(16).fill(0),score=0,won=false; add2048(board);add2048(board);
  const stage=$("#mini-stage");
  const draw=()=>{stage.innerHTML=`<div class="mini-2048 dot3-mini-board">${board.map(v=>`<div class="mini-2048-cell" data-value="${Math.min(v,128)}">${v}</div>`).join("")}</div>`;$("#mini-score").textContent=`${t("gameScore")}: ${score}`;};
  const slide=line=>{const values=line.filter(Boolean);for(let i=0;i<values.length-1;i++)if(values[i]===values[i+1]){values[i]*=2;score+=values[i];values.splice(i+1,1);}return values.concat(Array(4-values.length).fill(0));};
  const move=dir=>{if(won)return;const old=board.join();let next=Array(16).fill(0);for(let n=0;n<4;n++){let ids=dir==="left"?[n*4,n*4+1,n*4+2,n*4+3]:dir==="right"?[n*4+3,n*4+2,n*4+1,n*4]:dir==="up"?[n,n+4,n+8,n+12]:[n+12,n+8,n+4,n];const out=slide(ids.map(i=>board[i]));ids.forEach((id,i)=>next[id]=out[i]);}board=next;if(board.join()!==old)add2048(board);draw();if(board.some(v=>v>=128)){won=true;miniWin();}};
  const key=e=>{const map={ArrowLeft:"left",ArrowRight:"right",ArrowUp:"up",ArrowDown:"down"};if(map[e.key]){e.preventDefault();move(map[e.key]);}};document.addEventListener("keydown",key);
  let sx=0,sy=0;stage.addEventListener("pointerdown",e=>{sx=e.clientX;sy=e.clientY;});stage.addEventListener("pointerup",e=>{const dx=e.clientX-sx,dy=e.clientY-sy;if(Math.max(Math.abs(dx),Math.abs(dy))>24)move(Math.abs(dx)>Math.abs(dy)?dx>0?"right":"left":dy>0?"down":"up");});
  miniCleanup=()=>document.removeEventListener("keydown",key);draw();
}

function startMemory(game) {
  miniShell(game,"gameMemoryHelp");const icons=["🎮","🖥️","⚡","🎧","🏆","💎"],cards=[...icons,...icons].sort(()=>Math.random()-.5);let first=null,lock=false,matched=0,moves=0;
  const stage=$("#mini-stage");stage.innerHTML=`<div class="mini-memory dot3-mini-board">${cards.map((v,i)=>`<button data-memory="${i}" aria-label="Thẻ ${i+1}">${v}</button>`).join("")}</div>`;
  stage.addEventListener("click",e=>{const b=e.target.closest("[data-memory]");if(!b||lock||b.classList.contains("done")||b===first)return;b.classList.add("open");if(!first){first=b;return;}moves++;$("#mini-score").textContent=`${t("gameScore")}: ${moves}`;if(cards[+first.dataset.memory]===cards[+b.dataset.memory]){first.classList.add("done");b.classList.add("done");first=null;if(++matched===icons.length)miniWin();}else{lock=true;const a=first;first=null;setTimeout(()=>{a.classList.remove("open");b.classList.remove("open");lock=false;},650);}});
}

function startSnake(game) {
  miniShell(game,"gameSnakeHelp");const stage=$("#mini-stage");stage.innerHTML=`<canvas class="mini-snake dot3-mini-board" width="400" height="400"></canvas><div class="mini-pad"><button class="btn up" data-dir="up">↑</button><button class="btn left" data-dir="left">←</button><button class="btn down" data-dir="down">↓</button><button class="btn right" data-dir="right">→</button></div>`;
  const canvas=$("canvas",stage),ctx=canvas.getContext("2d"),size=20;let snake=[{x:10,y:10},{x:9,y:10}],dir={x:1,y:0},next=dir,food={x:15,y:10},score=0,done=false;
  const setDir=name=>{const d={up:{x:0,y:-1},down:{x:0,y:1},left:{x:-1,y:0},right:{x:1,y:0}}[name];if(d&&!(d.x===-dir.x&&d.y===-dir.y))next=d;};
  const key=e=>{const m={ArrowUp:"up",ArrowDown:"down",ArrowLeft:"left",ArrowRight:"right"};if(m[e.key]){e.preventDefault();setDir(m[e.key]);}};document.addEventListener("keydown",key);stage.addEventListener("click",e=>{const b=e.target.closest("[data-dir]");if(b)setDir(b.dataset.dir);});
  const draw=()=>{ctx.fillStyle="#08111f";ctx.fillRect(0,0,400,400);ctx.fillStyle="#f5a400";ctx.fillRect(food.x*size+3,food.y*size+3,size-6,size-6);ctx.fillStyle="#10b981";snake.forEach((p,i)=>ctx.fillRect(p.x*size+2,p.y*size+2,size-4,size-4));};
  const timer=setInterval(()=>{if(done)return;dir=next;const head={x:snake[0].x+dir.x,y:snake[0].y+dir.y};if(head.x<0||head.y<0||head.x>=20||head.y>=20||snake.some(p=>p.x===head.x&&p.y===head.y)){done=true;clearInterval(timer);$("#mini-message").innerHTML=`<div class="notice error">Game over</div>`;$("#mini-actions").innerHTML=`<button class="btn" data-mini-open="snake">${t("gameRestart")}</button>`;return;}snake.unshift(head);if(head.x===food.x&&head.y===food.y){score++;food={x:Math.floor(Math.random()*20),y:Math.floor(Math.random()*20)};$("#mini-score").textContent=`${t("gameScore")}: ${score}`;if(score>=5){done=true;clearInterval(timer);miniWin();}}else snake.pop();draw();},120);
  miniCleanup=()=>{clearInterval(timer);document.removeEventListener("keydown",key);};draw();
}

function openMiniGame(code) {
  const game=DOT3_MINI_GAMES.find(g=>g.code===code);if(!game||game.disabled)return;
  if(game.wheel){$("#dot3-wheel-stage")?.scrollIntoView({behavior:"smooth",block:"start"});return;}
  if(code==="2048")start2048(game);if(code==="snake")startSnake(game);if(code==="memory")startMemory(game);
}
document.addEventListener("click",event=>{const open=event.target.closest("[data-mini-open]");if(open&&!open.disabled)openMiniGame(open.dataset.miniOpen);if(event.target.closest("[data-mini-close]"))closeMiniGame();if(event.target.closest("[data-mini-claim]"))claimMiniReward();if(event.target.id==="dot3-mini-layer")closeMiniGame();});
