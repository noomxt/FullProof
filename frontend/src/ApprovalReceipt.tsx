import {ShieldCheck,Stamp} from 'lucide-react';
import type {Review} from './api';
import {fmt,short} from './api';

/** Only a newly saved, confirmed ACCEPTED record may trigger the seal. */
export function isConfirmedApproval(review:Review|undefined,verificationId:string,mock:boolean){
 return !!review&&review.verification_id===verificationId&&review.review_status==='ACCEPTED'&&
  (mock?review.chain_status==='MOCK':review.chain_status==='CONFIRMED'&&!!review.review_tx_hash);
}
export default function ApprovalReceipt({review,mock}:{review:Review;mock:boolean}){
 return <section className="approval-receipt" role="status" aria-label={mock?'가상 승인 기록 완료':'관리자 승인 기록 확인 완료'}>
  <div className="approval-document"><span className="eyebrow">ADMINISTRATOR REVIEW</span><h3>{mock?'단계 완료 승인 · 로컬':'단계 완료 승인'}</h3><p>검토 대상 {short(review.verification_id)}</p><p>{fmt(review.reviewed_at)}</p><span className="approval-rule"/><p>{review.reason_text}</p></div>
  <div className="seal-stage" aria-hidden="true"><div className="stamp-tool"><Stamp size={43}/></div><div className="approval-imprint"><ShieldCheck size={28}/><strong>{mock?'로컬 승인':'승인 확인'}</strong><small>FULLPROOF</small></div></div>
  <p className="approval-footnote">{mock?'로컬 기록 · 전자서명·온체인 저장 없음':'서버에서 해당 검증의 승인 거래 기록을 확인했습니다.'}</p>
 </section>
}
