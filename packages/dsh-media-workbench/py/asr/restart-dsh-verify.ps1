# Restart DSH, verify plugin routes, relaunch desktop pet.
# Detached: survives the death of its parent.
$ErrorActionPreference = 'Continue'
$log = 'E:\desktop\shots\reboot-verify.txt'
function W($m) { ("[{0:HH:mm:ss}] {1}" -f (Get-Date), $m) | Out-File $log -Append -Encoding utf8 }

"=== DSH restart verification ===" | Out-File $log -Encoding utf8
W "start; waiting 25s so the chat reply goes out first"
Start-Sleep -Seconds 25

$dshExe = 'E:\dsh\DeepSeek Harness.exe'
$py = 'C:\Users\Administrator\AppData\Local\Programs\Python\Python312\python.exe'
$pet = 'E:\tools\asr\dsh-pet.py'

# 1. kill DSH
try {
  $ps = Get-Process -Name 'DeepSeek Harness' -ErrorAction SilentlyContinue
  if ($ps) { W ("killing DSH pids: " + (($ps | ForEach-Object { $_.Id }) -join ',')); $ps | Stop-Process -Force }
  else { W "DSH not running" }
} catch { W ("kill err: " + $_.Exception.Message) }
Start-Sleep -Seconds 3

# 2. launch DSH
try { Start-Process -FilePath $dshExe; W "DSH launched" } catch { W ("launch err: " + $_.Exception.Message) }

# 3. poll for /dsh-bubble/status == 200
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
      $r = Invoke-WebRequest -Uri "http://127.0.0.1:$p/dsh-bubble/status" -UseBasicParsing -TimeoutSec 2
      if ($r.StatusCode -eq 200) { $ok = $true; $port = $p; break }
    } catch { }
  }
  if ($ok) { break }
}

if (-not $ok) {
  W "FAIL: /dsh-bubble/status never returned 200 in 140s (plugin not loaded?)"
} else {
  W "OK: /dsh-bubble/status 200 on port $port"
  try {
    $r = Invoke-WebRequest -Uri "http://127.0.0.1:$port/dsh-bubble/status" -UseBasicParsing -TimeoutSec 5
    W ("body: " + $r.Content)
  } catch { W ("status body err: " + $_.Exception.Message) }

  # 4. push test
  try {
    $r = Invoke-WebRequest -Uri "http://127.0.0.1:$port/dsh-bubble/push" -Method POST -Body '{"id":"selftest","title":"self test","pct":50}' -ContentType 'application/json' -UseBasicParsing -TimeoutSec 5
    W ("push: " + $r.StatusCode + " " + $r.Content)
  } catch { W ("push err: " + $_.Exception.Message) }

  # 5. podcast state route
  try {
    $r = Invoke-WebRequest -Uri "http://127.0.0.1:$port/podcast/state" -UseBasicParsing -TimeoutSec 5
    W ("podcast/state: " + $r.StatusCode + " " + $r.Content)
  } catch { W ("podcast/state err: " + $_.Exception.Message) }

  # 6. podcast ctl route (POST)
  try {
    $r = Invoke-WebRequest -Uri "http://127.0.0.1:$port/podcast/ctl" -Method POST -Body '{"action":"pause"}' -ContentType 'application/json' -UseBasicParsing -TimeoutSec 5
    W ("podcast/ctl: " + $r.StatusCode + " " + $r.Content)
  } catch { W ("podcast/ctl err: " + $_.Exception.Message) }

  # 7. shot/latest
  try {
    $r = Invoke-WebRequest -Uri "http://127.0.0.1:$port/shot/latest" -UseBasicParsing -TimeoutSec 5
    W ("shot/latest: " + $r.StatusCode + " " + $r.Content)
  } catch { W ("shot/latest err: " + $_.Exception.Message) }
}

# 8. relaunch desktop pet (old one died with DSH)
try {
  Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -like '*dsh-pet*' } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
  Start-Sleep -Milliseconds 800
  Start-Process -FilePath $py -ArgumentList $pet -WindowStyle Hidden
  Start-Sleep -Seconds 3
  $found = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -like '*dsh-pet*' }
  if ($found) { W ("pet running pid " + (($found | ForEach-Object { $_.ProcessId }) -join ',')) }
  else { W "FAIL: pet not running" }
} catch { W ("pet err: " + $_.Exception.Message) }

W "done"
