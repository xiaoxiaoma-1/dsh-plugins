/**
 * dsh-ziwei —— 紫微斗数算命工作台（v4）
 *
 * 宿主职责：
 *  1) /api/dsh-ziwei/chart  排盘（iztro）
 *  2) /api/dsh-ziwei/ask    解读 / 提问，带大限流年数据，流式返回纯文本
 */

export const name = 'dsh-ziwei'
export const inject = ['connection']

let iztro = null
async function getAstro() {
  if (!iztro) {
    const mod = await import('iztro')
    iztro = mod.astro
  }
  return iztro
}

function normalizeInput(input) {
  const { solarDate, timeIndex, gender } = input || {}
  if (!solarDate || !/^\d{4}-\d{1,2}-\d{1,2}$/.test(String(solarDate))) {
    throw new Error('solarDate 需要形如 1995-08-16')
  }
  return {
    solarDate: String(solarDate),
    timeIndex: Number.isInteger(timeIndex) ? timeIndex : 0,
    gender: gender === '女' ? '女' : '男',
  }
}

function toChart(a) {
  return {
    solarDate: a.solarDate,
    lunarDate: a.lunarDate,
    chineseDate: a.chineseDate,
    time: a.time,
    timeRange: a.timeRange,
    sign: a.sign,
    zodiac: a.zodiac,
    fiveElementsClass: a.fiveElementsClass,
    soul: a.soul,
    body: a.body,
    gender: a.gender,
    earthlyBranchOfSoulPalace: a.earthlyBranchOfSoulPalace,
    earthlyBranchOfBodyPalace: a.earthlyBranchOfBodyPalace,
    palaces: a.palaces.map((p) => ({
      index: p.index,
      name: p.name,
      heavenlyStem: p.heavenlyStem,
      earthlyBranch: p.earthlyBranch,
      isBodyPalace: !!p.isBodyPalace,
      isOriginalPalace: !!p.isOriginalPalace,
      majorStars: (p.majorStars || []).map((s) => ({ name: s.name, brightness: s.brightness, mutagen: s.mutagen })),
      minorStars: (p.minorStars || []).map((s) => ({ name: s.name, brightness: s.brightness, mutagen: s.mutagen })),
      adjectiveStars: (p.adjectiveStars || []).map((s) => s.name),
      changsheng12: p.changsheng12,
      boshi12: p.boshi12,
      decadal: p.decadal ? { range: p.decadal.range, heavenlyStem: p.decadal.heavenlyStem, earthlyBranch: p.decadal.earthlyBranch } : null,
      ages: p.ages || [],
    })),
  }
}

async function buildAstrolabe(input) {
  const { solarDate, timeIndex, gender } = normalizeInput(input)
  const astro = await getAstro()
  return astro.bySolar(solarDate, timeIndex, gender, true, 'zh-CN')
}

async function buildChart(input) {
  return toChart(await buildAstrolabe(input))
}

const NO_JARGON = [
  '硬性语言要求（最重要，违反即视为失败）：',
  '1. 回答里不许出现这些词：命宫、身宫、主星、辅星、杂曜、四化、化禄、化权、化科、化忌、庙、旺、陷、长生、五行局、大限、流年、小限、煞星、以及任何星名（紫微、天机、太阳、武曲、天同、廉贞、贪狼、七杀、破军、文昌、文曲、左辅、右弼、擎羊、陀罗、火星、铃星、地空、地劫、天马、禄存……）。',
  '2. 想表达的意思，一律换成生活里的话。示范：不说“财帛宫七杀”，说“你赚钱靠敢接硬活、来钱快也花得快”；不说“命宫无主星”，说“你这人没有固定套路，遇什么人成什么事”；不说“化忌”，说“容易在这一块卡住、反复纠结”。',
  '3. 讲时间就说“今年”“这两年”“未来十年”“三十几岁以后”，不要用大限流年。',
  '4. 实在绕不开某个传统说法，最多用一次，后面必须紧跟括号解释，例如“文曲（代表嘴皮子和文字表达）”。',
  '5. 全程像跟朋友聊天：短句、具体、有例子；不要玄乎、不要排比、不要吓人。',
].join('\n')

const SYSTEM_READ = [
  '你是一位说话像朋友、不端着的命理顾问。对方是普通人，只学过语文，看不懂任何命理术语。',
  '',
  NO_JARGON,
  '',
  '内容要求：',
  '1. 每一段先给一句人话结论，再用两三句解释为什么。',
  '2. 不要算命式恐吓和空洞吉言；看不出来的地方直接说"这点看不出"。',
  '3. 结构：一、你是个什么样的人（三句话）二、你的长处 三、容易栽跟头的地方 四、适合做什么工作、钱怎么来 五、感情和家里人 六、身体要注意什么 七、往后十年大概怎么走 八、三条马上能做的建议。',
  '4. 900–1300 字，短段落，每段不超过四行，不要表格。',
].join('\n')

const SYSTEM_ASK = [
  '你是一位说话像朋友的命理顾问，用大白话回答具体问题，不端着、不吓人。',
  '',
  NO_JARGON,
  '',
  '回答结构：',
  '1. 第一句必须是明确结论（能/不能、行/不行、好/一般/要小心）。',
  '2. 再讲两三条原因，全部用生活语言，必要时举例子。',
  '3. 结尾给一两条现在就能做的事。',
  '4. 300–600 字，短段落，不要 # 标题、不要表格。',
  '5. 看不出就直说"这件事从你的出生信息里看不出"，不要编。',
].join('\n')

function starText(s) {
  return `${s.name}${s.brightness ? `(${s.brightness})` : ''}${s.mutagen ? `[${s.mutagen}]` : ''}`
}

function chartToText(chart) {
  const lines = []
  lines.push(`出生：${chart.solarDate} ${chart.time}（${chart.timeRange}） ${chart.gender}`)
  lines.push(`农历：${chart.lunarDate}；四柱：${chart.chineseDate}；五行局：${chart.fiveElementsClass}`)
  lines.push(`命主：${chart.soul}；身主：${chart.body}；命宫地支：${chart.earthlyBranchOfSoulPalace}；身宫地支：${chart.earthlyBranchOfBodyPalace}`)
  lines.push('十二宫：')
  for (const p of chart.palaces) {
    const major = (p.majorStars || []).map(starText).join('、') || '（无主星）'
    const minor = (p.minorStars || []).map(starText).join('、') || '—'
    const adj = (p.adjectiveStars || []).join('、') || '—'
    const dec = p.decadal?.range ? `大限 ${p.decadal.range[0]}-${p.decadal.range[1]} 岁` : ''
    lines.push(`${p.heavenlyStem}${p.earthlyBranch} ${p.name}${p.isBodyPalace ? '（身宫）' : ''}：主星 ${major}；辅星 ${minor}；杂曜 ${adj}；长生 ${p.changsheng12 || '—'}；${dec}`)
  }
  return lines.join('\n')
}

/** 把某一年的运限数据压成文字：大限、流年、小限、流年十二宫落位 */
function horoscopeToText(astro, chart, year) {
  const date = new Date(`${year}-06-01T12:00:00`)
  const h = astro.horoscope(date)
  const branchOf = (i) => chart.palaces[i]?.earthlyBranch || '?'
  const mapNames = (names) => names.map((n, i) => `${branchOf(i)}=${n}`).join('、')
  const lines = []
  lines.push(`目标年份：${year} 年（${h.yearly.heavenlyStem}${h.yearly.earthlyBranch}）`)
  lines.push(`虚岁：${h.age.nominalAge}`)
  lines.push(`大限：${h.decadal.heavenlyStem}${h.decadal.earthlyBranch}（${h.decadal.name}），大限四化：${(h.decadal.mutagen || []).join('、') || '—'}`)
  lines.push(`大限十二宫落位：${mapNames(h.decadal.palaceNames)}`)
  lines.push(`流年：${h.yearly.heavenlyStem}${h.yearly.earthlyBranch}，流年四化：${(h.yearly.mutagen || []).join('、') || '—'}`)
  lines.push(`流年十二宫落位：${mapNames(h.yearly.palaceNames)}`)
  lines.push(`小限：虚岁 ${h.age.nominalAge}，落在 ${branchOf(h.age.index)} 宫（${h.age.heavenlyStem}${h.age.earthlyBranch}）`)
  return lines.join('\n')
}

function buildAskPrompt(chart, horoText, question) {
  const head = [
    '下面这些是传统命理写法，只给你判断用；回答里一个这样的词都不要照抄，全部翻成大白话。',
    '',
    chartToText(chart),
    '',
    '运限数据：',
    horoText,
  ].join('\n')
  const tail = question
    ? `\n\n我的问题：${question}\n请直接回答这个问题，不要泛泛讲整张盘。`
    : '\n\n请按系统要求做一次整体解读。'
  return head + tail
}

function currentRoute(ctx) {
  const sel = ctx.get?.('agentDefaultModel')?.currentSelection?.()
  if (!sel || !sel.provider || !sel.model) throw new Error('读不到默认模型（agentDefaultModel 不可用）')
  return { provider: sel.provider, model: sel.model }
}

async function* streamText(ctx, { chart, horoText, system, question }, signal) {
  const route = currentRoute(ctx)
  const llm = ctx.get?.('llm')
  if (!llm?.prepareCall) throw new Error('llm 服务不可用')
  const call = await llm.prepareCall({ ...route, maxTokens: question ? 1400 : 2600 }, signal)
  const messages = [{ role: 'user', content: [{ type: 'text', text: buildAskPrompt(chart, horoText, question) }] }]
  for await (const chunk of call.stream({ ...call.config, messages, system, signal })) {
    if (chunk.type === 'text-delta') {
      if (chunk.text) yield chunk.text
    } else if (chunk.type === 'finish') {
      if (chunk.reason.kind !== 'stop' && chunk.reason.kind !== 'max-tokens') {
        const f = chunk.reason.failure
        throw new Error(`模型调用结束：${chunk.reason.kind}${f?.message ? ' - ' + f.message : ''}`)
      }
    }
  }
}

function streamResponse(iteratorFactory) {
  const encoder = new TextEncoder()
  const aborter = new AbortController()
  const stream = new ReadableStream({
    start(controller) {
      ;(async () => {
        try {
          const iterable = await iteratorFactory(aborter.signal)
          for await (const text of iterable) {
            controller.enqueue(encoder.encode(text))
          }
        } catch (e) {
          controller.enqueue(encoder.encode(`\n\n[失败] ${String(e?.message ?? e)}`))
        } finally {
          try { controller.close() } catch { }
        }
      })()
    },
    cancel() { try { aborter.abort() } catch { } },
  })
  return new Response(stream, {
    headers: { 'Content-Type': 'text/plain; charset=utf-8', 'Cache-Control': 'no-store' },
  })
}

export function apply(ctx) {
  const disposers = []
  const conn = ctx.connection ?? ctx.get?.('connection')
  if (!conn?.fetch?.register) {
    ctx.logger?.warn?.('dsh-ziwei: connection.fetch 不可用，接口未注册')
    return () => { }
  }

  // 排盘
  try {
    disposers.push(conn.fetch.register({
      path: '/api/dsh-ziwei/chart',
      methods: ['POST'],
      requestBody: 'buffered',
      async fetch(request) {
        if (request.method !== 'POST') return new Response('method not allowed', { status: 405 })
        let body
        try { body = await request.json() } catch { return new Response('bad json', { status: 400 }) }
        try {
          return Response.json({ ok: true, chart: await buildChart(body) })
        } catch (e) {
          return Response.json({ ok: false, error: String(e?.message ?? e) }, { status: 200 })
        }
      },
    }))
    ctx.logger?.info?.('dsh-ziwei: 排盘接口已注册 /api/dsh-ziwei/chart')
  } catch (e) {
    ctx.logger?.warn?.('dsh-ziwei: 排盘接口注册失败', e)
  }

  // 解读 / 提问（流式）
  try {
    disposers.push(conn.fetch.register({
      path: '/api/dsh-ziwei/ask',
      methods: ['POST'],
      requestBody: 'buffered',
      async fetch(request) {
        if (request.method !== 'POST') return new Response('method not allowed', { status: 405 })
        let body
        try { body = await request.json() } catch { return new Response('bad json', { status: 400 }) }
        return streamResponse(async (signal) => {
          const astro = await buildAstrolabe(body)
          const chart = toChart(astro)
          const year = Number(body.year) || new Date().getFullYear()
          const horoText = horoscopeToText(astro, chart, year)
          const question = String(body.question || '').trim()
          return streamText(ctx, {
            chart, horoText,
            system: question ? SYSTEM_ASK : SYSTEM_READ,
            question,
          }, signal)
        })
      },
    }))
    ctx.logger?.info?.('dsh-ziwei: 提问接口已注册 /api/dsh-ziwei/ask')
  } catch (e) {
    ctx.logger?.warn?.('dsh-ziwei: 提问接口注册失败', e)
  }

  return () => {
    for (const d of disposers) { try { d?.() } catch { } }
  }
}
