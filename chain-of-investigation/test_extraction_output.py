"""Contract and legacy compatibility checks with an injected AI client."""
import unittest
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch

from pydantic import ValidationError
from ai_engine import ClaimActionV11, ClaimExtractionV11, PROMPT_VERSION, parse_claim_with_llm
from verification_v11 import extract_v11


class ExtractionOutputTests(unittest.TestCase):
    def setUp(self):
        self.text = '  2026년 10월 18일 오후 2시 P001 통화 성공.\n'
        self.action = dict(action_type='PHONE_CALL', action_result='SUCCESS',
                           target_id='P001', occurred_at='2026-10-18T05:00:00Z',
                           source_excerpt='P001 통화 성공.')
        self.payload = dict(actions=[self.action], review_reasons=[])
        self.calls = []

    def client(self, payload=None, refusal=None):
        def parse(**kwargs):
            self.calls.append(kwargs)
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
                parsed=self.payload if payload is None else payload, refusal=refusal))])
        return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(parse=parse)))

    def test_new_model_contract_keeps_old_caller_fields(self):
        with patch('ai_provider.model_name', side_effect=['actual-request-model', 'changed-model']):
            result = parse_claim_with_llm(self.text, client=self.client())
        self.assertIs(self.calls[0]['response_format'], ClaimExtractionV11)
        self.assertEqual(result['raw_text'], self.text)
        self.assertEqual(result['claimed_time'], '2026-10-18 14:00:00')
        self.assertEqual(result['status_claim'], 'SUCCESS')
        self.assertEqual(result['actions'][0]['source_text'], 'P001 통화 성공.')
        self.assertEqual(result['model_name'], self.calls[0]['model'])
        self.assertEqual(result['prompt_version'], PROMPT_VERSION)

    def test_v11_output_has_only_common_action_fields(self):
        claim = dict(claim_id='CL1', claim_version=2, claim_text=self.text)
        original = deepcopy(claim)
        with patch('ai_provider.model_name', return_value='request-model'):
            result = extract_v11(claim, client=self.client())
        self.assertEqual(result['actions'], [self.action])
        self.assertEqual(result['extraction_status'], 'COMPLETED')
        self.assertEqual(result['model_name'], 'request-model')
        self.assertEqual(result['prompt_version'], PROMPT_VERSION)
        self.assertEqual(claim, original)

    def test_missing_values_not_invented(self):
        self.action.update(occurred_at=None, target_id=None, action_result='UNKNOWN')
        result = extract_v11(dict(claim_id='CL1', claim_version=1, claim_text=self.text), client=self.client())
        self.assertEqual(result['actions'], [self.action])
        self.assertTrue(result['review_required'])
        self.assertEqual(result['extraction_status'], 'NEEDS_REVIEW')

    def test_utc_previous_day_round_trip(self):
        self.action['occurred_at'] = '2026-10-17T15:30:00Z'
        payload = ClaimExtractionV11.model_validate(self.payload)
        result = extract_v11(dict(claim_id='CL1', claim_version=1, claim_text=self.text),
                             client=self.client(payload=payload))
        self.assertEqual(result['actions'][0]['occurred_at'], '2026-10-17T15:30:00Z')

    def test_invalid_utc_rejected(self):
        for value in ('2026-10-18 14:00:00', '2026-10-18T14:00:00+09:00',
                      '2026-02-30T05:00:00Z', '2026-10-18T05:00:00.123Z'):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                ClaimActionV11(**dict(self.action, occurred_at=value))

    def test_ungrounded_excerpt_is_failed(self):
        self.action['source_excerpt'] = '없는 원문'
        result = parse_claim_with_llm(self.text, client=self.client())
        self.assertEqual(result['error_code'], 'AI_RESPONSE_INVALID')
        self.assertEqual(result['actions'], [])

    def test_refusal_keeps_attempt_metadata(self):
        with patch('ai_provider.model_name', return_value='request-model'):
            result = parse_claim_with_llm(self.text, client=self.client(refusal='refused'))
        self.assertEqual(result['parse_status'], 'FAILED')
        self.assertEqual(result['model_name'], 'request-model')
        self.assertEqual(result['prompt_version'], PROMPT_VERSION)


if __name__ == '__main__':
    unittest.main()
