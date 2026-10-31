import {it,expect} from 'vitest';
import {latestVerifications,entryTab,roleTabs} from '../src/roles';
import type {Case,Verification} from '../src/api';
it('counts only current recorded results even when a case is closed',()=>{
 const v=(id:string,verdict:string|null,freshness_status:string,chain_status:string)=>({verification_id:id,verdict,freshness_status,chain_status}) as Verification;
 const cases=[{status:'CLOSED',verifications:[v('supported','SUPPORTED','CURRENT','CONFIRMED'),v('old','SUPPORTED','NEEDS_REVERIFICATION','CONFIRMED'),v('pending',null,'CURRENT','PENDING'),v('failed','SUPPORTED','CURRENT','FAILED')]},{status:'OPEN',verifications:[v('mock','INSUFFICIENT','CURRENT','MOCK')]}] as Case[];
 expect(latestVerifications(cases).map(v=>v.verification_id)).toEqual(['supported','mock']);
});
it('provides independent entry tasks for agency and administrator',()=>{expect(entryTab('AGENCY')).toBe('proofs');expect(entryTab('ADMIN')).toBe('verification');expect(entryTab('OFFICER')).toBe('overview')});
it('excludes officer claim and verdict screens from agency task navigation',()=>{expect(roleTabs.AGENCY.some(t=>(t[0] as string)==='records'||(t[0] as string)==='verification')).toBe(false);expect(roleTabs.OFFICER.some(t=>(t[0] as string)==='admin')).toBe(false)});
