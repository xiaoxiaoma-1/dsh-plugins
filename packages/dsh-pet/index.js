/**
 * dsh-pet —— 宿主端（智能桌宠）
 *
 * 一个插件给出四样东西：
 *   1. 桌面上的宠物（窗口外，Python 画的一层，由本插件 spawn 与回收）
 *   2. 对话进度数据（哪些对话在干活、干了多久、谁刚干完）
 *   3. 贾维斯的脑子：一个常驻会话，能开窗口派活、盯进度、收结果
 *   4. 贾维斯的嘴和耳朵的接口：桌宠那层 Python 进程靠这组接口听写和说话
 *
 * 接口（★ 一律不带 /api/ 前缀：cookie guard 按前缀拦 /api/*，外部进程没有 cookie）：
 *   GET  /pet/status           → { ok, running:[{id,title,ms}], runningCount, done:[...] }
 *   POST /pet/push             {"id","title","detail","pct","state"}  外部任务上报
 *   GET  /pet/jarvis/state     → { ok, jarvis:{sessionId}, tasks:[...], last:{text,at} }
 *   POST /pet/jarvis/say       {"text"}   用户说的话投给贾维斯
 *   POST /pet/spawn            {"title","task","cwd"}  开一个干活的窗口
 */

import { spawn } from 'node:child_process'
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

export const name = 'dsh-pet'

// 不声明 inject，ctx.webServer 就是 undefined，注册会被 try/catch 静默吞掉 → 全部 404
export const inject = ['webServer']

const HERE = dirname(fileURLToPath(import.meta.url))
const PET_SCRIPT = join(HERE, 'pet', 'pet.py')
const PET_PY = process.env.DSH_PET_PY ||
  (process.env.LOCALAPPDATA || 'C:\\Users\\Public\\AppData\\Local') + '\\Programs\\Python\\Python312\\pythonw.exe'

const MIN_MS = 5000        // 短于这个的 turn 不记「已完成」（问答别刷屏）
const MAX_EVENTS = 60
const TASK_LIMIT = 40
const REPLY_SETTLE_MS = 900
const REPORT_GAP_MS = 15000   // 同一个窗口两次回报至少隔这么久，别刷屏
// 回报往哪送：false = 队列 + 桌宠的嘴（默认，因为 DSH 那个会话读不出文字）
const REPORT_TO_DSH = false

// 贾维斯的人格：只在会话刚建好时交代一次。短，因为每条消息都会带进上下文。
const PERSONA = [
  '[上线说明] 你是主人的调度员，不是聊天机器人。',
  '1. 主人是动嘴跟你说话，你负责真去办事：能调工具就直接调，别问"要不要我做"。',
  '2. 话短、口语。你的回答会被念出来，不要表格、不要代码块、不要 markdown。',
  '3. 要开新窗口做整件事就用 jarvis_spawn；看派出去的活用 jarvis_tasks。',
  '4. 查得出来的就去查（看板、文件、网页），别编，别只说"我查一下"。',
  '5. 干完一句话说结论，几件事同时好了就问先验收哪个。',
].join('\n')

// 调度员用 V4.1 Flash：便宜、快、够聪明去调工具。
// ★ buddy 这条渠道会拦插件发起的请求（Illegal API invocation from an unapproved channel），
//   所以默认走 codearts，失败再往下换。
const EXECUTOR_CANDIDATES = [
  { provider: 'deepseek-account', model: 'deepseek-flash' },   // 就是 DeepSeek-V4.1-Flash
  { provider: 'siliconflow', model: 'deepseek-ai/DeepSeek-V3.2' },
]
const EXECUTOR_MODEL = EXECUTOR_CANDIDATES[0]

// 派出去的「执行窗口」用哪个模型：主人要的是「转述给更聪明的模型去干」。
// ★ 首选 siliconflow/deepseek-ai/DeepSeek-V3.2 —— 这是主人自己定的「干活模型」，
//   余额充足、直连真实 API。
// ★ 不能用 buddy/deepseek-v4-pro：会话里能选中，但一发请求就被拦——
//   「buddy: 请求被拦截 Illegal API invocation from an unapproved channel」，
//   实测 turn 直接 error 结束，窗口里一个字都没有。
const WORKER_CANDIDATES = [
  { provider: 'siliconflow', model: 'deepseek-ai/DeepSeek-V3.2' },
  { provider: 'deepseek-account', model: 'deepseek-flash' },
]
const WORKER_MODEL = (() => {
  const raw = String(process.env.DSH_PET_EXEC_MODEL || '').trim()
  if (raw.includes('/')) {
    const [provider, ...rest] = raw.split('/')
    return { provider, model: rest.join('/') }
  }
  return WORKER_CANDIDATES[0]
})()

// 执行窗口的开场简报：它不知道自己在为谁干活、也不知道这活是嘴上说的。
// 不给这段，它会反问、会只给方案、会等确认——那样派活就白派了。
function executorBrief(said) {
  const lines = [
    '[执行简报 · 这条指令来自主人的语音，由贾维斯转述给你]',
    '1. 你不需要跟任何人确认：把活直接干完。不许反问、不许只给方案、不许停在"要不要我继续"。',
    '2. 干完只回三样：做了什么、验证结果（真跑过什么命令）、剩余风险。不贴大段 diff。',
    '3. 删除/覆盖/批量修改这类不可逆动作，先留备份或回滚点再做。',
    '4. 交付位置默认 E:\\desktop（用户明确说了别的位置就按他说的）。',
  ]
  const s = String(said || '').trim()
  if (s) lines.push('5. 主人原话（可能有口语省略，和下面任务书冲突时以任务书为准）：' + s.slice(0, 300))
  lines.push('', '—— 以下是贾维斯转述的任务书 ——', '')
  return lines.join('\n')
}

// 会话标题在不同事件里挂的位置不一样，依次兜底取第一个非空的
function pickTitle(p) {
  const cands = [
    p && p.data && p.data.title,
    p && p.title,
    p && p.session && p.session.title,
    p && p.agent && p.agent.session && p.agent.session.title,
    p && p.agent && p.agent.session && p.agent.session.name,
    p && p.session && p.session.name,
  ]
  for (const c of cands) {
    if (typeof c === 'string' && c.trim()) return c.trim()
  }
  return ''
}

function pickSessionId(p) {
  const cands = [
    p && p.session && p.session.id,
    p && p.sessionId,
    p && p.agent && p.agent.session && p.agent.session.id,
    p && p.agent && p.agent.id,
    p && p.data && p.data.sessionId,
    p && p.data && p.data.session && p.data.session.id,
  ]
  for (const c of cands) {
    if (typeof c === 'string' && c) return c
  }
  return ''
}

function sendJson(res, code, body) {
  try {
    res.writeHead(code, { 'content-type': 'application/json; charset=utf-8' })
    res.end(JSON.stringify(body))
  } catch { }
}

function isLoopback(req) {
  const a = req.socket?.remoteAddress || ''
  return a === '127.0.0.1' || a === '::1' || a === '::ffff:127.0.0.1'
}

function readJson(req, limit = 1024 * 1024) {
  return new Promise((resolve) => {
    const chunks = []
    let total = 0
    req.on('data', (c) => {
      total += c.length
      if (total > limit) { try { req.destroy() } catch { } ; resolve(null); return }
      chunks.push(c)
    })
    req.on('end', () => {
      const raw = Buffer.concat(chunks).toString('utf8')
      if (!raw) return resolve({})
      try { resolve(JSON.parse(raw)) } catch { resolve(null) }
    })
    req.on('error', () => resolve(null))
  })
}

/** 从一条 assistant/message 事件里只取「真正说出口的话」。
 *  结构是 { type, seq, data:{ turn, step, message:{ role, content:[{type:'reasoning'},{type:'text'},...] } } }，
 *  必须跳过 reasoning/tool_use 那些块——否则会把模型的思考和工具参数一起念出来。 */
function assistantText(ev) {
  if (!ev) return ''
  const d = ev.data
  const msg = (d && d.message) || ev.message || ev
  const content = msg && msg.content
  if (!Array.isArray(content)) return ''
  let out = ''
  for (const b of content) {
    if (b && b.type === 'text' && typeof b.text === 'string') out += b.text
  }
  return out.trim()
}

/** 从一条事件里把可见文字拼出来（结构在不同版本里会套一层，所以递归兜底） */
function extractText(node, depth = 0) {
  if (!node || depth > 6) return ''
  if (typeof node === 'string') return node
  if (Array.isArray(node)) return node.map((n) => extractText(n, depth + 1)).join('')
  if (typeof node === 'object') {
    if (node.type === 'text' && typeof node.text === 'string') return node.text
    for (const k of ['message', 'content', 'parts', 'blocks']) {
      if (node[k]) {
        const r = extractText(node[k], depth + 1)
        if (r) return r
      }
    }
  }
  return ''
}

/** pet.py 用 %TEMP%\dsh-pet.lock 做单实例判断：这里先把它干掉，新进程才真的能起。 */
function killStalePet(ctx) {
  try {
    const tmp = process.env.TEMP || process.env.TMP || '.'
    const lock = join(tmp, 'dsh-pet.lock')
    if (!existsSync(lock)) return
    const pid = parseInt(String(readFileSync(lock, 'utf8')).trim(), 10)
    if (!pid || pid === process.pid) return
    try {
      process.kill(pid)
      bootLog('结束上一只桌宠 pid=' + pid)
    } catch (e) {
      bootLog('结束旧桌宠失败 pid=' + pid + ': ' + String((e && e.message) || e))
    }
    // kill 是即时的（TerminateProcess），新进程查锁时会发现那个 pid 已经不在了
  } catch (e) {
    ctx.logger?.warn?.('dsh-pet: 清理旧桌宠失败 ' + String((e && e.message) || e))
  }
}

function startPet(ctx) {
  if (!existsSync(PET_PY) || !existsSync(PET_SCRIPT)) {
    ctx.logger?.info?.('dsh-pet: 缺少 Python 或 pet.py，桌宠不启动（插件其它功能照常）')
    return null
  }
  // ★ 热重挂的坑：上一只桌宠没被 kill 掉（dispose 没跑 / kill 失败），
  //   pet.py 里有单实例锁，新进程一看「已经有人在跑」就直接 exit，
  //   于是你以为改了 Python 就生效了，其实一直是旧代码在跑。所以先按锁文件清场。
  killStalePet(ctx)
  try {
    const child = spawn(PET_PY, [PET_SCRIPT], { stdio: 'ignore', windowsHide: true, detached: false })
    child.on('error', (e) => ctx.logger?.warn?.('dsh-pet: 桌宠启动失败 ' + String(e?.message || e)))
    child.on('exit', (code) => ctx.logger?.info?.(`dsh-pet: 桌宠进程退出 code=${code}`))
    ctx.logger?.info?.(`dsh-pet: 桌宠已启动 pid=${child.pid}`)
    return child
  } catch (e) {
    ctx.logger?.warn?.('dsh-pet: 桌宠 spawn 异常 ' + String(e?.message || e))
    return null
  }
}

/**
 * 加载打点。pythonw 那边没控制台，DSH 的 logger 也不落盘，
 * 出了「路由 404 但代码没错」这种事只能靠这个文件看走到哪一步。
 */
function bootLog(msg) {
  try {
    const dir = process.env.DSH_HOME || 'E:\\DSH-data\\.dsh'
    writeFileSync(join(dir, 'pet-boot.log'), new Date().toISOString() + ' ' + msg + '\n', { flag: 'a' })
  } catch { }
}

export function apply(ctx) {
  try {
    return applyInner(ctx)
  } catch (e) {
    bootLog('apply 抛异常: ' + String((e && e.stack) || e))
    throw e
  }
}

function applyInner(ctx) {
  bootLog('=== apply 开始 ===')
  const events = []            // push 上来的外部任务
  const startedAt = new Map()  // id → 起始时间
  const titles = new Map()     // id → 对话标题
  const finished = []          // 最近完成的 turn

  const petChild = startPet(ctx)
  bootLog('startPet 完成 ' + (petChild ? 'pid=' + petChild.pid : '未启动'))

  // ── 贾维斯：会话 id + 派出去的任务表（落盘，重启不丢）────────────────
  const home = process.env.DSH_HOME || 'E:\\DSH-data\\.dsh'
  const stateFile = join(home, 'jarvis-state.json')
  const jstate = loadState(stateFile)
  const tasks = new Map()
  // ★ 重启后旧任务一律标成「已回报」：否则一启动就把上周干完的活重新播报一遍
  for (const t of jstate.tasks || []) {
    t.reported = true
    tasks.set(t.sessionId, t)
  }
  let jarvisId = jstate.jarvisId || ''
  let lastReply = jstate.lastReply || { text: '', at: 0 }
  // 干完活的回报，等桌宠念；重启后旧的标成已念，别一启动就复读上周的
  const reports = (jstate.reports || []).map((r) => ({ ...r, spoken: true }))
  let creating = null
  let lastReadAt = 0

  function saveJ() {
    try {
      mkdirSync(dirname(stateFile), { recursive: true })
      writeFileSync(stateFile, JSON.stringify({
        jarvisId,
        lastReply,
        reports: reports.slice(0, 20),
        tasks: [...tasks.values()].slice(-TASK_LIMIT),
      }, null, 2), 'utf8')
    } catch (e) {
      ctx.logger?.warn?.('dsh-pet: 贾维斯状态落盘失败 ' + String(e?.message || e))
    }
  }

  const sc = () => ctx.get('sessionController')

  function defaultCwd() {
    try {
      const wd = ctx.get('workingDirectory')
      if (wd?.defaultDirectory) return wd.defaultDirectory
    } catch { }
    return process.cwd()
  }

  // 任务书里写了「目录：E:\xxx」就按它开窗口：窗口在错的目录里干活，
  // 等于把活派到别人的工位上——用户还得自己搬回来。
  function cwdFromTask(task) {
    const m = /目录[：:]\s*([A-Za-z]:\\[^\r\n]+)/.exec(String(task || ''))
    if (!m) return ''
    let p = m[1].trim().replace(/[。；;,，]\s*$/, '')
    try {
      if (existsSync(p)) return p
    } catch { }
    return ''
  }

  function newRpcId() {
    return 'jarvis-' + Date.now().toString(36) + '-' + Math.random().toString(36).slice(2, 8)
  }

  async function say(sessionId, text) {
    return deliverTo(sessionId, text)
  }

  function ensureJarvis() {
    if (jarvisId) return Promise.resolve(jarvisId)
    if (creating) return creating
    creating = (async () => {
      const ctl = sc()
      if (!ctl) throw new Error('sessionController 不可用')
      const created = await ctl.create({ cwd: defaultCwd() })
      jarvisId = created.sessionId
      try { ctl.rename({ sessionId: jarvisId, title: '贾维斯（调度员）' }) } catch { }
      saveJ()
      ctx.logger?.info?.('dsh-pet: 贾维斯会话已创建 ' + jarvisId)
      // ★ 指定调度员模型（V4.1 Flash）。不指定就吃默认模型，又贵又慢。
      try {
        await ctl.selectModel({
          sessionId: jarvisId,
          provider: EXECUTOR_MODEL.provider,
          model: EXECUTOR_MODEL.model,
        })
        bootLog('调度员模型已设为 ' + EXECUTOR_MODEL.provider + '/' + EXECUTOR_MODEL.model)
      } catch (e) {
        bootLog('设模型失败: ' + String((e && e.message) || e))
      }
      try { await say(jarvisId, PERSONA) } catch (e) {
        ctx.logger?.warn?.('dsh-pet: 人格交代失败 ' + String(e?.message || e))
      }
      return jarvisId
    })().finally(() => { creating = null })
    return creating
  }

  async function readLastAssistant(sessionId) {
    const sq = ctx.get('sessionQuery')
    if (!sq) return ''
    let obs
    try {
      obs = await sq.observeSession(sessionId)
    } catch {
      return ''
    }
    try {
      const list = obs?.events || []
      for (let i = list.length - 1; i >= 0; i--) {
        const e = list[i]
        if (!e || e.type !== 'assistant/message') continue
        const t = assistantText(e)
        if (t) return t
      }
      return ''
    } finally {
      try { obs?.[Symbol.asyncDispose]?.() } catch { }
    }
  }

  /**
   * 这个窗口最后一轮是报错挂掉的吗？
   *
   * 实测会发生在两种时候：投递太早（pre-step outside running phase）、
   * 会话驱动还没就绪（no initiating agent is active）。两种都表现为
   * 「派了活，窗口里一个字都没有」——不把错误捞出来报给主人，
   * 主人只会觉得贾维斯又傻了。
   */
  async function readLastError(sessionId) {
    const sq = ctx.get('sessionQuery')
    if (!sq) return ''
    let obs
    try { obs = await sq.observeSession(sessionId) } catch { return '' }
    try {
      const list = obs?.events || []
      for (let i = list.length - 1; i >= 0; i--) {
        const e = list[i]
        if (!e || e.type !== 'turn/end') continue
        const reason = e.data && e.data.reason
        if (reason && reason.kind === 'error') {
          const m = (reason.error && reason.error.message) || '未知错误'
          return String(m).slice(0, 200)
        }
        return ''   // 最后一轮是正常结束，不翻旧账
      }
      return ''
    } finally {
      try { obs?.[Symbol.asyncDispose]?.() } catch { }
    }
  }

  /**
   * 等新建的会话真的能收消息。
   *
   * ctl.create() 一返回就 followup，会撞上「pre-step outside running phase」——
   * 会话对象还没进 running 阶段。所以先把它叫热、确认 agent 在线再投。
   */
  async function waitAgentReady(sessionId, timeoutMs = 8000) {
    const t0 = Date.now()
    let lastErr = ''
    while (Date.now() - t0 < timeoutMs) {
      let agent
      try {
        const agents = ctx.get('agents')
        agent = agents && agents.get ? agents.get(sessionId) : undefined
      } catch { }
      if (!agent) {
        const ctl = sc()
        if (ctl && ctl.resolveAgent) {
          try {
            const found = await ctl.resolveAgent(sessionId)
            if (found && found.agent) agent = found.agent
            else if (found && found.error) lastErr = String(found.error.message || found.error)
          } catch (e) { lastErr = String((e && e.message) || e) }
        }
      }
      if (agent) {
        // ★ 这里绝对不要 kick()/wakeDriver()：那会先开一个空 turn，
        //   「空的首批输入不打开步骤」，于是 driver 停在一个没有 step 的轮次里，
        //   后面投进来的话只能等下一次轮次边界，表现就是「派了活窗口一动不动」。
        bootLog('窗口就绪 ' + sessionId + '（等了 ' + (Date.now() - t0) + 'ms）')
        return { ok: true, waited: Date.now() - t0 }
      }
      await new Promise((r) => setTimeout(r, 250))
    }
    bootLog('窗口没就绪 ' + sessionId + '（' + timeoutMs + 'ms，' + lastErr + '）')
    return { ok: false, waited: timeoutMs, error: lastErr }
  }

  /**
   * 把一句话送进某个会话。
   *
   * sessionController.prompt 是 @Remote 方法，host 侧直接调会缺 invocation 上下文
   * （实测报 signal.throwIfAborted is not a function）。所以这里按「从稳到险」多路试，
   * 成功一条就返回，全挂时把每一路的错误都带出去——一次就能看清哪条路是通的。
   */
  async function deliverTo(sessionId, text, opts = {}) {
    const src = { kind: 'user', rpcId: newRpcId() }
    const content = [{ type: 'text', text }]
    const tried = []
    const ctl = sc()

    const attempt = async (name, fn) => {
      try {
        const r = await fn()
        return { ok: true, via: name, result: r }
      } catch (e) {
        const m = String((e && e.message) || e)
        // 「already pending」= 这句话已经在队列里了，目的已达成，不算失败
        if (/already pending/i.test(m)) return { ok: true, via: name + '(queued)', result: 'queued' }
        tried.push(name + ': ' + m)
        return null
      }
    }

    // ① agents 直接投（实测这条能真正把 turn 带起来：followup 入队 + kick 唤醒驱动）
    const agents = (() => { try { return ctx.get('agents') } catch { return undefined } })()
    if (agents) {
      let agent = (() => { try { return agents.get(sessionId) } catch { return undefined } })()
      // 新建的会话是冷的，agents.get 拿不到——先让会话控制器把它热起来
      if (!agent && ctl && ctl.resolveAgent) {
        try {
          const found = await ctl.resolveAgent(sessionId)
          if (found && found.agent) agent = found.agent
          else if (found && found.error) tried.push('resolveAgent: ' + (found.error.message || String(found.error)))
          else tried.push('resolveAgent: 没返回 agent')
        } catch (e) {
          tried.push('resolveAgent: ' + String((e && e.message) || e))
        }
      }
      if (agent) {
        const msg = { id: newRpcId(), role: 'user', content, source: src }
        let hit = await attempt('agent.followup(msg)', () => {
          agent.followup(msg)
          // ★ 只调 wakeDriver，绝不手贱再调 kick()：
          //   wakeDriver 内部是 withInitiator(agent, ()=>kick())，带发起方作用域；
          //   在外面裸调 kick() 会同时踩两个坑——
          //   ① turn/end error「no initiating agent is active」
          //   ② 两个驱动抢同一个 agent，后来的那个报「pre-step outside running phase」，
          //      把正在跑的工具打断（tool/result 变成 interrupted-tool-result）。
          //   实测现象：窗口明明调了工具、也写了报告，最后一步被自己打断，等于白干。
          try { agent.wakeDriver?.() } catch { }
          return 'ok'
        })
        if (hit) return hit
        hit = await attempt('agent.steer(msg)', () => {
          agent.steer(msg)
          try { agent.kick?.() } catch { }
          return 'ok'
        })
        if (hit) return hit
      } else {
        tried.push('agent: 不在线（会话没激活）')
      }
    } else {
      tried.push('agents 服务拿不到')
    }

    // ② sessionController.prompt —— 官方入口，但它走「排队提示词」，
    //    只在轮次边界才被领取，新建会话上实测常常一个 step 都不跑（turn/start 有、request 没有）。
    //    所以放第二，前提是上面那条已经确认不通。
    if (ctl && ctl.prompt) {
      let hit = await attempt('prompt(src)', () =>
        ctl.prompt({ sessionId, content: content.map((c) => ({ ...c })), ...opts }, src))
      if (hit) return hit
      hit = await attempt('prompt+requestId', () =>
        ctl.prompt({ sessionId, content, requestId: newRpcId(), ...opts }, src))
      if (hit) return hit
    } else {
      tried.push('sessionController.prompt 不可用')
    }

    throw new Error(tried.join(' ｜ '))
  }

  /**
   * 子窗口的活干完了 → 把结果记进「回报队列」。
   *
   * ★ 为什么不是直接投进 DSH 里那个贾维斯会话：实测那个会话的 assistant/message
   *   只有 reasoning + tool-call 两种块，text 块 0 条（66 条事件里一条都没有），
   *   投进去也永远读不出字来，桌宠就只能干等着不出声。
   *   所以回报改走「队列 + 桌宠的嘴」：桌宠拉到新回报就让本地大脑说一句结论。
   */
  async function reportToJarvis(rec, text) {
    // 2026-11-09 贾维斯 AI 已拆除：回报队列没人消费了，直接不再写。
    return
    const body = String(text || '').replace(/\s+/g, ' ').trim().slice(0, 320)
    if (!body) return
    reports.unshift({ id: 'r' + Date.now().toString(36) + Math.random().toString(36).slice(2, 6), title: rec.title || '未命名', text: body, at: Date.now(), spoken: false })
    if (reports.length > 20) reports.length = 20
    saveJ()
    bootLog('回报入队 ' + (rec.title || ''))
    if (!REPORT_TO_DSH) return
    try {
      const jid = jarvisId || (await ensureJarvis())
      await deliverTo(jid, '【回报】子窗口「' + (rec.title || '未命名') + '」干完了：' + body)
    } catch (e) {
      bootLog('回报投递失败: ' + String((e && e.message) || e))
    }
  }

  async function spawnTask(title, task, cwdIn, said) {
    const ctl = sc()
    if (!ctl) throw new Error('sessionController 不可用')
    const t = String(title || '').trim() || '未命名任务'
    const body = String(task || '').trim()
    if (!body) throw new Error('task 不能为空')
    const cwd = String(cwdIn || '').trim() || cwdFromTask(body) || defaultCwd()
    const created = await ctl.create({ cwd })
    const sessionId = created.sessionId
    try { ctl.rename({ sessionId, title: t }) } catch { }

    // 执行窗口显式换成强模型：不指定就吃默认模型（deepseek-flash），
    // 那样「转述给更聪明的模型」就落空了，派出去的活还是原来那个脑子在干。
    let workerNow = { provider: '', model: '' }
    if (ctl.selectModel) {
      for (const cand of [WORKER_MODEL, ...WORKER_CANDIDATES]) {
        try {
          await ctl.selectModel({ sessionId, provider: cand.provider, model: cand.model })
          workerNow = cand
          break
        } catch (e) {
          bootLog('执行窗口设模型失败 ' + cand.provider + '/' + cand.model + ': ' + String((e && e.message) || e))
        }
      }
    }

    // ★ 先等窗口真能收消息，再投。不等就会撞「pre-step outside running phase」：
    //   实测表现是窗口起了一下、一个字没说、直接 turn error 结束——
    //   主人看到的就是「派了活没动静」。
    const ready = await waitAgentReady(sessionId)
    if (!ready.ok) bootLog('警告：窗口未就绪就投递 ' + sessionId)

    const brief = executorBrief(said) + body
    let delivered = null
    let lastSayErr = ''
    for (let attempt = 1; attempt <= 2; attempt++) {
      try {
        delivered = await say(sessionId, brief)
        break
      } catch (e) {
        lastSayErr = String((e && e.message) || e)
        bootLog('投递第 ' + attempt + ' 次失败: ' + lastSayErr)
        await new Promise((r) => setTimeout(r, 1200))
        try { await waitAgentReady(sessionId, 3000) } catch { }
      }
    }
    if (!delivered) throw new Error('投递失败：' + lastSayErr)

    tasks.set(sessionId, {
      sessionId, title: t, task: body, cwd,
      state: 'running', startedAt: Date.now(), endedAt: 0, lastText: '',
      reported: false,   // 干完了要回报给贾维斯一次
      worker: workerNow.provider ? workerNow.provider + '/' + workerNow.model : '',
      said: String(said || '').slice(0, 300),
      readyMs: ready.waited,
    })
    while (tasks.size > TASK_LIMIT) {
      const oldest = [...tasks.values()].sort((a, b) => (a.startedAt || 0) - (b.startedAt || 0))[0]
      if (!oldest) break
      tasks.delete(oldest.sessionId)
    }
    saveJ()
    return { sessionId, title: t, cwd }
  }

  function taskList() {
    const now = Date.now()
    return [...tasks.values()]
      .sort((a, b) => (b.startedAt || 0) - (a.startedAt || 0))
      .map((t) => ({
        sessionId: t.sessionId,
        title: t.title,
        state: t.state,
        worker: t.worker || '',
        said: t.said || '',
        error: t.error || '',
        runningMs: t.state === 'running' ? now - (t.startedAt || now) : (t.endedAt || 0) - (t.startedAt || 0),
        lastText: String(t.lastText || '').slice(0, 400),
        reported: !!t.reportedAt,
      }))
  }

  // ── 事件：标题、跑没跑、谁刚停下 ────────────────────────────────
  // ★ 会话标题走独立的 session/title 事件（不监听它，菜单里只能显示「未命名任务」）
  try {
    ctx.on('session/title', (payload) => {
      try {
        const sid = pickSessionId(payload)
        const t = pickTitle(payload)
        if (!sid || !t) return
        titles.set(sid, t)
        const rec = tasks.get(sid)
        if (rec && !rec.title) { rec.title = t; saveJ() }
      } catch { }
    })
  } catch { }

  try {
    ctx.on('agent/status', (payload) => {
      try {
        const a = payload && payload.agent
        const id = (a && (a.id || a.sessionId)) || pickSessionId(payload)
        if (!id) return
        const t = pickTitle(payload) || pickTitle(a)
        if (t) titles.set(id, t)
        if (payload.status === 'running') {
          if (!startedAt.has(id)) startedAt.set(id, Date.now())
          const rec = tasks.get(id)
          if (rec) { rec.state = 'running'; if (!rec.startedAt) rec.startedAt = Date.now(); saveJ() }
        } else if (payload.status === 'idle' || payload.status === 'stopped') {
          startedAt.delete(id)
          const rec = tasks.get(id)
          if (rec && rec.state === 'running') { rec.state = 'idle'; rec.endedAt = Date.now(); saveJ() }
        }
      } catch { }
    })
  } catch { }

  try {
    ctx.on('agent/turn-stopping', (payload) => {
      try {
        const a = payload && payload.agent
        const id = (a && (a.id || a.sessionId)) || pickSessionId(payload)
        const t0 = id ? startedAt.get(id) : 0
        const ms = t0 ? Date.now() - t0 : 0
        if (id) startedAt.delete(id)
        if (!id) return
        const rec = tasks.get(id)
        if (rec) { rec.state = 'idle'; rec.endedAt = Date.now() }
        const isJarvis = id === jarvisId
        if (!rec && !isJarvis) return
        // 短于 MIN_MS 的 turn 不记「已完成」（问答别刷屏），但贾维斯的回复照样要收
        if (!isJarvis && ms >= MIN_MS) {
          let title = pickTitle(payload) || pickTitle(a)
          if (!title) title = titles.get(id) || ''
          finished.push({ title: String(title || ''), ms, at: Date.now() })
          if (finished.length > MAX_EVENTS) finished.splice(0, finished.length - MAX_EVENTS)
        }
        setTimeout(async () => {
          const text = await readLastAssistant(id)
          if (!text) {
            // 读不到字：这一轮可能就是报错挂的（投递太早/驱动没就绪）。
            // 报错也必须回报，否则主人永远只知道「派了活没动静」。
            const cur0 = tasks.get(id)
            if (!isJarvis && cur0 && (!cur0.reportedAt || Date.now() - cur0.reportedAt > REPORT_GAP_MS)) {
              const err = await readLastError(id)
              if (err) {
                cur0.error = err
                cur0.state = 'idle'
                cur0.endedAt = cur0.endedAt || Date.now()
                cur0.reportedAt = Date.now()
                cur0.reported = true
                saveJ()
                reportToJarvis(cur0, '窗口报错挂了：' + err).catch((e) => bootLog('报错回报失败: ' + String((e && e.message) || e)))
              }
            }
            return
          }
          if (isJarvis) lastReply = { text, at: Date.now() }
          const cur = tasks.get(id)
          if (!cur) { saveJ(); return }
          const fresh = text !== cur.lastText
          cur.lastText = text
          saveJ()
          // ★ 子窗口干完了要把结果送回贾维斯——不然派出去的活就是哑巴，
          //   主人问「做好了吗」贾维斯只能读表格，念不出来。
          if (!isJarvis && fresh && text && (!cur.reportedAt || Date.now() - cur.reportedAt > REPORT_GAP_MS)) {
            cur.reported = true
            cur.reportedAt = Date.now()
            saveJ()
            reportToJarvis(cur, text).catch((e) => bootLog('回报失败: ' + String((e && e.message) || e)))
          }
        }, REPLY_SETTLE_MS)
      } catch { }
    })
  } catch { }

  // 2026-11-09 用户决定：拆掉贾维斯 AI，只留桌宠。
  // 原来这里注册 jarvis_spawn / jarvis_tasks 两只手，现在没有了——桌宠不再派活。
  const disposers = []

  // ── HTTP：桌宠轮询 ──────────────────────────────────────────────
  try {
    ctx.effect(() =>
      ctx.webServer.register({
        kind: 'exact',
        path: '/pet/status',
        handler: async (req, res) => {
          const now = Date.now()
          const running = []
          for (const [id, t0] of startedAt.entries()) {
            running.push({ id, title: titles.get(id) || '', ms: now - t0 })
          }
          running.sort((a, b) => b.ms - a.ms)
          // 外部 push 的任务也算「正在干活」，按 id 去重取最新
          const pushed = {}
          for (const e of events) {
            if (e.state === 'running') pushed[e.id || e.title] = e
            else delete pushed[e.id || e.title]
          }
          const extra = Object.values(pushed).map((e) => ({
            id: 'ext:' + (e.id || e.title),
            title: e.title || '',
            ms: Math.max(0, now - (e.at || now)),
            detail: e.detail || '',
            pct: e.pct || 0,
          }))
          const all = running.concat(extra)
          sendJson(res, 200, {
            ok: true,
            running: all,
            runningCount: all.length,
            done: finished.slice(-8).reverse(),
            at: now,
          })
        },
      }),
    )
    ctx.logger?.info?.('dsh-pet: /pet/status 已注册')
    bootLog('route /pet/status ok')
  } catch (e) {
    ctx.logger?.warn?.('dsh-pet: /pet/status 注册失败 ' + String(e?.message || e))
  }

  // 外部任务上报（脚本/命令行都能用）
  try {
    ctx.effect(() =>
      ctx.webServer.register({
        kind: 'exact',
        path: '/pet/push',
        handler: async (req, res) => {
          const m = String(req.method || '').toUpperCase()
          if (m && m !== 'POST') return sendJson(res, 405, { ok: false, error: '只接受 POST' })
          const body = await readJson(req)
          if (body === null) return sendJson(res, 400, { ok: false, error: 'JSON 解析失败' })
          events.push({
            id: String(body.id || ''),
            title: String(body.title || ''),
            detail: String(body.detail || ''),
            pct: Number(body.pct) || 0,
            state: String(body.state || 'running'),
            at: Date.now(),
          })
          if (events.length > MAX_EVENTS) events.splice(0, events.length - MAX_EVENTS)
          return sendJson(res, 200, { ok: true })
        },
      }),
    )
    ctx.logger?.info?.('dsh-pet: /pet/push 已注册')
    bootLog('route /pet/push ok')
  } catch (e) {
    ctx.logger?.warn?.('dsh-pet: /pet/push 注册失败 ' + String(e?.message || e))
  }


  // 2026-11-09 拆掉贾维斯 AI：/pet/spawn、/pet/jarvis/state、/pet/jarvis/say、
  // /pet/jarvis/reports/ack、/pet/jarvis/diag 全部下线。
  // 要恢复：见 E:\DSH-backup\dsh-pet-jarvis-20261109-1129 里的原件。

  ctx.on('dispose', () => {
    for (const d of disposers) { try { d?.() } catch { } }
    saveJ()
    try {
      if (petChild && !petChild.killed) {
        petChild.kill()
        ctx.logger?.info?.('dsh-pet: 桌宠已随插件退出')
      }
    } catch { }
  })
  // 不再在启动时自动创建贾维斯会话（那会在后台白开一个对话窗口）
}


function loadState(file) {
  try {
    if (!existsSync(file)) return {}
    return JSON.parse(readFileSync(file, 'utf8'))
  } catch {
    return {}
  }
}
