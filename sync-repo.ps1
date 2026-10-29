$ErrorActionPreference = "Continue"
$RepoPath = "c:\Users\18897\Desktop\生物实验室管理系统"
$LogFile = Join-Path $RepoPath "sync.log"

function Write-Log($msg) {
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -Path $LogFile -Value "[$ts] $msg" -Encoding UTF8
}

Set-Location $RepoPath
Write-Log "===== sync start ====="

try {
    $pullOut = git pull origin main 2>&1
    Write-Log "git pull: $pullOut"
} catch {
    Write-Log "git pull FAILED: $_"
}

# Stage all tracked/untracked files EXCEPT runtime log
git add -A 2>&1 | Out-Null
git reset HEAD -- sync.log 2>&1 | Out-Null   # don't commit the log itself

$status = git status --porcelain 2>&1
if ($status) {
    Write-Log "detected uncommitted changes, auto add + commit"
    $commitMsg = "auto-sync: save local changes $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
    git commit -m $commitMsg 2>&1 | ForEach-Object { Write-Log "commit: $_" }
} else {
    Write-Log "no local changes to commit"
}

try {
    $pushOut = git push origin main 2>&1
    Write-Log "git push: $pushOut"
} catch {
    Write-Log "git push FAILED: $_"
}

Write-Log "===== sync end ====="