import fs from 'node:fs'

const P = 'E:\\dsh-plugins\\custom-plugins\\dsh-podcast\\client.js'
let src = fs.readFileSync(P, 'utf8')
const fallback = fs.readFileSync('E:\\desktop\\media\\_fallback_topics.txt', 'utf8').trim()

fs.copyFileSync(P, P + '.bak-before-picker')
let edits = 0

function rep(oldS, newS, label) {
  if (!src.includes(oldS)) { console.log('!! 未找到锚点:', label); return }
  src = src.replace(oldS, newS)
  edits++
  console.log('ok:', label)
}

// A. 在 PodcastApp 之前插入兜底选题常量
rep(
  '    function PodcastApp() {',
  '    /* 兜底选题（后端 /topics 拿不到时也能选，46 条按分数排） */\n' +
  '    ' + fallback + '\n\n    function PodcastApp() {',
  'A 插入兜底常量'
)

// B. state 增加 pool / poolOpen
rep(
  "      const [topic, setTopic] = useState('')\n      const [topics, setTopics] = useState([])",
  "      const [topic, setTopic] = useState('')\n      const [pool, setPool] = useState(FALLBACK_TOPICS)\n      const [poolOpen, setPoolOpen] = useState(false)\n      const [topics, setTopics] = useState([])",
  'B 加 pool state'
)

// C. loadTopics 拉 60 条并归一化
rep(
  "          const r = await apiFetch('/topics?limit=12')\n          setTopics(r.topics || [])",
  "          const r = await apiFetch('/topics?limit=60')\n          const rows = (r.topics || []).map((t) => ({ t: t.title, s: t.score, b: t.board || '', h: t.hook || '' }))\n          if (rows.length) { setPool(rows); setTopics(rows) }",
  'C loadTopics 归一化'
)

// D. chips 区改成「可展开的选题池选择器」
const oldChips = `          topics.length > 0 && h('div', { className: 'pc-chips' }, [
            h('span', { className: 'pc-chip pc-chip-gold' }, \`今日选题池 \${topics.length} 条\`),
            ...topics.slice(0, 3).map((t, i) => h('span', {
              key: i,
              className: 'pc-chip' + (t.title === topic ? ' pc-chip-on' : ''),
              title: t.hook || t.angle || '',
              onClick: () => { if (!busy) setTopic(t.title) },
            }, t.title.length > 14 ? t.title.slice(0, 14) + '…' : t.title)),
          ]),`

const newChips = `          h('div', { className: 'pc-chips' }, [
            h('span', {
              className: 'pc-chip pc-chip-gold pc-chip-btn',
              onClick: () => { if (!busy) setPoolOpen((v) => !v) },
            }, poolOpen ? '收起选题池 ▲' : \`从选题池选话题 · \${pool.length} 条 ▾\`),
            topic && h('span', { className: 'pc-chip pc-chip-on', title: topic }, '已选：' + (topic.length > 16 ? topic.slice(0, 16) + '…' : topic)),
          ]),
          poolOpen && h('div', { className: 'pc-pool-list' },
            pool.map((t, i) => h('div', {
              key: i,
              className: 'pc-pool-row' + (t.t === topic ? ' pc-pool-row-on' : ''),
              onClick: () => { if (busy) return; setTopic(t.t); setPoolOpen(false) },
            }, [
              h('span', { className: 'pc-pool-score' }, String(t.s == null ? '' : t.s)),
              h('span', { className: 'pc-pool-title' }, t.t),
              t.b ? h('span', { className: 'pc-pool-board' }, t.b) : null,
            ]))),`

rep(oldChips, newChips, 'D 选题池选择器')

// E. 文案：去掉「自动填充」
rep(
  "h('span', { className: 'pc-pool' }, [h('i', { key: 'd', className: 'pc-dot' }), '从选题池自动填充']),",
  "h('span', { className: 'pc-pool' }, [h('i', { key: 'd', className: 'pc-dot' }), '上面点开就是全部选题，自己挑']),",
  'E 文案改'
)

// F. CSS：选择器样式（用普通字符串，避免脚本自身解析 ${}）
const cssNew = [
  '.pc-chip-on{ border-color:${C.gold};color:${C.gold};max-width:100%;overflow:hidden;text-overflow:ellipsis; }',
  '.pc-chip-btn:hover{ background:color-mix(in srgb,${C.gold} 18%,transparent); }',
  '.pc-pool-list{ margin-top:12px;max-height:300px;overflow-y:auto;border:1px solid ${C.border};border-radius:12px;background:${C.base}; }',
  '.pc-pool-row{ display:flex;align-items:center;gap:9px;padding:9px 11px;cursor:pointer;border-bottom:1px solid ${C.border}; }',
  '.pc-pool-row:last-child{ border-bottom:none; }',
  '.pc-pool-row:hover{ background:${C.cell2}; }',
  '.pc-pool-row-on{ background:color-mix(in srgb,${C.gold} 14%,transparent); }',
  '.pc-pool-score{ font-size:12px;font-weight:700;color:${C.gold};min-width:22px;text-align:right;flex:none; }',
  '.pc-pool-title{ flex:1;min-width:0;font-size:13px;line-height:1.5;overflow:hidden;text-overflow:ellipsis;white-space:nowrap; }',
  '.pc-pool-board{ font-size:11px;color:${C.sub};flex:none; }',
].join('\n')
rep(
  '.pc-chip-on{ border-color:${C.gold};color:${C.gold}; }',
  cssNew,
  'F 选择器样式'
)

fs.writeFileSync(P, src, 'utf8')
const b = fs.readFileSync(P)
console.log('---')
console.log('改动数:', edits, '/ 6')
console.log('BOM:', b[0] === 0xef ? '有(要修)' : '无')
console.log('行数:', src.split('\n').length)
