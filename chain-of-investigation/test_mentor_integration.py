"""Opt-in local-chain tests for mentor follow-up. Never use real institution data."""
import json
import os
import subprocess
import sys
import unittest
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from fastapi import HTTPException
from test_ai_backend_integration import BackendIntegrationTests as Harness


@unittest.skipUnless(os.getenv('FULLPROOF_CHAIN_INTEGRATION')=='1','disposable local chain required')
class MentorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Harness.setUpClass()
        import database
        database.init_db()
    @classmethod
    def tearDownClass(cls):Harness.tearDownClass()
    def setUp(self):
        self.harness=Harness('runTest');self.harness.setUp()
    def tearDown(self):self.harness.http.close()
    def __getattr__(self,key):
        harness=self.__dict__.get('harness')
        if harness is not None:return getattr(harness,key)
        raise AttributeError(key)
    def body(self,claim,proofs):
        return dict(claim={k:claim[k] for k in ('case_id','claim_id','claim_version')},proofs=proofs)
    def count(self):return self.contract.functions.getVerificationHistoryLength(self.api.case_uint(self.case_id),0).call()
    def test_duplicate_sync_reuses_id_and_one_transaction(self):
        claim,proofs=self.seed();a=self.verify(claim,proofs,'SUPPORTED');b=self.verify(claim,proofs,'SUPPORTED')
        self.assertEqual(a['verification_id'],b['verification_id']);self.assertEqual(a['verification_tx_hash'],b['verification_tx_hash']);self.assertEqual(self.count(),1)
    def test_concurrent_async_requests_share_one_job(self):
        claim,proofs=self.seed();body=self.body(claim,proofs)
        with ThreadPoolExecutor(2) as pool:responses=list(pool.map(lambda _:self.http.post('/api/v1/verification-requests',json=body),range(2)))
        self.assertEqual([r.status_code for r in responses],[202,202]);ids=[r.json()['data']['verification_id'] for r in responses]
        self.assertEqual(ids[0],ids[1]);self.assertEqual(self.count(),1)
        job=self.http.get('/api/v1/verification-requests/'+ids[0]).json()['data'];self.assertEqual(job['request_state'],'CONFIRMED')
    def test_response_lost_after_transaction_is_reconciled_without_resubmission(self):
        claim,proofs=self.seed();original=self.api.confirmed
        def lost(tx):original(tx);raise HTTPException(503,'Injected lost receipt response')
        with patch.object(self.api,'confirmed',side_effect=lost):a=self.verify(claim,proofs,'SUPPORTED')
        b=self.verify(claim,proofs,'SUPPORTED');self.assertEqual(a['verification_id'],b['verification_id']);self.assertEqual(self.count(),1)
    def test_restart_reuses_existing_verification(self):
        import database
        claim,proofs=self.seed();a=self.verify(claim,proofs,'SUPPORTED')
        script='''import json,sys,os
import database
database.DB_PATH=sys.argv[1]
os.environ['CONTRACT_ADDRESS']=sys.argv[2]
import main
from fastapi.testclient import TestClient
with TestClient(main.app) as client:
 r=client.post('/api/v1/verifications',json=json.loads(sys.argv[3]));assert r.status_code==201,r.text
 assert r.json()['data']['verification_id']==sys.argv[4],r.text
print('RESTARTED IDEMPOTENCY: PASS')
'''
        run=subprocess.run([sys.executable,'-c',script,str(database.DB_PATH),self.contract.address,json.dumps(self.body(claim,proofs)),a['verification_id']],capture_output=True,text=True)
        self.assertEqual(run.returncode,0,run.stdout+run.stderr);self.assertEqual(self.count(),1)
    def test_mapping_confirmation_changes_decision_instead_of_reusing_insufficient(self):
        claim,proofs=self.seed(confirm=False);a=self.verify(claim,proofs,'INSUFFICIENT')
        mapping=self.api.V11_MAPPING_HISTORY[(self.case_id,self.claim_id)][-1]
        draft=self.api.PROOF_DRAFTS[(self.case_id,'PROOF-001',1)];note='기관 원본과 명시적인 통화 ID를 확인했습니다.'
        message=self.api.build_v11_mapping_confirmation_message(self.case_id,mapping,claim['claim_hash'],draft['proof_hash'],draft['proof_content']['source_sha256'],note)
        signature=self.w3.provider.make_request('eth_sign',[self.admin,self.w3.to_hex(text=message)])['result']
        self.post(f"/api/v1/claims/{self.claim_id}/proof-mappings/{mapping['mapping_id']}/confirm",dict(case_id=self.case_id,claim_text=claim['claim_text'],evidence_source_sha256=draft['proof_content']['source_sha256'],evidence_note=note,signer_address=self.admin,signature=signature),200)
        b=self.verify(claim,proofs,'SUPPORTED');self.assertNotEqual(a['verification_id'],b['verification_id']);self.assertEqual(self.count(),2)
    def test_new_proof_invalidates_old_approval_and_gets_a_new_verification(self):
        claim,proofs=self.seed();a=self.verify(claim,proofs,'SUPPORTED')
        self.post(f"/api/v1/verifications/{a['verification_id']}/reviews",self.signed_review(a),200)
        p=deepcopy(proofs[0]);p['proof_id']='EXTRA-PROOF'
        now=self.w3.eth.get_block('latest')['timestamp']
        draft=self.post('/api/v1/proofs/drafts',dict(proof_content=p,source_text=json.dumps(p),nonce=self.contract.functions.agencyNonces(self.agency).call(),deadline=now+3600))['data']
        typed=deepcopy(draft['typed_data']);typed['types']['EIP712Domain']=[dict(name=n,type=t) for n,t in [('name','string'),('version','string'),('chainId','uint256'),('verifyingContract','address')]]
        sig=self.w3.provider.make_request('eth_signTypedData_v4',[self.agency,json.dumps(typed)])['result'];m=typed['message']
        self.post('/api/v1/proofs/anchor',dict(case_id=self.case_id,step_id=0,proof_id=p['proof_id'],proof_version=1,proof_hash=m['proofHash'],occurred_at=int(m['occurredAt']),issued_at=int(m['issuedAt']),agency=self.agency,nonce=int(m['nonce']),deadline=int(m['deadline']),signature=sig))
        self.post(f'/api/v1/cases/{self.case_id}/close',self.signed_close(),409)
        b=self.verify(claim,proofs,'SUPPORTED');self.assertNotEqual(a['verification_id'],b['verification_id']);self.assertEqual(self.count(),2)
        self.post(f'/api/v1/cases/{self.case_id}/close',self.signed_close(),409)
    def test_unknown_submission_is_not_blindly_retried(self):
        from mentor_support import stage_result
        claim,proofs=self.seed()
        def unknown(result):stage_result(result);raise HTTPException(503,'Injected ambiguous submission')
        with patch.object(self.api,'anchor_v11_verification',side_effect=unknown) as fn:
            a=self.http.post('/api/v1/verifications',json=self.body(claim,proofs));b=self.http.post('/api/v1/verifications',json=self.body(claim,proofs))
        self.assertEqual(a.status_code,202,a.text);self.assertEqual(b.status_code,202,b.text)
        self.assertEqual(a.json()['data']['verification_id'],b.json()['data']['verification_id']);self.assertEqual(fn.call_count,1);self.assertEqual(b.json()['data']['request_state'],'UNKNOWN');self.assertEqual(self.count(),0)
    def test_retired_api_routes_are_blocked_before_validation(self):
        for path in ['/api/v1/cases/verify','/api/v1/cases/proofs/anchor',f'/api/v1/cases/{self.case_id}/steps/0/sync',f'/api/v1/cases/{self.case_id}/steps/0/recover-proof']:
            r=self.http.post(path,json={});self.assertEqual(r.status_code,410,r.text);self.assertEqual(r.json()['error']['code'],'LEGACY_ROUTE_DISABLED')
    def test_legacy_contract_write_always_reverts(self):
        with self.assertRaisesRegex(Exception,'LEGACY_PROOF_DISABLED'):
            self.contract.functions.anchorProof(0,0,b'\0'*32,b'\0'*32,1,1,1,0,self.agency,b'').call({'from':self.admin})
    def test_integrity_endpoint_returns_raw_inputs_and_real_chain_hashes(self):
        import hashlib
        import rfc8785
        claim,proofs=self.seed();v=self.verify(claim,proofs,'SUPPORTED');r=self.http.get('/api/v1/verifications/'+v['verification_id']+'/integrity-data')
        self.assertEqual(r.status_code,200,r.text);d=r.json()['data'];chain=d['onchain']
        self.assertEqual('0x'+hashlib.sha256(d['claim']['claim_text'].encode()).hexdigest(),chain['claim_hash'])
        content={k:v for k,v in d['verification'].items() if k not in ('verification_hash','verification_tx_hash')}
        self.assertEqual('0x'+hashlib.sha256(rfc8785.dumps(content)).hexdigest(),chain['verification']['verification_hash'])
        self.assertEqual(chain['verification']['verdict'],'SUPPORTED')
    def test_known_failure_before_submission_can_be_retried_without_new_id(self):
        claim,proofs=self.seed()
        with patch.object(self.api,'process_v11_verification',side_effect=HTTPException(503,'Injected failure before anchor')):
            response=self.http.post('/api/v1/verifications',json=self.body(claim,proofs));self.assertEqual(response.status_code,503,response.text)
        from mentor_support import fingerprint,connection
        inputs=self.api.build_v11_verification_inputs(self.api.V11VerificationRequest(**self.body(claim,proofs)));key,_=fingerprint(inputs,self.api)
        with connection() as db:ident=db.execute('SELECT verification_id FROM verification_requests WHERE input_key=?',(key,)).fetchone()[0]
        v=self.verify(claim,proofs,'SUPPORTED');self.assertEqual(v['verification_id'],ident);self.assertEqual(self.count(),1)

    def test_chain_rollback_does_not_return_a_false_confirmed_cached_result(self):
        claim,proofs=self.seed()
        snapshot=self.w3.provider.make_request('evm_snapshot',[])['result']
        self.verify(claim,proofs,'SUPPORTED')
        self.assertTrue(self.w3.provider.make_request('evm_revert',[snapshot])['result'])
        response=self.http.post('/api/v1/verifications',json=self.body(claim,proofs))
        self.assertEqual(response.status_code,202,response.text)
        self.assertEqual(response.json()['data']['request_state'],'UNKNOWN')
        self.assertEqual(self.count(),0)

    def test_same_claim_id_in_different_cases_does_not_share_a_request(self):
        from uuid import uuid4
        self.harness.claim_id='SHARED-CLAIM-ID'
        claim,proofs=self.seed(with_proof=False)
        first=self.verify(claim,proofs,'INSUFFICIENT')
        first_case=self.case_id
        self.harness.case_id='OTHER-CASE-'+uuid4().hex
        self.post('/api/v1/cases',dict(case_id=self.case_id))
        self.post(f'/api/v1/cases/{self.case_id}/steps',dict(step_name='통화 확인'),200)
        claim,proofs=self.seed(with_proof=False)
        second=self.verify(claim,proofs,'INSUFFICIENT')
        self.assertNotEqual(first['verification_id'],second['verification_id'])
        self.assertEqual(second['case_id'],self.case_id)
        self.assertEqual(self.contract.functions.getVerificationHistoryLength(self.api.case_uint(first_case),0).call(),1)
        self.assertEqual(self.count(),1)


def load_tests(loader, tests, pattern):
    return loader.loadTestsFromTestCase(MentorTests)
