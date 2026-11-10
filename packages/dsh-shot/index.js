/**
 * dsh-shot —— 截图（host 端）
 *
 * 两个路由：
 *   GET  /shot/screen  → 用 .NET 截整个屏幕，返回 dataUrl + 屏幕尺寸（前端盖遮罩拖框用）
 *   POST /shot/save    → 接裁好的 PNG，写 E:\desktop\shots\，返回路径
 *
 * 为什么不用浏览器的 getDisplayMedia：Electron 里它默认不注册 handler，
 * 调了不弹选择器、直接 reject，用户看到的就是「点了没反应」。
 * 而且就算弹出来，它也只能选「一个窗口」，不能像正常截图工具那样直接框屏幕的一块。
 *
 * 截图走 PowerShell + .NET（System.Drawing.Graphics.CopyFromScreen）：
 * 快（约 150ms）、全屏、不需要用户先选窗口。前端拿到整屏图再让用户拖框裁切。
 */

import { execFile, spawn } from 'node:child_process'
import { mkdirSync, writeFileSync, unlinkSync, existsSync, readFileSync, statSync } from 'node:fs'
import { join } from 'node:path'

export const name = 'dsh-shot'
export const inject = ['webServer']

const OUT_DIR = 'E:\\desktop\\shots'
const MAX_BYTES = 24 * 1024 * 1024

const PS = 'C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe'
const SNIP = (process.env.LOCALAPPDATA || 'C:\\Users\\Public\\AppData\\Local') + '\\Microsoft\\WindowsApps\\SnippingTool.exe'
const OVERLAY = 'E:\\tools\\asr\\shot_overlay.ps1'
const VBS_RUN = 'E:\\tools\\asr\\run_overlay.vbs'
const TMP_DIR = 'E:\\desktop\\shots\\.tmp'

/**
 * 全屏截图（定稿·纯方案）：host 截整个虚拟桌面（两个屏拼起来），直接返回 dataUrl。
 * 框选完全在前端做 —— 前端把这张图铺满浏览器窗口，用户在窗口里框任意位置，
 * 再按比例换算回原图坐标裁切。
 *
 * 为什么最终是这个：
 * 从 DSH（Electron）里启动任何 GUI 程序都拿不到可见窗口（十一次实测），
 * 所以「弹一个全屏覆盖层」这条路在 DSH 内部走不通。
 * 这个方案不碰任何窗口，100% 能工作，而且两个屏的内容一次全给你看。
 */
function overlayShot() {
  return new Promise((resolve, reject) => {
    const body = 'Add-Type -AssemblyName System.Windows.Forms,System.Drawing;$b=[System.Windows.Forms.SystemInformation]::VirtualScreen;$w=$b.Width; $h=$b.Height;$bmp=New-Object System.Drawing.Bitmap $w,$h;$g=[System.Drawing.Graphics]::FromImage($bmp);$g.CopyFromScreen($b.X,$b.Y,0,0,$bmp.Size);$ms=New-Object System.IO.MemoryStream;$bmp.Save($ms,[System.Drawing.Imaging.ImageFormat]::Png);[Console]::Out.Write(\"$w,$h|\" + [Convert]::ToBase64String($ms.ToArray()));$g.Dispose(); $bmp.Dispose(); $ms.Dispose()'
    execFile(
      PS,
      ['-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-Command', body],
      { timeout: 20000, maxBuffer: 96 * 1024 * 1024, windowsHide: true },
      (err, stdout) => {
        if (err) { reject(new Error('截屏失败：' + String(err.message).slice(0, 80))); return }
        const s = String(stdout || '').trim()
        const p = s.indexOf('|')
        if (p < 0) { reject(new Error('截屏返回格式不对')); return }
        const dim = s.slice(0, p).split(',')
        const b64 = s.slice(p + 1)
        if (!b64 || b64.length < 500) { reject(new Error('截屏是空的')); return }
        resolve({
          cancel: false,
          dataUrl: 'data:image/png;base64,' + b64,
          w: Number(dim[0]) || 0,
          h: Number(dim[1]) || 0,
        })
      },
    )
  })
}

// 模块级日志占位（apply 里会替换成真正的 ctx.logger）
let _logger = null
function ctxLoggerInfo(msg) { try { _logger?.info?.(msg) } catch { } }

function json(res, code, obj) {
  res.writeHead(code, { 'content-type': 'application/json; charset=utf-8' })
  res.end(JSON.stringify(obj))
}

function isLoopback(req) {
  const a = req.socket?.remoteAddress || ''
  return a === '127.0.0.1' || a === '::1' || a === '::ffff:127.0.0.1'
}

function readBody(req, limit = MAX_BYTES) {
  return new Promise((resolve, reject) => {
    const chunks = []
    let total = 0
    req.on('data', (c) => {
      total += c.length
      if (total > limit) { reject(new Error('图片太大')); req.destroy(); return }
      chunks.push(c)
    })
    req.on('end', () => resolve(Buffer.concat(chunks)))
    req.on('error', reject)
  })
}

function stamp() {
  const d = new Date()
  const p = (n, w = 2) => String(n).padStart(w, '0')
  return `${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}-${p(d.getHours())}${p(d.getMinutes())}${p(d.getSeconds())}`
}

function captureScreen(box) {
  const env = { ...process.env }
  if (box) {
    env.SHOT_X = String(Math.round(box.x))
    env.SHOT_Y = String(Math.round(box.y))
    env.SHOT_W = String(Math.round(box.w))
    env.SHOT_H = String(Math.round(box.h))
  }
  return new Promise((resolve, reject) => {
    execFile(
      PS,
      ['-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-Command', SCREEN_PS],
      { timeout: 15000, maxBuffer: 64 * 1024 * 1024, windowsHide: true, env },
      (err, stdout) => {
        if (err) { reject(err); return }
        const b64 = String(stdout || '').trim()
        if (!b64 || b64.length < 500) { reject(new Error('截屏返回空')); return }
        resolve(b64)
      },
    )
  })
}

export function apply(ctx, rawConfig = {}) {
  _logger = ctx.logger
  const config = { enabled: true, ...(rawConfig || {}) }
  if (config.enabled === false) return

  ctx.effect(() =>
    ctx.webServer.register({
      kind: 'exact',
      path: '/shot/health',
      handler: async (req, res) => {
        if (!isLoopback(req)) return json(res, 403, { ok: false, error: '只允许本机' })
        json(res, 200, { ok: true, dir: OUT_DIR, mode: 'host-screen' })
      },
    }),
  )

  // 调 Windows 系统截图（ms-screenclip:）—— 它铺满整个屏幕，双屏也能框
  ctx.effect(() =>
    ctx.webServer.register({
      kind: 'exact',
      path: '/shot/system',
      handler: async (req, res) => {
        if (!isLoopback(req)) return json(res, 403, { ok: false, error: '只允许本机' })
        try {
          // 先清空剪贴板里的旧图，避免读到上一次的
          await new Promise((resolve) => {
            execFile(
              PS,
              ['-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-Command',
                'Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.Clipboard]::Clear()'],
              { timeout: 8000, windowsHide: true },
              () => resolve(),
            )
          })
          // 启动系统截图（直接调 SnippingTool.exe /clip，实测能出窗口）
          // 注意：ms-screenclip: 协议起的是同一个进程但不渲染 UI，不要用
          const { spawn } = await import('node:child_process')
          const p = spawn(SNIP, ['/clip'], {
            detached: true,
            stdio: 'ignore',
            windowsHide: false,
          })
          p.unref()
          ctx.logger?.info?.('dsh-shot: 已拉起系统截图 SnippingTool.exe /clip')
          json(res, 200, { ok: true, mode: 'system' })
        } catch (e) {
          json(res, 500, { ok: false, error: String(e?.message ?? e).slice(0, 200) })
        }
      },
    }),
  )

  // 读系统剪贴板里的图片（系统截图框完会放这儿）
  ctx.effect(() =>
    ctx.webServer.register({
      kind: 'exact',
      path: '/shot/clipboard',
      handler: async (req, res) => {
        if (!isLoopback(req)) return json(res, 403, { ok: false, error: '只允许本机' })
        try {
          const b64 = await new Promise((resolve) => {
            execFile(
              PS,
              ['-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-Command',
                [
                  'Add-Type -AssemblyName System.Windows.Forms,System.Drawing',
                  '$img = [System.Windows.Forms.Clipboard]::GetImage()',
                  'if ($img -eq $null) { [Console]::Out.Write("NONE"); exit }',
                  '$ms = New-Object System.IO.MemoryStream',
                  '$img.Save($ms, [System.Drawing.Imaging.ImageFormat]::Png)',
                  '[Console]::Out.Write(([Convert]::ToBase64String($ms.ToArray())))',
                  '$img.Dispose(); $ms.Dispose()',
                ].join('; ')],
              { timeout: 12000, maxBuffer: 96 * 1024 * 1024, windowsHide: true },
              (err, stdout) => {
                if (err) { resolve(''); return }
                resolve(String(stdout || '').trim())
              },
            )
          })
          if (!b64 || b64 === 'NONE' || b64.length < 500) {
            return json(res, 200, { ok: false, empty: true })
          }
          json(res, 200, { ok: true, dataUrl: 'data:image/png;base64,' + b64 })
        } catch (e) {
          json(res, 500, { ok: false, error: String(e?.message ?? e).slice(0, 200) })
        }
      },
    }),
  )

  // ★ 全屏框选：截整屏 → 弹 WPF 覆盖层 → 框 → 裁 → 返回 dataUrl
  ctx.effect(() =>
    ctx.webServer.register({
      kind: 'exact',
      path: '/shot/overlay',
      handler: async (req, res) => {
        if (!isLoopback(req)) return json(res, 403, { ok: false, error: '只允许本机' })
        const t0 = Date.now()
        try {
          const r = await overlayShot()
          if (r.cancel) return json(res, 200, { ok: true, cancel: true })
          json(res, 200, { ok: true, dataUrl: r.dataUrl, w: r.w, h: r.h, ms: Date.now() - t0 })
        } catch (e) {
          json(res, 500, { ok: false, error: String(e?.message ?? e).slice(0, 200) })
        }
      },
    }),
  )

  // ★ 桌宠截图：读 E:\desktop\shots\latest.txt（独立桌宠进程写的）
  // 前端每 2 秒轮询这个，有新路径就自动填进输入框
  ctx.effect(() =>
    ctx.webServer.register({
      kind: 'exact',
      path: '/shot/latest',
      handler: async (req, res) => {
        if (!isLoopback(req)) return json(res, 403, { ok: false, error: '只允许本机' })
        const f = 'E:\\desktop\\shots\\latest.txt'
        try {
          if (!existsSync(f)) return json(res, 200, { ok: true, empty: true })
          const p = readFileSync(f, 'utf8').trim()
          if (!p) return json(res, 200, { ok: true, empty: true })
          let at = 0
          try { at = statSync(p).mtimeMs } catch { at = statSync(f).mtimeMs }
          json(res, 200, { ok: true, path: p, at, exist: existsSync(p) })
        } catch (e) {
          json(res, 200, { ok: true, empty: true })
        }
      },
    }),
  )

  // 截全屏，返回 dataUrl
  ctx.effect(() =>
    ctx.webServer.register({
      kind: 'exact',
      path: '/shot/screen',
      handler: async (req, res) => {
        if (!isLoopback(req)) return json(res, 403, { ok: false, error: '只允许本机' })
        const t0 = Date.now()
        try {
          const b64 = await captureScreen(null)
          json(res, 200, {
            ok: true,
            dataUrl: 'data:image/png;base64,' + b64,
            ms: Date.now() - t0,
          })
        } catch (e) {
          json(res, 500, { ok: false, error: String(e?.message ?? e).slice(0, 200) })
        }
      },
    }),
  )

  // 存裁好的图
  ctx.effect(() =>
    ctx.webServer.register({
      kind: 'exact',
      path: '/shot/save',
      handler: async (req, res) => {
        if (!isLoopback(req)) return json(res, 403, { ok: false, error: '只允许本机' })
        if (req.method !== 'POST') return json(res, 405, { ok: false, error: '只接受 POST' })
        try {
          const raw = await readBody(req)
          let buf = raw
          let ext = 'png'
          if (raw.slice(0, 1).toString() === '{') {
            let j = null
            try { j = JSON.parse(raw.toString('utf8')) } catch { j = null }
            if (!j || !j.dataUrl) return json(res, 400, { ok: false, error: '没收到图片' })
            const m = String(j.dataUrl).match(/^data:image\/(png|jpeg|webp);base64,(.+)$/)
            if (!m) return json(res, 400, { ok: false, error: '格式不支持' })
            ext = m[1] === 'jpeg' ? 'jpg' : m[1]
            buf = Buffer.from(m[2], 'base64')
          }
          if (!buf || buf.length < 100) return json(res, 400, { ok: false, error: '图片是空的' })
          mkdirSync(OUT_DIR, { recursive: true })
          const file = join(OUT_DIR, `shot-${stamp()}.${ext}`)
          writeFileSync(file, buf)
          ctx.logger?.info?.(`dsh-shot: 存了 ${file}（${(buf.length / 1024).toFixed(0)}KB）`)
          json(res, 200, { ok: true, path: file, bytes: buf.length })
        } catch (e) {
          json(res, 500, { ok: false, error: String(e?.message ?? e) })
        }
      },
    }),
  )

  ctx.logger?.info?.('dsh-shot: 已加载（/shot/screen 走系统截屏、/shot/save 存盘）')
}
