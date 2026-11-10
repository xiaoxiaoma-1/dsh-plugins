/**
 * my-memory — 反思
 *
 * 单次任务内连续 ≥N 个工具 step 后，引导模型记忆值得保存的内容。
 */

export const REFLECT_MARKER = '[my-memory-reflect]'
export const PLUGIN_SOURCE = { kind: 'plugin:my-memory', producer: 'my-memory', form: 'snapshot' }

/** 构建反思引导消息 */
export function buildReflectMessage() {
  return `${REFLECT_MARKER}
【记忆反思】
本轮任务已执行多个工具步骤。请回顾以上工作，判断是否有值得长期记忆的内容：

1. **新记忆**：是否发现了新的事实、用户偏好、项目信息、或设计原则？
   - 如有，用 memory_remember 写入对应层级（fact/lesson/user/project/rules）
   - 附上关键词（8-13 个）和适当标签（tags）

2. **更新判断**：是否发现已有记忆需要修正或补充？
   - 用 memory_search 找到 id，再用 memory_remember 传该 id 修改（不另设修改工具）
   - 教训/纠正写入 lesson 层并标记 corrected

3. **冲突处理**：新旧结论矛盾时，用新结论覆盖旧条目（传旧 id 改写），别留两条互相打脸

如果本轮没有值得记忆的内容，直接回复"无需记忆"即可。`
}

/**
 * 构建「本轮收尾」引导消息：先写本轮总结，再（可选）反思长期记忆。
 * 与反思共用同一个 marker，保证 isReflectTurn 能识别、不会套娃。
 */
export function buildTurnSummaryMessage({ localTime = '', reflect = false, project = null } = {}) {
  const parts = [`${REFLECT_MARKER}
【本轮收尾】${localTime ? `\n当前时间：${localTime}` : ''}

**第一步：用 memory_progress 写一行进度**
- content：30 字以内，格式「做了什么 → 结论 → 下一步」
- 例：\`注入层改完，命中降到3条，下一步做经验包自动沉淀\`
- 换窗口前（上下文到交接线）改用 kind=handoff，写 300 字内交接单：目标 / 做到哪 / 下一步 / 卡在哪
- 这一轮没有实质推进（纯确认、寒暄、重复）就不写，别凑`]

  if (project) {
    parts.push(`
**偏离度自查（项目：${project}）**
对照上面【当前项目】图纸里的目标，给这一轮打个 0-100 的偏离分：
- ≤30：正常，不用提
- 30-50：在回复里说一句"这步和初衷有点偏"
- 50-70：列出偏在哪，等用户点头再继续
- >70：停下，先问要不要改回去
只提醒，不自己改方向。`)
  }

  if (reflect) {
    parts.push(`
**第二步：反思有没有值得长期记忆的内容**
1. **新记忆**：新的事实、用户偏好、项目信息、设计原则 → memory_remember（8-13 个 keywords + tags）
2. **更新判断**：已有记忆需要修正 → memory_search 找到 id，用 memory_remember 传 id 改
3. **冲突处理**：新旧矛盾时用新结论覆盖旧条目，不要留两条打架的`)
  }

  parts.push(`\n两步都没有内容时，直接回复"无需记忆"即可。`)
  return parts.join('\n')
}

/** 扫描事件流，统计当前 turn 内的工具步骤数 */export function countToolStepsThisTurn(events) {
  let count = 0
  let startIdx = -1
  for (let i = events.length - 1; i >= 0; i--) {
    if (events[i]?.type === 'turn/start') {
      startIdx = i
      break
    }
  }
  if (startIdx < 0) return 0
  for (let i = startIdx; i < events.length; i++) {
    if (events[i]?.type === 'tool/result') count++
  }
  return count
}

/** 判断最近一个 turn 的结束原因 */
export function lastTurnEndReason(events) {
  for (let i = events.length - 1; i >= 0; i--) {
    if (events[i]?.type === 'turn/start') break
    if (events[i]?.type === 'turn/end' && events[i]?.data?.reason?.kind) {
      return events[i].data.reason.kind
    }
  }
  return null
}

/** 判断当前 turn 是否为反思轮（避免反思套反思） */
export function isReflectTurn(events) {
  let startIdx = -1
  for (let i = events.length - 1; i >= 0; i--) {
    if (events[i]?.type === 'turn/start') {
      startIdx = i
      break
    }
  }
  if (startIdx < 0) return false
  for (let i = startIdx; i < events.length; i++) {
    const e = events[i]
    if (e?.type !== 'user/message') continue
    if (e.data?.source?.kind === 'user') continue
    const text = (e.data?.content ?? [])
      .filter(b => b.type === 'text' && typeof b.text === 'string')
      .map(b => b.text)
      .join(' ')
    if (text.includes(REFLECT_MARKER)) return true
  }
  return false
}
