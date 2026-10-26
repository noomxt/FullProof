import unittest

from fastapi.testclient import TestClient


class LegacyRecoverProofTests(unittest.TestCase):
    def test_legacy_recover_proof_is_disabled(self):
        import main

        with TestClient(main.app) as client:
            response = client.post(
                "/api/v1/cases/TEST-001/steps/0/recover-proof",
                json={"tx_hash": "0x" + "0" * 64},
            )

        self.assertEqual(response.status_code, 410)
        self.assertEqual(
            response.json()["detail"],
            "Legacy Proof recovery disabled in v1.1",
        )


if __name__ == "__main__":
    unittest.main()
