# 키 없는 클라이언트 연결

실제 Gemini 키는 호스트의 `chain-of-investigation/.env`에만 있습니다. ZIP/프론트 JS/VITE 변수에 키를 넣지 않습니다. 이 배포본의 `shared-demo.json`은 아직 서버 주소가 비어 있으며 공유 서버 배포 완료를 뜻하지 않습니다.

## 구조

호스트 PC에서 FastAPI(127.0.0.1:8000), Hardhat(127.0.0.1:8545), 공유 Vite(0.0.0.0:5173)를 실행합니다. 외부 클라이언트는 localhost Vite 프록시를 통해 호스트의 `/backend`와 `/rpc`에 연결합니다. 실제 AI 요청·판정·체인 제출은 호스트의 공식 코드가 처리합니다.

클라이언트는 원본 전체 소스 ZIP을 받아도 프론트 의존성만 설치합니다. 서버 주소는 --server 또는 shared-demo.json에서 읽습니다. 키나 서버 환경파일은 읽지 않습니다. localhost에서 접속하여 Web Crypto·MetaMask 보안 컨텍스트를 유지합니다. 직접 HTTP LAN 주소로 열면 화면에서 안전한 연결 안내가 표시됩니다.

RPC 프록시는 지갑의 네트워크 확인에 필요한 읽기 메서드만 허용합니다. eth_sendTransaction, eth_sendRawTransaction, eth_sign, Hardhat 제어 메서드 등은 차단합니다. HTTP API 자체의 인증·업무 규칙은 공식 백엔드 기준이며, 이 프록시는 API 인증을 대체하지 않습니다.

## 아직 하지 않은 것

- 공개 인터넷 서버·고정 HTTPS 도메인 배포
- 실제 두 Windows PC 간 방화벽·라우터 연결 확인
- 외부 Gemini 호출 테스트(개발 검증은 fixture 사용)
- 실제 MetaMask 확장 검증(주입 테스트 지갑 사용)
- API 인증·기관별 접근 통제·사용량 제한·운영 인프라

따라서 신뢰하는 팀원 사이 개발 네트워크용입니다. 공개 주소/서버 계정이 정해지면 인증·HTTPS 프록시·RPC 네트워크 설정을 포함해 별도로 배포해야 합니다.

## 문제 해결

- Shared server is not configured: 호스트가 --share 실행 후 생성한 shared-demo.json을 받거나 --server 주소 지정.
- Shared host unavailable: 서버 PC 실행 상태·LAN IP·개인 네트워크 방화벽·같은 네트워크 여부 확인.
- 포트 충돌: 이전 실행 종료 또는 클라이언트 --port 5174 사용.
- MetaMask 연결 오류: 등록된 테스트 계정 선택 및 RPC를 클라이언트 localhost /rpc로 설정.
- 새로고침 후 다른 시연 모드: 상단 연결 설정에서 팀 API 연결 선택. 브라우저는 지난 선택을 보존합니다.
- 호스트 IP 감지 실패/VPN: --public-url로 실제 접근 가능한 IP와 5173 포트 지정.

기존 .env를 새 소스 폴더로 복사할 때는 로컬에서만 처리하세요. 배포 ZIP은 package_project.py로 생성하면 .env·DB·로그·node_modules·테스트 스크린샷을 제외합니다.
