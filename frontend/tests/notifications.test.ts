import {it,expect} from 'vitest';
import {notificationEvents,mergeNotifications} from '../src/notificationEvents';
import type {Case,Proof,Review,Verification} from '../src/api';
const c=(patch:Partial<Case>={}):Case=>({case_id:'CASE-1',title:'중앙공원 실종 신고',proofs:[],reviews:[],verifications:[],...patch}) as Case;
const proof=(status='CONFIRMED',version=1)=>({proof_id:'P1',proof_version:version,step_id:2,chain_status:status,proof_issued_at:'2026-10-18T05:00:00Z'}) as Proof;
const review=(status='REVISION_REQUESTED')=>({review_id:'R1',review_status:status,chain_status:'CONFIRMED',step_id:2,reviewed_at:'2026-10-18T05:01:00Z'}) as Review;
it('baselines past events without creating notifications',()=>{const events=notificationEvents([c({proofs:[proof()]})],'OFFICER');expect(mergeNotifications(null,events)).toEqual({known:[events[0].id],items:[]})});
it('notifies only confirmed proof records, not pending, failed or simulated records',()=>{expect(notificationEvents([c({proofs:['PENDING','FAILED','MOCK','UNKNOWN'].map(x=>proof(x))})],'OFFICER')).toEqual([]);expect(notificationEvents([c({proofs:[proof()]})],'OFFICER')).toHaveLength(1)});
it('deduplicates refreshes, preserves read state and notifies a new proof version',()=>{
 let s=mergeNotifications(null,[]);const events=notificationEvents([c({proofs:[proof()]})],'OFFICER');s=mergeNotifications(s,events);expect(s.items).toHaveLength(1);s.items[0].read=true;s=mergeNotifications(s,events);expect(s.items[0].read).toBe(true);s=mergeNotifications(s,notificationEvents([c({proofs:[proof('CONFIRMED',2)]})],'OFFICER'));expect(s.items).toHaveLength(2);
});
it('keeps previous history across a temporarily empty response',()=>{let s=mergeNotifications(mergeNotifications(null,[]),notificationEvents([c({proofs:[proof()]})],'OFFICER'));s=mergeNotifications(s,[]);expect(s.items).toHaveLength(1);expect(mergeNotifications(s,notificationEvents([c({proofs:[proof()]})],'OFFICER')).items).toHaveLength(1)});
it('links reviews to the correct case history and step without a write action',()=>{const e=notificationEvents([c({reviews:[review()]})],'OFFICER')[0];expect(e.title).toContain('보완 요청');expect(e.href).toContain('tab=history');expect(e.href).toContain('step=2');expect(e.href).toContain('notice=');expect(notificationEvents([c({reviews:[{...review(),chain_status:'SUBMITTED'}]})],'OFFICER')).toEqual([])});
it('does not invent an agency request and names admin events as verification records',()=>{
 const v={verification_id:'V1',step_id:1,chain_status:'CONFIRMED',freshness_status:'CURRENT',created_at:null} as Verification;
 const source=c({proofs:[proof()],verifications:[v]});expect(notificationEvents([source],'AGENCY')).toEqual([]);const e=notificationEvents([source],'ADMIN');expect(e).toHaveLength(1);expect(e[0].title).toBe('새 검증 기록을 확인해 주세요');expect(e[0].href).toContain('tab=verification');expect(notificationEvents([c({verifications:[{...v,freshness_status:'NEEDS_REVERIFICATION'}]})],'ADMIN')).toEqual([]);
});
it('isolates identical record IDs in different cases',()=>{const events=notificationEvents([c({proofs:[proof()]}),c({case_id:'CASE-2',proofs:[proof()]})],'OFFICER');expect(new Set(events.map(e=>e.id)).size).toBe(2)});
