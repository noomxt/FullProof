"""Offline schema/adapter regression checks; no claim about live model accuracy."""
import unittest
from copy import deepcopy
from unittest.mock import patch

from pydantic import ValidationError
from ai_engine import ClaimAction, _finalize
from verification_v11 import extract_v11


class ActionTypeTests(unittest.TestCase):
    def action(self, kind, text):
        return dict(action_type=kind, target_id='P001',
                    claimed_time='2026-10-18 14:00:00',
                    status_claim='SUCCESS', source_text=text)

    def test_common_types_survive_extraction_adapter(self):
        for kind, text in (
            ('PHONE_CALL', 'P001과 통화 성공'),
            ('CCTV_REQUEST', 'P001 CCTV 영상 제공 요청 완료'),
            ('CCTV_REVIEW', 'P001 CCTV 영상 열람 완료'),
            ('LOCATION_REQUEST', 'P001 위치정보 조회 요청 완료'),
        ):
            with self.subTest(kind=kind):
                claim = dict(claim_id='CL1', claim_version=1, claim_text=text)
                original = deepcopy(claim)
                parsed = _finalize(text, dict(actions=[self.action(kind, text)], review_reasons=[]))
                with patch('ai_engine.parse_claim_with_llm', return_value=parsed):
                    result = extract_v11(claim)
                self.assertEqual(result['extraction_status'], 'COMPLETED')
                self.assertEqual(result['actions'][0]['action_type'], kind)
                self.assertEqual(result['actions'][0]['source_excerpt'], text)
                self.assertNotIn('call_id', result['actions'][0])
                self.assertEqual(claim, original)

    def test_legacy_types_rejected_by_schema(self):
        for kind in ('CCTV_CHECK', 'LOCATION_TRACE'):
            with self.subTest(kind=kind), self.assertRaises(ValidationError):
                ClaimAction(**self.action(kind, 'P001 기록'))

    def test_request_and_review_require_separate_claims(self):
        request, review = 'P001 CCTV 제공 요청 완료.', 'P001 CCTV 열람 완료.'
        parsed = _finalize(request + review, dict(actions=[
            self.action('CCTV_REQUEST', request), self.action('CCTV_REVIEW', review)
        ], review_reasons=[]))
        self.assertEqual(parsed['parse_status'], 'NEEDS_REVIEW')
        self.assertEqual([a['action_type'] for a in parsed['actions']],
                         ['CCTV_REQUEST', 'CCTV_REVIEW'])

    def test_unclassifiable_action_requires_review(self):
        parsed = _finalize('P001 기록', dict(actions=[
            self.action('UNKNOWN', 'P001 기록')], review_reasons=[]))
        self.assertEqual(parsed['parse_status'], 'NEEDS_REVIEW')


if __name__ == '__main__':
    unittest.main()
