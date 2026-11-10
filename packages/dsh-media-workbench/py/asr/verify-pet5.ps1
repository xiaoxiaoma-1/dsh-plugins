$ErrorActionPreference = 'Continue'
$log = 'E:\desktop\shots\pet-verify5.txt'
function W($m) { ("[{0:HH:mm:ss}] {1}" -f (Get-Date), $m) | Out-File $log -Append -Encoding utf8 }

"=== dsh-pet v5 (title / no timer / podcast close) ===" | Out-File $log -Encoding utf8
W "start; waiting 15s"
Start-Sleep -Seconds 15

Get-CimInstance Win32_Process -Filter "Name='pythonw.exe' OR Name='python.exe'" |
  Where-Object { $_.CommandLine -like '*pet.py*' } |
  ForEach-Object { W ("kill pet " + $_.ProcessId); Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Remove-Item "$env:TEMP\dsh-pet.lock" -ErrorAction SilentlyContinue
Start-Sleep -Seconds 1

try {
  $ps = Get-Process -Name 'DeepSeek Harness' -ErrorAction SilentlyContinue
  if ($ps) { W ("kill DSH: " + (($ps | ForEach-Object { $_.Id }) -join ',')); $ps | Stop-Process -Force }
} catch { W ("kill err: " + $_.Exception.Message) }
Start-Sleep -Seconds 4

try { Start-Process -FilePath 'E:\dsh\DeepSeek Harness.exe'; W "DSH launched" }
catch { W ("launch err: " + $_.Exception.Message) }

$ok = $false; $port = $null
for ($i = 0; $i -lt 70; $i++) {
  Start-Sleep -Seconds 2
  $ports = @()
  try {
    $ports = Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue |
      Where-Object { $_.LocalPort -ge 50000 -and $_.LocalPort -le 66000 } |
      Select-Object -ExpandProperty LocalPort -Unique
  } catch { }
  foreach ($p in $ports) {
    try {
      $r = Invoke-WebRequest -Uri "http://127.0.0.1:$p/pet/status" -UseBasicParsing -TimeoutSec 2
      if ($r.StatusCode -eq 200) { $ok = $true; $port = $p; break }
    } catch { }
  }
  if ($ok) { break }
}

if (-not $ok) { W "FAIL: /pet/status never 200" }
else {
  W "OK port $port"
  try { W ("pet/status: " + (Invoke-WebRequest -Uri "http://127.0.0.1:$port/pet/status" -UseBasicParsing -TimeoutSec 5).Content) } catch { }
  try { W ("podcast/state: " + (Invoke-WebRequest -Uri "http://127.0.0.1:$port/podcast/state" -UseBasicParsing -TimeoutSec 5).Content) } catch { }
}

Start-Sleep -Seconds 4
$pet = Get-CimInstance Win32_Process -Filter "Name='pythonw.exe' OR Name='python.exe'" |
  Where-Object { $_.CommandLine -like '*pet.py*' }
if ($pet) {
  foreach ($p in $pet) {
    $par = Get-CimInstance Win32_Process -Filter "ProcessId=$($p.ParentProcessId)"
    W ("pet RUNNING pid=" + $p.ProcessId + " parent=" + $par.Name)
  }
} else { W "FAIL: pet not spawned" }
W "done"
