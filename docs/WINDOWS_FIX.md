# Windows 화면 실행 오류 수정

Notifications.tsx와 notifications.ts는 Linux에서는 서로 다른 파일이지만 Windows의 대소문자 구분 없는 모듈 탐색에서 충돌할 수 있습니다. 이로 인해 App에서 default 컴포넌트를 요청했는데 로직 모듈이 로드되어 전체 화면이 실행되지 않았습니다.

컴포넌트는 WorkNotifications.tsx, 이벤트 로직은 notificationEvents.ts로 변경하고 모든 import를 갱신했습니다. ZIP 생성 단계에도 대소문자와 확장자를 제외한 JS/TS 모듈 이름 충돌 검사를 추가했습니다.

기존 폴더 위에 덮어쓰면 이전 충돌 파일이 남을 수 있습니다. 반드시 새 폴더에 압축을 풀어 실행하세요. API 키/모델 설정은 개인 .env에 다시 설정합니다.

검증: 프론트엔드 테스트 73개 통과(maxWorkers=1), TypeScript 및 Vite 빌드 통과, 패키지 모듈 이름 충돌 검사 통과. Windows 기기에서 직접 재실행하지는 않았습니다.
