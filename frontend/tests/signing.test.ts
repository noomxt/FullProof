import {it,expect} from 'vitest';
import golden from './fixtures/official-signatures.json';
import {mappingMessage,reviewMessage,closeMessage,canonical,utf8Hex} from '../src/signing';
it('matches exact official Python RFC8785 review bytes including Korean/newline/quote/null',()=>expect(reviewMessage(golden.chain_id,golden.contract,'V1','0x'+'1'.repeat(64),golden.data)).toBe(golden.review_expected));
it('matches exact official Python closure bytes',()=>expect(closeMessage(golden.chain_id,golden.contract,'C1',golden.close)).toBe(golden.close_expected));
it('matches exact official newline mapping message including nonce',()=>expect(mappingMessage('C1',golden.mapping,'0x'+'1'.repeat(64),'0x'+'2'.repeat(64),'0x'+'3'.repeat(64),'원본 통화 ID 확인 · 가상 자료')).toBe(golden.mapping_expected));
it('encodes personal_sign as UTF-8 bytes',()=>expect(utf8Hex('가')).toBe('0xeab080'));
it('rejects invalid unicode and unsafe integers rather than signing different bytes',()=>{expect(()=>canonical('\ud800')).toThrow();expect(()=>canonical(9007199254740992)).toThrow()});
