> 최신 업데이트: 상단 업무 알림(15초 조회), 관리자 근거 우선 진입, 기술 상세 접기, 중립적인 사건명/번호를 반영했습니다. [사용 안내](docs/WORKFLOW_UPDATE.md) · [발표자 사건 대응표](docs/PRESENTER_CASES.md). 서버 알림함은 아니며, 실제 API가 제공하는 확인된 기록만 알림으로 사용합니다.

# 최신 실행 안내 — API 전용

이 버전은 항상 팀 공식 API에 연결합니다. 연결 설정 버튼, Mock 선택 및 자동 대체 동작을 제거했습니다. 과거 브라우저 설정과 VITE_SERVICE_MODE 값은 무시합니다.

전체 로컬 실행: `py configure_ai.py`로 개인 키를 설정한 뒤 `py start_connected.py --live`를 실행하세요. 이미 백엔드를 별도로 실행 중이면 `py start_frontend.py`로 프론트엔드만 켤 수 있습니다. API 서버가 꺼져 있으면 연결 실패와 재시도 안내가 나타납니다.

API 키는 `chain-of-investigation/.env`에서만 관리하며 Git과 ZIP에 넣지 않습니다. 아래 과거 테스트 결과의 Mock 실행은 당시 버전 또는 테스트 내부 fixture를 의미하며 현재 화면에서 선택할 수 없습니다.

# FullProof — 업무 홈 · 역할별 디자인

현재 백엔드 연결 기준은 `final-mentor-v11 @7998973`입니다. 최종 시연 기준으로 확정된 커밋은 아니며 이후 팀 변경 시 다시 맞춰야 합니다.

## 2026-10-31 화면·동작 업데이트

- 첫 접속 `/`: **업무 시스템 접속** 홈. 수사담당자·원천기관·관리자 선택.
- 역할별 대시보드 `/workspace`, 사건 상세 `/cases/:id`, 이력 `/history`.
- 세 역할 공통 왼쪽 **홈**과 로고로 역할 선택 화면으로 돌아갑니다. 저장된 기록은 유지됩니다.
- 기존 배경색과 Noto Sans KR 글꼴 유지. 수사담당자는 사건철, 원천기관은 노트북, 관리자는 종이와 승인 인장 일러스트.
- 마우스를 올릴 때의 효과는 제거했습니다. 클릭 눌림, 홈 카드 등장, 페이지 전환, 진행 표시, 성공 체크를 적용했습니다.
- 관리자 인장은 **새 ACCEPTED 기록을 재조회하고 기록 상태를 확인한 다음** 표시합니다. 실패·취소·보완 요청·단순 확인에는 표시하지 않습니다. Mock은 ‘가상 승인’으로 명시합니다.
- 운영체제 ‘동작 줄이기’ 설정을 따릅니다. 소리는 없습니다.
- **이번 버전은 로컬 실행용입니다. 공유 서버 배포는 진행하지 않았습니다.**

빠른 디자인 확인: `py start_frontend.py` → `http://127.0.0.1:5173`.
실제 기존 API 실행: 키를 로컬에서 설정한 뒤 `py start_connected.py --live`. `--share` 없이 본인 컴퓨터에서만 실행합니다.

기존 `.env`가 있는 경우 새 폴더의 `chain-of-investigation/.env`로 개인 컴퓨터에서만 복사하세요. API 키는 ZIP·Git에 포함하지 않습니다.

검증 결과와 확인하지 못한 부분: [docs/DESIGN_TEST_RESULTS.md](docs/DESIGN_TEST_RESULTS.md).

## 기존 역할별 기능

- 수사담당자: 사건 업무, Claim 원문 고정·추출, 증빙 연결·검증.
- 원천기관: 증빙 제공 데스크, 기존 초안 서명, 제공 이력.
- 관리자: 검토 대기·보완·종결 가능 건수, 검증 근거, 관리자 확인·종결.
- 역할을 바꾸면 해당 역할의 첫 화면으로 이동합니다. 다른 역할의 업무 메뉴는 표시하지 않습니다.
- ‘현재 일치 판정’을 **‘증빙이 뒷받침하는 검증’**으로 변경했습니다. **최신 검증 기준 · 종결 사건 포함**을 표시합니다. 사건 수와 검증 수를 구분합니다.
- **시연 사건 선택하기**에서 네 가지 사례를 고릅니다. 기본적으로 같은 유형의 진행 사건을 이어 열며, 체크하면 새 회차를 만듭니다.
- 밝은 네이비·화이트와 어두운 배경을 모두 지원합니다. 상태 색상과 로고 원본은 유지합니다.

역할 선택은 시연용 화면 분리입니다. 실제 사용자 로그인·기관별 접근 통제는 구현한 것이 아닙니다. 원천기관 대상 목록도 정식 증빙 요청 API를 가정하지 않고 기존 시연 사건·Proof를 사용합니다.

## 지금 바로 화면 확인

Node.js 22.13 이상, Python 3.12를 권장합니다.

```powershell
py start_frontend.py
```

프론트엔드만 시작합니다. 팀 API 서버를 먼저 실행해야 데이터를 조회할 수 있습니다. 전체 구성은 `py start_connected.py --live`를 사용하세요.

## 다른 사람이 키 없이 실제 API를 사용하는 방법

**이 파일에 API 키를 넣지 않았습니다.** 현재 외부에 배포된 공유 서버도 없습니다. 아래 공유 실행을 먼저 해야 받는 사람이 키 없이 연결할 수 있습니다.

### 1. 서버를 켜는 사람 — 다연이 PC 한 대

기존 `chain-of-investigation/.env`를 이 폴더의 같은 위치에 개인 컴퓨터에서만 복사하거나, 아래를 한 번 실행해 키를 설정합니다.

```powershell
py configure_ai.py
```

모델 설정은 팀에서 실제 확인한 로컬 `.env` 설정을 사용하세요. 이후 같은 네트워크에서 공유 실행:

```powershell
py start_connected.py --live --share
```

서버는 준비가 끝나면 공유 주소를 표시하고, 키가 없는 `shared-demo.json`에 접속 주소만 씁니다. 그 상태에서 별도 PowerShell에서 패키징합니다.

```powershell
py package_project.py
```

생성된 `FullProof_v1.1_Role_Workspace.zip`을 팀원에게 전달하세요. `.env`, 키, DB, 로그, 의존성은 제외됩니다. 서버 PC와 실행 창은 켜둡니다.

주소 자동 감지가 맞지 않으면 PC의 실제 LAN IP로 지정할 수 있습니다:

```powershell
py start_connected.py --live --share --public-url http://192.168.0.10:5173
```

위 IP는 예시입니다. 루프백(127.0.0.1) 주소를 다른 PC에 전달하면 안 됩니다. Windows 방화벽에서 개인 네트워크의 Node.js/5173 접근을 허용해야 할 수 있습니다.

### 2. 파일을 받는 사람 — Gemini 키 설정 없음

같은 네트워크에서 ZIP을 풀고 `fullproof` 폴더에서:

```powershell
py start_shared_client.py
```

주소가 아직 담기지 않은 ZIP이라면 호스트가 알려준 주소를 지정합니다:

```powershell
py start_shared_client.py --server http://192.168.0.10:5173
```

스크립트는 공유 서버를 확인하고 프론트 의존성을 설치한 뒤 **http://127.0.0.1:5173**을 엽니다. 실행 모드를 팀 API 연결로 선택하세요. 백엔드·AI·DB·체인은 호스트 PC 것을 사용합니다. 클라이언트에 Gemini API 키를 입력하거나 백엔드·체인을 별도로 실행하지 않습니다.

브라우저의 해시 계산·지갑 기능은 HTTPS/localhost가 필요하므로, HTTP LAN 주소를 직접 열기보다는 위 클라이언트로 localhost에서 접속합니다. 이미 5173을 사용 중이면 `--port 5174`를 추가합니다.

MetaMask 설치·등록된 테스트 계정 선택은 서명 시 별도로 필요합니다. Gemini 키 없는 연결과 지갑 서명은 다른 단계입니다. 기존 Hardhat 네트워크가 다른 PC를 보고 있다면 MetaMask RPC 주소를 클라이언트의 `http://127.0.0.1:5173/rpc`(포트 변경 시 그 포트)로 맞추세요.

### 범위

이 구성은 **신뢰하는 팀원과 같은 네트워크에서 쓰는 개발 시연**입니다. 인터넷 어디서나 링크 하나로 쓰는 공개 서비스 배포는 아직 하지 않았습니다. 공개 배포는 고정 서버/HTTPS 주소와 API 인증·사용량 제한을 함께 정해야 합니다. 실제 서버 계정·도메인·키를 받지 않은 상태에서 배포했다고 표시하지 않습니다.

## 내 PC에서 전체 로컬 연결만 확인

```powershell
py start_connected.py --fixture
```

고정 AI 추출, 실제 로컬 API/Hardhat, MetaMask 서명으로 실행합니다. 실제 Gemini는:

```powershell
py start_connected.py --live
```

기존 서버는 먼저 Ctrl+C로 종료하세요. 소스 ZIP에는 `.env`가 없으므로 호스트의 실제 키는 로컬에서 설정합니다.

## 문서와 코드

- `docs/ROLE_WORKSPACE.md`: 역할·집계·시연 선택 흐름
- `docs/SHARED_DEMO.md`: 공유 연결 구조·제약
- `docs/DEMO.md`: 변경된 메뉴 기준 시연 순서
- `docs/TEST_RESULTS.md`: 직접 확인한 범위
- `frontend/src/Dashboard.tsx`: 역할별 첫 화면
- `frontend/src/roles.ts`, `session.ts`: 역할별 메뉴·연결
- `frontend/src/App.tsx`: 공통 프레임·사건 업무
- `frontend/src/official.ts`: 공식 API 어댑터
- `frontend/vite.config.ts`: API 프록시·읽기 전용 RPC 프록시
- `start_shared_client.py`: 키 없는 클라이언트 실행
- `chain-of-investigation/`: 공식 백엔드 원본, 수정 없음

## 확인 방법

```powershell
cd frontend
npm.cmd test
npm.cmd run build
```

자동 브라우저 테스트는 `tests/browser_connected.mjs`, `tests/role-visual.mjs`, 공유 클라이언트 확인은 `tests/shared-client.mjs`에 있습니다. 로컬 테스트 실행 준비 사항과 실제 결과는 TEST_RESULTS 문서를 참고하세요.
