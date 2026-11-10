/**
 * dsh-rea —— 把 REA（Reverse Engineer Anything）包成 AI 可直接调用的分析工具（host 端，无 UI）
 *
 * 四个工具：
 *   rea_probe(path)    概览：类型/架构/sha256/函数数/字符串数/段，附域名计数
 *   rea_domains(path)  字节扫描抽 URL 与域名（不用引擎，秒级）
 *   rea_js(path)       Electron / JS 应用结构（限节点数，防爆量）
 *   rea_report(path)   汇总成 Markdown 报告落盘
 *
 * 硬约束：
 *   - 只读：不执行目标程序、不写目标文件、不上传任何数据
 *   - 输出有界：大输出一律裁剪，绝不把几百 MB 原文回灌给模型
 *   - 引擎不齐也能用：probe 失败时退回 PE 头解析；domains 完全不依赖引擎
 */

import { spawn } from 'node:child_process'
import { readFileSync, writeFileSync, mkdirSync, existsSync, statSync, openSync, readSync, closeSync } from 'node:fs'
import { join, basename } from 'node:path'
import { createHash } from 'node:crypto'

export const name = 'dsh-rea'
export const inject = ['tools']

const REA_DIR = 'E:\\dsh-plugins\\tools\\rea'
const REA_ENTRY = join(REA_DIR, 'node_modules', 'rea-agents', 'scripts', 'rea.mjs')
const REPORT_DIR = 'E:\\dsh-plugins\\rea-reports'
const NODE_HINT = process.execPath

function reaEnv() {
  return {
    ...process.env,
    JAVA_HOME: 'E:\\tools\\jdk25',
    GHIDRA_INSTALL_DIR: 'E:\\tools\\ghidra_12.1.4_PUBLIC',
    Path: ['E:\\tools\\jdk25\\bin', 'E:\\tools\\rizin\\bin', 'E:\\tools\\apktool', process.env.Path || ''].join(';'),
  }
}

function runCli(args, timeoutMs = 300000) {
  return new Promise((resolve) => {
    let out = ''
    let err = ''
    let done = false
    const child = spawn(NODE_HINT, [REA_ENTRY, ...args], { env: reaEnv(), windowsHide: true })
    const timer = setTimeout(() => {
      if (!done) { done = true; try { child.kill() } catch { } resolve({ ok: false, code: 'timeout', out, err }) }
    }, timeoutMs)
    child.stdout.on('data', (d) => {
      // 进度 JSON 行直接丢弃，只保留最终结果（否则输出会被刷爆）
      const s = d.toString('utf8')
      for (const line of s.split('\n')) {
        if (!line.trim()) continue
        if (line.includes('"rea_progress"')) continue
        out += line + '\n'
      }
    })
    child.stderr.on('data', (d) => { err += d.toString('utf8') })
    child.on('close', (code) => {
      if (done) return
      done = true
      clearTimeout(timer)
      resolve({ ok: code === 0, code, out, err })
    })
    child.on('error', (e) => {
      if (done) return
      done = true
      clearTimeout(timer)
      resolve({ ok: false, code: 'spawn', out, err: String(e && e.message) })
    })
  })
}

function sha256(file) {
  const fd = openSync(file, 'r')
  const hash = createHash('sha256')
  const buf = Buffer.alloc(4 * 1024 * 1024)
  let pos = 0
  for (;;) {
    const n = readSync(fd, buf, 0, buf.length, pos)
    if (n <= 0) break
    hash.update(buf.subarray(0, n))
    pos += n
  }
  closeSync(fd)
  return hash.digest('hex')
}

/** 极简 PE 头解析：引擎不可用时的兜底，只取机器类型与段数 */
function peSummary(file) {
  try {
    const fd = openSync(file, 'r')
    const head = Buffer.alloc(4096)
    readSync(fd, head, 0, 4096, 0)
    closeSync(fd)
    if (head.readUInt16LE(0) !== 0x5a4d) return null
    const peOff = head.readUInt32LE(0x3c)
    if (peOff + 6 > head.length) return null
    if (head.readUInt32LE(peOff) !== 0x00004550) return null
    const machine = head.readUInt16LE(peOff + 4)
    const sections = head.readUInt16LE(peOff + 6)
    const arch = { 0x8664: 'x86_64', 0x14c: 'x86', 0xaa64: 'arm64', 0x1c4: 'armnt' }[machine] || ('0x' + machine.toString(16))
    return { format: 'pe', architecture: arch, sectionCount: sections }
  } catch {
    return null
  }
}

const URL_RE = /https?:\/\/[A-Za-z0-9._~:\/?#\[\]@!$&'()*+,;=%-]{4,200}/g
const DOM_RE = /\b(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+(?:com|cn|net|org|io|tv|cc|co|xyz|top|vip|cloud|dev|app)\b/gi
const NOISE = /w3\.org|schemas|xmlns|purl\.org|example\.com|localhost|127\.0\.0\.1|digicert|sectigo|ocsp|crl|\.pdb$|adobe\.com|gimp\.org|figma\.com|sketch\.com|qt\.io|lua\.org|luajit|github\.com\/|byted\.org/i

function scanUrls(file, maxBytes = 400 * 1024 * 1024) {
  const size = statSync(file).size
  const limit = Math.min(size, maxBytes)
  const fd = openSync(file, 'r')
  const chunk = 8 * 1024 * 1024
  const urls = new Set()
  const domains = new Set()
  let carry = ''
  for (let off = 0; off < limit; off += chunk) {
    const buf = Buffer.alloc(Math.min(chunk, limit - off))
    readSync(fd, buf, 0, buf.length, off)
    const text = carry + buf.toString('latin1')
    for (const m of text.match(URL_RE) || []) if (!NOISE.test(m)) urls.add(m)
    for (const m of text.match(DOM_RE) || []) { const d = m.toLowerCase(); if (!NOISE.test(d)) domains.add(d) }
    carry = text.slice(-4096)
  }
  closeSync(fd)
  return { urls: [...urls].slice(0, 120), domains: [...domains].slice(0, 120), urlCount: urls.size, domainCount: domains.size }
}

async function probe(path) {
  if (!existsSync(path)) throw new Error(`路径不存在：${path}`)
  const st = statSync(path)
  const base = { path, name: basename(path), sizeBytes: st.size, sizeMB: Math.round(st.size / 1048576), sha256: sha256(path) }
  const pe = peSummary(path)
  const result = { ...base, pe }
  if (/\.(asar|js|mjs|cjs)$/i.test(path) || st.isDirectory()) {
    const r = await runCli(['analyze-javascript-application', path, '--format', 'json', '--max-semantic-nodes', '1500', '--max-semantic-nodes-per-file', '300', '--analysis-timeout-ms', '60000'], 180000)
    const parsed = safeJson(r.out)
    result.js = parsed ? summarizeJs(parsed) : { error: (r.err || r.out || 'no output').slice(0, 400), code: r.code }
    return result
  }
  const r = await runCli(['analyze', path, '--format', 'json'], 300000)
  const parsed = safeJson(r.out)
  if (parsed) {
    const nr = parsed.normalized_result || {}
    result.native = {
      format: nr.format || (parsed.subject && parsed.subject.format) || (pe && pe.format),
      architecture: nr.architecture || (parsed.subject && parsed.subject.architecture) || (pe && pe.architecture),
      imageBase: nr.image_base,
      segments: nr.segment_count,
      functions: nr.procedure_count,
      strings: nr.string_count,
      engine: ((parsed.analysis_profile || {}).parameters || {}).upstream_analysis_profile ? 'ghidra' : undefined,
      limitations: (nr.limitations || []).slice(0, 4),
    }
  } else {
    result.nativeError = { code: r.code, detail: (r.err || r.out || 'no output').slice(0, 400), fellBackTo: 'pe-header' }
  }
  return result
}

function safeJson(text) {
  if (!text) return null
  const t = text.replace(/^\uFEFF/, '').trim()
  if (!t.startsWith('{')) return null
  try { return JSON.parse(t) } catch { }
  // 多行 JSON：取第一个 { 到最后一个 }
  const a = t.indexOf('{'), b = t.lastIndexOf('}')
  if (a >= 0 && b > a) { try { return JSON.parse(t.slice(a, b + 1)) } catch { } }
  return null
}

function summarizeJs(parsed) {
  const nr = parsed.normalized_result || {}
  return {
    files: nr.file_count ?? nr.fileCount,
    nodes: nr.node_count ?? nr.semantic_node_count,
    exports: Array.isArray(nr.exports) ? nr.exports.length : undefined,
    unknowns: Array.isArray(nr.unknowns) ? nr.unknowns.length : undefined,
    limitations: (nr.limitations || []).slice(0, 3),
  }
}

export function apply(ctx) {
  const disposers = []

  disposers.push(ctx.tools.register({
    name: 'rea_probe',
    description: '【REA】目标概览：识别文件类型/架构/哈希/段/函数数/字符串数，并附域名数量。适用于 exe/dll/apk/asar/目录。输出有界，几十秒。',
    parameters: {
      type: 'object',
      properties: {
        path: { type: 'string', description: '目标绝对路径（可执行文件、DLL、APK、asar 或目录）' },
      },
      required: ['path'],
      additionalProperties: false,
    },
    output: {
      schema: { type: 'object', additionalProperties: true },
      render: (args, value) => [{ type: 'text', text: JSON.stringify(value, null, 2) }],
    },
    execute: async (args) => {
      const info = await probe(args.path)
      const dom = scanUrls(args.path)
      info.domainsPreview = { count: dom.domainCount, top: dom.domains.slice(0, 15) }
      return info
    },
  }))

  disposers.push(ctx.tools.register({
    name: 'rea_domains',
    description: '【REA】字节扫描目标里写死的 URL 与域名，判断它连哪些服务器（秒级，不需要引擎）。适合回答"它会不会把数据传出去"。',
    parameters: {
      type: 'object',
      properties: {
        path: { type: 'string', description: '目标文件绝对路径' },
        limit: { type: 'number', description: '最多返回多少条，默认 40' },
      },
      required: ['path'],
      additionalProperties: false,
    },
    output: {
      schema: { type: 'object', additionalProperties: true },
      render: (args, value) => [{ type: 'text', text: JSON.stringify(value, null, 2) }],
    },
    execute: async (args) => {
      if (!existsSync(args.path)) throw new Error(`路径不存在：${args.path}`)
      const r = scanUrls(args.path)
      const limit = Math.max(1, Math.min(120, args.limit || 40))
      return { path: args.path, urlCount: r.urlCount, domainCount: r.domainCount, domains: r.domains.slice(0, limit), urls: r.urls.slice(0, limit) }
    },
  }))

  disposers.push(ctx.tools.register({
    name: 'rea_js',
    description: '【REA】拆 Electron / JavaScript 应用（asar 或目录）的结构，限节点数输出，不会回灌几百 MB。',
    parameters: {
      type: 'object',
      properties: {
        path: { type: 'string', description: 'asar 文件或已解包目录' },
        sourcePath: { type: 'string', description: '可选：只看某个具体文件（相对应用根）' },
      },
      required: ['path'],
      additionalProperties: false,
    },
    output: {
      schema: { type: 'object', additionalProperties: true },
      render: (args, value) => [{ type: 'text', text: JSON.stringify(value, null, 2) }],
    },
    execute: async (args) => {
      const cli = ['analyze-javascript-application', args.path, '--format', 'json', '--max-semantic-nodes', '2000', '--max-semantic-nodes-per-file', '400', '--analysis-timeout-ms', '90000']
      if (args.sourcePath) cli.push('--source-path', args.sourcePath)
      const r = await runCli(cli, 240000)
      const parsed = safeJson(r.out)
      if (!parsed) return { ok: false, code: r.code, detail: (r.err || r.out || 'no output').slice(0, 500) }
      return { ok: true, summary: summarizeJs(parsed) }
    },
  }))

  disposers.push(ctx.tools.register({
    name: 'rea_report',
    description: '【REA】对目标做一次完整静态分析并写成 Markdown 报告，存到 E:\\dsh-plugins\\rea-reports\\，返回报告路径与关键结论。',
    parameters: {
      type: 'object',
      properties: {
        path: { type: 'string', description: '目标绝对路径' },
        title: { type: 'string', description: '报告标题（可选）' },
      },
      required: ['path'],
      additionalProperties: false,
    },
    output: {
      schema: { type: 'object', additionalProperties: true },
      render: (args, value) => [{ type: 'text', text: JSON.stringify(value, null, 2) }],
    },
    execute: async (args) => {
      const info = await probe(args.path)
      const dom = scanUrls(args.path)
      mkdirSync(REPORT_DIR, { recursive: true })
      const stamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19)
      const file = join(REPORT_DIR, `${(args.title || basename(args.path)).replace(/[\\/:*?"<>|]/g, '_')}-${stamp}.md`)
      const lines = []
      lines.push(`# ${args.title || basename(args.path)} 静态分析报告`, '')
      lines.push(`- 目标：\`${args.path}\``)
      lines.push(`- 大小：${info.sizeMB} MB`)
      lines.push(`- SHA256：\`${info.sha256}\``)
      if (info.pe) lines.push(`- PE：${info.pe.architecture}，${info.pe.sectionCount} 个段`)
      if (info.native) {
        const n = info.native
        lines.push(`- 引擎：${n.engine || 'rea'}`)
        if (n.functions != null) lines.push(`- 函数数：${n.functions}`)
        if (n.strings != null) lines.push(`- 字符串数：${n.strings}`)
        if (n.segments != null) lines.push(`- 段数：${n.segments}`)
      }
      if (info.js) lines.push(`- JS 应用：${JSON.stringify(info.js)}`)
      if (info.nativeError) lines.push(`- 引擎分析失败：${info.nativeError.detail}`)
      lines.push('', '## 外联域名（字节扫描）', '')
      if (dom.domains.length === 0) lines.push('（未发现）')
      for (const d of dom.domains.slice(0, 80)) lines.push(`- ${d}`)
      lines.push('', '## URL 样本', '')
      for (const u of dom.urls.slice(0, 60)) lines.push(`- \`${u}\``)
      if (info.native && info.native.limitations) {
        lines.push('', '## 分析局限', '')
        for (const l of info.native.limitations) lines.push(`- ${l}`)
      }
      writeFileSync(file, lines.join('\n'), 'utf8')
      return { ok: true, report: file, sha256: info.sha256, sizeMB: info.sizeMB, domains: dom.domainCount, urls: dom.urlCount }
    },
  }))

  return () => { for (const d of disposers) { try { d?.() } catch { } } }
}
