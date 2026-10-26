"""Historical prototype orchestration and offline analysis history (PRD 9).

Not the v1.1 production verification entry point. v1.1 uses stored Claim
extraction and verification_v11.verify_v11 through main.py. Institution signing
of prototype analysis payloads is disabled in backend_bridge.
"""
import hashlib
import json
import sqlite3
from contextlib import contextmanager
import time
from pathlib import Path
from uuid import uuid4
from datetime import datetime, timezone
from copy import deepcopy
from verification import (VERSION, DEMO_POLICY, normalize_claim, normalize_proof,
    compare_fields, semantic_compare, decide, resolve_policy, evaluate_steps, evidence_warning)


def json_bytes(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8')


def input_fingerprint(value):
    # Local analysis fingerprint; NOT the contract's Keccak-256 hash.
    return hashlib.sha256(json_bytes(value)).hexdigest()


class RequestConflict(ValueError):
    pass


class AnalysisStore:
    def __init__(self, path):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS analyses (
              request_id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL,
              analysis_id TEXT UNIQUE NOT NULL, case_id TEXT NOT NULL,
              created_at TEXT NOT NULL, payload TEXT NOT NULL, input_payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS deliveries (
              analysis_id TEXT PRIMARY KEY, storage_status TEXT NOT NULL,
              anchor_status TEXT NOT NULL, transaction_hash TEXT, details TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS alert_states (
              case_id TEXT NOT NULL, evidence_id TEXT NOT NULL, version TEXT NOT NULL,
              state TEXT NOT NULL, PRIMARY KEY(case_id, evidence_id));
            CREATE TABLE IF NOT EXISTS alert_history (
              id INTEGER PRIMARY KEY, case_id TEXT NOT NULL, evidence_id TEXT NOT NULL,
              version TEXT NOT NULL, state TEXT NOT NULL, created_at TEXT NOT NULL);
            ''')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        try:
            with db:
                yield db
        finally:
            db.close()

    def by_request(self, request_id, fingerprint=None):
        with self.connect() as db:
            row = db.execute('SELECT fingerprint,payload FROM analyses WHERE request_id=?', (request_id,)).fetchone()
        if row is None:
            return None
        if fingerprint is not None and row[0] != fingerprint:
            raise RequestConflict('REQUEST_ID_CONFLICT')
        return json.loads(row[1])

    def get(self, analysis_id):
        with self.connect() as db:
            row = db.execute('SELECT payload,input_payload FROM analyses WHERE analysis_id=?', (analysis_id,)).fetchone()
            delivery = db.execute('SELECT details FROM deliveries WHERE analysis_id=?', (analysis_id,)).fetchone()
        if row is None:
            raise KeyError(analysis_id)
        return {'analysis': json.loads(row[0]), 'input': json.loads(row[1]),
                'delivery': json.loads(delivery[0]) if delivery else None}

    def history(self, case_id):
        with self.connect() as db:
            rows = db.execute('SELECT payload FROM analyses WHERE case_id=? ORDER BY rowid', (case_id,)).fetchall()
        return [json.loads(r[0]) for r in rows]

    def save(self, request, result):
        fingerprint = input_fingerprint(request)
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            existing = db.execute('SELECT fingerprint,payload FROM analyses WHERE request_id=?', (request['request_id'],)).fetchone()
            if existing:
                if existing[0] != fingerprint:
                    raise RequestConflict('REQUEST_ID_CONFLICT')
                return json.loads(existing[1]), 'ALREADY_SAVED'
            db.execute('INSERT INTO analyses VALUES(?,?,?,?,?,?,?)',
                       (request['request_id'], fingerprint, result['analysis_id'], request['case_id'],
                        result['evaluated_at'], json_bytes(result).decode(), json_bytes(request).decode()))
        return result, 'SAVED'

    def set_delivery(self, analysis_id, response):
        self.get(analysis_id)
        if response.get('analysis_id') != analysis_id:
            raise ValueError('RESPONSE_REFERENCE_MISMATCH')
        if response.get('storage_status') not in ('SAVED', 'ALREADY_SAVED', 'REJECTED'):
            raise ValueError('INVALID_STORAGE_STATUS')
        if response.get('anchor_status') not in ('NOT_REQUESTED', 'PENDING', 'SUBMITTED', 'CONFIRMED', 'FAILED'):
            raise ValueError('INVALID_ANCHOR_STATUS')
        if response['anchor_status'] in ('SUBMITTED', 'CONFIRMED') and not response.get('transaction_hash'):
            raise ValueError('TRANSACTION_HASH_REQUIRED')
        with self.connect() as db:
            db.execute('INSERT OR REPLACE INTO deliveries VALUES(?,?,?,?,?)',
                       (analysis_id, response['storage_status'], response['anchor_status'],
                        response.get('transaction_hash'), json_bytes(response).decode()))

    def observe_alert(self, case_id, warning):
        """Persistent transition deduplication; emits event for backend to notify."""
        version = str(warning.get('deadline_version'))
        state = warning.get('warning_code') if warning['action_required'] else 'RESOLVED'
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            previous = db.execute('SELECT version,state FROM alert_states WHERE case_id=? AND evidence_id=?',
                                  (case_id, warning['evidence_id'])).fetchone()
            changed = previous != (version, state)
            if changed:
                db.execute('INSERT OR REPLACE INTO alert_states VALUES(?,?,?,?)',
                           (case_id, warning['evidence_id'], version, state))
                db.execute('INSERT INTO alert_history(case_id,evidence_id,version,state,created_at) VALUES(?,?,?,?,?)',
                           (case_id, warning['evidence_id'], version, state, warning['evaluated_at']))
        return changed and (previous is not None or state != 'RESOLVED')


def analyze(request, *, client=None, parse_function=None):
    """validation passed here must come from a trusted adapter, not HTTP clients."""
    if parse_function is None:
        from ai_engine import parse_claim_with_llm
        parse_function = parse_claim_with_llm
    for key in ('request_id', 'case_id', 'claim_id', 'claim_version', 'step_id', 'raw_text', 'evaluated_at'):
        if key not in request:
            raise ValueError('MISSING_' + key.upper())
    if not isinstance(request['case_id'], str) or not request['case_id']:
        raise ValueError('INVALID_CASE_ID')
    if type(request['step_id']) is not int or request['step_id'] < 0:
        raise ValueError('INVALID_STEP_ID')
    from verification import timestamp
    timestamp(request['evaluated_at'])
    policy = resolve_policy(request.get('policy_pack') or DEMO_POLICY,
                            request.get('case_context', {}), request.get('case_registered_at'))
    step = next((s for s in policy['resolved_steps'] if s['step_id'] == request['step_id']), None)
    if step is None:
        raise ValueError('STEP_NOT_IN_POLICY')
    aid = str(uuid4())
    result = {'request_id': request['request_id'], 'analysis_id': aid,
              'case_id': request['case_id'], 'step_id': request['step_id'],
              'input_refs': {k: request.get(k) for k in ('case_id', 'step_id', 'claim_id', 'claim_version')},
              'analysis_version': VERSION, 'policy_version': policy['policy_version'],
              'is_demo_policy': policy['is_demo'], 'evaluated_at': request['evaluated_at'],
              'anchor_status': 'NOT_REQUESTED'}
    extracted = parse_function(request['raw_text'], client=client)
    result['structured_claim'] = extracted
    warnings = [evidence_warning(e, request['evaluated_at'], request.get('warning_threshold_hours', 24)) for e in request.get('evidence', [])]
    result['warnings'] = warnings
    proof = normalize_proof(request.get('proof'))
    for field in ('case_id', 'step_id'):
        if proof and field in proof and proof[field] != request[field]:
            raise ValueError('REFERENCE_MISMATCH')
    if proof:
        result['input_refs'].update(proof_id=proof.get('proof_id'), proof_version=proof.get('proof_version'))
    input_version = {'claim_id': request['claim_id'], 'claim_version': request['claim_version'], 'proof_id': proof.get('proof_id') if proof else None, 'proof_version': proof.get('proof_version') if proof else None}
    actions = normalize_claim(extracted, request.get('claim_timezone', '+09:00')).get('actions', [])
    action_results = []
    for index, action in enumerate(actions):
        mapping_ambiguous = len(actions) != 1
        if mapping_ambiguous:
            comparison = {'comparison_status': 'BLOCKED', 'field_checks': [], 'blocking_reasons': ['PROOF_MAPPING_AMBIGUOUS']}
        else:
            comparison = compare_fields(action, proof, request.get('proof_validation', {'status': 'PENDING'}), step['comparison_policy'])
        if comparison['comparison_status'] == 'COMPLETED' and step['comparison_policy'].get('semantic_required', True):
            semantics = semantic_compare(action['source_text'], proof.get('proof_text', ''), comparison['field_checks'], client=client)
        else:
            semantics = {'processing_status': 'BLOCKED', 'semantic_status': None, 'findings': [], 'review_required': True, 'error_code': (comparison.get('blocking_reasons') or ['SEMANTIC_NOT_REQUIRED'])[0]}
        judgment = decide(comparison, semantics, semantic_required=step['comparison_policy'].get('semantic_required', True))
        judgment.update(action_index=index, step_id=request['step_id'], action_type=action['action_type'],
                        action_result=action['status_claim'], analysis_id=aid,
                        input_version=input_version, policy_version=policy['policy_version'])
        action_results.append(judgment)
    if extracted['parse_status'] == 'FAILED':
        verdict, processing = None, 'FAILED'
    elif not action_results:
        verdict, processing = 'INSUFFICIENT', 'NEEDS_REVIEW'
    elif any(r['verdict'] == 'CONTRADICTED' for r in action_results):
        verdict, processing = 'CONTRADICTED', 'NEEDS_REVIEW'
    elif any(r['verdict'] != 'SUPPORTED' for r in action_results) or extracted['parse_status'] == 'NEEDS_REVIEW':
        verdict, processing = 'INSUFFICIENT', 'NEEDS_REVIEW'
    else:
        verdict, processing = 'SUPPORTED', 'COMPLETED'
    result.update(verdict=verdict, processing_status=processing, action_results=action_results,
                  error_code=extracted.get('error_code'), review_required=processing != 'COMPLETED',
                  reason_text=' / '.join(r['reason_text'] for r in action_results) or '수행 행동을 확인할 수 없습니다.',
                  reason_codes=sorted({c for r in action_results for c in r['reason_codes']}))
    # Assess only supplied snapshot; mark partial assessments explicitly.
    all_results = request.get('prior_action_results', []) + action_results
    versions = dict(request.get('current_versions', {}))
    versions[str(request['step_id'])] = input_version
    assessment = evaluate_steps(policy, all_results, versions, evidence_warnings=warnings)
    assessment['scope'] = 'COMPLETE_SNAPSHOT' if request.get('snapshot_complete') is True else 'PARTIAL_SNAPSHOT'
    if assessment['scope'] == 'PARTIAL_SNAPSHOT' and assessment['readiness_status'] == 'READY':
        assessment['readiness_status'] = 'NEEDS_REVIEW'
    result.update(policy_assessment=assessment, resolved_policy=policy)
    return result


def analyze_and_save(store, request, **kwargs):
    fingerprint = input_fingerprint(request)
    cached = store.by_request(request['request_id'], fingerprint)
    if cached:
        return {'storage_status': 'ALREADY_SAVED', 'analysis': cached}
    result = analyze(request, **kwargs)
    saved, state = store.save(request, result)
    return {'storage_status': state, 'analysis': saved}


def deliver_result(store, analysis_id, endpoint, *, session=None, token=None, attempts=3):
    """Explicit configured analysis endpoint only; does not use old /anchor.

    POST receiver must implement request_id idempotency. Retry identical payload.
    HTTP contract status must be returned separately from storage status.
    """
    import requests
    if session is None:
        session = requests.Session()
    if type(attempts) is not int or not 1 <= attempts <= 5:
        raise ValueError('INVALID_RETRY_COUNT')
    payload = store.get(analysis_id)['analysis']
    headers = {'Idempotency-Key': payload['request_id']}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    last_error = 'DELIVERY_FAILED'
    for attempt in range(attempts):
        try:
            response = session.post(endpoint, json=payload, headers=headers, timeout=(5, 30))
            if response.status_code in (408, 429) or response.status_code >= 500:
                last_error = 'TEMPORARY_HTTP_ERROR'
            elif response.status_code >= 400:
                return {'delivery_status': 'REJECTED', 'http_status': response.status_code, 'retryable': False}
            else:
                body = response.json()
                if body.get('request_id') != payload['request_id']:
                    raise ValueError('RESPONSE_REFERENCE_MISMATCH')
                store.set_delivery(analysis_id, body)
                return {'delivery_status': 'COMPLETED', **body}
        except (requests.Timeout, requests.ConnectionError):
            last_error = 'DELIVERY_UNCONFIRMED'
        except (ValueError, TypeError, KeyError):
            return {'delivery_status': 'FAILED', 'error_code': 'INVALID_BACKEND_RESPONSE', 'retryable': False}
        if attempt + 1 < attempts:
            time.sleep(min(2 ** attempt, 4))
    return {'delivery_status': 'UNCONFIRMED', 'error_code': last_error,
            'retryable': True, 'request_id': payload['request_id']}
