# 팀 API 정합성·중복 구현 비교

## 기준

- 받은 백엔드 ZIP: FullProof-fix-v1.1-legacy-cleanup.zip
- 받은 AI ZIP: FullProof-fix-ai-legacy-cleanup-v1.1.zip
- 비교한 이전 프론트 통합본: FullProof_v1.1_Mentor_Update.zip

ZIP에는 Git 이력이 없으므로 특정 커밋의 실제 포함 여부는 증명하지 않습니다. 실제 받은 파일의 SHA-256을 기준으로 대조했습니다.

## 채택한 구현

| 기능 | 이번 선택 |
|---|---|
| Claim 원문 버전·온체인 기록 | 팀 main.py·컨트랙트 그대로 |
| 기관 Proof EIP-712·Anchor | 팀 API 그대로, 프론트는 초안 서명만 수행 |
| 매핑 메시지·확정 | 팀 API·서명 메시지 그대로 |
| Verification | 팀 POST `/api/v1/verifications`, claim/proofs 형식 |
| 완료 결과 조회 | 팀 GET `/api/v1/verifications/{verification_id}` |
| 중복 방지 | 팀 V11_VERIFICATION_IDEMPOTENCY + RLock + SQLite 상태 저장 |
| 관리자 승인·종결 | 팀 API·컨트랙트 조건 그대로 |
| 구 API·구 anchorProof | 팀 cleanup 구현 그대로 |
| AI 구 판정·구 기관 일괄 서명 차단 | AI 담당자 cleanup 코드 |
| 사건별 화면·서명 UI·원문 재해시 | 프론트엔드 구현 |

**mentor_support.py, 별도 verification_requests 테이블, `/api/v1/verification-requests` API, 별도 백그라운드 판정 서버는 이번 버전에 없습니다.** 동일 기능을 양쪽에서 중복 실행하지 않습니다. AI·Rule 정책과 모델 프롬프트, 팀 계약·DB·쓰기 API를 프론트 통합 명목으로 바꾸지 않았습니다.

## 현재 필요한 보조 조회

팀 `/cases` 응답만으로는 모든 Proof 원문·매핑·Verification·관리자 사유를 화면에서 조회하기 어렵기 때문에, `frontend_server.py`는 main.app에 다음 읽기 기능만 추가합니다.

- `/api/v1/frontend/status`: 공개 체인 설정·기관 signer/nonce·관리자·확인자 주소·AI 모드·정책 해시. 비밀키 미반환.
- `/api/v1/frontend/cases`, `/api/v1/frontend/cases/{case_id}`: 저장된 자료를 화면용으로 묶고 실제 영수증·컨트랙트 참조로 상태 표시.
- `/api/v1/frontend/drafts/{case_id}/{proof_id}/{version}`: 미서명 초안 재조회.
- `/api/v1/frontend/transactions/{tx_hash}`: 실제 영수증 조회.
- `/api/v1/frontend/verifications/{verification_id}/integrity-data`: 원문·판정·정책·실제 온체인 참조를 읽어 반환. 해시 재계산은 브라우저에서 수행.

관리자 사유 원문과 종결 응답 표시를 위해 공식 성공 응답 일부를 별도 `frontend-audit.db`에 복사합니다. 이는 새 승인/종결 API가 아니고 서명이나 거래도 대신 수행하지 않습니다. 다른 클라이언트가 만든 검토는 체인 이력으로 상태를 확인하되 사유·tx를 읽지 못하면 미확인으로 표시합니다. 정식 조회 API가 준비되면 이 보조 모듈을 없애거나 공식 조회로 옮길 수 있습니다.

## 확인되지 않은 공식 system/status

이번 ZIP에는 `/api/v1/system/status` 경로가 없습니다. 팀원이 로컬에서 구현·테스트한 파일이 아직 포함되지 않았을 수 있습니다. 현재 클라이언트는 그 경로부터 요청하고 404에만 보조 조회로 전환합니다. 다른 오류나 호환되지 않는 응답을 성공으로 숨기지 않습니다.

정식 응답이 공유되면 `official.ts:getConfig()`를 그 명세에 맞춰 정리해야 합니다. 현재는 System 타입의 chain/ai/capabilities 구조를 사용하는 상태 응답만 받아들입니다. 다른 필드 이름을 임의로 추측하지 않습니다.

`/demo/session`은 외부 HTTP 요청이 아니라 로컬 화면 역할 선택 호환 처리입니다. 가짜 Bearer 인증을 만들지 않습니다.

## 중복 방지의 확인 범위와 남은 협의

정상 완료 응답 이후 반복 요청·서버 재시작 시 같은 Verification ID가 반환되는 팀 테스트는 통과했습니다. 그러나 다음 실패 구간은 별도입니다.

1. 실제 거래·영수증은 성공
2. 확인 응답을 읽는 구간에서 오류 주입 (HTTP 503)
3. 결과/중복 키가 저장되기 전에 요청이 끝남
4. 같은 요청을 백엔드에 재전송
5. Verification 이력이 1건에서 2건으로 증가

별도 로컬 체인에서 재현한 결과는 `BACKEND_DIAGNOSTIC.json`입니다. **이것은 합격 테스트가 아니라 남은 장애 구간을 보여 주는 진단입니다.** 팀 백엔드의 기존 성공 경로를 실패했다고 뜻하지 않습니다.

프론트는 Verification POST의 응답이 불명확하면 브라우저에 요청 참조를 남기고 재전송을 막습니다. 이후 새로 저장된 동일 Claim·Proof·정책의 확정 결과가 확인될 때만 재사용합니다. 이를 확인할 수 없으면 상태 새로고침·이력 확인을 안내합니다. 다른 클라이언트의 재전송까지 서버에서 해결한 것은 아닙니다.

백엔드 측 후속 검토 제안:

- 거래 전 Verification ID·처리 중 상태를 먼저 저장하고, 제출 tx를 보관해 응답 유실 뒤 조회로 복구할지
- 기존 캐시 반환 직전에 현재 체인·참조가 유효한지 확인할지
- 새로운 미선택 Proof도 종결 최신성에 영향을 주므로, 입력 키에 Proof 이력 변경 문맥을 포함할지

뒤의 두 항목은 소스 검토에 따른 확인 제안이며 이번 진단 스크립트가 모두 실험한 항목은 아닙니다. 이 합본에서 팀 쓰기 규칙을 임의로 교체하지 않았습니다.

## 처리 중 화면

팀 Verification API는 현재 동기 응답입니다. 화면에 ‘검증 및 판정 기록 중’ 로딩을 보여 주고 중복 클릭·역할 변경을 막습니다. 서버가 요청 ID부터 반환하는 비동기 상태 API를 현재 구현했다고 표시하지 않습니다. AI 추출도 별도 로딩을 표시합니다.

## 파일 출처

`SOURCE_MANIFEST.json`에 백엔드 파일별 원본 해시, 선택한 AI 파일의 출처, 합본 해시를 적었습니다. main.py, database.py, contracts/ChainOfInvestigation.sol은 백엔드 ZIP과 바이트 단위로 같습니다. AI 담당 수정 파일만 AI ZIP에서 가져왔습니다. 팀원의 로컬 파일과 GitHub 원격을 추가로 확인한 결과로 표시하지 않습니다.
