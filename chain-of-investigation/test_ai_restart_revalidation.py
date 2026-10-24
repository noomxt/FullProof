"""AI-owned checks against official 019dd0b: extract/read and reverify after restart.

Uses disposable local chain + synthetic provider output for repeatability.
No frontend, Uvicorn restart or multi-worker claims are made.
"""
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
import test_ai_backend_integration as fixtures


CHILD = r'''
import json, sys
from pathlib import Path
from unittest.mock import patch
payload = json.load(sys.stdin)
import database
database.DB_PATH = payload['db_path']
import main
from fastapi.testclient import TestClient
artifact = json.loads(main.ABI_PATH.read_text(encoding='utf-8'))
main.contract = main.w3.eth.contract(address=payload['contract'], abi=artifact['abi'])
case_id, claim_id = payload['case_id'], payload['claim_id']
stored = main.stored_v11_claim(case_id, claim_id, 1)
assert stored['claim_text'] == payload['claim_text']
assert stored['claim_hash'] == payload['claim_hash']
assert stored['structured_claim'] == payload['structured_claim']
original_id = payload['original']['verification_id']
assert main.V11_VERIFICATION_RESULTS[original_id] == payload['original']
with TestClient(main.app) as client:
    # Reading a persisted extraction must not silently rerun the provider.
    with patch('ai_engine.parse_claim_with_llm', side_effect=AssertionError('Unexpected provider call')):
        extracted = client.post(f'/api/v1/claims/{claim_id}/extract', json={
            'case_id':case_id, 'claim_version':1})
    assert extracted.status_code == 200, extracted.text
    assert extracted.json()['data'] == payload['structured_claim']
    response = client.post('/api/v1/verifications', json={
        'claim': {'case_id':case_id, 'claim_id':claim_id, 'claim_version':1},
        'proofs':payload['proofs']})
    assert response.status_code == 201, response.text
    result = response.json()['data']
    assert result['verdict'] == payload['expected'], result
    for field in ('claim_ref','proof_refs','proof_refs_hash','policy_hash','conflicts','missing_information','evidence_refs'):
        assert result[field] == payload['original'][field], (field,result)
    assert result['verification_id'] != original_id
    assert main.V11_VERIFICATION_RESULTS[original_id] == payload['original']
    receipt = main.w3.eth.get_transaction_receipt(result['verification_tx_hash'])
    assert receipt.status == 1
    record = main.contract.functions.getLatestVerification(main.case_uint(case_id),0).call()
    assert main.Web3.to_hex(record[7]) == result['verification_hash']
    assert database.load_v11_store('verification_results')[result['verification_id']] == result
print(json.dumps(dict(case_id=case_id, verdict=result['verdict'],
    original_verification=original_id, new_verification=result['verification_id'],
    extraction_preserved=True, prior_history_preserved=True,
    claim_ref=result['claim_ref'], proof_refs=result['proof_refs'],
    verification_tx_hash=result['verification_tx_hash'], receipt_status=receipt.status)))
'''


@unittest.skipUnless(os.getenv('FULLPROOF_CHAIN_INTEGRATION') == '1', 'opt-in disposable chain required')
class RestartRevalidationTests(unittest.TestCase):
    # Reuse the actual API/chain fixture without inheriting all its test methods.
    setUpClass = classmethod(fixtures.BackendIntegrationTests.setUpClass.__func__)
    tearDownClass = classmethod(fixtures.BackendIntegrationTests.tearDownClass.__func__)
    setUp = fixtures.BackendIntegrationTests.setUp
    tearDown = fixtures.BackendIntegrationTests.tearDown
    post = fixtures.BackendIntegrationTests.post
    seed = fixtures.BackendIntegrationTests.seed
    verify = fixtures.BackendIntegrationTests.verify

    def restart_and_verify(self, expected, **seed_args):
        import database
        claim, proofs = self.seed(**seed_args)
        original = self.verify(claim, proofs, expected)
        persisted = self.api.stored_v11_claim(self.case_id, self.claim_id, 1)
        payload = dict(db_path=str(database.DB_PATH), contract=self.contract.address,
            case_id=self.case_id, claim_id=self.claim_id, claim_text=claim['claim_text'],
            claim_hash=claim['claim_hash'], structured_claim=persisted['structured_claim'],
            original=original, proofs=proofs, expected=expected)
        completed = subprocess.run([sys.executable, '-c', CHILD], input=json.dumps(payload),
            text=True, capture_output=True, timeout=60)
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        evidence = json.loads(completed.stdout)
        self.results[-1]['restart_revalidation'] = evidence

    def test_supported_after_restart(self):
        self.restart_and_verify('SUPPORTED')

    def test_contradicted_after_restart(self):
        self.restart_and_verify('CONTRADICTED', result='CALL_FAILED')

    def test_no_proof_after_restart(self):
        self.restart_and_verify('INSUFFICIENT', with_proof=False)

    def test_confirmed_but_no_call_ref_after_restart(self):
        self.restart_and_verify('INSUFFICIENT', reference=False)

    def test_first_extraction_of_restored_claim(self):
        import database
        text = self.local.strftime('%Y년 %m월 %d일 %H시 %M분 %S초에 P001과 통화 연결에 성공했다.')
        claim = self.post(f'/api/v1/cases/{self.case_id}/claims', dict(claim_id=self.claim_id,
            claim_version=1, step_id=0, claim_text=text))
        payload = dict(db_path=str(database.DB_PATH), contract=self.contract.address,
            case_id=self.case_id, claim_id=self.claim_id, text=text, claim_hash=claim['claim_hash'],
            wall_time=self.local.strftime('%Y-%m-%d %H:%M:%S'), utc=self.utc)
        script = r'''
import json, sys
from unittest.mock import patch
p = json.load(sys.stdin)
import database
database.DB_PATH = p['db_path']
import main
from ai_engine import _finalize, PROMPT_VERSION
from fastapi.testclient import TestClient
artifact = json.loads(main.ABI_PATH.read_text(encoding='utf-8'))
main.contract = main.w3.eth.contract(address=p['contract'], abi=artifact['abi'])
claim = main.stored_v11_claim(p['case_id'], p['claim_id'], 1)
assert claim['structured_claim'] is None
parsed = _finalize(p['text'], dict(actions=[dict(action_type='PHONE_CALL', target_id='P001',
    claimed_time=p['wall_time'], status_claim='SUCCESS', source_text=p['text'])], review_reasons=[]))
parsed.update(model_name='restart-provider-fixture', prompt_version=PROMPT_VERSION)
with TestClient(main.app) as client:
    with patch('ai_engine.parse_claim_with_llm', return_value=parsed) as provider:
        response = client.post(f"/api/v1/claims/{p['claim_id']}/extract", json={
            'case_id':p['case_id'], 'claim_version':1})
        provider.assert_called_once_with(p['text'], client=None)
    assert response.status_code == 200, response.text
    result = response.json()['data']
    assert result['extraction_status'] == 'COMPLETED'
    action = result['actions'][0]
    assert action['action_result'] == 'SUCCESS' and action['occurred_at'] == p['utc']
    assert action['source_excerpt'] == p['text'] and action['target_id'] == 'P001'
    persisted = database.load_cases()[p['case_id']]['v11_claims'][0]
    assert persisted['claim_text'] == p['text'] and persisted['claim_hash'] == p['claim_hash']
    assert persisted['structured_claim'] == result
    verification = client.post('/api/v1/verifications', json={'claim':{
        'case_id':p['case_id'], 'claim_id':p['claim_id'], 'claim_version':1}, 'proofs':[]})
    assert verification.status_code == 201, verification.text
    assert verification.json()['data']['verdict'] == 'INSUFFICIENT'
print(json.dumps(dict(case_id=p['case_id'], first_extraction_after_restart=True,
    original_bytes_preserved=True, verdict='INSUFFICIENT')))
'''
        completed = subprocess.run([sys.executable, '-c', script], input=json.dumps(payload),
            text=True, capture_output=True, timeout=60)
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.results.append(json.loads(completed.stdout))


if __name__ == '__main__':
    unittest.main()
