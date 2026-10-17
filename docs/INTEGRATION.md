# 실제 팀 연결 및 실행

이 버전은 팀 FastAPI·AI 모듈·기존 Solidity 컨트랙트를 묶어 로컬 실행 도구를 추가했습니다. 모델이나 블록체인 자체를 새로 구현하지 않았습니다. 컨트랙트 원문은 이전 통합본과 동일합니다.

## 자동 실행

Windows PowerShell에서 fullproof 폴더를 열고:

```powershell
py configure_ai.py
py start_fullproof.py --live
```

키는 숨김 입력이며 `team-backend/.env`에만 저장됩니다. 프론트엔드 환경변수에 키를 넣지 않습니다. 모델명은 AI 담당자에게 확인하세요. 키나 모델이 틀리면 실제 API 오류가 표시되며 시연 응답으로 대체하지 않습니다.

키 없는 통합 점검: `py start_fullproof.py --fixture`. 실제 외부 AI 호출 없이 고정 SDK 응답만 제공하고 팀 파서·비교·정책 로직을 실행합니다. 서명과 로컬 체인 기록은 실제 실행됩니다. 네 가지 원문/Proof 조합 이외에는 명시적으로 실패합니다.

실행 순서는 의존성 설치 → solc-js 컴파일 → Hardhat RPC → 컨트랙트 배포와 가상 기관 등록 → FastAPI → 가상 사건·단계 → Vite입니다. 로그는 `.local-run/`에 있습니다. 5173·8000·8545 중 점유된 포트가 있으면 기존 프로그램을 종료하라는 안내를 표시하며 임의 프로세스를 종료하지 않습니다. 자동 실행은 localhost 전용입니다.

## 수동 실행 / 팀 작업

프론트엔드 (fullproof):

```powershell
npm.cmd ci
npm.cmd run dev
```

체인 (별도 터미널, team-backend):

```powershell
npm.cmd ci
npm.cmd run compile
npm.cmd run node
```

컨트랙트 배포 (별도 터미널, team-backend):

```powershell
npm.cmd run deploy:local
```

`@openzeppelin/contracts`는 5.6.1, solc는 0.8.34로 고정했습니다. 컴파일 EVM 타깃은 OpenZeppelin의 mcopy 사용에 맞춰 Cancun입니다. 팀 원본 컨트랙트는 수정하지 않았습니다. solc-js는 npm으로 설치되므로 Hardhat의 별도 컴파일러 다운로드가 필요하지 않습니다. 기존 register-agencies.ts / anchor-signed-proof.ts / send-op-tx.ts는 참고용 원본이며 새 자동 실행에서는 호출하지 않습니다.

배포는 **로컬 체인 ID 31337에서만** 실행됩니다. 배포 주소·공개 기관/서명자 주소는 `local-demo.json`에, RPC·컨트랙트 주소는 `.env`에 반영합니다. 관리자 계정은 Hardhat #0, 가상 기관 및 서명자는 #1입니다. 배포 스크립트는 개인키를 저장하지 않습니다. 컴파일 결과 및 현재 런타임 해시가 일치하는 기존 배포는 재사용합니다.

백엔드 (별도 터미널, team-backend):

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

이미 배포·키 설정이 끝난 `.env`가 있으면 마지막 Copy-Item 명령을 실행하지 마세요. `.env`를 덮어쓰면 기존 키·주소가 지워집니다. 이후:

```powershell
$env:AI_PROVIDER="gemini"
$env:LOCAL_DEMO="1"
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
```

고정 응답 시연은 AI_PROVIDER를 fixture로 설정합니다. FastAPI 문서: http://127.0.0.1:8000/docs. 루트 주소도 문서로 이동합니다. POST `/api/v1/demo/bootstrap`는 로컬 체인에 시연 사건·정책 단계 4×5개를 준비합니다. 자동 실행은 이 요청까지 수행합니다.

## 프론트엔드 환경변수

기존 Mock 화면은 `VITE_API_MODE=mock`을 유지하세요. 팀 API는 `src/api/team.ts`가 별도로 호출합니다. 주소 변경은 fullproof/.env.local:

```env
VITE_API_MODE=mock
VITE_TEAM_API_URL=http://127.0.0.1:8000
```

Vite를 재시작해야 적용됩니다. 운영 주소가 아직 확정되지 않았으므로 존재하지 않는 API를 가정하지 않았습니다. 다른 프론트엔드 포트를 사용한다면 main.py CORS 허용 목록을 함께 조정해야 합니다.

## 데이터·서명·저장 계약

- 요청의 원문·Proof와 분석 결과를 SQLite에 보존하고 그 **고정된 데이터**로 서명 payload를 생성합니다. 저장 단계에서 AI를 다시 호출하지 않습니다.
- 일반 분석의 Proof 인증은 기본 PENDING입니다. 실제 원천기관 발급 진위를 확인하는 어댑터가 필요합니다. 현재 서명 초안의 내부 VALID는 미서명 비교를 위한 값이며 외부 검증 완료를 의미하지 않습니다.
- 프론트엔드는 기관 ID와 실제 등록 서명자를 구분합니다. 서명 직전에 `/blockchain/agencies/{address}`에서 signer·nonce를 읽습니다.
- INSUFFICIENT를 컨트랙트 VERIFIED/PENDING 등에 임의 매핑하지 않습니다. 일치/불일치 초안만 기관 서명 대상으로 허용합니다. 고정 응답 시연 결과는 체인 31337에만 저장할 수 있습니다.
- 서명 거부·서명 불일치·nonce 재사용은 성공으로 표시하지 않습니다. 요청 응답이 유실되면 저장 상태를 조회하고 자동으로 거래를 재전송하지 않습니다.
- 성공 영수증을 확인한 뒤에도 SQLite 저장이 실패하면 CONFIRMED + case_persistence=FAILED + recovery_required=true를 보존합니다. 상태 조회로 해당 분석의 사건 스냅샷을 다시 저장할 수 있습니다. 전체 DB 복구 기능은 아닙니다.
- 이전 로컬 체인의 이력은 현재 거래 영수증과 블록 해시가 다르거나 사라지면 STALE_CHAIN으로 표시합니다. 영구 보존 체인이 필요한 운영 구조와는 구분합니다.

자동 실행 DB: `team-backend/data/local-cases.db`, `data/local-ai.sqlite3`. 수동 실행 기본 사건 DB: `team-backend/fullproof.db`. 필요하면 CASE_DB_PATH / AI_DB_PATH로 분리하세요. 어떤 경로도 실제 개인정보를 넣지 않습니다.

## 팀원이 이어받을 부분

인증·권한·기관 신원 확인, 독립 Proof 인증, 원본 자료 저장 정책, 장소 등 AI 계약 확장, 체크포인트 경로 통합, 다중 서버·다중 relayer의 nonce/중복 제출 제어, 영구 체인 선택은 후속 설계 대상입니다. 현재 제출 잠금은 단일 Python 프로세스의 로컬 중복 클릭 범위를 다룹니다.

실제 Gemini 호출은 키·모델 설정 후 직접 확인해야 하며, MetaMask 확장 프로그램 승인은 사용자 PC에서 확인해야 합니다. 로컬 자동 테스트의 지갑 RPC 서명과 구분합니다.
