import {caseCatalog} from './caseCatalog';
/** Known fixture titles only; source data, IDs and signed payloads never change. */
export const caseTitle=(title:string)=>{
 const names=['정상 일치','결과 불일치','증빙 부족','연결 불명확','연결 근거 부족'];
 const index=names.findIndex(name=>title==='실종 사건 · '+name||title==='가상 실종 사건 · '+name);
 return index<0?title.replace(/^가상 실종 사건 · /,'실종 사건 · '):caseCatalog[Math.min(index,3)].title;
};
export function caseReference(id:string){const entry=caseCatalog.find(c=>id.startsWith('FP-'+c.id+'-'));return entry?entry.number+' · '+id.slice(('FP-'+entry.id+'-').length):id}
