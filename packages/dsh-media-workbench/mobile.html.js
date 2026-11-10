const html = String.raw`<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover,maximum-scale=1,user-scalable=no">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="theme-color" content="#0b0e12">
<title>口袋</title>
<style>
  *{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
  html,body{margin:0;height:100%;overflow:hidden}
  body{
    background:#0b0e12;color:#e6e9ee;
    font:15px/1.65 -apple-system,"PingFang SC","Microsoft YaHei",sans-serif;
    padding:env(safe-area-inset-top) 0 env(safe-area-inset-bottom);
    display:flex;flex-direction:column;
  }
  button{font-family:inherit;cursor:pointer;border:none;background:none;color:inherit}
  input,textarea{font-family:inherit}

  /* 顶部状态 */
  .top{flex:none;padding:14px 18px 10px;display:flex;align-items:center;gap:8px;font-size:12.5px;color:#8b939e}
  .dot{width:7px;height:7px;border-radius:50%;background:#78dc8c;flex:none}
  .dot.off{background:#e09182}
  .top b{color:#c9d1da;font-weight:500}

  /* 内容区 */
  .main{flex:1;overflow-y:auto;-webkit-overflow-scrolling:touch;padding:0 16px 16px}
  .pane{display:none}
  .pane.on{display:block}

  /* 撞：卡片 */
  .stack{position:relative;min-height:320px;margin-top:6px}
  .card{
    position:absolute;inset:0;border-radius:18px;background:#1c2129;
    border:1px solid #2b333d;padding:20px 18px;display:flex;flex-direction:column;
    transition:transform .28s cubic-bezier(.22,1,.36,1),opacity .28s;
    will-change:transform;touch-action:pan-y;
  }
  .card.behind{transform:scale(.94) translateY(10px);opacity:.5;border-color:#242b34}
  .card .who{font-size:11.5px;color:#7f8894;margin-bottom:12px}
  .card .claim{flex:1;font-size:17.5px;line-height:1.72;color:#f2f3f5;font-weight:500}
  .card .hintline{margin-top:14px;font-size:12px;color:#5c6672;text-align:center}

  .swipehint{display:flex;justify-content:space-between;padding:0 6px;margin-top:14px;font-size:12.5px}
  .swipehint .no{color:#e09182}
  .swipehint .yes{color:#8fd39b}
  .counter{text-align:center;font-size:12px;color:#6f7883;margin-top:12px}

  /* 理由输入 */
  .sheet{
    position:fixed;inset:0;background:rgba(8,10,13,.72);backdrop-filter:blur(8px);
    display:none;flex-direction:column;justify-content:flex-end;z-index:50;
  }
  .sheet.on{display:flex}
  .sheetbox{
    background:#151a20;border-radius:20px 20px 0 0;padding:18px 18px calc(18px + env(safe-area-inset-bottom));
    border-top:1px solid #2b333d;
  }
  .sheetq{font-size:13px;color:#9aa4b1;margin-bottom:10px;line-height:1.6}
  .sheetq b{color:#f2ce84}
  textarea{width:100%;min-height:110px;padding:12px;border-radius:12px;font-size:15px;line-height:1.7;
    background:#0e1217;color:#e6e9ee;border:1px solid #2b333d;resize:none;outline:none}
  textarea:focus{border-color:rgba(217,169,74,.6)}
  .sheetacts{display:flex;gap:10px;margin-top:12px}
  .btn{flex:1;padding:13px 0;border-radius:12px;font-size:15px;text-align:center;border:1px solid #333c47;color:#b9c2cd}
  .btn:active{transform:scale(.98)}
  .btn.gold{background:rgba(217,169,74,.16);border-color:rgba(217,169,74,.5);color:#f2ce84}
  .btn[disabled]{opacity:.4;pointer-events:none}

  /* 说 */
  .saybox{margin-top:8px}
  .saybox textarea{min-height:150px;font-size:16px}
  .sayacts{display:flex;gap:10px;margin-top:12px;align-items:center}
  .micbig{flex:none;width:64px;height:64px;border-radius:50%;background:rgba(217,169,74,.14);
    border:2px solid rgba(217,169,74,.5);display:flex;align-items:center;justify-content:center;font-size:24px}
  .micbig:active{background:rgba(217,169,74,.3)}
  .recent{margin-top:22px}
  .recent h4{font-size:12.5px;color:#7f8894;font-weight:500;margin:0 0 10px}
  .recent .it{padding:12px 0;border-top:1px solid #1e242c;font-size:14px;color:#cfd6de;line-height:1.6}

  /* 进度 */
  .prog{margin-top:8px}
  .pcard{border-radius:14px;background:#1c2129;border:1px solid #2b333d;padding:15px;margin-bottom:11px}
  .pcard .t{font-size:15px;color:#f0f2f4;margin-bottom:3px}
  .pcard .d{font-size:12px;color:#7f8894;margin-bottom:9px}
  .bar{height:5px;border-radius:3px;background:#0e1217;overflow:hidden}
  .bar i{display:block;height:100%;background:linear-gradient(90deg,#e3ba63,#c8973c);transition:width .4s}
  .kpi{display:flex;gap:10px;margin-top:6px}
  .kpi div{flex:1;border-radius:12px;background:#151a20;padding:12px;text-align:center}
  .kpi .n{font-size:22px;font-weight:700;color:#f2ce84;font-variant-numeric:tabular-nums}
  .kpi .l{font-size:11px;color:#7f8894;margin-top:2px}

  /* 底部导航 */
  .nav{flex:none;display:flex;border-top:1px solid #1e242c;background:#0e1217;
    padding-bottom:env(safe-area-inset-bottom)}
  .nav .tab{flex:1;padding:9px 0 11px;text-align:center;font-size:11px;color:#5c6672;line-height:1.35}
  .nav .tab .ic{display:block;font-size:19px;margin-bottom:2px}
  .nav .tab.on{color:#f2ce84}

  /* 首次输 key */
  .gate{position:fixed;inset:0;background:#0b0e12;display:flex;flex-direction:column;
    justify-content:center;padding:28px;z-index:99}
  .gate h3{margin:0 0 6px;font-size:19px}
  .gate p{margin:0 0 18px;font-size:13px;color:#7f8894;line-height:1.7}
  .gate input{width:100%;padding:13px;border-radius:12px;background:#151a20;color:#e6e9ee;
    border:1px solid #2b333d;font-size:14px;outline:none}
  .gate input:focus{border-color:rgba(217,169,74,.6)}
  .gate button{width:100%;margin-top:14px;padding:14px;border-radius:12px;font-size:15px;
    background:rgba(217,169,74,.16);border:1px solid rgba(217,169,74,.5);color:#f2ce84}
  .empty{text-align:center;color:#6f7883;font-size:13px;padding:60px 20px;line-height:1.9}
</style>
</head>
<body>

<div class="gate" id="gate">
  <h3>口袋 · 先连一次</h3>
  <p>输入你电脑上的 api-key（<code>E:\DSH-data\.dsh\openai-gateway\api-key</code> 文件里的那串），
     只存这台手机，不传出去。</p>
  <input id="keyin" type="password" placeholder="粘贴 key" autocomplete="off">
  <button onclick="saveKey()">连上</button>
</div>

<div class="top"><span class="dot" id="dot"></span><span id="stat"><b>连接中…</b></span></div>

<div class="main">
  <!-- 撞 -->
  <div class="pane on" id="pane-clash">
    <div class="stack" id="stack"></div>
    <div class="swipehint"><span class="no">← 左滑 不认同</span><span class="yes">右滑 认同 →</span></div>
    <div class="counter" id="counter"></div>
  </div>

  <!-- 说 -->
  <div class="pane" id="pane-say">
    <div class="saybox">
      <textarea id="idea" placeholder="想到什么就先说一句，不用成型"></textarea>
      <div class="sayacts">
        <button class="micbig" onclick="voice()">🎙</button>
        <button class="btn gold" style="flex:1" onclick="saveIdea()">记下来</button>
      </div>
    </div>
    <div class="recent">
      <h4>最近记的</h4>
      <div id="ideas"></div>
    </div>
  </div>

  <!-- 进度 -->
  <div class="pane" id="pane-prog">
    <div class="prog" id="prog"></div>
  </div>
</div>

<div class="nav">
  <button class="tab on" data-p="clash" onclick="go('clash')"><span class="ic">◉</span>撞</button>
  <button class="tab" data-p="say" onclick="go('say')"><span class="ic">✎</span>说</button>
  <button class="tab" data-p="prog" onclick="go('prog')"><span class="ic">▤</span>进度</button>
</div>

<div class="sheet" id="sheet">
  <div class="sheetbox">
    <div class="sheetq" id="sheetq"></div>
    <textarea id="why" placeholder="写多少都行，但不能空"></textarea>
    <div class="sheetacts">
      <button class="btn" onclick="closeSheet()">取消</button>
      <button class="btn gold" id="savebtn" onclick="submitVote()">存进我的观点</button>
    </div>
  </div>
</div>

<script>
const LS_KEY = 'dsh_pocket_key';
let KEY = localStorage.getItem(LS_KEY) || '';
let cur = null;          // 当前卡片
let pendingVerdict = '';

function api(path, opt) {
  opt = opt || {};
  return fetch(path, {
    method: opt.method || 'GET',
    headers: Object.assign({ 'authorization': 'Bearer ' + KEY }, opt.body ? { 'content-type': 'application/json' } : {}),
    body: opt.body ? JSON.stringify(opt.body) : undefined,
  }).then(r => { if (r.status === 401) throw new Error('key 不对'); return r.json() });
}

function saveKey() {
  const v = document.getElementById('keyin').value.trim();
  if (!v) return;
  KEY = v; localStorage.setItem(LS_KEY, v);
  document.getElementById('gate').style.display = 'none';
  boot();
}

function go(p) {
  document.querySelectorAll('.pane').forEach(e => e.classList.remove('on'));
  document.getElementById('pane-' + p).classList.add('on');
  document.querySelectorAll('.nav .tab').forEach(e => e.classList.toggle('on', e.dataset.p === p));
  if (p === 'prog') loadProg();
  if (p === 'say') loadIdeas();
}

/* ---------- 撞 ---------- */
let queue = [];
function loadClash() {
  api('/api/dsh-media/clash/list?limit=20').then(j => {
    if (!j.ok) { setStat('读不到观点：' + (j.error || '')); return; }
    queue = j.items || [];
    document.getElementById('counter').textContent = '已表态 ' + j.done + ' · 还剩 ' + j.left;
    renderTop();
  }).catch(e => setStat('连接失败：' + e.message));
}

function renderTop() {
  const stack = document.getElementById('stack');
  stack.innerHTML = '';
  if (!queue.length) {
    stack.innerHTML = '<div class="empty">这条流空了。<br>过会儿再来翻两张。</div>';
    return;
  }
  const next = queue[1], top = queue[0];
  if (next) {
    const b = document.createElement('div');
    b.className = 'card behind';
    stack.appendChild(b);
  }
  const c = document.createElement('div');
  c.className = 'card';
  c.innerHTML = '<div class="who">' + (top.author ? '@' + String(top.author).slice(0, 22) : '来源未标') + '</div>'
    + '<div class="claim">' + esc(top.claim) + '</div>'
    + '<div class="hintline">左滑不认同 · 右滑认同</div>';
  stack.appendChild(c);
  bindSwipe(c, top);
}

function esc(s) { return String(s || '').replace(/[&<>]/g, m => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[m])) }

function bindSwipe(el, item) {
  let x0 = 0, y0 = 0, dx = 0, active = false;
  el.addEventListener('touchstart', e => {
    const t = e.touches[0]; x0 = t.clientX; y0 = t.clientY; dx = 0; active = true;
    el.style.transition = 'none';
  }, { passive: true });
  el.addEventListener('touchmove', e => {
    if (!active) return;
    const t = e.touches[0];
    dx = t.clientX - x0;
    const dy = t.clientY - y0;
    if (Math.abs(dy) > Math.abs(dx) + 12) { active = false; el.style.transform = ''; return; }
    el.style.transform = 'translateX(' + dx + 'px) rotate(' + (dx / 22) + 'deg)';
    el.style.borderColor = dx > 30 ? 'rgba(120,220,140,.8)' : dx < -30 ? 'rgba(214,120,96,.8)' : '#2b333d';
  }, { passive: true });
  el.addEventListener('touchend', () => {
    if (!active) return;
    active = false;
    el.style.transition = '';
    if (dx > 70) { fly(el, 1); openSheet(item, 'agree'); }
    else if (dx < -70) { fly(el, -1); openSheet(item, 'disagree'); }
    else { el.style.transform = ''; el.style.borderColor = '#2b333d'; }
  });
}

function fly(el, dir) {
  el.style.transform = 'translateX(' + (dir * 420) + 'px) rotate(' + (dir * 18) + 'deg)';
  el.style.opacity = '0';
}

function openSheet(item, verdict) {
  cur = item; pendingVerdict = verdict;
  document.getElementById('sheetq').innerHTML =
    (verdict === 'agree' ? '你<b>认同</b>这句话' : '你<b>不认同</b>这句话')
    + ' —— ' + (verdict === 'agree' ? '还能想到什么？' : '为什么反对？');
  document.getElementById('why').value = '';
  document.getElementById('savebtn').disabled = true;
  document.getElementById('sheet').classList.add('on');
}

document.getElementById('why').addEventListener('input', e => {
  document.getElementById('savebtn').disabled = !e.target.value.trim();
});

function closeSheet() {
  document.getElementById('sheet').classList.remove('on');
  if (cur) renderTop();
}

function submitVote() {
  const why = document.getElementById('why').value.trim();
  if (!why || !cur) return;
  api('/api/dsh-media/clash/answer', {
    method: 'POST',
    body: { atomId: cur.id, verdict: pendingVerdict, why },
  }).then(j => {
    if (j.ok) {
      queue.shift();
      document.getElementById('sheet').classList.remove('on');
      renderTop();
    } else setStat('没存上：' + (j.error || ''));
  }).catch(e => setStat('失败：' + e.message));
}

/* ---------- 说 ---------- */
function saveIdea() {
  const el = document.getElementById('idea');
  const v = el.value.trim();
  if (!v) return;
  api('/api/dsh-media/myideas/add', { method: 'POST', body: { content: v, source: 'mobile' } })
    .then(j => {
      if (j.ok) { el.value = ''; setStat('记下了'); loadIdeas(); }
      else setStat('失败：' + (j.error || ''));
    }).catch(e => setStat('失败：' + e.message));
}

function loadIdeas() {
  api('/api/dsh-media/myideas/list?limit=8').then(j => {
    if (!j.ok) return;
    const box = document.getElementById('ideas');
    box.innerHTML = (j.ideas || []).map(x =>
      '<div class="it">' + esc(x.content) + '</div>').join('') || '<div class="it" style="color:#6f7883">还没有</div>';
  }).catch(() => {});
}

function voice() {
  const R = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!R) { setStat('这个浏览器不支持语音，用键盘听写吧'); return; }
  const r = new R();
  r.lang = 'zh-CN'; r.interimResults = false; r.maxAlternatives = 1;
  setStat('听着…');
  r.onresult = e => {
    document.getElementById('idea').value += e.results[0][0].transcript;
    setStat('听到了');
  };
  r.onerror = () => setStat('没听清');
  r.onend = () => {};
  r.start();
}

/* ---------- 进度 ---------- */
function loadProg() {
  api('/api/dsh-media/dash/stats').then(j => {
    const box = document.getElementById('prog');
    if (!j || !j.ok) { box.innerHTML = '<div class="empty">读不到进度</div>'; return; }
    let h = '<div class="kpi">'
      + '<div><div class="n">' + (j.views || 0) + '</div><div class="l">观点</div></div>'
      + '<div><div class="n">' + (j.posts || 0) + '</div><div class="l">稿库</div></div>'
      + '<div><div class="n">' + (j.live || 0) + '</div><div class="l">直播</div></div>'
      + '</div>';
    box.innerHTML = h;
  }).catch(() => {
    document.getElementById('prog').innerHTML = '<div class="empty">读不到进度</div>';
  });
}

/* ---------- 状态 ---------- */
function setStat(t) {
  document.getElementById('stat').innerHTML = '<b>' + esc(t) + '</b>';
}

function boot() {
  setStat('连着');
  document.getElementById('dot').className = 'dot';
  loadClash();
}

if (KEY) { document.getElementById('gate').style.display = 'none'; boot(); }
else { document.getElementById('gate').style.display = 'flex'; }
</script>
</body>
</html>`;
export default html;
