# 관리자 승인 → 사건 정상 종결 시험 통합

시험 브랜치: test/ai-verification-integration-v1.1.
AI 연결 기준 89849eb에 관리자 브랜치 feature/admin-review-v1.1의 0c1cecf를 병합했습니다.
main.py는 자동 병합됐으며 관리자 코드의 동작은 변경하지 않았습니다.
공식 feature/integration-v1.1과 feature/admin-review-v1.1 브랜치는 변경하지 않습니다.

## 검증 범위

별도 127.0.0.1:18545 Hardhat 체인에 새 계약을 배포하고 임시 SQLite DB를 사용했습니다.
프론트 화면 대신 FastAPI TestClient로 실제 API 핸들러를 호출했습니다.
기관 Proof EIP-712 서명, 담당자 매핑 확인 서명, 관리자 검토 서명,
종결 요청 서명은 로컬 테스트 계정의 실제 서명입니다.

정상 경로:

1. 사건·필수 단계 생성 및 Claim 원문 온체인 고정.
2. 저장된 Claim의 AI 추출.
3. 기관 원본 Draft 생성·기관 서명·Proof Anchor.
4. Claim–Proof 매핑 생성·담당자 서명 확정·독립 통화 참조 대조.
5. SUPPORTED Verification 온체인 기록과 verification_hash 확인.
6. 관리자 ACCEPTED 서명 검증 및 VerificationReviewAnchored 이벤트 확인.
7. 관리자 종결 서명 검증, closeCase 조건 검사와 거래 실행.
8. CaseClosed 이벤트, 성공 receipt, 온체인 CLOSED 및 백엔드 is_closed=True 확인.

## 정상 경로 외 차단 조건

- SUPPORTED라도 관리자 승인 전에는 종결 차단.
- CONTRADICTED/INSUFFICIENT를 ACCEPTED로 승인하거나 사건 종결하는 요청 차단.
- CONTRADICTED의 ACKNOWLEDGED 기록은 허용하되 종결은 차단.
- 관리자 외 계정의 승인·종결 요청 및 서명 내용 변조 차단.
- 만료된 승인 서명 차단, 동일 승인 nonce 재사용 차단.
- 새로운 Verification 생성 시 기존 승인이 자동 적용되지 않고 종결 차단.
- 정상 종결 후 재종결 차단.
- 기존 AI 연결의 원본 변조/과거 버전/불명확한 매핑 차단도 회귀 확인.

## 실행 결과

- 전체 회귀/HTTP/체인 테스트: 118개 통과.
  AI 기존 102개 + 실제 백엔드·체인 시나리오 16개입니다.
- acceptance/admin-chain-integration.json에 시나리오와 검증·승인·종결 거래 해시를 저장했습니다.
- 실제 Gemini를 포함한 정상 경로 1건도 통과했습니다. acceptance/admin-chain-live.json에
  Verification·관리자 승인·사건 종결 거래 해시와 온체인 CLOSED 상태를 기록했습니다.
  첫 호출은 AI_TIMEOUT으로 실패했고, 한 차례 재시도 후 정상 완료했습니다.
  첫 실패 기록은 acceptance/admin-chain-live-timeout.json에 별도 보존합니다.

## 재실행

의존성 설치와 계약 컴파일 후 별도 로컬 Hardhat 노드를 18545에서 실행합니다.

```text
FULLPROOF_CHAIN_INTEGRATION=1
FULLPROOF_TEST_REPORT=admin-chain-integration.json
python run_checks.py
```

실제 Gemini 1건으로 정상 승인·종결까지 확인하려면 Gemini 환경 변수를 설정하고
FULLPROOF_LIVE_AI=1, FULLPROOF_TEST_REPORT=admin-chain-live.json을 추가한 뒤
아래 단일 테스트를 실행합니다. 외부 API 호출은 run_checks.py의 45초 중단과 분리합니다.

```text
python -m unittest test_ai_backend_integration.BackendIntegrationTests.test_admin_supported_approval_and_normal_closure -v
```

## 통합 한계 및 후속 작업

- AI-백엔드-연동결과.md의 CALL_REF 명시 참조·기관 원본 형식을 그대로 사용했습니다.
  자연어가 비슷하거나 매핑 상태가 CONFIRMED라는 이유만으로 연결 근거를 인정하지 않습니다.
- 관리자·종결 nonce 저장 및 Proof/매핑/Verification 메모리 저장의 재시작 지속성은
  기존 백엔드 구현 범위에 따릅니다. 영속 저장 작업과 별도 통합해야 합니다.
- 프론트 화면, 실제 기관 시스템, 배포 서버에 대한 검증은 포함하지 않습니다.
- database.py와 Solidity 계약은 이 병합에서 수정하지 않았습니다.
