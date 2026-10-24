"""Generate synthetic v1.1 contract vectors, not institution attestations."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import rfc8785
from verification_v11 import verify_v11, digest, PROOF_FIELDS, POLICY


def main():
    root = Path(__file__).resolve().parent.parent
    out = root / 'vector-check'
    vector = json.loads((out / 'vector.json').read_text(encoding='utf-8'))
    proof = deepcopy(vector['proof_content'])
    proof['proof_hash'] = digest(proof, rfc8785.dumps)
    text = '  2026년 10월 18일 오후 2시 SUBJECT-01 통화 성공.\r\n'
    claim = dict(schema_version='1.1', case_id=proof['case_id'], step_id=0,
                 claim_id='CLAIM-CONTRACT', claim_version=1, claim_text=text,
                 claim_hash='0x'+sha256(text.encode()).hexdigest(),
                 structured_claim=dict(schema_version='1.1', claim_id='CLAIM-CONTRACT', claim_version=1,
                    extraction_status='COMPLETED', model_name='synthetic-fixture',
                    prompt_version='fixture-v1', review_required=False,
                    actions=[dict(action_type='PHONE_CALL', action_result='SUCCESS', target_id='SUBJECT-01',
                        occurred_at=proof['proof_occurred_at'], source_excerpt='SUBJECT-01 통화 성공.')]))
    mapping = dict(claim_id=claim['claim_id'], claim_version=1, proof_id=proof['proof_id'], proof_version=1,
                   issuer_agency_id=proof['issuer_agency_id'], call_id=proof['call_id'], mapping_status='CONFIRMED')
    checks = []
    for verdict in ('SUPPORTED', 'CONTRADICTED', 'INSUFFICIENT'):
        p = deepcopy(proof)
        if verdict == 'CONTRADICTED':
            p['result'] = 'CALL_FAILED'
            p['proof_hash'] = digest({k:p[k] for k in PROOF_FIELDS}, rfc8785.dumps)
        result = verify_v11(claim=claim, proofs=[] if verdict == 'INSUFFICIENT' else [p],
                            mappings=[mapping], proof_validation={(p['proof_id'], 1): dict(
                                status='VALID', mapping_evidence_sufficient=True)}, canonicalize=rfc8785.dumps,
                            verification_id='VERIFY-CONTRACT-' + verdict)
        assert result['verdict'] == verdict
        content = {k:v for k,v in result.items() if k not in ('verification_hash','verification_tx_hash')}
        checks.append(dict(name='verification-'+verdict, content=content, expected_hash=result['verification_hash']))
        (out / ('response-' + verdict.lower() + '.json')).write_text(json.dumps(
            dict(success=True, data=result, error=None), ensure_ascii=False, indent=2), encoding='utf-8')
    checks += [dict(name='policy', content=POLICY, expected_hash=digest(POLICY, rfc8785.dumps)),
               dict(name='empty-proof-refs', content=dict(schema_version='1.1', proof_refs=[]),
                    expected_hash=digest(dict(schema_version='1.1', proof_refs=[]), rfc8785.dumps)),
               dict(name='proof-key-order', content=dict(reversed(list(vector['proof_content'].items()))),
                    expected_hash=proof['proof_hash'])]
    shared = dict(mock_input=True, claim_text=text, claim_hash=claim['claim_hash'], jcs_checks=checks)
    (out / 'common-v11.json').write_text(json.dumps(shared, ensure_ascii=False, indent=2), encoding='utf-8')
    print('Generated claim, proof, policy, refs and three verdict hash vectors')


if __name__ == '__main__':
    main()
