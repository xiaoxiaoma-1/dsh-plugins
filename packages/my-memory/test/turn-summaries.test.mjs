// 临时单测：不启动 DSH，验证 turn-summaries 的滚动/门控/注入逻辑
import { mkdirSync, rmSync } from 'node:fs'
import { homedir } from 'node:os'
import { join } from 'node:path'
import { getDb, closeAllDbs } from '../db.js'
import {
  ensureSummaryTable, insertTurnSummary, recentTurnSummaries,
  buildSummaryInjection, localTimeString, autoFillTags, shouldSummarizeThisTurn,
} from '../turn-summaries.js'

const dir = '.my-memory-test'
const abs = join(homedir(), dir)
rmSync(abs, { recursive: true, force: true })
mkdirSync(abs, { recursive: true })

let pass = 0, fail = 0
const ok = (cond, msg) => { if (cond) pass++; else { fail++; console.log('  FAIL:', msg) } }

const db = getDb('C:/Users/Administrator/.dsh/profiles/desktop', dir)
const WS = 'desktop', S1 = 'sess-1'

ok(ensureSummaryTable(db) === true, 'ensureSummaryTable 返回 true')
ok(ensureSummaryTable(db) === true, 'ensureSummaryTable 幂等')

// 1. 时间格式
const lt = localTimeString(Date.now(), 'Asia/Shanghai')
console.log('  localTime:', lt)
ok(/^\d{4}-\d{2}-\d{2} \d{2}:\d{2} \(周.\) Asia\/Shanghai$/.test(lt), 'localTimeString 格式')

// 2. 3 条 normal → 只留 2
for (let i = 0; i < 3; i++) {
  insertTurnSummary(db, { workspace: WS, sessionId: S1, content: `normal-${i}`, value: 'normal' })
}
ok(recentTurnSummaries(db, { workspace: WS, sessionId: S1, limit: 10 }).length === 2, 'normal 窗口保留 2 条')

// 3. none 不占位、不淘汰
insertTurnSummary(db, { workspace: WS, sessionId: S1, content: '寒暄', value: 'none' })
ok(recentTurnSummaries(db, { workspace: WS, sessionId: S1, limit: 10 }).length === 2, 'none 不进窗口')
const activeAll = db.db.prepare("SELECT COUNT(*) n FROM turn_summaries WHERE status='active'").get().n
ok(activeAll === 3, `none 仍落库（active 总数 3，实际 ${activeAll}）`)

// 4. 不完整 → 不淘汰
insertTurnSummary(db, { workspace: WS, sessionId: S1, content: '被截断', value: 'normal', complete: false })
ok(recentTurnSummaries(db, { workspace: WS, sessionId: S1, limit: 10 }).length === 3, '不完整不淘汰（3 条）')

// 5. high 上限 6
for (let i = 0; i < 8; i++) {
  insertTurnSummary(db, { workspace: WS, sessionId: 'sess-2', content: `high-${i}`, value: 'high', highMax: 6 })
}
const highs = db.db.prepare("SELECT COUNT(*) n FROM turn_summaries WHERE session_id='sess-2' AND status='active'").get().n
ok(highs === 6, `high 最多保留 6（实际 ${highs}）`)
const archivedReason = db.db.prepare("SELECT archived_reason r FROM turn_summaries WHERE session_id='sess-2' AND status='archived' LIMIT 1").get()
ok(archivedReason?.r?.includes('高价值'), '归档原因可读')

// 6. 注入：本会话 / 同工作区其他会话
const injSelf = buildSummaryInjection(db, { workspace: WS, sessionId: S1, window: 2 })
ok(injSelf.includes('上次聊到哪') && injSelf.includes('第 '), '本会话注入含轮次')
const injOther = buildSummaryInjection(db, { workspace: WS, sessionId: 'brand-new', window: 2 })
ok(injOther.includes('另一个会话'), '新会话回退到同工作区其他会话')
const injCross = buildSummaryInjection(db, { workspace: 'td', sessionId: 'new', window: 2 })
ok(injCross.includes('另一个工作区') && injCross.includes('desktop'), '跨工作区注入标注来源')

// 7. 自动补标签
const tags = autoFillTags(['my-tag'], { workspace: WS })
ok(tags.join(',') === 'my-tag,shared-global,workspace-agnostic,workspace:desktop,needs-review', `autoFillTags 结果 ${tags.join(',')}`)
const tags2 = autoFillTags(['shared-global', 'workspace:td', 'content-type:lesson'], { workspace: WS })
ok(tags2.length === 4 && !tags2.includes('needs-review'), '已有标签不重复补')

// 8. 是否值得总结
const mkEvents = (toolCalls, userChars) => {
  const evs = [{ type: 'turn/start' }]
  if (userChars) evs.push({ type: 'user/message', data: { source: { kind: 'user' }, content: [{ type: 'text', text: 'x'.repeat(userChars) }] } })
  for (let i = 0; i < toolCalls; i++) evs.push({ type: 'tool/result', data: { name: 'read' } })
  return evs
}
ok(shouldSummarizeThisTurn(mkEvents(1, 2), { minUserChars: 30 }) === true, '有工具调用→总结')
ok(shouldSummarizeThisTurn(mkEvents(0, 10), { minUserChars: 30 }) === false, '短寒暄→不总结')
ok(shouldSummarizeThisTurn(mkEvents(0, 50), { minUserChars: 30 }) === true, '长提问→总结')

console.log(`\n结果：${pass} 通过 / ${fail} 失败`)
closeAllDbs()
process.exit(fail === 0 ? 0 : 1)
