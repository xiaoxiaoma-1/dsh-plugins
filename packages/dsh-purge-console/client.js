/**
 * dsh-purge-console — 客户端
 *
 * 作用：把 dsh-purge（破甲）那些原本散落在界面浮层里、或者只能改配置文件才能动的东西，
 * 收进 DSH 设置页左侧栏的一个分节「破甲控制台」。
 *
 * 架构约束（照抄 dsh-plugin-ai-super-search 已验证的契约）：
 *   1. 左侧栏的每一项 = 向 `settings.section` 注册一次，注册项要 id / order / label；
 *   2. 分节自己是容器，用 renderSlot(子 slot 名) 渲染真正的内容；
 *   3. `ctx` 只在 apply() 闭包里可用，组件里拿不到；
 *   4. 状态用 store + hooks 注入，组件通过 props.useXxx(selector) 订阅。
 *
 * 为什么不去改 dsh-purge 本体：它是第三方插件，自带更新通道（v1.1.92 还在迭代），
 * 改它 client.js 下一次更新就被覆盖。所以本插件只调它已经暴露的同源 HTTP 接口：
 *   GET  /dsh-purge/status
 *   POST /dsh-purge/apply      （可带 { content } 覆盖提示词注入）
 *   POST /dsh-purge/revert
 *   POST /dsh-purge/restart
 *   GET  /dsh-purge/hooks-deny
 *   POST /dsh-purge/hooks-deny { hooksDenyBypass: boolean }
 */

window.__ModuleLoader__.load({
  id: 'dsh-purge-console',
  factory: (require) => {
    var module = { exports: {} };
    var exports = module.exports;
    Object.defineProperty(exports, Symbol.toStringTag, { value: 'Module' });

    const React = require('react');
    const { useState, useEffect, useCallback } = React;
    const h = React.createElement;

    // ───────────────────────────── 样式 ─────────────────────────────
    /** 表单作用域类名：原生控件的下拉项 / placeholder 只能用样式表覆盖。 */
    const SCOPE = 'dsh-purge-console-scope';

    const C = {
      primary: 'var(--dsw-alias-label-primary, #0f172a)',
      secondary: 'var(--dsw-alias-label-secondary, #475569)',
      tertiary: 'var(--dsw-alias-label-tertiary, #94a3b8)',
      border: 'var(--dsw-alias-border-l2, #cbd5e1)',
      field: 'var(--dsw-alias-bg-layer-1, transparent)',
      fieldText: 'var(--dsw-alias-label-primary, #0f172a)',
      optionBg: 'var(--dsw-alias-bg-layer-3, #ffffff)',
      btnText: 'var(--dsw-alias-label-primary-inverted, #ffffff)',
      btn: 'var(--dsw-alias-button-primary-fill, #2563eb)',
      ok: 'var(--dsw-alias-state-success-primary, #16a34a)',
      warn: 'var(--dsw-alias-state-warn-primary, #f59e0b)',
      err: 'var(--dsw-alias-state-error-primary, #dc2626)',
    };

    // 字号遵守本机规矩：标题 17px、正文 13px、辅助 12px，行距不低于 1.6。
    const S = {
      wrap: { display: 'flex', flexDirection: 'column', width: '100%', maxWidth: 820, fontSize: 13 },
      card: { border: '1px solid ' + C.border, borderRadius: 12, padding: '18px 20px', marginTop: 14 },
      title: { fontSize: 17, fontWeight: 700, color: C.primary, lineHeight: 1.6, marginBottom: 4 },
      desc: { fontSize: 12.5, color: C.tertiary, lineHeight: 1.7 },
      stats: { display: 'flex', gap: 10, flexWrap: 'wrap', marginTop: 14 },
      stat: { flex: '1 1 120px', minWidth: 110, border: '1px solid ' + C.border, borderRadius: 10, padding: '10px 12px' },
      statNum: { fontSize: 22, fontWeight: 700, lineHeight: 1.3, color: C.primary, fontVariantNumeric: 'tabular-nums' },
      statLabel: { fontSize: 12, color: C.tertiary, marginTop: 2, lineHeight: 1.6 },
      line: { display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'baseline', padding: '7px 0', borderBottom: '1px dashed ' + C.border, fontSize: 13, lineHeight: 1.7 },
      lineKey: { color: C.secondary, flex: '0 0 auto' },
      lineVal: { color: C.primary, textAlign: 'right', overflowWrap: 'anywhere' },
      block: { borderTop: '1px solid ' + C.border, paddingTop: 14, marginTop: 14 },
      name: { fontSize: 14, fontWeight: 600, color: C.primary, lineHeight: 1.6 },
      btnRow: { display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center', marginTop: 14 },
      btn: { height: 36, padding: '0 16px', borderRadius: 9, border: 'none', cursor: 'pointer', fontSize: 13, fontWeight: 600, background: C.btn, color: C.btnText, font: 'inherit' },
      btnGhost: { height: 36, padding: '0 16px', borderRadius: 9, border: '1px solid ' + C.border, background: 'transparent', color: C.secondary, cursor: 'pointer', fontSize: 13, font: 'inherit' },
      btnDanger: { height: 36, padding: '0 16px', borderRadius: 9, border: '1px solid ' + C.err, background: 'transparent', color: C.err, cursor: 'pointer', fontSize: 13, fontWeight: 600, font: 'inherit' },
      tagOk: { display: 'inline-block', fontSize: 11.5, padding: '2px 8px', borderRadius: 5, background: 'rgba(22,163,74,0.12)', color: C.ok, fontWeight: 600 },
      tagWarn: { display: 'inline-block', fontSize: 11.5, padding: '2px 8px', borderRadius: 5, background: 'rgba(245,158,11,0.14)', color: C.warn, fontWeight: 600 },
      tagErr: { display: 'inline-block', fontSize: 11.5, padding: '2px 8px', borderRadius: 5, background: 'rgba(220,38,38,0.13)', color: C.err, fontWeight: 600 },
      note: { marginTop: 12, fontSize: 12.5, lineHeight: 1.7, color: C.warn },
      list: { marginTop: 10, maxHeight: 300, overflowY: 'auto', border: '1px solid ' + C.border, borderRadius: 9, padding: '6px 10px' },
      listRow: { display: 'flex', gap: 10, alignItems: 'baseline', padding: '5px 0', borderBottom: '1px solid ' + C.border, fontSize: 12.5, lineHeight: 1.6 },
      mono: { fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Consolas, monospace', fontSize: 12 },
      toggleRow: { display: 'flex', gap: 10, alignItems: 'flex-start', marginTop: 10 },
      sum: { cursor: 'pointer', fontSize: 13, color: C.secondary, marginTop: 12, lineHeight: 1.7 },
    };

    // ─────────────────────────── 接口调用 ───────────────────────────
    function apiUrl(path) {
      try { return new URL(path, window.location.origin).toString(); } catch { return path; }
    }

    function timeoutOf(path, method) {
      const p = String(path || '');
      const m = String(method || 'GET').toUpperCase();
      if (p.indexOf('/dsh-purge/apply') !== -1) return 240000;
      if (p.indexOf('/dsh-purge/revert') !== -1) return 120000;
      if (p.indexOf('/dsh-purge/restart') !== -1) return 60000;
      if (p.indexOf('/dsh-purge/status') !== -1) return 60000;
      if (m === 'POST') return 60000;
      return 20000;
    }

    async function callApi(path, init) {
      const options = Object.assign({ cache: 'no-store', credentials: 'same-origin' }, init || {});
      const method = options.method || 'GET';
      const ctrl = new AbortController();
      const timer = setTimeout(() => ctrl.abort(), timeoutOf(path, method));
      options.signal = ctrl.signal;
      try {
        const res = await fetch(apiUrl(path), options);
        const text = await res.text();
        let data = null;
        try { data = text ? JSON.parse(text) : null; } catch {
          throw new Error('接口返回了非 JSON 内容（HTTP ' + res.status + '）');
        }
        if (!res.ok) {
          const reason = (data && (data.error || data.missing_ai_base)) || ('HTTP ' + res.status);
          const err = new Error(reason);
          err.status = res.status;
          err.data = data;
          throw err;
        }
        return data || {};
      } catch (e) {
        if (e && (e.name === 'AbortError' || /abort/i.test(String(e.message || '')))) {
          throw new Error('请求超时：' + path + '（后端可能正在同步落盘，稍后刷新看结果）');
        }
        throw e;
      } finally {
        clearTimeout(timer);
      }
    }

    // ───────────────────────────── 小组件 ─────────────────────────────
    function Stat(props) {
      const color = props.tone === 'err' ? C.err : props.tone === 'warn' ? C.warn : props.tone === 'ok' ? C.ok : C.primary;
      return h('div', { style: S.stat },
        h('div', { style: Object.assign({}, S.statNum, { color: color }) }, String(props.value) ),
        h('div', { style: S.statLabel }, props.label));
    }

    function Line(props) {
      return h('div', { style: S.line },
        h('span', { style: S.lineKey }, props.label),
        h('span', { style: S.lineVal }, props.value));
    }

    function statusTag(status) {
      const text = String(status || '');
      if (text === 'applied') return h('span', { style: S.tagOk }, '已打');
      if (text === 'already') return h('span', { style: S.tagOk }, '已在');
      if (text === 'skipped') return h('span', { style: S.tagWarn }, '跳过');
      if (text === 'pending') return h('span', { style: S.tagWarn }, '待处理');
      if (text === 'missing' || text === 'drifted') return h('span', { style: S.tagErr }, '漂移/未命中');
      return h('span', { style: S.tagWarn }, text || '未知');
    }

    // ───────────────────────────── 容器 ─────────────────────────────
    function ConsoleSection(props) {
      return h('div', { style: S.wrap }, props.renderSlot('settings.dsh-purge-console.item'));
    }

    // ───────────────────────────── 表单 ─────────────────────────────
    function ConsoleForm(props) {
      const snap = props.usePurgeConsole((s) => s);
      const [busy, setBusy] = useState('');
      const [openList, setOpenList] = useState(false);

      const run = useCallback(async (label, fn) => {
        setBusy(label);
        try {
          await fn();
        } finally {
          setBusy('');
        }
      }, []);

      const status = snap.status;
      const patches = Array.isArray(status && status.patches) ? status.patches : [];
      const patchNames = (status && status.patch_names) || {};
      const progress = status && status.apply_progress;

      const onApply = () => {
        if (!window.confirm('打补丁会改写 DSH 内置插件文件（已自动备份），完成后需要重启 DSH 才生效。继续？')) return;
        void run('apply', () => props.applyPurge());
      };
      const onRevert = () => {
        if (!window.confirm('回滚会把所有补丁还原成备份原件（保留你自己写的 prompt-inject.md）。继续？')) return;
        void run('revert', () => props.revertPurge());
      };
      const onRestart = () => {
        if (!window.confirm('重启 DSH：当前会话窗口会断开。继续？')) return;
        void run('restart', () => props.restartDsh());
      };

      const noteStyle = Object.assign({}, S.note, {
        color: String(snap.note).startsWith('✅') ? C.ok
          : String(snap.note).startsWith('❌') ? C.err : C.warn,
      });

      return h('div', { style: S.wrap, className: SCOPE },
        h('div', { style: S.card },
          h('div', { style: S.title }, '破甲控制台'),
          h('div', { style: S.desc },
            '这里管理 dsh-purge 对 DSH 的全部改动：补丁、回滚、重启、拦截绕过。'),
          h('div', { style: S.desc },
            '不碰 dsh-purge 本体，只调它自己的接口，所以它升级换代这里不会跟着坏。'),

          snap.loading
            ? h('div', { style: S.note }, '正在读取状态…')
            : null,

          snap.error
            ? h('div', { style: Object.assign({}, S.note, { color: C.err }) }, '❌ ' + snap.error)
            : null,

          status
            ? h('div', null,
              // ── 数字面板：先给结论
              h('div', { style: S.stats },
                h(Stat, {
                  value: status.patches_applied == null ? '—' : status.patches_applied,
                  label: '已生效补丁',
                  tone: 'ok',
                }),
                h(Stat, {
                  value: status.patches_total == null ? '—' : status.patches_total,
                  label: '补丁总数',
                }),
                h(Stat, {
                  value: status.patches_pending == null ? '—' : status.patches_pending,
                  label: '待处理',
                  tone: status.patches_pending ? 'warn' : null,
                }),
                h(Stat, {
                  value: status.patches_drifted == null ? '—' : status.patches_drifted,
                  label: '漂移',
                  tone: status.patches_drifted ? 'err' : null,
                })),

              // ── 关键事实
              h('div', { style: S.block },
                h(Line, { label: '破甲版本', value: status.plugin_version || '—' }),
                h(Line, {
                  label: '宿主版本',
                  value: (status.host_version || '—') + (status.host_supported === false ? '  ⚠ 与插件声明的 ' + (status.host_target || '目标版本') + ' 不一致' : '  ✓ 已适配'),
                }),
                h(Line, {
                  label: 'app.asar',
                  value: status.asar_still_sealed
                    ? '仍处于封包状态 —— 补丁写在解开目录，当前进程读不到'
                    : '已解开，补丁可被读取',
                }),
                h(Line, { label: '备份原件', value: status.has_backup ? '有，可回滚' : '没有 —— 回滚前请先打一次补丁生成备份' }),
                h(Line, { label: '提示词注入', value: status.override_status || '—' }),
                h(Line, { label: '拦截绕过', value: status.hooks_deny_bypass ? '已开启' : '已关闭' }),
                h(Line, { label: 'shim 命令', value: [status.shim_cmd, status.shim_ps1, status.shim_bin].filter(Boolean).join(' · ') || '—' })),

              // ── 进度
              progress && progress.active
                ? h('div', { style: Object.assign({}, S.note, { color: C.warn }) },
                  '⏳ 正在执行：' + (progress.kind || 'apply') + ' / ' + (progress.stage || '准备中'))
                : null,

              // ── 开关
              h('div', { style: S.block },
                h('div', { style: S.name }, '拦截绕过（hooks deny bypass）'),
                h('div', { style: S.desc }, '关掉之后，官方对命令/工具调用的 deny 规则会重新生效。改完立即作用于下一次工具调用，不需要重启。'),
                h('label', { style: S.toggleRow },
                  h('input', {
                    type: 'checkbox',
                    checked: snap.hooksBypass === true,
                    disabled: busy !== '' || snap.saving === true,
                    onChange: (e) => {
                      const next = e.target.checked;
                      void run('hooks', () => props.setHooksBypass(next));
                    },
                  }),
                  h('span', { style: { fontSize: 13, lineHeight: 1.7, color: C.secondary } },
                    snap.hooksBypass ? '当前：已绕过（模型可以正常执行工具）' : '当前：未绕过（官方 deny 生效）'))),

              // ── 动作
              h('div', { style: S.btnRow },
                h('button', {
                  style: Object.assign({}, S.btn, { opacity: busy || snap.saving ? 0.6 : 1 }),
                  disabled: Boolean(busy) || snap.saving === true,
                  onClick: onApply,
                }, busy === 'apply' ? '打补丁中…' : '打补丁'),
                h('button', {
                  style: Object.assign({}, S.btnGhost, { opacity: busy || snap.saving ? 0.6 : 1 }),
                  disabled: Boolean(busy) || snap.saving === true,
                  onClick: onRevert,
                }, busy === 'revert' ? '回滚中…' : '回滚到原件'),
                h('button', {
                  style: Object.assign({}, S.btnDanger, { opacity: busy || snap.saving ? 0.6 : 1 }),
                  disabled: Boolean(busy) || snap.saving === true,
                  onClick: onRestart,
                }, busy === 'restart' ? '重启中…' : '重启 DSH'),
                h('button', {
                  style: S.btnGhost,
                  disabled: Boolean(busy),
                  onClick: () => void run('reload', () => props.reloadStatus()),
                }, busy === 'reload' ? '刷新中…' : '刷新状态')),

              // ── 补丁明细
              patches.length
                ? h('div', { style: S.block },
                  h('div', { style: Object.assign({}, S.sum, { marginTop: 0, cursor: 'pointer' }), onClick: () => setOpenList(!openList) },
                    (openList ? '▾ ' : '▸ ') + '补丁明细（' + patches.length + ' 条）'),
                  openList
                    ? h('div', { style: S.list }, patches.map((p, i) => h('div', { key: String(p.id != null ? p.id : i), style: S.listRow },
                      h('span', { style: Object.assign({}, S.mono, { flex: '0 0 72px', color: C.tertiary }) }, '#' + (p.id != null ? p.id : i)),
                      h('span', { style: { flex: '1 1 auto', color: C.primary } }, patchNames[String(p.id)] || '(未命名)'),
                      h('span', { style: Object.assign({}, S.mono, { flex: '0 0 auto', color: C.tertiary }) }, p.layer || ''),
                      statusTag(p.status))))
                    : null)
                : null)
            : null,

          snap.note ? h('div', { style: noteStyle }, snap.note) : null,

          h('div', { style: S.block },
            h('div', { style: S.desc },
              '说明：补丁和回滚都需要重启 DSH 才算真正生效；重启会断开当前会话窗口，会话记录不会丢。')))
      );
    }

    // ───────────────────────────── 主体 ─────────────────────────────
    const name = 'dsh-purge-console';
    const inject = ['slots'];

    function apply(ctx) {
      let snapshot = {
        loading: true,
        error: '',
        note: '',
        status: null,
        hooksBypass: null,
        saving: false,
      };
      const listeners = new Set();
      const notify = () => { for (const listener of listeners) listener(); };
      const setSnapshot = (patch) => {
        snapshot = Object.assign({}, snapshot, patch);
        notify();
      };
      const store = {
        getSnapshot: () => snapshot,
        subscribe: (listener) => {
          listeners.add(listener);
          return () => { listeners.delete(listener); };
        },
      };

      const reloadStatus = async () => {
        setSnapshot({ loading: true, error: '' });
        try {
          const data = await callApi('/dsh-purge/status');
          setSnapshot({
            loading: false,
            error: '',
            status: data,
            hooksBypass: data.hooks_deny_bypass === true,
          });
        } catch (e) {
          setSnapshot({
            loading: false,
            error: '读不到破甲状态：' + String((e && e.message) || e) +
              '（确认 dsh-purge 已安装并已加载；刚启动时它要等 web 就绪，过几秒刷新一次）',
            status: null,
          });
        }
      };

      const applyPurge = async () => {
        setSnapshot({ saving: true, note: '' });
        try {
          const data = await callApi('/dsh-purge/apply', {
            method: 'POST',
            headers: { 'content-type': 'application/json' },
            body: JSON.stringify({}),
          });
          setSnapshot({ saving: false, note: '✅ 打补丁完成：' + (data && data.message ? data.message : '已写入，重启 DSH 后生效') });
        } catch (e) {
          setSnapshot({ saving: false, note: '❌ 打补丁失败：' + String((e && e.message) || e) });
        }
        await reloadStatus();
      };

      const revertPurge = async () => {
        setSnapshot({ saving: true, note: '' });
        try {
          const data = await callApi('/dsh-purge/revert', {
            method: 'POST',
            headers: { 'content-type': 'application/json' },
            body: JSON.stringify({}),
          });
          setSnapshot({ saving: false, note: '✅ 回滚完成：' + (data && data.message ? data.message : '已还原备份原件，重启 DSH 后生效') });
        } catch (e) {
          setSnapshot({ saving: false, note: '❌ 回滚失败：' + String((e && e.message) || e) });
        }
        await reloadStatus();
      };

      const restartDsh = async () => {
        setSnapshot({ saving: true, note: '' });
        try {
          const data = await callApi('/dsh-purge/restart', {
            method: 'POST',
            headers: { 'content-type': 'application/json' },
            body: JSON.stringify({}),
          });
          if (data && data.ok === false) {
            setSnapshot({ saving: false, note: '⚠ 未能重启：' + (data.error || '未知原因') });
          } else {
            setSnapshot({ saving: false, note: '✅ 已发起重启，窗口马上会断开，重连后生效。' });
          }
        } catch (e) {
          setSnapshot({ saving: false, note: '❌ 重启请求失败：' + String((e && e.message) || e) });
        }
      };

      const setHooksBypass = async (next) => {
        const previous = snapshot.hooksBypass;
        setSnapshot({ saving: true, note: '', hooksBypass: next });
        try {
          await callApi('/dsh-purge/hooks-deny', {
            method: 'POST',
            headers: { 'content-type': 'application/json' },
            body: JSON.stringify({ hooksDenyBypass: next === true }),
          });
          setSnapshot({ saving: false, note: '✅ 已' + (next ? '开启' : '关闭') + '拦截绕过，下一次工具调用起生效。' });
        } catch (e) {
          setSnapshot({ saving: false, hooksBypass: previous, note: '❌ 保存失败：' + String((e && e.message) || e) });
        }
      };

      // 左侧栏分节：这就是「设置左侧栏里出现一项」的全部机制。
      ctx.slots.inject('settings.section', () =>
        ctx.slots.register(
          {
            name: 'settings.section',
            id: 'dsh-purge-console',
            order: 130,
            label: () => '破甲控制台',
            children: { 'settings.dsh-purge-console.item': { kind: 'list', scope: 'root' } },
          },
          ConsoleSection,
        ));

      ctx.slots.inject('settings.dsh-purge-console.item', () =>
        ctx.slots.register(
          {
            name: 'settings.dsh-purge-console.item',
            id: 'dsh-purge-console-form',
            order: 0,
            inject: () => ({ hooks: { purgeConsole: store }, applyPurge, revertPurge, restartDsh, setHooksBypass, reloadStatus }),
          },
          ConsoleForm,
        ));

      // 连接重置（重启后重连）时自动重读一次，避免面板停在旧数字上。
      ctx.effect(
        () => [ctx.on && ctx.on('connection/reset', () => { void reloadStatus(); })].filter(Boolean),
        'dsh-purge-console: reload on connection reset',
      );

      // 深色适配：原生 checkbox 之外的控件（未来加输入框时）走主题变量。
      ctx.effect(() => {
        if (typeof document === 'undefined') return;
        const style = document.createElement('style');
        style.dataset.plugin = 'dsh-purge-console';
        style.textContent = [
          '.' + SCOPE + ' input::placeholder,',
          '.' + SCOPE + ' textarea::placeholder {',
          '  color: ' + C.tertiary + ';',
          '  opacity: 1;',
          '}',
          '.' + SCOPE + ' select option {',
          '  background: ' + C.optionBg + ';',
          '  color: ' + C.fieldText + ';',
          '}',
        ].join('\n');
        document.head.appendChild(style);
        return () => style.remove();
      }, 'dsh-purge-console: field styles');

      void reloadStatus();
    }

    module.exports = { name, inject, apply };
    return module.exports;
  },
});
