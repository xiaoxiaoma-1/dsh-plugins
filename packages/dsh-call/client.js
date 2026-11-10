/**
 * dsh-call —— 通话面板（客户端）
 *
 * 形态：左侧栏一个电话图标 → 点开整块中央区域变成「通话界面」：
 *   中间是说话/思考状态和转写记录，底部一个大圆麦克风按钮，说完自动发送。
 * 不走输入框，用户从头到尾只说一句话、点一下按钮。
 *
 * 投递方式：桥接组件挂在 conversation.input.right 上，把宿主的 InputActions
 * 存到模块级变量；通话面板拿到后 setDraft + submit 投递。
 * 朗读：先用浏览器自带 speechSynthesis（Windows 有中文语音），下一版换 Edge 神经语音。
 */

window.__ModuleLoader__.load({
  id: 'dsh-call',
  factory(require) {
    const React = require('react')
    const h = React.createElement
    const { useState, useEffect, useRef, useCallback } = React

    const PANEL_KEY = 'call'
    const TARGET_RATE = 16000

    // 宿主侧能力：由输入框右侧的桥接组件写入。
    // 注意不做卸载清理：点开侧栏「通话」时会话面板会被替换，桥接组件随之卸载，
    // 若此时清空就拿不到投递能力了。只保留最后一次写入的值。
    const bridge = { inputActions: null, sessionId: null }

    const C = {
      text: 'var(--dsw-alias-label-primary, #e8e8ec)',
      sub: 'var(--dsw-alias-label-secondary, #9a9aa2)',
      faint: 'var(--dsw-alias-label-tertiary, #66666e)',
      border: 'var(--dsw-alias-separator-primary, rgba(255,255,255,0.08))',
      base: 'var(--dsw-alias-bg-base, #141417)',
      card: 'var(--dsw-alias-bg-layer-1, rgba(255,255,255,0.035))',
      accent: '#6aa9ff',
      green: '#5ecb8a',
      red: '#e0716f',
      amber: '#dcb56a',
    }

    // ── 音频工具 ───────────────────────────────────────────────
    function resampleTo16k(input, inputRate) {
      if (inputRate === TARGET_RATE) return input
      const ratio = inputRate / TARGET_RATE
      const n = Math.floor(input.length / ratio)
      const out = new Float32Array(n)
      for (let i = 0; i < n; i++) {
        const pos = i * ratio
        const i0 = Math.floor(pos)
        const i1 = Math.min(i0 + 1, input.length - 1)
        const frac = pos - i0
        out[i] = input[i0] * (1 - frac) + input[i1] * frac
      }
      return out
    }

    function toPcm16(samples) {
      const buf = new ArrayBuffer(samples.length * 2)
      const view = new DataView(buf)
      for (let i = 0; i < samples.length; i++) {
        let s = Math.max(-1, Math.min(1, samples[i]))
        view.setInt16(i * 2, s < 0 ? s * 0x8000 : s * 0x7fff, true)
      }
      return buf
    }

    async function captureStart() {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      })
      const ac = new (window.AudioContext || window.webkitAudioContext)()
      const src = ac.createMediaStreamSource(stream)
      const proc = ac.createScriptProcessor(4096, 1, 1)
      const chunks = []
      proc.onaudioprocess = (e) => {
        const d = e.inputBuffer.getChannelData(0)
        chunks.push(new Float32Array(d))
      }
      src.connect(proc)
      proc.connect(ac.destination)
      return { stream, ac, src, proc, chunks }
    }

    function captureStop(cap) {
      try { cap.proc.disconnect() } catch { }
      try { cap.src.disconnect() } catch { }
      try { cap.stream.getTracks().forEach((t) => t.stop()) } catch { }
      try { cap.ac.close() } catch { }
      const total = cap.chunks.reduce((n, c) => n + c.length, 0)
      const merged = new Float32Array(total)
      let off = 0
      for (const c of cap.chunks) { merged.set(c, off); off += c.length }
      const rate = cap.ac.sampleRate || 48000
      return toPcm16(resampleTo16k(merged, rate))
    }

    // ── 图标 ───────────────────────────────────────────────────
    function PhoneIcon({ size = 20 }) {
      return h('svg', {
        width: size, height: size, viewBox: '0 0 24 24', fill: 'none',
        stroke: 'currentColor', strokeWidth: 1.4, strokeLinecap: 'round',
        strokeLinejoin: 'round', 'aria-hidden': true, style: { display: 'block' },
      }, h('path', {
        d: 'M4.2 4.6c.6-.6 1.5-.6 2.1 0l2.2 2.2c.6.6.6 1.5 0 2.1l-.9.9c-.3.3-.3.7-.1 1 1 1.6 2.3 2.9 3.9 3.9.3.2.7.2 1-.1l.9-.9c.6-.6 1.5-.6 2.1 0l2.2 2.2c.6.6.6 1.5 0 2.1l-1 1c-1.1 1.1-2.7 1.4-4.1.8-2.8-1.2-5.3-3.7-6.5-6.5-.6-1.4-.3-3 .8-4.1z',
      }))
    }

    // ── 输入框右侧桥接（只存宿主的输入动作，不渲染）─────────────
    function InputBridge(props) {
      useEffect(() => {
        if (props?.inputActions) bridge.inputActions = props.inputActions
        if (props?.sessionId) bridge.sessionId = props.sessionId
      })
      return null
    }

    // ── 通话面板 ───────────────────────────────────────────────
    function CallPanel(props) {
      const ctx = props?.ctx
      const [state, setState] = useState('idle') // idle | listening | thinking | sent | error
      const [lines, setLines] = useState([])     // {who:'me'|'ai'|'sys', text}
      const [level, setLevel] = useState(0)
      const [err, setErr] = useState('')
      const [speaking, setSpeaking] = useState(false)
      const [voice, setVoice] = useState(true)   // 自动朗读开关
      const capRef = useRef(null)
      const rafRef = useRef(0)
      const listRef = useRef(null)
      const seenRef = useRef(0)   // 已朗读/已显示的最大 seq
      const watchRef = useRef(null)

      const push = useCallback((who, text) => {
        setLines((v) => [...v.slice(-40), { who, text }])
      }, [])

      /* ---------- 语音播报：从回复里挑出「该念的那段」 ---------- */
      const pickSpeakText = (md) => {
        if (!md) return ''
        // ① 显式标记 【说】…【屏幕】
        const m = String(md).match(/【说】([\s\S]*?)(?=【屏幕】|$)/)
        if (m && m[1].trim()) return m[1].trim()
        // ② 没有标记：清掉 markdown，取前两句
        let t = String(md)
          .replace(/```[\s\S]*?```/g, '')       // 代码块
          .replace(/^\s*\|.*\|\s*$/gm, '')      // 表格行
          .replace(/^#{1,6}\s*/gm, '')          // 标题
          .replace(/^\s*[-*+]\s+/gm, '')        // 列表符
          .replace(/\[([^\]]*)\]\([^)]*\)/g, '$1') // 链接
          .replace(/[*_`>~]/g, '')
          .replace(/\n{2,}/g, '\n')
          .trim()
        if (!t) return ''
        const sents = t.split(/(?<=[。！？!?；;]|\n)/).map((x) => x.trim()).filter(Boolean)
        let out = ''
        for (const s of sents.slice(0, 2)) {
          if ((out + s).length > 90) break
          out += s
        }
        return out.slice(0, 120)
      }

      const speak = useCallback((text) => {
        if (!text) return
        try {
          const syn = window.speechSynthesis
          if (!syn) return
          syn.cancel()
          const u = new SpeechSynthesisUtterance(text)
          u.lang = 'zh-CN'
          u.rate = 1.05
          u.pitch = 1
          const vs = syn.getVoices() || []
          const zh = vs.find((v) => /^zh/i.test(v.lang || '')) || vs.find((v) => /chinese|中文/i.test(v.name || ''))
          if (zh) u.voice = zh
          u.onstart = () => setSpeaking(true)
          u.onend = () => setSpeaking(false)
          u.onerror = () => setSpeaking(false)
          syn.speak(u)
        } catch { }
      }, [])

      const stopSpeak = useCallback(() => {
        try { window.speechSynthesis?.cancel() } catch { }
        setSpeaking(false)
      }, [])

      /* ---------- 订阅会话，接收我的回复并朗读 ---------- */
      useEffect(() => {
        let unsub = null
        let dead = false
        const DEBUG = true

        const extract = (ev) => {
          // 兜底：不同版本的结构可能不同，全部试一遍
          const d = ev?.data ?? ev ?? {}
          const cands = []
          if (typeof d.text === 'string') cands.push(d.text)
          if (typeof d.markdown === 'string') cands.push(d.markdown)
          if (typeof d.content === 'string') cands.push(d.content)
          if (typeof d.delta === 'string') cands.push(d.delta)
          if (Array.isArray(d.blocks)) cands.push(d.blocks.map((b) => b?.text ?? '').join('\n'))
          if (Array.isArray(d.content)) cands.push(d.content.map((b) => b?.text ?? '').join('\n'))
          if (d.message) {
            if (typeof d.message === 'string') cands.push(d.message)
            else if (Array.isArray(d.message.content)) cands.push(d.message.content.map((b) => b?.text ?? '').join('\n'))
            else if (typeof d.message.text === 'string') cands.push(d.message.text)
          }
          return cands.filter((x) => typeof x === 'string' && x.trim()).sort((a, b) => b.length - a.length)[0] || ''
        }

        const handle = (w) => {
          if (dead || !w) return
          const entries = w.entries || []
          // 先看 settle-assistant
          const ch = w.change
          if (ch && ch.kind === 'settle-assistant' && ch.entry && ch.entry.type === 'event') {
            const ev = ch.entry.event
            const seq = ev?.seq || 0
            if (seq > seenRef.current) {
              const txt = extract(ev)
              if (txt) {
                seenRef.current = seq
                push('ai', txt)
                if (voice) speak(pickSpeakText(txt))
              }
            }
          }
          // 再扫尾部的 assistant/message
          for (let i = entries.length - 1; i >= 0; i--) {
            const e = entries[i]
            if (!e || e.type !== 'event') continue
            const ev = e.event
            if (!ev || ev.type !== 'assistant/message') continue
            const seq = ev.seq || 0
            if (seq <= seenRef.current) break
            const txt = extract(ev)
            if (txt) {
              seenRef.current = seq
              push('ai', txt)
              if (voice) speak(pickSpeakText(txt))
              if (DEBUG) { try { console.log('[call] ai event', JSON.stringify(ev).slice(0, 800)) } catch { } }
            }
            break
          }
        }

        const bind = () => {
          if (dead) return false
          const sid = bridge.sessionId
          if (!sid) return false
          try {
            const b = ctx?.sessions?.binding?.(sid)
            if (!b) return false
            const es = b.eventSource
            if (!es || typeof es.subscribe !== 'function') return false
            // 先读当前快照（拿已有的最新一条）
            try { handle(es.getSnapshot()) } catch { }
            unsub = es.subscribe(() => {
              try { handle(es.getSnapshot()) } catch { }
            })
            watchRef.current = b
            return true
          } catch { return false }
        }

        let timer = null
        if (!bind()) {
          timer = setInterval(() => { if (bind()) { clearInterval(timer); timer = null } }, 1200)
        }
        return () => {
          dead = true
          if (timer) clearInterval(timer)
          try { unsub?.() } catch { }
          stopSpeak()
        }
      }, [ctx, push, speak, stopSpeak, voice])

      useEffect(() => {
        if (listRef.current) listRef.current.scrollTop = listRef.current.scrollHeight
      }, [lines])

      useEffect(() => () => {
        cancelAnimationFrame(rafRef.current)
        if (capRef.current) { try { captureStop(capRef.current) } catch { } }
      }, [])

      const startListen = useCallback(async () => {
        setErr('')
        try {
          const cap = await captureStart()
          capRef.current = cap
          setState('listening')
          const meter = () => {
            const c = capRef.current
            if (!c) return
            const last = c.chunks[c.chunks.length - 1]
            if (last) {
              let sum = 0
              for (let i = 0; i < last.length; i += 4) sum += last[i] * last[i]
              setLevel(Math.min(1, Math.sqrt(sum / (last.length / 4)) * 9))
            }
            rafRef.current = requestAnimationFrame(meter)
          }
          meter()
        } catch (e) {
          setState('error')
          setErr('麦克风打不开：' + (e?.message ?? e))
        }
      }, [])

      const stopAndSend = useCallback(async () => {
        const cap = capRef.current
        if (!cap) return
        capRef.current = null
        cancelAnimationFrame(rafRef.current)
        setLevel(0)
        setState('thinking')
        let pcm
        try { pcm = captureStop(cap) } catch { pcm = null }
        if (!pcm || pcm.byteLength < 6400) {
          setState('idle')
          setErr('这句太短，没听清')
          return
        }
        try {
          const r = await fetch('/call/transcribe', {
            method: 'POST',
            headers: { 'content-type': 'application/octet-stream' },
            body: pcm,
          })
          const j = await r.json()
          if (!j?.ok) {
            setState('error')
            setErr(j?.error || '转写失败')
            return
          }
          const text = String(j.text || '').trim()
          if (!text) {
            setState('idle')
            setErr('没听出字来')
            return
          }
          push('me', text)
          const sid = bridge.sessionId
          let delivered = false
          // 首选一等 API：直接向会话投递用户消息（不依赖输入框存活）
          try {
            const face = sid ? ctx?.sessions?.binding?.(sid)?.session : null
            if (face && typeof face.prompt === 'function') {
              const r = await face.prompt([{ type: 'text', text }], 'queue')
              delivered = !(r && r.ok === false)
            }
          } catch {
            delivered = false
          }
          if (!delivered) {
            const actions = bridge.inputActions
            if (actions?.setDraft && actions?.submit) {
              actions.setDraft(text)
              setTimeout(() => {
                try { actions.submit() } catch (e) { setErr('发送失败：' + (e?.message ?? e)) }
              }, 60)
              delivered = true
            }
          }
          if (!delivered) {
            setState('error')
            setErr('没找到可发送的对话，先在左侧打开一个对话')
            return
          }
          setState('sent')
          setErr('')
        } catch (e) {
          setState('error')
          setErr('网络失败：' + (e?.message ?? e))
        }
      }, [push])

      const talking = state === 'listening'
      const busy = state === 'thinking'

      const bubble = (line) => {
        const mine = line.who === 'me'
        return h('div', {
          key: Math.random().toString(36).slice(2),
          style: {
            alignSelf: mine ? 'flex-end' : 'flex-start',
            maxWidth: '76%',
            padding: '9px 13px',
            borderRadius: 12,
            background: mine ? 'rgba(106,169,255,0.16)' : C.card,
            border: `1px solid ${mine ? 'rgba(106,169,255,0.3)' : C.border}`,
            color: mine ? '#dfe9ff' : C.text,
            fontSize: 13.5,
            lineHeight: 1.65,
            wordBreak: 'break-word',
            whiteSpace: 'pre-wrap',
          },
        }, line.text)
      }

      return h('div', {
        style: {
          width: '100%', height: '100%', minHeight: 480,
          display: 'flex', flexDirection: 'column',
          background: C.base, color: C.text, fontFamily: 'inherit',
        },
      },
      // 顶栏
      h('div', {
        style: {
          display: 'flex', alignItems: 'center', gap: 10,
          padding: '10px 16px', borderBottom: `1px solid ${C.border}`, flex: '0 0 auto',
        },
      },
      h('div', { style: { color: C.accent } }, h(PhoneIcon, { size: 17 })),
      h('div', { style: { fontSize: 17, fontWeight: 600, letterSpacing: 0.3 } }, '通话'),
      h('div', {
        style: {
          fontSize: 12.5, color: C.faint, flex: 1, minWidth: 0,
          overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
        },
      }, speaking ? '正在说…' : talking ? '正在听…' : busy ? '转写中…' : state === 'sent' ? '已发出，等它回答' : '点下面的大按钮说话'),
      h('button', {
        style: {
          appearance: 'none', border: `1px solid ${voice ? 'rgba(106,169,255,0.5)' : C.border}`,
          background: voice ? 'rgba(106,169,255,0.14)' : 'transparent',
          color: voice ? C.accent : C.sub, borderRadius: 6, padding: '3px 10px', fontSize: 12,
          cursor: 'pointer', fontFamily: 'inherit',
        },
        onClick: () => { setVoice((v) => !v); if (voice) stopSpeak() },
        title: voice ? '关掉自动朗读' : '打开自动朗读',
      }, voice ? '🔊 朗读' : '🔇 静音'),
      speaking
        ? h('button', {
          style: {
            appearance: 'none', border: `1px solid ${C.border}`, background: 'transparent',
            color: C.sub, borderRadius: 6, padding: '3px 10px', fontSize: 12,
            cursor: 'pointer', fontFamily: 'inherit',
          },
          onClick: stopSpeak,
        }, '打断')
        : null,
      h('button', {
        style: {
          appearance: 'none', border: `1px solid ${C.border}`, background: 'transparent',
          color: C.sub, borderRadius: 6, padding: '3px 10px', fontSize: 12,
          cursor: 'pointer', fontFamily: 'inherit',
        },
        onClick: () => { setLines([]); setErr(''); setState('idle') },
      }, '清空'),
      ),

      // 转写区
      h('div', {
        ref: listRef,
        style: {
          flex: 1, overflowY: 'auto', padding: '16px 18px',
          display: 'flex', flexDirection: 'column', gap: 9,
        },
      },
      lines.length === 0
        ? h('div', {
          style: {
            margin: 'auto', textAlign: 'center', color: C.faint,
            fontSize: 13, lineHeight: 1.9, maxWidth: 360,
          },
        },
          h('div', { style: { fontSize: 15, color: C.sub, marginBottom: 6 } }, '像打电话一样说话'),
          h('div', null, '点下面的大按钮开始，说完再点一下，它就把你的话发出去。'),
          h('div', null, '说完不用打字，也不用碰输入框。'),
        )
        : lines.map(bubble),
      ),

      // 错误
      err
        ? h('div', {
          style: {
            margin: '0 18px 8px', padding: '8px 11px', borderRadius: 7,
            background: 'rgba(224,113,111,0.12)', border: '1px solid rgba(224,113,111,0.32)',
            color: '#f0a5a3', fontSize: 12.5, lineHeight: 1.5,
          },
        }, err)
        : null,

      // 底部话筒
      h('div', {
        style: {
          flex: '0 0 auto', padding: '18px 0 26px',
          display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 10,
          borderTop: `1px solid ${C.border}`,
        },
      },
      h('div', {
        style: {
          width: 86, height: 86, borderRadius: '50%',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          cursor: busy ? 'default' : 'pointer',
          background: talking ? 'rgba(224,113,111,0.18)' : 'rgba(106,169,255,0.14)',
          border: `1px solid ${talking ? 'rgba(224,113,111,0.55)' : 'rgba(106,169,255,0.45)'}`,
          boxShadow: talking
            ? `0 0 0 ${Math.round(6 + level * 16)}px rgba(224,113,111,${0.06 + level * 0.1})`
            : 'none',
          transition: 'box-shadow 90ms linear, background 160ms',
          color: talking ? C.red : C.accent,
          WebkitAppRegion: 'no-drag',
        },
        onClick: () => {
          if (busy) return
          if (talking) stopAndSend()
          else startListen()
        },
        title: talking ? '说完了，点一下发送' : '点一下开始说话',
      },
        talking
          ? h('div', { style: { width: 22, height: 22, borderRadius: 4, background: C.red } })
          : h('svg', {
            width: 30, height: 30, viewBox: '0 0 24 24', fill: 'none',
            stroke: 'currentColor', strokeWidth: 1.5, strokeLinecap: 'round',
          },
            h('rect', { x: 9, y: 3, width: 6, height: 11, rx: 3 }),
            h('path', { d: 'M5.5 11.5a6.5 6.5 0 0 0 13 0' }),
            h('line', { x1: 12, y1: 18, x2: 12, y2: 21.5 }),
          ),
      ),
      h('div', { style: { fontSize: 12.5, color: C.faint } },
        talking ? '再点一下结束，自动发送' : busy ? '正在转成文字…' : '点一下开始说话'),
      h('div', { style: { fontSize: 11.5, color: 'rgba(102,102,110,0.75)' } },
        '说完的话会直接进当前对话，不用打字'),
      ),
      )
    }

    const name = 'dsh-call'
    const inject = ['slots']

    function apply(ctx) {
      const disposers = []
      try {
        disposers.push(ctx.slots.inject('sidebar.panellist', () =>
          ctx.slots.register(
            { name: 'sidebar.panellist', id: PANEL_KEY, order: 26, label: () => '通话' },
            PhoneIcon,
          ),
        ))
      } catch (e) {
        try { ctx.logger?.warn?.('dsh-call: 侧栏图标注册失败', e) } catch { }
      }
      try {
        disposers.push(ctx.slots.inject('main', () =>
          ctx.slots.register({ name: 'main', key: PANEL_KEY, inject: () => ({ ctx }) }, CallPanel),
        ))
      } catch (e) {
        try { ctx.logger?.warn?.('dsh-call: 通话面板注册失败', e) } catch { }
      }
      try {
        disposers.push(ctx.slots.inject('conversation.input.right', () =>
          ctx.slots.register(
            { name: 'conversation.input.right', id: 'call-bridge', order: 99 },
            InputBridge,
          ),
        ))
      } catch (e) {
        try { ctx.logger?.warn?.('dsh-call: 输入桥接注册失败', e) } catch { }
      }
      return () => { for (const d of disposers) { try { d?.() } catch { } } }
    }

    return { name, inject, apply }
  },
})
