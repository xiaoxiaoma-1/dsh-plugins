# 本地模型部署指南（给 AI 用）

这几个模型不是「装个软件」那么简单：要拉权重（几 GB 到几十 GB）、建 venv、配显存。**没有它们，播客台、变声、人声分离、PDF 解析这几条线跑不了；其它插件不受影响。**

**给 AI 的话**：用户说要装某个模型时，先读对应那一节，按「前置 → 拉代码 → 拉权重 → 建环境 → 启动 → 验证」的顺序带他做，每步告诉他"你应该看到什么"。**不要跳步，不要假设他有 GitHub 访问能力，先问他能不能打开 GitHub。**

---

## 总览

| # | 模型 | 官方仓库 | 干什么 | 权重 | 显存（估算） | 本机体积 |
|---|---|---|---|---|---|---|
| M1 | SoulX-Podcast | `Soul-AILab/SoulX-Podcast` | 双人对谈播客 TTS（主音质档） | `SoulX-Podcast-1.7B` 5.36GB | 8–10GB | 11.3GB |
| M2 | CosyVoice | `QwenAudio/CosyVoice` | 声音克隆、零样本配音 | `CosyVoice2-0.5B` 5.23GB | 6–8GB | 11.2GB |
| M3 | so-vits-svc | `svc-develop-team/so-vits-svc` | 歌声转换（把你的声音换成别人） | 自己在 `logs/` 下训练 | 4–6GB | 22.8GB |
| M4 | RVC | RVC 官方整合包（网页版 WebUI） | 实时变声、音色替换 | `assets/*.pth` 内置 + 自己训 `.index` | 4–6GB | 18.4GB |
| M5 | dfnet | 人声分离环境（Python venv） | 从音频里分离人声/伴奏 | 随包 | CPU 也行 | 4.7GB |
| M6 | MinerU | `opendatalab/MinerU`（4.1.3） | PDF 解析成结构化文本（书库入库用） | 随包 | CPU 也行 | 0.6GB |

**显存是估算值，装之前让用户报一下显卡型号**（`nvidia-smi` 或任务管理器→性能→GPU）。低于表里的数字就先别装，会 OOM 报错。

---

## M1 · SoulX-Podcast（播客主档）

**干什么**：给一个话题，生成两个主持人自然对谈的音频，带笑声、停顿这类口语特征。播客台的高质量档就是它。

**前置**：Python 3.10–3.12、Git、≥8GB 显存的 N 卡、GitHub 能打开。

**步骤**

```powershell
# 1) 拉代码（放哪都行，本机放在 E:\tools\soulx-podcast）
cd E:\tools
git clone https://github.com/Soul-AILab/SoulX-Podcast.git

# 2) 建环境（在项目目录里）
cd soulx-podcast
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -U pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

**3) 拉权重**——权重必须放在 `pretrained_models/SoulX-Podcast-1.7B/` 下。下载命令以官方 README 的 Download 一节为准（HuggingFace 或 ModelScope 两种，国内优先 ModelScope，不用翻墙）。

拉完这个目录下应该能看到模型文件和配置，**总大小 5.36GB 左右**。少了就是没下全，重新拉。

**4) 验证**

```powershell
.\.venv\Scripts\python.exe -c "import torch; print(torch.cuda.is_available())"
```

看到 `True` 才算显卡认到了。再跑官方 README 里的第一条示例命令，能输出一段音频文件就是通了。

**装不上怎么办**：播客台自动降级到 `edge-tts`（免费、快、音质一般）。节目照样能出，只是听着没那么"像人"。

---

## M2 · CosyVoice（声音克隆）

**干什么**：给几秒参考音，用它说任何话。配音、口播替换用。

**前置**：同 M1，显存 ≥6GB。

**步骤**

```powershell
cd E:\tools
git clone https://github.com/QwenAudio/CosyVoice.git
cd CosyVoice
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -U pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

**权重**：放 `pretrained_models/CosyVoice2-0.5B/`，大小 5.23GB 左右。下载方式见官方 README（ModelScope 国内可直接拉）。

**验证**：官方 README 的零样本克隆示例，给一段 3–10 秒的 wav，能生成新音频即为通。

**注意**：克隆别人的声音涉及肖像/声音权，自己玩可以，别拿去做商业内容。

---

## M3 · so-vits-svc（歌声转换）

**干什么**：把一段清唱换成某个音色的歌声。这不是"文字转语音"，是"声音换声音"。

**别和 GPT-SoVITS 搞混**，两个不同项目。本机装的是 so-vits-svc。

**前置**：≥4GB 显存；需要自己准备**训练数据**（目标音色的干声，至少 30 分钟），这一步没有捷径。

**步骤**

```powershell
cd E:\tools
git clone https://github.com/svc-develop-team/so-vits-svc.git sovits
cd sovits
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -U pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

**权重**：预训练底模放 `pretrained/`（官方 README 给链接）。**你自己的音色模型要自己训**——本机 `logs/` 下那几十 GB 是原机主人训练的私人音色，不给。

**验证**：官方 README 的 `inference_main.py` 示例，用任一公开底模跑出一段音频即通。

**装不上怎么办**：这条线不做也不影响别的。它就是玩票性质。

---

## M4 · RVC（实时变声）

**干什么**：实时把麦克风声音换成另一个音色，直播、语音聊天用。

**这个最简单**：官网下整合包（带 runtime 和 ffmpeg 的压缩包），解压即用，不用建 venv。

**步骤**

1. 去 RVC 官方发布页下 **N 卡整合包**（文件名通常带 `Nvidia` 和日期）
2. 解压到 `E:\tools\RVC20260718Nvidia`（或任意目录，路径别带中文）
3. 双击 `go-webui.bat`，浏览器会自动打开 `http://127.0.0.1:7897` 这类地址
4. 首次启动会下载底模（`assets/` 下的 `D32k.pth`/`D40k.pth`/`D48k.pth`，各 105MB）

**音色模型（`.index`）要自己训**：本机 `assets/` 里那几个 `*V1.index` 是原机主人自己训练的私人音色，不给。

**验证**：WebUI 能打开、能选到音色、点「转换」出音频即通。

---

## M5 · dfnet（人声分离）

**干什么**：一段音频里把人和伴奏拆开。采集来的视频要提取干净人声，得先过它。

**这个最轻**：装好 Python 包就能用，CPU 也能跑。

```powershell
cd E:\tools
python -m venv dfnet
.\dfnet\Scripts\python.exe -m pip install -U pip
.\dfnet\Scripts\python.exe -m pip install audio-separator
```

**验证**

```powershell
.\dfnet\Scripts\audio-separator.exe --help
```

能打出帮助就是通了。

---

## M6 · MinerU（PDF 解析）

**干什么**：把 PDF（尤其扫描件、带公式的）解析成结构化文本。书库入库靠它。

**前置**：Python 3.10+，磁盘留 2GB。CPU 能跑，慢一点。

```powershell
cd E:\tools
python -m venv mineru-venv
.\mineru-venv\Scripts\python.exe -m pip install -U pip
.\mineru-venv\Scripts\python.exe -m pip install "mineru[core]"
```

**验证**

```powershell
.\mineru-venv\Scripts\mineru.exe --version
```

能打出 `4.x` 就是通了。

---

## 装模型之前先问用户这三句

1. **你显卡是什么型号？**（`nvidia-smi` 或 任务管理器 → 性能 → GPU 1 看「专用 GPU 内存」）
2. **磁盘还剩多少？**（M1+M2+M3+M4 全装要 65GB）
3. **你确定要用这条线吗？**（不知道自己要不要，就别装。这四十几 GB 下下来不用，纯浪费）

---

## 一句话判断

| 你想干的事 | 必须装 |
|---|---|
| 生成双人对谈播客 | M1（没有就降级 edge-tts） |
| 用自己的/别人的音色说话 | M2 |
| 唱歌换音色 | M3 + 自己训练 |
| 实时变声直播 | M4 + 自己训练 |
| 从视频里提干净人声 | M5 |
| PDF 书转文字入库 | M6 |
| 只是文字对话、写东西、看板、截图 | **一个都不用装** |
