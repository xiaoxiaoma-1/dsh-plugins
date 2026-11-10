# SoulX 第三步：绕开 triton（Windows 没有 wheel），torch 走官方 CUDA 源，其余走阿里云
$ErrorActionPreference = 'Continue'
$log = 'E:\tools\soulx-install3.log'
$root = 'E:\tools\soulx-podcast'
$vpy = Join-Path $root '.venv\Scripts\python.exe'
function Log($m) { ((Get-Date -Format 'HH:mm:ss') + '  ' + $m) | Tee-Object -FilePath $log -Append }

Log 'START'
Log 'torch 2.7.1 + torchaudio (CUDA 126)...'
uv pip install --python $vpy torch==2.7.1 torchaudio==2.7.1 --index-url https://download.pytorch.org/whl/cu126 2>&1 | Tee-Object -FilePath $log -Append

Log 'rest deps (no triton)...'
uv pip install --python $vpy librosa numpy scipy s3tokenizer diffusers transformers==4.57.1 accelerate==1.10.1 onnxruntime onnxruntime-gpu einops gradio --index-url https://mirrors.aliyun.com/pypi/simple/ 2>&1 | Tee-Object -FilePath $log -Append

Log 'verify:'
& $vpy -c "import torch;print('torch',torch.__version__,'cuda',torch.cuda.is_available(),torch.cuda.get_device_name(0) if torch.cuda.is_available() else '')" 2>&1 | Tee-Object -FilePath $log -Append
& $vpy -c "import librosa,diffusers,transformers;print('libs ok',transformers.__version__)" 2>&1 | Tee-Object -FilePath $log -Append
Log 'DONE'
