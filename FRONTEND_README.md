# 프론트엔드 완료 범위와 실제 API 연결 경계

## 완료 범위

v1.1 기준 입력·후보 선택·검증 표시·관리자 확인·보완·승인·종결 화면과 전환, 역할별 제어, 로딩·실패·재시도·빈 상태를 구현했습니다. Mock 모드에서는 브라우저만 실행하며 준비된 가상 결과를 반환합니다.

| 구분 | 프론트엔드 Mock | 팀 API 모드 |
| --- | --- | --- |
| 사건·Claim | 브라우저 localStorage | 서버 응답 |
| 추출·판정 | 미리 정의한 가상 결과 | 팀 AI·Rule Engine |
| 기관 서명 | 지갑 호출 없는 가상 처리 | MetaMask 어댑터 |
| 기록 상태 | MOCK · 온체인 미저장 | PENDING/SUBMITTED/CONFIRMED/FAILED/UNKNOWN |
| 거래 해시 | null, 가짜 해시 생성 금지 | 서버 거래 응답 |
| 관리자 확인 | 브라우저 가상 이력 | capability 지원 시 API 호출 |
| 종결 | 가상 사건 CLOSED | 서버 권한·조건 검사에 따름 |
| 오류 | 시연 도구로 재현 가능 | 실제 오류 표시, Mock으로 자동 우회하지 않음 |

이 문서의 '완료'는 프론트엔드 책임 범위입니다. 실제 AI·기관 인증·블록체인 컨트랙트 기능이 모두 완료됐다는 뜻이 아닙니다.

## 관리자 처리 규칙

- ACKNOWLEDGED: 판정 확인만 기록하고 완료 승인으로 취급하지 않음.
- REVISION_REQUESTED: 사유와 대상 verification_id/hash를 별도 이력으로 저장.
- ACCEPTED: 최신 CURRENT+SUPPORTED 판정만 가능.
- 모든 처리에서 관리자 역할과 사유를 요구.
- 기존 검증 verdict를 수정하지 않음.
- 새 Claim/Proof 입력 또는 새 검증 시 기존 승인을 자동 적용하지 않음.
- Claim·검증·승인 이력은 보존하고 화면에서 이전 이력도 표시.

## 종결 규칙과 화면

가상 사건은 최신 Claim 참조, CURRENT, SUPPORTED, 유효 Proof 참조, 최신 관리자 ACCEPTED가 있을 때만 종결 가능. 사유를 입력해야 실행 가능. 종결 후 입력·검증·관리자 변경을 차단하고 종결 사유·시각을 보존. 실제 종결 권한은 최종 백엔드·컨트랙트가 강제해야 하며 프론트엔드 버튼 제한만으로 대체하지 않음.

## API 교체 지점

- `src/api.ts`: api<T>(), setRole(), signProof(), VITE_API_BASE_URL.
- `src/AdminReview.tsx`: POST reviews의 review_status/reason_text/verification_hash 및 POST close의 reason_text.
- `src/mock.ts`: Mock 전용, 운영 API·AI 판정 구현으로 사용하지 않음.
- `src/App.tsx`: 화면 표시 타입에 맞춘 어댑터 호출.

Mock 고유 chain_status=MOCK은 브라우저 서비스 내부 상태입니다. 실제 API의 enum이나 Solidity enum에 이 값을 추가하지 않습니다.

## 실행

```powershell
py start_frontend.py
```

백엔드, Python 패키지, 지갑, AI 키, 체인 프로세스 없이 시작합니다. 기본 4개 사건, 준비된 시연 원문을 사용합니다. 이전 모드 선택이 남아 있으면 상단 실행 모드에서 프론트엔드 Mock을 선택합니다.

## 이번 변경 검증

2026-10-19, Linux / Node 24 / Chromium 134 / Playwright 1.51.1.

- 프론트엔드 단위 테스트 **17개 통과**: HTTP 어댑터 5개, Mock 생명주기 12개.
- TypeScript·Vite production build 성공.
- 정상 흐름: 가상 원문 → 고정 추출 → 기관 시연 → 후보 연결 → 판정 → 결과 확인 → 승인 → 종결.
- 결과 확인만으로 종결 불가, 불일치·근거 부족·연결 불명확의 승인·종결 차단.
- Claim 새 버전 후 이전 승인을 유지하면서 재검증·재승인 요구.
- 실패 시 결과를 만들지 않고 재시도 가능.
- 실제 트랜잭션 해시 null, Mock 기록은 CONFIRMED로 표시하지 않음.
- 브라우저 전체 흐름과 역할 변경, 새로고침 후 보존, 관리자·종결 이력 확인.
- 브라우저 Mock 테스트 중 8000/8545/Google API 요청이 발생하지 않음을 확인.
- desktop 1440 / mobile 390 배치 확인, 가로 넘침 없음.

Windows 실행은 직접 검증하지 못했습니다. Node만 실행하는 독립 경로와 Windows npm.cmd 런처를 제공했습니다. 실제 API 모드의 Gemini·MetaMask·서버 기능 완료 여부는 이전 팀 연결 문서를 참고하세요.
