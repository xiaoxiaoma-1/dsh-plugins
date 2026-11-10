/**
 * dsh-ponytail-lazy —— 让 AI 写代码时自动应用 Ponytail 的「聪明懒」原则
 *
 * 工作机制：插件只向系统提示注入一段原则文本（systemPrompt.section）。
 * 系统提示常驻每次对话上下文，所以 AI 在构思和输出代码时会实时遵守这些原则，
 * 用户不需要任何额外操作，也看不到优化过程 —— 这正是「方案一：大脑助手」。
 *
 * 稳定性：整个 apply 过程包裹在 try/catch 中，任何异常只记日志，绝不让宿主启动失败。
 */

const PRINCIPLES = `## Ponytail 代码优化原则（写代码时自动遵守）

### 写代码前先过 7 个问题，能停在前面的就停下
1. 这功能真的需要吗？—— 不需要就不写
2. 项目代码库里已经有吗？—— 有就复用，不重复造
3. 语言标准库有吗？—— 用内置能力
4. 平台/框架原生有吗？—— 用原生 API
5. 已安装的依赖里有吗？—— 有就用
6. 能一行/几行解决吗？—— 就写几行，不拆抽象层
7. 以上都没有，才写新代码

### 永远不能省的边界（这条优先于「精简」）
- 输入验证：该校验的必须校验
- 错误处理：不允许空 catch，不允许吞异常
- 安全性：权限、转义、防注入不能删
- 可访问性：需要时不能砍

### 输出风格
- 代码能短则短，实现够用即止；不写用不到的配置项、抽象层、防御性分支
- 不为“以后可能要”提前设计；不确定就先问一句
- 精简的是实现，不是调查：先看清楚项目里有什么，再动手写`;

function safeApply(ctx) {
  const disposers = [];
  try {
    if (ctx.systemPrompt && typeof ctx.systemPrompt.section === 'function') {
      disposers.push(ctx.systemPrompt.section({
        name: 'ponytail:principles',
        order: 200,
        text: PRINCIPLES,
      }));
      ctx.logger?.info?.('ponytail-lazy: 已注入代码优化原则');
    } else {
      ctx.logger?.warn?.('ponytail-lazy: 当前宿主没有 systemPrompt 服务，插件未生效');
    }
  } catch (error) {
    ctx.logger?.warn?.('ponytail-lazy: 注入原则失败 - ' + (error && error.message ? error.message : String(error)));
  }
  return () => {
    for (const dispose of disposers) {
      try { dispose?.(); } catch { /* 忽略清理异常 */ }
    }
  };
}

export default function ponytailLazyPlugin(ctx) {
  try {
    return safeApply(ctx);
  } catch (error) {
    ctx?.logger?.warn?.('ponytail-lazy: 插件加载异常 - ' + (error && error.message ? error.message : String(error)));
    return () => {};
  }
}

export { PRINCIPLES };
