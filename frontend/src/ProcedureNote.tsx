import type {ReactNode} from 'react';
export default function ProcedureNote({title,children}:{title:string;children:ReactNode}){return <div className="procedure-note" role="note"><strong>{title}</strong><p>{children}</p></div>}
