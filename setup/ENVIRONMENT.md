# 环境清单（给 AI 看的说明书）

这个仓库里的插件不是纯前端代码，一半以上要靠本机环境干活。这份文件的作用：**换一台电脑时，把这份文件丢给 AI，让它照着把环境配成和原机器一样**。

装法分三级。**第一级不装，一个插件都跑不起来；第二级按需；第三级是几十 GB 的模型，想用再拉。**

先把一级跑完，再往下。

---

## 怎么让 AI 一次配好

对 DSH 说这一句就行：

> 读 setup/ENVIRONMENT.md，按第一级和第二级把环境配好，配完跑 setup/verify-env.mjs 给我看结果

它会自己装、自己验、缺什么自己补。装不上的（第三级模型、要手动下载的绿色包）它会告诉你去点哪里。

---

## 第一级：核心（必须，全部能自动装）

| # | 东西 | 版本 | 干什么用 | 谁依赖 |
|---|---|---|---|---|
| C1 | Windows 10/11 x64 | — | 全部插件只在 Windows 验证过 | 全部 |
| C2 | DeepSeek Harness 桌面端 | ≥ 0.2.0 | 插件宿主 | 全部 |
| C3 | Node.js | ≥ 22（原机 v24.19.0） | 插件运行、install.mjs | 全部 |
| C4 | Python | 3.12.x（原机 3.12.10） | 语音、转写、采集脚本 | dsh-call、dsh-shot、dsh-bubble、dsh-pet、dsh-finance-health |
| C5 | Git | ≥ 2.40 | 拉仓库 | 全部 |
| C6 | ffmpeg | ≥ 6（原机 9.0.2 full） | 音视频转码、抽帧 | 自媒体工作台、播客台 |

Python 包（装进一个 venv，别装进系统 Python）：

```
faster-whisper==1.2.1      语音转文字
funasr==1.4.22             中文语音识别
ctranslate2==4.8.4         faster-whisper 的推理后端
edge-tts==7.3.1            TTS 快档（免费）
av==19.0.2                 音视频解码
huggingface_hub==2.4.0     拉模型
jieba==0.42.1              中文分词
openai / requests / httpx  调用模型接口
```

原机 venv 在 `E:\tools\asr\.venv`（Python 3.12.10）。新机器照这个位置建，插件的默认路径就对得上；不想照抄就设环境变量 `DSH_PYTHON` 指过去。

---

## 第二级：工具（插件用到才装）

| # | 东西 | 大小 | 干什么用 | 谁依赖 | 装法 |
|---|---|---|---|---|---|
| T1 | DouyinLiveRecorder | ~750MB | 直播录制与转写管线 | 自媒体工作台 | git clone 后 `pip install -r requirements.txt` |
| T2 | JDK 25 | ~290MB | REA 反编译 Java 部分 | dsh-rea | `winget install EclipseAdoptium.Temurin.25.JDK`，或解压到 `E:\tools\jdk25` |
| T3 | Ghidra 12.x | ~860MB | 逆向分析 | dsh-rea | 官网下 zip 解压到 `E:\tools\ghidra_12.1.4_PUBLIC` |
| T4 | rizin | ~65MB | 二进制分析 | dsh-rea | `winget install rizin.rizin` 或解压到 `E:\tools\rizin` |
| T5 | apktool | ~15MB | 拆 APK | dsh-rea | 官网下 jar + bat 放 `E:\tools\apktool` |
| T6 | 7-Zip | ~9MB | 解压各类安装包 | 环境搭建本身 | `winget install 7zip.7zip` |
| T7 | SnippingTool | 系统自带 | dsh-shot 区域截图 | dsh-shot | Win10/11 自带，不用装 |

---

## 第三级：模型资产（几十 GB，按需，不进仓库）

**这些不是"装环境"，是"拉模型"。不装也能用 11 个插件，只是播客台、变声、数字人这几条线跑不了。**

| # | 东西 | 原机体积 | 干什么 |
|---|---|---|---|
| M1 | soulx-podcast | 11.3GB | 高质量双人对谈 TTS（播客主档） |
| M2 | CosyVoice | 11.2GB | 声音克隆 |
| M3 | GPT-SoVITS（sovits） | 22.8GB | 音色训练与合成 |
| M4 | RVC | 18.4GB | 实时变声 |
| M5 | dfnet | 4.7GB | 人声分离 |
| M6 | mineru | 0.6GB | PDF 解析（书库入库） |

六项合计约 **69GB**。原机全放在 `E:\tools\` 下，每个目录自带 venv 和权重。

新机器上不追求一次拉全。用哪条线拉哪个，装法记在各自的模型仓库 README 里，这里只保证：**装完之后路径和原机一致，插件不用改代码。**

---

## 插件 → 环境依赖矩阵

| 插件 | 需要 |
|---|---|
| `my-memory` | C2、C3（零外部依赖，装了就能用） |
| `dsh-work-board` | C2、C3 |
| `dsh-workbench-hub` | C2、C3 |
| `dsh-ziwei` | C2、C3、npm `iztro` |
| `dsh-ponytail-lazy` | C2、C3 |
| `dsh-purge-console` | C2、C3 |
| `dsh-jarvis` | C2、C3、C4（语音播报） |
| `dsh-call` | C2、C3、C4、Python 包（funasr/edge-tts）+ `speech_server.py` |
| `dsh-bubble` | C2、C3、C4（桌宠进程） |
| `dsh-pet` | C2、C3、C4 + `dsh-pet.py` |
| `dsh-shot` | C2、C3、C4 + `shot_overlay.ps1` + T7 |
| `dsh-finance-health` | C2、C3、C4 |
| `dsh-rea` | C2、C3 + T2 + T3 + T4 + T5 |
| 自媒体工作台（私有） | 全部一级 + T1 + ffmpeg + M5 |
| 学习台（私有） | 一级 |
| 播客台（私有） | 一级 + M1 + M3 |

**标了脚本文件的（`speech_server.py`、`shot_overlay.ps1`、`dsh-pet.py`），这些脚本没进开源仓库**——它们在原机 `E:\tools\asr\` 下，属于私有资产。想用对应插件，得先拿到这些脚本，或者自己写一个等价物。

---

## 路径约定（不改代码就能换机器的方法）

插件里所有本机路径都能用环境变量顶掉，按这个表设：

| 环境变量 | 用途 | 原机值 |
|---|---|---|
| `DSH_HOME` | DSH 数据目录 | `E:\DSH-data\.dsh` |
| `DSH_PYTHON` | python.exe 全路径 | `%LOCALAPPDATA%\Programs\Python\Python312\python.exe` |
| `DSH_ASR_SCRIPT` | 语音服务脚本 | `E:\tools\asr\speech_server.py` |
| `DSH_PET_PY` | 桌宠用的 pythonw | `%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe` |
| `DSH_PET_SCRIPT` | 桌宠脚本 | `E:\tools\asr\dsh-pet.py` |
| `DSH_FINANCE_DIR` | 财务数据目录 | `E:\desktop\财务健康` |
| `DSH_FINANCE_PYTHON` | 财务插件用 python | 同上 |
| `DSH_INTRO_KEY_FILE` | 模型网关 key 文件 | `E:\DSH-data\.dsh\openai-gateway\api-key` |

新机器如果盘符不同（没有 E 盘），把这些变量改掉就行，不用动代码。

---

## 装不上怎么办（降级顺序）

1. **Python 装不上** → 只有 4 个插件（call / shot / bubble / pet / finance）真的需要它；先跳过，其它 8 个照用
2. **ffmpeg 装不上** → 自媒体台和播客台的转码会失败，其它正常
3. **REA 的工具链不全** → 只装 jdk25 + rizin 就能分析 Java 类目标；Ghidra 是重型可选
4. **模型不拉** → 播客台降级到 `edge-tts`（快档、免费、音质一般），其它不受影响
5. **完全没有外网** → 一级的 C3/C4/C5/C6 用离线安装包；Python 包可以提前 `pip download` 带走

---

## 验证

```bash
node setup/verify-env.mjs
```

逐项打勾，缺什么直接告诉你装哪个。全部一级 + 需要的二级过了，就可以 `node install.mjs` 装插件了。
