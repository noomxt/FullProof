# 직접 실행한 테스트 — 2026-10-26

공식 기준: final-mentor-v11 @7998973a84f72e7c96ddb7f295c00e81fb6643d8.

| 항목 | 결과 | 조건 |
| --- | --- | --- |
| 프론트 테스트 | 50개 통과 | API·Mock·서명·브라우저 해시·진행 조회·오류·재조회 |
| TypeScript / Vite 빌드 | 통과 | npm run build |
| 공식 run_checks.py | 118개 통과, 건너뜀 없음 | 별도 로컬 Hardhat 18545 |
| 공식 run_mentor_checks.py | 130개 통과, 건너뜀 없음 | 별도 로컬 Hardhat 18545 |
| 컨트랙트 컴파일 | 통과 | 변경 없는 공식 Solidity, solc 0.8.34 |
| 브라우저 E2E | 통과, 페이지 오류 없음 | Chromium + 실제 FastAPI + 로컬 Hardhat |

118과 130은 중복 테스트를 포함하므로 합산하지 않습니다. 팀원이 공유한 156개라는 수치는 팀의 실행 범위이며, 여기서는 저장소에 있는 두 공식 실행 스크립트의 실제 출력과 분리해 기록합니다. 원시 로그는 run_checks.txt, run_mentor_checks.txt, FRONTEND_TEST_RESULTS.txt, FRONTEND_BUILD_RESULTS.txt에 있습니다.

## 브라우저에서 확인한 범위

- 기관 EIP-712 서명, 매핑·관리자·종결 personal_sign을 주입 테스트 지갑으로 수행.
- SUPPORTED → ACKNOWLEDGED만으로 종결 불가 → ACCEPTED → 사건 종결.
- CONTRADICTED 및 두 가지 INSUFFICIENT에서 승인·종결 제한.
- 지갑 서명 거절 후 기존 매핑 재사용.
- async API 시작·GET 상태 조회·같은 입력 요청 ID 재사용.
- 페이지 새로고침 후 기존 요청 상태 조회: 새 Verification POST 없이 완료 결과 확인.
- frontend/status에서 등록 기관·관리자 지갑 설정 조회.
- 공식 integrity-data 원문으로 브라우저 JCS/SHA-256 재계산·실제 체인 해시 대조.
- 이력 재조회, 실제 거래 영수증 조회, 모바일 390px 수평 넘침 없음.
- 네트워크 요청에서 system/status와 동기 POST verifications 미사용 확인.

LOCAL_TEST_RESULTS.json에 확인 항목이 있습니다. 테스트 스크린샷은 내부 확인용이며 산출물에 포함하지 않습니다.

## 테마 추가 확인

상단 라이트·다크 버튼, 키보드 Space 전환, 새로고침 시 선택 유지, 다크 모드의 전체 API 시연 흐름, 모바일 390px 수평 넘침 없음을 브라우저에서 확인했습니다. 테마 추가 후 TypeScript/Vite 빌드도 통과했습니다. 기존 50개 단위 테스트 및 공식 회귀 테스트 결과는 테마 추가 이전 실행이며, 테마 추가 후에는 관련 브라우저 E2E와 빌드를 다시 실행했습니다. 백엔드에는 변경이 없습니다.

## 장애·진행 상태

프론트 단위 테스트에서는 PROCESSING·SUBMITTED·FAILED·UNKNOWN, 응답 유실, 조회 실패, 대기 시간 초과, ID 불일치, 거래 없는 완료 응답, 저장된 요청 복귀를 확인했습니다. 실패·불명확 응답에서 자동 POST하지 않습니다.

공식 멘토 회귀 테스트에는 거래 성공 후 응답 유실 복구, 동시 요청 재사용, 서버 재시작 후 재사용, 매핑·추가 Proof 변경에 따른 새 판정이 포함되어 있습니다. 이전 Team_Aligned의 중복 장애 재현을 이 버전의 미해결 결함이라고 표시하지 않습니다.

## 직접 확인하지 않은 범위

실제 MetaMask 브라우저 확장과 팝업, 외부 Gemini 호출, 사용자 Windows 설치·실행, 운영 배포·다중 서버·기관 인증·전체 SQLite 복구. 브라우저 테스트는 주입 EIP-1193 지갑과 고정 AI 추출을 사용했고, 실거래는 공개 로컬 테스트 계정으로 수행했습니다. 자동 실행 도구의 사용자 Windows 재현 확인은 남아 있습니다.

프론트와 별도 실행 도구를 추가했으며 공식 백엔드·AI·DB·컨트랙트 소스는 수정하지 않았습니다.
