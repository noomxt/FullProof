"""Opt-in real API + isolated Hardhat integration, no production data.

FULLPROOF_CHAIN_INTEGRATION=1 python -m unittest test_ai_backend_integration -v
RPC must be a disposable local chain (default port 18545). The contract is
deployed afresh and SQLite uses a temporary file. LLM output is injected unless
FULLPROOF_LIVE_AI=1; signatures, source hashes, RPC checks and anchoring are real.
"""
import json
import os
import tempfile
import unittest
from copy import deepcopy
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4


@unittest.skipUnless(os.getenv('FULLPROOF_CHAIN_INTEGRATION') == '1', 'opt-in disposable local chain required')
class BackendIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from web3 import Web3
        import database
        cls.temp = tempfile.TemporaryDirectory()
        cls.old_db = database.DB_PATH
        database.DB_PATH = Path(cls.temp.name) / 'integration.db'
        os.environ['RPC_URL'] = os.getenv('FULLPROOF_TEST_RPC_URL', 'http://127.0.0.1:18545')
        if not os.environ['RPC_URL'].startswith(('http://127.0.0.1:', 'http://localhost:')):
            raise RuntimeError('Only a disposable local RPC is allowed')
        import main
        cls.api = main
        cls.w3 = main.w3
        if not cls.w3.is_connected():
            raise RuntimeError('Start the isolated Hardhat node first')
        cls.admin, cls.recorder, cls.agency = cls.w3.eth.accounts[:3]
        artifact = json.loads((Path(__file__).parent / main.ABI_PATH).read_text(encoding='utf-8'))
        factory = cls.w3.eth.contract(abi=artifact['abi'], bytecode=artifact['bytecode'])
        receipt = cls.w3.eth.wait_for_transaction_receipt(factory.constructor().transact({'from':cls.admin}))
        cls.contract = cls.w3.eth.contract(address=receipt.contractAddress, abi=artifact['abi'])
        main.contract = cls.contract
        for tx in (cls.contract.functions.setVerificationRecorder(cls.recorder, True).transact({'from':cls.admin}),
                   cls.contract.functions.registerAgency(cls.agency, 2, cls.agency).transact({'from':cls.admin})):
            cls.w3.eth.wait_for_transaction_receipt(tx)
        os.environ['V11_MAPPING_REVIEWERS'] = cls.admin
        cls.results = []
        cls.extractions = []
        cls.executed_tests = []
        cls.failed_tests = []

    @classmethod
    def tearDownClass(cls):
        import database
        import gc
        database.DB_PATH = cls.old_db
        gc.collect()
        cls.temp.cleanup()
        report = Path(__file__).parent / 'acceptance' / (
            os.getenv('FULLPROOF_TEST_REPORT') or (
                'backend-chain-live.json' if os.getenv('FULLPROOF_LIVE_AI') == '1' else 'backend-chain-integration.json'))
        report.parent.mkdir(exist_ok=True)
        report.write_text(json.dumps(dict(chain_id=cls.w3.eth.chain_id, contract=cls.contract.address,
            live_ai=os.getenv('FULLPROOF_LIVE_AI') == '1', scenarios=cls.results,
            extractions=cls.extractions, executed_tests=cls.executed_tests,
            failed_tests=cls.failed_tests), indent=2), encoding='utf-8')

    def setUp(self):
        from fastapi.testclient import TestClient
        self.http = TestClient(self.api.app)
        self.executed_tests.append(self.id())
        self.case_id = 'AI-INTEGRATION-' + uuid4().hex[:12]
        self.claim_id = 'CLAIM-' + self.case_id
        self.post('/api/v1/cases', dict(case_id=self.case_id))
        self.post(f'/api/v1/cases/{self.case_id}/steps', dict(step_name='통화 확인'), 200)
        self.occurred = datetime.fromtimestamp(self.w3.eth.get_block('latest')['timestamp']-120, timezone.utc)
        self.utc = self.occurred.strftime('%Y-%m-%dT%H:%M:%SZ')
        self.local = self.occurred.astimezone(timezone(timedelta(hours=9)))

    def tearDown(self):
        self.http.close()
        result = self._outcome.result
        self.failed_tests[:] = sorted({t.id() for t, _ in result.failures + result.errors})

    def post(self, path, body, expected=201):
        response = self.http.post(path, json=body)
        self.assertEqual(response.status_code, expected, response.text)
        return response.json()

    def seed(self, result='CALL_CONNECTED', confirm=True, reference=True, with_proof=True, source_call_id=None):
        text = self.local.strftime('%Y년 %m월 %d일 %H시 %M분 %S초에 P001과 통화 연결에 성공했다.')
        if reference:
            text += ' CALL_REF[TELECOM-001:CALL-001]'
        claim = self.post(f'/api/v1/cases/{self.case_id}/claims', dict(claim_id=self.claim_id,
            claim_version=1, step_id=0, claim_text=text))
        if os.getenv('FULLPROOF_LIVE_AI') == '1':
            import ai_engine
            original_parse = ai_engine.parse_claim_with_llm
            def capture(*args, **kwargs):
                parsed = original_parse(*args, **kwargs)
                self.extractions.append(dict(case=self.case_id, status=parsed['parse_status'],
                    error_code=parsed.get('error_code'), model=parsed.get('model_name')))
                return parsed
            with patch('ai_engine.parse_claim_with_llm', side_effect=capture):
                extracted = self.post(f'/api/v1/claims/{self.claim_id}/extract', dict(case_id=self.case_id, claim_version=1), 200)
            self.assertEqual(extracted['data']['extraction_status'], 'COMPLETED', extracted)
        else:
            from ai_engine import _finalize, PROMPT_VERSION
            parsed = _finalize(text, dict(actions=[dict(action_type='PHONE_CALL', target_id='P001',
                claimed_time=self.local.strftime('%Y-%m-%d %H:%M:%S'), status_claim='SUCCESS', source_text=text)], review_reasons=[]))
            parsed.update(model_name='injected-integration-fixture', prompt_version=PROMPT_VERSION)
            with patch('ai_engine.parse_claim_with_llm', return_value=parsed):
                self.post(f'/api/v1/claims/{self.claim_id}/extract', dict(case_id=self.case_id, claim_version=1), 200)
        if not with_proof:
            return claim, []
        proof = dict(schema_version='1.1', proof_id='PROOF-001', proof_version=1, case_id=self.case_id,
            step_id=0, issuer_agency_id='TELECOM-001', agency_address=self.agency, proof_type='CALL_LOG',
            call_id='CALL-001', target_id='P001', action_type='PHONE_CALL', proof_occurred_at=self.utc,
            proof_issued_at=self.occurred.replace().strftime('%Y-%m-%dT%H:%M:%SZ'), result=result,
            source_sha256='0x'+'0'*64)
        now = self.w3.eth.get_block('latest')['timestamp']
        source = dict(proof)
        if source_call_id is not None:
            source['call_id'] = source_call_id
        draft = self.post('/api/v1/proofs/drafts', dict(proof_content=proof,
            source_text=json.dumps(source, ensure_ascii=False), nonce=self.contract.functions.agencyNonces(self.agency).call(),
            deadline=now+3600))['data']
        typed = deepcopy(draft['typed_data'])
        typed['types']['EIP712Domain'] = [dict(name=n, type=t) for n,t in (
            ('name','string'),('version','string'),('chainId','uint256'),('verifyingContract','address'))]
        signed = self.w3.provider.make_request('eth_signTypedData_v4', [self.agency, json.dumps(typed)])
        self.assertNotIn('error', signed)
        msg = typed['message']
        self.post('/api/v1/proofs/anchor', dict(case_id=self.case_id, step_id=0, proof_id='PROOF-001',
            proof_version=1, proof_hash=msg['proofHash'], occurred_at=int(msg['occurredAt']), issued_at=int(msg['issuedAt']),
            agency=self.agency, nonce=int(msg['nonce']), deadline=int(msg['deadline']), signature=signed['result']))
        mapping = self.post(f'/api/v1/claims/{self.claim_id}/proof-mappings', dict(case_id=self.case_id,
            step_id=0, claim_version=1, claim_text=text, proof_id='PROOF-001', proof_version=1,
            issuer_agency_id='TELECOM-001', call_id='CALL-001'))['data']
        if confirm:
            note = '기관 통화 원본과 원문에 명시된 통화 참조를 확인했습니다.'
            message = self.api.build_v11_mapping_confirmation_message(self.case_id, mapping, claim['claim_hash'],
                draft['proof_hash'], draft['source_sha256'], note)
            signed = self.w3.provider.make_request('eth_sign', [self.admin, self.w3.to_hex(text=message)])
            self.assertNotIn('error', signed)
            self.post(f"/api/v1/claims/{self.claim_id}/proof-mappings/{mapping['mapping_id']}/confirm", dict(
                case_id=self.case_id, claim_text=text, evidence_source_sha256=draft['source_sha256'],
                evidence_note=note, signer_address=self.admin, signature=signed['result']), 200)
        return claim, [draft['proof_content']]

    def verify(self, claim, proofs, expected):
        result = self.post('/api/v1/verifications', dict(claim={k:claim[k] for k in
            ('case_id','claim_id','claim_version')}, proofs=proofs))['data']
        self.assertEqual(result['verdict'], expected)
        self.assertTrue(result['verification_tx_hash'])
        receipt = self.w3.eth.get_transaction_receipt(result['verification_tx_hash'])
        self.assertEqual(receipt.status, 1)
        record = self.contract.functions.getLatestVerification(self.api.case_uint(self.case_id), 0).call()
        self.assertEqual(self.w3.to_hex(record[7]), result['verification_hash'])
        self.assertEqual(record[8], {'SUPPORTED':1,'CONTRADICTED':2,'INSUFFICIENT':3}[expected])
        self.results.append(dict(case=self.case_id, verdict=expected, verification_hash=result['verification_hash'],
            tx_hash=result['verification_tx_hash'], block_number=receipt.blockNumber))
        return result


    def test_persistence_after_process_restart(self):
        import subprocess
        import sys
        import database

        # ?? API? Claim, Proof, ??, Verification ??
        claim, proofs = self.seed()
        verification = self.verify(claim, proofs, "SUPPORTED")

        # ?? Python ?????? ?? SQLite DB ???
        script = """
import sys
import database

database.DB_PATH = sys.argv[1]

proofs = database.load_v11_store("proof_drafts")
mappings = database.load_v11_store("mapping_history")
verifications = database.load_v11_store("verification_results")

case_id, claim_id, verification_id = sys.argv[2:5]

assert (case_id, "PROOF-001", 1) in proofs
assert proofs[(case_id, "PROOF-001", 1)]["status"] == "ANCHORED"
assert proofs[(case_id, "PROOF-001", 1)]["source_bytes"]

assert (case_id, claim_id) in mappings
assert any(
    m["mapping_status"] == "CONFIRMED"
    for m in mappings[(case_id, claim_id)]
)

assert verification_id in verifications
assert verifications[verification_id]["verdict"] == "SUPPORTED"

print("API PERSISTENCE AND PROCESS RESTORE: PASS")
"""
        completed = subprocess.run(
            [
                sys.executable, "-c", script,
                str(database.DB_PATH),
                self.case_id,
                self.claim_id,
                verification["verification_id"]
            ],
            capture_output=True,
            text=True,
            check=True
        )
        print(completed.stdout)


    def test_restart_then_admin_approval_and_closure(self):
        import subprocess
        import sys
        import database
        import json

        claim, proofs = self.seed()
        verification = self.verify(claim, proofs, "SUPPORTED")

        payload = {
            "db_path": str(database.DB_PATH),
            "contract_address": self.contract.address,
            "case_id": self.case_id,
            "verification_id": verification["verification_id"],
            "review": self.signed_review(verification),
            "close": self.signed_close()
        }

        child_script = """
import json
import sys

payload = json.load(sys.stdin)

import database
database.DB_PATH = payload["db_path"]

import main
from fastapi.testclient import TestClient
from pathlib import Path

artifact = json.loads(
    (Path(main.__file__).parent / main.ABI_PATH).read_text(
        encoding="utf-8"
    )
)

main.contract = main.w3.eth.contract(
    address=payload["contract_address"],
    abi=artifact["abi"]
)

assert payload["case_id"] in main.cases_db
assert payload["verification_id"] in main.V11_VERIFICATION_RESULTS

case_id = payload["case_id"]
verification_id = payload["verification_id"]

with TestClient(main.app) as client:
    review = client.post(
        f"/api/v1/verifications/{verification_id}/reviews",
        json=payload["review"]
    )
    assert review.status_code == 200, (
        f"Review failed: {review.status_code} {review.text}"
    )

    closure = client.post(
        f"/api/v1/cases/{case_id}/close",
        json=payload["close"]
    )
    assert closure.status_code == 200, (
        f"Closure failed: {closure.status_code} {closure.text}"
    )

assert database.load_cases()[case_id]["is_closed"] is True

chain_case = main.contract.functions.cases(
    main.case_uint(case_id)
).call()
assert chain_case[1] == 1

print("RESTARTED FASTAPI REVIEW AND CLOSURE: PASS")
"""

        completed = subprocess.run(
            [sys.executable, "-c", child_script],
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            timeout=90
        )

        if completed.returncode != 0:
            self.fail(
                "Restart test failed:\\n"
                + completed.stdout + "\\n"
                + completed.stderr
            )

        print(completed.stdout)

    def test_supported(self):
        self.verify(*self.seed(), 'SUPPORTED')

    def test_contradicted(self):
        self.verify(*self.seed(result='CALL_FAILED'), 'CONTRADICTED')

    def test_insufficient_without_proof(self):
        self.verify(*self.seed(with_proof=False), 'INSUFFICIENT')

    def test_confirmed_without_explicit_link_remains_insufficient(self):
        self.verify(*self.seed(reference=False), 'INSUFFICIENT')

    def test_unconfirmed_mapping_remains_insufficient(self):
        self.verify(*self.seed(confirm=False), 'INSUFFICIENT')

    def test_source_identity_mismatch_remains_insufficient(self):
        self.verify(*self.seed(source_call_id='CALL-OTHER'), 'INSUFFICIENT')

    def test_confirmation_signature_tampering_remains_insufficient(self):
        claim, proofs = self.seed()
        self.api.V11_MAPPING_HISTORY[(self.case_id, self.claim_id)][0]['confirmation_evidence']['note'] += ' altered'
        self.verify(claim, proofs, 'INSUFFICIENT')

    def test_client_cannot_forge_extraction(self):
        claim, proofs = self.seed()
        claim['structured_claim'] = {'actions':[], 'extraction_status':'COMPLETED'}
        self.post('/api/v1/verifications', dict(claim=claim, proofs=proofs), 409)

    def test_source_tampering_rejected(self):
        claim, proofs = self.seed()
        self.api.PROOF_DRAFTS[(self.case_id, 'PROOF-001', 1)]['source_bytes'] += b'tamper'
        self.post('/api/v1/verifications', dict(claim={k:claim[k] for k in
            ('case_id','claim_id','claim_version')}, proofs=proofs), 409)

    def test_claim_and_extraction_saved_with_existing_case_storage(self):
        import database
        claim, _ = self.seed(with_proof=False)
        persisted = database.load_cases()[self.case_id]['v11_claims'][0]
        self.assertEqual(persisted['claim_text'], claim['claim_text'])
        self.assertEqual(persisted['claim_hash'], claim['claim_hash'])
        self.assertEqual(persisted['structured_claim']['extraction_status'], 'COMPLETED')

    def test_stale_claim_version_rejected(self):
        claim, proofs = self.seed()
        self.post(f'/api/v1/cases/{self.case_id}/claims', dict(claim_id=self.claim_id,
            claim_version=2, step_id=0, claim_text=claim['claim_text']+' 수정'))
        self.post('/api/v1/verifications', dict(claim={k:claim[k] for k in
            ('case_id','claim_id','claim_version')}, proofs=proofs), 409)

    def sign_local(self, signer, message):
        signed = self.w3.provider.make_request('eth_sign', [signer, self.w3.to_hex(text=message)])
        self.assertNotIn('error', signed)
        return signed['result']

    def signed_review(self, verification, status='ACCEPTED', signer=None):
        signer = signer or self.admin
        body = dict(review_status=status, reason_code=None, reason_text='통합 검증 확인',
                    signer_address=signer, signature='0x', nonce=uuid4().hex,
                    deadline=self.w3.eth.get_block('latest')['timestamp']+3600)
        message = self.api.build_v11_admin_review_message(verification['verification_id'],
            verification['verification_hash'], self.api.V11SignedReviewRequest(**body))
        body['signature'] = self.sign_local(signer, message)
        return body

    def signed_close(self, signer=None):
        signer = signer or self.admin
        body = dict(reason='필수 단계의 최신 판정과 관리자 승인 확인', signer_address=signer,
                    signature='0x', nonce=uuid4().hex,
                    deadline=self.w3.eth.get_block('latest')['timestamp']+3600)
        message = self.api.build_v11_close_message(self.case_id, self.api.V11SignedCloseCaseSchema(**body))
        body['signature'] = self.sign_local(signer, message)
        return body

    def test_admin_supported_approval_and_normal_closure(self):
        verification = self.verify(*self.seed(), 'SUPPORTED')
        # Supported alone must not close a case before administrator review.
        self.post(f'/api/v1/cases/{self.case_id}/close', self.signed_close(), 409)
        review_body = self.signed_review(verification)
        review = self.post(f"/api/v1/verifications/{verification['verification_id']}/reviews", review_body, 200)['data']
        receipt = self.w3.eth.get_transaction_receipt(review['review_tx_hash'])
        self.assertEqual(receipt.status, 1)
        self.assertTrue(self.contract.functions.isLatestVerificationApproved(self.api.case_uint(self.case_id), 0).call())
        self.post(f"/api/v1/verifications/{verification['verification_id']}/reviews", review_body, 409)
        close_body = self.signed_close()
        closed = self.post(f'/api/v1/cases/{self.case_id}/close', close_body, 200)
        self.assertEqual(closed['chain_status'], 'CONFIRMED')
        close_receipt = self.w3.eth.get_transaction_receipt(closed['tx_hash'])
        self.assertEqual(close_receipt.status, 1)
        chain_case = self.contract.functions.cases(self.api.case_uint(self.case_id)).call()
        self.assertEqual(chain_case[1], 1)
        self.assertTrue(self.api.cases_db[self.case_id]['is_closed'])
        self.post(f'/api/v1/cases/{self.case_id}/close', close_body, 409)
        self.results[-1].update(review_tx_hash=review['review_tx_hash'], close_tx_hash=closed['tx_hash'],
                                chain_status='CLOSED', close_block=close_receipt.blockNumber)

    def test_admin_cannot_accept_contradicted_or_close(self):
        verification = self.verify(*self.seed(result='CALL_FAILED'), 'CONTRADICTED')
        self.post(f"/api/v1/verifications/{verification['verification_id']}/reviews", self.signed_review(verification), 409)
        self.post(f"/api/v1/verifications/{verification['verification_id']}/reviews",
                  self.signed_review(verification, 'ACKNOWLEDGED'), 200)
        self.post(f'/api/v1/cases/{self.case_id}/close', self.signed_close(), 409)

    def test_admin_cannot_accept_insufficient_or_close(self):
        verification = self.verify(*self.seed(with_proof=False), 'INSUFFICIENT')
        self.post(f"/api/v1/verifications/{verification['verification_id']}/reviews", self.signed_review(verification), 409)
        self.post(f'/api/v1/cases/{self.case_id}/close', self.signed_close(), 409)

    def test_admin_invalid_signatures_rejected(self):
        verification = self.verify(*self.seed(), 'SUPPORTED')
        path = f"/api/v1/verifications/{verification['verification_id']}/reviews"
        self.post(path, self.signed_review(verification, signer=self.agency), 403)
        tampered = self.signed_review(verification); tampered['reason_text'] += '변조'
        self.post(path, tampered, 403)
        expired = self.signed_review(verification); expired['deadline'] = 1
        self.post(path, expired, 403)
        self.post(f'/api/v1/cases/{self.case_id}/close', self.signed_close(signer=self.agency), 403)
        tampered = self.signed_close(); tampered['reason'] += '변조'
        self.post(f'/api/v1/cases/{self.case_id}/close', tampered, 403)

    def test_admin_approval_does_not_cover_new_verification(self):
        claim, proofs = self.seed()
        first = self.verify(claim, proofs, 'SUPPORTED')
        self.post(f"/api/v1/verifications/{first['verification_id']}/reviews", self.signed_review(first), 200)
        self.verify(claim, proofs, 'SUPPORTED')
        self.assertFalse(self.contract.functions.isLatestVerificationApproved(self.api.case_uint(self.case_id), 0).call())
        self.post(f'/api/v1/cases/{self.case_id}/close', self.signed_close(), 409)


if __name__ == '__main__':
    unittest.main()
