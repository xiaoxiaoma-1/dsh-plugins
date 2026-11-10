# ClipWatch: poll the Windows clipboard and emit one line per change.
# ASCII only on purpose - Windows PowerShell 5.1 misreads UTF-8 .ps1 without BOM.
$ErrorActionPreference = 'SilentlyContinue'
Add-Type -AssemblyName System.Windows.Forms | Out-Null
$last = [string]::Empty
while ($true) {
    try {
        $c = Get-Clipboard -Raw
        if ($null -ne $c) {
            $c = [string]$c
            if ($c -ne $last) {
                $last = $c
                $one = $c -replace "`r", ' ' -replace "`n", ' '
                if ($one.Length -gt 4000) { $one = $one.Substring(0, 4000) }
                [Console]::Out.WriteLine($one)
                [Console]::Out.Flush()
            }
        }
    } catch { }
    Start-Sleep -Milliseconds 700
}
