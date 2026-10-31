# 이번 수정본 테스트 — 2026-10-29

공식 백엔드 기준: final-mentor-v11 @7998973a84f72e7c96ddb7f295c00e81fb6643d8.

## 직접 실행

| 항목 | 결과 | 범위 |
| --- | --- | --- |
| 프론트 단위 테스트 | 53개 통과 | API·서명·해시·요청 진행·역할 메뉴·최신 검증 집계 |
| TypeScript / Vite 빌드 | 통과 | 최종 프론트 소스 |
| 역할별 브라우저 확인 | 통과 | 서로 다른 첫 화면·업무 메뉴·시연 사례 이어 열기 |
| 화면 확인 | 통과 | 세 역할의 라이트/다크·390px 모바일·한글 폰트 |
| 실제 로컬 API E2E | 통과 | FastAPI·Hardhat·고정 추출·주입 EIP-1193 지갑 |
| 키 없는 클라이언트 연결 | 통과 | 같은 Linux 환경의 두 프론트 프로세스·공유 API/체인 |
| 공유 실행 도구 | 통과 | 명시적 루프백 URL·설치된 의존성 재사용·fixture |
| 공식 컨트랙트 컴파일 | 통과 | 변경 없는 Solidity·solc 0.8.34 |

프론트 로그: FRONTEND_TEST_RESULTS.txt, FRONTEND_BUILD_RESULTS.txt.
브라우저 결과: ROLE_UI_RESULTS.json, LOCAL_TEST_RESULTS.json.
공유 연결: SHARED_CLIENT_RESULTS.json, LAUNCHER_RESULTS.json.

브라우저 E2E는 역할별 첫 화면을 거쳐 기관 EIP-712·매핑 personal_sign·SUPPORTED 판정·브라우저 해시/온체인 대조·관리자 ACKNOWLEDGED와 ACCEPTED 구분·사건 종결을 확인했습니다. CONTRADICTED, Proof 없음 INSUFFICIENT, CALL_REF 없음 INSUFFICIENT도 승인·종결 차단을 확인했습니다. 서명 거절 후 매핑 재사용, 새로고침 후 기존 요청 조회, 동일 입력의 기존 ID 재사용, 모바일 넘침 없음을 확인했습니다.

클라이언트 테스트에서는 Gemini 키 환경변수가 없는 프로세스로 공유 서버에 접속해 사건을 등록하고 호스트에서 같은 사건을 조회했습니다. /rpc를 통한 네트워크 조회는 성공하고 eth_sendTransaction은 403으로 차단됐습니다. 이 테스트는 외부 Gemini 호출 없이 fixture를 썼습니다.

## 환경 제약·미검증

- 실제 두 Windows PC 사이 LAN·방화벽·공유기 연결은 확인하지 않았습니다.
- 공유 LAN 바인딩(0.0.0.0)은 사용자 Windows에서 확인해야 합니다. 이 환경은 Node의 networkInterfaces 호출을 제한해, 공유 실행 도구는 명시적 127.0.0.1 URL로 검사했습니다.
- 실제 Gemini 재호출·MetaMask 확장 팝업은 이번 수정에서 테스트하지 않았습니다. 고정 추출 및 주입 테스트 지갑을 사용했습니다.
- 외부 인터넷 공유 서버/HTTPS 도메인은 배포하지 않았습니다. shared-demo.json의 server_url은 비어 있는 상태로 제공합니다.
- 실제 API 인증·기관별 접근 통제·운영 배포·다중 서버·전체 DB 복구는 구현한 범위가 아닙니다.
- 신선한 Windows 환경에서 의존성 설치는 검증하지 않았고, 이번 실행은 기존 잠금 파일에 대응하는 설치된 의존성을 재사용했습니다.

## 이전 백엔드 테스트와 구분

공식 run_checks.py 118개, run_mentor_checks.py 130개 통과 로그는 이전 2026-10-26 실행 기록입니다(두 집합 중복 포함). 이번에는 공식 백엔드 소스를 바꾸지 않았고, 프론트·공유 연결 관련 확인과 컨트랙트 컴파일을 수행했습니다. 팀이 보고한 156개 테스트와 합산하지 않습니다.

초기 브라우저 실행에서는 설치 캐시가 없어 브라우저 바이너리를 준비했고, 역할별 개요 이름 변경으로 옛 테스트 선택자가 맞지 않던 부분을 갱신한 뒤 재실행했습니다. 최종 결과 JSON은 수정된 흐름을 실제 실행한 결과입니다.
