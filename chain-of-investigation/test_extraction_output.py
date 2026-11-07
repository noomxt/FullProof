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
        self.assertEqual(result['actions'], [dict(self.action,
            occurred_date='2026-10-18', occurred_time='14:00:00')])
        self.assertEqual(result['extraction_status'], 'COMPLETED')
        self.assertEqual(result['model_name'], 'request-model')
        self.assertEqual(result['prompt_version'], PROMPT_VERSION)
        self.assertEqual(claim, original)

    def test_missing_values_not_invented(self):
        self.action.update(occurred_at=None, target_id=None, action_result='UNKNOWN')
        result = extract_v11(dict(claim_id='CL1', claim_version=1, claim_text=self.text), client=self.client())
        self.assertEqual(result['actions'], [dict(self.action,
            occurred_date=None, occurred_time=None)])
        self.assertTrue(result['review_required'])
        self.assertEqual(result['extraction_status'], 'NEEDS_REVIEW')

    def test_utc_previous_day_round_trip(self):
        self.action['occurred_at'] = '2026-10-17T15:30:00Z'
        payload = ClaimExtractionV11.model_validate(self.payload)
        result = extract_v11(dict(claim_id='CL1', claim_version=1, claim_text=self.text),
                             client=self.client(payload=payload))
        self.assertEqual(result['actions'][0]['occurred_at'], '2026-10-17T15:30:00Z')
        self.assertEqual(result['actions'][0]['occurred_date'], '2026-10-18')
        self.assertEqual(result['actions'][0]['occurred_time'], '00:30:00')

    def test_date_only_survives_parser_and_v11_without_invented_time(self):
        text = '2024년 10월 10일 실종자와 통화에 성공했으며 안전을 확인했다.'
        payload = dict(actions=[dict(action_type='PHONE_CALL', action_result='SUCCESS',
            target_id=None, occurred_at=None, occurred_date='2024-10-10',
            occurred_time=None, source_excerpt=text)], review_reasons=[])
        parsed = parse_claim_with_llm(text, client=self.client(payload))
        self.assertEqual(parsed['actions'][0]['occurred_date'], '2024-10-10')
        self.assertIsNone(parsed['actions'][0]['claimed_time'])
        self.assertIn('occurred_time', parsed['actions'][0]['missing_fields'])
        self.assertNotIn('occurred_date', parsed['actions'][0]['missing_fields'])
        result = extract_v11(dict(claim_id='CL1', claim_version=1, claim_text=text),
                             client=self.client(payload))
        self.assertEqual(result['actions'], payload['actions'])
        self.assertEqual(result['extraction_status'], 'NEEDS_REVIEW')
        self.assertTrue(result['review_required'])

    def test_invalid_partial_fields_rejected(self):
        for field, value in [('occurred_date', '2024-02-30'),
                             ('occurred_date', '2024-2-01'),
                             ('occurred_time', '24:00:00'),
                             ('occurred_time', '9:00:00')]:
            with self.subTest(field=field, value=value), self.assertRaises(ValidationError):
                ClaimActionV11(**dict(self.action, **{field: value}))

    def test_inconsistent_full_and_partial_datetime_is_failed(self):
        for fields in [dict(occurred_date='2026-10-19'), dict(occurred_time='15:00:00')]:
            payload = dict(actions=[dict(self.action, **fields)], review_reasons=[])
            result = parse_claim_with_llm(self.text, client=self.client(payload))
            self.assertEqual(result['parse_status'], 'FAILED')
            self.assertEqual(result['actions'], [])

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

    def test_provider_service_failure_keeps_no_invented_actions(self):
        from ai_provider import error_code
        self.assertEqual(error_code(SimpleNamespace(status_code=503)), 'AI_SERVICE_UNAVAILABLE')

    def test_provider_reported_model_is_preserved(self):
        def parse(**kwargs):
            return SimpleNamespace(model='provider-resolved-model', choices=[SimpleNamespace(
                message=SimpleNamespace(parsed=self.payload, refusal=None))])
        client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(parse=parse)))
        result = parse_claim_with_llm(self.text, client=client)
        self.assertEqual(result['model_name'], 'provider-resolved-model')


if __name__ == '__main__':
    unittest.main()
