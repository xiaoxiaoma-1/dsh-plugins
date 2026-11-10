/**
 * dsh-work-board —— 四栏工作看板（host 端）
 *
 * 四栏：待完成 todo → 进行中 doing → 阶段完成 stage → 已完成 done
 *
 * 设计约束（用户逐条拍板，2026-10-30）：
 *   - 一卡 = 一个项目，可挂多个对话（手风琴展开）
 *   - 建卡由 AI 在聊天里调工具完成，不靠关键词猜
 *   - 「进行中 → 阶段完成」默认自动，但只在**本轮真干活**时触发，带开关
 *   - 数据全局一份，跨工作区共用一个总盘
 *
 * 数据落在 $DSH_HOME/work-board/board.json，原子写（先写 .tmp 再 rename）。
 */

import { homedir } from 'node:os'
import { join } from 'node:path'
import { mkdirSync, readFileSync, writeFileSync, existsSync, renameSync } from 'node:fs'

export const name = 'dsh-work-board'
export const inject = ['tools', 'connection']

const STATUSES = ['todo', 'doing', 'stage', 'done']
const STATUS_LABEL = { todo: '待完成', doing: '进行中', stage: '阶段完成', done: '已完成' }

function dshHome() {
  return process.env.DSH_HOME || join(homedir(), '.dsh')
}

function emptyBoard() {
  return { version: 1, cards: [] }
}

function loadBoard(file) {
  try {
    if (!existsSync(file)) return emptyBoard()
    const raw = JSON.parse(readFileSync(file, 'utf8'))
    if (!raw || !Array.isArray(raw.cards)) return emptyBoard()
    return { version: 1, cards: raw.cards }
  } catch {
    return emptyBoard()
  }
}

function saveBoard(file, board) {
  const dir = join(file, '..')
  mkdirSync(dir, { recursive: true })
  const tmp = file + '.tmp'
  writeFileSync(tmp, JSON.stringify(board, null, 2), 'utf8')
  renameSync(tmp, file)
}

function newId() {
  return 'c' + Date.now().toString(36) + Math.random().toString(36).slice(2, 6)
}

function nowIso() {
  const d = new Date()
  const p = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}

export function apply(ctx, rawConfig = {}) {
  const config = { enabled: true, autoStage: true, storeDir: 'work-board', ...(rawConfig || {}) }
  if (config.enabled === false) return

  const dir = join(dshHome(), config.storeDir || 'work-board')
  const file = join(dir, 'board.json')

  mkdirSync(dir, { recursive: true })
  let board = loadBoard(file)

  const persist = () => {
    try { saveBoard(file, board) } catch (e) { ctx.logger?.warn?.('work-board: 保存失败', e) }
  }

  const find = (id) => board.cards.find((c) => c.id === id) || null

  function createCard({ title, note = '', nextStep = '', workspace = '', status = 'todo' }) {
    const card = {
      id: newId(),
      title: String(title || '').trim() || '未命名项目',
      note: String(note || ''),
      nextStep: String(nextStep || ''),
      status: STATUSES.includes(status) ? status : 'todo',
      workspace: workspace || '',
      sessions: [],
      lastSessionId: null,
      createdAt: nowIso(),
      updatedAt: nowIso(),
      lastStepAt: null,
    }
    board.cards.unshift(card)
    persist()
    return card
  }

  function moveCard(id, status) {
    const card = find(id)
    if (!card) throw new Error(`找不到卡片：${id}`)
    if (!STATUSES.includes(status)) throw new Error(`非法状态：${status}（只能是 ${STATUSES.join('/')}）`)
    card.status = status
    card.updatedAt = nowIso()
    if (status === 'stage') card.lastStepAt = nowIso()
    if (status === 'done') card.lastStepAt = card.lastStepAt || nowIso()
    persist()
    return card
  }

  function updateCard(id, patch = {}) {
    const card = find(id)
    if (!card) throw new Error(`找不到卡片：${id}`)
    for (const k of ['title', 'note', 'nextStep', 'workspace']) {
      if (typeof patch[k] === 'string') card[k] = patch[k]
    }
    card.updatedAt = nowIso()
    persist()
    return card
  }

  function bindSession(id, sessionId, sessionTitle) {
    const card = find(id)
    if (!card) throw new Error(`找不到卡片：${id}`)
    if (!sessionId) throw new Error('sessionId 必填')
    const existing = card.sessions.find((s) => s.id === sessionId)
    if (existing) {
      if (sessionTitle) existing.title = sessionTitle
      existing.at = nowIso()
    } else {
      card.sessions.unshift({ id: sessionId, title: sessionTitle || '未命名对话', at: nowIso() })
    }
    card.lastSessionId = sessionId
    card.updatedAt = nowIso()
    persist()
    return card
  }

  /** 本轮结束后的自动推进：仅在"真干活"时把进行中推到阶段完成。 */
  function autoAdvance(sessionId, sessionTitle) {
    if (config.autoStage === false) return null
    let card = board.cards.find((c) => c.sessions.some((s) => s.id === sessionId)) || null
    if (!card) {
      // 没绑过的会话：挂到最近动过的「进行中」卡片上（用户点「开始」后就来聊，是这个路径）
      const doing = board.cards
        .filter((c) => c.status === 'doing')
        .sort((a, b) => String(b.updatedAt).localeCompare(String(a.updatedAt)))
      card = doing[0] || null
      if (!card) return null
    }
    bindSession(card.id, sessionId, sessionTitle)
    if (card.status === 'doing') {
      card.status = 'stage'
      card.lastStepAt = nowIso()
      card.updatedAt = nowIso()
      persist()
    }
    return card
  }

  function snapshot() {
    const counts = { todo: 0, doing: 0, stage: 0, done: 0 }
    for (const c of board.cards) if (counts[c.status] != null) counts[c.status]++
    return { cards: board.cards, counts, file, statuses: STATUSES, labels: STATUS_LABEL }
  }

  // ── 工具：给 AI 在聊天里建卡 / 改卡 ───────────────────────────────
  const disposers = []
  disposers.push(ctx.tools.register({
    name: 'board_create',
    description: '在工作看板建一张卡（默认落在「待完成」）。用户说"记一下/帮我建个卡/这个想法存起来"时用它。note 里写清：目标、拆解步骤、方法论、验收标准。',
    parameters: {
      type: 'object',
      properties: {
        title: { type: 'string', description: '项目名（简短，能一眼认出）' },
        note: { type: 'string', description: '卡片正文：目标 / 拆解 / 方法论 / 验收标准' },
        nextStep: { type: 'string', description: '下一步一句话' },
        workspace: { type: 'string', description: '所属工作区名或路径' },
        status: { type: 'string', enum: ['todo', 'doing', 'stage', 'done'], description: '初始状态，默认 todo' },
      },
      required: ['title'],
      additionalProperties: false,
    },
    output: {
      schema: { type: 'object', additionalProperties: true },
      render: (args, value) => [{ type: 'text', text: JSON.stringify(value, null, 2) }],
    },
    execute: async (args) => {
      const card = createCard(args)
      return { ok: true, id: card.id, title: card.title, status: card.status }
    },
  }))

  disposers.push(ctx.tools.register({
    name: 'board_list',
    description: '列出看板卡片。可按状态过滤：todo/doing/stage/done。',
    parameters: {
      type: 'object',
      properties: {
        status: { type: 'string', enum: ['todo', 'doing', 'stage', 'done'], description: '只看这一栏' },
      },
      additionalProperties: false,
    },
    output: {
      schema: { type: 'object', additionalProperties: true },
      render: (args, value) => [{ type: 'text', text: JSON.stringify(value, null, 2) }],
    },
    execute: async (args) => {
      const cards = args.status ? board.cards.filter((c) => c.status === args.status) : board.cards
      const brief = cards.map((c) => ({
        id: c.id, title: c.title, status: c.status, statusLabel: STATUS_LABEL[c.status],
        nextStep: c.nextStep || '', sessions: c.sessions.length, updatedAt: c.updatedAt,
      }))
      return { total: brief.length, cards: brief }
    },
  }))

  disposers.push(ctx.tools.register({
    name: 'board_move',
    description: '把卡片移到另一栏。todo=待完成, doing=进行中, stage=阶段完成, done=已完成。',
    parameters: {
      type: 'object',
      properties: {
        id: { type: 'string', description: '卡片 id' },
        status: { type: 'string', enum: ['todo', 'doing', 'stage', 'done'], description: '目标状态' },
      },
      required: ['id', 'status'],
      additionalProperties: false,
    },
    output: {
      schema: { type: 'object', additionalProperties: true },
      render: (args, value) => [{ type: 'text', text: JSON.stringify(value, null, 2) }],
    },
    execute: async (args) => {
      const card = moveCard(args.id, args.status)
      return { ok: true, id: card.id, status: card.status }
    },
  }))

  disposers.push(ctx.tools.register({
    name: 'board_update',
    description: '改卡片内容：标题、正文、下一步。每轮干完活建议更新一次 nextStep。',
    parameters: {
      type: 'object',
      properties: {
        id: { type: 'string', description: '卡片 id' },
        title: { type: 'string', description: '新标题' },
        note: { type: 'string', description: '整段覆盖正文' },
        nextStep: { type: 'string', description: '下一步一句话' },
      },
      required: ['id'],
      additionalProperties: false,
    },
    output: {
      schema: { type: 'object', additionalProperties: true },
      render: (args, value) => [{ type: 'text', text: JSON.stringify(value, null, 2) }],
    },
    execute: async (args) => {
      const { id, ...patch } = args
      const card = updateCard(id, patch)
      return { ok: true, id: card.id, updatedAt: card.updatedAt }
    },
  }))

  disposers.push(ctx.tools.register({
    name: 'board_bind',
    description: '把当前对话绑到某张卡上（卡片点开就能回到这个对话）。通常不需要手动调用，自动推进时会绑。',
    parameters: {
      type: 'object',
      properties: {
        id: { type: 'string', description: '卡片 id' },
        sessionId: { type: 'string', description: '对话 id' },
        sessionTitle: { type: 'string', description: '对话标题' },
      },
      required: ['id', 'sessionId'],
      additionalProperties: false,
    },
    output: {
      schema: { type: 'object', additionalProperties: true },
      render: (args, value) => [{ type: 'text', text: JSON.stringify(value, null, 2) }],
    },
    execute: async (args) => {
      const card = bindSession(args.id, args.sessionId, args.sessionTitle)
      return { ok: true, id: card.id, sessions: card.sessions.length }
    },
  }))

  // ── 每轮结束：真有产出才推进 ─────────────────────────────────────
  const agentOffs = []
  disposers.push(ctx.on('agent/created', ({ agent }) => {
    let workCount = 0
    const sessionId = () => {
      try { return agent?.id ?? agent?.session?.id ?? agent?.sessionId ?? null } catch { return null }
    }
    const sessionTitle = () => {
      try {
        const t = agent?.session?.title ?? agent?.session?.meta?.title
        return typeof t === 'string' && t.trim() ? t.trim() : '未命名对话'
      } catch { return '未命名对话' }
    }

    const offs = []
    const offTool = agent.ctx.on('tools/result', () => { workCount += 1 })
    const offTurn = agent.ctx.on('agent/turn-stopping', () => {
      const worked = workCount > 0
      workCount = 0
      if (!worked) return
      const sid = sessionId()
      if (!sid) return
      try {
        const card = autoAdvance(sid, sessionTitle())
        if (card) ctx.logger?.info?.(`work-board: 会话 ${sid} 完成一步 → ${card.title} (${card.status})`)
      } catch (e) {
        ctx.logger?.warn?.('work-board: 自动推进失败', e)
      }
    })
    offs.push(() => { try { offTool?.() } catch { } }, () => { try { offTurn?.() } catch { } })
    const offDisposed = agent.ctx.on('agent/disposed', () => {
      for (const f of offs) { try { f() } catch { } }
    })
    agentOffs.push(() => { try { offDisposed?.() } catch { } })
  }))

  // ── 客户端 RPC：/api/work-board ────────────────────────────────────
  let unregisterFetch = null
  try {
    const connection = ctx.connection ?? ctx.get?.('connection')
    if (connection?.fetch?.register) {
      unregisterFetch = connection.fetch.register({
        path: '/api/work-board',
        methods: ['POST'],
        requestBody: 'buffered',
        async fetch(request) {
          if (request.method !== 'POST') return new Response('method not allowed', { status: 405 })
          let message
          try { message = await request.json() } catch { return new Response('body is not JSON', { status: 400 }) }
          const rpcId = typeof message?.rpcId === 'string' ? message.rpcId : 'invalid'
          const call = message?.payload
          if (message?.type !== 'client-request' || typeof message?.rpcId !== 'string' ||
              message?.method !== 'work-board' || !call || typeof call.method !== 'string') {
            return Response.json({ type: 'server-response', rpcId, result: { ok: false, error: { code: 'bad-request', message: 'Invalid request' } } })
          }
          const p = call.payload || {}
          try {
            let value
            switch (call.method) {
              case 'snapshot': value = snapshot(); break
              case 'create': value = createCard(p); break
              case 'move': value = moveCard(p.id, p.status); break
              case 'update': value = updateCard(p.id, p); break
              case 'bind': value = bindSession(p.id, p.sessionId, p.sessionTitle); break
              case 'path': value = { file }; break
              default: throw new Error(`Unknown method: ${call.method}`)
            }
            return Response.json({ type: 'server-response', rpcId, result: { ok: true, value } })
          } catch (e) {
            return Response.json({ type: 'server-response', rpcId, result: { ok: false, error: { code: 'handler-failed', message: e?.message ?? String(e) } } })
          }
        },
      })
      ctx.logger?.info?.('work-board: 数据端点已注册 /api/work-board')
    } else {
      ctx.logger?.warn?.('work-board: connection.fetch 不可用，前端取数会失败')
    }
  } catch (e) {
    ctx.logger?.warn?.('work-board: 数据端点注册失败', e)
  }

  /* 对外服务：别的插件（比如需求发掘台点「有用」）要建卡时用这个，
     直接走本插件内存里的 board，客户端轮询 snapshot 立刻能看到。 */
  try {
    ctx.provide('workBoard', {
      createCard,
      moveCard,
      updateCard,
      bindSession,
      snapshot,
      file: () => file,
    })
    ctx.logger?.info?.('work-board: 服务 workBoard 已提供')
  } catch (e) {
    ctx.logger?.warn?.('work-board: 服务 workBoard 提供失败', e)
  }

  return () => {
    for (const d of disposers) { try { d?.() } catch { } }
    for (const d of agentOffs) { try { d?.() } catch { } }
    if (typeof unregisterFetch === 'function') { try { unregisterFetch() } catch { } }
  }
}
