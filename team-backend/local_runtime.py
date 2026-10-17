"""Readiness and explicit, local-only synthetic case setup.

No private keys or wallet signing are exposed by these routes.
"""
import json
import os
from pathlib import Path
from threading import Lock
from fastapi import HTTPException
from fastapi.responses import RedirectResponse
from demo_provider import SCENARIOS, execution_metadata
from database import save_case


def register_runtime_routes(app, ctx):
    bootstrap_lock = Lock()
    root = Path(__file__).parent

    def local_config():
        file = root / 'local-demo.json'
        try:
            data = json.loads(file.read_text(encoding='utf-8'))
            if ctx['contract'] and data['contract_address'].lower() == ctx['contract'].address.lower():
                return data
        except (OSError, ValueError, KeyError):
            pass
        return None

    @app.get('/', include_in_schema=False)
    def home():
        return RedirectResponse('/docs')

    @app.get('/api/v1/system/status')
    def system_status():
        chain = {'ready':False, 'chain_id':None, 'block_number':None,
                 'contract_address':ctx['CONTRACT_ADDRESS'] or None}
        try:
            ctx['require_chain']()
            chain.update(ready=True, chain_id=ctx['w3'].eth.chain_id,
                         block_number=ctx['w3'].eth.block_number)
        except Exception:
            pass
        execution = execution_metadata()
        return {'service':'FullProof', 'environment':'LOCAL_DEMO' if os.getenv('LOCAL_DEMO') == '1' else 'TEAM_API',
                'execution':execution, 'ai_ready':(os.getenv('LOCAL_DEMO') == '1') if execution['is_simulated'] else bool(os.getenv('GEMINI_API_KEY','').strip()),
                'gemini_key_configured':bool(os.getenv('GEMINI_API_KEY','').strip()),
                'model':os.getenv('GEMINI_MODEL') or 'gemini-3.8-flash',
                'chain':chain, 'local_demo':local_config(), 'case_count':len(ctx['cases_db'])}

    @app.get('/api/v1/demo/scenarios')
    def scenarios():
        return {'is_demo':True, 'scenarios':SCENARIOS}

    @app.get('/api/v1/blockchain/agencies/{address}')
    def agency_state(address: str):
        ctx['require_chain']()
        try:
            address = ctx['Web3'].to_checksum_address(address)
            if not ctx['contract'].functions.isAuthorizedAgency(address).call():
                raise HTTPException(404, '기관 주소가 체인에 등록되지 않았습니다.')
            info = ctx['contract'].functions.agencies(address).call()
            return {'agency':address, 'signer':info[2],
                    'nonce':str(ctx['contract'].functions.agencyNonces(address).call()),
                    'chain_id':ctx['w3'].eth.chain_id, 'active':info[1]}
        except (ValueError, TypeError):
            raise HTTPException(422, '유효한 기관 지갑 주소가 필요합니다.')

    @app.post('/api/v1/demo/bootstrap')
    def bootstrap():
        ctx['require_chain']()
        if os.getenv('LOCAL_DEMO') != '1' or ctx['w3'].eth.chain_id != 31337:
            raise HTTPException(403, '시연 사건 등록은 LOCAL_DEMO=1, 로컬 체인 31337에서만 가능합니다.')
        # Reconcile only the four fixed demo IDs from the actual chain. This
        # also repairs stale demo SQLite snapshots after restarting Hardhat.
        with bootstrap_lock:
            for scenario in SCENARIOS:
                cid = ctx['case_uint'](scenario['case_id'])
                onchain = ctx['contract'].functions.cases(cid).call()
                if not onchain[3]:
                    ctx['confirmed'](ctx['contract'].functions.createCase(cid).transact({'from':ctx['sender']()}))
                onchain = ctx['contract'].functions.cases(cid).call()
                if onchain[1] != 0:
                    raise HTTPException(409, '시연 사건이 이미 종료되었습니다. 새 로컬 체인으로 시작해 주세요.')
                for spec in ctx['DEMO_POLICY']['steps'][onchain[2]:]:
                    ctx['confirmed'](ctx['contract'].functions.addStep(cid, spec['step_name'], spec['required']).transact({'from':ctx['sender']()}))
                steps = []
                for spec in ctx['DEMO_POLICY']['steps']:
                    values = ctx['contract'].functions.caseSteps(cid, spec['step_id']).call()
                    if values[0] != spec['step_name']:
                        raise HTTPException(409, '시연 정책과 기존 체인 단계명이 다릅니다.')
                    steps.append({'step_id':spec['step_id'], 'step_name':values[0], 'is_required':values[1],
                        'status':ctx['STATUS_REVERSE'][values[2]], 'claim_hash':ctx['Web3'].to_hex(values[3]),
                        'proof_hash':ctx['Web3'].to_hex(values[4]), 'is_completed':values[5]})
                record = {'case_id':scenario['case_id'], 'title':scenario['title'], 'is_closed':False,
                          'close_reason':'', 'step_count':len(steps), 'steps':steps, 'is_demo':True}
                save_case(record)
                ctx['cases_db'][scenario['case_id']] = record
        return {'seeded':len(SCENARIOS), 'is_demo':True, 'chain_id':31337}
