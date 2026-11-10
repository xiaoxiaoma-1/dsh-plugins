@echo off
chcp 65001 >nul
title 截图框选测试

echo 正在截全屏...
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "Add-Type -AssemblyName System.Windows.Forms,System.Drawing; $b=[System.Windows.Forms.SystemInformation]::VirtualScreen; $bmp=New-Object System.Drawing.Bitmap $b.Width,$b.Height; $g=[System.Drawing.Graphics]::FromImage($bmp); $g.CopyFromScreen($b.X,$b.Y,0,0,$bmp.Size); $bmp.Save('%TEMP%\shot_full.png',[System.Drawing.Imaging.ImageFormat]::Png); $g.Dispose(); $bmp.Dispose()"

if not exist "%TEMP%\shot_full.png" (
  echo 截图失败
  pause
  exit /b 1
)

echo.
echo 现在会弹出全屏框选层（两个屏幕都盖住）
echo   - 拖一个框，松开 = 出坐标
echo   - Esc = 取消
echo.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "E:\tools\asr\shot_overlay.ps1" -Image "%TEMP%\shot_full.png"

echo.
echo 上面的输出就是框选结果（X,Y,W,H），CANCEL 表示取消。
echo.
pause
