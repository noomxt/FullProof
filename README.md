# FullProof v1.1 — final-mentor-v11 프론트 연결본

공식 기준: `noomxt/FullProof`의 `final-mentor-v11`, 커밋 `7998973a84f72e7c96ddb7f295c00e81fb6643d8`.
기존 Team_Aligned 대신 이 버전을 새 폴더에서 사용하세요. 공식 백엔드·AI·컨트랙트 소스는 그대로 사용하고 프론트엔드 요청·응답 처리를 맞췄습니다. GitHub에 자동 푸시하거나 다른 브랜치를 병합하지 않았습니다.

## 실행

Node.js 22.13 이상, Python 3.12를 권장합니다. Windows PowerShell에서 이 README와 `start_connected.py`가 있는 폴더를 여세요.

```powershell
py start_connected.py --fixture
```

처음에는 npm·Python 의존성을 설치하고 컨트랙트를 컴파일·배포합니다. 이후 `http://127.0.0.1:5173`으로 접속하고 **시연 설정 → 팀 API 연결**을 선택하세요. 기존 5173·8000 서버가 실행 중이라면 이전 실행 창에서 Ctrl+C로 종료하세요. 기존 체인·DB를 자동 삭제하지 않습니다.

`--fixture`는 고정 AI 추출을 사용하며 외부 Gemini 요청이 없습니다. 백엔드와 Hardhat 거래는 실제 로컬 실행이고, 화면의 기관·매핑·관리자 서명에는 실제 MetaMask 확장이 필요합니다. 역할 선택은 실제 인증이 아닙니다.

실제 Gemini를 사용하려면 로컬에서만 키를 설정하세요.

```powershell
py configure_ai.py
py start_connected.py --live
```

키는 `chain-of-investigation/.env`의 `GEMINI_API_KEY`에만 저장하며 Git에 올리지 않습니다. AI가 실제로 호출됐는지는 서버 응답·로그로 확인하세요. `--live`의 외부 호출은 이 배포본 제작 과정에서 테스트하지 않았습니다.

프론트만 가상 시연하려면:

```powershell
py start_frontend.py
```

그 후 **프론트엔드 Mock** 모드를 선택하세요. Mock은 가상 서명·판정·저장으로 실제 체인 기록과 분리됩니다.

## 화면 테마

상단의 **다크 모드 / 라이트 모드** 버튼으로 어두운 배경과 흰색 배경을 전환합니다. 선택은 브라우저에 저장되어 새로고침 후에도 유지됩니다. 기본값은 라이트 모드입니다. 로고 원본 색상은 유지합니다.

## 변경 내용

- 지갑·기관·관리자 설정은 `/api/v1/frontend/status`에서 읽습니다.
- 무결성 원문은 `/api/v1/verifications/{id}/integrity-data`에서 받아 브라우저에서 JCS/SHA-256을 다시 계산합니다.
- 검증은 `POST /api/v1/verification-requests`에 공식 Claim 참조·Proof 목록을 전달합니다.
- 처리 중에는 `GET /api/v1/verification-requests/{id}`로 조회하고 서버 완료·실패·상태 불명확을 구분합니다.
- 새로고침 후 사건의 **검증 요청 처리 상태 → 기존 요청 상태 조회**로 이어서 확인합니다. 자동 POST 재시도는 없습니다.
- 결과 다시 조회도 위 상태 API의 실제 완료 `result`를 사용합니다. 이 공식 커밋에는 `GET /api/v1/verifications/{id}`가 없습니다.
- 서버의 기관 EIP-712, 매핑·관리자·종결 personal_sign 및 종결 규칙은 바꾸지 않았습니다.

이전 Team_Aligned의 `frontend_integrity.py`, 장애 진단 코드, 별도 판정 캐시는 사용하지 않습니다. 이 버전의 `mentor_support.py`는 공식 브랜치에 포함된 서버 구현입니다.

## 구조

```text
frontend/src/official.ts             공식 API 어댑터
frontend/src/verificationRequests.ts 요청 저장·진행 조회·복귀
frontend/src/App.tsx                 사건 목록·사건별 업무·처리 상태 화면
frontend/src/signing.ts              공식 메시지 형식
frontend/src/wallet.ts               MetaMask 연결·계정·네트워크 확인
frontend/src/integrity.ts            브라우저 해시 재계산
frontend/tests/                      프론트 테스트
chain-of-investigation/              공식 브랜치 백엔드·AI·컨트랙트
local-tools/                        별도 로컬 실행·배포 도구
start_connected.py                  연결 실행 도구
configure_ai.py                     로컬 키 입력 도구
docs/                               연동·시연·테스트·출처 문서
```

상세 사항은 `docs/FRONTEND_ALIGNMENT.md`, `docs/DEMO.md`, `docs/TEST_RESULTS.md`를 확인하세요.
