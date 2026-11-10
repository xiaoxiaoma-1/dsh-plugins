<#
.SYNOPSIS
  按 py/README.md 建数据目录骨架（幂等，已存在就跳过）
.EXAMPLE
  powershell -ExecutionPolicy Bypass -File py\setup-data.ps1
  powershell -ExecutionPolicy Bypass -File py\setup-data.ps1 -Root "D:\my-data"
#>
param([string]$Root = "")

$ErrorActionPreference = "Continue"
if (-not $Root) {
  $Root = $env:DSH_MEDIA_DATA
  if (-not $Root) { $Root = Join-Path $env:USERPROFILE "dsh-media-data" }
}

Write-Host "数据根目录: $Root" -ForegroundColor Cyan

$dirs = @(
  "hot",
  "media",
  "media\exports",
  "wengao",
  "live\rec",
  "live\transcript"
)

foreach ($d in $dirs) {
  $p = Join-Path $Root $d
  if (Test-Path $p) { Write-Host "  已存在 $d" -ForegroundColor DarkGray }
  else { New-Item -ItemType Directory -Force -Path $p | Out-Null; Write-Host "  建好   $d" -ForegroundColor Green }
}

# 主库建表（空库，等采集往里写）
$dbScript = Join-Path $PSScriptRoot "media\_init_db.py"
if (Test-Path $dbScript) {
  Write-Host "`n初始化数据库..." -ForegroundColor Gray
  $py = $env:DSH_PYTHON
  if (-not $py) { $py = "python" }
  & $py $dbScript $Root
} else {
  Write-Host "`n（没找到 media\_init_db.py，跳过建表；表结构见 py\README.md）" -ForegroundColor Yellow
}

# 打印环境变量设置命令
Write-Host "`n把下面这句贴到 PowerShell 里跑一次，让插件找到这个目录：" -ForegroundColor Cyan
Write-Host "  [Environment]::SetEnvironmentVariable('DSH_MEDIA_DATA', '$Root', 'User')" -ForegroundColor White
Write-Host "`n设完托盘退出 DSH 再重开。" -ForegroundColor Gray