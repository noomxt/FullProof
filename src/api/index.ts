import {mockApi} from './mock';import {httpApi} from './http';
export const isMock=import.meta.env.VITE_API_MODE!=='http';
export const api=isMock?mockApi:httpApi;
