// 导出浏览器 cookie 到文件（供 python 复用登录态）
const fs = await import('node:fs');
const PORT = process.env.CDP_PORT || '9333';
const list = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json();
const page = list.find(t => t.type === 'page' && /xiaoeknow/.test(t.url)) || list.find(t => t.type === 'page');
const ws = new WebSocket(page.webSocketDebuggerUrl);
let id = 0; const pending = new Map();
function send(m, p = {}) { return new Promise((res, rej) => { const i = ++id; pending.set(i, { res, rej }); ws.send(JSON.stringify({ id: i, method: m, params: p })); }); }
ws.addEventListener('message', (ev) => { const m = JSON.parse(ev.data); if (m.id && pending.has(m.id)) { const p = pending.get(m.id); pending.delete(m.id); m.error ? p.rej(new Error(JSON.stringify(m.error))) : p.res(m.result); } });
await new Promise(r => ws.addEventListener('open', r));
const { cookies } = await send('Network.getAllCookies');
const keep = cookies.filter(c => /xiaoeknow|xetlk|xiaoe-tech/.test(c.domain));
const simple = keep.map(c => ({ name: c.name, value: c.value, domain: c.domain, path: c.path }));
fs.writeFileSync('E:/desktop/media/_xet_cookies.json', JSON.stringify(simple, null, 1), 'utf8');
console.log('COOKIE_N', simple.length);
console.log('NAMES', simple.map(c => c.name).join(', ').slice(0, 500));
process.exit(0);
