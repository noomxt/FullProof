"""v1.1 Rule Engine. Inputs and canonicalizer come from the trusted backend.

Does not verify institution signatures or submit blockchain transactions.
Never accept validation or mapping assurance directly from an HTTP client.
"""
from copy import deepcopy
from datetime import datetime
from hashlib import sha256
import re
from uuid import uuid4

POLICY = {
    'schema_version': '1.1', 'policy_id': 'CALL_VERIFICATION',
    'policy_version': 'policy-v1',
    'required_fields': ['action_result', 'action_type', 'target_id'],
    'time_tolerance_seconds': 600, 'proof_mapping_required': True,
    'semantic_analysis_required': False,
}
PROOF_FIELDS = ('schema_version proof_id proof_version case_id step_id '
                'issuer_agency_id agency_address proof_type call_id target_id '
                'action_type proof_occurred_at proof_issued_at result source_sha256').split()


def extract_v11(claim, *, client=None):
    """Adapt the existing grounded parser without changing original Claim bytes."""
    from ai_engine import parse_claim_with_llm, StructuredClaimV11
    from verification import normalize_claim, timestamp
    validate_claim_identity(claim)
    parsed = parse_claim_with_llm(claim['claim_text'], client=client)
    actions = normalize_claim(parsed).get('actions', [])
    # Preserve the parser's distinct request/review types.
    # MVP v1.1 only permits PHONE_CALL in the decision function.
    renamed = []
    for action in actions:
        renamed.append(dict(action_type=action['action_type'],
                            action_result=action['status_claim'], target_id=action['target_id'],
                            occurred_at=timestamp(action['claimed_time']).strftime('%Y-%m-%dT%H:%M:%SZ') if action.get('claimed_time') else None,
                            source_excerpt=action['source_text']))
    failed = parsed.get('parse_status') == 'FAILED'
    review = failed or len(renamed) != 1 or parsed.get('parse_status') != 'SUCCESS'
    result = dict(schema_version='1.1', claim_id=claim['claim_id'], claim_version=claim['claim_version'],
                extraction_status='FAILED' if failed else 'NEEDS_REVIEW' if review else 'COMPLETED',
                actions=renamed, model_name=parsed.get('model_name'),
                prompt_version=parsed.get('prompt_version'), review_required=review)
    # Legacy injected parsers may have no model metadata. Never invent a model.
    return StructuredClaimV11.model_validate(result).model_dump()


def digest(value, canonicalize):
    encoded = canonicalize(value)
    if not isinstance(encoded, bytes):
        raise ValueError('JCS_CANONICALIZER_MUST_RETURN_BYTES')
    return '0x' + sha256(encoded).hexdigest()


def check_hash(value):
    if not isinstance(value, str) or not re.fullmatch(r'0x[0-9a-f]{64}', value):
        raise ValueError('INVALID_HASH')
    return value


def utc(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z', value):
        raise ValueError('INVALID_UTC_TIMESTAMP')
    return datetime.strptime(value, '%Y-%m-%dT%H:%M:%SZ')


def missing_comparison_value(value):
    """Blank text is absent evidence; never rewrite original/hash input values."""
    return value is None or (isinstance(value, str) and
                             (not value.strip() or value == 'UNKNOWN'))


def ref(record, kind):
    ident, version = record[kind + '_id'], record[kind + '_version']
    if not isinstance(ident, str) or not ident or type(version) is not int or version < 1:
        raise ValueError('INVALID_REFERENCE')
    return {kind + '_id': ident, kind + '_version': version,
            kind + '_hash': check_hash(record[kind + '_hash'])}


def validate_claim_identity(claim):
    """Validate before paying for extraction; hashing remains backend-owned."""
    if not isinstance(claim, dict):
        raise ValueError('INVALID_CLAIM')
    if claim.get('schema_version', '1.1') != '1.1':
        raise ValueError('INVALID_SCHEMA_VERSION')
    if not isinstance(claim.get('claim_id'), str) or not claim['claim_id'].strip():
        raise ValueError('INVALID_CLAIM_ID')
    if type(claim.get('claim_version')) is not int or claim['claim_version'] < 1:
        raise ValueError('INVALID_CLAIM_VERSION')
    text = claim.get('claim_text')
    if not isinstance(text, str) or not text.strip() or len(text) > 20000:
        raise ValueError('INVALID_CLAIM_TEXT')


def validate_extraction(extraction, claim):
    """Reject malformed data independently of Proof availability and verdict."""
    from ai_engine import ClaimActionV11
    if extraction is None:
        return {}
    if not isinstance(extraction, dict):
        raise ValueError('INVALID_EXTRACTION')
    if not extraction:
        return extraction
    if extraction.get('schema_version') != '1.1':
        raise ValueError('INVALID_EXTRACTION_SCHEMA')
    if (extraction.get('claim_id'), extraction.get('claim_version')) != (claim['claim_id'], claim['claim_version']):
        raise ValueError('EXTRACTION_REFERENCE_MISMATCH')
    if type(extraction.get('claim_version')) is not int:
        raise ValueError('INVALID_EXTRACTION_VERSION')
    if extraction.get('extraction_status') not in ('PENDING', 'COMPLETED', 'NEEDS_REVIEW', 'FAILED'):
        raise ValueError('INVALID_EXTRACTION_STATUS')
    if 'review_required' in extraction and type(extraction['review_required']) is not bool:
        raise ValueError('INVALID_REVIEW_REQUIRED')
    for field in ('prompt_version',):
        if not isinstance(extraction.get(field), str) or not extraction[field].strip():
            raise ValueError('EXTRACTION_METADATA_REQUIRED')
    if extraction.get('extraction_status') == 'COMPLETED' and (
            not isinstance(extraction.get('model_name'), str) or not extraction['model_name'].strip()):
        raise ValueError('EXTRACTION_MODEL_REQUIRED')
    actions = extraction.get('actions')
    if not isinstance(actions, list):
        raise ValueError('INVALID_EXTRACTION_ACTIONS')
    for action in actions:
        # Validate blank legacy comparison values as missing without changing
        # the original object or any hash input.
        checked = dict(action) if isinstance(action, dict) else action
        if isinstance(checked, dict) and isinstance(checked.get('occurred_at'), str) and not checked['occurred_at'].strip():
            checked['occurred_at'] = None
        validated = ClaimActionV11.model_validate(checked)
        if not validated.source_excerpt.strip() or validated.source_excerpt not in claim['claim_text']:
            raise ValueError('INVALID_SOURCE_EXCERPT')
        if validated.target_id is not None and validated.target_id.strip() and validated.target_id not in validated.source_excerpt:
            raise ValueError('UNGROUNDED_TARGET_ID')
    return extraction


def sort_conflicts(conflicts):
    """Validate MVP conflict types and sort null before every string.

    No type coercion: null and the empty string remain distinct hash inputs.
    Returns a new list without modifying the original records.
    """
    def nullable_key(value):
        if value is None:
            return (0, '')
        if not isinstance(value, str):
            raise ValueError('INVALID_CONFLICT_VALUE_TYPE')
        return (1, value)

    def key(item):
        if not isinstance(item, dict) or any(k not in item for k in
                ('field', 'reason_code', 'claim_value', 'proof_value')):
            raise ValueError('INVALID_CONFLICT_RECORD')
        if not isinstance(item['field'], str) or not isinstance(item['reason_code'], str):
            raise ValueError('INVALID_CONFLICT_SORT_FIELD_TYPE')
        return (item['field'], item['reason_code'],
                nullable_key(item['claim_value']), nullable_key(item['proof_value']))

    return sorted(conflicts, key=key)


def verify_v11(*, claim, proofs, mappings, proof_validation, canonicalize,
               policy=None, verification_id=None, registered_policy_hash=None,
               expected_proof_refs_hash=None):
    """Return exactly section 10.2; canonicalize must be backend RFC8785 -> bytes.

    proof_validation is keyed by (proof_id, proof_version), with status=VALID
    only after backend signature/agency/source verification, and
    mapping_evidence_sufficient=True only after independent link assessment.
    Policy immutability and current-version resolution belong to backend storage.
    """
    policy = deepcopy(POLICY if policy is None else policy)
    if not isinstance(policy, dict):
        raise ValueError('INVALID_POLICY')
    if set(policy) != set(POLICY):
        raise ValueError('UNSUPPORTED_POLICY_FIELDS')
    if policy.get('schema_version') != '1.1' or policy.get('policy_id') != 'CALL_VERIFICATION':
        raise ValueError('UNSUPPORTED_POLICY')
    if not isinstance(policy.get('policy_version'), str) or not policy['policy_version']:
        raise ValueError('INVALID_POLICY_VERSION')
    fields = policy.get('required_fields')
    if not isinstance(fields, list) or any(f not in ('action_type', 'action_result', 'target_id', 'occurred_at') for f in fields):
        raise ValueError('INVALID_REQUIRED_FIELDS')
    if not {'action_type', 'action_result', 'target_id'}.issubset(fields):
        raise ValueError('CORE_FIELDS_REQUIRED')
    policy['required_fields'] = sorted(set(fields))
    if type(policy.get('time_tolerance_seconds')) is not int or policy['time_tolerance_seconds'] < 0:
        raise ValueError('INVALID_TIME_TOLERANCE')
    if policy.get('proof_mapping_required') is not True or policy.get('semantic_analysis_required') is not False:
        raise ValueError('UNSUPPORTED_POLICY_RULES')
    validate_claim_identity(claim)
    if claim.get('schema_version') != '1.1' or not isinstance(claim.get('case_id'), str) or not claim['case_id'].strip():
        raise ValueError('INVALID_CLAIM')
    if type(claim.get('step_id')) is not int or claim['step_id'] < 0:
        raise ValueError('INVALID_STEP_ID')
    claim_ref = ref(claim, 'claim')
    if '0x' + sha256(claim['claim_text'].encode('utf-8')).hexdigest() != claim_ref['claim_hash']:
        raise ValueError('CLAIM_HASH_MISMATCH')
    refs, seen = [], set()
    if not isinstance(proofs, list) or not isinstance(mappings, list) or not isinstance(proof_validation, dict):
        raise ValueError('INVALID_VERIFICATION_COLLECTIONS')
    if any(not isinstance(m, dict) for m in mappings):
        raise ValueError('INVALID_MAPPING')
    for proof in proofs:
        if not isinstance(proof, dict):
            raise ValueError('INVALID_PROOF')
        if type(proof.get('step_id')) is not int or proof['step_id'] < 0:
            raise ValueError('INVALID_PROOF_STEP_ID')
        if proof.get('schema_version') != '1.1' or any(proof.get(k) != claim[k] for k in ('case_id', 'step_id')):
            raise ValueError('REFERENCE_MISMATCH')
        item = ref(proof, 'proof')
        key = (item['proof_id'], item['proof_version'])
        if key in seen:
            raise ValueError('DUPLICATE_PROOF_REFERENCE')
        seen.add(key)
        check_hash(proof['source_sha256'])
        for field in ('issuer_agency_id', 'agency_address', 'proof_type', 'action_type', 'proof_issued_at'):
            if not isinstance(proof.get(field), str) or not proof[field].strip():
                raise ValueError('INVALID_PROOF_FIELD:' + field)
        for field in ('target_id', 'call_id', 'result'):
            if proof.get(field) is not None and not isinstance(proof[field], str):
                raise ValueError('INVALID_PROOF_FIELD:' + field)
        utc(proof['proof_issued_at'])
        if not missing_comparison_value(proof.get('proof_occurred_at')):
            utc(proof['proof_occurred_at'])
        if digest({k: proof[k] for k in PROOF_FIELDS}, canonicalize) != item['proof_hash']:
            raise ValueError('PROOF_HASH_MISMATCH')
        refs.append(item)
    refs.sort(key=lambda r: (r['proof_id'], r['proof_version']))
    extraction = validate_extraction(claim.get('structured_claim'), claim)
    actions = extraction.get('actions', [])
    missing, conflicts = [], []
    state, verdict = 'COMPLETED', None
    if extraction.get('extraction_status') == 'PENDING':
        state, missing = 'PENDING', ['EXTRACTION_PENDING']
    elif extraction.get('extraction_status') == 'FAILED':
        state, missing = 'FAILED', ['EXTRACTION_FAILED']
    elif extraction.get('extraction_status') != 'COMPLETED' or extraction.get('review_required') or len(actions) != 1:
        state, verdict, missing = 'NEEDS_REVIEW', 'INSUFFICIENT', ['CLAIM_ACTION_REVIEW_REQUIRED']
        if not actions:
            missing.append('CLAIM_ACTION_MISSING')
        elif len(actions) > 1:
            missing.append('CLAIM_SPLIT_REQUIRED')
    elif not proofs:
        verdict, missing = 'INSUFFICIENT', ['PROOF_MISSING']
    elif len(proofs) != 1:
        verdict, missing = 'INSUFFICIENT', ['MULTIPLE_PROOFS_REVIEW_REQUIRED']
    else:
        proof, action = proofs[0], actions[0]
        if action.get('action_result') not in ('SUCCESS', 'FAIL', 'UNKNOWN'):
            raise ValueError('INVALID_ACTION_RESULT')
        for target in (action.get('target_id'), proof.get('target_id')):
            if target is not None and not isinstance(target, str):
                raise ValueError('INVALID_TARGET_ID')
        if not action.get('source_excerpt') or action['source_excerpt'] not in claim['claim_text']:
            raise ValueError('INVALID_SOURCE_EXCERPT')
        key = (proof['proof_id'], proof['proof_version'])
        validation = proof_validation.get(key, {})
        if not isinstance(validation, dict):
            raise ValueError('INVALID_PROOF_VALIDATION')
        linked = [m for m in mappings if
                  type(m.get('claim_version')) is int and type(m.get('proof_version')) is int and
                  (m.get('claim_id'), m.get('claim_version')) == (claim['claim_id'], claim['claim_version']) and
                  (m.get('proof_id'), m.get('proof_version')) == key and
                  m.get('mapping_status') == 'CONFIRMED' and
                  m.get('issuer_agency_id') == proof['issuer_agency_id'] and
                  m.get('call_id') == proof.get('call_id')]
        if validation.get('status') != 'VALID':
            missing.append('PROOF_NOT_VALIDATED')
        if len(linked) != 1 or validation.get('mapping_evidence_sufficient') is not True:
            missing.append('PROOF_MAPPING_AMBIGUOUS')
        if action.get('action_type') != 'PHONE_CALL' or proof.get('proof_type') != 'CALL_LOG':
            missing.append('UNSUPPORTED_ACTION_OR_PROOF_TYPE')
        if not missing:
            outcome = {'CALL_CONNECTED': 'SUCCESS', 'CALL_FAILED': 'FAIL'}.get(proof.get('result'), 'UNKNOWN')
            values = {'action_type': proof.get('action_type'), 'target_id': proof.get('target_id'),
                      'action_result': outcome, 'occurred_at': proof.get('proof_occurred_at')}
            for field in sorted(set(fields) | {'occurred_at'}):
                left, right = action.get(field), values[field]
                if missing_comparison_value(left) or missing_comparison_value(right):
                    missing.append(field)
                    continue
                same = left == right
                if field == 'occurred_at':
                    same = abs((utc(left) - utc(right)).total_seconds()) <= policy['time_tolerance_seconds']
                if not same:
                    conflicts.append(dict(field=field, claim_value=left, proof_value=right,
                                          reason_code='RESULT_MISMATCH' if field == 'action_result' else field.upper() + '_MISMATCH'))
        # Missing linkage/required information cannot establish a contradiction.
        verdict = 'INSUFFICIENT' if missing else 'CONTRADICTED' if conflicts else 'SUPPORTED'
    conflicts = sort_conflicts(conflicts)
    vid = verification_id if verification_id is not None else 'VERIFY-' + str(uuid4())
    if not isinstance(vid, str) or not vid:
        raise ValueError('INVALID_VERIFICATION_ID')
    result = dict(schema_version='1.1', verification_id=vid, case_id=claim['case_id'],
                  step_id=claim['step_id'], claim_ref=claim_ref, proof_refs=refs,
                  processing_status=state, verdict=verdict, conflicts=conflicts,
                  missing_information=sorted(set(missing)),
                  reason_text={None: '추출 처리에 실패했습니다.', 'SUPPORTED': '기관 Proof가 필수 비교 조건과 주장을 뒷받침합니다.',
                               'CONTRADICTED': '연결이 확인된 유효 Proof와 주장 사이에 충돌이 있습니다.',
                               'INSUFFICIENT': '필수 정보 또는 유효한 연결 근거가 부족합니다.'}[verdict],
                  evidence_refs=sorted({r['proof_id'] for r in refs}), review_required=verdict != 'SUPPORTED',
                  decision_policy_version=policy['policy_version'], policy_hash=digest(policy, canonicalize),
                  proof_refs_hash=digest({'schema_version': '1.1', 'proof_refs': refs}, canonicalize))
    result['verification_tx_hash'] = None
    if registered_policy_hash is not None and check_hash(registered_policy_hash) != result['policy_hash']:
        raise ValueError('REGISTERED_POLICY_HASH_MISMATCH')
    if expected_proof_refs_hash is not None and check_hash(expected_proof_refs_hash) != result['proof_refs_hash']:
        raise ValueError('PROOF_REFS_HASH_MISMATCH')
    if 'CLAIM_SPLIT_REQUIRED' in missing:
        result['reason_text'] = '하나의 Claim에 여러 수행 행동이 있습니다. 원문을 보존하고 행동별 새 Claim을 등록해 주세요.'
    elif 'CLAIM_ACTION_MISSING' in missing:
        result['reason_text'] = '원문에서 수행 행동을 확인할 수 없습니다. 수행 행동을 확인해 주세요.'
    elif state == 'PENDING':
        result['reason_text'] = 'AI 추출이 진행 중입니다. 완료 후 검증해 주세요.'
    # reason_text is hashed content: finalize it before the official digest.
    result['verification_hash'] = digest({k: v for k, v in result.items()
                                        if k not in ('verification_hash', 'verification_tx_hash')}, canonicalize)
    return result


def register_v11_routes(app, *, resolver=None):
    """Resolver authenticates and loads immutable inputs; no raw trust flags in body.

    Returns compute-only results. Backend must store/anchor separately.
    """
    from fastapi import Request, HTTPException
    from fastapi.responses import JSONResponse
    from starlette.concurrency import run_in_threadpool

    @app.post('/api/v1/verifications')
    async def create_verification(request: Request):
        if resolver is None:
            return JSONResponse(status_code=503, content={'success': False, 'data': None,
                'error': {'code': 'V11_BACKEND_RESOLVER_REQUIRED',
                          'message': '인증·원본·매핑·서명 검증 및 공식 JCS 함수를 제공하는 백엔드 연결이 필요합니다.', 'details': {}}})
        try:
            body = await request.json()
            if not isinstance(body, dict):
                raise ValueError('JSON_OBJECT_REQUIRED')
            inputs = await run_in_threadpool(resolver, request, body)
            result = await run_in_threadpool(verify_v11, **inputs)
            return {'success': True, 'data': result, 'error': None}
        except HTTPException as exc:
            return JSONResponse(status_code=exc.status_code, headers=exc.headers,
                content={'success': False, 'data': None, 'error': {
                    'code': 'BACKEND_REQUEST_REJECTED', 'message': str(exc.detail), 'details': {}}})
        except (ValueError, KeyError, TypeError) as exc:
            return JSONResponse(status_code=422, content={'success': False, 'data': None,
                'error': {'code': 'INVALID_VERIFICATION_INPUT', 'message': str(exc), 'details': {}}})


def register_v11_extraction_route(app, *, resolver=None, client=None):
    """Backend resolver(request, claim_id, body) authenticates and loads Claim.

    The backend persists original bytes/hash BEFORE calling this endpoint,
    and stores the returned extraction under the exact Claim version. A body
    must never be used as an authoritative Claim or source of trust flags.
    Blocking provider calls run outside FastAPI's event loop.
    """
    from fastapi import Request, HTTPException
    from fastapi.responses import JSONResponse
    from starlette.concurrency import run_in_threadpool

    @app.post('/api/v1/claims/{claim_id}/extract')
    async def create_extraction(claim_id: str, request: Request):
        if resolver is None:
            return JSONResponse(status_code=503, content={'success': False, 'data': None,
                'error': {'code': 'V11_EXTRACTION_RESOLVER_REQUIRED',
                          'message': '인증된 저장 Claim 조회 연결이 필요합니다.', 'details': {}}})
        try:
            body = await request.json()
            if not isinstance(body, dict):
                raise ValueError('JSON_OBJECT_REQUIRED')
            claim = await run_in_threadpool(resolver, request, claim_id, body)
            validate_claim_identity(claim)
            if claim['claim_id'] != claim_id:
                raise ValueError('CLAIM_REFERENCE_MISMATCH')
            if 'claim_version' in body and (type(body['claim_version']) is not int or
                    body['claim_version'] != claim['claim_version']):
                raise ValueError('CLAIM_VERSION_MISMATCH')
            result = await run_in_threadpool(extract_v11, claim, client=client)
            return {'success': True, 'data': result, 'error': None}
        except HTTPException as exc:
            return JSONResponse(status_code=exc.status_code, headers=exc.headers,
                content={'success': False, 'data': None, 'error': {
                    'code': 'BACKEND_REQUEST_REJECTED', 'message': str(exc.detail), 'details': {}}})
        except (ValueError, KeyError, TypeError) as exc:
            return JSONResponse(status_code=422, content={'success': False, 'data': None,
                'error': {'code': 'INVALID_EXTRACTION_INPUT', 'message': str(exc), 'details': {}}})
