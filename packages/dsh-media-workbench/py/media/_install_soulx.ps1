# SoulX-Podcast 安装（后台跑，日志 E:\tools\soulx-install.log）
$ErrorActionPreference = 'Continue'
$log = 'E:\tools\soulx-install.log'
function Log($m) { $t = Get-Date -Format 'HH:mm:ss'; "$t  $m" | Tee-Object -FilePath $log -Append }

Log '=== 开始 ==='
$root = 'E:\tools\soulx-podcast'
if (-not (Test-Path $root)) {
    Log '克隆仓库（直连）...'
    git clone --depth 1 https://github.com/Soul-AILab/SoulX-Podcast.git $root 2>&1 | Tee-Object -FilePath $log -Append
    if (-not (Test-Path (Join-Path $root 'requirements.txt'))) {
        Log '直连失败，换 ghfast 镜像...'
        Remove-Item $root -Recurse -Force -ErrorAction SilentlyContinue
        git clone --depth 1 https://ghfast.top/https://github.com/Soul-AILab/SoulX-Podcast.git $root 2>&1 | Tee-Object -FilePath $log -Append
    }
    if (-not (Test-Path (Join-Path $root 'requirements.txt'))) {
        Log 'ghfast 也失败，换 gitclone...'
        Remove-Item $root -Recurse -Force -ErrorAction SilentlyContinue
        git clone --depth 1 https://gitclone.com/github.com/Soul-AILab/SoulX-Podcast.git $root 2>&1 | Tee-Object -FilePath $log -Append
    }
}
Log ('仓库状态: ' + (Test-Path (Join-Path $root 'requirements.txt')))

Log '准备 python 3.11（uv）...'
uv python install 3.11 2>&1 | Tee-Object -FilePath $log -Append
$py311 = (uv python find 3.11 2>$null)
Log ('python3.11 = ' + $py311)

if ($py311) {
    Log '建 venv...'
    if (-not (Test-Path (Join-Path $root '.venv'))) {
        uv venv --python 3.11 (Join-Path $root '.venv') 2>&1 | Tee-Object -FilePath $log -Append
    }
    $vpy = Join-Path $root '.venv\Scripts\python.exe'
    Log ('venv python: ' + $vpy + ' 存在=' + (Test-Path $vpy))
    if (Test-Path $vpy) {
        Log '装依赖（国内镜像）...'
        & $vpy -m pip install -r (Join-Path $root 'requirements.txt') -i https://mirrors.aliyun.com/pypi/simple/ 2>&1 | Tee-Object -FilePath $log -Append
        Log '下模型（hf-mirror）...'
        $env:HF_ENDPOINT = 'https://hf-mirror.com'
        & $vpy -m pip install -U huggingface_hub -i https://mirrors.aliyun.com/pypi/simple/ 2>&1 | Tee-Object -FilePath $log -Append
        $dl = "from huggingface_hub import snapshot_download; snapshot_download('Soul-AILab/SoulX-Podcast-1.7B', local_dir=r'$root\pretrained_models\SoulX-Podcast-1.7B')"
        & $vpy -c $dl 2>&1 | Tee-Object -FilePath $log -Append
        Log '模型目录内容:'
        Get-ChildItem (Join-Path $root 'pretrained_models\SoulX-Podcast-1.7B') -ErrorAction SilentlyContinue | Select-Object Name, Length | Format-Table -AutoSize | Out-String | ForEach-Object { $_.Trim() } | Tee-Object -FilePath $log -Append
    }
}
Log '=== 结束 ==='
