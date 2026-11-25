# 윈도우 PC 쪽 Claude 장기기억을 비공개 저장소 claude-memory 와 맞춘다. 실행: powershell -File tools\sync_memory.ps1
$ErrorActionPreference = "Continue"
$MEM = "$env:USERPROFILE\.claude\projects\c--Users-world-OneDrive-------1122----\memory"
$REPO = "$env:USERPROFILE\.claude-memory-sync"
if (-not (Test-Path "$REPO\.git")) { git clone -q https://github.com/ljh769-create/claude-memory $REPO }
Set-Location $REPO
git pull -q --rebase --autostash 2>$null
Get-ChildItem "$MEM\*.md" | ForEach-Object { $t = Join-Path $REPO $_.Name; if (-not (Test-Path $t) -or $_.LastWriteTime -gt (Get-Item $t).LastWriteTime) { Copy-Item $_.FullName $t -Force } }
Get-ChildItem "$REPO\*.md" | ForEach-Object { $t = Join-Path $MEM $_.Name; if (-not (Test-Path $t) -or $_.LastWriteTime -gt (Get-Item $t).LastWriteTime) { Copy-Item $_.FullName $t -Force } }
git add -A
git diff --cached --quiet; if ($LASTEXITCODE -ne 0) { git commit -q -m "장기기억 동기화(윈도우) $(Get-Date -Format 'MM/dd HH:mm')"; git push -q 2>$null }
"장기기억 동기화 끝: $((Get-ChildItem "$MEM\*.md").Count)개"
