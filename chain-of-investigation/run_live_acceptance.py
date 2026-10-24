"""Explicit live Gemini acceptance using synthetic text, no blockchain writes.

Usage: python run_live_acceptance.py --env-file PATH --output PATH
Never writes keys, provider error bodies, or real investigation records.
"""
import argparse
import json
from pathlib import Path

CASES = [
    ('connected', '2026년 10월 18일 오후 2시에 P001과 통화 연결에 성공했다.',
     [('PHONE_CALL', 'SUCCESS', 'P001', '2026-10-18T05:00:00Z')]),
    ('failed', '2026년 10월 18일 오후 2시에 P001에게 전화를 걸었으나 연결에 실패했다.',
     [('PHONE_CALL', 'FAIL', 'P001', '2026-10-18T05:00:00Z')]),
    ('attempt', '2026년 10월 18일 오후 2시에 P001에게 전화를 걸었다.',
     [('PHONE_CALL', 'UNKNOWN', 'P001', '2026-10-18T05:00:00Z')]),
    ('plan', '내일 P001에게 전화할 예정이다.', []),
    ('missing', '전화 연결에 성공했다.', [('PHONE_CALL', 'SUCCESS', None, None)]),
    ('cctv_request', '2026년 10월 18일 오후 2시에 P001 관련 CCTV 영상 제공 요청을 완료했다.',
     [('CCTV_REQUEST', 'SUCCESS', 'P001', '2026-10-18T05:00:00Z')]),
    ('cctv_review', '2026년 10월 18일 오후 2시에 P001 관련 CCTV 영상을 열람 완료했다.',
     [('CCTV_REVIEW', 'SUCCESS', 'P001', '2026-10-18T05:00:00Z')]),
    ('location_request', '2026년 10월 18일 오후 2시에 P001 위치정보 조회 요청을 완료했다.',
     [('LOCATION_REQUEST', 'SUCCESS', 'P001', '2026-10-18T05:00:00Z')]),
    ('multiple', '2026년 10월 18일 오후 2시에 P001과 통화 연결에 성공했다. 2026년 10월 18일 오후 3시에 P002와 통화 연결에 실패했다.',
     [('PHONE_CALL', 'SUCCESS', 'P001', '2026-10-18T05:00:00Z'),
      ('PHONE_CALL', 'FAIL', 'P002', '2026-10-18T06:00:00Z')]),
    ('relative', '어제 오후 2시에 P001과 통화 연결에 성공했다.',
     [('PHONE_CALL', 'SUCCESS', 'P001', None)]),
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--env-file', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--limit', type=int, default=len(CASES))
    parser.add_argument('--resume', action='store_true')
    args = parser.parse_args()
    from dotenv import load_dotenv
    load_dotenv(args.env_file)
    from verification_v11 import extract_v11
    rows = []
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    if args.resume and output.exists():
        rows = json.loads(output.read_text(encoding='utf-8'))['cases']
    for name, text, expected in CASES[:args.limit]:
        if any(r['case'] == name and r['passed'] for r in rows):
            continue
        claim = dict(schema_version='1.1', claim_id='LIVE-' + name, claim_version=1, claim_text=text)
        result = extract_v11(claim)
        actual = [(a['action_type'], a['action_result'], a['target_id'], a['occurred_at'])
                  for a in result['actions']]
        review = len(expected) != 1 or any(None in a or a[1] == 'UNKNOWN' for a in expected)
        passed = actual == expected and result['extraction_status'] != 'FAILED' and result['review_required'] == review
        rows = [r for r in rows if r['case'] != name]
        rows.append(dict(case=name, passed=passed, expected=expected, result=result))
        output.write_text(json.dumps(dict(mock_input=True, passed=sum(r['passed'] for r in rows),
            total=len(rows), cases=rows), ensure_ascii=False, indent=2), encoding='utf-8')
        print(name, 'PASS' if passed else 'FAIL', result['extraction_status'], flush=True)
        # Configuration/service failures cannot be repaired by inventing a pass.
        if result['extraction_status'] == 'FAILED':
            break
    return 0 if len(rows) == min(args.limit, len(CASES)) and all(r['passed'] for r in rows) else 1


if __name__ == '__main__':
    raise SystemExit(main())
