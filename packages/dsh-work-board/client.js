/**
 * dsh-work-board — 客户端：侧栏「看板」入口 + 四栏面板
 *
 * 硬经验（照搬 my-memory 踩过的）：
 *   1. panellist 的 id 必须等于 main 的 key，否则点了空白。
 *   2. 面板状态别依赖侧栏组件（会被 owner 重挂载）。
 *   3. 卡片主体点击进对话，展开历史对话用单独的小按钮，避免误触。
 *   4. 手风琴在卡片内展开（点一下开、再点一下收），比下拉框稳。
 */

window.__ModuleLoader__.load({
  id: 'dsh-work-board',
  factory(require) {
    const React = require('react')
    const h = React.createElement
    const { useState, useEffect, useCallback } = React

    const PANEL_KEY = 'work-board'

    const C = {
      text: 'var(--dsw-alias-label-primary, #cfcfd4)',
      sub: 'var(--dsw-alias-label-secondary, #8a8a92)',
      faint: 'var(--dsw-alias-label-tertiary, #5c5c64)',
      border: 'var(--dsw-alias-separator-primary, rgba(255,255,255,0.07))',
      base: 'var(--dsw-alias-bg-base, #141417)',
      card: 'var(--dsw-alias-bg-layer-1, rgba(255,255,255,0.03))',
      accent: '#6aa9ff',
      todo: '#8a8a92',
      doing: '#6aa9ff',
      stage: '#dcb56a',
      done: '#7fcf9a',
    }

    const COLUMNS = [
      { key: 'todo', title: '待完成', hint: '想法 / 待研究 / 待安装' },
      { key: 'doing', title: '进行中', hint: '正在做的' },
      { key: 'stage', title: '阶段完成', hint: '这步完了，还没收尾' },
      { key: 'done', title: '已完成', hint: '收工' },
    ]

    function makeRpc() {
      return async (method, payload) => {
        const rpcId = 'rpc-' + Math.random().toString(36).slice(2)
        const resp = await fetch('/api/work-board', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            type: 'client-request',
            rpcId,
            method: 'work-board',
            payload: { method, payload: payload || {} },
          }),
        })
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
        const json = await resp.json()
        if (json?.result?.ok === true) return json.result.value
        throw new Error(json?.result?.error?.message ?? '请求失败')
      }
    }

    // ── 侧栏图标（细线几何，和全站风格一致）──────────────────────
    function BoardIcon({ size = 20 }) {
      const s = size
      const col = (x) => h('rect', {
        key: 'c' + x,
        x, y: 3.4, width: 4.6, height: 17.2, rx: 1.1,
        stroke: 'currentColor', strokeWidth: 0.85, fill: 'none', opacity: 0.9,
      })
      const bars = (x, ys) => ys.map((y, i) => h('line', {
        key: `b${x}-${i}`,
        x1: x + 0.9, y1: y, x2: x + 3.7, y2: y,
        stroke: 'currentColor', strokeWidth: 0.7, opacity: 0.55, strokeLinecap: 'round',
      }))
      return h('svg', {
        width: s, height: s, viewBox: '0 0 24 24', fill: 'none', 'aria-hidden': true,
        style: { display: 'block' },
      },
      col(2),
      col(9.7),
      col(17.4),
      ...bars(2, [7, 10, 13]),
      ...bars(9.7, [7, 10]),
      ...bars(17.4, [7]),
      )
    }

    const btnStyle = (active) => ({
      appearance: 'none',
      border: `1px solid ${active ? 'rgba(106,169,255,0.45)' : C.border}`,
      background: active ? 'rgba(106,169,255,0.14)' : 'transparent',
      color: active ? C.accent : C.sub,
      borderRadius: 6,
      padding: '3px 8px',
      fontSize: 11.5,
      lineHeight: 1.5,
      cursor: 'pointer',
      fontFamily: 'inherit',
      WebkitAppRegion: 'no-drag',
    })

    function Card({ card, onMove, onOpen, expanded, onToggleExpand, onOpenSession }) {
      const color = C[card.status] || C.sub
      const note = (card.note || '').trim()
      const [showNote, setShowNote] = useState(false)
      return h('div', {
        style: {
          border: `1px solid ${C.border}`,
          borderLeft: `2px solid ${color}`,
          borderRadius: 8,
          background: C.card,
          padding: '9px 10px',
          marginBottom: 8,
          display: 'flex',
          flexDirection: 'column',
          gap: 6,
        },
      },
      h('div', {
        style: { display: 'flex', alignItems: 'flex-start', gap: 6, cursor: 'pointer' },
        onClick: () => onOpen(card),
        title: '打开这个项目的对话',
      },
      h('div', { style: { flex: 1, fontSize: 13, color: '#e9e9ee', fontWeight: 500, lineHeight: 1.4, wordBreak: 'break-word' } }, card.title),
      ),

      card.nextStep
        ? h('div', { style: { fontSize: 11.5, color: C.sub, lineHeight: 1.45, wordBreak: 'break-word' } }, `→ ${card.nextStep}`)
        : null,

      note
        ? h('div', { style: { fontSize: 11.5, color: C.faint, lineHeight: 1.45 } },
          h('span', {
            style: { cursor: 'pointer', textDecoration: 'underline dotted', WebkitAppRegion: 'no-drag' },
            onClick: (e) => { e.stopPropagation(); setShowNote((v) => !v) },
          }, showNote ? '收起正文' : `正文 ${note.length} 字`),
          showNote
            ? h('div', {
              style: {
                marginTop: 5, padding: '6px 8px', borderRadius: 6,
                background: 'rgba(255,255,255,0.03)', color: C.sub,
                whiteSpace: 'pre-wrap', maxHeight: 220, overflow: 'auto',
              },
            }, note)
            : null,
        )
        : null,

      // 历史对话手风琴
      h('div', { style: { fontSize: 11.5, color: C.sub, display: 'flex', alignItems: 'center', gap: 6 } },
      h('span', {
        style: { cursor: 'pointer', WebkitAppRegion: 'no-drag' },
        onClick: (e) => { e.stopPropagation(); onToggleExpand(card.id) },
      }, `${expanded ? '▾' : '▸'} 历史对话 ${card.sessions.length}`),
      card.updatedAt ? h('span', { style: { color: C.faint } }, card.updatedAt) : null,
      ),

      expanded && card.sessions.length
        ? h('div', {
          style: {
            display: 'flex', flexDirection: 'column', gap: 3,
            paddingLeft: 8, borderLeft: `1px dashed ${C.border}`,
          },
        }, card.sessions.map((s) => h('div', {
          key: s.id,
          onClick: (e) => { e.stopPropagation(); onOpenSession(s.id) },
          title: s.id,
          style: { fontSize: 11.5, color: C.accent, cursor: 'pointer', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' },
        }, `${s.title || '未命名对话'}  ·  ${s.at || ''}`)))
        : null,

      h('div', { style: { display: 'flex', flexWrap: 'wrap', gap: 5, marginTop: 1 } },
      card.status === 'todo' ? h('button', { style: btnStyle(true), onClick: () => onMove(card, 'doing') }, '开始') : null,
      card.status === 'doing' ? h('button', { style: btnStyle(false), onClick: () => onMove(card, 'stage') }, '本步完成') : null,
      card.status === 'stage' ? h('button', { style: btnStyle(false), onClick: () => onMove(card, 'doing') }, '退回进行中') : null,
      card.status === 'stage' ? h('button', { style: btnStyle(true), onClick: () => onMove(card, 'done') }, '完成') : null,
      card.status === 'doing' ? h('button', { style: btnStyle(false), onClick: () => onMove(card, 'done') }, '完成') : null,
      card.status === 'done' ? h('button', { style: btnStyle(false), onClick: () => onMove(card, 'doing') }, '重新打开') : null,
      ),
      )
    }

    function BoardPanel({ rpc, ctx }) {
      const [snap, setSnap] = useState(null)
      const [err, setErr] = useState('')
      const [expanded, setExpanded] = useState({})

      const load = useCallback(async () => {
        try {
          const s = await rpc('snapshot')
          setSnap(s)
          setErr('')
        } catch (e) {
          setErr(String(e?.message ?? e))
        }
      }, [rpc])

      useEffect(() => {
        load()
        const t = setInterval(load, 4000)
        return () => clearInterval(t)
      }, [load])

      const uiWorkspace = (() => {
        try { return ctx?.uiWorkspace ?? ctx?.get?.('uiWorkspace') ?? null } catch { return null }
      })()

            const openSession = (id) => {
        // SessionId 既可能是裸 uuid，也可能带 session- 前缀：两种都试，取第一个成功的
        const bare = String(id || '').replace(/^session-/, '')
        const tries = [bare, `session-${bare}`]
        let lastErr = null
        for (const t of tries) {
          try {
            uiWorkspace.openSession(t)
            setErr('')
            return
          } catch (e) { lastErr = e }
        }
        setErr(`打开对话失败：${lastErr?.message ?? lastErr ?? '未知原因'}`)
      }

      const openCard = (card) => {
        const target = card.lastSessionId || (card.sessions[0] && card.sessions[0].id)
        if (target) { openSession(target); return }
        try { uiWorkspace?.startSession?.() } catch (e) { setErr(`新建对话失败：${e?.message ?? e}`) }
      }

      const onMove = async (card, status) => {
        try {
          await rpc('move', { id: card.id, status })
          load()
        } catch (e) { setErr(String(e?.message ?? e)) }
      }

      const cards = snap?.cards ?? []
      const counts = snap?.counts ?? {}

      return h('div', {
        style: {
          width: '100%', height: '100%', minHeight: 420, display: 'flex', flexDirection: 'column',
          background: C.base, color: C.text, fontFamily: 'inherit',
        },
      },
      // 顶栏
      h('div', {
        style: {
          display: 'flex', alignItems: 'center', gap: 12, padding: '10px 14px',
          borderBottom: `1px solid ${C.border}`, flex: '0 0 auto',
        },
      },
      h('div', { style: { fontSize: 14, fontWeight: 600, color: C.text, whiteSpace: 'nowrap' } }, '看板'),
      h('div', {
        style: {
          fontSize: 11.5, color: C.faint, flex: 1, minWidth: 0,
          overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
        },
      },
        `共 ${cards.length} 个项目 · ` + COLUMNS.map((c) => `${c.title} ${counts[c.key] ?? 0}`).join(' · ')),
      err ? h('div', { style: { fontSize: 11.5, color: '#e08a8a', maxWidth: 360, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' } }, err) : null,
      h('button', {
        style: { ...btnStyle(false), flex: '0 0 auto' },
        onClick: load,
      }, '刷新'),
      ),

      // 四栏
      h('div', {
        style: {
          flex: 1, display: 'flex', gap: 10, padding: 12, overflow: 'hidden',
        },
      },
      COLUMNS.map((col) => {
        const list = cards.filter((c) => c.status === col.key)
        return h('div', {
          key: col.key,
          style: {
            flex: '1 1 0', minWidth: 0, display: 'flex', flexDirection: 'column',
            border: `1px solid ${C.border}`, borderRadius: 10, overflow: 'hidden',
            background: 'rgba(255,255,255,0.015)',
          },
        },
        h('div', {
          style: {
            padding: '8px 10px', borderBottom: `1px solid ${C.border}`,
            display: 'flex', alignItems: 'baseline', gap: 6,
          },
        },
        h('span', { style: { fontSize: 12.5, fontWeight: 600, color: C[col.key] || C.text } }, col.title),
        h('span', { style: { fontSize: 11, color: C.faint } }, String(list.length)),
        h('span', { style: { fontSize: 10.5, color: C.faint, marginLeft: 'auto' } }, col.hint),
        ),
        h('div', { style: { flex: 1, overflowY: 'auto', padding: 8 } },
          list.length === 0
            ? h('div', { style: { fontSize: 11.5, color: C.faint, padding: '10px 2px' } }, '空')
            : list.map((card) => h(Card, {
              key: card.id,
              card,
              expanded: !!expanded[card.id],
              onToggleExpand: (id) => setExpanded((v) => ({ ...v, [id]: !v[id] })),
              onMove,
              onOpen: openCard,
              onOpenSession: openSession,
            })),
        ),
        )
      }),
      ),
      )
    }

    const name = 'dsh-work-board'
    const inject = ['slots', 'uiWorkspace']

    function apply(ctx) {
      const rpc = makeRpc()
      const disposers = []

      try {
        disposers.push(ctx.slots.inject('sidebar.panellist', () =>
          ctx.slots.register(
            { name: 'sidebar.panellist', id: PANEL_KEY, order: 18, label: () => '看板' },
            BoardIcon,
          ),
        ))
      } catch (e) {
        try { ctx.logger?.warn?.('work-board: 侧栏导航注册失败', e) } catch { }
      }

      try {
        disposers.push(ctx.slots.inject('main', () =>
          ctx.slots.register(
            { name: 'main', key: PANEL_KEY, inject: () => ({ rpc, ctx }) },
            BoardPanel,
          ),
        ))
      } catch (e) {
        try { ctx.logger?.warn?.('work-board: 主面板注册失败', e) } catch { }
      }

      return () => { for (const d of disposers) { try { d?.() } catch { } } }
    }

    return { name, inject, apply }
  },
})
