"""Start the official local backend + frontend. Gemini mode is explicit.
Never resets an existing chain/database and never writes private keys.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
ROOT=Path(__file__).resolve().parent
CHAIN=ROOT/'chain-of-investigation'
TOOLS=ROOT/'local-tools'
FRONT=ROOT/'frontend'


def busy(port):
    with socket.socket() as s:
        return s.connect_ex(('127.0.0.1',port))==0


def install_npm(folder,npm):
    lock=folder/'package-lock.json'
    marker=folder/'node_modules/.fullproof-lock'
    expected=hashlib.sha256(lock.read_bytes()).hexdigest()
    if not marker.exists() or marker.read_text()!=expected:
        subprocess.run([npm,'ci'],cwd=folder,check=True)
        marker.write_text(expected)


def main():
    p=argparse.ArgumentParser()
    m=p.add_mutually_exclusive_group(required=True)
    m.add_argument('--fixture',action='store_true',help='Fixed AI extraction only; real local chain and wallet signatures')
    m.add_argument('--live',action='store_true',help='Actual Gemini API; put your key only in backend .env')
    a=p.parse_args()
    npm=shutil.which('npm.cmd' if os.name=='nt' else 'npm');node=shutil.which('node')
    if not npm or not node:raise SystemExit('Install Node.js 22.13+ first.')
    if busy(8000) or busy(5173):raise SystemExit('Port 8000 or 5173 is already used. Stop the old FullProof process first.')
    logs=ROOT/'.local-run';logs.mkdir(exist_ok=True)
    children=[];handles=[]
    def spawn(args,cwd,name,env=None):
        handle=(logs/(name+'.log')).open('w',encoding='utf-8');handles.append(handle)
        proc=subprocess.Popen(args,cwd=cwd,stdout=handle,stderr=subprocess.STDOUT,env=env);children.append(proc);return proc
    try:
        install_npm(TOOLS,npm);install_npm(FRONT,npm)
        python=CHAIN/('.venv/Scripts/python.exe' if os.name=='nt' else '.venv/bin/python')
        if not python.exists():subprocess.run([sys.executable,'-m','venv',str(CHAIN/'.venv')],check=True)
        marker=CHAIN/'.venv/.fullproof-ui-requirements'
        requirements=ROOT/'requirements-local-lock.txt'
        h=hashlib.sha256(requirements.read_bytes()).hexdigest()
        if not marker.exists() or marker.read_text()!=h:
            subprocess.run([str(python),'-m','pip','install','-r',str(requirements)],check=True);marker.write_text(h)
        if not busy(8545):
            child=spawn([node,'node_modules/hardhat/dist/src/cli.js','node','--hostname','127.0.0.1'],TOOLS,'chain')
            for _ in range(200):
                if busy(8545):break
                if child.poll() is not None:raise RuntimeError('chain exited; see .local-run/chain.log')
                time.sleep(.1)
            else:raise RuntimeError('Local chain startup timeout')
        subprocess.run([node,'scripts/compile-local.mjs'],cwd=TOOLS,check=True)
        subprocess.run([node,'scripts/deploy-local.mjs'],cwd=TOOLS,check=True)
        env={**os.environ,'FULLPROOF_UI_AI_MODE':'live' if a.live else 'fixture','PYTHONUTF8':'1'}
        child=spawn([str(python),'-m','uvicorn','frontend_server:app','--host','127.0.0.1','--port','8000'],CHAIN,'backend',env)
        for _ in range(200):
            try:
                with urllib.request.urlopen('http://127.0.0.1:8000/api/v1/frontend/status',timeout=2) as r:
                    if json.load(r)['chain']['available']:break
            except Exception:pass
            if child.poll() is not None:raise RuntimeError('backend exited; see .local-run/backend.log')
            time.sleep(.15)
        else:raise RuntimeError('Backend readiness timeout; see .local-run/backend.log')
        spawn([node,'node_modules/vite/bin/vite.js','--host','127.0.0.1','--open'],FRONT,'frontend',{**os.environ,'VITE_SERVICE_MODE':'api'})
        print('Open http://127.0.0.1:5173 ; select TEAM API in demo settings if browser remembers Mock.',flush=True)
        print('AI: '+('LIVE GEMINI' if a.live else 'FIXED EXTRACTION (no Gemini request)')+' | real local chain | MetaMask required',flush=True)
        while True:
            for child in children:
                if child.poll() is not None:raise RuntimeError('A process exited; inspect .local-run logs.')
            time.sleep(.5)
    except KeyboardInterrupt:pass
    finally:
        for child in reversed(children):
            if child.poll() is None:child.terminate()
        for child in children:
            try:child.wait(timeout=5)
            except subprocess.TimeoutExpired:child.kill()
        for h in handles:h.close()
if __name__=='__main__':main()
