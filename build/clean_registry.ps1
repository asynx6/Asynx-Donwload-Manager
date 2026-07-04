Get-ChildItem -Path 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall' | ForEach-Object {
    $n = $_.GetValue('DisplayName')
    if ($n -like '*AsynxDL*') {
        Write-Output $_.Name
        Remove-Item -Path $_.PSPath -Recurse -Force -ErrorAction SilentlyContinue
    }
}
Write-Output 'done'
