"""Reproducible local integration checks; no Gemini key is read or used.

py test_connected.py --browser
Install browser once: npx.cmd playwright install chromium
"""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import urllib.request
from contextlib import contextmanager

ROOT = Path(__file__).resolve().parent


@contextmanager
def services():
    (ROOT/'.local-run').mkdir(exist_ok=True)
    with (ROOT/'.local-run/integration-launcher.log').open('w',encoding='utf-8') as log:
        process=subprocess.Popen([sys.executable,'-u',str(ROOT/'start_fullproof.py'),'--fixture','--no-browser'],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,
            start_new_session=os.name!='nt')
        try:
            deadline=time.monotonic()+240
            while time.monotonic()<deadline:
                if process.poll() is not None:
                    raise RuntimeError((ROOT/'.local-run/integration-launcher.log').read_text(encoding='utf-8'))
                try:
                    if 'Ready: http://127.0.0.1:5173/integration' not in (ROOT/'.local-run/integration-launcher.log').read_text(encoding='utf-8'):
                        time.sleep(.5)
                        continue
                    with urllib.request.urlopen('http://127.0.0.1:5173/integration',timeout=2) as response:
                        if response.status==200: break
                except Exception:
                    time.sleep(.5)
            else:
                raise RuntimeError('Launcher timed out. See .local-run/integration-launcher.log')
            yield
        finally:
            if process.poll() is None:
                if os.name=='nt':
                    subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                else:
                    process.send_signal(signal.SIGINT)
                    try: process.wait(timeout=15)
                    except subprocess.TimeoutExpired: os.killpg(process.pid,signal.SIGKILL)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--browser',action='store_true')
    args=parser.parse_args()
    with services():
        subprocess.run(['node','scripts/integration-test.mjs'],cwd=ROOT/'team-backend',check=True)
        if args.browser:
            subprocess.run(['node','tests/browser-smoke.mjs'],cwd=ROOT,check=True)
    with services():
        subprocess.run(['node','scripts/integration-test.mjs','--verify-stale'],cwd=ROOT/'team-backend',check=True)
    evidence=ROOT/'docs/LOCAL_TEST_EVIDENCE.json'
    data=json.loads(evidence.read_text())
    data['restart_check']='PASS: previous local-chain confirmations become STALE_CHAIN after reset'
    data['browser_check']='PASS: injected browser wallet adapter; real MetaMask extension not tested' if args.browser else 'NOT_RUN'
    evidence.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    print('PASS: connected checks completed; all owned services stopped.')


if __name__=='__main__':
    main()
