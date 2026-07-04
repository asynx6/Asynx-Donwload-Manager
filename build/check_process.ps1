$p = Get-Process -Name 'AsynxDL' -ErrorAction SilentlyContinue
if ($p) {
    Write-Output 'RUNNING'
} else {
    Write-Output 'NOT_RUNNING'
}
