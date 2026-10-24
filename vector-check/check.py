"""Offline Mock vector check. Does not sign or contact a blockchain."""
import json
import sys
from pathlib import Path
from hashlib import sha256
from datetime import datetime

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / '.vector-test-deps'))
import rfc8785
from eth_account.messages import encode_typed_data
from eth_utils import keccak

v = json.loads((ROOT / 'vector.json').read_text(encoding='utf-8'))
p, m = v['proof_content'], v['message']
h = lambda b: '0x' + sha256(b).hexdigest()
proof_hash = h(rfc8785.dumps(p))
signable = encode_typed_data(full_message={k:v[k] for k in ('types', 'primaryType', 'domain', 'message')})
digest = '0x' + keccak(b'\x19' + signable.version + signable.header + signable.body).hex()
checks = dict(proof_hash=proof_hash == m['proofHash'], digest=digest == v['expected_digest'],
              case_id=str(int.from_bytes(sha256(p['case_id'].encode()).digest(), 'big')) == m['caseId'],
              proof_id=h(p['proof_id'].encode()) == m['proofIdHash'],
              proof_version=str(p['proof_version']) == m['proofVersion'],
              occurred_at=str(int(datetime.fromisoformat(p['proof_occurred_at']).timestamp())) == m['occurredAt'],
              issued_at=str(int(datetime.fromisoformat(p['proof_issued_at']).timestamp())) == m['issuedAt'])
result = dict(proof_hash=proof_hash, digest=digest, checks=checks)
(ROOT / 'python-result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
print(json.dumps(result, indent=2))
assert all(checks.values()), checks
