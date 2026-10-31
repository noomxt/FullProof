# API 전용 연결

2026-10-31. 연결 설정과 실행 모드 선택을 제거했습니다. 런타임 API 모듈은 officialRequest만 호출하고, 서명은 실제 지갑 연결을 사용합니다. localStorage의 fullproof.service.mode나 VITE_SERVICE_MODE는 연결 방식을 바꾸지 않습니다. 연결 실패 시 오류·재시도만 표시하며 Mock으로 전환하지 않습니다.

기존 Mock 모듈은 자동화 테스트 fixture용으로만 남아 있습니다. 제품 API 모듈은 Mock 모듈을 import하지 않습니다. 역할별 화면 테스트는 테스트 내부에서 명시적으로 fixture를 주입합니다.

실행: `py configure_ai.py`로 개인 키를 설정한 뒤 `py start_connected.py --live`. 이미 백엔드가 켜져 있을 때만 `py start_frontend.py`를 단독으로 사용합니다. 프론트엔드만 켠다고 API 서버가 실행되지는 않습니다. 서버 키는 chain-of-investigation/.env에서 관리합니다.

확인: Vitest 61개 통과, TypeScript 및 Vite 빌드 통과. 저장된 Mock 설정 무시, API 실패 시 대체 데이터 미표시, 모드 선택 UI 부재 확인 포함. 실제 Gemini·MetaMask·Hardhat 전체 실행 및 브라우저 시각 검사는 이번 수정에서 재실행하지 않았습니다. 백엔드·컨트랙트 코드는 변경하지 않았습니다.
