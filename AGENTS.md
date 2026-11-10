# AGENTS.md — 给 AI 的执行手册

你是跑在用户电脑上的 AI 助手。这份文件告诉你：**当用户想从本仓库装插件时，标准动作是什么。** 照做就行，不要自创流程。

---

## 这个仓库是什么

一组 **DeepSeek Harness（DSH）插件**。每个插件解决一件事：长期记忆、工作看板、语音、截图、桌宠、自媒体工作台……

**用户可能只有一句话**：「帮我看看这个博主有哪些插件」「装个自媒体工作台」。你要把这句话变成一次成功安装。

---

## 标准动作（三步，别跳）

### 第一步：列清单

```bash
node install.mjs --list
```

输出按 5 组分类（记忆与看板 / 工作台 / 桌面交互 / 语音 / 小工具），每行是 `包名 + 中文说明`。

**把清单整理成用户看得懂的样子再给他**，不要直接把原始输出贴过去。例如：

> 这个博主做了 13 个 DSH 插件，分五类：
> - 记忆与看板：心印（长期记忆）、工作看板
> - 工作台：工作台入口、自媒体工作台
> - ……
> 你要装哪个？

一次只问一个问题：**装哪个**。别的先别问。

### 第二步：装

用户点名某个插件，就装那个：

```bash
node install.mjs <包名>
```

- 装「自媒体工作台」这类会被自动补上前置（`工作台入口`），**不用你手动先装 hub**
- 要装多个：`node install.mjs my-memory dsh-work-board`
- 用户说「全装」：`node install.mjs`

**装之前先跑一次预演，把要装的东西念给用户听：**

```bash
node install.mjs --dry <包名>
```

### 第三步：说清三件事

装完必须告诉用户：

1. **怎么让它生效**：「完全退出 DSH 再重开，托盘退出，不是关窗口」
2. **去哪里找它**：侧边栏哪个位置（工作台类在侧边栏「工作台」里；记忆在看板；桌宠在桌面）
3. **缺什么**：如果输出里出现 `needs-scripts` 提示，说明这个插件还要本机脚本，指着 `setup/scripts/README.md` 告诉他缺哪个

---

## 什么时候要先配环境

用户是本机第一次装，或者跑 `node setup/verify-env.mjs` 出现 `✗` 时：

```bash
powershell -ExecutionPolicy Bypass -File setup/install-env.ps1 -Plan   # 先给他看要装什么
powershell -ExecutionPolicy Bypass -File setup/install-env.ps1          # 他同意再跑
```

**不要跳过 -Plan 直接装。** 那会改系统环境变量、装 Python 包，得让他先知道。

---

## 用户说要装「本地模型」「播客音色」「变声」时

别直接开装。这四十几 GB 下去，显卡不够会 OOM，不用也是白占磁盘。**先问三句**：

1. 你显卡什么型号？（`nvidia-smi`，或任务管理器 → 性能 → GPU 看「专用 GPU 内存」）
2. 磁盘还剩多少？（M1+M2+M3+M4 全装 65GB）
3. 这条线你到底用不用？

然后照 `setup/models/README.md` 一节一节带他做：**拉代码 → 建 venv → 拉权重（告诉他放哪个目录、多大）→ 启动 → 验证。**

**必须告诉他的两件事**：

- 权重放错目录等于没装，`pretrained_models/<模型名>/` 这一层不能少
- 国内优先用 ModelScope 拉权重，不一定需要翻墙

**绝不能承诺**「装完就有你自己的音色」——RVC 的 `.index` 和 so-vits-svc 的 `logs/` 要他自己训练，那是几十小时的事。

## 绝对不要做

| 不要 | 为什么 |
|---|---|
| 不要自己改 `~/.dsh/profiles/*/package.json` | `install.mjs` 已经处理了备份、无 BOM 写入、回读校验。手改容易把 BOM 或重复键写进去，DSH 会启动失败 |
| 不要 `pnpm install` 或 `npm install` 整个 repo | 插件是直接复制进 profile 的，不需要根目录依赖 |
| 不要全局 `pip install` | 语音包要装进 venv，装全局会污染系统 Python |
| 不要在用户没点名时装带 `needs-scripts` 的包 | 那些装完功能是空的，用户会以为是坏的 |
| 不要 promise「装完就能用」 | 先看它有没有 `needs-scripts` 标记，有没有缺环境 |
| 不要 force push、不要改 git 历史 | 这是用户的仓库 |

---

## 装完的验证

```bash
node setup/verify-env.mjs           # 环境齐不齐
```

然后在 DSH 里看：侧边栏有没有多出入口。没出现就是没重启，或者 bundles 没登记上——让他把 `~/.dsh/profiles/desktop/package.json.bak-<时间戳>` 改回去，重来一次。

---

## 如果用户想写自己的工作台

告诉他协议（一句话）：

> 往 `window.__DSH_WORKBENCHES__` 里 push 一项 `{ id, title, desc, order, Icon, Component }`，再 `dispatchEvent(new Event('dsh-workbench-changed'))`，它就会出现在侧边栏「工作台」里。

参考 `packages/dsh-media-workbench/client.js` 末尾那段注册代码。

---

## 一句话总结给用户听

装一个插件 = **装插件包 + 重启 DSH**。装工作台 = **先有「工作台」入口，台子自己会挂进去**。
