import type {ReactNode} from 'react';
import {Notice} from './ui';
export function TechnicalDetails({children,title='무결성·기술 상세'}:{children:ReactNode;title?:string}){return <details className="technical-details"><summary>{title}</summary><div className="technical-body">{children}</div></details>}
export function errorSummary(message:string){
 if(/Case does not exist/i.test(message))return '현재 연결된 체인에서 사건을 찾지 못했습니다. 서버와 체인 상태를 확인해 주세요.';
 if(/4001|서명을 취소|User rejected/i.test(message))return '지갑 서명이 취소됐습니다. 기록 상태를 확인한 뒤 다시 진행할 수 있습니다.';
 if(/연결|CONNECTION|fetch|프록시/i.test(message))return '서버에 연결하지 못했거나 응답을 확인할 수 없습니다. 연결 상태를 확인해 주세요.';
 if(/timeout|시간 초과|불명확/i.test(message))return '처리 결과를 아직 확인하지 못했습니다. 다시 제출하기 전에 기존 기록 상태를 확인해 주세요.';
 if(/계정|MetaMask|지갑|network|chain/i.test(message))return '서명 지갑과 연결 네트워크를 확인해 주세요.';
 return '작업을 완료하지 못했습니다. 기존 기록과 입력 조건을 확인해 주세요.';
}
export function OperationError({message}:{message:string}){return <Notice error><p>{errorSummary(message)}</p><TechnicalDetails title="오류 상세"><pre className="json-view">{message}</pre></TechnicalDetails></Notice>}
