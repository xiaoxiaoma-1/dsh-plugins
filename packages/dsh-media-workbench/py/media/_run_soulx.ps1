# SoulX 实测（无 Start-Job，避免 5.1 解析坑）
$ErrorActionPreference = 'Continue'
$log = 'E:\tools\soulx-run.log'
$root = 'E:\tools\soulx-podcast'
$vpy = Join-Path $root '.venv\Scripts\python.exe'
function Log($m) { ((Get-Date -Format 'HH:mm:ss') + '  ' + $m) | Out-File -FilePath $log -Append -Encoding UTF8 }

$env:PYTHONPATH = $root
# Windows 下 python 默认用 GBK 读文件，中文 JSON 会炸；UTF-8 模式一次性解决
$env:PYTHONUTF8 = '1'
Set-Location $root
Log 'GPU before inference:'
nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader 2>&1 | Out-File -FilePath $log -Append -Encoding UTF8
Log 'START'
$sw = [Diagnostics.Stopwatch]::StartNew()
& $vpy cli/podcast.py --json_path example/podcast_script/script_probe.json --model_path pretrained_models/SoulX-Podcast-1.7B --output_path outputs/probe.wav --seed 7 *>&1 | Out-File -FilePath $log -Append -Encoding UTF8
$sw.Stop()
Log ('ELAPSED ' + [math]::Round($sw.Elapsed.TotalSeconds, 1) + ' s')
Log 'GPU after inference:'
nvidia-smi --query-gpu=memory.used --format=csv,noheader 2>&1 | Out-File -FilePath $log -Append -Encoding UTF8
$out = Join-Path $root 'outputs\probe.wav'
if (Test-Path $out) {
    $st = Get-Item $out
    Log ('OUTPUT ' + [math]::Round($st.Length / 1MB, 2) + ' MB')
    & $vpy -c "import soundfile as sf;d,sr=sf.read(r'$out');print('dur',round(len(d)/sr,1),'sr',sr)" 2>&1 | Out-File -FilePath $log -Append -Encoding UTF8
} else { Log 'NO OUTPUT FILE' }
Log 'DONE'
