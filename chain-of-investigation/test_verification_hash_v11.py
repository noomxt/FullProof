
from hash_utils import (
    hash_claim_text,
    hash_proof_refs,
    hash_verification,
)

claim_hash = hash_claim_text("테스트 Claim 원문")
proof_refs = []

base = {
    "schema_version": "1.1",
    "verification_id": "VER-TEST-001",
    "case_id": "CASE-TEST-001",
    "step_id": 0,
    "claim_ref": {
        "claim_id": "CLAIM-001",
        "claim_version": 1,
        "claim_hash": claim_hash,
    },
    "proof_refs": proof_refs,
    "processing_status": "COMPLETED",
    "verdict": "INSUFFICIENT",
    "conflicts": [
        {
            "field": "result",
            "reason_code": "RESULT_MISMATCH",
            "claim_value": "",
            "proof_value": "FAIL",
        },
        {
            "field": "result",
            "reason_code": "RESULT_MISMATCH",
            "claim_value": None,
            "proof_value": "FAIL",
        },
    ],
    "missing_information": ["target", "occurred_at"],
    "reason_text": "테스트용 검증 결과",
    "evidence_refs": [],
    "review_required": False,
    "decision_policy_version": "1.0",
    "policy_hash": "0x" + "a" * 64,
    "proof_refs_hash": hash_proof_refs(proof_refs),
}

first = dict(base)

second = dict(base)
second["conflicts"] = list(reversed(base["conflicts"]))
second["missing_information"] = list(
    reversed(base["missing_information"])
)

hash1 = hash_verification(first)
hash2 = hash_verification(second)

print("첫 번째 해시:", hash1)
print("두 번째 해시:", hash2)
print("해시 일치 여부:", hash1 == hash2)

assert hash1 == hash2

print("STEP 63 테스트 통과!")
