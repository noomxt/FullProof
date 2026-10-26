# FullProof v1.1 · 팀 수정본 기준 프론트엔드 연동

이번 버전은 받은 두 ZIP을 기준으로 구성했습니다.

- 백엔드·블록체인: `fix/v1.1-legacy-cleanup`
- AI: `fix/ai-legacy-cleanup-v1.1`의 AI 담당 변경 파일과 시연 자료
- 프론트엔드: 새 로고·사건별 업무 탭·MetaMask 서명·해시 재계산 화면

**main.py·database.py·컨트랙트는 백엔드 ZIP 그대로입니다.** 우리 쪽 별도 검증 작업 서버(`mentor_support.py`)와 `/verification-requests` 구현은 포함하지 않았습니다. 검증 실행·완료 요청 중복 방지·결과 조회는 팀 API를 사용합니다. 파일 출처와 대조 결과는 `docs/SOURCE_MANIFEST.json`에 있습니다. 아직 팀 공식 브랜치에 푸시하거나 병합하지 않았습니다.

## 먼저 확인할 사항

팀원이 로컬 구현했다고 알려준 `/api/v1/system/status`는 이번 백엔드 ZIP에 없습니다. 프론트엔드는 공식 경로를 먼저 요청하고 **404인 경우에만 읽기 전용 `/api/v1/frontend/status`를 사용**합니다. 실제 공식 응답 규격이 다르면 임의로 변환하지 않고 오류로 알립니다.

팀 백엔드의 완료 응답 재시도·프로세스 재시작 중복 방지 테스트는 통과했습니다. 다만 **거래 성공 뒤 응답이 유실되고 다시 요청하는 경우**는 추가 진단에서 중복 기록이 재현됐습니다. 프론트엔드는 이때 자동 재전송을 막지만, 백엔드 자체의 해당 장애 구간 처리는 팀과 협의해야 합니다. 정상 시연 흐름의 성공과 이 한계를 구분하세요. 자세한 내용은 `docs/TEAM_ALIGNMENT.md`입니다.

## 실행

이전 실행을 Ctrl+C로 종료하고 **새 폴더에 압축을 풀어** README와 실행 파일이 있는 `fullproof` 폴더에서 실행합니다. 기존 DB·실제 .env를 ZIP에 포함하지 않았습니다.

화면만 실행 (지갑·키·백엔드 불필요):

```powershell
py start_frontend.py
```

팀 API·실제 로컬 체인 실행 (AI 추출만 고정 응답):

```powershell
py start_connected.py --fixture
```

http://127.0.0.1:5173 에서 오른쪽 위 **시연 설정 → 팀 API 연결**을 선택합니다. 이전 Mock 선택이 브라우저에 저장돼 있을 수 있습니다. Python 3.12 이상·Node.js 22.13 이상을 권장하며, 직접 검증한 환경은 Linux / Python 3.12 / Node 24입니다. Windows 실행은 미검증입니다.

Gemini 실제 호출:

```powershell
py configure_ai.py
py start_connected.py --live
```

키는 비공개 입력으로 `chain-of-investigation/.env`에만 저장됩니다. `.env`·개인키는 Git에 올리지 않습니다. 이번 테스트에서는 실제 Gemini를 호출하지 않았습니다.

실행 파일은 의존성 설치 → 팀 컨트랙트 컴파일·로컬 배포 → 기관·기록자 등록 → 백엔드와 Vite 실행을 수행합니다. 로그는 `.local-run/chain.log`, `backend.log`, `frontend.log`입니다. 종료는 실행한 터미널에서 Ctrl+C입니다. 다른 프로그램이 8000/5173을 사용 중이면 먼저 종료해야 합니다. 체인·DB를 자동 삭제하거나 복구하지 않습니다.

## MetaMask

MetaMask를 설치한 브라우저에서 접속합니다. 화면 역할 변경과 지갑 계정 변경은 별도입니다. 로컬 네트워크는 체인 ID 31337입니다.

| 단계 | 기본 로컬 계정 | 방식 |
|---|---|---|
| 기관 Proof | Hardhat 계정 1 (`0x7099…79C8`) | EIP-712 |
| 매핑 확정 | Hardhat 계정 0 (`0xf39F…2266`) | personal_sign |
| 관리자 검토·종결 | Hardhat 계정 0 | JCS + personal_sign |

로컬 테스트 계정은 chain.log에서 확인해 MetaMask로 가져옵니다. 테스트 계정에 실제 자산을 넣지 않습니다. 지갑 서명은 프론트에서, 거래 전송·권한 검사·판정·종결 조건은 팀 백엔드/컨트랙트에서 처리합니다. 서명 전후 계정·체인 변경도 확인합니다.

## 시연 순서

1. 사건 목록 → 새 시연 사건 → 정상 일치 선택 → 생성
2. 사건 개요 → 수사 기록 → 원문 등록·고정 → 구조화 실행
3. 기관 증빙·연결 → 원천기관 역할·기관 지갑 → Proof 초안 → 서명·저장
4. 수사 담당자 역할·확인자 지갑 → 통화 후보 선택 → 매핑 서명 확정
5. 증빙 비교·검증 → 검증 실행 → 판정·거래 상태 확인
6. ‘백엔드 판정 결과 다시 조회’로 팀 GET API 확인
7. ‘해시 재계산 및 온체인 대조’로 브라우저의 재계산 결과 확인
8. 관리자 역할·관리자 지갑 → 결과 확인(승인 아님) → 단계 완료 승인
9. 조건 충족 후 종결 사유 입력·서명 → 종결 확인 → 이력 조회

불일치·증빙 부족 사례도 동일하게 확인합니다. 증빙 부족은 Proof·매핑 없이 검증할 수 있습니다. 연결 불명확 사례는 CALL_REF가 없는 음성 사례입니다. 불일치·근거 부족은 승인·종결할 수 없습니다. 모든 자료는 합성이며 실제 수사 시스템과 연결하지 않습니다. 통화 자료 제공·발신 기록을 다른 수사행위나 영상 열람의 이행으로 확대 판정하지 않습니다.

## 구조

```text
frontend/
  src/official.ts          팀 API 요청·응답 변환 / 불명확한 요청 재전송 차단
  src/wallet.ts            MetaMask 계정·체인 확인 및 서명
  src/signing.ts           공식 메시지 형식
  src/integrity.ts         브라우저 JCS·SHA-256 재계산
  src/App.tsx              사건 목록·사건별 업무 탭
  src/AdminReview.tsx      관리자 검토·종결 화면
  src/mock.ts              브라우저 Mock (실제 호출 없음)
chain-of-investigation/
  main.py                  팀 백엔드 원본
  contracts/               팀 컨트랙트 원본
  frontend_server.py       추가 조회·공개 설정·성공 응답 보조 이력
  frontend_integrity.py    원문·체인 조회 전용 함수
local-tools/               별도 로컬 실행 도구
start_connected.py         로컬 연결 실행
start_frontend.py          화면만 실행
docs/                     비교표·명세·테스트·파일 출처
```

단일 로컬 시연 프로세스입니다. 역할 선택은 인증이 아니며 API에 가짜 인증 토큰을 보내지 않습니다. 서비스 배포·다중 서버·실제 기관 인증·전체 DB 복구를 완성한 버전은 아닙니다.

## 테스트

이번 합본의 팀 회귀 테스트 **119개**, 프론트 테스트 **38개**, TypeScript·Vite 빌드를 확인했습니다. 전 버전의 133개와는 테스트 구성이 다릅니다. 팀 AI/백엔드 테스트를 기준으로 실행했으며, 별도 멘토 작업 서버 테스트는 제외했습니다.

브라우저 테스트는 실제 로컬 API·Hardhat과 주입 EIP-1193 테스트 지갑·고정 추출 응답을 사용합니다. 실제 MetaMask 확장·외부 Gemini·사용자 Windows 환경 검증은 남아 있습니다. 상세 결과는 `docs/TEST_RESULTS.md`를 확인하세요.
