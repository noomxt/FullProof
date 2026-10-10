"""FullProof API — upgraded ChainOfInvestigation integration.

Local demonstration only. Proofs must be signed externally by registered agency
signers; this server never fabricates an agency signature.
"""
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from web3 import Web3

from database import (
    init_db,
    save_case,
    load_cases,
    save_checkpoint,
    load_checkpoint,
    load_latest_case_checkpoint,
    list_case_checkpoints,
    save_proof_result_atomic,
)

from eth_account.messages import encode_typed_data

load_dotenv()
try:
    from ai_engine import parse_claim_with_llm, verify_claim_vs_proof, get_family_progress_from_backend
    AI_AVAILABLE = True
except ImportError:
    AI_AVAILABLE = False
    def get_family_progress_from_backend(case_id):
        return {"case_id": case_id, "status": "UNAVAILABLE", "message": "AI module unavailable"}

app = FastAPI(title="FullProof API", version="2.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:5500", "http://127.0.0.1:5500",], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
ROOT = Path(__file__).resolve().parent
ABI_PATH = ROOT / "artifacts/contracts/ChainOfInvestigation.sol/ChainOfInvestigation.json"
w3 = Web3(Web3.HTTPProvider(os.getenv("RPC_URL", "http://127.0.0.1:8545")))
CONTRACT_ADDRESS = os.getenv("CONTRACT_ADDRESS", "")
contract = None
if ABI_PATH.exists() and CONTRACT_ADDRESS:
    with ABI_PATH.open(encoding="utf-8") as f:
        contract = w3.eth.contract(address=Web3.to_checksum_address(CONTRACT_ADDRESS), abi=json.load(f)["abi"])

STATUS = {"PENDING": 0, "VERIFIED": 1, "SUPPORTED": 1, "MISMATCH": 2, "CONTRADICTED": 2, "EXPIRING_SOON": 3}
STATUS_REVERSE = {0: "PENDING", 1: "VERIFIED", 2: "MISMATCH", 3: "EXPIRING_SOON"}
PROOF_TYPES = {"Proof": [
    {"name": "caseId", "type": "uint256"}, {"name": "stepId", "type": "uint256"},
    {"name": "claimHash", "type": "bytes32"}, {"name": "proofHash", "type": "bytes32"},
    {"name": "result", "type": "uint8"}, {"name": "evidenceTimestamp", "type": "uint64"},
    {"name": "nonce", "type": "uint256"}, {"name": "deadline", "type": "uint64"},
    {"name": "agency", "type": "address"},
]}

# SQLite 데이터베이스 초기화
init_db()

# 저장된 사건 및 수사 단계 불러오기
cases_db = load_cases()


def require_chain():
    if not contract or not w3.is_connected() or not w3.eth.get_code(contract.address):
        raise HTTPException(503, "Blockchain unavailable, contract not deployed, or ABI/address not configured")

def sender():
    accounts = w3.eth.accounts
    if not accounts:
        raise HTTPException(503, "No unlocked local transaction account available")
    return accounts[0]

def confirmed(tx):
    receipt = w3.eth.wait_for_transaction_receipt(tx, timeout=120)
    if receipt.status != 1:
        raise HTTPException(400, "Blockchain transaction reverted")
    return tx.hex()

def case_uint(case_id: str):
    return int(case_id) if case_id.isdigit() else int(hashlib.sha256(case_id.encode()).hexdigest(), 16)

def canonical_hash(obj):
    return Web3.keccak(text=json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str))

def parse_timestamp(value):
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return int(datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=timezone.utc).timestamp()) if "+" not in value and "Z" not in value else int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp())
    raise ValueError("Timestamp must be Unix seconds or ISO8601")

def validate_proof(request, signature):
    require_chain()
    agency = Web3.to_checksum_address(request["agency"])
    if not contract.functions.isAuthorizedAgency(agency).call():
        raise ValueError("Agency is not authorized")
    if int(request["deadline"]) <= w3.eth.get_block("latest")["timestamp"]:
        raise ValueError("Signature expired")
    if int(request["nonce"]) != contract.functions.agencyNonces(agency).call():
        raise ValueError("Invalid or used nonce")
    domain = {"name": "FullProof", "version": "1", "chainId": w3.eth.chain_id, "verifyingContract": contract.address}
    message = encode_typed_data(domain_data=domain, message_types=PROOF_TYPES, message_data=request)
    recovered = w3.eth.account.recover_message(message, signature=signature)
    # The contract checks whether recovered is the agency's authorized signer.
    onchain_recovered = contract.functions.recoverProofSigner(tuple(request[k] for k in ["caseId", "stepId", "claimHash", "proofHash", "result", "evidenceTimestamp", "nonce", "deadline", "agency"]), signature).call()
    if recovered.lower() != onchain_recovered.lower():
        raise ValueError("Signature recovery mismatch")

    # 등록된 기관의 공식 서명자와 실제 서명자를 비교
    agency_info = contract.functions.agencies(agency).call()

    registered_signer = agency_info[2]

    if recovered.lower() != registered_signer.lower():
        raise ValueError(
            "Signature is not from the registered agency signer"
        )
    return recovered

class CaseCreateSchema(BaseModel):
    case_id: str
    title: str = "신규 수사 사건"

class StepCreateSchema(BaseModel):
    step_name: str
    is_required: bool = True

class VerifyRequestSchema(BaseModel):
    case_id: str
    step_id: int = Field(ge=0)
    raw_claim_text: str
    proof: dict
    evidence_deadline: str = "2026-12-31 23:59:59"
    agency: str
    signature: str
    nonce: int = Field(ge=0)
    deadline: int = Field(gt=0)
    evidence_timestamp: int = Field(ge=0)


class AnchorProofSchema(BaseModel):
    case_id: str
    step_id: int = Field(ge=0)

    claim_text: str
    proof_text: str

    agency: str
    claim_hash: str
    proof_hash: str

    result: int = Field(ge=0, le=3)
    evidence_timestamp: int = Field(ge=0)
    nonce: int = Field(ge=0)
    deadline: int = Field(gt=0)

    signature: str


class RecoverProofSchema(BaseModel):
    tx_hash: str



class CloseCaseSchema(BaseModel):
    reason: str = "수사 완료"


@app.get("/api/v1/cases/{case_id}/chain-status")
def get_case_chain_status(case_id: str):
    # SQLite에 저장된 사건 확인
    local_case = cases_db.get(case_id)

    # 블록체인 연결 및 컨트랙트 확인
    require_chain()

    try:
        onchain_case = contract.functions.cases(
            case_uint(case_id)
        ).call()

        # CaseInfo의 exists 필드
        onchain_exists = bool(onchain_case[3])

        # 온체인 단계 개수
        onchain_step_count = (
            int(onchain_case[2]) if onchain_exists else 0
        )

        local_exists = local_case is not None
        local_step_count = (
            len(local_case["steps"]) if local_exists else 0
        )

        # 사건 존재 여부와 단계 개수 비교
        is_synced = (
            local_exists == onchain_exists
            and (
                not local_exists
                or local_step_count == onchain_step_count
            )
        )

        if local_exists and not onchain_exists:
            message = "SQLite에만 사건이 존재합니다. 로컬 체인 초기화 여부를 확인하세요."
        elif not local_exists and onchain_exists:
            message = "블록체인에만 사건이 존재합니다. SQLite 복구가 필요합니다."
        elif not local_exists and not onchain_exists:
            message = "양쪽 모두 사건이 존재하지 않습니다."
        elif not is_synced:
            message = "사건은 양쪽에 있지만 수사 단계 개수가 다릅니다."
        else:
            message = "사건 존재 여부와 수사 단계 개수가 일치합니다."

        return {
            "case_id": case_id,
            "sqlite": {
                "exists": local_exists,
                "step_count": local_step_count
            },
            "blockchain": {
                "exists": onchain_exists,
                "step_count": onchain_step_count
            },
            "is_synced": is_synced,
            "message": message
        }

    except Exception as e:
        raise HTTPException(
            400,
            f"Chain status check failed: {e}"
        )


@app.get("/api/v1/cases")
def get_all_cases():
    return list(cases_db.values())

@app.post("/api/v1/cases", status_code=status.HTTP_201_CREATED)
def create_case(data: CaseCreateSchema):
    require_chain()
    if data.case_id in cases_db:
        raise HTTPException(400, "Case already exists")
    try:
        tx = confirmed(contract.functions.createCase(case_uint(data.case_id)).transact({"from": sender()}))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(400, f"On-chain createCase failed: {e}")
    record = {"case_id": data.case_id, "title": data.title, "is_closed": False, "close_reason": "", "step_count": 0, "steps": [], "tx_hash": tx}
    cases_db[data.case_id] = record
    save_case(record)
    return record

@app.get("/api/v1/cases/{case_id}")
def get_case_detail(case_id: str):
    if case_id not in cases_db:
        raise HTTPException(404, "Case not found")
    return cases_db[case_id]

@app.post("/api/v1/cases/{case_id}/steps")
def add_case_step(case_id: str, data: StepCreateSchema):
    require_chain()
    case = cases_db.get(case_id)
    if not case:
        raise HTTPException(404, "Case not found")
    if case["is_closed"]:
        raise HTTPException(400, "Cannot modify closed case")
    try:
        tx = confirmed(contract.functions.addStep(case_uint(case_id), data.step_name, data.is_required).transact({"from": sender()}))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(400, f"On-chain addStep failed: {e}")
    step = {"step_id": len(case["steps"]), "step_name": data.step_name, "claim_hash": "0x" + "00" * 32, "proof_hash": "0x" + "00" * 32, "status": "PENDING", "is_completed": False, "is_required": data.is_required, "tx_hash": tx}
    case["steps"].append(step)
    case["step_count"] = len(case["steps"])
    save_case(case)
    return step

@app.post("/api/v1/cases/verify")
def verify_and_anchor_step(data: VerifyRequestSchema):
    require_chain()
    case = cases_db.get(data.case_id)
    if not case:
        raise HTTPException(404, "Case not found")
    if case["is_closed"]:
        raise HTTPException(400, "Cannot modify closed case")
    if data.step_id >= len(case["steps"]):
        raise HTTPException(400, "Step index out of bounds")
    if not AI_AVAILABLE:
        raise HTTPException(503, "AI engine missing: cannot automatically mark proof VERIFIED")
    try:
        claim = parse_claim_with_llm(data.raw_claim_text)
        ai_status, reason = verify_claim_vs_proof(claim, data.proof, data.evidence_deadline)
        result = STATUS.get(str(ai_status).upper())
        if result is None:
            raise ValueError("Unknown AI verification status")
        # Signed payload must match the exact canonical bytes the agency signed.
        claim_hash, proof_hash = canonical_hash(claim), canonical_hash(data.proof)
        request = {"caseId": case_uint(data.case_id), "stepId": data.step_id, "claimHash": claim_hash, "proofHash": proof_hash, "result": result, "evidenceTimestamp": data.evidence_timestamp, "nonce": data.nonce, "deadline": data.deadline, "agency": Web3.to_checksum_address(data.agency)}
        recovered = validate_proof(request, data.signature)
        tx = confirmed(contract.functions.anchorProof(request["caseId"], request["stepId"], claim_hash, proof_hash, result, data.evidence_timestamp, data.deadline, data.nonce, request["agency"], data.signature).transact({"from": sender()}))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(400, f"Proof validation/anchoring failed: {e}")
    step = case["steps"][data.step_id]
    step.update({"claim_hash": Web3.to_hex(claim_hash), "proof_hash": Web3.to_hex(proof_hash), "status": STATUS_REVERSE[result], "is_completed": result == 1, "tx_hash": tx})
    return {"case_id": data.case_id, "step_id": data.step_id, "status": STATUS_REVERSE[result], "reason_detail": reason, "claim_hash": step["claim_hash"], "proof_hash": step["proof_hash"], "signer": recovered, "tx_hash": tx}


@app.post("/api/v1/cases/proofs/anchor")
def anchor_signed_proof(data: AnchorProofSchema):
    require_chain()

    # 1. 사건과 수사 단계 확인
    case = cases_db.get(data.case_id)

    if not case:
        raise HTTPException(404, "Case not found")

    if case["is_closed"]:
        raise HTTPException(400, "Cannot modify closed case")

    if data.step_id >= len(case["steps"]):
        raise HTTPException(400, "Step index out of bounds")
    
    # SQLite와 현재 블록체인 사건 상태 비교
    try:
        onchain_case = contract.functions.cases(
            case_uint(data.case_id)
        ).call()

        onchain_exists = bool(onchain_case[3])
        onchain_step_count = int(onchain_case[2])

        if not onchain_exists:
            raise HTTPException(
                409,
                "SQLite에는 사건이 있지만 블록체인에는 없습니다. 체인 초기화 여부를 확인하세요."
            )

        if onchain_step_count != len(case["steps"]):
            raise HTTPException(
                409,
                "SQLite와 블록체인의 수사 단계 개수가 일치하지 않습니다."
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            503,
            f"On-chain case status check failed: {e}"
        )



    
    
    # 사건별 최신 체크포인트 자동 조회
    checkpoint_id = f"CASE_{data.case_id}_LATEST"
    checkpoint = load_latest_case_checkpoint(data.case_id)

    if checkpoint is not None:
        checkpoint_result = check_blockchain_checkpoint(
            checkpoint_id
        )

        if not checkpoint_result["is_valid"]:
            raise HTTPException(
                status_code=409,
                detail=(
                    "블록체인 체크포인트가 일치하지 않습니다. "
                    "Proof 기록이 차단되었습니다. "
                    + checkpoint_result["message"]
                )
            )
    else:
        # 기존 Proof가 있는데 체크포인트가 없으면 기록 차단
        history_count = contract.functions.getProofHistoryLength(
            case_uint(data.case_id),
            data.step_id
        ).call()

        if history_count > 0:
            raise HTTPException(
                status_code=409,
                detail=(
                    "기존 Proof 이력이 있지만 사건별 체크포인트가 없습니다. "
                    "기록을 중단하고 체크포인트 상태를 확인하세요."
                )
            )


    # 2. AI 연동 전에는 PENDING만 허용
    if data.result != STATUS["PENDING"]:
        raise HTTPException(
            400,
            "AI verification is not connected. Only PENDING is allowed"
        )

    try:
        
        # 3. 전달받은 해시 형식 확인
        claim_hash = bytes.fromhex(data.claim_hash.removeprefix("0x"))
        proof_hash = bytes.fromhex(data.proof_hash.removeprefix("0x"))

        if len(claim_hash) != 32 or len(proof_hash) != 32:
            raise ValueError("Claim/Proof hashes must be 32 bytes")

        # 4. 원본 텍스트에서 SHA-256 해시 직접 계산
        expected_claim_hash = hashlib.sha256(
            data.claim_text.encode("utf-8")
        ).digest()

        expected_proof_hash = hashlib.sha256(
            data.proof_text.encode("utf-8")
        ).digest()

        # 5. 원본 데이터와 전달된 해시 비교
        if claim_hash != expected_claim_hash:
            raise ValueError(
                "Claim hash mismatch: original text does not match"
            )

        if proof_hash != expected_proof_hash:
            raise ValueError(
                "Proof hash mismatch: original text does not match"
            )


        # 4. EIP-712 서명 메시지 재구성
        request = {
            "caseId": case_uint(data.case_id),
            "stepId": data.step_id,
            "claimHash": claim_hash,
            "proofHash": proof_hash,
            "result": data.result,
            "evidenceTimestamp": data.evidence_timestamp,
            "nonce": data.nonce,
            "deadline": data.deadline,
            "agency": Web3.to_checksum_address(data.agency)
        }

        # 5. 기관 권한, nonce, 만료시간, 전자서명 확인
        recovered = validate_proof(request, data.signature)

        # 6. 스마트 컨트랙트에 전달할 인자
        args = (
            request["caseId"],
            request["stepId"],
            claim_hash,
            proof_hash,
            data.result,
            data.evidence_timestamp,
            data.deadline,
            data.nonce,
            request["agency"],
            data.signature
        )

        # 7. 실제 전송 전에 컨트랙트 검증
        contract.functions.anchorProof(*args).call({"from": sender()})

        # 8. 블록체인에 Proof 기록
        tx = confirmed(
            contract.functions.anchorProof(*args).transact(
                {"from": sender()}
            )
        )
        
        # 성공한 Proof 트랜잭션의 블록 정보 조회
        receipt = w3.eth.get_transaction_receipt(tx)

        if receipt["status"] != 1:
            raise ValueError("Proof transaction failed")

        if (
            not receipt["to"]
            or receipt["to"].lower() != contract.address.lower()
        ):
            raise ValueError("Proof transaction contract mismatch")

        
        # 현재 수사 단계의 Proof History 개수 조회
        proof_count = contract.functions.getProofHistoryLength(
            case_uint(data.case_id),
            data.step_id
        ).call()

        # 새 체크포인트 정보
        checkpoint_data = {
            "chain_id": w3.eth.chain_id,
            "contract_address": contract.address,
            "block_number": receipt["blockNumber"],
            "block_hash": receipt["blockHash"].hex(),
            "tx_hash": receipt["transactionHash"].hex()
        }

        # 1. Proof별 체크포인트 이력 보존
        history_checkpoint = {
            **checkpoint_data,
            "checkpoint_id": (
                f"CASE_{data.case_id}_STEP_{data.step_id}"
                f"_PROOF_{proof_count}"
            )
        }


        # 2. 해당 사건의 최신 체크포인트 갱신
        latest_checkpoint = {
            **checkpoint_data,
            "checkpoint_id": f"CASE_{data.case_id}_LATEST"
        }




        # 9. 온체인 기록 개수 확인
        history_count = contract.functions.getProofHistoryLength(
            request["caseId"], request["stepId"]
        ).call()

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            400,
            f"Proof anchoring failed: {e}"
        )

    
    # 10. 블록체인 기록 후 로컬 API 상태 갱신
    step = case["steps"][data.step_id]

    step.update({
        "claim_hash": data.claim_hash,
        "proof_hash": data.proof_hash,
        "status": "PENDING",
        "is_completed": False,
        "tx_hash": tx
    })

    # SQLite 통합 저장
    try:
        save_proof_result_atomic(
            case,
            history_checkpoint,
            latest_checkpoint
        )

    except Exception as e:
        # DB 저장 실패 시 블록체인 기록은 이미 완료된 상태
        raise HTTPException(
            status_code=503,
            detail={
                "message": "블록체인 Proof 기록은 성공했지만 SQLite 저장에 실패했습니다.",
                "blockchain_status": "SUCCESS",
                "database_status": "FAILED",
                "tx_hash": tx,
                "case_id": data.case_id,
                "step_id": data.step_id,
                "recovery_required": True,
                "error": str(e)
            }
        )


    return {
        "message": "Signed Proof anchored successfully",
        "case_id": data.case_id,
        "step_id": data.step_id,
        "status": "PENDING",
        "signer": recovered,
        "tx_hash": tx,
        "proof_history_count": history_count
    }


@app.post("/api/v1/cases/{case_id}/steps/{step_id}/sync")
def sync_step_from_blockchain(case_id: str, step_id: int):
    require_chain()

    case = cases_db.get(case_id)
    if not case:
        raise HTTPException(404, "Case not found in SQLite")

    if step_id < 0 or step_id >= len(case["steps"]):
        raise HTTPException(400, "Invalid step ID")

    try:
        cid = case_uint(case_id)

        count = contract.functions.getProofHistoryLength(
            cid, step_id
        ).call()

        if count == 0:
            raise HTTPException(
                404, "No on-chain Proof history for this step"
            )

        # 최신 Proof 이력 조회
        record = contract.functions.getProofRecord(
            cid, step_id, count - 1
        ).call()

        proof_id = record[0]
        claim_hash = Web3.to_hex(record[3])
        proof_hash = Web3.to_hex(record[4])
        result = record[5]

        if result not in STATUS_REVERSE:
            raise ValueError("Unknown on-chain verification status")

        step = case["steps"][step_id]
        step.update({
            "claim_hash": claim_hash,
            "proof_hash": proof_hash,
            "status": STATUS_REVERSE[result],
            "is_completed": result == STATUS["VERIFIED"]
        })

        # SQLite 영구 저장
        save_case(case)

        return {
            "message": "SQLite synchronized with on-chain Proof",
            "case_id": case_id,
            "step_id": step_id,
            "proof_id": proof_id,
            "proof_history_count": count,
            "claim_hash": claim_hash,
            "proof_hash": proof_hash,
            "status": STATUS_REVERSE[result]
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            400,
            f"Blockchain synchronization failed: {e}"
        )

@app.get("/api/v1/cases/{case_id}/steps/{step_id}/proof-history")
def proof_history(case_id: str, step_id: int):
    require_chain()
    if step_id < 0:
        raise HTTPException(400, "Invalid step ID")
    try:
        cid = case_uint(case_id)
        count = contract.functions.getProofHistoryLength(cid, step_id).call()
        result = []
        for i in range(count):
            record = contract.functions.getProofRecord(cid, step_id, i).call()
            result.append({"index": i, "raw_record": [Web3.to_hex(v) if isinstance(v, bytes) else v for v in record]})
        return {"case_id": case_id, "step_id": step_id, "count": count, "history": result}
    except Exception as e:
        raise HTTPException(400, f"Proof history unavailable: {e}")

@app.get("/api/v1/cases/{case_id}/family-progress")
def get_family_progress(case_id: str):
    if case_id not in cases_db:
        raise HTTPException(404, "Case not found")
    return get_family_progress_from_backend(case_id)

@app.post("/api/v1/cases/{case_id}/close")
def close_case_endpoint(case_id: str, body: CloseCaseSchema):
    require_chain()
    case = cases_db.get(case_id)
    if not case:
        raise HTTPException(404, "Case not found")
    if case["is_closed"]:
        raise HTTPException(400, "Case is already closed")
    try:
        tx = confirmed(contract.functions.closeCase(case_uint(case_id), body.reason).transact({"from": sender()}))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(400, f"On-chain closeCase failed: {e}")
    case["is_closed"] = True
    case["close_reason"] = body.reason
    save_case(case)
    return {"status": "SUCCESS", "message": f"Case {case_id} closed successfully", "tx_hash": tx}


@app.get("/api/v1/blockchain/checkpoints/{checkpoint_id}")
def check_blockchain_checkpoint(checkpoint_id: str):
    require_chain()

    # 1. SQLite에서 저장된 체크포인트 조회
    checkpoint = load_checkpoint(checkpoint_id)

    if checkpoint is None:
        raise HTTPException(
            404,
            "Checkpoint not found in SQLite"
        )

    try:
        # 2. 현재 연결된 블록체인 정보 조회
        current_chain_id = w3.eth.chain_id
        current_contract = contract.address

        # 3. 체인 ID 및 컨트랙트 주소 비교
        if (
            current_chain_id != checkpoint["chain_id"]
            or current_contract.lower()
            != checkpoint["contract_address"].lower()
        ):
            return {
                "checkpoint_id": checkpoint_id,
                "is_valid": False,
                "message": "체인 ID 또는 컨트랙트 주소가 다릅니다."
            }

        # 4. 저장된 블록 번호로 현재 체인 조회
        if w3.eth.block_number < checkpoint["block_number"]:
            return {
                "checkpoint_id": checkpoint_id,
                "is_valid": False,
                "message": "현재 체인에 체크포인트 블록이 없습니다."
            }

        block = w3.eth.get_block(
            checkpoint["block_number"]
        )

        current_block_hash = block["hash"].hex()

        # 5. 블록 해시 비교
        if (
            current_block_hash.lower()
            != checkpoint["block_hash"].lower()
        ):
            return {
                "checkpoint_id": checkpoint_id,
                "is_valid": False,
                "message": "블록 해시가 일치하지 않습니다."
            }

        # 6. 저장된 트랜잭션 확인
        receipt = w3.eth.get_transaction_receipt(
            checkpoint["tx_hash"]
        )

        if (
            receipt["status"] != 1
            or receipt["blockNumber"] != checkpoint["block_number"]
            or receipt["blockHash"].hex().lower()
            != checkpoint["block_hash"].lower()
            or not receipt["to"]
            or receipt["to"].lower()
            != checkpoint["contract_address"].lower()
        ):
            return {
                "checkpoint_id": checkpoint_id,
                "is_valid": False,
                "message": "트랜잭션 기록이 체크포인트와 일치하지 않습니다."
            }

        return {
            "checkpoint_id": checkpoint_id,
            "is_valid": True,
            "chain_id": current_chain_id,
            "block_number": checkpoint["block_number"],
            "block_hash": current_block_hash,
            "tx_hash": checkpoint["tx_hash"],
            "message": "저장된 블록 및 트랜잭션 기록이 현재 체인과 일치합니다."
        }

    except Exception as e:
        return {
            "checkpoint_id": checkpoint_id,
            "is_valid": False,
            "message": f"체크포인트 검증 실패: {e}"
        }

@app.get("/api/v1/cases/{case_id}/checkpoints")
def get_case_checkpoints(case_id: str):
    checkpoints = list_case_checkpoints(case_id)

    return {
        "case_id": case_id,
        "count": len(checkpoints),
        "checkpoints": checkpoints
    }


@app.post("/api/v1/cases/{case_id}/steps/{step_id}/recover-proof")
def recover_proof(
    case_id: str,
    step_id: int,
    data: RecoverProofSchema
):
    require_chain()

    # 1. SQLite에 사건과 수사 단계가 존재하는지 확인
    case = cases_db.get(case_id)

    if case is None:
        raise HTTPException(404, "Case not found")

    if step_id < 0 or step_id >= len(case["steps"]):
        raise HTTPException(400, "Invalid step ID")

    # 2. 트랜잭션 해시 형식 검사
    if (
        not isinstance(data.tx_hash, str)
        or len(data.tx_hash) != 66
        or not data.tx_hash.startswith("0x")
        or any(c not in "0123456789abcdefABCDEF" for c in data.tx_hash[2:])
    ):
        raise HTTPException(400, "Invalid transaction hash")

    try:
        receipt = w3.eth.get_transaction_receipt(data.tx_hash)
        transaction = w3.eth.get_transaction(data.tx_hash)

        # 3. 실제 성공한 트랜잭션인지 확인
        if receipt["status"] != 1:
            raise HTTPException(409, "Transaction failed")

        # 4. 현재 스마트 컨트랙트에 보낸 거래인지 확인
        if (
            not transaction["to"]
            or transaction["to"].lower() != contract.address.lower()
        ):
            raise HTTPException(
                409, "Transaction contract mismatch"
            )

        # 5. 호출된 함수와 인자 해석
        function, arguments = contract.decode_function_input(
            transaction["input"]
        )

        if function.fn_name != "anchorProof":
            raise HTTPException(
                409, "Transaction is not an anchorProof call"
            )

        # 6. 사건 ID와 수사 단계 ID 비교
        if arguments["caseId"] != case_uint(case_id):
            raise HTTPException(
                409, "Transaction case ID mismatch"
            )

        if arguments["stepId"] != step_id:
            raise HTTPException(
                409, "Transaction step ID mismatch"
            )

        
        
        # 7. 실제 트랜잭션의 ProofAnchored 이벤트 추출
        events = contract.events.ProofAnchored().process_receipt(receipt)

        if len(events) != 1:
            raise HTTPException(
                409,
                "Expected exactly one ProofAnchored event"
            )

        event = events[0]["args"]

        # 8. 이벤트의 사건 및 단계 확인
        if event["caseId"] != case_uint(case_id):
            raise HTTPException(409, "Event case ID mismatch")

        if event["stepId"] != step_id:
            raise HTTPException(409, "Event step ID mismatch")

        # 9. 이벤트 내용과 트랜잭션 입력값 비교
        if (
            event["agency"].lower() != arguments["agency"].lower()
            or bytes(event["claimHash"]) != bytes(arguments["claimHash"])
            or bytes(event["proofHash"]) != bytes(arguments["proofHash"])
            or int(event["status"]) != int(arguments["result"])
            or int(event["evidenceTimestamp"]) != int(arguments["evidenceTimestamp"])
        ):
            raise HTTPException(
                409,
                "Event does not match transaction arguments"
            )

        # 10. Proof ID로 실제 온체인 기록 식별
        proof_count = contract.functions.getProofHistoryLength(
            case_uint(case_id),
            step_id
        ).call()

        matching_proof_index = None
        proof_id = int(event["proofId"])

        for i in range(proof_count):
            record = contract.functions.getProofRecord(
                case_uint(case_id),
                step_id,
                i
            ).call()

            if int(record[0]) == proof_id:
                matching_proof_index = i

                # 이벤트와 실제 Proof 기록 비교
                if (
                    record[1].lower() != event["agency"].lower()
                    or record[2].lower() != event["signer"].lower()
                    or bytes(record[3]) != bytes(event["claimHash"])
                    or bytes(record[4]) != bytes(event["proofHash"])
                    or int(record[5]) != int(event["status"])
                    or int(record[6]) != int(event["evidenceTimestamp"])
                ):
                    raise HTTPException(
                        409,
                        "On-chain Proof record does not match event"
                    )

                break

        if matching_proof_index is None:
            raise HTTPException(
                409,
                "Proof ID not found in on-chain history"
            )


        # 아직 SQLite는 수정하지 않음
        return {
            "message": "Proof recovery transaction validation passed",
            "case_id": case_id,
            "step_id": step_id,
            "tx_hash": data.tx_hash,
            "block_number": receipt["blockNumber"],
            "transaction_valid": True,
            "proof_history_matched": True,
            "proof_id": proof_id,
            "matching_proof_index": matching_proof_index,
            "database_modified": False
        }

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            400,
            f"Proof recovery validation failed: {e}"
        )
