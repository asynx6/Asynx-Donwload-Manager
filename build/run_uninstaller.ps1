$uninstall = 'C:\Users\asynx\AppData\Local\AsynxDL\unins000.exe'
$p = Start-Process -FilePath $uninstall -ArgumentList '/SILENT /NORESTART /LOG=C:\Users\asynx\Downloads\AsynxDL\dist\uninstall3.log' -PassThru -Wait
Write-Output ('ExitCode=' + $p.ExitCode)
