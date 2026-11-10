# shot_overlay.ps1
# 全屏框选覆盖层（WPF）。这是绕开「浏览器窗口盖不住屏幕」的唯一办法。
#
# 用法：shot_overlay.ps1 -Image "E:\...\full.png"
# 输出：stdout 打印 "X,Y,W,H"（屏幕坐标，相对整个虚拟桌面）；取消则打印 CANCEL
#
# 原理：先由调用方截好全屏图，这里把图铺在一个无边框、覆盖整个虚拟桌面的 WPF 窗口上，
# 用户在图上拖框，松开就把坐标打出来。窗口关掉后，调用方按坐标裁那张图。

param(
    [Parameter(Mandatory = $true)][string]$Image,
    [string]$Out = '',
    [double]$Dim = 0.45
)

# ---- 自隐藏控制台（关键）----
# 为什么不是用 -WindowStyle Hidden：那会把整个进程的所有窗口都隐藏，包括下面要显示的 WPF 层。
# 这里只精确隐藏「控制台窗口」这一个句柄，WPF 窗口不受影响。
try {
    Add-Type -Name ConHide -Namespace W32 -MemberDefinition @"
[System.Runtime.InteropServices.DllImport("kernel32.dll")] public static extern System.IntPtr GetConsoleWindow();
[System.Runtime.InteropServices.DllImport("user32.dll")] public static extern bool ShowWindow(System.IntPtr hWnd, int nCmdShow);
"@
    $cw = [W32.ConHide]::GetConsoleWindow()
    if ($cw -ne [System.IntPtr]::Zero) { [W32.ConHide]::ShowWindow($cw, 0) | Out-Null }
} catch { }
# ---- 自隐藏控制台结束 ----

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName PresentationFramework, PresentationCore, WindowsBase, System.Windows.Forms

# 虚拟桌面（所有屏拼起来）边界
$vs = [System.Windows.Forms.SystemInformation]::VirtualScreen
$W = $vs.Width
$H = $vs.Height
$OX = $vs.X
$OY = $vs.Y

[xml]$xaml = @"
<Window xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
        xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"
        WindowStyle="None" AllowsTransparency="True" Background="Transparent"
        WindowState="Normal"
        Topmost="True" ShowInTaskbar="False" ResizeMode="NoResize"
        WindowStartupLocation="Manual" Cursor="Cross">
  <Canvas x:Name="Root" Background="#00000000">
    <Image x:Name="Shot" Stretch="Fill" Opacity="0.85" IsHitTestVisible="False"/>
    <Border x:Name="Sel" Visibility="Collapsed" BorderBrush="#FF6AA9FF" BorderThickness="2"
            Background="Transparent">
      <Border.Effect>
        <DropShadowEffect BlurRadius="0" ShadowDepth="0" Color="Black" Opacity="0.55"/>
      </Border.Effect>
    </Border>
    <Border x:Name="Tag" Visibility="Collapsed" Background="White" CornerRadius="3" Padding="6,2">
      <TextBlock x:Name="TagText" Foreground="#FF111111" FontSize="12" FontWeight="SemiBold"
                 FontFamily="Microsoft YaHei UI"/>
    </Border>
    <Border Background="#CC141821" CornerRadius="8" Padding="16,9"
            Canvas.Left="0" Canvas.Top="0" x:Name="Hint">
      <StackPanel Orientation="Horizontal">
        <TextBlock Text="拖一个框，松开就截" Foreground="#FFEDEDF0" FontSize="14"
                   FontFamily="Microsoft YaHei UI"/>
        <TextBlock Text="    Esc 取消" Foreground="#FF8A8A94" FontSize="12"
                   FontFamily="Microsoft YaHei UI" VerticalAlignment="Center"/>
      </StackPanel>
    </Border>
  </Canvas>
</Window>
"@

$reader = New-Object System.Xml.XmlNodeReader $xaml
$win = [Windows.Markup.XamlReader]::Load($reader)

$root = $win.FindName('Root')
$shot = $win.FindName('Shot')
$sel = $win.FindName('Sel')
$tag = $win.FindName('Tag')
$tagText = $win.FindName('TagText')
$hint = $win.FindName('Hint')

# 载入全屏图 —— 用 BitmapFrame.Create(FileStream) 并 Freeze，
# 比 BitmapImage+UriSource 稳（后者在隐藏窗口/无 UI 线程上下文时经常静默失败）
$fs = [System.IO.File]::OpenRead($Image)
try {
    $frame = [System.Windows.Media.Imaging.BitmapFrame]::Create($fs)
    $frame.Freeze()
    $shot.Source = $frame
    [Console]::Error.WriteLine("IMG_OK " + $frame.PixelWidth + "x" + $frame.PixelHeight)
} catch {
    [Console]::Error.WriteLine("IMG_FAIL " + $_.Exception.Message)
} finally {
    $fs.Close()
}
$shot.Width = $W
$shot.Height = $H

# 图不透明地铺满（暗化交给下面那层 Border 的 DropShadow 做）
$shot.Opacity = 1.0

# 提示条居中
$hint.Measure([System.Windows.Size]::new([double]::PositiveInfinity, [double]::PositiveInfinity))
[Windows.Controls.Canvas]::SetLeft($hint, ($W - $hint.DesiredSize.Width) / 2)
[Windows.Controls.Canvas]::SetTop($hint, 24)

$script:down = $false
$script:x0 = 0.0
$script:y0 = 0.0
$script:cur = $null
$script:result = 'CANCEL'

function Set-Sel($x, $y, $w, $h) {
    [Windows.Controls.Canvas]::SetLeft($sel, $x)
    [Windows.Controls.Canvas]::SetTop($sel, $y)
    $sel.Width = $w
    $sel.Height = $h
    $sel.Visibility = 'Visible'
    $tagText.Text = "$([int]$w) x $([int]$h)"
    $tag.Visibility = 'Visible'
    $tag.Measure([System.Windows.Size]::new([double]::PositiveInfinity, [double]::PositiveInfinity))
    $tx = $x
    $ty = $y - $tag.DesiredSize.Height - 6
    if ($ty -lt 0) { $ty = $y + 6 }
    [Windows.Controls.Canvas]::SetLeft($tag, $tx)
    [Windows.Controls.Canvas]::SetTop($tag, $ty)
}

$root.Add_MouseLeftButtonDown({
    $script:down = $true
    $p = $_.GetPosition($root)
    $script:x0 = $p.X
    $script:y0 = $p.Y
    $script:cur = $p
    $sel.Visibility = 'Collapsed'
    $tag.Visibility = 'Collapsed'
})

$root.Add_MouseMove({
    if (-not $script:down) { return }
    $p = $_.GetPosition($root)
    $script:cur = $p
    $x = [Math]::Min($script:x0, $p.X)
    $y = [Math]::Min($script:y0, $p.Y)
    $w = [Math]::Abs($p.X - $script:x0)
    $h = [Math]::Abs($p.Y - $script:y0)
    if ($w -ge 1 -and $h -ge 1) { Set-Sel $x $y $w $h }
})

$root.Add_MouseLeftButtonUp({
    if (-not $script:down) { return }
    $script:down = $false
    $p = $_.GetPosition($root)
    $x = [Math]::Min($script:x0, $p.X)
    $y = [Math]::Min($script:y0, $p.Y)
    $w = [Math]::Abs($p.X - $script:x0)
    $h = [Math]::Abs($p.Y - $script:y0)
    if ($w -lt 6 -or $h -lt 6) { $sel.Visibility = 'Collapsed'; $tag.Visibility = 'Collapsed'; return }
    $script:result = "{0},{1},{2},{3}" -f [int]$x, [int]$y, [int]$w, [int]$h
    $win.Close()
})

$win.Add_KeyDown({
    if ($_.Key -eq [Windows.Input.Key]::Escape) {
        $script:result = 'CANCEL'
        $win.Close()
    }
})

$win.Add_ContentRendered({
    $win.Activate() | Out-Null
    $win.Focus() | Out-Null
})

# 强制铺满整个虚拟桌面（多屏时 Left/Top 可能是负数）
try {
    $win.WindowState = 'Normal'
    $win.Left = $OX
    $win.Top = $OY
    $win.Width = $W
    $win.Height = $H
} catch { }

$win.ShowDialog() | Out-Null

# 结果：优先写文件（execFile 捕获 stdout 会阻塞 GUI），否则打 stdout
if ($Out -ne '') {
    try {
        [System.IO.File]::WriteAllText($Out, $script:result, (New-Object System.Text.UTF8Encoding($false)))
    } catch {
        [Console]::Out.Write($script:result)
    }
} else {
    [Console]::Out.Write($script:result)
}
