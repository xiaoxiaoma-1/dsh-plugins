import fs from 'node:fs'

const P = 'E:\\dsh-plugins\\custom-plugins\\dsh-podcast\\client.js'
const NEW = 'E:\\desktop\\media\\_new_podcastapp.js'

const lines = fs.readFileSync(P, 'utf8').split('\n')
// 定位要替换的区间：从 "--------- 主组件" 注释行 到 PodcastApp 的结束大括号（下一行是注册注释）
let start = -1
let end = -1
for (let i = 0; i < lines.length; i++) {
  if (start < 0 && lines[i].includes('主组件')) { start = i; continue }
  if (start >= 0 && lines[i].includes("const name = 'dsh-podcast'")) { end = i - 1; break }
}
if (start < 0 || end < 0) {
  console.error('定位失败 start=', start, 'end=', end)
  process.exit(1)
}
// 回退：end 上面如果有空行也一并替换
while (end > start && lines[end].trim() === '') end--

const block = fs.readFileSync(NEW, 'utf8').replace(/\s+$/, '')
const before = lines.slice(0, start)
const after = lines.slice(end + 1)

// 备份
fs.copyFileSync(P, P + '.bak-before-v2ui')

const out = [...before, block, '', ...after].join('\n')
fs.writeFileSync(P, out, 'utf8')

const b = fs.readFileSync(P)
console.log('替换行区间:', start + 1, '→', end + 1, '(共', end - start + 1, '行)')
console.log('新文件行数:', out.split('\n').length)
console.log('BOM:', b[0] === 0xef ? '有(要修)' : '无')
console.log('含「AI播客生成器」:', out.includes('AI播客生成器'))
console.log('含 pc-go 按钮:', out.includes('pc-go'))
