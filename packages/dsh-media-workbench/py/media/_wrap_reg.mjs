import fs from 'node:fs'

const P = 'E:\\dsh-plugins\\custom-plugins\\dsh-podcast\\index.js'
let lines = fs.readFileSync(P, 'utf8').split('\n')
fs.copyFileSync(P, P + '.bak-before-dbg')

let changed = 0
for (let i = 0; i < lines.length; i++) {
  if (lines[i].includes('disposers.push(conn.fetch.register({')) {
    lines[i] = lines[i].replace('disposers.push(conn.fetch.register({', 'reg(conn, disposers, {')
    // 从下一行起找第一处以 })) 结尾的块尾
    for (let j = i + 1; j < Math.min(i + 60, lines.length); j++) {
      if (/^\s*\}\)\)\s*$/.test(lines[j])) {
        lines[j] = lines[j].replace('}))', '})')
        changed++
        break
      }
    }
  }
}

fs.writeFileSync(P, lines.join('\n'), 'utf8')
const out = fs.readFileSync(P, 'utf8')
console.log('改写的路由数:', changed)
console.log('残留 disposers.push(conn.fetch.register:', (out.match(/disposers\.push\(conn\.fetch\.register/g) || []).length)
console.log('reg( 调用数:', (out.match(/reg\(conn, disposers, \{/g) || []).length)
