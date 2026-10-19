# FullProof Verification v1.1 전달용 연동 규격

작성일: 2026-10-19
기준: 첨부된 「FullProof 팀 공통 데이터·API·블록체인 연동 기술 규격 v1.1」 4, 6, 7, 9, 10, 11, 15, 17절.
상태: C:\Users\minju\FullProof\chain-of-investigation 기존 AI 코드를 확인하고 v1.1 연동 모듈을 추가했다. 원문 공통 규격은 팀 최종 검토용 통합안이다. 백엔드 인증·원본 조회·서명 검증·매핑 평가·공식 JCS 함수와 온체인 저장은 통합 연결이 필요하다.

## 1. 호출과 책임

POST /api/v1/verifications

공통 규격은 경로와 결과 JSON을 정의하지만 요청 본문 전체와 AI 내부 호출 방식은 확정하지 않았다. request-proposal.json은 백엔드 공개 API의 요청 제안이다. mapping_ids는 추가 제안 필드이며 팀 합의가 필요하다. 임의로 기존 API에 적용하지 않는다.

백엔드는 요청의 Claim·Proof ID, 버전, 해시를 저장된 기록과 대조하고 인증·권한, 사건·단계 참조, 매핑을 검증한다. 클라이언트가 보낸 해시나 매핑 ID만 신뢰하지 않는다. 정책은 백엔드에 등록된 적용 정책으로 선택한다.

AI 내부 호출에는 백엔드가 조회한 Claim 원문과 structured_claim, 해당 버전의 Proof 전체, 매핑 이력과 연결 근거, 유효성 검증 결과, 전체 policy_content를 전달해야 한다. 참조 객체만으로는 필드 비교를 수행할 수 없다. 내부 요청 필드명·검증 결과 표현은 실제 코드 확인 후 확정해야 한다.

AI는 행동·결과·대상·시각·원문 근거를 추출한다. Rule Engine이 최종 판정한다. 백엔드가 공식 JCS/SHA-256 계산, 저장, 온체인 기록을 담당한다. AI는 call_id를 생성하거나 추측하지 않는다.

## 2. 결과 구조

응답은 success, data, error로 감싼다. data는 공통 규격 10.2절의 Verification 객체다.

| 필드 | 타입·규칙 |
| --- | --- |
| schema_version | string, 1.1 |
| verification_id | string, 재검증마다 신규 ID |
| case_id / step_id | string / 0 이상 integer |
| claim_ref | claim_id, claim_version(1 이상), claim_hash |
| proof_refs | proof_id, proof_version(1 이상), proof_hash 객체 배열. 빈 배열 허용 |
| processing_status | PENDING / COMPLETED / NEEDS_REVIEW / FAILED |
| verdict | SUPPORTED / CONTRADICTED / INSUFFICIENT / null |
| conflicts | field, claim_value, proof_value, reason_code 객체 배열 |
| missing_information | 부족한 필드명 또는 식별 코드 문자열 배열로 제안 |
| reason_text | 판정 근거 문자열 |
| evidence_refs | 실제 참조한 Proof ID 문자열 배열 |
| review_required | boolean, 관리자 review_status와 별개 |
| decision_policy_version | 실제 적용 정책 버전 문자열 |
| policy_hash | 전체 policy_content의 JCS/SHA-256 |
| proof_refs_hash | 정렬한 참조 목록 래퍼 객체의 JCS/SHA-256 |
| verification_hash | 백엔드 계산 전 null, 계산 후 32바이트 해시 |
| verification_tx_hash | 제출 전 null, 거래 확보 후 거래 해시 |

해시는 0x + 64자리 소문자 16진수. 시간은 UTC 초 단위 YYYY-MM-DDTHH:MM:SSZ. claim_value/proof_value는 string 또는 null만 허용한다. 숫자·boolean·객체·배열은 문자열로 변환하지 않고 검증 오류로 처리한다. missing_information 코드 목록은 팀 합의 대상이다.

freshness_status, chain_status, review_status, retention_status는 별도 상태다. 10.2절 Verification 해시 객체에 임의로 추가하지 않는다. 거래 제출만으로 CONFIRMED를 반환하지 않는다.

## 3. 판정 규칙

- 유효하고 연결이 명확한 Proof가 필수 필드와 핵심 주장을 뒷받침하면 SUPPORTED.
- 유효하고 연결이 명확한 Proof와 핵심 주장이 충돌하면 CONTRADICTED. CALL_CONNECTED는 SUCCESS, CALL_FAILED는 FAIL, 누락·모호한 값은 UNKNOWN으로 비교한다. 기관 원본 result는 보존한다.
- Proof 없음, 불명확한 매핑, 필요한 정보 누락은 INSUFFICIENT. UNKNOWN을 곧바로 충돌로 처리하지 않는다.
- 사건·단계 참조 오류는 요청 오류이며 정상 INSUFFICIENT로 숨기지 않는다.
- 행동 0개 또는 2개 이상은 NEEDS_REVIEW. 최종 판정을 생성할 수 없다면 verdict는 null로 유지하고 검토를 요청한다. 이 조합의 세부 처리는 팀 합의가 필요하다.
- 처리 실패는 processing_status=FAILED, verdict=null. INSUFFICIENT와 구분한다.
- 시간 비교는 주장 수행 시각과 Proof 수행 시각을 사용한다. 발급·등록 시각으로 대체하지 않는다. 예시 정책 허용 범위는 600초이며 실제 수사 기준이 아니다.
- 후보 검색에서 성공·실패 일치 여부로 Proof를 미리 제외하지 않는다. 수동 매핑 CONFIRMED만으로 연결 근거가 충분하다고 간주하지 않는다.

## 4. 해시와 온체인 인계

proof_refs는 proof_id 문자열, proof_version 숫자 순으로 정렬한다. 동일 ID·버전은 중복 거부하며 다른 해시가 연결되면 무결성 오류다.

proof_refs_hash = SHA256(JCS_UTF8({"schema_version":"1.1","proof_refs":[정렬된 참조]}))

Proof가 없어도 빈 배열을 넣어 계산한다. null 해시를 저장하면 안 된다.

verification_content는 아래 17개 필드만 포함한다.

schema_version, verification_id, case_id, step_id, claim_ref, proof_refs, processing_status, verdict, conflicts, missing_information, reason_text, evidence_refs, review_required, decision_policy_version, policy_hash, proof_refs_hash

verification_hash = SHA256(JCS_UTF8(verification_content))

verification_hash, verification_tx_hash 및 API 래퍼는 해시 입력에서 제외한다. 단순 JSON 키 정렬을 JCS 대용으로 사용하지 않는다.

conflicts는 field, reason_code, claim_value, proof_value 순으로 오름차순 정렬한다. claim_value와 proof_value는 null을 모든 문자열보다 먼저 배치한다: null < "" < "A" < "B". null과 빈 문자열은 별개이며 원래 JSON 값을 보존한다. field와 reason_code는 문자열이어야 한다. 이 규칙은 블록체인 파트가 전달한 MVP 세부 정렬 규칙을 반영한 것이다. missing_information은 오름차순, evidence_refs는 오름차순·중복 제거한다.

policy_hash는 정책 버전 문자열만이 아니라 required_fields, time_tolerance_seconds, proof_mapping_required, semantic_analysis_required 등을 포함한 전체 정책 객체로 계산한다. 동일 정책 ID·버전의 규칙은 변경하지 않는다.

Solidity verdict 매핑: NONE=0, SUPPORTED=1, CONTRADICTED=2, INSUFFICIENT=3. NONE을 근거 부족으로 사용하지 않는다. 실패·미완료 결과를 유효한 최종 판정으로 기록하지 않는다.

기관은 Proof에만 서명한다. Verification은 별도의 허용된 시스템 기록자가 기록한다. 최신 입력 변경 시 기존 결과를 수정하지 않고 신규 Verification을 만든다. 이전 관리자 승인을 자동 적용하지 않는다.

## 5. 첨부 JSON의 사용 범위

- request-proposal.json: 공개 API 요청 제안. 확정된 현재 구현 요청이 아니다.
- response-contradicted.json: 원문 10.2절의 결과를 공통 성공 응답으로 감싼 예시.
- response-supported.json: 유효한 Proof가 성공을 뒷받침하는 경우의 출력 모양. 서로 다른 가상 입력 시나리오이며 CONTRADICTED 예시의 같은 실제 Proof와 함께 사용하면 안 된다.
- response-insufficient-before-hashing.json: Proof가 없는 경우의 해시 계산 전 중간 객체. proof_refs_hash=null은 중간 상태 표시이며 저장·온체인 제출 가능한 완성 응답이 아니다.

모든 반복문자 해시는 원문의 설명용 자리표시자다. 실제 원문·Proof·정책으로 계산한 테스트 벡터가 아니므로 서명·무결성 검증·온체인 기록에 사용하면 안 된다. 실제 백엔드 공식 함수가 policy_hash, proof_refs_hash, verification_hash를 계산한 뒤 제출한다.

## 6. 기존 코드에 반영할 변경과 확인

기존 코드 확인 후 verification_v11.py에 추출 어댑터와 결정적 판정 함수를 추가하고, verification.py의 기관 결과·시각 변환 및 backend_bridge.py의 새 경로 등록을 수정했다. 기존 AI API도 유지한다.

1. 행동 유형과 결과 분리, 원문 근거·모델·프롬프트 버전 보존.
2. proof_ids/proof_hashes 병렬 배열을 claim_ref/proof_refs로 변경.
3. Proof 버전·해시, 매핑 근거·기관 유효성 검증 후 비교.
4. 세 가지 판정과 처리 실패·검토 상태 분리.
5. 실제 전체 정책과 해시, 결정적 배열 정렬 및 공식 해시 함수 연동.
6. 기존 결과 보존, 재검증 신규 ID, 별도 온체인 상태 처리.

통합 확인 항목: 성공/실패 충돌, 성공 일치, Proof 없음, 모호한 매핑, UNKNOWN 결과, 행동 두 개, 잘못된 사건·단계, 중복·변조 참조, 시간 경계, 정책 변경, 입력 변경 후 재검증, 거래 제출 후 상태 미확정.

온체인 계약 변경·배포 및 실제 Gemini/OpenAI 호출을 포함한 End-to-End 검증은 수행하지 않았다.

## 7. 실제 함수 및 통합 방법

verification_v11.extract_v11(claim, client=None)는 기존 parser를 호출하여 action_result, occurred_at(UTC), source_excerpt, 모델·프롬프트 버전을 반환한다. 기존 parser의 한국 시각(+09:00) 해석을 사용한다. call_id를 만들지 않는다.

verification_v11.verify_v11(claim=..., proofs=..., mappings=..., proof_validation=..., canonicalize=..., policy=..., verification_id=...)는 규격 10.2의 객체를 반환한다. verification_id 생략 시 UUID 기반 신규 ID를 만든다. 이 함수는 저장·온체인 제출을 수행하지 않는다.

공식 JCS 구현 예: rfc8785.dumps를 canonicalize 인자로 제공한다. backend 공식 해시 함수가 따로 있다면 동일한 RFC8785 UTF-8 bytes 규약으로 주입한다. rfc8785==0.1.4로 예시 해시를 계산했다.

proof_validation은 백엔드 전용 (proof_id, proof_version) 튜플 키 사전이다. status=VALID는 기관 서명·기관 권한·원본 해시 검증이 끝났음을 뜻한다. mapping_evidence_sufficient=True는 수동 선택과 별개로 연결 근거가 충분하다고 평가했음을 뜻한다. HTTP 요청자가 이 값들을 직접 지정하게 하면 안 된다.

register_ai_routes(..., verification_resolver=resolver)로 새 POST /api/v1/verifications를 연결한다. resolver(request, body)는 인증·권한을 검사하고 DB에서 해당 버전 입력 및 등록 정책을 조회하여 verify_v11 인자 사전을 반환하는 동기 함수다. 예외 권한 처리는 FastAPI HTTPException으로 거부한다. resolver 미설정 시 공통 실패 응답의 503 V11_BACKEND_RESOLVER_REQUIRED를 반환한다. 기본 서버에서 JSON만 보내 곧바로 유효 판정을 받을 수는 없다.

새 경로는 판정 계산 전용이다. 원문의 '판정·기록' API 전체를 완성하려면 백엔드 저장 및 별도 시스템 기록자의 온체인 기록을 붙여야 한다. 관리자의 승인, 최신성 판정, 정책 버전 불변성, 사건 종결 검사는 백엔드·컨트랙트 담당 범위다.

현재 MVP 모듈은 PHONE_CALL/CALL_LOG와 단일 Proof만 최종 비교한다. 여러 Proof는 INSUFFICIENT로 검토를 요청한다. 필수 비교에는 정책의 3개 핵심 필드와 수행 시각을 포함한다. semantic_analysis_required=True 또는 지원하지 않는 정책 확장은 입력 오류로 거부하여 미구현 규칙을 생략한 채 SUPPORTED로 처리하지 않는다.

## 8. 계산된 예시와 설명용 예시 구분

computed-input-*.json과 computed-response-*.json이 서로 대응하는 가상 테스트 입력·출력이다. 해시들은 실제 RFC8785/SHA-256 계산값이다. 입력의 Proof 원본 해시는 가상 고정 바이트 해시 자리표시자이고 기관 서명은 제공되지 않는다. 테스트는 백엔드 검증을 통과했다고 가정한 fixture를 사용하며 실제 기관 유효성을 증명하지 않는다.

verification-content-*.json은 verification_hash 계산에 들어간 정확한 객체다. policy-content.json은 전체 정책 입력이다. 기존 response-*.json은 원문 형태를 설명하는 자리표시자 예시이므로 실제 연동에서는 computed-*를 참고한다. computed-response-insufficient.json은 빈 proof_refs의 해시도 실제 계산되어 있다.

블록체인 팀에 보낼 자료: 이 문서, request-proposal.json, computed-input/response 3쌍, verification-content 3개, policy-content.json. 공개 요청 본문과 내부 resolver 계약은 제안이므로 팀 합의 후 확정한다.

## 9. 검증 범위 및 남은 통합 작업

오프라인 테스트 53개와 수정 파일 구문 검사가 통과했다. 신규 v1.1 모듈의 HTTP/JCS 경로 테스트도 별도 실행에서 통과했으나, 전체 테스트는 중간에 발견한 bridge 구문 오류 수정 이후 HTTP·기존 서명 연동까지 전부 재실행하지 못했다. 현재 샌드박스에서는 HTTP 테스트 실행이 멈춰 중단했으며 실제 외부 AI·기관 서명·Hardhat 거래는 검증하지 않았다.

기존 /api/v1/ai/analyses 및 기존 기관 서명 draft 경로는 이전 규격이다. 새 v1.1 모듈 추가가 기존 컨트랙트·기관 서명 흐름의 v1.1 전환을 의미하지 않는다. 블록체인 담당자는 기존 Domain version=1 및 Claim/판정 포함 서명을 새 ProofAttestation/Domain version=2로 전환해야 한다.
