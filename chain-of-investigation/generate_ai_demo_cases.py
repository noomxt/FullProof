"""Build synthetic MVP AI examples through extract_v11 and verify_v11.

No API keys, provider calls, wallet signatures or blockchain transactions.
Proof trust flags exist only inside this offline fixture harness, not requests.
"""
import argparse
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from types import SimpleNamespace
import rfc8785
from verification_v11 import POLICY, PROOF_FIELDS, digest, extract_v11, verify_v11


SAMPLE_AGENCY = '0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC'


def build_case(verdict, agency=SAMPLE_AGENCY):
    assert verdict in ('SUPPORTED', 'CONTRADICTED', 'INSUFFICIENT')
    case_id, claim_id = 'CASE-DEMO-'+verdict, 'CLAIM-DEMO-'+verdict
    call_id = 'CALL-DEMO-'+verdict
    excerpt = '2026년 10월 18일 오후 2시에 SUBJECT-01과 통화 연결에 성공했다.'
    text = excerpt + f' CALL_REF[TELECOM-001:{call_id}]'
    action = dict(action_type='PHONE_CALL', action_result='SUCCESS', target_id='SUBJECT-01',
                  occurred_at='2026-10-18T05:00:00Z', source_excerpt=excerpt)
    def fake_parse(**kwargs):
        return SimpleNamespace(model='offline-demo-fixture', choices=[SimpleNamespace(message=SimpleNamespace(
            refusal=None, parsed=dict(actions=[deepcopy(action)], review_reasons=[])))])
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(parse=fake_parse)))
    claim = dict(schema_version='1.1', claim_id=claim_id, claim_version=1,
                 case_id=case_id, step_id=0, claim_text=text,
                 claim_hash='0x'+sha256(text.encode('utf-8')).hexdigest())
    structured = extract_v11(claim, client=client)
    claim['structured_claim'] = structured
    assert structured['actions'] == [action] and structured['extraction_status'] == 'COMPLETED'

    proofs, mappings, validation = [], [], {}
    proof_base = mapping_request = None
    comparison_result = None
    if verdict != 'INSUFFICIENT':
        source = dict(issuer_agency_id='TELECOM-001', call_id=call_id, target_id='SUBJECT-01',
                      action_type='PHONE_CALL', proof_occurred_at=action['occurred_at'],
                      proof_issued_at='2026-10-18T05:30:00Z',
                      result='CALL_CONNECTED' if verdict == 'SUPPORTED' else 'CALL_FAILED')
        source_bytes = rfc8785.dumps(source)
        proof = dict(schema_version='1.1', proof_id='PROOF-DEMO-'+verdict, proof_version=1,
                     case_id=case_id, step_id=0, agency_address=agency, proof_type='CALL_LOG',
                     **source, source_sha256='0x'+sha256(source_bytes).hexdigest())
        proof['proof_hash'] = digest({k:proof[k] for k in PROOF_FIELDS}, rfc8785.dumps)
        proofs.append(proof)
        # Internal-only test assumptions: actual backend must validate all of these.
        mappings.append(dict(claim_id=claim_id, claim_version=1, claim_hash=claim['claim_hash'],
            proof_id=proof['proof_id'], proof_version=1, issuer_agency_id='TELECOM-001',
            call_id=call_id, mapping_status='CONFIRMED'))
        validation[(proof['proof_id'],1)] = dict(status='VALID', mapping_evidence_sufficient=True)
        proof_base = dict(proof_content={k:proof[k] for k in PROOF_FIELDS},
                          source_text=source_bytes.decode('utf-8'))
        mapping_request = dict(case_id=case_id, step_id=0, claim_version=1, claim_text=text,
            proof_id=proof['proof_id'], proof_version=1, issuer_agency_id='TELECOM-001',
            call_id=call_id, mapping_method='MANUAL_SELECTION', mapping_status='PENDING')
        comparison_result = 'SUCCESS' if verdict == 'SUPPORTED' else 'FAIL'
    result = verify_v11(claim=claim, proofs=proofs, mappings=mappings, proof_validation=validation,
        canonicalize=rfc8785.dumps, verification_id='VERIFY-DEMO-'+verdict,
        registered_policy_hash=digest(POLICY, rfc8785.dumps))
    assert result['verdict'] == verdict and result['processing_status'] == 'COMPLETED'
    assert result['verification_tx_hash'] is None
    if verdict == 'CONTRADICTED':
        assert result['conflicts'] == [dict(field='action_result', claim_value='SUCCESS',
                                           proof_value='FAIL', reason_code='RESULT_MISMATCH')]
    if verdict == 'INSUFFICIENT':
        assert result['proof_refs'] == [] and result['missing_information'] == ['PROOF_MISSING']
    assert 'call_id' not in structured['actions'][0]
    assert structured['actions'][0]['source_excerpt'] in text
    for proof in proofs:
        assert f"CALL_REF[{proof['issuer_agency_id']}:{proof['call_id']}]" in text
        assert '0x'+sha256(proof_base['source_text'].encode()).hexdigest() == proof['source_sha256']
    return dict(mock_data=True, expected_verdict=verdict,
        comparison=dict(claim_result='SUCCESS', normalized_proof_result=comparison_result),
        requests=dict(case_create=dict(case_id=case_id, title='AI MVP '+verdict),
            step_create=dict(step_name='통화 확인', is_required=True),
            claim_create=dict(claim_id=claim_id, claim_version=1, step_id=0, claim_text=text),
            extract=dict(case_id=case_id, claim_version=1),
            proof_draft_base=proof_base, mapping_create=mapping_request,
            verification=dict(claim=dict(case_id=case_id, claim_id=claim_id, claim_version=1), proofs=proofs)),
        expected_extraction=dict(success=True, data=structured, error=None),
        expected_verification=dict(success=True, data=result, error=None))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, default=Path(__file__).parent / 'docs' / 'ai-demo-v1.1')
    parser.add_argument('--agency-address', default=SAMPLE_AGENCY)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    for verdict in ('SUPPORTED', 'CONTRADICTED', 'INSUFFICIENT'):
        case = build_case(verdict, args.agency_address)
        (args.out / (verdict.lower()+'.json')).write_text(
            json.dumps(case, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        print(verdict, 'PASS', 'conflicts='+str(len(case['expected_verification']['data']['conflicts'])),
              'missing='+str(case['expected_verification']['data']['missing_information']))


if __name__ == '__main__':
    main()
