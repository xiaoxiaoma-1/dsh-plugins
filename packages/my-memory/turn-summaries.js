/**
 * my-memory — 每轮对话总结（价值门控滚动窗口）
 *
 * 设计要点（2026-10-29 定稿）：
 * 1. 时间只做「排序 + 显示」，不做淘汰依据；淘汰按 value。
 * 2. value: high=关键决策/新事实/用户纠正/明确结论；normal=有实质信息；none=纯确认/寒暄/重复。
 * 3. none 不占位、不触发淘汰（垃圾轮挤不掉好东西）。
 * 4. 窗口 = 最近 window 条 normal/high + 最多 1 条最新（最新那条不参与淘汰）。
 * 5. high 单独保留最多 highMax 条，超出归档。
 * 6. 本轮不完整（complete=false，撞 token 上限）→ 不淘汰任何东西。
 * 7. 淘汰只标 archived，永不物理删除。
 * 8. 时间存两种形态：毫秒 created_at（机器用）+ local_time（人可读）。
 */

import { newId } from './db.js'

const ensured = new WeakSet()

const DDL = `
CREATE TABLE IF NOT EXISTS turn_summaries (
  id TEXT PRIMARY KEY,
  workspace TEXT NOT NULL DEFAULT '',
  session_id TEXT NOT NULL DEFAULT '',
  turn_no INTEGER NOT NULL DEFAULT 0,
  created_at INTEGER NOT NULL,
  local_time TEXT NOT NULL DEFAULT '',
  content TEXT NOT NULL,
  value TEXT NOT NULL DEFAULT 'normal',
  complete INTEGER NOT NULL DEFAULT 1,
  status TEXT NOT NULL DEFAULT 'active',
  archived_reason TEXT
)`

/** 懒建表（每个库句柄一次） */
export function ensureSummaryTable(db) {
  if (!db || !db.db) return false
  if (ensured.has(db)) return true
  db.db.exec(DDL)
  db.db.exec('CREATE INDEX IF NOT EXISTS idx_ts_ws_sess ON turn_summaries(workspace, session_id, created_at DESC)')
  db.db.exec('CREATE INDEX IF NOT EXISTS idx_ts_created ON turn_summaries(created_at DESC)')
  ensured.add(db)
  return true
}

/** 工作区 = 目录名（desktop / td ...） */
export function workspaceName(cwd) {
  if (typeof cwd !== 'string' || cwd.length === 0) return 'unknown'
  const parts = cwd.replace(/[\\/]+$/, '').split(/[\\/]/)
  const last = parts[parts.length - 1]
  return last || 'unknown'
}

/** 人可读时间：2026-10-29 03:15 (周四) Asia/Shanghai */
export function localTimeString(ts = Date.now(), timeZone = 'Asia/Shanghai') {
  try {
    const fmt = new Intl.DateTimeFormat('zh-CN', {
      timeZone,
      year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit', hour12: false, weekday: 'short',
    })
    const p = {}
    for (const part of fmt.formatToParts(new Date(ts))) p[part.type] = part.value
    return `${p.year}-${p.month}-${p.day} ${p.hour}:${p.minute} (${p.weekday}) ${timeZone}`
  } catch {
    return new Date(ts).toISOString()
  }
}

function counts(db, workspace, sessionId) {
  const rows = db.db.prepare(
    `SELECT value, COUNT(*) AS n FROM turn_summaries
     WHERE workspace = ? AND session_id = ? AND status = 'active' GROUP BY value`
  ).all(workspace, sessionId)
  const out = { high: 0, normal: 0, none: 0 }
  for (const r of rows) out[r.value] = r.n
  return out
}

/**
 * 按价值滚动：归档多余的旧总结。返回归档条数。
 * 窗口 = 最近 keepNormal 条 normal/high + high 最多 keepHigh 条。
 * none 永不因滚动被归档（只留作流水）。
 */
export function rollTurnSummaries(db, { workspace = 'unknown', sessionId = 'unknown', keepNormal = 2, keepHigh = 6 } = {}) {
  if (!ensureSummaryTable(db)) return 0
  const rows = db.db.prepare(
    `SELECT id, value, created_at FROM turn_summaries
     WHERE workspace = ? AND session_id = ? AND status = 'active'
     ORDER BY created_at DESC`
  ).all(workspace, sessionId)

  const high = rows.filter(r => r.value === 'high')
  const normal = rows.filter(r => r.value === 'normal')
  const losers = [
    ...normal.slice(keepNormal).map(r => ({ ...r, reason: `窗口外（normal 保留最近 ${keepNormal} 条）` })),
    ...high.slice(keepHigh).map(r => ({ ...r, reason: `高价值超出上限 ${keepHigh} 条` })),
  ]
  if (!losers.length) return 0
  const stmt = db.db.prepare(`UPDATE turn_summaries SET status = 'archived', archived_reason = ? WHERE id = ?`)
  for (const r of losers) stmt.run(r.reason, r.id)
  return losers.length
}

/** 写入一条本轮总结 */
export function insertTurnSummary(db, opts = {}) {
  if (!ensureSummaryTable(db)) throw new Error('记忆库不可用')
  const {
    workspace = 'unknown', sessionId = 'unknown', content = '',
    value = 'normal', complete = true,
    window = 2, highMax = 6, timeZone = 'Asia/Shanghai',
  } = opts
  const v = ['high', 'normal', 'none'].includes(value) ? value : 'normal'
  const now = Date.now()
  const turnNo = (db.db.prepare('SELECT COUNT(*) AS n FROM turn_summaries WHERE session_id = ?').get(sessionId)?.n ?? 0) + 1
  const id = newId(now)
  const local = localTimeString(now, timeZone)
  db.db.prepare(
    `INSERT INTO turn_summaries (id, workspace, session_id, turn_no, created_at, local_time, content, value, complete, status)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'active')`
  ).run(id, workspace, sessionId, turnNo, now, local, String(content), v, complete ? 1 : 0)

  let archived = 0
  // none 不占位、不淘汰；不完整不淘汰
  if (v !== 'none' && complete) {
    archived = rollTurnSummaries(db, { workspace, sessionId, keepNormal: window, keepHigh: highMax })
  }
  return { id, turnNo, localTime: local, archived, counts: counts(db, workspace, sessionId) }
}

/** 取最近 N 条（默认只取有营养的，不含 none） */
export function recentTurnSummaries(db, { workspace = 'unknown', sessionId = 'unknown', limit = 2, includeNone = false } = {}) {
  if (!ensureSummaryTable(db)) return []
  const cond = includeNone ? '' : " AND value <> 'none'"
  return db.db.prepare(
    `SELECT * FROM turn_summaries
     WHERE workspace = ? AND session_id = ? AND status = 'active'${cond}
     ORDER BY created_at DESC LIMIT ?`
  ).all(workspace, sessionId, limit)
}

/**
 * 构建【上次聊到哪】注入文本。优先级：
 * 1) 当前工作区 + 当前会话 最近 window 条
 * 2) 当前工作区其他会话 最近 1 条
 * 3) 跨工作区 最近 1 条（必须标注来源）
 */
export function buildSummaryInjection(db, { workspace = 'unknown', sessionId = 'unknown', window = 2, crossWorkspace = true } = {}) {
  if (!ensureSummaryTable(db)) return ''
  const local = recentTurnSummaries(db, { workspace, sessionId, limit: window })
  if (local.length) {
    const lines = [`【上次聊到哪】（本会话最近 ${local.length} 条，工作区 ${workspace}）`]
    for (const r of local.slice().reverse()) {
      lines.push(`- ${r.local_time}｜第 ${r.turn_no} 轮｜${r.value}\n  ${r.content.replace(/\n/g, '\n  ')}`)
    }
    return lines.join('\n')
  }

  const other = db.db.prepare(
    `SELECT * FROM turn_summaries
     WHERE workspace = ? AND session_id <> ? AND status = 'active' AND value <> 'none'
     ORDER BY created_at DESC LIMIT 1`
  ).get(workspace, sessionId)
  if (other) {
    return `【上次聊到哪】（同工作区 ${workspace}，来自另一个会话 ${other.local_time}）\n- ${other.content}`
  }

  if (!crossWorkspace) return ''
  const cross = db.db.prepare(
    `SELECT * FROM turn_summaries
     WHERE workspace <> ? AND status = 'active' AND value <> 'none'
     ORDER BY created_at DESC LIMIT 1`
  ).get(workspace)
  if (cross) {
    return `【上次聊到哪】（注意：来自另一个工作区「${cross.workspace}」，${cross.local_time}）\n- ${cross.content}`
  }
  return ''
}

/** 判断本轮是否值得总结：有工具调用，或用户本轮说了足够多的话 */
export function shouldSummarizeThisTurn(events = [], { minUserChars = 30 } = {}) {
  let startIdx = -1
  for (let i = events.length - 1; i >= 0; i--) {
    if (events[i]?.type === 'turn/start') { startIdx = i; break }
  }
  if (startIdx < 0) return false
  let toolCalls = 0
  let userChars = 0
  for (let i = startIdx; i < events.length; i++) {
    const e = events[i]
    if (e?.type === 'tool/result') toolCalls++
    if (e?.type === 'user/message') {
      if (e.data?.source?.kind && e.data.source.kind !== 'user') continue
      const blocks = Array.isArray(e.data?.content) ? e.data.content : []
      for (const b of blocks) {
        if (b?.type === 'text' && typeof b.text === 'string') userChars += b.text.length
      }
    }
  }
  return toolCalls >= 1 || userChars >= minUserChars
}

/** 记忆写入时自动补机械标签（不含 content-type 猜测） */
export function autoFillTags(tags, { workspace = 'unknown' } = {}) {
  const out = Array.isArray(tags) ? [...tags] : []
  const push = t => { if (!out.includes(t)) out.push(t) }
  push('shared-global')
  push('workspace-agnostic')
  if (!out.some(t => typeof t === 'string' && t.startsWith('workspace:'))) push(`workspace:${workspace}`)
  if (!out.some(t => typeof t === 'string' && t.startsWith('content-type:'))) push('needs-review')
  return out
}

/** 最近一条总结的时间（给 memory_now 用） */
export function latestSummaryAnywhere(db, { workspace = 'unknown', sessionId = 'unknown' } = {}) {
  if (!ensureSummaryTable(db)) return null
  return db.db.prepare(
    `SELECT * FROM turn_summaries
     WHERE (workspace = ? AND session_id = ?) OR workspace = ?
     ORDER BY created_at DESC LIMIT 1`
  ).get(workspace, sessionId, workspace) ?? null
}
