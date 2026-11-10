/**
 * dsh-shot —— 截图按钮（客户端）
 *
 * 贴在输入框右侧。点一下 → host 端用 .NET 截整个屏幕 → 盖一层遮罩让你拖框选区
 * → 松开自动裁切 → 存盘 → 路径填进输入框发出去。
 *
 * 为什么不用浏览器 getDisplayMedia：Electron 里它默认没注册 handler，
 * 调了不弹选择器、直接 reject，用户看到的就是「点了没反应」。
 * 而且它只能选「一个窗口」，不能像正常截图工具那样直接框屏幕的一块。
 *
 * 现在整条链是：PowerShell 截全屏（约 1 秒，双屏 3840×1080）→ 前端遮罩拖框 → canvas 裁原图像素。
 * 另：全局监听 Ctrl+V，Win+Shift+S 截的图直接粘也走同一条存盘+投递路径。
 */

window.__ModuleLoader__.load({
  id: 'dsh-shot',
  factory(require) {
    const React = require('react')
    const h = React.createElement
    const { useState, useEffect, useRef, useCallback } = React

    // 截图前的窗口尺寸（CropOverlay 卸载时还原用，两个组件共用，所以放模块级）
    let savedWin = null

    const C = {
      text: 'var(--dsh-fg, #e8e8ea)',
      sub: 'var(--dsh-fg-muted, #a8a8b0)',
      faint: 'var(--dsh-fg-faint, #6a6a72)',
      border: 'var(--dsh-border, rgba(255,255,255,0.10))',
      accent: '#6aa9ff',
      green: '#6fcf8a',
    }

    function CamIcon({ size = 16 }) {
      return h('svg', {
        width: size, height: size, viewBox: '0 0 24 24', fill: 'none',
        stroke: 'currentColor', strokeWidth: 1.7, strokeLinecap: 'round', strokeLinejoin: 'round',
      },
        h('path', { d: 'M3 8.5A2.5 2.5 0 0 1 5.5 6h1.7l1.2-1.8h7.2L16.8 6h1.7A2.5 2.5 0 0 1 21 8.5v9A2.5 2.5 0 0 1 18.5 20h-13A2.5 2.5 0 0 1 3 17.5z' }),
        h('circle', { cx: 12, cy: 13, r: 3.4 }),
      )
    }

    async function saveShot(dataUrl) {
      const r = await fetch('/shot/save', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ dataUrl }),
      })
      const j = await r.json().catch(() => null)
      if (!j || !j.ok) throw new Error((j && j.error) || '存盘失败')
      return j.path
    }

    /* ★ 全屏框选：host 截整屏 → 弹 WPF 全屏覆盖层 → 用户框 → 裁好返回 dataUrl
       这是唯一能做到「在整个屏幕上框选」的路 —— 浏览器窗口盖不住屏幕。 */
    async function grabScreen() {
      const r = await fetch('/shot/overlay', { method: 'POST', cache: 'no-store' })
      const j = await r.json().catch(() => null)
      if (!j || !j.ok) throw new Error((j && j.error) || '框选失败')
      if (j.cancel) return null
      return { url: j.dataUrl, w: j.w, h: j.h }
    }

    function crop(url, sx, sy, sw, sh) {
      return new Promise((res, rej) => {
        const im = new Image()
        im.onload = () => {
          try {
            const cv = document.createElement('canvas')
            cv.width = Math.max(1, Math.round(sw))
            cv.height = Math.max(1, Math.round(sh))
            cv.getContext('2d').drawImage(im, sx, sy, sw, sh, 0, 0, cv.width, cv.height)
            res({ url: cv.toDataURL('image/png'), w: cv.width, h: cv.height })
          } catch (e) { rej(e) }
        }
        im.onerror = () => rej(new Error('读图失败'))
        im.src = url
      })
    }

    /* ---------- 框选遮罩 ---------- */
    function CropOverlay({ shot, onDone, onCancel }) {
      const [box, setBox] = useState(null)
      const [drag, setDrag] = useState(null)
      const imgRef = useRef(null)

      const geom = useCallback(() => {
        const im = imgRef.current
        if (!im) return null
        const r = im.getBoundingClientRect()
        const sc = Math.min(r.width / shot.w, r.height / shot.h)
        const dw = shot.w * sc
        const dh = shot.h * sc
        return { left: r.left + (r.width - dw) / 2, top: r.top + (r.height - dh) / 2, dw, dh, sc }
      }, [shot])

      useEffect(() => {
        const onKey = (e) => { if (e.key === 'Escape') onCancel() }
        window.addEventListener('keydown', onKey)
        return () => {
          window.removeEventListener('keydown', onKey)
          try { if (document.fullscreenElement) document.exitFullscreen() } catch { }
          // 还原窗口尺寸
          const s = savedWin
          if (s && s.w) {
            try { window.moveTo(s.x, s.y); window.resizeTo(s.w, s.h) } catch { }
            savedWin = null
          }
        }
      }, [onCancel])

      const down = (e) => {
        if (e.button !== 0) return
        setDrag({ x0: e.clientX, y0: e.clientY })
        setBox({ x: e.clientX, y: e.clientY, w: 0, h: 0 })
        e.preventDefault()
      }

      const move = (e) => {
        if (!drag) return
        const x = Math.min(drag.x0, e.clientX)
        const y = Math.min(drag.y0, e.clientY)
        setBox({ x, y, w: Math.abs(e.clientX - drag.x0), h: Math.abs(e.clientY - drag.y0) })
      }

      const up = () => {
        if (!drag || !box) { setDrag(null); return }
        setDrag(null)
        const g = geom()
        if (!g || box.w < 6 || box.h < 6) { setBox(null); return }
        const x0 = Math.max(g.left, box.x)
        const y0 = Math.max(g.top, box.y)
        const x1 = Math.min(g.left + g.dw, box.x + box.w)
        const y1 = Math.min(g.top + g.dh, box.y + box.h)
        const sw = x1 - x0
        const sh = y1 - y0
        if (sw < 4 || sh < 4) { setBox(null); return }
        onDone({
          sx: (x0 - g.left) / g.sc,
          sy: (y0 - g.top) / g.sc,
          sw: sw / g.sc,
          sh: sh / g.sc,
        })
      }

      return h('div', {
        onMouseDown: down,
        onMouseMove: move,
        onMouseUp: up,
        style: {
          position: 'fixed', inset: 0, zIndex: 99999,
          background: '#000',
          cursor: 'crosshair', userSelect: 'none',
        },
      },
        h('img', {
          ref: imgRef,
          src: shot.url,
          draggable: false,
          style: {
            position: 'absolute', inset: 0, width: '100%', height: '100%',
            objectFit: 'fill', opacity: 1, pointerEvents: 'none',
          },
        }),
        (box && box.w > 0 && box.h > 0)
          ? h('div', {
            style: {
              position: 'absolute', left: box.x, top: box.y, width: box.w, height: box.h,
              border: '2px solid #6aa9ff',
              boxShadow: '0 0 0 9999px rgba(0,0,0,0.58)',
              pointerEvents: 'none',
              background: 'transparent',
            },
          },

            h('div', {
              style: {
                position: 'absolute', left: 0, top: -24, fontSize: 11.5,
                padding: '2px 7px', borderRadius: 4, whiteSpace: 'nowrap',
                background: '#ffffff', color: '#111', fontWeight: 600,
              },
            }, `${Math.round(box.w)} × ${Math.round(box.h)}`),
          )
          : null,
        h('div', {
          style: {
            position: 'fixed', top: 18, left: '50%', transform: 'translateX(-50%)',
            padding: '8px 18px', borderRadius: 8, pointerEvents: 'none',
            background: 'rgba(20,20,24,0.92)', border: '1px solid rgba(255,255,255,0.14)',
            color: '#e8e8ea', fontSize: 13,
            display: 'flex', gap: 14, alignItems: 'center',
          },
        },
          h('span', null, '拖一个框，松开就截（两个屏都在这张图里）'),
          h('span', { style: { color: '#6a6a72', fontSize: 12 } }, 'Esc 取消'),
        ),
      )
    }

    /* ---------- 主按钮 ---------- */
    function ShotButton(props) {
      const inputActions = props?.inputActions
      const [busy, setBusy] = useState(false)
      const [shot, setShot] = useState(null)
      const [tip, setTip] = useState('')
      const [bad, setBad] = useState(false)
      const cancelled = useRef(false)

      const flash = useCallback((msg, isBad) => {
        setTip(msg)
        setBad(!!isBad)
        setTimeout(() => setTip(''), 3400)
      }, [])

      // 只把路径填进输入框，不自动发送 —— 用户要补一句「我为什么截这张图」
      const deliver = useCallback((path) => {
        const text = `[截图] ${path}\n`
        try {
          if (inputActions?.setDraft) {
            inputActions.setDraft(text)
            // 把焦点和光标放到末尾，用户可以直接开始打字
            setTimeout(() => {
              try {
                const ae = document.activeElement
                const ta = (ae && (ae.tagName === 'TEXTAREA' || ae.isContentEditable)) ? ae : document.querySelector('textarea')
                if (ta) {
                  ta.focus()
                  if (ta.tagName === 'TEXTAREA') {
                    const n = ta.value.length
                    try { ta.setSelectionRange(n, n) } catch { }
                  }
                }
              } catch { }
            }, 120)
            return true
          }
        } catch { }
        return false
      }, [inputActions])

          // 就在当前窗口里截：不动窗口、不全屏、不占屏
      const start = useCallback(async () => {
        if (busy) return
        setBusy(true); setTip('')
        try {
          const f = await grabScreen()
          if (!f) { setBusy(false); flash('取消了', false); return }
          // 图是整块虚拟桌面（两块屏拼起来），交给 CropOverlay 在窗口里框
          setShot(f)
        } catch (e) {
          flash('截图失败：' + String(e?.message ?? e).slice(0, 60), true)
        }
        setBusy(false)
      }, [busy, flash])

      const finish = useCallback(async (sel) => {
        const cur = shot
        setShot(null)
        if (!cur) return
        setBusy(true)
        try {
          const c2 = await crop(cur.url, sel.sx, sel.sy, sel.sw, sel.sh)
          const path = await saveShot(c2.url)
          const ok = deliver(path)
          flash(ok ? `已截 ${c2.w}×${c2.h}，填进输入框了，补句话再发` : `已存：${path}`, false)
        } catch (e) {
          flash('裁切/存盘失败：' + String(e?.message ?? e).slice(0, 50), true)
        }
        setBusy(false)
      }, [shot, deliver, flash])

      useEffect(() => {
        const onPaste = async (e) => {
          const items = e.clipboardData?.items
          if (!items) return
          for (const it of items) {
            if (!it.type || !it.type.startsWith('image/')) continue
            const f = it.getAsFile()
            if (!f) continue
            e.preventDefault()
            setBusy(true)
            try {
              const dataUrl = await new Promise((res, rej) => {
                const fr = new FileReader()
                fr.onload = () => res(String(fr.result || ''))
                fr.onerror = () => rej(new Error('读剪贴板失败'))
                fr.readAsDataURL(f)
              })
              const path = await saveShot(dataUrl)
              const ok = deliver(path)
              flash(ok ? '粘贴的图已发出' : `已存：${path}`, false)
            } catch (err) {
              flash('粘贴失败：' + String(err?.message ?? err).slice(0, 50), true)
            }
            setBusy(false)
            return
          }
        }
        window.addEventListener('paste', onPaste)
        return () => window.removeEventListener('paste', onPaste)
      }, [deliver, flash])

      /* ★ 轮询桌宠截图：桌面右下角那个小金球框完会写 latest.txt，这里接住自动填进输入框 */
      useEffect(() => {
        let last = ''
        let alive = true
        const tick = async () => {
          if (!alive) return
          try {
            const r = await fetch('/shot/latest', { cache: 'no-store' })
            const j = await r.json()
            if (j && j.ok && j.path && j.path !== last && j.exist) {
              last = j.path
              const ok = deliver(j.path)
              flash(ok ? '桌宠截图已填入，补句话就发' : ('已存：' + j.path), false)
            }
          } catch { }
          if (alive) setTimeout(tick, 2000)
        }
        tick()
        return () => { alive = false }
      }, [deliver, flash])

      return h('div', { style: { display: 'inline-flex', alignItems: 'center' } },
        h('div', { style: { position: 'relative', display: 'inline-flex', alignItems: 'center' } },
          h('button', {
            type: 'button',
            onClick: start,
            disabled: busy,
            title: busy ? '正在截屏…' : '截图（点一下直接框选，Ctrl+V 也能粘图）',
            style: {
              appearance: 'none',
              width: 30, height: 30, borderRadius: 7,
              display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
              border: `1px solid ${busy ? 'rgba(106,169,255,0.5)' : C.border}`,
              background: busy ? 'rgba(106,169,255,0.14)' : 'transparent',
              color: busy ? C.accent : C.sub,
              cursor: busy ? 'default' : 'pointer',
              padding: 0, fontFamily: 'inherit',
              transition: 'background 150ms, border-color 150ms, color 150ms',
            },
            onMouseEnter: (e) => {
              if (!busy) { e.currentTarget.style.background = 'rgba(255,255,255,0.06)'; e.currentTarget.style.color = C.text }
            },
            onMouseLeave: (e) => {
              if (!busy) { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = C.sub }
            },
          },
            busy
              ? h('div', {
                style: {
                  width: 12, height: 12, borderRadius: '50%',
                  border: `1.6px solid ${C.accent}`, borderTopColor: 'transparent',
                  animation: 'dsh-shot-spin 0.7s linear infinite',
                },
              })
              : h(CamIcon, { size: 16 }),
          ),
          tip ? h('div', {
            style: {
              position: 'absolute', bottom: 38, right: 0, whiteSpace: 'nowrap',
              fontSize: 11.5, padding: '4px 9px', borderRadius: 6,
              background: bad ? 'rgba(224,113,111,0.16)' : 'rgba(111,207,138,0.14)',
              border: `1px solid ${bad ? 'rgba(224,113,111,0.4)' : 'rgba(111,207,138,0.35)'}`,
              color: bad ? '#f0a5a3' : C.green,
              pointerEvents: 'none', zIndex: 10,
            },
          }, tip) : null,
        ),
        h('style', { key: 'shot-css' }, '@keyframes dsh-shot-spin{to{transform:rotate(360deg)}}'),
        shot ? h(CropOverlay, {
          shot,
          onDone: finish,
          onCancel: () => { setShot(null); flash('取消了', false) },
        }) : null,

      )
    }

    const name = 'dsh-shot'
    const inject = ['slots']

    function apply(ctx) {
      const disposers = []
      try {
        disposers.push(ctx.slots.inject('conversation.input.right', () =>
          ctx.slots.register(
            { name: 'conversation.input.right', id: 'shot-btn', order: 50, label: () => '截图' },
            ShotButton,
          ),
        ))
      } catch (e) {
        try { ctx.logger?.warn?.('dsh-shot: 截图按钮注册失败', e) } catch { }
      }
      return () => { for (const d of disposers) { try { d?.() } catch { } } }
    }

    return { name, inject, apply }
  },
})
