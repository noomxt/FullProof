# AI Verification ↔ 최신 백엔드 시험 통합

기준 커밋: feature/integration-v1.1의 c45fdeb.
시험 브랜치: test/ai-verification-integration-v1.1.
공식 통합 브랜치와 기존 AI 브랜치는 이 작업에서 변경하지 않습니다.

## 변경 범위

- 기존 Claim 등록 성공 후 원문·해시·버전을 cases_db의 v11_claims에 저장합니다.
  기존 save_case/load_cases JSON 저장 기능을 사용하며 database.py는 수정하지 않았습니다.
- POST /api/v1/claims/{claim_id}/extract를 추가했습니다. body는 case_id, claim_version입니다.
  온체인 최신 Claim 검증 전후로 서버에서 추출하고, 원본 버전에 결과를 저장합니다.
- POST /api/v1/verifications는 서버에 저장된 Claim/추출과 기관 서명·Anchor가 끝난
  Draft만 사용합니다. 요청자의 structured_claim을 신뢰하지 않습니다.
- 기존 process_v11_verification/anchor_v11_verification 흐름으로 실제 판정과 해시를 기록합니다.
- 기존 기관 EIP-712·담당자 매핑 확인 서명 기능을 그대로 사용하고, 판정 직전에
  담당자 서명·기관 원본·정확한 통화 참조를 재검증합니다.
- 최신 AI 모듈과 회귀 테스트를 AI 브랜치에서 가져왔습니다.
- 누락된 OpenZeppelin 컨트랙트 의존성과 Python 의존성, 재현용 잠금 파일을 보완했습니다.

## 매핑 근거를 인정하는 좁은 MVP 조건

CONFIRMED라는 상태나 설명문만으로 mapping_evidence_sufficient를 True로 하지 않습니다.
mapping_evidence.py에서 아래 조건을 모두 확인합니다.

1. 서버 매핑의 Claim/Proof ID·버전·해시·기관·통화 ID가 정확히 일치.
2. 변경되지 않은 Claim 원문에 CALL_REF[기관ID:통화ID] 참조가 명시되어 있음.
3. 기관 원본 UTF-8 JSON에 issuer_agency_id, call_id, target_id, action_type,
   proof_occurred_at이 있고, 서명된 Proof의 동일 필드와 정확히 일치.
4. 원본 바이트 SHA-256이 서명된 source_sha256과 일치.
5. 저장된 확인 메시지의 서명을 다시 복구하고 허용된 담당자 및 확인자와 대조.

예: `P001과 통화 연결에 성공했다. CALL_REF[TELECOM-001:CALL-001]`.
이 참조는 담당자가 원문을 입력할 때 포함한 값이며 AI가 생성하지 않습니다.
단순 대상·시간 유사성이나 성공/실패 결과로 매칭하지 않습니다.
이는 시험용으로 명시한 증거 형식입니다. 기존 일반 자연어 Claim에 이 참조가 없으면,
서명 확인이 끝났어도 INSUFFICIENT를 유지합니다. 다른 실제 기관 원본 형식과
독립 연계 방식이 필요한 경우 backend 담당자와 별도 근거 검증기를 합의해야 합니다.

## 검증

- AI 단위/HTTP 102개와 실제 백엔드·Hardhat 연동 11개: 총 113개 통과.
- 기존 Solidity 컨트랙트 Mocha 테스트: 30개 통과.
- Solidity 컴파일 및 TypeScript 타입 검사 통과.
- 실제 체인 테스트에서 성공 receipt, 저장된 verification_hash, verdict Enum을 확인.
- 실제 Gemini까지 포함한 SUPPORTED/CONTRADICTED/INSUFFICIENT 세 건도 모두 통과.
  첫 실행은 공급자 503/시간 초과로 실패했고 한 차례 재시도 후 3건을 모두 확인했습니다.
- 미확정 매핑, 명시 참조 누락, 기관 원본 식별자 불일치, 확인 서명 내용 변조는 INSUFFICIENT.
- 요청자가 보낸 추출 결과 위조, 원본 바이트 변조, 과거 Claim 버전은 거부.
- Claim 원문과 추출 결과가 기존 SQLite 사건 JSON 저장에서 재조회되는 것까지 확인.

테스트 결과 파일:
- acceptance/backend-chain-integration.json: 고정 AI 응답 + 실제 서명/RPC/온체인 기록.
- acceptance/backend-chain-live.json: 실제 Gemini 호출 포함 별도 실행 결과.
  세 최종 판정의 성공 receipt와 온체인 해시 확인 결과를 기록했습니다.

## 재실행

1. Python requirements.txt와 Node 의존성 설치(npm ci 또는 pnpm install).
2. `hardhat build`, `tsc --noEmit`.
3. 별도 터미널에서 `hardhat node --hostname 127.0.0.1 --port 18545`.
4. FULLPROOF_CHAIN_INTEGRATION=1 설정 후 `python run_checks.py`.
5. 실제 Gemini는 GEMINI_API_KEY/GEMINI_MODEL 및 FULLPROOF_LIVE_AI=1 설정 후
   test_ai_backend_integration의 test_supported, test_contradicted,
   test_insufficient_without_proof만 실행. 서비스 호출이 있어 run_checks.py의 45초
   중단 장치를 사용하는 전체 회귀와 분리합니다.

테스트는 새 컨트랙트를 배포하고 임시 SQLite DB를 사용합니다. 기존 8545 노드나
운영 지갑·실제 사건 데이터를 사용하지 않습니다. 테스트를 위해 서버를 외부에 공개하지 않습니다.
실제 HTTP 라우팅은 FastAPI TestClient로 실행하며 별도 네트워크 서버 배포 테스트와는 다릅니다.

## 백엔드 담당자에게 공유할 부분

- main.py 변경: create_claim 저장, extract_stored_v11_claim, stored_v11_claim,
  create_v11_verification의 신뢰 입력 해석, process_v11_verification의 연결 근거 평가.
- 새 Claim 데이터는 case JSON의 v11_claims에 있습니다. 향후 전용 저장소로 옮길 때
  원문과 버전별 추출 기록을 보존해야 합니다.
- Proof Draft·매핑·Verification 저장은 현재 백엔드의 메모리 저장 방식을 유지했습니다.
  서버 재시작/다중 worker 지속성은 보장하지 않으며, 담당자의 Proof 영속화 작업과 합쳐야 합니다.
- 관리자 검토·승인·사건 종결 구현 및 계약은 수정하지 않았습니다.
- 원문 통화 참조에 의한 연결 근거 형식은 시험 브랜치 제안이므로 공식 정책 반영 전 리뷰가 필요합니다.
- 이는 AI → 백엔드 → 로컬 체인 범위 검증이며 프론트와 관리자 승인까지의 전체 통합 완료가 아닙니다.
