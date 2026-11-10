# py/ —— 自媒体工作台的真正实现

插件的界面在 `client.js`，但**所有真活都在这里的 263 个脚本里**。没有它们，界面能打开，点任何按钮都没反应。

## 目录

| 目录 | 脚本数 | 干什么 |
|---|---|---|
| `media/` | 162 | 主流程：采集入库、选题、成稿、素材卡、圆桌、手机端、书库查询、拆分、导出 |
| `asr/` | 44 | 语音与桌面：`speech_server.py`（转写服务，8777）、`dsh-pet.py`（桌宠）、`hotdaily.py`（热榜）、`shot_overlay.ps1`（截图遮罩）、`memory_promote.py`（纠正升级为规则） |
| `shuku/` | 52 | 书库治理：拆章、OCR 状态、统计、盘点 |
| `gh/` | 5 | GitHub 热门项目采集与点评 |

## 路径怎么配（不用改代码）

插件里所有路径都走两个环境变量：

| 变量 | 默认值 | 作用 |
|---|---|---|
| `DSH_PY_ROOT` | 插件目录下的 `py/` | 脚本根。想放别处就设这个 |
| `DSH_MEDIA_DATA` | `~/dsh-media-data` | **所有会写东西的地方都挂这下面**（热榜、库、导出、直播录制） |
| `DSH_PYTHON` | `%LOCALAPPDATA%\Programs\Python\Python312\python.exe` | 跑脚本的解释器 |
| `DSH_TOOLS_DIR` | `E:\tools` | 第三方工具目录（DouyinLiveRecorder 等） |

数据目录结构（`DSH_MEDIA_DATA` 下）：

```
<DATA_ROOT>/
├── hot/                 热榜抓取结果（按日期）
├── media/
│   ├── workbench.db     主库：素材、观点、选题、成稿
│   ├── settings.json    界面设置
│   ├── personas.json    角色（写稿人格）
│   ├── roundtable.json  圆桌配置
│   └── exports/         导出产物
├── wengao/              稿件原文件（md）
└── live/
    ├── rec/             直播录制文件
    └── transcript/      逐字稿
```

**换机器时只做一件事**：设 `DSH_MEDIA_DATA` 指向你的数据盘，然后在新位置建上面这套空目录。脚本会自己往里写。

## Python 依赖

跑这些脚本要一个装了语音包的 venv（见 `setup/ENVIRONMENT.md` 的 C4b）：

```
faster-whisper  funasr  ctranslate2  edge-tts  av  huggingface_hub  jieba
requests  httpx  openai  pandas  openpyxl  pydub
```

`setup/install-env.ps1` 会装好前十个；后面几个是表格和音频处理用，缺哪个脚本会直接报 `ModuleNotFoundError`，按名字 `pip install` 补上即可。

## 数据库从哪来

`workbench.db` 是空的话，界面能开但没内容。两张核心表：

```sql
-- 素材（书/推文/直播逐字稿/视频文案）
CREATE TABLE IF NOT EXISTS posts (
  id INTEGER PRIMARY KEY, platform TEXT, author TEXT, title TEXT,
  content TEXT, url TEXT, created_at INTEGER, topic TEXT
);
-- 观点（从素材里抽出来的）
CREATE TABLE IF NOT EXISTS insights (
  id INTEGER PRIMARY KEY, post_id INTEGER, text TEXT,
  kind TEXT, created_at INTEGER
);
```

先有 `posts` 才能跑「拆解」「选题」。没有素材库的话，用 `capture_one.py <url>` 先抓几条进来试。

## 三个最容易踩的坑

1. **脚本跑不起来先看 `DSH_PYTHON`**：默认路径是 Python 3.12 的系统安装位置，你若用 venv 就指向 venv 的 `python.exe`
2. **中文路径**：`DSH_MEDIA_DATA` 别放带空格的路径，脚本里有些地方没加引号
3. **ffmpeg 不在 PATH**：采集和剪辑会静默失败，先 `ffmpeg -version` 确认

## 少数脚本带原机路径残留

263 个里有 38 个还写着原机的绝对路径（作者本机是 `E:\`）。这些脚本多数是历史脚本、不是主流程必经之路。真用到时：

```powershell
# 在 py/ 目录里批量查
Select-String -Path .\media\*.py -Pattern 'E:\\' | Select-Object Filename,LineNumber
```

看到哪一行报错就改哪一行，改成 `Path(os.environ['DSH_MEDIA_DATA']) / 'xxx'` 即可。
