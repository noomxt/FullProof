import os
import json
import hashlib
import requests
from datetime import datetime, timedelta
from typing import Dict, Any, List, Tuple
from pydantic import BaseModel
from openai import OpenAI

# ==========================================
# 0. 백엔드 및 AI API 설정 (박지수 님 서버 연동)
# ==========================================
BACKEND_BASE_URL = "http://127.0.0.1:8000/api/v1/cases"
BACKEND_ANCHOR_URL = f"{BACKEND_BASE_URL}/anchor"
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY", "your-api-key"))

# ==========================================
# [기능 2] 수사 가이드라인(Policy Pack) 판단 엔진
# ==========================================
POLICY_TEMPLATES = {
    "MISSING_PERSON": [
        {"step_id": 1, "step_name": "통신사 위치 조회", "time_limit_hours": 24, "required": True},
        {"step_id": 2, "step_name": "마지막 확인지 CCTV 확보", "time_limit_hours": 24, "required": True},
        {"step_id": 3, "step_name": "보호자 및 주변인 통화 내역 확인", "time_limit_hours": 72, "required": True}
    ]
}

def get_guidelines_from_policy_pack(case_type: str = "MISSING_PERSON") -> List[Dict[str, Any]]:
    """사건 유형에 맞는 표준 수사 가이드라인(필수 STEP 및 기한) 산출"""
    now = datetime.now()
    template = POLICY_TEMPLATES.get(case_type, [])
    
    guidelines = []
    for step in template:
        deadline = now + timedelta(hours=step["time_limit_hours"])
        guidelines.append({
            "step_id": step["step_id"],
            "step_name": step["step_name"],
            "required": step["required"],
            "deadline": deadline.strftime("%Y-%m-%d %H:%M:%S")
        })
    return guidelines

# ==========================================
# [기능 1] 수사 기록(Claim) 자연어 파싱 및 일치 여부 대조
# ==========================================
class StructuredClaimSchema(BaseModel):
    action_type: str    # PHONE_CALL, CCTV_CHECK, LOCATION_TRACE
    target_id: str      # 대상자 식별자
    claimed_time: str   # YYYY-MM-DD HH:MM:SS
    status_claim: str   # SUCCESS, FAIL

def parse_claim_with_llm(raw_claim_text: str) -> Dict[str, Any]:
    try:
        completion = client.beta.chat.completions.parse(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "수사 기록의 자연어 문장에서 핵심 사실조건(Target, Time, Action)을 추출하세요."},
                {"role": "user", "content": raw_claim_text}
            ],
            response_format=StructuredClaimSchema,
        )
        data = completion.choices[0].message.parsed
        return {
            "raw_text": raw_claim_text,
            "action_type": data.action_type,
            "target_id": data.target_id,
            "claimed_time": data.claimed_time,
            "status_claim": data.status_claim
        }
    except Exception as e:
        return {
            "raw_text": raw_claim_text,
            "action_type": "UNKNOWN",
            "target_id": "UNKNOWN",
            "claimed_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "status_claim": "FAIL"
        }

def verify_claim_vs_proof(claim: Dict[str, Any], proof: Dict[str, Any], evidence_deadline: str) -> Tuple[str, str]:
    """경찰이 입력한 수사와 원천기관 Proof 교차검증 (일치: SUPPORTED / 불일치: CONTRADICTED)"""
    now = datetime.now()
    deadline = datetime.strptime(evidence_deadline, "%Y-%m-%d %H:%M:%S")

    if not proof and (deadline - now).total_seconds() <= 86400:
        return "EXPIRING_SOON", "🔴 CCTV/시한성 증거 삭제 임박 (24시간 이내 확보 필요)"

    if not proof or not proof.get("is_issued"):
        return "INSUFFICIENT", "원천기관의 서명된 Proof가 미확보 상태입니다."

    if claim.get("target_id") != proof.get("target_id"):
        return "CONTRADICTED", "❌ 대상자 ID(Target ID) 불일치 - 실제 수사내역과 다름"
    
    if claim.get("action_type") != proof.get("action_type"):
        return "CONTRADICTED", "❌ 수사 행위 유형(Action Type) 불일치 - 실제 수사내역과 다름"

    claim_dt = datetime.strptime(claim["claimed_time"], "%Y-%m-%d %H:%M:%S")
    proof_dt = datetime.strptime(proof["timestamp"], "%Y-%m-%d %H:%M:%S")
    if abs((claim_dt - proof_dt).total_seconds()) > 900:
        return "CONTRADICTED", "❌ 주장 시점과 원천기관 기록 시간 불일치 (15분 이상 차이)"

    if claim.get("status_claim") == "SUCCESS" and not proof.get("success"):
        return "CONTRADICTED", "❌ 실제 기관 접속/통화 성공 여부 불일치"

    return "SUPPORTED", "⭕ 원천기관 Proof와 수사기록 완벽 일치 (검증 완료)"

# ==========================================
# [기능 3 & 4] 종결 승인 통제 규칙 (가이드라인 미충족 시 거부 + 상급자 2명 승인)
# ==========================================
def evaluate_case_closure(case_id: int, current_steps_status: List[Dict[str, Any]]) -> Tuple[str, str]:
    """[기능 3] 가이드라인 필수 항목 중 미완료(INSUFFICIENT)나 불일치(CONTRADICTED)가 존재하면 종결 거부"""
    for step in current_steps_status:
        if step.get("required") and step.get("status") != "SUPPORTED":
            return "REJECTED", f"🚫 수사 종결 불가: 필수 수사단계 [{step.get('step_name')}] 미충족 (상태: {step.get('status')})"
    return "PENDING_APPROVAL", "✅ 가이드라인 충족 완료. 상급 경찰 2명의 종결 승인이 필요합니다."

def approve_case_closure(case_id: int, supervisor_signatures: List[str]) -> Tuple[str, str]:
    """[기능 4] 상급 경찰 2명 승인 검증 멀티식(Multi-Sig) 로직"""
    if len(supervisor_signatures) < 2:
        return "APPROVAL_FAILED", f"🚫 승인 실패: 상급 경찰 승인 서명이 부족합니다. (현재 {len(supervisor_signatures)}/2명)"
    return "CLOSED", f"🎉 수사 최종 종결 승인 완료 (승인 상급자: {', '.join(supervisor_signatures)})"

# ==========================================
# [기능 5] 유가족 대략적 진행 현황 창구 (%)
# ==========================================
def get_family_progress_from_backend(case_id: int) -> Dict[str, Any]:
    """유가족용 창구: 정밀 수사 기밀은 은폐하고 대략적인 진행률(%) 및 가공 상태 출력"""
    url = f"{BACKEND_BASE_URL}/{case_id}/steps"
    try:
        response = requests.get(url)
        response.raise_for_status()
        case_steps = response.json().get("steps", [])
    except Exception:
        # 백엔드 연결 전 응답 규격 예시
        case_steps = []

    total_steps = len(case_steps) if case_steps else 3
    completed_weight = 0.0
    family_steps = []

    for step in case_steps:
        status = step.get("status", "INSUFFICIENT")
        if status == "SUPPORTED":
            w, disp = 1.0, "확인 완료"
        elif status in ["EXPIRING_SOON", "PENDING"]:
            w, disp = 0.5, "진행 중"
        else:
            w, disp = 0.0, "확인 예정"

        completed_weight += w
        family_steps.append({
            "step_name": step.get("step_name"),
            "progress_percent": int(w * 100),
            "display_status": disp
        })

    overall_percent = int((completed_weight / total_steps) * 100) if total_steps > 0 else 0
    return {
        "overall_progress_percent": overall_percent,
        "progress_text": f"전체 수사 절차 중 {overall_percent}% 확인 완료",
        "steps": family_steps
    }

# ==========================================
# 온체인 블록체인 앵커링 전송
# ==========================================
def anchor_to_blockchain(case_id: int, step_id: int, status: str, reason: str, claim: dict, proof: dict):
    raw_payload = json.dumps({"claim": claim, "proof": proof}, sort_keys=True).encode()
    proof_hash = "0x" + hashlib.sha256(raw_payload).hexdigest()

    body = {
        "case_id": case_id,
        "step_id": step_id,
        "status": status,
        "reason": reason,
        "result_hash": proof_hash
    }

    try:
        res = requests.post(BACKEND_ANCHOR_URL, json=body)
        res.raise_for_status()
        return res.json()
    except Exception:
        return {"status": "ANCHORED_LOCALLY", "hash": proof_hash}