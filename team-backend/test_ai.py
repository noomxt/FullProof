"""Offline PRD checks. Mocks validate plumbing, not real LLM accuracy."""
import unittest
import tempfile
from pathlib import Path
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch
from ai_engine import _finalize, parse_claim_with_llm, verify_claim_vs_proof
from verification import *
from pipeline import *

TEXT = '2026년 10월 10일 14시에 P001에게 전화했으나 연결 실패.'
ACTION = dict(action_type='PHONE_CALL', target_id='P001', claimed_time='2026-10-10T14:00:00+09:00', status_claim='FAIL', source_text=TEXT)
PROOF = dict(proof_id='P-1', proof_version=1, action_type='PHONE_CALL', target_id='P001', occurred_at='2026-10-10T05:00:00Z', action_result='FAIL', proof_text='P001에게 발신했으나 무응답으로 연결되지 않음.')
CP = dict(required_fields=['target_id','action_type','claimed_time','status_claim'], time_tolerance_seconds=900, semantic_required=True)
SEM = dict(processing_status='COMPLETED', semantic_status='SUPPORTS', findings=[], error_code=None)


def parse_fixture(text, client=None):
    a = deepcopy(ACTION)
    a['claimed_time'] = '2026-10-10 14:00:00'
    return _finalize(text, {'actions':[a], 'review_reasons':[]})


def request():
    return dict(request_id='R1',case_id='C1',step_id=0,claim_id='CL1',claim_version=1,
                raw_text=TEXT,proof=deepcopy(PROOF),proof_validation={'status':'VALID'},
                evaluated_at='2026-10-10T06:00:00Z')


class CoreTests(unittest.TestCase):
    def compare(self, action=None, proof=None, validation=None, policy=None):
        return compare_fields(action or ACTION, proof or PROOF, validation or {'status':'VALID'}, policy or CP)

    def test_all_fields_match(self):
        self.assertTrue(all(c['status']=='MATCH' for c in self.compare()['field_checks']))

    def test_time_boundary(self):
        p=deepcopy(PROOF);p['occurred_at']='2026-10-10T05:15:00Z'
        self.assertEqual(self.compare(proof=p)['field_checks'][2]['status'],'MATCH')
        p['occurred_at']='2026-10-10T05:15:01Z'
        self.assertEqual(self.compare(proof=p)['field_checks'][2]['status'],'MISMATCH')

    def test_success_failure_both_directions(self):
        for left,right in [('FAIL','SUCCESS'),('SUCCESS','FAIL')]:
            a=deepcopy(ACTION);a['status_claim']=left
            p=deepcopy(PROOF);p['action_result']=right
            self.assertEqual(self.compare(a,p)['field_checks'][3]['status'],'MISMATCH')

    def test_multiple_mismatches_retained(self):
        p=deepcopy(PROOF);p.update(target_id='P002',action_result='SUCCESS')
        r=decide(self.compare(proof=p),SEM)
        self.assertEqual(r['verdict'],'CONTRADICTED')
        self.assertEqual(len(r['conflicts']),2)

    def test_missing_not_mismatch(self):
        p=deepcopy(PROOF);p['target_id']=None
        self.assertEqual(decide(self.compare(proof=p),SEM)['verdict'],'INSUFFICIENT')

    def test_invalid_proof_blocks(self):
        self.assertEqual(decide(self.compare(validation={'status':'INVALID'}),SEM)['verdict'],'INSUFFICIENT')

    def test_no_proof(self):
        self.assertEqual(compare_fields(ACTION,None,{'status':'VALID'},CP)['blocking_reasons'],['PROOF_MISSING'])

    def test_timezone_required(self):
        p=deepcopy(PROOF);p['occurred_at']='2026-10-10 14:00:00'
        with self.assertRaises(ValueError): self.compare(proof=p)

    def test_missing_tolerance(self):
        p=deepcopy(CP);p['time_tolerance_seconds']=None
        self.assertEqual(self.compare(policy=p)['field_checks'][2]['status'],'UNKNOWN')

    def test_legacy_aliases_no_mutation(self):
        original={'timestamp':'2026-10-10T05:00:00Z','success':False}
        copy=deepcopy(original)
        p=normalize_proof(original)
        self.assertEqual(p['action_result'],'FAIL');self.assertEqual(original,copy)

    def test_conflicting_aliases_rejected(self):
        with self.assertRaises(ValueError): normalize_proof({'success':False,'action_result':'SUCCESS'})

    def test_semantic_unclear(self):
        self.assertEqual(decide(self.compare(),{'semantic_status':'UNCLEAR'})['verdict'],'INSUFFICIENT')

    def test_semantic_failure_does_not_erase_conflict(self):
        p=deepcopy(PROOF);p['target_id']='P002'
        self.assertEqual(decide(self.compare(proof=p),{'processing_status':'FAILED'})['verdict'],'CONTRADICTED')

    def test_semantic_only_conflict_requires_human(self):
        self.assertEqual(decide(self.compare(),{'semantic_status':'CONFLICTS'})['verdict'],'INSUFFICIENT')

    def test_supported(self): self.assertEqual(decide(self.compare(),SEM)['verdict'],'SUPPORTED')

    def test_invalid_source_excerpts(self):
        data=SemanticExtraction(findings=[Finding(claim_excerpt='invented',proof_excerpt='invented',relation='SUPPORTS',reason_code='MATCH',reason_text='x')])
        client=SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(parse=lambda **kw: SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(refusal=None,parsed=data))]))))
        self.assertEqual(semantic_compare(TEXT,PROOF['proof_text'],[],client=client)['processing_status'],'FAILED')

    def test_claim_timezone_normalization(self):
        r=normalize_claim(parse_fixture(TEXT))
        self.assertEqual(timestamp(r['actions'][0]['claimed_time']),timestamp(PROOF['occurred_at']))

    def test_legacy_no_validation_never_supported(self):
        self.assertEqual(verify_claim_vs_proof(parse_fixture(TEXT),PROOF)[0],'INSUFFICIENT')


class PolicyTests(unittest.TestCase):
    def policy(self):
        p=deepcopy(DEMO_POLICY);p['steps']=p['steps'][:1]
        return p

    def resolved(self): return resolve_policy(self.policy(),{},None)

    def result(self):
        return dict(step_id=0,action_type='PHONE_CALL',action_result='FAIL',verdict='SUPPORTED',analysis_id='A1',input_version=1,policy_version='demo-v1')

    def test_attempt_can_be_failed_and_satisfied(self):
        self.assertEqual(evaluate_steps(self.resolved(),[self.result()],{'0':1})['readiness_status'],'READY')

    def test_success_requirement(self):
        p=self.resolved();p['resolved_steps'][0]['require_success']=True
        self.assertEqual(evaluate_steps(p,[self.result()],{'0':1})['readiness_status'],'NOT_READY')

    def test_stale_result(self):
        self.assertEqual(evaluate_steps(self.resolved(),[self.result()],{'0':2})['readiness_status'],'NEEDS_REVIEW')

    def test_missing_action(self):
        self.assertEqual(evaluate_steps(self.resolved(),[],{})['readiness_status'],'NOT_READY')

    def test_missing_context(self):
        p=self.policy();p['steps'][0]['applicability_conditions']={'urgent':True}
        r=resolve_policy(p,{},None)
        self.assertEqual(r['policy_status'],'NEEDS_CONTEXT')
        self.assertEqual(evaluate_steps(r,[],{})['readiness_status'],'NEEDS_REVIEW')

    def test_not_applicable_does_not_auto_ready(self):
        p=self.policy();p['steps'][0]['applicability_conditions']={'urgent':True}
        r=resolve_policy(p,{'urgent':False},None)
        self.assertEqual(evaluate_steps(r,[],{})['readiness_status'],'NEEDS_REVIEW')

    def test_fixed_deadline(self):
        p=self.policy();p['steps'][0]['deadline_rule']={'basis':'case_registered_at','hours':24,'kind':'TASK'}
        a=resolve_policy(p,{},'2026-10-10T00:00:00Z')
        b=resolve_policy(p,{},'2026-10-10T00:00:00Z')
        self.assertEqual(a,b)

    def test_cycle_rejected(self):
        p=self.policy();p['steps'][0]['dependencies']=[0]
        with self.assertRaises(ValueError): resolve_policy(p,{},None)

    def test_exception_requires_approval(self):
        p=self.resolved()
        self.assertEqual(evaluate_steps(p,[],{},exceptions=[{'step_id':0,'validated':False}])['readiness_status'],'NOT_READY')
        self.assertEqual(evaluate_steps(p,[],{},exceptions=[{'step_id':0,'validated':True,'approval_id':'AP1'}])['readiness_status'],'READY')


class WarningTests(unittest.TestCase):
    def evidence(self):
        return dict(evidence_id='E1',step_id=3,evidence_expires_at='2026-10-11T00:00:00Z',deadline_source='mock agency retention',deadline_version=1,preservation_status='NOT_SECURED')

    def test_exact_threshold(self):
        self.assertEqual(evidence_warning(self.evidence(),'2026-10-10T00:00:00Z')['deadline_status'],'EXPIRING_SOON')

    def test_exact_deadline(self):
        r=evidence_warning(self.evidence(),'2026-10-11T00:00:00Z')
        self.assertEqual(r['deadline_status'],'DEADLINE_PASSED')
        self.assertNotIn('삭제되었습니다',r['warning_text'])

    def test_missing_source(self):
        e=self.evidence();e['deadline_source']=None
        self.assertEqual(evidence_warning(e,'2026-10-10T00:00:00Z')['deadline_status'],'UNKNOWN')

    def test_secured_requires_reference(self):
        e=self.evidence();e['preservation_status']='SECURED'
        self.assertTrue(evidence_warning(e,'2026-10-11T00:00:00Z')['action_required'])
        e['preservation_ref']='PRES1'
        self.assertFalse(evidence_warning(e,'2026-10-11T00:00:00Z')['action_required'])

    def test_invalid_threshold(self):
        with self.assertRaises(ValueError): evidence_warning(self.evidence(),'2026-10-10T00:00:00Z',-1)


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.store=AnalysisStore(Path(self.temp.name)/'ai.db')
    def tearDown(self): self.temp.cleanup()

    def run_analysis(self,r):
        with patch('pipeline.semantic_compare',return_value=deepcopy(SEM)):
            return analyze_and_save(self.store,r,parse_function=parse_fixture)

    def test_pipeline_save_and_retry(self):
        r=request();first=self.run_analysis(r);second=self.run_analysis(r)
        self.assertEqual(first['analysis']['verdict'],'SUPPORTED')
        self.assertEqual(second['storage_status'],'ALREADY_SAVED')
        self.assertEqual(first['analysis']['analysis_id'],second['analysis']['analysis_id'])

    def test_conflicting_request(self):
        r=request();self.run_analysis(r);r['claim_version']=2
        with self.assertRaises(RequestConflict): self.run_analysis(r)

    def test_history_after_reopen(self):
        r=request();self.run_analysis(r);r['request_id']='R2';r['claim_version']=2;self.run_analysis(r)
        reopened=AnalysisStore(Path(self.temp.name)/'ai.db')
        self.assertEqual(len(reopened.history('C1')),2)

    def test_pipeline_pending_blocks_support(self):
        r=request();r['proof_validation']={'status':'PENDING'}
        self.assertEqual(self.run_analysis(r)['analysis']['verdict'],'INSUFFICIENT')

    def test_parse_failure(self):
        r=analyze(request(),parse_function=lambda *a,**k: {'parse_status':'FAILED','actions':[],'error_code':'AI_TIMEOUT'})
        self.assertIsNone(r['verdict']);self.assertEqual(r['processing_status'],'FAILED')

    def test_alert_dedup_and_transition(self):
        e=WarningTests().evidence()
        w=evidence_warning(e,'2026-10-10T00:00:00Z')
        self.assertTrue(self.store.observe_alert('C1',w))
        self.assertFalse(self.store.observe_alert('C1',w))
        w=evidence_warning(e,'2026-10-11T00:00:00Z')
        self.assertTrue(self.store.observe_alert('C1',w))

    def test_delivery_does_not_report_anchor(self):
        result=self.run_analysis(request())['analysis'];aid=result['analysis_id']
        body={'request_id':'R1','analysis_id':aid,'storage_status':'SAVED','anchor_status':'NOT_REQUESTED','transaction_hash':None}
        session=SimpleNamespace(post=lambda *a,**k: SimpleNamespace(status_code=200,json=lambda:body))
        r=deliver_result(self.store,aid,'http://localhost/analysis',session=session)
        self.assertEqual(r['anchor_status'],'NOT_REQUESTED')

    def test_delivery_rejects_confirmation_without_tx(self):
        result=self.run_analysis(request())['analysis'];aid=result['analysis_id']
        body={'request_id':'R1','analysis_id':aid,'storage_status':'SAVED','anchor_status':'CONFIRMED'}
        session=SimpleNamespace(post=lambda *a,**k: SimpleNamespace(status_code=200,json=lambda:body))
        self.assertEqual(deliver_result(self.store,aid,'http://localhost/analysis',session=session)['delivery_status'],'FAILED')

    def test_http_validation_cannot_be_spoofed(self):
        from backend_bridge import AnalyzeRequest
        from pydantic import ValidationError
        with self.assertRaises(ValidationError):
            AnalyzeRequest(request_id='R',case_id='C',step_id=0,claim_id='CL',claim_version=1,raw_claim_text=TEXT,proof_validation={'status':'VALID'})

    def test_http_save_with_pending_validation(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from backend_bridge import register_ai_routes
        app=FastAPI();register_ai_routes(app,{'C1':{'steps':[{}],'is_closed':False}},db_path=Path(self.temp.name)/'http.db')
        client=TestClient(app)
        body={'request_id':'HR1','case_id':'C1','step_id':0,'claim_id':'CL1','claim_version':1,'raw_claim_text':TEXT,'proof':PROOF}
        with patch('ai_engine.parse_claim_with_llm',side_effect=parse_fixture):
            a=client.post('/api/v1/ai/analyses',json=body)
            b=client.post('/api/v1/ai/analyses',json=body)
        self.assertEqual(a.status_code,200,a.text)
        self.assertEqual(a.json()['analysis']['verdict'],'INSUFFICIENT')
        self.assertEqual(b.json()['storage_status'],'ALREADY_SAVED')
        self.assertEqual(client.post('/api/v1/cases/verify').status_code,409)


class SignedBridgeTests(unittest.TestCase):
    def setUp(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from backend_bridge import register_ai_routes, register_signed_draft_routes
        self.temp=tempfile.TemporaryDirectory()
        self.app=FastAPI()
        self.cases={'C1':{'is_closed':False,'steps':[{'step_name':DEMO_POLICY['steps'][0]['step_name']}]}}
        self.store=register_ai_routes(self.app,self.cases,db_path=Path(self.temp.name)/'signed.db')
        class FakeWeb3:
            @staticmethod
            def to_checksum_address(v): return v
            @staticmethod
            def to_hex(v): return '0x'+v.hex() if isinstance(v,bytes) else v
            @staticmethod
            def to_bytes(hexstr): return bytes.fromhex(hexstr[2:])
        self.chain_calls=[]
        class FakeCall:
            def call(inner,tx): return None
            def transact(inner,tx): return bytes.fromhex('ab'*32)
        def anchor(*args):
            self.chain_calls.append(args)
            return FakeCall()
        self.ctx={'Web3':FakeWeb3,'require_chain':lambda:None,
                  'canonical_hash':lambda v:hashlib.sha256(json_bytes(v)).digest(),
                  'case_uint':lambda v:42,'w3':SimpleNamespace(eth=SimpleNamespace(chain_id=31337,
                      get_transaction_receipt=lambda tx:{'status':1,'blockHash':bytes.fromhex('cd'*32),'blockNumber':1})),
                  'contract':SimpleNamespace(address='0xcontract',functions=SimpleNamespace(anchorProof=anchor)),
                  'PROOF_TYPES':{'Proof':[]},'validate_proof':lambda request,signature:'0xsigner',
                  'sender':lambda:'0xsender','confirmed':lambda tx:FakeWeb3.to_hex(tx)}
        register_signed_draft_routes(self.app,self.cases,self.store,self.ctx)
        self.client=TestClient(self.app)
        body={'request_id':'D1','case_id':'C1','step_id':0,'claim_id':'CL1','claim_version':1,
              'raw_claim_text':TEXT,'proof':deepcopy(PROOF)}
        with patch('ai_engine.parse_claim_with_llm',side_effect=parse_fixture),patch('pipeline.semantic_compare',return_value=deepcopy(SEM)):
            response=self.client.post('/api/v1/ai/drafts',json=body)
        self.assertEqual(response.status_code,200,response.text)
        self.draft=response.json()['analysis']
        self.body={'analysis_id':self.draft['analysis_id'],'agency':'0xagency','signature':'0xsigned',
                   'nonce':0,'deadline':2000000000,'evidence_timestamp':int(timestamp(PROOF['occurred_at']).timestamp())}
    def tearDown(self): self.temp.cleanup()

    def test_unsigned_draft_is_explicitly_provisional(self):
        self.assertTrue(self.draft['is_provisional'])
        self.assertEqual(self.draft['trust_status'],'PENDING_SIGNATURE')
        self.assertNotIn('is_completed',self.cases['C1']['steps'][0])

    def test_frozen_anchor_never_reparses(self):
        with patch('ai_engine.parse_claim_with_llm',side_effect=AssertionError('Unexpected LLM call')):
            r=self.client.post('/api/v1/ai/anchor',json=self.body)
        self.assertEqual(r.status_code,200,r.text)
        self.assertEqual(r.json()['anchor_status'],'CONFIRMED')
        self.assertEqual(self.chain_calls[0][2],self.ctx['canonical_hash'](self.draft['structured_claim']))
        self.assertEqual(self.chain_calls[0][3],self.ctx['canonical_hash'](PROOF))

    def test_confirmed_anchor_retry_no_resubmit(self):
        self.client.post('/api/v1/ai/anchor',json=self.body)
        self.client.post('/api/v1/ai/anchor',json=self.body)
        self.assertEqual(len(self.chain_calls),1)

    def test_wrong_evidence_timestamp_rejected(self):
        self.body['evidence_timestamp']+=1
        self.assertEqual(self.client.post('/api/v1/ai/anchor',json=self.body).status_code,409)
        self.assertEqual(len(self.chain_calls),0)

    def test_policy_step_name_mismatch(self):
        self.cases['C1']['steps'][0]['step_name']='different step'
        self.assertEqual(self.client.post('/api/v1/ai/anchor',json=self.body).status_code,409)

    def test_invalid_signature_not_saved_as_confirmed(self):
        def fail(*a): raise ValueError('Invalid signature')
        self.ctx['validate_proof']=fail
        self.assertEqual(self.client.post('/api/v1/ai/anchor',json=self.body).status_code,400)
        self.assertIsNone(self.store.get(self.draft['analysis_id'])['delivery'])

    def test_timeout_retains_submitted_and_retry_no_resubmit(self):
        def fail(*a): raise TimeoutError('Confirmation timed out')
        self.ctx['confirmed']=fail
        self.assertEqual(self.client.post('/api/v1/ai/anchor',json=self.body).status_code,400)
        r=self.client.post('/api/v1/ai/anchor',json=self.body)
        self.assertEqual(r.json()['anchor_status'],'SUBMITTED')
        self.assertEqual(len(self.chain_calls),1)

    def test_confirmed_chain_sqlite_failure_is_recoverable_by_status(self):
        with patch('backend_bridge.persist_case', side_effect=OSError('disk unavailable')):
            response=self.client.post('/api/v1/ai/anchor',json=self.body)
        self.assertEqual(response.status_code,503)
        stored=self.store.get(self.draft['analysis_id'])['delivery']
        self.assertEqual(stored['anchor_status'],'CONFIRMED')
        self.assertEqual(stored['case_persistence'],'FAILED')
        self.assertTrue(stored['recovery_required'])
        with patch('backend_bridge.persist_case') as persist:
            state=self.client.get('/api/v1/ai/anchor-status/'+self.draft['analysis_id'])
        self.assertEqual(state.status_code,200,state.text)
        self.assertEqual(state.json()['case_persistence'],'SAVED')
        self.assertFalse(state.json()['recovery_required'])
        persist.assert_called_once()
        self.assertEqual(len(self.chain_calls),1)

    def test_changed_block_identity_does_not_reuse_confirmation(self):
        with patch('backend_bridge.persist_case'):
            self.client.post('/api/v1/ai/anchor',json=self.body)
        self.ctx['w3'].eth.get_transaction_receipt=lambda tx:{'status':1,'blockHash':bytes.fromhex('ef'*32),'blockNumber':1}
        response=self.client.get('/api/v1/ai/anchor-status/'+self.draft['analysis_id'])
        self.assertEqual(response.json()['anchor_status'],'STALE_CHAIN')



if __name__=='__main__': unittest.main(verbosity=2)
