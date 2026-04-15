# chatty

[![npm](https://img.shields.io/npm/v/@namjookim/chatty)](https://www.npmjs.com/package/@namjookim/chatty)
[![node](https://img.shields.io/node/v/@namjookim/chatty)](https://nodejs.org)
[![license](https://img.shields.io/github/license/namjoo-kim-gachon/chatty)](LICENSE)

터미널 실시간 채팅 — React/Ink 기반 TUI + CLI 원격 제어

```
┌─ #lobby ──────────────────────────────────────────────────┐
│ alice   안녕하세요!                                         │
│ bob     반갑습니다 :)                                       │
│ alice   오늘 날씨 좋네요                                    │
├───────────────────────────────────────────────────────────┤
│ > _                                                       │
└───────────────────────────────────────────────────────────┘
```

## Features

- **멀티룸 채팅** — 공개/비공개/비밀번호 방, 룸 번호(#1, #2…)로 빠르게 이동
- **Google OAuth** — 계정 생성 없이 Google 로그인
- **실시간 스트리밍** — SSE(Server-Sent Events) 기반 즉시 전달
- **모더레이션** — 슬로우모드, 뮤트, 밴, 단어 필터, 신고
- **chatty-cli** — 실행 중인 TUI를 외부 프로세스/스크립트에서 원격 제어
- **Claude Code 연동** — chatty 스킬로 Claude가 채팅 룸을 직접 읽고 씀
- **멀티언어** — 시스템 로케일 자동 감지

---

## Quick Start

퍼블릭 서버(chatty.1000.school)에 바로 접속할 수 있습니다.

```bash
npm install -g @namjookim/chatty
chatty
```

최초 실행 시 브라우저가 열리고 Google 로그인 → 완료되면 채팅 시작.

---

## 설치 및 명령어

```bash
# 전역 설치
npm install -g @namjookim/chatty

# TUI 실행
chatty

# 로그인만 별도 실행
chatty login

# 닉네임 변경
chatty nickname
```

---

## TUI 키보드 단축키

| 키 | 동작 |
|----|------|
| `Ctrl+R` / `Ctrl+Shift+R` | 다음 / 이전 룸으로 전환 |
| `PageUp` / `PageDown` | 메시지 스크롤 |
| `End` | 최신 메시지로 이동 |
| `Ctrl+C` | 종료 |

---

## 슬래시 명령어 (TUI 내)

| 명령어 | 설명 |
|--------|------|
| `/who` | 현재 룸 접속자 목록 |
| `/join <번호>` | 룸 입장 |
| `/leave` | 현재 룸 나가기 |
| `/create <이름>` | 새 룸 생성 |
| `/me <동작>` | 액션 메시지 (`* alice 웃는다`) |
| `/topic [텍스트]` | 공지 보기 / 설정 |
| `/pass <닉네임>` | 룸 소유권 양도 |
| `/mute <닉네임>` | 유저 뮤트 (방장 전용) |
| `/unmute <닉네임>` | 뮤트 해제 (방장 전용) |
| `/ban <닉네임>` | 유저 밴 (방장 전용) |
| `/unban <닉네임>` | 밴 해제 (방장 전용) |
| `/quit` | TUI 종료 |

---

## chatty-cli

실행 중인 TUI 인스턴스를 TCP 소켓(기본 포트 7800)으로 제어합니다.  
스크립트, 자동화, Claude Code 연동 등에 활용할 수 있습니다.

```bash
# 현재 상태 확인
chatty-cli status

# 룸 목록 / 검색
chatty-cli rooms list
chatty-cli rooms list --query "game"

# 룸 입장 / 나가기
chatty-cli rooms join 3
chatty-cli rooms leave

# 룸 생성
chatty-cli rooms create --name "새 방" --description "설명" --max-members 50

# 메시지 읽기 / 보내기
chatty-cli messages list --limit 20
chatty-cli messages send "안녕하세요"

# 유저 목록 / 모더레이션
chatty-cli users list
chatty-cli users mute <닉네임>
chatty-cli users ban <닉네임>

# 사람이 읽기 편한 출력
chatty-cli --pretty rooms list
```

포트 변경: `CHATTY_SOCKET_PORT=7801 chatty-cli status`

---

## 설정

첫 실행 시 `~/.config/chatty/config.json`이 자동 생성됩니다.

```json
{
  "server_url": "https://chatty.1000.school",
  "theme": "default",
  "locale": "ko",
  "keybindings": {
    "scroll_up": "pageup",
    "scroll_down": "pagedown",
    "scroll_bottom": "end"
  },
  "reconnect": {
    "max_attempts": 10,
    "base_delay_ms": 1000,
    "max_delay_ms": 30000
  }
}
```

| 환경변수 | 설명 | 기본값 |
|----------|------|--------|
| `CHATTY_SERVER_URL` | 서버 주소 | `https://chatty.1000.school` |
| `CHATTY_CONFIG` | 설정 파일 경로 | `~/.config/chatty/config.json` |
| `CHATTY_SOCKET_PORT` | CLI 소켓 포트 | `7800` |

---

## Self-hosting

직접 서버를 운영하려면 아래 절차를 따르세요.

### 요구사항

- Python 3.12+, [uv](https://docs.astral.sh/uv/)
- PostgreSQL
- Redis

### 서버 실행

```bash
git clone https://github.com/namjoo-kim-gachon/chatty.git
cd chatty

# 환경변수 설정
cp .env.example .env
# .env 파일 편집

# 서버 실행
uv run uvicorn app.main:app --port 7799 --app-dir apps/server
```

### `.env` 주요 항목

| 변수 | 설명 |
|------|------|
| `CHATTY_DATABASE_URL` | PostgreSQL 연결 문자열 |
| `CHATTY_REDIS_URL` | Redis URL |
| `CHATTY_SECRET_KEY` | JWT 서명 키 (운영 환경에서 반드시 변경) |
| `CHATTY_GOOGLE_CLIENT_ID` | Google OAuth 클라이언트 ID |
| `CHATTY_GOOGLE_CLIENT_SECRET` | Google OAuth 시크릿 |
| `CHATTY_BASE_URL` | OAuth 리다이렉트 기준 URL (예: `https://your-domain.com`) |

Google OAuth 자격증명은 [Google Cloud Console](https://console.cloud.google.com/)에서 발급받으세요.  
리다이렉트 URI: `{CHATTY_BASE_URL}/auth/google/callback`

### 클라이언트에서 자체 서버 연결

```bash
CHATTY_SERVER_URL=http://localhost:7799 chatty
```

또는 `~/.config/chatty/config.json`의 `server_url`을 변경하세요.

---

## 개발

```bash
# 의존성 설치
cd apps/client && npm install

# TUI 개발 서버
npm run dev

# 서버 개발 서버
cd /path/to/chatty
uv run uvicorn app.main:app --reload --port 7799 --app-dir apps/server

# 테스트
uv run pytest apps/server/tests/ -v   # 서버
npm test --workspace apps/client       # 클라이언트
```

---

## License

MIT
