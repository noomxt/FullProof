
import hashlib
import json

from eth_account.messages import encode_typed_data
from main import w3, contract, case_uint

# 로컬 Hardhat의 테스트용 통신사 계정
agency = w3.eth.accounts[2]

case_id = "CASE-PROOF-V11-001"
proof_id = "PROOF-TELECOM-V11-001"

proof_id_hash = "0x" + hashlib.sha256(
    proof_id.encode("utf-8")
).hexdigest()

# Proof 내용의 예시 해시
proof_hash = "0x" + hashlib.sha256(
    "통신사 테스트 통화 기록".encode("utf-8")
).hexdigest()

# 현재 블록 시각 기준
block_time = w3.eth.get_block("latest")["timestamp"]

request = {
    "caseId": case_uint(case_id),
    "stepId": 0,
    "proofIdHash": proof_id_hash,
    "proofVersion": 1,
    "proofHash": proof_hash,
    "occurredAt": block_time - 120,
    "issuedAt": block_time - 60,
    "agency": agency,
    "nonce": contract.functions.agencyNonces(agency).call(),
    "deadline": block_time + 3600,
}

domain = {
    "name": "FullProof",
    "version": "1",
    "chainId": w3.eth.chain_id,
    "verifyingContract": contract.address,
}

types = {
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
}

message = encode_typed_data(
    domain_data=domain,
    message_types=types,
    message_data=request,
)

# 로컬 Hardhat 계정에서 서명 요청
# 실제 운영에서는 기관 지갑이 직접 서명해야 함
signature = w3.provider.make_request(
    "eth_signTypedData_v4",
    [
        agency,
        json.dumps({
            "types": {
                **types,
                "EIP712Domain": [
                    {"name": "name", "type": "string"},
                    {"name": "version", "type": "string"},
                    {"name": "chainId", "type": "uint256"},
                    {"name": "verifyingContract", "type": "address"},
                ],
            },
            "primaryType": "ProofAttestation",
            "domain": domain,
            "message": {
                **request,
                "caseId": str(request["caseId"]),
                "stepId": str(request["stepId"]),
                "nonce": str(request["nonce"]),
            },
        }),
    ],
)

if "error" in signature:
    raise RuntimeError(signature["error"])

print("기관 주소:", agency)
print("Proof ID:", proof_id)
print("Proof 해시:", proof_hash)
print("서명 생성 성공:", bool(signature.get("result")))
print("서명:", signature.get("result"))

# FastAPI에 제출할 요청 JSON
api_payload = {
    "proof_version": 1,
    "case_id": case_id,
    "step_id": request["stepId"],
    "proof_id": proof_id,
    "proof_hash": proof_hash,
    "occurred_at": request["occurredAt"],
    "issued_at": request["issuedAt"],
    "agency": request["agency"],
    "nonce": request["nonce"],
    "deadline": request["deadline"],
    "signature": signature["result"],
}

print("\n=== FastAPI 요청 JSON ===")
print(json.dumps(api_payload, ensure_ascii=False, indent=2))
