# -*- coding: utf-8 -*-
"""用 trending.db 里的真实数据生成工作台总面板预览页。"""
import json
import os
import re
import sqlite3
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, 'trending.db')
OUT = os.path.join(HERE, 'preview.html')


def load():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    d = con.execute('select max(date) from snapshots').fetchone()[0]
    rows = [dict(r) for r in con.execute(
        'select s.rank,s.repo,s.stars,s.stars_today,r.lang,r.desc'
        ' from snapshots s left join repos r on r.repo=s.repo'
        ' where s.date=? order by s.rank', (d,))]
    con.close()
    return d, rows


EMOJI = re.compile(
    '[\U0001F000-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF\uFE0F\u200D\u20E3]+',
)


def clean_desc(s):
    """简介里常有 emoji 和徽章，抠掉后压成一行，截 46 字。"""
    s = EMOJI.sub('', s)
    s = re.sub(r'\s+', ' ', s).strip(' .·|-')
    if len(s) > 46:
        s = s[:46].rstrip() + '…'
    return s


def main():
    d, rows = load()
    total = sum(r['stars_today'] or 0 for r in rows)
    langs = {}
    for r in rows:
        k = r['lang'] or '未标注'
        langs[k] = langs.get(k, 0) + 1
    langs = sorted(langs.items(), key=lambda x: -x[1])
    top_lang = langs[0][0] if langs else '—'
    avg = round(total / len(rows)) if rows else 0

    by_rise = sorted(rows, key=lambda r: -(r['stars_today'] or 0))
    rank_of = {r['repo']: i for i, r in enumerate(by_rise, 1)}

    items = []
    for r in by_rise:
        items.append({
            'repo': r['repo'],
            'lang': r['lang'] or '',
            'desc': clean_desc(r['desc'] or ''),
            'today': r['stars_today'] or 0,
            'total': r['stars'] or 0,
            'rank': r['rank'],
        })

    data = {
        'date': d,
        'count': len(rows),
        'total': total,
        'avg': avg,
        'topLang': top_lang,
        'langs': langs,
        'items': items,
    }
    html = TPL.replace('__DATA__', json.dumps(data, ensure_ascii=False))
    with open(OUT, 'w', encoding='utf-8') as f:
        f.write(html)
    print('写好了', OUT, '条数', len(rows))


TPL = r'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>GitHub 热榜总面板</title>
<style>
  *{box-sizing:border-box}
  body{margin:0;background:#15181d;color:#e8e9ec;
    font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;
    font-size:13px;line-height:1.65;-webkit-font-smoothing:antialiased}
  .wrap{max-width:1180px;margin:0 auto;padding:22px 26px 30px}
  /* 顶栏 */
  .head{display:flex;align-items:flex-end;gap:14px;padding-bottom:16px;
    border-bottom:1px solid rgba(255,255,255,.09)}
  .mark{width:34px;height:34px;border-radius:9px;flex:0 0 auto;
    background:linear-gradient(140deg,#3a2f18,#15181d);border:1px solid rgba(201,162,75,.45);
    display:flex;align-items:center;justify-content:center;font-size:15px;color:#e6c879}
  .t1{font-size:19px;font-weight:650;letter-spacing:.2px}
  .t2{font-size:12.5px;color:#8b929f;margin-top:1px}
  .grow{flex:1}
  .pill{font-size:12.5px;color:#8b929f;display:flex;align-items:center;gap:6px}
  .dot{width:6px;height:6px;border-radius:50%;background:#57b97f;box-shadow:0 0 0 3px rgba(87,185,127,.15)}
  /* KPI */
  .kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:11px;margin:16px 0 18px}
  .kpi{background:#1c2027;border:1px solid rgba(255,255,255,.08);border-radius:9px;padding:13px 15px}
  .kpi b{display:block;font-size:30px;line-height:1.15;font-weight:680;
    color:#f2dfa6;font-variant-numeric:tabular-nums;letter-spacing:-.5px}
  .kpi span{font-size:12.5px;color:#8b929f}
  /* 主体 */
  .cols{display:grid;grid-template-columns:1fr 300px;gap:16px;align-items:start}
  .panel{background:#1c2027;border:1px solid rgba(255,255,255,.08);border-radius:9px;overflow:hidden}
  .ph{display:flex;align-items:center;justify-content:space-between;
    padding:12px 15px;border-bottom:1px solid rgba(255,255,255,.07)}
  .ph b{font-size:14.5px;font-weight:620}
  .ph em{font-style:normal;font-size:12.5px;color:#8b929f}
  /* 榜行 */
  .row{display:grid;grid-template-columns:28px minmax(0,1fr) 78px 76px;gap:10px;
    padding:10px 15px;border-bottom:1px solid rgba(255,255,255,.045);align-items:center}
  .row>*{min-width:0}
  .row:last-child{border-bottom:0}
  .row:nth-child(-n+3) .rk{color:#e6c879}
  .rk{font-size:12.5px;color:#6c7482;font-variant-numeric:tabular-nums;text-align:right}
  .nm{font-size:13.5px;font-weight:600;color:#e8e9ec;white-space:nowrap;
    overflow:hidden;text-overflow:ellipsis}
  .nm i{font-style:normal;color:#6c7482;font-weight:400}
  .ds{font-size:12.5px;color:#8b929f;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-top:1px}
  .lg{font-size:12px;color:#9aa3b2;background:rgba(255,255,255,.05);
    border:1px solid rgba(255,255,255,.07);border-radius:5px;padding:1px 7px;
    justify-self:start;white-space:nowrap}
  .ts{text-align:right;font-variant-numeric:tabular-nums}
  .ts b{color:#e6c879;font-size:14.5px;font-weight:650}
  .ts span{display:block;font-size:11.5px;color:#6c7482}
  /* 右栏 */
  .side{display:flex;flex-direction:column;gap:14px}
  .lb{display:flex;align-items:center;gap:9px;padding:7px 15px}
  .lb i{font-style:normal;width:56px;font-size:12.5px;color:#b9c0cc;flex:0 0 auto}
  .bar{flex:1;height:7px;border-radius:99px;background:rgba(255,255,255,.06);overflow:hidden}
  .bar s{display:block;height:100%;background:#c9a24b;border-radius:99px}
  .lb em{font-style:normal;font-size:12px;color:#8b929f;width:20px;text-align:right;font-variant-numeric:tabular-nums}
  .state{padding:4px 15px 12px;font-size:12.5px;color:#8b929f}
  .state div{display:flex;justify-content:space-between;padding:5px 0;border-bottom:1px dashed rgba(255,255,255,.06)}
  .state div:last-child{border:0}
  .state b{color:#cfd4dc;font-weight:500}
  .note{margin-top:14px;font-size:12.5px;color:#6c7482;line-height:1.7}
</style></head>
<body><div class="wrap">
  <div class="head">
    <div class="mark">★</div>
    <div>
      <div class="t1">GitHub 热榜</div>
      <div class="t2">今天在涨什么 · 谁在冲 · 值不值得看</div>
    </div>
    <div class="grow"></div>
    <div class="pill"><span class="dot"></span>数据已更新 <span id="dt"></span></div>
  </div>

  <div class="kpis">
    <div class="kpi"><b id="k1"></b><span>今日上榜项目</span></div>
    <div class="kpi"><b id="k2"></b><span>一天总涨星</span></div>
    <div class="kpi"><b id="k3"></b><span>平均涨星 / 个</span></div>
    <div class="kpi"><b id="k4" style="font-size:24px"></b><span>最扎堆语言</span></div>
  </div>

  <div class="cols">
    <div class="panel">
      <div class="ph"><b>涨星榜</b><em>按今天新增星数排</em></div>
      <div id="list"></div>
    </div>
    <div class="side">
      <div class="panel">
        <div class="ph"><b>语言分布</b><em>16 个项目</em></div>
        <div id="langs" style="padding:8px 0 10px"></div>
      </div>
      <div class="panel">
        <div class="ph"><b>采集状态</b></div>
        <div class="state">
          <div><span>数据源</span><b>GitHub Trending 日榜</b></div>
          <div><span>最近采集</span><b id="s1">—</b></div>
          <div><span>历史天数</span><b id="s2">1 天</b></div>
          <div><span>下次采集</span><b>明天 08:00</b></div>
        </div>
      </div>
      <div class="note">判断层还没接：每个项目「干什么 / 一个人能不能做 / 值不值得抄」正在做。</div>
    </div>
  </div>
</div>
<script>
const D = __DATA__;
const nf = (n) => n.toLocaleString('en-US');
document.getElementById('dt').textContent = D.date;
document.getElementById('k1').textContent = D.count;
document.getElementById('k2').textContent = nf(D.total);
document.getElementById('k3').textContent = nf(D.avg);
document.getElementById('k4').textContent = D.topLang;
document.getElementById('s1').textContent = D.date;

const list = document.getElementById('list');
D.items.forEach((it, i) => {
  const row = document.createElement('div');
  row.className = 'row';
  const [owner, name] = it.repo.split('/');
  row.innerHTML = `
    <div class="rk">${i + 1}</div>
    <div>
      <div class="nm">${owner}<i>/</i>${name}</div>
      <div class="ds">${it.desc || '（没写简介）'}</div>
    </div>
    <div class="lg">${it.lang || '—'}</div>
    <div class="ts"><b>+${nf(it.today)}</b><span>共 ${nf(it.total)}</span></div>`;
  list.appendChild(row);
});

const maxC = Math.max(...D.langs.map(x => x[1]));
const langs = document.getElementById('langs');
D.langs.forEach(([k, c]) => {
  const d = document.createElement('div');
  d.className = 'lb';
  d.innerHTML = `<i>${k}</i><div class="bar"><s style="width:${(c / maxC) * 100}%"></s></div><em>${c}</em>`;
  langs.appendChild(d);
});
</script></body></html>'''

if __name__ == '__main__':
    main()
