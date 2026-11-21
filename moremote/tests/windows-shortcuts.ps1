# Exercise the same WScript shell links that the source and portable installers create.
$ErrorActionPreference = "Stop"
$fixture = Join-Path ([IO.Path]::GetTempPath()) ("mawj-links-" + [guid]::NewGuid())
$folder = New-Item -ItemType Directory -Path $fixture
$exe = Join-Path $fixture "MoRemotePersonal.exe"
$other = Join-Path $fixture "other.exe"
$helper = Join-Path $PSScriptRoot "..\installer\portable\mawj-shortcuts.ps1"
$ws = New-Object -ComObject WScript.Shell
function Save-Link($Name, $Target, $Arguments) {
  $link = $ws.CreateShortcut((Join-Path $fixture $Name))
  $link.TargetPath = $Target
  $link.Arguments = $Arguments
  $link.Save()
}
try {
  New-Item -ItemType File -Path $exe, $other | Out-Null
  Save-Link "Mo Remote.lnk" $exe ""
  Save-Link "Mo Remote Personal.lnk" $exe "--personal"
  & $helper -Mode Install -Executable $exe -Folders @($folder.FullName)
  $new = Join-Path $fixture "Mawj.lnk"
  if ((Test-Path (Join-Path $fixture "Mo Remote.lnk")) -or $ws.CreateShortcut($new).TargetPath -ne $exe) {
    throw "The original shortcut did not migrate to Mawj."
  }
  & $helper -Mode Install -Executable $exe -Folders @($folder.FullName)
  & $helper -Mode Uninstall -Executable $exe -Folders @($folder.FullName)
  if ((Test-Path $new) -or -not (Test-Path (Join-Path $fixture "Mo Remote Personal.lnk"))) {
    throw "Uninstall must remove only the app's unmodified shortcuts."
  }
  Save-Link "Mawj.lnk" $other ""
  Save-Link "Mo Remote.lnk" $exe ""
  & $helper -Mode Install -Executable $exe -Folders @($folder.FullName)
  if ($ws.CreateShortcut($new).TargetPath -ne $other -or -not (Test-Path (Join-Path $fixture "Mo Remote.lnk"))) {
    throw "A personal Mawj shortcut must keep its target and the previous working link."
  }
} finally {
  Remove-Item -LiteralPath $fixture -Recurse -Force
}
Write-Host "Mawj shortcut upgrade, collision and uninstall passed."
