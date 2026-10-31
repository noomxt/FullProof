
from hash_utils import hash_proof_content

proof = {
    "schema_version": "1.1",
    "proof_id": "PROOF-001",
    "proof_version": 1,
    "case_id": "CASE-001",
    "step_id": 0,
    "issuer_agency_id": "TELECOM-001",
    "agency_address": "0x0000000000000000000000000000000000000001",
    "proof_type": "CALL_LOG",
    "call_id": "CALL-001",
    "target_id": "SUBJECT-DEMO-01",
    "action_type": "PHONE_CALL",
    "proof_occurred_at": "2026-10-18T05:05:00Z",
    "proof_issued_at": "2026-10-18T05:30:00Z",
    "result": "CALL_FAILED",
    "source_sha256": "0x" + "a" * 64,
}

hash_a = hash_proof_content(proof)

proof_other = {**proof, "call_id": "CALL-002"}
hash_b = hash_proof_content(proof_other)

proof_reordered = dict(reversed(list(proof.items())))
hash_c = hash_proof_content(proof_reordered)

print("Proof 원본 해시:", hash_a)
print("call_id 변경 시 해시 변경:", hash_a != hash_b)
print("JSON 필드 순서 변경 시 동일:", hash_a == hash_c)
