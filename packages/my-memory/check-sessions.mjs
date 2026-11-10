#!/usr/bin/env node
/**
 * my-memory — 会话健康检查脚本
 *
 * 扫描所有 DSH 会话文件，检测两类常见损坏：
 *   1. 消息缺少 id 字段（"lacks an identified message"）
 *   2. agent/inbox/spliced 的 inserted 中存在未解包的 {messages:[...]} 包装对象
 *   3. 消息缺少有效的 source.kind 字段（"requires a producer-owned source kind"）
 *
 * 用法：
 *   node check-sessions.mjs          # 扫描 + 报告
 *   node check-sessions.mjs --fix    # 扫描 + 自动修复 + 报告
 *
 * 退出码：0 = 无问题，1 = 发现问题（--fix 时为修复后仍残留）
 */

import { zstdDecompressSync, zstdCompressSync } from 'node:zlib'
import { randomUUID } from 'node:crypto'
import { readFileSync, writeFileSync, readdirSync, statSync, copyFileSync } from 'node:fs'
import { join, basename, dirname } from 'node:path'
import { homedir } from 'node:os'

const SESSIONS_ROOT = join(homedir(), '.dsh', 'sessions')
const doFix = process.argv.includes('--fix')

const MSG_TYPES = new Set(['user/message', 'system/message', 'assistant/message', 'tool/result'])

function walk(dir) {
  const results = []
  for (const name of readdirSync(dir)) {
    const full = join(dir, name)
    const st = statSync(full)
    if (st.isDirectory()) results.push(...walk(full))
    else if (name.endsWith('.jsonl.zstd')) results.push(full)
  }
  return results
}

function extractMessage(obj) {
  const t = obj.type
  const data = obj.data
  if (t === 'user/message') return data
  if (t === 'system/message' || t === 'assistant/message' || t === 'tool/result') return data?.message
  return null
}

let totalFiles = 0
let totalIssues = 0
let totalFixed = 0

const files = walk(SESSIONS_ROOT)
for (const fpath of files) {
  totalFiles++
  let decompressed
  try {
    decompressed = zstdDecompressSync(readFileSync(fpath))
  } catch (e) {
    console.log(`[解压失败] ${fpath}: ${e.message}`)
    totalIssues++
    continue
  }

  const text = decompressed.toString('utf-8')
  const lines = text.split('\n')
  let modified = false
  const fileIssues = []

  for (let i = 0; i < lines.length; i++) {
    if (!lines[i].trim()) continue
    let obj
    try { obj = JSON.parse(lines[i]) } catch { continue }

    // 检查 1: 消息缺少 id
    if (MSG_TYPES.has(obj.type)) {
      const msg = extractMessage(obj)
      if (msg && typeof msg === 'object') {
        if (typeof msg.id !== 'string' || msg.id === '') {
          fileIssues.push(`seq=${obj.seq} ${obj.type}: 消息缺少 id`)
          if (doFix) { msg.id = randomUUID(); modified = true; totalFixed++ }
        }
        const src = msg.source
        if (!src || typeof src !== 'object' || typeof src.kind !== 'string' || src.kind === '' || src.kind === 'plugin') {
          fileIssues.push(`seq=${obj.seq} ${obj.type}: 消息 source.kind 无效`)
        }
      }
    }

    // 检查 2: agent/inbox/spliced 的 inserted 包装对象
    if (obj.type === 'agent/inbox/spliced') {
      const inserted = obj.data?.inserted
      if (Array.isArray(inserted)) {
        let changed = false
        const newInserted = []
        for (const item of inserted) {
          if (item && typeof item === 'object' && 'messages' in item && !('source' in item) && !('role' in item)) {
            fileIssues.push(`seq=${obj.seq}: inserted 存在未解包的 {messages:[...]} 包装对象`)
            if (doFix) { newInserted.push(...item.messages); changed = true; totalFixed++ }
            else newInserted.push(item)
          } else {
            newInserted.push(item)
          }
        }
        if (changed) { obj.data.inserted = newInserted; modified = true }
      }
    }

    if (modified) lines[i] = JSON.stringify(obj, undefined, 0)
  }

  if (fileIssues.length > 0) {
    const short = fpath.replace(SESSIONS_ROOT, '')
    console.log(`\n${short}`)
    for (const issue of fileIssues) console.log(`  ${issue}`)
    totalIssues += fileIssues.length
  }

  if (modified && doFix) {
    copyFileSync(fpath, fpath + '.backup')
    const fixedBytes = Buffer.from(lines.join('\n'), 'utf-8')
    const compressed = zstdCompressSync(fixedBytes)
    writeFileSync(fpath, compressed)
    console.log(`  → 已修复并备份`)
  }
}

console.log(`\n${'─'.repeat(50)}`)
console.log(`扫描 ${totalFiles} 个会话文件，发现 ${totalIssues} 个问题`)
if (doFix) console.log(`修复了 ${totalFixed} 个问题`)
console.log(totalIssues === 0 ? '✓ 所有会话健康' : (doFix ? '✓ 修复完成' : '⚠ 运行 --fix 自动修复'))
process.exit(totalIssues === 0 ? 0 : 1)
