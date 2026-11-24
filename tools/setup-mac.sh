#!/bin/bash
# 미니맥 원클릭 세팅 (여러 번 실행해도 안전). 비밀번호·브라우저 허용만 사람이 한다.
# 실행: bash -c "$(curl -fsSL https://raw.githubusercontent.com/ljh769-create/testhomepage/main/tools/setup-mac.sh)"
set -u
REPO="ljh769-create/testhomepage"
DIR="$HOME/hanui"
say() { printf '\n\033[1;36m== %s ==\033[0m\n' "$*"; }

say "1/8 맥 비밀번호를 한 번 입력하세요 (글자가 안 보이는 게 정상)"
sudo -v || exit 1
( while true; do sudo -n true; sleep 50; kill -0 "$$" 2>/dev/null || exit; done ) 2>/dev/null &

say "2/8 Homebrew 설치 (Xcode 도구 포함, 10~20분 걸릴 수 있음)"
if ! command -v brew >/dev/null 2>&1; then
  NONINTERACTIVE=1 /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi
for b in /opt/homebrew/bin/brew /usr/local/bin/brew; do
  [ -x "$b" ] && eval "$("$b" shellenv)" && \
    { grep -q 'brew shellenv' ~/.zprofile 2>/dev/null || echo "eval \"\$($b shellenv)\"" >> ~/.zprofile; }
done
command -v brew >/dev/null || { echo "Homebrew 설치 실패. 이 화면을 캡처해 주세요."; exit 1; }

say "3/8 프로그램 설치 (git, node, python, gh, 크롬, 탈스케일)"
brew install git node python gh
brew install --cask google-chrome tailscale 2>/dev/null || brew install --cask google-chrome tailscale

say "4/8 Claude Code 설치"
command -v claude >/dev/null 2>&1 || curl -fsSL https://claude.ai/install.sh | bash
grep -q '.local/bin' ~/.zprofile 2>/dev/null || echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zprofile
export PATH="$HOME/.local/bin:$PATH"

say "5/8 GitHub 로그인 — 뜨는 브라우저에서 코드 입력 후 '허용'만 누르세요"
gh auth status >/dev/null 2>&1 || gh auth login -h github.com -p https -w
gh auth setup-git
LOGIN="$(gh api user -q .login)"
git config --global user.name "$LOGIN"
git config --global user.email "$LOGIN@users.noreply.github.com"

say "6/8 저장소 내려받기 + 네이버 도구 설치"
[ -d "$DIR/.git" ] && git -C "$DIR" pull --ff-only || gh repo clone "$REPO" "$DIR"
( cd "$DIR/naver-blog" && npm install ) || echo "npm install 실패(나중에 Claude에게 시키세요)"

say "7/8 24시간 서버 설정 (잠자기 끄기·정전 후 자동 켜짐·원격 접속)"
sudo pmset -a sleep 0 displaysleep 10 disksleep 0 autorestart 1 womp 1
sudo systemsetup -setremotelogin on 2>/dev/null || echo "(SSH는 설정 > 일반 > 공유 > 원격 로그인을 직접 켜세요)"
sudo /System/Library/CoreServices/RemoteManagement/ARDAgent.app/Contents/Resources/kickstart \
  -activate -configure -access -on -privs -all -restart -agent >/dev/null 2>&1 \
  || echo "(화면 공유는 설정 > 일반 > 공유 > 화면 공유를 직접 켜세요)"
open -a Tailscale 2>/dev/null

say "8/8 완료 확인"
for c in git node python3 gh claude; do
  printf '%-8s ' "$c"; command -v "$c" >/dev/null && "$c" --version 2>/dev/null | head -1 || echo "없음 ❌"
done
cat <<EOF

✅ 자동 세팅 끝. 남은 사람 할 일 (3가지)
 1) 탈스케일 앱(메뉴바)에서 로그인 → 윈도우 PC에도 같은 계정으로 설치
 2) 터미널에서:  cd ~/hanui && claude   → 처음 한 번 브라우저에서 로그인 허용
    그다음 이렇게 입력:  "naver-blog/SETUP_FOR_AI.md 읽고 네이버 로그인 준비해줘"
 3) 시스템 설정 > 사용자 및 그룹 > 자동 로그인 켜기 (재부팅 대비)
EOF
