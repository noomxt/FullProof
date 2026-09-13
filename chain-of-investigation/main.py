import json
import os
import hashlib
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from enum import Enum
from typing import List, Optional
from web3 import Web3
from dotenv import load_dotenv

# dotenv 로드
load_dotenv()

# AI 엔진 함수 임포트
from ai_engine import (
    parse_claim_with_llm,
    verify_claim_vs_proof,
    evaluate_case_closure,
    approve_case_closure,
    get_family_progress_from_backend
)

app = FastAPI(title="FullProof Chain of Investigation API", version="1.0.0")

# 4. CORS 설정 (localhost:3000 및 GitHub Pages 허용)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_origin_regex=r"https://.*\.github\.io",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 1. 로컬 블록체인 연결
w3 = Web3(Web3.HTTPProvider("http://127.0.0.1:8545"))

# 2. 배포된 스마트 컨트랙트 주소 및 ABI 로드
CONTRACT_ADDRESS = "0x5FbDB2315678afecb367f032d93F642f64180aa3"
ABI_PATH = os.path.join("artifacts", "contracts", "ChainOfInvestigation.sol", "ChainOfInvestigation.json")

try:
    with open(ABI_PATH, "r") as f:
        contract_json = json.load(f)
        contract_abi = contract_json["abi"]
    contract = w3.eth.contract(address=CONTRACT_ADDRESS, abi=contract_abi)
except Exception as e:
    print(f"⚠️ ABI 로드 경고: {e}")

# In-Memory 캐시 DB (사건 목록 조회 및 프론트엔드 대시보드 연동용)
cases_db = {}

# Utility Helpers
def get_bytes32_case_id(case_id_str: str) -> bytes:
    """문자열 사건 ID를 Solidity bytes32 keccak256 해시로 변환"""
    return w3.keccak(text=str(case_id_str))

def map_ai_status_to_contract_enum(ai_status: str) -> int:
    """AI 검증 상태를 스마트 컨트랙트 Status Enum(0:PENDING, 1:SUPPORTED, 2:CONTRADICTED)으로 매핑"""
    if ai_status == "SUPPORTED":
        return 1
    elif ai_status == "CONTRADICTED":
        return 2
    return 0

# --- Pydantic Data Schemas ---
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

# --- API Endpoints ---

@app.get("/")
def read_root():
    return {
        "status": "Backend Active",
        "blockchain_connected": w3.is_connected(),
        "contract_address": CONTRACT_ADDRESS
    }

# 1. 사건 목록 조회
@app.get("/api/v1/cases")
def get_all_cases():
    return list(cases_db.values())

# 5. 새 사건 생성 (스마트 컨트랙트 createCase 연동)
@app.post("/api/v1/cases", status_code=status.HTTP_201_CREATED)
def create_case(data: CaseCreateSchema):
    try:
        admin_account = w3.eth.accounts[0]
        case_bytes32 = get_bytes32_case_id(data.case_id)
        
        # 온체인 사건 생성 트랜잭션 전송
        tx_hash = contract.functions.createCase(case_bytes32).transact({'from': admin_account})
        w3.eth.wait_for_transaction_receipt(tx_hash)

        new_case = {
            "case_id": data.case_id,
            "title": data.title,
            "is_closed": False,
            "close_reason": "",
            "step_count": 0,
            "steps": [],
            "tx_hash": tx_hash.hex()
        }
        cases_db[data.case_id] = new_case
        return new_case
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# 2. 사건 상세 및 STEP 조회
@app.get("/api/v1/cases/{case_id}")
def get_case_detail(case_id: str):
    if case_id not in cases_db:
        raise HTTPException(status_code=404, detail="Case not found")
    return cases_db[case_id]

# 6. 수사 STEP 추가 (스마트 컨트랙트 addStep 연동)
@app.post("/api/v1/cases/{case_id}/steps")
def add_step(case_id: str, data: StepCreateSchema):
    if case_id not in cases_db:
        raise HTTPException(status_code=404, detail="Case not found")
    try:
        admin_account = w3.eth.accounts[0]
        case_bytes32 = get_bytes32_case_id(case_id)

        # 온체인 addStep 트랜잭션 전송
        tx_hash = contract.functions.addStep(case_bytes32, data.description).transact({'from': admin_account})
        w3.eth.wait_for_transaction_receipt(tx_hash)

        case = cases_db[case_id]
        new_step_id = len(case["steps"])
        new_step = {
            "step_id": new_step_id,
            "description": data.description,
            "proof_hash": "",
            "status": "PENDING",
            "is_completed": False,
            "tx_hash": tx_hash.hex()
        }
        case["steps"].append(new_step)
        case["step_count"] = len(case["steps"])
        return new_step
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# 7. AI 검증 및 온체인 앵커링 통합 처리 (reason_code & tx_hash 반환)
@app.post("/api/v1/cases/verify")
def verify_and_anchor_step(data: VerifyRequestSchema):
    if data.case_id not in cases_db:
        raise HTTPException(status_code=404, detail="Case not found")
    
    case = cases_db[data.case_id]
    if data.step_id >= len(case["steps"]):
        raise HTTPException(status_code=400, detail="Step index out of range")

    try:
        # 1. AI LLM 파싱 및 대조 검증
        claim = parse_claim_with_llm(data.raw_claim_text)
        ai_status, reason_text = verify_claim_vs_proof(claim, data.proof, data.evidence_deadline)

        # 2. 증거 해시 생성 및 규격 매핑
        proof_hash_str = "0x" + hashlib.sha256(json.dumps(data.proof).encode()).hexdigest()
        enum_status = map_ai_status_to_contract_enum(ai_status)
        reason_code = f"RC_{ai_status}_VERIFIED"

        # 3. 온체인 anchorProof 트랜잭션 수행
        admin_account = w3.eth.accounts[0]
        case_bytes32 = get_bytes32_case_id(data.case_id)

        tx_hash = contract.functions.anchorProof(
            case_bytes32,
            data.step_id,
            proof_hash_str,
            enum_status
        ).transact({'from': admin_account})
        
        w3.eth.wait_for_transaction_receipt(tx_hash)

        # DB 상태 업데이트
        target_step = case["steps"][data.step_id]
        target_step["proof_hash"] = proof_hash_str
        target_step["status"] = ai_status
        target_step["is_completed"] = (ai_status == "SUPPORTED")

        # 3, 8. reason_code 및 tx_hash 반환
        return {
            "case_id": data.case_id,
            "step_id": data.step_id,
            "status": ai_status,
            "reason_code": reason_code,
            "reason_detail": reason_text,
            "proof_hash": proof_hash_str,
            "tx_hash": tx_hash.hex()
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# [기능 5] 유가족 진행률 대시보드 데이터 조회
@app.get("/api/v1/cases/{case_id}/family-progress")
def get_family_progress(case_id: str):
    return get_family_progress_from_backend(case_id)