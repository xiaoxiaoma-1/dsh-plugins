# dsh-ponytail-lazy

让 AI 写代码时自动遵守 Ponytail 的「聪明懒」原则：少写代码、不重复造轮子，但验证、错误处理、安全一条都不省。

## 工作机制

插件只做一件事：通过 `ctx.systemPrompt.section()` 向系统提示注入一段原则文本。系统提示每次对话都会进入上下文，所以 AI 在构思和输出代码时就会自动按这些原则来——你不需要调用任何命令，也看不到优化过程，只看到更精简的代码。

- 注入点：`index.js` 中的 `PRINCIPLES` 文本
- 失败保护：注入异常只写日志，不会影响 DSH 启动
- 无外部依赖：不引入 schemastery 等第三方包

## 安装方式（本地 profile）

1. 插件目录放在 profile 下，例如 `~/.dsh/profiles/desktop/ponytail-plugin`
2. profile `package.json` 添加依赖：`"dsh-ponytail-lazy": "file:./ponytail-plugin"`
3. `node_modules` 中建立链接（可 `New-Item -ItemType Junction` 代替 pnpm install）
4. `dsh.profile.bundles` 中加入 `dsh-ponytail-lazy`
5. 完全退出 DSH 后重新启动

## 7 步检查法

写代码前依次问：真的需要吗 → 代码库有吗 → 标准库有吗 → 平台原生有吗 → 依赖里有吗 → 能几行搞定吗 → 都没有才写新代码。

## 边界（优先于精简）

输入验证、错误处理、安全性、可访问性不能因为"精简"被删掉。

## 升级与回滚

- 回滚：从 `dsh.profile.bundles` 移除 `dsh-ponytail-lazy`，重启即可；插件文件可保留
- 升级：直接改 `index.js` 中的原则文本，重启生效
