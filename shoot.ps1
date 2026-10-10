# mdbeacon-lab / shoot.ps1  ——  按窗口标题截图
# 用法:  pwsh -File shoot.ps1 -Out <绝对路径png> -Title <标题子串>
# 找到标题包含 -Title 的窗口，置顶，按其矩形截图保存为 PNG。
param(
  [Parameter(Mandatory=$true)][string]$Out,
  [string]$Title = "mdbeacon-lab"
)
Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.Windows.Forms
$sig = @"
using System;
using System.Runtime.InteropServices;
using System.Text;
public class WinApi {
  public delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumWindowsProc cb, IntPtr lParam);
  [DllImport("user32.dll", CharSet=CharSet.Auto)] public static extern int GetWindowText(IntPtr hWnd, StringBuilder lpString, int nMaxCount);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT rect);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern void keybd_event(byte bVk, byte bScan, uint dwFlags, IntPtr dwExtraInfo);
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left, Top, Right, Bottom; }
}
"@
Add-Type -TypeDefinition $sig

$found = [IntPtr]::Zero
$cb = [WinApi+EnumWindowsProc]{
  param($h,$l)
  $sb = New-Object Text.StringBuilder 512
  [WinApi]::GetWindowText($h, $sb, 512) | Out-Null
  if ([WinApi]::IsWindowVisible($h) -and $sb.ToString().Contains($Title)) { $script:found = $h; return $false }
  return $true
}
[WinApi]::EnumWindows($cb, [IntPtr]::Zero) | Out-Null

if ($found -eq [IntPtr]::Zero) { Write-Error "no window matching '$Title'"; exit 2 }

# 置顶并稍等渲染
[WinApi]::SetForegroundWindow($found) | Out-Null
Start-Sleep -Milliseconds 250
# ALT 键释放，避免某些情况下窗口无法真正置顶
[WinApi]::keybd_event(0x12, 0, 2, [IntPtr]::Zero) | Out-Null
[WinApi]::SetForegroundWindow($found) | Out-Null
Start-Sleep -Milliseconds 350

$r = New-Object WinApi+RECT
[WinApi]::GetWindowRect($found, [ref]$r) | Out-Null
$w = $r.Right - $r.Left
$ht = $r.Bottom - $r.Top
if ($w -le 0 -or $ht -le 0) { Write-Error "bad rect $w x $ht"; exit 3 }

$bmp = New-Object System.Drawing.Bitmap $w, $ht
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen($r.Left, $r.Top, 0, 0, $bmp.Size)
$bmp.Save($Out, [System.Drawing.Imaging.ImageFormat]::Png)
$g.Dispose(); $bmp.Dispose()
Write-Host "saved $Out ($w x $ht)  hwnd=$found"
