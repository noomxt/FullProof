# FullProof — 팀 코드 연결 버전

가상의 수사 기록(Claim)과 증빙(Proof)을 비교하고, 기관 지갑의 EIP-712 서명을 팀 컨트랙트에 기록하는 로컬 해커톤 애플리케이션입니다. 실제 경찰 시스템·원천기관에는 연결하지 않습니다.

## 가장 빠른 실행 — Windows / VS Code

Node.js **22.13 이상(24 권장)**, Python **3.10 이상(3.12 권장)**이 필요합니다. 압축을 풀고 **fullproof** 폴더를 VS Code로 여세요. 이전 5173·8000·8545 서버는 각 터미널에서 Ctrl+C로 종료하세요.

Gemini 키를 가지고 있다면 먼저:

```powershell
py configure_ai.py
```

키를 붙여 넣어도 화면에 표시되지 않습니다. 다음 입력에는 AI 팀원이 사용하는 모델명을 넣으세요. 기본값은 예시이며, 계정에서 모델을 사용할 수 있는지는 실제 호출로 확인합니다. 키는 `team-backend/.env`에만 저장됩니다.

이어서:

```powershell
py start_fullproof.py --live
```

처음 실행 시 npm·Python 패키지 설치, 팀 컨트랙트 컴파일, 로컬 Hardhat 시작·배포, 가상 기관 등록, FastAPI 시작, 가상 사건 4건 등록, Vite 시작을 순서대로 수행합니다. 설치에는 인터넷이 필요합니다. 준비되면 **http://127.0.0.1:5173/integration**이 열립니다. 명령 실행 중인 터미널을 켜 두세요. Ctrl+C는 이 실행 도구가 시작한 서버들을 종료합니다.

키 없이 연결 흐름을 점검하려면:

```powershell
py start_fullproof.py --fixture
```

이 모드는 **실제 AI를 호출하지 않고 고정 응답을 사용**합니다. 팀의 파서 응답 검증·규칙 비교·정책 평가·백엔드·SQLite는 실행되며, 지갑으로 서명하면 **로컬 Hardhat에 실제 거래를 생성**합니다. 고정 응답 결과에는 `execution.is_simulated=true`가 붙고 화면에도 표시됩니다. 임의 입력은 지원하지 않고 오류를 반환합니다. Gemini 모드 실패를 고정 응답으로 자동 대체하지 않습니다.

키가 설정된 상태에서 인자 없이 `py start_fullproof.py`를 실행하면 Gemini 모드를 선택합니다. 키가 없으면 고정 응답 모드를 선택하며 터미널과 화면에 실행 방식을 표시합니다. 명확한 시연을 위해 `--live` 또는 `--fixture`를 권장합니다.

## MetaMask 준비와 시연

1. 실행 중 생성된 `.local-run/chain.log`에서 **Account #1**의 로컬 테스트 계정을 확인해 MetaMask로 가져오세요. 공개된 Hardhat 테스트 계정으로 실제 자산을 다루지 않습니다. 앱에는 개인키 입력란이 없습니다.
2. 연결 화면에서 `기록·증빙 일치` 시나리오를 선택합니다.
3. `기관 서명용 분석 초안 생성`을 누릅니다. 고정 응답/Gemini 실행 표시와 항목별 비교를 확인합니다.
4. `지갑 네트워크 연결`로 로컬 네트워크(31337)를 선택하고, 등록 서명자 Account #1을 선택합니다. 백엔드의 기관 주소는 자동으로 채워집니다.
5. `MetaMask 서명 및 저장 요청`을 누르고 서명 내용을 확인합니다. 현재 nonce와 실제 등록 서명자는 자동 조회합니다.
6. `CONFIRMED`·거래 해시·`사건 저장: SAVED`를 확인하고, 사건 이력에서 기록 상세를 다시 조회합니다.
7. 시각 불일치는 확인 필요로 기록됩니다. 증빙 없음과 CCTV 제공만 확인된 사례는 **INSUFFICIENT**로 보류되어 서명 저장이 비활성화됩니다.

일반 분석은 독립 증빙 인증 어댑터가 아직 없으므로 PENDING/INSUFFICIENT가 정상일 수 있습니다. 서명용 초안은 서명 전 내부 비교이고 실제 기관 인증을 의미하지 않습니다. 기관이 서명한 결과의 해시와 이력만 온체인에 남으며, 블록체인이 원본 내용의 진실성을 보증하지 않습니다.

## 화면과 데이터 범위

- `/integration`: 실제 FastAPI·SQLite·로컬 컨트랙트로 연결된 사건 선택, Claim/Proof 비교, 서명·거래 상태, 분석 이력.
- `/`, `/cases/...`, `/claims/...`, `/history`: 최초 요청에 맞춘 **별도의 Mock 프론트엔드 시연**. 여기의 사건은 팀 DB와 다르고 실제 AI/체인 저장을 실행하지 않습니다. 런처는 혼동을 줄이기 위해 `/integration`을 바로 엽니다.
- 모든 사건·원문·기관은 가상입니다. 기관 API는 연결되지 않았습니다.
- 현재 팀 AI 계약의 비교 항목은 대상 ID·행위·시각·결과입니다. 위치 비교 등 원래 Mock 화면의 모든 필드를 실데이터 화면으로 옮긴 상태는 아닙니다.

## 폴더

| 경로 | 역할 |
|---|---|
| `src/pages/` | 기존 4개 Mock 화면 + 팀 연결 워크스페이스 |
| `src/api/team.ts` | 실제 팀 API 호출·오류·등록 서명자 확인·MetaMask 서명 |
| `src/api/mock.ts`, `src/data/` | 최초 프론트엔드 시연 데이터와 서비스 |
| `team-backend/main.py` | 팀 FastAPI·체인 호출·SQLite 사건 |
| `team-backend/ai_engine.py`, `pipeline.py`, `verification.py` | 팀 AI·규칙·정책 로직 |
| `team-backend/ai_provider.py` | Gemini API 어댑터 |
| `team-backend/demo_provider.py`, `demo-scenarios.json` | 명시적인 고정 응답 시연 어댑터·자료 |
| `team-backend/backend_bridge.py` | 분석 초안·동결 데이터 서명·저장·영수증·DB 동기화 |
| `team-backend/local_runtime.py` | 연결 상태·nonce/서명자 조회·로컬 가상 사건 등록 |
| `team-backend/contracts/ChainOfInvestigation.sol` | 변경하지 않은 팀 Solidity 컨트랙트 |
| `team-backend/scripts/compile-local.mjs`, `deploy-local.mjs` | 로컬 컴파일·배포·가상 기관 등록 |
| `configure_ai.py`, `start_fullproof.py` | 로컬 키 설정·통합 실행 |
| `test_connected.py`, `tests/` | 통합·브라우저·프론트엔드 테스트 |
| `docs/` | 실제 API 계약·연동·시연·테스트 결과 |

## 테스트

서버를 종료한 상태에서:

```powershell
npm.cmd ci
npm.cmd test
npm.cmd run build
py -m unittest discover -s tests -p "test_*.py"
cd team-backend
.\.venv\Scripts\python.exe -m unittest discover -p "test_*.py"
cd ..
py test_connected.py
```

실제 브라우저와 로컬 RPC 지갑 어댑터까지 포함하려면:

```powershell
npx.cmd playwright install chromium
py test_connected.py --browser
```

자동 테스트는 고정 응답으로 실행되며 실제 Gemini 사용료를 발생시키지 않습니다. 브라우저 테스트의 지갑은 Hardhat RPC 어댑터입니다. MetaMask 확장 프로그램 자체의 수동 테스트를 대체하지 않습니다. 상세 결과는 [docs/TEST_RESULTS.md](docs/TEST_RESULTS.md)를 참고하세요.

## 주의할 실행 특성

Hardhat은 메모리 체인이므로 종료하면 거래가 사라집니다. SQLite 이력은 남습니다. 다음 실행 때 기존 이력은 현재 체인의 영수증과 대조하여 `STALE_CHAIN`으로 표시되며, 시연 사건 스냅샷은 새 체인에서 다시 준비합니다. 영구 운영 체인이나 전체 장애 복구 기능이 아닙니다.

이 서버는 인증·권한을 갖춘 운영 서비스가 아닙니다. 실행 도구는 서버와 RPC를 127.0.0.1에만 바인딩합니다. 공공기관 연결·공개 운영·테스트넷 배포는 별도 작업입니다. 체크포인트 원본 경로와 새 분석 저장 경로의 통합도 남아 있습니다.

[실행·연동 가이드](docs/INTEGRATION.md) · [실제 API 명세](docs/CONNECTED_API.md) · [시연 순서](docs/DEMO.md)
