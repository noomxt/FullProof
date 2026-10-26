# AI Verification v1.1 integration

이 브랜치는 AI v1.1 계산 모듈과 입력·출력 fixture를 공유합니다. 온체인 기록·기관 서명 검증 완료를 의미하지 않습니다.

## 파일

- verification_v11.py: extract_v11(), verify_v11(), sort_conflicts(), register_v11_routes()
- verification.py: 기존 비교 엔진과 기관 result/시각 변환
- backend_bridge.py: 기존 AI API 어댑터. pipeline.py, ai_engine.py, ai_provider.py는 같은 폴더의 기존 모듈을 사용합니다.
- test_verification_v11.py, test_conflict_sort.py: 판정·정렬 테스트
- docs/verification-v1.1/request-proposal.json: 공개 요청 제안
- docs/verification-v1.1/computed-input-*.json, computed-response-*.json: 가상 입력과 실제 JCS/SHA-256 계산 출력
- docs/verification-v1.1/policy-content.json: 전체 정책 객체

## 기존 FastAPI에 연결

AI 담당 전체 규격별 근거는 `AI-v1.1-규격대조표.md`에 기록합니다.
공식 추출 API는 `register_v11_extraction_route`로 별도 연결합니다.

```python
from verification_v11 import register_v11_extraction_route, register_v11_routes
register_v11_extraction_route(app, resolver=resolve_stored_claim)
register_v11_routes(app, resolver=resolve_verification_inputs)
```

resolve_stored_claim(request, claim_id, body)는 인증/권한 검사 후 이미 저장·고정된
Claim의 해당 버전을 반환합니다. body 자체를 Claim으로 사용하지 마세요.
추출 결과 저장과 실패 이력 저장은 백엔드 책임입니다.
동일 경로가 이미 있으면 중복 등록하지 말고 기존 핸들러에서 extract_v11/verify_v11을 호출합니다.

### B안 ProofAttestation 검토 결과

팀 공유 기준은 Domain `FullProof` / version `2`, primaryType `ProofAttestation`입니다.
필드 순서는 아래와 정확히 일치해야 합니다.

```text
uint256 caseId
uint256 stepId
bytes32 proofIdHash
uint256 proofVersion
bytes32 proofHash
uint64 occurredAt
uint64 issuedAt
address agency
uint256 nonce
uint64 deadline
```

`verify_v11`은 EIP-712 데이터를 생성하지 않으며, 기존 `proof_version` 참조를 유지합니다.
`backend_bridge.register_signed_draft_routes`는 Domain version 1로 Claim·Proof·판정을
함께 서명하는 구버전 전용 코드입니다. v1.1 통합에서 등록하지 마세요. 필드 추가만으로
새 컨트랙트에 호환되지 않습니다. v1.1은 아래 `register_v11_routes`만 연결하고,
Proof 독립 서명·검증·온체인 기록은 백엔드의 새 구현을 사용합니다.
구버전 함수는 기존 호출부 호환을 위해 보존하며 v1.1 구현으로 표시하지 않습니다.

공유된 Mock 기대값:
- proofHash: `0xd9491d4f357151184e95ba4f4044686cb93b88daaa62cd6d443614b236ca793b`
- EIP-712 Digest: `0x0261a3ca1da9fddfe34b2d0e2643b1f3266b03a17c2d3cf5538074ea3e6e324b`

원본 proof_content 수신 후 `../vector-check/`에서 Python(rfc8785 + eth-account)과
JavaScript(canonicalize + ethers)로 독립 계산했습니다. 두 환경 모두 위 proofHash와
EIP-712 Digest에 일치했습니다. caseId, proofIdHash, proofVersion, occurredAt,
issuedAt의 원본 JSON 대응도 확인했습니다. 결과는 python-result.json과
javascript-result.json에 보존합니다. source_sha256은 Mock 고정값이며 실제 원본의
무결성이나 기관 서명 검증을 입증하지 않습니다. 실제 서명/온체인 호출은 수행하지 않았습니다.

블록체인 담당 FastAPI에서 새 경로만 연결하려면 다음을 사용합니다.

```python
from verification_v11 import register_v11_routes
register_v11_routes(app, resolver=resolve_verification_inputs)
```

register_v11_routes 자체는 /api/v1/verifications만 등록하며 /api/v1/cases/verify를 수정하지 않습니다. 동일 경로를 두 번 등록하지 마세요.

기존 backend_bridge.register_ai_routes()는 구버전 /api/v1/cases/verify를 409 응답으로 대체하는 이전 동작도 포함합니다. 기존 블록체인 API를 보존해야 하면 이 함수를 통째로 등록하지 말고 위의 register_v11_routes만 호출하세요.

resolve_verification_inputs(request, body)는 동기 함수로, 인증·권한 확인 후 저장된 해당 버전의 claim, proofs, mappings, proof_validation, 등록 policy, verification_id를 조회하고 verify_v11의 키워드 인자 사전을 반환합니다. canonicalize에는 백엔드 공식 RFC8785 bytes 함수를 전달합니다. Python 예시는 rfc8785.dumps입니다.

proof_validation은 (proof_id, proof_version) 튜플 키의 백엔드 전용 사전입니다. status=VALID 및 mapping_evidence_sufficient=True는 서버가 기관 서명·권한·원본·연결 근거를 검사한 결과여야 합니다. HTTP 요청자의 자체 선언을 그대로 사용하지 않습니다.

resolver 미설정 시 503 V11_BACKEND_RESOLVER_REQUIRED. 설정 후 성공 응답은 success/data/error 래퍼이며 data가 Verification 객체입니다. 이 경로는 현재 계산 전용입니다. 블록체인 담당자가 verify_v11 결과를 저장하고 별도 시스템 권한으로 온체인 기록하는 흐름을 붙여야 합니다. 재시도 시 ID·저장 중복 방지와 정책 버전 불변성도 백엔드에서 관리합니다.

conflicts는 field, reason_code, claim_value, proof_value 순으로 정렬하며 null < "" < "A" < "B"입니다. 비교값은 string/null만 허용하고 숫자·boolean·객체·배열은 변환하지 않고 거부합니다.

## 의존성과 검증

### v1.1 판정 우선순위

1. 사건·단계·버전 참조 오류, 해시 불일치, 잘못된 시각 형식은 입력 오류로 거부합니다.
2. 추출 실패는 `processing_status=FAILED`, `verdict=null`입니다.
3. 행동 수/추출 검토 필요, Proof 부재, 기관 검증 미완료, 연결 근거 부족은 `INSUFFICIENT`입니다.
4. 연결이 명확한 유효 Proof라도 비교 필수 정보가 누락되면 `INSUFFICIENT`가 충돌보다 우선합니다.
5. 비교 정보가 모두 있으면 충돌 존재 시 `CONTRADICTED`, 모두 일치하면 `SUPPORTED`입니다.

공백만 있는 비교값은 누락으로 취급합니다. 이 판정용 검사에서 원문이나 해시 입력을
수정하지 않습니다. 누락과 함께 발견된 개별 필드 차이는 `conflicts`에 남을 수 있으나,
최종 판정은 `INSUFFICIENT`이며 충돌 확정으로 표시하면 안 됩니다.
매핑/기관 검증이 불충분한 경우에는 필드 비교 자체를 진행하지 않습니다.

### AI 추출 출력 호환

AI 응답 스키마는 `ClaimExtractionV11`이며 행동 필드는 `action_type`,
`action_result`, `target_id`, `occurred_at`, `source_excerpt`입니다.
`occurred_at`은 UTC 초 단위 `YYYY-MM-DDTHH:MM:SSZ` 또는 null입니다.
시간대가 없는 한국어 기록은 한국 표준시로 해석하며, 상대 날짜는 추측하지 않습니다.

기존 `parse_claim_with_llm()` 호출부에는 `status_claim`, `claimed_time`,
`source_text` 및 기존 단일 행동 필드를 계속 반환합니다. `claimed_time`은
기존과 같은 한국 표준시의 시간대 없는 문자열입니다. 기존 `normalize_claim()`의
기본 `+09:00` 해석과 함께 사용합니다. v1.1 소비자는 `extract_v11()`을 사용합니다.
원문은 수정하지 않으며, 새 Claim이나 call_id를 생성하지 않습니다.

`model_name`은 공급자 응답에 명시된 모델 ID(없으면 실제 요청 ID), `prompt_version`은
`extract-v1.1-prompt-v2`입니다. API 호출 전 실패는 `model_name=null`입니다.
메타데이터가 없는 구버전 추출 결과를 주입하면 해당 값은 null로 유지합니다.
v1.1 최종 판정에서는 메타데이터 누락을 거부하므로 구버전 추출 결과는 재추출해야 합니다.
오프라인 테스트는 출력 계약과 호환성을 검증하며 실제 Gemini 추출 정확도를 보장하지 않습니다.

```text
python -m pip install -r requirements-v11.txt
python -m unittest test_verification_v11 test_conflict_sort
```

전체 회귀 테스트는 `python run_checks.py`로
전체 테스트를 실행합니다. 실행기는 45초 초과 시 스택을 출력하고 실패로 종료합니다.
이번 전체 점검 결과는 단위/HTTP 102개, 파서 자체 검사 10개 통과입니다.
실제 Gemini 합성 입력 10건도 모두 통과했으며, 서비스 503이 발생한 건은 재시도 후 확인했습니다.
Windows 제한 실행 환경에서는 TestClient가 API 호출 전 내부 socketpair 초기화에서
정지할 수 있습니다. 이번 환경에서는 동일 테스트를 실행 제한 밖에서 돌려 정상 완료를
확인했습니다. 운영 API 코드를 변경하거나 테스트를 생략해서 해결한 것은 아닙니다.

v1.1 HTTP 테스트는 공식 RFC8785 해시, 세 판정의 200 응답, 잘못된 해시·사건 참조·시각 및
깨진 JSON의 422 공통 오류 응답, resolver 미설정 시 503 응답을 확인합니다.
실제 외부 AI 결과는 acceptance/live-gemini.json에 기록합니다.
실제 기관 서명·Hardhat End-to-End 검증은 별도 필요합니다.
computed fixture는 실제 기관 자료가 아니며 검증 완료를 가정한 가상 데이터입니다.

전체 필드·제약은 docs/verification-v1.1/Verification-v1.1-전달용.md를 참고하세요.
