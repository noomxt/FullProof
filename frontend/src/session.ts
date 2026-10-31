import {createContext} from 'react';
import type {Role,System} from './api';
export const Session=createContext<{role:Role;system:System|null}>({role:'OFFICER',system:null});
