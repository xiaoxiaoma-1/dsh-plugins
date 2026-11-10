/**
 * dsh-finance-health —— 客户端：往「工作台」合集里加一张「经济体检」卡
 *
 * 约定（dsh-workbench-hub）：往 window.__DSH_WORKBENCHES__ 里 push
 *   { id, title, desc, order?, Icon?, Component }
 * 再 dispatch 'dsh-workbench-changed'，合集页自动刷新。
 */

window.__ModuleLoader__.load({
  id: 'dsh-finance-health',
  factory(require) {
    const React = require('react')
    const h = React.createElement
    const { useState, useEffect, useCallback, useRef } = React

    const API = '/api/dsh-finance'
    const C = {
      text: 'var(--dsw-alias-label-primary)',
      sub: 'var(--dsw-alias-label-secondary)',
      border: 'var(--dsw-alias-border-l1)',
      cell: 'var(--dsw-alias-bg-layer-1)',
      accent: 'var(--dsw-alias-brand-primary)',
    }
    // 金色：与当前文字色混合，深浅主题都够对比度（不要给 var() 拼十六进制后缀）
    const GOLD = 'color-mix(in srgb, #d9a94a 76%, var(--dsw-alias-label-primary) 24%)'
    const UP = 'color-mix(in srgb, #d66a6a 78%, var(--dsw-alias-label-primary) 22%)'
    const DOWN = 'color-mix(in srgb, #4fae86 76%, var(--dsw-alias-label-primary) 24%)'

    const CSS = `
.fh-wrap{ padding:22px 26px 30px; overflow:auto; height:100%; box-sizing:border-box; }
.fh-head{ display:flex; align-items:flex-end; gap:14px; flex-wrap:wrap; margin-bottom:4px; }
.fh-title{ font-size:22px; font-weight:650; letter-spacing:.4px; color:${GOLD}; }
.fh-meta{ font-size:12.5px; color:${C.sub}; }
.fh-spacer{ flex:1 1 auto; }
.fh-btn{ font-size:12.5px; padding:7px 15px; border-radius:8px; cursor:pointer;
  border:1px solid ${C.border}; background:transparent; color:${C.text};
  transition:none; }
.fh-btn:hover{ border-color:${GOLD}; color:${GOLD}; }
.fh-btn:disabled{ opacity:.45; cursor:default; }
.fh-note{ font-size:12px; line-height:1.7; color:${C.sub}; margin:10px 0 18px;
  border-left:2px solid ${GOLD}; padding-left:10px; }
.fh-grid{ display:grid; grid-template-columns:repeat(auto-fill,minmax(168px,1fr)); gap:12px; }
.fh-card{ border:1px solid ${C.border}; border-radius:11px; padding:14px 15px 13px;
  background:${C.cell}; display:flex; flex-direction:column; gap:5px; }
.fh-k{ font-size:12px; color:${C.sub}; letter-spacing:.2px; }
.fh-v{ font-size:26px; font-weight:640; line-height:1.05; color:${C.text};
  font-variant-numeric:tabular-nums; }
.fh-u{ font-size:12px; color:${C.sub}; margin-left:3px; font-weight:400; }
.fh-t{ font-size:11.5px; color:${C.sub}; display:flex; gap:8px; align-items:center; }
.fh-dot{ width:5px; height:5px; border-radius:50%; display:inline-block; }
.fh-sec{ margin-top:26px; font-size:13px; font-weight:600; color:${C.text};
  letter-spacing:.3px; display:flex; align-items:center; gap:9px; }
.fh-sec::after{ content:''; flex:1 1 auto; height:1px; background:${C.border}; }
.fh-md{ margin-top:12px; font-size:13px; line-height:1.85; color:${C.text}; }
.fh-md h2{ font-size:14.5px; font-weight:640; margin:18px 0 8px; color:${GOLD}; }
.fh-md p{ margin:6px 0; }
.fh-md li{ margin:4px 0 4px 18px; color:${C.text}; }
.fh-md blockquote{ margin:10px 0; padding:8px 12px; border-left:2px solid ${C.border};
  color:${C.sub}; font-size:12.5px; }
.fh-empty{ margin-top:16px; font-size:13px; color:${C.sub}; line-height:1.9; }
.fh-log{ margin-top:14px; font-size:11.5px; color:${C.sub}; line-height:1.7;
  max-height:120px; overflow:auto; font-family:ui-monospace,Consolas,monospace; }
`

    function fmt(v, unit) {
      if (v == null) return '—'
      const s = Math.abs(v) >= 1000 ? v.toFixed(0) : String(v)
      return s
    }

    /** 行内格式：**加粗** → <b>，其余原样 */
    function inline(text, keyPrefix) {
      const parts = String(text).split(/(\*\*[^*]+\*\*)/g)
      return parts.map((p, i) => {
        if (p.length > 4 && p.startsWith('**') && p.endsWith('**')) {
          return h('b', {
            key: keyPrefix + 'b' + i,
            style: { color: GOLD, fontWeight: 650 },
          }, p.slice(2, -2))
        }
        return p
      })
    }

    /** 极简 markdown → React（#、##、- 、> 、**粗体**） */
    function renderMd(md) {
      if (!md) return null
      const lines = md.split(/\r?\n/)
      const out = []
      let list = []
      const flush = () => {
        if (list.length) {
          const items = list
          out.push(h('ul', { key: 'ul' + out.length, style: { margin: '6px 0', padding: 0 } },
            items.map((t, i) => h('li', { key: i }, inline(t, 'li' + i)))))
          list = []
        }
      }
      lines.forEach((ln, i) => {
        const s = ln.trim()
        if (!s) { flush(); return }
        if (s.startsWith('## ')) { flush(); out.push(h('h2', { key: i }, inline(s.slice(3), 'h' + i))); return }
        if (s.startsWith('# ')) { flush(); out.push(h('h2', { key: i }, inline(s.slice(2), 'h' + i))); return }
        if (s.startsWith('> ')) { flush(); out.push(h('blockquote', { key: i }, inline(s.slice(2), 'q' + i))); return }
        if (/^[-*] /.test(s)) { list.push(s.slice(2)); return }
        flush()
        out.push(h('p', { key: i }, inline(s, 'p' + i)))
      })
      flush()
      return out
    }

    function Meta({ status }) {
      if (!status) return h('span', { className: 'fh-meta' }, '正在读数据…')
      if (!status.date) {
        return h('span', { className: 'fh-meta' }, '还没有数据 · 点右边「更新数据」跑一次')
      }
      return h('span', { className: 'fh-meta' },
        '数据日 ', h('b', { style: { color: C.text } }, status.date),
        status.collectedAt ? ' · 采集于 ' + status.collectedAt : '',
        status.report ? ' · 报告已生成' : ' · 报告还没生成')
    }

    function Home() {
      const [st, setSt] = useState(null)
      const [err, setErr] = useState('')
      const timer = useRef(null)

      const load = useCallback(async () => {
        try {
          const r = await fetch(API + '/status', { cache: 'no-store' })
          const j = await r.json()
          setSt(j)
          setErr('')
        } catch (e) {
          setErr('读不到数据：' + (e?.message || e))
        }
      }, [])

      useEffect(() => {
        load()
        timer.current = setInterval(load, 5000)
        return () => { if (timer.current) clearInterval(timer.current) }
      }, [load])

      const onUpdate = useCallback(async () => {
        try {
          await fetch(API + '/update', { method: 'POST' })
          load()
        } catch (e) {
          setErr('触发更新失败：' + (e?.message || e))
        }
      }, [load])

      const running = !!st?.job?.running
      const metrics = st?.metrics || []

      return h('div', { className: 'fh-wrap' },
        h('style', null, CSS),

        h('div', { className: 'fh-head' },
          h('div', { className: 'fh-title' }, '经济体检'),
          h('div', null, h(Meta, { status: st })),
          h('div', { className: 'fh-spacer' }),
          h('button', {
            className: 'fh-btn',
            disabled: running,
            onClick: onUpdate,
          }, running ? (st.job.step || '更新中') + '…' : '更新数据'),
        ),

        h('div', { className: 'fh-note' },
          '基于公开信息的个人判断与估计，不是投资建议，也不保证准确。实际情况可能不同，一切以官方发布和实际发生为准。'),

        err ? h('div', { className: 'fh-empty' }, err) : null,

        !st ? h('div', { className: 'fh-empty' }, '正在加载…') :
          (!metrics.length
            ? h('div', { className: 'fh-empty' },
              '还没有指标数据。点右上「更新数据」，会跑 fetch_macro.py 抓数据、judge.py 出体检报告。')
            : h('div', { className: 'fh-grid' },
              metrics.map((m) => h('div', { className: 'fh-card', key: m.key },
                h('div', { className: 'fh-k' }, m.label),
                h('div', { className: 'fh-v' },
                  fmt(m.value, m.unit),
                  m.unit ? h('span', { className: 'fh-u' }, m.unit) : null),
                h('div', { className: 'fh-t' },
                  m.delta == null ? null : h('span', {
                    className: 'fh-dot',
                    style: { background: m.delta > 0 ? UP : (m.delta < 0 ? DOWN : C.sub) },
                  }),
                  m.delta == null ? '环比 —' : (m.delta > 0 ? '环比 +' : '环比 ') + m.delta,
                  h('span', { style: { opacity: .7 } }, m.month || ''),
                ),
              )))),

        (running || st?.job?.error) && st?.job?.log?.length
          ? h('div', { className: 'fh-log' }, st.job.log.map((l, i) => h('div', { key: i }, l)))
          : null,

        st?.reportMd
          ? h('div', null,
            h('div', { className: 'fh-sec' }, '体检全文'),
            h('div', { className: 'fh-md' }, renderMd(st.reportMd)))
          : null,

        h('div', { className: 'fh-sec' }, '下一步'),
        h('div', { className: 'fh-md' },
          h('p', null, '这份判断是快照。数据一变，结论就会变 —— 建议每周点一次「更新数据」，看趋势有没有转向。')),
      )
    }

    function Icon({ size = 20 }) {
      return h('svg', {
        width: size, height: size, viewBox: '0 0 24 24', fill: 'none',
        style: { display: 'block' },
      },
        h('path', {
          d: 'M3.5 17.5 L8.5 11 L12.5 14.5 L20.5 5',
          stroke: 'currentColor', strokeWidth: 1.1,
          strokeLinecap: 'round', strokeLinejoin: 'round',
        }),
        h('path', {
          d: 'M15.5 5 H20.5 V10',
          stroke: 'currentColor', strokeWidth: 1.1,
          strokeLinecap: 'round', strokeLinejoin: 'round',
        }),
      )
    }

    const name = 'dsh-finance-health'
    const inject = ['slots']

    function apply(ctx) {
      window.__DSH_WORKBENCHES__ = window.__DSH_WORKBENCHES__ || []
      const arr = window.__DSH_WORKBENCHES__
      const entry = {
        id: 'finance-health',
        title: '经济体检',
        desc: '宏观指标 + 五段判断，一键更新',
        order: 30,
        Icon,
        Component: Home,
      }
      const i = arr.findIndex((x) => x && x.id === entry.id)
      if (i >= 0) arr[i] = entry
      else arr.push(entry)
      try {
        window.dispatchEvent(new CustomEvent('dsh-workbench-changed'))
      } catch { }

      return () => {
        const j = arr.findIndex((x) => x && x.id === entry.id)
        if (j >= 0) arr.splice(j, 1)
        try { window.dispatchEvent(new CustomEvent('dsh-workbench-changed')) } catch { }
      }
    }

    return { name, inject, apply }
  },
})
