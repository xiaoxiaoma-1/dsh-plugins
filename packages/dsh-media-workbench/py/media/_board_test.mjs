// 单板块实测：抽该板块素材 → 新 prompt 出题 → 只留 >=75 分 → 落库
import fs from 'node:fs'
import { spawn } from 'node:child_process'

const PY = 'E:\\tools\\asr\\.venv\\Scripts\\python.exe'
const POOL = 'E:\\desktop\\media\\pool_db.py'
const BASE = 'http://127.0.0.1:8326/v1'
const KEY = fs.readFileSync('E:\\DSH-data\\.dsh\\openai-gateway\\api-key', 'utf8').trim()
const MODEL = 'siliconflow/deepseek-ai/DeepSeek-V3.2'
const DIMS = ['普世性', '数字冲击', '反常识', '可操作', '痛点强度', '时效性', '争议空间', '经验可挂', '能落到动作', '标题性']
const BOARD = process.argv[2] || '商业与变现'
const WANT = Number(process.argv[3] || 10)
const MIN = 75

function run(args, stdin) {
  return new Promise((res) => {
    const c = spawn(PY, [POOL, ...args], { windowsHide: true, env: { ...process.env, PYTHONIOENCODING: 'utf-8' } })
    let out = ''
    c.stdout.setEncoding('utf8')
    c.stdout.on('data', (d) => { out += d })
    c.on('close', () => { try { res(JSON.parse((out || '{}').trim().split('\n').pop())) } catch { res({ ok: false, error: out }) } })
    if (stdin !== undefined) c.stdin.write(JSON.stringify(stdin))
    c.stdin.end()
  })
}

const SYSTEM = `你是内容策划，服务对象是一个做知识类内容的自媒体博主。这一轮你只负责一个板块：${BOARD}。
下面素材全部取自他库里「${BOARD}」这一类的书和他的推文。

产出目标：${WANT} 条「今天就能开写」的选题，不是选题方向，不是方法论条目。

标题硬规范（不合格的直接别给，宁可少给）：
- 句子里必须有具体的东西：一个数字、一个具体场景、一个具体后果，或者一组具体对比
- 15-26 字，一句话念完，像人话，不像 PPT 目录
- 可以狠、可以反常识、可以直接得罪人，但不要喊口号、不要鸡汤
- 禁止这些开头：为什么你 / 你总是 / 别再迷信 / 如何 / 关于什么什么的思考 / 我们要怎么做
- 反面（这种别给）：别再迷信周末补觉，它可能是你失眠的元凶 / 如何绕过意志力陷阱，真正改变一个旧习惯
- 正面（这种才对）：发1000条烂视频，比憋10条精品更有用 / 客户问价你先报高三成，成交率反而更高

每条还要给：
- angle：从哪一刀切进去，一句话，不许复述素材
- hook：开头第一句，要让人停下来
- source_kind / source_ref：取自素材标号
- dims：十维各 0-10 整数，键名固定：普世性、数字冲击、反常识、可操作、痛点强度、时效性、争议空间、经验可挂、能落到动作、标题性
  · 痛点强度 = 能不能戳到观众此刻正在难受的事，不是「这个话题重要」
  · 数字冲击 = 标题或论点里有没有让人一愣的数字、倍数、时间
  · 反常识 = 有没有推翻一个大家都默认的结论
- why：一句话说清凭什么值得写

自己先按这个尺子过滤，别把平庸的塞进来：
90 分 = 看到就想转发，或者立刻想反驳，且跟他本人强相关
75-85 = 值得写，能出一条有观点的视频
70 以下 = 正确但没劲，不要给

只输出 JSON 数组，不要 markdown 代码块，不要解释。`

const pick = await run(['pick', '--board', BOARD, '--n', String(WANT * 2)])
if (!pick.ok) { console.log('抽素材失败', pick); process.exit(1) }
console.log(`【${BOARD}】抽到 ${pick.items.length} 条素材（` + pick.items.reduce((a, x) => (a[x.kind] = (a[x.kind] || 0) + 1, a), {}) + '）')

const payload = pick.items.map((x, i) => `#${i + 1} [${x.kind}:${x.ref}] ${x.title}\n${x.text}`).join('\n\n')
const t0 = Date.now()
const r = await fetch(BASE + '/chat/completions', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + KEY },
  body: JSON.stringify({
    model: MODEL,
    messages: [{ role: 'system', content: SYSTEM }, { role: 'user', content: `素材（每条都带 kind:ref，出选题时 source_kind / source_ref 从这里取）：\n\n${payload}\n\n请给 ${WANT} 条选题。` }],
    max_tokens: 6000, temperature: 0.7,
  }),
})
const j = await r.json()
const raw = j?.choices?.[0]?.message?.content || ''
console.log('耗时', ((Date.now() - t0) / 1000).toFixed(1) + 's，输出', raw.length, '字')
let t = raw.trim().replace(/^```[a-zA-Z]*\s*/, '').replace(/```\s*$/, '').trim()
const a = t.indexOf('['), b = t.lastIndexOf(']')
if (a >= 0 && b > a) t = t.slice(a, b + 1)
const arr = JSON.parse(t)

const list = []
let low = 0
for (const it of arr) {
  const title = String(it.title || '').trim()
  if (!title) continue
  const dims = {}
  for (const k of DIMS) { const n = Math.round(Number(it.dims?.[k])); dims[k] = Number.isFinite(n) ? Math.max(0, Math.min(10, n)) : 0 }
  const score = DIMS.reduce((s, k) => s + dims[k], 0)
  if (score < MIN) { low++; continue }
  list.push({
    board: BOARD, title, angle: String(it.angle || ''), hook: String(it.hook || ''),
    source_kind: String(it.source_kind || ''), source_ref: String(it.source_ref || ''),
    dims, score, level: score >= 85 ? 'A' : score >= 70 ? 'B' : 'C', why: String(it.why || ''),
  })
}
console.log(`模型给了 ${arr.length} 条，${low} 条被 ${MIN} 分线挡掉，留下 ${list.length} 条\n`)
for (const x of list.sort((p, q) => q.score - p.score)) {
  console.log(`[${x.score} ${x.level}] ${x.title}`)
  console.log(`      角度：${(x.angle || '').slice(0, 60)}`)
  console.log(`      开头：${(x.hook || '').slice(0, 50)}`)
}
if (list.length) {
  const imp = await run(['import'], list)
  console.log('\n落库：', JSON.stringify(imp))
}
