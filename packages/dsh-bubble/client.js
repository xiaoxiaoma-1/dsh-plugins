/**
 * dsh-bubble 客户端 —— 通用悬浮气泡
 *
 * 目的：任何插件都能往上推任务状态，用户在任何页面都能看到「哪个活干完了」。
 *
 * 对外接口（挂在 window 上，别的插件直接调）：
 *   window.__DSH_BUBBLE__.start(id, title, opts)   开始一个任务
 *   window.__DSH_BUBBLE__.progress(id, pct, detail) 推进度（0-100）
 *   window.__DSH_BUBBLE__.done(id, detail)          完成
 *   window.__DSH_BUBBLE__.fail(id, detail)          失败
 *   window.__DSH_BUBBLE__.remove(id)                移除
 *   window.__DSH_BUBBLE__.list()                    读当前全部任务
 *   window.__DSH_BUBBLE__.subscribe(fn)             订阅变化，返回取消函数
 *
 * 如果调用时气泡插件还没加载，把调用先塞进队列：
 *   (window.__DSH_BUBBLE_QUEUE__ = window.__DSH_BUBBLE_QUEUE__ || []).push(['done', id, detail])
 * 气泡加载后会立刻把队列里的调用补执行一遍。
 */
window.__ModuleLoader__.load({
  id: 'dsh-bubble',
  factory(require) {
    const React = require('react')
    const h = React.createElement
    const { useEffect, useRef, useState, useCallback } = React

    /* ==================== 任务状态（模块级，跨插件共享） ==================== */
    const TASKS = new Map()
    const subs = new Set()
    const MAX_DONE = 12
    const emit = () => { for (const f of subs) { try { f() } catch { } } }

    function setTask(id, patch) {
      if (!id) return null
      const prev = TASKS.get(id) || { id, title: '', status: 'running', pct: 0, detail: '', at: Date.now() }
      const next = Object.assign({}, prev, patch, { at: Date.now() })
      TASKS.set(id, next)
      // 已完成的只留最近 MAX_DONE 条，避免越积越多
      const doneList = [...TASKS.values()].filter((t) => t.status !== 'running').sort((a, b) => b.at - a.at)
      if (doneList.length > MAX_DONE) {
        for (const t of doneList.slice(MAX_DONE)) TASKS.delete(t.id)
      }
      emit()
      return next
    }

    /* 系统通知：收起来了也看得见（Electron 里就是右下角那条） */
    function notify(title, body) {
      try {
        if (typeof window === 'undefined' || !window.Notification) return
        const fire = () => {
          try {
            const n = new window.Notification(title, { body: String(body || ''), silent: false })
            n.onclick = () => { try { window.focus() } catch { } }
            setTimeout(() => { try { n.close() } catch { } }, 9000)
          } catch { }
        }
        if (window.Notification.permission === 'granted') { fire(); return }
        if (window.Notification.permission === 'denied') return
        try {
          Promise.resolve(window.Notification.requestPermission()).then((p) => { if (p === 'granted') fire() }).catch(() => { })
        } catch { }
      } catch { }
    }

    const API = {
      version: 1,
      start(id, title, opts) {
        const o = opts || {}
        return setTask(id, { title: String(title || ''), status: 'running', pct: 0, detail: o.detail || '' })
      },
      progress(id, pct, detail) {
        const p = Math.max(0, Math.min(100, Number(pct) || 0))
        const patch = { status: 'running', pct: p }
        if (detail != null) patch.detail = String(detail)
        return setTask(id, patch)
      },
      done(id, detail) {
        const patch = { status: 'done', pct: 100 }
        if (detail != null) patch.detail = String(detail)
        const prev = TASKS.get(id)
        const t = setTask(id, patch)
        if (prev && prev.status !== 'done') notify('✓ 完成了', (t && t.title ? t.title : id) + (detail ? ' · ' + detail : ''))
        return t
      },
      fail(id, detail) {
        const patch = { status: 'error' }
        if (detail != null) patch.detail = String(detail)
        const prev = TASKS.get(id)
        const t = setTask(id, patch)
        if (prev && prev.status !== 'error') notify('✕ 失败了', (t && t.title ? t.title : id) + (detail ? ' · ' + detail : ''))
        return t
      },
      remove(id) { TASKS.delete(id); emit() },
      list() { return [...TASKS.values()] },
      subscribe(fn) {
        if (typeof fn !== 'function') return () => { }
        subs.add(fn)
        return () => { subs.delete(fn) }
      },
    }
    try { window.__DSH_BUBBLE__ = API } catch { }

    /* ==================== 拉宿主端的「对话完成」事件 ==================== */
    /* 客户端没有任何对话事件，只能定时问宿主：/api/dsh-bubble/events */
    const POLL_MS = 5000
    function startTurnWatch() {
      if (typeof window === 'undefined') return
      if (window.__DSH_BUBBLE_TURN_WATCH__) return
      let dead = false
      const tick = async () => {
        if (dead) return
        try {
          const r = await fetch('/api/dsh-bubble/events', { headers: { accept: 'application/json' } })
          if (!r.ok) return
          const j = await r.json()
          for (const e of ((j && j.events) || [])) {
            try {
              // 外部脚本推来的长任务（提炼、下载、转写……）
              if (e && e.type === 'task' && e.id) {
                const tid = 'task-' + e.id
                if (e.state === 'done') API.done(tid, e.detail || '完成')
                else if (e.state === 'fail') API.fail(tid, e.detail || '失败')
                else if (TASKS.has(tid)) API.progress(tid, Number(e.pct) || 0, e.detail || '')
                else API.start(tid, e.title || e.id, { detail: e.detail || '', pct: Number(e.pct) || 0 })
                continue
              }
              const secs = Math.round((Number(e.ms) || 0) / 1000)
              const who = e.title || '会话'
              const id = 'chat-' + (e.at || Date.now())
              API.start(id, `${who} · AI 干完了`, { detail: `用了 ${secs} 秒` })
              API.done(id, `用了 ${secs} 秒`)
            } catch { }
          }
        } catch { }
      }
      const iv = setInterval(tick, POLL_MS)
      tick()
      window.__DSH_BUBBLE_TURN_WATCH__ = () => { dead = true; clearInterval(iv) }
    }

    // 补执行"气泡还没加载时"攒下的调用
    try {
      const q = window.__DSH_BUBBLE_QUEUE__
      if (Array.isArray(q) && q.length) {
        const pending = q.splice(0, q.length)
        for (const item of pending) {
          try {
            const m = item && item[0]
            if (m && typeof API[m] === 'function') API[m](item[1], item[2], item[3])
          } catch { }
        }
      }
      if (!Array.isArray(window.__DSH_BUBBLE_QUEUE__)) window.__DSH_BUBBLE_QUEUE__ = []
    } catch { }

    /* ==================== 样式 ==================== */
    const CSS = `
.bub-root{ position:fixed; z-index:9400; width:54px; height:54px; }
.bub-ball{ position:relative; width:54px; height:54px; border-radius:50%; border:none; cursor:grab; user-select:none;
  background:radial-gradient(circle at 38% 30%,
    color-mix(in srgb, var(--dsw-alias-label-primary, #f2f2f4) 13%, var(--dsw-alias-bg-base, #131316)) 0%,
    var(--dsw-alias-bg-base, #131316) 58%,
    color-mix(in srgb, var(--dsw-alias-bg-base, #131316) 72%, #000) 100%);
  box-shadow:0 6px 20px rgba(0,0,0,.28), inset 0 -3px 8px rgba(0,0,0,.22), inset 0 2px 4px rgba(255,255,255,.10);
  display:flex; align-items:center; justify-content:center; }
.bub-ball:active{ cursor:grabbing; }
.bub-ball::before{ content:''; position:absolute; inset:-4px; border-radius:50%; background:conic-gradient(#e3ba63 var(--p,0%), rgba(255,255,255,.09) 0);
  -webkit-mask:radial-gradient(circle, transparent 0 27px, #000 27px); mask:radial-gradient(circle, transparent 0 27px, #000 27px);
  opacity:0; transition:opacity .3s ease; pointer-events:none; }
.bub-running::before{ opacity:1; }
.bub-eyes{ display:flex; align-items:center; gap:7px; transition:transform .09s linear; }
.bub-eye{ width:9px; height:12px; border-radius:50%; background:var(--dsw-alias-label-primary, #f6f2e9); display:block; transition:height .1s ease; }
.bub-blink .bub-eye{ height:2.5px; }
.bub-poke{ animation:bubPoke .34s cubic-bezier(.34,1.56,.64,1); }
@keyframes bubPoke{ 0%{ transform:scale(1) } 32%{ transform:scale(.9) } 68%{ transform:scale(1.06) } 100%{ transform:scale(1) } }
.bub-done-flash::after{ content:''; position:absolute; inset:-4px; border-radius:50%; border:2px solid rgba(120,220,140,.75); animation:bubFlash 1.1s ease-out 2; pointer-events:none; }
@keyframes bubFlash{ 0%{ transform:scale(1); opacity:.9 } 100%{ transform:scale(1.35); opacity:0 } }
.bub-badge{ position:absolute; top:-3px; right:-3px; min-width:17px; height:17px; padding:0 4px; border-radius:9px; background:var(--dsw-alias-brand-primary, #d9a94a); color:var(--dsw-alias-bg-base, #1a1a1a);
  font-size:10.5px; font-weight:700; line-height:17px; text-align:center; box-shadow:0 2px 6px rgba(0,0,0,.5); }

.bub-panel{ position:absolute; width:340px; background:var(--dsw-alias-bg-base, #131316); border:1px solid var(--dsw-alias-border-l1, rgba(227,186,99,.3)); border-radius:14px;
  box-shadow:0 18px 48px rgba(0,0,0,.72), 0 0 0 1px rgba(0,0,0,.35); padding:11px 12px; display:flex; flex-direction:column; gap:8px;
  animation:bubFade .16s ease both; }
@keyframes bubFade{ from{opacity:0; transform:translateY(4px)} to{opacity:1; transform:none} }
.bub-head{ display:flex; align-items:center; gap:8px; }
.bub-title{ flex:1; min-width:0; font-size:12.5px; color:var(--dsw-alias-label-primary, #ececee); font-weight:600; }
.bub-close{ flex:none; width:18px; height:18px; line-height:16px; text-align:center; border-radius:5px; color:#9d9da3; cursor:pointer; font-size:15px; }
.bub-close:hover{ color:#ececee; background:rgba(255,255,255,.08); }
.bub-list{ display:flex; flex-direction:column; gap:6px; max-height:300px; overflow-y:auto; }
.bub-empty{ font-size:12px; color:#8b8b93; line-height:1.7; padding:8px 2px; }
.bub-item{ padding:8px 9px; border-radius:9px; background:color-mix(in srgb, var(--dsw-alias-label-primary, #fff) 4%, transparent); border-left:2px solid transparent; }
.bub-item-run{ border-left-color:rgba(227,186,99,.75); }
.bub-item-done{ border-left-color:var(--dsw-alias-state-success-primary, rgba(120,220,140,.75)); }
.bub-item-err{ border-left-color:var(--dsw-alias-state-error-primary, rgba(226,102,94,.85)); }
.bub-row{ display:flex; align-items:center; gap:8px; }
.bub-name{ flex:1; min-width:0; font-size:12.5px; color:var(--dsw-alias-label-primary, #e2e2e6); overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.bub-st{ flex:none; font-size:11px; color:#8b8b93; font-variant-numeric:tabular-nums; }
.bub-st-done{ color:var(--dsw-alias-state-success-primary, #78dc8c); }
.bub-st-err{ color:var(--dsw-alias-state-error-primary, #e2665e); }
.bub-detail{ font-size:11.5px; color:var(--dsw-alias-label-secondary, #9d9da3); margin-top:3px; line-height:1.6; overflow:hidden; display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; }
.bub-bar{ height:3px; border-radius:2px; background:rgba(255,255,255,.13); margin-top:6px; overflow:hidden; }
.bub-bar i{ display:block; height:100%; background:linear-gradient(90deg,#e3ba63,#c8973c); transition:width .35s ease; }
.bub-foot{ font-size:11px; color:#77777f; line-height:1.6; border-top:1px solid rgba(255,255,255,.06); padding-top:7px; }
/* 播放条：播客把状态广播过来，这里统一显示和控制，页面只留这一个球 */
.bub-player{ display:flex; align-items:center; gap:9px; padding:8px 9px; border-radius:9px;
  background:color-mix(in srgb, var(--dsw-alias-label-primary, #fff) 5%, transparent);
  border-left:2px solid color-mix(in srgb, var(--dsw-alias-brand-primary, #d9a94a) 75%, transparent); }
.bub-player-main{ flex:none; width:28px; height:28px; border-radius:8px; display:flex; align-items:center; justify-content:center;
  cursor:pointer; font-size:13px; color:var(--dsw-alias-label-primary, #ececee);
  background:color-mix(in srgb, var(--dsw-alias-brand-primary, #d9a94a) 16%, transparent);
  border:1px solid color-mix(in srgb, var(--dsw-alias-brand-primary, #d9a94a) 45%, transparent); }
.bub-player-main:hover{ background:color-mix(in srgb, var(--dsw-alias-brand-primary, #d9a94a) 30%, transparent); }
.bub-player-info{ flex:1; min-width:0; }
.bub-player-title{ font-size:12.5px; color:var(--dsw-alias-label-primary, #ececee); overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.bub-player-bar{ height:3px; border-radius:2px; background:rgba(255,255,255,.13); margin-top:5px; overflow:hidden; cursor:pointer; }
.bub-player-bar i{ display:block; height:100%; background:linear-gradient(90deg,#e3ba63,#c8973c); transition:width .4s linear; }
.bub-player-time{ flex:none; font-size:11px; color:#8b8b93; font-variant-numeric:tabular-nums; }
.bub-ball-playing::before{ animation-duration:2.4s !important; }
`

    /* ==================== 气泡本体 ==================== */
    function Bubble() {
      const [, force] = useState(0)
      const [open, setOpen] = useState(false)
      const [blink, setBlink] = useState(false)
      const [poke, setPoke] = useState(false)
      const [eye, setEye] = useState({ dx: 0, dy: 0 })
      const [flashDone, setFlashDone] = useState(false)
      // 播客等其它插件广播过来的播放状态（这个球是页面唯一的悬浮物）
      const [player, setPlayer] = useState(() => {
        try { return window.__dshPodcastPlayer?.state?.() || null } catch { return null }
      })
      const [xy, setXy] = useState(() => {
        try {
          const s = JSON.parse(window.localStorage.getItem('dsh-bubble-pos') || 'null')
          if (s && Number.isFinite(s.x) && Number.isFinite(s.y)) return s
        } catch { }
        return { x: Math.max(8, window.innerWidth - 80), y: Math.max(8, window.innerHeight - 80) }
      })
      const fmtT = (s) => {
        if (!Number.isFinite(s) || s < 0) return '0:00'
        const m = Math.floor(s / 60)
        const r = Math.floor(s % 60)
        return `${m}:${String(r).padStart(2, '0')}`
      }
      const dragRef = useRef(null)
      const ballRef = useRef(null)
      const rootRef = useRef(null)
      const xyRef = useRef(xy)
      const prevDoneRef = useRef(0)

      useEffect(() => { xyRef.current = xy }, [xy])

      /* 订阅播放状态：别的插件发 dsh-player-state，这里就更新（一个球管所有） */
      useEffect(() => {
        const on = (e) => setPlayer(e?.detail || null)
        try { window.addEventListener('dsh-player-state', on) } catch { }
        return () => { try { window.removeEventListener('dsh-player-state', on) } catch { } }
      }, [])

      /* 订阅任务变化 */
      useEffect(() => {
        const f = () => force((x) => x + 1)
        subs.add(f)
        return () => { subs.delete(f) }
      }, [])

      /* 有任务刚完成 → 闪一下 + 自动展开 */
      useEffect(() => {
        const doneCount = [...TASKS.values()].filter((t) => t.status === 'done').length
        if (doneCount > prevDoneRef.current) {
          setFlashDone(true)
          setOpen(true)
          const t1 = setTimeout(() => setFlashDone(false), 1300)
          const t2 = setTimeout(() => setOpen(false), 4200)
          prevDoneRef.current = doneCount
          return () => { clearTimeout(t1); clearTimeout(t2) }
        }
        prevDoneRef.current = doneCount
        return undefined
      }, [TASKS.size])

      /* 随机眨眼 */
      useEffect(() => {
        let t1 = 0, t2 = 0, dead = false
        const schedule = () => {
          t1 = setTimeout(() => {
            if (dead) return
            setBlink(true)
            t2 = setTimeout(() => { if (dead) return; setBlink(false); schedule() }, 130)
          }, 3000 + Math.random() * 4500)
        }
        schedule()
        return () => { dead = true; clearTimeout(t1); clearTimeout(t2) }
      }, [])

      /* 鼠标：眼睛跟随 + 拖动 */
      useEffect(() => {
        const onMove = (e) => {
          const d = dragRef.current
          if (d) {
            const nx = Math.max(6, Math.min(window.innerWidth - 60, e.clientX - d.ox))
            const ny = Math.max(6, Math.min(window.innerHeight - 60, e.clientY - d.oy))
            if (Math.abs(nx - d.sx) > 3 || Math.abs(ny - d.sy) > 3) d.moved = true
            setXy({ x: nx, y: ny })
            return
          }
          const el = ballRef.current
          if (!el) return
          const r = el.getBoundingClientRect()
          const dx = e.clientX - (r.left + r.width / 2)
          const dy = e.clientY - (r.top + r.height / 2)
          const len = Math.hypot(dx, dy) || 1
          const k = Math.min(1, len / 150) * 3.2
          setEye({ dx: (dx / len) * k, dy: (dy / len) * k })
        }
        const onUp = () => {
          const d = dragRef.current
          if (!d) return
          dragRef.current = null
          try { window.localStorage.setItem('dsh-bubble-pos', JSON.stringify(xyRef.current)) } catch { }
          if (!d.moved) setOpen((v) => !v)
        }
        document.addEventListener('mousemove', onMove)
        document.addEventListener('mouseup', onUp)
        return () => {
          document.removeEventListener('mousemove', onMove)
          document.removeEventListener('mouseup', onUp)
        }
      }, [])

      /* 点外面收起（延迟一帧挂监听，否则展开那一下立刻被关） */
      useEffect(() => {
        if (!open) return undefined
        const onDoc = (e) => {
          const el = rootRef.current
          if (el && e.target && el.contains(e.target)) return
          setOpen(false)
        }
        const t = setTimeout(() => { document.addEventListener('mousedown', onDoc, true) }, 0)
        return () => { clearTimeout(t); try { document.removeEventListener('mousedown', onDoc, true) } catch { } }
      }, [open])

      const all = [...TASKS.values()]
      const running = all.filter((t) => t.status === 'running')
      const finished = all.filter((t) => t.status !== 'running').sort((a, b) => b.at - a.at)
      const shown = [...running, ...finished]
      const runningPct = running.length
        ? Math.round(running.reduce((s, t) => s + (Number(t.pct) || 0), 0) / running.length)
        : 0

      const onDown = (e) => {
        const r = e.currentTarget.getBoundingClientRect()
        dragRef.current = { ox: e.clientX - r.left, oy: e.clientY - r.top, sx: e.clientX, sy: e.clientY, moved: false }
        try { e.preventDefault() } catch { }
        setPoke(true)
        setBlink(true)
        setTimeout(() => setBlink(false), 140)
        setTimeout(() => setPoke(false), 340)
      }

      const panelLeft = Math.max(8, Math.min(xy.x - 288, window.innerWidth - 350))
      const panelTop = Math.max(8, xy.y - 130)

      const fmtAgo = (ts) => {
        const s = Math.max(0, Math.round((Date.now() - ts) / 1000))
        if (s < 60) return '刚刚'
        if (s < 3600) return Math.floor(s / 60) + ' 分钟前'
        return Math.floor(s / 3600) + ' 小时前'
      }

      return h('div', { key: 'bub', ref: rootRef, className: 'bub-root', style: { left: xy.x + 'px', top: xy.y + 'px' } }, [
        open && h('div', { key: 'p', className: 'bub-panel', style: { left: (panelLeft - xy.x) + 'px', top: (panelTop - xy.y) + 'px' } }, [
          h('div', { key: 'hd', className: 'bub-head' }, [
            h('div', { key: 't', className: 'bub-title' },
              running.length ? `${running.length} 个任务在跑` : (finished.length ? '最近完成' : '待命中')),
            h('div', { key: 'x', className: 'bub-close', title: '收起', onClick: (e) => { e.stopPropagation(); setOpen(false) } }, '×'),
          ]),
          player && player.src
            ? h('div', { key: 'pl', className: 'bub-player' }, [
              h('div', {
                key: 'm', className: 'bub-player-main', title: player.playing ? '暂停' : '播放',
                onClick: (e) => { e.stopPropagation(); try { window.__dshPodcastPlayer?.toggle?.() } catch { } },
              }, player.playing ? '❚❚' : '▶'),
              h('div', { key: 'i', className: 'bub-player-info' }, [
                h('div', { key: 't', className: 'bub-player-title', title: player.title || '' }, player.title || '正在播放'),
                h('div', {
                  key: 'b', className: 'bub-player-bar',
                  onClick: (e) => {
                    e.stopPropagation()
                    const r = e.currentTarget.getBoundingClientRect()
                    const p = Math.max(0, Math.min(1, (e.clientX - r.left) / Math.max(1, r.width)))
                    try { window.__dshPodcastPlayer?.seek?.(p * (player.dur || 0)) } catch { }
                  },
                }, h('i', { style: { width: (player.dur ? Math.min(100, (player.pos / player.dur) * 100) : 0) + '%' } })),
              ]),
              h('div', { key: 'tm', className: 'bub-player-time' }, `${fmtT(player.pos)}/${fmtT(player.dur)}`),
            ])
            : null,
          h('div', { key: 'l', className: 'bub-list' },
            shown.length === 0
              ? h('div', { key: 'e', className: 'bub-empty' }, '现在没有任务。别的插件调 window.__DSH_BUBBLE__ 就能往这里推。')
              : shown.map((t) => h('div', {
                key: t.id,
                className: 'bub-item bub-item-' + (t.status === 'running' ? 'run' : t.status === 'done' ? 'done' : 'err'),
              }, [
                h('div', { key: 'r', className: 'bub-row' }, [
                  h('div', { key: 'n', className: 'bub-name', title: t.title }, t.title || t.id),
                  h('div', {
                    key: 's',
                    className: 'bub-st' + (t.status === 'done' ? ' bub-st-done' : t.status === 'error' ? ' bub-st-err' : ''),
                  }, t.status === 'running' ? `${Math.round(Number(t.pct) || 0)}%` : t.status === 'done' ? '完成' : '失败'),
                ]),
                t.detail ? h('div', { key: 'd', className: 'bub-detail' }, t.detail) : null,
                t.status === 'running'
                  ? h('div', { key: 'b', className: 'bub-bar' }, h('i', { style: { width: Math.max(2, Math.min(100, Number(t.pct) || 0)) + '%' } }))
                  : h('div', { key: 'a', className: 'bub-detail' }, fmtAgo(t.at)),
              ]))),
          h('div', { key: 'f', className: 'bub-foot' }, '拖动可移动 · 点球展开/收起 · 点外面自动关'),
        ]),
        h('div', {
          key: 'ball',
          ref: ballRef,
          className: 'bub-ball'
            + (running.length ? ' bub-running' : '')
            + (player && player.playing ? ' bub-ball-playing' : '')
            + (blink ? ' bub-blink' : '')
            + (poke ? ' bub-poke' : '')
            + (flashDone ? ' bub-done-flash' : ''),
          style: { '--p': running.length ? runningPct + '%' : '0%' },
          title: running.length ? `${running.length} 个任务在跑` : '点开看任务',
          onMouseDown: onDown,
        }, [
          h('div', { key: 'e', className: 'bub-eyes', style: { transform: `translate(${eye.dx}px,${eye.dy}px)` } }, [
            h('i', { key: 'l', className: 'bub-eye' }),
            h('i', { key: 'r', className: 'bub-eye' }),
          ]),
          running.length > 0
            ? h('i', { key: 'bd', className: 'bub-badge' }, String(running.length))
            : (finished.length > 0 && !open ? h('i', { key: 'bd2', className: 'bub-badge' }, String(finished.length)) : null),
        ]),
      ])
    }

    return {
      name: 'dsh-bubble',
      inject: ['slots'],
      apply(ctx) {
        try {
          if (typeof document !== 'undefined' && !document.getElementById('dsh-bubble-style')) {
            const st = document.createElement('style')
            st.id = 'dsh-bubble-style'
            st.textContent = CSS
            document.head.appendChild(st)
          }
        } catch { }

        // 开始盯「对话完成」（轮询宿主端）
        try { startTurnWatch() } catch { }

        // 标记：本插件接管页面悬浮物。其它插件（如 dsh-podcast）检测到它就不再多画一个球
        try { window.__dshBubbleMounted = true } catch { }

        const disposers = []
        try {
          disposers.push(ctx.slots.inject('shell.overlay', () =>
            ctx.slots.register(
              { name: 'shell.overlay', id: 'dsh-bubble', order: 70 },
              Bubble,
            ),
          ))
        } catch (e) {
          try { ctx.logger?.warn?.('dsh-bubble: 悬浮层注册失败', e) } catch { }
        }

        return () => { for (const d of disposers) { try { d?.() } catch { } } }
      },
    }
  },
})
