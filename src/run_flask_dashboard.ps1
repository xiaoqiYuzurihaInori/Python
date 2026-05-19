$envFile = Join-Path $PSScriptRoot "..\.env"
if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        if ($_ -notmatch '^\s*#' -and $_ -match '=') {
            $key, $value = $_ -split '=', 2
            [System.Environment]::SetEnvironmentVariable($key.Trim(), $value.Trim(), 'Process')
        }
    }
}

$projectRoot = Join-Path $PSScriptRoot ".."
$pythonCandidates = @(
    "D:\Anaconda\python.exe",
    "D:\Anaconda3\python.exe",
    (Get-Command python -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source -ErrorAction SilentlyContinue)
) | Where-Object { $_ -and (Test-Path $_) } | Select-Object -Unique

if (-not $pythonCandidates) {
    throw "未找到可用的 Python 解释器。请先安装 Python，或手动使用 'python flask_app.py' 启动。"
}

$pythonExe = $pythonCandidates[0]

Set-Location $projectRoot
& $pythonExe (Join-Path $projectRoot "flask_app.py")
