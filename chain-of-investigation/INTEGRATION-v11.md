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

```text
python -m pip install -r requirements-v11.txt
python -m unittest test_verification_v11 test_conflict_sort
```

오프라인 회귀 테스트 57개 통과. 실제 외부 AI·기관 서명·Hardhat End-to-End 검증은 별도 필요합니다. computed fixture는 실제 기관 자료가 아니며 검증 완료를 가정한 가상 데이터입니다.

전체 필드·제약은 docs/verification-v1.1/Verification-v1.1-전달용.md를 참고하세요.
