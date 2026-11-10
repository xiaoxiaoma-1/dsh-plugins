# CosyVoice2 第二步：逐包安装（requirements 里的 onnxruntime==1.18.0 在 win 上解析不了，改为按需装）
$ErrorActionPreference = 'Continue'
$log = 'E:\tools\cosy-install2.log'
$root = 'E:\tools\CosyVoice'
$vpy = Join-Path $root '.venv\Scripts\python.exe'
function Log($m) { ((Get-Date -Format 'HH:mm:ss') + '  ' + $m) | Out-File -FilePath $log -Append -Encoding UTF8 }

Log 'START'
Log 'torch 2.3.1 cu121...'
uv pip install --python $vpy torch==2.3.1 torchaudio==2.3.1 --index-url https://download.pytorch.org/whl/cu121 *>&1 | Out-File -FilePath $log -Append -Encoding UTF8

Log 'core deps...'
$pkgs = @(
  'conformer==0.3.2','diffusers==0.29.0','hydra-core==1.3.2','HyperPyYAML==1.2.3','inflect==7.3.1',
  'librosa==0.10.2','lightning==2.2.4','matplotlib==3.7.5','modelscope==1.20.0','networkx==3.1',
  'numpy==1.26.4','omegaconf==2.3.0','onnx==1.16.0','pyworld==0.3.4','rich==13.7.1',
  'soundfile==0.12.1','tensorboard==2.14.0','transformers==4.51.3','x-transformers==2.11.24',
  'uvicorn==0.30.0','fastapi==0.115.6','gdown==5.1.0','gradio==5.4.0','pyarrow==18.1.0',
  'protobuf==4.25','pydantic==2.7.0','openai-whisper==20231117'
)
uv pip install --python $vpy @pkgs --index-url https://mirrors.aliyun.com/pypi/simple/ *>&1 | Out-File -FilePath $log -Append -Encoding UTF8

Log 'onnxruntime (win wheel)...'
uv pip install --python $vpy onnxruntime *>&1 | Out-File -FilePath $log -Append -Encoding UTF8

Log 'verify:'
& $vpy -c "import torch;print('torch',torch.__version__,'cuda',torch.cuda.is_available())" *>&1 | Out-File -FilePath $log -Append -Encoding UTF8
Push-Location $root
& $vpy -c "import sys;sys.path.insert(0,'.');from cosyvoice.cli.cosyvoice import CosyVoice2;print('import ok')" *>&1 | Out-File -FilePath $log -Append -Encoding UTF8
Pop-Location
Log 'DONE'
