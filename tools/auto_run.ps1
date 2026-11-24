# 1시간마다 윈도우 작업 스케줄러가 실행: Claude를 화면 없이 따로 띄워 남은 작업을 이어 하고 배포한다.
# 로그: 바탕 화면\자동작업_기록.txt   잠금: tools\.auto_run.lock (55분 안에 다시 실행되지 않게)
$ErrorActionPreference = "Continue"
$proj = Split-Path -Parent $PSScriptRoot
$log = Join-Path ([Environment]::GetFolderPath("Desktop")) "자동작업_기록.txt"
$lock = Join-Path $PSScriptRoot ".auto_run.lock"
function Log($m) { Add-Content -Path $log -Value ("[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm"), $m) -Encoding utf8 }

if ((Test-Path $lock) -and ((Get-Date) - (Get-Item $lock).LastWriteTime).TotalMinutes -lt 55) { Log "이전 자동 작업이 아직 진행 중이라 건너뜀"; exit 0 }
Set-Content -Path $lock -Value (Get-Date) -Encoding utf8

$claude = Get-ChildItem "$env:USERPROFILE\.vscode\extensions" -Directory -Filter 'anthropic.claude-code-*' -ErrorAction SilentlyContinue |
  Sort-Object LastWriteTime -Descending | ForEach-Object { Join-Path $_.FullName 'resources\native-binary\claude.exe' } | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $claude) { $claude = "$env:USERPROFILE\.local\bin\claude.exe" }
if (-not (Test-Path $claude)) { Log "Claude 실행 파일을 찾지 못함"; Remove-Item $lock -Force; exit 1 }

# 한글 지시문을 명령줄로 넘기면 PowerShell 5.1 에서 글자가 깨지므로, 지시문은 tools/auto_prompt.md 에 두고 영어(ASCII)로 그 파일을 읽으라고만 전달한다.
$prompt = 'Read tools/auto_prompt.md (UTF-8, Korean) in this project and carry out every step in it exactly. Reply in Korean.'

Set-Location $proj
Log "자동 작업 시작"
try {
  $out = & $claude -p $prompt --model opus 2>&1 | Out-String
  $last = ($out -split "`n" | Where-Object { $_.Trim() } | Select-Object -Last 3) -join " / "
  Log ("끝: " + $last)
} catch { Log ("오류: " + $_.Exception.Message) }
Remove-Item $lock -Force -ErrorAction SilentlyContinue
