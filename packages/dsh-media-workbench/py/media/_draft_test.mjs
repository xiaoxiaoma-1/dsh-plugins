// 实测「写这篇」链路：取选题 → 取原文 → 模型写稿（和宿主同一份 prompt）
import fs from 'node:fs'
import { spawn } from 'node:child_process'

const PY = 'E:\\tools\\asr\\.venv\\Scripts\\python.exe'
const POOL = 'E:\\desktop\\media\\pool_db.py'
const KEY = fs.readFileSync('E:\\DSH-data\\.dsh\\openai-gateway\\api-key', 'utf8').trim()
const BASE = 'http://127.0.0.1:8326/v1'
const MODEL = 'siliconflow/deepseek-ai/DeepSeek-V3.2'
const NEEDLE = process.argv[2] || '小红书粉丝超过10万'

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

const lst = await run(['list', '--limit', '300'])
const t = (lst.topics || []).find((x) => (x.title || '').includes(NEEDLE))
if (!t) { console.log('找不到选题'); process.exit(1) }
console.log('选题:', t.title, '|', t.score, '分 |', t.board)
const src = await run(['src', '--kind', t.source_kind, '--ref', t.source_ref])
if (!src.ok) { console.log('取素材失败', src); process.exit(1) }
console.log('原文:', src.title, src.date, '|', (src.text || '').length, '字')

const SYSTEM = `你要替一个做知识类内容的自媒体博主，把一条选题写成可以直接开拍的口播稿。

铁律：
- 只用【原始素材】里的事实和观点。素材里没有的数字、案例、经历，一个都不许加。
- 素材不足以支撑这条选题，就直说「素材不够，这条写不了」并说明缺什么，不要硬写。
- 用大白话，第一人称，像在跟同行的朋友讲话。
- 不要「值得注意的是」「意义重大」这类空话，不要「点赞关注」结尾。

结构：
1. 开头第一句就是钩子，直接砸出去
2. 讲清这件事到底是什么（博主本人没读过原始素材，背景要交代清楚）
3. 为什么是这样：机制、因果
4. 一个具体例子，只能来自素材
5. 落到动作：听完能做什么

长度 700-1100 字。只输出稿子本身，不要标题、不要解释、不要 markdown。`

const prompt = `选题：${t.title}
切入角度：${t.angle}
开头钩子：${t.hook}
来源：${src.title} ${src.date}

【原始素材】
${String(src.text).slice(0, 4000)}`

const t0 = Date.now()
const r = await fetch(BASE + '/chat/completions', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + KEY },
  body: JSON.stringify({ model: MODEL, messages: [{ role: 'system', content: SYSTEM }, { role: 'user', content: prompt }], max_tokens: 2600, temperature: 0.6 }),
})
const j = await r.json()
const text = j?.choices?.[0]?.message?.content || ''
console.log('耗时', ((Date.now() - t0) / 1000).toFixed(1) + 's，稿子', text.length, '字\n')
console.log(text)
await run(['setdraft', '--id', t.id], { text, source: { kind: src.kind, title: src.title, date: src.date }, at: new Date().toISOString().slice(0, 19) })
console.log('\n已存进这条选题')
