// 客户端冒烟：用假 React 把每个工作台/面板都渲染一遍，抓未定义变量这类运行时错误
import fs from 'node:fs'

const FILE = 'E:/dsh-plugins/custom-plugins/dsh-media-workbench/client.js'
const src = fs.readFileSync(FILE, 'utf8')

let mod = null
const win = {
  __ModuleLoader__: { load: (m) => { mod = m } },
  __DSH_WORKBENCHES__: [],
  addEventListener() { },
  dispatchEvent() { },
  confirm: () => false,
  location: { origin: 'http://127.0.0.1' },
}

const R = {
  createElement: (t, p, ...c) => ({ t, p: p || {}, c: c.length <= 1 ? c[0] : c }),
  useState: (v) => [typeof v === 'function' ? v() : v, () => { }],
  useEffect: () => { },
  useRef: (v) => ({ current: v === undefined ? null : v }),
  useCallback: (f) => f,
  useMemo: (f) => f(),
  Fragment: 'Fragment',
}

const doc = {
  getElementById: () => null,
  createElement: () => ({ style: {}, click() { } }),
  head: { appendChild() { } },
  body: { appendChild() { } },
}

const code = new Function('window', 'document', 'fetch', src)
code(win, doc, () => Promise.resolve({ json: () => Promise.resolve({ ok: false }), text: () => Promise.resolve('') }))

if (!mod || typeof mod.factory !== 'function') { console.log('模块没加载'); process.exit(1) }
const api = mod.factory((n) => (n === 'react' ? R : {}))
api.apply()
const P = api.__panels

const seen = []
const errs = []

function render(el, path, depth = 0) {
  if (depth > 40) return
  if (el == null || typeof el === 'boolean') return
  if (Array.isArray(el)) { el.forEach((x, i) => render(x, path + '[' + i + ']', depth + 1)); return }
  if (typeof el === 'string' || typeof el === 'number') return
  if (typeof el.t === 'function') {
    const nm = el.t.name || 'anon'
    if (seen.includes(nm)) return
    seen.push(nm)
    let out
    try { out = el.t(el.p || {}) } catch (e) { errs.push(nm + ' @ ' + path + ' → ' + e.message); return }
    render(out, path + '>' + nm, depth + 1)
    return
  }
  render(el.c, path, depth + 1)
}

function run(name, fn) {
  try {
    const tree = fn()
    render(tree, name)
    console.log('✓ ' + name)
  } catch (e) {
    errs.push(name + ' 直接抛错 → ' + e.message)
    console.log('✗ ' + name + ' → ' + e.message)
  }
}

const reg = win.__DSH_WORKBENCHES__
console.log('注册的工作台:', reg.map((x) => x.id + '/' + x.title).join(' , '))
run('卡片墙(自媒体)', () => ({ t: P.MediaWorkbench, p: {}, c: [] }))
run('卡片墙(能力提升)', () => ({ t: P.GrowLab, p: {}, c: [] }))

const card = (id, title, group) => ({ id, title, group, desc: '', tag: '', detail: '说明文字' })
const noop = () => { }
for (const c of [
  card('hot', '今日热点'), card('inspire', '每日灵感'), card('capture', '采集台'),
  card('library', '稿库'), card('topics', '选题池'), card('self', '我的观点'),
  card('corpus', '我的语料库'), card('personas', '分身'), card('roundtable', '圆桌会议'),
  card('speech', '脱稿口播', 'grow'), card('review', '发布复盘', 'night'),
]) {
  run('面板 ' + c.id, () => ({ t: P.Detail, p: { card: c, onBack: noop, onWrite: noop }, c: [] }))
}
run('写观点弹框(有感而发)', () => ({ t: P.Composer, p: { topic: null, onClose: noop, onSaved: noop }, c: [] }))
run('写观点弹框(绑选题)', () => ({
  t: P.Composer,
  p: { topic: { id: 't1', title: '发1000条烂视频' }, onClose: noop, onSaved: noop }, c: [],
}))

console.log('\n渲染过的组件 ' + seen.length + ' 个')
if (errs.length) {
  console.log('发现问题 ' + errs.length + ' 个:')
  for (const e of errs) console.log(' - ' + e)
  process.exit(2)
}
console.log('渲染无异常')
