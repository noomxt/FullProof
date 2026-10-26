
from hash_utils import hash_proof_refs, hash_verification

proof_refs = [
    {
        "proof_id": "PROOF-001",
        "proof_version": 1,
        "proof_hash": "0x" + "b" * 64,
    }
]

verification = {
    "schema_version": "1.1",
    "verification_id": "VERIFY-001",
    "case_id": "CASE-001",
    "step_id": 0,
    "claim_ref": {
        "claim_id": "CLAIM-001",
        "claim_version": 1,
        "claim_hash": "0x" + "a" * 64,
    },
    "proof_refs": proof_refs,
    "processing_status": "COMPLETED",
    "verdict": "CONTRADICTED",
    "conflicts": [
        {
            "field": "action_result",
            "claim_value": "SUCCESS",
            "proof_value": "FAIL",
            "reason_code": "RESULT_MISMATCH",
        }
    ],
    "missing_information": [],
    "reason_text": "통화 결과가 일치하지 않습니다.",
    "evidence_refs": ["PROOF-001"],
    "review_required": True,
    "decision_policy_version": "policy-v1",
    "policy_hash": "0x" + "c" * 64,
    "proof_refs_hash": hash_proof_refs(proof_refs),
}

original_hash = hash_verification(verification)

changed_verdict = {
    **verification,
    "verdict": "SUPPORTED",
}

print("검증 결과 해시:", original_hash)
print(
    "판정 변경 시 해시 변경:",
    original_hash != hash_verification(changed_verdict)
)
