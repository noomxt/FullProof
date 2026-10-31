import {it,expect} from 'vitest';
import {caseCatalog} from '../src/caseCatalog';
import {caseReference,caseTitle} from '../src/presentation';
it('provides stable neutral names without exposing verdicts in titles',()=>{expect(caseCatalog.map(c=>c.number)).toEqual(['FP-001','FP-002','FP-003','FP-004']);for(const c of caseCatalog)expect(c.title+' '+c.note).not.toMatch(/SUPPORTED|CONTRADICTED|INSUFFICIENT|정상 일치|결과 불일치|증빙 부족/)});
it('formats known fixture IDs without modifying raw IDs or arbitrary titles',()=>{const id='FP-contradicted-abcd1234';expect(caseReference(id)).toBe('FP-002 · abcd1234');expect(id).toBe('FP-contradicted-abcd1234');expect(caseTitle('가상 실종 사건 · 정상 일치')).toBe('중앙공원 실종 신고');expect(caseTitle('사용자가 정한 사건명')).toBe('사용자가 정한 사건명')});
