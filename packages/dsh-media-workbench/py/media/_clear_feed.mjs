import fs from 'node:fs'

const F = 'E:\\DSH-data\\.dsh\\our-free-model\\feed.json'
const TARGET = '2026-11-08-v2.8.2-picks-star-ask'
if (fs.existsSync(F)) {
  const d = JSON.parse(fs.readFileSync(F, 'utf8'))
  const before = (d.announcements || []).length
  d.announcements = []
  d.source = 'blocked-by-user'
  d.blockedReason = 'user removed startup ad 2026-11-08'
  fs.writeFileSync(F, JSON.stringify(d, null, 2) + '\n', 'utf8')
  console.log('feed.json 清空前条数:', before, '→ 现在:', JSON.parse(fs.readFileSync(F, 'utf8')).announcements.length)
}
