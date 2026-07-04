$setup = 'C:\Users\asynx\Downloads\AsynxDL\dist\AsynxDL_Setup_v1.0.0.exe'
$p = Start-Process -FilePath $setup -ArgumentList '/SP- /SILENT /NORESTART /LOG=C:\Users\asynx\Downloads\AsynxDL\dist\install_test.log' -PassThru -Wait
Write-Output ('ExitCode=' + $p.ExitCode)
