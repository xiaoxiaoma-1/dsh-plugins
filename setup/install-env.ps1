<#
.SYNOPSIS
  按 setup/ENVIRONMENT.md 自动配置第一级、第二级环境（幂等，已装就跳过）。

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File setup\install-env.ps1 -Plan
  powershell -ExecutionPolicy Bypass -File setup\install-env.ps1

.NOTES
  -Plan  只打印要做什么，不实际安装
#>
param(
  [switch]$Plan,
  [string]$ToolsDir = "E:\tools",
  [string]$VenvPath = ""
)

$ErrorActionPreference = "Continue"
$todo = @()
$done = @()
$fail = @()

function Say($m, $c = "Gray") { Write-Host $m -ForegroundColor $c }
function Step($m) { Write-Host "`n== $m" -ForegroundColor Cyan }
function Run($exe, $argList, $what) {
  if ($Plan) { Say "  [plan] $exe $($argList -join ' ')" "DarkGray"; return $true }
  Say "  执行: $exe $($argList -join ' ')" "DarkGray"
  try {
    & $exe @argList 2>&1 | ForEach-Object { if ($_ -and $_.ToString().Trim()) { Say "    $_" "DarkGray" } }
    return ($LASTEXITCODE -eq 0)
  } catch {
    Say "  失败: $($_.Exception.Message)" "Red"
    return $false
  }
}
function Have($cmd) { return [bool](Get-Command $cmd -ErrorAction SilentlyContinue) }
function HaveWinget() { return (Have "winget") }
function WingetInstall($id, $label) {
  if (-not (HaveWinget)) { Say "  没有 winget，请手动装 $label" "Yellow"; $fail += $label; return $false }
  $ok = Run "winget" @("install", "--id", $id, "-e", "--silent", "--accept-source-agreements", "--accept-package-agreements") $label
  if ($ok) { $done += $label } else { $fail += $label }
  return $ok
}

Say "DSH 插件环境配置（第一级 + 第二级）" "White"
Say "工具目录: $ToolsDir"
if ($Plan) { Say "模式: 只预演，不落盘" "Yellow" }

# ---------- 第一级 ----------
Step "C3 Node.js >= 22"
if (Have "node") {
  $nv = (& node --version) -replace "v", ""
  $major = [int]($nv.Split(".")[0])
  if ($major -ge 22) { Say "  已有 v$nv，跳过" "Green"; $done += "Node $nv" }
  else { Say "  已有 v$nv 但低于 22" "Yellow"; WingetInstall "OpenJS.NodeJS.LTS" "Node.js LTS" | Out-Null }
} else { WingetInstall "OpenJS.NodeJS.LTS" "Node.js LTS" | Out-Null }

Step "C4 Python 3.12"
$pyOk = $false
foreach ($p in @("$env:LOCALAPPDATA\Programs\Python\Python312\python.exe", "$ToolsDir\asr\.venv\Scripts\python.exe")) {
  if (Test-Path $p) { Say "  已有 $p" "Green"; $done += "Python"; $pyOk = $true; break }
}
if (-not $pyOk) {
  if (Have "python") {
    $v = (& python --version) 2>&1
    Say "  PATH 里有 $v" "Green"; $done += "Python"; $pyOk = $true
  } else {
    WingetInstall "Python.Python.3.12" "Python 3.12" | Out-Null
    $pyOk = $true
  }
}

Step "C5 Git"
if (Have "git") { Say "  已有 $(git --version)" "Green"; $done += "Git" }
else { WingetInstall "Git.Git" "Git" | Out-Null }

Step "C6 ffmpeg"
if (Have "ffmpeg") { Say "  已有 ffmpeg" "Green"; $done += "ffmpeg" }
else { WingetInstall "Gyan.FFmpeg" "ffmpeg" | Out-Null }

# ---------- Python 环境 ----------
Step "C4b Python 语音包（venv）"
if (-not $VenvPath) {
  if (Test-Path "$ToolsDir\asr") { $VenvPath = "$ToolsDir\asr\.venv" }
  else { $VenvPath = "$env:LOCALAPPDATA\Programs\Python\venv-dsh" }
}
$venvPy = Join-Path $VenvPath "Scripts\python.exe"
if (Test-Path $venvPy) {
  Say "  venv 已存在: $VenvPath" "Green"
} else {
  Say "  建 venv: $VenvPath" "Gray"
  if (-not $Plan) { New-Item -ItemType Directory -Force -Path (Split-Path $VenvPath) | Out-Null }
  Run "python" @("-m", "venv", $VenvPath) "创建 venv" | Out-Null
  $done += "venv"
}
$pkgs = @(
  "faster-whisper==1.2.1", "funasr==1.4.22", "ctranslate2==4.8.4",
  "edge-tts==7.3.1", "av==19.0.2", "huggingface_hub==2.4.0",
  "jieba==0.42.1", "requests", "httpx", "openai"
)
if ($Plan) {
  Say "  [plan] pip install $($pkgs -join ' ')" "DarkGray"
} else {
  Say "  安装 $($pkgs.Count) 个包（几分钟）" "Gray"
  & $venvPy -m pip install --upgrade pip 2>&1 | Out-Null
  $okAll = Run $venvPy (@("-m", "pip", "install") + $pkgs) "Python 包"
  if ($okAll) { $done += "Python 包" } else { $fail += "Python 包" }
}

# ---------- 环境变量 ----------
Step "环境变量"
$envs = @{
  "DSH_PYTHON"     = $venvPy
  "DSH_PET_PY"     = (Join-Path (Split-Path $venvPy) "pythonw.exe")
  "DSH_ASR_SCRIPT" = "$ToolsDir\asr\speech_server.py"
  "DSH_PET_SCRIPT" = "$ToolsDir\asr\dsh-pet.py"
}
foreach ($k in $envs.Keys) {
  $v = $envs[$k]
  if ($Plan) { Say "  [plan] 用户环境变量 $k = $v" "DarkGray"; continue }
  [Environment]::SetEnvironmentVariable($k, $v, "User")
  Say "  已设 $k = $v" "Green"
}
$done += "环境变量"

# ---------- 第二级 ----------
Step "第二级 · 要手动下的（脚本不代劳）"
$manual = @(
  "T1 DouyinLiveRecorder  -> git clone 后 pip install -r requirements.txt，放 $ToolsDir\DouyinLiveRecorder",
  "T2 JDK 25              -> winget install EclipseAdoptium.Temurin.25.JDK，或解压到 $ToolsDir\jdk25",
  "T3 Ghidra 12.x         -> 官网下 zip，解压到 $ToolsDir\ghidra_12.1.4_PUBLIC",
  "T4 rizin               -> winget install rizin.rizin，或解压到 $ToolsDir\rizin",
  "T5 apktool             -> 官网下 jar+bat，放 $ToolsDir\apktool",
  "T7 SnippingTool        -> Win10/11 自带，无需安装"
)
foreach ($m in $manual) { Say "  $m" "Gray" }

Step "第三级 · 模型（按需，几十 GB，不在这里拉）"
Say "  soulx-podcast / CosyVoice / GPT-SoVITS / RVC / dfnet / mineru" "DarkGray"
Say "  要哪条线再拉哪个，装法见各自仓库 README" "DarkGray"

# ---------- 汇总 ----------
Step "汇总"
Say "  完成: $($done -join ', ')" "Green"
if ($fail.Count) { Say "  失败: $($fail -join ', ')" "Red"; Say "  失败项多为网络或权限导致，重跑一次本脚本即可（幂等）" "Yellow" }

Say "`n下一步：" "White"
Say "  1) node setup/verify-env.mjs     看体检结果" "Gray"
Say "  2) node install.mjs              装插件" "Gray"
Say "  3) 托盘退出 DSH 再重开" "Gray"
exit 0
