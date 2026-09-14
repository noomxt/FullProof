# 첫 커밋 안내

## 이번 전달물

현재 FullProof 사이트의 PPT 기반 화면과 시연 로직을 담은 첫 커밋용 소스입니다. 백엔드·블록체인 감사에서 발견한 문제를 해결한 통합 완성본은 아닙니다.

Sites 전용 식별 설정, Git 이력/인증정보, 설치된 라이브러리와 빌드 출력은 제외했습니다. 실행 코드와 의존성 잠금 파일, 테스트, CI, 수동 배포 설정을 포함했습니다.

## 기존 noomxt/FullProof 저장소에 반영

1. 기존 저장소를 내려받거나 GitHub Desktop에서 엽니다.
2. 로컬 변경사항이 있다면 먼저 커밋하거나 따로 보관합니다.
3. README만 있는 현재 main을 기준으로 새 브랜치(예: `feature/frontend-foundation`)를 만듭니다.
4. 이 압축 안의 `FullProof-frontend-starter` 폴더 **내부 파일 전체**를 저장소 최상위에 복사합니다. 폴더 자체를 한 단계 더 넣지 않습니다. `.github`, `.gitignore`, `.env.example`도 포함합니다.
5. 기존 README를 이번 프런트엔드 README로 교체합니다. 프로젝트 전체 소개를 유지하려면 별도로 합쳐도 됩니다. 기존 backend/policy 브랜치는 건드릴 필요가 없습니다.
6. 저장소 최상위에서 `npm ci`, `npm test`, `npm run build`를 실행합니다.
7. 변경 내용을 확인하고 커밋한 뒤 해당 브랜치를 push합니다.

기존의 고장난 `feature/frontend-ui` 위에 파일을 섞기보다 main에서 시작하면 오래된 App.jsx/api.js/fixtures.js와 혼동하기 쉽지 않습니다. 기존 코드 이력은 기존 브랜치에 그대로 남습니다.

## 커밋 메시지

```text
feat(frontend): add PPT-aligned FullProof demo foundation
```

커밋 설명 예시:

```text
Add the five-stage investigation demo from case intake to administrator review.
Include mock agency proofs, browser demo signatures, deterministic validation,
three scenarios, and session audit export.

AI, institution authentication, FastAPI, persistent storage, and blockchain
integration remain pending. Verify baseline with tests and production build.
```

## 이번 커밋의 완료 기준

- 저장소에서 npm ci 후 개발 화면을 열 수 있음
- 정상/불일치/CCTV 기한 임박 시연이 있음
- 테스트와 빌드가 성공함
- 미연결 기능이 실제 구현된 것처럼 표시되지 않음

실제 백엔드 연결 및 GitHub 업로드는 이번 전달물에 포함된 완료 작업이 아닙니다. 사용자가 첫 커밋을 남긴 후 그 기준점에서 API 어댑터와 서버/컨트랙트를 수정하면 됩니다.
