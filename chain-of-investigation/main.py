"""FullProof API — upgraded ChainOfInvestigation integration.

Local demonstration only. Proofs must be signed externally by registered agency
signers; this server never fabricates an agency signature.
"""

from verification_v11 import POLICY, PROOF_FIELDS, verify_v11

import os
import secrets

from eth_keys.exceptions import BadSignature
from eth_account import Account
from eth_account.messages import encode_defunct

import time
import rfc8785
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
from hash_utils import hash_claim_text

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


def verification_sender():
    """v1.1 Verification 전용 시스템 기록자 계정"""
    require_chain()

    accounts = w3.eth.accounts
    if len(accounts) < 2:
        raise HTTPException(
            503,
            "Verification recorder account unavailable"
        )

    recorder = accounts[1]

    if not contract.functions.isVerificationRecorder(recorder).call():
        raise HTTPException(
            403,
            "Account is not an authorized Verification recorder"
        )

    return recorder

def confirmed(tx):
    receipt = w3.eth.wait_for_transaction_receipt(tx, timeout=120)
    if receipt.status != 1:
        raise HTTPException(400, "Blockchain transaction reverted")
    return tx.hex()

def case_uint(case_id: str) -> int:
    return int.from_bytes(
        hashlib.sha256(case_id.encode("utf-8")).digest(),
        byteorder="big"
    )


def canonical_hash(obj):
    return Web3.keccak(text=json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str))

def v11_sha256(obj):
    """FullProof v1.1: RFC8785/JCS + SHA-256"""
    canonical_bytes = rfc8785.dumps(obj)
    return "0x" + hashlib.sha256(canonical_bytes).hexdigest()


V11_PROOF_FIELDS = (
    "schema_version",
    "proof_id",
    "proof_version",
    "case_id",
    "step_id",
    "issuer_agency_id",
    "agency_address",
    "proof_type",
    "call_id",
    "target_id",
    "action_type",
    "proof_occurred_at",
    "proof_issued_at",
    "result",
    "source_sha256",
)


def v11_proof_hash(proof):
    """AI v1.1에서 정의한 기관 Proof 원본 해시 계산"""
    try:
        content = {
            key: proof[key]
            for key in V11_PROOF_FIELDS
        }
    except (KeyError, TypeError):
        raise HTTPException(
            400,
            "Invalid v1.1 Proof content"
        )

    return v11_sha256(content)


# FullProof v1.1 - Mock Draft 보관
# 개발용 메모리 저장. 서버 재시작 시 초기화된다.
PROOF_DRAFTS = {}


class ProofDraftSchema(BaseModel):
    proof_content: dict
    source_text: str
    nonce: int = Field(ge=0)
    deadline: int = Field(gt=0)


@app.post("/api/v1/proofs/drafts", status_code=201)
def create_proof_draft(data: ProofDraftSchema):
    from datetime import datetime, timezone
    from hash_utils import hash_proof_content

    require_chain()

    proof = dict(data.proof_content)

    # 1. Mock 원본 해시를 백엔드에서 직접 생성
    source_bytes = data.source_text.encode("utf-8")
    proof["source_sha256"] = (
        "0x" + hashlib.sha256(source_bytes).hexdigest()
    )

    # 2. 공식 v1.1 Proof 필드 검증 및 해시 계산
    try:
        proof_hash = hash_proof_content(proof)
    except (TypeError, ValueError) as exc:
        raise HTTPException(422, str(exc))

    if proof_hash != v11_proof_hash(proof):
        raise HTTPException(500, "Proof hash mismatch")

    # 3. 사건 및 단계 검증
    case = cases_db.get(proof["case_id"])

    if not case:
        raise HTTPException(404, "Case not found")

    if case["is_closed"]:
        raise HTTPException(409, "Case already closed")

    step_id = proof["step_id"]
    if step_id >= len(case["steps"]):
        raise HTTPException(400, "Invalid step_id")

    if not Web3.is_address(proof["agency_address"]):
        raise HTTPException(422, "Invalid agency address")

    agency = Web3.to_checksum_address(
        proof["agency_address"]
    )

    # 4. UTC 시간 문자열을 Unix timestamp로 변환
    def to_timestamp(value):
        if not isinstance(value, str):
            raise HTTPException(422, "Invalid UTC timestamp")

        try:
            dt = datetime.strptime(
                value, "%Y-%m-%dT%H:%M:%SZ"
            ).replace(tzinfo=timezone.utc)
            return int(dt.timestamp())
        except ValueError:
            raise HTTPException(422, "Invalid UTC timestamp")

    if proof["proof_occurred_at"] is None:
        raise HTTPException(
            422,
            "Signed MVP Proof requires proof_occurred_at"
        )

    occurred_at = to_timestamp(proof["proof_occurred_at"])
    issued_at = to_timestamp(proof["proof_issued_at"])

    if issued_at < occurred_at:
        raise HTTPException(422, "Invalid proof timestamps")

    proof_id_hash = (
        "0x" + hashlib.sha256(
            proof["proof_id"].encode("utf-8")
        ).hexdigest()
    )

    # 5. B안 EIP-712 서명 데이터 구성
    typed_data = {
        "types": {
            "ProofAttestation": [
                {"name": "caseId", "type": "uint256"},
                {"name": "stepId", "type": "uint256"},
                {"name": "proofIdHash", "type": "bytes32"},
                {"name": "proofVersion", "type": "uint256"},
                {"name": "proofHash", "type": "bytes32"},
                {"name": "occurredAt", "type": "uint64"},
                {"name": "issuedAt", "type": "uint64"},
                {"name": "agency", "type": "address"},
                {"name": "nonce", "type": "uint256"},
                {"name": "deadline", "type": "uint64"}
            ]
        },
        "primaryType": "ProofAttestation",
        "domain": {
            "name": "FullProof",
            "version": "2",
            "chainId": w3.eth.chain_id,
            "verifyingContract": contract.address
        },
        "message": {
            "caseId": str(case_uint(proof["case_id"])),
            "stepId": str(step_id),
            "proofIdHash": proof_id_hash,
            "proofVersion": str(proof["proof_version"]),
            "proofHash": proof_hash,
            "occurredAt": str(occurred_at),
            "issuedAt": str(issued_at),
            "agency": agency,
            "nonce": str(data.nonce),
            "deadline": str(data.deadline)
        }
    }

    # 6. Draft 저장 - 동일 ID/버전 덮어쓰기 금지
    draft_key = (
        proof["case_id"],
        proof["proof_id"],
        proof["proof_version"]
    )

    if draft_key in PROOF_DRAFTS:
        raise HTTPException(
            409,
            "Draft already exists for this Proof version"
        )

    PROOF_DRAFTS[draft_key] = {
        "proof_content": proof,
        "source_bytes": source_bytes,
        "proof_hash": proof_hash,
        "typed_data": typed_data,
        "status": "UNSIGNED"
    }

    return {
        "success": True,
        "data": {
            "proof_content": proof,
            "source_sha256": proof["source_sha256"],
            "proof_hash": proof_hash,
            "typed_data": typed_data,
            "draft_status": "UNSIGNED"
        },
        "error": None
    }



def validate_v11_onchain_proof(proof):
    """v1.1 기관 Proof 원본과 최신 온체인 기록 대조"""
    require_chain()

    try:
        case_id = proof["case_id"]
        step_id = proof["step_id"]
        proof_id = proof["proof_id"]
        proof_version = proof["proof_version"]
        agency = proof["agency_address"]

        if not isinstance(case_id, str) or not case_id:
            raise ValueError("Invalid case ID")

        if type(step_id) is not int or step_id < 0:
            raise ValueError("Invalid step ID")

        if type(proof_version) is not int or proof_version < 1:
            raise ValueError("Invalid Proof version")

        if not isinstance(proof_id, str) or not proof_id:
            raise ValueError("Invalid Proof ID")

        if not Web3.is_address(agency):
            raise ValueError("Invalid agency address")

        proof_id_hash = "0x" + hashlib.sha256(
            proof_id.encode("utf-8")
        ).hexdigest()

        proof_hash = v11_proof_hash(proof)

        is_latest = contract.functions.isLatestAgencyProof(
            case_uint(case_id),
            step_id,
            Web3.to_checksum_address(agency),
            proof_id_hash,
            proof_version,
            proof_hash
        ).call()

        if not is_latest:
            raise HTTPException(
                400,
                "Proof is not the latest registered agency Proof"
            )


        # FullProof v1.1 - 백엔드 Mock 원본 검증
        draft_key = (
            case_id,
            proof_id,
            proof_version
        )

        draft = PROOF_DRAFTS.get(draft_key)

        if draft is None:
            raise HTTPException(
                409,
                "Verified Proof Draft not found"
            )

        # 기관 서명과 온체인 기록이 완료된 Draft만 인정
        if draft["status"] != "ANCHORED":
            raise HTTPException(
                409,
                "Proof has not been anchored"
            )

        # 저장한 실제 Mock 원본 바이트 검증
        expected_source_hash = (
            "0x" + hashlib.sha256(
                draft["source_bytes"]
            ).hexdigest()
        )

        if (
            expected_source_hash
            != draft["proof_content"]["source_sha256"]
        ):
            raise HTTPException(
                409,
                "Proof source integrity mismatch"
            )

        # 검증 요청에 포함된 Proof가
        # 실제 서명 및 기록된 Draft와 동일한지 확인
        if draft["proof_hash"] != proof_hash:
            raise HTTPException(
                409,
                "Proof differs from anchored Draft"
            )

        if (
            draft["proof_content"]["agency_address"].lower()
            != agency.lower()
        ):
            raise HTTPException(
                409,
                "Proof agency mismatch"
            )
        return {
            "proof_id": proof_id,
            "proof_version": proof_version,
            "proof_hash": proof_hash,
            "proof_id_hash": proof_id_hash,
            "agency": Web3.to_checksum_address(agency),
            "status": "VALID"
        }

    except HTTPException:
        raise

    except (KeyError, TypeError, ValueError) as e:
        raise HTTPException(
            400,
            f"Invalid v1.1 agency Proof: {e}"
        )


def validate_v11_onchain_claim(claim):
    """v1.1 Claim 원문과 온체인 등록 기록 대조"""
    require_chain()

    try:
        case_id = claim["case_id"]
        step_id = claim["step_id"]
        claim_id = claim["claim_id"]
        claim_version = claim["claim_version"]
        claim_text = claim["claim_text"]

        if not isinstance(case_id, str) or not case_id:
            raise ValueError("Invalid case ID")
        if type(step_id) is not int or step_id < 0:
            raise ValueError("Invalid step ID")
        if not isinstance(claim_id, str) or not claim_id:
            raise ValueError("Invalid Claim ID")
        if type(claim_version) is not int or claim_version < 1:
            raise ValueError("Invalid Claim version")
        if not isinstance(claim_text, str) or not claim_text:
            raise ValueError("Invalid Claim text")

        claim_id_hash = "0x" + hashlib.sha256(
            claim_id.encode("utf-8")
        ).hexdigest()

        claim_hash = "0x" + hashlib.sha256(
            claim_text.encode("utf-8")
        ).hexdigest()

        registered = contract.functions.isRegisteredClaim(
            case_uint(case_id),
            step_id,
            claim_id_hash,
            claim_version,
            claim_hash
        ).call()

        if not registered:
            raise HTTPException(
                400,
                "Claim does not match on-chain record"
            )

        # v1.1: 과거 Claim이 아닌 최신 Claim만 검증에 사용
        latest_claim = contract.functions.getLatestClaim(
            case_uint(case_id),
            step_id
        ).call()

        if (
            Web3.to_hex(latest_claim[0]) != claim_id_hash
            or latest_claim[1] != claim_version
            or Web3.to_hex(latest_claim[2]) != claim_hash
        ):
            raise HTTPException(
                409,
                "Claim is outdated: re-verification required"
            )

        return {
            "claim_id": claim_id,
            "claim_version": claim_version,
            "claim_hash": claim_hash,
            "status": "VALID"
        }

    except HTTPException:
        raise

    except (KeyError, TypeError, ValueError) as e:
        raise HTTPException(
            400,
            f"Invalid v1.1 Claim: {e}"
        )

def anchor_v11_verification(result):
    """검증 완료된 v1.1 Verification의 온체인 기록 단계"""

    if result.get("schema_version") != "1.1":
        raise HTTPException(400, "Invalid schema version")

    if (
        result.get("processing_status") != "COMPLETED"
        or result.get("verdict") not in (
            "SUPPORTED",
            "CONTRADICTED",
            "INSUFFICIENT"
        )
    ):
        raise HTTPException(
            400,
            "Verification is not finalized"
        )

    # 공식 JCS/SHA-256 해시 확인
    verification_hash = validate_v11_verification_hashes(result)

    # 온체인 기록 직전 최신 Claim 참조 확인
    chain_case_id = case_uint(result["case_id"])
    step_id = result["step_id"]
    claim_ref = result["claim_ref"]

    if not contract.functions.isLatestClaimVerified(
        chain_case_id, step_id
    ).call():
        # 이 함수는 이미 기록된 Verification 기준으로 판단하므로
        # 신규 Verification 등록 전 검사에는 사용하지 않는다.
        pass

    latest_claim = contract.functions.getLatestClaim(
        chain_case_id, step_id
    ).call()

    expected_claim_id_hash = "0x" + hashlib.sha256(
        claim_ref["claim_id"].encode("utf-8")
    ).hexdigest()

    if (
        Web3.to_hex(latest_claim[0]) != expected_claim_id_hash
        or latest_claim[1] != claim_ref["claim_version"]
        or Web3.to_hex(latest_claim[2]) != claim_ref["claim_hash"]
    ):
        raise HTTPException(
            409,
            "Claim changed before Verification anchoring"
        )

    # Verification이 참조한 모든 Proof의 최신성 재확인
    # proof_refs에는 agency 주소가 없으므로, 기관과 연결된
    # 검증 완료 원본 데이터가 필요한 검사는 호출 전에 수행해야 한다.

    # v1.1: Verification이 참조한 Proof가 실제 온체인에
    # 존재하며 해당 기관의 최신 버전인지 확인한다.
    proof_refs = result["proof_refs"]

    if (
        result["verdict"] in ("SUPPORTED", "CONTRADICTED")
        and not proof_refs
    ):
        raise HTTPException(
            400,
            "Final verdict requires agency Proof"
        )

    proof_count = contract.functions.getAgencyProofHistoryLength(
        chain_case_id, step_id
    ).call()

    for proof_ref in proof_refs:
        proof_id_hash = "0x" + hashlib.sha256(
            proof_ref["proof_id"].encode("utf-8")
        ).hexdigest()

        matched = False

        for index in range(proof_count):
            record = contract.functions.getAgencyProofRecord(
                chain_case_id, step_id, index
            ).call()

            if (
                Web3.to_hex(record[0]) == proof_id_hash
                and record[1] == proof_ref["proof_version"]
                and Web3.to_hex(record[2]) == proof_ref["proof_hash"]
            ):
                agency = record[3]

                matched = contract.functions.isLatestAgencyProof(
                    chain_case_id,
                    step_id,
                    agency,
                    proof_id_hash,
                    proof_ref["proof_version"],
                    proof_ref["proof_hash"]
                ).call()

                if matched:
                    break

        if not matched:
            raise HTTPException(
                409,
                "Verification references an invalid or outdated Proof"
            )

    claim_ref = result["claim_ref"]

    verdict_map = {
        "SUPPORTED": 1,
        "CONTRADICTED": 2,
        "INSUFFICIENT": 3
    }

    verification_id_hash = (
        "0x" + hashlib.sha256(
            result["verification_id"].encode("utf-8")
        ).hexdigest()
    )

    tx_hash = confirmed(
        contract.functions.anchorVerification(
            case_uint(result["case_id"]),
            result["step_id"],
            verification_id_hash,
            "0x" + hashlib.sha256(
                claim_ref["claim_id"].encode("utf-8")
            ).hexdigest(),
            claim_ref["claim_version"],
            claim_ref["claim_hash"],
            result["proof_refs_hash"],
            result["policy_hash"],
            verification_hash,
            verdict_map[result["verdict"]]
        ).transact({
            "from": verification_sender()
        })
    )

    return {
        "verification_id": result["verification_id"],
        "verification_hash": verification_hash,
        "verification_tx_hash": tx_hash
    }




def process_v11_verification(validated_inputs):
    """FullProof v1.1 - 검증된 입력만 AI Rule Engine에 전달"""

    from verification_v11 import verify_v11

    claim = validated_inputs["claim"]
    proofs = validated_inputs["proofs"]

    # 1. 백엔드가 Claim과 Proof를 직접 검증
    validate_v11_onchain_claim(claim)

    verified_proofs = {}

    for proof in proofs:
        validation = validate_v11_onchain_proof(proof)

        key = (
            validation["proof_id"],
            validation["proof_version"]
        )

        if key in verified_proofs:
            raise HTTPException(
                409,
                "Duplicate Proof version"
            )

        verified_proofs[key] = {
             "status": "VALID",
            # 독립적인 매핑 근거 충분성 검증이
            # 구현되기 전에는 True로 설정하지 않는다.
            "mapping_evidence_sufficient": False
        }

    # 2. 매핑 근거는 현재 백엔드에서 독립 검증되지 않음
    # 외부 입력의 mapping_evidence_sufficient=True를 신뢰하지 않는다.
    safe_mappings = []

    for mapping in validated_inputs.get("mappings", []):
        safe_mapping = dict(mapping)
        safe_mapping["mapping_evidence_sufficient"] = False
        safe_mappings.append(safe_mapping)

    # 3. 백엔드 검증 결과만 AI에 전달
    safe_inputs = {
        **validated_inputs,
        "proof_validation": verified_proofs,
        "mappings": safe_mappings
    }

    result = verify_v11(
        **safe_inputs,
        canonicalize=rfc8785.dumps
    )

    # 4. v1.1 해시 검증
    validate_v11_verification_hashes(result)

    # 5. 확정된 판정만 온체인 기록
    if (
        result["processing_status"] != "COMPLETED"
        or result["verdict"] not in (
            "SUPPORTED",
            "CONTRADICTED",
            "INSUFFICIENT"
        )
    ):
        return result

    anchor_result = anchor_v11_verification(result)

    result["verification_tx_hash"] = (
        anchor_result["verification_tx_hash"]
    )

    return result


def validate_v11_verification_hashes(result):
    """v1.1 Proof 참조 해시와 Verification 해시를 검증한다."""

    proof_refs = result["proof_refs"]

    expected_proof_refs_hash = v11_sha256({
        "schema_version": "1.1",
        "proof_refs": proof_refs
    })

    if result["proof_refs_hash"] != expected_proof_refs_hash:
        raise HTTPException(
            400,
            "Verification proof_refs_hash mismatch"
        )

    fields = (
        "schema_version",
        "verification_id",
        "case_id",
        "step_id",
        "claim_ref",
        "proof_refs",
        "processing_status",
        "verdict",
        "conflicts",
        "missing_information",
        "reason_text",
        "evidence_refs",
        "review_required",
        "decision_policy_version",
        "policy_hash",
        "proof_refs_hash",
    )

    verification_content = {
        key: result[key] for key in fields
    }

    expected_verification_hash = v11_sha256(
        verification_content
    )

    if result.get("verification_hash") not in (
        None,
        expected_verification_hash
    ):
        raise HTTPException(
            400,
            "Verification hash mismatch"
        )

    return expected_verification_hash

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

class ClaimCreateSchema(BaseModel):
    claim_id: str = Field(min_length=1)
    claim_version: int = Field(ge=1)
    step_id: int = Field(ge=0)
    claim_text: str = Field(min_length=1)


class ProofAttestationSchema(BaseModel):
    case_id: str
    step_id: int = Field(ge=0)

    proof_id: str = Field(min_length=1)
    proof_version: int = Field(ge=1)
    proof_hash: str

    occurred_at: int = Field(gt=0)
    issued_at: int = Field(gt=0)

    agency: str
    nonce: int = Field(ge=0)
    deadline: int = Field(gt=0)

    signature: str


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


@app.post(
    "/api/v1/cases/{case_id}/claims",
    status_code=status.HTTP_201_CREATED
)
def create_claim(case_id: str, data: ClaimCreateSchema):
    require_chain()

    # 1. 사건이 존재하는지 확인
    case = cases_db.get(case_id)

    if not case:
        raise HTTPException(404, "Case not found")

    if case["is_closed"]:
        raise HTTPException(400, "Cannot modify closed case")

    # 2. 해당 수사 단계가 존재하는지 확인
    if data.step_id >= len(case["steps"]):
        raise HTTPException(400, "Invalid step_id")

    # 3. Claim ID와 원문을 SHA-256으로 해시
    claim_id_hash = "0x" + hashlib.sha256(
        data.claim_id.encode("utf-8")
    ).hexdigest()

    claim_hash = hash_claim_text(data.claim_text)

    # Claim 원본 작성자 식별자와 입력 시각
    # 현재 API에 작성자 입력 필드가 없으므로 인증된 등록자 주소를 임시 식별자로 사용
    author_id_hash = "0x" + hashlib.sha256(
        sender().lower().encode("utf-8")
    ).hexdigest()

    # 서버가 원본을 처음 접수한 시각으로 기록
    input_at = int(w3.eth.get_block("latest")["timestamp"])

    # 4. 블록체인에 Claim 기록
    try:
        tx_hash = confirmed(
            contract.functions.anchorClaim(
                case_uint(case_id),
                data.step_id,
                claim_id_hash,
                data.claim_version,
                claim_hash,
                author_id_hash,
                input_at
            ).transact({"from": sender()})
        )

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            400,
            f"On-chain anchorClaim failed: {e}"
        )

    # 5. 등록 결과 반환
    return {
        "schema_version": "1.1",
        "case_id": case_id,
        "step_id": data.step_id,
        "claim_id": data.claim_id,
        "claim_version": data.claim_version,
        "claim_text": data.claim_text,
        "claim_hash": claim_hash,
        "claim_tx_hash": tx_hash,
        "chain_status": "CONFIRMED"
    }

@app.get("/api/v1/cases/{case_id}/steps/{step_id}/claims")
def get_claim_history(case_id: str, step_id: int):
    require_chain()

    case = cases_db.get(case_id)

    if not case:
        raise HTTPException(404, "Case not found")

    if step_id < 0 or step_id >= len(case["steps"]):
        raise HTTPException(400, "Invalid step_id")

    chain_case_id = case_uint(case_id)

    try:
        count = contract.functions.getClaimHistoryLength(
            chain_case_id, step_id
        ).call()

        records = []

        for index in range(count):
            record = contract.functions.getClaimRecord(
                chain_case_id, step_id, index
            ).call()

            records.append({
                "claim_id_hash": Web3.to_hex(record[0]),
                "claim_version": record[1],
                "claim_hash": Web3.to_hex(record[2]),
                "author_id_hash": Web3.to_hex(record[3]),
                "input_at": record[4],
                "recorded_at": record[5],
                "recorder": record[6]
            })

    except Exception as e:
        raise HTTPException(
            500,
            f"On-chain Claim lookup failed: {e}"
        )

    return {
        "case_id": case_id,
        "step_id": step_id,
        "total": count,
        "claims": records
    }

@app.post(
    "/api/v1/proofs/anchor",
    status_code=status.HTTP_201_CREATED
)
def anchor_agency_proof(data: ProofAttestationSchema):
    require_chain()

    # FullProof v1.1 - Draft 검증
    draft_key = (
        data.case_id,
        data.proof_id,
        data.proof_version
    )

    draft = PROOF_DRAFTS.get(draft_key)

    if draft is None:
        raise HTTPException(
            409,
            "Verified Proof Draft not found"
        )

    if draft["status"] != "UNSIGNED":
        raise HTTPException(
            409,
            "Proof Draft already submitted"
        )

    # 저장된 Mock 원본 바이트의 무결성 재검사
    source_hash = "0x" + hashlib.sha256(
        draft["source_bytes"]
    ).hexdigest()

    if source_hash != draft["proof_content"]["source_sha256"]:
        raise HTTPException(
            409,
            "Proof source hash mismatch"
        )

    # 원본 Proof 구조에서 다시 계산
    if v11_proof_hash(draft["proof_content"]) != data.proof_hash:
        raise HTTPException(
            409,
            "Proof content hash mismatch"
        )

    # 요청 전체가 기관의 서명 대상과 일치해야 한다.
    signed_message = draft["typed_data"]["message"]

    expected_message = {
        "caseId": str(case_uint(data.case_id)),
        "stepId": str(data.step_id),
        "proofIdHash": (
            "0x" + hashlib.sha256(
                data.proof_id.encode("utf-8")
            ).hexdigest()
        ),
        "proofVersion": str(data.proof_version),
        "proofHash": data.proof_hash,
        "occurredAt": str(data.occurred_at),
        "issuedAt": str(data.issued_at),
        "agency": Web3.to_checksum_address(data.agency),
        "nonce": str(data.nonce),
        "deadline": str(data.deadline)
    }

    if expected_message != signed_message:
        raise HTTPException(
            409,
            "Signed Proof differs from verified Draft"
        )

    # 1. 사건과 단계가 존재하는지 확인
    case = cases_db.get(data.case_id)

    if not case:
        raise HTTPException(404, "Case not found")

    if case["is_closed"]:
        raise HTTPException(400, "Cannot modify closed case")

    if data.step_id >= len(case["steps"]):
        raise HTTPException(400, "Invalid step_id")

    # 2. Proof 해시와 기관 주소 형식 확인
    def valid_hash(value):
        return (
            isinstance(value, str)
            and len(value) == 66
            and value.startswith("0x")
            and all(c in "0123456789abcdef" for c in value[2:])
        )

    if not valid_hash(data.proof_hash):
        raise HTTPException(400, "Invalid proof_hash")

    if not Web3.is_address(data.agency):
        raise HTTPException(400, "Invalid agency address")

    if (
        not isinstance(data.signature, str)
        or not data.signature.startswith("0x")
        or len(data.signature) != 132
    ):
        raise HTTPException(400, "Invalid signature format")

    if data.issued_at < data.occurred_at:
        raise HTTPException(400, "Invalid proof timestamps")

    # 3. Proof ID를 SHA-256으로 해시
    proof_id_hash = "0x" + hashlib.sha256(
        data.proof_id.encode("utf-8")
    ).hexdigest()

    agency_address = Web3.to_checksum_address(data.agency)

    # 4. Solidity ProofAttestation 구조체 구성
    request = (
        case_uint(data.case_id),
        data.step_id,
        proof_id_hash,
        data.proof_version,
        data.proof_hash,
        data.occurred_at,
        data.issued_at,
        agency_address,
        data.nonce,
        data.deadline,
    )

    # 5. 기관 서명 검증 및 온체인 기록
    try:
        tx_hash = confirmed(
            contract.functions.anchorProofAttestation(
                request,
                data.signature
            ).transact({"from": sender()})
        )

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            400,
            f"On-chain Proof attestation failed: {e}"
        )

    draft["status"] = "ANCHORED"
    # 6. 결과 반환
    return {
        "schema_version": "1.1",
        "case_id": data.case_id,
        "step_id": data.step_id,
        "proof_id": data.proof_id,
        "proof_id_hash": proof_id_hash,
        "proof_hash": data.proof_hash,
        "agency": agency_address,
        "proof_tx_hash": tx_hash,
        "chain_status": "CONFIRMED"
    }


@app.get("/api/v1/cases/{case_id}/steps/{step_id}/agency-proofs")
def get_agency_proof_history(case_id: str, step_id: int):
    require_chain()

    case = cases_db.get(case_id)

    if not case:
        raise HTTPException(404, "Case not found")

    if step_id < 0 or step_id >= len(case["steps"]):
        raise HTTPException(400, "Invalid step_id")

    try:
        chain_case_id = case_uint(case_id)

        count = contract.functions.getAgencyProofHistoryLength(
            chain_case_id, step_id
        ).call()

        records = []

        for index in range(count):
            record = contract.functions.getAgencyProofRecord(
                chain_case_id, step_id, index
            ).call()

            records.append({
                "proof_id_hash": Web3.to_hex(record[0]),
                "proof_version": record[1],
                "proof_hash": Web3.to_hex(record[2]),
                "agency": record[3],
                "signer": record[4],
                "occurred_at": record[5],
                "issued_at": record[6],
                "recorded_at": record[7],
                "signature_digest": Web3.to_hex(record[8])
            })

    except Exception as e:
        raise HTTPException(
            500,
            f"On-chain agency Proof lookup failed: {e}"
        )

    return {
        "case_id": case_id,
        "step_id": step_id,
        "total": count,
        "proofs": records
    }





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


# ============================================================
# FullProof v1.1 API integration
# ============================================================

from typing import Any, Literal
from datetime import datetime, timezone
from uuid import uuid4

# MVP temporary stores.
# Not persistent across server restart or multiple workers.
V11_MAPPING_HISTORY = {}
V11_VERIFICATION_RESULTS = {}


def v11_now():
    return datetime.now(timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def v11_success(data):
    return {
        "success": True,
        "data": data,
        "error": None,
    }


# ------------------------------------------------------------
# A. Claim-Proof mapping
# ------------------------------------------------------------



class V11MappingRequest(BaseModel):
    case_id: str
    step_id: int = Field(ge=0)

    claim_version: int = Field(ge=1)
    claim_text: str = Field(min_length=1)

    proof_id: str = Field(min_length=1)
    proof_version: int = Field(ge=1)

    issuer_agency_id: str = Field(min_length=1)
    call_id: str | None = None

    mapping_method: str = "MANUAL_SELECTION"

    mapping_status: Literal[
        "PENDING",
        "AMBIGUOUS",
        "REJECTED"
    ] = "PENDING"


@app.post(
    "/api/v1/claims/{claim_id}/proof-mappings",
    status_code=201
)
def create_v11_mapping(
    claim_id: str,
    data: V11MappingRequest
):
    require_chain()

    # 1. 사건 및 수사 단계 확인
    case = cases_db.get(data.case_id)

    if case is None:
        raise HTTPException(404, "Case not found")

    if case["is_closed"]:
        raise HTTPException(409, "Case already closed")

    if data.step_id >= len(case["steps"]):
        raise HTTPException(422, "Invalid step_id")

    # 2. Claim이 실제 온체인에 등록된
    #    최신 버전인지 검증
    claim = {
        "case_id": data.case_id,
        "step_id": data.step_id,
        "claim_id": claim_id,
        "claim_version": data.claim_version,
        "claim_text": data.claim_text
    }

    claim_validation = validate_v11_onchain_claim(
        claim
    )

    if claim_validation["status"] != "VALID":
        raise HTTPException(
            409,
            "Claim on-chain validation failed"
        )

    # 2. 백엔드가 보관한 Proof Draft 확인
    draft_key = (
        data.case_id,
        data.proof_id,
        data.proof_version
    )

    draft = PROOF_DRAFTS.get(draft_key)

    if draft is None:
        raise HTTPException(
            404, "Proof Draft not found"
        )

    if draft["status"] != "ANCHORED":
        raise HTTPException(
            409, "Proof has not been anchored"
        )

    proof = draft["proof_content"]

    # 3. 기관 및 통화 식별자 일치 확인
    if (
        proof["case_id"] != data.case_id
        or proof["step_id"] != data.step_id
        or proof["issuer_agency_id"]
           != data.issuer_agency_id
        or proof["call_id"] != data.call_id
    ):
        raise HTTPException(
            409, "Proof mapping reference mismatch"
        )

    # 4. 실제 온체인 Proof와 대조

    proof_validation = validate_v11_onchain_proof(
        proof
    )

    if proof_validation["status"] != "VALID":
        raise HTTPException(
            409,
            "Proof on-chain validation failed"
        )

    # 5. 아직 인증된 담당자 확인 및
    #    Claim 최신 버전 검증이 연결되지 않았음
    #    따라서 CONFIRMED로 기록하지 않는다.
    mapping = {
    "schema_version": "1.1",
    "mapping_id": "MAP-" + uuid4().hex,

    "claim_id": claim_id,
    "claim_version": data.claim_version,
    "claim_hash": claim_validation["claim_hash"],

    "proof_id": data.proof_id,
    "proof_version": data.proof_version,
    "issuer_agency_id": data.issuer_agency_id,
    "call_id": data.call_id,

    "claim_validation_status": "VALID",
    "proof_validation_status": "VALID",

    "mapping_status": data.mapping_status,
    "mapping_method": data.mapping_method,

    "confirmed_by": None,
    "confirmed_at": None,
    "confirmation_nonce": secrets.token_hex(16),
    "confirmation_evidence": None,

    }

    key = (data.case_id, claim_id)
    V11_MAPPING_HISTORY.setdefault(
        key, []
    ).append(mapping)

    return v11_success(mapping)

class V11MappingConfirmRequest(BaseModel):
    case_id: str
    claim_text: str = Field(min_length=1)
    evidence_source_sha256: str
    evidence_note: str = Field(min_length=10)
    signer_address: str
    signature: str


def build_v11_mapping_confirmation_message(
    case_id, mapping, claim_hash,
    proof_hash, evidence_source_sha256,
    evidence_note
):
    return "\n".join([
        "FullProof v1.1 Mapping Confirmation",
        f"case_id={case_id}",
        f"mapping_id={mapping['mapping_id']}",
        f"claim_id={mapping['claim_id']}",
        f"claim_version={mapping['claim_version']}",
        f"claim_hash={claim_hash}",
        f"proof_id={mapping['proof_id']}",
        f"proof_version={mapping['proof_version']}",
        f"proof_hash={proof_hash}",
        f"evidence_source_sha256={evidence_source_sha256}",
        f"evidence_note={evidence_note}",
        f"nonce={mapping['confirmation_nonce']}"
    ])


@app.post(
    "/api/v1/claims/{claim_id}/proof-mappings/"
    "{mapping_id}/confirm"
)
def confirm_v11_mapping(
    claim_id: str,
    mapping_id: str,
    data: V11MappingConfirmRequest
):
    require_chain()

    # 1. 개발 환경에서 허용된 담당자 주소 확인
    allowed = {
        address.strip().lower()
        for address in os.getenv(
            "V11_MAPPING_REVIEWERS", ""
        ).split(",")
        if address.strip()
    }

    if not allowed:
        raise HTTPException(
            503,
            "Mapping reviewer authorization is not configured"
        )

    if data.signer_address.lower() not in allowed:
        raise HTTPException(
            403,
            "Reviewer is not authorized"
        )

    # 2. 기존 매핑 찾기
    history = V11_MAPPING_HISTORY.get(
        (data.case_id, claim_id), []
    )

    mapping = next(
        (
            item for item in history
            if item["mapping_id"] == mapping_id
        ),
        None
    )

    if mapping is None:
        raise HTTPException(404, "Mapping not found")

    if mapping["mapping_status"] != "PENDING":
        raise HTTPException(
            409, "Mapping is not pending"
        )

    case = cases_db.get(data.case_id)
    if case is None:
        raise HTTPException(404, "Case not found")
    if case.get("is_closed"):
        raise HTTPException(409, "Case is closed")

    # 3. 최신 Claim 재검증
    proof_key = (
        data.case_id,
        mapping["proof_id"],
        mapping["proof_version"]
    )

    draft = PROOF_DRAFTS.get(proof_key)
    if draft is None or draft["status"] != "ANCHORED":
        raise HTTPException(
            409, "Anchored Proof Draft is unavailable"
        )

    proof = draft["proof_content"]

    claim = {
        "case_id": data.case_id,
        "step_id": proof["step_id"],
        "claim_id": claim_id,
        "claim_version": mapping["claim_version"],
        "claim_text": data.claim_text
    }

    claim_result = validate_v11_onchain_claim(claim)
    proof_result = validate_v11_onchain_proof(proof)

    if (
        claim_result["status"] != "VALID"
        or proof_result["status"] != "VALID"
    ):
        raise HTTPException(
            409, "Claim or Proof validation failed"
        )

    # 4. Proof와 매핑 식별자 재대조
    if (
        proof["case_id"] != data.case_id
        or proof["proof_id"] != mapping["proof_id"]
        or proof["proof_version"] != mapping["proof_version"]
        or proof["issuer_agency_id"]
           != mapping["issuer_agency_id"]
        or proof["call_id"] != mapping["call_id"]
    ):
        raise HTTPException(
            409, "Mapping reference mismatch"
        )

    # 5. 원본 증빙의 해시 검증
    source_hash = proof["source_sha256"]

    if (
        data.evidence_source_sha256.lower()
        != source_hash.lower()
    ):
        raise HTTPException(
            409, "Evidence source hash mismatch"
        )

    # 6. 확인 내용과 서명을 연결
    message = build_v11_mapping_confirmation_message(
        data.case_id,
        mapping,
        claim_result["claim_hash"],
        draft["proof_hash"],
        source_hash,
        data.evidence_note
    )

    try:
        recovered = Account.recover_message(
            encode_defunct(text=message),
            signature=data.signature
        )
    except (ValueError, TypeError):
        raise HTTPException(
            400, "Invalid confirmation signature"
        )

    if recovered.lower() != data.signer_address.lower():
        raise HTTPException(
            403, "Confirmation signature mismatch"
        )

    # 7. 확인 이력 기록
    from datetime import datetime, timezone

    confirmed_at = datetime.now(
        timezone.utc
    ).isoformat()

    mapping["mapping_status"] = "CONFIRMED"
    mapping["confirmed_by"] = recovered
    mapping["confirmed_at"] = confirmed_at
    mapping["confirmation_evidence"] = {
        "source_sha256": source_hash,
        "note": data.evidence_note,
        "signature": data.signature,
        "claim_hash": claim_result["claim_hash"],
        "proof_hash": draft["proof_hash"]
    }

    return v11_success(mapping)


# ------------------------------------------------------------
# B. Verification
# ------------------------------------------------------------

class V11VerificationRequest(BaseModel):
    claim: dict[str, Any]
    proofs: list[dict[str, Any]] = Field(
        default_factory=list
    )


@app.post("/api/v1/verifications", status_code=201)
def create_v11_verification(
    data: V11VerificationRequest
):
    claim = data.claim

    try:
        case_id = claim["case_id"]
        claim_id = claim["claim_id"]
        step_id = claim["step_id"]
    except (KeyError, TypeError):
        raise HTTPException(
            422, "Missing Claim reference"
        )

    case = cases_db.get(case_id)

    if case is None:
        raise HTTPException(404, "Case not found")

    if case["is_closed"]:
        raise HTTPException(409, "Case already closed")

    if type(step_id) is not int or (
        step_id < 0 or step_id >= len(case["steps"])
    ):
        raise HTTPException(422, "Invalid step_id")

    for proof in data.proofs:
        if (
            proof.get("case_id") != case_id
            or proof.get("step_id") != step_id
        ):
            raise HTTPException(
                422, "Proof case or step mismatch"
            )

    # Mapping records are NOT automatically trusted.
    # The backend has not yet authenticated a human
    # confirmer or independently assessed link evidence.
    history = V11_MAPPING_HISTORY.get(
        (case_id, claim_id), []
    )

    safe_mappings = []

    for mapping in history:
        safe_mapping = dict(mapping)
        safe_mapping[
            "mapping_evidence_sufficient"
        ] = False
        safe_mappings.append(safe_mapping)

    validated_inputs = {
        "claim": claim,
        "proofs": data.proofs,
        "mappings": safe_mappings,
        # Never take this from the request.
        "proof_validation": {},
    }

    # The existing function validates Claim/Proof on-chain
    # and reconstructs proof_validation internally.
    result = process_v11_verification(validated_inputs)

    verification_id = result.get("verification_id")

    if verification_id:
        V11_VERIFICATION_RESULTS[
            verification_id
        ] = result

    return v11_success(result)


# ------------------------------------------------------------
# C. Administrator review request validation
# ------------------------------------------------------------

class V11ReviewRequest(BaseModel):
    review_status: Literal[
        "ACKNOWLEDGED",
        "ACCEPTED",
        "REVISION_REQUESTED"
    ]
    reason_code: str | None = None
    reason_text: str = ""


class V11SignedReviewRequest(V11ReviewRequest):
    signer_address: str
    signature: str
    nonce: str = Field(min_length=16)
    deadline: int = Field(gt=0)


def build_v11_admin_review_message(
    verification_id,
    verification_hash,
    data
):
    payload = {
        "purpose": "FullProof v1.1 Administrator Review",
        "chain_id": w3.eth.chain_id,
        "contract_address": contract.address,
        "verification_id": verification_id,
        "verification_hash": verification_hash,
        "review_status": data.review_status,
        "reason_code": data.reason_code,
        "reason_text": data.reason_text,
        "signer_address": data.signer_address,
        "nonce": data.nonce,
        "deadline": data.deadline
    }

    return rfc8785.dumps(payload).decode("utf-8")


V11_USED_ADMIN_REVIEW_NONCES = set()



@app.post(
    "/api/v1/verifications/{verification_id}/reviews"
)

def create_v11_review(
    verification_id: str,
    data: V11SignedReviewRequest
):
    from uuid import uuid4
    from datetime import datetime, timezone

    require_chain()

    verification = V11_VERIFICATION_RESULTS.get(
        verification_id
    )

    if verification is None:
        raise HTTPException(
            404,
            "Verification not found"
        )

    if verification.get("processing_status") != "COMPLETED":
        raise HTTPException(
            409,
            "Verification is not completed"
        )

    verdict = verification.get("verdict")

    if (
        data.review_status == "ACCEPTED"
        and verdict != "SUPPORTED"
    ):
        raise HTTPException(
            409,
            "Only SUPPORTED verification can be accepted"
        )

    # v1.1 관리자 상태 -> Solidity Enum
    action_map = {
        "ACCEPTED": 1,             # APPROVE
        "ACKNOWLEDGED": 2,         # CONFIRM
        "REVISION_REQUESTED": 3   # REQUEST_CHANGES
    }

    action = action_map[data.review_status]

    case_id = verification["case_id"]
    step_id = verification["step_id"]
    verification_hash = verification["verification_hash"]

    verification_id_hash = (
        "0x" + hashlib.sha256(
            verification_id.encode("utf-8")
        ).hexdigest()
    )


    # 1. 서명 유효기간 검사
    current_block_time = w3.eth.get_block(
        "latest"
    )["timestamp"]

    if data.deadline <= current_block_time:
        raise HTTPException(
            403, "Administrator signature expired"
        )

    # 2. 서명 재사용 방지
    nonce_key = (
        data.signer_address.lower(),
        data.nonce
    )

    if nonce_key in V11_USED_ADMIN_REVIEW_NONCES:
        raise HTTPException(
            409, "Administrator review nonce already used"
        )

    # 3. Verification과 검토 내용을 묶은
    #    서명 메시지 생성
    message = build_v11_admin_review_message(
        verification_id,
        verification_hash,
        data
    )


    try:
        recovered = Account.recover_message(
            encode_defunct(text=message),
            signature=data.signature
        )
    except (ValueError, TypeError, BadSignature):
        raise HTTPException(
            status_code=403,
            detail="Invalid administrator signature"
        )

    # 4. 요청한 주소와 실제 서명자 비교
    if recovered.lower() != data.signer_address.lower():
        raise HTTPException(
            403, "Administrator signature mismatch"
        )

    # 5. 컨트랙트에 등록된 관리자와 비교
    onchain_admin = contract.functions.admin().call()

    if recovered.lower() != onchain_admin.lower():
        raise HTTPException(
            403, "Signer is not contract administrator"
        )

    admin = recovered


    # 관리자 권한은 Solidity onlyAdmin에서 강제한다.
    # 트랜잭션 제출 전에 사전 검증도 수행한다.
    try:
        contract.functions.recordVerificationReview(
            case_uint(case_id),
            step_id,
            verification_id_hash,
            verification_hash,
            action
        ).call({"from": admin})

        tx = contract.functions.recordVerificationReview(
            case_uint(case_id),
            step_id,
            verification_id_hash,
            verification_hash,
            action
        ).transact({"from": admin})

        receipt = w3.eth.wait_for_transaction_receipt(
            tx,
            timeout=120
        )

        if receipt.status != 1:
            raise HTTPException(
                409,
                "Administrator review transaction failed"
            )

        # 기록 확인: 해당 트랜잭션의 이벤트를 검증한다.
        events = (
            contract.events.VerificationReviewAnchored()
            .process_receipt(receipt)
        )

        expected_event = any(
            event["args"]["caseId"] == case_uint(case_id)
            and event["args"]["stepId"] == step_id
            and Web3.to_hex(
                event["args"]["verificationIdHash"]
            ).lower() == verification_id_hash.lower()
            and Web3.to_hex(
                event["args"]["verificationHash"]
            ).lower() == verification_hash.lower()
            and int(event["args"]["action"]) == action
            and event["args"]["reviewer"].lower() == admin.lower()
            for event in events
        )

        if not expected_event:
            raise HTTPException(
                409,
                "Administrator review event mismatch"
            )

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            409,
            f"Administrator review rejected: {exc}"
        )

    review = {
        "schema_version": "1.1",
        "review_id": "REVIEW-" + uuid4().hex,
        "case_id": case_id,
        "step_id": step_id,
        "verification_id": verification_id,
        "verification_hash": verification_hash,
        "review_status": data.review_status,
        "reviewer_id": admin,
        "reviewed_at": datetime.now(
            timezone.utc
        ).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "reason_code": data.reason_code,
        "reason_text": data.reason_text
    }

    review["review_hash"] = v11_sha256(review)
    review["review_tx_hash"] = tx.hex()
    V11_USED_ADMIN_REVIEW_NONCES.add(nonce_key)

    return v11_success(review)