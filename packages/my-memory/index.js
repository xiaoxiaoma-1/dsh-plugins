/**
 * my-memory — 专属跨会话记忆插件（host 端）
 *
 * 基于 meow-memory 七层架构，增强：
 *   - 向量语义检索（轻量 n-gram 哈希嵌入 + 余弦相似度）
 *   - 记忆标签与分类（tags 列 + 按标签过滤/聚合）
 *   - 记忆关系图谱（memory_relations 表：引用/依赖/冲突/补充/演化）
 *   - 记忆导出与迁移（JSON / Markdown 双格式导出）
 *   - 记忆统计仪表盘（各层计数 + 标签分布 + 热门 + 最近活动）
 *
 * 七层：soul / user / project / fact / lesson / topic / rules
 * 存储：node:sqlite，每层一表，零运行时依赖。
 */

import { randomUUID } from 'node:crypto'
import { homedir } from 'node:os'
import z from '@deepseek-ai/schemastery'
import { getDb, closeAllDbs, LEVELS, LEVEL_LABELS, RELATION_TYPES } from './db.js'
import { bm25Search } from './bm25.js'
import { embed, embedMemory, vectorSearch } from './embed.js'
import {
  buildFirstTurnInjection,
  buildHitInjection,
  buildProgressInjection,
  buildProjectAnchor,
  getSessionState,
  PLUGIN_SOURCE,
} from './inject.js'
import { readOccupancy, formatOccupancy, actionFor } from './meter.js'
import {
  buildReflectMessage,
  buildTurnSummaryMessage,
  isReflectTurn,
} from './reflect.js'
import {
  autoFillTags,
  buildSummaryInjection,
  ensureSummaryTable,
  insertTurnSummary,
  latestSummaryAnywhere,
  localTimeString,
  shouldSummarizeThisTurn,
  workspaceName,
} from './turn-summaries.js'

export const name = 'my-memory'
// connection 必须声明：图谱窗口的数据路由走 ctx.connection.fetch.register，
// 不 inject 就拿不到 ctx.connection，路由静默不注册，前端一律 404（已踩过一次）。
export const inject = ['tools', 'systemPrompt', 'connection']

// ── 配置 schema ─────────────────────────────────────────────────────
const config = z.object({
  enabled: z.boolean().default(true),
  projectDir: z.string().default('.my-memory'),
  hitTopK: z.number().min(0).max(10).default(2),
  vectorTopK: z.number().min(0).max(20).default(2),
  reflect: z.boolean().default(true),
  reflectTurns: z.number().min(1).max(50).default(7),
  titleMax: z.number().min(10).max(200).default(40),
  // ── 每轮总结（价值门控滚动窗口）──
  turnSummary: z.boolean().default(true),
  summaryWindow: z.number().min(1).max(10).default(2),
  summaryHighMax: z.number().min(1).max(50).default(6),
  summaryMinUserChars: z.number().min(0).max(500).default(30),
  workspaceFilter: z.boolean().default(true),
  // ── 上下文计量阈值（占窗口比例）──
  // V3.2 实际只能吃下标称窗口的一半左右，所以 45% 提醒、50% 必须交接换窗口；
  // 换成真长窗口模型可放宽。
  contextWarnRatio: z.number().min(0.1).max(1).default(0.45),
  contextHandoffRatio: z.number().min(0.1).max(1).default(0.5),
  timeZone: z.string().default('Asia/Shanghai'),
})

Object.assign(config.meta, { volatile: true })

export { config as Config }

// ── 辅助函数 ─────────────────────────────────────────────────────────

/** 用户纠正语气：命中即认为"用户纠正了我"（要求够长，避免误判） */
const CORRECTION_PATTERNS = [
  /不对/, /错了/, /不是这样/, /不是这个/, /我说的是/, /你搞错/, /你理解错/,
  /重来/, /应该是/, /别这样/, /不要这样/, /谁让你/,
]

/** 返回纠正原文（不是纠正则返回 null） */
function looksLikeCorrection(text) {
  const t = String(text ?? '').trim()
  if (t.length < 6) return null
  return CORRECTION_PATTERNS.some(re => re.test(t)) ? t.slice(0, 200) : null
}

/** 从工具调用参数里猜涉及的文件/命令，给经验包草案留证据 */
function guessTarget(payload) {
  const raw = payload?.args ?? payload?.arguments ?? payload?.input ?? payload?.params
  const s = typeof raw === 'string' ? raw : JSON.stringify(raw ?? '')
  if (!s || s === '{}') return ''
  const file = s.match(/[A-Za-z]:[\\/][^"',\s]{3,120}|[\w\-.]+[\\/][\w\-./]{2,120}|[\w\-.]+\.(?:js|mjs|cjs|ts|json|md|yml|yaml|ps1|sh)/)
  if (file) return file[0].slice(0, 120)
  const cmd = s.match(/"command"\s*:\s*"((?:[^"\\]|\\.){3,120})"/)
  return cmd ? cmd[1].slice(0, 120) : ''
}

function workspaceOfAgent(agent) {
  const cwd = agent?.session?.header?.cwd
  return typeof cwd === 'string' && cwd.length > 0 ? cwd : null
}

function sessionIdOfAgent(agent) {
  const id = agent?.session?.header?.id
  return typeof id === 'string' && id.length > 0 ? id : 'unknown'
}

function sessionEventsOf(session) {
  if (typeof session?.ownEvents === 'function') {
    const evs = session.ownEvents()
    return Array.isArray(evs) ? evs : []
  }
  const evs = session?.events
  return Array.isArray(evs) ? evs : []
}

function messageText(msg) {
  if (typeof msg?.content === 'string') return msg.content
  if (Array.isArray(msg?.content)) {
    return msg.content.filter(b => b.type === 'text').map(b => b.text).join(' ')
  }
  return ''
}

function isUserMessage(msg) {
  return msg?.source?.kind === 'user' || (msg?.source?.kind === undefined && msg?.role === 'user')
}

// createUserMessage 延迟加载（apply 中初始化）
let createUserMessage = null

/** 校验插件消息满足 DSH v4 格式不变量，避免损坏会话 */
function assertValidPluginMessage(msg) {
  if (typeof msg?.id !== 'string' || msg.id === '')
    throw new Error('plugin message missing id')
  if (msg.role !== 'user')
    throw new Error('plugin message must have role "user"')
  if (!Array.isArray(msg.content))
    throw new Error('plugin message must have array content')
  const src = msg.source
  if (typeof src?.kind !== 'string' || src.kind === '' || src.kind === 'plugin')
    throw new Error('plugin message has invalid source.kind')
  return msg
}

function createPluginMessage(text, form = 'snapshot') {
  const sectionName = form === 'notice' ? '记忆反思' : '长期记忆'
  const source = {
    ...PLUGIN_SOURCE,
    form,
    sections: [{ name: sectionName, text }],
  }
  let msg
  if (createUserMessage) {
    msg = createUserMessage({ content: [{ type: 'text', text }], source })
  } else {
    msg = { id: randomUUID(), role: 'user', content: [{ type: 'text', text }], source }
  }
  return assertValidPluginMessage(msg)
}

// ── 主 apply ────────────────────────────────────────────────────────
export async function apply(ctx, rawConfig) {
  const cfg = rawConfig ?? {}
  const enabled = cfg.enabled ?? true
  if (!enabled) {
    ctx.logger?.info?.('my-memory: 已停用')
    return
  }

  const projectDir = cfg.projectDir ?? '.my-memory'
  const hitTopK = cfg.hitTopK ?? 2
  const vectorTopK = cfg.vectorTopK ?? 2

  // 延迟加载 createUserMessage（DSH 官方消息构造器）
  if (!createUserMessage) {
    try {
      const dshLlm = await import('@deepseek-ai/dsh-llm')
      createUserMessage = dshLlm.createUserMessage
    } catch { /* 降级到手动构造 */ }
  }
  const reflectEnabled = cfg.reflect ?? true
  const reflectTurns = cfg.reflectTurns ?? 7
  const titleMax = cfg.titleMax ?? 40
  const turnSummary = cfg.turnSummary ?? true
  const summaryWindow = cfg.summaryWindow ?? 2
  const summaryHighMax = cfg.summaryHighMax ?? 6
  const summaryMinUserChars = cfg.summaryMinUserChars ?? 30
  const workspaceFilter = cfg.workspaceFilter ?? true
  const contextWarnPct = Math.round((cfg.contextWarnRatio ?? 0.45) * 100)
  const contextHandoffPct = Math.round((cfg.contextHandoffRatio ?? 0.5) * 100)
  const timeZone = cfg.timeZone ?? 'Asia/Shanghai'

  ctx.logger?.info?.('my-memory: 插件已激活')
  const disposers = []

  // ── 系统提示：记忆使用手册 ──────────────────────────────────────
  // DSH 0.2.x: section() 接受 text 字段（非 provide 函数）
  disposers.push(ctx.systemPrompt.section({
    name: 'my-memory:guide',
    order: 130,
    text: `【心印 · 记忆系统】（包名 my-memory，界面名「心印」，图谱面板名「脉络」）
你拥有跨会话的长期记忆能力。记忆分七层：
- soul：关于你（AI）自身的认知
- user：关于用户的信息与偏好
- project：项目信息（含子类 overview/structure/decisions/quotes/ops/todo）
- fact：原子事实
- lesson：错误教训与用户纠正
- topic：进行中的话题（带目标句）
- rules：设计原则与行为准则

另有**经验系统**：将工程项目中遇到的问题、解决方案、关键收获沉淀为经验包，越用越聪明。

可用工具（只有这些，别调不存在的）：
- memory_remember：写入记忆；传 id 即修改已有记忆（修改/打标签都走它）
- memory_search：双路检索（关键词 + 语义），只回标题和摘要
- memory_read：按 id 读全文；只有真正读了才算"用上"
- memory_experience：经验包（怎么做某类事）
- memory_turn_summary：写本轮进度（即将被进度行取代）
- memory_now：当前本地时间
- memory_context：当前上下文占用（几成、还剩多少）

使用原则：
- 重要事实、用户偏好、项目决策应及时记忆
- 检索时先用 memory_search 看摘要，需要细节再 memory_read
- 教训和纠正写入 lesson 层并标记 corrected
- 解决了一个难题后，用 memory_experience 沉淀经验包（问题→解决方案→收获）
- 遇到新问题时，先用 memory_experience 搜索是否有类似经验可复用
- 系统会自动检测「工具失败→成功」模式并创建经验包草案，收到通知后请用 memory_experience update 补充关键收获`,
  }))

  // ── 注册记忆工具（全局，db 从 initiator 解析） ──────────────────
  disposers.push(registerAllTools(ctx, projectDir, hitTopK, vectorTopK, {
    turnSummary, summaryWindow, summaryHighMax, timeZone, workspaceFilter,
  }))

  // ── RPC endpoint: 记忆关系图谱数据（供前端可视化） ──────────────
  disposers.push(registerGraphEndpoint(ctx, projectDir))

  // ── agent/created：每 agent 注入与反思 ──────────────────────────
  disposers.push(ctx.on('agent/created', ({ agent }) => {
    const workspace = workspaceOfAgent(agent)
    if (!workspace) return
    const sessionId = sessionIdOfAgent(agent)
    const sessionState = getSessionState(sessionId)
    let db
    try { db = getDb(workspace, projectDir) } catch (e) {
      ctx.logger?.warn?.(`my-memory: 无法打开记忆库: ${e?.message ?? e}`)
      return
    }

    // agent/pre-step：注入记忆
    const preStep = agent.ctx.on('agent/pre-step', async (payload, next) => {
      const decision = await next()
      try {
        const events = sessionEventsOf(agent.session)
        if (isReflectTurn(events)) return decision

        const msgs = decision.messages ?? payload.messages ?? []
        const userMsgs = msgs.filter(m => isUserMessage(m))
        if (userMsgs.length === 0) return decision

        const text = messageText(userMsgs[userMsgs.length - 1])
        if (!text || text.length < 2) return decision

        // 用户纠正检测：命中就记下来，本轮收尾时自动沉淀经验草案
        const correction = looksLikeCorrection(text)
        if (correction) {
          sessionState.corrections.push(correction)
          if (sessionState.corrections.length > 5) sessionState.corrections.shift()
        }

        // 项目锚定：会话还没锚定项目时，从用户这句话里匹配已知项目名，
        // 锚定后命中检索才会带上该项目自己的记忆（项目蓝图、进度、教训）
        let anchoredNow = false
        if (!sessionState.currentProject) {
          try {
            const hit = db.listProjectNames()
              .filter(n => typeof n === 'string' && n.length >= 2)
              .find(n => text.includes(n))
            if (hit) { sessionState.currentProject = hit; anchoredNow = true }
          } catch { /* 锚定失败不影响注入 */ }
        }

        const injections = []
        // 刚锚定到某个项目 → 注入一次项目图纸，防止做着做着跑偏
        if (anchoredNow) {
          try {
            const anchor = buildProjectAnchor(db, sessionState.currentProject)
            if (anchor) injections.push(createPluginMessage(anchor))
          } catch (e) { ctx.logger?.warn?.(`my-memory: 项目锚定注入失败: ${e?.message ?? e}`) }
        }
        // 上下文计量：到 warn 线提醒收敛，到 handoff 线要求本轮结束前写交接单（每档只提醒一次）
        try {
          const occ = readOccupancy(ctx, agent.session)
          const advice = occ
            ? actionFor(occ.percent, { warnRatio: contextWarnPct, handoffRatio: contextHandoffPct })
            : null
          const level = advice === 'handoff' ? contextHandoffPct : advice === 'progress' ? contextWarnPct : 0
          if (level > sessionState.occupancyNotified) {
            sessionState.occupancyNotified = level
            const tips = advice === 'handoff'
              ? `已到 ${contextHandoffPct}%：本轮结束前必须写交接单（目标 / 做到哪 / 下一步 / 卡在哪），然后换新窗口接着做；再往后就会撞输出上限。`
              : `已到 ${contextWarnPct}%：开始收敛，只推进当前这一步，结束前写一行进度。`
            injections.push(createPluginMessage(`【上下文占用】${formatOccupancy(occ)}\n${tips}`))
          }
        } catch (e) { ctx.logger?.warn?.(`my-memory: 上下文计量失败: ${e?.message ?? e}`) }
        if (!sessionState.injected) {
          let inj = buildFirstTurnInjection(db, titleMax)
          // 新机制：上次进度行 + 交接单（替代冗长的每轮总结）
          try {
            const p = buildProgressInjection(db, { workspace: workspaceName(workspace) })
            if (p) inj = inj ? `${inj}\n\n${p}` : p
          } catch (e) { ctx.logger?.warn?.(`my-memory: 进度注入失败: ${e?.message ?? e}`) }
          if (turnSummary) {
            try {
              const s = buildSummaryInjection(db, {
                workspace: workspaceName(workspace),
                sessionId,
                window: summaryWindow,
              })
              if (s) inj = inj ? `${inj}\n\n${s}` : s
            } catch (e) { ctx.logger?.warn?.(`my-memory: 总结注入失败: ${e?.message ?? e}`) }
          }
          if (inj) { injections.push(createPluginMessage(inj)); sessionState.injected = true }
        } else {
          sessionState.messageCount++
          const hit = buildHitInjection(db, text, {
            hitTopK,
            vectorTopK,
            project: sessionState.currentProject,
            workspace: workspaceName(workspace),
            workspaceFilter,
          })
          if (hit) injections.push(createPluginMessage(hit))
        }
        if (injections.length > 0) {
          return { ...decision, messages: [...injections, ...msgs] }
        }
      } catch (e) { ctx.logger?.warn?.(`my-memory: pre-step 注入失败: ${e?.message ?? e}`) }
      return decision
    })

    // tools/result：计数 + 自动经验捕获
    const recentFailures = []
    let lastCaptureStep = 0
    let totalSteps = 0

    const toolResult = agent.ctx.on('tools/result', (payload) => {
      sessionState.toolSteps++
      totalSteps++

      // 从 payload 提取工具名和结果
      const toolName = payload?.name ?? payload?.toolName ?? payload?.tool?.name ?? 'unknown'
      const resultStr = typeof payload?.result === 'string' ? payload.result
        : typeof payload?.output === 'string' ? payload.output
        : payload?.result?.text ?? ''
      const isError = payload?.error != null || payload?.ok === false
        || /^\[exit code: [1-9]/m.test(resultStr) || /error|failed|cannot|unable/i.test(resultStr.slice(0, 300))
      const errorMsg = payload?.error?.message ?? payload?.error
        ?? (isError ? resultStr.slice(0, 200) : '')

      // 排除 memory_* 工具自身的结果
      if (toolName.startsWith('memory_')) return

      if (isError && errorMsg.length > 5) {
        recentFailures.push({
          toolName,
          error: String(errorMsg).slice(0, 200),
          target: guessTarget(payload),
          step: totalSteps,
          timestamp: Date.now(),
        })
        if (recentFailures.length > 5) recentFailures.shift()
      } else {
        // 成功后有失败记录 → 自动存经验草案（takeaways 留空，等 AI 补一行收获才算成品）
        if (recentFailures.length > 0 && totalSteps - lastCaptureStep > 3) {
          const failures = recentFailures.splice(0)
          lastCaptureStep = totalSteps
          try {
            const problemParts = failures.map(f => `${f.toolName}: ${f.error}`).join(' → ')
            const targets = [...new Set(failures.map(f => f.target).filter(Boolean))].slice(0, 5)
            const exp = db.insertExperience({
              project: sessionState.currentProject ?? 'auto-captured',
              problem: `工具失败后成功：${problemParts.slice(0, 300)}`,
              solution: `最终通过 ${toolName} 成功完成（第 ${totalSteps} 步）${targets.length ? `\n涉及：${targets.join('、')}` : ''}`,
              takeaways: '',
              tags: ['auto-draft', 'auto-captured', ...new Set(failures.map(f => f.toolName))],
              importance: 5,
            })
            db.setVector?.(exp.id, embedMemory?.({ content: exp.problem + exp.solution }) ?? [])
            const notice = createPluginMessage(
              `【经验草案】「失败→成功」已自动存下（${[...new Set(failures.map(f => f.toolName))].join(', ')} → ${toolName}），id=${exp.id}。`
              + `用 memory_experience update 补一行"关键收获"、去掉 auto-draft 标签，才算成品。`,
              'notice'
            )
            if (typeof agent.inject === 'function') agent.inject(notice)
          } catch (e) { ctx.logger?.warn?.(`my-memory: 经验自动捕获注入失败: ${e?.message ?? e}`) }
        }
      }
    })

    // agent/turn-stopping：用户纠正沉淀 + 每轮收尾 + 反思
    let reflectPending = false
    const turnStop = agent.ctx.on('agent/turn-stopping', async () => {
      if (reflectPending) return
      const events = sessionEventsOf(agent.session)
      if (isReflectTurn(events)) return

      // 用户纠正过 → 自动存一条经验草案（第二种自动沉淀现场）
      if (sessionState.corrections.length > 0) {
        try {
          const said = sessionState.corrections.splice(0)
          const exp = db.insertExperience({
            project: sessionState.currentProject ?? 'auto-captured',
            problem: `用户纠正：${said.join(' / ').slice(0, 300)}`,
            solution: '（待补：这次被纠正后怎么改对的）',
            takeaways: '',
            tags: ['auto-draft', 'user-correction'],
            importance: 6,
          })
          const notice = createPluginMessage(
            `【经验草案】用户纠正已记录（id=${exp.id}）。用 memory_experience update 写清三件事：错在哪、怎么改对的、以后怎么避免；去掉 auto-draft 标签才算完成。`,
            'notice'
          )
          if (typeof agent.inject === 'function') agent.inject(notice)
        } catch (e) { ctx.logger?.warn?.(`my-memory: 纠正经验捕获失败: ${e?.message ?? e}`) }
      }

      // 最后一步是 memory_* 工具 → 正在写记忆，不再注入，避免自激
      let lastTool = null
      for (let i = events.length - 1; i >= 0; i--) {
        if (events[i]?.type === 'tool/result') { lastTool = events[i]?.data?.name ?? events[i]?.data?.toolName; break }
      }
      if (lastTool?.startsWith('memory_')) { sessionState.toolSteps = 0; return }

      const wantSummary = turnSummary && shouldSummarizeThisTurn(events, { minUserChars: summaryMinUserChars })
      const wantReflect = reflectEnabled && sessionState.toolSteps >= reflectTurns
      if (!wantSummary && !wantReflect) return

      reflectPending = true
      sessionState.toolSteps = 0
      try {
        const text = wantSummary
          ? buildTurnSummaryMessage({
            localTime: localTimeString(Date.now(), timeZone),
            reflect: wantReflect,
            project: sessionState.currentProject,
          })
          : buildReflectMessage()
        const msg = createPluginMessage(text, 'notice')
        if (typeof agent.followup === 'function') await agent.followup(msg)
        else if (typeof agent.inject === 'function') agent.inject(msg)
      } catch (e) { ctx.logger?.warn?.(`my-memory: 总结/反思注入失败: ${e?.message ?? e}`) } finally { reflectPending = false }
    })

    const disposed = agent.ctx.on('agent/disposed', () => {
      preStep?.(); toolResult?.(); turnStop?.()
    })

    disposers.push(() => { preStep?.(); toolResult?.(); turnStop?.(); disposed?.() })
  }))

  return () => {
    disposers.forEach(d => { try { d?.() } catch { } })
    closeAllDbs()
  }
}

// ── 图谱可视化 RPC 端点 ────────────────────────────────────────────
function registerGraphEndpoint(ctx, projectDir) {
  try {
    const connection = ctx.connection ?? ctx.get?.('connection')
    if (!connection?.fetch?.register) {
      ctx.logger?.warn?.('my-memory: connection.fetch 不可用，数据 RPC 端点未注册')
      return () => {}
    }

    // ── 搜索辅助：构建可检索列表 + BM25 + 向量 ───────────────────
    function doSearch(db, query, opts = {}) {
      const { level, project, tag, limit = 10, vectorTopK = 5 } = opts
      const searchLevels = level ? [level] : LEVELS
      let allSearchable = []
      for (const lv of searchLevels) allSearchable.push(...db.listSearchable(lv))
      if (project) {
        allSearchable = allSearchable.filter(m =>
          !m.project || m.project === '全局' || m.project.toLowerCase() === 'global' ||
          (m.project && m.project.split(',').map(s => s.trim()).includes(project)))
      }
      if (tag) allSearchable = allSearchable.filter(m => m.tags.includes(tag))
      if (allSearchable.length === 0) return []
      const bm25Hits = bm25Search(allSearchable, query, { topK: limit })
      const vectors = []
      for (const m of allSearchable) {
        let vec = db.getVector(m.id)
        if (!vec) { vec = embedMemory(m); db.setVector(m.id, m.level, vec) }
        vectors.push({ memoryId: m.id, level: m.level, vector: vec })
      }
      const queryVec = embed(query)
      const vecHits = vectorSearch(vectors, queryVec, { topK: vectorTopK })
      const seen = new Set()
      const merged = []
      for (const h of bm25Hits) {
        if (!seen.has(h.row.id)) { seen.add(h.row.id); merged.push({ ...h.row, score: h.score, source: 'keyword' }) }
      }
      for (const h of vecHits) {
        if (!seen.has(h.memoryId)) {
          seen.add(h.memoryId)
          const found = db.findById(h.memoryId)
          if (found) merged.push({ ...found.row, score: h.score, source: 'semantic' })
        }
      }
      return merged.slice(0, limit)
    }

    connection.fetch.register({
      path: '/api/my-memory-graph',
      methods: ['POST'],
      requestBody: 'buffered',
      async fetch(request) {
        if (request.method !== 'POST') return new Response('method not allowed', { status: 405 })
        let message
        try { message = await request.json() } catch { return new Response('body is not JSON', { status: 400 }) }
        const rpcId = typeof message.rpcId === 'string' ? message.rpcId : 'invalid'
        const call = message.payload
        if (message.type !== 'client-request' || typeof message.rpcId !== 'string' ||
            message.method !== 'my-memory-graph' || !call || typeof call.method !== 'string') {
          return Response.json({ type: 'server-response', rpcId, result: { ok: false, error: { code: 'bad-request', message: 'Invalid request' } } })
        }
        try {
          const db = getDb(homedir(), projectDir)
          const p = call.payload || {}
          let value

          if (call.method === 'graph') {
            const allData = db.exportAll()
            value = {
              nodes: allData.memories.map(m => ({
                id: m.id, level: m.level,
                title: m.title || m.content.slice(0, 40),
                content: m.content.slice(0, 300),
                tags: m.tags || [], importance: m.importance || 1,
                project: m.project || null,
              })),
              edges: (allData.relations || []).map(r => ({
                from: r.from_id, to: r.to_id, type: r.relation_type,
              })),
            }
          }

          else if (call.method === 'stats') {
            value = db.getStats()
          }

          else if (call.method === 'search') {
            value = doSearch(db, p.query || '', {
              level: p.level, project: p.project, tag: p.tag,
              limit: p.limit || 20, vectorTopK: 5,
            })
          }

          else if (call.method === 'export') {
            if (p.format === 'markdown') {
              value = { format: 'markdown', content: db.exportMarkdown() + '\n\n' + db.exportExperiencesMarkdown() }
            } else {
              value = { format: 'json', content: JSON.stringify(db.exportAll(), null, 2) }
            }
          }

          else if (call.method === 'experiences') {
            value = db.listExperiences(p.project || null)
          }

          else if (call.method === 'createExperience') {
            const inserted = db.insertExperience({
              project: p.project || '通用',
              problem: p.problem || '',
              solution: p.solution || '',
              takeaways: p.takeaways || '',
              skill_name: p.skillName || null,
              tags: p.tags || [],
              importance: p.importance || 5,
            })
            value = inserted
          }

          else if (call.method === 'allMemories') {
            const allData = db.exportAll()
            value = allData.memories.map(m => ({
              id: m.id, level: m.level,
              title: m.title || m.content.slice(0, 40),
              content: m.content,
              tags: m.tags || [], importance: m.importance || 1,
              project: m.project || null, status: m.status,
              keywords: m.keywords || [],
              createdAt: m.created_at, updatedAt: m.updated_at,
            }))
          }

          else {
            return Response.json({ type: 'server-response', rpcId, result: { ok: false, error: { code: 'unknown-method', message: `Unknown method: ${call.method}` } } })
          }

          return Response.json({ type: 'server-response', rpcId, result: { ok: true, value } })
        } catch (e) {
          ctx.logger?.warn?.(`my-memory: RPC handler failed: ${e?.message ?? e}`)
          return Response.json({ type: 'server-response', rpcId, result: { ok: false, error: { code: 'handler-failed', message: e?.message ?? String(e) } } })
        }
      },
    })
    ctx.logger?.info?.('my-memory: 数据 RPC 端点已注册 /api/my-memory-graph')
    return () => {}
  } catch (e) {
    ctx.logger?.warn?.(`my-memory: 数据 RPC 端点注册失败: ${e?.message ?? e}`)
    return () => {}
  }
}

// ── 工具注册 ────────────────────────────────────────────────────────
/** 从 ToolRunContext 获取 db */
function dbFromExec(exec, projectDir) {
  const ws = workspaceOfAgent(exec?.agent)
  if (!ws) throw new Error('无法确定工作区')
  return getDb(ws, projectDir)
}

const textOutput = {
  schema: { type: 'object', additionalProperties: true, properties: { text: { type: 'string' } } },
  render: (_args, value) => [{
    type: 'text',
    text: typeof value === 'string' ? value : JSON.stringify(value ?? {}, null, 2),
  }],
}

function registerAllTools(ctx, projectDir, hitTopK, vectorTopK, summaryOpts = {}) {
  const disposers = []
  const {
    turnSummary = true,
    summaryWindow = 2,
    summaryHighMax = 6,
    timeZone = 'Asia/Shanghai',
    workspaceFilter = true,
  } = summaryOpts

  // memory_remember（新建；传 id 即修改，已吞并原 memory_update / memory_tag）
  disposers.push(ctx.tools.register({
    name: 'memory_remember',
    description: '写入一条记忆；传 id 则修改已有记忆（不再单独提供修改/打标签工具）。自动按 level+title 去重合并。',
    parameters: {
      type: 'object',
      additionalProperties: false,
      required: ['level'],
      properties: {
        id: { type: 'string', description: '要修改的记忆 id；不传就是新建' },
        level: { type: 'string', enum: LEVELS },
        title: { type: 'string', description: '记忆标题（≤80字）；新建必填' },
        content: { type: 'string', description: '记忆正文；新建必填' },
        importance: { type: 'number', description: '重要度 0-10' },
        keywords: { type: 'array', items: { type: 'string' }, description: '检索关键词' },
        tags: { type: 'array', items: { type: 'string' }, description: '分类标签' },
        project: { type: 'string', description: '项目名（逗号分隔多项目）' },
        subcategory: { type: 'string' },
        status: { type: 'string', enum: ['active', 'archived'] },
        goal: { type: 'string', description: '目标句（topic 层专用）' },
      },
    },
    output: textOutput,
    async execute(args, exec) {
      const db = dbFromExec(exec, projectDir)
      const ws = workspaceName(workspaceOfAgent(exec?.agent))
      const { id, level, ...rest } = args
      if (id) {
        db.update(level, id, rest)
        const found = db.findById(id)
        if (found) db.setVector(found.row.id, level, embedMemory(found.row))
        return { text: `已更新 [${level}] ${id}` }
      }
      if (!rest.title || !rest.content) return { text: '新建记忆必须给 title 和 content' }
      const filled = { ...rest, level, tags: autoFillTags(rest.tags, { workspace: ws }) }
      const inserted = db.insert(filled)
      db.setVector(inserted.id, inserted.level, embedMemory(inserted))
      return { text: `已记忆 [${level}] ${rest.title} (id: ${inserted.id})` }
    },
  }))

  // memory_search
  disposers.push(ctx.tools.register({
    name: 'memory_search',
    description: '双路检索记忆：BM25 关键词 + 向量语义相似度。',
    parameters: {
      type: 'object',
      additionalProperties: false,
      required: ['query'],
      properties: {
        query: { type: 'string', description: '检索词' },
        level: { type: 'string', enum: LEVELS },
        project: { type: 'string' },
        tag: { type: 'string', description: '按标签过滤' },
        limit: { type: 'number', description: '返回条数上限' },
        allWorkspaces: { type: 'boolean', description: '跨工作区检索（默认只查通用层 + 当前工作区）' },
      },
    },
    output: textOutput,
    async execute(args, exec) {
      const db = dbFromExec(exec, projectDir)
      const limit = args.limit ?? hitTopK + vectorTopK
      // 收集可检索记忆
      const searchLevels = args.level ? [args.level] : LEVELS
      let allSearchable = []
      for (const lv of searchLevels) {
        allSearchable.push(...db.listSearchable(lv))
      }
      // 项目锚定过滤
      if (args.project) {
        allSearchable = allSearchable.filter(m =>
          !m.project || m.project === '全局' || m.project.toLowerCase() === 'global' ||
          (m.project && m.project.split(',').map(s => s.trim()).includes(args.project))
        )
      }
      if (args.tag) {
        allSearchable = allSearchable.filter(m => m.tags.includes(args.tag))
      }
      // 工作区过滤（默认开启）：通用层 + 当前工作区；无 workspace 标签的旧数据保留
      if (workspaceFilter && !args.allWorkspaces) {
        const wsTag = `workspace:${workspaceName(workspaceOfAgent(exec?.agent))}`
        allSearchable = allSearchable.filter(m => {
          const tags = m.tags ?? []
          if (tags.includes('shared-global') || tags.includes('workspace-agnostic')) return true
          if (tags.includes(wsTag)) return true
          return !tags.some(t => typeof t === 'string' && t.startsWith('workspace:'))
        })
      }
      if (allSearchable.length === 0) return { text: '未找到相关记忆' }
      // BM25 关键词命中
      const bm25Hits = bm25Search(allSearchable, args.query, { topK: limit })
      // 向量语义命中
      const vectors = []
      for (const m of allSearchable) {
        let vec = db.getVector(m.id)
        if (!vec) { vec = embedMemory(m); db.setVector(m.id, m.level, vec) }
        vectors.push({ memoryId: m.id, level: m.level, vector: vec })
      }
      const queryVec = embed(args.query)
      const vecHits = vectorSearch(vectors, queryVec, { topK: vectorTopK })
      // 合并去重
      const seen = new Set()
      const merged = []
      for (const h of bm25Hits) {
        if (!seen.has(h.row.id)) { seen.add(h.row.id); merged.push({ ...h.row, score: h.score, source: 'keyword' }) }
      }
      for (const h of vecHits) {
        if (!seen.has(h.memoryId)) {
          seen.add(h.memoryId)
          const found = db.findById(h.memoryId)
          if (found) merged.push({ ...found.row, score: h.score, source: 'semantic' })
        }
      }
      if (merged.length === 0) return { text: '未找到相关记忆' }
      return { text: merged.slice(0, limit).map(h =>
        `[${h.level}] ${h.title ?? h.content.slice(0, 40)}\n  id: ${h.id} | importance: ${h.importance} | tags: ${(h.tags ?? []).join(', ')}\n  ${h.content.slice(0, 200)}`
      ).join('\n\n') }
    },
  }))

  // memory_read
  disposers.push(ctx.tools.register({
    name: 'memory_read',
    description: '按 id 读取单条记忆完整元数据。',
    parameters: {
      type: 'object',
      additionalProperties: false,
      required: ['id'],
      properties: {
        id: { type: 'string' },
        level: { type: 'string', enum: LEVELS },
      },
    },
    output: textOutput,
    async execute(args, exec) {
      const db = dbFromExec(exec, projectDir)
      const m = db.findById(args.id)
      if (!m) return { text: `未找到 id: ${args.id}` }
      // 只有真正被读出来用，才算"用上了"：命中次数 +1，同时刷新访问时间
      // findById 返回 { row, level }，id 在 m.row.id 上（早先写成 m.id 会绑定失败）
      db.bumpHit(m.level, m.row.id)
      return { text: JSON.stringify(m, null, 2) }
    },
  }))

  // memory_experience — 经验系统
  disposers.push(ctx.tools.register({
    name: 'memory_experience',
    description: '经验系统：将工程项目中遇到的问题和解决方案沉淀为经验包，支持创建/搜索/列出/更新/删除。AI 越用越聪明。',
    parameters: {
      type: 'object',
      additionalProperties: false,
      required: ['action'],
      properties: {
        action: { type: 'string', enum: ['create', 'search', 'list', 'get', 'update', 'delete'], description: '操作类型' },
        project: { type: 'string', description: '项目名（create 时必填，search/list 时可选过滤）' },
        problem: { type: 'string', description: '问题描述（create 时必填）' },
        solution: { type: 'string', description: '解决方案（create 时必填）' },
        takeaways: { type: 'string', description: '关键收获/可复用的洞察' },
        skill_name: { type: 'string', description: 'Skill 名称（将经验提升为可复用模式）' },
        tags: { type: 'array', items: { type: 'string' }, description: '标签' },
        importance: { type: 'number', description: '重要度 1-10' },
        id: { type: 'string', description: '经验 id（get/update/delete 时必填）' },
        query: { type: 'string', description: '搜索关键词（search 时必填）' },
        limit: { type: 'number', description: '返回条数上限' },
      },
    },
    output: textOutput,
    async execute(args, exec) {
      const db = dbFromExec(exec, projectDir)

      if (args.action === 'create') {
        if (!args.problem || !args.solution) return { text: '创建经验需要 problem 和 solution' }
        const exp = db.insertExperience({
          project: args.project ?? '通用',
          problem: args.problem,
          solution: args.solution,
          takeaways: args.takeaways ?? '',
          skill_name: args.skill_name ?? null,
          tags: args.tags ?? [],
          importance: args.importance ?? 5,
        })
        return { text: `已创建经验包 [${exp.project}] ${args.skill_name ?? args.problem.slice(0, 40)} (id: ${exp.id})` }
      }

      if (args.action === 'search') {
        const results = db.searchExperiences(args.query ?? '', { project: args.project, limit: args.limit ?? 10 })
        if (results.length === 0) return { text: '未找到相关经验' }
        return { text: results.map(e =>
          `【${e.skill_name ?? '经验'}】[${e.project}]\n  id: ${e.id} | importance: ${e.importance} | hits: ${e.hit_count}\n  问题: ${e.problem}\n  方案: ${e.solution}\n  收获: ${e.takeaways || '(无)'}`
        ).join('\n\n') }
      }

      if (args.action === 'list') {
        const results = db.listExperiences(args.project ?? null)
        if (results.length === 0) return { text: '无经验记录' }
        return { text: `共 ${results.length} 条经验:\n` + results.map(e =>
          `  [${e.project}] ${e.skill_name ?? e.problem.slice(0, 40)} (id: ${e.id}, hits: ${e.hit_count})`
        ).join('\n') }
      }

      if (args.action === 'get') {
        if (!args.id) return { text: '需要 id' }
        const exp = db.findExperience(args.id)
        if (!exp) return { text: `未找到经验 id: ${args.id}` }
        return { text: JSON.stringify(exp, null, 2) }
      }

      if (args.action === 'update') {
        if (!args.id) return { text: '需要 id' }
        const { id, action, ...updates } = args
        // 补了关键收获，就自动摘掉 auto-draft 标签，草案即成品
        if (typeof updates.takeaways === 'string' && updates.takeaways.trim().length > 0) {
          const cur = db.findExperience(id)
          const tags = Array.isArray(updates.tags)
            ? updates.tags
            : (cur?.tags ?? [])
          updates.tags = tags.filter(t => t !== 'auto-draft')
        }
        db.updateExperience(id, updates)
        return { text: `已更新经验 ${id}` }
      }

      if (args.action === 'delete') {
        if (!args.id) return { text: '需要 id' }
        db.deleteExperience(args.id)
        return { text: `已删除经验 ${args.id}` }
      }

      return { text: `未知操作: ${args.action}` }
    },
  }))

  // memory_progress — 进度行 / 交接单（替代原来的每轮长总结）
  disposers.push(ctx.tools.register({
    name: 'memory_progress',
    description: '写一行进度（kind=line，30 字内：做了什么→结论→下一步）或一份交接单（kind=handoff，300 字内：目标/做到哪/下一步/卡在哪）。新窗口开场会自动带出来。上下文到交接线时改写成 handoff。',
    parameters: {
      type: 'object',
      additionalProperties: false,
      required: ['content'],
      properties: {
        content: { type: 'string', description: '进度行（≤30字）或交接单（≤300字）正文' },
        kind: { type: 'string', enum: ['line', 'handoff'], description: '默认 line；换窗口前写 handoff' },
      },
    },
    output: textOutput,
    async execute(args, exec) {
      const db = dbFromExec(exec, projectDir)
      const ws = workspaceName(workspaceOfAgent(exec?.agent))
      const sid = sessionIdOfAgent(exec?.agent)
      const content = String(args.content ?? '').trim()
      const r = db.addProgress({
        workspace: ws,
        sessionId: sid,
        kind: args.kind === 'handoff' ? 'handoff' : 'line',
        content,
        localTime: localTimeString(Date.now(), timeZone),
      })
      if (!r) return { text: '进度内容为空，未写入' }
      return { text: `已记录${r.kind === 'handoff' ? '交接单' : '进度行'}（${r.local_time}）` }
    },
  }))

  // memory_now
  disposers.push(ctx.tools.register({
    name: 'memory_now',
    description: '获取当前本地时间（时区、星期、时间戳），以及最近一条对话总结的时间与间隔。',
    parameters: { type: 'object', additionalProperties: false, properties: {} },
    output: textOutput,
    async execute(_args, exec) {
      const db = dbFromExec(exec, projectDir)
      const ws = workspaceName(workspaceOfAgent(exec?.agent))
      const sid = sessionIdOfAgent(exec?.agent)
      const now = Date.now()
      const lines = [
        `当前时间：${localTimeString(now, timeZone)}`,
        `时间戳：${now}`,
        `时区：${timeZone}`,
      ]
      try {
        const last = latestSummaryAnywhere(db, { workspace: ws, sessionId: sid })
        if (last) {
          const mins = Math.max(0, Math.round((now - last.created_at) / 60000))
          lines.push(`最近一条总结：${last.local_time}（${mins} 分钟前，工作区 ${last.workspace}，${last.value}）`)
        }
      } catch { /* 总结表不可用不影响取时间 */ }
      return { text: lines.join('\n') }
    },
  }))

  // memory_context — 上下文占用
  disposers.push(ctx.tools.register({
    name: 'memory_context',
    description: '查看当前对话的上下文占用：已用多少 token、占窗口百分比、还剩多少。用于判断何时该写进度行或交接单。',
    parameters: { type: 'object', additionalProperties: false, properties: {} },
    output: textOutput,
    async execute(_args, exec) {
      const occ = readOccupancy(ctx, exec?.agent?.session)
      if (!occ) return { text: '读不到上下文占用（tokenMeter 不可用）。' }
      const advice = actionFor(occ.percent, { warnRatio: contextWarnPct, handoffRatio: contextHandoffPct })
      const tip = advice === 'handoff'
        ? `已到 ${contextHandoffPct}%：本轮结束前写交接单（目标 / 做到哪 / 下一步 / 卡在哪），然后换新窗口。`
        : advice === 'progress'
          ? `已到 ${contextWarnPct}%：开始收敛，结束前写一行进度。`
          : '余量充足，正常推进。'
      return { text: `${formatOccupancy(occ)}\n${tip}` }
    },
  }))

  return () => disposers.forEach(d => { try { d?.() } catch { } })
}