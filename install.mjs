#!/usr/bin/env node
/**
 * DSH 插件一键安装器
 *
 *   node install.mjs                 装全部
 *   node install.mjs --pick          交互式挑选要装哪些（推荐给别人用）
 *   node install.mjs my-memory       只装指定的（可写多个）
 *   node install.mjs --list          列出仓库里有哪些插件
 *   node install.mjs --profile xxx   装到指定 profile（默认 desktop）
 *   node install.mjs --dry           只打印要做什么，不落盘
 *   node install.mjs --yes           不问，直接按参数装（给 AI 用）
 *
 * 特性：
 *   - 自动处理前置依赖：装「自媒体工作台」会先装「工作台入口」，不然装完没地方点进去
 *   - 幂等：重复跑不会装两遍
 *   - 安全：写 profile 前备份、无 BOM 写入、写完回读校验
 */
import fs from 'node:fs'
import path from 'node:path'
import os from 'node:os'
import readline from 'node:readline'
import { fileURLToPath } from 'node:url'

const ROOT = path.dirname(fileURLToPath(import.meta.url))
const PKGS = path.join(ROOT, 'packages')
const args = process.argv.slice(2)
const flags = args.filter((a) => a.startsWith('--'))
const plain = args.filter((a) => !a.startsWith('--'))

const argVal = (name, fallback) => {
  const i = args.indexOf(name)
  return i >= 0 && args[i + 1] && !args[i + 1].startsWith('--') ? args[i + 1] : fallback
}
const profileName = argVal('--profile', 'desktop')
const dry = flags.includes('--dry')

const log = (...a) => console.log(...a)
const ok = (...a) => console.log('  ✓', ...a)
const warn = (...a) => console.log('  !', ...a)
const die = (msg) => {
  console.error('\n✗ ' + msg + '\n')
  process.exit(1)
}
const readJson = (p) => {
  try {
    return JSON.parse(fs.readFileSync(p, 'utf8').replace(/^\uFEFF/, ''))
  } catch {
    return null
  }
}

/* ---------------- 1. 收集仓库里的插件 ---------------- */
if (!fs.existsSync(PKGS)) die(`找不到 packages 目录：${PKGS}`)
const all = fs
  .readdirSync(PKGS, { withFileTypes: true })
  .filter((d) => d.isDirectory())
  .map((d) => {
    const dir = path.join(PKGS, d.name)
    const pkg = readJson(path.join(dir, 'package.json'))
    if (!pkg || !pkg.name) return null
    const meta = (pkg.dsh && pkg.dsh.market) || {}
    return {
      id: d.name,
      dir,
      pkg,
      name: pkg.name,
      label: meta.label || pkg.description || '',
      group: meta.group || '其它',
      requires: (pkg.dsh && pkg.dsh.requires) || [],
      tag: meta.tag || '',
    }
  })
  .filter(Boolean)
  .sort((a, b) => a.group.localeCompare(b.group) || a.name.localeCompare(b.name))

if (!all.length) die('packages 里没有可用的插件（每个都要有 package.json 的 name 字段）')

if (flags.includes('--list')) {
  log(`\n仓库里共 ${all.length} 个插件：\n`)
  let g = ''
  for (const p of all) {
    if (p.group !== g) {
      g = p.group
      log(`  ${g}`)
    }
    log(`    ${p.name.padEnd(26)} ${p.label}`)
  }
  log('\n用法：node install.mjs            装全部')
  log('      node install.mjs --pick     挑选着装（推荐）')
  log('      node install.mjs <名字>      装指定几个')
  log('')
  process.exit(0)
}

/* ---------------- 2. 选哪些 ---------------- */
let picked = all.filter((p) => !p.tag.includes('needs-scripts') || flags.includes('--with-scripts'))

if (plain.length) {
  picked = all.filter((p) => plain.includes(p.name) || plain.includes(p.id))
  const missing = plain.filter((n) => !picked.some((t) => t.name === n || t.id === n))
  if (missing.length) die(`仓库里没有这些插件：${missing.join(', ')}\n  用 --list 看看有哪些`)
}

if (flags.includes('--pick')) {
  if (!process.stdin.isTTY) die('--pick 需要交互终端。给 AI 用请直接传插件名，例如：node install.mjs dsh-media-workbench')
  log('\n选择要装的插件（输入编号，空格或逗号分隔；直接回车=全装）\n')
  let g = ''
  const idx = []
  picked.forEach((p, i) => {
    if (p.group !== g) {
      g = p.group
      log(`  ${g}`)
    }
    const req = p.requires.length ? `  ← 需要先装 ${p.requires.join(', ')}` : ''
    log(`    ${String(i + 1).padStart(2)}. ${p.name.padEnd(26)} ${p.label}${req}`)
    idx.push(p)
  })
  log('\n  0. 全部装')
  const answer = await ask('\n你的选择：')
  const nums = answer
    .split(/[\s,，、]+/)
    .filter(Boolean)
    .map(Number)
  if (!nums.length || nums.includes(0)) {
    // 全装
  } else {
    const bad = nums.filter((n) => !Number.isInteger(n) || n < 1 || n > idx.length)
    if (bad.length) die(`编号超出范围：${bad.join(', ')}`)
    picked = nums.map((n) => idx[n - 1])
  }
}

/* ---------------- 3. 解析前置依赖（拓扑排序） ---------------- */
const byName = new Map(all.map((p) => [p.name, p]))
const ordered = []
const seen = new Set()
const visiting = new Set()
function visit(p, chain = []) {
  if (seen.has(p.name)) return
  if (visiting.has(p.name)) {
    warn(`循环依赖，跳过该链：${[...chain, p.name].join(' → ')}`)
    return
  }
  visiting.add(p.name)
  for (const r of p.requires) {
    const dep = byName.get(r)
    if (!dep) {
      warn(`${p.name} 声明依赖 ${r}，但仓库里没有这个包，跳过这一条`)
      continue
    }
    visit(dep, [...chain, p.name])
  }
  visiting.delete(p.name)
  seen.add(p.name)
  ordered.push(p)
}
for (const p of picked) visit(p)

const autoAdded = ordered.filter((p) => !picked.includes(p))
if (autoAdded.length) {
  log(`\n为了能用，额外带上前置：${autoAdded.map((p) => p.name).join('、')}`)
}

/* ---------------- 4. 找 DSH 与 profile ---------------- */
const dshHome = process.env.DSH_HOME || path.join(os.homedir(), '.dsh')
if (!fs.existsSync(dshHome)) {
  die(
    `找不到 DSH 数据目录：${dshHome}\n` +
      `  先安装 DeepSeek Harness 桌面端并运行过一次，或设置环境变量 DSH_HOME 指向它。`
  )
}
const profileDir = path.join(dshHome, 'profiles', profileName)
const manifestPath = path.join(profileDir, 'package.json')
if (!fs.existsSync(manifestPath)) {
  const others = fs.existsSync(path.join(dshHome, 'profiles'))
    ? fs.readdirSync(path.join(dshHome, 'profiles')).join(', ')
    : '无'
  die(`找不到 profile "${profileName}"：${manifestPath}\n  现有的 profile：${others}`)
}
const manifest = readJson(manifestPath)
if (!manifest) die(`profile 的 package.json 无法解析（可能是 BOM 或格式坏了）：${manifestPath}`)

log(`\nDSH 目录   ${dshHome}`)
log(`Profile    ${profileName}`)
log(`要装       ${ordered.length} 个${dry ? '（--dry，不会落盘）' : ''}\n`)

/* ---------------- 5. 装机 ---------------- */
const deps = { ...(manifest.dependencies || {}) }
const bundles = [...((manifest.dsh && manifest.dsh.profile && manifest.dsh.profile.bundles) || [])]
const installed = []
const needsDeps = []
const needsScripts = []

for (const t of ordered) {
  const dest = path.join(profileDir, 'node_modules', t.name)
  log(`→ ${t.name}`)

  if (!dry) {
    fs.rmSync(dest, { recursive: true, force: true })
    fs.mkdirSync(path.dirname(dest), { recursive: true })
    fs.cpSync(t.dir, dest, { recursive: true, dereference: true })
  }
  ok(`复制到 node_modules/${t.name}`)

  deps[t.name] = `file:./node_modules/${t.name}`
  if (!bundles.includes(t.name)) bundles.push(t.name)
  ok('已登记 dependencies + bundles')

  const extDeps = Object.keys(t.pkg.dependencies || {}).filter(
    (d) => !d.startsWith('@deepseek-ai/') && !d.startsWith('node:')
  )
  if (extDeps.length) needsDeps.push(`${t.name} → ${extDeps.join(', ')}`)
  if (t.tag.includes('needs-scripts')) needsScripts.push(t.name)
  installed.push(t.name)
}

if (dry) {
  log('\n（--dry 结束，什么都没改）\n')
  process.exit(0)
}

/* ---------------- 6. 写回 profile ---------------- */
const stamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19)
const backup = `${manifestPath}.bak-${stamp}`
fs.copyFileSync(manifestPath, backup)
ok(`已备份 profile 清单 → ${path.basename(backup)}`)

manifest.dependencies = deps
manifest.dsh = manifest.dsh || {}
manifest.dsh.profile = manifest.dsh.profile || {}
manifest.dsh.profile.bundles = bundles
fs.writeFileSync(manifestPath, JSON.stringify(manifest, null, 2) + '\n', { encoding: 'utf8' })

const back = fs.readFileSync(manifestPath, 'utf8')
if (back.charCodeAt(0) === 0xfeff) die('写出来的文件带 BOM，已中止。用备份还原：' + backup)
try {
  JSON.parse(back)
} catch (e) {
  die(`写完之后 JSON 解析失败：${e.message}\n  用备份还原：${backup}`)
}
ok('回读校验通过（无 BOM、JSON 可解析）')

/* ---------------- 7. 收尾 ---------------- */
log(`\n装好了 ${installed.length} 个：${installed.join('、')}\n`)
if (needsScripts.length) {
  log('这些插件还要本机脚本才能干活（脚本不进 git，见 setup/scripts/README.md）：')
  for (const n of needsScripts) log(`  ${n}`)
  log('')
}
if (needsDeps.length) {
  log('这几个插件还需要外部依赖，在 profile 目录里装：')
  for (const line of needsDeps) log(`  ${line}`)
  log(`\n  cd "${profileDir}" && pnpm add <包名>\n`)
}
log(`下一步：完全退出 DSH 再重开（托盘退出，不是关窗口）。`)
log(`还原：把 ${path.basename(backup)} 改回 package.json 即可。\n`)

/* ---------------- 工具：读一行输入 ---------------- */
function ask(q) {
  const rl = readline.createInterface({ input: process.stdin, output: process.stdout })
  return new Promise((resolve) => rl.question(q, (a) => (rl.close(), resolve(a.trim()))))
}
