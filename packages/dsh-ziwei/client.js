/**
 * dsh-ziwei — 客户端：侧栏「算命」入口 + 整页紫微命盘 + AI 解读抽屉
 *
 * 交互：零打字。年份按十年翻页（一屏十来个，不铺 87 个）；其余下拉同样自绘暗色网格。
 */

window.__ModuleLoader__.load({
  id: 'dsh-ziwei',
  factory(require) {
    const React = require('react')
    const h = React.createElement
    const { useState, useEffect, useCallback, useRef, useMemo } = React

    const PANEL_KEY = 'ziwei'
    const STORE_KEY = 'dsh-ziwei:last'
    const HINT_KEY = 'dsh-ziwei:yearHintSeen'
    const qaKeyOf = (date, timeIndex, gender) => `dsh-ziwei:qa:v2:${date}|${timeIndex}|${gender}`
    function loadTurns(key) {
      try {
        const arr = JSON.parse(window.localStorage.getItem(key) || '[]')
        if (!Array.isArray(arr)) return []
        const byQ = new Map()
        for (const t of arr) {
          if (!t || !t.q || typeof t.a !== 'string' || t.a.length < 8) continue
          byQ.set(t.q, t) // 同一个问题只留最后一版
        }
        return [...byQ.values()].map((t, i) => ({ ...t, id: `h${Date.now()}${i}` }))
      } catch { return [] }
    }

    /** 跟随主题：探针读取真实的主题底色，判断深浅 */
    function detectDark() {
      try {
        const probe = document.createElement('div')
        probe.style.cssText = 'position:fixed;left:-9999px;top:0;width:1px;height:1px;background:var(--dsw-alias-bg-base)'
        document.body.appendChild(probe)
        const rgb = getComputedStyle(probe).backgroundColor
        document.body.removeChild(probe)
        const m = rgb.match(/\d+(\.\d+)?/g)
        if (m && m.length >= 3) {
          const lum = Number(m[0]) * 0.299 + Number(m[1]) * 0.587 + Number(m[2]) * 0.114
          return lum < 128
        }
      } catch { }
      return true
    }

    const IS_DARK = detectDark()

    const C = {
      text: 'var(--dsw-alias-label-primary)',
      sub: 'var(--dsw-alias-label-secondary)',
      faint: 'var(--dsw-alias-label-secondary)',
      border: 'var(--dsw-alias-border-l1)',
      borderStrong: 'var(--dsw-alias-border-l2)',
      base: 'var(--dsw-alias-bg-base)',
      cell: 'var(--dsw-alias-bg-layer-1)',
      cellAlt: 'var(--dsw-alias-bg-layer-2)',
      pop: 'var(--dsw-alias-bg-overlay)',
      drawer: 'var(--dsw-alias-bg-layer-1)',
      sheet: 'var(--dsw-alias-bg-overlay)',
      accent: IS_DARK ? '#d8b877' : '#8a5a1e',
      body: IS_DARK ? '#cfc9bd' : '#2f2c27',
      starMain: IS_DARK ? '#f0e6d2' : '#24304f',
      starMinor: IS_DARK ? '#a8cfc9' : '#1f5f5b',
      starBright: IS_DARK ? '#d8b877' : '#7a4a12',
      red: 'var(--dsw-alias-state-error-primary)',
      green: 'var(--dsw-alias-state-success-primary)',
      blue: IS_DARK ? '#8ab4e8' : '#2f5c8a',
      yellow: IS_DARK ? '#dcbf7a' : '#7a5a10',
    }

    const HOURS = ['早子时 00-01', '丑时 01-03', '寅时 03-05', '卯时 05-07', '辰时 07-09', '巳时 09-11',
      '午时 11-13', '未时 13-15', '申时 15-17', '酉时 17-19', '戌时 19-21', '亥时 21-23', '晚子时 23-24']

    const CELL = {
      巳: [1, 1], 午: [1, 2], 未: [1, 3], 申: [1, 4],
      辰: [2, 1], 酉: [2, 4],
      卯: [3, 1], 戌: [3, 4],
      寅: [4, 1], 丑: [4, 2], 子: [4, 3], 亥: [4, 4],
    }

    const MUTAGEN_COLOR = { 禄: C.green, 权: C.blue, 科: C.yellow, 忌: C.red }

    const fieldStyle = {
      appearance: 'none',
      background: 'var(--dsw-alias-bg-layer-2)',
      border: `1px solid ${C.border}`,
      borderRadius: 6,
      color: C.text,
      padding: '4px 8px',
      fontSize: 12.5,
      fontFamily: 'inherit',
      cursor: 'pointer',
      display: 'flex',
      alignItems: 'center',
      gap: 4,
      userSelect: 'none',
      whiteSpace: 'nowrap',
      outline: 'none',
    }

    const btnStyle = {
      appearance: 'none',
      border: `1px solid color-mix(in srgb, ${C.accent} 55%, transparent)`,
      background: `color-mix(in srgb, ${C.accent} 14%, transparent)`,
      color: C.accent,
      borderRadius: 6,
      padding: '4px 14px',
      fontSize: 12.5,
      cursor: 'pointer',
      fontFamily: 'inherit',
    }

    function Icon({ size = 20 }) {
      const s = size
      return h('svg', { width: s, height: s, viewBox: '0 0 24 24', fill: 'none', 'aria-hidden': true, style: { display: 'block' } },
        h('circle', { cx: 12, cy: 12, r: 9, stroke: 'currentColor', strokeWidth: 0.9, opacity: 0.9 }),
        h('circle', { cx: 12, cy: 12, r: 5.2, stroke: 'currentColor', strokeWidth: 0.8, opacity: 0.6 }),
        h('line', { x1: 12, y1: 2.2, x2: 12, y2: 7.2, stroke: 'currentColor', strokeWidth: 0.8, opacity: 0.7 }),
        h('line', { x1: 12, y1: 16.8, x2: 12, y2: 21.8, stroke: 'currentColor', strokeWidth: 0.8, opacity: 0.7 }),
        h('line', { x1: 2.2, y1: 12, x2: 7.2, y2: 12, stroke: 'currentColor', strokeWidth: 0.8, opacity: 0.7 }),
        h('line', { x1: 16.8, y1: 12, x2: 21.8, y2: 12, stroke: 'currentColor', strokeWidth: 0.8, opacity: 0.7 }),
        h('circle', { cx: 12, cy: 12, r: 1.4, fill: 'currentColor' }),
      )
    }

    function useOutside(ref, open, close) {
      useEffect(() => {
        if (!open) return undefined
        const onDoc = (e) => { if (ref.current && !ref.current.contains(e.target)) close() }
        document.addEventListener('mousedown', onDoc)
        return () => document.removeEventListener('mousedown', onDoc)
      }, [open, ref, close])
    }

    /** 年份：左右拖动 / 滚轮直接改（左=更早、右=更晚），点一下再按「年代→年份」精确选 */
    function YearPick({ value, onChange, min = 1940, max = 2026 }) {
      const [open, setOpen] = useState(false)
      const [hint, setHint] = useState(false)
      const [step, setStep] = useState('decade')
      const [decade, setDecade] = useState(Math.floor(value / 10) * 10)
      const ref = useRef(null)
      const btnRef = useRef(null)
      const dragRef = useRef(null)
      const draggedRef = useRef(false)
      const valueRef = useRef(value)
      valueRef.current = value
      useOutside(ref, open, () => setOpen(false))

      // 第一次打开面板时，自己冒出来讲一次"能拖"，之后只在鼠标停上去时提示
      useEffect(() => {
        let seen = false
        try { seen = window.localStorage.getItem(HINT_KEY) === '1' } catch { }
        if (seen) return undefined
        setHint(true)
        const t = setTimeout(() => {
          setHint(false)
          try { window.localStorage.setItem(HINT_KEY, '1') } catch { }
        }, 7000)
        return () => clearTimeout(t)
      }, [])

      const clamp = (v) => Math.min(max, Math.max(min, v))

      useEffect(() => {
        const el = btnRef.current
        if (!el) return undefined
        const onWheel = (e) => {
          if (open) return
          e.preventDefault()
          const d = Math.sign(e.deltaY || 0) * (e.shiftKey ? 10 : 1)
          if (d) onChange(clamp(valueRef.current + d))
        }
        el.addEventListener('wheel', onWheel, { passive: false })
        return () => el.removeEventListener('wheel', onWheel)
      }, [open, onChange])

      const firstDecade = Math.floor(min / 10) * 10
      const lastDecade = Math.floor(max / 10) * 10
      const decades = []
      for (let d = firstDecade; d <= lastDecade; d += 10) decades.push(d)

      const toggle = () => {
        const next = !open
        setOpen(next)
        if (next) { setStep('decade'); setDecade(Math.floor(value / 10) * 10) }
      }

      const onPointerDown = (e) => {
        if (e.button !== 0) return
        dragRef.current = { x: e.clientX, year: valueRef.current }
        draggedRef.current = false
        try { e.currentTarget.setPointerCapture(e.pointerId) } catch { }
      }
      const onPointerMove = (e) => {
        const st = dragRef.current
        if (!st) return
        const dx = e.clientX - st.x
        if (Math.abs(dx) < 4) return
        draggedRef.current = true
        onChange(clamp(st.year + Math.round(dx / 8)))
      }
      const endDrag = () => { dragRef.current = null }
      const onClickBox = () => {
        if (draggedRef.current) { draggedRef.current = false; return }
        toggle()
      }

      const chipStyle = (active) => ({
        appearance: 'none', border: `1px solid ${active ? 'color-mix(in srgb, ' + C.accent + ' 55%, transparent)' : 'transparent'}`,
        background: active ? 'color-mix(in srgb, ' + C.accent + ' 16%, transparent)' : 'var(--dsw-alias-bg-layer-2)',
        color: active ? C.accent : C.text, borderRadius: 4, padding: '6px 0',
        fontSize: 11.5, fontFamily: 'inherit', cursor: 'pointer', whiteSpace: 'nowrap',
      })

      const yearsInDecade = []
      for (let y = decade; y < decade + 10 && y <= max; y++) if (y >= min) yearsInDecade.push(y)

      return h('div', { ref, style: { position: 'relative', flex: 'none' } },
        h('button', {
          ref: btnRef,
          type: 'button',
          style: { ...fieldStyle, width: 96, cursor: 'ew-resize', touchAction: 'none', ...(open ? { borderColor: `color-mix(in srgb, ${C.accent} 55%, transparent)` } : null) },
          onPointerDown,
          onPointerMove,
          onPointerUp: endDrag,
          onPointerCancel: endDrag,
          onClick: onClickBox,
          onMouseEnter: () => setHint(true),
          onMouseLeave: () => setHint(false),
          title: '左右拖动或滚轮直接改年份（左=更早）；点一下按年代精确选',
        },
        h('span', { style: { color: C.faint, fontSize: 11, marginRight: 1, pointerEvents: 'none' } }, '⇔'),
        h('span', { pointerEvents: 'none' }, String(value)),
        h('span', { style: { color: C.faint, fontSize: 11, pointerEvents: 'none' } }, '年'),
        h('span', { style: { marginLeft: 'auto', color: C.faint, fontSize: 9, transform: open ? 'rotate(180deg)' : 'none', pointerEvents: 'none' } }, '▾'),
        ),
        hint && !open ? h('div', {
          style: {
            position: 'absolute', top: 'calc(100% + 6px)', left: 0, zIndex: 95, width: 232,
            background: C.sheet, border: `1px solid color-mix(in srgb, ${C.accent} 35%, transparent)`, borderRadius: 6,
            padding: '8px 10px', fontSize: 11.5, lineHeight: 1.7, color: C.sub,
            boxShadow: '0 10px 26px rgba(0,0,0,0.5)', pointerEvents: 'none',
          },
        },
        h('div', { style: { color: C.accent, marginBottom: 2 } }, '这个年份可以拖'),
        '按住数字左右拖就能改（往右变晚、往左变早），滚轮也行。',
        h('br'),
        '不想拖就点一下，按「年代 → 年份」两步选。',
        ) : null,
        open ? h('div', {
          style: {
            position: 'absolute', top: 'calc(100% + 4px)', left: 0, zIndex: 90,
            background: C.pop, border: `1px solid ${C.borderStrong}`, borderRadius: 8,
            padding: 6, width: 240, boxShadow: '0 14px 34px rgba(0,0,0,0.6)',
          },
        },
        step === 'decade'
          ? h('div', { style: { display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 4 } },
            decades.map((d) => h('button', {
              key: d, type: 'button',
              onClick: () => { setDecade(d); setStep('year') },
              style: chipStyle(d === decade),
            }, `${d}–${Math.min(d + 9, max)}`)),
          )
          : h('div', null,
            h('div', { style: { display: 'flex', alignItems: 'center', gap: 6, padding: '0 2px 6px' } },
              h('button', {
                type: 'button',
                onClick: () => setStep('decade'),
                style: {
                  appearance: 'none', border: `1px solid ${C.border}`, background: 'var(--dsw-alias-bg-layer-2)',
                  color: C.sub, borderRadius: 4, padding: '2px 8px', fontSize: 11, cursor: 'pointer', fontFamily: 'inherit',
                },
              }, '‹ 年代'),
              h('span', { style: { fontSize: 11, color: C.faint } }, `${decade}–${Math.min(decade + 9, max)}`),
            ),
            h('div', { style: { display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 4 } },
              yearsInDecade.map((y) => h('button', {
                key: y, type: 'button',
                onClick: () => { onChange(y); setOpen(false) },
                style: chipStyle(y === value),
              }, String(y))),
            ),
          )
        ) : null,
      )
    }

    /** 通用小下拉（月/日/时辰/性别） */
    function Drop({ value, options, onChange, width = 70, cols = 6, itemWidth = 34, maxHeight = 260, unit = '' }) {
      const [open, setOpen] = useState(false)
      const [hover, setHover] = useState(null)
      const ref = useRef(null)
      useOutside(ref, open, () => setOpen(false))
      const cur = options.find((o) => o.value === value)
      return h('div', { ref, style: { position: 'relative', flex: 'none' } },
        h('button', {
          type: 'button',
          style: { ...fieldStyle, width, ...(open ? { borderColor: `color-mix(in srgb, ${C.accent} 55%, transparent)` } : null) },
          onClick: () => setOpen((v) => !v),
          title: '点选',
        },
        h('span', { style: { overflow: 'hidden', textOverflow: 'ellipsis' } }, cur ? cur.label : '—'),
        unit ? h('span', { style: { color: C.faint, fontSize: 11 } }, unit) : null,
        h('span', { style: { marginLeft: 'auto', color: C.faint, fontSize: 9, transform: open ? 'rotate(180deg)' : 'none' } }, '▾'),
        ),
        open ? h('div', {
          style: {
            position: 'absolute', top: 'calc(100% + 4px)', left: 0, zIndex: 90,
            background: C.pop, border: `1px solid ${C.borderStrong}`, borderRadius: 8,
            padding: 6, display: 'grid', gridTemplateColumns: `repeat(${cols}, ${itemWidth}px)`,
            gap: 4, maxHeight, overflowY: 'auto', boxShadow: '0 14px 34px rgba(0,0,0,0.6)',
          },
        },
        options.map((o) => {
          const selected = o.value === value
          const isHover = hover === o.value
          return h('button', {
            key: String(o.value),
            type: 'button',
            onMouseEnter: () => setHover(o.value),
            onMouseLeave: () => setHover((v) => (v === o.value ? null : v)),
            onClick: () => { onChange(o.value); setOpen(false) },
            style: {
              appearance: 'none', border: `1px solid ${selected ? 'color-mix(in srgb, ' + C.accent + ' 55%, transparent)' : 'transparent'}`,
              background: selected ? 'color-mix(in srgb, ' + C.accent + ' 16%, transparent)' : (isHover ? 'var(--dsw-alias-bg-layer-2)' : 'var(--dsw-alias-bg-layer-1)'),
              color: selected ? C.accent : C.text, borderRadius: 4, padding: '5px 0',
              fontSize: 12.5, fontFamily: 'inherit', cursor: 'pointer', textAlign: 'center', whiteSpace: 'nowrap',
            },
          }, o.label)
        }),
        ) : null,
      )
    }

    function StarLine({ stars, big }) {
      if (!stars || !stars.length) return null
      return h('div', { style: { fontSize: big ? 14 : 12, lineHeight: 1.45, wordBreak: 'break-word' } },
        stars.map((s, i) => h('span', { key: i, style: { color: big ? C.starMain : C.starMinor, fontWeight: big ? 600 : 400, marginRight: 4, whiteSpace: 'nowrap' } },
          s.name,
          s.brightness ? h('span', { style: { color: C.starBright, fontSize: '0.82em', fontWeight: 400 } }, `(${s.brightness})`) : null,
          s.mutagen ? h('span', { style: { color: MUTAGEN_COLOR[s.mutagen] || C.accent, fontSize: '0.82em', marginLeft: 1 } }, `[${s.mutagen}]`) : null,
        )),
      )
    }

    function Palace({ p, soulBranch }) {
      const pos = CELL[p.earthlyBranch] || [1, 1]
      const ages = p.decadal && p.decadal.range ? `${p.decadal.range[0]}-${p.decadal.range[1]}` : ''
      return h('div', {
        style: {
          gridRow: pos[0], gridColumn: pos[1],
          border: `1px solid ${p.isBodyPalace ? 'color-mix(in srgb, ' + C.accent + ' 55%, transparent)' : C.border}`,
          background: C.cell, borderRadius: 4, padding: '6px 8px',
          minHeight: 0, overflow: 'hidden',
          display: 'flex', flexDirection: 'column', gap: 3,
        },
      },
      h('div', { style: { display: 'flex', alignItems: 'baseline', gap: 5, fontSize: 12.5, color: C.sub, whiteSpace: 'nowrap' } },
        h('span', { style: { color: p.earthlyBranch === soulBranch ? C.accent : C.sub, fontSize: 13.5 } }, `${p.heavenlyStem}${p.earthlyBranch}`),
        h('span', null, p.name),
        p.isBodyPalace ? h('span', { style: { color: C.accent, fontSize: 10.5, border: `1px solid color-mix(in srgb, ${C.accent} 40%, transparent)`, borderRadius: 3, padding: '0 3px' } }, '身') : null,
        h('span', { style: { marginLeft: 'auto', color: C.sub, fontSize: 10.5 } }, ages),
      ),
      h(StarLine, { stars: p.majorStars, big: true }),
      h(StarLine, { stars: p.minorStars, big: false }),
      p.adjectiveStars && p.adjectiveStars.length
        ? h('div', { style: { fontSize: 11, color: C.sub, lineHeight: 1.35, wordBreak: 'break-word', overflow: 'hidden' } }, p.adjectiveStars.join(' '))
        : null,
      p.changsheng12 ? h('div', { style: { marginTop: 'auto', fontSize: 10.5, color: C.sub } }, p.changsheng12) : null,
      )
    }

    function Center({ chart }) {
      const rows = [
        ['阳历', chart.solarDate],
        ['农历', chart.lunarDate],
        ['四柱', chart.chineseDate],
        ['时辰', `${chart.time}（${chart.timeRange}）`],
        ['五行局', chart.fiveElementsClass],
        ['命主', chart.soul],
        ['身主', chart.body],
        ['命/身宫', chart.earthlyBranchOfSoulPalace && chart.earthlyBranchOfBodyPalace
          ? `${chart.earthlyBranchOfSoulPalace}宫 / ${chart.earthlyBranchOfBodyPalace}宫`
          : ''],
      ].filter((r) => r[1] !== undefined && r[1] !== '')
      return h('div', {
        style: {
          gridRow: '2 / span 2', gridColumn: '2 / span 2',
          display: 'flex', flexDirection: 'column', justifyContent: 'center', gap: 5,
          padding: '10px 18px', minHeight: 0, overflow: 'hidden',
        },
      },
      h('div', { style: { fontSize: 17, fontWeight: 600, color: C.accent, letterSpacing: 3, marginBottom: 4 } }, '紫 微 斗 数'),
      rows.map(([k, v]) => h('div', { key: k, style: { display: 'flex', gap: 10, fontSize: 13, lineHeight: 1.6 } },
        h('span', { style: { color: C.sub, width: 52, flex: 'none' } }, k),
        h('span', { style: { color: C.text, wordBreak: 'break-word' } }, String(v)),
      )),
      )
    }

    /** 极简 markdown 渲染：标题行 → 金色小标题，**粗体** → 加亮，其余按段落 */
    function renderRich(text) {
      const lines = String(text || '').split('\n')
      const nodes = []
      for (let i = 0; i < lines.length; i++) {
        const raw = lines[i]
        const trimmed = raw.trim()
        if (!trimmed) { nodes.push(h('div', { key: i, style: { height: 7 } })); continue }
        const isHead = /^(#{1,4}\s+|[①②③④⑤⑥⑦]|[一二三四五六七]、)/.test(trimmed) && trimmed.length < 42
        const body = trimmed.replace(/^#{1,4}\s+/, '')
        if (isHead) {
          nodes.push(h('div', { key: i, style: { fontSize: 14, fontWeight: 600, color: C.accent, margin: '12px 0 6px' } }, body.replace(/\*\*/g, '')))
          continue
        }
        const parts = body.split(/(\*\*[^*]+\*\*)/)
        nodes.push(h('div', { key: i, style: { marginBottom: 5 } },
          parts.map((p, k) => {
            const bold = /^\*\*[^*]+\*\*$/.test(p)
            return h('span', { key: k, style: bold ? { fontWeight: 600, color: C.text } : null }, bold ? p.slice(2, -2) : p)
          }),
        ))
      }
      return nodes
    }

    function Reading({ turns, busy, error, onClose, onRetry, subtitle, onQuote }) {
      const bodyRef = useRef(null)
      const [sel, setSel] = useState(null)
      useEffect(() => {
        const onUp = (e) => {
          const bodyEl = bodyRef.current
          if (!bodyEl) return
          const s = window.getSelection()
          const text = s ? String(s).trim() : ''
          if (!text || text.length < 4) { setSel(null); return }
          const node = s.anchorNode
          const el = node && node.nodeType === 3 ? node.parentNode : node
          if (!el || !bodyEl.contains(el)) { setSel(null); return }
          setSel({ x: e.clientX, y: e.clientY, text: text.slice(0, 220) })
        }
        const clear = () => setSel(null)
        document.addEventListener('mouseup', onUp)
        window.addEventListener('scroll', clear, true)
        return () => {
          document.removeEventListener('mouseup', onUp)
          window.removeEventListener('scroll', clear, true)
        }
      }, [])
      const finishedRef = useRef(false)
      const turnRefs = useRef({})
      useEffect(() => {
        const el = bodyRef.current
        if (!el) return undefined
        const toAnchor = () => {
          const bandY = el.clientHeight * 0.26
          el.scrollTop = Math.max(0, el.scrollHeight - 380 - bandY)
        }
        const toQuestion = () => {
          const last = turns[turns.length - 1]
          const node = last && turnRefs.current[last.id]
          if (node) el.scrollTop = Math.max(0, node.offsetTop - 6)
          else toAnchor()
        }
        if (busy) {
          finishedRef.current = true
          // 流式时把最新一行顶到参考线上，眼睛不用追着往下跑
          toAnchor()
          return undefined
        }
        if (finishedRef.current) {
          finishedRef.current = false
          // 收尾：把这一轮的「问：」顶到第一行，从头读整段
          const t = setTimeout(toQuestion, 150)
          const t2 = setTimeout(toQuestion, 450)
          return () => { clearTimeout(t); clearTimeout(t2) }
        }
        return undefined
      }, [turns, busy])
      const bodyStyle = { fontSize: 13.5, lineHeight: 2.1, color: C.body, wordBreak: 'break-word' }
      return h('div', {
        style: {
          position: 'absolute', top: 0, right: 0, bottom: 0, width: 440, zIndex: 70,
          background: C.drawer, borderLeft: `1px solid ${C.border}`,
          display: 'flex', flexDirection: 'column', boxShadow: '-18px 0 40px rgba(0,0,0,0.45)',
        },
      },
      h('div', { style: { display: 'flex', alignItems: 'center', gap: 8, padding: '10px 14px', borderBottom: `1px solid ${C.border}` } },
        h('span', { style: { color: C.accent, fontSize: 13, fontWeight: 600, whiteSpace: 'nowrap' } }, '命盘问答'),
        subtitle ? h('span', { style: { color: C.faint, fontSize: 11, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' } }, subtitle) : null,
        h('button', {
          type: 'button', onClick: onClose, title: '关闭',
          style: { ...fieldStyle, marginLeft: 'auto', padding: '2px 8px', fontSize: 12 },
        }, '关闭'),
      ),
      h('div', { style: { position: 'relative', flex: '1 1 auto', minHeight: 0 } },
        h('div', {
          ref: bodyRef,
          style: {
            position: 'absolute', inset: 0, overflowY: 'auto', padding: '12px 16px',
            paddingBottom: 380, scrollBehavior: 'smooth',
          },
        },
        error ? h('div', { style: { ...bodyStyle, color: C.red } }, error) : null,
        turns.length === 0
          ? h('div', { style: { color: C.faint, fontSize: 12, lineHeight: 1.9 } },
            '点上面那排问题直接问，或者点「解读」先看整体命格。', h('br'), '每次回答都会引用你盘里的宫位、星曜和大限流年。')
          : turns.map((t) => h('div', {
            key: t.id,
            ref: (node) => { if (node) turnRefs.current[t.id] = node },
            style: { marginBottom: 16 },
          },
            h('div', { style: { color: C.accent, fontSize: 12.5, marginBottom: 6, fontWeight: 600 } }, `问：${t.q}`),
            t.a
              ? h('div', { style: { fontSize: 13.5, lineHeight: 2.1, color: C.body, wordBreak: 'break-word' } }, renderRich(t.a))
              : (busy
                ? h('div', { style: { paddingTop: 4 } },
                  [92, 86, 70].map((w, i) => h('div', {
                    key: i,
                    style: {
                      height: 9, width: `${w}%`, borderRadius: 4,
                      background: 'var(--dsw-alias-border-l2)', marginBottom: 8,
                      animation: 'ziwei-pulse 1.2s ease-in-out infinite',
                    },
                  })),
                )
                : h('div', { style: { color: C.faint, fontSize: 11.5 } }, '（这题没算完，点下面重新算）')),
            (t.a || !busy) ? h('button', {
              type: 'button',
              onClick: () => onRetry && onRetry(t),
              disabled: busy,
              style: {
                appearance: 'none', marginTop: 4, padding: '1px 6px', fontSize: 10.5,
                background: 'transparent', border: `1px solid ${C.border}`, borderRadius: 4,
                color: C.faint, cursor: busy ? 'default' : 'pointer', fontFamily: 'inherit',
                opacity: busy ? 0.4 : 1,
              },
            }, '重新算这题') : null,
          )),
      )),
      sel && !busy
        ? h('div', {
          style: {
            position: 'fixed', zIndex: 220,
            left: Math.max(8, Math.min(sel.x, window.innerWidth - 190)),
            top: Math.min(sel.y + 10, window.innerHeight - 60),
          },
        },
        h('button', {
          type: 'button',
          onMouseDown: (e) => e.preventDefault(),
          onClick: () => {
            const q = `就这一段再详细展开，最好举具体例子：\n「${sel.text}」`
            setSel(null)
            try { window.getSelection()?.removeAllRanges() } catch { }
            onQuote && onQuote(q)
          },
          style: {
            appearance: 'none', borderRadius: 999, padding: '5px 14px', fontSize: 12,
            fontFamily: 'inherit', cursor: 'pointer', whiteSpace: 'nowrap',
            border: `1px solid color-mix(in srgb, ${C.accent} 55%, transparent)`,
            background: C.sheet, color: C.accent,
            boxShadow: '0 10px 26px rgba(0,0,0,0.35)',
          },
        }, '就这段细说'),
        )
        : null,
      )
    }

    function readSaved() {
      try {
        const raw = window.localStorage.getItem(STORE_KEY)
        if (!raw) return null
        const o = JSON.parse(raw)
        if (o && Number(o.year) && Number(o.month) && Number(o.day)) return o
      } catch { }
      return null
    }

    function ZiweiPanel() {
      const saved = readSaved()
      const [year, setYear] = useState(saved?.year ?? 1995)
      const [month, setMonth] = useState(saved?.month ?? 8)
      const [day, setDay] = useState(saved?.day ?? 16)
      const [timeIndex, setTimeIndex] = useState(saved?.timeIndex ?? 2)
      const [gender, setGender] = useState(saved?.gender ?? '男')
      const [chart, setChart] = useState(null)
      const [err, setErr] = useState('')
      const [busy, setBusy] = useState(false)
      const [turns, setTurns] = useState([])
      const [customQ, setCustomQ] = useState('')
      const [qaKey, setQaKey] = useState('')
      const [readBusy, setReadBusy] = useState(false)
      const [readErr, setReadErr] = useState('')
      const [readOpen, setReadOpen] = useState(false)
      const mountedRef = useRef(false)
      const abortRef = useRef(null)
      const seqRef = useRef(0)
      const busyRef = useRef(false)
      const turnsRef = useRef([])
      turnsRef.current = turns

      const daysInMonth = new Date(year, month, 0).getDate()
      const safeDay = Math.min(day, daysInMonth)
      const solarDate = `${year}-${month}-${safeDay}`

      const cast = useCallback(async (payload) => {
        const body = payload || { solarDate, timeIndex, gender }
        setBusy(true)
        setErr('')
        try {
          const resp = await fetch('/api/dsh-ziwei/chart', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
          })
          const json = await resp.json()
          if (json.ok) {
            setChart(json.chart)
            // 换成这个人：把他的问答记录取出来；换回来时还在
            const key = qaKeyOf(body.solarDate, body.timeIndex, body.gender)
            setQaKey(key)
            setTurns(loadTurns(key))
            setReadErr('')
            try {
              window.localStorage.setItem(STORE_KEY, JSON.stringify({
                year: Number(body.solarDate.split('-')[0]),
                month: Number(body.solarDate.split('-')[1]),
                day: Number(body.solarDate.split('-')[2]),
                timeIndex: body.timeIndex,
                gender: body.gender,
              }))
            } catch { }
          } else setErr(json.error || '排盘失败')
        } catch (e) {
          setErr(String(e?.message ?? e))
        } finally {
          setBusy(false)
        }
      }, [solarDate, timeIndex, gender])

      const ask = useCallback(async (question, targetYear, opts) => {
        if (busyRef.current) return
        const q = String(question || '').trim() || '整体命格解读'
        const replaceId = opts && opts.replaceId
        // 同一个问题已经算过：直接打开看，不再花 token 重算
        if (!(opts && opts.force)) {
          const hit = turnsRef.current.find((t) => t.q === q && t.a)
          if (hit) { setReadOpen(true); return }
        }
        busyRef.current = true
        setReadOpen(true)
        setReadBusy(true)
        setReadErr('')
        const id = `t${Date.now()}${++seqRef.current}`
        const year = targetYear || new Date().getFullYear()
        setTurns((t) => {
          const base = replaceId ? t.filter((x) => x.id !== replaceId) : t
          return [...base, { id, q, a: '', year }]
        })
        const ac = new AbortController()
        abortRef.current = ac
        try {
          const resp = await fetch('/api/dsh-ziwei/ask', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              solarDate, timeIndex, gender,
              question: q === '整体命格解读' ? '' : q,
              year,
            }),
            signal: ac.signal,
          })
          if (!resp.ok || !resp.body) throw new Error(`接口异常：${resp.status}`)
          const reader = resp.body.getReader()
          const dec = new TextDecoder()
          for (;;) {
            const { done, value } = await reader.read()
            if (done) break
            const piece = dec.decode(value, { stream: true })
            if (piece) setTurns((t) => t.map((x) => (x.id === id ? { ...x, a: x.a + piece } : x)))
          }
        } catch (e) {
          if (String(e?.name) !== 'AbortError') setReadErr(String(e?.message ?? e))
        } finally {
          busyRef.current = false
          setReadBusy(false)
        }
      }, [solarDate, timeIndex, gender])

      const nowYear = new Date().getFullYear()

      const submitCustom = useCallback(() => {
        const q = customQ.trim()
        if (!q || !chart || readBusy) return
        setCustomQ('')
        ask(q, nowYear)
      }, [customQ, chart, readBusy, ask, nowYear])

      // 预设问题是"一批批随机出"的，不是写死的；年份跟着当前年份走
      const QUESTION_POOL = useMemo(() => {
        const y = nowYear
        return [
          { label: `${y} 年运势`, question: `${y} 年整体运势怎么样？`, year: y },
          { label: `${y + 1} 年运势`, question: `${y + 1} 年整体运势怎么样？`, year: y + 1 },
          { label: '事业变动', question: '今年工作上会不会有变动？该不该主动换？', year: y },
          { label: '换工作', question: '我适合换工作吗？什么时候换比较好？', year: y },
          { label: '钱从哪来', question: '我的钱主要从哪来？靠什么最挣钱？', year: y },
          { label: '漏财点', question: '我容易在哪花钱、哪块漏财？', year: y },
          { label: '桃花', question: '今年的桃花怎么样？', year: y },
          { label: '感情坑', question: '我的感情里容易出什么问题？', year: y },
          { label: '适合结婚', question: '我大概什么时候适合结婚/定下来？', year: y },
          { label: '健康', question: '我该注意哪些健康问题？', year: y },
          { label: '适合城市', question: '我适合在哪个方向、哪种城市发展？', year: y },
          { label: '上班还是自由', question: '我适合上班还是做自由职业/创业？', year: y },
          { label: '家人关系', question: '我和父母、家里人的关系要注意什么？', year: y },
          { label: '考试运', question: '今年适合考试、考证或进修吗？', year: y },
          { label: '贵人', question: '我这两年的贵人大概是什么样的人？', year: y },
          { label: '最大短板', question: '我最大的短板是什么？怎么补？', year: y },
          { label: '未来十年', question: '未来十年大概是个什么走势？', year: y },
          { label: '能不能投资', question: '今年适不适合做投资、冒险的投入？', year: y },
          { label: '适不适合合伙', question: '我适合跟人合伙做事吗？', year: y },
          { label: '转运时间', question: '我什么时候会明显顺起来？', year: y },
        ]
      }, [nowYear])

      const pickPresets = useCallback(() => {
        const arr = QUESTION_POOL.slice()
        for (let i = arr.length - 1; i > 0; i--) {
          const j = Math.floor(Math.random() * (i + 1))
          const t = arr[i]; arr[i] = arr[j]; arr[j] = t
        }
        return arr.slice(0, 6)
      }, [QUESTION_POOL])

      const [presetList, setPresetList] = useState(() => pickPresets())

      // 打开面板：有上次记录就自动排一次（零点击）
      useEffect(() => {
        if (mountedRef.current) return
        mountedRef.current = true
        const s = readSaved()
        if (s) {
          const dim = new Date(s.year, s.month, 0).getDate()
          cast({ solarDate: `${s.year}-${s.month}-${Math.min(s.day, dim)}`, timeIndex: s.timeIndex, gender: s.gender })
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
      }, [])

      // 面板卸载时中断还在跑的解读，别白烧 token
      useEffect(() => () => { try { abortRef.current?.abort() } catch { } }, [])

      // 生日一改就自动重排（防抖 500ms），不用再点「排盘」
      const firstRun = useRef(true)
      useEffect(() => {
        if (firstRun.current) { firstRun.current = false; return undefined }
        const t = setTimeout(() => { cast() }, 500)
        return () => clearTimeout(t)
      }, [cast])

      // 问答记录按「这个人的盘」存：换人换记录，换回来又接上；没算完的不存
      useEffect(() => {
        if (!qaKey) return undefined
        const t = setTimeout(() => {
          try {
            const keep = turns.filter((x) => x.a && x.a.length > 8).slice(-20)
            window.localStorage.setItem(qaKey, JSON.stringify(keep))
          } catch { }
        }, 500)
        return () => clearTimeout(t)
      }, [turns, qaKey])

      const soulBranch = chart?.earthlyBranchOfSoulPalace
      const hasReading = turns.some((t) => t.q === '整体命格解读' && t.a)

      return h('div', {
        style: {
          position: 'relative',
          width: '100%', height: '100%', minHeight: 420, display: 'flex', flexDirection: 'column',
          background: C.base, color: C.text, fontFamily: 'inherit', overflow: 'hidden',
        },
      },
      // 顶栏
      h('div', {
        style: {
          display: 'flex', alignItems: 'center', gap: 8, padding: '9px 14px',
          borderBottom: `1px solid ${C.border}`, flexWrap: 'wrap', flex: 'none',
        },
      },
      h('div', { style: { fontSize: 13.5, fontWeight: 600, color: C.accent, whiteSpace: 'nowrap', marginRight: 4 } }, '紫微斗数'),
      h(YearPick, { value: year, onChange: setYear }),
      h(Drop, {
        value: month, width: 66, cols: 6, itemWidth: 32, unit: '月',
        options: Array.from({ length: 12 }, (_, i) => i + 1).map((m) => ({ value: m, label: String(m) })),
        onChange: setMonth,
      }),
      h(Drop, {
        value: safeDay, width: 66, cols: 7, itemWidth: 28, unit: '日',
        options: Array.from({ length: daysInMonth }, (_, i) => i + 1).map((d) => ({ value: d, label: String(d) })),
        onChange: setDay,
      }),
      h(Drop, {
        value: timeIndex, width: 126, cols: 2, itemWidth: 88, maxHeight: 260,
        options: HOURS.map((label, i) => ({ value: i, label })),
        onChange: setTimeIndex,
      }),
      h(Drop, {
        value: gender, width: 60, cols: 2, itemWidth: 32,
        options: [{ value: '男', label: '男' }, { value: '女', label: '女' }],
        onChange: setGender,
      }),
      h('button', { style: btnStyle, onClick: () => cast(), disabled: busy }, busy ? '排盘中…' : '排盘'),
      h('button', {
        style: { ...btnStyle, background: `color-mix(in srgb, ${C.accent} 28%, transparent)` },
        onClick: () => ask('', nowYear),
        disabled: !chart || readBusy,
      }, readBusy ? '解读中…' : (hasReading ? '看解读' : '解读')),
      h('button', {
        style: { ...btnStyle, border: `1px solid ${C.border}`, background: 'var(--dsw-alias-bg-layer-2)', color: C.text, opacity: turns.length ? 1 : 0.5 },
        onClick: () => setReadOpen(true),
        disabled: !chart,
        title: '打开这个人之前的问答记录',
      }, turns.length ? `问答记录 ${turns.length}` : '问答记录'),
      err ? h('span', { style: { fontSize: 11.5, color: C.red } }, err) : null,
      ),

      // 常见问题（点一下直接问，零打字）
      h('div', {
        style: { display: 'flex', alignItems: 'center', gap: 6, padding: '7px 14px', borderBottom: `1px solid ${C.border}`, flexWrap: 'wrap', flex: 'none' },
      },
      h('span', { style: { fontSize: 11.5, color: C.faint, marginRight: 2 } }, '想问：'),
      h('button', {
        type: 'button',
        disabled: readBusy,
        onClick: () => setPresetList(pickPresets()),
        title: '换一批问题',
        style: {
          appearance: 'none', borderRadius: 999, padding: '3px 9px', fontSize: 11.5,
          fontFamily: 'inherit', cursor: readBusy ? 'default' : 'pointer', whiteSpace: 'nowrap',
          border: `1px dashed ${C.border}`, background: 'transparent', color: C.sub,
          opacity: readBusy ? 0.45 : 1,
        },
      }, '⟳ 换一批'),
      presetList.map((p) => h('button', {
        key: p.label,
        type: 'button',
        disabled: !chart || readBusy,
        onClick: () => ask(p.question, p.year),
        style: {
          appearance: 'none', borderRadius: 999, padding: '3px 10px', fontSize: 11.5,
          fontFamily: 'inherit', cursor: 'pointer', whiteSpace: 'nowrap',
          border: `1px solid color-mix(in srgb, ${C.accent} 40%, transparent)`, background: `color-mix(in srgb, ${C.accent} 10%, transparent)`, color: C.accent,
          opacity: (!chart || readBusy) ? 0.45 : 1,
        },
      }, p.label)),
      h('input', {
        type: 'text',
        value: customQ,
        placeholder: '自己写个问题，回车就问…',
        onChange: (e) => setCustomQ(e.target.value),
        onKeyDown: (e) => { if (e.key === 'Enter') submitCustom() },
        disabled: !chart || readBusy,
        style: {
          flex: '1 1 200px', minWidth: 150,
          background: 'var(--dsw-alias-bg-layer-2)', border: `1px solid ${C.border}`, borderRadius: 6,
          color: C.text, padding: '4px 10px', fontSize: 12.5, fontFamily: 'inherit', outline: 'none',
          opacity: (!chart || readBusy) ? 0.5 : 1,
        },
      }),
      h('button', {
        type: 'button',
        onClick: submitCustom,
        disabled: !chart || readBusy || !customQ.trim(),
        style: {
          appearance: 'none', borderRadius: 6, padding: '4px 12px', fontSize: 12,
          fontFamily: 'inherit', cursor: 'pointer', whiteSpace: 'nowrap',
          border: `1px solid color-mix(in srgb, ${C.accent} 55%, transparent)`, background: `color-mix(in srgb, ${C.accent} 20%, transparent)`, color: C.accent,
          opacity: (!chart || readBusy || !customQ.trim()) ? 0.45 : 1,
        },
      }, '提问'),
      ),

      // 盘面
      chart
        ? h('div', {
          style: {
            flex: '1 1 auto', minHeight: 0, padding: 10,
            display: 'grid', gridTemplateColumns: 'repeat(4, minmax(0, 1fr))',
            gridTemplateRows: 'repeat(4, minmax(0, 1fr))', gap: 6,
          },
        },
        chart.palaces.map((p, i) => h(Palace, { key: i, p, soulBranch })),
        h(Center, { chart }),
        )
        : h('div', { style: { flex: '1 1 auto', display: 'flex', alignItems: 'center', justifyContent: 'center', color: C.faint, fontSize: 13 } },
          busy ? '排盘中…' : '选生日 → 点「排盘」'),

      readOpen ? h(Reading, {
        turns, busy: readBusy, error: readErr,
        subtitle: chart ? `${chart.solarDate} ${chart.time} ${chart.gender}` : '',
        onRetry: (t) => ask(t.q, t.year, { force: true, replaceId: t.id }),
        onQuote: (q) => ask(q),
        onClose: () => {
          try { abortRef.current?.abort() } catch { }
          setReadOpen(false)
        },
      }) : null,
      )
    }

    const name = 'dsh-ziwei'
    const inject = []

    function apply(ctx) {
      const disposers = []
      try {
        if (typeof document !== 'undefined' && !document.getElementById('dsh-ziwei-style')) {
          const s = document.createElement('style')
          s.id = 'dsh-ziwei-style'
          s.textContent = '@keyframes ziwei-pulse{0%,100%{opacity:.22}50%{opacity:.75}}'
          document.head.appendChild(s)
        }
      } catch { }

      // 注册成一个工作台，由「工作台」合集页统一入口
      const registry = window.__DSH_WORKBENCHES__ || (window.__DSH_WORKBENCHES__ = [])
      const entry = {
        id: 'ziwei',
        title: '算命工作台',
        desc: '紫微斗数排盘 + AI 解读与追问',
        order: 10,
        Icon,
        Component: ZiweiPanel,
      }
      const found = registry.findIndex((x) => x && x.id === 'ziwei')
      if (found >= 0) registry[found] = entry
      else registry.push(entry)
      try { window.dispatchEvent(new Event('dsh-workbench-changed')) } catch { }

      return () => {
        for (const d of disposers) { try { d?.() } catch { } }
        const i = registry.findIndex((x) => x && x.id === 'ziwei')
        if (i >= 0) registry.splice(i, 1)
        try { window.dispatchEvent(new Event('dsh-workbench-changed')) } catch { }
      }
    }

    return { name, inject, apply }
  },
})
