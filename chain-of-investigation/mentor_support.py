"""Mentor follow-up: durable verification requests, conservative RPC recovery,
and independent browser integrity inputs. Single local service, no production auth.
"""
from copy import deepcopy
import hashlib
import json
import os
import secrets
import threading
import time
from uuid import uuid4
from fastapi import HTTPException
import rfc8785
import database
from contextlib import contextmanager
from web3.exceptions import TransactionNotFound

OWNER = secrets.token_hex(16)
CONTEXT = threading.local()


@contextmanager
def connection():
    db=database.get_connection()
    db.execute('''CREATE TABLE IF NOT EXISTS verification_requests (
        input_key TEXT PRIMARY KEY, verification_id TEXT UNIQUE NOT NULL,
        namespace TEXT NOT NULL, case_id TEXT NOT NULL, state TEXT NOT NULL,
        phase TEXT NOT NULL, owner TEXT NOT NULL, result_json TEXT,
        tx_hash TEXT, error TEXT, updated_at REAL NOT NULL)''')
    db.commit()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def digest(value):
    return '0x'+hashlib.sha256(rfc8785.dumps(value)).hexdigest()


def namespace(core):
    core.require_chain()
    return digest(dict(chain_id=core.w3.eth.chain_id, contract=core.contract.address,
                       first_block_hash=core.w3.eth.get_block(1)['hash'].hex(),
                       contract_code_hash=hashlib.sha256(core.w3.eth.get_code(core.contract.address)).hexdigest()))


def fingerprint(inputs, core):
    claim=inputs['claim']
    # Revalidate server-owned references even when a cached result exists.
    core.validate_v11_onchain_claim(claim)
    for p in inputs['proofs']:
        core.validate_v11_onchain_proof(p)
    refs=sorted([dict(proof_id=p['proof_id'],proof_version=p['proof_version'],proof_hash=p['proof_hash']) for p in inputs['proofs']], key=lambda p:(p['proof_id'],p['proof_version']))
    if len({(p['proof_id'],p['proof_version']) for p in refs})!=len(refs):
        raise HTTPException(409,'Duplicate Proof version')
    ns=namespace(core)
    # Mapping evidence and proof epoch affect the decision/freshness. Do not
    # reuse an INSUFFICIENT result after confirmation or after new Proof arrival.
    content=dict(namespace=ns,case_id=claim['case_id'],step_id=claim['step_id'],claim_ref=dict(claim_id=claim['claim_id'],claim_version=claim['claim_version'],claim_hash=claim['claim_hash']),
                 extraction=claim.get('structured_claim'),proof_refs=refs,policy_hash=core.v11_sha256(core.POLICY),
                 mappings=core.V11_MAPPING_HISTORY.get((claim['case_id'],claim['claim_id']),[]),
                 allowed_reviewers=sorted({a.strip().lower() for a in os.getenv('V11_MAPPING_REVIEWERS','').split(',') if a.strip()}),
                 proof_epoch=core.contract.functions.getAgencyProofHistoryLength(core.case_uint(claim['case_id']),claim['step_id']).call())
    return digest(content),ns


def row_by_id(ident):
    with connection() as db:
        row=db.execute('SELECT * FROM verification_requests WHERE verification_id=?',(ident,)).fetchone()
    if not row:raise HTTPException(404,'Verification request not found')
    return dict(row)


def update(ident, **values):
    allowed={'state','phase','owner','result_json','tx_hash','error'}
    if not set(values)<=allowed:raise ValueError('Invalid request update')
    values['updated_at']=time.time()
    with connection() as db:
        db.execute('UPDATE verification_requests SET '+','.join(k+'=?' for k in values)+' WHERE verification_id=?',(*values.values(),ident))


def stage_result(result):
    ident=getattr(CONTEXT,'verification_id',None)
    if ident:
        update(ident,phase='RESULT_READY',result_json=json.dumps(result,ensure_ascii=False))


def note_submission(tx_hash):
    ident=getattr(CONTEXT,'verification_id',None)
    if ident:
        value=tx_hash.hex() if hasattr(tx_hash,'hex') else str(tx_hash)
        update(ident,state='SUBMITTED',phase='WAITING_RECEIPT',tx_hash=value if value.startswith('0x') else '0x'+value)


def persist_result(core,result):
    core.V11_VERIFICATION_RESULTS[result['verification_id']]=deepcopy(result)
    core.save_v11_store('verification_results',core.V11_VERIFICATION_RESULTS)


def recover(row,core):
    """Never submit again to resolve uncertainty. Reconcile actual chain events."""
    if row['state']=='CONFIRMED':
        try:
            receipt=core.w3.eth.get_transaction_receipt(row['tx_hash'])
            ident=hashlib.sha256(row['verification_id'].encode()).digest()
            if receipt.status==1 and core.contract.functions.registeredVerificationIds(ident).call():
                return row
        except Exception:
            pass
        update(row['verification_id'],state='UNKNOWN',phase='CHAIN_RECORD_UNAVAILABLE',error='현재 체인에서 기존 거래를 확인하지 못했습니다. 초기화·롤백·RPC 상태를 확인하세요.')
        row=row_by_id(row['verification_id'])
    if not row.get('result_json'):
        if row['owner']!=OWNER and row['state'] in ('PROCESSING','SUBMITTED'):
            update(row['verification_id'],state='UNKNOWN',phase='SERVER_RESTARTED',error='서버 재시작으로 진행 여부를 확인해야 합니다. 자동 재제출하지 않습니다.')
            return row_by_id(row['verification_id'])
        return row
    result=json.loads(row['result_json'])
    if result.get('verdict') not in ('SUPPORTED','CONTRADICTED','INSUFFICIENT'):
        return row
    try:
        expected=hashlib.sha256(row['verification_id'].encode()).digest()
        events=core.contract.events.VerificationAnchored().get_logs(from_block=0,to_block='latest',argument_filters={'caseId':core.case_uint(result['case_id'])})
        match=next((e for e in events if bytes(e['args']['verificationIdHash'])==expected),None)
        if match:
            # Verify against actual contract storage, not just an event name.
            count=core.contract.functions.getVerificationHistoryLength(core.case_uint(result['case_id']),result['step_id']).call()
            stored=next((r for i in range(count) if bytes((r:=core.contract.functions.getVerificationRecord(core.case_uint(result['case_id']),result['step_id'],i).call())[0])==expected),None)
            if not stored or core.Web3.to_hex(stored[7])!=result['verification_hash']:
                raise ValueError('On-chain Verification hash mismatch')
            tx=core.Web3.to_hex(match['transactionHash'])
            receipt=core.w3.eth.get_transaction_receipt(tx)
            if receipt.status!=1:raise ValueError('Receipt status is not successful')
            result['verification_tx_hash']=tx
            persist_result(core,result)
            update(row['verification_id'],state='CONFIRMED',phase='COMPLETED',tx_hash=tx,result_json=json.dumps(result,ensure_ascii=False),error=None)
            return row_by_id(row['verification_id'])
        if row.get('tx_hash'):
            try:
                r=core.w3.eth.get_transaction_receipt(row['tx_hash'])
                if r.status==0:
                    update(row['verification_id'],state='FAILED',phase='TRANSACTION_REVERTED',error='거래가 되돌려졌습니다.')
                    return row_by_id(row['verification_id'])
            except TransactionNotFound:
                pass
        if row['owner']!=OWNER and row['state'] in ('PROCESSING','SUBMITTED'):
            update(row['verification_id'],state='UNKNOWN',phase='RECOVERY_REQUIRED',error='기록을 확인하지 못했습니다. 자동 재제출하지 않습니다.')
    except Exception as exc:
        if row['state'] not in ('PROCESSING',) or row['owner']!=OWNER:
            update(row['verification_id'],state='UNKNOWN',phase='RPC_STATUS_UNKNOWN',error=str(exc))
    return row_by_id(row['verification_id'])


def public(row):
    result=json.loads(row['result_json']) if row.get('result_json') else None
    return dict(verification_id=row['verification_id'],case_id=row['case_id'],request_state=row['state'],phase=row['phase'],
                status_url='/api/v1/verification-requests/'+row['verification_id'],tx_hash=row['tx_hash'],
                result=result if row['state'] in ('CONFIRMED','FAILED') else None,error=row['error'])


def request_status(ident,core):
    row=row_by_id(ident)
    if row['namespace']!=namespace(core):raise HTTPException(409,'Request belongs to a different local chain deployment')
    return public(recover(row,core))


def work(ident,inputs,core):
    CONTEXT.verification_id=ident
    try:
        result=core.process_v11_verification({**inputs,'verification_id':ident})
        persist_result(core,result)
        state='CONFIRMED' if result.get('verification_tx_hash') else 'FAILED'
        update(ident,state=state,phase='COMPLETED' if state=='CONFIRMED' else 'EXTRACTION_OR_DECISION_FAILED',
               result_json=json.dumps(result,ensure_ascii=False),tx_hash=result.get('verification_tx_hash'),error=None)
    except Exception as exc:
        row=row_by_id(ident)
        # Before stage_result there is no chain submission. Once staged, an RPC
        # error can hide a successful submission; keep UNKNOWN and reconcile.
        staged=bool(row.get('result_json'))
        update(ident,state='UNKNOWN' if staged else 'FAILED',phase='STATUS_UNKNOWN' if staged else 'FAILED_BEFORE_SUBMISSION',error=str(getattr(exc,'detail',exc)))
        if staged:recover(row_by_id(ident),core)
    finally:
        CONTEXT.verification_id=None


def create_request(inputs,core,background=None):
    key,ns=fingerprint(inputs,core)
    created=False
    with connection() as db:
        db.execute('BEGIN IMMEDIATE')
        row=db.execute('SELECT * FROM verification_requests WHERE input_key=?',(key,)).fetchone()
        if row is None:
            ident='VERIFY-'+str(uuid4())
            db.execute('INSERT INTO verification_requests VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                       (key,ident,ns,inputs['claim']['case_id'],'PROCESSING','VALIDATING_AND_COMPARING',OWNER,None,None,None,time.time()))
            created=True
        else:
            ident=row['verification_id']
            # Explicit retry is safe only when failure happened before staging.
            if row['state']=='FAILED' and not row['result_json'] and not row['tx_hash']:
                db.execute("UPDATE verification_requests SET state='PROCESSING',phase='VALIDATING_AND_COMPARING',owner=?,error=NULL,updated_at=? WHERE input_key=?",(OWNER,time.time(),key))
                created=True
        db.commit()
    if created:
        if background is not None:background.add_task(work,ident,deepcopy(inputs),core)
        else:work(ident,inputs,core)
    return request_status(ident,core)


def sync_result(job,core):
    if job['request_state'] in ('CONFIRMED','FAILED') and job['result'] is not None:
        return core.v11_success(job['result'])
    if job['request_state']=='FAILED':raise HTTPException(503,job['error'] or 'Verification failed')
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=202,content=core.v11_success(job))


def case_requests(case_id,core):
    ns=namespace(core)
    with connection() as db:
        ids=[r[0] for r in db.execute('SELECT verification_id FROM verification_requests WHERE namespace=? AND case_id=? ORDER BY updated_at',(ns,case_id))]
    return [request_status(i,core) for i in ids]


def integrity_data(ident,core):
    result=deepcopy(core.V11_VERIFICATION_RESULTS.get(ident))
    if not result:raise HTTPException(404,'Verification not found')
    core.require_chain()
    case=core.cases_db[result['case_id']]
    claim=next((deepcopy(c) for c in case.get('v11_claims',[]) if c['claim_id']==result['claim_ref']['claim_id'] and c['claim_version']==result['claim_ref']['claim_version']),None)
    if not claim:raise HTTPException(409,'Original Claim is unavailable')
    proofs=[]
    for ref in result['proof_refs']:
        d=core.PROOF_DRAFTS.get((result['case_id'],ref['proof_id'],ref['proof_version']))
        if not d:raise HTTPException(409,'Original Proof is unavailable')
        proofs.append(dict(content=deepcopy(d['proof_content']),source_text=d['source_bytes'].decode('utf-8'),stored_proof_hash=d['proof_hash']))
    cid=core.case_uint(result['case_id']);step=result['step_id']
    claims=[core.contract.functions.getClaimRecord(cid,step,i).call() for i in range(core.contract.functions.getClaimHistoryLength(cid,step).call())]
    agencies=[core.contract.functions.getAgencyProofRecord(cid,step,i).call() for i in range(core.contract.functions.getAgencyProofHistoryLength(cid,step).call())]
    verifs=[core.contract.functions.getVerificationRecord(cid,step,i).call() for i in range(core.contract.functions.getVerificationHistoryLength(cid,step).call())]
    def hash_id(value):return hashlib.sha256(value.encode()).digest()
    c=next((r for r in claims if bytes(r[0])==hash_id(claim['claim_id']) and r[1]==claim['claim_version']),None)
    v=next((r for r in verifs if bytes(r[0])==hash_id(ident)),None)
    p=[]
    for proof in proofs:
        content=proof['content']
        record=next((r for r in agencies if bytes(r[0])==hash_id(content['proof_id']) and r[1]==content['proof_version'] and r[3].lower()==content['agency_address'].lower()),None)
        p.append(dict(proof_id=content['proof_id'],proof_version=content['proof_version'],proof_hash=core.Web3.to_hex(record[2]) if record else None))
    return dict(claim=claim,proofs=proofs,verification=result,policy=deepcopy(core.POLICY),chain_id=core.w3.eth.chain_id,contract_address=core.contract.address,
                onchain=dict(claim_hash=core.Web3.to_hex(c[2]) if c else None,proofs=p,
                             verification=dict(verification_id_hash=core.Web3.to_hex(v[0]),claim_id_hash=core.Web3.to_hex(v[1]),claim_version=v[2],claim_hash=core.Web3.to_hex(v[3]),proof_refs_hash=core.Web3.to_hex(v[4]),policy_hash=core.Web3.to_hex(v[5]),verification_hash=core.Web3.to_hex(v[7]),verdict={1:'SUPPORTED',2:'CONTRADICTED',3:'INSUFFICIENT'}.get(v[8])) if v else None))
