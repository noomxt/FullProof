# API 계약 제안과 연동 가이드
아래 경로와 응답은 프론트엔드가 제안하는 초안입니다. 실제 API 존재·접근 권한·경찰 시스템 연동 가능성을 가정하지 않습니다.

## 현재 어댑터 계약
응답은 `{data:...}` 래퍼 없이 직접 JSON입니다. 실제 서버가 래퍼를 쓰면 `src/api/http.ts`에서 변환하세요.

| 메서드 | 제안 경로 | 응답 |
|---|---|---|
| GET | /cases | Case[] |
| GET | /cases/:id/claims | Claim[] |
| GET | /claims/:id | Claim 또는 null |
| POST | /claims/:id/verifications | Verification |
| GET | /verifications | Verification[] (최신 우선) |
| POST | /verifications/:id/blockchain | 갱신된 Verification |

타입의 전체 필드는 `src/types.ts`, 실제 Mock 예시는 `src/data/mock.ts`에 있습니다. 시간은 시간대가 있는 ISO 8601 문자열을 사용하세요. 화면은 Asia/Seoul로 표시합니다. 검증 결과 비교 항목의 시간은 원본 값을 표시합니다.
조회 시간 제한은 15초이며 실패 화면에서 재시도합니다. POST를 자동 재시도하지 않습니다. 실제 연동 시 idempotency key, 중복 제출 방지, 페이지네이션, 정렬을 협의하세요.

## AI 팀 응답 제안 (아직 호출하지 않음)
```json
{
  "recordId": "REC-001",
  "sourceText": "가상의 원문 수사 진행 기록",
  "analysisMode": "model",
  "modelVersion": "팀이 제공할 버전",
  "claims": [{
    "id": "CL-001", "caseId": "FP-2026-001",
    "type": "CCTV 자료", "stage": "요청",
    "location": "해솔역 2번 출구", "time": "2026-10-08T10:00:00+09:00",
    "target": "가상 성인 A", "result": "요청 접수 완료",
    "sourceSpan": {"start": 0, "end": 12}, "missingFields": []
  }],
  "rationale": "각 필드의 원문 근거"
}
```
`sourceSpan`은 문자열 오프셋 기준을 합의하세요. 불명확한 값은 추정하여 채우지 말고 null과 missingFields로 표현하도록 타입을 확장하세요. 현재 프론트엔드는 사전 구조화된 Claim만 조회하며 실제 모델 호출을 구현하지 않습니다.

## 검증 응답
`Verification`은 비교 항목, verdict, rationale, nextAction, demo, chain을 포함합니다. Mock의 `demo` 타입은 true로 제한되어 있습니다. 실제 연결 전에 boolean으로 바꾸고 서버가 `demo:false`를 반환하도록 합의하세요. AI가 근거를 생성하는 경우 근거 원문·출처 ID를 추가하고 담당자의 최종 확인 기능을 별도 설계하세요.
현재 Mock은 단계/장소/시간/사건번호만 비교합니다. 대상·결과는 Proof에서 제공하지 않으므로 검증되었다고 표시하지 않습니다. 실제 시간 허용 오차나 식별자 매칭 정책은 백엔드와 합의해야 합니다.

## 블록체인 팀 응답 제안
```json
{
  "verificationId": "검증 ID",
  "status": "pending",
  "network": "팀이 선택할 네트워크",
  "transactionHash": null,
  "recordHash": "합의된 직렬화 방식의 SHA-256",
  "confirmedAt": null,
  "error": null
}
```
제안 상태: unconnected / pending / failed / confirmed. 현재 화면 타입에는 confirmed가 없으며 실제 저장 완료를 시연하지 않습니다. 연동 시 confirmed 상태, 실제 transactionHash, 영수증, 확인 수를 추가하고 확정된 응답에만 완료 배지를 표시하세요. 네트워크 탐색기 주소도 팀에서 제공한 값으로만 구성하세요.
현재 Mock 해시는 `{id,claimId,createdAt,verdict,comparisons}` 객체의 JSON.stringify 값입니다. 실제 기록은 키 순서·인코딩·필드·해시 알고리즘을 합의하고 프론트/백엔드/체인 간 고정된 테스트 벡터를 사용하세요. 현 UI는 해시를 재검증하지 않습니다.

## 연결 순서
1. 팀과 엔드포인트·필드·오류 형식·권한·CORS·개인정보 처리 범위를 합의합니다.
2. `src/types.ts`를 실제 DTO에 맞추거나 `http.ts`에서 UI 모델로 매핑합니다. 현재 타입 단언만 하므로 실제 데이터에 대한 런타임 스키마 검증을 반드시 추가합니다.
3. `.env.local`에 `VITE_API_MODE=http`, `VITE_API_BASE_URL=https://팀에서-제공한-주소`를 넣고 Vite를 다시 시작합니다.
4. 인증은 팀의 보안 설계에 따라 구현합니다. 현재 어댑터에는 인증 기능이 없습니다. 비밀키나 서버 자격증명을 VITE 변수에 넣지 않습니다.
5. AI 추출과 Proof 수집은 팀 API가 수행하고 프론트에는 구조화 결과를 전달합니다.
6. 이력 및 저장 요청 응답을 연결하고, confirmed 표시·영수증 조회·해시 재검증을 구현합니다.
7. 네 가지 시나리오와 오류·권한·중복 제출·네트워크 지연을 실제 통합 환경에서 테스트합니다.

실제 모드의 초기화 기능은 비활성입니다. 실패 시연 플래그는 Mock에서만 사용하며 HTTP API에 전달하지 않습니다. 현재 이력 상세 화면은 Mock 데이터에 맞춰져 있으므로 체인 응답을 연결할 때 트랜잭션 표시도 갱신하세요.
