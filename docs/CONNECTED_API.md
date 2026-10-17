# 실제 연결 API 계약

기준 주소 `http://127.0.0.1:8000/api/v1`. 정확한 JSON 스키마는 실행 중 `/docs` 또는 `/openapi.json`에서 확인합니다. 이 파일은 ZIP에 구현된 FastAPI 기준이며, `API.md`는 초기 제안 문서입니다.

| 메서드 | 경로 | 용도 |
|---|---|---|
| GET | /system/status | 백엔드·분석 모드·키 설정 여부·현재 체인 상태. 비밀키 반환 안 함 |
| GET | /demo/scenarios | 네 가지 가상 원문·Proof 자료 |
| POST | /demo/bootstrap | 로컬 31337 + LOCAL_DEMO=1에서만 가상 사건·단계 생성/재동기화 |
| GET | /cases | SQLite 사건 목록 |
| GET | /cases/{case_id} | 사건과 수사 단계 |
| POST | /cases | 팀 원래 사건 생성. 실제 컨트랙트 거래 필요 |
| POST | /cases/{case_id}/steps | 팀 원래 단계 추가. 실제 컨트랙트 거래 필요 |
| POST | /ai/analyses | 일반 분석, 독립 Proof 인증 기본 PENDING |
| POST | /ai/drafts | 서명용 비교 초안 |
| GET | /ai/analyses/{analysis_id} | 저장된 입력·분석·전송 상태 |
| GET | /ai/cases/{case_id}/history | 사건별 분석 이력 |
| GET | /blockchain/agencies/{address} | 실제 등록 서명자와 현재 nonce |
| POST | /ai/drafts/{analysis_id}/signing-payload | 고정 분석에 대한 EIP-712 데이터 |
| POST | /ai/anchor | 서명 검증 후 컨트랙트 호출 |
| GET | /ai/anchor-status/{analysis_id} | 현재 체인 영수증·블록 해시·SQLite 상태 확인 |
| GET | /cases/{case_id}/steps/{step_id}/proof-history | 실제 컨트랙트 Proof 이력 |

## 분석 요청

```json
{
  "request_id": "매 요청의 UUID; 동일 요청 재시도에는 같은 값",
  "case_id": "FP-DEMO-001",
  "step_id": 0,
  "claim_id": "FP-DEMO-001:0",
  "claim_version": 1,
  "raw_claim_text": "2026년 10월 10일 14시에 P001에게 전화했으나 연결 실패.",
  "proof": {
    "proof_id": "DEMO-P1", "proof_version": 1,
    "action_type": "PHONE_CALL", "target_id": "P001",
    "occurred_at": "2026-10-10T14:00:00+09:00",
    "action_result": "FAIL",
    "proof_text": "P001에게 발신했으나 무응답으로 연결되지 않음."
  },
  "evidence": []
}
```

`proof: null`은 자료 부재입니다. 시각에는 시간대가 필요합니다. `action_result`(행위 결과)와 `verdict`(기록 비교 결과)는 다릅니다. 연결 실패라는 기록과 연결 실패라는 증빙은 서로 일치할 수 있습니다.

응답의 `analysis` 주요 필드:

```json
{
  "analysis_id":"서버 발급 UUID", "case_id":"FP-DEMO-001", "step_id":0,
  "verdict":"SUPPORTED", "processing_status":"COMPLETED",
  "is_provisional":true, "trust_status":"PENDING_SIGNATURE",
  "execution":{"provider":"fixture", "is_simulated":true, "label":"고정 응답 시연 · AI 호출 없음"},
  "structured_claim":{"actions":[]}, "action_results":[],
  "reason_text":"서명 전 분석 초안입니다. ...", "anchor_status":"NOT_REQUESTED"
}
```

실제 모드는 execution.provider=gemini, is_simulated=false입니다. 이 값은 호출 경로 표시이고 API 성공 여부는 processing_status와 error_code로 확인합니다. 실제 분석 오류를 SUPPORTED로 바꾸지 않습니다. Verdict: SUPPORTED / CONTRADICTED / INSUFFICIENT / null(처리 실패). 항목별 근거는 action_results[].field_checks 및 semantic_result에 포함됩니다.

## 서명·저장

서명 payload 및 anchor 요청:

```json
{
  "analysis_id":"초안 분석 ID",
  "agency":"등록된 기관의 0x 주소",
  "nonce":0,
  "deadline":2000000000,
  "evidence_timestamp":1791608400,
  "signature":"payload 생성 시 빈 문자열; anchor 시 실제 서명"
}
```

`evidence_timestamp`는 해당 Proof.occurred_at의 Unix 초와 같아야 합니다. 예시 정수를 그대로 쓰지 말고 자료에서 계산하세요. deadline은 서명 유효기한입니다. nonce는 실제 체인에서 읽습니다. payload의 uint256 사건 식별자는 JavaScript 정밀도 손실 방지를 위해 문자열입니다.

EIP-712 domain은 name=FullProof, version=1, 실제 chainId와 verifyingContract입니다. Proof 타입 순서는 팀 컨트랙트의 caseId·stepId·claimHash·proofHash·result·evidenceTimestamp·nonce·deadline·agency와 같습니다. 실제 등록 signer 계정으로 서명해야 합니다.

실제 성공 응답 주요 필드:

```json
{
  "analysis_id":"분석 ID", "storage_status":"SAVED", "anchor_status":"CONFIRMED",
  "transaction_hash":"실제 0x 거래 해시", "chain_id":31337,
  "contract_address":"실제 배포 주소", "block_hash":"실제 블록 해시", "block_number":27,
  "case_persistence":"SAVED", "recovery_required":false
}
```

SUBMITTED는 전송만 완료, CONFIRMED는 영수증 status=1, FAILED는 영수증 실패, NOT_REQUESTED는 거래 미요청입니다. STALE_CHAIN은 현재 체인과 기존 영수증이 일치하지 않는 **조회 응답 상태**입니다. UNKNOWN은 프론트엔드가 응답을 확인하지 못한 UI 상태입니다. 어떤 경우도 CONFIRMED로 꾸미지 않습니다.

## 오류·재시도

FastAPI 오류는 `{"detail":"설명"}` 또는 구조화 detail 객체입니다. 409는 요청 ID 충돌·서명 대상 부적합·정책 불일치, 422는 입력 오류, 503은 체인/저장 불가 등입니다. AI 인증·한도·모델 오류는 분석의 error_code와 processing_status로도 반환됩니다.

분석 원문·Proof가 바뀌면 새 request_id를 사용합니다. 서버 저장 이력의 동일 ID는 같은 입력으로만 재시도합니다. anchor 응답 유실 시 먼저 anchor-status를 조회하세요. 거래 해시가 있으면 무조건 다시 서명하지 않습니다.
