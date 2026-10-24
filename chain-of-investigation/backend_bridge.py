"""Register isolated AI endpoints on Jisu's existing FastAPI app.

No changes to contract/signing schema. This integration only stores analyses;
never reports anchoring success. Old verify route is disabled by default because
it reparses a signed Claim and cannot represent INSUFFICIENT.
Provide trusted_validator to obtain verified institution records from backend.
Default validation is PENDING, so unverified proofs cannot become SUPPORTED.
"""
import os
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field
from pipeline import AnalysisStore, RequestConflict, analyze_and_save


class AnalyzeRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    request_id: str = Field(min_length=1, max_length=128)
    case_id: str = Field(min_length=1)
    step_id: int = Field(ge=0)
    claim_id: str = Field(min_length=1)
    claim_version: int = Field(ge=1)
    raw_claim_text: str = Field(min_length=1, max_length=20000)
    proof: Optional[dict] = None
    evidence: list[dict] = Field(default_factory=list)


def register_ai_routes(app, cases_db, *, trusted_validator=None, policy_pack=None, db_path=None, verification_resolver=None):
    store = AnalysisStore(db_path or os.getenv('AI_DB_PATH', str(Path(__file__).parent / 'data' / 'ai.sqlite3')))
    # Deliberately fail closed on the unsafe legacy path; keep unrelated routes.
    app.router.routes[:] = [r for r in app.router.routes
                            if not (getattr(r, 'path', '') == '/api/v1/cases/verify' and 'POST' in getattr(r, 'methods', set()))]

    @app.post('/api/v1/cases/verify')
    def legacy_verify_disabled():
        raise HTTPException(409, 'Use /api/v1/ai/analyses. Frozen payload/signature flow and INSUFFICIENT mapping must be agreed before anchoring.')

    @app.post('/api/v1/ai/analyses')
    def create_analysis(body: AnalyzeRequest):
        case = cases_db.get(body.case_id)
        if case is None:
            raise HTTPException(404, 'Case not found')
        if case.get('is_closed'):
            raise HTTPException(409, 'Case is closed')
        steps = case.get('steps', [])
        if body.step_id >= len(steps):
            raise HTTPException(400, 'Step index out of bounds')
        validation = trusted_validator(body.case_id, body.step_id, body.proof) if trusted_validator else {'status': 'PENDING', 'reason_codes': ['TRUSTED_PROOF_VALIDATOR_NOT_CONFIGURED']}
        # stable request fingerprint despite server-clock changes on retry
        cached = store.by_request(body.request_id)
        if cached:
            old = store.get(cached['analysis_id'])['input']
            old_body = old['http_request']
            if old_body != body.model_dump():
                raise HTTPException(409, 'REQUEST_ID_CONFLICT')
            return {'request_id': body.request_id, 'analysis_id': cached['analysis_id'],
                    'storage_status': 'ALREADY_SAVED', 'anchor_status': 'NOT_REQUESTED', 'analysis': cached}
        request = body.model_dump()
        request['http_request'] = body.model_dump()
        request['raw_text'] = request.pop('raw_claim_text')
        request.update(evaluated_at=datetime.now(timezone.utc).isoformat(),
                       proof_validation=validation, snapshot_complete=False)
        if policy_pack is not None:
            request['policy_pack'] = policy_pack
        try:
            saved = analyze_and_save(store, request)
            result = saved['analysis']
            for warning in result['warnings']:
                store.observe_alert(body.case_id, warning)
            return {'request_id': body.request_id, 'analysis_id': result['analysis_id'],
                    'storage_status': saved['storage_status'], 'anchor_status': 'NOT_REQUESTED', 'analysis': result}
        except RequestConflict as exc:
            raise HTTPException(409, str(exc))
        except (ValueError, KeyError, TypeError) as exc:
            raise HTTPException(422, str(exc))

    @app.get('/api/v1/ai/analyses/{analysis_id}')
    def get_analysis(analysis_id: str):
        try:
            return store.get(analysis_id)
        except KeyError:
            raise HTTPException(404, 'Analysis not found')

    @app.get('/api/v1/ai/cases/{case_id}/history')
    def get_history(case_id: str):
        if case_id not in cases_db:
            raise HTTPException(404, 'Case not found')
        return {'case_id': case_id, 'history': store.history(case_id)}

    from verification_v11 import register_v11_routes
    register_v11_routes(app, resolver=verification_resolver)
    return store


class AnchorRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    analysis_id: str = Field(min_length=1)
    agency: str
    signature: str
    nonce: int = Field(ge=0)
    deadline: int = Field(gt=0)
    evidence_timestamp: int = Field(ge=0)


def register_signed_draft_routes(app, cases_db, store, chain_context, *, policy_pack=None):
    """LEGACY v1 ONLY: incompatible with v1.1 ProofAttestation / Domain version 2.

    Do not register this function for the v1.1 integration. It signs Claim +
    Proof + verdict for the old contract. Merely adding proofVersion cannot
    migrate its anchorProof arguments or its signature validation semantics.
    v1.1 uses register_v11_routes for decisions; the backend owns independent
    institution ProofAttestation creation, validation and anchoring.

    Unsigned drafts are explicitly provisional. After signing, anchoring uses
    immutable stored bytes/results and never reruns an LLM. No fabricated VALID
    proof is exposed as a final verified analysis.
    """
    from pipeline import analyze, input_fingerprint
    from verification import timestamp

    def checked_case(case_id, step_id):
        case = cases_db.get(case_id)
        if not case:
            raise HTTPException(404, 'Case not found')
        if case.get('is_closed'):
            raise HTTPException(409, 'Case is closed')
        if step_id >= len(case.get('steps', [])):
            raise HTTPException(400, 'Step index out of bounds')
        return case

    @app.post('/api/v1/ai/drafts')
    def create_draft(body: AnalyzeRequest):
        checked_case(body.case_id, body.step_id)
        key = 'draft:' + body.request_id
        cached = store.by_request(key)
        if cached:
            original = store.get(cached['analysis_id'])['input']
            if original['http_request'] != body.model_dump():
                raise HTTPException(409, 'REQUEST_ID_CONFLICT')
            return {'storage_status':'ALREADY_SAVED', 'trust_status':'PENDING_SIGNATURE', 'analysis':cached}
        request = body.model_dump()
        request['raw_text'] = request.pop('raw_claim_text')
        request.update(request_id=key, http_request=body.model_dump(),
                       evaluated_at=datetime.now(timezone.utc).isoformat(), snapshot_complete=False,
                       proof_validation={'status':'VALID','validation_id':'UNSIGNED_DRAFT_ONLY'})
        if policy_pack is not None:
            request['policy_pack'] = policy_pack
        try:
            draft = analyze(request)
            draft.update(is_provisional=True, trust_status='PENDING_SIGNATURE',
                         reason_text='서명 전 분석 초안입니다. ' + draft['reason_text'])
            draft, state = store.save(request, draft)
            return {'storage_status':state,'trust_status':'PENDING_SIGNATURE','analysis':draft}
        except (ValueError, KeyError, TypeError) as exc:
            raise HTTPException(422,str(exc))

    @app.post('/api/v1/ai/drafts/{analysis_id}/signing-payload')
    def signing_payload(analysis_id: str, body: AnchorRequest):
        if body.analysis_id != analysis_id:
            raise HTTPException(400, 'Analysis reference mismatch')
        return prepare(body)

    def prepare(body):
        try:
            stored = store.get(body.analysis_id)
        except KeyError:
            raise HTTPException(404,'Analysis not found')
        draft, original = stored['analysis'], stored['input']
        if not draft.get('is_provisional'):
            raise HTTPException(400,'Not an institution-signing draft')
        case = checked_case(draft['case_id'],draft['step_id'])
        # Only the newest draft for this step can be submitted.
        drafts=[r for r in store.history(draft['case_id']) if r.get('is_provisional') and r['step_id']==draft['step_id']]
        if not drafts or drafts[-1]['analysis_id']!=draft['analysis_id']:
            raise HTTPException(409,'Stale draft: prepare the latest analysis')
        verdict=draft['verdict']
        if verdict not in ('SUPPORTED','CONTRADICTED'):
            raise HTTPException(409,'INSUFFICIENT/failed analysis cannot be mapped to an existing on-chain status')
        selected=next(s for s in draft['resolved_policy']['resolved_steps'] if s['step_id']==draft['step_id'])
        if case['steps'][draft['step_id']].get('step_name')!=selected['step_name']:
            raise HTTPException(409,'Backend step and Policy Pack are not aligned; configure the correct policy')
        stage=next(s for s in draft['policy_assessment']['step_results'] if s['step_id']==draft['step_id'])
        if verdict=='SUPPORTED' and stage['status']!='SATISFIED':
            raise HTTPException(409,'Supported record does not satisfy step completion criterion')
        proof=original.get('proof')
        if not proof:
            raise HTTPException(409,'Proof missing')
        from verification import normalize_proof
        normalized=normalize_proof(proof)
        try:
            occurrence=int(timestamp(normalized.get('occurred_at')).timestamp())
        except (ValueError, TypeError):
            raise HTTPException(422,'Proof action timestamp with timezone required')
        if occurrence!=body.evidence_timestamp:
            raise HTTPException(409,'evidence_timestamp must equal Proof action occurrence time')
        ctx=chain_context
        ctx['require_chain']()
        try:
            agency=ctx['Web3'].to_checksum_address(body.agency)
            request={'caseId':ctx['case_uint'](draft['case_id']), 'stepId':draft['step_id'],
                     'claimHash':ctx['canonical_hash'](draft['structured_claim']),
                     'proofHash':ctx['canonical_hash'](proof), 'result':1 if verdict=='SUPPORTED' else 2,
                     'evidenceTimestamp':body.evidence_timestamp,'nonce':body.nonce,
                     'deadline':body.deadline,'agency':agency}
            domain={'name':'FullProof','version':'1','chainId':ctx['w3'].eth.chain_id,
                    'verifyingContract':ctx['contract'].address}
            # JSON uints represented as strings to avoid JS precision loss.
            message={k:(ctx['Web3'].to_hex(v) if k in ('claimHash','proofHash') else str(v) if k in ('caseId','stepId','evidenceTimestamp','nonce','deadline') else v) for k,v in request.items()}
            return {'analysis_id':draft['analysis_id'],'domain':domain,'types':ctx['PROOF_TYPES'],
                    'message':message,'trust_status':'PENDING_SIGNATURE'}
        except (ValueError, TypeError) as exc:
            raise HTTPException(422,str(exc))

    @app.get('/api/v1/ai/anchor-status/{analysis_id}')
    def poll_anchor(analysis_id: str):
        try:
            saved = store.get(analysis_id)
        except KeyError:
            raise HTTPException(404, 'Analysis not found')
        delivery = saved['delivery']
        if not delivery:
            return {'analysis_id': analysis_id, 'anchor_status': 'NOT_REQUESTED'}
        if delivery['anchor_status'] != 'SUBMITTED':
            return delivery
        ctx = chain_context
        ctx['require_chain']()
        try:
            receipt = ctx['w3'].eth.get_transaction_receipt(delivery['transaction_hash'])
        except Exception as exc:
            if type(exc).__name__ == 'TransactionNotFound':
                return delivery
            raise HTTPException(503, 'Cannot confirm transaction status')
        delivery.update(anchor_status='CONFIRMED' if receipt['status'] == 1 else 'FAILED',
                        trust_status='VALID' if receipt['status'] == 1 else 'INVALID')
        store.set_delivery(analysis_id, delivery)
        if receipt['status'] == 1:
            draft, original = saved['analysis'], saved['input']
            step = cases_db.get(draft['case_id'], {}).get('steps', [])
            if draft['step_id'] < len(step):
                step[draft['step_id']].update(
                    claim_hash=ctx['Web3'].to_hex(ctx['canonical_hash'](draft['structured_claim'])),
                    proof_hash=ctx['Web3'].to_hex(ctx['canonical_hash'](original['proof'])),
                    status='VERIFIED' if draft['verdict'] == 'SUPPORTED' else 'MISMATCH',
                    is_completed=draft['verdict'] == 'SUPPORTED', tx_hash=delivery['transaction_hash'])
        return delivery

    @app.post('/api/v1/ai/anchor')
    def anchor_frozen_analysis(body: AnchorRequest):
        try:
            stored=store.get(body.analysis_id)
        except KeyError:
            raise HTTPException(404,'Analysis not found')
        delivery=stored['delivery']
        if delivery and delivery['anchor_status'] in ('CONFIRMED', 'SUBMITTED'):
            return delivery
        prepared=prepare(body)
        ctx=chain_context
        m=prepared['message']
        request={k:int(v) if k in ('caseId','stepId','result','evidenceTimestamp','nonce','deadline') else ctx['Web3'].to_bytes(hexstr=v) if k in ('claimHash','proofHash') else v for k,v in m.items()}
        draft=stored['analysis']
        try:
            recovered=ctx['validate_proof'](request,body.signature)
            call=ctx['contract'].functions.anchorProof(request['caseId'],request['stepId'],request['claimHash'],request['proofHash'],request['result'],request['evidenceTimestamp'],request['deadline'],request['nonce'],request['agency'],body.signature)
            transaction_sender=ctx['sender']()
            # Contract enforces authorized signer as well as nonce/deadline.
            call.call({'from':transaction_sender})
            tx=call.transact({'from':transaction_sender})
            tx_hash=ctx['Web3'].to_hex(tx)
            response={'request_id':draft['request_id'],'analysis_id':draft['analysis_id'],
                      'storage_status':'SAVED','anchor_status':'SUBMITTED','transaction_hash':tx_hash,
                      'trust_status':'PENDING_CONFIRMATION','signer':recovered}
            store.set_delivery(draft['analysis_id'],response)
            confirmed_hash=ctx['confirmed'](tx)
            response.update(anchor_status='CONFIRMED',transaction_hash=confirmed_hash,trust_status='VALID')
            store.set_delivery(draft['analysis_id'],response)
            case=cases_db[draft['case_id']]
            case['steps'][draft['step_id']].update(claim_hash=m['claimHash'],proof_hash=m['proofHash'],
                status='VERIFIED' if request['result']==1 else 'MISMATCH',is_completed=request['result']==1,tx_hash=confirmed_hash)
            return response
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(400, 'Signature/anchoring failed: '+str(exc))
