"""Explicit offline fixtures: no live LLM, institutional signatures or blockchain."""
import argparse
import json
from copy import deepcopy
from unittest.mock import patch
from pathlib import Path
from datetime import datetime, timezone
from ai_engine import parse_claim_with_llm
from pipeline import AnalysisStore, analyze_and_save


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--live',action='store_true',help='Call real OpenAI for parsing and semantics (API key required)')
    parser.add_argument('--db',default='data/demo.sqlite3')
    args=parser.parse_args()
    scenarios=[('supported','FAIL',True),('contradicted','SUCCESS',True),('insufficient','FAIL',False)]
    text='2026년 10월 10일 14시에 대상자 P001에게 전화했으나 연결되지 않았다.'
    store=AnalysisStore(args.db)
    for label,outcome,has_proof in scenarios:
        from uuid import uuid4
        proof={'proof_id':'PROOF_'+label,'proof_version':1,'action_type':'PHONE_CALL','target_id':'P001',
               'occurred_at':'2026-10-10T14:00:00+09:00','action_result':outcome,
               'proof_text':'P001 발신 결과: '+('연결 실패' if outcome=='FAIL' else '통화 연결 성공')}
        request={'request_id':str(uuid4()),'case_id':'DEMO_'+label,'step_id':0,'claim_id':'CLAIM_1','claim_version':1,
                 'raw_text':text,'proof':proof if has_proof else None,
                 'proof_validation':{'status':'VALID','validation_id':'MOCK_VALIDATION_ONLY'},
                 'evaluated_at':'2026-10-10T06:00:00Z',
                 'evidence':[{'evidence_id':'E1','step_id':3,'evidence_expires_at':'2026-10-10T18:00:00Z',
                              'deadline_source':'가상 보존 기한','deadline_version':1,'preservation_status':'REQUESTED'}]}
        if args.live:
            # --live tests real AI, but institutional validation remains a fixture.
            response=analyze_and_save(store,request)
        else:
            parsed={'parse_status':'SUCCESS','raw_text':text,'actions':[
                {'action_type':'PHONE_CALL','target_id':'P001','claimed_time':'2026-10-10 14:00:00',
                 'status_claim':'FAIL','source_text':text,'missing_fields':[]}], 'review_reasons':[], 'error_code':None}
            with patch('pipeline.semantic_compare',return_value={'processing_status':'COMPLETED','semantic_status':'SUPPORTS',
                       'findings':[],'review_required':False,'error_code':None}):
                response=analyze_and_save(store,request,parse_function=lambda *a,**kw:deepcopy(parsed))
        result=response['analysis']
        print(json.dumps({'scenario':label,'execution_mode':'LIVE_AI_WITH_MOCK_AGENCY' if args.live else 'OFFLINE_FIXTURE',
                          'verdict':result['verdict'],'reason':result['reason_text'],
                          'readiness':result['policy_assessment']['readiness_status'],
                          'warnings':result['warnings'],'storage_status':response['storage_status'],
                          'anchor_status':'NOT_REQUESTED'},ensure_ascii=False,indent=2))

if __name__=='__main__': main()
