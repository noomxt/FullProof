import json
import os
import hashlib
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from web3 import Web3
from eth_account.messages import encode_defunct
from dotenv import load_dotenv

load_dotenv()

from ai_engine import parse_claim_with_llm, verify_claim_vs_proof, get_family_progress_from_backend

app = FastAPI(title="FullProof API", version="1.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_origin_regex=r"https://.*\.github\.io",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

w3 = Web3(Web3.HTTPProvider("http://127.0.0.1:8545"))
CONTRACT_ADDRESS = "0x5FbDB2315678afecb367f032d93F642f64180aa3"
ABI_PATH = os.path.join("artifacts", "contracts", "ChainOfInvestigation.sol", "ChainOfInvestigation.json")

try:
    with open(ABI_PATH, "r") as f:
        contract_json = json.load(f)
        contract_abi = contract_json["abi"]
    contract = w3.eth.contract(address=CONTRACT_ADDRESS, abi=contract_abi)
except Exception as e:
    print(f"⚠️ ABI 로드 실패: {e}")

cases_db = {}

# [문제 3 해결] 4상태 온체인 Enum 매핑 (EXPIRING_SOON -> 3)
def map_ai_status_to_contract_enum(ai_status: str) -> int:
    status_map = {
        "PENDING": 0,
        "SUPPORTED": 1,
        "CONTRADICTED": 2,
        "EXPIRING_SOON": 3
    }
    return status_map.get(ai_status, 0)

def map_contract_enum_to_str(enum_val: int) -> str:
    reverse_map = {0: "PENDING", 1: "SUPPORTED", 2: "CONTRADICTED", 3: "EXPIRING_SOON"}
    return reverse_map.get(enum_val, "PENDING")

def get_bytes32_case_id(case_id_str: str) -> bytes:
    return w3.keccak(text=str(case_id_str))

# [문제 1 해결] Proof 원천기관 서명 검증 함수
def verify_proof_signature(proof: dict) -> bool:
    signature = proof.get("signature")
    issuer_address = proof.get("issuer_address")
    
    if not signature or not issuer_address:
        return False
    
    try:
        # 서명 대상 데이터 추출 (signature 제외)
        proof_data = {k: v for k, v in proof.items() if k != "signature"}
        message_str = json.dumps(proof_data, sort_keys=True)
        message = encode_defunct(text=message_str)
        
        recovered_address = w3.eth.account.recover_message(message, signature=signature)
        
        # 기관 권한 온체인 확인
        is_authorized = contract.functions.isAuthorizedAgency(recovered_address).call()
        return (recovered_address.lower() == issuer_address.lower()) and is_authorized
    except Exception:
        return False

# Pydantic Schemas
class CaseCreateSchema(BaseModel):
    case_id: str
    title: Optional[str] = "신규 수사 사건"

class StepCreateSchema(BaseModel):
    description: str

class VerifyRequestSchema(BaseModel):
    case_id: str
    step_id: int
    raw_claim_text: str
    proof: dict
    evidence_deadline: str = "2026-12-31 23:59:59"

# [문제 4 해결] 서버 가동 시 온체인 데이터 복구 (Event 로그 스캔)
@app.on_event("startup")
def sync_cases_from_blockchain():
    if not w3.is_connected():
        return
    try:
        case_created_events = contract.events.CaseCreated.get_logs(fromBlock=0)
        for event in case_created_events:
            case_bytes32 = event.args.caseId
            # 사건 정보 복구 로직
            onchain_case = contract.functions.cases(case_bytes32).call()
            case_id_str = case_bytes32.hex()
            
            steps = []
            step_count = onchain_case[4]
            for i in range(step_count):
                step_info = contract.functions.getStepInfo(case_bytes32, i).call()
                steps.append({
                    "step_id": i,
                    "description": step_info[0],
                    "proof_hash": step_info[1],
                    "status": map_contract_enum_to_str(step_info[2]),
                    "is_completed": step_info[3],
                    "tx_hash": event.transactionHash.hex()
                })
            
            cases_db[case_id_str] = {
                "case_id": case_id_str,
                "title": "복구된 사건",
                "is_closed": onchain_case[2],
                "close_reason": onchain_case[3],
                "step_count": step_count,
                "steps": steps,
                "tx_hash": event.transactionHash.hex()
            }
    except Exception as e:
        print(f"⚠️ 온체인 데이터 복구 실패: {e}")

@app.get("/api/v1/cases")
def get_all_cases():
    return list(cases_db.values())

@app.post("/api/v1/cases/verify")
def verify_and_anchor_step(data: VerifyRequestSchema):
    if data.case_id not in cases_db:
        raise HTTPException(status_code=404, detail="Case not found")
    
    case = cases_db[data.case_id]
    
    # [문제 2 해결] 서버 차원에서도 종결 사건 수정 차단
    if case.get("is_closed", False):
        raise HTTPException(status_code=400, detail="Cannot modify closed case")

    # [문제 1 해결] 서명 없는 증빙 제출 차단
    if not verify_proof_signature(data.proof):
        raise HTTPException(
            status_code=400, 
            detail="Invalid Proof: Missing or unauthorized agency digital signature"
        )

    try:
        claim = parse_claim_with_llm(data.raw_claim_text)
        ai_status, reason_text = verify_claim_vs_proof(claim, data.proof, data.evidence_deadline)

        proof_hash_str = "0x" + hashlib.sha256(json.dumps(data.proof).encode()).hexdigest()
        enum_status = map_ai_status_to_contract_enum(ai_status)

        admin_account = w3.eth.accounts[0]
        case_bytes32 = get_bytes32_case_id(data.case_id)

        # 스마트 컨트랙트 앵커링
        tx_hash = contract.functions.anchorProof(
            case_bytes32,
            data.step_id,
            proof_hash_str,
            enum_status
        ).transact({'from': admin_account})
        
        w3.eth.wait_for_transaction_receipt(tx_hash)

        # [문제 3 해결] 최신 앵커링 트랜잭션 해시 및 상태값(EXPIRING_SOON 포함) 정확히 업데이트
        target_step = case["steps"][data.step_id]
        target_step["proof_hash"] = proof_hash_str
        target_step["status"] = ai_status
        target_step["is_completed"] = (ai_status == "SUPPORTED")
        target_step["tx_hash"] = tx_hash.hex()

        return {
            "case_id": data.case_id,
            "step_id": data.step_id,
            "status": ai_status,
            "reason_code": f"RC_{ai_status}_VERIFIED",
            "reason_detail": reason_text,
            "proof_hash": proof_hash_str,
            "tx_hash": tx_hash.hex()
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))