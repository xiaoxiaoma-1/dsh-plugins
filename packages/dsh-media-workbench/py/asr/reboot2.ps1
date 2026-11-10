# Round 2: restart DSH and verify the pet is now spawned BY the plugin, not by a scheduler.
$ErrorActionPreference = 'Continue'
$log = 'E:\desktop\shots\reboot2.txt'
function W($m) { ("[{0:HH:mm:ss}] {1}" -f (Get-Date), $m) | Out-File $log -Append -Encoding utf8 }

"=== round 2: pet must be spawned by plugin ===" | Out-File $log -Encoding utf8
W "start; waiting 22s"
Start-Sleep -Seconds 22

# 1. kill the old pet so the only way it can come back is the plugin spawning it
try {
  $pets = Get-CimInstance Win32_Process -Filter "Name='pythonw.exe' OR Name='python.exe'" |
    Where-Object { $_.CommandLine -like '*dsh-pet*' }
  foreach ($p in $pets) { W ("killing old pet pid " + $p.ProcessId); Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue }
  if (-not $pets) { W "no old pet running" }
} catch { W ("pet kill err: " + $_.Exception.Message) }
Start-Sleep -Seconds 1

# 2. kill DSH
try {
  $ps = Get-Process -Name 'DeepSeek Harness' -ErrorAction SilentlyContinue
  if ($ps) { W ("killing DSH pids: " + (($ps | ForEach-Object { $_.Id }) -join ',')); $ps | Stop-Process -Force }
  else { W "DSH not running" }
} catch { W ("kill err: " + $_.Exception.Message) }
Start-Sleep -Seconds 4

# 3. launch DSH
try { Start-Process -FilePath 'E:\dsh\DeepSeek Harness.exe'; W "DSH launched" }
catch { W ("launch err: " + $_.Exception.Message) }

# 4. poll for the plugin route
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
  W "FAIL: /dsh-bubble/status never 200"
} else {
  W "OK: /dsh-bubble/status 200 on port $port"
  try { W ("body: " + (Invoke-WebRequest -Uri "http://127.0.0.1:$port/dsh-bubble/status" -UseBasicParsing -TimeoutSec 5).Content) } catch { }
  try {
    $r = Invoke-WebRequest -Uri "http://127.0.0.1:$port/podcast/state" -UseBasicParsing -TimeoutSec 5
    W ("podcast/state: " + $r.StatusCode)
  } catch { W ("podcast/state err: " + $_.Exception.Message) }
}

# 5. did the PLUGIN bring the pet back? and who is its parent?
Start-Sleep -Seconds 4
$pet = Get-CimInstance Win32_Process -Filter "Name='pythonw.exe' OR Name='python.exe'" |
  Where-Object { $_.CommandLine -like '*dsh-pet*' }
if ($pet) {
  foreach ($p in $pet) {
    $par = Get-CimInstance Win32_Process -Filter "ProcessId=$($p.ParentProcessId)"
    W ("pet RUNNING pid=" + $p.ProcessId + " parent=" + $par.ProcessId + " (" + $par.Name + ")")
    W ("pet cmdline: " + $p.CommandLine)
  }
} else {
  W "FAIL: pet NOT running (plugin did not spawn it)"
}
W "done"
