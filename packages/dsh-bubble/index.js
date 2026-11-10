/**
 * dsh-bubble —— 宿主端
 *
 * 客户端只有一个球（UI），但要「每个对话框 AI 干完活都弹提示」，光靠浏览器端做不到：
 * 客户端只有 connection/reset、locale/change、slots/changed、theme/change 四个事件，
 * 没有任何对话相关事件。所以宿主端在这里监听 turn 结束，攒成队列，客户端定时来拉。
 *
 * 接口（★ 除 /events 外一律不带 /api/ 前缀：DSH 的 cookie guard 按前缀拦 /api/*，
 *        外部进程（Python 桌宠）没有 cookie，带 /api/ 一律 401）：
 *   GET  /dsh-bubble/status → { ok, running:[{id,title,ms}], runningCount, done:[...] }   给桌宠轮询
 *   POST /dsh-bubble/push   {"type","id","title","detail","pct","state"}                 外部任务上报
 *   GET  /api/dsh-bubble/events → { ok, events:[...] }                                   给浏览器客户端拉
 *
 * ★ 桌宠归插件管：DSH 加载本插件时 spawn 桌面球（dsh-pet.py），插件卸载/DSH 退出时杀掉。
 *   装这一个插件 = 网页里的球 + 桌面上的球，全都有；不需要计划任务，不需要手动启动。
 */

import { spawn } from 'node:child_process'
import { existsSync } from 'node:fs'

export const name = 'dsh-bubble'

// ★ 关键：不声明 inject，ctx.webServer 拿不到，注册全被 try/catch 吞掉 → 404
export const inject = ['webServer']

// 桌宠运行环境：找不到就静默跳过（网页内的球照常工作，不影响插件其它功能）
const PET_PY = process.env.DSH_PET_PY ||
  (process.env.LOCALAPPDATA || 'C:\\Users\\Public\\AppData\\Local') + '\\Programs\\Python\\Python312\\pythonw.exe'
const PET_SCRIPT = process.env.DSH_PET_SCRIPT || 'E:\\tools\\asr\\dsh-pet.py'

function startPet(ctx) {
  if (!existsSync(PET_PY) || !existsSync(PET_SCRIPT)) {
    ctx.logger?.info?.('dsh-bubble: 本机没有桌宠运行环境，跳过桌面球（网页内的球不受影响）')
    return null
  }
  try {
    const child = spawn(PET_PY, [PET_SCRIPT], {
      stdio: 'ignore',
      windowsHide: true,
      detached: false,
    })
    child.on('error', (e) => ctx.logger?.warn?.('dsh-bubble: 桌宠启动失败 ' + String(e?.message || e)))
    child.on('exit', (code) => ctx.logger?.info?.(`dsh-bubble: 桌宠进程退出 code=${code}`))
    ctx.logger?.info?.(`dsh-bubble: 桌宠已启动 pid=${child.pid}`)
    return child
  } catch (e) {
    ctx.logger?.warn?.('dsh-bubble: 桌宠 spawn 异常 ' + String(e?.message || e))
    return null
  }
}

// 只对「干了很久」的 turn 弹提示：短问答弹了会烦（用户可调）
const MIN_MS = 30000
const MAX_EVENTS = 50

function sendJson(res, code, body) {
  try {
    res.writeHead(code, { 'content-type': 'application/json; charset=utf-8' })
    res.end(JSON.stringify(body))
  } catch { }
}

export function apply(ctx) {
  const events = []
  const startedAt = new Map()
  // ★ 之前漏了这一行：agent/status 里 titles.set 直接抛 ReferenceError，
  //    被 catch 吞掉，导致 startedAt.set 永远不执行 → running 永远是空 → 金环不出现
  const titles = new Map()

  // 桌宠随插件起，插件走它也走
  const petChild = startPet(ctx)

  try {
    ctx.on('agent/status', (payload) => {
      try {
        const a = payload && payload.agent
        const id = a && (a.id || a.sessionId)
        if (!id) return
        try {
          const tt = (a && a.session && (a.session.title || a.session.name)) || ''
          if (tt) titles.set(id, String(tt))
        } catch { }
        if (payload.status === 'running') startedAt.set(id, Date.now())
        else if (payload.status === 'idle' || payload.status === 'stopped') startedAt.delete(id)
      } catch { }
    })
  } catch { }

  try {
    ctx.on('agent/turn-stopping', (payload) => {
      try {
        const a = payload && payload.agent
        const id = a && (a.id || a.sessionId)
        const t0 = id ? startedAt.get(id) : 0
        const ms = t0 ? Date.now() - t0 : 0
        if (id) startedAt.delete(id)
        if (ms < MIN_MS) return
        let title = ''
        try { title = (a && a.session && (a.session.title || a.session.name)) || '' } catch { }
        if (!title && id) title = titles.get(id) || ''
        events.push({ type: 'turn-end', at: Date.now(), ms, title: String(title || '') })
        if (events.length > MAX_EVENTS) events.splice(0, events.length - MAX_EVENTS)
      } catch { }
    })
  } catch { }

  // ★ 当前状态（给桌面宠物轮询）
  try {
    ctx.effect(() =>
      ctx.webServer.register({
        kind: 'exact',
        path: '/dsh-bubble/status',
        handler: async (req, res) => {
          const now = Date.now()
          const running = []
          for (const [id, t0] of startedAt.entries()) {
            running.push({ id, title: titles.get(id) || '', ms: now - t0 })
          }
          running.sort((a, b) => b.ms - a.ms)
          const done = events
            .filter((e) => e.type === 'turn-end')
            .slice(-8)
            .map((e) => ({ title: e.title || '', ms: e.ms || 0, at: e.at || 0 }))
          // 最近一条外部上报的任务状态（播客生成、批量提炼之类）
          const last = {}
          for (let i = events.length - 1; i >= 0 && Object.keys(last).length < 3; i--) {
            const e = events[i]
            if (e.type !== 'turn-end' && e.id) last[e.id] = e
          }
          sendJson(res, 200, {
            ok: true,
            running,
            runningCount: running.length,
            done,
            tasks: Object.values(last),
            at: now,
          })
        },
      }),
    )
    ctx.logger?.info?.('dsh-bubble: /dsh-bubble/status 已注册（桌面宠物读取）')
  } catch (e) {
    ctx.logger?.warn?.('dsh-bubble: /status 注册失败 ' + String(e?.message || e))
  }

  // 外部推任务状态（Python 脚本、命令行工具都能调）：
  //   POST /dsh-bubble/push {"type":"task","id":"extract","title":"提炼观点","pct":30,"detail":"234/782"}
  try {
    ctx.effect(() =>
      ctx.webServer.register({
        kind: 'exact',
        path: '/dsh-bubble/push',
        handler: async (req, res) => {
          if (req.method !== 'POST') return sendJson(res, 405, { ok: false, error: '只接受 POST' })
          let body = {}
          try {
            const chunks = []
            for await (const c of req) chunks.push(c)
            const raw = Buffer.concat(chunks).toString('utf8')
            body = raw ? JSON.parse(raw) : {}
          } catch (e) {
            return sendJson(res, 400, { ok: false, error: 'JSON 解析失败：' + String(e?.message || e) })
          }
          const ev = {
            type: String(body.type || 'task'),
            id: String(body.id || ''),
            title: String(body.title || ''),
            detail: String(body.detail || ''),
            pct: Number(body.pct) || 0,
            state: String(body.state || 'running'),
            at: Date.now(),
          }
          events.push(ev)
          if (events.length > MAX_EVENTS) events.splice(0, events.length - MAX_EVENTS)
          return sendJson(res, 200, { ok: true })
        },
      }),
    )
    ctx.logger?.info?.('dsh-bubble: /dsh-bubble/push 已注册（外部任务可上报）')
  } catch (e) {
    ctx.logger?.warn?.('dsh-bubble: /push 注册失败 ' + String(e?.message || e))
  }

  // 浏览器客户端来拉（拉走即清空）。这条留在 /api/：浏览器带 cookie，没问题
  try {
    const conn = ctx.connection ?? ctx.get?.('connection')
    conn.fetch.register({
      path: '/api/dsh-bubble/events',
      methods: ['GET'],
      requestBody: 'buffered',
      async fetch() {
        const out = events.splice(0, events.length)
        return Response.json({ ok: true, events: out })
      },
    })
    ctx.logger?.info?.('dsh-bubble: /events 已注册（turn 结束阈值 ' + MIN_MS + 'ms）')
  } catch (e) {
    ctx.logger?.warn?.('dsh-bubble: /events 注册失败 ' + String(e?.message || e))
  }

  // 插件卸载 / DSH 退出：把桌宠一起收走，别留野进程
  ctx.on('dispose', () => {
    try {
      if (petChild && !petChild.killed) {
        petChild.kill()
        ctx.logger?.info?.('dsh-bubble: 桌宠已随插件退出')
      }
    } catch { }
  })
}
