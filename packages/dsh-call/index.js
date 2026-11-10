/**
 * dsh-call —— 通话面板（host 端）
 *
 * 只做一件事：把浏览器录到的 16k PCM 转成文字。
 * 转写走本机常驻的 faster-whisper 服务（E:\tools\asr\speech_server.py，127.0.0.1:8777），
 * 没起就尝试自动拉起；都失败时返回明确错误，前端提示。
 *
 * 为什么不在插件里自己跑模型：faster-whisper 在 Python 侧已经跑通并有实测数据，
 * 重复造一份 Node 侧推理没有收益，且模型下载/校验是别人插件的资产。
 */

import { spawn } from 'node:child_process'
import { existsSync } from 'node:fs'

export const name = 'dsh-call'
export const inject = ['webServer']

const ASR_PORT = 8777
const ASR_URL = `http://127.0.0.1:${ASR_PORT}`
const ASR_SCRIPT = process.env.DSH_ASR_SCRIPT || 'E:\\tools\\asr\\speech_server.py'
const PYTHON = process.env.DSH_PYTHON ||
  (process.env.LOCALAPPDATA || 'C:\\Users\\Public\\AppData\\Local') + '\\Programs\\Python\\Python312\\python.exe'

function json(res, code, obj) {
  const body = JSON.stringify(obj)
  res.writeHead(code, { 'content-type': 'application/json; charset=utf-8' })
  res.end(body)
}

function isLoopback(req) {
  const a = req.socket?.remoteAddress || ''
  return a === '127.0.0.1' || a === '::1' || a === '::ffff:127.0.0.1'
}

function readBody(req, limit = 32 * 1024 * 1024) {
  return new Promise((resolve, reject) => {
    const chunks = []
    let total = 0
    req.on('data', (c) => {
      total += c.length
      if (total > limit) {
        reject(new Error('音频太大'))
        req.destroy()
        return
      }
      chunks.push(c)
    })
    req.on('end', () => resolve(Buffer.concat(chunks)))
    req.on('error', reject)
  })
}

async function asrAlive() {
  try {
    const r = await fetch(`${ASR_URL}/health`, { signal: AbortSignal.timeout(1200) })
    return r.ok
  } catch {
    return false
  }
}

let starting = null

/** 确保本机 ASR 服务在跑：先探活，再尝试拉起（只拉一次）。 */
function ensureAsr(logger) {
  if (starting) return starting
  starting = (async () => {
    if (await asrAlive()) return true
    if (!existsSync(ASR_SCRIPT) || !existsSync(PYTHON)) return false
    try {
      const p = spawn(PYTHON, [ASR_SCRIPT], {
        cwd: 'E:\\tools\\asr',
        detached: true,
        stdio: 'ignore',
        windowsHide: true,
      })
      p.unref()
      logger?.info?.('dsh-call: 已拉起本地转写服务 127.0.0.1:8777')
    } catch (e) {
      logger?.warn?.('dsh-call: 拉起转写服务失败', e)
      return false
    }
    // 最多等 20 秒（首次要加载模型）
    for (let i = 0; i < 40; i++) {
      await new Promise((r) => setTimeout(r, 500))
      if (await asrAlive()) return true
    }
    return false
  })().finally(() => {
    starting = null
  })
  return starting
}

export function apply(ctx, rawConfig = {}) {
  const config = { enabled: true, ...(rawConfig || {}) }
  if (config.enabled === false) return

  ctx.effect(() =>
    ctx.webServer.register({
      kind: 'exact',
      path: '/call/health',
      handler: async (req, res) => {
        if (!isLoopback(req)) return json(res, 403, { ok: false, error: '只允许本机' })
        json(res, 200, { ok: true, asr: await asrAlive() })
      },
    }),
  )

  ctx.effect(() =>
    ctx.webServer.register({
      kind: 'exact',
      path: '/call/transcribe',
      handler: async (req, res) => {
        if (!isLoopback(req)) return json(res, 403, { ok: false, error: '只允许本机' })
        if (req.method !== 'POST') return json(res, 405, { ok: false, error: '只接受 POST' })
        const t0 = Date.now()
        try {
          const pcm = await readBody(req)
          if (pcm.length < 6400) {
            return json(res, 200, { ok: true, text: '', ms: 0, note: '太短' })
          }
          const up = await ensureAsr(ctx.logger)
          if (!up) {
            return json(res, 503, {
              ok: false,
              error: '本地转写服务没起来（127.0.0.1:8777）',
              hint: '到 E:\\tools\\asr 跑 python speech_server.py',
            })
          }
          const r = await fetch(`${ASR_URL}/asr?m=small`, {
            method: 'POST',
            headers: { 'content-type': 'application/octet-stream' },
            body: pcm,
            signal: AbortSignal.timeout(60000),
          })
          const j = await r.json().catch(() => null)
          if (!j || j.ok !== true) {
            return json(res, 502, { ok: false, error: (j && j.error) || `转写服务返回 ${r.status}` })
          }
          json(res, 200, { ok: true, text: j.text || '', model: j.model, ms: j.ms ?? Date.now() - t0 })
        } catch (e) {
          json(res, 500, { ok: false, error: String(e?.message ?? e) })
        }
      },
    }),
  )

  ctx.logger?.info?.('dsh-call: 通话面板已加载（/call/health、/call/transcribe）')
}
