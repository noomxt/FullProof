# 프론트엔드 API 연결

환경 변수는 frontend/.env.example을 참고합니다. 개발 서버는 `/backend`를 백엔드 8000으로 프록시하므로 기존 main.py CORS를 수정하지 않습니다. `VITE_BACKEND_TARGET`으로 대상 주소를 설정합니다. 배포 시에는 호스팅 서버에도 동일한 프록시 또는 정확한 CORS 구성이 필요합니다.

| 작업 | 경로 / 필드 |
|---|---|
| 사건 생성 | POST /api/v1/cases : case_id, title |
| 단계 추가 | POST /api/v1/cases/{case_id}/steps : step_name, is_required |
| Claim | POST /api/v1/cases/{case_id}/claims : claim_id, claim_version, step_id, claim_text |
| 추출 | POST /api/v1/claims/{claim_id}/extract : case_id, claim_version |
| Draft | POST /api/v1/proofs/drafts : proof_content, source_text, 실제 기관 nonce, deadline |
| Anchor | POST /api/v1/proofs/anchor : Draft의 ProofAttestation 필드 + signature |
| 매핑 생성·확정 | 기존 공식 경로, PENDING 생성 후 정확한 확인 메시지 서명 |
| 검증 | POST /api/v1/verifications : claim 참조 객체 + 실제 Proof 목록 |
| 판정 조회 | GET /api/v1/verifications/{verification_id} : 팀 success/data/error 래퍼 |
| 관리자 검토 | POST /api/v1/verifications/{verification_id}/reviews : review_status, reason_code, reason_text, signer_address, signature, nonce, deadline |
| 종결 | POST /api/v1/cases/{case_id}/close : reason, signer_address, signature, nonce, deadline |

기관은 서버 typed_data를 EIP-712로 서명합니다. 매핑은 공식 줄바꿈 메시지, 검토/종결은 공식 JCS JSON을 UTF-8 hex로 바꾸어 MetaMask personal_sign을 호출합니다. 계정과 체인을 서명 전후에 확인합니다. 프론트는 거래를 직접 전송하지 않습니다. 정수형 EIP-712 문자열을 임의로 실수로 바꾸지 않습니다.

원시 JSON과 success/data/error 응답을 모두 처리합니다. `reason_text`는 화면용 이름이고 종결 API에는 `reason`으로 변환해 보냅니다. 쓰기 API의 실제 필드 형식은 docs/fullproof-v1.1-openapi.json에서 확인할 수 있습니다. 이 파일은 받은 main.py에서 직접 추출했습니다.

## 기존 팀 환경 사용

팀이 이미 배포한 실제 ABI와 컨트랙트 주소를 사용하는 경우 자동 로컬 배포 도구 대신 해당 환경을 유지해 실행합니다. chain-of-investigation/.env에 RPC_URL, CONTRACT_ADDRESS, UI_AGENCY_ADDRESS, V11_MAPPING_REVIEWERS, GEMINI_API_KEY를 설정합니다. ABI는 팀 artifact 경로에 있어야 합니다. Python 패키지 설치 후:

```powershell
cd chain-of-investigation
$env:FULLPROOF_UI_AI_MODE="live"
.\.venv\Scripts\python.exe -m uvicorn frontend_server:app --host 127.0.0.1 --port 8000
```

다른 터미널에서 frontend 폴더:

```powershell
npm.cmd ci
npm.cmd run dev
```

`main:app`만 실행하면 아직 보조 조회 경로가 없으므로 전체 화면을 사용할 수 없습니다. 공식 조회 API와 system/status가 통합되면 보조 모듈을 제거하고 main:app으로 전환할 수 있습니다.

## 무결성 확인

Claim 원문의 공백·줄바꿈을 유지해 SHA-256 계산. Proof/Verification/정책/Proof 참조 목록은 공식 필드만 골라 JCS+SHA-256 계산. 전달받은 저장 해시와 실제 로컬 체인에서 조회한 해시·참조·판정을 비교합니다. 조회 불가는 일치가 아닙니다. 이는 서버와 독립적인 별도 RPC 감사나 자료 자체의 사실성을 증명하는 기능이 아닙니다.

미선택 Proof 추가 등으로 종결 조건이 달라지는 경우 화면은 실제 체인의 최신 Verification 및 Proof 이력 개수를 읽어 ‘재검증 필요’로 표시합니다. backend 캐시 반환의 현재 체인 재검증 범위는 TEAM_ALIGNMENT.md의 후속 검토 항목입니다.
