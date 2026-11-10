// 把 dsh-podcast 接进 profile：拷贝文件 + 写 dependencies + bundles + 校验（node 写，不带 BOM）
import fs from 'node:fs'
import path from 'node:path'

const SRC = 'E:\\dsh-plugins\\custom-plugins\\dsh-podcast'
const DST = 'E:\\DSH-data\\.dsh\\profiles\\desktop\\node_modules\\dsh-podcast'
const PF = 'E:\\DSH-data\\.dsh\\profiles\\desktop\\package.json'

fs.mkdirSync(DST, { recursive: true })
for (const f of ['index.js', 'client.js', 'package.json', 'cordis.patch.yml', 'icon.svg']) {
  const s = path.join(SRC, f)
  if (fs.existsSync(s)) fs.copyFileSync(s, path.join(DST, f))
}

const raw = fs.readFileSync(PF, 'utf8')
const j = JSON.parse(raw)   // 先确认原文件能解析
j.dependencies = j.dependencies || {}
j.dependencies['dsh-podcast'] = 'file:E:/dsh-plugins/custom-plugins/dsh-podcast'
j.dsh = j.dsh || {}
j.dsh.profile = j.dsh.profile || {}
const b = j.dsh.profile.bundles || []
if (!b.includes('dsh-podcast')) b.push('dsh-podcast')
j.dsh.profile.bundles = b
fs.writeFileSync(PF, JSON.stringify(j, null, 2), 'utf8')

// 校验
const b3 = fs.readFileSync(PF).subarray(0, 3)
console.log('BOM bytes:', [...b3].join(','))
const chk = JSON.parse(fs.readFileSync(PF, 'utf8'))
console.log('JSON ok, bundles =', chk.dsh.profile.bundles.length)
console.log('has dsh-podcast dep:', !!chk.dependencies['dsh-podcast'])
console.log('has dsh-podcast bundle:', chk.dsh.profile.bundles.includes('dsh-podcast'))
console.log('copied:', fs.readdirSync(DST).join(', '))
