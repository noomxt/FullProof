"""Explicit fixed responses for wiring checks. No model or AI inference here.

The team's parser, comparison, decision and policy code still run unchanged.
Only the SDK response is replaced, for the four advertised synthetic inputs.
"""
import json
import os
from pathlib import Path
from types import SimpleNamespace

SCENARIOS = json.loads((Path(__file__).parent / 'demo-scenarios.json').read_text(encoding='utf-8'))


class FixtureClient:
    def __init__(self, raw, proof):
        if not any(s['raw_claim_text'] == raw and s['proof'] == proof for s in SCENARIOS):
            raise ValueError('FIXTURE_INPUT_NOT_SUPPORTED: choose an unchanged demo scenario')
        self.raw, self.proof = raw, proof
        self.chat = SimpleNamespace(completions=SimpleNamespace(parse=self.parse))

    def parse(self, *, messages, response_format, **kwargs):
        if response_format.__name__ == 'ClaimExtraction':
            cctv = self.raw == SCENARIOS[3]['raw_claim_text']
            data = {'actions': [{'action_type':'CCTV_CHECK' if cctv else 'PHONE_CALL',
                'target_id':'CCTV001' if cctv else 'P001', 'claimed_time':'2026-10-10 14:00:00',
                'status_claim':'SUCCESS' if cctv else 'FAIL', 'source_text':self.raw}], 'review_reasons':[]}
        elif response_format.__name__ == 'SemanticExtraction':
            cctv = self.raw == SCENARIOS[3]['raw_claim_text']
            data = {'findings':[{'claim_excerpt':self.raw, 'proof_excerpt':self.proof['proof_text'],
                'relation':'UNCLEAR' if cctv else 'SUPPORTS',
                'reason_code':'VIEW_LOG_MISSING' if cctv else 'DEMO_PHONE_ATTEMPT',
                'reason_text':'고정 시연 응답: 제공 기록만으로 열람을 확인할 수 없습니다.' if cctv else '고정 시연 응답: 전화 시도와 연결 실패 기록이 대응합니다.'}]}
        else:
            raise ValueError('FIXTURE_SCHEMA_NOT_SUPPORTED')
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
            parsed=response_format.model_validate(data), refusal=None))])


def analysis_options(raw, proof):
    provider = os.getenv('AI_PROVIDER', 'gemini')
    if provider == 'fixture':
        if os.getenv('LOCAL_DEMO') != '1':
            raise ValueError('FIXTURE_REQUIRES_LOCAL_DEMO')
        return {'client': FixtureClient(raw, proof)}
    if provider != 'gemini':
        raise ValueError('UNKNOWN_AI_PROVIDER')
    return {}


def execution_metadata():
    fixture = os.getenv('AI_PROVIDER', 'gemini') == 'fixture'
    return {'provider':'fixture' if fixture else 'gemini', 'is_simulated':fixture,
            'label':'고정 응답 시연 · AI 호출 없음' if fixture else 'Gemini API 호출'}
