"""Readiness diagnostic on a disposable local chain, NOT an acceptance pass.
Requires FULLPROOF_TEST_RPC_URL and a compiled team artifact. Synthetic data only.
"""
import json
import os
from pathlib import Path
import sys
from unittest.mock import patch
from fastapi import HTTPException
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'chain-of-investigation'))
from test_ai_backend_integration import BackendIntegrationTests as Harness

os.environ['FULLPROOF_TEST_REPORT']='frontend-backend-diagnostic.json'
Harness.setUpClass()
h=Harness('runTest')
try:
    h.setUp()
    claim,proofs=h.seed()
    original=h.api.confirmed
    def lost(tx):
        original(tx)
        raise HTTPException(503,'Injected lost response after a real successful transaction')
    body=dict(claim={k:claim[k] for k in ('case_id','claim_id','claim_version')},proofs=proofs)
    with patch.object(h.api,'confirmed',side_effect=lost):
        first=h.http.post('/api/v1/verifications',json=body)
    count_before=h.contract.functions.getVerificationHistoryLength(h.api.case_uint(h.case_id),0).call()
    second=h.http.post('/api/v1/verifications',json=body)
    count_after=h.contract.functions.getVerificationHistoryLength(h.api.case_uint(h.case_id),0).call()
    report=dict(scope='Synthetic diagnostic, real local transaction, injected lost receipt response. No production data.',
                first_http=first.status_code,records_after_lost_response=count_before,retry_http=second.status_code,
                records_after_backend_retry=count_after,duplicate_gap_reproduced=count_after>count_before,
                note='Normal completed-response retries are covered by the team cache; this tests a different failure window. The frontend blocks blind resubmission on ambiguous responses; backend/RPC reconciliation remains a team follow-up.')
    (ROOT/'docs/BACKEND_DIAGNOSTIC.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(json.dumps(report,ensure_ascii=False,indent=2))
finally:
    h.http.close()
    Harness.tearDownClass()
