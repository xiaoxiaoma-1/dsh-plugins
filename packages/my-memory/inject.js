/**
 * my-memory — 记忆注入
 *
 * 注入原则：只给"知道有这么条记忆"的索引，不给全文。
 *   - 首轮：各层标题索引（每条一行，按重要度截断）
 *   - 第二轮起：命中的标题 + 120 字摘要 + id，需要细节用 memory_read(id) 深读
 *
 * 这样首轮注入从原来的 ~47000 字符（约 3 万 token）压到 2000 字符量级。
 * 注入作为独立 plugin snapshot 消息，不改写用户 prompt。
 */

import { bm25Search } from './bm25.js'
import { vectorSearch, embed, embedMemory } from './embed.js'
import { LEVELS, LEVEL_LABELS } from './db.js'

/** 插件消息来源标记 */
export const PLUGIN_SOURCE = { kind: 'plugin:my-memory', producer: 'my-memory', form: 'snapshot' }

/** 各层索引条数上限（超出按重要度 + 命中次数取前 N） */
const INDEX_CAP = { soul: 20, user: 30, rules: 25, topic: 8 }

/** 单条索引的最大字数 */
const INDEX_CHARS = 40

/** 单条命中摘要的最大字数（摘要用于"判断要不要深读"，60 字够，比只给标题强） */
const HIT_CHARS = 60

/** 每轮最多注入几条命中（上游 meow-memory 只给 2 条，这里取 3） */
const HIT_MAX = 3

function clean(text) {
  return String(text ?? '').replace(/\s+/g, ' ').trim()
}

/** 一行索引：标题优先，无标题取正文开头 */
function oneLine(rec, max = INDEX_CHARS) {
  const src = clean(rec.title) || clean(rec.content)
  return src.length > max ? src.slice(0, max) + '…' : src
}

/** 重要度优先、其次命中次数、最后更新时间 */
function bySalience(a, b) {
  return (b.importance ?? 0) - (a.importance ?? 0)
    || (b.hit_count ?? 0) - (a.hit_count ?? 0)
    || (b.updated_at ?? 0) - (a.updated_at ?? 0)
}

/** 会话状态：记录已注入的 id、是否首轮 */
export class SessionState {
  constructor() {
    this.injected = false      // 首轮注入是否完成
    this.seenIds = new Set()   // 本会话已注入过的记忆 id
    this.messageCount = 0      // 用户消息计数
    this.toolSteps = 0         // 本轮工具步骤计数
    this.currentProject = null // 当前锚定项目
    this.occupancyNotified = 0 // 已提醒过的上下文档位（50 / 70），避免每轮重复提示
    this.corrections = []      // 本轮被用户纠正的原话（给经验包自动沉淀用）
  }
}

/** 全局会话状态表 */
const sessionStates = new Map()

export function getSessionState(sessionId) {
  let s = sessionStates.get(sessionId)
  if (!s) {
    s = new SessionState()
    sessionStates.set(sessionId, s)
  }
  return s
}

export function deleteSessionState(sessionId) {
  sessionStates.delete(sessionId)
}

/**
 * 构建首轮注入文本：各层标题索引 + 项目名 + 话题 + 工具导引。
 * 只给索引，不给正文；正文靠 memory_search / memory_read 按需取。
 */
export function buildFirstTurnInjection(db, titleMax = INDEX_CHARS) {
  const sections = []
  const active = db.allActive()

  const pushIndex = (label, rows, key) => {
    if (!Array.isArray(rows) || rows.length === 0) return
    const cap = INDEX_CAP[key] ?? 25
    const shown = [...rows].sort(bySalience).slice(0, cap)
    const hidden = rows.length - shown.length
    const head = hidden > 0
      ? `【${label}】（共 ${rows.length} 条，此处按重要度列前 ${shown.length} 条；细节用 memory_search 检索全文）`
      : `【${label}】（共 ${rows.length} 条；细节用 memory_search 检索全文）`
    sections.push([head, ...shown.map(r => `- ${oneLine(r, titleMax)}`)].join('\n'))
  }

  pushIndex('关于你（AI 自身）', active.soul, 'soul')
  pushIndex('关于用户', active.user, 'user')

  const globalRules = (active.rules ?? []).filter(r =>
    !r.project || r.project === '全局' || String(r.project).toLowerCase() === 'global')
  pushIndex('设计原则与行为准则', globalRules, 'rules')

  // 项目名压成一行，避免 90 个项目各占一行
  const projects = db.listProjectNames()
  if (projects.length > 0) {
    const shown = projects.slice(0, 40)
    const more = projects.length - shown.length
    sections.push(`【已知项目（共 ${projects.length} 个）】\n${shown.join('、')}${more > 0 ? ` 等 ${projects.length} 个` : ''}`)
  }

  if ((active.topic ?? []).length > 0) {
    const lines = ['【进行中的话题】']
    for (const t of active.topic.slice(0, INDEX_CAP.topic)) {
      const title = t.title ?? clean(t.content).slice(0, titleMax)
      const goal = t.goal ? `（目标：${clean(t.goal).slice(0, 50)}…）` : ''
      lines.push(`- ${title}${goal}`)
    }
    sections.push(lines.join('\n'))
  }

  // 工具使用导引（保持精简，只列用途，不展开用法）
  sections.push(`【记忆工具】
长期记忆与经验包都在库里，先检索再深读：
- memory_search：检索（关键词 + 语义双路），只回标题 + 摘要 + id
- memory_read：按 id 读全文，只有真正读了才算"用上"
- memory_remember：写入记忆；传 id 即修改
- memory_experience：经验包（怎么做某类事）
- memory_now：当前时间
- memory_context：当前上下文占用
七层：soul(AI自身) / user(用户) / project(项目) / fact(事实) / lesson(教训) / topic(话题) / rules(准则)`)

  return sections.join('\n\n')
}

/**
 * 构建关键词命中注入文本（第二轮起每条用户消息）。
 * 只给 id + 标题 + 120 字摘要；需要全文时由 AI 调 memory_read。
 */
export function buildHitInjection(db, query, opts = {}) {
  const { hitTopK = 3, vectorTopK = 5, project } = opts

  // 收集可检索记忆
  const searchableLevels = ['fact', 'lesson', 'rules', 'topic', 'project']
  let allSearchable = []
  for (const level of searchableLevels) {
    allSearchable.push(...db.listSearchable(level))
  }

  // 项目锚定过滤
  if (project) {
    allSearchable = allSearchable.filter(m =>
      !m.project || m.project === '全局' || m.project.toLowerCase() === 'global' ||
      (m.project && m.project.split(',').map(s => s.trim()).includes(project))
    )
  } else {
    // 未锚定只搜全局
    allSearchable = allSearchable.filter(m =>
      !m.project || m.project === '全局' || m.project.toLowerCase() === 'global'
    )
  }

  if (allSearchable.length === 0) return null

  // 工作区过滤：通用层 + 当前工作区（无 workspace 标签的旧数据保留）
  if (opts.workspaceFilter !== false && opts.workspace) {
    const wsTag = `workspace:${opts.workspace}`
    allSearchable = allSearchable.filter(m => {
      const tags = m.tags ?? []
      if (tags.includes('shared-global') || tags.includes('workspace-agnostic')) return true
      if (tags.includes(wsTag)) return true
      return !tags.some(t => typeof t === 'string' && t.startsWith('workspace:'))
    })
    if (allSearchable.length === 0) return null
  }

  // BM25 关键词命中
  const bm25Hits = bm25Search(allSearchable, query, { topK: hitTopK })

  // 向量语义命中
  const vectors = []
  for (const m of allSearchable) {
    let vec = db.getVector(m.id)
    if (!vec) {
      vec = embedMemory(m)
      db.setVector(m.id, m.level, vec)
    }
    vectors.push({ memoryId: m.id, level: m.level, vector: vec })
  }
  const queryVec = embed(query)
  const vecHits = vectorSearch(vectors, queryVec, { topK: vectorTopK })

  // 合并去重
  const seen = new Set()
  const hits = []
  for (const h of bm25Hits) {
    if (!seen.has(h.row.id)) {
      seen.add(h.row.id)
      hits.push({ row: h.row, score: h.score, source: 'keyword' })
    }
  }
  for (const h of vecHits) {
    if (!seen.has(h.memoryId)) {
      seen.add(h.memoryId)
      const found = db.findById(h.memoryId)
      if (found) {
        hits.push({ row: found.row, score: h.score, source: 'semantic' })
      }
    }
  }

  if (hits.length === 0) return null

  // 按分数排序后只留前 HIT_MAX 条：条数比字数更该省
  hits.sort((a, b) => (b.score ?? 0) - (a.score ?? 0))
  const picked = hits.slice(0, HIT_MAX)

  // 构建注入文本：id + 标题 + 60 字摘要，不给全文
  const lines = ['【可能相关的记忆（只有摘要；要看全文用 memory_read 传 id）】']
  for (const h of picked) {
    const r = h.row
    const label = LEVEL_LABELS[r.level] ?? r.level
    const title = clean(r.title)
    const body = clean(r.content)
    const brief = title && !body.startsWith(title) ? `${title}｜${body.slice(0, HIT_CHARS)}` : body.slice(0, HIT_CHARS)
    const ellipsis = body.length > HIT_CHARS ? '…' : ''
    lines.push(`- [${label}] id=${r.id} ${brief}${ellipsis}`)
  }
  return lines.join('\n')
}

/**
 * 新窗口开场：带出上次的进度行 + 最近一份交接单。
 * 这是"换窗口不断线"的主力，替代原来 200 字的每轮总结。
 */
export function buildProgressInjection(db, { workspace } = {}) {
  let handoff = null
  let lines = []
  try {
    handoff = db.latestProgress({ workspace, kind: 'handoff' })
    lines = db.recentProgress({ workspace, kind: 'line', limit: 2 }) ?? []
  } catch {
    return null
  }
  if (!handoff && lines.length === 0) return null
  const out = ['【上次进度】']
  if (handoff) {
    out.push(`交接单（${handoff.local_time ?? ''}）：${clean(handoff.content)}`)
  }
  for (const l of lines.slice().reverse()) {
    out.push(`- ${l.local_time ?? ''} ${clean(l.content)}`)
  }
  out.push('（接着往下做；如果方向已变，先说一句再改）')
  return out.join('\n')
}

/**
 * 项目锚定后注入一次"图纸"：这个项目的目标与关键约束。
 * 作用是防跑偏——每轮都看得到初衷，偏离超过 30 分就该主动提醒用户。
 */
export function buildProjectAnchor(db, project) {
  if (!project) return null
  let rows = []
  try {
    rows = (db.listSearchable('project') ?? []).filter(r => r.project === project)
  } catch {
    return null
  }
  if (rows.length === 0) return null
  const top = [...rows].sort(bySalience).slice(0, 2)
  const lines = [`【当前项目】${project}`]
  for (const r of top) {
    const title = clean(r.title) || clean(r.content).slice(0, 40)
    lines.push(`- ${title}：${clean(r.content).slice(0, 120)}…`)
  }
  lines.push('（这条是项目图纸；做的事明显偏离它就提醒用户，偏离大时先停下来问）')
  return lines.join('\n')
}

/**
 * 压缩后重注入：长期记忆索引 + 本会话查阅过的记忆摘要。
 */
export function buildReinjection(db, sessionState) {
  const sections = [buildFirstTurnInjection(db)]
  if (sessionState.seenIds.size > 0) {
    const lines = ['【本会话已查阅的记忆】']
    for (const id of sessionState.seenIds) {
      const found = db.findById(id)
      if (found) {
        lines.push(`- (${LEVEL_LABELS[found.level]}) ${oneLine(found.row, 60)}`)
      }
    }
    sections.push(lines.join('\n'))
  }
  return sections.join('\n\n')
}
