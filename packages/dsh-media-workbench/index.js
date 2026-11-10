/**
 * dsh-media-workbench —— 宿主端
 *
 * 已注册接口：
 *   GET  /api/dsh-media/hot          读今日热点结构化数据（读不到则回退到最近一份）
 *   POST /api/dsh-media/hot/refresh  触发重新抓取（后台跑 hotdaily.py，返回是否已启动）
 *   GET  /api/dsh-media/stats        数据库统计（原子/推文数）
 */

import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { spawn } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const HOT_DIR = dataPath('hot')
const DB = dataPath('media', 'workbench.db')
const PY = (process.env.DSH_PYTHON || path.join(TOOLS_ROOT, 'asr', '.venv', 'Scripts', 'python.exe'))
const SCRIPT = pyPath('asr', 'hotdaily.py')
const I18N_SCRIPT = pyPath('asr', 'hot_i18n.py')
const IDEA_SCRIPT = pyPath('asr', 'daily_idea.py')
const WBQ = pyPath('media', 'wbquery.py')
const BOOKS_Q = pyPath('media', 'books_query.py')
const DASH_CTL = pyPath('shuku', 'split_ctl.py')
const DASH_STATS = pyPath('shuku', 'dash_stats.py')
const LINK_ROUTER = pyPath('media', 'link_router.py')
const OCR_STATUS = pyPath('shuku', 'ocr_status.py')

/* ---- 直播录制（DouyinLiveRecorder）磁盘状态，按平台分组 ---- */
const LIVE_ROOT = dataPath('live', 'rec')          // 下面按平台分目录：抖音直播 / 小红书直播 / B站直播 ...
const LIVE_TR_ROOT = dataPath('live', 'transcript')
const LIVE_PIPE_STATE = path.join(TOOLS_ROOT, 'DouyinLiveRecorder', '.pipeline_state.json')
const LIVE_PIPE_LOG = 'E:\\tools\\DouyinLiveRecorder\\logs\\pipeline.log'
const LIVE_CFG = 'E:\\tools\\DouyinLiveRecorder\\config'
const LIVE_FOLLOW = 'E:\\tools\\DouyinLiveRecorder\\.follow_status.json'
const LIVE_PAUSE = 'E:\\tools\\DouyinLiveRecorder\\.pause_record'
// 小红书关注里谁在直播：脚本要开真窗口（headless 会被风控），跑一次约 10-20 秒
const XHS_FOLLOW_SCRIPT = 'E:\\tools\\DouyinLiveRecorder\\xhs_follow_live.py'
const XHS_FOLLOW_JSON = 'E:\\tools\\DouyinLiveRecorder\\.xhs_follow_live.json'
// playwright 装在系统 python，asr 的 venv 里没有
const PY_SYS = (process.env.DSH_PYTHON || path.join(process.env.LOCALAPPDATA || '', 'Programs', 'Python', 'Python312', 'python.exe'))
// GitHub 热榜：collect.py 抓取入库，query.py 出 JSON，intro.py 写简介，judge.py 记判断
const GH_QUERY = pyPath('gh', 'query.py')
const GH_COLLECT = pyPath('gh', 'collect.py')
const GH_INTRO = pyPath('gh', 'intro.py')
const GH_JUDGE = pyPath('gh', 'judge.py')
// AI 简介走本机 OpenAI 兼容网关（硅基流动 V3.2）。换 key 用环境变量覆盖，不写死新路径。
const GH_INTRO_BASE = process.env.DSH_INTRO_BASE || 'http://127.0.0.1:8326/v1'
const GH_INTRO_KEY_FILE = process.env.DSH_INTRO_KEY_FILE || 'E:\\DSH-data\\.dsh\\openai-gateway\\api-key'
const GH_INTRO_MODEL = process.env.DSH_INTRO_MODEL || 'siliconflow/deepseek-ai/DeepSeek-V3.2'
const WORK_BOARD_FILE = path.join(process.env.DSH_HOME || path.join(os.homedir(), '.dsh'), 'work-board', 'board.json')
// 拆解条目 → 原文出处（书查 book_chunks / 稿查 posts）
const SPLIT_SOURCE = pyPath('media', 'split_source.py')

// 录制器目录名 → 界面上的平台名。没列到的就去掉结尾「直播」
const PLATFORM_LABEL = {
  '抖音直播': '抖音',
  '抖音': '抖音',
  '小红书直播': '小红书',
  'B站直播': 'B站',
  '哔哩哔哩直播': 'B站',
  '快手直播': '快手',
  '虎牙直播': '虎牙',
  '斗鱼直播': '斗鱼',
  'YY直播': 'YY',
}
// 录制器能接、但当前还没配地址的平台（界面上给个「未接入」）
const KNOWN_PLATFORMS = ['抖音', '小红书', 'B站', '快手']

function readDirAny(dir) {
  try { return fs.readdirSync(dir, { withFileTypes: true }) } catch { return [] }
}

function readTextSafe(p) {
  try { return fs.readFileSync(p, 'utf8') } catch { return '' }
}

function scanAnchorDir(dir, now) {
  let total = 0, files = 0, last = 0
  for (const f of readDirAny(dir)) {
    if (!f.isFile() || !f.name.toLowerCase().endsWith('.mp4')) continue
    try {
      const st = fs.statSync(path.join(dir, f.name))
      total += st.size
      files += 1
      if (st.mtimeMs > last) last = st.mtimeMs
    } catch { }
  }
  if (!files) return null
  return {
    files,
    mb: Math.round(total / 1048576),
    idleSec: Math.round((now - last) / 1000),
    lastAt: last,
    active: now - last < 120000,
  }
}

export function liveStatusNow() {
  const now = Date.now()
  const platforms = []      // [{ key, label, active:[], idle:[], totalMb }]
  const allAnchors = []     // 扁平列表，给排队统计用

  for (const pent of readDirAny(LIVE_ROOT)) {
    if (!pent.isDirectory()) continue
    const pdir = path.join(LIVE_ROOT, pent.name)
    const label = PLATFORM_LABEL[pent.name] || pent.name.replace(/直播$/, '')
    const active = []
    const idle = []
    for (const aent of readDirAny(pdir)) {
      if (!aent.isDirectory()) continue
      const info = scanAnchorDir(path.join(pdir, aent.name), now)
      if (!info) continue
      const item = { anchor: aent.name, platform: label, dir: path.join(pdir, aent.name), ...info }
      allAnchors.push(item)
      if (info.active) active.push(item)
      else idle.push(item)
    }
    if (!active.length && !idle.length) continue
    active.sort((a, b) => b.mb - a.mb)
    idle.sort((a, b) => b.lastAt - a.lastAt)
    platforms.push({ key: pent.name, label, active, idle: idle.slice(0, 6), totalMb: active.reduce((s, a) => s + a.mb, 0) })
  }
  platforms.sort((a, b) => (b.active.length - a.active.length) || (b.totalMb - a.totalMb))

  // 已配置（URL_config 里没被注释的）平台数，用于标「已接入/未接入」
  // 注意：判断依据是「有没有配监控地址」，不是「有没有录制目录」——
  // 配了地址还没开播时目录不存在，界面不能因此说未接入。
  const PLATFORM_OF_HOST = [
    [/(^|\.)douyin\.com$/, '抖音'],
    [/(^|\.)(xiaohongshu\.com|xhslink\.(com|cn))$/, '小红书'],
    [/(^|\.)bilibili\.com$/, 'B站'],
    [/(^|\.)kuaishou\.com$/, '快手'],
  ]
  const hostOf = (u) => { try { return new URL(u).hostname } catch { return '' } }
  const monitoredBy = { 抖音: 0, 小红书: 0, B站: 0, 快手: 0 }
  let configured = 0
  const cfgTxt = readTextSafe(path.join(LIVE_CFG, 'URL_config.ini'))
  for (const raw of cfgTxt.split('\n')) {
    const line = raw.trim()
    if (!line || line.startsWith('#')) continue
    const urlPart = line.split(',')[0].trim()
    if (!/^https?:\/\//.test(urlPart)) continue
    configured += 1
    const host = hostOf(urlPart)
    const hit = PLATFORM_OF_HOST.find(([re]) => re.test(host))
    if (hit) monitoredBy[hit[1]] = (monitoredBy[hit[1]] || 0) + 1
  }

  let state = {}
  try { state = JSON.parse(readTextSafe(LIVE_PIPE_STATE) || '{}') } catch { state = {} }
  let pipe = {}
  try { pipe = JSON.parse(readTextSafe(path.join(TOOLS_ROOT, 'DouyinLiveRecorder', '.pipeline_status.json')) || '{}') } catch { }
  // 正在转写的分段不算「待转写」，否则数字会重复
  const runningKeys = new Set((pipe.running || []).map((r) => r.anchor + '/' + r.name))
  let done = 0
  for (const v of Object.values(state)) if (v && v.status === 'done') done += 1

  let pending = 0, pendingMb = 0
  const wl = readTextSafe(path.join(LIVE_CFG, 'transcribe_whitelist.txt'))
    .split('\n').map((s) => s.trim()).filter((s) => s && !s.startsWith('#'))
  for (const a of allAnchors) {
    if (wl.length && !wl.some((w) => a.anchor.includes(w))) continue
    for (const f of readDirAny(a.dir)) {
      if (!f.isFile() || !f.name.toLowerCase().endsWith('.mp4')) continue
      const p = path.join(a.dir, f.name)
      try {
        if (runningKeys.has(a.anchor + '/' + f.name)) continue
        const st = fs.statSync(p)
        if (st.size < 10 * 1048576) continue
        if (now - st.mtimeMs < 180000) continue
        if (state[p] && state[p].status === 'done') continue
        if (state[p] && (state[p].retry || 0) >= 3) continue
        pending += 1
        pendingMb += st.size / 1048576
      } catch { }
    }
  }

  const outs = []
  for (const ent of readDirAny(LIVE_TR_ROOT)) {
    if (!ent.isDirectory()) continue
    for (const f of readDirAny(path.join(LIVE_TR_ROOT, ent.name))) {
      if (!f.isFile() || !f.name.endsWith('.txt')) continue
      const p = path.join(LIVE_TR_ROOT, ent.name, f.name)
      try {
        const st = fs.statSync(p)
        outs.push({ anchor: ent.name, name: f.name, chars: Math.round(st.size / 3), at: st.mtimeMs })
      } catch { }
    }
  }
  outs.sort((a, b) => b.at - a.at)

  const whitelist = readTextSafe(path.join(LIVE_CFG, 'transcribe_whitelist.txt'))
    .split('\n').map((s) => s.trim()).filter((s) => s && !s.startsWith('#'))

  let pipelineAlive = false
  try {
    const lg = fs.statSync(LIVE_PIPE_LOG)
    pipelineAlive = now - lg.mtimeMs < 180000
  } catch { }

  let disk = null
  try {
    const s = fs.statfsSync('D:')
    disk = { freeGb: Math.round((s.bfree * s.bsize) / 1073741824), totalGb: Math.round((s.blocks * s.bsize) / 1073741824) }
  } catch { }

  const activeAll = allAnchors.filter((a) => a.active)

  let follow = {}
  try { follow = JSON.parse(readTextSafe(LIVE_FOLLOW) || '{}') } catch { follow = {} }
  let paused = false
  try { paused = fs.existsSync(LIVE_PAUSE) } catch { }

  const cap = {
    pending: capQueue.filter((x) => x.status === 'pending').length,
    running: capQueue.filter((x) => x.status === 'running').length,
    done: capQueue.filter((x) => x.status === 'done' || x.status === 'duplicate').length,
    failed: capQueue.filter((x) => x.status === 'failed').length,
    recent: capQueue.slice(-12).reverse().map((x) => ({
      url: x.url, key: x.key, status: x.status, at: x.at, error: x.error || '',
      result: x.result || null,
    })),
  }

  return {
    ok: true,
    ts: now,
    platforms,
    known: KNOWN_PLATFORMS,
    monitored: configured,
    monitoredBy,
    paths: { rec: LIVE_ROOT, transcript: LIVE_TR_ROOT, book: dataPath('wengao') },
    paused,
    follow: {
      live: follow.followedLive || 0,
      anchors: (follow.anchors || []).slice(0, 40),
      updated: follow.updated || 0,
    },
    rec: {
      active: activeAll,
      idle: allAnchors.filter((a) => !a.active).sort((a, b) => b.lastAt - a.lastAt).slice(0, 10),
      totalMb: allAnchors.reduce((s, a) => s + a.mb, 0),
      configuredUrls: configured,
    },
    queue: { pending, pendingMb: Math.round(pendingMb), done, pipelineAlive, whitelist: wl },
    capture: cap,
    transcribe: {
      running: (pipe.running || []).length,
      doneToday: pipe.doneToday || 0,
      parallel: pipe.parallel || 1,
    },
    out: outs.slice(0, 6),
    disk,
  }
}

function runPyJson(script, args = []) {
  return new Promise((resolve) => {
    const child = spawn(PY, [script, ...args], {
      windowsHide: true,
      env: { ...process.env, PYTHONIOENCODING: 'utf-8' },
    })
    let out = ''
    let err = ''
    // 不设编码的话多字节中文会被分块截断成乱码（书名的 ◆◆◆ 就是这么来的）
    child.stdout.setEncoding('utf8')
    child.stderr.setEncoding('utf8')
    child.stdout.on('data', (d) => { out += d })
    child.stderr.on('data', (d) => { err += d })
    child.on('close', () => {
      const line = (out || '').trim().split('\n').pop() || '{}'
      try {
        resolve(JSON.parse(line))
      } catch (e) {
        resolve({ ok: false, error: (err || out || 'parse fail').slice(-300) })
      }
    })
    child.on('error', (e) => resolve({ ok: false, error: String(e).slice(-200) }))
  })
}

/* 跑 python，带超时和额外环境变量（AI 简介这种慢接口用） */
function runPyJsonEx(script, args = [], opts = {}) {
  return new Promise((resolve) => {
    let child
    try {
      child = spawn(PY, [script, ...args], {
        windowsHide: true,
        env: { ...process.env, PYTHONIOENCODING: 'utf-8', ...(opts.env || {}) },
      })
    } catch (e) {
      return resolve({ ok: false, error: String(e?.message ?? e).slice(-200) })
    }
    let out = ''
    let err = ''
    let done = false
    const finish = (v) => {
      if (done) return
      done = true
      clearTimeout(timer)
      resolve(v)
    }
    const timer = setTimeout(() => {
      try { child.kill() } catch { }
      finish({ ok: false, error: '超时：' + Math.round((opts.timeoutMs || 120000) / 1000) + ' 秒没跑完' })
    }, opts.timeoutMs || 120000)
    child.stdout.setEncoding('utf8')
    child.stderr.setEncoding('utf8')
    child.stdout.on('data', (d) => { out += d })
    child.stderr.on('data', (d) => { err += d })
    child.on('close', () => {
      const line = (out || '').trim().split('\n').pop() || '{}'
      try { finish(JSON.parse(line)) } catch { finish({ ok: false, error: (err || out || 'parse fail').slice(-300) }) }
    })
    child.on('error', (e) => finish({ ok: false, error: String(e).slice(-200) }))
  })
}

function ghIntroEnv() {
  return {
    DSH_INTRO_BASE: GH_INTRO_BASE,
    DSH_INTRO_KEY_FILE: GH_INTRO_KEY_FILE,
    DSH_INTRO_MODEL: GH_INTRO_MODEL,
  }
}

/* 往工作看板（dsh-work-board）建一张卡：同一份 board.json、同一套字段和原子写 */
function addBoardCard({ title, note, nextStep, workspace }) {
  let board = { version: 1, cards: [] }
  try {
    if (fs.existsSync(WORK_BOARD_FILE)) {
      const raw = JSON.parse(fs.readFileSync(WORK_BOARD_FILE, 'utf8'))
      if (raw && Array.isArray(raw.cards)) board = { version: 1, cards: raw.cards }
    }
  } catch { board = { version: 1, cards: [] } }
  const p = (n) => String(n).padStart(2, '0')
  const d = new Date()
  const at = `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
  const card = {
    id: 'c' + Date.now().toString(36) + Math.random().toString(36).slice(2, 6),
    title: String(title || '').trim() || '未命名项目',
    note: String(note || ''),
    nextStep: String(nextStep || ''),
    status: 'todo',
    workspace: workspace || '',
    sessions: [],
    lastSessionId: null,
    createdAt: at,
    updatedAt: at,
    lastStepAt: null,
  }
  board.cards.unshift(card)
  fs.mkdirSync(path.dirname(WORK_BOARD_FILE), { recursive: true })
  const tmp = WORK_BOARD_FILE + '.tmp'
  fs.writeFileSync(tmp, JSON.stringify(board, null, 2), 'utf8')
  fs.renameSync(tmp, WORK_BOARD_FILE)
  return card
}

/* 建卡：优先走看板插件提供的 workBoard 服务（内存同步，界面 4 秒内就能看到）；
   没装看板插件时才退回直接写 board.json。 */
function createBoardCard(ctx, fields) {
  try {
    const wb = ctx?.get?.('workBoard')
    if (wb && typeof wb.createCard === 'function') return wb.createCard(fields)
  } catch { /* 服务不可用就退回文件 */ }
  return addBoardCard(fields)
}

async function dashStats() {
  return runPyJson(DASH_STATS)
}async function dashCtl(cmd) {
  const r = await runPyJson(DASH_CTL, [cmd])
  const s = await dashStats()
  return { ...r, stats: s }
}

let refreshing = false

/* ---------------- 每日自动任务：热点 + 灵感 ---------------- */
/* 打开就绪后补跑当天数据，之后每 20 分钟看一眼跨没跨天。
   失败不硬闯：间隔翻倍，连续 3 次后压到 4 小时。 */
const AUTO_MIN_HOUR = 5            // 5 点前不生成：凌晨抓出来的「今日热点」其实是昨天的
const AUTO_TICK_MS = 20 * 60 * 1000
const AUTO_RETRY_MS = 30 * 60 * 1000

const auto = {
  startedAt: 0,
  timer: null,
  hot: { running: false, at: 0, ok: null, error: '', tries: 0, nextAt: 0 },
  idea: { running: false, at: 0, ok: null, error: '', tries: 0, nextAt: 0 },
}

/* 本地日期。原先用 toISOString() 是 UTC，早上 8 点前会把「今天」算成昨天 */
function localDate(d) {
  const t = d || new Date()
  const p = (n) => String(n).padStart(2, '0')
  return `${t.getFullYear()}-${p(t.getMonth() + 1)}-${p(t.getDate())}`
}

function todayFile(prefix) {
  return path.join(HOT_DIR, `${prefix}-${localDate()}.json`)
}

function hasTodayHot() {
  try { return fs.existsSync(todayFile('hot')) } catch { return false }
}

function hasTodayIdea() {
  try { return fs.existsSync(todayFile('idea')) } catch { return false }
}

/* ---------------- 采集队列：收下的链接自动转写入库 ---------------- */
const CAPTURE = pyPath('asr', 'capture_one.py')
let capQueue = []          // [{url, status:'pending'|'running'|'done'|'failed', at, result, error}]
let capRunning = false

let capChild = null

function runCapture(url) {
  return new Promise((resolve) => {
    let child
    try {
      child = spawn(PY, [CAPTURE, url], {
        windowsHide: true,
        env: { ...process.env, PYTHONIOENCODING: 'utf-8' },
      })
      capChild = child
    } catch (e) {
      return resolve({ ok: false, error: String(e?.message ?? e) })
    }
    let out = ''
    let err = ''
    child.stdout.setEncoding('utf8')
    child.stderr.setEncoding('utf8')
    child.stdout.on('data', (d) => { out += d })
    child.stderr.on('data', (d) => { err += d })
    child.on('error', (e) => resolve({ ok: false, error: String(e?.message ?? e) }))
    child.on('exit', (code) => {
      if (capChild === child) capChild = null
      const lines = out.trim().split('\n').filter(Boolean)
      const last = lines[lines.length - 1] || ''
      try {
        const j = JSON.parse(last)
        if (j && j.ok) return resolve(j)
        return resolve({ ok: false, step: (j && j.step) || 'unknown', error: (j && j.error) || err.slice(0, 400) })
      } catch {
        resolve({ ok: false, step: 'unknown', error: (err || out || ('exit ' + code)).slice(0, 400) })
      }
    })
  })
}

function capPump() {
  if (capRunning) return
  const job = capQueue.find((x) => x.status === 'pending')
  if (!job) return
  capRunning = true
  job.status = 'running'
  job.startedAt = Date.now()
  runCapture(job.url).then((res) => {
    if (job.status === 'cancelled') {
      capRunning = false
      capPump()
      return
    }
    if (res && res.ok) {
      job.status = res.duplicate ? 'duplicate' : 'done'
      job.result = { post_id: res.post_id, title: res.title, chars: res.chars, duration: res.duration, duplicate: !!res.duplicate }
    } else {
      job.status = 'failed'
      job.step = (res && res.step) || 'unknown'
      job.error = (res && res.error) || 'unknown'
    }
    capRunning = false
    capPump()
  }).catch((e) => {
    // 没有这个 catch 的话，pump 里任何一处抛错都会变成 UnhandledPromiseRejection，
    // 宿主把整个采集链路停住，界面上只看到一个红色报错。
    try {
      job.status = 'failed'
      job.error = 'pump 异常：' + String(e && e.message ? e.message : e).slice(0, 300)
    } catch { }
    capRunning = false
    try { capPump() } catch { }
  })
}

function normUrl(u) {
  try {
    const x = new URL(String(u).trim())
    x.hash = ''
    // 抖音分享链接的追踪参数都去掉，只留路径
    x.search = ''
    let p = x.pathname.replace(/\/+$/, '')
    return (x.host + p).toLowerCase()
  } catch { return String(u || '').trim().toLowerCase() }
}

function capEnqueue(url) {
  if (!url) return { ok: false, error: 'empty url' }
  const key = normUrl(url)
  // 1) 队列里已有的同一条（失败/取消的不算）直接忽略
  if (capQueue.some((x) => x.key === key && x.status !== 'failed' && x.status !== 'cancelled')) {
    return { ok: true, duplicate: true }
  }
  capQueue.push({ url, key, status: 'pending', at: Date.now() })
  if (capQueue.length > 100) capQueue = capQueue.slice(-100)
  capPump()
  return { ok: true, queued: true, total: capQueue.length }
}

// 失败的链接：一键重拍（不改 url，只把状态打回 pending 再进泵）
function capRetry(sel) {
  let job = null
  if (sel && (sel.at || sel.url)) {
    const k = sel.url ? normUrl(sel.url) : ''
    job = capQueue.find((x) => x.status === 'failed' && ((sel.at && x.at === sel.at) || (k && x.key === k))) || null
  }
  if (!job) job = capQueue.filter((x) => x.status === 'failed').sort((a, b) => b.at - a.at)[0] || null
  if (!job) return { ok: false, error: '没有失败的条目' }
  job.status = 'pending'
  job.error = ''
  job.at = Date.now()
  job.retriedAt = Date.now()
  capPump()
  return { ok: true, url: job.url }
}


// 调 python 查库，返回 JSON
function queryWb(args) {
  return new Promise((resolve) => {
    let child
    try {
      child = spawn(PY, [WBQ, ...args], { windowsHide: true })
    } catch (e) {
      return resolve({ ok: false, error: String(e?.message ?? e) })
    }
    let out = ''
    let err = ''
    child.stdout.setEncoding('utf8')
    child.stderr.setEncoding('utf8')
    child.stdout.on('data', (d) => { out += d })
    child.stderr.on('data', (d) => { err += d })
    child.on('error', (e) => resolve({ ok: false, error: String(e?.message ?? e) }))
    child.on('exit', (code) => {
      if (code !== 0) {
        return resolve({ ok: false, error: (err || ('exit ' + code)).slice(0, 500) })
      }
      try {
        resolve(JSON.parse(out))
      } catch (e) {
        resolve({ ok: false, error: 'JSON 解析失败：' + out.slice(0, 200) })
      }
    })
  })
}

function readJson(p) {
  try {
    return JSON.parse(fs.readFileSync(p, 'utf8'))
  } catch {
    return null
  }
}

function listHot() {
  try {
    return fs.readdirSync(HOT_DIR)
      .filter((f) => /^hot-\d{4}-\d{2}-\d{2}\.json$/.test(f))
      .sort()
      .reverse()
  } catch {
    return []
  }
}

function loadHot() {
  const files = listHot()
  if (!files.length) return { ok: false, reason: 'no-data' }
  const today = `hot-${localDate()}.json`
  const pick = files.includes(today) ? today : files[0]
  const data = readJson(path.join(HOT_DIR, pick))
  if (!data) return { ok: false, reason: 'unreadable' }
  return { ok: true, file: pick, isToday: pick === today, data }
}

function listIdea() {
  try {
    return fs.readdirSync(HOT_DIR)
      .filter((f) => /^idea-\d{4}-\d{2}-\d{2}\.json$/.test(f))
      .sort()
      .reverse()
  } catch {
    return []
  }
}

function loadIdea() {
  const files = listIdea()
  if (!files.length) return { ok: false, reason: 'no-data' }
  const today = `idea-${localDate()}.json`
  const pick = files.includes(today) ? today : files[0]
  const data = readJson(path.join(HOT_DIR, pick))
  if (!data) return { ok: false, reason: 'unreadable' }
  return { ok: true, file: pick, isToday: pick === today, data }
}

function dbStats() {
  try {
    const st = fs.statSync(DB)
    return { ok: true, sizeMB: +(st.size / 1024 / 1024).toFixed(1), mtime: st.mtime.toISOString() }
  } catch {
    return { ok: false }
  }
}

/* ---------------- AI 讲透：流式调用默认模型 ---------------- */

const SETTINGS_FILE = dataPath('media', 'settings.json')

function readSettings() {
  try { return readJson(SETTINGS_FILE) || {} } catch { return {} }
}
function writeSettings(obj) {
  try { fs.writeFileSync(SETTINGS_FILE, JSON.stringify(obj, null, 2), 'utf8') } catch { }
}

function currentRoute(ctx) {
  // 用户在面板里选过模型就优先用它，否则跟随 DSH 当前模型
  try {
    const saved = readSettings().model
    if (saved && saved.provider && saved.model) return { provider: saved.provider, model: saved.model }
  } catch { }
  const sel = ctx.get?.('agentDefaultModel')?.currentSelection?.()
  if (!sel || !sel.provider || !sel.model) throw new Error('读不到默认模型（agentDefaultModel 不可用）')
  return { provider: sel.provider, model: sel.model }
}

/* 从 profile 的 cordis.patch.yml 与免费模型目录里收集可选模型 */
function listModels(ctx) {
  const out = []
  try {
    const sel = ctx.get?.('agentDefaultModel')?.currentSelection?.()
    if (sel && sel.provider && sel.model) out.push({ provider: sel.provider, model: sel.model, label: sel.model + '（当前默认）', group: '默认' })
  } catch { }
  try {
    const yml = fs.readFileSync('E:\\DSH-data\\.dsh\\profiles\\desktop\\cordis.patch.yml', 'utf8')
    let provider = ''
    for (const line of yml.split('\n')) {
      const pv = line.match(/^ {6}([A-Za-z0-9_-]+):\s*$/)
      if (pv && !/^(models|config|providers)$/.test(pv[1])) { provider = pv[1]; continue }
      const mv = line.match(/^ {10}- id:\s*(.+?)\s*$/)
      if (mv && provider && !/provider:/.test(line)) {
        out.push({ provider, model: mv[1], label: mv[1], group: provider })
      }
    }
  } catch { }
  // 免费通道（our-free-model 插件提供的模型）
  try {
    const cat = readJson('E:\\Users\\Administrator\\.dsh\\our-free-model\\catalog.json')
    if (cat && Array.isArray(cat.entries)) {
      for (const id of cat.entries) {
        if (!out.some((x) => x.model === id)) out.push({ provider: 'deepseek-account', model: id, label: id, group: 'deepseek-account' })
      }
    }
  } catch { }
  return out
}

const EXPLAIN_SYSTEM = `你是一个内容和商业方向的思考搭档，服务对象是一个准备做知识类自媒体的博主。

对方会给你一段素材（别人的推文），或者素材里的某个片段，要求你讲透。

写作要求：
- 用大白话，不用"值得注意的是""意义重大"这类空话
- 先给结论，再给理由
- 必要时举一个具体例子（最好是对方能对号入座的场景）
- 讲清楚：这条跟"做内容"有什么关系，能怎么用
- 如果这条素材本身价值不高，直接说"这条没什么用，原因是……"，不要硬夸
- 不要复述原文，直接讲你的理解
- 控制长度，300 字以内，除非对方要求展开`

async function* streamText(ctx, { prompt, maxTokens = 1200 }, signal) {
  const route = currentRoute(ctx)
  const llm = ctx.get?.('llm')
  if (!llm?.prepareCall) throw new Error('llm 服务不可用')
  const call = await llm.prepareCall({ ...route, maxTokens }, signal)
  const messages = [{ role: 'user', content: [{ type: 'text', text: prompt }] }]
  for await (const chunk of call.stream({ ...call.config, messages, system: EXPLAIN_SYSTEM, signal })) {
    if (chunk.type === 'text-delta') {
      if (chunk.text) yield chunk.text
    } else if (chunk.type === 'finish') {
      if (chunk.reason.kind !== 'stop' && chunk.reason.kind !== 'max-tokens') {
        const f = chunk.reason.failure
        throw new Error(`模型调用结束：${chunk.reason.kind}${f?.message ? ' - ' + f.message : ''}`)
      }
    }
  }
}

function streamResponse(iteratorFactory) {
  const encoder = new TextEncoder()
  const aborter = new AbortController()
  const stream = new ReadableStream({
    start(controller) {
      ;(async () => {
        try {
          const iterable = await iteratorFactory(aborter.signal)
          for await (const text of iterable) {
            controller.enqueue(encoder.encode(text))
          }
        } catch (e) {
          controller.enqueue(encoder.encode(`\n\n[失败] ${String(e?.message ?? e)}`))
        } finally {
          try { controller.close() } catch { }
        }
      })()
    },
    cancel() { try { aborter.abort() } catch { } },
  })
  return new Response(stream, {
    headers: { 'Content-Type': 'text/plain; charset=utf-8', 'Cache-Control': 'no-store' },
  })
}

function buildExplainPrompt({ text, kind, context }) {
  const k = kind === 'expand' ? 'expand' : 'explain'
  const head = k === 'expand'
    ? '下面这段是某条素材里的一部分，我没看懂，请你把它讲透、举例子、说明它到底指什么。'
    : '下面是一条素材，请你把它讲透。'
  let p = head
  if (context) p += `\n\n【这条素材的完整内容】\n${context}`
  p += `\n\n【要讲清的部分】\n${text}`
  p += '\n\n请按这个顺序讲：1) 它在说什么（一句话）2) 为什么是这样（理由）3) 举一个具体例子 4) 对做内容的人意味着什么'
  return p
}

/* ---------------- 自动为灵感素材写「角度 + 问题」 ---------------- */

const IDEA_SYSTEM = `你是内容策划。给你几条素材（别人的推文原话），你要为每条写两样东西：

1. angle（角度）：这条能怎么变成内容。写判断，不要复述原文。要具体、可执行。
   - 禁止："值得思考""很有启发""值得关注"这类空话
   - 好例子："关键在机制层面——不是模仿他的风格，是他按了观众哪个按钮"
   
2. question（问题）：拿这条能问出什么。必须是一个能直接说出口的问句，让人一愣。

要求：
- 每条 angle 30-60 字，question 15-30 字
- 如果某条素材本身没什么可用价值，angle 直接写"这条价值不高：原因……"
- 严格只输出 JSON，不要任何解释文字、不要 markdown 代码块

输出格式：
[{"id":"素材id","angle":"...","question":"..."}]`

async function completeText(ctx, { prompt, maxTokens = 4000 }, signal) {
  let acc = ''
  for await (const t of streamTextWith(ctx, { prompt, maxTokens, system: IDEA_SYSTEM }, signal)) {
    acc += t
  }
  return acc
}

async function* streamTextWith(ctx, { prompt, maxTokens = 1200, system }, signal) {
  const route = currentRoute(ctx)
  const llm = ctx.get?.('llm')
  if (!llm?.prepareCall) throw new Error('llm 服务不可用')
  const call = await llm.prepareCall({ ...route, maxTokens }, signal)
  const messages = [{ role: 'user', content: [{ type: 'text', text: prompt }] }]
  for await (const chunk of call.stream({ ...call.config, messages, system, signal })) {
    if (chunk.type === 'text-delta') {
      if (chunk.text) yield chunk.text
    } else if (chunk.type === 'finish') {
      if (chunk.reason.kind !== 'stop' && chunk.reason.kind !== 'max-tokens') {
        const f = chunk.reason.failure
        throw new Error(`模型调用结束：${chunk.reason.kind}${f?.message ? ' - ' + f.message : ''}`)
      }
    }
  }
}

function parseLooseJson(s) {
  let t = String(s || '').trim()
  // 去掉可能的 markdown 围栏
  t = t.replace(/^```[a-zA-Z]*\s*/, '').replace(/```\s*$/, '').trim()
  const a = t.indexOf('[')
  const b = t.lastIndexOf(']')
  if (a >= 0 && b > a) t = t.slice(a, b + 1)
  try { return JSON.parse(t) } catch { return null }
}

/* 解析一个对象（模型偶尔会包一层说明文字或 markdown 围栏） */
function parseLooseJsonObj(s) {
  let t = String(s || '').trim()
  t = t.replace(/^```[a-zA-Z]*\s*/, '').replace(/```\s*$/, '').trim()
  const a = t.indexOf('{')
  const b = t.lastIndexOf('}')
  if (a >= 0 && b > a) t = t.slice(a, b + 1)
  try {
    const v = JSON.parse(t)
    return v && typeof v === 'object' && !Array.isArray(v) ? v : null
  } catch { return null }
}

/** 为缺 angle 的条目补写，直接落盘 */
async function refineIdea(ctx) {
  const hit = loadIdea()
  if (!hit.ok) return { ok: false, reason: hit.reason }
  const file = hit.file
  const abs = path.join(HOT_DIR, file)
  const data = hit.data || {}
  const items = data.items || []
  const todo = items.filter((x) => !x.angle || !x.question)
  if (!todo.length) return { ok: true, updated: 0, skipped: items.length }

  const payload = todo.map((x) => ({ id: x.id, 素材: x.knowledge }))
  const prompt = '请为下面每条素材写 angle 和 question，严格按 JSON 数组输出：\n' + JSON.stringify(payload, null, 2)
  const raw = await completeText(ctx, { prompt })
  const arr = parseLooseJson(raw)
  if (!Array.isArray(arr)) return { ok: false, reason: 'model-output-unparsable', raw: String(raw).slice(0, 300) }

  let updated = 0
  for (const r of arr) {
    const it = items.find((x) => x.id === r.id)
    if (!it) continue
    if (r.angle) { it.angle = String(r.angle).trim(); updated++ }
    if (r.question) it.question = String(r.question).trim()
  }
  if (updated) {
    data.items = items
    data.refined_at = new Date().toISOString().slice(0, 19)
    fs.writeFileSync(abs, JSON.stringify(data, null, 2), 'utf8')
  }
  return { ok: true, updated, total: items.length }
}

/* ---------------- 每日自动任务：跑脚本 + 补翻译 + 补角度 ---------------- */

/* 跑一个 python 脚本，收 stdout/stderr。超时直接杀，避免挂住调度器 */
function runPy(script, args, timeoutMs) {
  return new Promise((resolve) => {
    if (!fs.existsSync(script)) return resolve({ ok: false, error: '脚本不存在：' + script })
    let child
    try {
      child = spawn(PY, [script, ...(args || [])], { windowsHide: true })
    } catch (e) {
      return resolve({ ok: false, error: String(e?.message ?? e) })
    }
    let out = ''
    let err = ''
    let done = false
    const finish = (res) => {
      if (done) return
      done = true
      clearTimeout(timer)
      resolve(res)
    }
    const timer = setTimeout(() => {
      try { child.kill() } catch { }
      finish({ ok: false, error: '超时（' + Math.round(timeoutMs / 1000) + ' 秒没跑完）' })
    }, timeoutMs || 600000)
    child.stdout.setEncoding('utf8')
    child.stderr.setEncoding('utf8')
    child.stdout.on('data', (d) => { out += d })
    child.stderr.on('data', (d) => { err += d })
    child.on('error', (e) => finish({ ok: false, error: String(e?.message ?? e) }))
    child.on('exit', (code) => {
      if (code === 0) return finish({ ok: true, out, err, code })
      finish({ ok: false, error: (err || out || ('exit ' + code)).slice(-600), code })
    })
  })
}

async function completeTextWith(ctx, { system, prompt, maxTokens = 4000 }, signal) {
  let acc = ''
  for await (const t of streamTextWith(ctx, { prompt, maxTokens, system }, signal)) acc += t
  return acc
}

const TRANSLATE_SYSTEM = `你是翻译。用户会给你一批英文的科技新闻标题和推文，你把它们翻成中文。

规则：
- 人名、公司名、产品名保留原文（如 Anthropic、Hacker News、Gemini）
- 标题风格紧凑，像科技媒体标题，不要加「一文读懂」这类装饰
- 推文口语化，保持原话的语气，不要美化
- 专有名词不确定就保留英文
- 严格只输出 JSON 数组，不要解释、不要 markdown 代码块`

/* 给当天热点补中文：先跑 hot_i18n.py 的固定词表（命中快），剩下的交给模型 */
async function translateMissing(ctx) {
  const hit = loadHot()
  if (!hit.ok) return { ok: false, reason: hit.reason }
  const abs = path.join(HOT_DIR, hit.file)
  const data = hit.data || {}

  const jobs = []
  ;(data.hn || []).forEach((x, i) => {
    if (x.title && !x.title_zh) jobs.push({ key: 'hn:' + i, en: x.title, kind: 'hn' })
  })
  Object.keys(data.groups || {}).forEach((g) => {
    ;(data.groups[g] || []).forEach((x, i) => {
      if (x.text && !x.text_zh) jobs.push({ key: 'x:' + g + ':' + i, en: x.text, kind: 'x' })
    })
  })
  if (!jobs.length) return { ok: true, translated: 0, total: 0 }

  const payload = jobs.map((j) => ({ k: j.key, t: String(j.en).slice(0, 700) }))
  const prompt = '把下面这批内容翻成中文，按 {"k":"同上","zh":"译文"} 的数组输出：\n' + JSON.stringify(payload)
  let raw
  try {
    raw = await completeTextWith(ctx, { system: TRANSLATE_SYSTEM, prompt, maxTokens: 6000 })
  } catch (e) {
    return { ok: false, reason: 'model-failed', error: String(e?.message ?? e) }
  }
  const arr = parseLooseJson(raw)
  if (!Array.isArray(arr)) return { ok: false, reason: 'unparsable', raw: String(raw).slice(0, 200) }

  const map = new Map()
  for (const r of arr) {
    if (!r || !r.k) continue
    const zh = String(r.zh || '').trim()
    if (zh) map.set(String(r.k), zh)
  }

  let n = 0
  ;(data.hn || []).forEach((x, i) => {
    const zh = map.get('hn:' + i)
    if (zh) { x.title_zh = zh; n++ }
  })
  Object.keys(data.groups || {}).forEach((g) => {
    ;(data.groups[g] || []).forEach((x, i) => {
      const zh = map.get('x:' + g + ':' + i)
      if (zh) { x.text_zh = zh; n++ }
    })
  })

  if (n) {
    data.i18n_at = new Date().toISOString().slice(0, 19)
    try { fs.writeFileSync(abs, JSON.stringify(data, null, 2), 'utf8') } catch (e) {
      return { ok: false, reason: 'write-failed', error: String(e?.message ?? e) }
    }
  }
  return { ok: true, translated: n, total: jobs.length, missed: jobs.length - n }
}

/* 只补角度（素材已经在，不重新挑） */
async function autoRefine(ctx) {
  const job = auto.idea
  if (job.running) return
  job.running = true
  try {
    const r = await refineIdea(ctx)
    if (r && r.ok === false) throw new Error(r.error || r.reason || '未知')
    job.ok = true
    job.error = ''
    job.tries = 0
    job.nextAt = 0
    job.refined = r && r.updated ? r.updated : 0
    ctx.logger?.info?.('dsh-media-workbench: 灵感补角度完成 ' + job.refined + ' 条')
  } catch (e) {
    autoFail(job, e)
    ctx.logger?.warn?.('dsh-media-workbench: 灵感补角度失败 ' + job.error)
  } finally {
    job.running = false
    job.at = Date.now()
  }
}

function autoFail(job, e) {
  job.ok = false
  job.error = String(e?.message ?? e).slice(0, 300)
  job.tries += 1
  // 30 分钟 → 1 小时 → 之后 4 小时
  const wait = job.tries >= 3 ? 4 * 3600 * 1000 : AUTO_RETRY_MS * Math.pow(2, job.tries - 1)
  job.nextAt = Date.now() + wait
}

/* 当天热点：抓取 → 固定词表翻译 → 模型补译 */
async function autoHot(ctx) {
  const job = auto.hot
  if (job.running) return
  job.running = true
  ctx.logger?.info?.('dsh-media-workbench: 自动抓热点开始')
  try {
    const r = await runPy(SCRIPT, [], 10 * 60 * 1000)
    if (!r.ok) throw new Error('抓取失败：' + r.error)
    const f = todayFile('hot')
    if (!fs.existsSync(f)) throw new Error('抓取跑完了但没生成 ' + path.basename(f))
    try { await runPy(I18N_SCRIPT, [f], 2 * 60 * 1000) } catch { }
    let tr = null
    try { tr = await translateMissing(ctx) } catch (e) { tr = { ok: false, error: String(e?.message ?? e) } }
    job.ok = true
    job.error = ''
    job.tries = 0
    job.nextAt = 0
    job.translated = tr && tr.translated ? tr.translated : 0
    ctx.logger?.info?.('dsh-media-workbench: 自动抓热点完成，补译 ' + job.translated + ' 条')
  } catch (e) {
    autoFail(job, e)
    ctx.logger?.warn?.('dsh-media-workbench: 自动抓热点失败 ' + job.error)
  } finally {
    job.running = false
    job.at = Date.now()
  }
}

/* 只补翻译（文件已经在，不重新抓） */
async function autoI18n(ctx) {
  const job = auto.hot
  if (job.running) return
  job.running = true
  try {
    const f = todayFile('hot')
    try { await runPy(I18N_SCRIPT, [f], 2 * 60 * 1000) } catch { }
    const tr = await translateMissing(ctx)
    if (!tr.ok) throw new Error('补中文失败：' + (tr.error || tr.reason || '未知'))
    job.ok = true
    job.error = ''
    job.tries = 0
    job.nextAt = 0
    job.translated = tr.translated || 0
    ctx.logger?.info?.('dsh-media-workbench: 热点补中文完成 ' + job.translated + ' 条')
  } catch (e) {
    autoFail(job, e)
    ctx.logger?.warn?.('dsh-media-workbench: 热点补中文失败 ' + job.error)
  } finally {
    job.running = false
    job.at = Date.now()
  }
}

/* 当天灵感：脚本挑素材 → 模型补角度和问题 */
async function autoIdea(ctx) {
  const job = auto.idea
  if (job.running) return
  job.running = true
  ctx.logger?.info?.('dsh-media-workbench: 自动生成灵感开始')
  try {
    const r = await runPy(IDEA_SCRIPT, [], 3 * 60 * 1000)
    if (!r.ok) throw new Error('挑素材失败：' + r.error)
    const f = todayFile('idea')
    if (!fs.existsSync(f)) throw new Error('脚本跑完了但没生成 ' + path.basename(f))
    let ref = null
    try { ref = await refineIdea(ctx) } catch (e) { ref = { ok: false, error: String(e?.message ?? e) } }
    job.ok = true
    job.error = ref && ref.ok === false ? '素材已生成，但补角度失败：' + (ref.error || ref.reason || '未知') : ''
    job.tries = job.error ? 1 : 0
    job.nextAt = job.error ? Date.now() + AUTO_RETRY_MS : 0
    job.refined = ref && ref.updated ? ref.updated : 0
    ctx.logger?.info?.('dsh-media-workbench: 自动生成灵感完成，补角度 ' + job.refined + ' 条')
  } catch (e) {
    autoFail(job, e)
    ctx.logger?.warn?.('dsh-media-workbench: 自动生成灵感失败 ' + job.error)
  } finally {
    job.running = false
    job.at = Date.now()
  }
}

/* 今天的文件在，但中文还没补过（模型那次没跑成或没跑），只补翻译不重抓 */
function hotNeedsI18n() {
  try {
    const hit = loadHot()
    if (!hit.ok || !hit.isToday) return false
    const d = hit.data || {}
    if (d.i18n_at) return false
    const missHn = (d.hn || []).some((x) => x.title && !x.title_zh)
    const missX = Object.keys(d.groups || {}).some((g) => (d.groups[g] || []).some((x) => x.text && !x.text_zh))
    return missHn || missX
  } catch {
    return false
  }
}

/* 今天的灵感在，但角度/问题还没写完，只补角度不重挑素材 */
function ideaNeedsRefine() {
  try {
    const hit = loadIdea()
    if (!hit.ok || !hit.isToday) return false
    const items = (hit.data && hit.data.items) || []
    return items.some((x) => !x.angle || !x.question)
  } catch {
    return false
  }
}

/* 每 20 分钟看一眼：跨天 / 还没生成，就补跑 */
function autoTick(ctx) {
  try {
    const hour = new Date().getHours()
    if (hour < AUTO_MIN_HOUR) return
    if (!auto.hot.running && !hasTodayHot() && Date.now() >= auto.hot.nextAt) autoHot(ctx)
    else if (!auto.hot.running && hotNeedsI18n() && Date.now() >= auto.hot.nextAt) autoI18n(ctx)
    if (!auto.idea.running && !hasTodayIdea() && Date.now() >= auto.idea.nextAt) autoIdea(ctx)
    else if (!auto.idea.running && ideaNeedsRefine() && Date.now() >= auto.idea.nextAt) autoRefine(ctx)
  } catch (e) {
    ctx.logger?.warn?.('dsh-media-workbench: 自动任务 tick 出错 ' + String(e?.message ?? e))
  }
}

function startAuto(ctx) {
  if (auto.timer) return
  auto.startedAt = Date.now()
  // 宿主刚起来别抢资源，等 15 秒再补跑
  const first = setTimeout(() => autoTick(ctx), 15 * 1000)
  if (first.unref) first.unref()
  auto.timer = setInterval(() => autoTick(ctx), AUTO_TICK_MS)
  if (auto.timer.unref) auto.timer.unref()
  ctx.logger?.info?.('dsh-media-workbench: 每日自动任务已启动（热点 + 灵感，每 20 分钟检查一次）')
}

function stopAuto() {
  if (auto.timer) { clearInterval(auto.timer); auto.timer = null }
}

function autoStatus() {
  return {
    ok: true,
    now: Date.now(),
    minHour: AUTO_MIN_HOUR,
    hot: { today: hasTodayHot(), ...auto.hot },
    idea: { today: hasTodayIdea(), ...auto.idea },
  }
}

/* ---------------- 剪贴板哨兵 ---------------- */

const CLIP_PS1 = pyPath('asr', 'clipwatch.ps1')
const DOUYIN_RE = /https?:\/\/v\.douyin\.com\/[A-Za-z0-9_\-]+\/?/i
const DOUYIN_RE2 = /https?:\/\/(?:www\.)?douyin\.com\/video\/\d+/i

let clipChild = null
let clipLines = []      // 待取的原始剪贴板行
let clipSeen = new Set()
let clipGateOpen = false  // 用户点过"是"之后为 true

function extractDouyin(text) {
  const out = []
  const m1 = String(text || '').match(new RegExp(DOUYIN_RE, 'gi')) || []
  const m2 = String(text || '').match(new RegExp(DOUYIN_RE2, 'gi')) || []
  for (const u of m1.concat(m2)) {
    const clean = u.replace(/[，。、\s]+$/, '')
    if (!out.includes(clean)) out.push(clean)
  }
  return out
}

function startClipWatch() {
  if (clipChild) return { ok: true, running: true }
  // 插件每次重载都会起一个新哨兵，旧的不清理就会叠着跑，同一段剪贴板被重复采集
  killStaleClipWatchers(0)
  try {
    const child = spawn('powershell', ['-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', CLIP_PS1], {
      windowsHide: true,
    })
    child.stdout.setEncoding('utf8')
    let buf = ''
    child.stdout.on('data', (d) => {
      buf += d
      let i
      while ((i = buf.indexOf('\n')) >= 0) {
        const line = buf.slice(0, i).replace(/\r$/, '')
        buf = buf.slice(i + 1)
        if (!line.trim()) continue
        const links = extractDouyin(line)
        if (!links.length) continue
        for (const u of links) {
          if (clipSeen.has(u)) continue
          clipSeen.add(u)
          clipLines.push({ url: u, at: Date.now() })
      // 被动模式：开闸状态下收到即入采集队列，不依赖面板轮询
      if (clipGateOpen) { try { capEnqueue(u) } catch { } }
        }
        if (clipLines.length > 200) clipLines = clipLines.slice(-200)
      }
    })
    child.on('exit', () => { clipChild = null })
    child.on('error', () => { clipChild = null })
    clipChild = child
    return { ok: true, started: true }
  } catch (e) {
    clipChild = null
    return { ok: false, error: String(e?.message ?? e) }
  }
}

/* 清掉历史遗留的 clipwatch 进程（只认命令行里的 clipwatch.ps1） */
function killStaleClipWatchers(exceptPid) {
  if (process.platform !== 'win32') return
  try {
    // 不用 -Filter 的引号嵌套，整条命令零双引号，避免 spawn 转义踩坑
    const ps = "Get-CimInstance Win32_Process | "
      + "Where-Object { $_.Name -eq 'powershell.exe' -and $_.CommandLine -match 'clipwatch\\.ps1' -and $_.ProcessId -ne " + (exceptPid || 0) + " } | "
      + "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
    const c = spawn('powershell', ['-NoProfile', '-Command', ps], { windowsHide: true, detached: true })
    if (c.unref) c.unref()
  } catch { }
}

function stopClipWatch() {
  try { clipChild?.kill() } catch { }
  clipChild = null
  killStaleClipWatchers(0)
  return { ok: true }
}

export const name = 'dsh-media-workbench'
export const inject = ['connection']

export function apply(ctx) {
  // 被动模式：宿主启动就开哨兵 + 默认开闸，复制链接即采集，不用点开面板
  try { clipGateOpen = true; startClipWatch() } catch (e) { ctx.logger?.warn?.('被动采集启动失败', e) }

  // DSH 每次启动 → 扫一次有没有新入库的内容需要提炼成观点（跑完就退，不常驻）
  // 用户要求：只在打开 DSH 时扫，不要定时轮询
  try {
    const PY = (process.env.DSH_PYTHON || path.join(process.env.LOCALAPPDATA || '', 'Programs', 'Python', 'Python312', 'pythonw.exe'))
    const SCRIPT = pyPath('media', 'auto_extract.py')
    if (fs.existsSync(PY) && fs.existsSync(SCRIPT)) {
      setTimeout(() => {
        try {
          const p = spawn(PY, [SCRIPT, '--once'], {
            detached: true,
            stdio: 'ignore',
            windowsHide: true,
            cwd: 'E:\\desktop\\media',
          })
          p.unref()
          ctx.logger?.info?.('dsh-media-workbench: 已触发启动时观点提炼扫描')
        } catch (e) {
          ctx.logger?.warn?.('启动时提炼扫描启动失败', e)
        }
      }, 30000) // 等 DSH 起来稳了再跑，不跟启动抢资源

      // 口袋手机服务：DSH 起来时顺手确认它在跑（计划任务每5分钟也会兜底）
      setTimeout(() => {
        try {
          const http = require('node:http')
          const req = http.get({ host: '127.0.0.1', port: 8788, path: '/api/ping', timeout: 1500 }, (res) => {
            res.resume()
            ctx.logger?.info?.('dsh-media-workbench: 口袋服务在线')
          })
          req.on('error', () => {
            try {
              const q = spawn(PY, [pyPath('media', 'mobile_server.py')], {
                detached: true, stdio: 'ignore', windowsHide: true, cwd: 'E:\\desktop\\media',
              })
              q.unref()
              ctx.logger?.info?.('dsh-media-workbench: 口袋服务不在，已拉起')
            } catch (e2) { ctx.logger?.warn?.('拉起口袋服务失败', e2) }
          })
          req.on('timeout', () => { try { req.destroy() } catch { } })
        } catch (e) {
          ctx.logger?.warn?.('检查口袋服务失败', e)
        }
      }, 8000)

      // 记忆自我迭代：7 天内没跑过就扫一遍「反复被纠正但没进 AGENTS.md」的教训，自动晋升
      setTimeout(() => {
        try {
          const mp = pyPath('media', 'memory_promote.py')
          if (fs.existsSync(mp)) {
            const q = spawn(PY, [mp, '--if-due'], {
              detached: true, stdio: 'ignore', windowsHide: true, cwd: 'E:\\desktop\\media',
            })
            q.unref()
            ctx.logger?.info?.('dsh-media-workbench: 已触发记忆自我迭代（7 天一次）')
          }
        } catch (e) {
          ctx.logger?.warn?.('记忆自我迭代触发失败', e)
        }
      }, 60000)
    }
  } catch (e) {
    ctx.logger?.warn?.('启动时提炼扫描挂载失败', e)
  }

  const disposers = []
  const conn = ctx.connection ?? ctx.get?.('connection')
  if (!conn?.fetch?.register) {
    ctx.logger?.warn?.('dsh-media-workbench: connection.fetch 不可用')
    return () => {}
  }

  // 探针：确认注册链路本身是否可用
  try {
    disposers.push(conn.fetch.register({
      path: '/api/dsh-media/ping',
      methods: ['GET'],
      requestBody: 'buffered',
      async fetch() {
        return Response.json({ ok: true, pong: Date.now() })
      },
    }))
    ctx.logger?.info?.('dsh-media-workbench: /ping 已注册')
  } catch (e) {
    ctx.logger?.warn?.('dsh-media-workbench: /ping 注册失败', e)
  }

  // 读热点
  try {
    disposers.push(conn.fetch.register({
      path: '/api/dsh-media/hot',
      methods: ['GET'],
      requestBody: 'buffered',
      async fetch() {
        try {
          return Response.json(loadHot())
        } catch (e) {
          return Response.json({ ok: false, reason: 'handler-error', error: String(e?.message ?? e) })
        }
      },
    }))
    ctx.logger?.info?.('dsh-media-workbench: /hot 已注册')
  } catch (e) {
    ctx.logger?.warn?.('dsh-media-workbench: /hot 注册失败', e)
  }

  // 读每日灵感
  try {
    disposers.push(conn.fetch.register({
      path: '/api/dsh-media/idea',
      methods: ['GET'],
      requestBody: 'buffered',
      async fetch() {
        try {
          return Response.json(loadIdea())
        } catch (e) {
          return Response.json({ ok: false, reason: 'handler-error', error: String(e?.message ?? e) })
        }
      },
    }))
    ctx.logger?.info?.('dsh-media-workbench: /idea 已注册')
  } catch (e) {
    ctx.logger?.warn?.('dsh-media-workbench: /idea 注册失败', e)
  }

  // AI 讲透（流式）
  try {
    disposers.push(conn.fetch.register({
      path: '/api/dsh-media/explain',
      methods: ['POST'],
      requestBody: 'buffered',
      async fetch(request) {
        let body
        try { body = await request.json() } catch { return new Response('bad json', { status: 400 }) }
        if (!body || !body.text) return new Response('missing text', { status: 400 })
        return streamResponse(async (signal) => {
          return streamText(ctx, { prompt: buildExplainPrompt(body) }, signal)
        })
      },
    }))
    ctx.logger?.info?.('dsh-media-workbench: /explain 已注册')
  } catch (e) {
    ctx.logger?.warn?.('dsh-media-workbench: /explain 注册失败', e)
  }

  // 自动补全灵感的角度与问题（幂等：只处理缺的）
  try {
    disposers.push(conn.fetch.register({
      path: '/api/dsh-media/idea/refine',
      methods: ['POST'],
      requestBody: 'buffered',
      async fetch() {
        try {
          return Response.json(await refineIdea(ctx))
        } catch (e) {
          return Response.json({ ok: false, reason: 'refine-error', error: String(e?.message ?? e) })
        }
      },
    }))
    ctx.logger?.info?.('dsh-media-workbench: /idea/refine 已注册')
  } catch (e) {
    ctx.logger?.warn?.('dsh-media-workbench: /idea/refine 注册失败', e)
  }

  /* ---------- 剪贴板哨兵 ---------- */
  const clipRoute = (p, methods, fn) => {
    try {
      disposers.push(conn.fetch.register({
        path: p, methods, requestBody: 'buffered', async fetch(req) { return fn(req) },
      }))
    } catch (e) {
      ctx.logger?.warn?.('dsh-media-workbench: ' + p + ' 注册失败', e)
    }
  }

  // 稿库语义匹配：转发到手机服务（同一个库、同一套判断，不用写两份）
  clipRoute('/api/dsh-media/match', ['GET'], async (req) => {
    try {
      const u = new URL(req.url)
      const text = u.searchParams.get('text') || ''
      if (!text) return Response.json({ ok: false, error: '缺少 text' })
      const r = await fetch('http://127.0.0.1:8788/api/match?text=' + encodeURIComponent(text))
      const j = await r.json()
      return Response.json(j)
    } catch (e) {
      return Response.json({ ok: false, error: '匹配服务没起来：' + String(e && e.message) })
    }
  })

  clipRoute('/api/dsh-media/dash/stats', ['GET'], async () => Response.json(await dashStats()))
  clipRoute('/api/dsh-media/dash/start', ['POST'], async () => Response.json(await dashCtl('start')))
  clipRoute('/api/dsh-media/dash/pause', ['POST'], async () => Response.json(await dashCtl('pause')))
  clipRoute('/api/dsh-media/dash/cancel', ['POST'], async () => Response.json(await dashCtl('cancel')))

  clipRoute('/api/dsh-media/clip/start', ['POST'], async () => Response.json(startClipWatch()))
  clipRoute('/api/dsh-media/clip/stop', ['POST'], async () => Response.json(stopClipWatch()))

  /* ---- 小红书关注里谁在播 ---- */
  // 读上次结果（不弹窗、不耗时）
  clipRoute('/api/dsh-media/xhs-follow', ['GET'], async () => {
    const raw = readTextSafe(XHS_FOLLOW_JSON)
    if (!raw) return Response.json({ ok: false, empty: true, hint: '还没查过' })
    try {
      return Response.json(JSON.parse(raw))
    } catch {
      return Response.json({ ok: false, error: '缓存文件坏了' })
    }
  })
  // 触发一次检查（会弹一个浏览器窗口，十几秒）
  let xhsFollowBusy = false
  clipRoute('/api/dsh-media/xhs-follow/scan', ['POST'], async () => {
    if (xhsFollowBusy) return Response.json({ ok: false, busy: true, hint: '正在查，等一下' })
    xhsFollowBusy = true
    try {
      const done = await new Promise((resolve) => {
        let errTxt = ''
        let child
        try {
          child = spawn(PY_SYS, [XHS_FOLLOW_SCRIPT], { cwd: path.dirname(XHS_FOLLOW_SCRIPT), windowsHide: true })
        } catch (e) {
          resolve({ ok: false, error: '起不来 python：' + String(e?.message ?? e) })
          return
        }
        child.stderr?.on('data', (d) => { errTxt += String(d).slice(0, 400) })
        const timer = setTimeout(() => {
          try { child.kill() } catch { }
          resolve({ ok: false, error: '查了 60 秒还没回来，终止了' })
        }, 60000)
        child.on('error', (e) => { clearTimeout(timer); resolve({ ok: false, error: String(e?.message ?? e) }) })
        child.on('close', (code) => { clearTimeout(timer); resolve({ ok: code === 0, code, stderr: errTxt }) })
      })
      if (!done.ok) {
        return Response.json({ ok: false, error: done.error || ('脚本退出码 ' + done.code), detail: done.stderr || '' })
      }
      const raw = readTextSafe(XHS_FOLLOW_JSON)
      if (!raw) return Response.json({ ok: false, error: '跑完了但没读到结果文件' })
      return Response.json(JSON.parse(raw))
    } catch (e) {
      return Response.json({ ok: false, error: String(e?.message ?? e) })
    } finally {
      xhsFollowBusy = false
    }
  })

  /* ---- GitHub 热榜 ---- */
  // 读当天榜（不联网，读 sqlite）
  clipRoute('/api/dsh-media/gh-trending', ['GET'], async () => Response.json(await runPyJson(GH_QUERY)))
  // 立刻重抓一次（联网跑 collect.py，再读回来）
  clipRoute('/api/dsh-media/gh-trending/refresh', ['POST'], async () => {
    const got = await runPyJsonEx(GH_COLLECT, [], { timeoutMs: 180000 })
    const data = await runPyJson(GH_QUERY)
    return Response.json({ ok: !!data.ok, collect: got, data })
  })
  // 给一屏榜单补 AI 简介：一次最多 8 条，前端循环调；按榜补，没展开的榜不烧 token
  let ghIntroBusy = false
  clipRoute('/api/dsh-media/gh-trending/intro', ['POST'], async (req) => {
    let body = {}
    try { body = await req.json() } catch { }
    const list = String((body && body.list) || '').trim()
    if (ghIntroBusy) return Response.json({ ok: false, busy: true, hint: '上一条还在生成，等一下' })
    ghIntroBusy = true
    try {
      const args = ['--limit=8']
      if (/^[a-z0-9]+$/.test(list)) args.push('--list=' + list)
      return Response.json(await runPyJsonEx(GH_INTRO, args, { env: ghIntroEnv(), timeoutMs: 150000 }))
    } finally {
      ghIntroBusy = false
    }
  })
  // 判断一个项目：有用 → 进看板（待完成）；没用 → 以后不再出现
  clipRoute('/api/dsh-media/gh-trending/judge', ['POST'], async (req) => {
    let body = {}
    try { body = await req.json() } catch { }
    const repo = String((body && body.repo) || '').trim()
    const verdict = (body && body.verdict) === 'useful' ? 'useful'
      : (body && body.verdict) === 'useless' ? 'useless' : ''
    if (!/^[\w.-]+\/[\w.-]+$/.test(repo)) return Response.json({ ok: false, error: '仓库名不对：' + repo })
    if (!verdict) return Response.json({ ok: false, error: 'verdict 只能是 useful 或 useless' })
    let card = null
    if (verdict === 'useful') {
      const what = String((body && body.what) || '').trim()
      const use = String((body && body.use) || '').trim()
      const stars = Number((body && body.stars) || 0)
      const gained = Number((body && body.gained) || 0)
      const name = repo.split('/')[1] || repo
      const title = (what || name).replace(/[。.]$/, '').slice(0, 30) + '（' + repo + '）'
      const note = [
        '【来源】需求发掘台 · GitHub 热榜',
        '【仓库】' + repo + '（⭐ ' + stars.toLocaleString('en-US') + (gained ? ' · 本期 +' + gained.toLocaleString('en-US') : '') + '）',
        what ? '【是什么】' + what : '',
        use ? '【能做什么】' + use : '',
        '【链接】https://github.com/' + repo,
        '',
        '【下一步】看 README 和 issue，判断一个人能不能做、值不值得做。',
      ].filter(Boolean).join('\n')
      card = createBoardCard(ctx, {
        title, note, nextStep: '看 README，判断能不能做成小工具', workspace: 'desktop',
      })
    }
    const r = await runPyJson(GH_JUDGE, ['--repo', repo, '--verdict', verdict, '--card', card ? card.id : ''])
    return Response.json({ ok: !!(r && r.ok), card, judge: r })
  })
  clipRoute('/api/dsh-media/clip/gate', ['POST'], async (req) => {
    let body = {}
    try { body = await req.json() } catch { }
    clipGateOpen = !!(body && body.open)
    if (clipGateOpen) clipLines = []   // 开闸后清空已积压的，从此刻算
    return Response.json({ ok: true, open: clipGateOpen })
  })
  clipRoute('/api/dsh-media/clip/poll', ['GET'], async () => {
    const take = clipLines.slice()
    clipLines = []
    // 不在这里自动拉起哨兵：只有 /clip/start 才启动。
    // 否则一旦被停掉，轮询会把它反复复活。
    // 开闸状态下，收到即入采集队列（自动转写）
    if (clipGateOpen && take.length) {
      for (const it of take) capEnqueue(it.url)
    }
    return Response.json({
      ok: true,
      running: !!clipChild,
      gateOpen: clipGateOpen,
      items: take,
      total: clipSeen.size,
    })
  })

  /* ---------- 采集队列（转写入库） ---------- */
  clipRoute('/api/dsh-media/capture/queue', ['POST'], async (req) => {
    let body = {}
    try { body = await req.json() } catch { }
    return Response.json(capEnqueue(body && body.url))
  })
  // 智能分诊：主页→直播监控；视频→文案采集；直播→待录
  clipRoute('/api/dsh-media/capture/smart', ['POST'], async (req) => {
    let body = {}
    try { body = await req.json() } catch { }
    const url = (body && body.url) || ''
    const r = await runPyJson(LINK_ROUTER, [url])
    if (r && r.ok && r.kind === 'video') {
      const q = capEnqueue(r.url || url)
      r.queued = !!(q && q.queued)
      r.duplicate = !!(q && q.duplicate)
    }
    return Response.json(r)
  })
  clipRoute('/api/dsh-media/live/watchlist', ['GET'], async () => {
    return Response.json(await runPyJson(LINK_ROUTER, ['--list']))
  })
  clipRoute('/api/dsh-media/capture/status', ['GET'], async () => {
    return Response.json({
      ok: true,
      running: capRunning,
      items: capQueue.slice(-30).reverse(),
      counts: {
        pending: capQueue.filter((x) => x.status === 'pending').length,
        running: capQueue.filter((x) => x.status === 'running').length,
        done: capQueue.filter((x) => x.status === 'done').length,
        failed: capQueue.filter((x) => x.status === 'failed').length,
      },
    })
  })
  // 直播录制实时状态（读磁盘：在录谁、录多大、转写排队多少）
  clipRoute('/api/dsh-media/live/rec', ['GET'], async () => {
    try {
      return Response.json(liveStatusNow())
    } catch (e) {
      return Response.json({ ok: false, error: String(e?.message ?? e) })
    }
  })
  // 录制开关：暂停 / 恢复（守护进程 5 秒内生效）
  clipRoute('/api/dsh-media/live/pause', ['POST'], async () => {
    try { fs.writeFileSync(LIVE_PAUSE, String(Date.now())) } catch { }
    return Response.json({ ok: true, paused: true })
  })
  clipRoute('/api/dsh-media/live/resume', ['POST'], async () => {
    try { fs.unlinkSync(LIVE_PAUSE) } catch { }
    return Response.json({ ok: true, paused: false })
  })

  /* ---------- 每日自动任务的状态与手动触发 ---------- */
  clipRoute('/api/dsh-media/auto/status', ['GET'], async () => Response.json(autoStatus()))
  clipRoute('/api/dsh-media/auto/run', ['POST'], async (req) => {
    let body = {}
    try { body = await req.json() } catch { }
    const kind = String(body.kind || 'hot')
    if (kind === 'idea') { autoIdea(ctx); return Response.json({ ok: true, started: 'idea' }) }
    autoHot(ctx)
    return Response.json({ ok: true, started: 'hot' })
  })

  // 触发抓取：走自动任务同一条链路，抓完顺带补中文
  try {
    disposers.push(conn.fetch.register({
      path: '/api/dsh-media/hot/refresh',
      methods: ['POST'],
      requestBody: 'buffered',
      async fetch() {
        if (auto.hot.running || refreshing) return Response.json({ ok: true, running: true })
        refreshing = true
        autoHot(ctx).finally(() => { refreshing = false })
        return Response.json({ ok: true, started: true })
      },
    }))
  } catch (e) {
    ctx.logger?.warn?.('dsh-media-workbench: /refresh 注册失败', e)
  }

  // 数据库统计
  try {
    disposers.push(conn.fetch.register({
      path: '/api/dsh-media/stats',
      methods: ['GET'],
      requestBody: 'buffered',
      async fetch() {
        return Response.json(dbStats())
      },
    }))
  } catch (e) {
    ctx.logger?.warn?.('dsh-media-workbench: /stats 注册失败', e)
  }

  // 库总览：稿数 / 原子数 / 博主 / 原子类型分布
  try {
    disposers.push(conn.fetch.register({
      path: '/api/dsh-media/summary',
      methods: ['GET'],
      requestBody: 'buffered',
      async fetch() {
        return Response.json(await queryWb(['summary']))
      },
    }))
    ctx.logger?.info?.('dsh-media-workbench: /summary 已注册')
  } catch (e) {
    ctx.logger?.warn?.('dsh-media-workbench: /summary 注册失败', e)
  }


  // 稿库列表
  try {
    disposers.push(conn.fetch.register({
      path: '/api/dsh-media/posts',
      methods: ['GET'],
      requestBody: 'buffered',
      async fetch(req) {
        let author = null
        let topic = null
        let order = null
        let source = null
        let limit = 60
        try {
          const u = new URL(req.url || '/', 'http://localhost')
          author = u.searchParams.get('author')
          topic = u.searchParams.get('topic')
          order = u.searchParams.get('order')
          source = u.searchParams.get('source')
          const n = Number(u.searchParams.get('limit'))
          if (n > 0) limit = Math.min(n, 300)
        } catch { }
        return Response.json(await queryWb(['posts', author || '', String(limit), topic || '', order || '', source || '']))
      },
    }))
  } catch (e) {
    ctx.logger?.warn?.('dsh-media-workbench: /posts 注册失败', e)
  }

  // 原子列表（支持 视图/搜索/分页）
  try {
    disposers.push(conn.fetch.register({
      path: '/api/dsh-media/atoms',
      methods: ['GET'],
      requestBody: 'buffered',
      async fetch(req) {
        let type = null
        let limit = 80
        let offset = 0
        let view = null
        let q = null
        try {
          const u = new URL(req.url || '/', 'http://localhost')
          type = u.searchParams.get('type')
          view = u.searchParams.get('view')
          q = u.searchParams.get('q')
          const n = Number(u.searchParams.get('limit'))
          if (n > 0) limit = Math.min(n, 300)
          const off = Number(u.searchParams.get('offset'))
          if (off > 0) offset = off
        } catch { }
        return Response.json(await queryWb(['atoms', type || '', String(limit), String(offset), view || '', q || '']))
      },
    }))
    ctx.logger?.info?.('dsh-media-workbench: /atoms 已注册')
  } catch (e) {
    ctx.logger?.warn?.('dsh-media-workbench: /atoms 注册失败', e)
  }

  // 原子批量隐藏 / 恢复（用户在拆解面板逐条点删）
  clipRoute('/api/dsh-media/atoms/hide', ['POST'], async (req) => {
    let body = {}
    try { body = await req.json() } catch { }
    const ids = Array.isArray(body.ids) ? body.ids.join(',') : (body.id || '')
    const hidden = body.hidden === false ? 0 : 1
    if (!ids) return Response.json({ ok: false, error: 'missing ids' })
    return Response.json(await queryWb(['hide', String(ids), String(hidden)]))
  })

  // 稿子批量隐藏 / 恢复（内容库逐条点删）
  clipRoute('/api/dsh-media/posts/hide', ['POST'], async (req) => {
    let body = {}
    try { body = await req.json() } catch { }
    const ids = Array.isArray(body.ids) ? body.ids.join(',') : (body.id || '')
    const hidden = body.hidden === false ? 0 : 1
    if (!ids) return Response.json({ ok: false, error: 'missing ids' })
    return Response.json(await queryWb(['hidepost', String(ids), String(hidden)]))
  })

  // 稿子彻底删除（不可恢复，连带原子与来源记录）
  clipRoute('/api/dsh-media/posts/delete', ['POST'], async (req) => {
    let body = {}
    try { body = await req.json() } catch { }
    const ids = Array.isArray(body.ids) ? body.ids.join(',') : (body.id || '')
    if (!ids) return Response.json({ ok: false, error: 'missing ids' })
    return Response.json(await queryWb(['delpost', String(ids)]))
  })

  // 钩子库：每篇稿的开头句，按打法检索
  clipRoute('/api/dsh-media/hooks', ['GET'], async (req) => {
    let style = null, q = null, limit = 60, offset = 0
    try {
      const u = new URL(req.url || '/', 'http://localhost')
      style = u.searchParams.get('style')
      q = u.searchParams.get('q')
      const n = Number(u.searchParams.get('limit'))
      if (n > 0) limit = Math.min(n, 300)
      const off = Number(u.searchParams.get('offset'))
      if (off > 0) offset = off
    } catch { }
    return Response.json(await queryWb(['hooks', style || '', String(limit), String(offset), q || '']))
  })

  // 文案拆解五板块（干货/案例/金句/避坑/问答）
  clipRoute('/api/dsh-media/split', ['GET'], async (req) => {
    let board = null, q = null, limit = 80, offset = 0
    try {
      const u = new URL(req.url || '/', 'http://localhost')
      board = u.searchParams.get('board')
      q = u.searchParams.get('q')
      const n = Number(u.searchParams.get('limit'))
      if (n > 0) limit = Math.min(n, 300)
      const off = Number(u.searchParams.get('offset'))
      if (off > 0) offset = off
    } catch { }
    return Response.json(await queryWb(['split', board || '', String(limit), String(offset), q || '']))
  })

  // 某篇稿子拆出的原子（文案拆解 ↔ 内容库打通）
  clipRoute('/api/dsh-media/postatoms', ['GET'], async (req) => {
    let id = ''
    try {
      const u = new URL(req.url || '/', 'http://localhost')
      id = u.searchParams.get('id') || ''
    } catch { }
    if (!id) return Response.json({ ok: false, error: 'missing id' })
    return Response.json(await queryWb(['postatoms', id, '100']))
  })

  // 原子批量标记：fuzz（待定）/ ''（取消标记）
  clipRoute('/api/dsh-media/atoms/flag', ['POST'], async (req) => {
    let body = {}
    try { body = await req.json() } catch { }
    const ids = Array.isArray(body.ids) ? body.ids.join(',') : (body.id || '')
    const flag = body.flag || 'fuzz'
    if (!ids) return Response.json({ ok: false, error: 'missing ids' })
    return Response.json(await queryWb(['flag', String(ids), String(flag)]))
  })

  // 单篇全文
  try {
    disposers.push(conn.fetch.register({
      path: '/api/dsh-media/post',
      methods: ['GET'],
      requestBody: 'buffered',
      async fetch(req) {
        let id = ''
        try {
          const u = new URL(req.url || '/', 'http://localhost')
          id = u.searchParams.get('id') || ''
        } catch { }
        if (!id) return Response.json({ ok: false, error: 'missing id' })
        return Response.json(await queryWb(['post', id]))
      },
    }))
    ctx.logger?.info?.('dsh-media-workbench: /post 已注册')
  } catch (e) {
    ctx.logger?.warn?.('dsh-media-workbench: /post 注册失败', e)
  }

  // 拆解条目的原文出处：书查 book_chunks，稿查 posts（旧的 /post 只查 posts，书来源全点不开）
  clipRoute('/api/dsh-media/source', ['GET'], async (req) => {
    let id = ''
    try {
      const u = new URL(req.url || '/', 'http://localhost')
      id = u.searchParams.get('id') || ''
    } catch { }
    if (!id) return Response.json({ ok: false, error: 'missing id' })
    return Response.json(await runPyJson(SPLIT_SOURCE, [id]))
  })

  // 稿库「书」来源：列书
  clipRoute('/api/dsh-media/books', ['GET'], async (req) => {
    let limit = 60
    let q = ''
    let category = ''
    try {
      const u = new URL(req.url || '/', 'http://localhost')
      const n = Number(u.searchParams.get('limit'))
      if (n > 0) limit = Math.min(n, 300)
      q = u.searchParams.get('q') || ''
      category = u.searchParams.get('category') || ''
    } catch { }
    return Response.json(await runPyJson(BOOKS_Q, ['list', '--limit', String(limit), '--q', q, '--category', category]))
  })
  // 稿库「书」来源：读一本全文
  clipRoute('/api/dsh-media/book', ['GET'], async (req) => {
    let id = ''
    let title = ''
    try {
      const u = new URL(req.url || '/', 'http://localhost')
      id = u.searchParams.get('id') || ''
      title = u.searchParams.get('title') || ''
    } catch { }
    if (!id && !title) return Response.json({ ok: false, error: 'missing id/title' })
    return Response.json(await runPyJson(BOOKS_Q, ['book', '--id', id, '--title', title]))
  })

  /* ---------- 口播训练（能力提升） ---------- */
  const SPEECH_PORT = 8777
  const SPEECH_SCRIPT = pyPath('asr', 'speech_server.py')
  let speechChild = null

  async function ensureSpeech() {
    const ping = async () => {
      try {
        const r = await fetch(`http://127.0.0.1:${SPEECH_PORT}/health`)
        return r.ok
      } catch { return false }
    }
    if (await ping()) return true
    if (!speechChild) {
      try {
        speechChild = spawn(PY, [SPEECH_SCRIPT, String(SPEECH_PORT)], { windowsHide: true })
        speechChild.on('exit', () => { speechChild = null })
        speechChild.on('error', () => { speechChild = null })
      } catch { return false }
    }
    for (let i = 0; i < 40; i++) {
      await new Promise((r) => setTimeout(r, 500))
      if (await ping()) return true
    }
    return false
  }
  const WORD_POOL = ('电梯 雨伞 账单 风筝 螺丝 镜子 枕头 钥匙 冰箱 楼梯 窗帘 牙刷 闹钟 地图 印章 喇叭 背包 铅笔 火柴 水壶 拖鞋 衣架 台灯 头盔 渔船 铁钉 胶片 纸箱 铃铛 扑克 苹果 面包 出租车 菜市场 理发店 停车场 便利店 录音机 行李箱 雨衣 灯泡 书签 筷子 抹布 水龙头 充电器 计算器 打火机 围巾 帽子 胶带 剪刀 信箱').split(' ').filter(Boolean)
  function randomWords(n = 6) {
    const pool = WORD_POOL.slice()
    const out = []
    while (out.length < n && pool.length) out.push(pool.splice(Math.floor(Math.random() * pool.length), 1)[0])
    return out
  }

  clipRoute('/api/dsh-media/speech/words', ['GET'], async (req) => {
    let n = 6
    try {
      const u = new URL(req.url || '/', 'http://localhost')
      const k = Number(u.searchParams.get('n'))
      if (k >= 3 && k <= 10) n = k
    } catch { }
    return Response.json({ ok: true, words: randomWords(n) })
  })

  clipRoute('/api/dsh-media/speech/asr', ['POST'], async (req) => {
    const up = await ensureSpeech()
    if (!up) return Response.json({ ok: false, error: '语音服务没起来' })
    let model = 'small'
    try {
      const u = new URL(req.url || '/', 'http://localhost')
      const m = u.searchParams.get('m')
      if (m === 'turbo' || m === 'small') model = m
    } catch { }
    const buf = Buffer.from(await req.arrayBuffer())
    try {
      const r = await fetch(`http://127.0.0.1:${SPEECH_PORT}/asr?m=${model}`, {
        method: 'POST', headers: { 'Content-Type': 'application/octet-stream' }, body: buf,
      })
      return new Response(await r.text(), { status: r.status, headers: { 'Content-Type': 'application/json; charset=utf-8' } })
    } catch (e) {
      return Response.json({ ok: false, error: String(e?.message ?? e) })
    }
  })

  const FILLERS = ['嗯', '啊', '呃', '那个', '然后', '就是', '其实', '反正', '怎么说']
  clipRoute('/api/dsh-media/speech/score', ['POST'], async (req) => {
    let body = {}
    try { body = await req.json() } catch { }
    const words = Array.isArray(body.words) ? body.words : []
    const transcript = String(body.transcript || '')
    if (!transcript.trim()) return Response.json({ ok: false, error: '没有识别到内容' })
    const han = (transcript.match(/[\\u4e00-\\u9fff]/g) || []).length
    const secs = Math.max(1, Number(body.seconds) || 1)
    let fill = 0
    for (const f of FILLERS) fill += transcript.split(f).length - 1
    const used = words.filter((w) => w && transcript.includes(w))
    const mech = { chars: han, seconds: Math.round(secs), pace: Math.round(han / secs * 60), fillers: fill, used, usedCount: used.length, totalWords: words.length }
    const prompt = `你是口播教练。用户拿到这组词【${words.join('、')}】，脱稿讲了 ${mech.seconds} 秒，逐字稿：\n\n${transcript}\n\n只输出 JSON：{"contentScore":0-100,"logic":"一句评价结构","voice":"一句评价像不像在跟人说话","improvements":["改进1","改进2","改进3"]}。改进点要具体到下次怎么说，每条不超过30字。`
    try {
      let acc = ''
      for await (const t of streamTextWith(ctx, { prompt, maxTokens: 800, system: '你是严格但具体的口播教练。只输出 JSON。' })) acc += t
      let obj = null
      const a2 = acc.indexOf('{'), b2 = acc.lastIndexOf('}')
      if (a2 >= 0 && b2 > a2) { try { obj = JSON.parse(acc.slice(a2, b2 + 1)) } catch { } }
      if (!obj) return Response.json({ ok: false, error: '模型返回无法解析', mechanical: mech })
      return Response.json({ ok: true, mechanical: mech, review: obj })
    } catch (e) {
      return Response.json({ ok: false, error: String(e?.message ?? e), mechanical: mech })
    }
  })

  /* ---------- 分身（角色）与圆桌会议 ---------- */
  const PERSONAS_FILE = dataPath('media', 'personas.json')

  function loadPersonas() {
    try {
      const j = readJson(PERSONAS_FILE)
      return (j && Array.isArray(j.personas)) ? j.personas : []
    } catch { return [] }
  }

  function personaSystem(p, question, atoms) {
    const src = (atoms || []).map((a, i) => `[${i + 1}] ${String(a.knowledge || '').slice(0, 120)}`).join('\n')
    return `你是「${p.name}」，${p.title}。

你的知识来自用户精选的商业博主内容库，下面是与本次问题相关的素材（可能与问题不完全相关，无关就无视，不要硬套）：
${src || '（本次没有检索到明显相关的素材）'}

你的关注点：${p.focus}
你的判断框架：${p.frame}
你的说话方式：${p.voice}
你明确反对：${p.against}

用户问：${question}

用你的角度回答，200 字以内，口语，不要分点、不要标题、不要 markdown。只讲你自己的看法，不要替别人总结。`
  }

  clipRoute('/api/dsh-media/personas', ['GET'], async () => Response.json({ ok: true, personas: loadPersonas() }))

  clipRoute('/api/dsh-media/search', ['GET'], async (req) => {
    let q = ''
    let limit = 8
    try {
      const u = new URL(req.url || '/', 'http://localhost')
      q = u.searchParams.get('q') || ''
      const n = Number(u.searchParams.get('limit'))
      if (n > 0) limit = Math.min(n, 30)
    } catch { }
    return Response.json(await queryWb(['search', q, String(limit)]))
  })

  clipRoute('/api/dsh-media/personas/chat', ['POST'], async (req) => {
    let body = {}
    try { body = await req.json() } catch { }
    const id = String(body.personaId || '')
    const question = String(body.question || '').trim()
    if (!question) return Response.json({ ok: false, error: '缺少问题' })
    const p = loadPersonas().find((x) => x.id === id)
    if (!p) return Response.json({ ok: false, error: '找不到这个角色' })
    const found = await queryWb(['search', question, '6'])
    const atoms = (found && found.ok && Array.isArray(found.list)) ? found.list : []
    return streamResponse(async (signal) => streamTextWith(ctx, {
      prompt: personaSystem(p, question, atoms),
      maxTokens: 600,
      system: '你是一个有明确立场的顾问，说话口语、短句、不客套。',
    }, signal))
  })

  clipRoute('/api/dsh-media/personas/roundtable', ['POST'], async (req) => {
    let body = {}
    try { body = await req.json() } catch { }
    const question = String(body.question || '').trim()
    if (!question) return Response.json({ ok: false, error: '缺少问题' })
    let ids = Array.isArray(body.personaIds) ? body.personaIds : []
    let all = loadPersonas()
    if (!ids.length) ids = all.slice(0, 5).map((x) => x.id)
    const picked = ids.map((i) => all.find((x) => x.id === i)).filter(Boolean).slice(0, 8)
    const found = await queryWb(['search', question, '8'])
    const atoms = (found && found.ok && Array.isArray(found.list)) ? found.list : []
    const answers = await Promise.all(picked.map(async (p) => {
      try {
        let acc = ''
        for await (const t of streamTextWith(ctx, {
          prompt: personaSystem(p, question, atoms),
          maxTokens: 500,
          system: '你是顾问团的一员，只讲你这一角度的看法，允许和其他顾问冲突。',
        })) acc += t
        return { id: p.id, name: p.name, title: p.title, text: acc.trim() }
      } catch (e) {
        return { id: p.id, name: p.name, title: p.title, text: '', error: String(e?.message ?? e) }
      }
    }))
    return Response.json({ ok: true, question, answers, sources: atoms.slice(0, 6).map((a) => ({ id: a.id, knowledge: String(a.knowledge || '').slice(0, 80) })) })
  })

  // 顾问团：能不能加人（按素材量 + 是否已被覆盖）
  const PERSONA_MIN_ATOMS = 120

  clipRoute('/api/dsh-media/personas/suggest', ['GET'], async () => {
    const dist = await queryWb(['topics'])
    const list = (dist && dist.ok && Array.isArray(dist.topics)) ? dist.topics : []
    const ps = loadPersonas()
    const covered = new Set()
    for (const p of ps) for (const t of (p.topics || [])) covered.add(t)
    const cand = list
      .filter((t) => (t.n || 0) >= PERSONA_MIN_ATOMS && !covered.has(t.name))
      .map((t) => ({ topic: t.name, atoms: t.n }))
    return Response.json({
      ok: true,
      total: (dist && dist.total) || 0,
      threshold: PERSONA_MIN_ATOMS,
      existing: ps.length,
      candidates: cand,
      uncovered: list.filter((t) => !covered.has(t.name)).map((t) => ({ topic: t.name, atoms: t.n })),
    })
  })

  // 草稿：按话题蒸馏出一张人设卡（只返回，不落库）
  clipRoute('/api/dsh-media/personas/draft', ['POST'], async (req) => {
    let body = {}
    try { body = await req.json() } catch { }
    const topic = String(body.topic || '').trim()
    if (!topic) return Response.json({ ok: false, error: '缺少话题' })
    const got = await queryWb(['bytopic', topic, '30'])
    const atoms = (got && got.ok && Array.isArray(got.list)) ? got.list : []
    if (!atoms.length) return Response.json({ ok: false, error: '这个话题没有素材' })
    const corpus = atoms.map((a, i) => `[${i + 1}] ${String(a.knowledge || '').slice(0, 110)}`).join('\n')
    const prompt = `下面是一个内容库中「${topic}」类素材的抽样：

${corpus}

请据此设计一个顾问角色。只输出 JSON：
{"name":"两个字的中文名","title":"一句话定位（不超过18字）","focus":"他关注什么（一句话）","frame":"他的判断框架（一句话）","voice":"他说话的腔调（一句话）","against":"他明确反对什么（一句话）"}
要求：名字像真人，腔调要能和其他顾问区分开，不要说空话。`
    try {
      let acc = ''
      for await (const t of streamTextWith(ctx, { prompt, maxTokens: 500, system: '你是角色设计师。只输出 JSON。' })) acc += t
      const a2 = acc.indexOf('{'), b2 = acc.lastIndexOf('}')
      if (a2 < 0 || b2 <= a2) return Response.json({ ok: false, error: '解析失败', raw: acc.slice(0, 200) })
      const obj = JSON.parse(acc.slice(a2, b2 + 1))
      obj.topics = [topic]
      return Response.json({ ok: true, persona: obj, samples: atoms.slice(0, 3).map((a) => String(a.knowledge || '').slice(0, 60)) })
    } catch (e) {
      return Response.json({ ok: false, error: String(e?.message ?? e) })
    }
  })

  // 落库：把审核过的人设写进 personas.json
  clipRoute('/api/dsh-media/personas/add', ['POST'], async (req) => {
    let body = {}
    try { body = await req.json() } catch { }
    const p = body && body.persona
    if (!p || !p.name) return Response.json({ ok: false, error: '缺少角色数据' })
    try {
      const cur = readJson(PERSONAS_FILE) || { version: 2, personas: [] }
      const list = Array.isArray(cur.personas) ? cur.personas : []
      const id = 'p' + Date.now().toString(36)
      list.push({
        id, name: String(p.name).slice(0, 8), title: String(p.title || '').slice(0, 24),
        topics: Array.isArray(p.topics) ? p.topics.slice(0, 3) : [],
        focus: String(p.focus || ''), frame: String(p.frame || ''),
        voice: String(p.voice || ''), against: String(p.against || ''),
      })
      cur.version = (cur.version || 1) + 1
      cur.personas = list
      fs.writeFileSync(PERSONAS_FILE, JSON.stringify(cur, null, 2), 'utf8')
      return Response.json({ ok: true, id, total: list.length })
    } catch (e) {
      return Response.json({ ok: false, error: String(e?.message ?? e) })
    }
  })

  // 圆桌：再来一轮（互相反驳）
  clipRoute('/api/dsh-media/personas/roundtable/next', ['POST'], async (req) => {
    let body = {}
    try { body = await req.json() } catch { }
    const question = String(body.question || '').trim()
    const prev = Array.isArray(body.prev) ? body.prev : []
    if (!question) return Response.json({ ok: false, error: '缺少议题' })
    if (!prev.length) return Response.json({ ok: false, error: '还没有上一轮发言' })
    let ids = Array.isArray(body.personaIds) ? body.personaIds : []
    const all = loadPersonas()
    if (!ids.length) ids = prev.map((x) => x.id)
    const picked = ids.map((i) => all.find((x) => x.id === i)).filter(Boolean).slice(0, 8)
    const found = await queryWb(['search', question, '8'])
    const atoms = (found && found.ok && Array.isArray(found.list)) ? found.list : []
    const round = Number(body.round || 2)

    const answers = await Promise.all(picked.map(async (p) => {
      const others = prev.filter((x) => x.id !== p.id)
        .map((x) => `${x.name}：${String(x.text || '').slice(0, 160)}`).join('\n')
      const src = atoms.map((a, i) => `[${i + 1}] ${String(a.knowledge || '').slice(0, 100)}`).join('\n')
      const prompt = `议题：${question}

第 ${round} 轮。上一轮其他人这样说：
${others || '（其他人没有发言）'}

库内相关素材（可引用，不相关就无视）：
${src || '（无）'}

你是「${p.name}」，${p.title}。你的关注点：${p.focus}；判断框架：${p.frame}；腔调：${p.voice}；你反对：${p.against}

这一轮你要做的是**回应他们**，不是重复自己上一轮的话：
- 不同意谁的具体判断，就点名，说清楚哪里不成立
- 有他们没想到的角度，补上
- 被说服了就直说改口，并说明为什么
150 字以内，口语，不要分点，不要标题。`
      try {
        let acc = ''
        for await (const t of streamTextWith(ctx, {
          prompt, maxTokens: 420,
          system: '你们在开圆桌会议。只讲你这一角度的回应，允许直接反驳别人。',
        })) acc += t
        return { id: p.id, name: p.name, title: p.title, text: acc.trim() }
      } catch (e) {
        return { id: p.id, name: p.name, title: p.title, text: '', error: String(e?.message ?? e) }
      }
    }))
    return Response.json({ ok: true, round, answers })
  })

  /* ---------- 圆桌会议：带存档 + 追问 ---------- */
  const RT_FILE = dataPath('media', 'roundtable.json')

  function loadRT() {
    try {
      const j = readJson(RT_FILE)
      return (j && Array.isArray(j.topics)) ? j : { version: 1, topics: [] }
    } catch { return { version: 1, topics: [] } }
  }
  function saveRT(j) {
    try { fs.writeFileSync(RT_FILE, JSON.stringify(j, null, 2), 'utf8') } catch { }
  }
  const rtLen = (v, d) => String(v || '').slice(0, d)

  function roundPrompt(p, question, round, others, atoms) {
    const src = (atoms || []).map((a, i) => `[${i + 1}] ${String(a.knowledge || '').slice(0, 100)}`).join('\n')
    const seen = others ? `第 ${round} 轮。其他人上一轮这样说：\n${others}\n\n` : ''
    const task = others
      ? '这一轮要回应他们：不同意谁的具体判断就点名说清哪里不成立；有他们没想到的角度就补上；被说服就直说改口。'
      : '讲清你从自己角度怎么看这件事。'
    return `议题：${question}

${seen}库内相关素材（可引用，不相关就无视）：
${src || '（无）'}

你是「${p.name}」，${p.title}。关注点：${p.focus}；判断框架：${p.frame}；腔调：${p.voice}；你反对：${p.against}

${task}

${others ? '如果你看了他们的发言，觉得自己没有新的、跟别人不一样的东西值得说，就只输出 PASS（四个英文字母，不要解释、不要标点）。想说话就正常说，不要在正文里出现 PASS。' : ''}

格式要求（很重要）：
第一行只写一个用【】包住的标题，不超过 16 个字，概括你这段话的态度或结论；
第二行开始写正文，正文里不要出现任何【】。
正文里用两个星号把**最核心的短句或关键词**包起来，一到三处，不要滥用。
不要分点、不要用 markdown 列表。
长度按需要：简单的事一句话就够，值得展开的可以写两三百字，最多八百字。不要为了显得完整而凑字数，也不要为了守字数而把话说半截。`
  }

  clipRoute('/api/dsh-media/roundtable/list', ['GET'], async () => {
    const j = loadRT()
    const list = j.topics.map((t) => ({
      id: t.id, question: t.question, createdAt: t.createdAt,
      rounds: (t.rounds || []).length,
      speakers: ((t.rounds || [])[0] || {}).answers ? t.rounds[0].answers.length : 0,
      followups: (t.followups || []).length,
    })).reverse()
    return Response.json({ ok: true, list })
  })

  clipRoute('/api/dsh-media/roundtable/get', ['GET'], async (req) => {
    let id = ''
    try { const u = new URL(req.url || '/', 'http://localhost'); id = u.searchParams.get('id') || '' } catch { }
    const j = loadRT()
    const t = j.topics.find((x) => x.id === id)
    return t ? Response.json({ ok: true, topic: t }) : Response.json({ ok: false, error: '找不到这个议题' })
  })

  clipRoute('/api/dsh-media/roundtable/open', ['POST'], async (req) => {
    let body = {}
    try { body = await req.json() } catch { }
    const question = String(body.question || '').trim()
    if (!question) return Response.json({ ok: false, error: '缺少议题' })
    const all = loadPersonas()
    let ids = Array.isArray(body.personaIds) && body.personaIds.length ? body.personaIds : all.slice(0, 6).map((x) => x.id)
    const picked = ids.map((i) => all.find((x) => x.id === i)).filter(Boolean).slice(0, 8)
    const found = await queryWb(['search', question, '8'])
    const atoms = (found && found.ok && Array.isArray(found.list)) ? found.list : []
    const answers = await Promise.all(picked.map(async (p) => {
      try {
        let acc = ''
        for await (const t of streamTextWith(ctx, { prompt: roundPrompt(p, question, 1, '', atoms), maxTokens: 1100, system: '你们在开圆桌会议。只讲你这一角度的看法。' })) acc += t
        return { id: p.id, name: p.name, title: p.title, text: acc.trim() }
      } catch (e) { return { id: p.id, name: p.name, title: p.title, text: '', error: String(e?.message ?? e) } }
    }))
    const j = loadRT()
    const topic = {
      id: 'rt' + Date.now().toString(36), question,
      createdAt: new Date().toISOString().slice(0, 19).replace('T', ' '),
      rounds: [{ round: 1, answers }], followups: [],
      sources: atoms.slice(0, 6).map((a) => ({ id: a.id, knowledge: String(a.knowledge || '').slice(0, 80) })),
    }
    j.topics.push(topic)
    saveRT(j)
    return Response.json({ ok: true, topic })
  })

  clipRoute('/api/dsh-media/roundtable/next', ['POST'], async (req) => {
    let body = {}
    try { body = await req.json() } catch { }
    const j = loadRT()
    const t = j.topics.find((x) => x.id === String(body.id || ''))
    if (!t) return Response.json({ ok: false, error: '找不到这个议题' })
    const last = (t.rounds || [])[t.rounds.length - 1]
    if (!last) return Response.json({ ok: false, error: '还没有上一轮' })
    const all = loadPersonas()   // 每一轮全员举手，不只是上一轮说过话的人
    const found = await queryWb(['search', t.question, '8'])
    const atoms = (found && found.ok && Array.isArray(found.list)) ? found.list : []
    const round = t.rounds.length + 1
    const out = await Promise.all(all.map(async (p) => {
      const others = last.answers.filter((x) => x.id !== p.id)
        .map((x) => `${x.name}：${String(x.text || '').slice(0, 220)}`).join('\n')
      try {
        let acc = ''
        for await (const c of streamTextWith(ctx, { prompt: roundPrompt(p, t.question, round, others, atoms), maxTokens: 1100, system: '你们在开圆桌会议。允许直接反驳别人；没有新观点时可以只回 PASS 表示这轮不发言。' })) acc += c
        const text = acc.trim()
        if (/^PASS\b/i.test(text) || (text.length <= 12 && /PASS/i.test(text))) {
          return { id: p.id, name: p.name, title: p.title, silent: true }
        }
        return { id: p.id, name: p.name, title: p.title, text }
      } catch (e) { return { id: p.id, name: p.name, title: p.title, text: '', error: String(e?.message ?? e) } }
    }))
    const answers = out.filter((x) => !x.silent)
    const silent = out.filter((x) => x.silent).map((x) => x.name)
    t.rounds.push({ round, answers, silent })
    saveRT(j)
    return Response.json({ ok: true, topic: t })
  })

  clipRoute('/api/dsh-media/roundtable/ask', ['POST'], async (req) => {
    let body = {}
    try { body = await req.json() } catch { }
    const j = loadRT()
    const t = j.topics.find((x) => x.id === String(body.id || ''))
    if (!t) return Response.json({ ok: false, error: '找不到这个议题' })
    const question = String(body.question || '').trim()
    if (!question) return Response.json({ ok: false, error: '缺少问题' })
    const p = loadPersonas().find((x) => x.id === String(body.personaId || ''))
    if (!p) return Response.json({ ok: false, error: '找不到这个角色' })
    const found = await queryWb(['search', question + ' ' + t.question, '6'])
    const atoms = (found && found.ok && Array.isArray(found.list)) ? found.list : []
    const history = (body.history || []).slice(-6).map((h) => `${h.role === 'user' ? '用户' : p.name}：${String(h.text || '').slice(0, 200)}`).join('\n')
    const prompt = `议题：${t.question}

${history ? '你们刚才的对话：\n' + history + '\n\n' : ''}库内相关素材：
${(atoms || []).map((a, i) => `[${i + 1}] ${String(a.knowledge || '').slice(0, 100)}`).join('\n') || '（无）'}

你是「${p.name}」，${p.title}。关注点：${p.focus}；框架：${p.frame}；腔调：${p.voice}；反对：${p.against}

用户追问：${question}

直接回答，可以展开细说。长度按需要，别凑字数也别自我压缩。不要分点。
格式：第一行只写一个用【】包住的标题（不超过 16 字），第二行开始正文。
正文里用两个星号把**最核心的短句或关键词**包起来（一到三处）。`
    try {
      let acc = ''
      for await (const c of streamTextWith(ctx, { prompt, maxTokens: 1200, system: '你在圆桌会议上被单独追问，直接回答，允许展开。' })) acc += c
      const text = acc.trim()
      t.followups = t.followups || []
      t.followups.push({ personaId: p.id, name: p.name, question, answer: text, round: (t.rounds || []).length, sent: (body.sent === 0 || body.sent) ? Number(body.sent) : null, at: new Date().toISOString().slice(0, 19).replace('T', ' ') })
      saveRT(j)
      return Response.json({ ok: true, name: p.name, answer: text, round: (t.rounds || []).length, sent: (body.sent === 0 || body.sent) ? Number(body.sent) : null })
    } catch (e) {
      return Response.json({ ok: false, error: String(e?.message ?? e) })
    }
  })

  // 圆桌：导出 Markdown（写到 E:\\desktop\\media\\exports 并打开文件夹）
  clipRoute('/api/dsh-media/roundtable/export', ['POST'], async (req) => {
    let body = {}
    try { body = await req.json() } catch { }
    const j = loadRT()
    const t = j.topics.find((x) => x.id === String(body.id || ''))
    if (!t) return Response.json({ ok: false, error: '找不到这个议题' })

    const lines = []
    lines.push('# 圆桌会议 · ' + t.question)
    lines.push('')
    lines.push(`> ${t.createdAt} · ${(t.rounds || []).length} 轮 · ${((t.rounds || [])[0] || {}).answers ? t.rounds[0].answers.length : 0} 位顾问`)
    lines.push('')
    for (const rd of (t.rounds || [])) {
      lines.push('## 第 ' + rd.round + ' 轮' + (rd.round === 1 ? '（各自表态）' : '（互相回应）'))
      lines.push('')
      for (const a of (rd.answers || [])) {
        lines.push('### ' + a.name + ' · ' + a.title)
        lines.push('')
        lines.push(a.error ? '（失败：' + a.error + '）' : a.text)
        lines.push('')
      }
    }
    if ((t.followups || []).length) {
      lines.push('## 追问')
      lines.push('')
      for (const f of t.followups) {
        lines.push('**问 ' + f.name + '：** ' + f.question)
        lines.push('')
        lines.push('**' + f.name + '：** ' + f.answer)
        lines.push('')
      }
    }
    const md = lines.join('\n')
    try {
      const dir = dataPath('media', 'exports')
      fs.mkdirSync(dir, { recursive: true })
      const safe = String(t.question).replace(/[\\/:*?"<>|\s]+/g, '_').slice(0, 40)
      const file = path.join(dir, '圆桌_' + t.createdAt.replace(/[: ]/g, '-') + '_' + safe + '.md')
      fs.writeFileSync(file, md, 'utf8')
      if (body.open !== false) { try { spawn('explorer', ['/select,', file], { detached: true }) } catch { } }
      return Response.json({ ok: true, path: file, bytes: Buffer.byteLength(md, 'utf8') })
    } catch (e) {
      return Response.json({ ok: false, error: String(e?.message ?? e) })
    }
  })

  // 圆桌：批量导出多场（一个 Markdown 文件）
  clipRoute('/api/dsh-media/roundtable/export-many', ['POST'], async (req) => {
    let body = {}
    try { body = await req.json() } catch { }
    const ids = Array.isArray(body.ids) ? body.ids.map(String) : []
    const j = loadRT()
    const picked = ids.length ? j.topics.filter((t) => ids.includes(t.id)) : j.topics
    if (!picked.length) return Response.json({ ok: false, error: '没有可导出的记录' })
    const parts = []
    parts.push('# 圆桌会议合集')
    parts.push('')
    parts.push('> 共 ' + picked.length + ' 场 · 导出于 ' + new Date().toISOString().slice(0, 16).replace('T', ' '))
    parts.push('')
    for (const t of picked) {
      parts.push('---')
      parts.push('')
      parts.push('## ' + t.question)
      parts.push('')
      parts.push(`> ${t.createdAt} · ${(t.rounds || []).length} 轮`)
      parts.push('')
      for (const rd of (t.rounds || [])) {
        parts.push('### 第 ' + rd.round + ' 轮' + (rd.round === 1 ? '（各自表态）' : '（互相回应）'))
        parts.push('')
        for (const a of (rd.answers || [])) {
          parts.push('#### ' + a.name + ' · ' + a.title)
          parts.push('')
          parts.push(a.error ? '（失败：' + a.error + '）' : a.text)
          parts.push('')
        }
      }
      if ((t.followups || []).length) {
        parts.push('### 追问')
        parts.push('')
        for (const f of t.followups) {
          parts.push('**问 ' + f.name + '：** ' + f.question)
          parts.push('')
          parts.push('**' + f.name + '：** ' + f.answer)
          parts.push('')
        }
      }
    }
    const md = parts.join('\n')
    try {
      const dir = dataPath('media', 'exports')
      fs.mkdirSync(dir, { recursive: true })
      const stamp = new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-')
      const file = path.join(dir, '圆桌合集_' + stamp + '_' + picked.length + '场.md')
      fs.writeFileSync(file, md, 'utf8')
      if (body.open !== false) { try { spawn('explorer', ['/select,', file], { detached: true }) } catch { } }
      return Response.json({ ok: true, path: file, count: picked.length, bytes: Buffer.byteLength(md, 'utf8') })
    } catch (e) {
      return Response.json({ ok: false, error: String(e?.message ?? e) })
    }
  })

  // 取消一条采集（排队中或正在转写）
  clipRoute('/api/dsh-media/capture/cancel', ['POST'], async (req) => {
    let body = {}
    try { body = await req.json() } catch { }
    const url = String(body.url || '')
    const at = Number(body.at || 0)
    const job = capQueue.find((x) => (url ? x.url === url : x.at === at))
    if (!job) return Response.json({ ok: false, error: '队列里没有这一条' })
    if (job.status === 'done') return Response.json({ ok: false, error: '已经转写完了，删不掉' })
    if (job.status === 'running') {
      const pid = capChild && capChild.pid
      job.status = 'cancelled'
      if (pid) {
        try {
          spawn('taskkill', ['/PID', String(pid), '/T', '/F'], { windowsHide: true })
        } catch { try { capChild && capChild.kill('SIGKILL') } catch { } }
      }
    } else {
      job.status = 'cancelled'
    }
    return Response.json({ ok: true, status: job.status })
  })

  // 失败的链接：一键重试
  clipRoute('/api/dsh-media/capture/retry', ['POST'], async (req) => {
    let body = {}
    try { body = await req.json() } catch { }
    return Response.json(capRetry(body))
  })

  // 打开文件夹（只允许直播录制 / 逐字稿 / 书库三个根目录）
  // 已经开着同一个文件夹就把它调到最前，不重复开窗
  clipRoute('/api/dsh-media/open', ['POST'], async (req) => {
    let body = {}
    try { body = await req.json() } catch { }
    const map = { rec: LIVE_ROOT, transcript: LIVE_TR_ROOT, book: dataPath('wengao') }
    const p = map[String(body.which || '')]
    if (!p) return Response.json({ ok: false, error: 'unknown target' })
    let ps1 = ''
    try { ps1 = fileURLToPath(new URL('./open-folder.ps1', import.meta.url)) } catch { }
    if (!ps1 || !fs.existsSync(ps1)) {
      // 脚本丢了就退回最朴素的打开方式
      try {
        const child = spawn('explorer.exe', [p], { detached: true, windowsHide: true })
        if (child.unref) child.unref()
      } catch { }
      return Response.json({ ok: true, path: p, action: 'opened(no-script)' })
    }
    const r = await new Promise((resolve) => {
      let out = ''
      let child
      try {
        child = spawn('powershell.exe',
          ['-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', ps1, '-Path', p],
          { windowsHide: true })
      } catch (e) {
        resolve({ ok: false, error: String(e?.message ?? e) })
        return
      }
      child.stdout?.on('data', (d) => { out += String(d) })
      child.stderr?.on('data', (d) => { out += String(d) })
      child.on('error', (e) => resolve({ ok: false, error: String(e?.message ?? e) }))
      child.on('close', () => resolve({ ok: true, action: out.trim() }))
    })
    if (!r.ok) return Response.json({ ok: false, error: r.error })
    return Response.json({ ok: true, path: p, action: r.action })
  })

  // 书库 OCR：状态 / 扫描新书
  clipRoute('/api/dsh-media/ocr/status', ['GET'], async () => Response.json(await runPyJson(OCR_STATUS)))
  clipRoute('/api/dsh-media/ocr/scan', ['POST'], async () => Response.json(await runPyJson(OCR_STATUS, ['--scan'])))

  // 模型选择（整个工作台共用）
  clipRoute('/api/dsh-media/models', ['GET'], async () => {
    const list = listModels(ctx)
    let cur = null
    try { cur = currentRoute(ctx) } catch { }
    const saved = readSettings().model || null
    return Response.json({ ok: true, current: cur, saved, list })
  })

  clipRoute('/api/dsh-media/models/select', ['POST'], async (req) => {
    let body = {}
    try { body = await req.json() } catch { }
    const st = readSettings()
    if (!body.provider || !body.model) { delete st.model; writeSettings(st); return Response.json({ ok: true, saved: null }) }
    st.model = { provider: String(body.provider), model: String(body.model) }
    writeSettings(st)
    return Response.json({ ok: true, saved: st.model })
  })

  // 圆桌：删除记录（永久删除，前端二次确认）
  clipRoute('/api/dsh-media/roundtable/delete', ['POST'], async (req) => {
    let body = {}
    try { body = await req.json() } catch { }
    const ids = Array.isArray(body.ids) ? body.ids.map(String) : []
    if (!ids.length) return Response.json({ ok: false, error: '没有选中要删的记录' })
    const j = loadRT()
    const before = j.topics.length
    j.topics = j.topics.filter((t) => !ids.includes(t.id))
    saveRT(j)
    return Response.json({ ok: true, removed: before - j.topics.length, left: j.topics.length })
  })

  /* ==================================================================
   * 选题池 / 我的观点 / 我的语料库
   * 数据层：pool_db.py（pool_topics 与 my_views 两张表，和稿库物理隔离）
   * ================================================================== */
  const POOL_DB = pyPath('media', 'pool_db.py')
  const POOL_DIMS = ['普世性', '数字冲击', '反常识', '可操作', '痛点强度', '时效性', '争议空间', '经验可挂', '能落到动作', '标题性']

  /* 带 stdin 的 python 调用（写数据用） */
  function runPyJsonIn(script, args, body, timeoutMs = 120000) {
    return new Promise((resolve) => {
      let child
      try {
        child = spawn(PY, [script, ...args], {
          windowsHide: true,
          env: { ...process.env, PYTHONIOENCODING: 'utf-8' },
        })
      } catch (e) { return resolve({ ok: false, error: String(e?.message ?? e) }) }
      let out = ''
      let err = ''
      let done = false
      const finish = (v) => { if (done) return; done = true; clearTimeout(timer); resolve(v) }
      const timer = setTimeout(() => {
        try { child.kill() } catch { }
        finish({ ok: false, error: 'pool_db 超时' })
      }, timeoutMs)
      child.stdout.setEncoding('utf8')
      child.stderr.setEncoding('utf8')
      child.stdout.on('data', (d) => { out += d })
      child.stderr.on('data', (d) => { err += d })
      child.on('error', (e) => finish({ ok: false, error: String(e?.message ?? e) }))
      child.on('close', () => {
        const line = (out || '').trim().split('\n').pop() || '{}'
        try { finish(JSON.parse(line)) } catch { finish({ ok: false, error: (err || out || 'parse fail').slice(-300) }) }
      })
      try {
        if (body !== undefined && body !== null) child.stdin.write(JSON.stringify(body))
        child.stdin.end()
      } catch { }
    })
  }

  const poolPy = (args) => runPyJson(POOL_DB, args)
  const poolPyIn = (args, body) => runPyJsonIn(POOL_DB, args, body)

  // 建表（幂等），不阻塞启动
  poolPy(['init']).catch(() => { })

  // 八大板块，和书库/稿库的分类体系同源（post_labels.topic / book_labels.topic）
  const BOARDS = ['商业与变现', '内容创作', 'AI 与工具', '心理与人性', '语言与思维', '国学与哲学', '身心与生活', '权谋与政治']
  const POOL_MIN_SCORE = 75          // 低于这个分：不落库、不上屏（用户 2026-11-07 定的）

  function buildPoolSystem(board, want) {
    return `你是内容策划，服务对象是一个做知识类内容的自媒体博主。这一轮你只负责一个板块：${board}。
下面素材全部取自他库里「${board}」这一类的书和他的推文。

产出目标：${want} 条「今天就能开写」的选题，不是选题方向，不是方法论条目。

标题硬规范（不合格的直接别给，宁可少给）：
- 一眼看懂：看完标题就知道这句话在说什么，不用猜、不用回头看第二遍。看不懂的标题，标题性这一维直接给 0-3 分
- 句子里要有具体的东西：一个具体场景、一个具体后果、一组对比，或者一个数字
- 数字不是必选项。十条里带百分比/倍数的不要超过 3 条——全在堆 99%、90%、50% 会显得机械化
- 15-26 字，一句话念完，像人话，不像 PPT 目录
- 可以狠、可以反常识、可以直接得罪人，但不要喊口号、不要鸡汤
- 禁止这些开头：为什么你 / 你总是 / 别再迷信 / 如何 / 关于什么什么的思考 / 我们要怎么做
- 反面（这种别给）：别再迷信周末补觉，它可能是你失眠的元凶 / 如何绕过意志力陷阱，真正改变一个旧习惯
- 正面（这种才对）：发1000条烂视频，比憋10条精品更有用 / 客户问价你先报高三成，成交率反而更高

事实红线（违反就是废稿）：
- 每条选题必须能追到素材里的具体句子。素材里没有的事，一个字都不许写
- 战报类内容（涨粉多少、曝光多少、收入多少、几天做到多少）只有在素材原文里明确出现过才可以用，并且 why 里要引用那句原话
- 一条选题只谈一个平台。抖音和小红书规则不同、打法不同，不许放进同一条选题，也不许做平台对比
- 不许替他想像经历、凑细节、补数字

每条还要给：
- angle：从哪一刀切进去，一句话，不许复述素材
- hook：开头第一句，要让人停下来
- source_kind / source_ref：取自素材标号
- dims：十维各 0-10 整数，键名固定：普世性、数字冲击、反常识、可操作、痛点强度、时效性、争议空间、经验可挂、能落到动作、标题性
  · 痛点强度 = 能不能戳到观众此刻正在难受的事，不是「这个话题重要」
  · 数字冲击 = 标题或论点里有没有让人一愣的数字、倍数、时间
  · 反常识 = 有没有推翻一个大家都默认的结论
  · 标题性 = 一眼看懂 + 有钩子。看不懂就是 0-3 分
- why：一句话说清凭什么值得写；如果是战报类，把素材里那句原话抄进来

自己先按这个尺子过滤，别把平庸的塞进来：
90 分 = 看到就想转发，或者立刻想反驳，且跟他本人强相关
75-85 = 值得写，能出一条有观点的视频
70 以下 = 正确但没劲，不要给

只输出 JSON 数组，不要 markdown 代码块，不要解释。`
  }

  function normDim(v) {
    const n = Math.round(Number(v))
    if (!Number.isFinite(n)) return 0
    return Math.max(0, Math.min(10, n))
  }

  function scoreOf(dims) {
    let s = 0
    for (const k of POOL_DIMS) s += normDim(dims ? dims[k] : 0)
    return s
  }

  function levelOf(score) {
    if (score >= 85) return 'A'
    if (score >= 70) return 'B'
    return 'C'
  }

  /* 生成一个板块：抽稿 → 模型出题 → 按 10 维重算分 → 低于阈值丢掉 → 落库 */
  // 锁按板块分（前端会并发跑几个板块）；没有板块时用 '_' 当键
  const poolBusySet = new Set()

  /* 跨板块查重：同一个意思换个说法也算重复（今天实跑踩到「发1000条烂视频」给了三次） */
  function bigrams(s) {
    const t = String(s || '').replace(/[\s，。！？、：；""''（）()《》\-—·,.!?:;"']/g, '')
    const out = new Set()
    for (let i = 0; i < t.length - 1; i++) out.add(t.slice(i, i + 2))
    return out
  }

  function jaccard(a, b) {
    if (!a.size || !b.size) return 0
    let inter = 0
    for (const x of a) if (b.has(x)) inter += 1
    return inter / (a.size + b.size - inter)
  }

  /* 和已有标题重复：字面重合度高，或者短标题几乎被长标题包住（实测 A/B 只有 0.43 的 jaccard） */
  function isDupTitle(g, pool) {
    for (const x of pool) {
      if (jaccard(g, x) > 0.45) return true
      let inter = 0
      for (const t of g) if (x.has(t)) inter += 1
      if (inter / Math.min(g.size, x.size) > 0.6) return true
    }
    return false
  }

  async function genBoard(ctx, board, want, min) {
    const pickArgs = ['pick', '--n', String(want * 2)]
    if (board) pickArgs.push('--board', board)
    const pick = await poolPy(pickArgs)
    if (!pick || !pick.ok) return { ok: false, board, error: '抽素材失败：' + ((pick && pick.error) || '未知') }
    const items = pick.items || []
    if (!items.length) return { ok: false, board, error: '这个板块库里没抽到素材' }

    // 今天已经出过的选题，一起丢给模型，别换个说法再来一遍
    const day = localDate()
    const todayList = await poolPy(['list', '--day', day, '--limit', '300'])
    const exist = ((todayList && todayList.topics) || []).map((t) => String(t.title || '')).filter(Boolean)
    const existGrams = exist.map(bigrams)
    const existBlock = exist.length
      ? `\n\n今天已经出过这些选题，不要换个说法再给一遍（同意思、同角度都算重复）：\n` + exist.slice(0, 60).map((t) => '- ' + t).join('\n')
      : ''

    const payload = items
      .map((x, i) => `#${i + 1} [${x.kind}:${x.ref}] ${x.title}\n${x.text}`)
      .join('\n\n')
    const prompt = `素材（每条都带 kind:ref，出选题时 source_kind / source_ref 从这里取）：\n\n${payload}${existBlock}\n\n请给 ${want} 条选题。`
    const raw = await completeTextWith(ctx, { system: buildPoolSystem(board || '全部', want), prompt, maxTokens: 6000 })
    const arr = parseLooseJson(raw)
    if (!Array.isArray(arr)) return { ok: false, board, error: '模型输出不是数组', raw: String(raw).slice(0, 300) }

    const list = []
    let low = 0
    let dup = 0
    for (const it of arr) {
      const title = String(it && it.title ? it.title : '').trim()
      if (!title) continue
      const dims = {}
      for (const k of POOL_DIMS) dims[k] = normDim(it.dims ? it.dims[k] : 0)
      const score = scoreOf(dims)
      if (score < min) { low += 1; continue }
      const g = bigrams(title)
      if (isDupTitle(g, existGrams)) { dup += 1; continue }
      list.push({
        board: board || '',
        title: title.slice(0, 80),
        angle: String(it.angle || '').slice(0, 400),
        hook: String(it.hook || '').slice(0, 200),
        source_kind: String(it.source_kind || '').slice(0, 12),
        source_ref: String(it.source_ref || '').slice(0, 64),
        source_title: String(it.source_title || '').slice(0, 120),
        dims,
        score,
        level: levelOf(score),
        why: String(it.why || '').slice(0, 300),
      })
    }
    if (!list.length) {
      return {
        ok: true, board, added: 0, skipped: 0, lowDropped: low, dupDropped: dup, topics: [],
        note: '这批没有到 ' + min + ' 分的' + (dup ? '，另有 ' + dup + ' 条跟今天已有的重复' : ''),
      }
    }

    const imp = await poolPyIn(['import'], list)
    if (!imp || !imp.ok) return { ok: false, board, error: '写库失败：' + ((imp && imp.error) || '未知') }
    return { ok: true, board, added: imp.added, skipped: imp.skipped, lowDropped: low, dupDropped: dup }
  }

  clipRoute('/api/dsh-media/pool/stats', ['GET'], async () => Response.json(await poolPy(['stats'])))

  clipRoute('/api/dsh-media/pool/boards', ['GET'], async () => {
    const j = await poolPy(['boards'])
    const got = {}
    for (const b of (j && j.boards) || []) got[b.board] = b.n
    return Response.json({
      ok: true,
      min: POOL_MIN_SCORE,
      boards: BOARDS.map((b) => ({ board: b, n: got[b] || 0 })),
    })
  })

  clipRoute('/api/dsh-media/pool/list', ['GET'], async (req) => {
    const u = new URL(req.url, 'http://x')
    const args = ['list', '--limit', String(Math.min(300, Number(u.searchParams.get('limit')) || 120))]
    const day = u.searchParams.get('day')
    const status = u.searchParams.get('status')
    const board = u.searchParams.get('board')
    if (day) args.push('--day', day)
    if (status) args.push('--status', status)
    if (board) args.push('--board', board)
    return Response.json(await poolPy(args))
  })

  clipRoute('/api/dsh-media/pool/gen', ['POST'], async (req) => {
    let body = {}
    try { body = await req.json() } catch { }
    const board = String(body.board || '').trim()
    const lockKey = board || '_'
    if (poolBusySet.has(lockKey)) return Response.json({ ok: false, running: true, board, error: '这个板块上一轮还在生成' })
    poolBusySet.add(lockKey)
    try {
      const want = Math.max(3, Math.min(15, Number(body.n) || 10))
      const min = Number.isFinite(Number(body.min)) ? Number(body.min) : POOL_MIN_SCORE
      const r = await genBoard(ctx, board, want, min)
      if (!r.ok) return Response.json(r)
      const fresh = await poolPy(['list', '--limit', '300'])
      return Response.json({
        ...r,
        total: fresh && fresh.total ? fresh.total : 0,
        topics: (fresh && fresh.topics) || [],
      })
    } catch (e) {
      return Response.json({ ok: false, board, error: String(e?.message ?? e).slice(-300) })
    } finally {
      poolBusySet.delete(lockKey)
    }
  })

  /* 把一条选题写成稿：先取原始素材，再让模型写口播稿（他没读过原文，得先有东西能读） */
  const DRAFT_SYSTEM = `你要替一个做知识类内容的自媒体博主，把一条选题写成可以直接开拍的口播稿。

铁律：
- 只用【原始素材】里的事实和观点。素材里没有的数字、案例、经历，一个都不许加。
- 素材不足以支撑这条选题，就直说「素材不够，这条写不了」并说明缺什么，不要硬写。
- 用大白话，第一人称，像在跟同行的朋友讲话。
- 不要「值得注意的是」「意义重大」这类空话，不要「点赞关注」结尾。

结构：
1. 开头第一句就是钩子，直接砸出去
2. 讲清这件事到底是什么（博主本人没读过原始素材，背景要交代清楚）
3. 为什么是这样：机制、因果
4. 一个具体例子，只能来自素材
5. 落到动作：听完能做什么

长度 700-1100 字。只输出稿子本身，不要标题、不要解释、不要 markdown。`

  clipRoute('/api/dsh-media/pool/draft', ['POST'], async (req) => {
    let body = {}
    try { body = await req.json() } catch { }
    const id = String(body.id || '')
    if (!id) return Response.json({ ok: false, error: '缺少选题 id' })
    const got = await poolPy(['get', '--id', id])
    if (!got || !got.ok) return Response.json({ ok: false, error: '找不到这条选题' })
    const t = got.topic || {}
    if (t.draft && !body.rewrite) {
      return Response.json({ ok: true, cached: true, text: t.draft.text || '', source: t.draft.source || null })
    }
    const src = await poolPy(['src', '--kind', String(t.source_kind || ''), '--ref', String(t.source_ref || '')])
    if (!src || !src.ok) return Response.json({ ok: false, error: '取不到原始素材：' + ((src && src.error) || '未知') })
    try {
      const prompt = `选题：${t.title || ''}
切入角度：${t.angle || ''}
开头钩子：${t.hook || ''}
来源：${src.title || ''} ${src.date || ''}

【原始素材】
${String(src.text || '').slice(0, 4000)}`
      const text = await completeTextWith(ctx, { system: DRAFT_SYSTEM, prompt, maxTokens: 2600 })
      const pack = {
        text: String(text || '').trim(),
        source: { kind: src.kind || '', title: src.title || '', date: src.date || '' },
        at: new Date().toISOString().slice(0, 19),
      }
      await poolPyIn(['setdraft', '--id', id], pack)
      return Response.json({ ok: true, text: pack.text, source: pack.source })
    } catch (e) {
      return Response.json({ ok: false, error: String(e?.message ?? e).slice(-300) })
    }
  })

  /* 流式版：边写边推给界面，让他看着 AI 是怎么写这篇的（不是等 1 分钟蹦出一整篇） */
  clipRoute('/api/dsh-media/pool/draft/stream', ['POST'], async (req) => {
    let body = {}
    try { body = await req.json() } catch { }
    const id = String(body.id || '')
    if (!id) return Response.json({ ok: false, error: '缺少选题 id' })
    const got = await poolPy(['get', '--id', id])
    if (!got || !got.ok) return Response.json({ ok: false, error: '找不到这条选题' })
    const t = got.topic || {}
    const src = await poolPy(['src', '--kind', String(t.source_kind || ''), '--ref', String(t.source_ref || '')])
    if (!src || !src.ok) return Response.json({ ok: false, error: '取不到原始素材：' + ((src && src.error) || '未知') })
    const prompt = `选题：${t.title || ''}
切入角度：${t.angle || ''}
开头钩子：${t.hook || ''}
来源：${src.title || ''} ${src.date || ''}

【原始素材】
${String(src.text || '').slice(0, 4000)}`
    return streamResponse(async (signal) => {
      async function* run() {
        let acc = ''
        for await (const chunk of streamTextWith(ctx, { system: DRAFT_SYSTEM, prompt, maxTokens: 2600 }, signal)) {
          acc += chunk
          yield chunk
        }
        try {
          await poolPyIn(['setdraft', '--id', id], {
            text: acc.trim(),
            source: { kind: src.kind || '', title: src.title || '', date: src.date || '' },
            at: new Date().toISOString().slice(0, 19),
          })
        } catch { }
      }
      return run()
    })
  })

  clipRoute('/api/dsh-media/pool/status', ['POST'], async (req) => {
    let body = {}
    try { body = await req.json() } catch { }
    const id = String(body.id || '')
    const status = String(body.status || '')
    if (!id) return Response.json({ ok: false, error: '缺少选题 id' })
    return Response.json(await poolPy(['setstatus', '--id', id, '--status', status]))
  })

  clipRoute('/api/dsh-media/pool/del', ['POST'], async (req) => {
    let body = {}
    try { body = await req.json() } catch { }
    const ids = Array.isArray(body.ids) ? body.ids.map(String) : []
    if (!ids.length) return Response.json({ ok: false, error: '没选要删的' })
    return Response.json(await poolPy(['del', '--ids', ids.join(',')]))
  })

  /* ---------------- 我的观点 / 我的语料库 ---------------- */

  const VIEW_SYSTEM = `你是严格的写作教练。用户会给你一段他自己写的观点，你要评它，不是改它。

铁律：
- 一个字都不许改他的原文，也不许给"改写版本""示范段落"。给了就是违约。
- 你只指出：哪里立得住、哪里是空话、哪里缺证据、哪个反问能把人问住。
- 用大白话，不用"值得注意的是""意义重大"。

严格只输出 JSON，不要 markdown，不要解释。格式：
{
  "score": 0-100 的整数（这段能不能当视频论点直接输出）,
  "verdict": "能立住" 或 "半立住" 或 "立不住",
  "pros": ["最多 3 条，具体到句子"],
  "gaps": ["最多 3 条，说清缺什么：缺例子/缺数字/缺因果/是结论不是判断"],
  "questions": ["最多 3 条能把这个观点问深的问句"],
  "one_line": "一句话总评，30 字以内"
}`

  clipRoute('/api/dsh-media/views/list', ['GET'], async (req) => {
    const u = new URL(req.url, 'http://x')
    const args = ['views_list', '--limit', String(Math.min(200, Number(u.searchParams.get('limit')) || 50))]
    const q = u.searchParams.get('q')
    if (q) args.push('--q', q)
    return Response.json(await poolPy(args))
  })

  clipRoute('/api/dsh-media/views/get', ['GET'], async (req) => {
    const u = new URL(req.url, 'http://x')
    const id = u.searchParams.get('id')
    if (!id) return Response.json({ ok: false, error: '缺少 id' })
    return Response.json(await poolPy(['views_get', '--id', id]))
  })

  // 保存原文：一字不动落库，然后立刻返回 id（评审另开一步）
  clipRoute('/api/dsh-media/views/save', ['POST'], async (req) => {
    let body = {}
    try { body = await req.json() } catch { }
    const content = String(body.content || '')
    if (!content.trim()) return Response.json({ ok: false, error: '内容是空的，写点再提交' })
    return Response.json(await poolPyIn(['views_save'], {
      id: body.id || '',
      kind: body.kind || 'free',
      topicId: body.topicId || '',
      title: body.title || '',
      tags: body.tags || '',
      content,
    }))
  })

  // AI 只评不改

  /* ---------------- 能力提升：七种训练（出题 → 你答 → AI 评） ---------------- */
  const TRAIN_CFG = {
    topic: {
      name: '话题即兴',
      sys: '你是口播教练。用户要在 60 秒内讲清对一个观点或话题的看法。你要评他的表达，不改写。',
      ask: '给一个能立刻开讲的话题或观点，一句话，20 字以内。只输出这一句，不要解释。',
      judge: '严格只输出 JSON：{"score":0-100,"good":["最多2条，具体到他说的哪句"],"fix":["最多2条，具体怎么改"],"one_line":"一句话总评，30字以内"}\n评的维度：有没有明确立场、有没有理由支撑、有没有具体例子、有没有说清。',
    },
    retell: {
      name: '限时复述',
      sys: '你是复述训练教练。用户看了 30 秒材料，然后合上复述要点。你要比对要点覆盖率。',
      ask: '给一段 150-250 字的中文材料（真实观点、有 3-5 个要点），只输出材料本身。',
      judge: '严格只输出 JSON：{"score":0-100,"kept":["他复述对的关键点"],"missed":["他漏掉的关键点"],"one_line":"一句话总评，30字以内"}\n分数按要点覆盖比例给，不夸大。',
    },
    debate: {
      name: '反方辩论',
      sys: '你是辩论教练。用户拿到一个立场，任务是站反方把它推翻。你要评他的论证。',
      ask: '给一个有争议但成立的立场，一句话，20 字以内。只输出这一句。',
      judge: '严格只输出 JSON：{"score":0-100,"good":["最多2条，哪一步论证真的有效"],"leaks":["最多2条，哪里被原立场反打"],"one_line":"一句话总评，30字以内"}\n评的维度：有没有正面回应原立场、有没有偷换概念、有没有只情绪不论证。',
    },
    title: {
      name: '标题训练',
      sys: '你是标题编辑。用户会拿到一篇稿，要写 5 个标题。你按点击欲和信息准确度打分。',
      ask: '给一段 200-300 字的中文稿（真实观点、有具体信息），只输出稿子本身。',
      judge: '严格只输出 JSON：{"score":0-100,"per_title":[{"t":"他的标题","s":0-100,"why":"一句评"}],"best":"最该用的那个","one_line":"一句话总评，30字以内"}\n标题超过 20 字要扣分；只喊口号不给信息的要扣分。',
    },
    summary: {
      name: '摘要压缩',
      sys: '你是编辑。用户要把 2000 字压成 100 字。你要比对要点保留率。',
      ask: '给一段 600-900 字的中文长文（有 4-6 个要点），只输出正文。',
      judge: '严格只输出 JSON：{"score":0-100,"kept":["保留住的核心要点"],"lost":["压掉的关键信息"],"one_line":"一句话总评，30字以内"}\n超过 120 字直接扣到 60 分以下。',
    },
    question: {
      name: '提问训练',
      sys: '你是提问教练。用户拿到一个话题，要列 10 个问题。你要判断哪些是真问题。',
      ask: '给一个适合深挖的话题，一句话，20 字以内。只输出这一句。',
      judge: '严格只输出 JSON：{"score":0-100,"real":["他提的真问题"],"fake":["假问题：能百度到的、绕圈子的、回答不了的"],"one_line":"一句话总评，30字以内"}\n真问题 = 能逼对方给出具体信息或取舍的问题。',
    },
    analogy: {
      name: '类比训练',
      sys: '你是表达教练。用户要把一个专业概念讲给完全外行的人听。你要评他的类比。',
      ask: '给一个专业概念（商业/技术/心理皆可），一句话。只输出这个概念名和一句解释。',
      judge: '严格只输出 JSON：{"score":0-100,"works":["类比里成立的部分"],"breaks":["类比失效的地方"],"one_line":"一句话总评，30字以内"}\n评的维度：外行能不能听懂、类比有没有失真、有没有偷懒用术语。',
    },
  }

  /* 表达训练：转发到口袋服务（同一套词库和 prompt，不写两份） */
  async function spProxy(path, body) {
    try {
      const r = await fetch('http://127.0.0.1:8788' + path, {
        method: body ? 'POST' : 'GET',
        headers: body ? { 'content-type': 'application/json' } : {},
        body: body ? JSON.stringify(body) : undefined,
      })
      return Response.json(await r.json())
    } catch (e) {
      return Response.json({ ok: false, error: '口袋服务没起来：' + String(e && e.message) })
    }
  }

  /* ---------- 训练 / 书卡 / 润色：转发到口袋服务 ---------- */
  clipRoute('/api/dsh-media/sp/fit/week', ['GET'], async () => spProxy('/api/train_week', null))

  clipRoute('/api/dsh-media/sp/fit/check', ['POST'], async (req) => {
    let body = {}
    try { body = await req.json() } catch { }
    return spProxy('/api/train_check', { item: String(body.item || ''), date: body.date || null })
  })

  clipRoute('/api/dsh-media/sp/fit/guide', ['GET'], async (req) => {
    const u = new URL(req.url)
    return spProxy('/api/ex_guide?n=' + encodeURIComponent(u.searchParams.get('n') || ''), null)
  })

  clipRoute('/api/dsh-media/sp/books', ['GET'], async (req) => {
    const u = new URL(req.url)
    const qs = new URLSearchParams()
    if (u.searchParams.get('verdict')) qs.set('verdict', u.searchParams.get('verdict'))
    qs.set('limit', u.searchParams.get('limit') || '80')
    return spProxy('/api/book_cards?' + qs.toString(), null)
  })

  clipRoute('/api/dsh-media/sp/polish', ['POST'], async (req) => {
    let body = {}
    try { body = await req.json() } catch { }
    return spProxy('/api/speech_polish', { text: String(body.text || '') })
  })

  clipRoute('/api/dsh-media/sp/toview', ['POST'], async (req) => {
    let body = {}
    try { body = await req.json() } catch { }
    return spProxy('/api/speech_toview', { text: String(body.text || ''), title: body.title || '' })
  })

  clipRoute('/api/dsh-media/sp/analyze', ['POST'], async (req) => {
    let body = {}
    try { body = await req.json() } catch { }
    return spProxy('/api/speech_analyze', { text: String(body.text || '') })
  })

  clipRoute('/api/dsh-media/sp/settings', ['GET'], async () => spProxy('/api/speech_settings', null))

  clipRoute('/api/dsh-media/sp/settings/save', ['POST'], async (req) => {
    let body = {}
    try { body = await req.json() } catch { }
    return spProxy('/api/speech_settings_save', body)
  })

  clipRoute('/api/dsh-media/sp/tip', ['POST'], async (req) => {
    let body = {}
    try { body = await req.json() } catch { }
    return spProxy('/api/speech_tip', { text: String(body.text || '') })
  })

  clipRoute('/api/dsh-media/sp/report', ['POST'], async (req) => {
    let body = {}
    try { body = await req.json() } catch { }
    return spProxy('/api/speech_report', body)
  })

  clipRoute('/api/dsh-media/train/prompt', ['POST'], async (req) => {
    let body = {}
    try { body = await req.json() } catch { }
    const cfg = TRAIN_CFG[String(body.kind || '')]
    if (!cfg) return Response.json({ ok: false, error: '没有这个训练' })
    try {
      const text = await completeTextWith(ctx, {
        system: '你是训练出题助手，只输出题目本身，不要任何解释和前后缀。',
        prompt: cfg.ask, maxTokens: 800,
      })
      return Response.json({ ok: true, task: String(text || '').trim(), name: cfg.name })
    } catch (e) {
      return Response.json({ ok: false, error: '出不了题：' + String(e?.message ?? e) })
    }
  })

  clipRoute('/api/dsh-media/train/judge', ['POST'], async (req) => {
    let body = {}
    try { body = await req.json() } catch { }
    const cfg = TRAIN_CFG[String(body.kind || '')]
    if (!cfg) return Response.json({ ok: false, error: '没有这个训练' })
    const answer = String(body.answer || '').trim()
    if (answer.length < 10) return Response.json({ ok: false, error: '太短了，多写几句' })
    try {
      const prompt = `【题目】\n${String(body.task || '').slice(0, 1500)}\n\n【他的回答】\n${answer.slice(0, 3000)}\n\n${cfg.judge}`
      const raw = await completeTextWith(ctx, { system: cfg.sys, prompt, maxTokens: 1600 })
      const obj = parseLooseJsonObj(raw)
      if (!obj) return Response.json({ ok: false, error: '评语读不出来' })
      return Response.json({ ok: true, result: obj, name: cfg.name })
    } catch (e) {
      return Response.json({ ok: false, error: '评不了：' + String(e?.message ?? e) })
    }
  })

  clipRoute('/api/dsh-media/views/review', ['POST'], async (req) => {
    let body = {}
    try { body = await req.json() } catch { }
    const id = String(body.id || '')
    if (!id) return Response.json({ ok: false, error: '缺少 id' })
    const got = await poolPy(['views_get', '--id', id])
    if (!got || !got.ok) return Response.json({ ok: false, error: '读不到这条观点' })
    const content = String(got.view.content || '')
    if (!content.trim()) return Response.json({ ok: false, error: '原文是空的' })
    try {
      const prompt = `下面是我自己写的观点，请评它。原文一个字都不要改，也不要给我改写版。\n\n${content}`
      const raw = await completeTextWith(ctx, { system: VIEW_SYSTEM, prompt, maxTokens: 1600 })
      const obj = parseLooseJsonObj(raw)
      if (!obj) return Response.json({ ok: false, error: '模型输出读不出来', raw: String(raw).slice(0, 200) })
      const review = {
        score: Math.max(0, Math.min(100, Math.round(Number(obj.score) || 0))),
        verdict: String(obj.verdict || '').slice(0, 20),
        pros: Array.isArray(obj.pros) ? obj.pros.slice(0, 3).map((x) => String(x).slice(0, 200)) : [],
        gaps: Array.isArray(obj.gaps) ? obj.gaps.slice(0, 3).map((x) => String(x).slice(0, 200)) : [],
        questions: Array.isArray(obj.questions) ? obj.questions.slice(0, 3).map((x) => String(x).slice(0, 200)) : [],
        one_line: String(obj.one_line || '').slice(0, 80),
      }
      await poolPyIn(['views_review', '--id', id], review)
      return Response.json({ ok: true, id, review })
    } catch (e) {
      return Response.json({ ok: false, error: String(e?.message ?? e).slice(-300) })
    }
  })

  clipRoute('/api/dsh-media/views/del', ['POST'], async (req) => {
    let body = {}
    try { body = await req.json() } catch { }
    const ids = Array.isArray(body.ids) ? body.ids.map(String) : []
    if (!ids.length) return Response.json({ ok: false, error: '没选要删的' })
    return Response.json(await poolPy(['views_del', '--ids', ids.join(',')]))
  })

  /* ---------------- 我的灵感 ---------------- */

  clipRoute('/api/dsh-media/myideas/list', ['GET'], async (req) => {
    const u = new URL(req.url, 'http://x')
    const lim = String(Math.min(200, Number(u.searchParams.get('limit')) || 100))
    return Response.json(await poolPy(['ideas_list', '--limit', lim]))
  })

  clipRoute('/api/dsh-media/myideas/add', ['POST'], async (req) => {
    let body = {}
    try { body = await req.json() } catch { }
    const content = String(body.content || '').trim()
    if (!content) return Response.json({ ok: false, error: '写点东西再记' })
    return Response.json(await poolPyIn(['ideas_add'], {
      content,
      source: body.source || 'manual',
      tags: body.tags || '',
      note: body.note || '',
    }))
  })

  clipRoute('/api/dsh-media/myideas/del', ['POST'], async (req) => {
    let body = {}
    try { body = await req.json() } catch { }
    const ids = Array.isArray(body.ids) ? body.ids.map(String) : []
    if (!ids.length) return Response.json({ ok: false, error: '没选中' })
    return Response.json(await poolPy(['ideas_del', '--ids', ids.join(',')]))
  })

  // 灵感 → 观点：原话照搬，灵感本身标记 promoted 不丢
  clipRoute('/api/dsh-media/myideas/promote', ['POST'], async (req) => {
    let body = {}
    try { body = await req.json() } catch { }
    const id = String(body.id || '')
    if (!id) return Response.json({ ok: false, error: '缺少 id' })
    return Response.json(await poolPyIn(['ideas_promote', '--id', id], {
      title: body.title || '',
      content: body.content || '',
    }))
  })

  /* ---------------- 每日对撞 ---------------- */

  clipRoute('/api/dsh-media/clash/today', ['GET'], async (req) => {
    const u = new URL(req.url, 'http://x')
    const n = String(Math.min(5, Number(u.searchParams.get('n')) || 2))
    return Response.json(await poolPy(['clash_today', '--n', n]))
  })

  clipRoute('/api/dsh-media/clash/answer', ['POST'], async (req) => {
    let body = {}
    try { body = await req.json() } catch { }
    const ref = String(body.atomId || body.ref || '')
    if (!ref) return Response.json({ ok: false, error: '缺少观点 id' })
    return Response.json(await poolPy([
      'clash_answer', '--ref', ref,
      '--kind', String(body.verdict || 'unsure'),
      '--content', String(body.why || body.content || ''),
    ]))
  })

  // 手机端整页（独立 HTML，不依赖 DSH 前端框架）
  clipRoute('/api/dsh-media/mobile', ['GET'], async () => {
    try {
      const p = path.join(path.dirname(new URL(import.meta.url).pathname.replace(/^\//, '')), 'mobile.html.js')
      const html = (await import('file://' + p.replace(/\\/g, '/'))).default
      return new Response(html, { headers: { 'content-type': 'text/html; charset=utf-8' } })
    } catch (e) {
      return new Response('mobile 页面加载失败: ' + String(e && e.message), { status: 500, headers: { 'content-type': 'text/plain; charset=utf-8' } })
    }
  })

  // 观点库：平铺还没表过态的，不分类不分组
  clipRoute('/api/dsh-media/clash/list', ['GET'], async (req) => {
    const u = new URL(req.url, 'http://x')
    const args = ['clash_list', '--limit', String(Math.min(500, Number(u.searchParams.get('limit')) || 60))]
    const q = u.searchParams.get('q')
    if (q) args.push('--q', q)
    const k = u.searchParams.get('kind')
    if (k) args.push('--kind', k)
    return Response.json(await poolPy(args))
  })

  // 待补队列：表过态但还没写理由的
  clipRoute('/api/dsh-media/clash/pending', ['GET'], async () => {
    return Response.json(await poolPy(['clash_pending']))
  })

  /* ---------------- 每天自动刷新：8:00 之后缺哪个板块就补哪个 ---------------- */
  let poolAutoTimer = null
  let poolAutoBusy = false

  async function poolAutoTick() {
    if (poolAutoBusy || poolBusySet.size) return
    const h = new Date().getHours()
    if (h < 8 || h >= 23) return
    try {
      const j = await poolPy(['boards'])
      if (!j || !j.ok) return
      const got = {}
      for (const b of j.boards || []) got[b.board] = b.n
      const missing = BOARDS.filter((b) => (got[b] || 0) < 3)
      if (!missing.length) return
      poolAutoBusy = true
      ctx.logger?.info?.('dsh-media-workbench: 自动补板块 ' + missing[0])
      await genBoard(ctx, missing[0], 10, POOL_MIN_SCORE)
    } catch (e) {
      ctx.logger?.warn?.('dsh-media-workbench: 自动补板块失败', e)
    } finally {
      poolAutoBusy = false
    }
  }

  try {
    poolAutoTimer = setInterval(() => { poolAutoTick().catch(() => { }) }, 15 * 60 * 1000)
    setTimeout(() => { poolAutoTick().catch(() => { }) }, 3 * 60 * 1000)
  } catch { }

  ctx.logger?.info?.('dsh-media-workbench: 接口已注册 /api/dsh-media/*')

  // 启动每日自动任务：热点 + 灵感，缺当天数据就补
  try { startAuto(ctx) } catch (e) { ctx.logger?.warn?.('dsh-media-workbench: 自动任务启动失败', e) }

  return () => {
    try { stopAuto() } catch { }
    try { stopClipWatch() } catch { }
    try { if (poolAutoTimer) clearInterval(poolAutoTimer) } catch { }
    for (const d of disposers) { try { d?.() } catch {} }
  }
}
