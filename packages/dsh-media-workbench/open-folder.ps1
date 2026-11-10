param([string]$Path = '')

# 打开文件夹，并强制弹到桌面最前面。
# 背景：DSH 宿主在后台启动 explorer，Windows 的前台锁会把它压到其他窗口后面，
#       用户看到的就是"点了没反应，只在后台"。
# 手法：最小化→恢复 / TOPMOST 切换 / SetForegroundWindow 三轮重试。
# 用法: powershell -NoProfile -ExecutionPolicy Bypass -File open-folder.ps1 -Path "D:\xxx"

Add-Type @"
using System;
using System.Runtime.InteropServices;
public class Win {
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int n);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern bool BringWindowToTop(IntPtr h);
  [DllImport("user32.dll")] public static extern bool IsIconic(IntPtr h);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll")] public static extern bool SetWindowPos(IntPtr h, IntPtr after, int x, int y, int cx, int cy, uint f);
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
}
"@

if ([string]::IsNullOrWhiteSpace($Path)) { Write-Output 'nopath'; exit 1 }
if (-not (Test-Path -LiteralPath $Path)) { Write-Output 'missing'; exit 2 }

$target = 'file:///' + ($Path -replace '\\', '/')

function Find-Window {
  $sh = New-Object -ComObject Shell.Application
  $cands = @()
  foreach ($w in @($sh.Windows())) {
    try {
      if (([string]$w.LocationURL).TrimEnd('/') -eq $target.TrimEnd('/')) { $cands += $w }
    } catch { }
  }
  if ($cands.Count -eq 0) { return $null }
  # 同一路径可能开着好几个，优先挑没最小化、可见的那个
  foreach ($c in $cands) {
    try {
      $hh = [IntPtr]$c.HWND
      if ([Win]::IsWindowVisible($hh) -and -not [Win]::IsIconic($hh)) { return $c }
    } catch { }
  }
  return $cands[0]
}

function Force-Foreground([IntPtr]$h) {
  if ($h -eq [IntPtr]::Zero) { return $false }
  [void][Win]::ShowWindow($h, 5)
  [void][Win]::BringWindowToTop($h)
  if ([Win]::IsIconic($h)) { [void][Win]::ShowWindow($h, 9) }
  if ([Win]::GetForegroundWindow() -eq $h) { return $true }

  $SWP = 0x0001 -bor 0x0002 -bor 0x0040   # NOSIZE | NOMOVE | SHOWWINDOW
  $topmost = [IntPtr](-1)
  $notop = [IntPtr](-2)

  for ($i = 0; $i -lt 3; $i++) {
    if ($i -eq 0) {
      [void][Win]::ShowWindow($h, 6)          # SW_MINIMIZE
      Start-Sleep -Milliseconds 200
      [void][Win]::ShowWindow($h, 9)          # SW_RESTORE
    } elseif ($i -eq 1) {
      [void][Win]::SetWindowPos($h, $topmost, 0, 0, 0, 0, $SWP)
      Start-Sleep -Milliseconds 220
      [void][Win]::SetWindowPos($h, $notop, 0, 0, 0, 0, $SWP)
    } else {
      [void][Win]::BringWindowToTop($h)
      [void][Win]::SetWindowPos($h, $notop, 0, 0, 0, 0, $SWP)
    }
    [void][Win]::SetForegroundWindow($h)
    Start-Sleep -Milliseconds 260
    if ([Win]::GetForegroundWindow() -eq $h) { return $true }
  }
  return $false
}

$w = Find-Window
if ($w) {
  $ok = Force-Foreground ([IntPtr]$w.HWND)
  if ($ok) { Write-Output 'activated' } else { Write-Output 'activated-weak' }
  exit 0
}

# 没有就新开一个，开完再抢前台
Start-Process explorer.exe -ArgumentList ('"' + $Path + '"')
$deadline = (Get-Date).AddSeconds(6)
$hwnd = [IntPtr]::Zero
while ((Get-Date) -lt $deadline) {
  Start-Sleep -Milliseconds 400
  $w = Find-Window
  if ($w) { $hwnd = [IntPtr]$w.HWND; break }
}
if ($hwnd -ne [IntPtr]::Zero) {
  Start-Sleep -Milliseconds 400
  $ok = Force-Foreground $hwnd
  if ($ok) { Write-Output 'opened-front' } else { Write-Output 'opened-back' }
} else {
  Write-Output 'opened-notfound'
}
