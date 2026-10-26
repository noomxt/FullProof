# 공식 브랜치 연결 정리

기준: `final-mentor-v11 @7998973a84f72e7c96ddb7f295c00e81fb6643d8`. 이 커밋 이후 변경은 포함하지 않습니다.

## 경로 대응

| 화면 동작 | 실제 HTTP 요청 |
| --- | --- |
| 연결·기관·서명자·관리자 설정 | GET /api/v1/frontend/status |
| 사건 목록·상세 | GET /api/v1/frontend/cases, /cases/{case_id} |
| Claim 원문 고정 | POST /api/v1/cases/{case_id}/claims |
| AI 추출 | POST /api/v1/claims/{claim_id}/extract |
| 기관 서명 초안·기록 | POST /api/v1/proofs/drafts, /api/v1/proofs/anchor |
| 매핑 확인 | POST /api/v1/claims/{claim_id}/proof-mappings/{mapping_id}/confirm |
| 검증 시작 | POST /api/v1/verification-requests |
| 진행·결과 조회 | GET /api/v1/verification-requests/{verification_id} |
| 무결성 원문 조회 | GET /api/v1/verifications/{verification_id}/integrity-data |
| 관리자 승인·종결 | POST /api/v1/verifications/{id}/reviews, /api/v1/cases/{case_id}/close |

UI 내부의 `api('/api/v1/system/status')`와 `api('/api/v1/verifications', ...)`는 화면 공통 인터페이스입니다. `official.ts`가 위 실제 경로로 바꿉니다. 네트워크로 구 상태 경로를 보내지 않습니다. UI 내부의 결과 재조회도 요청 상태 API로 바꿉니다.

## Verification 요청

```json
{
  "claim": {"case_id":"CASE-1","claim_id":"CL-1","claim_version":1},
  "proofs": []
}
```

Proof가 있으면 서버에 등록된 원문 필드 목록을 보냅니다. 판정·서명 검증·정책 선택·입력 조합 해시는 모두 서버가 결정합니다. 프론트에서 Verification ID나 성공 서명을 만들어내지 않습니다.

서버의 `success/data/error` 응답을 해제합니다. 시작 응답의 HTTP 202는 완료가 아닙니다. `request_state`와 `phase`를 표시하며, PROCESSING·SUBMITTED는 최대 약 90초 동안 1초 간격으로 GET 조회합니다(각 HTTP 요청 시간은 별도). CONFIRMED이면서 같은 ID의 result와 거래 해시가 있어야 완료 결과로 반환합니다. FAILED·UNKNOWN·통신 오류는 실패 또는 확인 필요 안내로 남깁니다. 브라우저 표시는 서버 상태를 기반으로 하며 독립적인 영수증 대조는 무결성·거래 조회 기능에서 수행합니다.

알려진 요청 ID는 localStorage에 저장합니다. 새로고침 후에는 사건 조회 응답의 verification_requests를 표시하고 기존 요청 상태 조회로 이어갑니다. 저장된 요청의 조회가 실패해도 자동 POST하지 않습니다. 시작 응답을 잃어 ID를 받지 못한 경우 사건 새로고침으로 서버 요청을 확인할 수 있으며, 사용자의 명시적 재실행에서 같은 입력 재사용 여부는 공식 서버가 결정합니다. 프론트는 서버와 별도의 중복 방지 판정 캐시를 만들지 않습니다.

## 서명·권한

- Proof: 서버 초안의 EIP-712 typed_data를 등록 기관 지갑으로 서명합니다.
- 매핑: 공식 매핑 메시지를 personal_sign합니다.
- 관리자 확인·종결: 공식 RFC8785 JCS 메시지를 personal_sign합니다.
- 메시지를 UTF-8 hex로 전송하고 서명 전후 계정·체인 ID를 확인합니다.
- 화면 역할 선택은 인증이 아니며 가짜 Bearer 토큰을 HTTP에 보내지 않습니다.

## 공식 백엔드 소유권

main.py, frontend_server.py, mentor_support.py, AI, DB, 컨트랙트는 해당 공식 커밋 그대로입니다. 추가 서버 경로를 만들거나 덮어쓰지 않았습니다. SOURCE_MANIFEST.json에 Git blob 대조 결과가 있습니다. 기존 Team_Aligned에서 관찰한 응답 유실 후 중복 문제를 이 새 버전의 결함으로 재사용하지 않습니다. 공식 멘토 테스트의 거래 응답 유실 복구 확인을 다시 실행했습니다.

## 기존 팀 서버에 프론트만 연결

1. 같은 공식 커밋에서 기관·관리자·매핑 확인 지갑, RPC와 컨트랙트 설정을 맞춥니다.
2. 백엔드 디렉터리에서 `python -m uvicorn frontend_server:app --host 127.0.0.1 --port 8000`으로 실행합니다. main:app만 실행하면 프론트 전용 조회 경로가 없습니다.
3. frontend에서 `npm.cmd ci`, `npm.cmd run dev`를 실행합니다.
4. 다른 백엔드 주소는 frontend/.env.example을 참고하여 `VITE_BACKEND_TARGET`으로 Vite 프록시 대상, `VITE_API_BASE_URL`로 요청 접두 경로를 설정합니다.

전체 OpenAPI 스냅샷: fullproof-v1.1-openapi.json(공식 main), frontend-openapi.json(frontend_server 포함).

## 테마

상단 전환 버튼으로 라이트/다크를 선택합니다. 선택값은 `fullproof.theme`에만 저장합니다. `theme.ts`, `ThemeToggle.tsx`, `styles.css`에서 관리하며 서버 설정·지갑·API 모드와 독립적입니다. 첫 화면 로드 전에 저장된 테마를 적용해 흰색 화면이 잠깐 보이는 현상을 줄였습니다. 로고 파일은 수정하지 않았습니다.
