"""Read-only browser integrity view; no signing, decisions or transactions."""
from copy import deepcopy
import hashlib
from fastapi import HTTPException
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
