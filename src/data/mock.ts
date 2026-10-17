import type { Case, Claim } from '../types';
export const cases:Case[]=[
{id:'FP-2026-001',title:'해솔역 인근 실종 신고',region:'안산',status:'진행 중',openedAt:'2026-10-08',summary:'가상의 성인 A에 대한 실종 신고. 주변 영상 자료 요청과 열람 기록을 교차 확인합니다.'},
{id:'FP-2026-002',title:'푸른공원 이동 경로 확인',region:'수원',status:'진행 중',openedAt:'2026-10-07',summary:'가상의 성인 B에 대한 실종 신고. 기관 제공 기록의 장소와 시간을 대조합니다.'},
{id:'FP-2026-003',title:'별빛터미널 주변 확인',region:'성남',status:'진행 중',openedAt:'2026-10-06',summary:'가상의 성인 C에 대한 실종 신고. 독립적인 기관 증빙이 도착하지 않은 상황입니다.'},
{id:'FP-2026-004',title:'달빛거리 소재 확인',region:'안산',status:'종결',openedAt:'2026-10-05',summary:'가상의 성인 D에 대한 소재 확인 완료 사건. 자료 제공 단계만 확인할 수 있습니다.'}];
export const claims:Claim[]=[
{id:'CL-001',caseId:'FP-2026-001',text:'2026년 10월 8일 10시 해솔역 2번 출구 CCTV 자료를 가상 안산관제센터에 요청하였으며 접수가 완료되었다.',type:'CCTV 자료',stage:'요청',location:'해솔역 2번 출구',time:'2026-10-08T10:00:00+09:00',target:'가상 성인 A',result:'요청 접수 완료',proof:{id:'PR-001',agency:'가상 안산관제센터',source:'시연용 요청 접수 로그',stage:'요청',location:'해솔역 2번 출구',time:'2026-10-08T10:00:00+09:00',caseId:'FP-2026-001'}},
{id:'CL-002',caseId:'FP-2026-001',text:'2026년 10월 8일 14시 해솔역 2번 출구 CCTV 영상을 열람하여 이동 경로를 확인하였다.',type:'CCTV 자료',stage:'열람',location:'해솔역 2번 출구',time:'2026-10-08T14:00:00+09:00',target:'가상 성인 A',result:'영상 열람 완료',proof:{id:'PR-002',agency:'가상 안산관제센터',source:'시연용 자료 전달 로그 (열람 로그 없음)',stage:'제공',location:'해솔역 2번 출구',time:'2026-10-08T14:00:00+09:00',caseId:'FP-2026-001'}},
{id:'CL-003',caseId:'FP-2026-002',text:'2026년 10월 7일 11시 푸른공원 북문 CCTV 자료를 제공받았다.',type:'CCTV 자료',stage:'제공',location:'푸른공원 북문',time:'2026-10-07T11:00:00+09:00',target:'가상 성인 B',result:'자료 수신 완료',proof:{id:'PR-003',agency:'가상 수원관제센터',source:'시연용 자료 제공 로그',stage:'제공',location:'푸른공원 남문',time:'2026-10-07T13:00:00+09:00',caseId:'FP-2026-002'}},
{id:'CL-004',caseId:'FP-2026-003',text:'2026년 10월 6일 16시 별빛터미널 CCTV 자료 요청을 접수하였다.',type:'CCTV 자료',stage:'요청',location:'별빛터미널',time:'2026-10-06T16:00:00+09:00',target:'가상 성인 C',result:'요청 접수 완료',proof:null},
{id:'CL-005',caseId:'FP-2026-004',text:'2026년 10월 5일 9시 달빛거리 CCTV 자료를 제공받았다.',type:'CCTV 자료',stage:'제공',location:'달빛거리',time:'2026-10-05T09:00:00+09:00',target:'가상 성인 D',result:'자료 수신 완료',proof:{id:'PR-005',agency:'가상 안산관제센터',source:'시연용 자료 제공 로그',stage:'제공',location:'달빛거리',time:'2026-10-05T09:00:00+09:00',caseId:'FP-2026-004'}}];
