import fs from 'node:fs'

const KEY = fs.readFileSync('E:\\DSH-data\\.dsh\\openai-gateway\\api-key', 'utf8').trim()
const BASE = 'http://127.0.0.1:8326/v1'
const MODEL = 'siliconflow/deepseek-ai/DeepSeek-V3.2'

// 与 index.js 里 DRAFT_SYS 完全一致
const DRAFT_SYS = [
  '你是中文播客的对谈稿写手。写两个人聊天的稿子，不是讲稿。',
  '人物：S1 女（提问方，反应快、爱追问、会怀疑）；S2 男（回答方，讲道理、举具体例子、下判断）。',
  '硬性要求：',
  '1. 严格按给定轮数输出，S1 先开口，S1/S2 交替，不许出现第三个人',
  '2. 每轮 8~40 字，长短必须有落差，不要每句差不多长',
  '3. 纯附和（嗯/对/哦/嗯哼）全程只用 2~3 次，只用在起头和真惊讶处；其余用追问推进',
  '4. 关键观点之前用「嗯——」（嗯后面跟破折号）表示他在想，全程 2~3 次',
  '5. 疑问句一律用问号结尾，不许用句号收问句',
  '6. 口语化，允许「啊」「呃」「就」这类虚词，但别堆',
  '7. 禁止出现：首先、其次、总之、综上所述、值得注意的是、让我们一起、希望对你有帮助',
  '8. 内容要具体：带数字、带场景、带可执行的判断',
  '只输出 JSON，格式：{"lines":[["S1","台词"],["S2","台词"]]}',
].join('\n')

const topic = process.argv[2] || '小红书粉丝超过10万，赚钱难度会翻三倍'

const t0 = Date.now()
const r = await fetch(`${BASE}/chat/completions`, {
  method: 'POST',
  headers: { 'content-type': 'application/json', authorization: `Bearer ${KEY}` },
  body: JSON.stringify({
    model: MODEL,
    messages: [
      { role: 'system', content: DRAFT_SYS },
      { role: 'user', content: `话题：${topic}\n轮数：30\n请输出 JSON。` },
    ],
    temperature: 0.9,
    max_tokens: 6000,
  }),
})
const secs = ((Date.now() - t0) / 1000).toFixed(1)
console.log('HTTP', r.status, `耗时 ${secs}s`)
if (!r.ok) { console.log('失败:', (await r.text()).slice(0, 300)); process.exit(1) }
const j = await r.json()
const c = j?.choices?.[0]?.message?.content
if (!c) { console.log('空内容，可能是思考模式吃掉 token。finish_reason=', j?.choices?.[0]?.finish_reason); process.exit(1) }

const m = c.match(/\{[\s\S]*\}/)
if (!m) { console.log('没给 JSON，原文前 300 字：\n', c.slice(0, 300)); process.exit(1) }
let obj
try { obj = JSON.parse(m[0]) } catch (e) { console.log('JSON 解析失败:', e.message, '\n原文:', m[0].slice(0, 300)); process.exit(1) }

const lines = obj.lines || []
console.log('轮数:', lines.length)
const texts = lines.map((x) => x[1] || '')
const all = texts.join('')
const 附和 = (all.match(/[嗯对哦哎](?=[。，！？…—\s]|$)/g) || []).length
const 问号 = (all.match(/？/g) || []).length
const 思考 = (all.match(/嗯——/g) || []).length
const 书面词 = ['首先', '其次', '总之', '综上所述', '值得注意的是', '让我们一起', '希望对你有帮助'].filter((w) => all.includes(w))
const 平均 = (all.length / (texts.length || 1)).toFixed(1)
console.log(`平均每轮 ${平均} 字 | 问号 ${问号} 个 | 「嗯——」${思考} 次 | 书面词: ${书面词.length ? 书面词.join(',') : '无'}`)
console.log('前 6 轮：')
lines.slice(0, 6).forEach((x) => console.log(`  ${x[0]}: ${x[1]}`))
fs.writeFileSync('E:\\desktop\\media\\_draft_test.json', JSON.stringify({ topic, lines }, null, 2), 'utf8')
console.log('已存 E:\\desktop\\media\\_draft_test.json')
