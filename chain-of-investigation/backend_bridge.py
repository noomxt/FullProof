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


def register_ai_routes(app, cases_db, *, trusted_validator=None, policy_pack=None, db_path=None,
                       verification_resolver=None, extraction_resolver=None):
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
    if extraction_resolver is not None:
        from verification_v11 import register_v11_extraction_route
        register_v11_extraction_route(app, resolver=extraction_resolver)
    return store


def register_signed_draft_routes(app, cases_db, store, chain_context, *, policy_pack=None):
    """Retired v1 signing adapter: only register explicit 410 migration responses.

    No Claim, verdict, typed data, blockchain calls or storage writes are produced.
    Use backend ProofAttestation endpoints for institution-only signing.
    The signature remains import-compatible during backend API cleanup.
    """
    from fastapi.responses import JSONResponse

    def retired():
        return JSONResponse(status_code=410, content={
            'success': False, 'data': None, 'error': {
                'code': 'LEGACY_AI_SIGNING_DISABLED',
                'message': 'Use /api/v1/proofs/drafts, /api/v1/proofs/anchor and /api/v1/verifications.',
                'details': {}}})

    for path, methods in (
        ('/api/v1/ai/drafts', ['POST']),
        ('/api/v1/ai/drafts/{analysis_id}/signing-payload', ['POST']),
        ('/api/v1/ai/anchor-status/{analysis_id}', ['GET']),
        ('/api/v1/ai/anchor', ['POST']),
    ):
        app.add_api_route(path, retired, methods=methods, include_in_schema=False)
