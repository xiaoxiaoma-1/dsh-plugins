import fs from 'node:fs'

const P = 'E:\\dsh-plugins\\custom-plugins\\dsh-podcast\\index.js'
const lines = fs.readFileSync(P, 'utf8').split('\n')
fs.copyFileSync(P, P + '.bak-before-nowready')

// 找到 ready 块（1-based → 0-based）
const readyIdx = lines.findIndex((l) => /^\s*ctx\.on\('ready'/.test(l))
if (readyIdx < 0) { console.log('找不到 ready 块'); process.exit(1) }

// 从 readyIdx 往后找配对的 "  })"（缩进 2 空格）
let closeIdx = -1
for (let i = readyIdx + 1; i < lines.length; i++) {
  if (/^\s{0,2}\}\)\s*$/.test(lines[i])) { closeIdx = i; break }
}
if (closeIdx < 0) { console.log('找不到 ready 的闭合'); process.exit(1) }
console.log('ready 块行区间(1-based):', readyIdx + 1, '→', closeIdx + 1)

// 先改 conn 取值方式
for (let i = readyIdx; i < closeIdx; i++) {
  if (lines[i].includes("const conn = ctx.get('connection')")) {
    lines[i] = lines[i].replace(
      "const conn = ctx.get('connection')",
      "const conn = ctx.connection ?? ctx.get?.('connection')",
    )
    console.log('已改 conn 取值（第', i + 1, '行）')
  }
}

// 再从后往前删闭合行和 ready 行
lines.splice(closeIdx, 1)
lines.splice(readyIdx, 1)

// 整体缩进减 2（ready 块内的代码原来多缩进了一层），让结构回到 apply 直下
for (let i = readyIdx; i < closeIdx - 1; i++) {
  if (lines[i].startsWith('  ')) lines[i] = lines[i].slice(2)
}

fs.writeFileSync(P, lines.join('\n'), 'utf8')
const out = fs.readFileSync(P, 'utf8')
console.log('---')
console.log('还有 ctx.on(\'ready\'):', out.includes("ctx.on('ready'"))
console.log('conn 取值行:', (out.match(/const conn = .*/) || [''])[0])
console.log('reg( 调用数:', (out.match(/reg\(conn, disposers, \{/g) || []).length)
console.log('行数:', out.split('\n').length)
