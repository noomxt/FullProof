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
    suite=unittest.defaultTestLoader.discover(str(root), pattern='test*.py')
    result=unittest.TextTestRunner(verbosity=1).run(suite)
finally:
    faulthandler.cancel_dump_traceback_later()
raise SystemExit(0 if result.wasSuccessful() else 1)
