/**
 * my-memory — 轻量向量语义嵌入
 *
 * 无外部依赖的文本嵌入方案：基于字符 n-gram 哈希映射到固定维度向量。
 * 不如真正的 embedding 模型精确，但零依赖、零延迟，足以提供语义相似度排序。
 * 向量存储在 SQLite memory_vectors 表中，查询时计算余弦相似度。
 */

/**
 * 将文本嵌入为固定维度的浮点向量。
 * 算法：字符 n-gram（2-3 gram）→ 哈希到维度 → 带符号计数 → L2 归一化。
 * @param {string} text - 输入文本
 * @param {number} dimensions - 向量维度（默认 128）
 * @returns {number[]} 归一化向量
 */
export function embed(text, dimensions = 128) {
  if (!text || typeof text !== 'string') return new Array(dimensions).fill(0)
  const vec = new Float32Array(dimensions)
  const normalized = text.toLowerCase().replace(/\s+/g, ' ').trim()
  if (normalized.length === 0) return new Array(dimensions).fill(0)

  // 字符 n-gram（2-gram 和 3-gram）
  for (let n = 2; n <= 3; n++) {
    for (let i = 0; i <= normalized.length - n; i++) {
      const gram = normalized.slice(i, i + n)
      const hash = hashStr(gram)
      const idx = Math.abs(hash) % dimensions
      const sign = hash < 0 ? -1 : 1
      vec[idx] += sign
    }
  }

  // 词级特征（英文单词权重更高）
  const words = normalized.split(/[\s\p{P}]+/u).filter(w => w.length >= 2)
  for (const word of words) {
    const hash = hashStr(word)
    const idx = Math.abs(hash) % dimensions
    vec[idx] += 2 // 词级权重
  }

  // L2 归一化
  let norm = 0
  for (let i = 0; i < dimensions; i++) norm += vec[i] * vec[i]
  norm = Math.sqrt(norm)
  if (norm > 0) {
    for (let i = 0; i < dimensions; i++) vec[i] /= norm
  }

  return Array.from(vec)
}

/** 字符串哈希（32 位有符号） */
function hashStr(s) {
  let h = 0
  for (let i = 0; i < s.length; i++) {
    h = (h * 31 + s.charCodeAt(i)) | 0
  }
  return h
}

/** 余弦相似度 */
export function cosineSimilarity(a, b) {
  if (!a || !b || a.length !== b.length) return 0
  let dot = 0
  for (let i = 0; i < a.length; i++) dot += a[i] * b[i]
  return dot // 已归一化，dot 即 cosine
}

/**
 * 语义检索：对查询向量与全部记忆向量计算相似度，返回 top-K。
 * @param {Array} vectors - [{ memoryId, level, vector }]
 * @param {number[]} queryVec - 查询向量
 * @param {object} opts - { topK, level, minScore }
 * @returns {Array} [{ memoryId, level, score }]
 */
export function vectorSearch(vectors, queryVec, opts = {}) {
  const { topK = 5, level, minScore = 0.05 } = opts
  let filtered = vectors
  if (level) filtered = filtered.filter(v => v.level === level)

  const results = []
  for (const v of filtered) {
    const score = cosineSimilarity(queryVec, v.vector)
    if (score > minScore) results.push({ memoryId: v.memoryId, level: v.level, score })
  }
  return results.sort((a, b) => b.score - a.score).slice(0, topK)
}

/**
 * 为记忆条目生成嵌入文本（关键词 + 标题 + 内容）。
 */
export function embedMemory(row) {
  const text = [
    row.title ?? '',
    row.content ?? '',
    (row.keywords ?? []).join(' '),
    (row.tags ?? []).join(' '),
  ].join(' ')
  return embed(text)
}
