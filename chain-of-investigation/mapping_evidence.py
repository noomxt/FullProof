"""Narrow MVP link assessment, independent of Claim/Proof success or time proximity.

Only explicit original Claim references CALL_REF[issuer:call_id], a signed
officer confirmation, and matching institution source records are accepted.
This is a demo evidence format, not a general natural-language matching rule.
"""
import hashlib
import json
from eth_account import Account
from eth_account.messages import encode_defunct


def assess_mapping_link(claim, proof, mapping, draft, allowed_reviewers, build_message):
    if mapping.get('mapping_status') != 'CONFIRMED' or not proof.get('call_id'):
        return False
    pairs = dict(claim_id=claim['claim_id'], claim_version=claim['claim_version'],
                 claim_hash=claim['claim_hash'], proof_id=proof['proof_id'],
                 proof_version=proof['proof_version'], issuer_agency_id=proof['issuer_agency_id'],
                 call_id=proof['call_id'])
    if any(mapping.get(k) != v for k, v in pairs.items()):
        return False
    reference = f"CALL_REF[{proof['issuer_agency_id']}:{proof['call_id']}]"
    if reference not in claim['claim_text']:
        return False
    if draft.get('status') != 'ANCHORED':
        return False
    evidence = mapping.get('confirmation_evidence') or {}
    if (evidence.get('claim_hash') != claim['claim_hash'] or
            evidence.get('proof_hash') != draft['proof_hash'] or
            evidence.get('source_sha256') != proof['source_sha256']):
        return False
    source_bytes = draft.get('source_bytes')
    if not isinstance(source_bytes, bytes) or '0x'+hashlib.sha256(source_bytes).hexdigest() != proof['source_sha256']:
        return False
    try:
        source = json.loads(source_bytes)
        if not isinstance(source, dict) or any(source.get(k) != proof[k] for k in
                ('issuer_agency_id', 'call_id', 'target_id', 'action_type', 'proof_occurred_at')):
            return False
        message = build_message(claim['case_id'], mapping, claim['claim_hash'],
                                draft['proof_hash'], proof['source_sha256'], evidence['note'])
        recovered = Account.recover_message(encode_defunct(text=message), signature=evidence['signature'])
    except (ValueError, TypeError, KeyError, UnicodeError):
        return False
    return (recovered.lower() in allowed_reviewers and
            recovered.lower() == str(mapping.get('confirmed_by', '')).lower())
