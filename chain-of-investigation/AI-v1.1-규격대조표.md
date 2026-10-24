# AI·Rule Engine v1.1 규격 대조표

기준: 사용자가 전달한 FullProof 공통 규격 v1.1, 이후 합의된 B안 proofVersion 포함.
이 문서는 AI 담당 범위의 구현과 검증 근거를 기록한다. 팀 전체 통합 완료 선언이 아니다.

## AI 담당 조건

| 규격 | 조건 | 코드/검증 근거 |
| --- | --- | --- |
| 1.1, 3.4, 4.1 | 원문 수정 금지; 추출 전에 원문 저장·해시 고정 | AI는 입력을 변경하지 않음. test_claim_whitespace_and_unicode_bytes_preserved. 저장/온체인 고정은 backend resolver의 선행 조건 |
| 2.1, 2.3 | 문자열 사건 ID·정수 버전/단계; AI에서 사건 ID 변환 금지 | validate_claim_identity/ref/verify_v11; 온체인 변환은 실제 AI 경로에 없음 |
| 2.2, 4.2 | UTC 초 단위 시각; 발급 시각과 수행 시각 구분 | ClaimActionV11/utc; occurred_at 대 proof_occurred_at만 비교; 시각·날짜 경계 테스트 |
| 4.2–4.4 | action_type/action_result 분리; 네 행동 유형 | ClaimActionV11/SYSTEM_PROMPT; test_action_types, test_extraction_output |
| 4.4 | 단순 전화 시도에서 성공 추측 금지; 모호한 결과 UNKNOWN | SYSTEM_PROMPT; UNKNOWN → 검토/INSUFFICIENT; 실제 모델 acceptance 결과 별도 기록 |
| 4.3, 17.2 | 원문 근거·대상 근거 반환/검증 | source_excerpt 연속 부분문자열 확인; 대상 ID는 excerpt에서 확인; ungrounded/invented 테스트 |
| 4.2, 17.2 | 실제 모델/프롬프트 버전 기록 | 요청 모델 또는 공급자 응답 모델 ID; PROMPT_VERSION; 완료 추출의 메타데이터 누락 거부 |
| 4.5 | 0개 행동 검토; 1개 정상; 2개 이상 분리 요청 | _finalize/extract_v11/verify_v11; CLAIM_ACTION_MISSING/CLAIM_SPLIT_REQUIRED 및 원문 보존 |
| 4.5, 5.4 | call_id 생성/추측 금지 | 추출 스키마 extra=forbid; call_id 추출 시 거부 테스트 |
| 4.4, 5.5 | 기관 result 원본 유지; 비교 때만 정규화 | CALL_CONNECTED→SUCCESS, CALL_FAILED→FAIL; 원본 Proof 불변 테스트 |
| 6.1–6.4 | 자동 통화 매칭 금지; 명확한 연결 뒤 비교 | CONFIRMED + 정확한 Claim/Proof 버전/기관/call_id + 백엔드 연결 근거 검증 필요. 누락이면 필드 충돌 판정하지 않음 |
| 6.3, 10.3 | 참조 버전·해시 일치; 잘못된 사건/단계 입력 오류 | ref, Claim/Proof 해시 검증, extraction reference 검증. bool을 버전/단계로 허용하지 않음 |
| 7.1–7.3 | 공식 canonicalizer 주입; SHA-256/JCS | backend RFC8785 bytes 함수를 주입. Claim 원문은 UTF-8 그대로 비교. 테스트 JSON sort 함수를 운영 해시로 사용하지 않음 |
| 7.4 | proof_refs 정렬·중복 거부·빈 목록 허용 | verify_v11; expected_proof_refs_hash 제공 시 일치 검사; 빈 refs 해시 벡터 |
| 7.5 | 전체 정책 해시·실제 버전 반환 | POLICY 검증·required_fields 정렬/중복 제거; policy_hash/decision_policy_version |
| 7.5 | 같은 정책 ID/버전 내용 변경 차단 | backend 등록 정책 해시를 registered_policy_hash로 전달하면 변경 거부. 해시 레지스트리 영속 관리/버전 발급은 backend 소유 |
| 7.6 | 한국어·공백·Proof·정책·참조·판정 공통 해시 벡터 | vector-check/common-v11.json; Python/JS 독립 JCS 계산, 세 verdict의 verification_hash 일치 |
| 8.1–8.4 B안 | 기관은 Proof에만 서명 | v1.1 AI 경로에 서명 생성 없음. 팀 Mock ProofAttestation proofVersion 포함 Digest 양언어 일치 |
| 9.1–9.3 | 처리 상태와 판정 분리 | FAILED→null; 검토 필요→NEEDS_REVIEW/INSUFFICIENT; 나머지 COMPLETED와 세 verdict |
| 9.3 | 정보 누락·불명확한 연결은 INSUFFICIENT | 누락 우선 정책; 검증 전 Proof와 잘못된 매핑으로 CONTRADICTED 생성 금지 |
| 9.3 | 명확하고 유효한 Proof와 충돌은 CONTRADICTED | 양방향 성공/실패 충돌·시간 허용범위 경계·필드 비교 테스트 |
| 10.2–10.4 | 필수 Verification 필드·정렬·해시 자기 참조 제외 | verify_v11; reason_text 최종 확정 후 hash; HTTP와 양언어 벡터 테스트 |
| 15 순서 3 | 공식 Claim 추출 API 연결 | register_v11_extraction_route; 저장 Claim resolver만 신뢰; 경로 ID/요청 버전 확인 |
| 15 순서 8 | 공식 검증 API 연결 | register_v11_routes; trusted backend resolver; JSON 객체 검사 |
| 15.1–15.3 | 공통 성공/실패 envelope·오류 상태 | 200/422/503 및 resolver 403 보존 테스트; 블로킹 AI/동기 resolver는 별도 실행 스레드 |
| 17.2 | 사람 판단 보조; 결론/의도 추정 금지 | 정책 기반 필드 비교만 최종 판정. 시스템 프롬프트는 사실 판정 금지 |

## 백엔드·팀 연동 책임 (AI 구현으로 대체하지 않음)

- 인증/권한 검사, Claim 최초 저장·해시 고정 이후 추출 호출.
- 분리 전 Claim 유지 및 새 Claim의 parent_claim_id 저장/버전 발급.
- Proof 후보 조회/담당자 선택, 매핑 이력 저장, 기관 서명·권한·원본·연결 근거 검사.
- 해당 버전의 Claim/Proof를 불변 조회하고 AI 추출을 해당 Claim 버전에 저장.
- 등록 정책 내용/해시의 불변 레지스트리. 운영 resolver는 registered_policy_hash를 제공.
- 최종 검증 저장·verification_id 중복 방지·Proof/Claim 수정 시 재검증 최신성 판단.
- 기관 Proof 온체인 기록과 시스템 Verification 온체인 기록 분리.
- chain_status/관리자 review/사건 close/retention 상태는 Verification 판정과 별도로 관리.
- v1.1에서 register_signed_draft_routes는 등록하지 않음(구버전 서명 흐름).

## 실행 근거와 미확인 구분

- 전체 단위/HTTP 테스트: run_checks.py 실행 로그 기준. 실제 공급자 호출을 대체하지 않음.
- 공통 암호 벡터: vector-check/python-result.json, javascript-result.json.
- 실제 Gemini: acceptance/live-gemini.json. 합성 입력 10건 모두 기대 결과와 일치.
  성공/실패/단순 시도/예정/정보 누락/CCTV 요청·열람/위치 요청/복수 행동/상대 날짜를 확인.
  첫 실행의 503 서비스 오류 후 실패 건부터 재시도했으며, 고정 테스트셋 10건의
  통과는 임의의 모든 자연어 입력에서 정확성을 보장한다는 의미가 아님.
- 실제 팀 저장소 resolver/프론트/컨트랙트 E2E는 이 문서의 로컬 HTTP 테스트와 다름.
- 점검 당시 AI 브랜치 main.py는 기존 parse_claim_with_llm/verify_claim_vs_proof를 호출함.
  해당 main.py를 그대로 실행한 것을 v1.1 앱 통합이라고 표현하지 않음.
  팀 백엔드 main.py에서 저장/서명/매핑 resolver를 연결해야 함. AI 라이브러리의
  규격 구현과 실제 서버의 연결 완료를 구분함.

## 연결 예시

```python
from verification_v11 import register_v11_routes, register_v11_extraction_route

# resolver는 동기 함수. 인증된 서버 데이터만 반환한다.
register_v11_extraction_route(app, resolver=resolve_stored_claim)
register_v11_routes(app, resolver=resolve_verification_inputs)
```

resolve_stored_claim(request, claim_id, body)는 저장된 Claim 객체를 반환한다.
resolve_verification_inputs(request, body)는 verify_v11 키워드 인자를 반환한다.
둘 다 기존 backend의 인증 실패/미존재/권한 거부에 맞는 HTTPException을 낼 수 있다.
기존 backend에 같은 경로가 있으면 중복 등록하지 말고 extract_v11/verify_v11 함수를
기존 핸들러에서 호출한다. 추출/검증 결과의 영속 저장은 backend가 수행한다.
