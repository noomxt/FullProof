import {createElement as h} from 'react';
import {MemoryRouter,useLocation} from 'react-router-dom';
import {act,cleanup,fireEvent,render,screen} from '@testing-library/react';
import {afterEach,beforeEach,it,expect,vi} from 'vitest';
import Notifications from '../src/WorkNotifications';
import {api} from '../src/api';
import type {Case,System} from '../src/api';
vi.mock('../src/api',async original=>({...await original<typeof import('../src/api')>(),api:vi.fn()}));
const system={environment:'TEST',chain:{chain_id:31337,contract_address:'0xTEST'}} as System;
const fixture={case_id:'CASE-1',title:'중앙공원 실종 신고',proofs:[{proof_id:'P1',proof_version:1,step_id:2,chain_status:'CONFIRMED',proof_issued_at:'2026-10-18T05:00:00Z'}],reviews:[],verifications:[]} as unknown as Case;
const Location=()=>h('p',{'data-testid':'location'},useLocation().search);
function mount(){return render(h(MemoryRouter,null,h(Notifications,{role:'OFFICER',system,disabled:false}),h(Location)))}
beforeEach(()=>{localStorage.clear();vi.useFakeTimers();vi.mocked(api).mockReset()});
afterEach(()=>{cleanup();vi.useRealTimers()});
it('polls, marks a clicked event read, navigates to its step and preserves read state after remount',async()=>{
 vi.mocked(api).mockResolvedValue([]);const view=mount();await act(async()=>{});expect(screen.getByLabelText('알림 · 읽지 않음 0개')).toBeTruthy();
 vi.mocked(api).mockResolvedValue([fixture]);await act(async()=>{await vi.advanceTimersByTimeAsync(15000)});
 fireEvent.click(screen.getByLabelText('알림 · 읽지 않음 1개'));fireEvent.click(screen.getByRole('button',{name:/기관 증빙이 도착했습니다/}));
 expect(screen.getByTestId('location').textContent).toContain('step=2');expect(screen.getByLabelText('알림 · 읽지 않음 0개')).toBeTruthy();
 view.unmount();mount();await act(async()=>{});expect(screen.getByLabelText('알림 · 읽지 않음 0개')).toBeTruthy();fireEvent.click(screen.getByLabelText('알림 · 읽지 않음 0개'));expect(screen.getByRole('button',{name:/기관 증빙이 도착했습니다/})).toBeTruthy();
});
it('keeps unread records when polling fails and cancels polling on unmount',async()=>{
 vi.mocked(api).mockResolvedValue([]);const view=mount();await act(async()=>{});vi.mocked(api).mockResolvedValue([fixture]);await act(async()=>{await vi.advanceTimersByTimeAsync(15000)});vi.mocked(api).mockRejectedValue(Error('offline'));await act(async()=>{await vi.advanceTimersByTimeAsync(15000)});fireEvent.click(screen.getByLabelText('알림 · 읽지 않음 1개'));expect(screen.getByRole('status').textContent).toContain('기존 알림은 유지');expect(screen.getByRole('button',{name:/기관 증빙이 도착했습니다/})).toBeTruthy();view.unmount();expect(vi.getTimerCount()).toBe(0);
});
