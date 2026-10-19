
import hashlib
import jcs


def hash_claim_text(claim_text: str) -> str:
    """
    Claim 원문을 SHA-256으로 해시한다.

    공백, 줄바꿈, 문장부호 등 원문을 변경하지 않고
    입력받은 문자열 그대로 UTF-8로 인코딩한다.
    """
    if not isinstance(claim_text, str):
        raise TypeError("claim_text must be a string")

    if not claim_text:
        raise ValueError("claim_text must not be empty")

    return "0x" + hashlib.sha256(
        claim_text.encode("utf-8")
    ).hexdigest()


def hash_canonical_json(data: dict) -> str:
    """
    JSON 객체를 JCS로 직렬화한 뒤
    SHA-256 해시를 계산한다.
    """
    if not isinstance(data, dict):
        raise TypeError("data must be a dictionary")

    canonical_bytes = jcs.canonicalize(data)

    return "0x" + hashlib.sha256(
        canonical_bytes
    ).hexdigest()


def hash_proof_refs(proof_refs: list) -> str:
    """
    Proof 참조 목록의 SHA-256 해시를 계산한다.

    각 Proof는 proof_id, proof_version, proof_hash를 가진다.
    ID와 버전 기준으로 정렬하고 중복을 거부한다.
    """
    if not isinstance(proof_refs, list):
        raise TypeError("proof_refs must be a list")

    normalized = []
    seen = set()

    for ref in proof_refs:
        if not isinstance(ref, dict):
            raise TypeError("each proof ref must be a dictionary")

        if set(ref) != {"proof_id", "proof_version", "proof_hash"}:
            raise ValueError("invalid proof reference fields")

        proof_id = ref["proof_id"]
        version = ref["proof_version"]
        proof_hash = ref["proof_hash"]

        if not isinstance(proof_id, str) or not proof_id:
            raise ValueError("invalid proof_id")

        if type(version) is not int or version < 1:
            raise ValueError("invalid proof_version")

        if (
            not isinstance(proof_hash, str)
            or len(proof_hash) != 66
            or not proof_hash.startswith("0x")
            or any(c not in "0123456789abcdef" for c in proof_hash[2:])
        ):
            raise ValueError("invalid proof_hash")

        key = (proof_id, version)
        if key in seen:
            raise ValueError("duplicate proof reference")
        seen.add(key)

        normalized.append({
            "proof_id": proof_id,
            "proof_version": version,
            "proof_hash": proof_hash,
        })

    normalized.sort(
        key=lambda ref: (ref["proof_id"], ref["proof_version"])
    )

    payload = {
        "schema_version": "1.1",
        "proof_refs": normalized,
    }

    return hash_canonical_json(payload)


def hash_policy(policy: dict) -> str:
    """
    FullProof v1.1 정책 객체 전체를 JCS + SHA-256으로 해시한다.
    """
    if not isinstance(policy, dict):
        raise TypeError("policy must be a dictionary")

    required_keys = {
        "schema_version",
        "policy_id",
        "policy_version",
        "required_fields",
        "time_tolerance_seconds",
        "proof_mapping_required",
        "semantic_analysis_required",
    }

    if set(policy.keys()) != required_keys:
        raise ValueError("invalid policy fields")

    if policy["schema_version"] != "1.1":
        raise ValueError("unsupported schema_version")

    if not isinstance(policy["policy_id"], str) or not policy["policy_id"]:
        raise ValueError("invalid policy_id")

    if not isinstance(policy["policy_version"], str) or not policy["policy_version"]:
        raise ValueError("invalid policy_version")

    fields = policy["required_fields"]

    if not isinstance(fields, list):
        raise TypeError("required_fields must be a list")

    if any(not isinstance(f, str) or not f for f in fields):
        raise ValueError("invalid required_fields")

    if (
        type(policy["time_tolerance_seconds"]) is not int
        or policy["time_tolerance_seconds"] < 0
    ):
        raise ValueError("invalid time_tolerance_seconds")

    for key in ("proof_mapping_required", "semantic_analysis_required"):
        if type(policy[key]) is not bool:
            raise ValueError(f"{key} must be a boolean")

    normalized_policy = {
        **policy,
        "required_fields": sorted(set(fields)),
    }

    return hash_canonical_json(normalized_policy)


def hash_proof_content(proof: dict) -> str:
    """
    FullProof v1.1 Proof의 필수 필드를 검증한 뒤
    JCS + SHA-256 해시를 계산한다.
    """
    if not isinstance(proof, dict):
        raise TypeError("proof must be a dictionary")

    required_keys = {
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
    }

    if set(proof.keys()) != required_keys:
        raise ValueError("invalid proof_content fields")

    if proof["schema_version"] != "1.1":
        raise ValueError("unsupported schema_version")

    for key in (
        "proof_id", "case_id", "issuer_agency_id",
        "agency_address", "proof_type", "action_type",
        "proof_issued_at"
    ):
        if not isinstance(proof[key], str) or not proof[key]:
            raise ValueError(f"invalid {key}")

    if type(proof["proof_version"]) is not int or proof["proof_version"] < 1:
        raise ValueError("invalid proof_version")

    if type(proof["step_id"]) is not int or proof["step_id"] < 0:
        raise ValueError("invalid step_id")

    for key in ("call_id", "target_id", "proof_occurred_at", "result"):
        if proof[key] is not None and not isinstance(proof[key], str):
            raise ValueError(f"invalid {key}")

    for key in ("source_sha256",):
        value = proof[key]
        if (
            not isinstance(value, str)
            or len(value) != 66
            or not value.startswith("0x")
            or any(c not in "0123456789abcdef" for c in value[2:])
        ):
            raise ValueError(f"invalid {key}")

    return hash_canonical_json(proof)


def hash_verification(verification: dict) -> str:
    """
    FullProof v1.1 검증 결과를 JCS + SHA-256으로 해시한다.
    """
    if not isinstance(verification, dict):
        raise TypeError("verification must be a dictionary")

    required_keys = {
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
    }

    if set(verification.keys()) != required_keys:
        raise ValueError("invalid verification fields")

    if verification["schema_version"] != "1.1":
        raise ValueError("unsupported schema_version")

    claim_ref = verification["claim_ref"]

    if not isinstance(claim_ref, dict) or set(claim_ref) != {
        "claim_id", "claim_version", "claim_hash"
    }:
        raise ValueError("invalid claim_ref")

    if not isinstance(claim_ref["claim_id"], str) or not claim_ref["claim_id"]:
        raise ValueError("invalid claim_id")

    if type(claim_ref["claim_version"]) is not int or claim_ref["claim_version"] < 1:
        raise ValueError("invalid claim_version")

    def valid_hash(value):
        return (
            isinstance(value, str)
            and len(value) == 66
            and value.startswith("0x")
            and all(c in "0123456789abcdef" for c in value[2:])
        )

    for key in ("claim_hash",):
        if not valid_hash(claim_ref[key]):
            raise ValueError(f"invalid {key}")

    for key in ("policy_hash", "proof_refs_hash"):
        if not valid_hash(verification[key]):
            raise ValueError(f"invalid {key}")

    if verification["verdict"] not in (
        "SUPPORTED", "CONTRADICTED", "INSUFFICIENT"
    ):
        raise ValueError("invalid verdict")

    if verification["processing_status"] not in (
        "COMPLETED", "NEEDS_REVIEW"
    ):
        raise ValueError("invalid processing_status")

    if type(verification["review_required"]) is not bool:
        raise ValueError("review_required must be boolean")

    for key in ("conflicts", "missing_information", "evidence_refs"):
        if not isinstance(verification[key], list):
            raise ValueError(f"{key} must be a list")

    if not isinstance(verification["reason_text"], str):
        raise ValueError("reason_text must be a string")

    calculated_refs_hash = hash_proof_refs(verification["proof_refs"])

    if calculated_refs_hash != verification["proof_refs_hash"]:
        raise ValueError("proof_refs_hash mismatch")


    normalized = dict(verification)

    normalized["proof_refs"] = sorted(
        verification["proof_refs"],
        key=lambda ref: (ref["proof_id"], ref["proof_version"])
    )


    def conflict_value_key(value):
        if value is None:
            return (0, "")

        if isinstance(value, str):
            return (1, value)

        raise ValueError("conflict values must be strings or null")

    normalized["conflicts"] = sorted(
        verification["conflicts"],
        key=lambda item: (
            item["field"],
            item["reason_code"],
            conflict_value_key(item["claim_value"]),
            conflict_value_key(item["proof_value"]),
        )
    )


    normalized["missing_information"] = sorted(
        verification["missing_information"]
    )

    normalized["evidence_refs"] = sorted(
        set(verification["evidence_refs"])
    )

    return hash_canonical_json(normalized)
