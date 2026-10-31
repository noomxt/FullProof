/** Public display names are neutral. Scenario IDs remain internal backend fixture selectors. */
export const caseCatalog=[
 {id:'supported',number:'FP-001',title:'중앙공원 실종 신고',note:'중앙공원 일대 · 연락 경위 확인'},
 {id:'contradicted',number:'FP-002',title:'한빛역 실종 신고',note:'한빛역 일대 · 관계자 연락 확인'},
 {id:'insufficient',number:'FP-003',title:'호수마을 실종 신고',note:'호수마을 일대 · 통화 자료 확인'},
 {id:'ambiguous',number:'FP-004',title:'새봄거리 실종 신고',note:'새봄거리 일대 · 연락 기록 확인'}
] as const;
