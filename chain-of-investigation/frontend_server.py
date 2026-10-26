"""Local frontend companion. Official main.py routes and business rules are unchanged.
Adds READ views and an audit journal of successful responses; never signs for users.
Run one Uvicorn worker. Not production authentication or a recovery service.
"""
import json
import os
import sqlite3
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from fastapi import HTTPException
from starlette.responses import Response
import database
if os.getenv('FULLPROOF_UI_DB_PATH'):
    database.DB_PATH=Path(os.environ['FULLPROOF_UI_DB_PATH'])
import main as core

app = core.app
JOURNAL = Path(os.getenv('FULLPROOF_UI_AUDIT_PATH', str(Path(__file__).with_name('frontend-audit.db'))))
with sqlite3.connect(JOURNAL) as db:
    db.execute('CREATE TABLE IF NOT EXISTS audit (namespace TEXT, path TEXT, payload TEXT)')


def namespace():
    core.require_chain()
    # A restarted local chain must not inherit receipt metadata from an old run.
    return f'{core.contract.address}:{core.w3.eth.get_block(1)["hash"].hex()}'


def hx(value):
    if not value:
        return None
    return value if value.startswith('0x') else '0x' + value


def receipt_status(tx):
    if not tx:
        return 'PENDING'
    try:
        r = core.w3.eth.get_transaction_receipt(hx(tx))
        return 'CONFIRMED' if r.status == 1 else 'FAILED'
    except Exception:
        return 'UNKNOWN'


def audit_rows():
    with sqlite3.connect(JOURNAL) as db:
        return [(p, json.loads(v)) for p, v in db.execute('SELECT path,payload FROM audit WHERE namespace=?', (namespace(),))]


@app.middleware('http')
async def journal_success(request, call_next):
    response = await call_next(request)
    path = request.url.path
    if request.method != 'POST' or not (path.endswith('/reviews') or path.endswith('/close') or path == '/api/v1/proofs/anchor'):
        return response
    body = b''.join([chunk async for chunk in response.body_iterator])
    if 200 <= response.status_code < 300:
        try:
            payload = json.loads(body)
            value = payload.get('data', payload)
            with sqlite3.connect(JOURNAL) as db:
                db.execute('INSERT INTO audit VALUES(?,?,?)', (namespace(), path, json.dumps(value, ensure_ascii=False)))
        except Exception:
            # Official action may already have succeeded. Preserve the response;
            # missing journal metadata is displayed as unavailable, never fabricated.
            pass
    return Response(body, status_code=response.status_code, headers=dict(response.headers), media_type=response.media_type)


def public_config():
    available = bool(core.contract and core.w3.is_connected())
    if available:
        available = bool(core.w3.eth.get_code(core.contract.address))
    chain = {'available': available}
    if available:
        agency = os.getenv('UI_AGENCY_ADDRESS', '')
        signer = None
        if agency and core.Web3.is_address(agency):
            info = core.contract.functions.agencies(core.Web3.to_checksum_address(agency)).call()
            signer = info[2]  # AgencyInfo: type, signer, active
        chain.update(chain_id=core.w3.eth.chain_id, contract_address=core.contract.address,
                     agency_address=agency, signer_address=signer,
                     agency_nonce=str(core.contract.functions.agencyNonces(core.Web3.to_checksum_address(agency)).call()) if agency else None,
                     admin_address=core.contract.functions.admin().call(),
                     reviewer_addresses=[v.strip() for v in os.getenv('V11_MAPPING_REVIEWERS', '').split(',') if v.strip()],
                     rpc_url=os.getenv('RPC_URL', 'http://127.0.0.1:8545'), domain_version='2')
    return {'schema_version':'1.1', 'policy_hash':core.v11_sha256(core.POLICY), 'environment':'LOCAL_OFFICIAL_INTEGRATION', 'chain':chain,
            'ai':{'provider':'fixture' if FIXTURE else 'Gemini', 'is_simulated':FIXTURE,
                  'key_configured':bool(os.getenv('GEMINI_API_KEY'))},
            'capabilities':dict(claim_anchor=True,proof_attestation=True,verification_anchor=True,admin_review=True,close_case=True),
            'limitations':['로컬 합성 자료 전용 · 화면 역할 선택은 인증이 아닙니다.',
                           'Verification 중복 방지는 팀 백엔드 구현을 사용합니다. 응답 불명확 시 자동 재제출하지 않습니다.',
                           '관리자 사유는 frontend_server를 거친 성공 응답만 보조 이력에 보관됩니다.']}


@app.get('/api/v1/frontend/status')
def frontend_status():
    return public_config()


def tx_for_proof(case_id, proof_id, version):
    for path, value in reversed(audit_rows()):
        if path == '/api/v1/proofs/anchor' and value.get('case_id') == case_id and value.get('proof_id') == proof_id and value.get('proof_version', version)==version:
            return hx(value.get('proof_tx_hash'))
    # Official Proof Draft omits tx hash; recover from actual events.
    try:
        ident = bytes.fromhex(hashlib.sha256(proof_id.encode()).hexdigest())
        events = core.contract.events.AgencyProofAnchored().get_logs(from_block=0, to_block='latest', argument_filters={'caseId':core.case_uint(case_id)})
        for e in reversed(events):
            if bytes(e['args']['proofIdHash']) == ident and int(e['args']['proofVersion'])==version:
                return core.Web3.to_hex(e['transactionHash'])
    except Exception:
        pass
    return None


def case_view(record):
    from copy import deepcopy
    c = deepcopy(record)
    cid = c['case_id']
    claims = c.get('v11_claims', [])
    for claim in claims:
        claim['chain_status'] = receipt_status(claim.get('claim_tx_hash'))
    proofs = []
    for (case_id, _, _), draft in list(core.PROOF_DRAFTS.items()):
        if case_id != cid:
            continue
        p = deepcopy(draft['proof_content'])
        tx = tx_for_proof(cid, p['proof_id'], p['proof_version']) if draft['status'] == 'ANCHORED' else None
        p.update(proof_hash=draft['proof_hash'], source_bytes=draft['source_bytes'].decode('utf-8'),
                 proof_tx_hash=tx, chain_status=receipt_status(tx) if draft['status']=='ANCHORED' else 'PENDING',
                 source_uri='가상 기관 원본', signature=None, mapping_reference='CALL_REF['+p['issuer_agency_id']+':'+p['call_id']+']')
        proofs.append(p)
    mappings = [deepcopy(m) for (case_id, _), rows in list(core.V11_MAPPING_HISTORY.items()) if case_id==cid for m in rows]
    for m in mappings:
        m['evidence_note'] = (m.get('confirmation_evidence') or {}).get('note', '')
    verifications = [deepcopy(v) for v in list(core.V11_VERIFICATION_RESULTS.values()) if v.get('case_id')==cid]
    reviews = [dict(v, chain_status=receipt_status(v.get('review_tx_hash'))) for path,v in audit_rows() if path.endswith('/reviews') and v.get('case_id')==cid]
    # Recover chain review existence even when created by another client.
    for v in verifications:
        tx = v.get('verification_tx_hash')
        v['created_at'] = None
        if tx:
            try:
                block=core.w3.eth.get_transaction_receipt(hx(tx))['blockNumber']
                v['created_at']=datetime.fromtimestamp(core.w3.eth.get_block(block)['timestamp'],timezone.utc).isoformat()
            except Exception:
                pass
        v.update(chain_status=receipt_status(tx),verification_tx_hash=hx(tx),request_id=tx or v['verification_id'])
        related = [x for x in claims if x['step_id']==v['step_id']]
        latest = related[-1] if related else None
        latest_proofs = {p['proof_id']:p for p in proofs}
        fresh = bool(latest and v['claim_ref']['claim_id']==latest['claim_id'] and v['claim_ref']['claim_version']==latest['claim_version'])
        for p in v.get('proof_refs', []):
            fresh = fresh and latest_proofs.get(p['proof_id'],{}).get('proof_version')==p['proof_version']
        same_step = [x for x in verifications if x['step_id']==v['step_id']]
        fresh = fresh and same_step[-1]['verification_id']==v['verification_id']
        try:
            chain_id=core.case_uint(cid)
            latest_record=core.contract.functions.getLatestVerification(chain_id,v['step_id']).call()
            epoch=core.contract.functions.getAgencyProofHistoryLength(chain_id,v['step_id']).call()
            fresh=fresh and bytes(latest_record[0])==hashlib.sha256(v['verification_id'].encode()).digest() and latest_record[6]==epoch
        except Exception:
            fresh=False
        v['freshness_status'] = 'CURRENT' if fresh else 'NEEDS_REVERIFICATION' 
        try:
            step = v['step_id']; n = core.contract.functions.getVerificationReviewHistoryLength(core.case_uint(cid), step).call()
            vi = hashlib.sha256(v['verification_id'].encode()).digest()
            for i in range(n):
                r = core.contract.functions.getVerificationReviewRecord(core.case_uint(cid),step,i).call()
                if bytes(r[0]) == vi and not any(x['verification_id']==v['verification_id'] and x.get('reviewer_id','').lower()==r[3].lower() and x.get('review_status')=={1:'ACCEPTED',2:'ACKNOWLEDGED',3:'REVISION_REQUESTED'}.get(r[2]) for x in reviews):
                    reviews.append(dict(review_id=f'chain-{step}-{i}',case_id=cid,step_id=step,verification_id=v['verification_id'],verification_hash=v['verification_hash'],review_status={1:'ACCEPTED',2:'ACKNOWLEDGED',3:'REVISION_REQUESTED'}.get(r[2],'UNKNOWN'),reviewer_id=r[3],reviewed_at=datetime.fromtimestamp(r[4],timezone.utc).isoformat(),reason_text='온체인 검토 이력 · 사유 원문은 현재 조회할 수 없습니다.',review_hash=None,review_tx_hash=None,chain_status='CONFIRMED'))
        except Exception:
            pass
        matches=[r for r in reviews if r['verification_id']==v['verification_id']]
        v['review_status']=matches[-1]['review_status'] if matches else 'PENDING'
    blockers=[]; eligible=False
    if not c.get('is_closed'):
        try:
            core.contract.functions.closeCase(core.case_uint(cid),'프론트엔드 종결 조건 조회').call({'from':core.contract.functions.admin().call()})
            eligible=True
        except Exception as e:
            blockers=[str(e)]
    close = next((v for p,v in reversed(audit_rows()) if p==f'/api/v1/cases/{cid}/close'),{})
    return dict(c, status='CLOSED' if c.get('is_closed') else 'OPEN', created_at=claims[0]['claim_created_at'] if claims else None,
                scenario_id=next((s for s in ['contradicted','insufficient','ambiguous'] if s in cid),'supported'),
                region='가상 지역',claims=claims,proofs=proofs,mappings=mappings,verifications=verifications,reviews=reviews,
                close_eligible=eligible,close_blockers=blockers,close_tx_hash=hx(close.get('tx_hash')),closed_at=None)


@app.get('/api/v1/frontend/cases')
def frontend_cases():
    core.require_chain()
    return [case_view(c) for c in list(core.cases_db.values())]


@app.get('/api/v1/frontend/cases/{case_id}')
def frontend_case(case_id: str):
    if case_id not in core.cases_db:
        raise HTTPException(404,'Case not found')
    return case_view(core.cases_db[case_id])


@app.get('/api/v1/frontend/drafts/{case_id}/{proof_id}/{version}')
def frontend_draft(case_id: str, proof_id: str, version: int):
    draft=core.PROOF_DRAFTS.get((case_id,proof_id,version))
    if not draft:
        raise HTTPException(404,'Draft not found')
    return dict(proof_content=draft['proof_content'],proof_hash=draft['proof_hash'],typed_data=draft['typed_data'],draft_status=draft['status'])


@app.get('/api/v1/frontend/transactions/{tx_hash}')
def frontend_transaction(tx_hash: str):
    core.require_chain()
    return dict(request_id=tx_hash,tx_hash=hx(tx_hash),chain_status=receipt_status(tx_hash),kind='ONCHAIN',error_code=None)


# Explicit opt-in test harness. Never enabled by default; actual rules/chain are used.
FIXTURE = os.getenv('FULLPROOF_UI_AI_MODE', 'live') == 'fixture'
if FIXTURE:
    import verification_v11 as module
    def fixture_extract(claim, **kwargs):
        text=claim['claim_text']
        expected='2026년 10월 18일 14시에 P001과 통화에 성공했다.'
        if text != expected and not (text.startswith(expected+' CALL_REF[DEMO-TEL:') and text.endswith(']')):
            return dict(schema_version='1.1',claim_id=claim['claim_id'],claim_version=claim['claim_version'],extraction_status='FAILED',actions=[],model_name='fixture-no-model',prompt_version='fixture-v1',review_required=True)
        return dict(schema_version='1.1',claim_id=claim['claim_id'],claim_version=claim['claim_version'],extraction_status='COMPLETED',actions=[dict(action_type='PHONE_CALL',action_result='SUCCESS',target_id='P001',occurred_at='2026-10-18T05:00:00Z',source_excerpt=text)],model_name='fixture-no-model',prompt_version='fixture-v1',review_required=False)
    module.extract_v11=fixture_extract


@app.get('/api/v1/frontend/verifications/{verification_id}/integrity-data')
def frontend_integrity(verification_id: str):
    from frontend_integrity import integrity_data
    return integrity_data(verification_id,core)
