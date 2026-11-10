/**
 * my-memory — 记忆工具定义
 *
 * 八个工具：remember / search / read / update / tag / graph / export / stats
 * 使用 schemastery 定义参数 schema，通过 ctx.tools.register 注册。
 */

import z from '@deepseek-ai/schemastery'
import { LEVELS, LEVEL_LABELS, RELATION_TYPES } from './db.js'
import { bm25Search } from './bm25.js'
import { embed, embedMemory, vectorSearch } from './embed.js'

const levelDesc = `记忆层级：${LEVELS.join(' / ')}`

/**
 * 注册全部记忆工具。
 * @param {object} ctx - Cordis 上下文
 * @param {object} db - MemoryDb 实例
 * @param {object} config - 解析后的配置
 */
export function registerMemoryTools(ctx, db, config) {
  const disposers = []

  // ── memory_remember ──────────────────────────────────────────────
  disposers.push(ctx.tools.register({
    name: 'memory_remember',
    description: `写入一条记忆。${levelDesc}。自动去重合并：若同 level 下 content 高度相似则更新而非新建。`,
    parameters: z.object({
      content: z.string().describe('记忆内容（必填）'),
      level: z.enum(LEVELS).describe('记忆层级（必填）'),
      title: z.string().optional().describe('标题（topic 建议填）'),
      project: z.string().optional().describe('关联项目名（project 层必填；多值逗号分隔；全局留空或填"全局"）'),
      keywords: z.array(z.string()).optional().describe('关键词列表（用于 BM25 检索）'),
      tags: z.array(z.string()).optional().describe('自由标签（用于分类与过滤）'),
      importance: z.number().min(1).max(5).optional().describe('重要性 1-5（默认 1）'),
      subcategory: z.string().optional().describe('project 子类：overview/structure/decisions/quotes/ops/todo'),
      goal: z.string().optional().describe('topic 的目标句'),
      corrected: z.boolean().optional().describe('lesson 是否来自用户纠正'),
    }),
    execute: async (args) => {
      const row = {
        level: args.level,
        content: args.content,
        title: args.title,
        project: args.project,
        keywords: args.keywords ?? [],
        tags: args.tags ?? [],
        importance: args.importance ?? 1,
        subcategory: args.subcategory,
        goal: args.goal,
        corrected: args.corrected ? 1 : 0,
      }
      // 去重：同 level 下 content 前 50 字符相同则更新
      const existing = db.list(args.level).find(m => m.content.slice(0, 50) === args.content.slice(0, 50))
      let result
      if (existing) {
        db.update(args.level, existing.id, {
          content: args.content,
          keywords: [...new Set([...existing.keywords, ...(args.keywords ?? [])])],
          tags: [...new Set([...existing.tags, ...(args.tags ?? [])])],
          importance: Math.max(existing.importance, args.importance ?? 1),
        })
        result = { id: existing.id, action: 'updated', level: args.level }
      } else {
        const inserted = db.insert(row)
        // 生成并存储向量
        const vec = embedMemory(inserted)
        db.setVector(inserted.id, inserted.level, vec)
        result = { id: inserted.id, action: 'created', level: args.level }
      }
      return { content: [{ type: 'text', text: JSON.stringify(result, null, 2) }] }
    },
  }))

  // ── memory_search ────────────────────────────────────────────────
  disposers.push(ctx.tools.register({
    name: 'memory_search',
    description: '检索记忆：BM25 关键词命中 + 向量语义相似度双路召回，合并排序返回 top-K。支持按 level/project/status/tag 过滤。',
    parameters: z.object({
      query: z.string().describe('查询文本（关键词或自然语言）'),
      level: z.enum(LEVELS).optional().describe('限定层级'),
      project: z.string().optional().describe('限定项目'),
      tag: z.string().optional().describe('限定标签'),
      topK: z.number().min(1).max(20).optional().describe('返回条数上限（默认 5）'),
      semantic: z.boolean().optional().describe('是否启用语义检索（默认 true）'),
    }),
    execute: async (args) => {
      const topK = args.topK ?? 5
      const useSemantic = args.semantic !== false

      // 收集可检索记忆
      let searchable = []
      const levels = args.level ? [args.level] : LEVELS
      for (const lv of levels) {
        searchable.push(...db.listSearchable(lv))
      }
      // 过滤
      if (args.project) {
        searchable = searchable.filter(m => !m.project || m.project.includes(args.project))
      }
      if (args.tag) {
        searchable = searchable.filter(m => m.tags.includes(args.tag))
      }
      if (searchable.length === 0) {
        return { content: [{ type: 'text', text: '无匹配记忆' }] }
      }

      // BM25 检索
      const bm25Hits = bm25Search(searchable, args.query, { topK })

      // 向量语义检索
      let vecHits = []
      if (useSemantic) {
        const vectors = []
        for (const m of searchable) {
          let vec = db.getVector(m.id)
          if (!vec) {
            vec = embedMemory(m)
            db.setVector(m.id, m.level, vec)
          }
          vectors.push({ memoryId: m.id, level: m.level, vector: vec })
        }
        const queryVec = embed(args.query)
        vecHits = vectorSearch(vectors, queryVec, { topK })
      }

      // 合并去重
      const seen = new Set()
      const results = []
      for (const h of bm25Hits) {
        if (!seen.has(h.row.id)) {
          seen.add(h.row.id)
          results.push({ ...h.row, score: Number(h.score.toFixed(4)), source: 'keyword' })
        }
      }
      for (const h of vecHits) {
        if (!seen.has(h.memoryId)) {
          seen.add(h.memoryId)
          const found = db.findById(h.memoryId)
          if (found) {
            results.push({ ...found.row, score: Number(h.score.toFixed(4)), source: 'semantic' })
          }
        }
      }

      // bump hit count
      for (const r of results) db.bumpHit(r.level, r.id)

      const output = results.slice(0, topK).map(r => ({
        id: r.id.slice(0, 12),
        level: r.level,
        title: r.title,
        content: r.content,
        importance: r.importance,
        tags: r.tags,
        score: r.score,
        source: r.source,
      }))
      return { content: [{ type: 'text', text: JSON.stringify(output, null, 2) }] }
    },
  }))

  // ── memory_read ──────────────────────────────────────────────────
  disposers.push(ctx.tools.register({
    name: 'memory_read',
    description: '按 id 读取单条记忆的完整元数据。',
    parameters: z.object({
      id: z.string().describe('记忆 id（支持 8+ 位前缀匹配）'),
    }),
    execute: async (args) => {
      const found = db.findById(args.id)
      if (!found) return { content: [{ type: 'text', text: '未找到' }] }
      const relations = db.getRelations(found.row.id)
      return {
        content: [{
          type: 'text',
          text: JSON.stringify({ ...found.row, level: found.level, relations }, null, 2),
        }],
      }
    },
  }))

  // ── memory_update ────────────────────────────────────────────────
  disposers.push(ctx.tools.register({
    name: 'memory_update',
    description: '修改记忆的 status / importance / keywords / tags / goal / content 等。',
    parameters: z.object({
      id: z.string().describe('记忆 id（支持前缀）'),
      content: z.string().optional(),
      title: z.string().optional(),
      importance: z.number().min(1).max(5).optional(),
      keywords: z.array(z.string()).optional(),
      tags: z.array(z.string()).optional(),
      status: z.enum(['active', 'archived', 'stale']).optional(),
      goal: z.string().optional(),
      project: z.string().optional(),
    }),
    execute: async (args) => {
      const found = db.findById(args.id)
      if (!found) return { content: [{ type: 'text', text: '未找到' }] }
      const patch = { ...args }
      delete patch.id
      const ok = db.update(found.level, found.row.id, patch)
      // 更新向量
      if (ok && args.content) {
        const updated = db.findById(found.row.id)
        if (updated) db.setVector(updated.row.id, updated.row.level, embedMemory(updated.row))
      }
      return { content: [{ type: 'text', text: ok ? '已更新' : '无变更' }] }
    },
  }))

  // ── memory_tag ───────────────────────────────────────────────────
  disposers.push(ctx.tools.register({
    name: 'memory_tag',
    description: '为记忆添加或移除标签，或列出全部标签。标签用于自由分类与过滤。',
    parameters: z.object({
      action: z.enum(['add', 'remove', 'list']).describe('操作：add/remove/list'),
      id: z.string().optional().describe('记忆 id（add/remove 必填）'),
      tags: z.array(z.string()).optional().describe('标签列表（add/remove 必填）'),
    }),
    execute: async (args) => {
      if (args.action === 'list') {
        const tags = db.listTags()
        return { content: [{ type: 'text', text: JSON.stringify(tags, null, 2) }] }
      }
      if (!args.id || !args.tags) return { content: [{ type: 'text', text: '需要 id 和 tags' }] }
      const found = db.findById(args.id)
      if (!found) return { content: [{ type: 'text', text: '未找到' }] }
      const ok = args.action === 'add'
        ? db.addTags(found.level, found.row.id, args.tags)
        : db.removeTags(found.level, found.row.id, args.tags)
      return { content: [{ type: 'text', text: ok ? `已${args.action === 'add' ? '添加' : '移除'}标签` : '无变更' }] }
    },
  }))

  // ── memory_graph ─────────────────────────────────────────────────
  // 已禁用：可视化关系图谱功能
  /*
  disposers.push(ctx.tools.register({
    name: 'memory_graph',
    description: `管理记忆间关系图谱。关系类型：${RELATION_TYPES.join(' / ')}。支持添加/删除/查询关系，以及获取全图。`,
    parameters: z.object({
      action: z.enum(['add', 'remove', 'query', 'all']).describe('操作'),
      fromId: z.string().optional().describe('源记忆 id（add/remove 必填）'),
      toId: z.string().optional().describe('目标记忆 id（add/remove 必填）'),
      relationType: z.enum(RELATION_TYPES).optional().describe('关系类型'),
      note: z.string().optional().describe('关系说明'),
      memoryId: z.string().optional().describe('记忆 id（query 必填：查该记忆的所有关系）'),
    }),
    execute: async (args) => {
      if (args.action === 'all') {
        const rels = db.getAllRelations()
        return { content: [{ type: 'text', text: JSON.stringify(rels, null, 2) }] }
      }
      if (args.action === 'query') {
        if (!args.memoryId) return { content: [{ type: 'text', text: '需要 memoryId' }] }
        const rels = db.getRelations(args.memoryId)
        return { content: [{ type: 'text', text: JSON.stringify(rels, null, 2) }] }
      }
      if (args.action === 'add') {
        if (!args.fromId || !args.toId || !args.relationType) {
          return { content: [{ type: 'text', text: '需要 fromId, toId, relationType' }] }
        }
        const ok = db.addRelation(args.fromId, args.toId, args.relationType, args.note ?? '')
        return { content: [{ type: 'text', text: ok ? '关系已添加' : '关系已存在（note 已更新）' }] }
      }
      if (args.action === 'remove') {
        if (!args.fromId || !args.toId || !args.relationType) {
          return { content: [{ type: 'text', text: '需要 fromId, toId, relationType' }] }
        }
        const ok = db.removeRelation(args.fromId, args.toId, args.relationType)
        return { content: [{ type: 'text', text: ok ? '关系已删除' : '关系不存在' }] }
      }
      return { content: [{ type: 'text', text: '未知操作' }] }
    },
  }))
  */

  // ── memory_export ────────────────────────────────────────────────
  disposers.push(ctx.tools.register({
    name: 'memory_export',
    description: '导出全部记忆为 JSON 或 Markdown 格式，或从 JSON 导入记忆。',
    parameters: z.object({
      format: z.enum(['json', 'markdown']).describe('导出格式'),
    }),
    execute: async (args) => {
      if (args.format === 'json') {
        const data = db.exportAll()
        return { content: [{ type: 'text', text: JSON.stringify(data, null, 2) }] }
      }
      const md = db.exportMarkdown()
      return { content: [{ type: 'text', text: md }] }
    },
  }))

  // ── memory_stats ─────────────────────────────────────────────────
  // 已禁用：统计仪表盘功能
  /*
  disposers.push(ctx.tools.register({
    name: 'memory_stats',
    description: '查看记忆统计仪表盘：各层条目数、标签分布、关系数、热门记忆、最近活动。',
    parameters: z.object({}),
    execute: async () => {
      const stats = db.getStats()
      const lines = [
        '【记忆统计仪表盘】',
        '',
        `总条目数: ${stats.total}`,
        '',
        '各层分布:',
        ...Object.entries(stats.levels).map(([k, v]) => `  ${LEVEL_LABELS[k] ?? k}: ${v}`),
        '',
        `关系数: ${stats.relations}`,
        '',
        '标签分布 (top 10):',
        ...stats.tags.slice(0, 10).map(t => `  #${t.tag}: ${t.count}`),
        '',
        '热门记忆 (top 5):',
        ...stats.topHit.slice(0, 5).map(h => `  [${h.hit_count}次] ${h.title ?? h.content?.slice(0, 30) ?? h.id}`),
      ]
      return { content: [{ type: 'text', text: lines.join('\n') }] }
    },
  }))
  */

  return () => disposers.forEach(d => d())
}
