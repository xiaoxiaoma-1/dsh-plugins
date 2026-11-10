/**
 * my-memory — 客户端：侧栏面板 + 记忆关系图
 *
 * 入口：sidebar.panellist（和「插件」「自动化任务」同组），点击由平台切到
 * main 面板 key=my-memory-graph，悬停/选中高亮全交给侧栏 owner。
 *
 * 上一版的问题（用户截图指出）：节点飞出画布、又小又散、一直乱动选不中。
 * 根因是删了边界约束、斥力过大、物理永不收敛。这版：
 *   - 物理带 alpha 衰减，收敛后**完全静止**，可以直接点
 *   - 加边界约束 + 强向心力，节点聚成一个"团"而不是散在四角
 *   - 节点放大到 2.4–10px，连线提亮到 13% 白
 *
 * 硬经验：
 *   1. 侧栏组件会被 owner 重挂载 → 面板状态不能依赖侧栏组件。
 *   2. Electron 顶栏是拖拽区，按钮要显式 -webkit-app-region: no-drag。
 *   3. panellist 的 id 必须对应 main 的 key，否则点了空白。
 */

window.__ModuleLoader__.load({
  id: 'my-memory',
  factory(require) {
    const React = require('react');
    const h = React.createElement;
    const { useRef, useEffect } = React;

    const LAYERS = [
      { key: 'soul', label: 'AI 自身', color: '#b8a6f0', desc: '我自己的设定' },
      { key: 'user', label: '用户', color: '#7fb4e8', desc: '你的偏好和习惯' },
      { key: 'project', label: '项目', color: '#7fcf9a', desc: '各项目的信息与进度' },
      { key: 'fact', label: '事实', color: '#dcb56a', desc: '客观技术事实' },
      { key: 'lesson', label: '教训', color: '#e08a8a', desc: '被纠正 / 踩过的坑' },
      { key: 'topic', label: '话题', color: '#dd8fb8', desc: '正在聊的事' },
      { key: 'rules', label: '准则', color: '#9aa1e8', desc: '做事的原则' },
    ];
    const COLOR = {}; const LABEL = {};
    for (const l of LAYERS) { COLOR[l.key] = l.color; LABEL[l.key] = l.label; }

    const C = {
      text: 'var(--dsw-alias-label-primary, #cfcfd4)',
      sub: 'var(--dsw-alias-label-secondary, #8a8a92)',
      faint: 'var(--dsw-alias-label-tertiary, #5c5c64)',
      border: 'var(--dsw-alias-separator-primary, rgba(255,255,255,0.06))',
      base: 'var(--dsw-alias-bg-base, #141417)',
    };

    // ── RPC ───────────────────────────────────────────────────────
    function makeRpc() {
      return async (method, payload) => {
        const rpcId = 'rpc-' + Math.random().toString(36).slice(2);
        const resp = await fetch('/api/my-memory-graph', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ type: 'client-request', rpcId, method: 'my-memory-graph', payload: { method, payload: payload || {} } }),
        });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const json = await resp.json();
        if (json?.result?.ok === true) return json.result.value;
        throw new Error(json?.result?.error?.message ?? 'RPC 调用失败');
      };
    }

    async function saveFile(name, text, mime) {
      try {
        if (window.showSaveFilePicker) {
          const handle = await window.showSaveFilePicker({ suggestedName: name });
          const writable = await handle.createWritable();
          await writable.write(new Blob([text], { type: mime }));
          await writable.close();
          return true;
        }
      } catch (e) {
        if (e && e.name === 'AbortError') return false;
      }
      const url = URL.createObjectURL(new Blob([text], { type: mime }));
      const a = document.createElement('a');
      a.href = url;
      a.download = name;
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      return true;
    }

    function el(tag, style, text) {
      const node = document.createElement(tag);
      if (style) Object.assign(node.style, style);
      if (text != null) node.textContent = text;
      return node;
    }
    function noDrag(node) {
      node.style.setProperty('-webkit-app-region', 'no-drag');
      return node;
    }
    function svgEl(tag, attrs) {
      const node = document.createElementNS('http://www.w3.org/2000/svg', tag);
      if (attrs) for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
      return node;
    }

    // ── 力导向（收敛即静止，可精确点选）──────────────────────────
    function createSimulation(nodes, edges, w, hgt) {
      const n = nodes.length;
      const idx = new Map();
      const px = new Float64Array(n);
      const py = new Float64Array(n);
      const vx = new Float64Array(n);
      const vy = new Float64Array(n);
      const rad = new Float64Array(n);
      const degree = new Uint16Array(n);
      const imp = new Float64Array(n);

      const pad = 40;
      nodes.forEach((m, i) => {
        idx.set(m.id, i);
        imp[i] = Math.max(1, Math.min(10, Number(m.importance) || 5));
      });

      const links = [];
      for (const e of edges) {
        const a = idx.get(e.from);
        const b = idx.get(e.to);
        if (a !== undefined && b !== undefined) { links.push([a, b]); degree[a]++; degree[b]++ }
      }

      for (let i = 0; i < n; i++) {
        // 大小 = 连接数 × 重要度；重要的明显更大更亮
        const base = 2.0 + Math.min(6.4, Math.sqrt(degree[i]) * 1.35);
        rad[i] = base * (0.70 + 0.34 * (imp[i] / 10));
      }

      // ── 径向分层 + 簇聚拢 ──────────────────────────────────────
      // 1) 按连通分量分组（一簇就是一坨，互不穿插）
      const parent = new Int32Array(n);
      for (let i = 0; i < n; i++) parent[i] = i;
      const find = (x) => { while (parent[x] !== x) { parent[x] = parent[parent[x]]; x = parent[x] } return x };
      for (const [a, b] of links) { const ra = find(a), rb = find(b); if (ra !== rb) parent[ra] = rb }
      const compMap = new Map();
      for (let i = 0; i < n; i++) { const r = find(i); if (!compMap.has(r)) compMap.set(r, []); compMap.get(r).push(i) }
      const groups = [...compMap.values()].sort((a, b) => b.length - a.length);
      // 孤立点（没有连线）不占扇区，统一撒在最外圈，否则会排成一圈圈靶环
      const linked = groups.filter(g => g.length > 1);
      const singles = groups.filter(g => g.length === 1).map(g => g[0]);

      // 2) 簇-球布局：每簇一个独立小球（球心=分支最多的那条），簇间强制留空
      const cx0 = w / 2, cy0 = hgt / 2;
      const RB = Math.min(w, hgt) * 0.46;
      const depth = new Float64Array(n);
      const bandR = linked.map(g => 10 + 3.4 * Math.sqrt(g.length));

      // 团心：黄金角铺开，迭代推开保证团与团之间留 14px
      const ctrs = linked.map((g, k) => {
        const t = k / Math.max(linked.length - 1, 1);
        const rr = RB * (0.10 + 0.68 * Math.sqrt(t));
        const a = k * 2.399963;
        return [cx0 + Math.cos(a) * rr, cy0 + Math.sin(a) * rr];
      });
      for (let it = 0; it < 600; it++) {
        let moved = false;
        for (let i = 0; i < ctrs.length; i++) {
          for (let j = i + 1; j < ctrs.length; j++) {
            const dx = ctrs[j][0] - ctrs[i][0];
            const dy = ctrs[j][1] - ctrs[i][1];
            const d = Math.sqrt(dx * dx + dy * dy) || 0.01;
            const need = bandR[i] + bandR[j] + 14;
            if (d < need) {
              const push = (need - d) / 2;
              const ux = dx / d, uy = dy / d;
              ctrs[i][0] -= ux * push; ctrs[i][1] -= uy * push;
              ctrs[j][0] += ux * push; ctrs[j][1] += uy * push;
              moved = true;
            }
          }
        }
        for (let i = 0; i < ctrs.length; i++) {
          const vx0 = ctrs[i][0] - cx0, vy0 = ctrs[i][1] - cy0;
          const d = Math.sqrt(vx0 * vx0 + vy0 * vy0);
          const lim = RB - bandR[i] - 6;
          if (d > lim) {
            ctrs[i][0] = cx0 + vx0 / d * lim;
            ctrs[i][1] = cy0 + vy0 / d * lim;
            moved = true;
          }
        }
        if (!moved) break;
      }

      // 团内：最大的当球心，其余黄金角螺旋围绕
      linked.forEach((g, gi) => {
        const cx = ctrs[gi][0], cy = ctrs[gi][1];
        const hub = g.reduce((best, i) => (degree[i] > degree[best] ? i : best), g[0]);
        px[hub] = cx; py[hub] = cy;
        const others = g.filter(i => i !== hub).sort((a, b) => degree[b] - degree[a]);
        others.forEach((i, k) => {
          const a = k * 2.399963 + Math.random() * 0.3;
          const rr = bandR[gi] * Math.sqrt((k + 1) / Math.max(others.length, 1)) * 0.96;
          px[i] = cx + Math.cos(a) * rr;
          py[i] = cy + Math.sin(a) * rr;
        });
      });

      // 孤立点：填在团与团之间的空隙，不吊到最外圈
      for (const i of singles) {
        const a = Math.random() * Math.PI * 2;
        const rr = RB * (0.52 + Math.random() * 0.42);
        px[i] = cx0 + Math.cos(a) * rr;
        py[i] = cy0 + Math.sin(a) * rr;
      }

      // 轻度防重叠（只推开贴在一起的，不破坏团结构）
      for (let it = 0; it < 80; it++) {
        for (let i = 0; i < n; i++) {
          for (let j = i + 1; j < n; j++) {
            const dx = px[j] - px[i], dy = py[j] - py[i];
            const d = Math.sqrt(dx * dx + dy * dy) || 0.01;
            const need = rad[i] + rad[j] + 3;
            if (d < need) {
              const p = (need - d) / 2;
              const ux = dx / d, uy = dy / d;
              px[i] -= ux * p; py[i] -= uy * p;
              px[j] += ux * p; py[j] += uy * p;
            }
          }
        }
      }

      // 景深：越靠中心越近越亮（球感）
      for (let i = 0; i < n; i++) {
        const dd = Math.sqrt((px[i] - cx0) ** 2 + (py[i] - cy0) ** 2) / RB;
        depth[i] = Math.max(0, Math.min(1, 1 - dd * 0.85));
        rad[i] *= 0.72 + 0.50 * depth[i];
      }

      let alpha = 1;

      function tick() {
        // 静态布局：不需要迭代，首帧画完即停
        alpha = 0;
      }

      return {
        px, py, rad, idx, links, tick, n, degree, imp, depth,
        get alpha() { return alpha },
        reset() { alpha = 0 },
      };
    }

    // ── 挂载图谱 ─────────────────────────────────────────────────
    function mountGraph(container, rpc) {
      let disposed = false;
      let raf = 0;

      const root = noDrag(el('div', {
        position: 'relative', width: '100%', height: '100%', minHeight: '360px',
        background: 'radial-gradient(ellipse 90% 70% at 50% 38%, #1c1c24 0%, #151519 42%, #0c0c0f 100%)',
        color: C.text,
        fontFamily: 'inherit', fontSize: '13px',
        display: 'flex', flexDirection: 'column',
        overflow: 'hidden',
      }));

      const bar = noDrag(el('div', {
        display: 'flex', alignItems: 'center', gap: '12px',
        padding: '8px 12px', borderBottom: `1px solid ${C.border}`,
      }));
      bar.appendChild(el('span', {
        fontSize: '12px', fontWeight: '600', letterSpacing: '2px', color: C.sub,
      }, '心印'));
      bar.appendChild(el('span', { fontSize: '11px', color: 'rgba(255,255,255,0.14)' }, '·'));
      const countSpan = el('span', { color: C.faint, fontSize: '11.5px' }, '加载中…');
      bar.appendChild(countSpan);
      bar.appendChild(el('div', { flex: '1' }));

      const search = noDrag(el('input', {
        width: '170px', padding: '3px 8px', borderRadius: '6px',
        border: `1px solid ${C.border}`, background: 'transparent',
        color: C.text, fontSize: '11.5px', outline: 'none',
      }));
      search.placeholder = '搜索';
      bar.appendChild(search);

      const busySpan = el('span', { color: C.faint, fontSize: '11px', minWidth: '42px' }, '');
      bar.appendChild(busySpan);

      const linkBtn = (label, fn) => {
        const b = noDrag(el('button', {
          padding: '2px 6px', borderRadius: '5px', fontSize: '11.5px', cursor: 'pointer',
          border: 'none', background: 'transparent', color: C.faint, WebkitAppRegion: 'no-drag',
        }, label));
        b.addEventListener('mouseenter', () => { b.style.color = C.text });
        b.addEventListener('mouseleave', () => { b.style.color = C.faint });
        b.addEventListener('click', (ev) => { ev.preventDefault(); ev.stopPropagation(); fn() });
        b.addEventListener('pointerdown', (ev) => ev.stopPropagation());
        return b;
      };
      bar.appendChild(linkBtn('重新布局', () => { if (sim) { sim.reset(); startLoop() } }));
      bar.appendChild(linkBtn('导出 JSON', () => doExport('json')));
      bar.appendChild(linkBtn('导出 MD', () => doExport('markdown')));
      bar.appendChild(linkBtn('复位', () => { scale = 1; tx = 0; ty = 0; applyView() }));
      root.appendChild(bar);

      const chips = noDrag(el('div', {
        position: 'absolute', left: '12px', bottom: '12px', zIndex: '2',
        display: 'flex', flexDirection: 'column', gap: '3px',
        padding: '9px 12px', borderRadius: '9px',
        background: 'rgba(18,18,22,0.9)',
        border: `1px solid ${C.border}`,
        fontSize: '11.5px', lineHeight: '1.6',
        maxWidth: '320px',
      }));
      root.appendChild(chips);

      const bodyWrap = el('div', { position: 'relative', flex: '1', minHeight: '0', overflow: 'hidden' });
      root.appendChild(bodyWrap);

      const svg = svgEl('svg', { width: '100%', height: '100%', style: 'display:block; cursor:grab' });
      bodyWrap.appendChild(svg);
      const viewport = svgEl('g', {});
      svg.appendChild(viewport);

      const detail = noDrag(el('div', {
        position: 'absolute', top: '12px', right: '12px', width: '290px',
        maxHeight: 'calc(100% - 40px)', overflow: 'auto', padding: '12px 14px',
        background: 'var(--dsw-alias-bg-layer-2, #1d1d21)',
        border: `1px solid ${C.border}`, borderRadius: '8px',
        fontSize: '12.5px', lineHeight: '1.7', display: 'none',
      }));
      bodyWrap.appendChild(detail);

      // 点空白处 = 取消选中、关闭详情、回到初始态
      svg.addEventListener('click', () => {
        if (!selectedPinned) return;
        selectedPinned = false;
        setFocus(null);
        detail.style.display = 'none';
      });

      let allNodes = [];
      let edges = [];
      const hiddenLevels = new Set();
      let focusedId = null;
      let selectedPinned = false;
      let query = '';
      let sim = null;
      let scale = 1;
      let tx = 0;
      let ty = 0;
      const circles = [];
      const lines = [];
      const glows = [];
      const adj = new Map();

      async function doExport(format) {
        busySpan.textContent = '导出中';
        try {
          const r = await rpc('export', { format });
          const ext = format === 'markdown' ? 'md' : 'json';
          const mime = format === 'markdown' ? 'text/markdown' : 'application/json';
          const stamp = new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-');
          const ok = await saveFile(`my-memory-${stamp}.${ext}`, r?.content ?? '', mime);
          busySpan.textContent = ok ? '已导出' : '已取消';
        } catch (e) {
          busySpan.textContent = '失败';
        }
        setTimeout(() => { busySpan.textContent = '' }, 2500);
      }

      function visibleNodes() {
        let arr = allNodes.filter(m => !hiddenLevels.has(m.level));
        if (query.trim()) {
          const q = query.trim().toLowerCase();
          arr = arr.filter(m => `${m.title} ${m.content} ${(m.tags || []).join(' ')}`.toLowerCase().includes(q));
        }
        return arr;
      }

      function buildScene() {
        const w = bodyWrap.clientWidth || 900;
        const hgt = bodyWrap.clientHeight || 600;
        const nodes = visibleNodes();
        sim = createSimulation(nodes, edges, w, hgt);
        svg.setAttribute('viewBox', `0 0 ${w} ${hgt}`);
        while (viewport.firstChild) viewport.removeChild(viewport.firstChild);
        circles.length = 0;
        lines.length = 0;
        adj.clear();

        nodes.forEach((m) => adj.set(m.id, new Set()));
        for (const e of edges) {
          if (adj.has(e.from) && adj.has(e.to)) {
            adj.get(e.from).add(e.to);
            adj.get(e.to).add(e.from);
          }
        }

        const defs = svgEl('defs', {});
        const gl = svgEl('filter', { id: 'mmGlow', x: '-80%', y: '-80%', width: '260%', height: '260%' });
        gl.appendChild(svgEl('feGaussianBlur', { stdDeviation: '3.4' }));
        defs.appendChild(gl);
        viewport.appendChild(defs);

        for (const [a, b] of sim.links) {
          // 弧线代替直线：星图感，不抢主体
          const line = svgEl('path', {
            fill: 'none',
            stroke: 'rgba(176,190,214,0.10)',
            'stroke-width': '0.6',
            'stroke-linecap': 'round',
          });
          viewport.appendChild(line);
          lines.push({ node: line, a, b });
        }

        const glows = [];
        glows.length = 0;
        nodes.forEach((m, i) => {
          const im = Math.max(1, Math.min(10, Number(m.importance) || 5));
          const col = COLOR[m.level] || '#9a9aa2';
          const dep = sim.depth ? sim.depth[i] : 1;
          const g = svgEl('circle', {
            fill: col, 'fill-opacity': String((0.05 + 0.12 * (im / 10)) * (0.45 + 0.55 * dep)),
            filter: 'url(#mmGlow)', 'pointer-events': 'none',
          });
          viewport.appendChild(g);
          glows.push({ node: g, i, id: m.id, baseOp: (0.05 + 0.12 * (im / 10)) * (0.45 + 0.55 * dep) });
          const baseOp = (0.34 + 0.60 * (im / 10)) * (0.55 + 0.45 * dep);
          const dot = svgEl('circle', {
            r: sim.rad[i], fill: col,
            'fill-opacity': String(baseOp), style: 'cursor:pointer',
          });
          const title = svgEl('title', {});
          title.textContent = `[${LABEL[m.level] || m.level}] ${m.title}`;
          dot.appendChild(title);
          dot.addEventListener('mouseenter', () => { if (!selectedPinned) setFocus(m.id) });
          dot.addEventListener('mouseleave', () => { if (!selectedPinned) setFocus(null) });
          dot.addEventListener('click', (ev) => {
            ev.stopPropagation();
            selectedPinned = true;
            setFocus(m.id);
            showDetail(m);
          });
          viewport.appendChild(dot);
          circles.push({ id: m.id, level: m.level, dot, i, baseOp });
        });

        // 预热到接近收敛，打开就能看清结构
        for (let k = 0; k < 220; k++) sim.tick();
        render();
        startLoop();
      }

      function setFocus(id) {
        if (focusedId === id) return;
        focusedId = id;
        applyFocus();
      }

      function applyFocus() {
        if (!focusedId) {
          for (const c of circles) c.dot.setAttribute('fill-opacity', String(c.baseOp));
          for (const g of glows) g.node.setAttribute('fill-opacity', String(g.baseOp));
          for (const l of lines) l.node.setAttribute('stroke', 'rgba(176,190,214,0.10)');
          return;
        }
        const nb = adj.get(focusedId) || new Set();
        for (const c of circles) {
          const self = c.id === focusedId;
          const near = nb.has(c.id);
          c.dot.setAttribute('fill-opacity', self ? '1' : near ? '0.9' : '0.07');
        }
        for (const g of glows) {
          const near2 = g.id === focusedId || nb.has(g.id);
          g.node.setAttribute('fill-opacity', near2 ? String(g.baseOp * 1.8) : '0');
        }
        for (const l of lines) {
          const a = circles[l.a] && circles[l.a].id;
          const b = circles[l.b] && circles[l.b].id;
          const hit = a === focusedId || b === focusedId;
          l.node.setAttribute('stroke', hit ? 'rgba(220,230,255,0.5)' : 'rgba(180,190,210,0.02)');
        }
      }

      function render() {
        if (!sim) return;
        for (const l of lines) {
          const x1 = sim.px[l.a], y1 = sim.py[l.a];
          const x2 = sim.px[l.b], y2 = sim.py[l.b];
          // 轻微弧度：控制点在中点垂直偏移 7%
          const mx = (x1 + x2) / 2, my = (y1 + y2) / 2;
          const dx = x2 - x1, dy = y2 - y1;
          const cx = mx - dy * 0.07, cy = my + dx * 0.07;
          l.node.setAttribute('d',
            `M${x1.toFixed(1)} ${y1.toFixed(1)} Q${cx.toFixed(1)} ${cy.toFixed(1)} ${x2.toFixed(1)} ${y2.toFixed(1)}`);
        }
        for (const g of glows) {
          const i = g.i;
          g.node.setAttribute('cx', sim.px[i].toFixed(1));
          g.node.setAttribute('cy', sim.py[i].toFixed(1));
          g.node.setAttribute('r', (sim.rad[i] * 2.3).toFixed(1));
        }
        for (const c of circles) {
          const i = c.i;
          c.dot.setAttribute('cx', sim.px[i].toFixed(1));
          c.dot.setAttribute('cy', sim.py[i].toFixed(1));
          const sel = selectedPinned && focusedId === c.id;
          c.dot.setAttribute('r', (sel ? sim.rad[i] + 2 : sim.rad[i]).toFixed(1));
          c.dot.setAttribute('stroke', sel ? '#fff' : 'none');
          c.dot.setAttribute('stroke-width', sel ? '1.2' : '0');
        }
      }

      function startLoop() {
        if (raf) cancelAnimationFrame(raf);
        const step = () => {
          if (disposed || !sim) return;
          sim.tick();
          render();
          // 收敛后停止：static 之后才点得准
          if (sim.alpha === 0) { raf = 0; return }
          raf = requestAnimationFrame(step);
        };
        raf = requestAnimationFrame(step);
      }

      function showDetail(m) {
        detail.style.display = 'block';
        detail.textContent = '';
        const head = el('div', { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' });
        head.appendChild(el('span', { color: COLOR[m.level] || C.text, fontSize: '10.5px', letterSpacing: '1px' }, (LABEL[m.level] || m.level).toUpperCase()));
        const x = noDrag(el('button', {
          padding: '0 6px', border: 'none', background: 'transparent',
          color: C.faint, cursor: 'pointer', fontSize: '15px', lineHeight: '1.3',
        }, '×'));
        x.addEventListener('click', (ev) => {
          ev.stopPropagation();
          detail.style.display = 'none';
          selectedPinned = false;
          setFocus(null);        });
        head.appendChild(x);
        detail.appendChild(head);
        detail.appendChild(el('div', { fontWeight: '600', marginBottom: '8px', fontSize: '13px' }, m.title || ''));
        detail.appendChild(el('div', { color: C.sub, whiteSpace: 'pre-wrap' }, m.content || ''));
        if (m.project) detail.appendChild(el('div', { marginTop: '10px', color: C.faint, fontSize: '11px' }, `项目：${m.project}`));
        if ((m.tags || []).length) detail.appendChild(el('div', { marginTop: '4px', color: C.faint, fontSize: '11px' }, `标签：${m.tags.join('、')}`));
      }

      function buildChips() {
        chips.textContent = '';
        chips.appendChild(el('div', {
          color: C.faint, fontSize: '10.5px', letterSpacing: '0.6px',
          marginBottom: '5px',
        }, '颜色说明 · 点一行可隐藏该类'));

        for (const l of LAYERS) {
          const cnt = allNodes.filter(x => x.level === l.key).length;
          if (cnt === 0) continue;
          const on = !hiddenLevels.has(l.key);
          const row = noDrag(el('div', {
            display: 'flex', alignItems: 'center', gap: '8px',
            cursor: 'pointer', padding: '1px 0',
            color: on ? C.sub : 'rgba(255,255,255,0.22)',
          }));
          row.appendChild(el('span', {
            width: '8px', height: '8px', borderRadius: '999px',
            background: l.color, opacity: on ? '1' : '0.28',
            flexShrink: '0',
          }));
          row.appendChild(el('span', { minWidth: '50px' }, l.label));
          row.appendChild(el('span', { color: C.faint, fontSize: '10.5px' }, `${l.desc} · ${cnt}`));
          row.addEventListener('click', (ev) => {
            ev.preventDefault();
            ev.stopPropagation();
            if (hiddenLevels.has(l.key)) hiddenLevels.delete(l.key);
            else hiddenLevels.add(l.key);
            buildChips();
            buildScene();
          });
          chips.appendChild(row);
        }
      }

      function applyView() {
        viewport.setAttribute('transform', `translate(${tx.toFixed(1)},${ty.toFixed(1)}) scale(${scale.toFixed(3)})`);
      }
      svg.addEventListener('wheel', (e) => {
        e.preventDefault();
        scale = Math.max(0.25, Math.min(4, scale * (e.deltaY > 0 ? 0.9 : 1.1)));
        applyView();
      }, { passive: false });

      let dragging = false;
      let lastX = 0;
      let lastY = 0;
      svg.addEventListener('mousedown', (e) => {
        if (e.button !== 0) return;
        dragging = true;
        lastX = e.clientX;
        lastY = e.clientY;
        svg.style.cursor = 'grabbing';
      });
      const onMove = (e) => {
        if (!dragging) return;
        tx += e.clientX - lastX;
        ty += e.clientY - lastY;
        lastX = e.clientX;
        lastY = e.clientY;
        applyView();
      };
      const onUp = () => {
        if (!dragging) return;
        dragging = false;
        svg.style.cursor = 'grab';
      };
      window.addEventListener('mousemove', onMove);
      window.addEventListener('mouseup', onUp);

      search.addEventListener('input', () => { query = search.value; buildScene() });
      const onResize = () => { try { buildScene() } catch { /* ignore */ } };
      window.addEventListener('resize', onResize);

      container.appendChild(root);

      (async () => {
        try {
          const g = await rpc('graph');
          if (disposed) return;
          allNodes = g?.nodes || [];
          edges = g?.edges || [];
          buildChips();
          buildScene();
          applyView();
          countSpan.textContent = `${allNodes.length} 节点 · ${edges.length} 关系`;
        } catch (e) {
          countSpan.textContent = '加载失败：' + (e && e.message ? e.message : e);
        }
      })();

      return function dispose() {
        disposed = true;
        if (raf) cancelAnimationFrame(raf);
        raf = 0;
        window.removeEventListener('mousemove', onMove);
        window.removeEventListener('mouseup', onUp);
        window.removeEventListener('resize', onResize);
        try { root.remove() } catch { /* ignore */ }
      };
    }

    // ── 主面板 ───────────────────────────────────────────────────
    function MemoryPanel({ rpc }) {
      const hostRef = useRef(null);
      useEffect(() => {
        const host = hostRef.current;
        if (!host) return undefined;
        const dispose = mountGraph(host, rpc);
        return () => { try { dispose() } catch { /* ignore */ } };
      }, []);
      return h('div', {
        ref: hostRef,
        style: { width: '100%', height: '100%', minHeight: '420px', display: 'flex' },
      });
    }

    /**
     * 侧栏图标：星座（用户选定的版本，别再动）。
     * 六颗卫星点 + 中心点，细线相连；只用 currentColor，跟随主题深浅。
     */
    function PanelIcon({ size = 16 }) {
      const R = 8.1;
      const pts = [];
      for (let i = 0; i < 6; i++) {
        const a = (Math.PI / 3) * i - Math.PI / 2;
        pts.push([12 + Math.cos(a) * R, 12 + Math.sin(a) * R]);
      }
      const spokes = pts.map((p, i) => h('line', {
        key: 's' + i, x1: 12, y1: 12, x2: p[0], y2: p[1],
        stroke: 'currentColor', strokeWidth: 0.85, opacity: 0.45, strokeLinecap: 'round',
      }));
      const ring = pts.map((p, i) => {
        const q = pts[(i + 2) % 6];
        return h('line', {
          key: 'r' + i, x1: p[0], y1: p[1], x2: q[0], y2: q[1],
          stroke: 'currentColor', strokeWidth: 0.7, opacity: 0.22, strokeLinecap: 'round',
        });
      });
      const dots = pts.map((p, i) => h('circle', {
        key: 'd' + i, cx: p[0], cy: p[1], r: 1.15, fill: 'currentColor', opacity: 0.8,
      }));
      return h('svg', {
        width: size, height: size, viewBox: '0 0 24 24', fill: 'none',
        'aria-hidden': true, style: { display: 'block' },
      },
      ...ring,
      ...spokes,
      h('circle', { cx: 12, cy: 12, r: 1.7, fill: 'currentColor' }),
      ...dots,
      );
    }

    const name = 'my-memory';
    const inject = ['slots'];
    const PANEL_KEY = 'my-memory-graph';

    function apply(ctx) {
      const rpc = makeRpc();
      const disposers = [];

      try {
        disposers.push(ctx.slots.inject('sidebar.panellist', () =>
          ctx.slots.register(
            { name: 'sidebar.panellist', id: PANEL_KEY, order: 20, label: () => '脉络' },
            PanelIcon,
          ),
        ));
      } catch (e) {
        try { ctx.logger?.warn?.('my-memory: 侧栏导航注册失败', e) } catch { /* 静默 */ }
      }

      try {
        disposers.push(ctx.slots.inject('main', () =>
          ctx.slots.register(
            { name: 'main', key: PANEL_KEY, inject: () => ({ rpc }) },
            MemoryPanel,
          ),
        ));
      } catch (e) {
        try { ctx.logger?.warn?.('my-memory: 主面板注册失败', e) } catch { /* 静默 */ }
      }

      return () => { for (const d of disposers) { try { d?.() } catch { /* ignore */ } } };
    }

    return { name, inject, apply };
  },
});
