/**
 * dsh-finance-health —— 宿主端：读宏观数据 / 出体检报告 / 一键更新
 *
 * 数据目录默认 E:\desktop\财务健康，可用 DSH_FINANCE_DIR 覆盖；
 * Python 解释器默认本机 Python312，可用 DSH_FINANCE_PYTHON 覆盖。
 */
import { spawn } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'

const DIR = process.env.DSH_FINANCE_DIR || 'E:\\desktop\\财务健康'
const PY = process.env.DSH_FINANCE_PYTHON
  || (process.env.LOCALAPPDATA || 'C:\\Users\\Public\\AppData\\Local') + '\\Programs\\Python\\Python312\\python.exe'

const DATA_DIR = path.join(DIR, 'data')

/** 更新任务状态（单例，同一时刻只跑一个） */
const job = {
  running: false,
  step: '',
  error: null,
  startedAt: 0,
  finishedAt: 0,
  log: [],
}

function pushLog(line) {
  let s = String(line).trim()
  if (!s) return
  // 丢掉 tqdm 进度条：形如 "47%|▏▎▍ | 9/19 [00:02<00:02, 3.47it/s]"
  if (/\d+%\|/.test(s) || /it\/s|s\/it/.test(s)) return
  if (/[█▏▎▍▌▋▊▉━─]{2,}/.test(s)) return
  job.log.push(s.slice(0, 300))
  if (job.log.length > 60) job.log.shift()
}

/** 找最新的 macro-YYYY-MM-DD.json */
function latestMacroFile() {
  let files = []
  try {
    files = fs.readdirSync(DATA_DIR).filter((f) => /^macro-\d{4}-\d{2}-\d{2}\.json$/.test(f))
  } catch {
    return null
  }
  if (!files.length) return null
  files.sort()
  return path.join(DATA_DIR, files[files.length - 1])
}

function readJson(p) {
  try {
    return JSON.parse(fs.readFileSync(p, 'utf8'))
  } catch {
    return null
  }
}

/** 从 items 里取每项最后一条，算环比 */
function digest(items) {
  const out = []
  const push = (key, label, value, unit, month, delta) => {
    out.push({ key, label, value, unit, month, delta })
  }
  const last2 = (arr) => (Array.isArray(arr) && arr.length ? arr.slice(-2) : [])
  const num = (v) => (typeof v === 'number' && isFinite(v) ? v : null)

  const pick = (k) => (items && Array.isArray(items[k]) ? items[k] : [])

  {
    const a = last2(pick('pmi'))
    if (a.length) {
      const v = num(a[a.length - 1].v)
      const p = a.length > 1 ? num(a[a.length - 2].v) : null
      push('pmi', '制造业 PMI', v, '', a[a.length - 1].m, p == null ? null : +(v - p).toFixed(2))
    }
  }
  {
    const a = last2(pick('retail'))
    if (a.length) {
      const v = num(a[a.length - 1].v)
      const p = a.length > 1 ? num(a[a.length - 2].v) : null
      push('retail', '社零同比', v, '%', a[a.length - 1].m, p == null ? null : +(v - p).toFixed(2))
    }
  }
  {
    const a = last2(pick('cpi'))
    if (a.length) {
      const v = num(a[a.length - 1].v)
      const p = a.length > 1 ? num(a[a.length - 2].v) : null
      push('cpi', 'CPI 同比', v, '%', a[a.length - 1].m, p == null ? null : +(v - p).toFixed(2))
    }
  }
  {
    const a = last2(pick('unemployment'))
    if (a.length) {
      const v = num(a[a.length - 1].v)
      const p = a.length > 1 ? num(a[a.length - 2].v) : null
      push('unemployment', '城镇调查失业率', v, '%', a[a.length - 1].m, p == null ? null : +(v - p).toFixed(2))
    }
  }
  {
    const a = last2(pick('money'))
    if (a.length) {
      const it = a[a.length - 1]
      const m1 = num(it.m1)
      const m2 = num(it.m2)
      const gap = m1 != null && m2 != null ? +(m1 - m2).toFixed(1) : null
      push('money', 'M1−M2 剪刀差', gap, '个百分点', it.m, null)
    }
  }
  {
    const a = last2(pick('bond'))
    if (a.length) {
      const it = a[a.length - 1]
      push('bond', '10 年国债', num(it.cn10), '%', it.d, null)
    }
  }
  {
    const a = last2(pick('gold'))
    if (a.length) {
      const it = a[a.length - 1]
      push('gold', '金价', num(it.close), '元/克', it.d, null)
    }
  }
  {
    const a = last2(pick('power'))
    if (a.length) {
      const v = num(a[a.length - 1].yoy)
      const p = a.length > 1 ? num(a[a.length - 2].yoy) : null
      push('power', '全社会用电量同比', v, '%', a[a.length - 1].m, p == null ? null : +(v - p).toFixed(2))
    }
  }
  // ── 市场行情：日涨跌幅 = 今日收盘 vs 上一交易日收盘 ──
  const chg = (arr) => {
    if (!Array.isArray(arr) || arr.length < 2) return null
    const c1 = num(arr[arr.length - 1].c)
    const c0 = num(arr[arr.length - 2].c)
    if (c1 == null || c0 == null || !c0) return null
    return +(((c1 - c0) / c0) * 100).toFixed(2)
  }
  const idx = (key, label, unit = '') => {
    const a = pick(key)
    if (!a.length) return
    const last = a[a.length - 1]
    push(key, label, num(last.c), unit, last.d, chg(a))
  }
  idx('us_nasdaq', '纳指')
  idx('us_sp500', '标普 500')
  idx('us_dow', '道指')
  idx('cn_sh', '上证')
  idx('hk_hsi', '恒生')
  idx('us_bond10', '美债 10 年', '%')
  idx('dollar_index', '美元指数')
  idx('rmb_usd', '人民币中间价', '元/100美元')
  idx('shibor', '隔夜 Shibor', '%')
  idx('copper', '沪铜', '元/吨')
  idx('crude', '原油 SC', '元/桶')
  idx('steel', '螺纹钢', '元/吨')
  idx('jp_nikkei', '日经 225')
  idx('kr_kospi', '韩国 KOSPI')
  idx('tw_tai', '台湾加权')
  idx('de_dax', '德国 DAX')
  idx('uk_ftse', '英国富时 100')
  idx('fr_cac', '法国 CAC40')
  idx('in_sensex', '印度 SENSEX')
  idx('br_bovespa', '巴西 BOVESPA')
  idx('bdi', '波罗的海 BDI')
  idx('crb', '路透 CRB 商品')

  return out
}

function statusPayload() {
  const f = latestMacroFile()
  const date = f ? path.basename(f).replace('macro-', '').replace('.json', '') : null
  const macro = f ? readJson(f) : null
  let report = null
  let reportMd = ''
  if (date) {
    const rp = path.join(DIR, `体检-${date}.md`)
    try {
      reportMd = fs.readFileSync(rp, 'utf8')
      report = { date, chars: reportMd.length }
    } catch {
      report = null
    }
  }
  return {
    ok: true,
    dir: DIR,
    date,
    collectedAt: macro?.at || null,
    metrics: macro?.items ? digest(macro.items) : [],
    errors: Array.isArray(macro?.errors) ? macro.errors : [],
    report,
    reportMd,
    job: { running: job.running, step: job.step, error: job.error, log: job.log.slice(-12) },
  }
}

function runScript(script) {
  return new Promise((resolve) => {
    let p
    try {
      p = spawn(PY, [script], { cwd: DIR, windowsHide: true })
    } catch (e) {
      pushLog('启动失败 ' + script + '：' + (e?.message || e))
      resolve(-1)
      return
    }
    p.stdout?.on('data', (d) => pushLog(String(d)))
    p.stderr?.on('data', (d) => pushLog(String(d)))
    p.on('error', (e) => {
      pushLog('执行出错 ' + script + '：' + (e?.message || e))
      resolve(-1)
    })
    p.on('close', (code) => resolve(code ?? -1))
  })
}

async function runUpdate() {
  if (job.running) return { ok: false, error: '已经在跑了' }
  job.running = true
  job.error = null
  job.step = '抓数据'
  job.startedAt = Date.now()
  job.finishedAt = 0
  job.log = []
  try {
    let code = await runScript('fetch_macro.py')
    if (code !== 0) throw new Error('抓数据失败（退出码 ' + code + '）')
    job.step = '出体检报告'
    code = await runScript('judge.py')
    if (code !== 0) throw new Error('出报告失败（退出码 ' + code + '）')
    job.step = '完成'
  } catch (e) {
    job.error = String(e?.message || e)
    job.step = '失败'
    pushLog(job.error)
  } finally {
    job.running = false
    job.finishedAt = Date.now()
  }
  return { ok: !job.error, error: job.error }
}

export const name = 'dsh-finance-health'
export const inject = ['connection']

export function apply(ctx) {
  const disposers = []
  const conn = ctx.connection ?? ctx.get?.('connection')
  if (!conn?.fetch?.register) {
    ctx.logger?.warn?.('dsh-finance-health: connection.fetch 不可用')
    return () => {}
  }

  const route = (p, methods, fn) => {
    try {
      disposers.push(conn.fetch.register({
        path: p, methods, requestBody: 'buffered', async fetch(req) { return fn(req) },
      }))
    } catch (e) {
      ctx.logger?.warn?.('dsh-finance-health: ' + p + ' 注册失败', e)
    }
  }

  route('/api/dsh-finance/status', ['GET'], async () => Response.json(statusPayload()))

  route('/api/dsh-finance/update', ['POST'], async () => {
    if (job.running) return Response.json({ ok: false, error: '已经在跑了', job })
    // 不阻塞请求，后台跑，前端轮询 status
    runUpdate().catch(() => {})
    return Response.json({ ok: true, started: true })
  })

  ctx.logger?.info?.('dsh-finance-health: 接口已注册 /api/dsh-finance/*')

  return () => { for (const d of disposers) { try { d?.() } catch { } } }
}
