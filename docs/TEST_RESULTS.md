# 테스트 결과 — 2026-10-26

## 직접 실행한 확인

| 항목 | 결과 | 범위 |
| --- | --- | --- |
| 팀 백엔드·AI 회귀 테스트 | 119개 통과, 건너뜀 없음 | 별도 로컬 Hardhat 실거래 포함 |
| 프론트 단위 테스트 | 38개 통과 | Mock, 요청 형식, 서명, 무결성, 응답 불명확 시 재전송 방지 |
| TypeScript·Vite 빌드 | 통과 | frontend npm run build |
| 팀 컨트랙트 컴파일 | 통과 | solc 0.8.34 |
| Chromium 브라우저 E2E | 통과 | 로컬 API·Hardhat, 주입 EIP-1193 테스트 지갑, 고정 AI 추출 |

브라우저에서는 SUPPORTED → 관리자 확인 → ACCEPTED → 사건 종결, CONTRADICTED 종결 차단, Proof 없음 INSUFFICIENT, CALL_REF 없음 INSUFFICIENT, 서명 거절 후 재시도, 새로고침 이력, 모바일 390px, 실거래 영수증, 브라우저 JCS/SHA-256 대조, 동일 요청 ID 재사용, 공식 Verification 결과 조회를 확인했습니다. 페이지 오류는 없었습니다.

원시 결과: LOCAL_TEST_RESULTS.json, TEAM_REGRESSION_RESULTS.txt, TEAM_CHAIN_RESULTS.json.

## 오류 진단에서 발견한 미해결 항목

BACKEND_DIAGNOSTIC.json은 성공 판정 자료가 아니라 별도 장애 재현 결과입니다. 체인 거래 성공 후 완료 응답을 잃도록 주입하면 첫 요청 HTTP 503에 체인 기록 1건, 같은 요청을 직접 다시 POST하면 HTTP 201에 체인 기록 2건이 됩니다. 정상 완료 응답 이후의 중복 방지는 통과했으나, 거래 성공과 결과 저장 사이 장애 복구는 백엔드 후속 확인이 필요합니다.

프론트는 상태 0/5xx 등 불명확한 응답에서 자동 재전송하지 않고 표시를 보존하며, 일치하는 실제 새 결과가 조회될 때만 복구합니다. 이 조치는 다른 클라이언트의 직접 재전송이나 백엔드 장애 자체를 해결하지 않습니다.

## 실행하지 않은 범위

- 실제 MetaMask 브라우저 확장: 주입 테스트 지갑으로 대체했습니다.
- 실제 Gemini 네트워크 호출: 고정 추출 응답을 사용했습니다.
- 사용자 Windows PowerShell에서의 설치·실행: Linux 환경에서 검사했습니다.
- 다중 서버, 운영 배포, 실제 기관 데이터, 전체 SQLite 복구.

받은 백엔드 ZIP에는 /api/v1/system/status가 없습니다. 팀원의 로컬 구현을 받기 전까지 조회 전용 /api/v1/frontend/status를 404 시에만 사용합니다.
