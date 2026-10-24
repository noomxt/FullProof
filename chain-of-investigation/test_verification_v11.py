"""Offline decision/adapter tests. Fixture serializer is NOT a JCS conformance test."""
import json
import unittest
from copy import deepcopy
from hashlib import sha256
from verification_v11 import verify_v11, digest, PROOF_FIELDS, POLICY


def fixture_bytes(obj):
    # Fixtures contain no floats or non-BMP keys. Production injects official JCS.
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()


class VerificationTests(unittest.TestCase):
    def setUp(self):
        text = 'SUBJECT-01 통화 성공'
        self.claim = dict(schema_version='1.1', case_id='CASE-001', step_id=0,
                          claim_id='CLAIM-001', claim_version=1, claim_text=text,
                          claim_hash='0x' + sha256(text.encode()).hexdigest(),
                          structured_claim=dict(schema_version='1.1', claim_id='CLAIM-001', claim_version=1, extraction_status='COMPLETED',
                            model_name='offline-fixture', prompt_version='fixture-v1', review_required=False,
                            actions=[dict(action_type='PHONE_CALL', action_result='SUCCESS', target_id='SUBJECT-01',
                                          occurred_at='2026-10-18T05:00:00Z', source_excerpt=text)]))
        self.proof = dict(schema_version='1.1', proof_id='PROOF-001', proof_version=1, case_id='CASE-001', step_id=0,
                          issuer_agency_id='TELECOM-001', agency_address='0x'+'1'*40, proof_type='CALL_LOG',
                          call_id='CALL-001', target_id='SUBJECT-01', action_type='PHONE_CALL',
                          proof_occurred_at='2026-10-18T05:00:00Z', proof_issued_at='2026-10-18T05:30:00Z',
                          result='CALL_CONNECTED', source_sha256='0x'+'a'*64)
        self.mapping = dict(claim_id='CLAIM-001', claim_version=1, proof_id='PROOF-001', proof_version=1,
                            issuer_agency_id='TELECOM-001', call_id='CALL-001', mapping_status='CONFIRMED')
        self.validation = {('PROOF-001', 1): dict(status='VALID', mapping_evidence_sufficient=True)}

    def run_case(self, has_proofs=True, **overrides):
        self.proof['proof_hash'] = digest({k:self.proof[k] for k in PROOF_FIELDS}, fixture_bytes)
        args = dict(claim=self.claim, proofs=[self.proof] if has_proofs else [], mappings=[self.mapping],
                    proof_validation=self.validation, canonicalize=fixture_bytes, verification_id='VERIFY-TEST')
        args.update(overrides)
        return verify_v11(**args)

    def test_supported(self):
        r = self.run_case()
        self.assertEqual(r['verdict'], 'SUPPORTED')
        self.assertEqual(r['processing_status'], 'COMPLETED')
        content = {k:v for k,v in r.items() if k not in ('verification_hash', 'verification_tx_hash')}
        self.assertEqual(r['verification_hash'], digest(content, fixture_bytes))

    def test_conflict(self):
        self.proof['result'] = 'CALL_FAILED'
        r = self.run_case()
        self.assertEqual(r['verdict'], 'CONTRADICTED')
        self.assertEqual(r['conflicts'][0]['reason_code'], 'RESULT_MISMATCH')

    def test_no_proof(self):
        r = self.run_case(False)
        self.assertEqual(r['verdict'], 'INSUFFICIENT')
        self.assertEqual(r['proof_refs'], [])
        self.assertIsNotNone(r['proof_refs_hash'])

    def test_mapping_and_validity(self):
        self.assertEqual(self.run_case(mappings=[])['verdict'], 'INSUFFICIENT')
        self.validation[('PROOF-001', 1)]['mapping_evidence_sufficient'] = False
        self.assertEqual(self.run_case()['verdict'], 'INSUFFICIENT')
        self.validation.clear()
        self.assertEqual(self.run_case()['verdict'], 'INSUFFICIENT')

    def test_unknown_not_conflict(self):
        self.proof['result'] = None
        self.assertEqual(self.run_case()['verdict'], 'INSUFFICIENT')

    def test_action_count(self):
        self.claim['structured_claim']['actions'] *= 2
        self.assertEqual(self.run_case()['processing_status'], 'NEEDS_REVIEW')
        self.claim['structured_claim']['actions'] = []
        self.assertEqual(self.run_case()['verdict'], 'INSUFFICIENT')

    def test_failed(self):
        self.claim['structured_claim']['extraction_status'] = 'FAILED'
        r = self.run_case()
        self.assertEqual(r['processing_status'], 'FAILED')
        self.assertIsNone(r['verdict'])

    def test_bad_reference(self):
        self.proof['case_id'] = 'OTHER'
        with self.assertRaisesRegex(ValueError, 'REFERENCE_MISMATCH'):
            self.run_case()

    def test_duplicates_and_tampering(self):
        self.run_case()
        with self.assertRaisesRegex(ValueError, 'DUPLICATE'):
            self.run_case(proofs=[self.proof, deepcopy(self.proof)])
        changed = deepcopy(self.proof)
        changed['call_id'] = 'OTHER'
        with self.assertRaisesRegex(ValueError, 'PROOF_HASH_MISMATCH'):
            self.run_case(proofs=[changed])

    def test_time_boundary(self):
        self.proof['proof_occurred_at'] = '2026-10-18T05:10:00Z'
        self.assertEqual(self.run_case()['verdict'], 'SUPPORTED')
        self.proof['proof_occurred_at'] = '2026-10-18T05:10:01Z'
        self.assertEqual(self.run_case()['verdict'], 'CONTRADICTED')

    def test_missing_field_takes_priority_over_result_conflict(self):
        for side, field in (('claim', 'target_id'), ('proof', 'target_id'),
                            ('claim', 'occurred_at'), ('proof', 'proof_occurred_at')):
            for value in (None, '', '   '):
                with self.subTest(side=side, field=field, value=value):
                    self.setUp()
                    record = self.proof if side == 'proof' else self.claim['structured_claim']['actions'][0]
                    record[field] = value
                    self.proof['result'] = 'CALL_FAILED'
                    result = self.run_case()
                    self.assertEqual(result['verdict'], 'INSUFFICIENT')
                    self.assertIn('occurred_at' if field == 'proof_occurred_at' else field,
                                  result['missing_information'])

    def test_unknown_result_takes_priority_over_target_conflict(self):
        for side in ('claim', 'proof'):
            for value in ('UNKNOWN', None, '') if side == 'proof' else ('UNKNOWN',):
                with self.subTest(side=side, value=value):
                    self.setUp()
                    self.proof['target_id'] = 'OTHER-SUBJECT'
                    if side == 'claim':
                        self.claim['structured_claim']['actions'][0]['action_result'] = value
                    else:
                        self.proof['result'] = value
                    result = self.run_case()
                    self.assertEqual(result['verdict'], 'INSUFFICIENT')
                    self.assertIn('action_result', result['missing_information'])

    def test_untrusted_proof_cannot_establish_conflict(self):
        for status in ('PENDING', 'INVALID', 'FAILED', None):
            with self.subTest(status=status):
                self.setUp()
                self.proof['result'] = 'CALL_FAILED'
                self.validation[('PROOF-001', 1)]['status'] = status
                result = self.run_case()
                self.assertEqual(result['verdict'], 'INSUFFICIENT')
                self.assertIn('PROOF_NOT_VALIDATED', result['missing_information'])
                self.assertEqual(result['conflicts'], [])

    def test_wrong_mapping_cannot_establish_conflict(self):
        changes = [dict(mapping_status=s) for s in ('PENDING', 'AMBIGUOUS', 'REJECTED')]
        changes += [dict(claim_version=2), dict(proof_version=2),
                    dict(issuer_agency_id='OTHER'), dict(call_id='CALL-002')]
        for change in changes:
            with self.subTest(change=change):
                self.setUp()
                self.proof['result'] = 'CALL_FAILED'
                self.mapping.update(change)
                result = self.run_case()
                self.assertEqual(result['verdict'], 'INSUFFICIENT')
                self.assertIn('PROOF_MAPPING_AMBIGUOUS', result['missing_information'])
                self.assertEqual(result['conflicts'], [])

    def test_manual_selection_alone_does_not_establish_conflict(self):
        self.proof['result'] = 'CALL_FAILED'
        self.validation[('PROOF-001', 1)]['mapping_evidence_sufficient'] = False
        self.assertEqual(self.run_case()['verdict'], 'INSUFFICIENT')

    def test_confirmed_conflict_in_both_directions(self):
        for claim_result, proof_result in (('SUCCESS', 'CALL_FAILED'), ('FAIL', 'CALL_CONNECTED')):
            with self.subTest(claim_result=claim_result):
                self.setUp()
                self.claim['structured_claim']['actions'][0]['action_result'] = claim_result
                self.proof['result'] = proof_result
                result = self.run_case()
                self.assertEqual(result['verdict'], 'CONTRADICTED')
                self.assertEqual(result['missing_information'], [])
                self.assertEqual(result['conflicts'][0]['reason_code'], 'RESULT_MISMATCH')

    def test_invalid_time_is_input_error_not_verdict(self):
        self.proof['proof_occurred_at'] = '2026-10-18 05:00:00'
        with self.assertRaisesRegex(ValueError, 'INVALID_UTC_TIMESTAMP'):
            self.run_case()

    def test_policy_and_claim_hash(self):
        p = deepcopy(POLICY)
        p['semantic_analysis_required'] = True
        with self.assertRaises(ValueError):
            self.run_case(policy=p)
        self.claim['claim_text'] += ' '
        with self.assertRaisesRegex(ValueError, 'CLAIM_HASH_MISMATCH'):
            self.run_case()

    def test_original_proof_preserved(self):
        from verification import normalize_proof
        self.run_case()
        original = deepcopy(self.proof)
        normalized = normalize_proof(self.proof)
        self.assertEqual(normalized['action_result'], 'SUCCESS')
        self.assertEqual(normalized['occurred_at'], self.proof['proof_occurred_at'])
        self.assertEqual(self.proof, original)

    def test_real_jcs_and_route(self):
        import rfc8785
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from verification_v11 import register_v11_routes
        self.proof['proof_hash'] = digest({k:self.proof[k] for k in PROOF_FIELDS}, rfc8785.dumps)
        args = dict(claim=self.claim, proofs=[self.proof], mappings=[self.mapping],
                    proof_validation=self.validation, canonicalize=rfc8785.dumps)
        app = FastAPI()
        register_v11_routes(app)
        with TestClient(app) as client:
            unavailable = client.post('/api/v1/verifications', json={})
        self.assertEqual(unavailable.status_code, 503)
        self.assertFalse(unavailable.json()['success'])
        self.assertIsNone(unavailable.json()['data'])
        self.assertEqual(unavailable.json()['error']['code'], 'V11_BACKEND_RESOLVER_REQUIRED')
        app = FastAPI()
        received = []
        def resolve(request, body):
            received.append((request.url.path, body))
            return args
        register_v11_routes(app, resolver=resolve)
        body = {'claim_id': 'CLAIM-001', 'claim_version': 1}
        original_args = deepcopy(args)
        with TestClient(app) as client:
            for verdict in ('SUPPORTED', 'CONTRADICTED', 'INSUFFICIENT'):
                with self.subTest(verdict=verdict):
                    args = deepcopy(original_args)
                    if verdict == 'CONTRADICTED':
                        args['proofs'][0]['result'] = 'CALL_FAILED'
                        proof = args['proofs'][0]
                        proof['proof_hash'] = digest({k: proof[k] for k in PROOF_FIELDS}, rfc8785.dumps)
                    elif verdict == 'INSUFFICIENT':
                        args.update(proofs=[], mappings=[], proof_validation={})
                    response = client.post('/api/v1/verifications', json=body)
                    self.assertEqual(response.status_code, 200, response.text)
                    envelope = response.json()
                    self.assertTrue(envelope['success'])
                    self.assertIsNone(envelope['error'])
                    self.assertEqual(envelope['data']['verdict'], verdict)
                    self.assertIsNone(envelope['data']['verification_tx_hash'])
                    content = {k: v for k, v in envelope['data'].items()
                               if k not in ('verification_hash', 'verification_tx_hash')}
                    self.assertEqual(envelope['data']['verification_hash'], digest(content, rfc8785.dumps))
                    if verdict == 'INSUFFICIENT':
                        self.assertIn('PROOF_MISSING', envelope['data']['missing_information'])
            self.assertEqual(received, [('/api/v1/verifications', body)] * 3)
            for invalid in ('hash', 'reference', 'timestamp'):
                with self.subTest(invalid=invalid):
                    args = deepcopy(original_args)
                    if invalid == 'hash':
                        args['claim']['claim_text'] += '변조'
                    elif invalid == 'reference':
                        args['proofs'][0]['case_id'] = 'OTHER-CASE'
                    else:
                        args['claim']['structured_claim']['actions'][0]['occurred_at'] = 'invalid'
                    response = client.post('/api/v1/verifications', json=body)
                    self.assertEqual(response.status_code, 422, response.text)
                    envelope = response.json()
                    self.assertFalse(envelope['success'])
                    self.assertIsNone(envelope['data'])
                    self.assertEqual(envelope['error']['code'], 'INVALID_VERIFICATION_INPUT')
                    self.assertEqual(envelope['error']['details'], {})
            malformed = client.post('/api/v1/verifications', content='{',
                                    headers={'Content-Type': 'application/json'})
            self.assertEqual(malformed.status_code, 422)
            self.assertEqual(malformed.json()['error']['code'], 'INVALID_VERIFICATION_INPUT')

    def test_parser_adapter(self):
        from unittest.mock import patch
        from verification_v11 import extract_v11
        parsed = dict(parse_status='SUCCESS', actions=[dict(action_type='PHONE_CALL', status_claim='SUCCESS',
                      target_id='SUBJECT-01', claimed_time='2026-10-18 14:00:00', source_text=self.claim['claim_text'])])
        with patch('ai_engine.parse_claim_with_llm', return_value=parsed), patch('ai_provider.model_name', return_value='test-model'):
            result = extract_v11(self.claim)
        self.assertEqual(result['actions'][0]['occurred_at'], '2026-10-18T05:00:00Z')
        self.assertNotIn('call_id', result['actions'][0])


if __name__ == '__main__':
    unittest.main()
