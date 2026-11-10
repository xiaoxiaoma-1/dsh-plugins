/**
 * my-memory — BM25 关键词检索
 *
 * 基于关键词的 BM25 排序检索，支持按 level/project/status/tags 过滤。
 * 独立实现，不依赖外部库。
 */

/** 中文分词：按字符 bigram + 英文按空格/标点分词 */
export function tokenize(text) {
  if (!text) return []
  const tokens = new Set()
  const cleaned = text.toLowerCase().replace(/[^\p{L}\p{N}]+/gu, ' ')
  // 英文分词
  for (const word of cleaned.split(/\s+/)) {
    if (word.length >= 2) tokens.add(word)
  }
  // 中文 bigram
  const cjk = text.replace(/[^\u4e00-\u9fff]+/g, '')
  for (let i = 0; i < cjk.length - 1; i++) {
    tokens.add(cjk.slice(i, i + 2))
  }
  return [...tokens]
}

/** BM25 检索器 */
export class BM25Index {
  constructor(documents, k1 = 1.5, b = 0.75) {
    this.k1 = k1
    this.b = b
    this.docs = documents
    this.docLen = documents.map(d => d.tokens.length)
    this.avgLen = this.docLen.length > 0
      ? this.docLen.reduce((a, b) => a + b, 0) / this.docLen.length
      : 0
    // 词频
    this.tf = documents.map(d => {
      const freq = new Map()
      for (const t of d.tokens) freq.set(t, (freq.get(t) ?? 0) + 1)
      return freq
    })
    // 文档频率
    this.df = new Map()
    for (const freq of this.tf) {
      for (const term of freq.keys()) {
        this.df.set(term, (this.df.get(term) ?? 0) + 1)
      }
    }
    this.N = documents.length
  }

  idf(term) {
    const df = this.df.get(term) ?? 0
    return Math.log(1 + (this.N - df + 0.5) / (df + 0.5))
  }

  score(queryTokens, docIdx) {
    let score = 0
    const freq = this.tf[docIdx]
    const len = this.docLen[docIdx]
    for (const term of queryTokens) {
      const f = freq.get(term)
      if (!f) continue
      const idf = this.idf(term)
      score += idf * (f * (this.k1 + 1)) / (f + this.k1 * (1 - this.b + this.b * len / (this.avgLen || 1)))
    }
    return score
  }

  search(queryTokens, topK = 5) {
    const results = []
    for (let i = 0; i < this.docs.length; i++) {
      const score = this.score(queryTokens, i)
      if (score > 0) results.push({ doc: this.docs[i], score, idx: i })
    }
    return results.sort((a, b) => b.score - a.score).slice(0, topK)
  }
}

/**
 * 对记忆条目做 BM25 检索。
 * @param {Array} memories - 记忆条目数组
 * @param {string} query - 查询文本
 * @param {object} opts - { topK, level, project, status, tag }
 * @returns {Array} 命中结果 [{ row, score }]
 */
export function bm25Search(memories, query, opts = {}) {
  const { topK = 5, level, project, status = 'active', tag } = opts
  // 过滤
  let filtered = memories
  if (level) filtered = filtered.filter(m => m.level === level)
  if (status) filtered = filtered.filter(m => m.status === status)
  if (project) filtered = filtered.filter(m => m.project === project || m.project === null)
  if (tag) filtered = filtered.filter(m => m.tags.includes(tag))

  if (filtered.length === 0) return []

  // 建索引：用 keywords + content 的 token
  const docs = filtered.map(m => ({
    row: m,
    tokens: tokenize((m.keywords?.join(' ') ?? '') + ' ' + (m.content ?? '') + ' ' + (m.title ?? '')),
  }))

  const index = new BM25Index(docs)
  const queryTokens = tokenize(query)
  if (queryTokens.length === 0) return []

  const hits = index.search(queryTokens, topK)
  return hits.map(h => ({ row: h.doc.row, score: h.score }))
}
