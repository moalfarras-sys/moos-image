# Keep personal links that happen to use one of our display names.
param(
  [Parameter(Mandatory)][ValidateSet("Install", "Uninstall")][string]$Mode,
  [Parameter(Mandatory)][string]$Executable,
  [string[]]$Folders = @([Environment]::GetFolderPath("Programs"), [Environment]::GetFolderPath("Desktop"))
)
$ErrorActionPreference = "Stop"
$dest = Split-Path -Parent $Executable
$icon = Join-Path $dest "app.ico"
$ws = New-Object -ComObject WScript.Shell

foreach ($folder in $Folders) {
  $path = Join-Path $folder "Mawj.lnk"
  $link = $ws.CreateShortcut($path)
  if ($Mode -eq "Install") {
    if ((Test-Path -LiteralPath $path) -and ($link.TargetPath -ne $Executable -or $link.Arguments)) {
      Write-Warning "Keeping the existing shortcut at $path."
      continue
    }
    $link.TargetPath = $Executable
    $link.WorkingDirectory = $dest
    $link.IconLocation = if (Test-Path -LiteralPath $icon) { "$icon,0" } else { "$Executable,0" }
    $link.Save()
  }
  $names = @("Mo Remote.lnk", "Mo Remote Personal.lnk")
  if ($Mode -eq "Uninstall") { $names += "Mawj.lnk" }
  foreach ($name in $names) {
    $old = Join-Path $folder $name
    if (Test-Path -LiteralPath $old -PathType Leaf) {
      $entry = $ws.CreateShortcut($old)
      if ($entry.TargetPath -eq $Executable -and -not $entry.Arguments) {
        Remove-Item -LiteralPath $old
      }
    }
  }
}
