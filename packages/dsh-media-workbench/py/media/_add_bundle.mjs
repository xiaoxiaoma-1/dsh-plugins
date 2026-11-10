import fs from 'node:fs'

const P = 'E:\\DSH-data\\.dsh\\profiles\\desktop\\package.json'
const j = JSON.parse(fs.readFileSync(P, 'utf8'))
const list = j.dsh.profile.bundles
if (!list.includes('dsh-podcast')) list.push('dsh-podcast')
fs.writeFileSync(P, JSON.stringify(j, null, 2) + '\n', 'utf8')

const raw = fs.readFileSync(P)
const bom = raw[0] === 0xef && raw[1] === 0xbb && raw[2] === 0xbf
const check = JSON.parse(fs.readFileSync(P, 'utf8'))
console.log('写入完成')
console.log('BOM:', bom ? '有（要修！）' : '无')
console.log('bundles 数量:', check.dsh.profile.bundles.length)
console.log('含 dsh-podcast:', check.dsh.profile.bundles.includes('dsh-podcast'))
console.log('顺序:', check.dsh.profile.bundles.slice(-4).join(' → '))
