/**
 * my-memory — SQLite 数据层
 *
 * 七层记忆存储（soul/user/project/fact/lesson/topic/rules），每层一张表。
 * 在 meow-memory 架构基础上增强：
 *   - tags 列：自由标签数组，支持按标签过滤与聚合
 *   - memory_relations 表：记忆间关系图谱（引用/依赖/冲突/补充）
 *   - memory_vectors 表：轻量向量嵌入，支持语义检索
 *
 * id = 时间前缀（base36 毫秒 + 随机后缀），id 排序即创建顺序。
 * 驱动：node:sqlite（Node ≥22.5 内置）。
 */

import { randomUUID } from 'node:crypto'
import { mkdirSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { homedir } from 'node:os'
import { DatabaseSync } from 'node:sqlite'

export const Level = {
  SOUL: 'soul',
  USER: 'user',
  PROJECT: 'project',
  FACT: 'fact',
  LESSON: 'lesson',
  TOPIC: 'topic',
  RULES: 'rules',
}

export const LEVELS = Object.values(Level)

export const LEVEL_LABELS = {
  soul: 'AI 自身',
  user: '用户信息与偏好',
  project: '项目',
  fact: '原子事实',
  lesson: '教训与纠正',
  topic: '进行中话题',
  rules: '设计原则与行为准则',
}

/** 关系类型 */
export const RELATION_TYPES = ['references', 'depends-on', 'conflicts', 'supplements', 'evolves']

/** 时间前缀 id：base36(毫秒,9位) + '-' + 26 位随机 = 36 字符 */
export function newId(now = Date.now()) {
  const t = now.toString(36).padStart(9, '0')
  return t + '-' + randomUUID().replace(/-/g, '').slice(0, 26)
}

const COMMON_COLS = `
  id TEXT PRIMARY KEY,
  title TEXT,
  content TEXT NOT NULL,
  importance INTEGER NOT NULL DEFAULT 1,
  keywords TEXT NOT NULL DEFAULT '[]',
  tags TEXT NOT NULL DEFAULT '[]',
  status TEXT NOT NULL DEFAULT 'active',
  source_session TEXT,
  hit_count INTEGER NOT NULL DEFAULT 0,
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL,
  last_accessed_at INTEGER
`

/** level → 建表语句 */
const SCHEMAS = {
  soul: `CREATE TABLE IF NOT EXISTS soul (${COMMON_COLS})`,
  user: `CREATE TABLE IF NOT EXISTS user (${COMMON_COLS})`,
  project: `CREATE TABLE IF NOT EXISTS project (${COMMON_COLS},
    project TEXT NOT NULL,
    subcategory TEXT)`,
  fact: `CREATE TABLE IF NOT EXISTS fact (${COMMON_COLS},
    project TEXT)`,
  lesson: `CREATE TABLE IF NOT EXISTS lesson (${COMMON_COLS},
    corrected INTEGER NOT NULL DEFAULT 0,
    project TEXT)`,
  topic: `CREATE TABLE IF NOT EXISTS topic (${COMMON_COLS},
    goal TEXT,
    project TEXT)`,
  rules: `CREATE TABLE IF NOT EXISTS rules (${COMMON_COLS},
    project TEXT)`,
}

/** 记忆库路径：跨工作区共享，固定在 ~/.my-memory/memory.db */
export function memoryDbPath(_workspace, dir = '.my-memory') {
  return join(homedir(), dir, 'memory.db')
}

export class MemoryDb {
  constructor(path) {
    mkdirSync(dirname(path), { recursive: true })
    this.db = new DatabaseSync(path)
    this.db.exec('PRAGMA journal_mode = WAL')
    this.db.exec('PRAGMA busy_timeout = 5000')
    for (const level of LEVELS) this.db.exec(SCHEMAS[level])
    this.db.exec(`CREATE TABLE IF NOT EXISTS memory_relations (
      id TEXT PRIMARY KEY,
      from_id TEXT NOT NULL,
      to_id TEXT NOT NULL,
      relation_type TEXT NOT NULL,
      note TEXT,
      created_at INTEGER NOT NULL,
      UNIQUE(from_id, to_id, relation_type)
    )`)
    this.db.exec(`CREATE INDEX IF NOT EXISTS idx_rel_from ON memory_relations(from_id)`)
    this.db.exec(`CREATE INDEX IF NOT EXISTS idx_rel_to ON memory_relations(to_id)`)
    this.db.exec(`CREATE TABLE IF NOT EXISTS memory_vectors (
      memory_id TEXT PRIMARY KEY,
      level TEXT NOT NULL,
      vector TEXT NOT NULL,
      updated_at INTEGER NOT NULL
    )`)
    this.db.exec(`CREATE TABLE IF NOT EXISTS dream_log (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      run_at INTEGER NOT NULL,
      summary TEXT,
      changes TEXT
    )`)
    // 进度行 / 交接单：替代冗长的每轮总结，供新窗口开场接续
    this.db.exec(`CREATE TABLE IF NOT EXISTS progress (
      id TEXT PRIMARY KEY,
      workspace TEXT,
      session_id TEXT,
      kind TEXT NOT NULL DEFAULT 'line',
      content TEXT NOT NULL,
      created_at INTEGER NOT NULL,
      local_time TEXT
    )`)
    this.db.exec(`CREATE INDEX IF NOT EXISTS idx_progress_ws ON progress(workspace, created_at DESC)`)
    // 经验系统：工程项目经验包（问题→解决方案→skill）
    this.db.exec(`CREATE TABLE IF NOT EXISTS experiences (
      id TEXT PRIMARY KEY,
      project TEXT NOT NULL,
      problem TEXT NOT NULL,
      solution TEXT NOT NULL,
      takeaways TEXT NOT NULL DEFAULT '',
      skill_name TEXT,
      tags TEXT NOT NULL DEFAULT '[]',
      importance INTEGER NOT NULL DEFAULT 5,
      hit_count INTEGER NOT NULL DEFAULT 0,
      created_at INTEGER NOT NULL,
      updated_at INTEGER NOT NULL
    )`)
    this.db.exec(`CREATE INDEX IF NOT EXISTS idx_exp_project ON experiences(project)`)
    this.db.exec(`CREATE INDEX IF NOT EXISTS idx_exp_tags ON experiences(tags)`)
    this.upgrade()
  }

  /** 幂等升级：补缺失的列 */
  upgrade() {
    for (const level of LEVELS) {
      const cols = new Set(
        (this.db.prepare(`PRAGMA table_info(${level})`).all()).map(c => c.name)
      )
      if (!cols.has('tags')) {
        this.db.exec(`ALTER TABLE ${level} ADD COLUMN tags TEXT NOT NULL DEFAULT '[]'`)
      }
    }
  }

  /** 新库判定 */
  isFresh() {
    const row = this.db.prepare('SELECT COUNT(*) AS n FROM soul').get()
    return row.n === 0
  }

  /** 插入记忆 */
  insert(row) {
    const now = Date.now()
    const full = {
      id: row.id ?? newId(now),
      level: row.level,
      title: row.title ?? null,
      content: row.content,
      importance: row.importance ?? 1,
      keywords: row.keywords ?? [],
      tags: row.tags ?? [],
      status: row.status ?? 'active',
      corrected: row.corrected ?? 0,
      project: row.project ?? null,
      subcategory: row.subcategory ?? null,
      goal: row.goal ?? null,
      source_session: row.source_session ?? null,
      hit_count: row.hit_count ?? 0,
      created_at: row.created_at ?? now,
      updated_at: row.updated_at ?? now,
      last_accessed_at: row.last_accessed_at ?? null,
    }
    const extraCols = this._extraCols(full.level)
    this.db.prepare(
      `INSERT INTO ${full.level} (id, title, content, importance, keywords, tags, status, source_session, hit_count, created_at, updated_at, last_accessed_at${extraCols.names})
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?${extraCols.placeholders})`
    ).run(
      full.id, full.title, full.content, full.importance,
      JSON.stringify(full.keywords), JSON.stringify(full.tags),
      full.status, full.source_session, full.hit_count,
      full.created_at, full.updated_at, full.last_accessed_at,
      ...extraCols.values(full)
    )
    return full
  }

  _extraCols(level) {
    if (level === 'project') return {
      names: ', project, subcategory',
      placeholders: ', ?, ?',
      values: r => [r.project ?? '', r.subcategory],
    }
    if (level === 'fact' || level === 'rules') return {
      names: ', project', placeholders: ', ?', values: r => [r.project],
    }
    if (level === 'lesson') return {
      names: ', corrected, project', placeholders: ', ?, ?', values: r => [r.corrected, r.project],
    }
    if (level === 'topic') return {
      names: ', goal, project', placeholders: ', ?, ?', values: r => [r.goal, r.project],
    }
    return { names: '', placeholders: '', values: () => [] }
  }

  /** 从数据库行还原为对象 */
  fromRow(level, r) {
    return {
      id: r.id,
      level,
      title: r.title,
      content: r.content,
      importance: r.importance,
      keywords: this._parseJson(r.keywords),
      tags: this._parseJson(r.tags),
      status: r.status,
      corrected: r.corrected ?? 0,
      project: r.project ?? null,
      subcategory: r.subcategory ?? null,
      goal: r.goal ?? null,
      source_session: r.source_session,
      hit_count: r.hit_count,
      created_at: r.created_at,
      updated_at: r.updated_at,
      last_accessed_at: r.last_accessed_at ?? null,
    }
  }

  _parseJson(s) {
    try { return JSON.parse(s) } catch { return [] }
  }

  /** 按 id 查找（跨表） */
  findById(id) {
    const prefix = id.length < 36
    for (const level of LEVELS) {
      const sql = prefix ? `SELECT * FROM ${level} WHERE id LIKE ?` : `SELECT * FROM ${level} WHERE id = ?`
      const r = this.db.prepare(sql).get(prefix ? `${id}%` : id)
      if (r) return { row: this.fromRow(level, r), level }
    }
    return undefined
  }

  /** 更新记忆 */
  update(level, id, patch) {
    const sets = []
    const args = []
    const push = (col, val) => { sets.push(`${col} = ?`); args.push(val) }
    if (patch.content !== undefined) push('content', patch.content)
    if (patch.title !== undefined) push('title', patch.title)
    if (patch.importance !== undefined) push('importance', patch.importance)
    if (patch.keywords !== undefined) push('keywords', JSON.stringify(patch.keywords))
    if (patch.tags !== undefined) push('tags', JSON.stringify(patch.tags))
    if (patch.status !== undefined) push('status', patch.status)
    if (patch.corrected !== undefined && level === 'lesson') push('corrected', patch.corrected)
    if (patch.project !== undefined && ['project', 'fact', 'lesson', 'rules', 'topic'].includes(level)) push('project', patch.project)
    if (patch.subcategory !== undefined && level === 'project') push('subcategory', patch.subcategory)
    if (patch.goal !== undefined && level === 'topic') push('goal', patch.goal)
    if (sets.length === 0) return false
    push('updated_at', Date.now())
    let targetId = id
    if (id.length < 36) {
      const matches = this.db.prepare(`SELECT id FROM ${level} WHERE id LIKE ?`).all(`${id}%`)
      if (matches.length !== 1) return false
      targetId = matches[0].id
    }
    const res = this.db.prepare(`UPDATE ${level} SET ${sets.join(', ')} WHERE id = ?`).run(...args, targetId)
    return res.changes > 0
  }

  // ── 进度行 / 交接单 ──────────────────────────────────────────

  /** 写一条进度行（kind='line'）或交接单（kind='handoff'） */
  addProgress({ workspace, sessionId, kind = 'line', content, createdAt, localTime } = {}) {
    if (!content) return null
    const at = createdAt ?? Date.now()
    const id = newId(at)
    this.db.prepare(`INSERT INTO progress (id, workspace, session_id, kind, content, created_at, local_time)
      VALUES (?, ?, ?, ?, ?, ?, ?)`)
      .run(id, workspace ?? null, sessionId ?? null, kind, content, at, localTime ?? null)
    return { id, kind, content, created_at: at, workspace: workspace ?? null, local_time: localTime ?? null }
  }

  /** 最近一条进度记录（可按工作区、类型过滤） */
  latestProgress({ workspace, kind } = {}) {
    return this._progressQuery({ workspace, kind, limit: 1 })[0] ?? null
  }

  /** 最近若干条进度记录 */
  recentProgress({ workspace, kind, limit = 3 } = {}) {
    return this._progressQuery({ workspace, kind, limit })
  }

  _progressQuery({ workspace, kind, limit = 1 } = {}) {
    const conds = []
    const args = []
    if (workspace) { conds.push('workspace = ?'); args.push(workspace) }
    if (kind) { conds.push('kind = ?'); args.push(kind) }
    const where = conds.length ? `WHERE ${conds.join(' AND ')}` : ''
    const n = Math.max(1, Math.min(50, Number(limit) || 1))
    return this.db.prepare(`SELECT * FROM progress ${where} ORDER BY created_at DESC LIMIT ${n}`).all(...args)
  }

  /** 添加标签 */
  addTags(level, id, tags) {
    const found = this.findById(id)
    if (!found) return false
    const existing = new Set(found.row.tags)
    for (const t of tags) existing.add(t)
    return this.update(level, found.row.id, { tags: [...existing] })
  }

  /** 移除标签 */
  removeTags(level, id, tags) {
    const found = this.findById(id)
    if (!found) return false
    const existing = new Set(found.row.tags)
    for (const t of tags) existing.delete(t)
    return this.update(level, found.row.id, { tags: [...existing] })
  }

  /** 按标签查找 */
  findByTag(tag, level) {
    const results = []
    const levels = level ? [level] : LEVELS
    for (const lv of levels) {
      const rows = this.db.prepare(`SELECT * FROM ${lv} WHERE tags LIKE ?`).all(`%"${tag}"%`)
      for (const r of rows) results.push(this.fromRow(lv, r))
    }
    return results
  }

  /** 列出所有标签及其计数 */
  listTags() {
    const tagMap = new Map()
    for (const level of LEVELS) {
      const rows = this.db.prepare(`SELECT tags FROM ${level}`).all()
      for (const r of rows) {
        for (const t of this._parseJson(r.tags)) {
          tagMap.set(t, (tagMap.get(t) ?? 0) + 1)
        }
      }
    }
    return [...tagMap.entries()].sort((a, b) => b[1] - a[1]).map(([tag, count]) => ({ tag, count }))
  }

  /** 列出某层记忆 */
  list(level, opts = {}) {
    const where = []
    const args = []
    if (opts.status) { where.push('status = ?'); args.push(opts.status) }
    if (opts.project !== undefined && ['project', 'fact', 'lesson', 'rules', 'topic'].includes(level)) {
      where.push('project = ?'); args.push(opts.project)
    }
    if (opts.tag) { where.push('tags LIKE ?'); args.push(`%"${opts.tag}"%`) }
    const sql = `SELECT * FROM ${level}${where.length ? ' WHERE ' + where.join(' AND ') : ''} ORDER BY created_at DESC`
    const rows = this.db.prepare(sql).all(...args)
    return rows.map(r => this.fromRow(level, r))
  }

  /** 全部 active 条目 */
  allActive() {
    const out = {}
    for (const level of LEVELS) out[level] = this.list(level, { status: 'active' })
    return out
  }

  /** 可检索条目 */
  listSearchable(level) {
    return this.list(level, { status: 'active' })
  }

  bumpHit(level, id) {
    this.db.prepare(`UPDATE ${level} SET hit_count = hit_count + 1, last_accessed_at = ? WHERE id = ?`).run(Date.now(), id)
  }

  count(level) {
    return this.db.prepare(`SELECT COUNT(*) AS n FROM ${level}`).get().n
  }

  /** 全部项目名 */
  listProjectNames() {
    const names = new Set()
    for (const level of ['project', 'fact', 'lesson', 'topic', 'rules']) {
      const rows = this.db.prepare(`SELECT project FROM ${level} WHERE project IS NOT NULL AND project != ''`).all()
      for (const r of rows) {
        if (r.project && r.project !== '全局' && r.project.toLowerCase() !== 'global') {
          for (const n of r.project.split(',').map(s => s.trim()).filter(s => s)) names.add(n)
        }
      }
    }
    return [...names].sort()
  }

  // ── 关系图谱 ──────────────────────────────────────────────────────────

  addRelation(fromId, toId, relationType, note = '') {
    if (!RELATION_TYPES.includes(relationType)) throw new Error(`未知关系类型: ${relationType}`)
    try {
      this.db.prepare(
        `INSERT INTO memory_relations (id, from_id, to_id, relation_type, note, created_at)
         VALUES (?, ?, ?, ?, ?, ?)
         ON CONFLICT(from_id, to_id, relation_type) DO UPDATE SET note = excluded.note`
      ).run(newId(), fromId, toId, relationType, note, Date.now())
      return true
    } catch { return false }
  }

  removeRelation(fromId, toId, relationType) {
    const res = this.db.prepare(
      `DELETE FROM memory_relations WHERE from_id = ? AND to_id = ? AND relation_type = ?`
    ).run(fromId, toId, relationType)
    return res.changes > 0
  }

  /** 获取某记忆的所有关系 */
  getRelations(memoryId) {
    const outgoing = this.db.prepare(
      `SELECT * FROM memory_relations WHERE from_id = ?`
    ).all(memoryId)
    const incoming = this.db.prepare(
      `SELECT * FROM memory_relations WHERE to_id = ?`
    ).all(memoryId)
    return { outgoing, incoming }
  }

  /** 获取全部关系（图谱可视化） */
  getAllRelations() {
    return this.db.prepare(`SELECT * FROM memory_relations ORDER BY created_at DESC`).all()
  }

  // ── 向量存储 ──────────────────────────────────────────────────────────

  setVector(memoryId, level, vector) {
    this.db.prepare(
      `INSERT INTO memory_vectors (memory_id, level, vector, updated_at)
       VALUES (?, ?, ?, ?)
       ON CONFLICT(memory_id) DO UPDATE SET vector = excluded.vector, updated_at = excluded.updated_at`
    ).run(memoryId, level, JSON.stringify(vector), Date.now())
  }

  getVector(memoryId) {
    const r = this.db.prepare(`SELECT vector FROM memory_vectors WHERE memory_id = ?`).get(memoryId)
    return r ? this._parseJson(r.vector) : null
  }

  /** 获取全部向量（语义检索用） */
  getAllVectors() {
    return this.db.prepare(`SELECT memory_id, level, vector FROM memory_vectors`).all()
      .map(r => ({ memoryId: r.memory_id, level: r.level, vector: this._parseJson(r.vector) }))
  }

  // ── 统计 ──────────────────────────────────────────────────────────────

  getStats() {
    const stats = { levels: {}, total: 0, tags: [], relations: 0, topHit: [], recentActivity: [], experiences: 0 }
    for (const level of LEVELS) {
      const count = this.count(level)
      stats.levels[level] = count
      stats.total += count
    }
    stats.experiences = this.db.prepare(`SELECT COUNT(*) AS n FROM experiences`).get().n
    stats.total += stats.experiences
    stats.tags = this.listTags()
    stats.relations = this.db.prepare(`SELECT COUNT(*) AS n FROM memory_relations`).get().n
    // 热门记忆（按 hit_count）
    const hot = []
    for (const level of LEVELS) {
      const rows = this.db.prepare(`SELECT id, title, content, hit_count FROM ${level} WHERE hit_count > 0 ORDER BY hit_count DESC LIMIT 5`).all()
      hot.push(...rows.map(r => ({ ...r, level })))
    }
    stats.topHit = hot.sort((a, b) => b.hit_count - a.hit_count).slice(0, 10)
    // 最近活动
    for (const level of LEVELS) {
      const rows = this.db.prepare(`SELECT id, title, updated_at FROM ${level} ORDER BY updated_at DESC LIMIT 3`).all()
      stats.recentActivity.push(...rows.map(r => ({ ...r, level })))
    }
    stats.recentActivity.sort((a, b) => b.updated_at - a.updated_at).slice(0, 10)
    return stats
  }

  // ── 导出/导入 ────────────────────────────────────────────────────────

  exportAll() {
    const data = { version: 2, exportedAt: new Date().toISOString(), memories: [], relations: [], experiences: [] }
    for (const level of LEVELS) {
      const rows = this.db.prepare(`SELECT * FROM ${level}`).all()
      for (const r of rows) {
        const row = this.fromRow(level, r)
        data.memories.push({ ...row, level })
      }
    }
    data.relations = this.db.prepare(`SELECT * FROM memory_relations`).all()
    data.experiences = this.listExperiences()
    return data
  }

  exportMarkdown() {
    const lines = ['# 记忆导出', '', `导出时间: ${new Date().toISOString()}`, '']
    for (const level of LEVELS) {
      const rows = this.list(level)
      if (rows.length === 0) continue
      lines.push(`## ${LEVEL_LABELS[level]} (${rows.length})`, '')
      for (const r of rows) {
        lines.push(`### ${r.title ?? r.content.slice(0, 40)}`)
        lines.push(`- **ID**: ${r.id}`)
        lines.push(`- **重要性**: ${r.importance}`)
        lines.push(`- **关键词**: ${r.keywords.join(', ')}`)
        if (r.tags.length > 0) lines.push(`- **标签**: ${r.tags.join(', ')}`)
        if (r.project) lines.push(`- **项目**: ${r.project}`)
        lines.push(`- **状态**: ${r.status}`)
        lines.push(`- **内容**: ${r.content}`)
        if (r.goal) lines.push(`- **目标**: ${r.goal}`)
        lines.push('')
      }
    }
    return lines.join('\n')
  }

  exportExperiencesMarkdown() {
    const exps = this.listExperiences()
    if (exps.length === 0) return '无经验记录'
    const lines = ['# 经验包导出', '', `导出时间: ${new Date().toISOString()}`, `共 ${exps.length} 条经验`, '']
    const byProject = {}
    for (const e of exps) {
      const p = e.project || '(通用)'
      if (!byProject[p]) byProject[p] = []
      byProject[p].push(e)
    }
    for (const [project, items] of Object.entries(byProject)) {
      lines.push(`## ${project} (${items.length})`, '')
      for (const e of items) {
        lines.push(`### ${e.skill_name ?? '经验'} — ${e.problem.slice(0, 60)}`)
        lines.push(`- **ID**: ${e.id}`)
        lines.push(`- **问题**: ${e.problem}`)
        lines.push(`- **解决方案**: ${e.solution}`)
        if (e.takeaways) lines.push(`- **关键收获**: ${e.takeaways}`)
        if (e.skill_name) lines.push(`- **Skill 名**: ${e.skill_name}`)
        if (e.tags.length > 0) lines.push(`- **标签**: ${e.tags.join(', ')}`)
        lines.push(`- **重要性**: ${e.importance} | **命中**: ${e.hit_count}`)
        lines.push('')
      }
    }
    return lines.join('\n')
  }

  importData(data) {
    let imported = 0
    for (const mem of data.memories ?? []) {
      if (!LEVELS.includes(mem.level)) continue
      const existing = this.findById(mem.id)
      if (existing) continue
      this.insert(mem)
      imported++
    }
    for (const rel of data.relations ?? []) {
      try { this.addRelation(rel.from_id, rel.to_id, rel.relation_type, rel.note ?? '') } catch { }
    }
    for (const exp of data.experiences ?? []) {
      if (!this.findExperience(exp.id)) {
        this.insertExperience(exp)
        imported++
      }
    }
    return imported
  }

  logDream(summary, changes) {
    this.db.prepare('INSERT INTO dream_log (run_at, summary, changes) VALUES (?, ?, ?)').run(Date.now(), summary, JSON.stringify(changes))
  }

  // ── 经验系统 ────────────────────────────────────────────────────────

  /** 创建经验包 */
  insertExperience(row) {
    const now = Date.now()
    const id = row.id ?? newId(now)
    this.db.prepare(
      `INSERT INTO experiences (id, project, problem, solution, takeaways, skill_name, tags, importance, hit_count, created_at, updated_at)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)`
    ).run(
      id, row.project ?? '', row.problem ?? '', row.solution ?? '',
      row.takeaways ?? '', row.skill_name ?? null,
      JSON.stringify(row.tags ?? []), row.importance ?? 5,
      now, now
    )
    return { id, ...row }
  }

  /** 按关键词搜索经验（BM25 风格简易匹配） */
  searchExperiences(query, opts = {}) {
    const limit = opts.limit ?? 10
    const project = opts.project
    let sql = `SELECT * FROM experiences WHERE 1=1`
    const params = []
    if (project) { sql += ` AND project = ?`; params.push(project) }
    sql += ` ORDER BY importance DESC, updated_at DESC LIMIT ?`
    params.push(limit)
    const rows = this.db.prepare(sql).all(...params)
    if (!query) return rows.map(r => this._expFromRow(r))
    // 简易关键词匹配排序
    const qLower = query.toLowerCase()
    const scored = rows.map(r => {
      let score = 0
      const text = `${r.problem} ${r.solution} ${r.takeaways} ${r.skill_name ?? ''}`.toLowerCase()
      for (const word of qLower.split(/\s+/)) {
        if (word.length > 0 && text.includes(word)) score += 1
      }
      return { row: r, score }
    }).filter(s => s.score > 0).sort((a, b) => b.score - a.score)
    return scored.map(s => this._expFromRow(s.row))
  }

  /** 列出所有经验（按项目分组可选） */
  listExperiences(project = null) {
    let sql = `SELECT * FROM experiences`
    const params = []
    if (project) { sql += ` WHERE project = ?`; params.push(project) }
    sql += ` ORDER BY updated_at DESC`
    return this.db.prepare(sql).all(...params).map(r => this._expFromRow(r))
  }

  /** 按 id 查找经验 */
  findExperience(id) {
    const row = this.db.prepare(`SELECT * FROM experiences WHERE id = ?`).get(id)
    return row ? this._expFromRow(row) : null
  }

  /** 更新经验 */
  updateExperience(id, updates) {
    const now = Date.now()
    const fields = []
    const params = []
    for (const [k, v] of Object.entries(updates)) {
      if (['project', 'problem', 'solution', 'takeaways', 'skill_name', 'importance'].includes(k)) {
        fields.push(`${k} = ?`); params.push(v)
      } else if (k === 'tags') {
        fields.push(`tags = ?`); params.push(JSON.stringify(v))
      }
    }
    if (fields.length === 0) return
    fields.push(`updated_at = ?`); params.push(now)
    params.push(id)
    this.db.prepare(`UPDATE experiences SET ${fields.join(', ')} WHERE id = ?`).run(...params)
  }

  /** 经验命中计数 +1 */
  bumpExperience(id) {
    this.db.prepare(`UPDATE experiences SET hit_count = hit_count + 1, updated_at = ? WHERE id = ?`).run(Date.now(), id)
  }

  /** 删除经验 */
  deleteExperience(id) {
    this.db.prepare(`DELETE FROM experiences WHERE id = ?`).run(id)
  }

  _expFromRow(r) {
    return {
      ...r,
      tags: JSON.parse(r.tags || '[]'),
    }
  }

  close() {
    try { this.db.close() } catch { }
  }
}

/** 全局 DB 实例缓存（按路径） */
const dbCache = new Map()

export function getDb(workspace, dir = '.my-memory') {
  const path = memoryDbPath(workspace, dir)
  let db = dbCache.get(path)
  if (!db) {
    db = new MemoryDb(path)
    dbCache.set(path, db)
  }
  return db
}

export function closeAllDbs() {
  for (const db of dbCache.values()) db.close()
  dbCache.clear()
}
