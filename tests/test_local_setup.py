"""Key wizard checks use a dummy value, never a real credential."""
import contextlib
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SPEC=importlib.util.spec_from_file_location('configure_ai',Path(__file__).resolve().parents[1]/'configure_ai.py')
configure=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(configure)

class KeySetupTests(unittest.TestCase):
    def test_key_stays_backend_only_without_echo(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);backend=root/'team-backend';backend.mkdir()
            file=backend/'.env';file.write_text('RPC_URL=http://127.0.0.1:8545\nCONTRACT_ADDRESS=0xexample\nGEMINI_API_KEY=\n')
            output=io.StringIO()
            with patch.object(configure,'ROOT',root),patch.object(configure,'getpass',return_value='TEST_ONLY_DUMMY'),patch('builtins.input',return_value='team-model'),contextlib.redirect_stdout(output):
                configure.main()
            self.assertIn('GEMINI_API_KEY=TEST_ONLY_DUMMY',file.read_text())
            self.assertIn('CONTRACT_ADDRESS=0xexample',file.read_text())
            self.assertIn('AI_PROVIDER=gemini',file.read_text())
            self.assertNotIn('TEST_ONLY_DUMMY',output.getvalue())
            self.assertEqual(list(root.glob('src/**/*')),[])

    def test_invalid_key_keeps_existing_settings(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);backend=root/'team-backend';backend.mkdir()
            file=backend/'.env';file.write_text('GEMINI_API_KEY=old-local-value\n')
            original=file.read_bytes()
            with patch.object(configure,'ROOT',root),patch.object(configure,'getpass',return_value=' '):
                with self.assertRaises(SystemExit):configure.main()
            self.assertEqual(file.read_bytes(),original)

if __name__=='__main__':unittest.main()
