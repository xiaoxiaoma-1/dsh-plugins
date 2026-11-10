# SoulX-Podcast 第二步：装依赖 + 下模型（uv pip，绕开 venv 没有 pip 的问题）
$ErrorActionPreference = 'Continue'
$log = 'E:\tools\soulx-install2.log'
$root = 'E:\tools\soulx-podcast'
$vpy = Join-Path $root '.venv\Scripts\python.exe'
function Log($m) { ((Get-Date -Format 'HH:mm:ss') + '  ' + $m) | Tee-Object -FilePath $log -Append }

Log 'START'
Log ('venv python exists: ' + (Test-Path $vpy))
Log 'install requirements via uv pip...'
uv pip install --python $vpy -r (Join-Path $root 'requirements.txt') --index-url https://mirrors.aliyun.com/pypi/simple/ 2>&1 | Tee-Object -FilePath $log -Append
Log 'install huggingface_hub...'
uv pip install --python $vpy huggingface_hub --index-url https://mirrors.aliyun.com/pypi/simple/ 2>&1 | Tee-Object -FilePath $log -Append
Log 'check torch:'
& $vpy -c "import torch;print('torch',torch.__version__,'cuda',torch.cuda.is_available())" 2>&1 | Tee-Object -FilePath $log -Append
Log 'download model via hf-mirror...'
$env:HF_ENDPOINT = 'https://hf-mirror.com'
$dst = Join-Path $root 'pretrained_models\SoulX-Podcast-1.7B'
$code = "from huggingface_hub import snapshot_download;snapshot_download('Soul-AILab/SoulX-Podcast-1.7B',local_dir=r'$dst')"
& $vpy -c $code 2>&1 | Tee-Object -FilePath $log -Append
Log 'model files:'
Get-ChildItem $dst -ErrorAction SilentlyContinue | ForEach-Object { $_.Name + '  ' + $_.Length } | Tee-Object -FilePath $log -Append
Log 'DONE'
