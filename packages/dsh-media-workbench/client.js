/**
 * dsh-media-workbench —— 客户端：自媒体工作台（App 首页式卡片墙）。
 *
 * 设计 V2「排版驱动」：
 *   · 不放大图标水印。视觉锚点是序号、字号层级、精确留白。
 *   · 唯一强调色是金色，且只出现在：顶部竖条、hover 顶线、序号高亮。
 *   · 动效克制：入场逐个淡入上浮；hover 时一条金线从左展开、底色微亮。
 */

window.__ModuleLoader__.load({
  id: 'dsh-media-workbench',
  factory(require) {
    const React = require('react')
    const h = React.createElement
    const { useState, useEffect, useRef, useCallback, useMemo } = React

    /* 颜色表（主题 token） */
    const C = {
      text: 'var(--dsw-alias-label-primary)',
      sub: 'var(--dsw-alias-label-secondary)',
      border: 'var(--dsw-alias-border-l1)',
      border2: 'var(--dsw-alias-border-l2)',
      base: 'var(--dsw-alias-bg-base)',
      cell: 'var(--dsw-alias-bg-layer-1)',
      cell2: 'var(--dsw-alias-bg-layer-2)',
      accent: 'var(--dsw-alias-brand-primary)',
      gold: 'var(--mw-gold, #c9a24b)',
      warn: 'var(--dsw-alias-state-warn-primary)',
      err: 'var(--dsw-alias-state-error-primary)',
      ok: 'var(--dsw-alias-state-success-primary)',
    }

    /* ---------------------------------------------------------------- 样式 */
    const CSS = `
@keyframes mw-rise{
  from{ opacity:0; transform: translateY(8px); }
  to{ opacity:1; transform: none; }
}
@keyframes mw-fade{
  from{ opacity:0; }
  to{ opacity:1; }
}
.mw-root{
  --mw-gold: #d9a94a;
  --mw-gold: color-mix(in srgb, #d9a94a 68%, var(--dsw-alias-label-primary) 32%);
  height:100%;
  display:flex;
  flex-direction:column;
  color: var(--dsw-alias-label-primary);
  font-family: inherit;
  -webkit-font-smoothing: antialiased;
  background:
    radial-gradient(ellipse 90% 46% at 50% -12%, color-mix(in srgb, var(--mw-gold) 7%, transparent) 0%, transparent 72%),
    var(--dsw-alias-bg-base);
}
.mw-head{
  position:relative;
  flex:none;
  display:flex;
  align-items:center;
  gap:12px;
  padding:16px 20px 15px;
  border-bottom:1px solid color-mix(in srgb, var(--dsw-alias-border-l1) 80%, transparent);
  animation: mw-fade .4s ease both;
}
.mw-head::after{
  content:'';
  position:absolute; right:0; top:0; width:46%; height:100%;
  background: radial-gradient(ellipse at 82% 30%, color-mix(in srgb, var(--mw-gold) 9%, transparent) 0%, transparent 62%);
  pointer-events:none;
}
.mw-mark{
  width:2px; height:26px; border-radius:2px; flex:none;
  background: linear-gradient(180deg, var(--mw-gold) 0%, color-mix(in srgb, var(--mw-gold) 8%, transparent) 100%);
}
.mw-title{
  font-size:17px; font-weight:640; letter-spacing:.45px; line-height:1.2;
}
.mw-sub{
  margin-top:3px; font-size:10px; letter-spacing:.9px;
  color: var(--dsw-alias-label-secondary); opacity:.72;
}
.mw-date{
  margin-left:auto; display:flex; align-items:center; gap:7px;
  font-size:10px; letter-spacing:.6px; color: var(--dsw-alias-label-secondary);
  padding:4px 11px; border-radius:20px;
  border:1px solid color-mix(in srgb, var(--dsw-alias-border-l1) 90%, transparent);
  position:relative; z-index:1;
}
.mw-dot{ width:3.5px; height:3.5px; border-radius:50%; background:var(--mw-gold); flex:none; }

.mw-body{
  flex:1 1 auto; min-height:0; overflow-y:auto;
  padding:16px 20px 20px;
  display:flex; flex-direction:column; gap:18px;
}
.mw-group{ display:flex; flex-direction:column; gap:10px; }
.mw-ghead{ display:flex; align-items:center; gap:9px; }
.mw-glabel{
  font-size:11px; font-weight:600; letter-spacing:2.4px; text-transform:uppercase;
  color: var(--dsw-alias-label-secondary); opacity:.68; flex:none;
}
.mw-gnote{
  font-size:10.5px; letter-spacing:.4px; color: var(--dsw-alias-label-secondary);
  opacity:.45; flex:none;
}
.mw-gline{
  flex:1 1 auto; height:1px;
  background: linear-gradient(90deg, color-mix(in srgb, var(--dsw-alias-border-l1) 100%, transparent) 0%, transparent 92%);
}
.mw-gnum{
  font-size:9px; letter-spacing:.5px; color:var(--dsw-alias-label-secondary);
  opacity:.3; flex:none; font-variant-numeric:tabular-nums;
}

.mw-grid{ display:grid; grid-template-columns:repeat(4, minmax(0,1fr)); grid-auto-rows:1fr; gap:9px; }

.mw-card{
  position:relative; overflow:hidden; text-align:left;
  appearance:none; cursor:pointer; font-family:inherit; color:inherit;
  padding:16px 18px 15px;
  min-height:136px;
  border-radius:13px;
  border:1px solid color-mix(in srgb, var(--dsw-alias-border-l1) 88%, transparent);
  background: var(--dsw-alias-bg-layer-1);
  display:flex; flex-direction:column;
  transition: border-color .28s ease, background-color .28s ease, transform .28s cubic-bezier(.2,.7,.3,1);
  opacity:0;
  animation: mw-rise .5s cubic-bezier(.2,.7,.3,1) forwards;
}
.mw-card::before{
  content:''; position:absolute; left:0; right:0; top:0; height:1px;
  background: linear-gradient(90deg, var(--mw-gold) 0%, transparent 78%);
  transform: scaleX(0); transform-origin:left;
  transition: transform .5s cubic-bezier(.2,.7,.3,1);
  pointer-events:none;
  opacity:.85;
}
.mw-card:hover{
  border-color: color-mix(in srgb, var(--mw-gold) 26%, var(--dsw-alias-border-l2));
  background: color-mix(in srgb, var(--mw-gold) 4%, var(--dsw-alias-bg-layer-1));
  transform: translateY(-1.5px);
}
.mw-card:hover::before{ transform: scaleX(1); }

.mw-idx{
  font-size:11px; font-weight:600; letter-spacing:1.4px;
  color: var(--dsw-alias-label-secondary); opacity:.48;
  margin-bottom:10px; font-variant-numeric:tabular-nums;
  transition: color .28s ease, opacity .28s ease;
}
.mw-card:hover .mw-idx{ color: var(--mw-gold); opacity:1; }

.mw-ctitle{
  font-size:17px; font-weight:600; letter-spacing:.35px; line-height:1.25;
  margin-bottom:6px;
}
.mw-cdesc{
  font-size:12.5px; line-height:1.6;
  color: var(--dsw-alias-label-secondary); opacity:.88;
  display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden;
  max-width: 94%;
}
.mw-cfoot{
  margin-top:auto; padding-top:11px;
  display:flex; align-items:center; gap:8px;
  font-size:11px; letter-spacing:.35px;
  color: var(--dsw-alias-label-secondary); opacity:.68;
  font-variant-numeric:tabular-nums;
}
.mw-cbar{
  width:12px; height:1px; flex:none;
  background: color-mix(in srgb, var(--dsw-alias-border-l2) 100%, transparent);
  transition: width .3s cubic-bezier(.2,.7,.3,1), background-color .3s ease;
}
.mw-card:hover .mw-cbar{ width:22px; background: var(--mw-gold); }
.mw-cstat{ overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }

.mw-card.is-accent .mw-idx{ color: var(--mw-gold); opacity:.9; }
.mw-card.is-accent .mw-cfoot{ color: color-mix(in srgb, var(--mw-gold) 55%, var(--dsw-alias-label-secondary)); opacity:.8; }

/* 详情 */
.mw-detail{ height:100%; display:flex; flex-direction:column; animation: mw-fade .34s ease both; }
.mw-dhead{
  flex:none; display:flex; align-items:center; gap:10px;
  padding:16px 20px 13px;
  border-bottom:1px solid color-mix(in srgb, var(--dsw-alias-border-l1) 80%, transparent);
}
.mw-back{
  appearance:none; cursor:pointer; font-family:inherit;
  font-size:12.5px; letter-spacing:.3px; font-weight:500;
  color: var(--dsw-alias-label-primary);
  background: color-mix(in srgb, var(--dsw-alias-bg-layer-2) 85%, transparent);
  border:1px solid color-mix(in srgb, var(--dsw-alias-border-l1) 85%, transparent);
  border-radius:7px; padding:5px 11px;
  transition: color .18s ease, background-color .18s ease, border-color .18s ease;
  opacity:1;
}
.mw-back:hover{
  color: var(--mw-gold);
  border-color: color-mix(in srgb, var(--mw-gold) 45%, var(--dsw-alias-border-l2));
  background: color-mix(in srgb, var(--mw-gold) 10%, var(--dsw-alias-bg-layer-2));
}
.mw-dtitle{ font-size:14px; font-weight:600; letter-spacing:.4px; }
.mw-dtag{
  font-size:9px; letter-spacing:.9px; color: var(--dsw-alias-label-secondary);
  border:1px solid color-mix(in srgb, var(--dsw-alias-border-l1) 90%, transparent);
  border-radius:20px; padding:1px 8px; opacity:.8;
}
.mw-dbody{
  flex:1 1 auto; min-height:0; overflow-y:auto;
  padding:18px 20px 26px;
}
.mw-badge{
  display:inline-flex; align-items:center; gap:6px;
  font-size:9.5px; letter-spacing:.7px;
  color: var(--dsw-alias-label-secondary); opacity:.72;
  border:1px dashed color-mix(in srgb, var(--dsw-alias-border-l2) 100%, transparent);
  border-radius:6px; padding:3px 9px; margin-bottom:16px;
}
.mw-dtext{
  font-size:12.5px; line-height:1.95; white-space:pre-wrap; max-width:690px;
}

/* 热点面板 */
.mw-hot-head{
  display:flex; align-items:center; gap:12px; margin-bottom:16px; flex-wrap:wrap;
}
.mw-hot-meta{ font-size:10px; letter-spacing:.5px; color:var(--dsw-alias-label-secondary); opacity:.7; }
.mw-hot-btn{
  appearance:none; cursor:pointer; font-family:inherit; font-size:10.5px; letter-spacing:.5px;
  color: var(--dsw-alias-label-primary); background: var(--dsw-alias-bg-layer-2);
  border:1px solid color-mix(in srgb, var(--dsw-alias-border-l1) 90%, transparent);
  border-radius:7px; padding:5px 12px;
  transition: border-color .24s ease, color .24s ease;
}
.mw-hot-btn:hover{ border-color: color-mix(in srgb, var(--mw-gold) 40%, var(--dsw-alias-border-l2)); color: var(--mw-gold); }
.mw-hot-btn:disabled{ opacity:.45; cursor:default; }
.mw-hot-group{ margin-bottom:20px; }
.mw-hot-gt{
  display:flex; align-items:center; gap:9px; margin-bottom:9px;
}
.mw-hot-gt-label{
  font-size:9px; letter-spacing:2.4px; font-weight:600; text-transform:uppercase;
  color: var(--dsw-alias-label-secondary); opacity:.65; flex:none;
}
.mw-hot-gt-line{ flex:1 1 auto; height:1px; background: linear-gradient(90deg, var(--dsw-alias-border-l1) 0%, transparent 90%); }
.mw-hot-item{
  padding:10px 0 10px 12px; margin-bottom:2px;
  border-left:1px solid color-mix(in srgb, var(--dsw-alias-border-l1) 70%, transparent);
  transition: border-color .24s ease;
}
.mw-hot-item:hover{ border-left-color: var(--mw-gold); }
.mw-hot-title{
  font-size:15.5px; font-weight:600; line-height:1.45; margin-bottom:6px; color: var(--dsw-alias-label-primary);
}
.mw-hot-body{
  font-size:13px; line-height:1.7; color: var(--dsw-alias-label-secondary);
  display:-webkit-box; -webkit-line-clamp:3; -webkit-box-orient:vertical; overflow:hidden;
}
.mw-hot-foot{
  margin-top:7px; display:flex; align-items:center; gap:12px;
  font-size:11px; letter-spacing:.4px; color:var(--dsw-alias-label-secondary); opacity:.6;
  font-variant-numeric: tabular-nums;
}
.mw-hot-foot a{ color:inherit; text-decoration:none; border-bottom:1px solid color-mix(in srgb, var(--dsw-alias-border-l2) 80%, transparent); }
.mw-hot-foot a:hover{ color: var(--mw-gold); border-bottom-color: var(--mw-gold); }
.mw-empty{
  padding:32px 0; text-align:center; font-size:11.5px; color:var(--dsw-alias-label-secondary); opacity:.6;
}
.mw-err{ font-size:11px; color: var(--dsw-alias-state-error-primary); opacity:.9; margin-top:8px; }
.mw-insight{
  margin-top:9px; padding:9px 12px;
  font-size:12.5px; line-height:1.75;
  color: var(--dsw-alias-label-primary); opacity:.88;
  background: color-mix(in srgb, var(--mw-gold) 7%, transparent);
  border-left:2px solid color-mix(in srgb, var(--mw-gold) 55%, transparent);
  border-radius:0 6px 6px 0;
}
.mw-insight-tag{ color: var(--mw-gold); opacity:.95; font-weight:600; letter-spacing:.4px; }

/* 每日灵感 */
.mw-idea-src{
  display:flex; gap:10px; align-items:flex-start;
  padding:11px 13px; border-radius:8px;
  background: color-mix(in srgb, var(--dsw-alias-bg-layer-2) 70%, transparent);
  border:1px solid color-mix(in srgb, var(--dsw-alias-border-l1) 80%, transparent);
}
.mw-idea-no{
  flex:none; font-size:11px; letter-spacing:1px; color:var(--dsw-alias-label-secondary);
  opacity:.75; padding-top:2px; font-weight:600;
}
.mw-idea-txt{
  font-size:13px; line-height:1.75; color:var(--dsw-alias-label-primary); opacity:.92;
}
.mw-idea-q{
  margin-top:10px; padding:10px 13px;
  font-size:13.5px; line-height:1.7; font-weight:600;
  color: var(--dsw-alias-label-primary);
  border-radius:8px;
  background: color-mix(in srgb, var(--mw-gold) 9%, transparent);
  border:1px dashed color-mix(in srgb, var(--mw-gold) 45%, transparent);
}
.mw-idea-q-tag{
  color: var(--mw-gold); font-weight:600; letter-spacing:.5px; margin-right:8px; font-size:12px;
}
.mw-explain{
  margin-top:10px; padding:12px 14px;
  font-size:13px; line-height:1.85; white-space:pre-wrap;
  color: var(--dsw-alias-label-primary); opacity:.94;
  background: color-mix(in srgb, var(--dsw-alias-bg-layer-2) 88%, transparent);
  border:1px solid color-mix(in srgb, var(--dsw-alias-border-l1) 90%, transparent);
  border-radius:8px;
}
.mw-clip-ask{
  padding:16px 18px; margin-bottom:18px; border-radius:10px;
  background: color-mix(in srgb, var(--mw-gold) 8%, var(--dsw-alias-bg-layer-1));
  border:1px solid color-mix(in srgb, var(--mw-gold) 42%, transparent);
}

/* 类型筛选 chips */
.mw-chips{ display:flex; flex-wrap:wrap; gap:7px; margin-bottom:6px; }
.mw-chip{
  appearance:none; cursor:pointer; font-family:inherit;
  padding:6px 12px; border-radius:20px;
  font-size:11.5px; letter-spacing:.3px; line-height:1.4;
  color: var(--dsw-alias-label-secondary);
  background: transparent;
  border:1px solid color-mix(in srgb, var(--dsw-alias-border-l1) 90%, transparent);
  transition: color .2s, border-color .2s, background .2s;
}
.mw-chip:hover{ color: var(--dsw-alias-label-primary); border-color: color-mix(in srgb, var(--mw-gold) 42%, transparent); }
.mw-chip.on{
  color:#17170F; background: var(--mw-gold); border-color: transparent; font-weight:600;
}

/* 原子条目 */
.mw-atom{ padding:16px 0 17px; border-bottom:1px solid color-mix(in srgb, var(--dsw-alias-border-l1) 55%, transparent); }
.mw-atom:last-child{ border-bottom:none; }
.mw-atom-top{ display:flex; align-items:center; gap:9px; margin-bottom:9px; }
.mw-atom-type{
  font-size:10px; letter-spacing:.7px; text-transform:uppercase; flex:none;
  padding:2.5px 8px; border-radius:5px;
  background: color-mix(in srgb, var(--mw-gold) 13%, transparent);
  color: color-mix(in srgb, var(--mw-gold) 86%, var(--dsw-alias-label-primary) 14%);
}
.mw-atom-type.t-case{ background: color-mix(in srgb, #6ea8d9 14%, transparent); color: #8fc0e8; }
.mw-atom-type.t-principle{ background: color-mix(in srgb, #d98a6e 14%, transparent); color: #e8a58c; }
.mw-atom-type.t-method{ background: color-mix(in srgb, #7fb98a 14%, transparent); color: #9dd0a6; }
.mw-atom-type.t-tool{ background: color-mix(in srgb, #9a8fd9 14%, transparent); color: #b6aee8; }
.mw-atom-type.t-anti-pattern{ background: color-mix(in srgb, #d96e8a 14%, transparent); color: #e89cb2; }
.mw-atom-date{ font-size:11px; color: var(--dsw-alias-label-secondary); opacity:.6; font-variant-numeric:tabular-nums; }
.mw-atom-conf{ font-size:10px; color: var(--dsw-alias-label-secondary); opacity:.34; margin-left:auto; }
.mw-atom-k{ font-size:14.5px; line-height:1.74; letter-spacing:.2px; }
.mw-atom-o{
  margin-top:10px; font-size:12.5px; line-height:1.68; white-space:pre-wrap;
  color: var(--dsw-alias-label-secondary); opacity:.6;
  display:-webkit-box; -webkit-line-clamp:3; -webkit-box-orient:vertical; overflow:hidden;
}
.mw-atom-foot{ margin-top:9px; font-size:11.5px; }
.mw-atom-foot a{
  color: color-mix(in srgb, var(--mw-gold) 80%, var(--dsw-alias-label-primary) 20%);
  text-decoration:none; border-bottom:1px solid transparent;
}
.mw-atom-foot a:hover{ border-bottom-color: currentColor; }

/* 稿库条目 */
.mw-post{ padding:16px 0 17px; border-bottom:1px solid color-mix(in srgb, var(--dsw-alias-border-l1) 55%, transparent); }
.mw-post:last-child{ border-bottom:none; }
.mw-post-top{ display:flex; align-items:center; gap:9px; margin-bottom:9px; }
.mw-post-date{ font-size:11px; color: var(--dsw-alias-label-secondary); opacity:.6; font-variant-numeric:tabular-nums; }
.mw-post-kind{
  font-size:10px; padding:2px 7px; border-radius:5px; flex:none;
  background: color-mix(in srgb, var(--dsw-alias-label-primary) 7%, transparent);
  color: var(--dsw-alias-label-secondary);
}
.mw-post-text{
  font-size:14px; line-height:1.74; white-space:pre-wrap;
  display:-webkit-box; -webkit-line-clamp:6; -webkit-box-orient:vertical; overflow:hidden;
}

/* ===== 精修层 v2（高级感）：只覆盖视觉，不改结构 =====
   原则：去掉大光晕、减少圆角、压低边框对比、拉开字级、留白节奏统一到 4px 网格 */
.mw-root{
  --mw-gold: color-mix(in srgb, #c8a04a 74%, var(--dsw-alias-label-primary) 26%);
  --mw-line: color-mix(in srgb, var(--dsw-alias-border-l1) 62%, transparent);
  --mw-line-2: color-mix(in srgb, var(--dsw-alias-border-l1) 40%, transparent);
  background: var(--dsw-alias-bg-base);
}
/* 头部：去掉右侧光斑，用一条细线收边 */
.mw-head{
  padding: 20px 24px 16px;
  gap: 14px;
  border-bottom: 1px solid var(--mw-line);
}
.mw-head::after{ display:none; }
.mw-mark{ width:2px; height:22px; opacity:.85; }
.mw-title{ font-size:18px; font-weight:660; letter-spacing:.2px; }
.mw-sub{ margin-top:4px; font-size:11px; letter-spacing:.3px; opacity:.62; }
.mw-date{
  border-radius:8px; border-color:var(--mw-line);
  font-size:11px; padding:5px 10px; letter-spacing:.2px;
}
.mw-body{ padding:20px 24px 28px; gap:20px; }
.mw-group{ gap:12px; }

/* 分组标题：更小更轻，靠留白分层 */
.mw-ghead{ padding-bottom:6px; }
.mw-glabel{ font-size:11.5px; letter-spacing:.4px; font-weight:600; opacity:.9; }
.mw-gnote{ font-size:11px; opacity:.5; }
.mw-gline{ height:1px; background:var(--mw-line-2); }

/* 卡片：单一表面、细边、hover 只提亮边框 */
.mw-card{
  border-radius:10px;
  border:1px solid var(--mw-line-2);
  background: color-mix(in srgb, var(--dsw-alias-bg-layer-1) 55%, transparent);
  padding:18px 18px 15px;
  transition: border-color .18s ease, background .18s ease, transform .18s ease;
}
.mw-card::before{ display:none; }
.mw-card:hover{
  border-color: color-mix(in srgb, var(--mw-gold) 42%, var(--mw-line));
  background: color-mix(in srgb, var(--dsw-alias-bg-layer-1) 78%, transparent);
  transform: translateY(-1px);
}
.mw-ctitle{ font-size:15px; font-weight:620; letter-spacing:.1px; }
.mw-cdesc{ font-size:12.5px; line-height:1.7; opacity:.62; margin-top:5px; }
.mw-cstat, .mw-cfoot{ font-size:11px; letter-spacing:.2px; opacity:.5; }
.mw-cbar{ height:1px; background:var(--mw-line-2); }

/* 序号与徽标：去装饰感 */
.mw-idx{ font-size:10px; opacity:.34; letter-spacing:.5px; }
.mw-badge{ border-radius:6px; font-size:10px; padding:2px 7px; }

/* 筛选 chip：方块化、去胶囊 */
.mw-chip{
  border-radius:7px; border:1px solid var(--mw-line-2);
  padding:5px 10px; font-size:12px; letter-spacing:.1px;
  transition: border-color .15s, color .15s, background .15s;
}
.mw-chip:hover{ border-color:var(--mw-line); }
.mw-chip.on{
  border-color: color-mix(in srgb, var(--mw-gold) 60%, transparent);
  background: color-mix(in srgb, var(--mw-gold) 10%, transparent);
  color: color-mix(in srgb, var(--mw-gold) 88%, var(--dsw-alias-label-primary) 12%);
}

/* 按钮：幽灵态，默认无底 */
.mw-hot-btn{
  border-radius:7px; border:1px solid var(--mw-line-2);
  padding:5px 11px; font-size:12px; letter-spacing:.1px;
  background:transparent; transition: border-color .15s, background .15s;
}
.mw-hot-btn:hover{ border-color:var(--mw-line); background: color-mix(in srgb, var(--dsw-alias-label-primary) 3%, transparent); }

/* 列表项：靠 hairline 分隔，不靠底色 */
.mw-hot-item{
  border-radius:9px; border:1px solid transparent;
  padding:12px 14px;
  transition: border-color .15s, background .15s;
}
.mw-hot-item:hover{ border-color:var(--mw-line-2); background: color-mix(in srgb, var(--dsw-alias-label-primary) 2%, transparent); }
.mw-hot-title{ font-size:14px; font-weight:560; line-height:1.55; letter-spacing:.1px; }
.mw-hot-foot{ font-size:11.5px; opacity:.55; }
.mw-hot-meta{ font-size:11px; opacity:.55; }

/* 详情页 */
.mw-detail{ background: var(--dsw-alias-bg-base); }
.mw-dhead{ padding:18px 22px 14px; border-bottom:1px solid var(--mw-line); gap:12px; }
.mw-dtitle{ font-size:17px; font-weight:640; }
.mw-dtag{
  font-size:11px; padding:3px 9px; border-radius:6px;
  background: color-mix(in srgb, var(--dsw-alias-label-primary) 5%, transparent);
  border:1px solid var(--mw-line-2);
}
.mw-back{
  border-radius:7px; padding:4px 9px; font-size:12px;
  border:1px solid var(--mw-line-2); background:transparent;
}
.mw-back:hover{ border-color:var(--mw-line); }
.mw-dbody{ padding:20px 22px 30px; }

/* 正文与引用 */
.mw-post{ border-radius:9px; padding:14px 16px; border:1px solid var(--mw-line-2); margin-bottom:10px; background: color-mix(in srgb, var(--dsw-alias-bg-layer-1) 42%, transparent); }
.mw-post:hover{ border-color: var(--mw-line); }
.mw-post-text{ font-size:14px; line-height:1.8; }
.mw-post-date, .mw-post-kind{ font-size:10.5px; opacity:.5; }
.mw-atom{ padding:16px 0 18px; border-bottom:1px solid var(--mw-line-2); }
.mw-atom-k{ font-size:14.5px; line-height:1.8; }
.mw-atom-o{ font-size:12.5px; opacity:.5; }
.mw-insight{
  border-left:2px solid color-mix(in srgb, var(--mw-gold) 55%, transparent);
  padding-left:12px; font-size:13.5px; line-height:1.8;
}
.mw-insight-tag{ font-size:10.5px; letter-spacing:.4px; opacity:.6; display:block; margin-bottom:4px; }
.mw-explain{ font-size:13.5px; line-height:1.85; opacity:.86; }
.mw-empty{ font-size:13px; opacity:.45; letter-spacing:.2px; }
.mw-err{ border-radius:8px; padding:10px 12px; font-size:12.5px; }

.mw-topic-tag{
  font-size:10px; padding:2px 8px; border-radius:999px; flex:none; letter-spacing:.3px;
  background: color-mix(in srgb, var(--mw-gold) 14%, transparent);
  color: color-mix(in srgb, var(--mw-gold) 80%, var(--dsw-alias-label-primary) 20%);
}

/* ===== 精修层 v3：大厂设计系统（排版驱动，去装饰） ===== */
.mw-root{
  background: var(--dsw-alias-bg-base) !important;
  --mw-gold: color-mix(in srgb, #c8a04a 78%, var(--dsw-alias-label-primary) 22%);
  --mw-hair: color-mix(in srgb, var(--dsw-alias-label-primary) 12%, transparent);
  --mw-hair-2: color-mix(in srgb, var(--dsw-alias-label-primary) 7%, transparent);
  --mw-ink: var(--dsw-alias-label-primary);
  --mw-ink-2: color-mix(in srgb, var(--dsw-alias-label-primary) 62%, transparent);
  --mw-ink-3: color-mix(in srgb, var(--dsw-alias-label-primary) 40%, transparent);
}
/* 头部：大标题 + 极细底边，去掉全部光斑 */
.mw-head{ padding: 26px 28px 18px !important; border-bottom: 1px solid var(--mw-hair) !important; }
.mw-head::after{ display:none !important; }
.mw-mark{ width:3px !important; height:26px !important; background: var(--mw-gold) !important; opacity:1 !important; }
.mw-title{ font-size:20px !important; font-weight:650 !important; letter-spacing:0 !important; }
.mw-sub{ margin-top:6px !important; font-size:11.5px !important; letter-spacing:.6px !important; color:var(--mw-ink-3) !important; opacity:1 !important; }
.mw-date{ border:none !important; padding:0 !important; background:none !important; font-size:11.5px !important; color:var(--mw-ink-3) !important; }
.mw-body{ padding:24px 28px 32px !important; gap:26px !important; }
.mw-group{ gap:14px !important; }

/* 分组头：小号字距标签 + 右侧细线 */
.mw-ghead{ padding-bottom:8px !important; border-bottom:1px solid var(--mw-hair-2) !important; }
.mw-glabel{ font-size:11px !important; letter-spacing:1.4px !important; font-weight:600 !important; color:var(--mw-ink-2) !important; opacity:1 !important; }
.mw-gnote{ font-size:11px !important; color:var(--mw-ink-3) !important; opacity:1 !important; }
.mw-gline{ display:none !important; }
.mw-gnum{ font-variant-numeric:tabular-nums; color:var(--mw-ink-3) !important; }

/* 卡片：无底色，纯 1px 边框，靠留白撑场 */
.mw-card{
  background: transparent !important;
  border: 1px solid var(--mw-hair) !important;
  border-radius: 6px !important;
  padding: 20px 20px 16px !important;
  box-shadow: none !important;
  transition: border-color .16s ease, background .16s ease !important;
}
.mw-card::before{ display:none !important; }
.mw-card:hover{ background: var(--mw-hair-2) !important; border-color: var(--mw-gold) !important; transform:none !important; }
.mw-idx{ position:absolute; top:14px; right:16px; font-size:10.5px !important; letter-spacing:.8px; color:var(--mw-ink-3) !important; opacity:1 !important; font-variant-numeric:tabular-nums; }
.mw-ctitle{ font-size:16px !important; font-weight:600 !important; letter-spacing:.1px !important; }
.mw-cdesc{ margin-top:8px !important; font-size:12.5px !important; line-height:1.75 !important; color:var(--mw-ink-2) !important; opacity:1 !important; }
.mw-cstat{ margin-top:14px !important; font-size:11px !important; color:var(--mw-ink-3) !important; opacity:1 !important; }
.mw-cbar{ display:none !important; }
.mw-cfoot{ font-size:11px !important; color:var(--mw-ink-3) !important; opacity:1 !important; }
.mw-badge{ border-radius:3px !important; font-size:10px !important; padding:2px 6px !important; border:1px solid var(--mw-hair) !important; background:none !important; }

/* 筛选项：纯文字，选中用金色下划线，不做胶囊不做块 */
.mw-chip{
  border:none !important; background:none !important; border-radius:0 !important;
  padding:5px 0 !important; margin-right:20px !important;
  font-size:12.5px !important; color:var(--mw-ink-3) !important;
  border-bottom:1px solid transparent !important;
}
.mw-chip:hover{ color:var(--mw-ink) !important; }
.mw-chip.on{ color:var(--mw-ink) !important; border-bottom-color: var(--mw-gold) !important; font-weight:600 !important; background:none !important; }

/* 按钮：文字按钮，hover 出下划线 */
.mw-hot-btn{
  border:none !important; background:none !important; border-radius:0 !important;
  padding:2px 0 !important; font-size:12.5px !important; color:var(--mw-gold) !important;
  border-bottom:1px solid transparent !important;
}
.mw-hot-btn:hover{ border-bottom-color: var(--mw-gold) !important; background:none !important; }
.mw-hot-btn:disabled{ color:var(--mw-ink-3) !important; }

/* 列表项：只靠 hairline 分隔，无底色无圆角 */
.mw-hot-item{ border:none !important; border-bottom:1px solid var(--mw-hair-2) !important; border-radius:0 !important; padding:14px 0 !important; background:none !important; }
.mw-hot-item:hover{ background:none !important; border-bottom-color: var(--mw-hair) !important; }
.mw-hot-title{ font-size:14.5px !important; font-weight:560 !important; line-height:1.55 !important; }
.mw-hot-foot{ font-size:11.5px !important; color:var(--mw-ink-3) !important; opacity:1 !important; }
.mw-hot-meta{ font-size:11.5px !important; color:var(--mw-ink-3) !important; opacity:1 !important; }

/* 详情页同语言 */
.mw-dhead{ padding:24px 28px 16px !important; border-bottom:1px solid var(--mw-hair) !important; }
.mw-dtitle{ font-size:19px !important; font-weight:640 !important; }
.mw-dtag{ border:none !important; background:none !important; font-size:11.5px !important; color:var(--mw-ink-3) !important; padding:0 !important; }
.mw-back{ border:none !important; background:none !important; padding:0 !important; font-size:12.5px !important; color:var(--mw-ink-2) !important; }
.mw-back:hover{ color:var(--mw-gold) !important; }
.mw-dbody{ padding:24px 28px 34px !important; }

/* 正文 */
.mw-post{ border:none !important; border-bottom:1px solid var(--mw-hair-2) !important; border-radius:0 !important; background:none !important; padding:16px 0 !important; margin:0 !important; }
.mw-post:hover{ background:none !important; }
.mw-post-text{ font-size:14.5px !important; line-height:1.85 !important; }
.mw-atom{ border-bottom:1px solid var(--mw-hair-2) !important; padding:18px 0 20px !important; }
.mw-atom-k{ font-size:15px !important; line-height:1.85 !important; }
.mw-insight{ border-left:2px solid var(--mw-gold) !important; padding-left:14px !important; }
.mw-explain{ font-size:14px !important; line-height:1.9 !important; color:var(--mw-ink-2) !important; }
.mw-empty{ font-size:13px !important; color:var(--mw-ink-3) !important; opacity:1 !important; }
.mw-topic-tag{ border-radius:3px !important; background:none !important; border:1px solid var(--mw-hair) !important; color:var(--mw-ink-2) !important; font-size:10px !important; }

/* 头部要有独立层叠上下文，否则下拉会被下方卡片盖住（看起来像弹层透明、点不到） */
.mw-head{ position: relative !important; z-index: 30 !important; }
.mw-body{ position: relative !important; z-index: 0 !important; }
.mw-dhead{ position: relative !important; z-index: 30 !important; }
.mw-dbody{ position: relative !important; z-index: 0 !important; }

/* 头部右侧：spacer 已把内容推开，日期不再自动占位，模型选择器紧贴其左 */
.mw-date{ margin-left: 0 !important; }
.mw-dtag{ margin-left: 0 !important; }

/* 原子筛选：每条右侧操作区 */
.mw-atom-r{ display:flex; align-items:center; gap:18px; margin-left:auto; }
.mw-act{
  border:none !important; background:none !important; border-radius:0 !important;
  padding:1px 0 !important; font-size:12px !important; line-height:1.6 !important;
  color:var(--mw-ink-3) !important; border-bottom:1px solid transparent !important;
  cursor:pointer; white-space:nowrap;
}
.mw-act:hover{ color:var(--mw-err) !important; border-bottom-color:currentColor !important; }
.mw-act.dim:hover{ color:var(--mw-gold) !important; }
.mw-act.undo:hover{ color:var(--mw-gold) !important; }
.mw-act:disabled{ opacity:.4 !important; cursor:default; }
.mw-atom.dropped{ opacity:.45; }
.mw-atom.dropped .mw-atom-k{ text-decoration:line-through; text-decoration-thickness:1px; }
.mw-atom.fuzzy{ border-left:2px solid var(--mw-gold) !important; padding-left:14px !important; }
.mw-atom-flag{
  font-size:10px !important; letter-spacing:.6px; color:var(--mw-gold) !important;
  border:1px solid color-mix(in srgb, var(--mw-gold) 45%, transparent) !important;
  border-radius:3px !important; padding:1px 5px !important;
}
.mw-search{
  width:100%; box-sizing:border-box; margin:0 0 14px 0;
  background:none !important; border:none !important;
  border-bottom:1px solid var(--mw-hair) !important; border-radius:0 !important;
  padding:8px 0 !important; font-size:14px !important; color:var(--mw-ink) !important;
  outline:none;
}
.mw-search::placeholder{ color:var(--mw-ink-3); }
.mw-search:focus{ border-bottom-color:var(--mw-gold) !important; }
.mw-more{
  display:block; margin:22px auto 0; border:none !important; background:none !important;
  font-size:13px !important; color:var(--mw-gold) !important; padding:6px 0 !important;
  border-bottom:1px solid transparent !important; cursor:pointer;
}
.mw-more:hover{ border-bottom-color:var(--mw-gold) !important; }
.mw-rows{ display:flex; flex-wrap:wrap; gap:0 18px; margin-bottom:4px; }

/* 打通：原子 ↔ 原文稿 */
.mw-src{
  margin-top:12px; padding:14px 16px;
  border-left:2px solid var(--mw-gold);
  background: color-mix(in srgb, var(--mw-gold) 5%, transparent);
}
.mw-src-h{ font-size:11.5px !important; letter-spacing:.4px; color:var(--mw-ink-3) !important; margin-bottom:8px; }
.mw-src-b{ font-size:14px !important; line-height:1.9 !important; color:var(--mw-ink-2) !important; white-space:pre-wrap; }
.mw-src-atom{ font-size:13.5px !important; line-height:1.8 !important; padding:6px 0; border-top:1px solid var(--mw-hair-2); }
.mw-src-atom:first-of-type{ border-top:none; }

/* ---- GitHub 热榜：五张榜 + 逐条判断 ---- */
.mw-gt-kpis{ display:flex; gap:12px; flex-wrap:wrap; margin-bottom:14px; }
.mw-gt-kpi{
  flex:1 1 0; min-width:130px; border:1px solid var(--dsw-alias-border-l1);
  border-radius:6px; padding:12px 14px; background:var(--dsw-alias-bg-layer-1);
}
.mw-gt-kpi-n{
  font-size:30px; font-weight:700; line-height:1.15; letter-spacing:-.5px;
  color:var(--dsw-alias-label-primary); font-variant-numeric:tabular-nums;
}
.mw-gt-kpi-n.is-accent{ color:var(--mw-gold); }
.mw-gt-kpi-s{ font-size:12.5px; color:var(--dsw-alias-label-secondary); margin-top:2px; }
.mw-gt-tip{ font-size:12.5px; line-height:1.7; color:var(--dsw-alias-label-secondary); margin:0 0 14px; }
.mw-gt-toast{
  font-size:12.5px; line-height:1.6; padding:9px 12px; border-radius:6px;
  margin-bottom:12px; border:1px solid var(--dsw-alias-border-l1);
}
.mw-gt-toast.is-ok{
  color:var(--dsw-alias-label-primary);
  border-color:color-mix(in srgb, var(--mw-gold) 48%, var(--dsw-alias-border-l1));
  background:color-mix(in srgb, var(--mw-gold) 10%, transparent);
}
.mw-gt-toast.is-err{ color:var(--dsw-alias-state-error-primary); border-color:color-mix(in srgb, var(--dsw-alias-state-error-primary) 45%, var(--dsw-alias-border-l1)); }
.mw-gt-toast.is-mute{ color:var(--dsw-alias-label-secondary); opacity:.9; }

.mw-gt-sec{
  margin-bottom:12px; border:1px solid var(--dsw-alias-border-l1); border-radius:8px;
  overflow:hidden; background:color-mix(in srgb, var(--dsw-alias-bg-layer-1) 62%, transparent);
}
.mw-gt-head{
  appearance:none; width:100%; display:flex; align-items:center; gap:10px;
  padding:13px 14px; background:none; border:none; cursor:pointer; font-family:inherit;
  text-align:left; color:var(--dsw-alias-label-primary);
}
.mw-gt-head:hover{ background:color-mix(in srgb, var(--mw-gold) 5%, transparent); }
.mw-gt-head.is-open{ border-bottom:1px solid var(--dsw-alias-border-l1); }
.mw-gt-chev{ width:14px; color:var(--mw-gold); font-size:12px; flex:none; }
.mw-gt-title{ font-size:17px; font-weight:600; letter-spacing:.3px; flex:none; }
.mw-gt-badge{
  font-size:12px; color:var(--dsw-alias-label-secondary);
  border:1px solid var(--dsw-alias-border-l2); border-radius:99px; padding:1px 8px; flex:none;
}
.mw-gt-sum{ font-size:12.5px; color:var(--mw-gold); font-variant-numeric:tabular-nums; flex:none; }
.mw-gt-sub{ font-size:12.5px; color:var(--dsw-alias-label-secondary); opacity:.8; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.mw-gt-more{ margin-left:auto; font-size:12px; color:var(--dsw-alias-label-secondary); flex:none; }
.mw-gt-head:hover .mw-gt-more{ color:var(--mw-gold); }
.mw-gt-row{
  display:grid; grid-template-columns:26px minmax(0,1fr) auto auto auto; gap:12px;
  align-items:center; padding:11px 14px; border-bottom:1px solid var(--dsw-alias-border-l1);
}
.mw-gt-row:last-child{ border-bottom:none; }
.mw-gt-row:hover{ background:color-mix(in srgb, var(--dsw-alias-label-primary) 2.5%, transparent); }
.mw-gt-rank{ font-size:12.5px; text-align:right; color:var(--dsw-alias-label-secondary); font-variant-numeric:tabular-nums; }
.mw-gt-main{ min-width:0; }
.mw-gt-repo{ font-size:15px; font-weight:600; line-height:1.4; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.mw-gt-owner{ color:var(--dsw-alias-label-secondary); font-weight:400; }
.mw-gt-what{ font-size:13px; line-height:1.65; margin-top:3px; color:var(--dsw-alias-label-primary); }
.mw-gt-what b,
.mw-gt-use b{ font-size:12px; font-weight:600; letter-spacing:.5px; color:var(--mw-gold); margin-right:7px; }
.mw-gt-use{ font-size:12.5px; line-height:1.6; margin-top:1px; color:var(--dsw-alias-label-secondary); }
.mw-gt-what.dim{ color:var(--dsw-alias-label-secondary); opacity:.75; }
.mw-gt-run{ color:var(--mw-gold); }
.mw-gt-tags{ display:flex; gap:6px; }
.mw-gt-lang{
  font-size:12px; color:var(--dsw-alias-label-secondary);
  border:1px solid var(--dsw-alias-border-l2); border-radius:4px; padding:1px 7px; white-space:nowrap;
}
.mw-gt-num{ text-align:right; font-variant-numeric:tabular-nums; min-width:72px; }
.mw-gt-gain{ font-size:14px; font-weight:650; color:var(--mw-gold); }
.mw-gt-stars{ font-size:12px; color:var(--dsw-alias-label-secondary); }
.mw-gt-act{ display:flex; gap:8px; justify-content:flex-end; }
.mw-gt-yes,.mw-gt-no{
  appearance:none; cursor:pointer; font-family:inherit; font-size:12.5px; padding:5px 12px;
  border-radius:6px; border:1px solid var(--dsw-alias-border-l1);
  background:var(--dsw-alias-bg-layer-2); color:var(--dsw-alias-label-primary);
  transition:background-color .18s ease, border-color .18s ease, color .18s ease;
}
.mw-gt-yes{
  border-color:color-mix(in srgb, var(--mw-gold) 55%, var(--dsw-alias-border-l1));
  color:var(--mw-gold); font-weight:600;
}
.mw-gt-yes:hover{ background:color-mix(in srgb, var(--mw-gold) 16%, transparent); border-color:var(--mw-gold); }
.mw-gt-no:hover{ background:color-mix(in srgb, var(--dsw-alias-label-primary) 6%, transparent); }
.mw-gt-yes:disabled,.mw-gt-no:disabled{ opacity:.45; cursor:default; }
.mw-gt-empty{ padding:20px 14px; font-size:12.5px; color:var(--dsw-alias-label-secondary); text-align:center; }
.mw-gt-skip{
  padding:9px 14px; font-size:12px; line-height:1.7;
  color:var(--dsw-alias-label-secondary); opacity:.8;
  border-top:1px dashed color-mix(in srgb, var(--dsw-alias-border-l2) 90%, transparent);
}
.mw-gt-foot{ font-size:12px; line-height:1.7; color:var(--dsw-alias-label-secondary); margin-top:16px; opacity:.9; }

`

    /* ---------------------------------------------------------------- 图标（仅工作台入口用） */
    const HubIcon = (props) => {
      const size = (props && props.size) || 18
      return h('svg', {
        width: size, height: size, viewBox: '0 0 24 24', fill: 'none',
        stroke: 'currentColor', strokeWidth: 1.15, strokeLinecap: 'round',
        'aria-hidden': true, style: { display: 'block' },
      },
      h('path', { d: 'M3.5 8.5h17' }),
      h('path', { d: 'M3.5 15.5h17' }),
      h('circle', { cx: 8, cy: 8.5, r: 1.7, fill: 'currentColor', stroke: 'none' }),
      h('circle', { cx: 15.5, cy: 15.5, r: 1.7, fill: 'currentColor', stroke: 'none', opacity: 0.5 }),
      )
    }

    /* ---------------------------------------------------------------- 数据 */
    const GROUPS = [
      { key: 'morning', label: '早上', note: '先看一眼外面' },
      { key: 'work', label: '内容生产', note: '采集 → 入库 → 选题 → 产出' },
      { key: 'persona', label: '顾问团', note: '八位顾问，各看各的角度' },
      { key: 'night', label: '收尾', note: '回看这一轮' },
    ]

    const CARDS = [
      {
        id: 'hot', group: 'morning', title: '今日热点', wide: true,
        desc: '各平台知识区正在热的东西', tag: '外网',
        stat: '— 今日未抓取',
        detail: '点按钮抓一次。抓不到就明确说「没抓到」，不做定时自动假装在线。\n\n热点接口天天变、抖音热榜有签名墙，这是全台最容易坏的一块，所以宁可诚实失败。',
      },
      {
        id: 'inspire', group: 'morning', title: '每日灵感', wide: true,
        desc: '从你的库里翻出今天能拍的 3 条', tag: '内部重组',
        stat: '库空 · 先去采集',
        detail: '不连外网，只读自己的稿库和观点库，按当天方向重新组合出 3 条建议。\n\n和「今日热点」正好配成一对：一个喂外部输入，一个吐内部组合。',
      },
      {
        id: 'speech', group: 'grow', title: '表达训练',
        desc: '脱稿说话，实时看见自己的口癖（填充词/犹豫词/笼统词）', tag: '可用',
        stat: '边说边出字',
        detail: '随机给 6 个词 → 你脱稿即兴讲 → 边说边出字 → 讲完打分。\n\n机械指标（语速、填充词、用词覆盖）本地算；内容分（结构、逻辑、像不像在跟人说话）由 AI 评。',
      },
      {
        id: 'topic', group: 'grow', title: '话题即兴',
        desc: '给一个观点，60 秒讲清你的看法', tag: '待做',
        stat: '等接上',
        detail: '给一个话题或观点，限时 60 秒说清立场和理由。',
      },
      {
        id: 'retell', group: 'grow', title: '限时复述',
        desc: '看材料 30 秒，合上复述要点', tag: '待做',
        stat: '等接上',
        detail: '显示一段材料 30 秒后隐藏，让你复述，AI 比对关键点覆盖率。',
      },
      {
        id: 'debate', group: 'grow', title: '反方辩论',
        desc: '给一个立场，你必须推翻它', tag: '待做',
        stat: '等接上',
        detail: '随机给你一个观点，你的任务是站反方把它推翻。',
      },
      {
        id: 'title', group: 'grow', title: '标题训练',
        desc: '给一篇稿，写 5 个标题', tag: '待做',
        stat: '等接上',
        detail: '从内容库挑一篇稿，让你写 5 个标题，AI 按点击欲和信息准确度打分。',
      },
      {
        id: 'summary', group: 'grow', title: '摘要压缩',
        desc: '2000 字压成 100 字', tag: '待做',
        stat: '等接上',
        detail: '给你一篇长稿，压缩成 100 字以内，比对要点保留率。',
      },
      {
        id: 'question', group: 'grow', title: '提问训练',
        desc: '给话题，列 10 个问题', tag: '待做',
        stat: '等接上',
        detail: '给一个话题，让你列 10 个问题，AI 判断哪些是真问题。',
      },
      {
        id: 'analogy', group: 'grow', title: '类比训练',
        desc: '把复杂概念讲给外行听', tag: '待做',
        stat: '等接上',
        detail: '给一个专业概念，要求你用生活化类比讲明白。',
      },
      {
        id: 'fit', group: 'body', title: '每日训练',
        desc: '在家练什么、每个动作怎么做、打勾', tag: '可用',
        stat: '每周 3 练 + 2 休息',
        detail: '按周一到周日排好，今天该练什么直接显示。每个动作点开有「怎么做 / 别这么做 / 做不动怎么办」三段教程。',
      },
      {
        id: 'med', group: 'body', title: '睡前冥想',
        desc: '跟着提示呼吸，脑子安静下来', tag: '可用',
        stat: '四档 · 3/5/10/15 分钟',
        detail: '呼吸 5 分钟、身体扫描 10 分钟、睡前 15 分钟、专注 3 分钟。有引导语、呼吸圆圈和提示音。',
      },
      {
        id: 'books', group: 'media', title: '书库',
        desc: '801 本书卡，按精读/翻翻筛', tag: '可用',
        stat: '精读 / 翻翻 / 跳过',
        detail: '每本书一张卡：核心讲什么、5-10 条洞察、适合谁、值不值得精读。',
      },
      {
        id: 'personas', group: 'persona', title: '分身',
        desc: '一群顾问，知识来自你的库', tag: '角色',
        stat: '8 个角色 · 一一对应八大类素材',
        detail: '每个分身有自己的关注点、判断框架和腔调，但知识都来自同一个内容库。\n\n点进去可以单聊；想知道同一件事别人怎么看，用「圆桌会议」。',
      },
      {
        id: 'roundtable', group: 'persona', title: '圆桌会议',
        desc: '一次提问，多个分身同时表态', tag: '群聊',
        stat: '允许互相冲突',
        detail: '写一个议题，几个顾问同时发言。价值不在于他们都说对，而在于他们互相反驳——商业顾问说该做，心理医生说你在逃避。',
      },
      {
        id: 'capture', group: 'work', title: '采集台',
        desc: '入口：粘链接转写、盯直播录制、路径设置', tag: '入口',
        stat: '0 条排队',
        detail: '两个标签页：\n\n· 手动甩链接——复制抖音链接，自动排队下载音频、转写逐字稿\n· 关注名单——每天 8:00 巡检一次，有新稿自动抓\n\n巡检坏了会亮红灯：@某某 连续 5 次失败、原因是什么。绝不静默漏抓。',
      },
      {
        id: 'library', group: 'work', title: '稿库',
        desc: '原文仓库：推文、口播稿、直播、书 · 全部已分类', tag: '仓库 / 核心',
        stat: '1462 篇',
        detail: '按来源分四类：\n\n· 推文 1247 篇——他的主贴原文\n· 抖音 144 条——口播稿\n· 直播 297 段——按主播分段\n· 书 931 本——全部已去重、已分类\n\n全部内容都过了同一套三层分类（8 大类 / 72 子类 / 主题标签），每条的标签都能点开筛选。\n点标题就地展开全文。',
      },
      {
        id: 'topics', group: 'work', title: '选题池',
        desc: '攒选题，标状态推进', tag: '想法 / 在写 / 已发',
        stat: '0 条',
        detail: '每条选题带状态：想法 → 在写 → 已发。\n可以从稿库的某一条原文生成，从「对撞台」的空白生成，也可以自己手写一条。',
      },
      {
        id: 'pool', group: 'work', title: '观点库',
        desc: '别人怎么看这件事 · 认同/不认同，表个态', tag: '别人的',
        stat: '9594 条',
        detail: '这里放的全是别人的观点，从稿库、直播里提炼出来的，一条一句。\n\n不分分类、不打标签，就是一条平铺的流，看到哪算哪。认同和不认同两个按钮，点了会让你写一句为什么。\n\n表过态的就不再出现。写下的理由进「我的观点」。',
      },
      {
        id: 'self', group: 'work', title: '我的观点',
        desc: '自己写的 + 观点库表态来的 · 展开能匹配稿库', tag: '你的立场',
        stat: '0 条观点',
        detail: '三条路进来：① 从选题池点「我来写」自己写；② 在观点库对别人的观点表态（认同/不认同）并写下理由；③ 直接「有感而发」记一句（原「我的灵感」已并入这里）。\n\n写的时候就是你自己写，写完整段交上去；AI 只告诉你：哪里立得住、哪里是空话、缺什么证据、哪个问句能把人问住。它不会替你改一个字。\n\n展开一条，会自动去稿库里找相关的原文——你写「干中学」，它把稿库里讲过这事的段落摆出来。',
      },
      {
        id: 'corpus', group: 'work', title: '我的语料库',
        desc: '我写过的话 · 只出不进，永不进稿库', tag: '私有',
        stat: '0 条',
        detail: '这里放的是你自己写下的观点，原文一字不动。\n\n它和稿库是两套表、两套数据：不进稿库、不被当素材拆解、不参与任何分类。\n\n用处：以后写稿要引"我说过什么"，从这里取；也能搜、能导出 md，数据在你手上。',
      },
      {
        id: 'review', group: 'night', title: '发布复盘', full: true,
        desc: '发了什么、数据如何、下次改哪', tag: '本月',
        stat: '本月 0 条 · 最近一次：无',
        stats: [['本月已发', '0'], ['平均完播', '—'], ['最该复盘', '无']],
        detail: '记录发出去的内容、平台数据、你自己的判断。\n下次开写之前回来看一眼，比空想有用。',
      },
    ]

    /* 能力提升那 8 张（group='grow'）不属于自媒体台的板块（GROUPS 里没有 grow），
       但它们是独立工作台「能力提升台」(GrowLab) 的数据源，不能删。
       这里单独索引出来给它用；自媒体台遍历 GROUPS 时看不到它们。 */
    const GROW_CARDS = CARDS.filter((c) => c.group === 'grow')
    const BODY_CARDS = CARDS.filter((c) => c.group === 'body')

    /* ---------------------------------------------------------------- 组件 */
    function Header() {
      const now = new Date()
      const week = ['日', '一', '二', '三', '四', '五', '六'][now.getDay()]
      return h('div', { className: 'mw-head' },
        h('div', { className: 'mw-mark' }),
        h('div', null,
          h('div', { className: 'mw-title' }, '自媒体工作台'),
          h('div', { className: 'mw-sub' }, '采集 · 拆解 · 选题 · 对撞 · 复盘'),
        ),
        h('div', { style: { flex: '1 1 auto' } }),
        h(ModelPicker, null),
        h('div', { className: 'mw-date' },
          h('span', { className: 'mw-dot' }),
          h('span', null, `${now.getMonth() + 1}月${now.getDate()}日 周${week}`),
        ),
      )
    }

    const TYPE_CN = { principle: '原则', method: '方法', insight: '洞察', 'anti-pattern': '反模式', case: '案例', tool: '工具', other: '其他' }
    const CONF_CN = { high: '高可信', medium: '中可信', low: '低可信' }
    const KIND_CN = { douyin: '抖音', live: '直播', x: '推特', bilibili: '哔哩哔哩', youtube: '油管', xiaohongshu: '小红书', book: '书籍' }
    const typeCn = (t) => TYPE_CN[t] || '其他'
    const confCn = (c) => CONF_CN[c] || ''
    const kindCn = (k) => KIND_CN[k] || (k || '')

    function Card({ card, idx, onOpen, statOverride }) {
      return h('button', {
        type: 'button',
        className: 'mw-card' + (card.accent ? ' is-accent' : ''),
        onClick: () => onOpen(card),
        style: {
          gridColumn: 'span 2',
          animationDelay: `${Math.min(idx * 34, 340)}ms`,
        },
      },
      h('div', { className: 'mw-idx' }, String(idx + 1).padStart(2, '0')),
      h('div', { className: 'mw-ctitle' }, card.title),
      h('div', { className: 'mw-cdesc' }, card.desc),
      // 满宽/大卡右侧的碎信息，避免大片留白
      card.stats
        ? h('div', {
          style: {
            position: 'absolute', right: 24, top: 0, bottom: 0,
            display: 'flex', alignItems: 'center', gap: 30,
          },
        },
        card.stats.map(([k, v]) =>
          h('div', { key: k, style: { display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 3 } },
            h('div', { style: { fontSize: card.full ? 16 : 13, fontWeight: 600, letterSpacing: .3, fontVariantNumeric: 'tabular-nums' } }, v),
            h('div', { style: { fontSize: 8.5, letterSpacing: .9, opacity: .45 } }, k),
          )),
        )
        : null,
      h('div', { className: 'mw-cfoot' },
        h('span', { className: 'mw-cbar' }),
        h('span', { className: 'mw-cstat' }, statOverride || card.stat),
      ),
      )
    }

    /* 自动任务的一句话状态。短提示用在面板顶部，长句含重试时间 */
    function autoLong(job, label) {
      if (!job) return ''
      const at = (ts) => new Date(ts).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
      if (job.running) return `${label}正在后台跑，跑完自动上屏`
      if (job.error) return `${label}${job.error}${job.nextAt ? '（' + at(job.nextAt) + ' 重试）' : ''}`
      if (job.at) return `${label}自动更新于 ${at(job.at)}`
      return ''
    }

    function CardWall({ onOpen, hot, summary, idea, autoSt, poolStat }) {
      let n = 0
      const [liveNow, setLiveNow] = useState(null)
      useEffect(() => {
        const load = () => fetch('/api/dsh-media/live/rec')
          .then((r) => r.text())
          .then((t) => { try { return JSON.parse(t) } catch { return null } })
          .then((j) => { if (j && j.ok) setLiveNow(j) })
          .catch(() => { })
        load()
        const t = setInterval(load, 5000)
        return () => clearInterval(t)
      }, [])
      const hd = hot && hot.data
      const hs = autoSt && autoSt.hot ? autoSt.hot : null
      const isSt = autoSt && autoSt.idea ? autoSt.idea : null
      const hotStat = hd
        ? `${hd.date} · HN ${(hd.hn || []).length} / X ${Object.values(hd.groups || {}).reduce((a, b) => a + b.length, 0)}` + (hs && hs.today ? '' : '（非今日）')
        : (hs && hs.running ? '正在抓取 · 稍后自动上屏' : '— 今日未抓取')
      const sum = summary && summary.ok ? summary : null
      const ida = idea && idea.data
      const ideaStat = ida
        ? `${ida.date} · ${(ida.items || []).length} 条灵感` + (isSt && isSt.today ? '' : '（非今日）')
        : (isSt && isSt.running ? '正在生成 · 稍后自动上屏' : '— 今日未生成')
      const statFor = (id, fallback) => {
        if (id === 'hot') return hotStat
        if (id === 'inspire') return ideaStat
        if (id === 'capture') {
          if (!liveNow) return fallback
          const act = liveNow.rec.active.length
          if (act) return '正在录 ' + act + ' 个 · 待转写 ' + liveNow.queue.pending
          return '未在录 · 待转写 ' + liveNow.queue.pending
        }
        if (id === 'topics') {
          if (!poolStat) return fallback
          return `今天 ${poolStat.today || 0} 条 · 共 ${poolStat.pool_topics || 0} 条`
        }
        if (id === 'self' || id === 'corpus') {
          if (!poolStat) return fallback
          return `${poolStat.my_views || 0} 条` + (id === 'corpus' ? ' · 私有' : '观点')
        }
        if (!sum) return fallback
        if (id === 'library') return `${Number(sum.posts).toLocaleString('en-US')} 篇`
        return fallback
      }
      return h('div', { className: 'mw-root' },
        h('style', { key: 'mw-css' }, CSS),
        h(Header, null),
        h('div', { className: 'mw-body' },
          GROUPS.map((g) => {
            const items = CARDS.filter((x) => x.group === g.key)
            if (!items.length) return null
            return h('div', { key: g.key, className: 'mw-group' },
              h('div', { className: 'mw-ghead' },
                h('span', { className: 'mw-glabel' }, g.label),
                g.note ? h('span', { className: 'mw-gnote' }, g.note) : null,
                h('span', { className: 'mw-gline' }),
                h('span', { className: 'mw-gnum' }, String(items.length).padStart(2, '0')),
              ),
              h('div', { className: 'mw-grid' },
                items.map((c) => {
                  const i = n++
                  return h(Card, {
                    key: c.id, card: c, idx: i, onOpen,
                    statOverride: statFor(c.id, null),
                  })
                }),
              ),
            )
          }),
        ),
      )
    }

    function HotPanel({ onBack, hot, onRefresh, refreshing, err, autoSt }) {
      const data = hot && hot.data
      const groupTitles = { AI: 'AI 圈在聊什么', '商业': '商业与创业', '财经': '财经与宏观' }
      const job = autoSt && autoSt.hot ? autoSt.hot : null
      const autoLine = autoLong(job, '热点')
      const tone = job && job.error ? C.warn : C.sub

      const body = []
      if (!data) {
        body.push(h('div', { key: 'empty', className: 'mw-empty' },
          job && job.running
            ? '今天的热点还在抓，跑完会自动出现在这里（大约 2-3 分钟）。'
            : '今天的热点还没生成。后台会自动抓，也可以点右上角「重新抓取」。' + (autoLine ? ' ' + autoLine : '')))
      } else {
        body.push(h('div', { key: 'head', className: 'mw-hot-head' },
          h('span', { className: 'mw-hot-meta' },
            `${data.date} · 生成于 ${(data.generated_at || '').slice(11, 16)} · HN ${data.hn ? data.hn.length : 0} 条 / X ${Object.values(data.groups || {}).reduce((a, b) => a + b.length, 0)} 条`),
          hot && !hot.isToday ? h('span', { className: 'mw-hot-meta', style: { color: C.warn } }, '（非今日数据）') : null,
          autoLine ? h('span', { className: 'mw-hot-meta', style: { color: tone } }, '· ' + autoLine) : null,
        ))

        // HN
        body.push(h('div', { key: 'hn', className: 'mw-hot-group' },
          h('div', { className: 'mw-hot-gt' },
            h('span', { className: 'mw-hot-gt-label' }, '全球科技前沿'),
            h('span', { className: 'mw-hot-gt-line' }),
            h('span', { className: 'mw-hot-gt-label' }, 'HACKER NEWS'),
          ),
          (data.hn || []).map((x, i) => h('div', { key: 'hn' + i, className: 'mw-hot-item' },
            h('div', { className: 'mw-hot-title' }, x.title_zh || x.title),
            x.insight_zh ? h('div', { className: 'mw-insight' },
              h('span', { className: 'mw-insight-tag' }, 'AI 说 · '), x.insight_zh) : null,
            h('div', { className: 'mw-hot-foot' },
              h('span', null, `[${x.score} 分]`),
              h('span', null, x.time),
              h('a', { href: x.url, target: '_blank', rel: 'noreferrer' }, '原文'),
            ),
          )),
        ))

        // X 三组
        Object.keys(groupTitles).forEach((g) => {
          const items = (data.groups || {})[g] || []
          body.push(h('div', { key: 'g' + g, className: 'mw-hot-group' },
            h('div', { className: 'mw-hot-gt' },
              h('span', { className: 'mw-hot-gt-label' }, groupTitles[g]),
              h('span', { className: 'mw-hot-gt-line' }),
              h('span', { className: 'mw-hot-gt-label' }, String(items.length)),
            ),
            items.length === 0
              ? h('div', { className: 'mw-empty' }, '这组今天没有筛出内容')
              : items.map((x, i) => h('div', { key: g + i, className: 'mw-hot-item' },
                h('div', { className: 'mw-hot-title' }, '@' + x.author),
                h('div', { className: 'mw-hot-body' }, x.text_zh || x.text),
                x.insight_zh ? h('div', { className: 'mw-insight' },
                  h('span', { className: 'mw-insight-tag' }, 'AI 说 · '), x.insight_zh) : null,
                h('div', { className: 'mw-hot-foot' },
                  h('span', null, `${x.likes} 赞`),
                  h('span', null, `${x.views} 浏览`),
                  h('span', null, x.time),
                  h('a', { href: x.url, target: '_blank', rel: 'noreferrer' }, '原推'),
                ),
              )),
          ))
        })
      }

      return h('div', { className: 'mw-root' },
        h('style', { key: 'mw-css' }, CSS),
        h('div', { className: 'mw-detail' },
          h('div', { className: 'mw-dhead' },
            h('button', { type: 'button', className: 'mw-back', onClick: onBack }, '‹ 工具列表'),
            h('div', { className: 'mw-dtitle' }, '今日热点'),
            data ? h('div', { className: 'mw-dtag' }, data.date) : null,
            h('div', { style: { flex: '1 1 auto' } }),
            h(ModelPicker, null),
            h('button', {
              type: 'button',
              className: 'mw-hot-btn',
              disabled: !!refreshing,
              onClick: onRefresh,
            }, refreshing ? '抓取中…' : '重新抓取'),
          ),
          h('div', { className: 'mw-dbody' },
            err ? h('div', { className: 'mw-err' }, err) : null,
            body,
          ),
        ),
      )
    }

    /* ---- 文案拆解：六个板块（钩子/干货/案例/金句/避坑/问答） ---- */
    const SPLIT_BOARDS = [
      ['hook', '钩子', '开头第一句'],
      ['dry', '干货', '道理、步骤'],
      ['case', '案例', '证明用的经历'],
      ['quote', '金句', '能截图的一句'],
      ['avoid', '避坑', '别做什么'],
      ['qa', '问答', '他答别人问'],
    ]

    function SplitPanel({ onBack }) {
      const [board, setBoard] = useState('hook')
      const [style, setStyle] = useState(null)
      const [kw, setKw] = useState('')
      const [q, setQ] = useState('')
      const [list, setList] = useState([])
      const [total, setTotal] = useState(0)
      const [styles, setStyles] = useState([])
      const [loading, setLoading] = useState(true)
      const [more, setMore] = useState(false)
      const [openPost, setOpenPost] = useState(null)
      const PAGE = 80

      const buildUrl = (off) => {
        const p = ['limit=' + PAGE, 'offset=' + off]
        if (style) p.push('style=' + encodeURIComponent(style))
        if (q) p.push('q=' + encodeURIComponent(q))
        return '/api/dsh-media/hooks?' + p.join('&')
      }

      useEffect(() => {
        let alive = true
        setLoading(true)
        if (board !== 'hook') {
          const p = ['limit=' + PAGE, 'offset=0', 'board=' + encodeURIComponent(board)]
          if (q) p.push('q=' + encodeURIComponent(q))
          fetch('/api/dsh-media/split?' + p.join('&'))
            .then((r) => r.json())
            .then((j) => {
              if (!alive) return
              if (j && j.ok) {
                setList(j.list || [])
                setTotal(j.total || 0)
                if (j.boards && j.boards.length) setStyles(j.boards)
              }
              setLoading(false)
            })
            .catch(() => { if (alive) setLoading(false) })
          return () => { alive = false }
        }
        fetch(buildUrl(0))
          .then((r) => r.json())
          .then((j) => {
            if (!alive) return
            if (j && j.ok) {
              setList(j.list || [])
              setTotal(j.total || 0)
              if (j.styles && j.styles.length) setStyles(j.styles)
            }
            setLoading(false)
          })
          .catch(() => { if (alive) setLoading(false) })
        return () => { alive = false }
      }, [style, q, board])

      useEffect(() => {
        const t = setTimeout(() => setQ(kw.trim()), 400)
        return () => clearTimeout(t)
      }, [kw])

      const loadMore = () => {
        if (more) return
        setMore(true)
        const p = ['limit=' + PAGE, 'offset=' + list.length]
        if (board !== 'hook') {
          p.push('board=' + encodeURIComponent(board))
          if (q) p.push('q=' + encodeURIComponent(q))
          fetch('/api/dsh-media/split?' + p.join('&'))
            .then((r) => r.json())
            .then((j) => { if (j && j.ok) setList((x) => x.concat(j.list || [])) })
            .catch(() => { })
            .then(() => setMore(false))
          return
        }
        fetch(buildUrl(list.length))
          .then((r) => r.json())
          .then((j) => { if (j && j.ok) setList((x) => x.concat(j.list || [])) })
          .catch(() => { })
          .then(() => setMore(false))
      }

      const loadPost = (pid) => {
        if (!pid) return
        if (openPost && openPost.id === pid) { setOpenPost(null); return }
        fetch('/api/dsh-media/post?id=' + encodeURIComponent(pid))
          .then((r) => r.json())
          .then((j) => { if (j && j.ok) setOpenPost({ id: pid, text: j.text || '', date: j.date || '', kind: j.kind || '' }) })
          .catch(() => { })
      }

      // 拆解条目 → 原文出处（书查 book_chunks、口播查 posts，两条路都走通）
      const loadSource = (sid) => {
        if (!sid) return
        if (openPost && openPost.sid === sid) { setOpenPost(null); return }
        fetch('/api/dsh-media/source?id=' + encodeURIComponent(sid))
          .then((r) => r.json())
          .then((j) => {
            if (j && j.ok) {
              setOpenPost({
                sid, kind: j.kind, title: j.title || '', date: j.date || '',
                text: j.text || '', quote: j.quote || '', hint: j.hint || '',
              })
            } else {
              setOpenPost({ sid, kind: 'unknown', title: '', date: '', text: '', hint: (j && j.error) || '读不到原文' })
            }
          })
          .catch(() => setOpenPost({ sid, kind: 'unknown', title: '', date: '', text: '', hint: '请求失败，宿主可能没重启' }))
      }

      const all = styles.reduce((a, b) => a + b.n, 0)

      return h('div', { className: 'mw-root' },
        h('style', { key: 'mw-css' }, CSS),
        h('div', { className: 'mw-detail' },
          h('div', { className: 'mw-dhead' },
            h('button', { type: 'button', className: 'mw-back', onClick: onBack }, '‹ 工具列表'),
            h('div', { className: 'mw-dtitle' }, '文案拆解'),
            h('div', { className: 'mw-dtag' }, (() => {
              const cur = SPLIT_BOARDS.find((b) => b[0] === board)
              const label = cur ? cur[1] : '钩子'
              const n = board === 'hook' ? all : total
              if (!n) return label + ' · 待拆'
              return Number(n).toLocaleString('en-US') + ' 条' + label
            })()),
          ),
          h('div', { className: 'mw-dbody' },
            h('div', { className: 'mw-chips mw-rows', style: { marginBottom: 18 } },
              SPLIT_BOARDS.map(([k, label, note]) => h('button', {
                key: k,
                type: 'button',
                className: 'mw-chip' + (board === k ? ' on' : ''),
                onClick: () => setBoard(k),
                title: note,
              }, label)),
            ),
            h('input', {
              key: 'kw',
              className: 'mw-search', value: kw,
              placeholder: board === 'hook' ? '搜钩子，边打边筛' : '搜这一块里的句子',
              onChange: (e) => setKw(e.target.value),
            }),
            board !== 'hook'
              ? (loading
                ? h('div', { key: 'ld2', className: 'mw-empty' }, '读取中…')
                : list.length
                  ? [
                    h('div', { key: 'meta2', className: 'mw-empty', style: { marginBottom: 6 } },
                      `共 ${Number(total).toLocaleString('en-US')} 条`),
                    list.map((x, i) => h('div', { key: (x.id || i) + '_b' + i, className: 'mw-atom' },
                      h('div', { className: 'mw-atom-top' },
                        h('span', { className: 'mw-atom-type t-other' }, (SPLIT_BOARDS.find((b) => b[0] === x.board) || [])[1] || x.board),
                        h('span', { className: 'mw-atom-date' }, x.date || ''),
                        x.source === 'douyin' ? h('span', { className: 'mw-atom-conf' }, '口播') : null,
                        x.note ? h('span', { className: 'mw-atom-date', style: { marginLeft: 'auto', opacity: .5 } }, x.note) : null,
                      ),
                      h('div', { className: 'mw-atom-k', style: { whiteSpace: 'pre-wrap' } }, x.text || ''),
                      h('div', { className: 'mw-atom-foot' },
                        h('button', {
                          type: 'button', className: 'mw-act dim', style: { fontSize: 12 },
                          onClick: () => loadSource(x.id),
                        }, (openPost && openPost.sid === x.id) ? '收起原文 ⌃' : '看原文 ›'),
                      ),
                      (openPost && openPost.sid === x.id)
                        ? h('div', { className: 'mw-src' },
                          h('div', { className: 'mw-src-h' },
                            (openPost.title ? '《' + openPost.title + '》' : '')
                            + (openPost.date ? ' ' + openPost.date : '')
                            + (openPost.text ? ' · 原文 ' + openPost.text.length + ' 字' : '')),
                          h('div', { className: 'mw-src-b' },
                            openPost.text || openPost.hint || '没有原文'))
                        : null,
                    )),
                    list.length < total ? h('button', {
                      key: 'more2', type: 'button', className: 'mw-more', disabled: more,
                      onClick: loadMore,
                    }, more ? '加载中…' : `继续看（还剩 ${total - list.length} 条）`) : null,
                  ]
                  : h('div', { key: 'em2', className: 'mw-empty' }, q ? '没搜到，换个词' : '这一类空的'))
              : [
                h('div', { key: 'chips', className: 'mw-chips mw-rows' },
                  h('button', {
                    type: 'button', className: 'mw-chip' + (style === null ? ' on' : ''),
                    onClick: () => setStyle(null),
                  }, `全部 ${all}`),
                  styles.map((s) => h('button', {
                    key: s.name, type: 'button',
                    className: 'mw-chip' + (style === s.name ? ' on' : ''),
                    onClick: () => setStyle(s.name),
                  }, `${s.name === 'other' ? '其他' : s.name} ${s.n}`)),
                ),
                loading
                  ? h('div', { key: 'ld', className: 'mw-empty' }, '读取中…')
                  : list.length
                    ? [
                      h('div', { key: 'meta', className: 'mw-empty', style: { marginBottom: 6 } },
                        `共 ${Number(total).toLocaleString('en-US')} 条`),
                      list.map((x, i) => h('div', { key: (x.id || i) + '_' + i, className: 'mw-atom' },
                        h('div', { className: 'mw-atom-top' },
                          h('span', { className: 'mw-atom-type t-other' }, x.style === 'other' ? '其他' : (x.style || '未分')),
                          h('span', { className: 'mw-atom-date' }, x.date || ''),
                          x.source === 'douyin' ? h('span', { className: 'mw-atom-conf' }, '口播') : null,
                        ),
                        h('div', { className: 'mw-atom-k' }, x.text || ''),
                        h('div', { className: 'mw-atom-foot' },
                          h('button', {
                            type: 'button', className: 'mw-act dim', style: { fontSize: 12 },
                            onClick: () => loadPost(x.postId),
                          }, (openPost && openPost.id === x.postId) ? '收起原文 ⌃' : '看原文 ›'),
                        ),
                        (openPost && openPost.id === x.postId)
                          ? h('div', { className: 'mw-src' },
                            h('div', { className: 'mw-src-h' }, `${openPost.date || ''} ${kindCn(openPost.kind)} · 全文 ${(openPost.text || '').length} 字`),
                            h('div', { className: 'mw-src-b' }, openPost.text || ''))
                          : null,
                      )),
                      list.length < total ? h('button', {
                        key: 'more', type: 'button', className: 'mw-more', disabled: more,
                        onClick: loadMore,
                      }, more ? '加载中…' : `继续看（还剩 ${total - list.length} 条）`) : null,
                    ]
                    : h('div', { key: 'em', className: 'mw-empty' }, q ? '没搜到，换个词' : '这一类空的'),
              ],
          ),
        ),
      )
    }

    /* ---- 文案拆解：读库里的原子，逐条筛 ---- */
    function AtomPanel({ onBack, summary }) {
      const [view, setView] = useState('keep')   // keep / fuzz / trash / all
      const [type, setType] = useState(null)
      const [kw, setKw] = useState('')
      const [q, setQ] = useState('')
      const [list, setList] = useState([])
      const [total, setTotal] = useState(0)
      const [loading, setLoading] = useState(true)
      const [more, setMore] = useState(false)
      const [busy, setBusy] = useState({})
      const [openPost, setOpenPost] = useState(null)

      const loadPost = (pid) => {
        if (!pid) return
        if (openPost && openPost.id === pid) { setOpenPost(null); return }
        fetch('/api/dsh-media/post?id=' + encodeURIComponent(pid))
          .then((r) => r.json())
          .then((j) => {
            if (j && j.ok) setOpenPost({ id: pid, text: j.text || '', date: j.date || '', kind: j.kind || '' })
          })
          .catch(() => { })
      }
      const [cnt, setCnt] = useState({
        keep: (summary && summary.keepAtoms) || 0,
        fuzz: (summary && summary.fuzzAtoms) || 0,
        trash: (summary && summary.hiddenAtoms) || 0,
        all: (summary && summary.atoms) || 0,
      })
      const PAGE = 60

      const buildUrl = (off) => {
        const p = ['limit=' + PAGE, 'offset=' + off, 'view=' + view]
        if (type) p.push('type=' + encodeURIComponent(type))
        if (q) p.push('q=' + encodeURIComponent(q))
        return '/api/dsh-media/atoms?' + p.join('&')
      }

      useEffect(() => {
        let alive = true
        setLoading(true)
        fetch(buildUrl(0))
          .then((r) => r.json())
          .then((j) => {
            if (!alive) return
            if (j && j.ok) { setList(j.list || []); setTotal(j.total || 0) }
            else { setList([]); setTotal(0) }
            setLoading(false)
          })
          .catch(() => { if (alive) { setList([]); setTotal(0); setLoading(false) } })
        return () => { alive = false }
      }, [view, type, q])

      // 搜索防抖：停手 400ms 再查
      useEffect(() => {
        const t = setTimeout(() => setQ(kw.trim()), 400)
        return () => clearTimeout(t)
      }, [kw])

      const loadMore = () => {
        if (more) return
        setMore(true)
        fetch(buildUrl(list.length))
          .then((r) => r.json())
          .then((j) => { if (j && j.ok) setList((p) => p.concat(j.list || [])) })
          .catch(() => { })
          .then(() => setMore(false))
      }

      const act = async (a, kind) => {
        if (busy[a.id]) return
        setBusy((p) => ({ ...p, [a.id]: true }))
        const url = kind === 'hide' ? '/api/dsh-media/atoms/hide' : '/api/dsh-media/atoms/flag'
        const body = kind === 'hide'
          ? { id: a.id, hidden: a.hidden ? false : true }
          : { id: a.id, flag: a.flag === 'fuzz' ? '' : 'fuzz' }
        try {
          const r = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
          const j = await r.json()
          if (!j || !j.ok) { setBusy((p) => ({ ...p, [a.id]: false })); return }
        } catch {
          setBusy((p) => ({ ...p, [a.id]: false })); return
        }
        setBusy((p) => ({ ...p, [a.id]: false }))
        // 本地就地更新
        setList((prev) => prev.map((x) => {
          if (x.id !== a.id) return x
          if (kind === 'hide') return { ...x, hidden: a.hidden ? 0 : 1, flag: a.hidden ? (x.flag || '') : '' }
          return { ...x, flag: a.flag === 'fuzz' ? '' : 'fuzz' }
        }).filter((x) => {
          if (view === 'keep') return !x.hidden && x.flag !== 'fuzz'
          if (view === 'fuzz') return !x.hidden && x.flag === 'fuzz'
          if (view === 'trash') return !!x.hidden
          return true
        }))
        setCnt((p) => {
          const n = { ...p }
          if (kind === 'hide') {
            if (a.hidden) { n.trash = Math.max(0, n.trash - 1); n.keep += 1 }
            else { n.trash += 1; if (a.flag === 'fuzz') n.fuzz = Math.max(0, n.fuzz - 1); else n.keep = Math.max(0, n.keep - 1) }
          } else {
            if (a.flag === 'fuzz') { n.fuzz = Math.max(0, n.fuzz - 1); n.keep += 1 }
            else { n.fuzz += 1; n.keep = Math.max(0, n.keep - 1) }
          }
          return n
        })
        setTotal((t) => {
          if (kind === 'hide' && view === 'all' && !a.hidden) return Math.max(0, t - 1)
          if (kind === 'hide' && view === 'trash' && a.hidden) return Math.max(0, t - 1)
          return t
        })
      }

      const types = (summary && summary.atomTypes) || []
      const viewChips = [
        ['all', '全部', cnt.keep + cnt.fuzz],
        ['keep', '待筛', cnt.keep],
        ['fuzz', '待定', cnt.fuzz],
        ['trash', '已删', cnt.trash],
      ]

      return h('div', { className: 'mw-root' },
        h('style', { key: 'mw-css' }, CSS),
        h('div', { className: 'mw-detail' },
          h('div', { className: 'mw-dhead' },
            h('button', { type: 'button', className: 'mw-back', onClick: onBack }, '‹ 工具列表'),
            h('div', { className: 'mw-dtitle' }, '文案拆解'),
            h('div', { className: 'mw-dtag' }, `${Number(cnt.keep + cnt.fuzz).toLocaleString('en-US')} 条在场`),
          ),
          h('div', { className: 'mw-dbody' },
            h('input', {
              className: 'mw-search',
              value: kw,
              placeholder: '搜关键词，边打边筛',
              onChange: (e) => setKw(e.target.value),
            }),
            h('div', { className: 'mw-chips' },
              viewChips.map(([v, label, n]) => h('button', {
                key: v,
                type: 'button',
                className: 'mw-chip' + (view === v ? ' on' : ''),
                onClick: () => setView(v),
              }, `${label} ${n}`)),
            ),
            h('div', { className: 'mw-chips mw-rows' },
              h('button', {
                type: 'button',
                className: 'mw-chip' + (type === null ? ' on' : ''),
                onClick: () => setType(null),
              }, '全部类型'),
              types.map((t) => h('button', {
                key: t.type,
                type: 'button',
                className: 'mw-chip' + (type === t.type ? ' on' : ''),
                onClick: () => setType(t.type),
              }, `${typeCn(t.type)} ${t.n}`)),
            ),
            loading
              ? h('div', { className: 'mw-empty' }, '读取中…')
              : (list && list.length)
                ? [
                  h('div', { key: 'meta', className: 'mw-empty', style: { marginBottom: 6 } },
                    `共 ${Number(total).toLocaleString('en-US')} 条`),
                  list.map((a, i) => h('div', {
                    key: (a.id || i) + '_' + i,
                    className: 'mw-atom' + (a.hidden ? ' dropped' : '') + (a.flag === 'fuzz' ? ' fuzzy' : ''),
                  },
                    h('div', { className: 'mw-atom-top' },
                      h('span', { className: 'mw-atom-type t-' + (a.type || 'other') }, typeCn(a.type)),
                      h('span', { className: 'mw-atom-date' }, a.date || ''),
                      a.flag === 'fuzz' ? h('span', { className: 'mw-atom-flag' }, '待定') : null,
                      h('div', { className: 'mw-atom-r' },
                        a.hidden
                          ? h('button', {
                            type: 'button', className: 'mw-act undo', disabled: !!busy[a.id],
                            onClick: () => act(a, 'hide'),
                          }, '恢复')
                          : [
                            h('button', {
                              key: 'f', type: 'button', className: 'mw-act dim', disabled: !!busy[a.id],
                              onClick: () => act(a, 'flag'),
                            }, a.flag === 'fuzz' ? '取消待定' : '待定'),
                            h('button', {
                              key: 'd', type: 'button', className: 'mw-act', disabled: !!busy[a.id],
                              onClick: () => act(a, 'hide'),
                            }, '删掉'),
                          ],
                      ),
                    ),
                    h('div', { className: 'mw-atom-k' }, a.knowledge || a.original || ''),
                    (a.original && a.knowledge && a.original !== a.knowledge)
                      ? h('div', { className: 'mw-atom-o' }, a.original) : null,
                    h('div', { className: 'mw-atom-foot', style: { display: 'flex', gap: 16, flexWrap: 'wrap' } },
                      a.postId ? h('button', {
                        type: 'button', className: 'mw-act dim', style: { fontSize: 12 },
                        onClick: () => loadPost(a.postId),
                      }, (openPost && openPost.id === a.postId) ? '收起原文 ⌃' : '出自这篇稿 · 看原文 ›')
                        : h('span', { style: { opacity: .45 } }, '原稿不在库里'),
                      a.url ? h('a', { href: a.url, target: '_blank', rel: 'noreferrer' }, '推到 x ↗') : null,
                    ),
                    (openPost && openPost.id === a.postId && a.postId)
                      ? h('div', { className: 'mw-src' },
                        h('div', { className: 'mw-src-h' },
                          `${openPost.date || ''} ${kindCn(openPost.kind)} · 全文 ${openPost.text ? openPost.text.length : 0} 字`),
                        h('div', { className: 'mw-src-b' }, openPost.text || ''))
                      : null,
                  )),
                  list.length < total ? h('button', {
                    key: 'more', type: 'button', className: 'mw-more', disabled: more,
                    onClick: loadMore,
                  }, more ? '加载中…' : `再看看后面的（还剩 ${total - list.length} 条）`) : null,
                ]
                : h('div', { className: 'mw-empty' },
                  view === 'trash' ? '没有删除的' : (q ? '没搜到，换个词' : '这一类空了')),
          ),
        ),
      )
    }

    /* ---- 稿库：读库里 1544 篇稿 ---- */
    /* ---- 能力提升 · 脱稿口播训练 ---- */
    function SpeechPanel({ onBack, pending }) {
      const [words, setWords] = useState([])
      const [on, setOn] = useState(false)
      const [text, setText] = useState('')
      const [secs, setSecs] = useState(0)
      const [busy, setBusy] = useState(false)
      const [result, setResult] = useState(null)
      const [err, setErr] = useState(null)
      const [polished, setPolished] = useState('')
      const [polBusy, setPolBusy] = useState(false)
      const [savedTip, setSavedTip] = useState('')

      const acRef = useRef(null)
      const streamRef = useRef(null)
      const procRef = useRef(null)
      const pendRef = useRef([])
      const allRef = useRef([])
      const timerRef = useRef(null)
      const tickRef = useRef(null)
      const busyRef = useRef(false)
      const secsRef = useRef(0)
      const vadRef = useRef({ spoken: false, quietSince: 0 })

      const newWords = () => {
        fetch('/api/dsh-media/speech/words?n=6')
          .then((r) => r.json())
          .then((j) => { if (j && j.ok) setWords(j.words || []) })
          .catch(() => { })
      }

      const doPolish = () => {
        const t = (text || '').trim()
        if (t.length < 15) { setErr('说几句再润色'); return }
        setPolBusy(true); setErr(null); setPolished('')
        fetch('/api/dsh-media/sp/polish', {
          method: 'POST', headers: { 'content-type': 'application/json' },
          body: JSON.stringify({ text: t }),
        }).then((r) => r.json()).then((j) => {
          setPolBusy(false)
          if (j && j.ok) setPolished(j.text || '')
          else setErr((j && j.error) || '润不了')
        }).catch((e) => { setPolBusy(false); setErr('润不了：' + String(e && e.message)) })
      }

      const saveToViews = (which) => {
        const t = (which === 'polished' && polished) ? polished : (text || '').trim()
        if (t.length < 10) { setErr('没内容可存'); return }
        setSavedTip('正在存…')
        fetch('/api/dsh-media/sp/toview', {
          method: 'POST', headers: { 'content-type': 'application/json' },
          body: JSON.stringify({ text: t }),
        }).then((r) => r.json()).then((j) => {
          setSavedTip(j && j.ok ? '已存到「我的观点」' : ((j && j.error) || '存不上'))
          setTimeout(() => setSavedTip(''), 2600)
        }).catch((e) => setSavedTip('存不上：' + String(e && e.message)))
      }

      const stopAll = () => {
        try { if (tickRef.current) clearInterval(tickRef.current) } catch { }
        try { if (timerRef.current) clearInterval(timerRef.current) } catch { }
        try { if (procRef.current) procRef.current.disconnect() } catch { }
        try { if (streamRef.current) streamRef.current.getTracks().forEach((t) => t.stop()) } catch { }
        try { if (acRef.current) acRef.current.close() } catch { }
        procRef.current = null; streamRef.current = null; acRef.current = null
      }

      useEffect(() => {
        newWords()
        return () => stopAll()
      }, [])

      const flush = async (force) => {
        if (busyRef.current) return
        const pend = pendRef.current
        pendRef.current = []
        if (!pend.length) return
        const total = pend.reduce((a, b) => a + b.length, 0)
        const buf = new Int16Array(total)
        let off = 0
        for (const p of pend) { buf.set(p, off); off += p.length }
        if (!force && total < 16000 * 0.8) { pendRef.current.push(buf); return }
        busyRef.current = true
        try {
          const r = await fetch('/api/dsh-media/speech/asr?m=small', {
            method: 'POST', headers: { 'Content-Type': 'application/octet-stream' },
            body: buf.buffer,
          })
          const j = await r.json()
          if (j && j.ok && j.text) setText((t) => (t ? t + j.text : j.text))
        } catch { } finally { busyRef.current = false }
      }

      const start = async () => {
        setErr(null); setResult(null); setText(''); setSecs(0)
        secsRef.current = 0
        pendRef.current = []; allRef.current = []
        vadRef.current = { spoken: false, quietSince: 0 }
        try {
          const stream = await navigator.mediaDevices.getUserMedia({
            audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true },
          })
          streamRef.current = stream
          const AC = window.AudioContext || window.webkitAudioContext
          const ac = new AC({ sampleRate: 16000 })
          acRef.current = ac
          const src = ac.createMediaStreamSource(stream)
          const proc = ac.createScriptProcessor(4096, 1, 1)
          procRef.current = proc
          proc.onaudioprocess = (e) => {
            const d = e.inputBuffer.getChannelData(0)
            const i16 = new Int16Array(d.length)
            for (let i = 0; i < d.length; i++) {
              const v = Math.max(-1, Math.min(1, d[i]))
              i16[i] = v < 0 ? v * 0x8000 : v * 0x7fff
            }
            pendRef.current.push(i16)
            allRef.current.push(i16)
          }
          src.connect(proc)
          proc.connect(ac.destination)
          setOn(true)
          timerRef.current = setInterval(() => flush(false), 6000)
          tickRef.current = setInterval(() => {
            secsRef.current += 1
            setSecs(secsRef.current)
          }, 1000)
        } catch (e) {
          setErr('打不开麦克风：' + (e && e.message ? e.message : e))
        }
      }

      const stop = async () => {
        const dur = secsRef.current
        stopAll()
        setOn(false)
        await flush(true)
        setBusy(true)
        try {
          const all = allRef.current
          if (!all.length) { setErr('这一轮没有录到声音'); setBusy(false); return }
          const total = all.reduce((a, b) => a + b.length, 0)
          const buf = new Int16Array(total)
          let off = 0
          for (const p of all) { buf.set(p, off); off += p.length }
          const r = await fetch('/api/dsh-media/speech/asr?m=turbo', {
            method: 'POST', headers: { 'Content-Type': 'application/octet-stream' },
            body: buf.buffer,
          })
          const j = await r.json()
          const finalText = (j && j.ok && j.text) ? j.text : text
          if (finalText) setText(finalText)
          const sr = await fetch('/api/dsh-media/speech/score', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ words, transcript: finalText, seconds: dur }),
          })
          const sj = await sr.json()
          if (sj && sj.ok) setResult(sj)
          else setErr((sj && sj.error) || '评分失败')
        } catch (e) {
          setErr(String(e && e.message ? e.message : e))
        }
        setBusy(false)
      }

      const fmt = (s) => String(Math.floor(s / 60)).padStart(1, '0') + ':' + String(s % 60).padStart(2, '0')

      if (pending) {
        return h('div', { className: 'mw-root' },
          h('style', { key: 'mw-css' }, CSS),
          h('div', { className: 'mw-detail' },
            h('div', { className: 'mw-dhead' },
              h('button', { type: 'button', className: 'mw-back', onClick: onBack }, '‹ 工具列表'),
              h('div', { className: 'mw-dtitle' }, pending),
              h('div', { style: { flex: '1 1 auto' } }),
              h(ModelPicker, null),
              h('div', { className: 'mw-hot-meta' }, '待做'),
            ),
            h('div', { className: 'mw-dbody' },
              h('div', { className: 'mw-empty', style: { textAlign: 'center', padding: '40px 0' } },
                '这个训练还没做。'),
              h('div', { className: 'mw-empty', style: { textAlign: 'center' } },
                '你说一句「做' + pending + '」，我就把它接上——复用现有的麦克风和打分逻辑。'),
            ),
          ),
        )
      }

      return h('div', { className: 'mw-root' },
        h('style', { key: 'mw-css' }, CSS),
        h('div', { className: 'mw-detail' },
          h('div', { className: 'mw-dhead' },
            h('button', { type: 'button', className: 'mw-back', onClick: onBack }, '‹ 工具列表'),
            h('div', { className: 'mw-dtitle' }, '表达训练'),
            h('div', { style: { flex: '1 1 auto' } }),
            h(ModelPicker, null),
            h('div', { className: 'mw-hot-meta' }, on ? `录音中 ${fmt(secs)}` : (busy ? '正在收尾…' : '待开始')),
          ),
          h('div', { className: 'mw-dbody' },
            err ? h('div', { className: 'mw-err' }, err) : null,

            h('div', { className: 'mw-hot-group' },
              h('div', { className: 'mw-hot-gt' },
                h('span', { className: 'mw-hot-gt-label' }, '这一轮的词'),
                h('span', { className: 'mw-hot-gt-line' }),
                h('button', { type: 'button', className: 'mw-hot-btn', disabled: on, onClick: newWords }, '换一组'),
              ),
              h('div', { style: { display: 'flex', flexWrap: 'wrap', gap: 8 } },
                words.map((w) => h('span', {
                  key: w,
                  style: {
                    fontSize: 15, padding: '7px 14px', borderRadius: 10,
                    background: C.cell2, border: '1px solid ' + C.border, color: C.text,
                  },
                }, w)),
              ),
              h('div', { style: { marginTop: 12, fontSize: 12, color: C.sub, lineHeight: 1.7 } },
                '拿到词之后直接用它们讲一个故事或一段观点，不用按顺序。建议 60 秒左右。'),
              h('div', { style: { display: 'flex', gap: 10, marginTop: 12, alignItems: 'center' } },
                on
                  ? h('button', { type: 'button', className: 'mw-hot-btn', onClick: stop }, '我讲完了，评分')
                  : h('button', { type: 'button', className: 'mw-hot-btn', disabled: busy, onClick: start }, '开始讲'),
                h('button', {
                  type: 'button', className: 'mw-hot-btn',
                  disabled: polBusy || !(text || '').trim(),
                  onClick: doPolish,
                }, polBusy ? '润色中…' : 'AI 润色'),
                h('button', {
                  type: 'button', className: 'mw-hot-btn',
                  disabled: !(text || '').trim(),
                  onClick: () => saveToViews('orig'),
                }, '存到我的观点'),
                savedTip ? h('div', { style: { fontSize: 12, color: C.gold, marginLeft: 8 } }, savedTip) : null,
              ),
            ),

            text ? h('div', { className: 'mw-hot-group' },
              h('div', { className: 'mw-hot-gt' },
                h('span', { className: 'mw-hot-gt-label' }, '实时转写'),
                h('span', { className: 'mw-hot-gt-line' }),
                h('span', { className: 'mw-hot-gt-label' }, `${text.length} 字`),
              ),
              h('div', {
                style: {
                  whiteSpace: 'pre-wrap', lineHeight: 1.75, fontSize: 14,
                  maxHeight: 260, overflowY: 'auto', padding: '10px 12px',
                  background: C.cell2, border: '1px solid ' + C.border, borderRadius: 10,
                },
              }, text),
            ) : null,

            polishBlock(),

            result ? h('div', { className: 'mw-hot-group' },
              h('div', { className: 'mw-hot-gt' },
                h('span', { className: 'mw-hot-gt-label' }, '这一轮的评分'),
                h('span', { className: 'mw-hot-gt-line' }),
                h('span', { className: 'mw-hot-gt-label' },
                  `${result.mechanical.usedCount}/${result.mechanical.totalWords} 个词用上 · ${result.review.contentScore} 分`),
              ),
              h('div', { style: { display: 'flex', gap: 18, flexWrap: 'wrap', fontSize: 13, color: C.sub, marginBottom: 10 } },
                h('span', null, `语速 ${result.mechanical.pace} 字/分`),
                h('span', null, `说了 ${result.mechanical.chars} 字`),
                h('span', null, `填充词 ${result.mechanical.fillers} 次`),
                h('span', null, `时长 ${result.mechanical.seconds} 秒`),
              ),
              h('div', { className: 'mw-insight', style: { marginBottom: 10 } },
                h('span', { className: 'mw-insight-tag' }, 'AI 说 · 结构'), result.review.logic || ''),
              h('div', { className: 'mw-insight', style: { marginBottom: 10 } },
                h('span', { className: 'mw-insight-tag' }, 'AI 说 · 像不像在跟人说话'), result.review.voice || ''),
              h('div', { style: { fontSize: 13, lineHeight: 1.9, color: C.text } },
                (result.review.improvements || []).map((s, i) => h('div', { key: i }, `　${i + 1}. ${s}`)),
              ),
              result.mechanical.usedCount < result.mechanical.totalWords
                ? h('div', { style: { marginTop: 10, fontSize: 12, color: C.warn } },
                  '没讲到的词：' + words.filter((w) => !(result.mechanical.used || []).includes(w)).join('、'))
                : null,
            ) : null,
          ),
        ),
      )
    }

    /* ---- 分身：一群顾问，各看各的角度 ---- */
    function PersonaPanel({ onBack }) {
      const [list, setList] = useState([])
      const [cur, setCur] = useState(null)
      const [turns, setTurns] = useState([])
      const [q, setQ] = useState('')
      const [busy, setBusy] = useState(false)
      const [err, setErr] = useState(null)
      const [sugg, setSugg] = useState(null)
      const [draft, setDraft] = useState(null)
      const [busy2, setBusy2] = useState(false)

      const refresh = () => {
        fetch('/api/dsh-media/personas')
          .then((r) => r.json())
          .then((j) => { if (j && j.ok) setList(j.personas || []) })
          .catch(() => setErr('读不到角色列表'))
        fetch('/api/dsh-media/personas/suggest')
          .then((r) => r.json())
          .then((j) => { if (j && j.ok) setSugg(j) })
          .catch(() => { })
      }

      useEffect(() => { refresh() }, [])

      const genDraft = async (topic) => {
        if (busy2) return
        setBusy2(true); setDraft(null); setErr(null)
        try {
          const r = await fetch('/api/dsh-media/personas/draft', {
            method: 'POST', headers: { 'content-type': 'application/json' },
            body: JSON.stringify({ topic }),
          })
          const j = await r.json()
          if (j && j.ok) setDraft(j.persona)
          else setErr((j && j.error) || '生成草稿失败')
        } catch (e) { setErr(String(e && e.message ? e.message : e)) }
        setBusy2(false)
      }

      const addPersona = async () => {
        if (!draft || busy2) return
        setBusy2(true)
        try {
          const r = await fetch('/api/dsh-media/personas/add', {
            method: 'POST', headers: { 'content-type': 'application/json' },
            body: JSON.stringify({ persona: draft }),
          })
          const j = await r.json()
          if (j && j.ok) { setDraft(null); refresh() }
          else setErr((j && j.error) || '加入失败')
        } catch (e) { setErr(String(e && e.message ? e.message : e)) }
        setBusy2(false)
      }

      const ask = async () => {
        const text = q.trim()
        if (!text || !cur || busy) return
        setQ('')
        setErr(null)
        setTurns((t) => [...t, { role: 'user', text }, { role: 'ai', text: '' }])
        setBusy(true)
        try {
          const r = await fetch('/api/dsh-media/personas/chat', {
            method: 'POST',
            headers: { 'content-type': 'application/json' },
            body: JSON.stringify({ personaId: cur.id, question: text }),
          })
          if (!r.body) throw new Error('无响应流')
          const reader = r.body.getReader()
          const dec = new TextDecoder()
          let acc = ''
          for (; ;) {
            const { done, value } = await reader.read()
            if (done) break
            acc += dec.decode(value, { stream: true })
            setTurns((t) => {
              const n = t.slice()
              n[n.length - 1] = { role: 'ai', text: acc }
              return n
            })
          }
        } catch (e) {
          setErr(String(e && e.message ? e.message : e))
        }
        setBusy(false)
      }

      const body = cur
        ? h('div', { className: 'mw-dbody' },
          h('button', { type: 'button', className: 'mw-back', style: { marginBottom: 14 }, onClick: () => { setCur(null); setTurns([]) } }, '‹ 换一个分身'),
          h('div', { style: { fontSize: 17, fontWeight: 640, marginBottom: 4 } }, cur.name + ' · ' + cur.title),
          h('div', { style: { fontSize: 12, color: C.sub, marginBottom: 16, lineHeight: 1.7 } }, cur.focus),
          turns.length === 0 ? h('div', { className: 'mw-empty' }, '问他一个问题，他会用自己的角度回答，引用的是你库里的内容。') : null,
          turns.map((t, i) => h('div', {
            key: i,
            style: {
              marginBottom: 12, fontSize: 14, lineHeight: 1.8, whiteSpace: 'pre-wrap',
              color: t.role === 'user' ? C.sub : C.text,
              paddingLeft: t.role === 'user' ? 0 : 12,
              borderLeft: t.role === 'user' ? 'none' : '2px solid ' + C.accent,
            },
          }, (t.role === 'user' ? '你：' : cur.name + '：') + t.text)),
          err ? h('div', { className: 'mw-err' }, err) : null,
          h('div', { style: { display: 'flex', gap: 10, marginTop: 14 } },
            h('input', {
              value: q,
              onChange: (e) => setQ(e.target.value),
              onKeyDown: (e) => { if (e.key === 'Enter') ask() },
              placeholder: '问他一句…',
              style: {
                flex: '1 1 auto', background: C.cell, border: '1px solid ' + C.border,
                borderRadius: 8, padding: '9px 12px', color: C.text, fontSize: 14, outline: 'none',
              },
            }),
            h('button', { type: 'button', className: 'mw-hot-btn', disabled: busy, onClick: ask }, busy ? '他在想…' : '问'),
          ),
        )
        : h('div', { className: 'mw-dbody' },
          h('div', { className: 'mw-ghead' },
            h('span', { className: 'mw-glabel' }, '分身名单'),
            h('span', { className: 'mw-gnote' }, '知识来自你的内容库，每人一个看问题的角度'),
          ),
          err ? h('div', { className: 'mw-err' }, err) : null,
          list.map((p) => h('div', {
            key: p.id, className: 'mw-hot-item', style: { cursor: 'pointer' },
            onClick: () => { setCur(p); setTurns([]) },
          },
            h('div', { className: 'mw-hot-title' }, p.name + ' · ' + p.title),
            h('div', { className: 'mw-hot-foot' }, h('span', { style: { color: C.sub } }, p.focus)),
          )),
          list.length === 0 ? h('div', { className: 'mw-empty' }, '还没有角色。检查 E:\\desktop\\media\\personas.json') : null,

          sugg && sugg.candidates && sugg.candidates.length ? h('div', { className: 'mw-hot-group', style: { marginTop: 22 } },
            h('div', { className: 'mw-ghead' },
              h('span', { className: 'mw-glabel' }, '可以新增的顾问'),
              h('span', { className: 'mw-gnote' }, '库里这些题材已攒够素材（≥' + sugg.threshold + ' 条），还没人管'),
            ),
            sugg.candidates.map((c) => h('div', {
              key: c.topic, className: 'mw-hot-item', style: { cursor: 'pointer' },
              onClick: () => genDraft(c.topic),
            },
              h('div', { className: 'mw-hot-title' }, c.topic),
              h('div', { className: 'mw-hot-foot' },
                h('span', { style: { color: C.sub } }, c.atoms + ' 条素材 · 点一下生成草稿' + (busy2 ? '（生成中…）' : ''))),
            )),
          ) : null,

          draft ? h('div', { className: 'mw-hot-group', style: { marginTop: 18 } },
            h('div', { className: 'mw-ghead' },
              h('span', { className: 'mw-glabel' }, '草稿：' + draft.name),
              h('span', { className: 'mw-gnote' }, '不满意就再点别的题材，或直接改 personas.json'),
            ),
            h('div', { style: { fontSize: 14, lineHeight: 2, paddingTop: 8 } },
              h('div', null, draft.title),
              h('div', { style: { color: C.sub } }, '关注：' + draft.focus),
              h('div', { style: { color: C.sub } }, '框架：' + draft.frame),
              h('div', { style: { color: C.sub } }, '腔调：' + draft.voice),
              h('div', { style: { color: C.sub } }, '反对：' + draft.against),
            ),
            h('div', { style: { marginTop: 10 } },
              h('button', { type: 'button', className: 'mw-hot-btn', disabled: busy2, onClick: addPersona }, '加入顾问团'),
              h('button', { type: 'button', className: 'mw-hot-btn', style: { marginLeft: 14 }, onClick: () => setDraft(null) }, '不要'),
            ),
          ) : null,
        )

      return h('div', { className: 'mw-root' },
        h('style', { key: 'mw-css' }, CSS),
        h('div', { className: 'mw-detail' },
          h('div', { className: 'mw-dhead' },
            h('button', { type: 'button', className: 'mw-back', onClick: onBack }, '‹ 工具列表'),
            h('div', { className: 'mw-dtitle' }, '分身'),
            h('div', { style: { flex: '1 1 auto' } }),
            h(ModelPicker, null),
            h('div', { className: 'mw-hot-meta' }, cur ? cur.name : list.length + ' 个角色'),
          ),
          body,
        ),
      )
    }

    /* 工作台统一的模型选择器（按接口分组） */
    const PROVIDER_CN = { siliconflow: '硅基流动', 'deepseek-account': 'DeepSeek 官方', 'our-free-model': '免费通道' }
    function ModelPicker() {
      const [list, setList] = useState([])
      const [cur, setCur] = useState(null)
      const [saved, setSaved] = useState(null)
      const [open, setOpen] = useState(false)
      const boxRef = useRef(null)
      const btnRef = useRef(null)
      const [pos, setPos] = useState(null)
      const [hover, setHover] = useState(null)

      const place = () => {
        const r = btnRef.current && btnRef.current.getBoundingClientRect()
        if (!r) return
        const W = Math.min(340, window.innerWidth - 24)
        // 面板右缘与按钮右缘对齐；若会超出屏幕则往左收
        const right = Math.max(12, window.innerWidth - r.right)
        setPos({ top: r.bottom + 2, right: right, width: W })
      }

      // 打开时用捕获阶段拦掉所有点击：弹层外→只关闭，弹层内→正常，
      // 绝不落到下面的卡片上（比遮罩层更可靠，不受父级 stacking context 影响）
      useEffect(() => {
        if (!open) return
        const guard = (e) => {
          const box = boxRef.current
          if (box && box.contains(e.target)) return
          e.stopPropagation()
          e.preventDefault()
          setOpen(false)
        }
        const onKey = (e) => { if (e.key === 'Escape') { e.stopPropagation(); setOpen(false) } }
        window.addEventListener('resize', place)
        document.addEventListener('scroll', place, true)
        document.addEventListener('mousedown', guard, true)
        document.addEventListener('click', guard, true)
        document.addEventListener('keydown', onKey, true)
        return () => {
          document.removeEventListener('mousedown', guard, true)
          document.removeEventListener('click', guard, true)
          document.removeEventListener('keydown', onKey, true)
          window.removeEventListener('resize', place)
          document.removeEventListener('scroll', place, true)
        }
      }, [open])

      useEffect(() => {
        fetch('/api/dsh-media/models')
          .then((r) => r.json())
          .then((j) => { if (j && j.ok) { setList(j.list || []); setCur(j.current); setSaved(j.saved) } })
          .catch(() => { })
      }, [])

      const pick = (m) => {
        setOpen(false)
        fetch('/api/dsh-media/models/select', {
          method: 'POST', headers: { 'content-type': 'application/json' },
          body: JSON.stringify(m ? { provider: m.provider, model: m.model } : {}),
        }).then((r) => r.json()).then((j) => { if (j && j.ok) setSaved(j.saved) }).catch(() => { })
      }

      const active = saved || (cur ? { provider: cur.provider, model: cur.model } : null)
      const shortName = (x) => { const t = String(x || ''); const i = t.lastIndexOf('/'); return i >= 0 ? t.slice(i + 1) : t }
      const label = active ? shortName(active.model) : '默认'

      // 按接口分组
      const groups = []
      for (const m of list) {
        let g = groups.find((x) => x.provider === m.provider)
        if (!g) { g = { provider: m.provider, items: [] }; groups.push(g) }
        if (!g.items.some((it) => it.model === m.model)) g.items.push(m)
      }

      // 弹层实底：直接写死深色，避免主题变量带透明度或未定义
      const solidBg = '#1c1c1e'

      return h('div', { ref: boxRef, style: { position: 'relative', flex: 'none' } },
        h('button', {
          ref: btnRef, type: 'button', onClick: () => {
            if (open) { setOpen(false); return }
            place(); setOpen(true)
            requestAnimationFrame(() => { place(); requestAnimationFrame(place) })
          },
          style: {
            fontFamily: 'inherit', cursor: 'pointer', fontSize: 12, fontWeight: 600,
            padding: '4px 10px', borderRadius: 999,
            color: C.accent, background: 'color-mix(in srgb, ' + C.accent + ' 12%, transparent)',
            border: '1px solid color-mix(in srgb, ' + C.accent + ' 40%, transparent)',
            maxWidth: 210, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
          },
          title: active ? (PROVIDER_CN[active.provider] || active.provider) + ' / ' + active.model : '未选择',
        }, label + ' ⌄'),
        open ? h('div', {
          style: {
            position: 'absolute', zIndex: 61,
            top: '100%', marginTop: 2, right: 0,
            width: 340, maxWidth: '80vw',
            maxHeight: '60vh',
            overflowY: 'auto',
            backgroundColor: solidBg, backgroundImage: 'none', opacity: 1,
            border: '1px solid ' + C.border, borderRadius: 10, padding: 8,
            boxShadow: '0 16px 40px rgba(0,0,0,.45), 0 0 0 1px ' + solidBg,
          },
        },
          h('div', {
            style: {
              padding: '8px 10px', cursor: 'pointer', fontSize: 12.5, borderRadius: 6,
              color: saved ? C.sub : C.text,
              background: hover === '__default' ? 'color-mix(in srgb, ' + C.accent + ' 16%, transparent)' : 'transparent',
              
            },
            onMouseEnter: () => setHover('__default'),
            onMouseLeave: () => setHover(null),
            onClick: () => pick(null),
          }, '用 DSH 主界面的模型' + (saved ? '' : ' ✓') + (cur ? '（现在：' + shortName(cur.model) + '）' : '')),
          groups.map((g) => h('div', { key: g.provider, style: { marginTop: 8 } },
            h('div', {
              style: { fontSize: 10.5, letterSpacing: 1, color: C.sub, padding: '6px 10px 4px', opacity: .8 },
            }, (PROVIDER_CN[g.provider] || g.provider) + ' · ' + g.provider),
            g.items.map((m, i) => {
              const on = saved && saved.model === m.model && saved.provider === m.provider
              return h('div', {
                key: m.provider + m.model + i,
                onClick: () => pick(m),
                onMouseEnter: () => setHover(m.provider + '/' + m.model),
                onMouseLeave: () => setHover(null),
                style: {
                  padding: '7px 10px', cursor: 'pointer', fontSize: 12.5, borderRadius: 6,
                  color: on ? C.accent : C.text,
                  background: on
                    ? 'color-mix(in srgb, ' + C.accent + ' 12%, transparent)'
                    : (hover === m.provider + '/' + m.model
                      ? 'color-mix(in srgb, ' + C.accent + ' 18%, transparent)'
                      : 'transparent'),
                  
                },
              }, shortName(m.model) + (on ? ' ✓' : ''))
            }),
          )),
          groups.length === 0 ? h('div', { style: { padding: 12, fontSize: 12, color: C.sub } }, '没读到模型列表，检查 profile 的 cordis.patch.yml') : null,
        ) : null,
      )
    }

    /* 从发言里拆出【标题】和正文 */
    function splitTitle(text) {
      const t = String(text || '')
      const m = t.match(/^\s*【([^】]{1,40})】\s*\n?/)
      if (m) return { title: m[1].trim(), body: t.slice(m[0].length).trim() }
      return { title: '', body: t }
    }

    /* 把一段话切成句子，方便把「细说」框插到被选中的那句后面 */
    function splitSentences(text) {
      const src = String(text || '')
      const out = []
      let buf = ''
      for (const ch of src) {
        buf += ch
        if ('。！？；!?;\n'.includes(ch)) { out.push(buf); buf = '' }
      }
      if (buf) out.push(buf)
      return out.length ? out : [src]
    }

    /* 把 **重点** 渲染成高亮 */
    function richText(text, tone) {
      const col = tone || C.accent
      const src = String(text || '')
      const parts = src.split(/\*\*([^*]+)\*\*/g)
      return parts.map((seg, i) => (i % 2 === 1
        ? h('mark', {
          key: i,
          style: {
            background: 'color-mix(in srgb, ' + col + ' 26%, transparent)',
            color: col, fontWeight: 600,
            padding: '1px 5px', borderRadius: 4,
            boxShadow: 'inset 0 -2px 0 color-mix(in srgb, ' + col + ' 55%, transparent)',
          },
        }, seg)
        : seg))
    }

    /* 每个角色一个高亮色 */
    const PERSONA_TONE = {
      business: '#d9a94a',   // 金
      creator: '#5fbf8f',    // 绿
      life: '#b08cd9',       // 紫
      psych: '#6aa8e8',      // 蓝
      ai: '#e08a4a',         // 橙
      voice: '#e07a9a',      // 粉
    }
    const toneOf = (id) => PERSONA_TONE[id] || '#d9a94a'

    /* 明确的小按钮（跟正文颜色区分开） */
    function chipBtn(label, onClick, tone) {
      const col = tone || C.accent
      return h('button', {
        type: 'button',
        onClick,
        style: {
          flex: 'none', cursor: 'pointer', fontFamily: 'inherit',
          fontSize: 12, fontWeight: 600, letterSpacing: .3, lineHeight: 1.4,
          padding: '3px 10px', borderRadius: 999,
          color: col, background: 'color-mix(in srgb, ' + col + ' 14%, transparent)',
          border: '1px solid color-mix(in srgb, ' + col + ' 45%, transparent)',
        },
      }, label)
    }

    /* ---- 圆桌会议：存档 + 多轮 + 就地细说 + 批量导出 ---- */
    function RoundTablePanel({ onBack }) {
      const [list, setList] = useState([])
      const [topic, setTopic] = useState(null)
      const [q, setQ] = useState('')
      const [busy, setBusy] = useState(false)
      const [err, setErr] = useState(null)
      const [askFor, setAskFor] = useState(null)
      const [askText, setAskText] = useState('')
      const [askBusy, setAskBusy] = useState(false)
      const [sel, setSel] = useState(null)
      const [asks, setAsks] = useState([])
      const [expanded, setExpanded] = useState({})   // 每一句的细说框
      const [busy2b, setBusy2b] = useState(false)
      const [picked, setPicked] = useState({})
      const [folded, setFolded] = useState({})
      const [exp, setExp] = useState(null)
      const [expBusy, setExpBusy] = useState(false)

      const loadList = () => {
        fetch('/api/dsh-media/roundtable/list')
          .then((r) => r.json())
          .then((j) => { if (j && j.ok) setList(j.list || []) })
          .catch(() => { })
      }
      useEffect(() => { loadList() }, [])

      const openTopic = (id) => {
        fetch('/api/dsh-media/roundtable/get?id=' + encodeURIComponent(id))
          .then((r) => r.json())
          .then((j) => { if (j && j.ok) { setTopic(j.topic); setErr(null); setSel(null) } })
          .catch(() => setErr('读不到这个议题'))
      }

      const open = async () => {
        const text = q.trim()
        if (!text || busy) return
        setErr(null); setBusy(true)
        try {
          const r = await fetch('/api/dsh-media/roundtable/open', {
            method: 'POST', headers: { 'content-type': 'application/json' },
            body: JSON.stringify({ question: text }),
          })
          const j = await r.json()
          if (j && j.ok) { setTopic(j.topic); setQ(''); loadList() }
          else setErr((j && j.error) || '圆桌没开起来')
        } catch (e) { setErr(String(e && e.message ? e.message : e)) }
        setBusy(false)
      }

      const next = async () => {
        if (busy || !topic) return
        setErr(null); setBusy(true)
        try {
          const r = await fetch('/api/dsh-media/roundtable/next', {
            method: 'POST', headers: { 'content-type': 'application/json' },
            body: JSON.stringify({ id: topic.id }),
          })
          const j = await r.json()
          if (j && j.ok) setTopic(j.topic)
          else setErr((j && j.error) || '这一轮没开成')
        } catch (e) { setErr(String(e && e.message ? e.message : e)) }
        setBusy(false)
      }

      const startExplain = (a, quote, rd, sent) => {
        const key = a.id + ':' + rd + ':' + Date.now().toString(36)
        setAsks((v) => [...v, { key, personaId: a.id, name: a.name, text: quote, round: rd, status: 'loading', answer: '' }])
        setBusy2b(true)
        fetch('/api/dsh-media/roundtable/ask', {
          method: 'POST', headers: { 'content-type': 'application/json' },
          body: JSON.stringify({ id: topic.id, personaId: a.id, sent, question: '请解释你刚才说的这段话是什么意思，用更直白的话讲一遍：' + quote }),
        })
          .then((r) => r.json())
          .then((j) => {
            if (j && j.ok) {
              setAsks((v) => v.filter((x) => x.key !== key))
              setTopic((t) => ({
                ...t,
                followups: [...(t.followups || []), { personaId: a.id, name: a.name, question: quote, answer: j.answer || '', round: rd, sent: (j && j.sent !== undefined ? j.sent : null), at: '' }],
              }))
            } else {
              setAsks((v) => v.map((x) => (x.key === key
                ? { ...x, status: 'error', answer: (j && j.error) || '没拿到回答' }
                : x)))
            }
          })
          .catch((e) => {
            setAsks((v) => v.map((x) => (x.key === key ? { ...x, status: 'error', answer: String(e && e.message ? e.message : e) } : x)))
          })
          .then(() => setBusy2b(false))
      }

      const askWith = async (personaId, name, text) => {
        if (!text || !topic || askBusy) return
        setAskBusy(true); setErr(null)
        try {
          const r = await fetch('/api/dsh-media/roundtable/ask', {
            method: 'POST', headers: { 'content-type': 'application/json' },
            body: JSON.stringify({ id: topic.id, personaId, question: text }),
          })
          const j = await r.json()
          if (j && j.ok) {
            const rd = j.round || (topic.rounds ? topic.rounds.length : 1)
            setTopic((t) => ({ ...t, followups: [...(t.followups || []), { personaId, name, question: text, answer: j.answer, round: rd, at: '' }] }))
            setAskText(''); setSel(null); setAskFor(null)
          } else setErr((j && j.error) || '追问失败')
        } catch (e) { setErr(String(e && e.message ? e.message : e)) }
        setAskBusy(false)
      }

      const onSelect = () => {
        try {
          const g = window.getSelection()
          const t = g ? String(g).trim() : ''
          if (t.length < 4) return   // 点空白不清掉已有的细说框
          let el = g.anchorNode
          el = el && el.nodeType === 3 ? el.parentElement : el
          let hit = null
          let sent = null
          while (el) {
            if (sent === null && el.dataset && el.dataset.sent !== undefined) sent = Number(el.dataset.sent)
            if (el.dataset && el.dataset.persona) { hit = { id: el.dataset.persona, name: el.dataset.name }; break }
            el = el.parentElement
          }
          if (hit) setSel({ text: t.slice(0, 300), sent, ...hit })
        } catch { }
      }

      const delMany = async () => {
        const ids = Object.keys(picked).filter((k) => picked[k])
        if (!ids.length) return
        if (!window.confirm('确定删除选中的 ' + ids.length + ' 场会议记录？删了就找不回来了。')) return
        try {
          const r = await fetch('/api/dsh-media/roundtable/delete', {
            method: 'POST', headers: { 'content-type': 'application/json' },
            body: JSON.stringify({ ids }),
          })
          const j = await r.json()
          if (j && j.ok) { setPicked({}); setExp(null); loadList() }
          else setErr((j && j.error) || '删除失败')
        } catch (e) { setErr(String(e && e.message ? e.message : e)) }
      }

      const exportMany = async (all) => {
        if (expBusy) return
        const ids = all ? [] : Object.keys(picked).filter((k) => picked[k])
        setExpBusy(true); setErr(null)
        try {
          const r = await fetch('/api/dsh-media/roundtable/export-many', {
            method: 'POST', headers: { 'content-type': 'application/json' },
            body: JSON.stringify({ ids }),
          })
          const j = await r.json()
          if (j && j.ok) setExp(j)
          else setErr((j && j.error) || '导出失败')
        } catch (e) { setErr(String(e && e.message ? e.message : e)) }
        setExpBusy(false)
      }

      const inputStyle = {
        flex: '1 1 auto', background: C.cell, border: '1px solid ' + C.border,
        borderRadius: 8, padding: '10px 12px', color: C.text, fontSize: 14, outline: 'none',
      }

      const nameStyle = { fontSize: 17, fontWeight: 680, letterSpacing: .2, color: C.text }
      const titleStyle = { fontSize: 13, color: C.sub }

      let body
      if (topic) {
        const rounds = topic.rounds || []
        const fus = topic.followups || []
        const lastRound = rounds.length ? rounds[rounds.length - 1].round : 0
        body = h('div', { className: 'mw-dbody', onMouseUp: onSelect },
          h('div', { style: { marginBottom: 18, paddingBottom: 12, borderBottom: '1px solid ' + C.border } },
            h('div', {
              style: { fontSize: 20, fontWeight: 700, lineHeight: 1.55, color: C.text, letterSpacing: .2 },
            }, topic.question),
            h('div', { style: { marginTop: 8, fontSize: 12, color: C.sub } },
              topic.createdAt + ' · ' + rounds.length + ' 轮'),
          ),
          rounds.map((rd) => h('div', { key: rd.round, style: { marginBottom: 24 } },
            h('div', { className: 'mw-ghead' },
              h('span', { className: 'mw-glabel' }, '第 ' + rd.round + ' 轮'),
              h('span', { className: 'mw-gnote' },
                (rd.round === 1 ? '各自表态' : '互相回应')
                + (rd.answers ? ' · ' + rd.answers.length + ' 位发言' : '')
                + (rd.silent && rd.silent.length ? ' · ' + rd.silent.join('、') + ' 本轮没话说' : '')),
            ),
            rd.answers.map((a) => {
              const mine = fus.filter((f) => f.personaId === a.id && ((f.round == null ? lastRound : f.round) === rd.round))
              const isLast = rd.round === lastRound
              return h('div', {
                key: a.id, 'data-persona': a.id, 'data-name': a.name,
                style: { padding: '18px 0 16px 16px', borderLeft: '2px solid color-mix(in srgb, ' + toneOf(a.id) + ' 50%, transparent)', borderBottom: '1px solid ' + C.border },
              },
                h('div', { style: { display: 'flex', alignItems: 'baseline', gap: 10, marginBottom: 10, flexWrap: 'wrap' } },
                  h('span', { style: nameStyle }, a.name),
                  h('span', { style: titleStyle }, a.title),
                  h('span', { style: { marginLeft: 'auto' } },
                    chipBtn('追问 ›', () => { setAskFor({ id: a.id, name: a.name }); setAskText('') })),
                ),
                (function () {
                  if (a.error) return h('div', { style: { fontSize: 14.5, color: C.err } }, '[失败] ' + a.error)
                  if (!a.text) return h('div', { style: { fontSize: 14.5, color: C.sub } }, '（没说话）')
                  const sp = splitTitle(a.text)
                  const tone = toneOf(a.id)
                  const sents = splitSentences(sp.body)

                  const rowFor = (f, sig) => {
                    const openIt = !!expanded[sig]
                    return h('div', {
                      key: sig,
                      style: { margin: '6px 0 0 8px', paddingLeft: 10, borderLeft: '3px solid ' + tone },
                    },
                      h('div', { style: { display: 'flex', alignItems: 'center', gap: 8 } },
                        chipBtn(openIt ? '收起 ⌃' : '看细说 ⌄', () => setExpanded((v) => ({ ...v, [sig]: !v[sig] }))),
                        h('span', { style: { fontSize: 11.5, color: C.sub } }, openIt ? '' : '（' + String(f.answer || '').length + ' 字）'),
                      ),
                      openIt ? h('div', { style: { marginTop: 6, fontSize: 14, lineHeight: 1.9, whiteSpace: 'pre-wrap' } }, richText(f.answer, tone)) : null,
                    )
                  }

                  const mineAll = fus.filter((f) => f.personaId === a.id && ((f.round == null ? lastRound : f.round) === rd.round))
                  const bySent = (k) => mineAll.filter((f) => f.sent === k)
                  const orphans = mineAll.filter((f) => f.sent === null || f.sent === undefined)

                  return h('div', null,
                    sp.title ? h('div', { style: { fontSize: 17, fontWeight: 700, color: tone, marginBottom: 8, lineHeight: 1.5 } }, sp.title) : null,

                    sents.map((sen, k) => h('div', { key: 's' + k, style: { marginBottom: 2 } },
                      h('span', {
                        'data-sent': k,
                        style: { fontSize: 14.5, lineHeight: 1.95, whiteSpace: 'pre-wrap' },
                      }, richText(sen, tone)),
                      asks.filter((x) => x.personaId === a.id && x.round === rd.round && x.sent === k).length
                        ? h('span', {
                          style: {
                            display: 'inline-flex', alignItems: 'center', gap: 6, marginLeft: 8,
                            padding: '1px 10px', borderRadius: 999, verticalAlign: 'middle',
                            border: '1px solid color-mix(in srgb, ' + tone + ' 55%, transparent)',
                            background: 'color-mix(in srgb, ' + tone + ' 16%, transparent)',
                            fontSize: 12, fontWeight: 600, color: tone,
                          },
                        }, '正在细说…')
                        : null,
                      (sel && sel.id === a.id && sel.sent === k) ? h('span', {
                        style: {
                          display: 'inline-flex', alignItems: 'center', gap: 6, marginLeft: 8,
                          padding: '1px 8px', borderRadius: 999, verticalAlign: 'middle',
                          border: '1px solid color-mix(in srgb, ' + tone + ' 55%, transparent)',
                          background: 'color-mix(in srgb, ' + tone + ' 12%, transparent)',
                        },
                      },
                        chipBtn('细说这句', () => startExplain(a, sel.text, rd.round, k)),
                        h('span', { style: { cursor: 'pointer', fontSize: 11, color: C.sub }, onClick: () => setSel(null) }, '✕'),
                      ) : null,
                      bySent(k).map((f, n) => rowFor(f, 'sd|' + a.id + '|' + rd.round + '|' + k + '|' + n)),
                    )),

                    (sel && sel.id === a.id && (sel.sent === null || sel.sent === undefined)) ? h('div', {
                      style: {
                        display: 'inline-flex', alignItems: 'center', gap: 8, marginTop: 8,
                        padding: '2px 10px', borderRadius: 999,
                        border: '1px solid color-mix(in srgb, ' + tone + ' 55%, transparent)',
                        background: 'color-mix(in srgb, ' + tone + ' 12%, transparent)',
                      },
                    },
                      chipBtn('细说这句', () => startExplain(a, sel.text, rd.round, null)),
                      h('span', { style: { cursor: 'pointer', fontSize: 11, color: C.sub }, onClick: () => setSel(null) }, '✕'),
                    ) : null,

                    asks.filter((x) => x.personaId === a.id && x.round === rd.round && (x.sent === null || x.sent === undefined))
                      .map((x) => h('div', {
                        key: x.key,
                        style: {
                          display: 'inline-flex', alignItems: 'center', gap: 8, marginTop: 8,
                          padding: '2px 10px', borderRadius: 999,
                          border: '1px solid color-mix(in srgb, ' + tone + ' 55%, transparent)',
                          background: 'color-mix(in srgb, ' + tone + ' 16%, transparent)',
                          fontSize: 12, fontWeight: 600, color: tone,
                        },
                      }, '正在细说…')),

                    orphans.length ? h('div', { style: { marginTop: 10 } },
                      h('div', { style: { fontSize: 11.5, color: C.sub, marginBottom: 4 } }, '这一段的其他细说'),
                      orphans.map((f, n) => rowFor(f, 'so|' + a.id + '|' + rd.round + '|' + n)),
                    ) : null,
                  )
                })(),

                isLast && askFor && askFor.id === a.id ? h('div', { style: { marginTop: 12, display: 'flex', gap: 10 } },
                  h('input', {
                    value: askText, onChange: (e) => setAskText(e.target.value),
                    onKeyDown: (e) => { if (e.key === 'Enter') askWith(a.id, a.name, askText.trim()) },
                    placeholder: '追问 ' + a.name + '：你刚才那句具体指什么？',
                    style: inputStyle,
                  }),
                  h('button', { type: 'button', className: 'mw-hot-btn', disabled: askBusy, onClick: () => askWith(a.id, a.name, askText.trim()) }, askBusy ? '…' : '问'),
                  h('button', { type: 'button', className: 'mw-hot-btn', onClick: () => setAskFor(null) }, '取消'),
                ) : null,
              )
            }),
          )),
          err ? h('div', { className: 'mw-err' }, err) : null,
          h('div', { style: { display: 'flex', gap: 16, alignItems: 'center', paddingTop: 18, flexWrap: 'wrap' } },
            h('button', { type: 'button', className: 'mw-hot-btn', disabled: busy, onClick: next }, busy ? '下一轮进行中…' : '再来一轮'),
            h('span', { style: { fontSize: 11.5, color: C.sub } }, '选中任意一句可以直接让它细说 · 每轮 ' + (rounds[0] ? rounds[0].answers.length : 0) + ' 次模型调用'),
          ),
        )
      } else {
        const pickedCount = Object.keys(picked).filter((k) => picked[k]).length
        const allOn = list.length > 0 && pickedCount === list.length
        body = h('div', { className: 'mw-dbody' },
          h('div', { className: 'mw-hot-group' },
            h('div', { className: 'mw-ghead' },
              h('span', { className: 'mw-glabel' }, '新建议题'),
              h('span', { className: 'mw-gnote' }, '第一轮各自表态，之后可以一轮轮吵下去'),
            ),
            h('div', { style: { display: 'flex', gap: 10 } },
              h('input', {
                value: q, onChange: (e) => setQ(e.target.value),
                onKeyDown: (e) => { if (e.key === 'Enter') open() },
                placeholder: '比如：怎么看待知识付费这门生意',
                style: inputStyle,
              }),
              h('button', { type: 'button', className: 'mw-hot-btn', disabled: busy, onClick: open }, busy ? '开会中…' : '开会'),
            ),
            err ? h('div', { className: 'mw-err', style: { marginTop: 10 } }, err) : null,
          ),
          h('div', { className: 'mw-hot-group', style: { marginTop: 10 } },
            h('div', { className: 'mw-ghead' },
              h('span', { className: 'mw-glabel' }, '历次会议'),
              h('span', { className: 'mw-gnote' }, list.length + ' 场 · 勾选后可以批量导出'),
            ),
            h('div', { style: { display: 'flex', gap: 14, alignItems: 'center', padding: '10px 0' } },
              h('button', {
                type: 'button', className: 'mw-hot-btn',
                onClick: () => {
                  const nextPick = {}
                  if (!allOn) list.forEach((t) => { nextPick[t.id] = true })
                  setPicked(nextPick)
                },
              }, allOn ? '取消全选' : '全选'),
              h('button', {
                type: 'button', className: 'mw-hot-btn', disabled: expBusy || !pickedCount,
                style: !pickedCount ? { opacity: .38, cursor: 'not-allowed' } : null,
                onClick: () => exportMany(false),
              }, expBusy ? '正在导出…' : (pickedCount ? '导出选中 ' + pickedCount + ' 场' : '导出选中')),
              h('button', {
                type: 'button', className: 'mw-hot-btn', disabled: !pickedCount,
                style: !pickedCount
                  ? { opacity: .38, cursor: 'not-allowed' }
                  : { color: C.err, borderColor: 'color-mix(in srgb, ' + C.err + ' 45%, transparent)' },
                onClick: delMany,
              }, pickedCount ? '删除选中 ' + pickedCount + ' 场' : '删除选中'),
            ),
            exp ? h('div', {
              style: {
                margin: '6px 0 12px', padding: '10px 12px', borderRadius: 8,
                border: '1px solid ' + C.border, background: C.cell2,
                fontSize: 12, lineHeight: 1.8, color: C.sub, wordBreak: 'break-all',
              },
            }, '已导出 ' + exp.count + ' 场：' + exp.path + '（' + Math.round(exp.bytes / 1024) + ' KB）') : null,
            list.length === 0 ? h('div', { className: 'mw-empty' }, '还没有记录。建议题开一场。') : null,
            list.map((t) => h('div', {
              key: t.id, className: 'mw-hot-item',
              style: { cursor: 'pointer', display: 'flex', alignItems: 'flex-start', gap: 12 },
              onClick: () => openTopic(t.id),
            },
              h('input', {
                type: 'checkbox', checked: !!picked[t.id],
                onClick: (e) => e.stopPropagation(),
                onChange: (e) => setPicked((p) => ({ ...p, [t.id]: e.target.checked })),
                style: { marginTop: 4, flex: 'none' },
              }),
              h('div', { style: { flex: '1 1 auto', minWidth: 0 } },
                h('div', { className: 'mw-hot-title' }, t.question),
                h('div', { className: 'mw-hot-foot' },
                  h('span', { style: { color: C.sub } }, `${t.rounds} 轮 · ${t.followups} 次追问 · ${t.createdAt}`)),
              ),
            )),
          ),
        )
      }

      return h('div', { className: 'mw-root' },
        h('style', { key: 'mw-css' }, CSS),
        h('div', { className: 'mw-detail' },
          h('div', { className: 'mw-dhead' },
            h('button', { type: 'button', className: 'mw-back', onClick: onBack }, '‹ 工具列表'),
            topic ? h('button', {
              type: 'button', className: 'mw-back', style: { marginLeft: 10 },
              onClick: () => { setTopic(null); setAskFor(null); setSel(null); loadList() },
            }, '‹ 历次会议') : null,
            h('div', { className: 'mw-dtitle', style: { marginLeft: 10 } }, '圆桌会议'),
            h('div', { style: { flex: '1 1 auto' } }),
            h(ModelPicker, null),
            h('div', { className: 'mw-hot-meta' }, topic ? '存档中' : (busy ? '开会中…' : list.length + ' 场记录')),
          ),
          body,
        ),
      )
    }

    /* ---- 内容库：按「讲的是什么内容」分类，点标题就地展开全文 ---- */
    function LibraryPanel({ onBack, summary }) {
      const [topic, setTopic] = useState(null)
      const [source, setSource] = useState(null)
      const [list, setList] = useState(null)
      const [topics, setTopics] = useState([])
      const [loading, setLoading] = useState(true)
      const [openDoc, setOpenDoc] = useState(null)
      const [openAtoms, setOpenAtoms] = useState(null)   // {postId, total, list}
      const [ocr, setOcr] = useState(null)
      const [scan, setScan] = useState(null)
      const [scanning, setScanning] = useState(false)
      const [dash, setDash] = useState(null)

      useEffect(() => {
        const load = () => {
          fetch('/api/dsh-media/ocr/status').then((r) => r.json())
            .then((j) => { if (j && j.ok) setOcr(j) }).catch(() => { })
          fetch('/api/dsh-media/dash/stats').then((r) => r.json())
            .then((j) => { if (j && j.ok) setDash(j) }).catch(() => { })
        }
        load()
        const t = setInterval(load, 6000)
        return () => clearInterval(t)
      }, [])

      const doScan = () => {
        setScanning(true)
        fetch('/api/dsh-media/ocr/scan', { method: 'POST' })
          .then((r) => r.json())
          .then((j) => { if (j && j.ok) setScan(j) })
          .catch(() => { })
          .then(() => setScanning(false))
      }

      const loadAtoms = (pid) => {
        if (!pid) return
        if (openAtoms && openAtoms.postId === pid) { setOpenAtoms(null); return }
        fetch('/api/dsh-media/postatoms?id=' + encodeURIComponent(pid))
          .then((r) => r.json())
          .then((j) => {
            if (j && j.ok) setOpenAtoms({ postId: pid, total: j.total || 0, list: j.list || [] })
          })
          .catch(() => { })
      }

      const loadDoc = (id) => {
        if (!id) return
        fetch('/api/dsh-media/post?id=' + encodeURIComponent(id))
          .then((r) => r.text())
          .then((t) => { try { return JSON.parse(t) } catch { return null } })
          .then((j) => { if (j && j.ok) setOpenDoc(j) })
          .catch(() => { })
      }

      const [booksP, setBooksP] = useState(null)
      useEffect(() => {
        if (source !== 'books') return
        fetch('/api/dsh-media/books?limit=100')
          .then((r) => r.json())
          .then((j) => { if (j && j.ok) setBooksP(j) })
          .catch(() => { })
      }, [source])

      const loadBook = (id) => {
        if (!id) return
        fetch('/api/dsh-media/book?id=' + encodeURIComponent(id))
          .then((r) => r.json())
          .then((j) => { if (j && j.ok) setOpenDoc({ id: j.id, text: j.text, chars: j.chars, title: j.title }) })
          .catch(() => { })
      }

      const delPost = (pid) => {
        if (!pid) return
        const ok = window.confirm('彻底删除这一篇？\n\n连带删掉它拆出的知识点，删了不能恢复。')
        if (!ok) return
        fetch('/api/dsh-media/posts/delete', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ id: pid }),
        })
          .then((r) => r.json())
          .then((j) => { if (j && j.ok) setList((prev) => (prev || []).filter((x) => x.id !== pid)) })
          .catch(() => { })
      }

      useEffect(() => {
        let alive = true
        setLoading(true)
        const parts = ['/api/dsh-media/posts?limit=80']
        if (topic) parts.push('&topic=' + encodeURIComponent(topic))
        if (source) parts.push('&source=' + encodeURIComponent(source))
        fetch(parts.join(''))
          .then((r) => r.json())
          .then((j) => {
            if (!alive) return
            setList(j && j.ok ? j.list : [])
            if (j && j.ok && j.topics && j.topics.length) setTopics(j.topics)
            setLoading(false)
          })
          .catch(() => { if (alive) { setList([]); setLoading(false) } })
        return () => { alive = false }
      }, [topic, source])

      const total = (summary && summary.posts) || 0
      const fm = (x) => Number(x || 0).toLocaleString('en-US')
      const uncat = (topics.find((t) => t.name === '未分类') || {}).n || 0
      const named = topics.filter((t) => t.name !== '未分类')
      // 内容库总账（wbquery summary 提供）
      const bySrc = (summary && summary.bySource) || []
      const recent = (summary && summary.recent) || {}
      const topicDist = (summary && summary.topics) || []
      const tagTop = (summary && summary.tagTop) || []
      const wan = (x) => {
        const n = Number(x || 0)
        return n >= 1e8 ? (n / 1e8).toFixed(2) + ' 亿' : n >= 1e4 ? (n / 1e4).toFixed(0) + ' 万' : String(n)
      }
      const recentOf = recent || {}

      return h('div', { className: 'mw-root' },
        h('style', { key: 'mw-css' }, CSS),
        h('div', { className: 'mw-detail' },
          h('div', { className: 'mw-dhead' },
            h('button', { type: 'button', className: 'mw-back', onClick: onBack }, '‹ 工具列表'),
            h('div', { className: 'mw-dtitle' }, '内容库'),
            h('div', { className: 'mw-dtag' }, `四类来源 · 全部已分类`),
            (summary && summary.hiddenPosts) ? h('div', { className: 'mw-dtag', style: { opacity: .55 } },
              `已筛掉 ${summary.hiddenPosts} 篇`) : null,
          ),
          h('div', { className: 'mw-dbody' },
            // ===== 总账：四类来源 =====
            h('div', { style: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(150px,1fr))', gap: 10, marginBottom: 14 } },
              bySrc.length
                ? bySrc.map((s) => h('div', {
                  key: s.key,
                  style: {
                    border: '1px solid ' + C.border, borderRadius: 8, padding: '12px 14px',
                    background: C.cell, display: 'flex', flexDirection: 'column', gap: 4,
                  },
                },
                h('div', { style: { fontSize: 12.5, color: C.sub } }, s.key),
                h('div', { style: { fontSize: 26, fontWeight: 600, lineHeight: 1.1, color: C.gold } },
                  fm(s.n) + (s.unit ? ' ' + s.unit : '')),
                h('div', { style: { fontSize: 12, color: C.sub } },
                  wan(s.chars) + '字' +
                  (s.segments ? ' · ' + fm(s.segments) + ' 段' : '') +
                  (recentOf[s.key] ? ' · 近7天 +' + fm(recentOf[s.key]) : '')),
                ))
                : h('div', { style: { fontSize: 12.5, color: C.sub } }, '读取中…'),
            ),
            // ===== 分类分布（8 大类）=====
            h('div', { className: 'mw-hot-group', style: { marginBottom: 12 } },
              h('div', { className: 'mw-hot-gt' },
                h('span', { className: 'mw-hot-gt-label' }, '分类分布'),
                h('span', { className: 'mw-hot-gt-line' }),
                h('span', { style: { fontSize: 12, color: C.sub } }, '一本书可挂多个大类'),
              ),
              h('div', { style: { display: 'flex', gap: 8, flexWrap: 'wrap' } },
                topicDist.map((t) => h('span', {
                  key: t.name,
                  style: {
                    fontSize: 12.5, color: C.sub, border: '1px solid ' + C.border,
                    borderRadius: 99, padding: '3px 11px', background: C.cell,
                  },
                }, t.name + ' ' + fm(t.n)))),
            ),
            // ===== 常用标签 =====
            tagTop.length ? h('div', { className: 'mw-hot-group', style: { marginBottom: 12 } },
              h('div', { className: 'mw-hot-gt' },
                h('span', { className: 'mw-hot-gt-label' }, '高频标签'),
                h('span', { className: 'mw-hot-gt-line' }),
                h('span', { style: { fontSize: 12, color: C.sub } }, '前 16 个'),
              ),
              h('div', { style: { display: 'flex', gap: 7, flexWrap: 'wrap' } },
                tagTop.slice(0, 16).map((t) => h('span', {
                  key: t.name,
                  style: {
                    fontSize: 12, color: C.sub, border: '1px solid ' + C.border,
                    borderRadius: 4, padding: '2px 8px', background: 'transparent',
                  },
                }, t.name + ' ' + t.n))),
            ) : null,
            h('div', { className: 'mw-chips mw-rows' },
              [['全部', null], ['推文', '主贴'], ['抖音文案', 'douyin'], ['直播', 'live'], ['书', 'books']].map(([label, k]) => h('button', {
                key: label,
                type: 'button',
                className: 'mw-chip' + (source === k ? ' on' : ''),
                onClick: () => setSource(k),
              }, k === null ? label + ' ' + fm(bySrc.reduce((a, b) => a + (b.n || 0), 0)) : label)),
            ),
            source === 'books' ? null : h('div', { className: 'mw-chips' },
              h('button', {
                type: 'button',
                className: 'mw-chip' + (topic === null ? ' on' : ''),
                onClick: () => setTopic(null),
              }, `全部 ${fm(topicDist.reduce((a, b) => a + (b.n || 0), 0))}`),
              topicDist.map((t) => h('button', {
                key: t.name,
                type: 'button',
                className: 'mw-chip' + (topic === t.name ? ' on' : ''),
                onClick: () => setTopic(t.name),
              }, `${t.name} ${fm(t.n)}`)),
            ),
            source === 'books'
              ? (booksP
                ? (booksP.list.length
                  ? booksP.list.map((b, i) => {
                    const isOpen = !!(openDoc && openDoc.id === b.id)
                    return h('div', {
                      key: b.id + '_' + i,
                      className: 'mw-post',
                      style: { cursor: 'pointer' },
                      onClick: () => { if (isOpen) setOpenDoc(null); else loadBook(b.id) },
                    },
                    h('div', { className: 'mw-post-top' },
                      b.category ? h('span', { className: 'mw-topic-tag' }, b.category) : null,
                      h('span', { className: 'mw-post-date' }, (b.pages || 0) + ' 页'),
                      h('span', { className: 'mw-post-kind' }, (b.chunks || 0) + ' 块'),
                    ),
                    h('div', { className: 'mw-post-text' }, isOpen ? (openDoc.text || '') : ('《' + b.title + '》')),
                    h('div', { className: 'mw-atom-foot' },
                      h('span', { style: { color: C.accent } }, isOpen ? '收起 ⌃' : '点开看全文 ›')),
                    )
                  })
                  : h('div', { className: 'mw-empty' }, '书库里还没有可读的书'))
                : h('div', { className: 'mw-empty' }, '读取中…'))
              : loading
              ? h('div', { className: 'mw-empty' }, '读取中…')
              : (list && list.length)
                ? list.map((p, i) => {
                  const isOpen = !!(openDoc && openDoc.id === p.id)
                  return h('div', {
                    key: (p.id || i) + '_' + i,
                    className: 'mw-post',
                    style: { cursor: 'pointer' },
                    onClick: () => { if (isOpen) setOpenDoc(null); else loadDoc(p.id) },
                    title: isOpen ? '点一下收起' : '点开看全文',
                  },
                    h('div', { className: 'mw-post-top' },
                      p.topic ? h('span', { className: 'mw-topic-tag' }, p.topic) : null,
                      h('span', { className: 'mw-post-date' }, p.date || ''),
                      p.kind ? h('span', { className: 'mw-post-kind' }, kindCn(p.kind)) : null,
                    ),
                    h('div', {
                      className: 'mw-post-text',
                      style: isOpen ? { display: 'block', WebkitLineClamp: 'unset', overflow: 'visible' } : null,
                    }, isOpen ? (openDoc.text || '') : (p.text || '')),
                    h('div', { className: 'mw-atom-foot', style: { display: 'flex', gap: 14, flexWrap: 'wrap' } },
                      h('span', { style: { color: C.accent } }, isOpen ? '收起 ⌃' : '点开看全文 ›'),
                      p.atomCount ? h('span', {
                        style: { color: C.accent, cursor: 'pointer' },
                        onClick: (e) => { e.stopPropagation(); loadAtoms(p.id) },
                      }, (openAtoms && openAtoms.postId === p.id) ? '收起拆解 ⌃' : `拆出 ${p.atomCount} 条 ›`) : null,
                      p.url ? h('a', {
                        href: p.url, target: '_blank', rel: 'noreferrer',
                        onClick: (e) => e.stopPropagation(),
                      }, '原文 ↗') : null,
                      h('span', {
                        style: { color: C.err, cursor: 'pointer' },
                        onClick: (e) => { e.stopPropagation(); delPost(p.id) },
                      }, '删掉')),
                    (openAtoms && openAtoms.postId === p.id)
                      ? h('div', { className: 'mw-src', onClick: (e) => e.stopPropagation() },
                        h('div', { className: 'mw-src-h' }, `这篇拆出 ${openAtoms.total} 条`),
                        openAtoms.list.map((a, k) => h('div', { key: 'a' + k, className: 'mw-src-atom' },
                          h('span', { className: 'mw-atom-type t-' + (a.type || 'other'), style: { fontSize: 10, marginRight: 8 } }, typeCn(a.type)),
                          a.knowledge || '')))
                      : null,
                  )
                })
                : h('div', { className: 'mw-empty' }, '没有数据'),
          ),
        ),
      )
    }

    function IdeaPanel({ onBack, idea, autoSt }) {
      const data = idea && idea.data
      const items = (data && data.items) || []
      const job = autoSt && autoSt.idea ? autoSt.idea : null
      const autoLine = autoLong(job, '灵感')

      const typeLabel = { principle: '原则', method: '方法', insight: '洞察', 'anti-pattern': '反模式', case: '案例', tool: '工具' }

      // 每条的结果：key -> { text, busy }
      const [ask, setAsk] = useState({})
      const [selPick, setSelPick] = useState(null)

      const runExplain = async (key, text, context) => {
        setAsk((p) => ({ ...p, [key]: { text: '', busy: true } }))
        try {
          const r = await fetch('/api/dsh-media/explain', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text, kind: 'explain', context }),
          })
          if (!r.body) throw new Error('无响应流')
          const reader = r.body.getReader()
          const dec = new TextDecoder()
          let acc = ''
          for (; ;) {
            const { done, value } = await reader.read()
            if (done) break
            acc += dec.decode(value, { stream: true })
            setAsk((p) => ({ ...p, [key]: { text: acc, busy: true } }))
          }
          setAsk((p) => ({ ...p, [key]: { text: acc, busy: false } }))
        } catch (e) {
          setAsk((p) => ({ ...p, [key]: { text: '[失败] ' + String(e && e.message ? e.message : e), busy: false } }))
        }
      }

      // 划词后点「这段细说」；没选中就收起按钮
      const onSelectText = () => {
        try {
          const sel = window.getSelection()
          const t = sel ? String(sel).trim() : ''
          setSelPick(t.length >= 4 ? t : null)
        } catch { setSelPick(null) }
      }

      return h('div', { className: 'mw-root' },
        h('style', { key: 'mw-css' }, CSS),
        h('div', { className: 'mw-detail' },
          h('div', { className: 'mw-dhead' },
            h('button', { type: 'button', className: 'mw-back', onClick: onBack }, '‹ 工具列表'),
            h('div', { className: 'mw-dtitle' }, '每日灵感'),
            data ? h('div', { className: 'mw-dtag' }, data.date) : null,
            h('div', { style: { flex: '1 1 auto' } }),
            h(ModelPicker, null),
            selPick ? h('button', {
              type: 'button', className: 'mw-hot-btn',
              onMouseDown: (e) => e.preventDefault(),
              onClick: () => { runExplain('__sel__', selPick, null); setSelPick(null) },
            }, '这段细说') : null,
            data ? h('div', { className: 'mw-hot-meta' },
              `${items.length} 条 · 素材 → 角度 → 问题`) : null,
            autoLine ? h('div', { className: 'mw-hot-meta', style: { color: job && job.error ? C.warn : C.sub } }, autoLine) : null,
          ),
          h('div', { className: 'mw-dbody', onMouseUp: onSelectText },
            items.length === 0
              ? h('div', { className: 'mw-empty' },
                job && job.running
                  ? '今天还没生成灵感，后台正在挑素材（大约 1 分钟），跑完自动出现。'
                  : '今天还没生成灵感。后台每天会自动生成；如果一直空着，看下面那行报错。' + (autoLine ? ' ' + autoLine : ''))
              : items.map((it, i) => {
                const key = it.id || String(i)
                const a = ask[key]
                return h('div', { key, className: 'mw-hot-group' },
                  h('div', { className: 'mw-hot-gt' },
                    h('span', { className: 'mw-hot-gt-label' }, `灵感 ${String(i + 1).padStart(2, '0')}`),
                    h('span', { className: 'mw-hot-gt-line' }),
                    h('span', { className: 'mw-hot-gt-label' },
                      [typeLabel[it.type] || it.type, it.confidence].filter(Boolean).join(' · ')),
                  ),
                  // ① 素材
                  h('div', { className: 'mw-idea-src' },
                    h('span', { className: 'mw-idea-no' }, '素材'),
                    h('span', { className: 'mw-idea-txt' }, it.knowledge),
                  ),
                  // ② 角度
                  it.angle ? h('div', { className: 'mw-insight', style: { marginTop: 10 } },
                    h('span', { className: 'mw-insight-tag' }, 'AI 说 · 怎么用'), it.angle) : null,
                  // ③ 问题
                  it.question ? h('div', { className: 'mw-idea-q' },
                    h('span', { className: 'mw-idea-q-tag' }, '能问出'), it.question
                  ) : null,

                  // ④ 讲透
                  h('div', { style: { display: 'flex', gap: 8, marginTop: 10, alignItems: 'center' } },
                    h('button', {
                      type: 'button', className: 'mw-hot-btn',
                      disabled: !!(a && a.busy),
                      onClick: () => runExplain(key, it.knowledge, null),
                    }, a && a.busy ? '正在讲…' : (a ? '重新讲' : '让 AI 讲透这条')),
                    a ? h('span', { className: 'mw-hot-meta' }, '划选任意文字可「这段细说」') : null,
                  ),
                  a && a.text ? h('div', { className: 'mw-explain' }, a.text) : null,

                  it.url ? h('div', { className: 'mw-hot-foot' },
                    h('a', { href: it.url, target: '_blank', rel: 'noreferrer' }, '原始出处'),
                  ) : null,
                )
              }),
            // 划词结果
            ask['__sel__'] ? h('div', { style: { marginTop: 18 } },
              h('div', { className: 'mw-hot-gt' },
                h('span', { className: 'mw-hot-gt-label' }, '你选中的那段'),
                h('span', { className: 'mw-hot-gt-line' }),
              ),
              h('div', { className: 'mw-explain' }, ask['__sel__'].text || '正在讲…'),
            ) : null,
          ),
        ),
      )
    }

    function CapturePanel({ onBack }) {
      const [state, setState] = useState({ running: false, gateOpen: false, items: [], total: 0 })
      const [ask, setAsk] = useState(null)       // 待确认的链接数组
      const [jobs, setJobs] = useState([])       // 后端采集队列
      const [counts, setCounts] = useState({})
      const [err, setErr] = useState(null)
      const [openDoc, setOpenDoc] = useState(null)
      const [recent, setRecent] = useState([])
      const [smartUrl, setSmartUrl] = useState('')
      const [smartMsg, setSmartMsg] = useState(null)
      const [smartBusy, setSmartBusy] = useState(false)
      const [watchList, setWatchList] = useState([])
      const [live, setLive] = useState(null)
      const [xhsFollow, setXhsFollow] = useState(null)
      const [xhsBusy, setXhsBusy] = useState(false)
      const [openMsg, setOpenMsg] = useState(null)
      const tickRef = useRef(0)

      const loadWatch = () => {
        fetch('/api/dsh-media/live/watchlist')
          .then((r) => r.text())
          .then((t) => { try { return JSON.parse(t) } catch { return null } })
          .then((j) => { if (j && j.ok) setWatchList(j.items || []) })
          .catch(() => { })
      }

      const loadXhsFollow = () => {
        fetch('/api/dsh-media/xhs-follow')
          .then((r) => r.text())
          .then((t) => { try { return JSON.parse(t) } catch { return null } })
          .then((j) => { if (j && !j.empty) setXhsFollow(j) })
          .catch(() => { })
      }

      const scanXhsFollow = () => {
        if (xhsBusy) return
        setXhsBusy(true)
        fetch('/api/dsh-media/xhs-follow/scan', { method: 'POST' })
          .then((r) => r.text())
          .then((t) => { try { return JSON.parse(t) } catch { return null } })
          .then((j) => setXhsFollow(j || { ok: false, error: '没返回' }))
          .catch(() => setXhsFollow({ ok: false, error: '请求失败' }))
          .finally(() => setXhsBusy(false))
      }

      const smartSubmit = () => {
        const url = (smartUrl || '').trim()
        if (!url) return
        setSmartBusy(true)
        setSmartMsg(null)
        fetch('/api/dsh-media/capture/smart', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ url }),
        })
          .then((r) => r.text())
          .then((t) => { try { return JSON.parse(t) } catch { return null } })
          .then((j) => {
            if (!j || !j.ok) { setSmartMsg({ ok: false, text: '判断失败：' + (j && j.error ? j.error : '接口没响应') }); return }
            let text = j.label || ''
            if (j.kind === 'profile') text += ' · ' + (j.message || '已加入监控')
            else if (j.kind === 'video') text += ' · ' + (j.duplicate ? '这条已经在队列里了' : (j.queued ? '已进采集队列' : '入队失败'))
            else if (j.kind === 'live') text += ' · ' + (j.message || '')
            setSmartMsg({ ok: j.kind !== 'unknown', text })
            if (j.kind === 'profile') loadWatch()
            if (j.kind === 'video') { localStorage.removeItem('nope'); }
            setSmartUrl('')
          })
          .catch(() => setSmartMsg({ ok: false, text: '请求失败，宿主可能没重启' }))
          .then(() => setSmartBusy(false))
      }

      const loadDoc = (id) => {
        if (!id) return
        fetch('/api/dsh-media/post?id=' + encodeURIComponent(id))
          .then((r) => r.text())
          .then((t) => { try { return JSON.parse(t) } catch { return null } })
          .then((j) => { if (j && j.ok) setOpenDoc(j); else setErr('读不到这篇逐字稿') })
          .catch(() => setErr('读不到这篇逐字稿'))
      }

      // 容错解析：接口没注册时返回纯文本 "not found"，不能直接当 JSON
      const safeJson = async (url, opts) => {
        const r = await fetch(url, opts)
        const txt = await r.text()
        try { return JSON.parse(txt) } catch {
          const hint = /not found/i.test(txt)
            ? '接口未注册 — 宿主没加载新版代码，需要重启 DSH'
            : `HTTP ${r.status}：${txt.slice(0, 60)}`
          throw new Error(hint)
        }
      }

      const poll = () => {
        safeJson('/api/dsh-media/clip/poll')
          .then((j) => {
            if (!j || !j.ok) { setErr('哨兵接口异常'); return }
            setErr(null)
            setState((p) => ({ ...p, running: j.running, gateOpen: j.gateOpen, total: j.total }))
            const items = j.items || []
            if (items.length && !j.gateOpen) {
              setAsk((prev) => {
                const merged = prev ? prev.slice() : []
                for (const it of items) if (!merged.some((x) => x.url === it.url)) merged.push(it)
                return merged
              })
            }
          })
          .catch((e) => setErr(String(e && e.message ? e.message : e)))
        // 采集队列状态
        fetch('/api/dsh-media/capture/status')
          .then((r) => r.text())
          .then((t) => { try { return JSON.parse(t) } catch { return null } })
          .then((j) => {
            if (j && j.ok) { setJobs(j.items || []); setCounts(j.counts || {}) }
          })
          .catch(() => { })
      }

      React.useEffect(() => {
        const t2 = setInterval(() => {
          const k = ++tickRef.current
          if (k === 1 || k % 5 === 0) {
            fetch('/api/dsh-media/posts?limit=8&order=created')
              .then((r) => r.text())
              .then((t) => { try { return JSON.parse(t) } catch { return null } })
              .then((j) => { if (j && j.ok && j.list) setRecent(j.list.slice(0, 8)) })
              .catch(() => { })
          }
        }, 2000)
        fetch('/api/dsh-media/clip/start', { method: 'POST' }).catch(() => { })
        loadXhsFollow()
        const t = setInterval(poll, 2000)
        poll()
        return () => {
          clearInterval(t)
          try { clearInterval(t2) } catch { }
          // 被动模式：面板关掉也不停哨兵，宿主那边一直在收
        }
      }, [])

      React.useEffect(() => {
        const t3 = setInterval(() => {
          fetch('/api/dsh-media/live/rec')
            .then((r) => r.text())
            .then((t) => { try { return JSON.parse(t) } catch { return null } })
            .then((j) => { if (j && j.ok) setLive(j) })
            .catch(() => { })
        }, 3000)
        return () => clearInterval(t3)
      }, [])

      const openGate = () => {
        fetch('/api/dsh-media/clip/gate', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ open: true }),
        }).then((r) => r.json()).then(() => {
          setState((p) => ({ ...p, gateOpen: true }))
          // 开闸前已收到的这批也直接入队
          if (ask && ask.length) {
            for (const it of ask) {
              fetch('/api/dsh-media/capture/queue', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url: it.url }),
              }).catch(() => { })
            }
          }
          setAsk(null)
        }).catch(() => setErr('开闸失败'))
      }

      const toggleRecord = () => {
        const url = (live && live.paused) ? '/api/dsh-media/live/resume' : '/api/dsh-media/live/pause'
        fetch(url, { method: 'POST' })
          .then(() => fetch('/api/dsh-media/live/rec'))
          .then((r) => r.json())
          .then((j) => { if (j && j.ok) setLive(j) })
          .catch(() => { })
      }

      const kpi = (label, val, sub, color) => h('div', {
        style: { border: '1px solid ' + C.border, background: C.cell, borderRadius: 6, padding: '12px 14px' },
      },
      h('div', { style: { fontSize: 12.5, color: C.sub, marginBottom: 4 } }, label),
      h('div', { style: { fontSize: 30, fontWeight: 700, lineHeight: 1.12, color: color || C.text, fontVariantNumeric: 'tabular-nums' } }, String(val)),
      h('div', { style: { fontSize: 11.5, color: C.sub, marginTop: 3 } }, sub || ''))

      return h('div', { className: 'mw-root' },
        h('style', { key: 'mw-css' }, CSS),
        h('div', { className: 'mw-detail' },
          h('div', { className: 'mw-dhead' },
            h('button', { type: 'button', className: 'mw-back', onClick: onBack }, '‹ 工具列表'),
            h('div', { className: 'mw-dtitle' }, '采集台'),
            h('div', { style: { flex: '1 1 auto' } }),
            h(ModelPicker, null),
            h('span', { className: 'mw-hot-meta' },
              state.gateOpen ? '哨兵已开闸 · 持续监听' : (state.running ? '哨兵运行中 · 等待授权' : '哨兵未启动')),
          ),
          h('div', { className: 'mw-dbody' },
            err ? h('div', { className: 'mw-err' }, err) : null,

            // 数据总览（大数字）
            !live ? null : h('div', { style: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(126px, 1fr))', gap: 12, marginBottom: 18 } },
              kpi('关注在播', (live.follow || {}).live || 0, '关注主播正在播',
                ((live.follow || {}).live ? C.ok : C.sub)),
              kpi('正在录', (live.rec.active || []).length, '个主播', (live.rec.active || []).length ? C.ok : C.sub),
              kpi('待转写', live.queue.pending || 0, live.queue.pendingMb ? live.queue.pendingMb + ' MB 积压' : '没有积压'),
              kpi('转写中', (live.transcribe || {}).running || 0, ((live.transcribe || {}).parallel || 1) > 1 ? (live.transcribe.parallel + ' 路并行') : '单路'),
              kpi('已转完', live.queue.done || 0, '今天 ' + ((live.transcribe || {}).doneToday || 0) + ' 份'),
              kpi('D 盘剩余', live.disk ? live.disk.freeGb : '—', 'GB', live.disk && live.disk.freeGb < 100 ? C.warn : C.text),
            ),

            // 路径设置
            h('div', { className: 'mw-hot-group', style: { marginBottom: 18 } },
              h('div', { className: 'mw-hot-gt' },
                h('span', { className: 'mw-hot-gt-label' }, '路径设置'),
                h('span', { className: 'mw-hot-gt-line' }),
                h('span', { className: 'mw-hot-gt-label', style: openMsg ? { color: C.gold } : null }, openMsg ? openMsg.text : '点「打开」看文件夹'),
              ),
              live && live.paths ? h('div', { style: { border: '1px solid ' + C.border, borderRadius: 6, overflow: 'hidden' } },
                [
                  ['直播录制', live.paths.rec, 'rec'],
                  ['逐字稿', live.paths.transcript, 'transcript'],
                  ['书库', live.paths.book, 'book'],
                ].map(([label, p, key]) => h('div', {
                  key,
                  style: { display: 'flex', alignItems: 'center', gap: 12, padding: '10px 14px', borderBottom: '1px solid ' + C.border },
                },
                h('span', { style: { width: 76, fontSize: 12.5, color: C.sub, flex: '0 0 auto' } }, label),
                h('span', { style: { flex: 1, fontSize: 12.5, fontFamily: 'Consolas, monospace', color: '#cfd4dd', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' } }, p),
                h('button', {
                  type: 'button', className: 'mw-hot-btn',
                  onClick: () => {
                    fetch('/api/dsh-media/open', {
                      method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ which: key }),
                    })
                      .then((r) => r.json())
                      .then((j) => {
                        if (j && j.ok) {
                          const a = String(j.action || '')
                          const msg = a.indexOf('activated') === 0
                            ? '已经开着，切到最前面了'
                            : (a.indexOf('opened') === 0 ? '打开了' : (a || '打开了'))
                          setOpenMsg({ key, text: msg })
                        } else setOpenMsg({ key, text: '没打开：' + ((j && j.error) || '未知原因') })
                      })
                      .catch(() => setOpenMsg({ key, text: '请求失败，宿主可能没重启' }))
                  },
                }, '打开'),
                )),
              ) : h('div', { style: { fontSize: 12.5, color: C.sub } }, '读取中…'),
            ),

            // 平台分布 + 在录明细
            h('div', { className: 'mw-hot-group', style: { marginBottom: 18 } },
              h('div', { className: 'mw-hot-gt' },
                h('span', { className: 'mw-hot-gt-label' }, '直播录制'),
                h('span', { className: 'mw-hot-gt-line' }),
                h('span', { className: 'mw-hot-gt-label' },
                  !live ? '读取中…' : ((live.rec.active || []).length ? '正在录 ' + live.rec.active.length + ' 个' : '当前没有在录')),
                live ? h('button', {
                  type: 'button', className: 'mw-hot-btn', style: { marginLeft: 10 },
                  onClick: toggleRecord,
                }, live.paused ? '开始录制' : '停止录制') : null,
              ),
              !live ? null : h('div', null,
                h('div', { style: { display: 'flex', gap: 12, flexWrap: 'wrap', marginBottom: 12 } },
                  (live.platforms || []).map((p) => h('div', {
                    key: p.key,
                    style: { flex: '1 1 150px', minWidth: 140, border: '1px solid ' + C.border, borderRadius: 6, padding: '10px 12px', background: C.cell },
                  },
                  h('div', { style: { fontSize: 12.5, color: C.sub } }, p.label),
                  h('div', { style: { fontSize: 24, fontWeight: 700, lineHeight: 1.3, color: p.active.length ? C.ok : C.text, fontVariantNumeric: 'tabular-nums' } },
                    p.active.length ? p.active.length : '0'),
                  h('div', { style: { fontSize: 11.5, color: C.sub, marginTop: 2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' } },
                    p.active.length
                      ? p.active.map((a) => a.anchor).join('、')
                      : (p.idle[0] ? '最近 ' + Math.round(p.idle[0].idleSec / 60) + ' 分钟前录过' : '没有记录')),
                  )),
                  (live.known || []).filter((k) => !(live.platforms || []).some((p) => p.label === k)).map((k) => {
                    const mon = (live.monitoredBy && live.monitoredBy[k]) || 0
                    return h('div', {
                      key: 'k' + k,
                      style: { flex: '1 1 150px', minWidth: 140, border: '1px dashed ' + (mon ? C.gold : C.border), borderRadius: 6, padding: '10px 12px' },
                    },
                    h('div', { style: { fontSize: 12.5, color: C.sub } }, k),
                    h('div', { style: { fontSize: mon ? 17 : 20, fontWeight: 600, color: mon ? C.gold : C.sub, opacity: mon ? 1 : .7, lineHeight: 1.3 } }, mon ? '待开播' : '未接入'),
                    h('div', { style: { fontSize: 12.5, color: C.sub, opacity: .8, marginTop: 2 } }, mon ? ('开播自动录 · ' + mon + ' 个地址') : '给直播间地址就能接'))
                  }),
                ),
                (live.follow && live.follow.live) ? h('div', { style: { fontSize: 12.5, color: C.sub, marginBottom: 8 } },
                  '关注里正在播：' + (live.follow.anchors || []).map((a) => a.name).filter(Boolean).slice(0, 10).join('、')) : null,
                (live.rec.active || []).length ? h('div', { style: { maxHeight: 230, overflowY: 'auto' } },
                  live.rec.active.map((a) => h('div', {
                    key: a.platform + a.anchor,
                    style: { display: 'flex', alignItems: 'center', gap: 10, padding: '8px 2px', borderBottom: '1px solid ' + C.border },
                  },
                  h('i', { style: { width: 7, height: 7, borderRadius: '50%', background: C.ok, flex: '0 0 auto' } }),
                  h('span', { style: { fontSize: 11.5, color: C.sub, border: '1px solid ' + C.border, borderRadius: 3, padding: '0 6px', flex: '0 0 auto' } }, a.platform),
                  h('span', { style: { fontSize: 13.5, flex: '1 1 auto', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' } }, a.anchor),
                  h('span', { style: { fontSize: 12.5, color: C.sub, fontVariantNumeric: 'tabular-nums' } }, (a.mb >= 1024 ? (a.mb / 1024).toFixed(1) + ' GB' : a.mb + ' MB') + ' · ' + a.files + ' 段'),
                  h('span', { style: { fontSize: 12.5, color: a.idleSec < 25 ? C.ok : C.sub, width: 76, textAlign: 'right' } }, a.idleSec < 25 ? '录制中' : a.idleSec + ' 秒前'),
                  )))
                  : h('div', { style: { fontSize: 12.5, color: C.sub, lineHeight: 1.75 } },
                    '现在没有主播在录。要开录：双击 E:\\tools\\DouyinLiveRecorder\\启动全部.bat —— 只录 URL_config.ini 里没被注释的直播间。',
                    (live.rec.idle || []).length ? h('div', { style: { marginTop: 6 } },
                      '最近录过：' + live.rec.idle.slice(0, 3).map((a) => a.anchor + '（' + Math.round(a.idleSec / 60) + ' 分钟前）').join('、')) : null),
                h('div', { style: { marginTop: 10, display: 'flex', gap: 18, flexWrap: 'wrap', fontSize: 12.5, color: C.sub } },
                  h('span', null, '清单 ' + (live.monitored || 0) + ' 个地址'),
                  h('span', null, '转写进程 ' + (live.queue.pipelineAlive ? '在跑' : '没开')),
                  live.queue.whitelist.length ? h('span', null, '只转写：' + live.queue.whitelist.join('、')) : h('span', null, '白名单为空 = 全转'),
                ),
              ),
            ),

            // 小红书关注里谁在播
            h('div', { style: { border: '1px solid ' + C.line, background: C.panel, borderRadius: 4, padding: '14px 16px', marginBottom: 16 } },
              h('div', { style: { display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 } },
                h('div', { style: { fontSize: 14, fontWeight: 600 } }, '小红书关注里谁在播'),
                h('div', { style: { flex: '1 1 auto' } }),
                h('button', {
                  type: 'button', className: 'mw-hot-btn', disabled: xhsBusy, onClick: scanXhsFollow,
                  style: { fontSize: 12.5 },
                }, xhsBusy ? '查着…会弹个小窗口' : '查一下'),
              ),
              !xhsFollow
                ? h('div', { style: { fontSize: 12.5, color: C.sub, lineHeight: 1.75 } },
                  '还没查过。点「查一下」，会弹一个浏览器窗口读你的关注页，十几秒后自动关掉。',
                  h('div', { style: { marginTop: 2, opacity: .75 } }, '为什么要弹窗口：小红书对关注页单独设了风控，后台悄悄读会被判「账号异常」。'))
                : xhsFollow.ok === false
                  ? h('div', { style: { fontSize: 12.5, color: C.err, lineHeight: 1.75 } }, '没查成：' + (xhsFollow.error || xhsFollow.hint || '未知原因'))
                  : h('div', null,
                    h('div', { style: { fontSize: 12.5, color: C.sub, marginBottom: 8 } },
                      (xhsFollow.at || '') + ' · 关注 ' + (xhsFollow.total || 0) + ' 人 · 在播 ' + ((xhsFollow.live || []).length) + ' 人'),
                    (xhsFollow.live || []).length
                      ? h('div', { style: { display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 8 } },
                        xhsFollow.live.map((x) => h('span', {
                          key: x.name,
                          style: { fontSize: 13.5, color: C.gold, border: '1px solid ' + C.gold, borderRadius: 4, padding: '3px 10px', fontWeight: 600 },
                        }, '● ' + x.name)))
                      : h('div', { style: { fontSize: 13, color: C.sub, marginBottom: 8 } }, '现在没人播。'),
                    h('div', { style: { fontSize: 12.5, color: C.sub, lineHeight: 1.8 } },
                      '关注的人：' + ((xhsFollow.items || []).map((x) => x.name).join('、') || '—')),
                  ),
            ),

            // 智能分诊：粘一条链接，自动判主页/视频并分流
            h('div', { style: { border: '1px solid ' + C.line, background: C.panel, borderRadius: 4, padding: '14px 16px', marginBottom: 16 } },
              h('div', { style: { fontSize: 14, fontWeight: 600, marginBottom: 4 } }, '粘链接，自动分流'),
              h('div', { style: { fontSize: 12.5, color: C.sub, lineHeight: 1.6, marginBottom: 10 } },
                '主页 → 加进直播监控（等开播）；视频 → 进文案采集队列。分享文案整段粘进来也行。'),
              h('div', { style: { display: 'flex', gap: 10 } },
                h('input', {
                  type: 'text',
                  placeholder: 'https://www.douyin.com/user/... 或 https://v.douyin.com/...',
                  value: smartUrl,
                  onChange: (e) => setSmartUrl(e.target.value),
                  onKeyDown: (e) => { if (e.key === 'Enter') smartSubmit() },
                  style: { flex: '1 1 auto', background: '#12151c', border: '1px solid ' + C.line, borderRadius: 3, color: C.text, padding: '9px 12px', fontSize: 13.5, outline: 'none' },
                }),
                h('button', { type: 'button', className: 'mw-hot-btn', onClick: smartSubmit, disabled: smartBusy },
                  smartBusy ? '判断中…' : '分流'),
              ),
              smartMsg ? h('div', { style: { marginTop: 10, fontSize: 13, color: smartMsg.ok ? '#6fbf8f' : '#e2b34a', lineHeight: 1.6 } }, smartMsg.text) : null,
              watchList.length ? h('div', { style: { marginTop: 10, fontSize: 12.5, color: C.sub, lineHeight: 1.8 } },
                '已盯住 ' + watchList.length + ' 个主播，开播就录：',
                watchList.slice(0, 3).map(function (w, i) { return h('div', { key: i, style: { color: '#cfd4dd' } }, '· ' + String(w.url || '').slice(0, 62)) })) : null,
            ),

            // 待授权提示
            ask && ask.length ? h('div', { className: 'mw-clip-ask' },
              h('div', { style: { fontSize: 14, fontWeight: 600, marginBottom: 6 } },
                `发现 ${ask.length} 条抖音链接，要开始采集吗？`),
              h('div', { style: { fontSize: 12, color: C.sub, lineHeight: 1.6, marginBottom: 10 } },
                '点「是」之后我会一直监听剪贴板，你连续复制多少条都会自动收下，不再打断你。'),
              h('div', { style: { display: 'flex', gap: 10 } },
                h('button', { type: 'button', className: 'mw-hot-btn', onClick: openGate }, '是，开始采集'),
                h('button', { type: 'button', className: 'mw-hot-btn', onClick: () => {
                  for (const it of ask) {
                    fetch('/api/dsh-media/capture/queue', {
                      method: 'POST', headers: { 'Content-Type': 'application/json' },
                      body: JSON.stringify({ url: it.url }),
                    }).catch(() => { })
                  }
                  setAsk(null)
                } }, '先收下这批'),
              ),
              h('div', { style: { marginTop: 12, fontSize: 11, color: C.sub, opacity: .8 } },
                ask.slice(0, 5).map((x) => h('div', { key: x.url, style: { marginBottom: 4 } }, '· ' + x.url)),
              ),
            ) : null,

            // 说明
            !ask && !jobs.length ? h('div', { className: 'mw-empty' },
              state.gateOpen
                ? '哨兵在跑。去抖音点「分享 → 复制链接」，复制完回来这里，链接会自动出现并开始转写。'
                : '正在监听剪贴板。复制一条抖音链接试试，我会在这里问你。') : null,

            // 逐字稿（就地展开）
            openDoc ? h('div', { className: 'mw-hot-group' },
              h('div', { className: 'mw-hot-gt' },
                h('span', { className: 'mw-hot-gt-label' }, '逐字稿'),
                h('span', { className: 'mw-hot-gt-line' }),
                h('button', { type: 'button', className: 'mw-hot-btn', onClick: () => setOpenDoc(null) }, '收起'),
              ),
              h('div', { style: { fontSize: 12, color: C.sub, marginBottom: 8 } },
                [(openDoc.chars || 0) + ' 字', openDoc.date].filter(Boolean).join(' · ')),
              h('div', {
                style: {
                  whiteSpace: 'pre-wrap', lineHeight: 1.75, fontSize: 13.5,
                  maxHeight: 380, overflowY: 'auto', padding: '12px 14px',
                  background: C.cell2, border: '1px solid ' + C.border, borderRadius: 10,
                },
              }, openDoc.text || '（空）'),
            ) : null,

            // 视频转写（粘进来的抖音视频）
            h('div', { className: 'mw-hot-group' },
              h('div', { className: 'mw-hot-gt' },
                h('span', { className: 'mw-hot-gt-label' }, '视频转写'),
                h('span', { className: 'mw-hot-gt-line' }),
                h('span', { className: 'mw-hot-gt-label' },
                  `待转写 ${counts.pending || 0} · 转写中 ${counts.running || 0} · 完成 ${counts.done || 0}${counts.failed ? ' · 失败 ' + counts.failed : ''}`),
                counts.failed ? h('button', {
                  type: 'button', className: 'mw-hot-btn', style: { marginLeft: 10 },
                  onClick: () => {
                    fetch('/api/dsh-media/capture/retry', {
                      method: 'POST', headers: { 'content-type': 'application/json' }, body: '{}',
                    }).then(() => poll()).catch(() => { })
                  },
                }, '全部重试') : null,
              ),
              jobs.length ? null : h('div', { style: { fontSize: 12.5, color: C.sub, lineHeight: 1.7 } },
                '还没有粘过视频链接。抖音里点「分享 → 复制链接」，粘进上面的框，会自动下载音频并转成逐字稿。'),
              jobs.slice(0, 8).map((x) => {
                const st = x.status
                const failLabel = x.step === 'fetch' ? '下载失败'
                  : x.step === 'ffmpeg' ? '音频转换失败'
                    : x.step === 'asr' ? '转写失败'
                      : '处理失败'
                const label = st === 'pending' ? '排队中'
                  : st === 'running' ? '正在转写…'
                    : st === 'duplicate' ? '库里已有 · 不重复录入'
                      : st === 'done' ? `已完成 · ${x.result && x.result.chars ? x.result.chars + ' 字' : ''}`
                        : st === 'cancelled' ? '已取消' : failLabel
                const color = st === 'done' ? C.ok : st === 'failed' ? C.err : st === 'duplicate' ? C.accent : C.sub
                return h('div', { key: x.url + x.at, className: 'mw-hot-item' },
                  h('div', { className: 'mw-hot-title' },
                    (x.result && x.result.title) || (st === 'pending' ? '排队中 · 等待抓取' : st === 'running' ? '正在抓取并转写…' : '抖音视频')),
                  h('div', { className: 'mw-hot-foot', style: { display: 'flex', alignItems: 'center', gap: 12 } },
                    h('span', { style: { color } }, label),
                    st === 'failed' ? h('span', { style: { color: C.sub } },
                      x.step === 'asr' ? '音频没识别出内容'
                        : x.step === 'fetch' ? '链接抓不到音频'
                          : x.step === 'ffmpeg' ? '音频格式转换失败'
                            : String(x.error || '').slice(0, 50)) : null,
                    (st === 'pending' || st === 'running') ? h('button', {
                      type: 'button', className: 'mw-hot-btn', style: { marginLeft: 'auto' },
                      onClick: (e) => {
                        e.stopPropagation()
                        fetch('/api/dsh-media/capture/cancel', {
                          method: 'POST', headers: { 'content-type': 'application/json' },
                          body: JSON.stringify({ url: x.url, at: x.at }),
                        }).then((r) => r.text()).then(() => poll()).catch(() => { })
                      },
                    }, st === 'running' ? '取消' : '不要这条') : null,
                    st === 'failed' ? h('button', {
                      type: 'button', className: 'mw-hot-btn', style: { marginLeft: 'auto' },
                      onClick: (e) => {
                        e.stopPropagation()
                        fetch('/api/dsh-media/capture/retry', {
                          method: 'POST', headers: { 'content-type': 'application/json' },
                          body: JSON.stringify({ url: x.url, at: x.at }),
                        }).then((r) => r.text()).then(() => poll()).catch(() => { })
                      },
                    }, '重试') : null,
                  ),
                  st === 'done' && x.result && x.result.post_id ? h('div', { style: { marginTop: 6 } },
                    h('button', {
                      type: 'button', className: 'mw-hot-btn',
                      onClick: () => {
                        const pid = x.result.post_id
                        if (openDoc && openDoc.id === pid) setOpenDoc(null)
                        else loadDoc(pid)
                      },
                    }, (openDoc && openDoc.id === x.result.post_id) ? '收起' : '看逐字稿'),
                    (openDoc && openDoc.id === x.result.post_id) ? h('div', {
                      style: {
                        whiteSpace: 'pre-wrap', lineHeight: 1.75, fontSize: 13.5, marginTop: 8,
                        maxHeight: 380, overflowY: 'auto', padding: '10px 12px',
                        background: C.cell2, border: '1px solid ' + C.border, borderRadius: 10,
                      },
                    }, openDoc.text || '（空）') : null,
                  ) : null,
                )
              }),
              jobs.length > 8 ? h('div', { style: { marginTop: 8, fontSize: 12, color: C.sub } }, '还有 ' + (jobs.length - 8) + ' 条更早的不显示') : null,
            ),
          ),
        ),
      )
    }

    /* ---- 拆解看板：实时进度 + 启停 ---- */
    const DASH_BOARDS = [['dry', '干货'], ['quote', '金句'], ['case', '案例'], ['hook', '钩子'], ['avoid', '避坑'], ['qa', '问答']]

    function DashPanel({ onBack }) {
      const [s, setS] = useState(null)
      const [busy, setBusy] = useState('')

      const load = () => fetch('/api/dsh-media/dash/stats').then((r) => r.json()).then((j) => { if (j && j.ok) setS(j) }).catch(() => {})
      useEffect(() => { load(); const t = setInterval(load, 3000); return () => clearInterval(t) }, [])

      const act = (k) => {
        setBusy(k)
        fetch('/api/dsh-media/dash/' + k, { method: 'POST' })
          .then((r) => r.json()).then((j) => { if (j && j.stats) setS({ ok: true, ...j.stats }) })
          .catch(() => {}).then(() => setBusy(''))
      }

      const n = (x) => Number(x || 0).toLocaleString('en-US')
      const st = s ? s.state : 'idle'
      const running = st === 'running' && s && s.left > 0
      const dotColor = running ? '#6fbf8f' : (st === 'paused' ? '#e2b34a' : '#9aa3b2')
      const stText = running ? '正在拆解 · 实时' : (st === 'paused' ? '已暂停' : '当前没有任务')

      const card = (label, val, sub, gold) => h('div', {
        style: { flex: 1, border: '1px solid rgba(255,255,255,.13)', background: '#1b1e24', borderRadius: 3, padding: '14px 16px' },
      },
      h('div', { style: { fontSize: 13, color: '#9aa3b2' } }, label),
      h('div', { style: { fontSize: 34, fontWeight: 700, lineHeight: 1.2, color: gold ? '#d9b45b' : '#eceef2', fontVariantNumeric: 'tabular-nums' } }, val),
      h('div', { style: { fontSize: 12.5, color: '#9aa3b2' } }, sub))

      const mx = Math.max(1, ...DASH_BOARDS.map((b) => (s && s.boards[b[0]]) || 0))

      return h('div', { className: 'mw-root' },
        h('div', { className: 'mw-detail' },
          h('div', { className: 'mw-dhead', style: { display: 'flex', alignItems: 'center', gap: 12 } },
            h('button', { type: 'button', className: 'mw-back', onClick: onBack }, '‹ 工具列表'),
            h('div', { className: 'mw-dtitle' }, '拆解看板'),
            h('span', { style: { display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 13, color: dotColor } },
              h('i', { style: { width: 8, height: 8, borderRadius: '50%', background: dotColor, display: 'inline-block' } }),
              stText),
            h('div', { style: { marginLeft: 'auto', display: 'flex', gap: 8 } },
              h('button', { type: 'button', className: 'mw-back', disabled: !!busy, onClick: () => act('start') }, busy === 'start' ? '启动中…' : '开始拆解'),
              h('button', { type: 'button', className: 'mw-back', disabled: !!busy, onClick: () => act('pause') }, '暂停'),
              h('button', { type: 'button', className: 'mw-back', disabled: !!busy, onClick: () => act('cancel') }, '停止')),
          ),
          h('div', { className: 'mw-dbody', style: { display: 'block' } },
            !s ? h('div', { style: { color: '#9aa3b2' } }, '读取中…') : h('div', null,
              h('div', { style: { display: 'flex', gap: 14 } },
                card('素材总数', n(s.book_src + s.post_src), '书 ' + n(s.book_src) + ' · 稿 ' + n(s.post_src), true),
                card('今天新增', n(s.today), '从 00:00 起'),
                card('已拆块数', n(s.done_chunks), '共 ' + n(s.total_chunks) + ' 块'),
                card('剩余块数', n(s.left), s.left > 0 ? '后台在跑' : '已跑完')),
              h('div', { style: { display: 'flex', gap: 14, marginTop: 14 } },
                h('div', { style: { flex: 1.35, border: '1px solid rgba(255,255,255,.13)', background: '#1b1e24', borderRadius: 3, padding: '16px' } },
                  h('div', { style: { fontSize: 13, color: '#9aa3b2', marginBottom: 10 } }, '六个板块'),
                  DASH_BOARDS.map((b) => {
                    const v = (s.boards && s.boards[b[0]]) || 0
                    const w = Math.max(1, Math.round((v / mx) * 100))
                    return h('div', { key: b[0], style: { display: 'grid', gridTemplateColumns: '52px 1fr 60px', alignItems: 'center', gap: 10, fontSize: 14, marginBottom: 9 } },
                      h('span', null, b[1]),
                      h('span', { style: { height: 9, background: '#20242b', border: '1px solid rgba(255,255,255,.13)', borderRadius: 99, overflow: 'hidden' } },
                        h('i', { style: { display: 'block', height: '100%', width: w + '%', background: '#d9b45b', opacity: 0.36 + 0.64 * (v / mx) } })),
                      h('span', { style: { textAlign: 'right', color: '#f2dfa6', fontVariantNumeric: 'tabular-nums' } }, n(v)))
                  })),
                h('div', { style: { flex: 1, border: '1px solid rgba(255,255,255,.13)', background: '#1b1e24', borderRadius: 3, padding: '16px' } },
                  h('div', { style: { fontSize: 13, color: '#9aa3b2', marginBottom: 10 } }, '来源'),
                  h('div', { style: { display: 'flex', gap: 10 } },
                    h('div', { style: { flex: 1, background: '#20242b', border: '1px solid rgba(255,255,255,.13)', borderRadius: 3, padding: '12px 14px' } },
                      h('div', { style: { fontSize: 24, fontWeight: 700, color: '#f2dfa6' } }, n(s.book_src)), h('div', { style: { fontSize: 12.5, color: '#9aa3b2' } }, '书籍')),
                    h('div', { style: { flex: 1, background: '#20242b', border: '1px solid rgba(255,255,255,.13)', borderRadius: 3, padding: '12px 14px' } },
                      h('div', { style: { fontSize: 24, fontWeight: 700, color: '#f2dfa6' } }, n(s.post_src)), h('div', { style: { fontSize: 12.5, color: '#9aa3b2' } }, '稿子'))),
                  h('div', { style: { fontSize: 13, color: '#9aa3b2', margin: '16px 0 10px' } }, '书库'),
                  h('div', { style: { display: 'flex', gap: 10 } },
                    h('div', { style: { flex: 1, background: '#20242b', border: '1px solid rgba(255,255,255,.13)', borderRadius: 3, padding: '12px 14px' } },
                      h('div', { style: { fontSize: 24, fontWeight: 700, color: '#f2dfa6' } }, n(s.books)), h('div', { style: { fontSize: 12.5, color: '#9aa3b2' } }, '本书')),
                    h('div', { style: { flex: 1, background: '#20242b', border: '1px solid rgba(255,255,255,.13)', borderRadius: 3, padding: '12px 14px' } },
                      h('div', { style: { fontSize: 24, fontWeight: 700, color: '#f2dfa6' } }, n(s.cats)), h('div', { style: { fontSize: 12.5, color: '#9aa3b2' } }, '个分类'))))),
              h('div', { style: { marginTop: 14, border: '1px solid rgba(255,255,255,.13)', background: '#1b1e24', borderRadius: 3, padding: '16px' } },
                h('div', { style: { display: 'flex', justifyContent: 'space-between', fontSize: 13.5, color: '#9aa3b2', marginBottom: 8 } },
                  h('span', null, '拆解进度 ', h('b', { style: { color: '#f2dfa6' } }, n(s.done_chunks) + ' / ' + n(s.total_chunks))),
                  h('span', null, s.left > 0 ? '剩余 ' + n(s.left) + ' 块' : '已全部完成')),
                h('div', { style: { height: 10, background: '#20242b', border: '1px solid rgba(255,255,255,.13)', borderRadius: 99, overflow: 'hidden' } },
                  h('i', { style: { display: 'block', height: '100%', width: Math.max(1, Math.min(100, s.total_chunks ? (s.done_chunks / s.total_chunks) * 100 : 0)) + '%', background: '#d9b45b' } })),
                h('div', { style: { display: 'flex', justifyContent: 'space-between', marginTop: 10, fontSize: 12.5, color: '#9aa3b2' } },
                  h('span', null, '模型 硅基流动 DeepSeek-V3.2 · 48 并发'),
                  h('span', null, '最后活动 ' + (s.updated || s.now || '—')))))
          ),
        ),
      )
    }

    function GhTrendPanel({ onBack }) {
      const ORDER = ['daily', 'weekly', 'monthly', 'year', 'top100']
      const [data, setData] = useState(null)
      const [err, setErr] = useState(null)
      const [refreshing, setRefreshing] = useState(false)
      const [openMap, setOpenMap] = useState({})
      const [intros, setIntros] = useState({})
      const [introRun, setIntroRun] = useState('')
      const [busyRepo, setBusyRepo] = useState('')
      const [toast, setToast] = useState(null)
      const [gone, setGone] = useState({})
      const introBusyRef = useRef({})

      const post = (url, body) => fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body || {}),
      }).then((r) => r.json())

      const load = () => {
        setErr(null)
        fetch('/api/dsh-media/gh-trending')
          .then((r) => r.json())
          .then((j) => {
            if (j && j.ok) setData(j)
            else { setData(null); setErr((j && (j.error || j.hint)) || '没读到数据') }
          })
          .catch((e) => setErr('接口没通：' + String(e && e.message ? e.message : e)))
      }

      useEffect(() => { load() }, [])

      // 数据一到：默认只展开日榜，其余收起（用户要求「需要时再自己打开」）
      useEffect(() => {
        if (!data) return
        const m = {}
        ORDER.forEach((k) => { m[k] = !!(data.lists && data.lists[k] && data.lists[k].defaultOpen) })
        setOpenMap(m)
      }, [data && data.collectedAt])

      // 补简介 + 和已装插件对比重复：只处理展开的榜，一次 8 条，循环到两种都做完
      const fillIntros = useCallback(async (k) => {
        if (introBusyRef.current[k]) return
        introBusyRef.current[k] = true
        setIntroRun(k)
        let reload = false
        try {
          for (let i = 0; i < 30; i++) {
            const r = await post('/api/dsh-media/gh-trending/intro', { list: k })
            if (!r || !r.ok) {
              if (r && r.error) setToast({ kind: 'err', text: '简介没生成：' + r.error })
              break
            }
            if (r.intros && Object.keys(r.intros).length) {
              setIntros((prev) => {
                const next = Object.assign({}, prev)
                for (const key in r.intros) next[key] = r.intros[key]
                return next
              })
            }
            if (r.dups) {
              for (const key in r.dups) {
                if (r.dups[key] && r.dups[key].name && (r.dups[key].conf || 0) >= 0.85) reload = true
              }
            }
            if (!r.generated && !r.duped) break
            if (!r.remaining && !r.dupRemaining) break
          }
        } catch (e) { /* 网络问题：保留原样，不打断看榜 */ }
        introBusyRef.current[k] = false
        setIntroRun('')
        if (reload) load()
      }, [data])

      useEffect(() => {
        if (!data) return
        ORDER.forEach((k) => {
          if (data.lists && data.lists[k] && data.lists[k].defaultOpen) fillIntros(k)
        })
      }, [data, fillIntros])

      useEffect(() => {
        if (!toast) return
        const t = setTimeout(() => setToast(null), 4200)
        return () => clearTimeout(t)
      }, [toast])

      const refresh = () => {
        if (refreshing) return
        setRefreshing(true)
        setErr(null)
        post('/api/dsh-media/gh-trending/refresh')
          .then((j) => {
            if (j && j.data && j.data.ok) setData(j.data)
            else setErr('重抓失败，还是用上次的数据')
          })
          .catch(() => setErr('重抓请求失败了'))
          .finally(() => setRefreshing(false))
      }

      const n = (v) => Number(v || 0).toLocaleString('en-US')
      const introOf = (it) => intros[it.repo] || it.intro || null

      const toggle = (k) => {
        const next = !openMap[k]
        setOpenMap((m) => Object.assign({}, m, { [k]: next }))
        if (next) fillIntros(k)
      }

      const judge = async (it, verdict) => {
        if (busyRepo) return
        setBusyRepo(it.repo)
        try {
          const iv = introOf(it) || {}
          const r = await post('/api/dsh-media/gh-trending/judge', {
            repo: it.repo, verdict,
            what: iv.what || '', use: iv.use || '',
            stars: it.stars, gained: it.gained,
          })
          if (!(r && r.ok)) {
            setToast({ kind: 'err', text: '没记上：' + ((r && r.error) || (r && r.judge && r.judge.error) || '未知原因') })
            return
          }
          setGone((g) => Object.assign({}, g, { [it.repo]: verdict }))
          setToast(verdict === 'useful'
            ? { kind: 'ok', text: '已进看板（待完成）：' + ((r.card && r.card.title) || it.repo) }
            : { kind: 'mute', text: '已隐藏：' + it.repo })
        } catch (e) {
          setToast({ kind: 'err', text: '请求失败，没记上' })
        } finally {
          setBusyRepo('')
        }
      }

      const row = (it, i, mode) => {
        if (gone[it.repo]) return null
        const parts = String(it.repo).split('/')
        const intro = introOf(it)
        const running = introRun === mode
        return h('div', { key: it.repo, className: 'mw-gt-row' },
          h('div', { className: 'mw-gt-rank' }, i + 1),
          h('div', { className: 'mw-gt-main' },
            h('div', { className: 'mw-gt-repo' },
              h('span', { className: 'mw-gt-owner' }, parts[0] + '/'),
              h('span', null, parts[1] || '')),
            intro
              ? h('div', null,
                h('div', { className: 'mw-gt-what' }, h('b', null, '干什么'), intro.what),
                intro.use ? h('div', { className: 'mw-gt-use' }, h('b', null, '能做什么'), intro.use) : null)
              : h('div', { className: 'mw-gt-what dim' },
                it.desc || '（仓库没写描述）',
                running ? h('span', { className: 'mw-gt-run' }, ' · 简介生成中…') : null)),
          h('div', { className: 'mw-gt-tags' }, it.lang ? h('span', { className: 'mw-gt-lang' }, it.lang) : null),
          h('div', { className: 'mw-gt-num' },
            it.gained ? h('div', { className: 'mw-gt-gain' }, '+' + n(it.gained)) : null,
            h('div', { className: 'mw-gt-stars' }, (it.gained ? '共 ' : '') + n(it.stars))),
          h('div', { className: 'mw-gt-act' },
            h('button', {
              type: 'button', className: 'mw-gt-yes', disabled: !!busyRepo,
              onClick: () => judge(it, 'useful'),
            }, busyRepo === it.repo ? '…' : '有用'),
            h('button', {
              type: 'button', className: 'mw-gt-no', disabled: !!busyRepo,
              onClick: () => judge(it, 'useless'),
            }, '没用')))
      }

      const section = (k) => {
        const L = data && data.lists && data.lists[k]
        if (!L) return null
        const vis = (L.items || []).filter((it) => !gone[it.repo])
        const isOpen = !!openMap[k]
        return h('div', { key: k, className: 'mw-gt-sec' },
          h('button', {
            type: 'button', className: 'mw-gt-head' + (isOpen ? ' is-open' : ''),
            onClick: () => toggle(k),
          },
          h('span', { className: 'mw-gt-chev' }, isOpen ? '▾' : '▸'),
          h('span', { className: 'mw-gt-title' }, L.label),
          h('span', { className: 'mw-gt-badge' }, vis.length + ' 个'),
          k === 'daily' && L.totalGain ? h('span', { className: 'mw-gt-sum' }, '共 +' + n(L.totalGain)) : null,
          h('span', { className: 'mw-gt-sub' }, L.sub),
          h('span', { className: 'mw-gt-more' }, isOpen ? '收起' : '展开')),
          isOpen
            ? h('div', { className: 'mw-gt-table' },
              vis.length ? vis.map((it, i) => row(it, i, k)) : h('div', { className: 'mw-gt-empty' }, '这一屏都判完了'),
              (L.skippedDup && L.skippedDup.length)
                ? h('div', { className: 'mw-gt-skip' },
                  '已跳过 ' + L.skippedDup.length + ' 个和你已装插件重复的：'
                  + L.skippedDup.map((s) => s.repo + '（' + s.name + '）').join('、'))
                : null)
            : null)
      }

      const stats = data && data.stats ? data.stats : null
      const KPI = (big, sub, accent) => h('div', { className: 'mw-gt-kpi' },
        h('div', { className: 'mw-gt-kpi-n' + (accent ? ' is-accent' : '') }, big),
        h('div', { className: 'mw-gt-kpi-s' }, sub))

      return h('div', { className: 'mw-root' },
        h('style', { key: 'mw-css' }, CSS),
        h('div', { className: 'mw-detail' },
          h('div', { className: 'mw-dhead' },
            h('button', { type: 'button', className: 'mw-back', onClick: onBack }, '‹ 工具列表'),
            h('div', { className: 'mw-dtitle' }, 'GitHub 热榜'),
            h('div', { className: 'mw-dtag' }, data ? data.date : '—'),
            h('div', { style: { flex: '1 1 auto' } }),
            h('button', {
              type: 'button', className: 'mw-hot-btn', disabled: refreshing, onClick: refresh,
            }, refreshing ? '抓取中…' : '重抓一次')),
          h('div', { className: 'mw-dbody' },
            err ? h('div', { className: 'mw-badge', style: { color: C.err } }, err) : null,
            !data
              ? h('div', { style: { fontSize: 13, color: C.sub, padding: '20px 0' } }, '读取中…')
              : h('div', null,
                h('div', { className: 'mw-gt-kpis' },
                  KPI(n(stats.count), '今日上榜项目'),
                  KPI(n(stats.total), '一天总涨星', true),
                  KPI(n(stats.avg), '平均涨星 / 个'),
                  KPI(stats.topLang, '最扎堆语言')),
                h('div', { className: 'mw-gt-tip' },
                  '每个项目下面两行是 AI 写的：干什么、能做什么。你看完自己判 —— 有用就进看板，没用就消失。'),
                introRun
                  ? h('div', { className: 'mw-gt-tip', style: { color: C.gold, opacity: .9 } },
                    '正在处理「' + ((data.lists[introRun] && data.lists[introRun].label) || introRun)
                    + '」：补简介、和已装插件对比重复…（不用等，边看边生成）')
                  : null,
                toast ? h('div', { className: 'mw-gt-toast is-' + toast.kind }, toast.text) : null,
                ORDER.map(section),
                h('div', { className: 'mw-gt-foot' },
                  '数据抓取 ' + (data.collectedAt || '—')
                  + ' · 判断记录：进看板 ' + n(data.counts ? data.counts.useful : 0)
                  + ' / 已隐藏 ' + n(data.counts ? data.counts.useless : 0),
                  h('div', { style: { marginTop: 4, opacity: .75 } },
                    '年榜 = 近一年新建的仓库按总星排（这一年攒的星）；老项目今年突然爆的，这张榜看不到。')),
              )),
        ),
      )
    }

    /* ================================ 需求发掘台 ================================ */
    // 和自媒体工作台并列的另一个台子。
    // 目的：发现需求 → 判断能不能做 → 做成软件。目前只有 GitHub 热榜一块。
    const IdeaIcon = (props) => {
      const size = (props && props.size) || 18
      return h('svg', {
        width: size, height: size, viewBox: '0 0 24 24', fill: 'none',
        stroke: 'currentColor', strokeWidth: 1.15, strokeLinecap: 'round',
        'aria-hidden': true, style: { display: 'block' },
      },
      h('circle', { cx: 10.6, cy: 10.6, r: 6.4 }),
      h('path', { d: 'M15.4 15.4l4.1 4.1' }),
      h('circle', { cx: 10.6, cy: 10.6, r: 2.2, fill: 'currentColor', stroke: 'none', opacity: 0.45 }),
      )
    }

    const IDEA_CARDS = [
      {
        id: 'ghtrend', title: 'GitHub 热榜',
        desc: '今天在涨什么 · 按新增星数排',
        tag: '需求雷达',
        note: '看别人在做什么、什么正在起来，是找需求的入口',
      },
    ]

    function IdeaLab() {
      const [active, setActive] = useState(null)
      if (active && active.id === 'ghtrend') {
        return h(GhTrendPanel, { onBack: () => setActive(null) })
      }
      return h('div', { className: 'mw-root' },
        h('style', { key: 'mw-css' }, CSS),
        h('div', { className: 'mw-detail' },
          h('div', { className: 'mw-dhead' },
            h('div', { className: 'mw-dtitle' }, '需求发掘台'),
            h('div', { className: 'mw-dtag' }, '外面在涨什么 → 有没有我能做的'),
          ),
          h('div', { className: 'mw-dbody' },
            h('div', {
              style: { fontSize: 13, color: C.sub, lineHeight: 1.8, marginBottom: 18 },
            }, '这里不是做内容，是找机会。目前只有一块，后面再加需求池、痛点库、竞品拆。'),
            h('div', {
              style: {
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
                gap: 12,
              },
            }, IDEA_CARDS.map((c) => h('button', {
              key: c.id,
              type: 'button',
              className: 'mw-card is-accent',
              onClick: () => setActive(c),
              style: {
                textAlign: 'left', padding: '16px 18px', cursor: 'pointer',
                display: 'flex', flexDirection: 'column', gap: 6,
              },
            },
            h('div', { style: { fontSize: 17, fontWeight: 650, color: C.text } }, c.title),
            h('div', { style: { fontSize: 12.5, color: C.sub, lineHeight: 1.7 } }, c.desc),
            h('div', { style: { fontSize: 12, color: C.gold, opacity: .9, marginTop: 2 } }, c.tag + ' · ' + c.note),
            ))),
          ),
        ),
      )
    }

    /* ================================ 能力提升台 ================================ */
    // 从自媒体工作台里拆出来的独立台子：练"怎么说"，不练"说什么"。
    // 目前只有「脱稿口播」是真的能跑；其余是明写「只有说明、机制没写」的空卡，不装样子。
    const GrowIcon = (props) => {
      const size = (props && props.size) || 18
      return h('svg', {
        width: size, height: size, viewBox: '0 0 24 24', fill: 'none',
        stroke: 'currentColor', strokeWidth: 1.15, strokeLinecap: 'round',
        'aria-hidden': true, style: { display: 'block' },
      },
      h('path', { d: 'M4 19.5h16' }),
      h('path', { d: 'M7 19.5v-6' }),
      h('path', { d: 'M12 19.5v-11' }),
      h('path', { d: 'M17 19.5v-4.5' }),
      )
    }

    function GrowPending({ card, onBack }) {
      return h('div', { className: 'mw-root' },
        h('style', { key: 'mw-css' }, CSS),
        h('div', { className: 'mw-detail' },
          h('div', { className: 'mw-dhead' },
            h('button', { type: 'button', className: 'mw-back', onClick: onBack }, '‹ 训练卡'),
            h('div', { className: 'mw-dtitle' }, card.title),
            h('div', { className: 'mw-dtag' }, '只有说明'),
          ),
          h('div', { className: 'mw-dbody' },
            h('div', { className: 'mw-badge' }, '这张卡还没接上，不装样子'),
            h('div', { className: 'mw-dtext' }, card.detail),
            h('div', { style: { marginTop: 20, fontSize: 12.5, color: C.sub, lineHeight: 1.85 } },
              '要接上它，得先把三件事定死：出什么题（题从哪来）、你怎么答（录音还是打字）、机器按什么判分（具体到口径，不然就是瞎给分）。'),
          ),
        ),
      )
    }

    function GrowLab() {
      const [active, setActive] = useState(null)
      const cards = GROW_CARDS

      if (active) {
        if (active.id === 'speech') return h(SpeechPanel, { onBack: () => setActive(null) })
        return h(GrowPending, { card: active, onBack: () => setActive(null) })
      }

      const ready = cards.filter((c) => c.tag === '可用').length
      return h('div', { className: 'mw-root' },
        h('style', { key: 'mw-css' }, CSS),
        h('div', { className: 'mw-detail' },
          h('div', { className: 'mw-dhead' },
            h('div', { className: 'mw-dtitle' }, '能力提升台'),
            h('div', { className: 'mw-dtag' }, `${cards.length} 张训练卡 · 已接通 ${ready} 张`),
          ),
          h('div', { className: 'mw-dbody' },
            h('div', { style: { fontSize: 13, color: C.sub, lineHeight: 1.85, marginBottom: 18 } },
              '这里只练一件事：开口。下面每张卡都是「随机出题 → 你答 → 当场判分」，答完不存档复盘就白练。'),
            h('div', {
              style: { display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(268px, 1fr))', gap: 12 },
            }, cards.map((c) => h('button', {
              key: c.id,
              type: 'button',
              className: 'mw-card is-accent',
              onClick: () => setActive(c),
              style: {
                textAlign: 'left', padding: '16px 18px', cursor: 'pointer',
                display: 'flex', flexDirection: 'column', gap: 6,
              },
            },
            h('div', { style: { display: 'flex', alignItems: 'baseline', gap: 8 } },
              h('div', { style: { fontSize: 17, fontWeight: 650, color: C.text } }, c.title),
              h('div', {
                style: {
                  fontSize: 10, letterSpacing: .8, padding: '2px 6px', borderRadius: 4,
                  border: '1px solid ' + C.border2,
                  color: c.tag === '可用' ? C.ok : C.sub,
                  opacity: c.tag === '可用' ? 1 : .8,
                },
              }, c.tag),
            ),
            h('div', { style: { fontSize: 12.5, color: C.sub, lineHeight: 1.7 } }, c.desc),
            ))),
            h('div', { style: { marginTop: 20, fontSize: 12, color: C.sub, lineHeight: 1.85, opacity: .85 } },
              '交接单上写的是九张，实际点名的是八张（脱稿口播 / 话题即兴 / 限时复述 / 反方辩论 / 标题训练 / 摘要压缩 / 提问训练 / 类比训练）。差的那一张等你补名字，补了我再加。'),
          ),
        ),
      )
    }

    /* ==================== 选题池 / 我的观点 / 我的语料库 ==================== */
    const DIM_KEYS = ['普世性', '数字冲击', '反常识', '可操作', '痛点强度', '时效性', '争议空间', '经验可挂', '能落到动作', '标题性']
    const POOL_STATUS = [['idea', '想法'], ['writing', '在写'], ['published', '已发']]
    const stCn = (s) => (POOL_STATUS.find((x) => x[0] === s) || ['', '想法'])[1]
    const stNext = (s) => (s === 'idea' ? 'writing' : s === 'writing' ? 'published' : 'idea')
    const lvlOf = (s) => (s >= 85 ? 'A' : s >= 70 ? 'B' : 'C')
    const lvlColor = (l) => (l === 'A' ? C.gold : l === 'B' ? C.ok : C.sub)

    const jget = (url) => fetch(url).then((r) => r.json())
    const jpost = (url, body) => fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body || {}),
    }).then((r) => r.json())

    function Top3({ dims }) {
      const arr = DIM_KEYS.map((k) => [k, Number((dims || {})[k]) || 0]).sort((a, b) => b[1] - a[1]).slice(0, 3)
      return h('span', { style: { fontSize: 11.5, color: C.sub, letterSpacing: .2 } },
        arr.map((x, i) => h('span', { key: x[0] }, (i ? ' · ' : '') + x[0].slice(0, 3) + ' ' + x[1])))
    }

    function ScoreTag({ score, level, big }) {
      const l = level || lvlOf(score)
      return h('div', { style: { display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 1, minWidth: big ? 54 : 44 } },
        h('div', {
          style: {
            fontSize: big ? 28 : 21, fontWeight: 700, lineHeight: 1.05,
            color: lvlColor(l), fontVariantNumeric: 'tabular-nums', letterSpacing: -.5,
          },
        }, String(score == null ? '—' : score)),
        h('div', { style: { fontSize: 9.5, letterSpacing: 1.2, color: C.sub, opacity: .8 } }, l + ' 级'),
      )
    }

    function Chip({ label, on, onClick }) {
      return h('button', {
        type: 'button', onClick,
        style: {
          padding: '5px 12px', fontSize: 12.5, borderRadius: 999, cursor: 'pointer',
          border: '1px solid ' + (on ? 'color-mix(in srgb, ' + C.gold + ' 60%, ' + C.border2 + ')' : C.border2),
          background: on ? 'color-mix(in srgb, ' + C.gold + ' 14%, transparent)' : 'transparent',
          color: on ? C.text : C.sub,
        },
      }, label)
    }

    function SmallBtn({ label, onClick, tone, disabled }) {
      return h('button', {
        type: 'button', onClick, disabled: !!disabled,
        style: {
          padding: '5px 11px', fontSize: 12, borderRadius: 7, cursor: disabled ? 'default' : 'pointer',
          border: '1px solid ' + C.border2, background: 'transparent',
          color: tone === 'warn' ? C.warn : tone === 'gold' ? C.gold : C.sub,
          opacity: disabled ? .5 : 1,
        },
      }, label)
    }

    /* ---------------- 选题池 ---------------- */
    function TopicsPanel({ onBack, onWrite }) {
      const [list, setList] = useState([])
      const [boards, setBoards] = useState([])
      const [minScore, setMinScore] = useState(75)
      const [filter, setFilter] = useState('all')
      const [statusF, setStatusF] = useState('all')
      const [busy, setBusy] = useState(null)       // {done,total,current}
      const [err, setErr] = useState(null)
      const [note, setNote] = useState(null)
      const [draft, setDraft] = useState(null)

      const load = () => jget('/api/dsh-media/pool/list?limit=300')
        .then((j) => { if (j && j.ok) setList(j.topics || []); else setErr((j && j.error) || '读不到选题') })
        .catch(() => setErr('接口没通，宿主可能没重启'))

      const loadBoards = () => jget('/api/dsh-media/pool/boards')
        .then((j) => {
          if (j && j.ok) {
            setBoards(j.boards || [])
            if (j.min) setMinScore(j.min)
          }
        })
        .catch(() => { })

      useEffect(() => { load(); loadBoards() }, [])

      const genOne = async (board) => {
        setErr(null); setNote(null)
        setBusy({ done: 0, total: 1, current: board })
        try {
          const j = await jpost('/api/dsh-media/pool/gen', { board, n: 10, min: minScore })
          if (!j || !j.ok) { setErr(board + '：' + ((j && j.error) || '生成失败')) }
          else {
            setNote(board + '：上了 ' + (j.added || 0) + ' 条' + (j.lowDropped ? '，' + j.lowDropped + ' 条低于 ' + minScore + ' 分丢掉' : '')
              + (j.note ? '（' + j.note + '）' : ''))
          }
        } catch (e) { setErr(board + '：请求失败') }
        setBusy(null)
        load(); loadBoards()
      }

      // 8 个板块并发 3 路跑，进度实时显示
      const genAll = async () => {
        const targets = boards.map((b) => b.board)
        if (!targets.length) return
        setErr(null); setNote(null)
        setBusy({ done: 0, total: targets.length, current: '' })
        let idx = 0, done = 0, added = 0, low = 0
        const bad = []
        const worker = async () => {
          while (idx < targets.length) {
            const b = targets[idx++]
            setBusy((s) => (s ? { ...s, current: b } : s))
            try {
              const j = await jpost('/api/dsh-media/pool/gen', { board: b, n: 10, min: minScore })
              if (j && j.ok) { added += j.added || 0; low += j.lowDropped || 0 }
              else bad.push(b + '（' + ((j && j.error) || '失败') + '）')
            } catch (e) { bad.push(b + '（请求失败）') }
            done += 1
            setBusy((s) => (s ? { ...s, done } : s))
          }
        }
        await Promise.all(Array.from({ length: Math.min(3, targets.length) }, worker))
        setBusy(null)
        setNote('跑完 ' + targets.length + ' 个板块：新增 ' + added + ' 条'
          + (low ? '，' + low + ' 条低于 ' + minScore + ' 分丢掉' : '')
          + (bad.length ? '；失败 ' + bad.join('、') : ''))
        load(); loadBoards()
      }

      // 流式：一边写一边上屏，看得见它是怎么起头、怎么拐弯、怎么收尾的
      const writeDraft = async (t, rewrite) => {
        setDraft({ id: t.id, title: t.title, text: '', streaming: true })
        try {
          const r = await fetch('/api/dsh-media/pool/draft/stream', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id: t.id, rewrite: !!rewrite }),
          })
          const ct = r.headers.get('content-type') || ''
          if (ct.indexOf('application/json') >= 0) {
            const j = await r.json()
            setDraft({ id: t.id, title: t.title, error: (j && (j.error || j.reason)) || '写不出来' })
            return
          }
          const reader = r.body.getReader()
          const dec = new TextDecoder()
          let acc = ''
          while (true) {
            const { done, value } = await reader.read()
            if (done) break
            acc += dec.decode(value, { stream: true })
            setDraft({ id: t.id, title: t.title, text: acc, streaming: true })
          }
          setDraft({ id: t.id, title: t.title, text: acc, streaming: false })
        } catch (e) {
          setDraft({ id: t.id, title: t.title, error: '请求失败' })
        }
      }

      const setStatus = (t) => {
        const next = stNext(t.status)
        setList((prev) => prev.map((x) => (x.id === t.id ? { ...x, status: next } : x)))
        jpost('/api/dsh-media/pool/status', { id: t.id, status: next }).catch(() => { })
      }

      const del = (t) => {
        if (typeof window !== 'undefined' && !window.confirm('删掉这条选题？删了找不回来。')) return
        setList((prev) => prev.filter((x) => x.id !== t.id))
        jpost('/api/dsh-media/pool/del', { ids: [t.id] }).catch(() => { })
      }

      const shownAll = list.filter((x) => (x.score || 0) >= minScore)
      const shown = shownAll
        .filter((x) => (filter === 'all' ? true : (x.board || '未分板块') === filter))
        .filter((x) => (statusF === 'all' ? true : x.status === statusF))

      const groups = []
      if (filter === 'all') {
        for (const b of boards) {
          const items = shown.filter((x) => (x.board || '') === b.board)
          groups.push({ board: b.board, items })
        }
        const loose = shown.filter((x) => !boards.some((b) => b.board === x.board))
        if (loose.length) groups.push({ board: '未分板块（旧数据）', items: loose, loose: true })
      } else {
        groups.push({ board: filter, items: shown })
      }

      const today = new Date()
      const todayStr = today.getFullYear() + '-' + String(today.getMonth() + 1).padStart(2, '0') + '-' + String(today.getDate()).padStart(2, '0')
      const todayN = shownAll.filter((x) => x.day === todayStr).length

      const row = (t) => {
        const d = draft && draft.id === t.id ? draft : null
        return h('div', { key: t.id, style: { borderTop: '1px solid ' + C.border } },
          h('div', {
            style: { display: 'flex', gap: 14, alignItems: 'flex-start', padding: '14px 2px 15px' },
          },
          h(ScoreTag, { score: t.score, level: t.level || lvlOf(t.score), big: true }),
          h('div', { style: { flex: '1 1 auto', minWidth: 0 } },
            h('div', { style: { fontSize: 16.5, fontWeight: 620, color: C.text, lineHeight: 1.55 } }, t.title),
            t.angle ? h('div', { style: { fontSize: 13, color: C.sub, lineHeight: 1.75, marginTop: 6 } }, t.angle) : null,
            t.hook ? h('div', { style: { fontSize: 13, color: C.text, lineHeight: 1.75, marginTop: 6, opacity: .85 } },
              h('span', { style: { color: C.gold } }, '开头 · '), t.hook) : null,
            h('div', { style: { display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap', marginTop: 9 } },
              h(Top3, { dims: t.dims }),
              t.source_ref ? h('span', { style: { fontSize: 11.5, color: C.sub, opacity: .75 } },
                '来源 ' + (t.source_kind || '') + ' ' + String(t.source_ref).slice(0, 18)) : null,
              h('span', { style: { fontSize: 11.5, color: C.sub, opacity: .75 } }, stCn(t.status)),
            ),
          ),
          h('div', { style: { display: 'flex', flexDirection: 'column', gap: 6, alignItems: 'flex-end' } },
            (t.draft && t.draft.text)
              ? h('span', {
                style: {
                  fontSize: 9.5, padding: '1px 6px', borderRadius: 4,
                  background: 'color-mix(in srgb, ' + C.gold + ' 16%, transparent)',
                  color: C.gold, border: '1px solid color-mix(in srgb, ' + C.gold + ' 32%, transparent)',
                },
              }, 'AI 已写')
              : null,
            h(SmallBtn, {
              label: d ? '收起' : 'AI 写', tone: 'gold',
              onClick: () => (d ? setDraft(null) : writeDraft(t)),
            }),
            h(SmallBtn, { label: '我来写', onClick: () => onWrite(t) }),
            h(SmallBtn, { label: stNext(t.status) === 'writing' ? '标在写' : stNext(t.status) === 'published' ? '标已发' : '退回想法', onClick: () => setStatus(t) }),
            h(SmallBtn, { label: '删', tone: 'warn', onClick: () => del(t) }),
          ),
          ),
          d ? h('div', {
            style: {
              margin: '0 0 18px 68px', padding: '14px 16px', borderRadius: 10,
              border: '1px solid ' + C.border2, background: C.cell,
            },
          },
          h('div', { style: { display: 'flex', alignItems: 'baseline', gap: 10, marginBottom: 10 } },
            h('div', { style: { fontSize: 11.5, letterSpacing: 1.1, color: C.gold, flex: '1 1 auto' } },
              'AI 写的口播文案 · 只用原始素材里的事实'),
            d.streaming ? null : h(SmallBtn, { label: '重写一遍', onClick: () => writeDraft(t, true) }),
          ),
          d.error
            ? h('div', { className: 'mw-err' }, '写不出来：' + d.error)
            : (!d.text && d.streaming)
              ? h('div', { style: { fontSize: 13, color: C.sub } }, '正在读原始素材、起第一句…')
              : h('div', { style: { whiteSpace: 'pre-wrap', fontSize: 14.5, lineHeight: 1.95, color: C.text } },
                d.text, d.streaming ? h('span', { style: { color: C.gold } }, '▍') : null),
          ) : null,
        )
      }

      return h('div', { className: 'mw-root' },
        h('style', { key: 'mw-css' }, CSS),
        h('div', { className: 'mw-detail' },
          h('div', { className: 'mw-dhead' },
            h('button', { type: 'button', className: 'mw-back', onClick: onBack }, '‹ 工具列表'),
            h('div', { className: 'mw-dtitle' }, '选题池'),
            h('div', { className: 'mw-dtag' }, `今天 ${todayN} 条 · 只看 ${minScore} 分以上`),
            h('div', { style: { flex: '1 1 auto' } }),
            h(ModelPicker, null),
            h('button', {
              type: 'button', className: 'mw-hot-btn', disabled: !!busy, onClick: genAll,
              style: { marginLeft: 8 },
            }, busy ? '跑板块 ' + busy.done + '/' + busy.total : '刷新全部板块'),
          ),
          h('div', { className: 'mw-dbody' },
            err ? h('div', { className: 'mw-err' }, err) : null,
            note ? h('div', { style: { fontSize: 12.5, color: C.sub, marginBottom: 12 } }, note) : null,
            busy ? h('div', {
              style: {
                fontSize: 12.5, color: C.gold, marginBottom: 12, padding: '8px 12px', borderRadius: 8,
                background: 'color-mix(in srgb, ' + C.gold + ' 10%, transparent)',
              },
            }, '正在出题：' + busy.current + '（' + busy.done + '/' + busy.total + ' 个板块跑完，每个约 1 分半）') : null,

            h('div', { style: { display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 12 } },
              h(Chip, { label: '全部板块 ' + shownAll.length, on: filter === 'all', onClick: () => setFilter('all') }),
              boards.map((b) => h(Chip, {
                key: b.board, label: b.board + ' ' + shownAll.filter((x) => x.board === b.board).length,
                on: filter === b.board, onClick: () => setFilter(b.board),
              })),
            ),
            h('div', { style: { display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 18 } },
              h(Chip, { label: '全部状态', on: statusF === 'all', onClick: () => setStatusF('all') }),
              POOL_STATUS.map(([k, cn]) => h(Chip, {
                key: k, label: cn + ' ' + shownAll.filter((x) => x.status === k).length,
                on: statusF === k, onClick: () => setStatusF(k),
              })),
            ),

            groups.map((g) => h('div', { key: g.board, style: { marginBottom: 22 } },
              h('div', {
                style: {
                  display: 'flex', alignItems: 'baseline', gap: 10, paddingBottom: 8,
                  borderBottom: '1px solid ' + C.border2,
                },
              },
              h('div', { style: { fontSize: 15.5, fontWeight: 650, color: C.gold, letterSpacing: .3 } }, g.board),
              h('div', { style: { fontSize: 12, color: C.sub } },
                g.items.length ? g.items.length + ' 条' : '今天还没出题'),
              h('div', { style: { flex: '1 1 auto' } }),
              g.loose ? null : h(SmallBtn, {
                label: busy ? '…' : '补这个板块',
                disabled: !!busy,
                onClick: () => genOne(g.board),
              }),
              ),
              g.items.length
                ? g.items.slice().sort((a, b) => (b.score || 0) - (a.score || 0)).map(row)
                : h('div', { style: { fontSize: 12.5, color: C.sub, padding: '12px 2px', opacity: .8 } },
                  busy ? '排队中…' : '这个板块今天还没有达到 ' + minScore + ' 分的选题。点右边「补这个板块」再出一轮。'),
            )),

            !shown.length && !groups.length
              ? h('div', { className: 'mw-empty' }, '还没有选题。点右上角「刷新全部板块」。')
              : null,
          ),
        ),
      )
    }

    /* ---------------- 写观点弹框 ---------------- */
    function Composer({ topic, onClose, onSaved }) {
      const [title, setTitle] = useState(topic ? topic.title : '')
      const [text, setText] = useState('')
      const [tags, setTags] = useState('')
      const [busy, setBusy] = useState(false)
      const [err, setErr] = useState(null)
      const [saved, setSaved] = useState(null)
      const [review, setReview] = useState(null)
      const taRef = useRef(null)

      useEffect(() => {
        const t = setTimeout(() => { try { taRef.current && taRef.current.focus() } catch { } }, 60)
        return () => clearTimeout(t)
      }, [])

      const submit = async () => {
        if (!text.trim()) { setErr('还一个字都没写'); return }
        setBusy(true); setErr(null)
        const head = (title.trim() || text.trim().slice(0, 24)).replace(/\s+/g, ' ')
        const sv = await jpost('/api/dsh-media/views/save', {
          kind: topic ? 'topic' : 'free',
          topicId: topic ? topic.id : '',
          title: head,
          tags: tags.trim(),
          content: text,
        }).catch(() => null)
        if (!sv || !sv.ok) { setBusy(false); setErr('保存失败：' + ((sv && sv.error) || '接口没通')); return }
        setSaved(sv.id)
        if (typeof onSaved === 'function') onSaved()
        setBusy(false)
        setReview({ loading: true })
        const rv = await jpost('/api/dsh-media/views/review', { id: sv.id }).catch(() => null)
        if (rv && rv.ok) setReview(rv.review)
        else setReview({ error: (rv && rv.error) || '评审没跑出来' })
      }

      const box = { background: C.cell, border: '1px solid ' + C.border2, borderRadius: 10, color: C.text, fontSize: 14.5, lineHeight: 1.8, padding: '12px 14px', width: '100%', boxSizing: 'border-box' }

      return h('div', {
        style: {
          position: 'fixed', inset: 0, background: 'rgba(0,0,0,.58)', zIndex: 9000,
          display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 20,
        },
        onClick: (e) => { if (e.target === e.currentTarget && !busy) onClose() },
      },
      h('div', {
        style: {
          width: 'min(820px, 96vw)', maxHeight: '88vh', overflow: 'auto',
          background: C.base, border: '1px solid ' + C.border2, borderRadius: 14,
          padding: '22px 24px 20px', boxShadow: '0 30px 80px rgba(0,0,0,.5)',
        },
      },
      h('div', { style: { display: 'flex', alignItems: 'baseline', gap: 10, marginBottom: 4 } },
        h('div', { style: { fontSize: 18, fontWeight: 660, color: C.text } }, topic ? '写你的观点' : '有感而发'),
        h('div', { style: { fontSize: 12, color: C.gold } }, topic ? '选题：' + topic.title : '不绑选题'),
      ),
      h('div', { style: { fontSize: 12, color: C.sub, marginBottom: 14 } },
        '原文一字不动地存进语料库。AI 只评不改，不会替你重写一个字。'),

      saved ? null : h('div', { style: { display: 'flex', flexDirection: 'column', gap: 10 } },
        h('input', {
          value: title, onChange: (e) => setTitle(e.target.value),
          placeholder: '标题（可空，默认取正文前 24 字）',
          style: { ...box, fontSize: 13.5, padding: '9px 12px' },
        }),
        h('textarea', {
          ref: taRef, value: text, onChange: (e) => setText(e.target.value),
          placeholder: '就这么写，想到哪写到哪。写完我再评。',
          style: { ...box, minHeight: 220, resize: 'vertical', fontFamily: 'inherit' },
        }),
        h('input', {
          value: tags, onChange: (e) => setTags(e.target.value),
          placeholder: '标签（可空，多个用逗号）',
          style: { ...box, fontSize: 13.5, padding: '9px 12px' },
        }),
        h('div', { style: { display: 'flex', alignItems: 'center', gap: 10 } },
          h('span', { style: { fontSize: 12, color: C.sub, fontVariantNumeric: 'tabular-nums' } }, text.length + ' 字'),
          h('div', { style: { flex: '1 1 auto' } }),
          h(SmallBtn, { label: '取消', onClick: () => { if (!busy) onClose() } }),
          h(SmallBtn, { label: busy ? '存 + 评审中…' : '提交并让 AI 评', tone: 'gold', disabled: busy, onClick: submit }),
        ),
      ),

      err ? h('div', { className: 'mw-err', style: { marginTop: 12 } }, err) : null,

      saved ? h('div', { style: { marginTop: 4 } },
        h('div', { style: { fontSize: 12.5, color: C.ok, marginBottom: 12 } }, '已存进语料库（原文没动）'),
        h('div', { style: { fontSize: 12, color: C.sub, letterSpacing: .6, marginBottom: 6 } }, '我的原文'),
        h('div', { style: { ...box, whiteSpace: 'pre-wrap', background: C.cell2 } }, text),
        h('div', { style: { marginTop: 16 } }, h(ReviewBlock, { review })),
        h('div', { style: { display: 'flex', justifyContent: 'flex-end', marginTop: 16 } },
          h(SmallBtn, { label: '关掉', onClick: onClose })),
      ) : null,
      ),
      )
    }

    /* AI 评审结果：只展示评价，不出现任何"改写版本" */
    function ReviewBlock({ review }) {
      if (!review) return null
      if (review.loading) return h('div', { style: { fontSize: 13, color: C.sub } }, 'AI 在评…（不会改你的字，只挑问题）')
      if (review.error) return h('div', { className: 'mw-err' }, '评审失败：' + review.error)
      const sec = (title, arr, color) => (arr && arr.length
        ? h('div', { style: { marginTop: 12 } },
          h('div', { style: { fontSize: 11.5, letterSpacing: 1.2, color, marginBottom: 5 } }, title),
          arr.map((x, i) => h('div', { key: i, style: { fontSize: 13.5, color: C.text, lineHeight: 1.8, opacity: .92 } }, '· ' + x)))
        : null)
      return h('div', {
        style: {
          border: '1px solid ' + C.border2, borderRadius: 12, padding: '16px 18px',
          background: 'color-mix(in srgb, ' + C.gold + ' 5%, transparent)',
        },
      },
      h('div', { style: { display: 'flex', alignItems: 'center', gap: 14, marginBottom: 4 } },
        h(ScoreTag, { score: review.score, level: lvlOf(review.score), big: true }),
        h('div', null,
          h('div', { style: { fontSize: 15, fontWeight: 620, color: C.text } }, review.verdict || '评完了'),
          review.one_line ? h('div', { style: { fontSize: 13, color: C.sub, marginTop: 4, lineHeight: 1.7 } }, review.one_line) : null,
        ),
      ),
      sec('立得住的地方', review.pros, C.ok),
      sec('缺的东西', review.gaps, C.warn),
      sec('可以问自己的', review.questions, C.gold),
      )
    }

    /* ---------------- 我的观点 ---------------- */
/* 稿库语义匹配的共享状态：展开一条观点时去稿库找讲同一件事的原文 */
const M = { match: null, matching: false }

function runMatch(text, refresh) {
  M.matching = true
  M.match = null
  if (refresh) refresh()
  fetch('/api/dsh-media/match?text=' + encodeURIComponent(String(text || '').slice(0, 500)))
    .then((r) => r.json())
    .then((j) => { M.matching = false; M.match = (j && j.ok) ? j : { hits: [], core: '' } })
    .catch(() => { M.matching = false; M.match = { hits: [], core: '', error: 1 } })
    .then(() => { if (refresh) refresh() })
}

    function SelfPanel({ onBack, topic, onWriteFree }) {
      const [list, setList] = useState([])
      const [open, setOpen] = useState(null)
      const [comp, setComp] = useState(!!topic)
      const [err, setErr] = useState(null)

      const load = () => jget('/api/dsh-media/views/list?limit=80')
        .then((j) => { if (j && j.ok) setList(j.views || []); else setErr((j && j.error) || '读不到') })
        .catch(() => setErr('接口没通，宿主可能没重启'))

      useEffect(() => { load() }, [])

      const openOne = (v) => {
        setOpen({ loading: true, id: v.id })
    M.match = null; M.matching = true
        jget('/api/dsh-media/views/get?id=' + encodeURIComponent(v.id))
          .then((j) => {
      if (j && j.ok) {
        setOpen(j.view)
        runMatch(j.view && j.view.content, () => setOpen((p) => (p ? Object.assign({}, p) : p)))
      } else setOpen({ error: (j && j.error) || '读不到' })
    })
          .catch(() => setOpen({ error: '请求失败' }))
      }

      const del = (v) => {
        if (typeof window !== 'undefined' && !window.confirm('删掉这条观点？删了找不回来。')) return
        jpost('/api/dsh-media/views/del', { ids: [v.id] }).then(() => { setOpen(null); load() }).catch(() => { })
      }

      const reReview = (v) => {
        setOpen({ ...v, ai_review: { loading: true } })
        jpost('/api/dsh-media/views/review', { id: v.id }).then((j) => {
          if (j && j.ok) setOpen({ ...v, ai_review: j.review })
          else setOpen({ ...v, ai_review: { error: (j && j.error) || '评审失败' } })
        }).catch(() => setOpen({ ...v, ai_review: { error: '请求失败' } }))
      }

      const box = { whiteSpace: 'pre-wrap', fontSize: 14.5, lineHeight: 1.85, color: C.text, background: C.cell, border: '1px solid ' + C.border2, borderRadius: 10, padding: '14px 16px' }

      return h('div', { className: 'mw-root' },
        h('style', { key: 'mw-css' }, CSS),
        h('div', { className: 'mw-detail' },
          h('div', { className: 'mw-dhead' },
            h('button', { type: 'button', className: 'mw-back', onClick: onBack }, '‹ 工具列表'),
            h('div', { className: 'mw-dtitle' }, '我的观点'),
            h('div', { className: 'mw-dtag' }, list.length + ' 条'),
            h('div', { style: { flex: '1 1 auto' } }),
            h(ModelPicker, null),
            h('button', {
              type: 'button', className: 'mw-hot-btn', onClick: () => setComp(true), style: { marginLeft: 8 },
            }, '有感而发'),
          ),
          h('div', { className: 'mw-dbody' },
            err ? h('div', { className: 'mw-err' }, err) : null,
            h('div', { style: { fontSize: 12.5, color: C.sub, lineHeight: 1.8, marginBottom: 16 } },
              '从选题池点「写这个」进来，或者直接「有感而发」。你写什么就存什么，一个字都不改；AI 只告诉你哪里立得住、哪里是空话。'),


            list.length === 0
              ? h('div', { className: 'mw-empty' }, '还没有观点。点右上角「有感而发」写第一条。')
              : list.flatMap((v) => [h('button', {
                key: v.id, type: 'button', onClick: () => (open && open.id === v.id ? setOpen(null) : openOne(v)),
                style: {
                  display: 'block', width: '100%', textAlign: 'left', cursor: 'pointer',
                  background: 'transparent', border: 'none', borderTop: '1px solid ' + C.border,
                  padding: '13px 2px 14px',
                },
              },
              h('div', { style: { display: 'flex', gap: 10, alignItems: 'baseline' } },
                h('span', {
                  style: {
                    fontSize: 10, letterSpacing: .8, padding: '2px 7px', borderRadius: 4,
                    border: '1px solid ' + C.border2, color: v.kind === 'topic' ? C.gold : C.sub,
                  },
                }, v.kind === 'topic' ? '选题' : '有感'),
                h('span', { style: { fontSize: 15, fontWeight: 600, color: C.text, flex: '1 1 auto', minWidth: 0 } }, v.title || '（无标题）'),
                v.ai_review && v.ai_review.score != null
                  ? h('span', { style: { fontSize: 14, fontWeight: 700, color: lvlColor(lvlOf(v.ai_review.score)), fontVariantNumeric: 'tabular-nums' } }, String(v.ai_review.score))
                  : h('span', { style: { fontSize: 11.5, color: C.sub, opacity: .7 } }, '未评'),
              ),
              h('div', { style: { fontSize: 12.5, color: C.sub, marginTop: 5, lineHeight: 1.7, overflow: 'hidden' } },
                (v.content || '').slice(0, 90)),
              ), open && open.id === v.id ? h('div', {
                key: 'inline-' + v.id,
                style: {
                  padding: '14px 2px 18px', borderTop: '1px solid ' + C.border,
                  background: 'rgba(217,169,74,.035)', marginBottom: 4,
                },
              }, [
                h('div', { key: 'h', style: { display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 } }, [
                  h('div', { key: 't', style: { fontSize: 15, fontWeight: 620, color: C.text } }, (open.title || '（无标题）')),
                  h('div', { key: 'd', style: { fontSize: 11.5, color: C.sub } }, open.created_at || ''),
                  h('div', { key: 's', style: { flex: '1 1 auto' } }),
                  h(SmallBtn, { key: 'r', label: '重新评', onClick: () => reReview(open) }),
                  h(SmallBtn, { key: 'c', label: '收起', onClick: () => setOpen(null) }),
                  h(SmallBtn, { key: 'x', label: '删', tone: 'warn', onClick: () => del(open) }),
                ]),
                open.loading ? h('div', { key: 'l', className: 'mw-empty' }, '读原文…')
                  : open.error ? h('div', { key: 'e', className: 'mw-err' }, open.error)
                    : h('div', { key: 'b' }, [
                      h('div', { key: 'lb', style: { fontSize: 11.5, letterSpacing: 1.2, color: C.sub, marginBottom: 6 } }, '我的原文（一字未改）'),
                      h('div', { key: 'ct', style: box }, open.content),
                      h('div', { key: 'rv', style: { marginTop: 16 } }, h(ReviewBlock, { review: open.ai_review })),
                      h('div', { key: 'mt', style: { marginTop: 18 } },
                        h('div', { style: { fontSize: 11.5, letterSpacing: 1.1, color: C.gold, marginBottom: 8 } },
                          M.matching ? '正在提炼主张、去稿库里找…'
                            : (M.match && M.match.core ? ('主张：' + M.match.core) : '稿库匹配')),
                        (M.match && M.match.hits && M.match.hits.length)
                          ? h('div', null, M.match.hits.map((x, k) => h('div', {
                            key: 'mh' + k,
                            style: {
                              padding: '11px 0', borderTop: k ? '1px solid ' + C.border : 'none',
                            },
                          },
                          h('div', { style: { fontSize: 11, color: C.sub, marginBottom: 4 } },
                            '［' + (x.src || '') + '］' + (x.why ? ' ' + x.why : '')),
                          h('div', { style: { fontSize: 13, color: C.sub, lineHeight: 1.8 } }, x.seg || ''),
                          )))
                          : (M.match && !M.matching
                            ? h('div', { style: { fontSize: 12.5, color: C.sub, opacity: .75 } },
                              '稿库里没有讲同一件事的原文，不用硬凑。')
                            : null),
                      ),
                      open.ai_review ? null : h('div', { key: 'go', style: { marginTop: 12 } },
                        h(SmallBtn, { label: '让 AI 评一下', tone: 'gold', onClick: () => reReview(open) })),
                    ]),
              ]) : null])
          ),
        ),
        comp ? h(Composer, {
          topic: topic || null,
          onClose: () => { setComp(false); load(); if (typeof onWriteFree === 'function') onWriteFree() },
          onSaved: load,
        }) : null,
      )
    }

    /* ---------------- 我的灵感 ---------------- */
    function IdeasPanel({ onBack }) {
      const [list, setList] = useState([])
      const [stale, setStale] = useState(0)
      const [text, setText] = useState('')
      const [busy, setBusy] = useState(false)
      const [err, setErr] = useState(null)
      const [done, setDone] = useState(null)

      const load = () => {
        jget('/api/dsh-media/myideas/list?limit=100')
          .then((j) => {
            if (j && j.ok) { setList(j.ideas || []); setStale(j.stale || 0); setErr(null) }
            else setErr((j && j.error) || '读不到灵感')
          })
          .catch((e) => setErr(String(e.message || e)))
      }
      useEffect(() => { load() }, [])

      const add = async () => {
        const v = text.trim()
        if (!v || busy) return
        setBusy(true)
        try {
          const r = await jpost('/api/dsh-media/myideas/add', { content: v, source: 'manual' })
          if (r && r.ok) { setText(''); load() } else setErr((r && r.error) || '记不下来')
        } catch (e) { setErr(String(e.message || e)) }
        setBusy(false)
      }

      const promote = async (it) => {
        if (busy) return
        setBusy(true)
        try {
          const r = await jpost('/api/dsh-media/myideas/promote', { id: it.id })
          if (r && r.ok) { setDone('已推进「我的观点」，原话还在灵感里'); load() }
          else setErr((r && r.error) || '推进失败')
        } catch (e) { setErr(String(e.message || e)) }
        setBusy(false)
      }

      const del = async (it) => {
        try {
          await jpost('/api/dsh-media/myideas/del', { ids: [it.id] })
          load()
        } catch (e) { setErr(String(e.message || e)) }
      }

      const days = (s) => {
        try {
          const d = (Date.now() - new Date(String(s).replace('T', ' ')).getTime()) / 86400000
          return Math.max(0, Math.floor(d))
        } catch { return 0 }
      }

      return h('div', { className: 'mw-root' },
        h('style', { key: 'mw-css' }, CSS),
        h('div', { className: 'mw-detail' },
          h('div', { className: 'mw-dhead' },
            h('button', { type: 'button', className: 'mw-back', onClick: onBack }, '‹ 工具列表'),
            h('div', { className: 'mw-dtitle' }, '我的灵感'),
            h('div', { className: 'mw-dtag' }, `${list.length} 条${stale ? ` · ${stale} 条一周没动` : ''}`),
          ),
          h('div', { className: 'mw-dbody' },
            err ? h('div', { style: { fontSize: 12.5, color: C.warn || '#e09182', marginBottom: 10 } }, err) : null,
            done ? h('div', { style: { fontSize: 12.5, color: '#8fd39b', marginBottom: 10 } }, done) : null,

            h('div', { style: { display: 'flex', gap: 8, marginBottom: 16 } },
              h('input', {
                key: 'i', value: text, placeholder: '想到什么就先打一句，不用成型',
                onChange: (e) => setText(e.target.value),
                onKeyDown: (e) => { if (e.key === 'Enter') add() },
                style: {
                  flex: 1, padding: '10px 12px', borderRadius: 10, fontSize: 13.5,
                  background: C.cell, color: C.text, border: '1px solid ' + C.border,
                },
              }),
              h('button', {
                key: 'b', type: 'button', onClick: add, disabled: busy,
                style: {
                  padding: '0 18px', borderRadius: 10, fontSize: 13.5, cursor: 'pointer',
                  background: 'rgba(217,169,74,.16)', color: '#f2ce84',
                  border: '1px solid rgba(217,169,74,.45)',
                },
              }, busy ? '…' : '记下'),
            ),

            list.length === 0
              ? h('div', { style: { fontSize: 12.5, color: C.sub, lineHeight: 1.8, padding: '10px 2px' } },
                '还没有灵感。上面打一句就行——不用完整，不用有道理，想到什么记什么。')
              : list.map((it) => {
                const d = days(it.created_at)
                const old = it.status === 'new' && d >= 7
                return h('div', {
                  key: it.id,
                  style: {
                    padding: '12px 13px', borderRadius: 11, marginBottom: 9,
                    background: C.cell, border: '1px solid ' + C.border,
                    borderLeft: '2px solid ' + (it.status === 'promoted' ? 'rgba(120,220,140,.7)' : old ? 'rgba(214,120,96,.75)' : 'rgba(217,169,74,.55)'),
                  },
                }, [
                  h('div', { key: 't', style: { fontSize: 13.5, color: C.text, lineHeight: 1.65, marginBottom: 9 } }, it.content),
                  h('div', { key: 'r', style: { display: 'flex', alignItems: 'center', gap: 8, fontSize: 11.5, color: C.sub } }, [
                    h('span', { key: 's', style: { color: it.status === 'promoted' ? '#8fd39b' : old ? '#e09182' : '#8b939e' } },
                      it.status === 'promoted' ? '已成观点' : (old ? `生的 · ${d} 天没动` : '生的')),
                    h('span', { key: 'sp', style: { flex: 1 } }),
                    it.status === 'promoted'
                      ? null
                      : h('button', {
                        key: 'p', type: 'button', onClick: () => promote(it),
                        style: { padding: '4px 11px', borderRadius: 8, fontSize: 11.5, cursor: 'pointer', background: 'rgba(217,169,74,.12)', color: '#f2ce84', border: '1px solid rgba(217,169,74,.4)' },
                      }, '养成观点'),
                    h('button', {
                      key: 'd', type: 'button', onClick: () => del(it),
                      style: { padding: '4px 11px', borderRadius: 8, fontSize: 11.5, cursor: 'pointer', background: 'transparent', color: '#8b939e', border: '1px solid ' + C.border },
                    }, '删'),
                  ]),
                ])
              }),
          ),
        ),
      )
    }

    /* ---------------- 观点库（别人的观点，表个态） ---------------- */
    function ViewsPoolPanel({ onBack }) {
      const [list, setList] = useState([])
      const [left, setLeft] = useState(0)
      const [done, setDone] = useState(0)
      const [err, setErr] = useState(null)
      const [draft, setDraft] = useState({})
      const [busy, setBusy] = useState(null)

      const load = () => {
        jget('/api/dsh-media/clash/list?limit=60')
          .then((j) => {
            if (j && j.ok) { setList(j.items || []); setLeft(j.left || 0); setDone(j.done || 0); setErr(null) }
            else setErr((j && j.error) || '读不到观点')
          })
          .catch((e) => setErr(String(e.message || e)))
      }
      useEffect(() => { load() }, [])

      const pick = (id, verdict) => {
        setDraft((prev) => {
          const cur = prev[id]
          if (cur && cur.verdict === verdict) {
            const n = { ...prev }
            delete n[id]
            return n
          }
          return { ...prev, [id]: { verdict, why: (cur && cur.why) || '' } }
        })
      }
      const editWhy = (id, v) => setDraft((p) => ({ ...p, [id]: { ...p[id], why: v } }))
      const cancel = (id) => setDraft((p) => { const n = { ...p }; delete n[id]; return n })

      const submit = async (it) => {
        const d = draft[it.id]
        if (!d || busy) return
        setBusy(it.id)
        try {
          const r = await jpost('/api/dsh-media/clash/answer', {
            atomId: it.id, verdict: d.verdict, why: String(d.why || '').trim(),
          })
          if (r && r.ok) {
            setList((prev) => prev.filter((x) => x.id !== it.id))
            setDraft((p) => { const n = { ...p }; delete n[it.id]; return n })
            setDone((x) => x + 1); setLeft((l) => Math.max(0, l - 1))
          } else setErr((r && r.error) || '没存上')
        } catch (e) { setErr(String(e.message || e)) }
        setBusy(null)
      }

      const QUESTION = { agree: '你为什么认同？写多少都行，但不能空', disagree: '你为什么不认同？写多少都行，但不能空' }

      return h('div', { className: 'mw-root' },
        h('style', { key: 'mw-css' }, CSS),
        h('div', { className: 'mw-detail' },
          h('div', { className: 'mw-dhead' },
            h('button', { type: 'button', className: 'mw-back', onClick: onBack }, '‹ 工具列表'),
            h('div', { className: 'mw-dtitle' }, '观点库'),
            h('div', { className: 'mw-dtag' }, `已表态 ${done} · 还剩 ${left}`),
          ),
          h('div', { className: 'mw-dbody' },
            err ? h('div', { style: { fontSize: 12.5, color: '#e09182', marginBottom: 10 } }, err) : null,

            list.length === 0
              ? h('div', { style: { fontSize: 13, color: C.sub, lineHeight: 1.9, padding: '14px 2px' } },
                done > 0 ? `全看完了。你已经表态 ${done} 条。` : '这条流是空的。')
              : list.map((it) => {
                const d = draft[it.id]
                return h('div', {
                  key: it.id,
                  style: {
                    padding: '14px 15px', borderRadius: 12, marginBottom: 10,
                    background: C.cell,
                    border: '1px solid ' + (d ? (d.verdict === 'agree' ? 'rgba(120,220,140,.45)' : 'rgba(214,120,96,.45)') : C.border),
                  },
                }, [
                  h('div', { key: 'c', style: { fontSize: 15, color: C.text, lineHeight: 1.7, marginBottom: 10 } }, it.claim),

                  d ? h('div', { key: 'box', style: { marginBottom: 10 } }, [
                    h('div', { key: 'q', style: { fontSize: 12.5, color: C.sub, marginBottom: 7 } }, QUESTION[d.verdict]),
                    h('textarea', {
                      key: 'ta', value: d.why, autoFocus: true,
                      placeholder: '必须写点东西：为什么认同/不认同，它跟你有什么关系',
                      onChange: (e) => editWhy(it.id, e.target.value),
                      style: {
                        width: '100%', minHeight: 96, padding: '10px 12px', borderRadius: 9, fontSize: 13.5,
                        lineHeight: 1.7, background: 'rgba(0,0,0,.28)', color: C.text,
                        border: '1px solid ' + C.border, resize: 'vertical',
                      },
                    }),
                  ]) : null,

                  h('div', { key: 'r', style: { display: 'flex', alignItems: 'center', gap: 8 } }, [
                    h('div', { key: 'a', style: { flex: 1, fontSize: 11.5, color: C.sub, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' } },
                      it.author ? '@' + String(it.author).slice(0, 20) : '来源未标'),
                    h('button', {
                      key: 'y', type: 'button', onClick: () => pick(it.id, 'agree'),
                      style: {
                        padding: '6px 16px', borderRadius: 8, fontSize: 12.5, cursor: 'pointer',
                        background: d && d.verdict === 'agree' ? 'rgba(120,220,140,.28)' : 'rgba(120,220,140,.10)',
                        color: '#8fd39b',
                        border: '1px solid rgba(120,220,140,' + (d && d.verdict === 'agree' ? '.85' : '.35') + ')',
                      },
                    }, '认同'),
                    h('button', {
                      key: 'n', type: 'button', onClick: () => pick(it.id, 'disagree'),
                      style: {
                        padding: '6px 16px', borderRadius: 8, fontSize: 12.5, cursor: 'pointer',
                        background: d && d.verdict === 'disagree' ? 'rgba(214,120,96,.28)' : 'rgba(214,120,96,.10)',
                        color: '#e09182',
                        border: '1px solid rgba(214,120,96,' + (d && d.verdict === 'disagree' ? '.85' : '.35') + ')',
                      },
                    }, '不认同'),
                    d ? h('button', {
                      key: 's', type: 'button', onClick: () => submit(it),
                      disabled: !String(d.why || '').trim(),
                      style: {
                        padding: '6px 16px', borderRadius: 8, fontSize: 12.5,
                        cursor: String(d.why || '').trim() ? 'pointer' : 'not-allowed',
                        background: String(d.why || '').trim() ? 'rgba(217,169,74,.18)' : 'transparent',
                        color: String(d.why || '').trim() ? '#f2ce84' : '#5c6672',
                        border: '1px solid ' + (String(d.why || '').trim() ? 'rgba(217,169,74,.5)' : C.border),
                      },
                    }, busy === it.id ? '…' : '存进我的观点') : null,
                    d ? h('button', {
                      key: 'x', type: 'button', onClick: () => cancel(it.id),
                      style: { padding: '6px 12px', borderRadius: 8, fontSize: 12.5, cursor: 'pointer', background: 'transparent', color: C.sub, border: '1px solid ' + C.border },
                    }, '取消') : null,
                  ]),
                ])
              }),
          ),
        ),
      )
    }

    /* ---------------- 我的语料库 ---------------- */
    /* ---------- 训练面板：出题 → 你答 → AI 评（七种训练共用） ---------- */
/* ---------- 每日训练（打卡 + 动作教程） ---------- */
function FitPanel({ onBack }) {
  const [data, setData] = useState(null)
  const [guides, setGuides] = useState({})
  const [busy, setBusy] = useState('')

  const load = () => {
    fetch('/api/dsh-media/sp/fit/week').then((r) => r.json()).then((j) => {
      if (j && j.ok) setData(j)
    }).catch(() => { })
  }
  useEffect(() => { load() }, [])

  const check = (item) => {
    setBusy(item)
    fetch('/api/dsh-media/sp/fit/check', {
      method: 'POST', headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ item }),
    }).then((r) => r.json()).then(() => { setBusy(''); load() }).catch(() => setBusy(''))
  }

  const toggleGuide = (name) => {
    if (guides[name]) {
      const n = { ...guides }; delete n[name]; setGuides(n); return
    }
    setBusy('g:' + name)
    fetch('/api/dsh-media/sp/fit/guide?n=' + encodeURIComponent(name))
      .then((r) => r.json()).then((j) => {
        setBusy('')
        if (j && j.ok) setGuides({ ...guides, [name]: j.guide })
      }).catch(() => setBusy(''))
  }

  const done = (data && data.done) || []
  const items = (data && data.todayItems) || []
  const WD = ['一', '二', '三', '四', '五', '六', '日']

  const guideBlock = (name) => {
    const g = guides[name]
    if (!g) {
      if (busy === 'g:' + name) return h('div', { style: { fontSize: 12, color: C.sub, marginTop: 8 } }, '读教程…')
      return null
    }
    return h('div', {
      style: {
        marginTop: 10, padding: '12px 14px', borderRadius: 9,
        background: C.base, border: '1px solid ' + C.border,
      },
    },
    h('div', { style: { fontSize: 12, color: C.gold, fontWeight: 600, marginBottom: 9 } }, g.target),
    h('div', { style: { fontSize: 10.5, letterSpacing: 1, color: C.sub, marginBottom: 5 } }, '怎么做'),
    h('ol', { style: { margin: 0, paddingLeft: 18 } },
      (g.steps || []).map((x, i) => h('li', {
        key: 's' + i, style: { fontSize: 12.5, lineHeight: 1.85, color: C.text, marginBottom: 3 },
      }, x))),
    (g.errors && g.errors.length)
      ? h('div', null,
        h('div', { style: { fontSize: 10.5, letterSpacing: 1, color: C.sub, margin: '11px 0 5px' } }, '别这么做'),
        h('ul', { style: { margin: 0, paddingLeft: 18 } },
          g.errors.map((x, i) => h('li', {
            key: 'e' + i, style: { fontSize: 12.5, lineHeight: 1.8, color: '#e0a894', marginBottom: 2 },
          }, x))))
      : null,
    g.easier
      ? h('div', { style: { marginTop: 11 } },
        h('div', { style: { fontSize: 10.5, letterSpacing: 1, color: C.sub, marginBottom: 5 } }, '做不动怎么办'),
        h('div', {
          style: {
            fontSize: 12.5, lineHeight: 1.85, color: '#8fd39b',
            background: 'color-mix(in srgb, #8fd39b 8%, transparent)',
            padding: '9px 11px', borderRadius: 7,
          },
        }, g.easier))
      : null,
    )
  }

  return h('div', { style: { display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0 } },
    h('div', { className: 'mw-dhead' },
      h(SmallBtn, { label: '‹ 身体管理台', onClick: onBack }),
      h('div', { className: 'mw-dtitle' }, '每日训练'),
      h('div', { style: { flex: '1 1 auto' } }),
      data ? h('div', { className: 'mw-dtag' },
        (data.streak > 0 ? `连续 ${data.streak} 天` : '今天开始')) : null,
    ),
    h('div', { className: 'mw-dbody', style: { flex: 1, minHeight: 0, overflowY: 'auto' } },
      !data ? h('div', { className: 'mw-empty' }, '读训练计划…')
        : h('div', null,
          h('div', { style: { fontSize: 20, fontWeight: 700, color: C.gold, marginBottom: 3 } },
            `周${WD[data.today]} · ${data.todayName}`),
          h('div', { style: { fontSize: 12.5, color: C.sub, marginBottom: 18 } }, data.todayFocus),
          items.length
            ? items.map((x) => {
              const on = done.indexOf(x.k) >= 0
              return h('div', {
                key: x.k,
                style: {
                  padding: '13px 16px', borderRadius: 11, marginBottom: 9,
                  background: on ? 'color-mix(in srgb, #8fd39b 8%, transparent)' : C.cell,
                  border: '1px solid ' + (on ? 'color-mix(in srgb, #8fd39b 35%, transparent)' : C.border),
                },
              },
              h('div', { style: { display: 'flex', alignItems: 'center', gap: 12 } },
                h('button', {
                  type: 'button',
                  onClick: () => check(x.k),
                  disabled: busy === x.k,
                  style: {
                    flex: 'none', width: 22, height: 22, borderRadius: 6, cursor: 'pointer',
                    border: '1.5px solid ' + (on ? '#8fd39b' : C.border2),
                    background: on ? 'color-mix(in srgb, #8fd39b 18%, transparent)' : 'transparent',
                    color: '#8fd39b', fontSize: 13, lineHeight: 1, padding: 0,
                  },
                }, on ? '✓' : ''),
                h('div', { style: { flex: 1, minWidth: 0 } },
                  h('div', { style: { fontSize: 15, fontWeight: 600, color: on ? '#8fd39b' : C.text } }, x.k),
                  h('div', { style: { fontSize: 12.5, color: C.gold, marginTop: 2 } }, x.s),
                  x.n ? h('div', { style: { fontSize: 11.5, color: C.sub, marginTop: 3, lineHeight: 1.6 } }, x.n) : null),
                h('button', {
                  type: 'button',
                  onClick: () => toggleGuide(x.k),
                  style: {
                    flex: 'none', fontSize: 10.5, padding: '3px 9px', borderRadius: 6, cursor: 'pointer',
                    border: '1px solid color-mix(in srgb, ' + C.gold + ' 40%, transparent)',
                    background: 'color-mix(in srgb, ' + C.gold + ' 10%, transparent)',
                    color: C.gold,
                  },
                }, guides[x.k] ? '收起' : '看怎么做'),
              ),
              guideBlock(x.k))
            })
            : h('div', {
              style: {
                padding: 22, textAlign: 'center', color: C.sub, fontSize: 13,
                background: C.cell, borderRadius: 11, border: '1px dashed ' + C.border,
              },
            }, '今天休息。肌肉是在休息时长出来的，别练。'),
          h('div', { style: { fontSize: 10.5, letterSpacing: 1.2, color: C.sub, margin: '22px 0 8px' } }, '这周安排'),
          (data.week || []).map((w) => h('div', {
            key: 'w' + w.d,
            style: {
              display: 'flex', gap: 10, alignItems: 'baseline', padding: '6px 0',
              fontSize: 12.5,
              background: w.today ? 'color-mix(in srgb, ' + C.gold + ' 8%, transparent)' : 'transparent',
              borderRadius: 6, paddingLeft: w.today ? 6 : 0,
            },
          },
          h('span', { style: { width: 16, color: C.sub } }, w.d),
          h('span', { style: { width: 80, color: w.items.length ? C.text : C.sub } }, w.name),
          h('span', { style: { flex: 1, color: C.sub, fontSize: 11.5 } }, w.focus))),
          h('div', { style: { fontSize: 10.5, letterSpacing: 1.2, color: C.sub, margin: '22px 0 8px' } }, '每天都要做'),
          (data.daily || []).map((x, i) => h('div', {
            key: 'd' + i, style: { fontSize: 12.5, color: C.sub, lineHeight: 1.9 },
          }, '· ' + x)),
        ),
    ),
  )
}

/* ---------- 睡前冥想 ---------- */
const MED_PLANS = [
  {
    id: 'breath5', nm: '呼吸 5 分钟', min: 5, ds: '数呼吸，最快静下来',
    cues: [[0, '坐好，背挺直。鼻子吸气 4 秒'], [20, '屏住 2 秒，再慢慢呼 6 秒'], [40, '不用控制，让呼吸自己走'],
      [60, '注意力放在鼻尖的气流上'], [120, '走神了没关系，拉回来就行'], [180, '心里默数：一、二、三'],
      [240, '再数一遍，数到十重来'], [290, '快结束了，最后一分钟'], [300, '慢慢睁眼']],
  },
  {
    id: 'body10', nm: '身体扫描 10 分钟', min: 10, ds: '从头到脚放松一遍',
    cues: [[0, '躺下，手放身体两侧'], [30, '把注意力放到头顶，让它放松'], [90, '往下走：额头、眼睛、下巴'],
      [150, '脖子、肩膀——这里最容易紧'], [210, '手臂、手掌、每根手指'], [270, '胸口、肚子，跟着呼吸起伏'],
      [330, '后背、腰、臀部'], [390, '大腿、膝盖'], [450, '小腿、脚踝、脚趾'],
      [510, '整个身体一起，从上往下放松'], [570, '快结束了，保持这个感觉'], [600, '慢慢睁眼']],
  },
  {
    id: 'sleep15', nm: '睡前 15 分钟', min: 15, ds: '躺床上，跟着睡着',
    cues: [[0, '躺好，关灯，手放肚子上'], [40, '吸气 4 秒，肚子鼓起来'], [80, '呼气 6 秒，肚子瘪下去'],
      [140, '想一件今天做得还行的小事'], [220, '再想一件明天要做的小事'], [300, '别想多了，就这两件'],
      [360, '身体从脚开始往下沉'], [450, '大腿沉了，背沉了，手沉了'], [540, '注意听房间里的声音，不用管它'],
      [660, '如果困了就睡，不用听完'], [780, '呼吸慢下来，越来越慢'], [870, '快结束了'], [900, '晚安']],
  },
  {
    id: 'focus3', nm: '专注 3 分钟', min: 3, ds: '刷完手机立刻做，把状态拉回来',
    cues: [[0, '停下手上的事，放下手机'], [15, '深吸一口气，慢慢呼出来'], [40, '看眼前的一个东西，什么都不想'],
      [70, '听最近的一个声音'], [100, '感受脚踩在地上的感觉'], [140, '差不多了，睁开眼'], [180, '好了']],
  },
]

function MedPanel({ onBack }) {
  const [plan, setPlan] = useState(null)
  const [left, setLeft] = useState(0)
  const [cue, setCue] = useState('')
  const [paused, setPaused] = useState(false)
  const [idx, setIdx] = useState(0)
  const timer = useRef(null)
  const actx = useRef(null)

  const beep = (freq, dur) => {
    try {
      if (!actx.current) actx.current = new (window.AudioContext || window.webkitAudioContext)()
      const o = actx.current.createOscillator(); const g = actx.current.createGain()
      o.type = 'sine'; o.frequency.value = freq
      const t = actx.current.currentTime
      g.gain.setValueAtTime(0.0001, t)
      g.gain.exponentialRampToValueAtTime(0.14, t + 0.02)
      g.gain.exponentialRampToValueAtTime(0.0001, t + dur)
      o.connect(g); g.connect(actx.current.destination)
      o.start(); o.stop(t + dur + 0.05)
    } catch (e) { }
  }

  const stop = (finished) => {
    if (timer.current) { clearInterval(timer.current); timer.current = null }
    setPlan(null); setCue(''); setIdx(0); setPaused(false)
    if (finished) { beep(396, 1.2); setTimeout(() => beep(528, 1.0), 700) }
  }

  const start = (p) => {
    setPlan(p); setLeft(p.min * 60); setIdx(0); setPaused(false); setCue(p.cues[0][1])
    beep(528, 0.5)
    if (timer.current) clearInterval(timer.current)
    let remain = p.min * 60
    timer.current = setInterval(() => {
      remain -= 1
      setLeft(remain)
      const passed = p.min * 60 - remain
      let cur = ''
      let ni = 0
      for (let i = 0; i < p.cues.length; i++) {
        if (passed >= p.cues[i][0]) { cur = p.cues[i][1]; ni = i }
      }
      setIdx((old) => { if (ni !== old) beep(660, 0.18); return ni })
      if (cur) setCue(cur)
      if (remain <= 0) { clearInterval(timer.current); timer.current = null; stop(true) }
    }, 1000)
  }

  useEffect(() => () => { if (timer.current) clearInterval(timer.current) }, [])

  const mm = Math.floor(left / 60); const ss = left % 60
  const pulse = 1 + 0.12 * Math.sin((plan ? plan.min * 60 - left : 0) / 4)

  if (!plan) {
    return h('div', { style: { display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0 } },
      h('div', { className: 'mw-dhead' },
        h(SmallBtn, { label: '‹ 身体管理台', onClick: onBack }),
        h('div', { className: 'mw-dtitle' }, '睡前冥想')),
      h('div', { className: 'mw-dbody', style: { flex: 1, minHeight: 0, overflowY: 'auto' } },
        h('div', { style: { fontSize: 13, color: C.sub, lineHeight: 1.8, marginBottom: 18 } },
          '睡前 10 分钟，脑子慢慢静下来。手机放一边，跟着字呼吸，眼睛可以闭着。'),
        MED_PLANS.map((p) => h('button', {
          key: p.id, type: 'button', onClick: () => start(p),
          className: 'mw-card',
          style: {
            display: 'block', width: '100%', textAlign: 'left', padding: '15px 18px',
            marginBottom: 10, cursor: 'pointer', background: C.cell,
            border: '1px solid ' + C.border2, borderRadius: 11,
          },
        },
        h('div', { style: { fontSize: 15.5, fontWeight: 600, color: C.text } }, p.nm),
        h('div', { style: { fontSize: 12, color: C.sub, marginTop: 3 } }, p.ds))),
      ))
  }

  return h('div', { style: { display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0 } },
    h('div', { className: 'mw-dhead' },
      h(SmallBtn, { label: '‹ 结束', onClick: () => stop(false) }),
      h('div', { className: 'mw-dtitle' }, plan.nm)),
    h('div', {
      className: 'mw-dbody',
      style: {
        flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column',
        alignItems: 'center', justifyContent: 'center', paddingBottom: 40,
      },
    },
    h('div', {
      style: {
        fontSize: 56, fontWeight: 200, color: C.gold,
        fontVariantNumeric: 'tabular-nums', letterSpacing: 2, marginBottom: 26,
      },
    }, mm + ':' + (ss < 10 ? '0' : '') + ss),
    h('div', {
      style: {
        width: 180, height: 180, borderRadius: '50%', display: 'flex',
        alignItems: 'center', justifyContent: 'center', marginBottom: 30,
        background: 'radial-gradient(circle, color-mix(in srgb, ' + C.gold + ' 12%, transparent), transparent 70%)',
        border: '1px solid color-mix(in srgb, ' + C.gold + ' 22%, transparent)',
      },
    }, h('div', {
      style: {
        width: 108, height: 108, borderRadius: '50%', transform: 'scale(' + pulse.toFixed(3) + ')',
        transition: 'transform .9s ease-in-out',
        background: 'radial-gradient(circle, color-mix(in srgb, ' + C.gold + ' 45%, transparent), color-mix(in srgb, ' + C.gold + ' 10%, transparent))',
      },
    })),
    h('div', {
      style: {
        fontSize: 17, lineHeight: 1.9, color: C.text, textAlign: 'center',
        minHeight: 68, maxWidth: 480, padding: '0 20px',
      },
    }, cue || '准备好了就深呼吸'),
    h('div', { style: { display: 'flex', gap: 10, marginTop: 26 } },
      h(SmallBtn, { label: paused ? '继续' : '暂停', onClick: () => {
        if (paused) { start(plan) } else { if (timer.current) { clearInterval(timer.current); timer.current = null } setPaused(true) }
      } }))),
  )
}

/* ---------- 书卡列表 ---------- */
function BookCardPanel({ onBack }) {
  const [items, setItems] = useState([])
  const [stat, setStat] = useState({})
  const [total, setTotal] = useState(0)
  const [v, setV] = useState('')
  const [open, setOpen] = useState(null)
  const [loading, setLoading] = useState(true)

  const load = (verdict) => {
    setLoading(true)
    const qs = '?limit=120' + (verdict ? '&verdict=' + encodeURIComponent(verdict) : '')
    fetch('/api/dsh-media/sp/books' + qs).then((r) => r.json()).then((j) => {
      setLoading(false)
      if (j && j.ok) { setItems(j.items || []); setStat(j.stat || {}); setTotal(j.total || 0) }
    }).catch(() => setLoading(false))
  }
  useEffect(() => { load('') }, [])

  const V = ['', '精读', '翻翻', '跳过']
  const vColor = (x) => x === '精读' ? '#8fd39b' : x === '翻翻' ? C.gold : C.sub

  return h('div', { style: { display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0 } },
    h('div', { className: 'mw-dhead' },
      h(SmallBtn, { label: '‹ 返回', onClick: onBack }),
      h('div', { className: 'mw-dtitle' }, '书库'),
      h('div', { style: { flex: '1 1 auto' } }),
      h('div', { className: 'mw-dtag' }, total + ' 张书卡')),
    h('div', { className: 'mw-dbody', style: { flex: 1, minHeight: 0, overflowY: 'auto' } },
      h('div', { style: { display: 'flex', gap: 8, marginBottom: 16 } },
        V.map((x) => h('button', {
          key: 'v' + x, type: 'button',
          onClick: () => { setV(x); load(x) },
          style: {
            padding: '6px 16px', borderRadius: 8, cursor: 'pointer', fontSize: 12.5,
            border: '1px solid ' + (v === x ? 'color-mix(in srgb, ' + C.gold + ' 50%, transparent)' : C.border2),
            background: v === x ? 'color-mix(in srgb, ' + C.gold + ' 12%, transparent)' : 'transparent',
            color: v === x ? C.gold : C.sub,
          },
        }, (x || '全部') + (stat[x] ? ' ' + stat[x] : '')))),
      loading ? h('div', { className: 'mw-empty' }, '读书卡…')
        : items.length ? items.map((it) => h('div', {
          key: it.id,
          style: {
            padding: '14px 16px', borderRadius: 11, marginBottom: 9,
            background: C.cell, border: '1px solid ' + C.border2, cursor: 'pointer',
          },
          onClick: () => setOpen(open === it.id ? null : it.id),
        },
        h('div', { style: { display: 'flex', alignItems: 'baseline', gap: 10 } },
          h('div', { style: { flex: 1, fontSize: 14.5, fontWeight: 600, color: C.text } }, it.title),
          h('span', {
            style: {
              flex: 'none', fontSize: 11, padding: '1px 7px', borderRadius: 4,
              border: '1px solid ' + vColor(it.verdict), color: vColor(it.verdict),
            },
          }, it.verdict)),
        h('div', { style: { fontSize: 12.5, color: C.sub, marginTop: 5, lineHeight: 1.7 } }, it.gist),
        open === it.id ? h('div', {
          style: {
            marginTop: 12, padding: '12px 14px', borderRadius: 9,
            background: C.base, border: '1px solid ' + C.border,
          },
        },
        h('div', { style: { fontSize: 10.5, letterSpacing: 1, color: C.sub, marginBottom: 6 } },
          '关键洞察 ' + (it.insights || []).length + ' 条'),
        (it.insights || []).map((x, i) => h('div', {
          key: 'i' + i,
          style: { fontSize: 12.5, lineHeight: 1.8, color: C.text, marginBottom: 4 },
        }, h('span', { style: { color: C.gold, marginRight: 6 } }, (i + 1) + '.'), x)),
        it.forWho ? h('div', { style: { marginTop: 10 } },
          h('div', { style: { fontSize: 10.5, color: C.sub, marginBottom: 4 } }, '适合谁'),
          h('div', { style: { fontSize: 12.5, color: C.text, lineHeight: 1.7 } }, it.forWho)) : null,
        it.why ? h('div', { style: { marginTop: 10 } },
          h('div', { style: { fontSize: 10.5, color: C.sub, marginBottom: 4 } }, '为什么这么判'),
          h('div', { style: { fontSize: 12.5, color: C.sub, lineHeight: 1.7 } }, it.why)) : null,
        ) : null,
      )) : h('div', { className: 'mw-empty' }, '没有书卡')),
  )
}

/* ---------- 身体管理台 ---------- */
function BodyLab() {
  const [active, setActive] = useState(null)
  if (active) {
    if (active.id === 'fit') return h(FitPanel, { onBack: () => setActive(null) })
    if (active.id === 'med') return h(MedPanel, { onBack: () => setActive(null) })
  }
  return h('div', { className: 'mw-root' },
    h('style', { key: 'mw-css', }, CSS),
    h('div', { className: 'mw-detail' },
      h('div', { className: 'mw-dhead' },
        h('div', { className: 'mw-dtitle' }, '身体管理台'),
        h('div', { className: 'mw-dtag' }, BODY_CARDS.length + ' 项'),
      ),
      h('div', { className: 'mw-dbody' },
        h('div', { style: { fontSize: 13, color: C.sub, lineHeight: 1.85, marginBottom: 18 } },
          '练 · 睡 · 吃。一个 64 公斤、体脂 30% 的人，问题不是胖，是肌肉少了二十公斤。'),
        h('div', {
          style: { display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(268px, 1fr))', gap: 12 },
        }, BODY_CARDS.map((c) => h('button', {
          key: c.id, type: 'button', className: 'mw-card is-accent',
          onClick: () => setActive(c),
          style: {
            textAlign: 'left', padding: '16px 18px', cursor: 'pointer',
            display: 'flex', flexDirection: 'column', gap: 6,
          },
        },
        h('div', { style: { fontSize: 15.5, fontWeight: 600, color: C.text } }, c.title),
        h('div', { style: { fontSize: 12, color: C.sub, lineHeight: 1.7 } }, c.desc),
        h('div', { style: { fontSize: 11, color: C.gold, marginTop: 4 } }, c.stat)))))),
  )
}

const TRAIN_KINDS = ['topic', 'retell', 'debate', 'title', 'summary', 'question', 'analogy']

function TrainPanel({ onBack, kind, name }) {
  const [task, setTask] = useState('')
  const [ans, setAns] = useState('')
  const [loading, setLoading] = useState(true)
  const [judging, setJudging] = useState(false)
  const [res, setRes] = useState(null)
  const [err, setErr] = useState('')

  const newTask = () => {
    setLoading(true); setErr(''); setRes(null); setAns('')
    fetch('/api/dsh-media/train/prompt', {
      method: 'POST', headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ kind }),
    }).then((r) => r.json()).then((j) => {
      setLoading(false)
      if (j && j.ok) setTask(j.task || '')
      else setErr((j && j.error) || '出不了题')
    }).catch(() => { setLoading(false); setErr('连不上') })
  }

  useEffect(() => { newTask() }, [kind])

  const submit = () => {
    if (ans.trim().length < 10) { setErr('多写几句再交'); return }
    setJudging(true); setErr(''); setRes(null)
    fetch('/api/dsh-media/train/judge', {
      method: 'POST', headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ kind, task, answer: ans }),
    }).then((r) => r.json()).then((j) => {
      setJudging(false)
      if (j && j.ok) setRes(j.result || {})
      else setErr((j && j.error) || '评不了')
    }).catch(() => { setJudging(false); setErr('连不上') })
  }

  const listBlock = (title, arr, color) => {
    if (!arr || !arr.length) return null
    return h('div', { style: { marginTop: 12 } },
      h('div', { style: { fontSize: 10.5, letterSpacing: 1, color: C.sub, marginBottom: 5 } }, title),
      arr.map((x, i) => {
        const t = (x && typeof x === 'object')
          ? (x.t ? `${x.t}（${x.s}）${x.why ? '：' + x.why : ''}` : JSON.stringify(x))
          : String(x)
        return h('div', {
          key: 'i' + i,
          style: { fontSize: 13, lineHeight: 1.8, color: color || C.sub },
        }, '· ' + t)
      }))
  }

  return h('div', { style: { display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0 } },
    h('div', { className: 'mw-dhead' },
      h(SmallBtn, { label: '‹ 能力提升台', onClick: onBack }),
      h('div', { className: 'mw-dtitle' }, name),
      h('div', { style: { flex: '1 1 auto' } }),
      h(SmallBtn, { label: '换一题', onClick: newTask }),
      h(SmallBtn, { label: '交上去，让 AI 评', tone: 'gold', onClick: submit }),
    ),
    h('div', { className: 'mw-dbody', style: { flex: 1, minHeight: 0, overflowY: 'auto' } },
      loading ? h('div', { className: 'mw-empty' }, '正在出题…')
        : h('div', {
          style: {
            padding: '14px 16px', borderRadius: 10, background: C.cell,
            border: '1px solid ' + C.border2, marginBottom: 16,
            fontSize: 15, lineHeight: 1.9, color: C.text, whiteSpace: 'pre-wrap',
          },
        }, task),
      h('div', { style: { fontSize: 11.5, letterSpacing: 1, color: C.gold, marginBottom: 8 } }, '你的答案'),
      h('textarea', {
        value: ans, onChange: (e) => setAns(e.target.value),
        placeholder: '在这儿作答。按 Win+H 可以直接语音输入。',
        style: {
          width: '100%', minHeight: 150, padding: 14, borderRadius: 10, resize: 'vertical',
          fontSize: 15, lineHeight: 1.9, background: C.cell, color: C.text,
          border: '1px solid ' + C.border2, outline: 'none', fontFamily: 'inherit',
        },
      }),
      err ? h('div', { className: 'mw-err', style: { marginTop: 10 } }, err) : null,
      judging ? h('div', { className: 'mw-empty', style: { marginTop: 14 } }, 'AI 正在看你的答案…') : null,
      res ? h('div', {
        style: {
          marginTop: 18, padding: '16px 18px', borderRadius: 10,
          border: '1px solid ' + C.border2, background: C.cell,
        },
      },
      h('div', { style: { display: 'flex', alignItems: 'baseline', gap: 12 } },
        res.score != null
          ? h('div', { style: { fontSize: 30, fontWeight: 800, color: C.gold, fontVariantNumeric: 'tabular-nums' } }, String(res.score))
          : null,
        h('div', { style: { fontSize: 11.5, letterSpacing: 1, color: C.sub } }, '分'),
      ),
      res.one_line ? h('div', { style: { fontSize: 13.5, color: C.text, lineHeight: 1.8, marginTop: 6 } }, res.one_line) : null,
      listBlock('好的地方', res.good || res.kept || res.real || res.works || [], '#9fc9a8'),
      listBlock('要改的', res.fix || res.missed || res.fake || res.breaks || res.leaks || res.lost, '#e0a894'),
      res.per_title && res.per_title.length ? listBlock('每个标题', res.per_title, C.sub) : null,
      res.best ? h('div', { style: { marginTop: 12 } },
        h('div', { style: { fontSize: 10.5, color: C.sub, marginBottom: 5 } }, '最该用'),
        h('div', { style: { fontSize: 13.5, color: C.gold } }, res.best)) : null,
      ) : null,
    ),
  )
}

function CorpusPanel({ onBack }) {
      const [list, setList] = useState([])
      const [q, setQ] = useState('')
      const [kw, setKw] = useState('')
      const [open, setOpen] = useState(null)
      const [err, setErr] = useState(null)

      useEffect(() => {
        const t = setTimeout(() => setKw(q.trim()), 400)
        return () => clearTimeout(t)
      }, [q])

      useEffect(() => {
        const url = '/api/dsh-media/views/list?limit=120' + (kw ? '&q=' + encodeURIComponent(kw) : '')
        jget(url)
          .then((j) => { if (j && j.ok) setList(j.views || []); else setErr((j && j.error) || '读不到') })
          .catch(() => setErr('接口没通，宿主可能没重启'))
      }, [kw])

      const openOne = (v) => {
        setOpen({ loading: true, id: v.id })
        jget('/api/dsh-media/views/get?id=' + encodeURIComponent(v.id))
          .then((j) => { if (j && j.ok) setOpen(j.view); else setOpen({ error: (j && j.error) || '读不到' }) })
          .catch(() => setOpen({ error: '请求失败' }))
      }

      const exportAll = () => {
        const md = ['# 我的语料库', '', '导出时间：' + new Date().toLocaleString('zh-CN'), '']
          .concat(list.map((v) => [
            '## ' + (v.title || '（无标题）'),
            '',
            '- 时间：' + (v.created_at || ''),
            '- 类型：' + (v.kind === 'topic' ? '选题' : '有感而发'),
            v.ai_review && v.ai_review.score != null ? '- 自评：' + v.ai_review.score + ' · ' + (v.ai_review.verdict || '') : '',
            '',
            (v.content || ''),
            '',
          ].filter(Boolean).join('\n')))
          .join('\n')
        try {
          const blob = new Blob([md], { type: 'text/markdown;charset=utf-8' })
          const a = document.createElement('a')
          a.href = URL.createObjectURL(blob)
          a.download = '我的语料库-' + new Date().toISOString().slice(0, 10) + '.md'
          a.click()
          setTimeout(() => URL.revokeObjectURL(a.href), 3000)
        } catch { }
      }

      const box = { whiteSpace: 'pre-wrap', fontSize: 14.5, lineHeight: 1.85, color: C.text, background: C.cell, border: '1px solid ' + C.border2, borderRadius: 10, padding: '14px 16px' }

      return h('div', { className: 'mw-root' },
        h('style', { key: 'mw-css' }, CSS),
        h('div', { className: 'mw-detail' },
          h('div', { className: 'mw-dhead' },
            h('button', { type: 'button', className: 'mw-back', onClick: onBack }, '‹ 工具列表'),
            h('div', { className: 'mw-dtitle' }, '我的语料库'),
            h('div', { className: 'mw-dtag' }, list.length + ' 条 · 私有'),
            h('div', { style: { flex: '1 1 auto' } }),
            h(SmallBtn, { label: '导出 md', onClick: exportAll }),
            h('button', {
              type: 'button', className: 'mw-hot-btn', onClick: () => { setOpen(null); setQ(''); setKw('') },
              style: { marginLeft: 8 },
            }, '刷新'),
          ),
          h('div', { className: 'mw-dbody' },
            err ? h('div', { className: 'mw-err' }, err) : null,
            h('div', { style: { fontSize: 12.5, color: C.sub, lineHeight: 1.8, marginBottom: 14 } },
              '这是你自己的话，只出不进：不进稿库、不被当成素材、不参与任何拆分。以后选题、写稿都从这里取你的原话。'),
            h('input', {
              value: q, onChange: (e) => setQ(e.target.value),
              placeholder: '搜你说过的话…',
              style: {
                width: '100%', boxSizing: 'border-box', background: C.cell, color: C.text,
                border: '1px solid ' + C.border2, borderRadius: 9, padding: '9px 13px',
                fontSize: 13.5, marginBottom: 16,
              },
            }),

            open ? h('div', { style: { marginBottom: 18 } },
              h('div', { style: { display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 } },
                h(SmallBtn, { label: '‹ 返回列表', onClick: () => setOpen(null) }),
                h('div', { style: { fontSize: 15, fontWeight: 620, color: C.text } }, open.title || '（无标题）'),
                h('div', { style: { fontSize: 11.5, color: C.sub } }, open.created_at || ''),
              ),
              open.loading ? h('div', { className: 'mw-empty' }, '读原文…')
                : open.error ? h('div', { className: 'mw-err' }, open.error)
                  : h('div', null,
                    h('div', { style: box }, open.content),
                    open.tags ? h('div', { style: { fontSize: 12, color: C.sub, marginTop: 8 } }, '标签：' + open.tags) : null,
                    h('div', { style: { marginTop: 14 } }, h(ReviewBlock, { review: open.ai_review })),
                  ),
            ) : null,

            list.length === 0
              ? h('div', { className: 'mw-empty' }, kw ? '没搜到这条。' : '语料库还是空的。去「我的观点」写第一条。')
              : list.map((v) => h('button', {
                key: v.id, type: 'button', onClick: () => (open && open.id === v.id ? setOpen(null) : openOne(v)),
                style: {
                  display: 'block', width: '100%', textAlign: 'left', cursor: 'pointer',
                  background: 'transparent', border: 'none', borderTop: '1px solid ' + C.border,
                  padding: '13px 2px 14px',
                },
              },
              h('div', { style: { display: 'flex', gap: 10, alignItems: 'baseline' } },
                h('span', { style: { fontSize: 15, fontWeight: 600, color: C.text, flex: '1 1 auto', minWidth: 0 } }, v.title || '（无标题）'),
                h('span', { style: { fontSize: 11.5, color: C.sub, opacity: .7, fontVariantNumeric: 'tabular-nums' } }, (v.chars || 0) + ' 字'),
              ),
              h('div', { style: { fontSize: 12.5, color: C.sub, marginTop: 5, lineHeight: 1.7, overflow: 'hidden' } }, (v.content || '').slice(0, 90)),
              )),
          ),
        ),
      )
    }

    function Detail({ card, onBack, hot, onRefresh, refreshing, err, summary, idea, autoSt, onWrite, writeTopic, onClearWrite }) {
      if (card.id === 'topics') {
        return h(TopicsPanel, { onBack, onWrite })
      }
      if (card.id === 'pool') {
        return h(ViewsPoolPanel, { onBack })
      }
      if (card.id === 'ideas') {
        return h(IdeasPanel, { onBack })
      }
      if (card.id === 'self') {
        return h(SelfPanel, {
          key: 'self-' + (writeTopic ? writeTopic.id : 'free'),
          onBack,
          topic: writeTopic || null,
          onWriteFree: onClearWrite,
        })
      }
      if (card.id === 'corpus') {
        return h(CorpusPanel, { onBack })
      }
      if (card.id === 'hot') {
        return h(HotPanel, { onBack, hot, onRefresh, refreshing, err, autoSt })
      }
      if (card.id === 'capture') {
        return h(CapturePanel, { onBack })
      }
      if (card.id === 'fit') {
        return h(FitPanel, { onBack })
      }
      if (card.id === 'med') {
        return h(MedPanel, { onBack })
      }
      if (card.id === 'books') {
        return h(BookCardPanel, { onBack })
      }
      if (card.id === 'speech') {
        return h(SpeechPanel, { onBack })
      }
      if (card.group === 'grow' && TRAIN_KINDS.indexOf(card.id) >= 0) {
        return h(TrainPanel, { onBack, kind: card.id, name: card.title })
      }
      if (card.group === 'grow') {
        return h(SpeechPanel, { onBack, pending: card.title })
      }
      if (card.id === 'personas') {
        return h(PersonaPanel, { onBack })
      }
      if (card.id === 'roundtable') {
        return h(RoundTablePanel, { onBack })
      }
      if (card.id === 'inspire') {
        return h(IdeaPanel, { onBack, idea, autoSt })
      }
      if (card.id === 'library') {
        return h(LibraryPanel, { onBack, summary })
      }
      return h('div', { className: 'mw-root' },
        h('style', { key: 'mw-css' }, CSS),
        h('div', { className: 'mw-detail' },
          h('div', { className: 'mw-dhead' },
            h('button', { type: 'button', className: 'mw-back', onClick: onBack }, '‹ 工具列表'),
            h('div', { className: 'mw-dtitle' }, card.title),
            card.tag ? h('div', { className: 'mw-dtag' }, card.tag) : null,
          ),
          h('div', { className: 'mw-dbody' },
            h('div', { className: 'mw-badge' }, 'V0 骨架 · 这块还没做'),
            h('div', { className: 'mw-dtext' }, card.detail),
          ),
        ),
      )
    }

    function MediaWorkbench() {
      // 记住上次打开的是哪张卡（采集台/稿库/选题池…）：切走再回来还在原来那一页
      const [active, setActive] = useState(() => {
        try {
          const raw = window.localStorage.getItem('mw-active')
          const o = raw ? JSON.parse(raw) : null
          return o && o.id ? o : null
        } catch { return null }
      })
      useEffect(() => {
        try {
          if (active && active.id) window.localStorage.setItem('mw-active', JSON.stringify(active))
          else window.localStorage.removeItem('mw-active')
        } catch { }
      }, [active && active.id])
      const [writeTopic, setWriteTopic] = useState(null)
      const [poolStat, setPoolStat] = useState(null)
      const [hot, setHot] = useState(null)
      const [summary, setSummary] = useState(null)
      const [idea, setIdea] = useState(null)
      const [refreshing, setRefreshing] = useState(false)
      const [err, setErr] = useState(null)
      const [autoSt, setAutoSt] = useState(null)
      const seenAuto = useRef({ hot: 0, idea: 0 })

      const readJson = async (url) => {
        const r = await fetch(url)
        const txt = await r.text()
        if (!txt) throw new Error(`HTTP ${r.status}，响应为空（接口可能没注册）`)
        try {
          return JSON.parse(txt)
        } catch {
          throw new Error(`HTTP ${r.status}，返回不是 JSON：${txt.slice(0, 90)}`)
        }
      }

      const loadHot = (silent) => {
        if (!silent) setErr(null)
        readJson('/api/dsh-media/hot')
          .then((j) => {
            if (j && j.ok) setHot(j)
            else {
              setHot(null)
              if (!silent) setErr('接口通了但没读到数据：' + (j && (j.reason || j.error) ? (j.reason || j.error) : '未知'))
            }
          })
          .catch((e) => { if (!silent) setErr('读不到热点接口：' + String(e && e.message ? e.message : e)) })
      }

      // 灵感：读回来，缺角度就让模型补，补完再读一次
      const loadIdea = () => {
        return readJson('/api/dsh-media/idea').then((j) => {
          if (!j || !j.ok) return
          setIdea(j)
          const items = (j.data && j.data.items) || []
          const need = items.some((x) => !x.angle || !x.question)
          if (!need) return
          return fetch('/api/dsh-media/idea/refine', { method: 'POST' })
            .then((r) => r.json())
            .then((res) => {
              if (res && res.ok && res.updated) return readJson('/api/dsh-media/idea').then((j2) => { if (j2 && j2.ok) setIdea(j2) })
            })
            .catch(() => { })
        }).catch(() => { })
      }

      React.useEffect(() => { loadHot(false) }, [])

      // 选题池 / 观点 / 语料库的条数（卡片上的数字）
      const loadPoolStat = () => readJson('/api/dsh-media/pool/stats')
        .then((j) => { if (j && j.ok) setPoolStat(j) })
        .catch(() => { })

      React.useEffect(() => { loadPoolStat() }, [])

      // 库总览：让卡片上的 0 变成真数字
      React.useEffect(() => {
        readJson('/api/dsh-media/summary')
          .then((j) => { if (j && j.ok) setSummary(j) })
          .catch(() => { })
      }, [])

      React.useEffect(() => { loadIdea() }, [])

      // 自动任务状态：30 秒看一次，后台跑完自动把新数据拉上屏
      React.useEffect(() => {
        let dead = false
        const tick = () => {
          readJson('/api/dsh-media/auto/status').then((s) => {
            if (dead || !s || !s.ok) return
            setAutoSt(s)
            const hAt = (s.hot && s.hot.at) || 0
            const iAt = (s.idea && s.idea.at) || 0
            if (!s.hot.running && hAt && hAt !== seenAuto.current.hot) loadHot(true)
            if (!s.idea.running && iAt && iAt !== seenAuto.current.idea) loadIdea()
            seenAuto.current = { hot: hAt, idea: iAt }
          }).catch(() => { })
        }
        tick()
        const t = setInterval(tick, 30000)
        return () => { dead = true; clearInterval(t) }
      }, [])

      // 手动抓取中轮询，最多等 5 分钟就放弃，避免按钮永远转
      React.useEffect(() => {
        if (!refreshing) return undefined
        let n = 0
        const t = setInterval(() => {
          n += 1
          if (n > 40) { setRefreshing(false); return }
          readJson('/api/dsh-media/hot').then((j) => {
            if (j && j.ok && j.data && j.isToday) {
              setHot(j); setRefreshing(false)
            }
          }).catch(() => {})
        }, 8000)
        return () => clearInterval(t)
      }, [refreshing])

      const onRefresh = () => {
        setRefreshing(true); setErr(null)
        fetch('/api/dsh-media/hot/refresh', { method: 'POST' })
          .then((r) => r.json())
          .then((j) => { if (!j || !j.ok) { setRefreshing(false); setErr('抓取启动失败：' + (j && j.error)) } })
          .catch((e) => { setRefreshing(false); setErr('抓取启动失败：' + String(e && e.message ? e.message : e)) })
      }

      // 选题池点「写这个」→ 直接进「我的观点」并带上这条选题
      const onWrite = (t) => {
        setWriteTopic(t || null)
        setActive({ id: 'self', group: 'work', title: '我的观点', desc: '', tag: '' })
      }
      const onClearWrite = () => setWriteTopic(null)

      if (active) {
        return h(Detail, {
          card: active, onBack: () => { setActive(null); setWriteTopic(null); loadPoolStat() },
          hot, onRefresh, refreshing, err, summary, idea, autoSt,
          onWrite, writeTopic, onClearWrite,
        })
      }
      return h(CardWall, { onOpen: setActive, hot, summary, idea, autoSt, poolStat })
    }

    /* ---------------------------------------------------------------- 注册 */
    const name = 'dsh-media-workbench'
    const inject = []

    function apply() {
      try {
        if (typeof document !== 'undefined' && !document.getElementById('dsh-media-workbench-style')) {
          const s = document.createElement('style')
          s.id = 'dsh-media-workbench-style'
          s.textContent = CSS
          document.head.appendChild(s)
        }
      } catch { }

      const registry = window.__DSH_WORKBENCHES__ || (window.__DSH_WORKBENCHES__ = [])
      // 两个并列的工作台：需求发掘台排在前面，自媒体工作台在后
      const entries = [
        {
          id: 'idea',
          title: '需求发掘台',
          desc: '外面在涨什么 / 有没有我能做的',
          order: 10,
          Icon: IdeaIcon,
          Component: IdeaLab,
        },
        {
          id: 'grow',
          title: '能力提升台',
          desc: '开口练 / 即兴 / 复述 / 辩论 / 标题 / 摘要',
          order: 15,
          Icon: GrowIcon,
          Component: GrowLab,
        },
        {
          id: 'media',
          title: '自媒体工作台',
          desc: '采集 / 稿库 / 选题 / 我的观点 / 我的语料库 / 顾问 / 复盘',
          order: 20,
          Icon: HubIcon,
          Component: MediaWorkbench,
        },
        {
          id: 'body',
          title: '身体管理台',
          desc: '每日训练 / 睡前冥想 · 练 · 睡 · 吃',
          order: 40,
          Icon: GrowIcon,
          Component: BodyLab,
        },
      ]
      for (const entry of entries) {
        const found = registry.findIndex((x) => x && x.id === entry.id)
        if (found >= 0) registry[found] = entry
        else registry.push(entry)
      }
      try { window.dispatchEvent(new Event('dsh-workbench-changed')) } catch { }

      return () => {
        for (const id of ['idea', 'media', 'grow']) {
          const i = registry.findIndex((x) => x && x.id === id)
          if (i >= 0) registry.splice(i, 1)
        }
        try { window.dispatchEvent(new Event('dsh-workbench-changed')) } catch { }
      }
    }

    // __panels 只给离线冒烟脚本用（假 React 直接逐个渲染面板），界面不读它
    const __panels = {
      MediaWorkbench, GrowLab, TopicsPanel, SelfPanel, CorpusPanel, Composer, Detail,
    }

    return { name, inject, apply, __panels }
  },
})
