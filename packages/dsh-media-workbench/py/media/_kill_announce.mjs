import fs from 'node:fs'
import path from 'node:path'

const DIR = 'E:\\DSH-data\\.dsh\\our-free-model'
const S = path.join(DIR, 'settings.json')
const F = path.join(DIR, 'feed.json')
const TARGET = '2026-11-08-v2.8.2-picks-star-ask'

// 备份
for (const p of [S, F]) {
  if (fs.existsSync(p)) fs.copyFileSync(p, p + '.bak-20261108')
}

// 1) settings：把 feedUrl 指向死地址，阻断远程公告；确保该 id 已在已读列表
const st = JSON.parse(fs.readFileSync(S, 'utf8'))
st.feedUrl = 'http://127.0.0.1:9/blocked-feed.json'
if (!Array.isArray(st.announcementsAcked)) st.announcementsAcked = []
if (!st.announcementsAcked.includes(TARGET)) st.announcementsAcked.push(TARGET)
fs.writeFileSync(S, JSON.stringify(st, null, 2) + '\n', 'utf8')

// 2) feed 缓存：删掉这条公告，其余保留
let removed = 0
if (fs.existsSync(F)) {
  const fd = JSON.parse(fs.readFileSync(F, 'utf8'))
  const rows = Array.isArray(fd.announcements) ? fd.announcements : []
  const keep = rows.filter((r) => {
    if (r && r.id === TARGET) { removed++; return false }
    return true
  })
  fd.announcements = keep
  fd.source = 'blocked'
  fs.writeFileSync(F, JSON.stringify(fd, null, 2) + '\n', 'utf8')
}

// 校验
const st2 = JSON.parse(fs.readFileSync(S, 'utf8'))
const fd2 = JSON.parse(fs.readFileSync(F, 'utf8'))
for (const p of [S, F]) {
  const b = fs.readFileSync(p)
  if (b[0] === 0xef && b[1] === 0xbb && b[2] === 0xbf) console.log('!! BOM in', p)
}
console.log('feedUrl      =', st2.feedUrl)
console.log('acked 含目标  =', st2.announcementsAcked.includes(TARGET))
console.log('已删公告条数  =', removed)
console.log('剩余公告条数  =', fd2.announcements.length)
console.log('remaining top3 =', fd2.announcements.slice(0, 3).map((x) => x.id).join(', '))
