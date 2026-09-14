# 백엔드 연결 안내

## 현재 코드의 연결 지점

| 사용자 동작 | 현재 위치/동작 | 실제 연결 시 필요한 것 |
|---|---|---|
| 사건 접수 | FlowApp.jsx의 접수 form, React 상태 | 사건 생성 API, 서버가 확정한 템플릿/필수 STEP 반환 |
| Claim 저장 | FlowApp.jsx의 saveClaims | 작성자 인증, Claim 생성/버전 관리 API |
| 기관 증빙 발행 | FlowApp.jsx의 issue → proofs.js | 원천기관 Mock 서비스, 기관 Wallet 서명, 독립 Proof 저장 |
| 검증 | FlowApp.jsx의 run → engine.js 또는 선택 API | 저장된 Claim/Proof ID로 요청, 서버 서명·AI·규칙 검증 |
| 관리자 확인 | FlowApp.jsx의 review | 관리자 인증, 보완/확인 기록, 최종 판단 정책 |
| 기록 조회/출력 | React ledger 상태, download | 영구 검증 이력, 체인 거래/블록/확정 상태 조회 |

현재 UI 상태는 서버 권한 검사를 대체하지 않습니다. 현재 proofs.js의 브라우저 키와 engine.js의 완료 판정을 실서비스의 신뢰 기준으로 사용하지 않습니다.

## 함께 제공한 선택 API의 규격

- POST `/api/v1/demo/verify`
- 입력: `{ step, now }`
- 응답: `{ status, reason, checks, completed, engine, source }`
- Node 시연 서버는 규칙 함수만 실행합니다. 기관 서명 진위·사용자 인증·체인 거래를 검증하지 않습니다.

## 팀 FastAPI와 다른 점

기존 FastAPI는 `/api/v1/cases/verify`에서 `{ case_id, step_id, raw_claim_text, proof, evidence_deadline }`를 받습니다. 상태는 SUPPORTED/CONTRADICTED 등을 쓰며 reason_detail/tx_hash를 반환합니다. 현재 UI가 기대하는 checks/completed와 STEP 데이터 구조도 다릅니다. URL 교체만으로 연결하지 말고 API 어댑터를 별도 작성해야 합니다.

## 다음 커밋의 권장 순서

1. 화면의 시연 상태 처리를 유지하면서 `src/api/` 등 별도 어댑터로 사건/Claim/Proof/검증/검토 함수를 분리합니다.
2. 서버 기준 case_id, step_id, template_version, claim_id, proof_id, issuer, UTC 시각, 확보 여부, 보존기한, 상태/사유 코드를 통일합니다. 필수 STEP은 서버 템플릿이 결정합니다.
3. 기관 Proof 발행과 검증 요청을 분리합니다. 브라우저가 보낸 임의 proof 사전을 기관의 신뢰된 증빙으로 취급하지 않습니다.
4. 서버의 역할 검증·기관 서명 검증·체인 권한·상태 매핑·관리자 확인·DB 복구를 먼저 고칩니다.
5. 실제 연결 모드를 추가합니다. 서버 실패 시 성공한 가상 응답으로 바꾸지 않고 오류/미확인 상태를 표시합니다.
6. 실제 거래의 성공/실패와 확정 여부를 확인한 뒤 저장 완료로 표시하고, 새로고침 후 서버에서 이력을 다시 불러옵니다.

## 통합 완료 기준

정상/불일치/기한 임박 3개 시나리오 외에도 서명 변조, 잘못된 기관·사건 연결, AI/서버 장애, 재시작 복구, 권한 없는 최종 확인 요청을 시험해야 합니다. 실제 AI 의미 대조와 서버 연결이 확인되기 전에는 기본 시연 표시를 제거하지 않습니다.
