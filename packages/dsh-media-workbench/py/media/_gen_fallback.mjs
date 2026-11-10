import fs from 'node:fs'

const raw = fs.readFileSync('E:\\desktop\\media\\_topics46.json', 'utf8').replace(/^\uFEFF/, '')
const d = JSON.parse(raw)
const slim = d.topics.map((t) => ({ t: t.title, s: t.score, b: t.board || '', h: (t.hook || '').slice(0, 60) }))
const js = 'const FALLBACK_TOPICS = ' + JSON.stringify(slim, null, 0) + '\n'
fs.writeFileSync('E:\\desktop\\media\\_fallback_topics.txt', js, 'utf8')
console.log('生成兜底数据', slim.length, '条，', js.length, '字节')
console.log('样例:', slim[0].s, slim[0].t)
