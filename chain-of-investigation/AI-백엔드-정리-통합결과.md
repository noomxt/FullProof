# AI·백엔드 멘토링 정리 합본

공통 기준: feature/integration-v1.1의 019dd0b.
합친 브랜치:
- fix/ai-legacy-cleanup-v1.1: 589eb39 (AI 정리 6092d1f와 세 판정 예시 포함).
- fix/v1.1-legacy-cleanup: 6f944b4 (백엔드·컨트랙트 정리와 검증 결과 조회 포함).

기존 AI 정리 브랜치에서 백엔드 정리를 병합했고 코드 충돌은 없었습니다.
프론트 코드는 이 통합에 포함하지 않았습니다.

## 함께 적용되는 변경

- AI 구버전 판정 함수는 명시적 오류로 차단.
- 기관이 Claim·판정까지 서명하던 AI 어댑터 코드를 제거하고 폐기 경로는 410 반환.
- 기존 backend /api/v1/cases/verify, 구버전 Proof Anchor 및 복구 경로 차단.
- Solidity legacy anchorProof 실행 차단 및 기존 성공 테스트를 차단/새 ProofAttestation 테스트로 전환.
- 공식 v1.1 저장 Claim 추출 → 독립 기관 Proof → 매핑 → 정책 판정 → 시스템 기록 흐름 유지.
- 동일한 서버 조회 입력(Claim/추출/Proof/매핑/정책) 재요청은 기존 Verification 재사용.
  중복 방지 키를 SQLite에 저장해 새 Python 프로세스에서도 중복 거래를 방지.
- GET /api/v1/verifications/{verification_id} 결과 조회 경로 포함.
- 세 판정 입력·출력 예시와 설명은 docs/ai-demo-v1.1에 유지.

## 합본 검증 결과

- Solidity 컴파일 성공(solc 0.8.34), TypeScript tsc --noEmit 성공.
- 컨트랙트 Mocha 테스트 27개 모두 통과.
- AI/HTTP/실제 서명·체인/영속화 전체 테스트 119개 모두 통과, 건너뛴 테스트 없음.
- API 사용 후 별도 프로세스 복원, 관리자 승인·종결, 재시작 후 동일 요청 중복 방지 통과.
- 합본 증거: acceptance/combined-legacy-cleanup-regression.json.

이전 120개/30개와 개수가 다른 것은 구버전 성공 테스트를 제거·대체하고,
폐기 API와 중복 방지 테스트를 반영했기 때문입니다. 같은 테스트 목록으로 수를 비교한 것이 아닙니다.
이번 모델 응답은 재현용 고정 응답이며, 지갑 서명·RPC 검증·온체인 기록은 실제 실행했습니다.
Gemini 추출 프롬프트와 정책은 이 병합에서 변경하지 않았고 실제 모델을 재호출하지 않았습니다.

## 남은 경계

- 프론트 담당자의 최신 로컬 연결 코드가 아직 원격에 없어 화면 연동 확인은 대기.
- 실제 Uvicorn 재기동/다중 서버 환경 검증을 완료했다고 표시하지 않습니다.
- 이 백엔드는 Verification 조회 API를 제공하지만 AI 호출 자체를 비동기 작업으로
  전환한 구현은 아닙니다. 처리 중 화면 표시는 프론트와 별도로 맞춥니다.
- 기관 ProofAttestation / 담당자 매핑 / 관리자 승인·종결의 서명 구조는 유지합니다.
- 원격 공식 브랜치 반영은 강제 push 없이 정상 fast-forward 가능한 경우에만 수행합니다.
