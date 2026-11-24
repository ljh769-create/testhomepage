#!/bin/bash
# 맥미니 추가 설치(이 PC와 같은 환경). 실행: bash tools/setup-mac-extras.sh
# Magnific(유료)은 설치하지 않습니다.
set +e
eval "$(/opt/homebrew/bin/brew shellenv)" 2>/dev/null

echo "== 1. VS Code =="
brew install --cask visual-studio-code

echo "== 2. Claude Code (없을 때만) =="
command -v claude >/dev/null || curl -fsSL https://claude.ai/install.sh | bash
export PATH="$HOME/.local/bin:$PATH"

echo "== 3. VS Code 안 Claude Code 확장 =="
code --install-extension anthropic.claude-code 2>/dev/null || \
  "/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code" --install-extension anthropic.claude-code

echo "== 4. 디자인 도구 =="
claude plugin marketplace add pbakaus/impeccable
claude plugin install impeccable@impeccable
claude plugin marketplace add nextlevelbuilder/ui-ux-pro-max-skill
claude plugin install ui-ux-pro-max@ui-ux-pro-max-skill

echo "== 5. 화면 확인·문서 검색 도구 =="
claude mcp add playwright -s user -- npx -y @playwright/mcp@latest
claude mcp add chrome-devtools -s user -- npx -y chrome-devtools-mcp@latest
claude mcp add context7 -s user -- npx -y @upstash/context7-mcp@latest

echo "== 6. 그림 확인용 =="
npm install -g playwright
npx playwright install chromium
pip3 install --user pillow 2>/dev/null || pip3 install --break-system-packages pillow

echo
echo "== 끝 =="
claude mcp list
echo "VS Code를 열고 Claude 창에서 같은 계정으로 로그인하세요."
