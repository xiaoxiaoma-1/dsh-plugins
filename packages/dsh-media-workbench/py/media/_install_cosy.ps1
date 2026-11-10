# CosyVoice2 安装（后台；Windows 上 pynini/wetext 可能失败，失败也照实记录）
$ErrorActionPreference = 'Continue'
$log = 'E:\tools\cosy-install.log'
$root = 'E:\tools\CosyVoice'
function Log($m) { ((Get-Date -Format 'HH:mm:ss') + '  ' + $m) | Out-File -FilePath $log -Append -Encoding UTF8 }

Log 'START'
if (-not (Test-Path (Join-Path $root 'requirements.txt'))) {
    Log 'clone...'
    git clone --depth 1 https://github.com/QwenAudio/CosyVoice.git $root *>&1 | Out-File -FilePath $log -Append -Encoding UTF8
    if (-not (Test-Path (Join-Path $root 'requirements.txt'))) {
        Remove-Item $root -Recurse -Force -ErrorAction SilentlyContinue
        git clone --depth 1 https://ghfast.top/https://github.com/QwenAudio/CosyVoice.git $root *>&1 | Out-File -FilePath $log -Append -Encoding UTF8
    }
}
Log ('repo ok: ' + (Test-Path (Join-Path $root 'requirements.txt')))

$vpy = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path $vpy)) {
    Log 'venv 3.10...'
    uv venv --python 3.10 (Join-Path $root '.venv') *>&1 | Out-File -FilePath $log -Append -Encoding UTF8
}
Log ('venv ok: ' + (Test-Path $vpy))

Log 'install requirements (跳过 ttsfrd，Windows 无轮子)...'
$req = Get-Content (Join-Path $root 'requirements.txt') | Where-Object { $_ -notmatch 'ttsfrd|WeTextProcessing' }
$tmpReq = Join-Path $root 'requirements_win.txt'
$req | Out-File -FilePath $tmpReq -Encoding ascii
uv pip install --python $vpy -r $tmpReq --index-url https://mirrors.aliyun.com/pypi/simple/ *>&1 | Out-File -FilePath $log -Append -Encoding UTF8

Log 'install modelscope...'
uv pip install --python $vpy modelscope --index-url https://mirrors.aliyun.com/pypi/simple/ *>&1 | Out-File -FilePath $log -Append -Encoding UTF8

Log 'download CosyVoice2-0.5B...'
$dl = "from modelscope import snapshot_download; snapshot_download('iic/CosyVoice2-0.5B', local_dir=r'$root\pretrained_models\CosyVoice2-0.5B')"
& $vpy -c $dl *>&1 | Out-File -FilePath $log -Append -Encoding UTF8

Log 'model dir:'
Get-ChildItem (Join-Path $root 'pretrained_models\CosyVoice2-0.5B') -ErrorAction SilentlyContinue | ForEach-Object { $_.Name + ' ' + $_.Length } | Out-File -FilePath $log -Append -Encoding UTF8
Log 'DONE'
