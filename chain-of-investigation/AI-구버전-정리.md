# 멘토링 후 AI 구버전 경로 정리

기준: 공식 feature/integration-v1.1, 019dd0b.
작업 브랜치: fix/ai-legacy-cleanup-v1.1.
백엔드 담당자의 fix/v1.1-legacy-cleanup과 분리해 AI 모듈만 수정했습니다.
main.py, database.py, Solidity 계약, 백엔드 API 등록 코드는 수정하지 않았습니다.

## 실제 v1.1 경로 (유지)

- 저장 Claim 추출: main.extract_stored_v11_claim → verification_v11.extract_v11
  → ai_engine.parse_claim_with_llm.
- 최종 판정: main.create_v11_verification → main.process_v11_verification
  → verification_v11.verify_v11.
- 파서의 기존 필드 호환 및 verification.normalize_claim/timestamp는 실제 추출에
  사용하므로 유지했습니다. 파서와 최종 판정 함수를 혼동해 제거하지 않았습니다.
- 기관 ProofAttestation 생성·서명 검증은 백엔드 담당 경로에 그대로 있습니다.

## 실행 차단/제거

1. ai_engine.verify_claim_vs_proof
   - import 호환용 이름만 유지합니다. 호출하면 LEGACY_AI_VERIFICATION_DISABLED
     RuntimeError를 냅니다. 최종 판정이나 의미 비교 LLM 호출을 수행하지 않습니다.
   - proof_validation=VALID 같은 인자로 다시 활성화할 수 없습니다.
   - 아직 이 이름을 import하는 기존 main.py의 AI_AVAILABLE을 불필요하게 깨뜨리지 않습니다.

2. backend_bridge.register_signed_draft_routes
   - 구버전 Claim+Proof+AI 판정을 한 번에 기관 서명하는 데이터 생성·전송 코드를 제거했습니다.
   - 다음 경로를 등록하더라도 410 LEGACY_AI_SIGNING_DISABLED만 반환합니다.
     POST /api/v1/ai/drafts
     POST /api/v1/ai/drafts/{analysis_id}/signing-payload
     POST /api/v1/ai/anchor
     GET /api/v1/ai/anchor-status/{analysis_id}
   - OpenAPI에서 위 폐기 경로를 숨기고, 체인·저장소·AI 호출을 하지 않습니다.

3. verification.py/pipeline.py
   - 공통 시간 변환과 과거 오프라인 비교/분석 유틸리티를 구분해 표시했습니다.
   - v1.1 운영 판정이나 기관 서명에 이 프로토타입 엔진을 사용하지 않도록 명시했습니다.

## 테스트

- 예전 서명 방식의 성공을 기대하던 7개 테스트를 폐기 경로 차단 테스트 3개로 대체했습니다.
- 신뢰 플래그를 전달해도 구버전 판정이 활성화되지 않는 검사 1개를 추가했습니다.
  따라서 기존 120개와 이번 테스트 개수는 다릅니다. 이번 전체 117개가 모두 통과했습니다.
- 파서 자체 검사 10개도 통과했습니다.
- 구버전 함수/서명 경로에서 LLM·체인·저장소 접근이 발생하면 실패하도록 검사합니다.
- v1.1 운영 API·서명·온체인 기록·승인·종결·프로세스 복원 회귀는 그대로 확인합니다.
- 결과 파일: acceptance/ai-legacy-cleanup-regression.json.
- 모델 프롬프트와 v1.1 Rule Engine 판정 정책은 변경하지 않아 이번에 실제 Gemini를
  재호출하지 않았습니다. 테스트 모델 응답은 재현용 주입 데이터입니다.

## 백엔드 담당자와 합칠 때

현재 공식 main.py의 구버전 /api/v1/cases/verify는 이 구버전 함수 이름을 호출합니다.
해당 API 자체의 제거/명시적 폐기 응답은 백엔드 cleanup 브랜치에서 처리해야 합니다.
AI 쪽 차단만으로 기존 API가 올바른 410 HTTP 응답을 반환한다고 주장하지 않습니다.
예전 anchorProof 및 VERIFIED/MISMATCH 별칭 정리도 백엔드·컨트랙트 담당 범위입니다.
이 문서의 변경과 백엔드 cleanup을 함께 반영하면 예전 경로 혼동을 줄일 수 있습니다.
