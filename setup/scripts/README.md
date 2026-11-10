# 本机脚本清单（工作台类插件的血肉）

`dsh-media-workbench`、`dsh-shot`、`dsh-call`、`dsh-pet`、`dsh-finance-health` 这几个插件，代码只是壳子，真正干活的是原机 `E:\tools\asr\` 下的一批脚本。

**这些脚本没有放进这个仓库。** 原因有两个：一部分绑死了私人数据（书库、稿件库、直播录制目录），一部分是原机作者攒的方法论核心。所以这里给的是**契约**——你照契约写一个等价物，插件就能跑。

---

## 三层：哪些会开出、哪些要自己写、哪些不打算给

| 层 | 脚本 | 状态 |
|---|---|---|
| 通用能力 | 语音服务、截图标注、桌宠进程、热点抓取 | **会开源**（脱敏后放 `setup/scripts/`） |
| 接私人数据 | 书库查询、稿件库查询、直播录制管线、稿件拆分、OCR 状态 | **只给表结构与接口**，数据自己造 |
| 方法论核心 | 选题生成、观点拆解、去 AI 味规则 | 不给（这是吃饭的东西） |

下表的「开源」列标了当前状态，`—` 表示按契约自己写。

---

## 契约表

### 语音与桌面

| 脚本 | 干什么 | 接口 | 开源 |
|---|---|---|---|
| `speech_server.py` | 常驻 HTTP 服务，收音频转文字，供 dsh-call / dsh-shot 调用 | `POST /asr`（音频 body）→ `{text}`；端口 `8777`；健康检查 `GET /health` | 计划 |
| `stream_asr_server.py` | 流式版本，边说边出字 | WebSocket，同样的转写结果 | 计划 |
| `dsh-pet.py` | 桌宠进程：把 AI 的进度画在桌面上 | 由 dsh-pet / dsh-bubble 用 `pythonw` 拉起，stdin 收 JSON 状态 | 计划 |
| `shot_overlay.ps1` | 截图时的全屏遮罩、框选、标注 | 由 dsh-shot 用 `powershell` 调用，参数是新截图的目标路径 | 计划 |
| `run_overlay.vbs` | 拉起遮罩但不弹黑窗 | 无参，转调上面的 ps1 | 计划 |

**要自己写的话，最小实现**：`speech_server.py` 用 `faster-whisper` 加载一个小模型，起个 HTTP 服务，`POST` 收 wav 返回 json 文本，监听 8777。二十行能跑通，插件就活了。

### 自媒体工作台 · 采集

| 脚本 | 干什么 | 接口 | 开源 |
|---|---|---|---|
| `hotdaily.py` | 抓各大平台热榜，落库 | `python hotdaily.py --date YYYY-MM-DD`，写 sqlite | 计划 |
| `hot_i18n.py` | 热榜条目翻中/英对照 | 读上一步的库，补字段 | 计划 |
| `capture_one.py` | 抓单条内容（链接→正文/视频→转写） | `python capture_one.py <url>` | 计划 |
| `xhs_follow_live.py` | 小红书直播跟录 | 轮询关注列表，命中就调录制器 | — |
| `clipwatch.ps1` | 监听剪辑输出目录，新片自动进流程 | 文件监听 | — |

### 自媒体工作台 · 内容库

| 脚本 | 干什么 | 接口 | 开源 |
|---|---|---|---|
| `wbquery.py` | 稿件库查询（全文/标签/时间） | 命令行传查询条件，stdout 出 json | — |
| `books_query.py` | 书库查询（24 万书块、1899 本） | 同上 | — |
| `split_ctl.py` | 长文拆块入库 | 读原文件，按章节切，写 sqlite | — |
| `dash_stats.py` | 库的统计面板数据 | stdout 出 json | — |
| `ocr_status.py` | 扫描件 OCR 进度 | stdout 出 json | — |
| `link_router.py` | 链接归类分发到对应管线 | 传 url，返回走哪条线 | — |
| `pool_db.py` | 连接池/统一 DB 入口 | 被上面几个 import | — |

**要自己写的话**：这几张表的最小结构写在 `setup/scripts/schema.sql`（后续补），字段名对上了，插件面板就能显示。

### 选题与成稿

| 脚本 | 干什么 | 接口 | 开源 |
|---|---|---|---|
| `daily_idea.py` | 从库里推选题 | 命令行传数量/方向，stdout 出 json | — |
| `auto_extract.py` | 从素材里抽观点 | 同上 | — |
| `memory_promote.py` | 把反复被纠正的点升成规则 | 读会话记录，写 AGENTS.md 追加区 | — |

### 其它

| 脚本 | 干什么 | 关联插件 |
|---|---|---|
| `mobile_server.py` | 手机端页面的本地服务 | 自媒体工作台手机端 |
| `github_trending/query.py` 等 | GitHub 热门项目采集与点评 | 自媒体工作台「选题」页 |

---

## 怎么接起来

插件里的路径全部走环境变量，把你的脚本放哪都行：

```powershell
# 用户级环境变量，设完重启 DSH
[Environment]::SetEnvironmentVariable('DSH_ASR_SCRIPT', 'D:\my\speech_server.py', 'User')
[Environment]::SetEnvironmentVariable('DSH_PYTHON', 'D:\Python312\python.exe', 'User')
```

`setup/install-env.ps1` 会按原机路径设好，你改盘符时改这几个就行，不用动代码。

---

## 判断标准

**想让某个插件真的可用，先看它在契约表里需要几个 `—`（要自己写的）。**

- 0 个 → 装了就能用
- 1~2 个 → 半天能补完，`speech_server.py` 是最典型的
- 3 个以上 → 属于「要接整套数据管线」，除非你有同等规模的素材库，否则先别装
