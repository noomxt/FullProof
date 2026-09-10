import json
import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from enum import Enum
from web3 import Web3
from dotenv import load_dotenv

# dotenv 파일 로드
load_dotenv()

# AI 엔진 함수 임포트
from ai_engine import (
    parse_claim_with_llm,
    verify_claim_vs_proof,
    evaluate_case_closure,
    approve_case_closure,
    get_family_progress_from_backend
)

app = FastAPI(title="Chain of Investigation API")

# 1. 로컬 블록체인 연결
w3 = Web3(Web3.HTTPProvider("http://127.0.0.1:8545"))

# 2. 배포된 스마트 컨트랙트 주소
CONTRACT_ADDRESS = "0x5FbDB2315678afecb367f032d93F642f64180aa3"

# 3. ABI 로드
ABI_PATH = os.path.join("artifacts", "contracts", "ChainOfInvestigation.sol", "ChainOfInvestigation.json")

try:
    with open(ABI_PATH, "r") as f:
        contract_json = json.load(f)
        contract_abi = contract_json["abi"]
    contract = w3.eth.contract(address=CONTRACT_ADDRESS, abi=contract_abi)
except Exception as e:
    print(f"⚠️ ABI 로드 실패: {e}")

# Enum & Data Schema
class VerificationStatus(int, Enum):
    PENDING = 0
    VERIFIED = 1
    MISMATCH = 2

class CreateCaseSchema(BaseModel):
    case_id: int

class RegisterFamilySchema(BaseModel):
    case_id: int
    family_wallet: str

class AddStepSchema(BaseModel):
    case_id: int
    step_name: str
    is_required: bool

class AnchorProofSchema(BaseModel):
    case_id: int
    step_id: int
    status: str
    reason: str
    result_hash: str

class VerifyStepSchema(BaseModel):
    case_id: int
    step_id: int
    raw_claim_text: str
    proof: dict
    evidence_deadline: str = "2026-12-31 23:59:59"

# ---------------------------------------------------------
# Utility Helper
# ---------------------------------------------------------
def map_ai_status_to_contract_enum(ai_status: str) -> int:
    """AI 검증 문자열 상태값을 블록체인 컨트랙트 Enum 숫자값으로 매핑"""
    if ai_status == "SUPPORTED":
        return VerificationStatus.VERIFIED.value
    elif ai_status == "CONTRADICTED":
        return VerificationStatus.MISMATCH.value
    else:
        return VerificationStatus.PENDING.value

# ---------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------

@app.get("/")
def read_root():
    return {
        "status": "Backend Active",
        "blockchain_connected": w3.is_connected(),
        "contract_address": CONTRACT_ADDRESS
    }

# [기능 1] 사건 생성
@app.post("/api/v1/cases")
def create_case(data: CreateCaseSchema):
    try:
        admin_account = w3.eth.accounts[0]
        tx_hash = contract.functions.createCase(data.case_id).transact({'from': admin_account})
        tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
        return {"result": "success", "case_id": data.case_id, "tx_hash": tx_hash.hex()}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# [기능 2] 수사 STEP 추가
@app.post("/api/v1/cases/steps")
def add_step(data: AddStepSchema):
    try:
        admin_account = w3.eth.accounts[0]
        tx_hash = contract.functions.addStep(data.case_id, data.step_name, data.is_required).transact({'from': admin_account})
        w3.eth.wait_for_transaction_receipt(tx_hash)
        return {"result": "success", "step_name": data.step_name}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# [민주 님 요청 2] 수사 STEP 전체 목록 조회 API (AI/유가족 연동용)
@app.get("/api/v1/cases/{case_id}/steps")
def get_case_steps(case_id: int):
    try:
        # 블록체인에서 step 데이터 읽기 (기본 구조 리턴)
        steps = []
        for i in range(10): # 최대 10개 조회 시도
            try:
                res = contract.functions.getStepInfoForFamily(case_id, i).call({'from': w3.eth.accounts[0]})

                if not res[0]:
                    break

                status_str = ["PENDING", "SUPPORTED", "CONTRADICTED"][res[2]]
                steps.append({
                    "step_id": i + 1,
                    "step_name": res[0],
                    "required": res[1],
                    "status": status_str
                })
            except Exception:
                break
        return {"case_id": case_id, "steps": steps}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# [민주 님 연동] AI 파싱 및 대조 검증 통합 엔드포인트
@app.post("/api/v1/cases/verify")
def verify_investigation_step(data: VerifyStepSchema):
    # 1. AI LLM 파싱
    claim = parse_claim_with_llm(data.raw_claim_text)
    # 2. Proof 대조 검증
    status, reason = verify_claim_vs_proof(claim, data.proof, data.evidence_deadline)
    return {
        "case_id": data.case_id,
        "step_id": data.step_id,
        "status": status,
        "reason": reason,
        "claim": claim
    }

# [민주 님 요청 1] AI 결과를 온체인 블록체인에 앵커링
@app.post("/api/v1/cases/anchor")
def anchor_proof(data: AnchorProofSchema):
    try:
        admin_account = w3.eth.accounts[0]
        enum_status = map_ai_status_to_contract_enum(data.status)
        
        # 해시 포맷 가공 (bytes32 규격 맞춤)
        proof_bytes = bytes.fromhex(data.result_hash[2:]) if data.result_hash.startswith("0x") else bytes.fromhex(data.result_hash)
        empty_claim = bytes(32)

        tx_hash = contract.functions.anchorProof(
            data.case_id,
            data.step_id - 1,
            empty_claim,
            proof_bytes,
            enum_status
        ).transact({'from': admin_account})
        
        w3.eth.wait_for_transaction_receipt(tx_hash)
        return {"result": "success", "status": data.status, "tx_hash": tx_hash.hex()}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# [기능 5] 유가족 진행률 대시보드 데이터 조회
@app.get("/api/v1/cases/{case_id}/family-progress")
def get_family_progress(case_id: int):
    return get_family_progress_from_backend(case_id)