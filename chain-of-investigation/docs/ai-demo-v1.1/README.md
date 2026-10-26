# AI 담당 MVP 세 판정 입력·출력 예시

범위: 통화 증빙 PHONE_CALL 한 종류, Claim 한 개에 행동 한 개.
운영 API나 판정 정책 변경 없이 기존 extract_v11/verify_v11을 실행해 생성한 합성 자료입니다.
파일의 model_name=offline-demo-fixture는 고정 응답 테스트임을 뜻합니다.
실제 Gemini 응답이나 실제 기관 서명·온체인 기록으로 표시하면 안 됩니다.

| 파일 | Claim | 기관 Proof | 기대 판정 | 핵심 근거 |
| --- | --- | --- | --- | --- |
| supported.json | 통화 연결 성공 | CALL_CONNECTED | SUPPORTED | action_result SUCCESS 대 SUCCESS |
| contradicted.json | 통화 연결 성공 | CALL_FAILED | CONTRADICTED | RESULT_MISMATCH, SUCCESS 대 FAIL |
| insufficient.json | 통화 연결 성공 | 미확보 | INSUFFICIENT | PROOF_MISSING, proof_refs=[] |

세 사례 모두 AI 추출 자체는 COMPLETED입니다. 세 번째도 AI 오류가 아니라
필수 증빙 부족 판정이며 processing_status=COMPLETED, verdict=INSUFFICIENT입니다.
정상 추출을 통화 성공 판정과 혼동하지 마세요. 결과가 불명확한 단순 발신 시도는
이번 세 사례와 별개로 action_result=UNKNOWN이며 SUCCESS로 추측하지 않습니다.

## 바로 확인할 내용

각 JSON은 다음을 구분합니다.

- requests: API 호출 시 사용할 입력 자료.
- expected_extraction: 공통 응답 형식의 AI 구조화 결과. actions의 action_type,
  action_result, target_id, occurred_at, source_excerpt와 모델·프롬프트 버전 포함.
- expected_verification: 판정, conflicts, missing_information, reason_text,
  evidence_refs, review_required 및 Claim/Proof 버전·해시 참조.

담당 범위는 AI 결과·근거 제공입니다. 프론트 구현이나 백엔드 서명·실행 설정을
이 자료가 대신 정하는 것은 아닙니다. 실제 API 명세는 백엔드 담당 안내를 따릅니다.

## 실제 연동 시 필요한 동적 값

- case_create와 step_create 후 claim_create를 등록하고 원문이 저장·고정된 뒤 extract 요청.
- supported/contradicted의 proof_draft_base는 입력 재료입니다. 실제 Draft 요청에는
  기관 지갑의 현재 nonce와 미래 deadline을 추가해야 합니다. 서명하지 않은 이 base를
  곧바로 Anchor나 Verification에 넣으면 실제 백엔드 검증을 통과하지 않습니다.
- agency_address는 예시 Hardhat 주소입니다. 실제 등록된 기관 지갑으로 맞춰 재생성하세요.
- 기관은 백엔드 Draft가 반환한 EIP-712 typed data에 서명합니다. Anchor와 매핑 확정은
  기존 백엔드·지갑 흐름을 사용합니다. 이 자료에는 가짜 기관/담당자 서명이 없습니다.
- mapping_create는 PENDING 요청입니다. 담당자 서명 확인과 기관 원본 검증이
  완료되어야 합니다. 예시 파일의 예상 판정을 만들기 위해 CONFIRMED나 검증 플래그를
  클라이언트에서 자체 선언하면 안 됩니다.
- verification 입력은 서버가 조회할 Claim 참조와 Proof 자료입니다. 실제 기관
  Anchor와 매핑 확정이 끝난 Proof를 사용하고, 신뢰 플래그를 HTTP로 보내지 않습니다.
- insufficient 사례는 Proof·매핑 단계를 건너뛰고 proofs=[]로 검증합니다.
- 동일 case/Claim/Proof ID를 이미 등록한 환경에서는 그대로 재등록하지 않습니다.
  반복 시연용 새 ID 세트 또는 데모 체인 초기화 여부는 백엔드 담당과 맞춥니다.

## 연결 근거와 원본

Claim 원문에 CALL_REF[TELECOM-001:통화ID]를 처음부터 포함했습니다.
이는 이번 MVP 합의 방식이며 정식 수사 기록의 필수 규격이 아닙니다.
AI가 call_id를 만들거나 Claim을 재작성하지 않습니다.
성공과 실패 여부로 Proof 후보를 골라내지 않습니다. contradicted도 같은 통화 ID를 비교합니다.

proof_draft_base.source_text는 합성 기관 원본 UTF-8 JSON이며, 그 정확한 바이트의
SHA-256을 source_sha256으로 계산했습니다. source_text를 재정렬/포맷하면 원본 해시가
달라질 수 있으므로 원본 문자열을 유지합니다. Proof 해시는 별도로 JCS+SHA-256입니다.

## 예상 응답을 사용할 때

SUPPORTED는 관리자 ACCEPTED 후 종결할 수 있는 판정이지 관리자 승인/종결 완료가 아닙니다.
CONTRADICTED/INSUFFICIENT는 ACCEPTED·정상 종결 대상이 아닙니다.
판정은 해당 Claim과 Proof의 일치 여부이며 사건 전체의 진실성이나 담당자의 고의성을 뜻하지 않습니다.

이 파일의 해시는 고정 fixture의 ID/기관 주소/근거 문구에 대한 실제 계산값입니다.
운영 API가 발급한 verification_id, 매핑 확인 결과, AI 근거 문구 등이 달라지면
verification_hash도 달라집니다. 검증 기준은 실제 응답 필드와 실제 해시 입력입니다.
verification_tx_hash=null은 오프라인 자료이며 온체인 저장 완료를 뜻하지 않습니다.

## 재생성

```text
python generate_ai_demo_cases.py
python generate_ai_demo_cases.py --agency-address 실제_등록_기관주소
```

rfc8785와 기존 AI 모듈 의존성만 사용합니다. 생성기는 외부 API·지갑·블록체인을
호출하지 않고, 세 기대 판정 및 원문 근거·원본 해시·충돌 사유를 확인한 뒤 저장합니다.
내부 검증에서만 사용한 유효 Proof/매핑 가정은 requests에 포함하지 않습니다.
실제 연결 테스트와 서명·권한·온체인 검증은 기존 통합 테스트로 별도 확인합니다.
