"""v1.1 contract gaps: fail closed before a verdict, real HTTP adapter paths."""
import unittest
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch
from hashlib import sha256

import test_verification_v11 as fixtures
from test_verification_v11 import fixture_bytes
from verification_v11 import (verify_v11, digest, PROOF_FIELDS, extract_v11,
                              register_v11_routes, register_v11_extraction_route)


class ContractTests(unittest.TestCase):
    def setUp(self):
        fixture = fixtures.VerificationTests()
        fixture.setUp()
        self.claim, self.proof = fixture.claim, fixture.proof
        self.mapping, self.validation = fixture.mapping, fixture.validation

    def args(self):
        self.proof['proof_hash'] = digest({k:self.proof[k] for k in PROOF_FIELDS}, fixture_bytes)
        return dict(claim=self.claim, proofs=[self.proof], mappings=[self.mapping],
                    proof_validation=self.validation, canonicalize=fixture_bytes,
                    verification_id='VERIFY-CONTRACT')

    def test_malformed_extraction_rejected_even_without_proof(self):
        for invalid in ([], 'wrong', dict(actions=None),
                        dict(schema_version='1.0'), dict(review_required='false'),
                        dict(claim_version=True), dict(model_name=None), dict(prompt_version='')):
            with self.subTest(invalid=invalid):
                self.setUp()
                if isinstance(invalid, dict):
                    self.claim['structured_claim'].update(invalid)
                else:
                    self.claim['structured_claim'] = invalid
                args = self.args()
                args['proofs'] = []
                with self.assertRaises(ValueError):
                    verify_v11(**args)

    def test_invented_target_rejected_even_without_proof(self):
        self.claim['structured_claim']['actions'][0]['target_id'] = 'INVENTED'
        args = self.args(); args['proofs'] = []
        with self.assertRaisesRegex(ValueError, 'UNGROUNDED_TARGET_ID'):
            verify_v11(**args)

    def test_generated_call_id_in_action_is_rejected(self):
        self.claim['structured_claim']['actions'][0]['call_id'] = 'INVENTED'
        with self.assertRaises(ValueError):
            verify_v11(**self.args())

    def test_split_reason_preserves_inputs_and_hashes_final_reason(self):
        self.claim['structured_claim']['actions'] *= 2
        args = self.args(); before = deepcopy(args)
        result = verify_v11(**args)
        self.assertEqual(result['verdict'], 'INSUFFICIENT')
        self.assertIn('CLAIM_SPLIT_REQUIRED', result['missing_information'])
        self.assertIn('행동별', result['reason_text'])
        self.assertEqual(args, before)
        self.assertEqual(result['verification_hash'], digest({k:v for k,v in result.items()
            if k not in ('verification_hash', 'verification_tx_hash')}, fixture_bytes))

    def test_no_action_requests_confirmation(self):
        self.claim['structured_claim']['actions'] = []
        self.assertIn('CLAIM_ACTION_MISSING', verify_v11(**self.args())['missing_information'])

    def test_pending_is_not_a_final_insufficient_verdict(self):
        self.claim['structured_claim'].update(extraction_status='PENDING', actions=[])
        result = verify_v11(**self.args())
        self.assertEqual(result['processing_status'], 'PENDING')
        self.assertIsNone(result['verdict'])
        self.assertIn('EXTRACTION_PENDING', result['missing_information'])

    def test_bool_step_and_mapping_version_not_accepted_as_integer(self):
        self.proof['step_id'] = False
        with self.assertRaisesRegex(ValueError, 'INVALID_PROOF_STEP_ID'):
            verify_v11(**self.args())
        self.proof['step_id'] = 0
        self.mapping['proof_version'] = True
        self.assertEqual(verify_v11(**self.args())['verdict'], 'INSUFFICIENT')

    def test_invalid_extraction_input_skips_provider(self):
        for update in (dict(claim_id=''), dict(claim_version=True),
                       dict(claim_text=[]), dict(schema_version='1.0')):
            with self.subTest(update=update), patch('ai_engine.parse_claim_with_llm') as parser:
                with self.assertRaises(ValueError):
                    extract_v11(dict(self.claim, **update))
                parser.assert_not_called()

    def test_original_proof_result_not_rewritten(self):
        args = self.args(); original = deepcopy(self.proof)
        verify_v11(**args)
        self.assertEqual(self.proof, original)
        self.assertEqual(self.proof['result'], 'CALL_CONNECTED')

    def test_policy_full_content_affects_hash(self):
        from verification_v11 import POLICY
        first = verify_v11(**self.args())
        policy = dict(POLICY, policy_version='policy-v2', time_tolerance_seconds=601)
        second = verify_v11(**self.args(), policy=policy)
        self.assertNotEqual(first['policy_hash'], second['policy_hash'])
        self.assertEqual(second['decision_policy_version'], 'policy-v2')

    def test_registered_policy_cannot_change_under_same_version(self):
        from verification_v11 import POLICY
        original = verify_v11(**self.args())
        changed = dict(POLICY, time_tolerance_seconds=601)
        with self.assertRaisesRegex(ValueError, 'REGISTERED_POLICY_HASH_MISMATCH'):
            verify_v11(**self.args(), policy=changed, registered_policy_hash=original['policy_hash'])

    def test_expected_reference_hash_checked(self):
        result = verify_v11(**self.args())
        verify_v11(**self.args(), expected_proof_refs_hash=result['proof_refs_hash'])
        with self.assertRaisesRegex(ValueError, 'PROOF_REFS_HASH_MISMATCH'):
            verify_v11(**self.args(), expected_proof_refs_hash='0x'+'0'*64)

    def test_claim_whitespace_and_unicode_bytes_preserved(self):
        for suffix in (' ', '\n', '\r\n', '\u0301'):
            with self.subTest(suffix=repr(suffix)):
                self.setUp()
                self.claim['claim_text'] += suffix
                self.claim['claim_hash'] = '0x' + sha256(self.claim['claim_text'].encode()).hexdigest()
                args = self.args(); original = deepcopy(args)
                result = verify_v11(**args)
                self.assertEqual(result['claim_ref']['claim_hash'], self.claim['claim_hash'])
                self.assertEqual(args, original)

    def test_http_extract_uses_stored_claim_and_version(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        app = FastAPI()
        seen = []
        def resolver(request, claim_id, body):
            seen.append((claim_id, body))
            return self.claim
        action = dict(action_type='PHONE_CALL', action_result='SUCCESS', target_id='SUBJECT-01',
                      occurred_at='2026-10-18T05:00:00Z', source_excerpt='SUBJECT-01 통화 성공')
        def parse(**kwargs):
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(refusal=None,
                parsed=dict(actions=[action], review_reasons=[])))])
        client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(parse=parse)))
        register_v11_extraction_route(app, resolver=resolver, client=client)
        register_v11_routes(app, resolver=lambda request, body:self.args())
        with TestClient(app) as http:
            result = http.post('/api/v1/claims/CLAIM-001/extract', json={
                'claim_version':1, 'claim_text':'HTTP body is not authoritative'})
            self.assertEqual(result.status_code, 200, result.text)
            self.assertTrue(result.json()['success'])
            structured = result.json()['data']
            self.assertEqual(structured['actions'], [action])
            self.claim['structured_claim'] = structured
            verified = http.post('/api/v1/verifications', json={})
            self.assertEqual(verified.json()['data']['verdict'], 'SUPPORTED')
            self.assertEqual(http.post('/api/v1/claims/OTHER/extract', json={}).status_code, 422)
            self.assertEqual(http.post('/api/v1/claims/CLAIM-001/extract', json={'claim_version':2}).status_code, 422)
            self.assertEqual(http.post('/api/v1/claims/CLAIM-001/extract', json=[]).status_code, 422)
            self.assertEqual(http.post('/api/v1/verifications', json=[]).status_code, 422)
            self.validation[('PROOF-001', 1)]['status'] = 'PENDING'
            spoof = http.post('/api/v1/verifications', json={'proof_validation': {
                'status':'VALID', 'mapping_evidence_sufficient':True}})
            self.assertEqual(spoof.json()['data']['verdict'], 'INSUFFICIENT')

    def test_http_authorization_and_unconfigured_extraction(self):
        from fastapi import FastAPI, HTTPException
        from fastapi.testclient import TestClient
        app = FastAPI()
        register_v11_extraction_route(app)
        with TestClient(app) as http:
            self.assertEqual(http.post('/api/v1/claims/CLAIM-001/extract', json={}).status_code, 503)
        def denied(*args):
            raise HTTPException(403, 'Not authorized')
        app = FastAPI()
        register_v11_extraction_route(app, resolver=denied)
        register_v11_routes(app, resolver=denied)
        with TestClient(app) as http:
            for path in ('/api/v1/claims/CLAIM-001/extract', '/api/v1/verifications'):
                result = http.post(path, json={})
                self.assertEqual(result.status_code, 403)
                self.assertFalse(result.json()['success'])
                self.assertIsNone(result.json()['data'])


if __name__ == '__main__':
    unittest.main()
