import tempfile
import faulthandler
from pathlib import Path
import unittest
root=Path(__file__).resolve().parent
scratch=root/'test-tmp'
scratch.mkdir(exist_ok=True)
tempfile.tempdir=str(scratch)
faulthandler.enable()
# Includes TestClient's event-loop startup, which HTTP timeouts cannot bound.
faulthandler.dump_traceback_later(45, exit=True)
try:
    # The backend also contains executable test_*.py demos which write to a
    # chain at import time. Do not import them through unittest discovery.
    suite=unittest.defaultTestLoader.loadTestsFromNames([
        'test_ai', 'test_action_types', 'test_extraction_output',
        'test_verification_v11', 'test_v11_contract', 'test_conflict_sort',
        'test_ai_backend_integration', 'test_mentor_integration',
    ])
    result=unittest.TextTestRunner(verbosity=1).run(suite)
finally:
    faulthandler.cancel_dump_traceback_later()
raise SystemExit(0 if result.wasSuccessful() else 1)
