# DSH 插件集合

> 仓库归属：GitHub 用户 **xiaoxiaoma-1**（中文圈叫「小小马杠1」）。别人口头上说这个名字，指的就是这个仓库。

给 [DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness)（下称 DSH）用的一组插件。每个插件单独一个包，可以只装一个，也可以全部装。

这里的东西都是给「让 AI 真在你电脑上干活」用的：记长期记忆、管工作看板、截图、语音、桌宠、音视频工作台……

## 换电脑怎么一步到位

**这台机器要变成和原机一样，先配环境，再装插件。** 顺序不能反——插件装上但环境没有，打开就报错。

```bash
git clone git@github.com:<你的用户名>/dsh-plugins.git
cd dsh-plugins

# 1) 照说明书配环境（人读，也是写给 AI 读的）
#    最省事：对 DSH 说「读 setup/ENVIRONMENT.md，把第一级和第二级配好」
powershell -ExecutionPolicy Bypass -File setup/install-env.ps1 -Plan   # 先预演
powershell -ExecutionPolicy Bypass -File setup/install-env.ps1          # 真装

# 2) 体检，缺什么它会告诉你补哪个
node setup/verify-env.mjs

# 3) 装插件
node install.mjs
```

`setup/` 里三个文件的分工：

| 文件 | 给谁看 | 作用 |
|---|---|---|
| `setup/ENVIRONMENT.md` | **人和 AI 都能读** | 完整环境清单，分三级：核心 / 工具 / 模型；每项写清用途、谁依赖、怎么装、怎么验、装不上怎么降级 |
| `setup/install-env.ps1` | 机器执行 | 幂等安装。已装的跳过，能自动的自动（winget / pip / venv），要手动下的只打印指引 |
| `setup/verify-env.mjs` | 机器执行 | 逐项体检，输出 ✓ / ! / ✗，末尾直接告诉你缺几项、补哪个 |

## 装法一：让 AI 帮你装（推荐）

克隆下来，对 DSH 里的 AI 说一句话：

> 把这个仓库的插件全部装进我的 DSH

等价于下面两行：

```bash
git clone https://github.com/<你的用户名>/dsh-plugins.git
cd dsh-plugins && node install.mjs
```

`install.mjs` 会做四件事，每件都打印出来：

1. 找到你的 DSH 目录和 profile（默认 `desktop`）
2. 把 `packages/` 里的插件复制进 `<DSH_HOME>/profiles/<profile>/node_modules/`
3. 登记到该 profile 的 `package.json`：`dependencies` 加一条、`dsh.profile.bundles` 加一条
4. 备份原清单 → 写入（无 BOM）→ 回读校验 JSON

装完**完全退出 DSH 再重开**（托盘退出，不是关窗口）。

常用参数：

```bash
node install.mjs --pick           # 挑着装：列出分组清单，按编号选（给人用）
node install.mjs --list           # 看有哪些插件
node install.mjs my-memory        # 只装一个
node install.mjs --dry            # 只打印要干什么，不落盘
node install.mjs --profile 别的   # 装到别的 profile
```

**几个设计上的讲究：**

- **分组挑选**：`--pick` 会把 13 个插件按「记忆与看板 / 工作台 / 桌面交互 / 语音 / 小工具」五组列出来，输编号就行，直接回车等于全装
- **自动补前置**：装「自媒体工作台」会**先自动装「工作台入口」**——不然台子装上了，侧边栏没地方点进去。这类依赖写在每个包 `package.json` 的 `dsh.requires` 里，安装器会做拓扑排序
- **要脚本的会被标出来**：带 `needs-scripts` 标记的插件（工作台、截图、语音、桌宠这几个），装完会提醒你「这些还要本机脚本才能干活，见 setup/scripts/README.md」
- **默认不全装**：`node install.mjs` 不带参数时，会跳过 `needs-scripts` 的包，只装开箱能用的。要连它一起装就加 `--with-scripts`

想还原：profile 目录里有 `package.json.bak-<时间戳>`，改回去即可。

## 装法二：手动

把 `packages/<插件名>` 整个文件夹复制到 `<DSH_HOME>/profiles/<profile>/node_modules/<插件名>`，然后在 profile 的 `package.json` 里做两处登记：

```json
{
  "dependencies": { "<插件名>": "file:./node_modules/<插件名>" },
  "dsh": { "profile": { "bundles": ["<插件名>"] } }
}
```

## 插件清单

| 插件 | 干什么 |
|---|---|
| `my-memory` | 长期记忆。七层（soul/user/project/fact/lesson/topic/rules）+ 经验包，跨会话检索，带记忆星云图 |
| `dsh-work-board` | 工作看板。卡片分「待完成/进行中/阶段完成/已完成」四栏 |
| `dsh-workbench-hub` | 工作台聚合入口，把几个工作台收在一个地方 |
| `dsh-call` | 语音通话通道：手机/微信侧说话，AI 在这台机器上干活 |
| `dsh-shot` | 截图工具：区域截图 → 存盘 → 回传路径给 AI |
| `dsh-pet` | 桌面宠物，会把进度冒泡报给你 |
| `dsh-bubble` | 悬浮球，长驻桌面显示当前状态 |
| `dsh-ziwei` | 紫微斗数排盘 |
| `dsh-finance-health` | 记账与财务健康度 |
| `dsh-ponytail-lazy` | 让 AI 少废话、直接干活的提示层 |
| `dsh-purge-console` | 清洗 DSH 指令权重，去掉不该抢话的部分 |
| `dsh-rea` | 逆向工程助手（静态分析 exe/dll/apk/asar） |

## 工作台接入协议（想自己写一个工作台的话）

侧边栏那个「工作台」入口（`dsh-workbench-hub`）是**动态发现**的，不认硬编码清单。任何插件只要在客户端注册一项，它就会出现在里面：

```js
const reg = window.__DSH_WORKBENCHES__ || (window.__DSH_WORKBENCHES__ = [])
reg.push({
  id: 'my-workbench',
  title: '我的工作台',
  desc: '一句话说明它是干什么的',
  order: 50,      // 越小排越前，可省
  Icon,           // React 组件，可省
  Component,      // 点进去渲染的整页组件
})
window.dispatchEvent(new Event('dsh-workbench-changed'))
```

参考 `packages/dsh-media-workbench/client.js` 末尾那段注册代码。

所以「装一个工作台」的完整链路是：**装包 → 它自己往注册表 push → 侧边栏自动出现**。`dsh-workbench-hub` 一行都不用改。

这也是为什么装工作台时会自动先装 hub——不然台子注册了，没人接住它。

## 已知限制（装之前先看）

- **一部分插件依赖本机工具链**，不是解压就能跑。能配环境变量的已经配了，剩下这些要自己改：

| 插件 | 需要的环境变量或路径 |
|---|---|
| `dsh-call` | `DSH_PYTHON`（python.exe）、`DSH_ASR_SCRIPT`（语音服务脚本）；不设就用 `%LOCALAPPDATA%\Programs\Python\Python312\python.exe` |
| `dsh-shot` | `OUT_DIR` 默认 `E:\desktop\shots`，得改成你自己的目录；另需 `SnippingTool.exe`（Win10/11 自带） |
| `dsh-pet` / `dsh-bubble` | `DSH_PET_PY`、`DSH_PET_SCRIPT`（pythonw + 桌宠脚本） |
| `dsh-finance-health` | `DSH_FINANCE_DIR`（数据目录）、`DSH_FINANCE_PYTHON` |
| `dsh-rea` | 需要 JDK、Ghidra、rizin、apktool，路径在 `index.js` 顶部 |
| `my-memory` | 无外部依赖，装了就能用；数据存在 `~/.my-memory/memory.db` |

- 每个插件目录里的 README 会写清它自己要什么；没有 README 的，说明还没整理，别指望开箱即用
- 只在 Windows 上验证过。macOS / Linux 没测。

## 许可证

MIT，见 [LICENSE](LICENSE)。用、改、商用都行，出事别找我。
