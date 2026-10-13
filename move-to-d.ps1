# move-to-d.ps1 - move dev tools from C: to D:\UserData and leave junctions behind.
# Run from the normal desktop PowerShell (NOT the VS Code terminal), with VS Code and Claude Code closed:
#   powershell -ExecutionPolicy Bypass -File D:\Projects\expense-tracker\move-to-d.ps1

$dest = "D:\UserData"

$running = Get-Process -Name "Code","claude","python","pythonw","pip" -ErrorAction SilentlyContinue
if ($running) {
    Write-Host "Close these first, then run again: $(($running.Name | Sort-Object -Unique) -join ', ')" -ForegroundColor Red
    exit 1
}

$items = [ordered]@{
    "$env:USERPROFILE\.local"                       = "$dest\.local"           # Claude Code
    "$env:USERPROFILE\.claude"                      = "$dest\.claude"          # Claude Code settings/history
    "$env:USERPROFILE\.vscode"                      = "$dest\.vscode"          # VS Code extensions
    "$env:LOCALAPPDATA\Programs\Python"             = "$dest\Python"           # Python 3.12
    "$env:LOCALAPPDATA\pip"                         = "$dest\pip"              # pip cache
    "$env:LOCALAPPDATA\Programs\Microsoft VS Code"  = "$dest\Microsoft VS Code" # VS Code app (user install)
}

New-Item -ItemType Directory -Force -Path $dest | Out-Null

foreach ($src in $items.Keys) {
    $dst = $items[$src]
    if (-not (Test-Path -LiteralPath $src)) { Write-Host "skip (not found): $src"; continue }

    $it = Get-Item -LiteralPath $src -Force
    if ($it.Attributes -band [IO.FileAttributes]::ReparsePoint) { Write-Host "skip (already on D): $src"; continue }

    Write-Host "Moving $src -> $dst ..." -ForegroundColor Cyan
    robocopy $src $dst /E /MOVE /COPY:DAT /R:1 /W:1 /NFL /NDL /NJH /NJS /NP | Out-Null
    if ($LASTEXITCODE -ge 8) {
        Write-Host "FAILED moving $src (robocopy code $LASTEXITCODE). Nothing deleted. Stopping." -ForegroundColor Red
        exit 1
    }

    if (Test-Path -LiteralPath $src) {
        $left = Get-ChildItem -LiteralPath $src -Recurse -File -Force -ErrorAction SilentlyContinue
        if ($left) {
            Write-Host "Some files in $src could not be moved (in use?). Stopping; close apps and rerun." -ForegroundColor Red
            exit 1
        }
        Remove-Item -LiteralPath $src -Recurse -Force
    }

    New-Item -ItemType Junction -Path $src -Target $dst | Out-Null
    Write-Host "  done: $src now points to $dst" -ForegroundColor Green
}

$pyMoved = Test-Path "$dest\Python\Python312\python.exe"
Write-Host "`nAll done. Data lives in $dest; old C: paths are links." -ForegroundColor Green
if ($pyMoved) { & "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe" --version }
