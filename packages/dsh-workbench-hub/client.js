/**
 * dsh-workbench-hub —— 客户端：侧栏一个「工作台」入口，里面是各工作台的合集。
 *
 * 约定：任何工作台插件往 window.__DSH_WORKBENCHES__ 里 push 一项：
 *   { id, title, desc, order?, Icon?, Component }
 * 然后 dispatch 'dsh-workbench-changed'，合集页会自动刷新。
 */

window.__ModuleLoader__.load({
  id: 'dsh-workbench-hub',
  factory(require) {
    const React = require('react')
    const h = React.createElement
    const { useState, useEffect, useCallback, useRef } = React

    const PANEL_KEY = 'workbench'
    const REGISTRY = '__DSH_WORKBENCHES__'
    const EVENT = 'dsh-workbench-changed'

    const C = {
      text: 'var(--dsw-alias-label-primary)',
      sub: 'var(--dsw-alias-label-secondary)',
      border: 'var(--dsw-alias-border-l1)',
      base: 'var(--dsw-alias-bg-base)',
      cell: 'var(--dsw-alias-bg-layer-1)',
      accent: 'var(--dsw-alias-brand-primary)',
    }

    const ORDER_KEY = 'dsh-workbench-order'
    const ACTIVE_KEY = 'dsh-workbench-active'

    /* 卡片悬停动效 + 点击张开 */
    const HUB_CSS = `
.wb-card{
  transition:
    transform .26s cubic-bezier(.22,.68,.32,1),
    box-shadow .26s cubic-bezier(.22,.68,.32,1),
    border-color .2s ease,
    background-color .2s ease;
  will-change: transform;
}
.wb-card:hover{
  transform: translateY(-7px) scale(1.045);
  box-shadow: 0 26px 52px -22px rgba(0,0,0,.62), 0 4px 12px -6px rgba(0,0,0,.32);
}
.wb-card:hover .wb-title{ color: var(--dsw-alias-brand-primary); }
.wb-card:active{ transform: translateY(-3px) scale(1.022); }
/* 拖拽悬停目标：让位收缩 */
.wb-over{ transform: scale(.97) !important; }
.wb-title{ transition: color .2s ease; }
.wb-preview{
  transition: transform .5s cubic-bezier(.22,.68,.32,1), filter .32s ease;
  transform-origin: center top;
  filter: saturate(.94);
}
.wb-card:hover .wb-preview{
  transform: scale(1.018);
  filter: saturate(1.08);
}
/* 打开：从卡片位置张开（慢、稳） */
.wb-sheet{
  transition:
    transform .58s cubic-bezier(.16,.84,.3,1),
    opacity .42s ease;
  will-change: transform, opacity;
  backface-visibility: hidden;
}
.wb-sheet-enter{
  opacity: 0;
}
/* 关闭：淡出 + 轻收，不做位移 */
.wb-sheet-leave{
  opacity: 0;
  transform: scale(.97);
}
/* 组件本体统一淡入——不管它自己渲染得多快 */
@keyframes wb-content-in{
  from{ opacity: 0; transform: translateY(6px) scale(.995); }
  to{ opacity: 1; transform: none; }
}
.wb-sheet-body{
  animation: wb-content-in .5s cubic-bezier(.16,.84,.3,1) both;
}
/* 卡片墙淡出 */
.wb-wall{
  transition: opacity .26s ease, transform .32s cubic-bezier(.22,.68,.32,1);
}
.wb-wall-out{
  opacity: 0;
  transform: scale(.985);
  pointer-events: none;
}
@media (prefers-reduced-motion: reduce){
  .wb-card, .wb-preview, .wb-title, .wb-sheet, .wb-wall{ transition: none !important; }
  .wb-card:hover, .wb-card:active{ transform: none; }
  .wb-card:hover .wb-preview{ transform: none; }
  .wb-sheet-enter, .wb-sheet-leave{ opacity: 1; transform: none; }
}
`

    function readOrder() {
      try {
        const a = JSON.parse(window.localStorage.getItem(ORDER_KEY) || '[]')
        return Array.isArray(a) ? a : []
      } catch { return [] }
    }

    function saveOrder(ids) {
      try { window.localStorage.setItem(ORDER_KEY, JSON.stringify(ids)) } catch { }
    }

    function list() {
      const arr = window[REGISTRY]
      if (!Array.isArray(arr)) return []
      const order = readOrder()
      const rank = (id) => {
        const i = order.indexOf(id)
        return i < 0 ? Number.MAX_SAFE_INTEGER : i
      }
      return arr.slice().sort((a, b) => {
        const ra = rank(a.id)
        const rb = rank(b.id)
        if (ra !== rb) return ra - rb
        return (a.order || 50) - (b.order || 50)
      })
    }

    function Icon({ size = 20 }) {
      // 九宫格：三个方块
      return h('svg', { width: size, height: size, viewBox: '0 0 24 24', fill: 'none', 'aria-hidden': true, style: { display: 'block' } },
        h('rect', { x: 3.5, y: 3.5, width: 7, height: 7, rx: 1.2, stroke: 'currentColor', strokeWidth: 0.9 }),
        h('rect', { x: 13.5, y: 3.5, width: 7, height: 7, rx: 1.2, stroke: 'currentColor', strokeWidth: 0.9 }),
        h('rect', { x: 3.5, y: 13.5, width: 7, height: 7, rx: 1.2, stroke: 'currentColor', strokeWidth: 0.9 }),
        h('rect', { x: 13.5, y: 13.5, width: 7, height: 7, rx: 1.2, stroke: 'currentColor', strokeWidth: 0.9, opacity: 0.45 }),
      )
    }

    /** 预览：把工作台按 1024×640 的虚拟窗口渲染，再等比缩到卡片宽度，整框完整可见 */
    function Preview({ Component }) {
      const boxRef = useRef(null)
      const [scale, setScale] = useState(0.34)
      useEffect(() => {
        const el = boxRef.current
        if (!el) return undefined
        const update = () => { if (el.clientWidth) setScale(el.clientWidth / 1024) }
        update()
        let ro
        try {
          ro = new ResizeObserver(update)
          ro.observe(el)
        } catch { }
        return () => { try { ro?.disconnect() } catch { } }
      }, [])
      const H = 640
      return h('div', {
        ref: boxRef,
        className: 'wb-preview',
        style: {
          position: 'relative', height: Math.round(H * scale), overflow: 'hidden',
          background: C.base, borderTop: `1px solid ${C.border}`,
        },
      },
      Component
        ? h('div', {
          style: {
            position: 'absolute', left: 0, top: 0, width: 1024, height: H,
            transform: `scale(${scale})`, transformOrigin: 'top left',
            pointerEvents: 'none', userSelect: 'none',
          },
        }, h(Component, null))
        : null,
      )
    }

    function Hub() {
      const [items, setItems] = useState(list())
      // 记住当前打开的是哪个工作台：切到别的页面再回来，不退回列表页
      const [activeId, setActiveId] = useState(() => {
        try { return window.localStorage.getItem(ACTIVE_KEY) || null } catch { return null }
      })
      // 打开哪个就记住哪个（关掉时清掉）
      useEffect(() => {
        try {
          if (activeId) window.localStorage.setItem(ACTIVE_KEY, activeId)
          else window.localStorage.removeItem(ACTIVE_KEY)
        } catch { }
      }, [activeId])
      // drag: { id, ox, oy, x, y, w, h }
      const [drag, setDrag] = useState(null)
      const [overId, setOverId] = useState(null)
      const dragRef = useRef(null)
      // 拖拽结束后紧跟的 click 要吞掉，否则会误打开工作台
      const suppressClickRef = useRef(false)

      useEffect(() => {
        const sync = () => setItems(list())
        sync()
        window.addEventListener(EVENT, sync)
        return () => window.removeEventListener(EVENT, sync)
      }, [])

      // 拖动一个卡片到另一个卡片上 → 在网格里互换位置并持久化
      const reorder = (fromId, toId) => {
        const ids = items.map((x) => x.id)
        const from = ids.indexOf(fromId)
        const to = ids.indexOf(toId)
        if (from < 0 || to < 0 || from === to) return
        ids.splice(to, 0, ids.splice(from, 1)[0])
        saveOrder(ids)
        setItems(list())
      }

      // 指针拖拽：卡片实体跟随鼠标，松手落位
      const onCardDown = (e, it) => {
        if (e.button !== 0) return
        const rect = e.currentTarget.getBoundingClientRect()
        const d = {
          id: it.id,
          ox: e.clientX - rect.left,
          oy: e.clientY - rect.top,
          x: rect.left,
          y: rect.top,
          w: rect.width,
          h: rect.height,
          moved: false,
        }
        dragRef.current = d
        setDrag(d)
        setOverId(null)
        try { e.currentTarget.setPointerCapture?.(e.pointerId) } catch { }
      }

      useEffect(() => {
        if (!drag) return undefined
        let raf = 0
        let pending = null

        const flush = () => {
          raf = 0
          if (!pending) return
          const { x, y, over } = pending
          pending = null
          setDrag((d) => (d ? { ...d, x, y, moved: true } : d))
          setOverId(over)
        }

        const onMove = (e) => {
          const d = dragRef.current
          if (!d) return
          const nx = e.clientX - d.ox
          const ny = e.clientY - d.oy
          // 超过阈值才算"拖拽"，纯点击不标记
          if (!d.moved && (Math.abs(nx - d.x) > 5 || Math.abs(ny - d.y) > 5)) d.moved = true
          // 落点判定：被拖卡片 pointerEvents 为 none，能取到下面的卡片
          let over = null
          if (typeof document !== 'undefined') {
            const el = document.elementFromPoint(e.clientX, e.clientY)
            const card = el && el.closest ? el.closest('[data-wb-id]') : null
            if (card) over = card.getAttribute('data-wb-id')
          }
          if (over === d.id) over = null
          pending = { x: nx, y: ny, over }
          if (!raf) raf = requestAnimationFrame(flush)
        }

        const onUp = () => {
          const d = dragRef.current
          dragRef.current = null
          if (d && d.moved) {
            // 抑制紧随其后的 click
            suppressClickRef.current = true
            setTimeout(() => { suppressClickRef.current = false }, 300)
          }
          if (d && overId && overId !== d.id && d.moved !== false) reorder(d.id, overId)
          setDrag(null)
          setOverId(null)
        }

        window.addEventListener('pointermove', onMove, { passive: true })
        window.addEventListener('pointerup', onUp)
        window.addEventListener('pointercancel', onUp)
        return () => {
          if (raf) cancelAnimationFrame(raf)
          window.removeEventListener('pointermove', onMove)
          window.removeEventListener('pointerup', onUp)
          window.removeEventListener('pointercancel', onUp)
        }
      }, [drag, overId, items])

      const active = items.find((x) => x.id === activeId)

      // 点击卡片 → 记录它在容器里的位置，让界面从那个位置张开
      const wrapRef = useRef(null)
      const [origin, setOrigin] = useState(null)
      // 恢复上次打开的工作台时直接是"已展开"状态，不跑入场动画（否则会停在 scale(0)/opacity(0) 的黑屏）
      const [sheetIn, setSheetIn] = useState(() => {
        try { return !!window.localStorage.getItem(ACTIVE_KEY) } catch { return false }
      })
      const [sheetKey, setSheetKey] = useState(0)
      const [leaving, setLeaving] = useState(false)

      const openCard = (e, it) => {
        const el = e && e.currentTarget
        const wrap = wrapRef.current
        let o = null
        if (el && wrap) {
          const r = el.getBoundingClientRect()
          const w = wrap.getBoundingClientRect()
          if (w.width && w.height) {
            o = {
              x: r.left - w.left,
              y: r.top - w.top,
              sw: Math.max(r.width / w.width, 0.06),
              sh: Math.max(r.height / w.height, 0.06),
            }
          }
        }
        // 先用目标位置渲染（隐藏），再触发过渡 —— key 变化强制重挂，避免二次点击没动画
        setOrigin(o)
        setSheetIn(false)
        setLeaving(false)
        setSheetKey((k) => k + 1)
        setActiveId(it.id)
        requestAnimationFrame(() => requestAnimationFrame(() => setSheetIn(true)))
      }

      const closeCard = () => {
        setSheetIn(false)
        setLeaving(true)
        setTimeout(() => {
          setActiveId(null)
          setOrigin(null)
          setLeaving(false)
        }, 360)
      }

      const backBar = (title, onBack) => h('div', {
        style: { display: 'flex', alignItems: 'center', gap: 8, padding: '9px 14px', borderBottom: `1px solid ${C.border}`, flex: 'none' },
      },
      h('button', {
        type: 'button',
        onClick: onBack || (() => setActiveId(null)),
        style: {
          appearance: 'none', border: `1px solid ${C.border}`, background: 'var(--dsw-alias-bg-layer-2)',
          color: C.text, borderRadius: 6, padding: '3px 10px', fontSize: 12.5, cursor: 'pointer', fontFamily: 'inherit',
        },
      }, '‹ 工作台'),
      h('span', { style: { fontSize: 13.5, fontWeight: 600, color: C.accent } }, title),
      )

      if (active && active.Component) {
        const style = { height: '100%', display: 'flex', flexDirection: 'column', background: C.base, color: C.text, fontFamily: 'inherit' }
        if (!sheetIn && origin && !leaving) {
          style.transformOrigin = 'top left'
          style.transform = `translate(${origin.x}px, ${origin.y}px) scale(${origin.sw}, ${origin.sh})`
          style.opacity = 0
          style.borderRadius = 14
          style.overflow = 'hidden'
        }
        const cls = leaving ? 'wb-sheet wb-sheet-leave' : (sheetIn ? 'wb-sheet' : 'wb-sheet wb-sheet-enter')
        return h('div', { ref: wrapRef, style: { height: '100%', position: 'relative', overflow: 'hidden' } },
          h('style', { key: 'wb-css' }, HUB_CSS),
          h('div', { key: sheetKey, className: cls, style: { ...style, position: 'relative', zIndex: 2 } },
            backBar(active.title, closeCard),
            h('div', { className: 'wb-sheet-body', style: { flex: '1 1 auto', minHeight: 0, position: 'relative' } }, h(active.Component, null)),
          ),
        )
      }

      return h('div', { ref: wrapRef, style: { height: '100%', display: 'flex', flexDirection: 'column', background: C.base, color: C.text, fontFamily: 'inherit' } },
        h('style', { key: 'wb-css' }, HUB_CSS),
        h('div', { style: { padding: '10px 16px', borderBottom: `1px solid ${C.border}` } },
          h('span', { style: { fontSize: 14, fontWeight: 600, color: C.accent } }, '工作台'),
          h('span', { style: { marginLeft: 10, fontSize: 11.5, color: C.sub } }, `${items.length} 个`),
        ),
        items.length === 0
          ? h('div', { style: { flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: C.sub, fontSize: 13 } },
            '还没有安装工作台（装好的工作台会自己出现在这里）')
          : h('div', {
            style: {
              flex: '1 1 auto', minHeight: 0, overflowY: 'auto', padding: 16,
              display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: 14, alignContent: 'start',
            },
          },
          items.map((it) => {
            const isSelfDragging = !!(drag && drag.id === it.id)
            const isOver = overId === it.id
            const dragging = !!drag
            return h('div', {
              key: it.id,
              'data-wb-id': it.id,
              className: isOver ? 'wb-card wb-over' : 'wb-card',
              onPointerDown: (e) => onCardDown(e, it),
              onClick: (e) => {
                if (suppressClickRef.current) return
                if (!dragRef.current) openCard(e, it)
              },
              style: {
                textAlign: 'left', cursor: dragging ? 'grabbing' : 'grab', fontFamily: 'inherit',
                border: `1px solid ${isOver ? C.accent : C.border}`,
                background: C.cell,
                color: C.text,
                borderRadius: 10, padding: 0, overflow: 'hidden',
                display: 'flex', flexDirection: 'column',
                opacity: isSelfDragging ? 0 : 1,
                boxShadow: isOver ? `0 0 0 2px ${C.accent}55` : 'none',
                transition: dragging ? 'none' : 'transform .26s cubic-bezier(.22,.68,.32,1), border-color .2s ease, box-shadow .2s ease',
                touchAction: 'none',
                userSelect: 'none',
              },
            },
            // 标题在上（固定高度，保证所有卡片的预览区起点一致）
            h('span', {
              style: {
                display: 'flex', alignItems: 'center', gap: 9,
                padding: '13px 15px 12px',
                height: 74, boxSizing: 'border-box', flex: 'none',
                overflow: 'hidden',
              },
            },
              h('span', { style: { color: C.accent, flex: 'none' } },
                it.Icon ? h(it.Icon, { size: 18 }) : h(Icon, { size: 18 }),
              ),
              h('span', { style: { display: 'flex', flexDirection: 'column', gap: 3, minWidth: 0 } },
                h('span', {
                  className: 'wb-title',
                  style: {
                    fontSize: 17, fontWeight: 600, letterSpacing: 0.3, lineHeight: 1.25,
                    display: '-webkit-box', WebkitLineClamp: 1, WebkitBoxOrient: 'vertical', overflow: 'hidden',
                  },
                }, it.title),
                h('span', {
                  style: {
                    fontSize: 12.5, color: C.sub, lineHeight: 1.45,
                    display: '-webkit-box', WebkitLineClamp: 1, WebkitBoxOrient: 'vertical', overflow: 'hidden',
                  },
                }, it.desc || ''),
              ),
            ),
            // 预览在下
            h(Preview, { Component: it.Component }),
            )
          }),
        ),
        // 拖动中的实体卡片：跟手、不透明、带投影
        drag && (() => {
          const it = items.find((x) => x.id === drag.id)
          if (!it) return null
          return h('div', {
            key: '__drag_clone',
            style: {
              position: 'fixed',
              left: drag.x, top: drag.y, width: drag.w,
              zIndex: 9999, pointerEvents: 'none',
              border: `1px solid ${C.accent}`, background: C.cell, color: C.text,
              borderRadius: 10, overflow: 'hidden',
              display: 'flex', flexDirection: 'column',
              transform: 'scale(1.04) rotate(-0.6deg)',
              transformOrigin: 'center center',
              boxShadow: '0 28px 64px -16px rgba(0,0,0,.7), 0 0 0 1px rgba(255,255,255,.06) inset',
              opacity: 1,
              willChange: 'left, top, transform',
            },
          },
          h('span', { style: { display: 'flex', alignItems: 'center', gap: 9, padding: '13px 15px 12px' } },
            h('span', { style: { color: C.accent, flex: 'none' } },
              it.Icon ? h(it.Icon, { size: 18 }) : h(Icon, { size: 18 }),
            ),
            h('span', { style: { display: 'flex', flexDirection: 'column', gap: 3, minWidth: 0 } },
              h('span', { style: { fontSize: 17, fontWeight: 600, letterSpacing: 0.3 } }, it.title),
              h('span', { style: { fontSize: 12.5, color: C.sub, lineHeight: 1.45 } }, it.desc || ''),
            ),
          ),
          h('div', { style: { flex: '1 1 auto', minHeight: 0, display: 'flex', flexDirection: 'column' } },
            h(Preview, { Component: it.Component }),
          ),
          )
        })(),
      )
    }

    const name = 'dsh-workbench-hub'
    const inject = ['slots']

    function apply(ctx) {
      const disposers = []
      try {
        disposers.push(ctx.slots.inject('sidebar.panellist', () =>
          ctx.slots.register({ name: 'sidebar.panellist', id: PANEL_KEY, order: 8, label: () => '工作台' }, Icon),
        ))
      } catch (e) { try { ctx.logger?.warn?.('workbench-hub: 侧栏注册失败', e) } catch { } }
      try {
        disposers.push(ctx.slots.inject('main', () =>
          ctx.slots.register({ name: 'main', key: PANEL_KEY }, Hub),
        ))
      } catch (e) { try { ctx.logger?.warn?.('workbench-hub: 主面板注册失败', e) } catch { } }
      return () => { for (const d of disposers) { try { d?.() } catch { } } }
    }

    return { name, inject, apply }
  },
})
