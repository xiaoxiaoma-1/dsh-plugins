/**
 * my-memory — 上下文计量
 *
 * 数据来源是 DSH 内置的 tokenMeter 服务（provider 上报的实际 prompt 大小），
 * 不是按字符数估的。取不到时返回 null，调用方自行降级，不影响插件启动。
 *
 * 相关事实（读 app.asar 确认）：
 *   - 服务名 tokenMeter：meter.measure(session).totalTokens 即当前上下文占用
 *   - 窗口大小：session.requestContext().contextWindow
 *   - 备用投影：sessionProjections 的 contextPressure → projectedTokens（下一次请求预估）
 */

/** 读当前会话的上下文占用 */
export function readOccupancy(ctx, session) {
  if (!ctx || !session) return null

  let size
  try {
    size = session.requestContext?.()?.contextWindow
  } catch {
    size = undefined
  }

  let used
  const meter = typeof ctx.get === 'function' ? ctx.get('tokenMeter') : undefined
  if (meter && typeof meter.measure === 'function') {
    try {
      used = meter.measure(session)?.totalTokens
    } catch {
      used = undefined
    }
  }

  // 兜底：读 contextPressure 投影
  if (typeof used !== 'number') {
    try {
      const p = ctx.sessionProjections?.get?.(session, 'contextPressure')
      used = p?.projectedTokens ?? p?.pressureTokens
    } catch {
      used = undefined
    }
  }

  if (typeof used !== 'number' || typeof size !== 'number' || size <= 0) return null

  const percent = Math.min(100, Math.round((used / size) * 100))
  return { used, size, percent, remaining: Math.max(0, size - used) }
}

function fmt(n) {
  if (n >= 10000) return `${(n / 10000).toFixed(1)} 万`
  return String(n)
}

/** 一行文字描述 */
export function formatOccupancy(occ) {
  if (!occ) return '上下文占用：读不到（tokenMeter 不可用）'
  return `上下文已用 ${occ.percent}%（${fmt(occ.used)} / ${fmt(occ.size)} token），剩余 ${fmt(occ.remaining)}`
}

/**
 * 按占用比例给出该做什么。
 * 默认 45% 起提醒收敛、50% 起要求本轮结束前写交接单。
 * 阈值要按"模型实际能吃下的窗口"调：V3.2 只有标称窗口的一半左右，所以 50% 就必须换；
 * 换成真正长窗口的模型可以放宽到 60/70。
 */
export function actionFor(percent, { warnRatio = 45, handoffRatio = 50 } = {}) {
  if (percent >= handoffRatio) return 'handoff'
  if (percent >= warnRatio) return 'progress'
  return null
}
