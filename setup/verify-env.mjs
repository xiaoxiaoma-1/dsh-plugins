#!/usr/bin/env node
/**
 * 环境体检：逐项检查 ENVIRONMENT.md 里列的依赖，告诉你缺什么、怎么补。
 *
 *   node setup/verify-env.mjs           检查全部
 *   node setup/verify-env.mjs --core    只查第一级（核心）
 *   node setup/verify-env.mjs --json    输出 JSON，方便 AI 解析
 */
import fs from 'node:fs'
import path from 'node:path'
import os from 'node:os'
import { execFileSync } from 'node:child_process'

const args = process.argv.slice(2)
const onlyCore = args.includes('--core')
const asJson = args.includes('--json')

const rows = []
const push = (level, id, name, status, detail) => rows.push({ level, id, name, status, detail })

const tryCmd = (cmd, cmdArgs = ['--version']) => {
  try {
    const out = execFileSync(cmd, cmdArgs, { encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'], timeout: 8000 })
    return (out || '').split('\n')[0].trim()
  } catch {
    return null
  }
}
const hasDir = (p) => {
  try {
    return fs.statSync(p).isDirectory()
  } catch {
    return false
  }
}
const dirSizeGB = (p) => {
  if (!hasDir(p)) return 0
  let total = 0
  const walk = (d) => {
    for (const e of fs.readdirSync(d, { withFileTypes: true })) {
      const fp = path.join(d, e.name)
      try {
        if (e.isDirectory()) walk(fp)
        else total += fs.statSync(fp).size
      } catch {}
    }
  }
  walk(p)
  return total / 1024 ** 3
}

/* ---------------- 覆盖路径（可用环境变量顶掉） ---------------- */
const TOOLS = process.env.DSH_TOOLS_DIR || 'E:\\tools'
const DSH_HOME = process.env.DSH_HOME || path.join(os.homedir(), '.dsh')

/* ---------------- 第一级：核心 ---------------- */
push('core', 'C1', 'Windows x64', os.platform() === 'win32' ? 'ok' : 'miss', `${os.platform()} ${os.arch()} ${os.release()}`)

push('core', 'C2', 'DSH 数据目录', hasDir(DSH_HOME) ? 'ok' : 'miss', DSH_HOME)

const nodeV = process.versions.node
push('core', 'C3', 'Node.js ≥22', parseInt(nodeV) >= 22 ? 'ok' : 'warn', `v${nodeV}`)

const pyPaths = [
  process.env.DSH_PYTHON,
  path.join(TOOLS, 'asr', '.venv', 'Scripts', 'python.exe'),
  path.join(process.env.LOCALAPPDATA || '', 'Programs', 'Python', 'Python312', 'python.exe'),
].filter(Boolean)
const pyHit = pyPaths.find((p) => fs.existsSync(p))
const pyV = pyHit ? tryCmd(pyHit, ['--version']) : tryCmd('python', ['--version'])
push('core', 'C4', 'Python 3.12', pyV ? 'ok' : 'miss', pyV ? `${pyV} @ ${pyHit || 'PATH'}` : '找不到 python.exe')

const gitV = tryCmd('git', ['--version'])
push('core', 'C5', 'Git', gitV ? 'ok' : 'miss', gitV || '未安装')

const ffV = tryCmd('ffmpeg', ['-version'])
push('core', 'C6', 'ffmpeg', ffV ? 'ok' : 'warn', ffV ? ffV.slice(0, 60) : '不在 PATH（只影响音视频转码）')

/* ---------------- Python 包（用 pip list 一次拿全，比逐个 import 快几十倍） ---------------- */
{
  const need = [
    ['faster_whisper', 'faster-whisper'],
    ['funasr', 'funasr'],
    ['edge_tts', 'edge-tts'],
    ['av', 'av'],
  ]
  const cands = [...new Set([pyHit, ...pyPaths, 'python'].filter(Boolean))]
  let best = null
  for (const py of cands) {
    let installed = null
    try {
      const out = execFileSync(py, ['-m', 'pip', 'list', '--format=freeze'], {
        encoding: 'utf8',
        stdio: ['ignore', 'pipe', 'ignore'],
        timeout: 90000,
      })
      installed = new Set(out.split('\n').map((l) => l.split('==')[0].trim().toLowerCase()))
    } catch {
      continue
    }
    if (!installed.size) continue
    const miss = need.filter(([, pipName]) => !installed.has(pipName.toLowerCase())).map(([imp]) => imp)
    if (!best || miss.length < best.miss.length) best = { py, miss }
    if (miss.length === 0) break
  }
  if (best) {
    push(
      'core',
      'C4b',
      'Python 语音包',
      best.miss.length === 0 ? 'ok' : best.miss.length < need.length ? 'warn' : 'miss',
      best.miss.length ? `缺 ${best.miss.join(', ')}（解释器 ${best.py}）` : `齐全（解释器 ${best.py}）`
    )
  } else {
    push('core', 'C4b', 'Python 语音包', 'miss', '找不到能用的 pip（先确认 C4 过了）')
  }
}

/* ---------------- 第二级：工具 ---------------- */
if (!onlyCore) {
  const tools = [
    ['T1', 'DouyinLiveRecorder', [path.join(TOOLS, 'DouyinLiveRecorder')]],
    ['T2', 'JDK 25', [path.join(TOOLS, 'jdk25')]],
    ['T3', 'Ghidra', [path.join(TOOLS, 'ghidra_12.1.4_PUBLIC'), path.join(TOOLS, 'ghidra_12.2_PUBLIC')]],
    ['T4', 'rizin', [path.join(TOOLS, 'rizin')]],
    ['T5', 'apktool', [path.join(TOOLS, 'apktool')]],
    ['T6', '7-Zip', ['C:\\Program Files\\7-Zip', 'C:\\Program Files (x86)\\7-Zip', path.join(TOOLS, '7z')]],
  ]
  for (const [id, name, paths] of tools) {
    const hit = paths.find(hasDir)
    push('tools', id, name, hit ? 'ok' : 'miss', hit || `都没有：${paths.join(' / ')}`)
  }
  const snipCands = [
    path.join(process.env.LOCALAPPDATA || '', 'Microsoft', 'WindowsApps', 'SnippingTool.exe'),
    'C:\\Windows\\System32\\SnippingTool.exe',
  ]
  const snipHit = snipCands.find((p) => fs.existsSync(p))
  // WindowsApps 里的是应用执行别名，existsSync 可能不认，退回 where 再找一次
  const snipWhere = snipHit ? null : tryCmd('where', ['SnippingTool.exe'])
  const snipOk = Boolean(snipHit || snipWhere)
  push('tools', 'T7', 'SnippingTool', snipOk ? 'ok' : 'warn', snipHit || snipWhere || '找不到（Win11 通常自带；没有的话 dsh-shot 用不了）')

  /* ---------------- 第三级：模型资产 ---------------- */
  const models = [
    ['M1', 'soulx-podcast', path.join(TOOLS, 'soulx-podcast')],
    ['M2', 'CosyVoice', path.join(TOOLS, 'CosyVoice')],
    ['M3', 'GPT-SoVITS', path.join(TOOLS, 'sovits')],
    ['M4', 'RVC', path.join(TOOLS, 'RVC20260718Nvidia')],
    ['M5', 'dfnet', path.join(TOOLS, 'dfnet')],
    ['M6', 'mineru', path.join(TOOLS, 'mineru-venv')],
  ]
  for (const [id, name, p] of models) {
    if (hasDir(p)) {
      const gb = dirSizeGB(p)
      push('models', id, name, gb > 0.05 ? 'ok' : 'warn', `${gb.toFixed(1)}GB`)
    } else {
      push('models', id, name, 'skip', '未安装（按需，不影响其它插件）')
    }
  }

  /* ---------------- 环境变量（进程里读不到就读注册表，User 级要新进程才生效） ---------------- */
  const userEnv = (() => {
    if (process.platform !== 'win32') return {}
    try {
      const out = execFileSync('reg', ['query', 'HKCU\\Environment'], {
        encoding: 'utf8',
        stdio: ['ignore', 'pipe', 'ignore'],
      })
      const map = {}
      for (const line of out.split(/\r?\n/)) {
        const m = line.match(/^\s+(\S+)\s+REG_[A-Z_]+\s+(.*)$/)
        if (m) map[m[1].toUpperCase()] = m[2].trim()
      }
      return map
    } catch {
      return {}
    }
  })()
  const envs = ['DSH_HOME', 'DSH_PYTHON', 'DSH_ASR_SCRIPT', 'DSH_PET_PY', 'DSH_PET_SCRIPT', 'DSH_FINANCE_DIR']
  for (const e of envs) {
    const inProc = process.env[e]
    const inUser = userEnv[e.toUpperCase()]
    if (inProc) push('env', e, e, 'ok', `${inProc}（当前进程）`)
    else if (inUser) push('env', e, e, 'ok', `${inUser}（用户环境变量，重启 DSH 后生效）`)
    else push('env', e, e, 'warn', '未设置（插件会用代码里的默认值）')
  }
}

/* ---------------- 输出 ---------------- */
if (asJson) {
  console.log(JSON.stringify({ platform: os.platform(), node: nodeV, rows }, null, 2))
  process.exit(0)
}

const icon = { ok: '✓', warn: '!', miss: '✗', skip: '-' }
const groupTitle = { core: '第一级 · 核心', tools: '第二级 · 工具', models: '第三级 · 模型（按需）', env: '环境变量' }
let cur = ''
for (const r of rows) {
  if (r.level !== cur) {
    cur = r.level
    console.log(`\n${groupTitle[cur]}`)
  }
  console.log(`  ${icon[r.status]} ${r.id.padEnd(5)} ${r.name.padEnd(22)} ${r.detail}`)
}

const miss = rows.filter((r) => r.status === 'miss')
const warn = rows.filter((r) => r.status === 'warn')
console.log('')
if (miss.length) {
  console.log(`✗ 缺 ${miss.length} 项，必须补：${miss.map((m) => m.id + ' ' + m.name).join('、')}`)
  console.log(`  照着 setup/ENVIRONMENT.md 对应的编号装，或者直接对 AI 说「按 ENVIRONMENT.md 把这 ${miss.length} 项补齐」`)
} else {
  console.log('✓ 第一、二级都齐了，可以直接 node install.mjs 装插件')
}
if (warn.length) console.log(`! ${warn.length} 项有告警（不挡路，功能会降级）：${warn.map((w) => w.id).join('、')}`)
console.log('')
