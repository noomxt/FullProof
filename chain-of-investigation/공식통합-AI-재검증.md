# 공식 통합 019dd0b AI 재검증

대상: feature/integration-v1.1의 019dd0bd2d4a7aa8db0fd1eb11db709ecb3bbda1.
기존 시험용 브랜치에서 위 공식 커밋으로 fast-forward한 뒤 실행했습니다.
AI·백엔드·DB 운영 코드는 수정하지 않았습니다.

## 확인 항목

- 공식 전체 회귀: 120개 통과. 기존 API 사용 후 새 프로세스 복원·관리자 승인·종결 포함.
- 추가 AI 재시작 검증: test_ai_restart_revalidation.py의 5개 테스트 모두 통과.
  - 복원된 추출 결과를 API에서 읽을 때 원문·모델/프롬프트 정보·근거가 그대로 유지됨.
  - 저장된 추출을 읽는 요청에서 불필요한 모델 재호출이 발생하지 않음.
  - SUPPORTED / CONTRADICTED / Proof 없는 INSUFFICIENT를 새 Python 프로세스에서 재검증.
  - CONFIRMED 매핑이 있어도 CALL_REF가 없으면 INSUFFICIENT 유지.
  - 이전 판정은 변경하지 않고 새 verification_id로 재검증 결과를 저장·온체인 기록.
  - Claim 참조, Proof 참조/해시, 정책 해시, conflicts, missing_information, evidence_refs가 복원 전후 동일.
  - 추출 전 Claim만 저장한 경우도 새 프로세스에서 최초 추출·저장 후 검증 가능.

## 근거와 재현

acceptance/official-019dd0b-regression.json: 공식 120개 실행 중 백엔드/체인 시나리오 결과.
acceptance/official-ai-restart-revalidation.json: 추가 AI 재시작 검증 결과.

별도 로컬 Hardhat 노드(18545)와 임시 SQLite, 합성 Claim·기관 원본을 사용했습니다.
서명·RPC 검증·온체인 기록은 실제로 실행했습니다. 이번 회귀의 모델 응답은 재현용
주입 데이터입니다. 공식 커밋에서 AI 코드가 이전 검증 대비 변경되지 않았으므로
실제 Gemini 호출을 반복하지 않았습니다. 이전 실제 모델 검증을 이번 실행으로 표시하지 않습니다.

```text
FULLPROOF_CHAIN_INTEGRATION=1
FULLPROOF_TEST_REPORT=official-ai-restart-revalidation.json
python -m unittest test_ai_restart_revalidation -v
```

새 Python 프로세스 + FastAPI TestClient 검증입니다. 실제 Uvicorn 재기동,
다중 서버/worker 동시 쓰기, 프론트 UI 확인은 이 검증에 포함하지 않았습니다.
관리자 요청 nonce의 재시작 지속성 등 다른 담당 범위를 추가 검증했다고 주장하지 않습니다.
