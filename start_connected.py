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
    p.add_argument('--share',action='store_true',help='Trusted LAN demo host; Gemini key remains on this computer')
    p.add_argument('--public-url',help='Host URL reachable by demo clients, e.g. http://192.168.0.10:5173')
    a=p.parse_args()
    if a.public_url and not a.share:raise SystemExit('--public-url requires --share')
    public_url=None
    if a.share:
        from urllib.parse import urlparse
        if a.public_url:
            parsed=urlparse(a.public_url)
            if parsed.scheme not in ('http','https') or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ('','/'):
                raise SystemExit('Use only a full http(s) host URL without credentials or paths.')
            public_url=a.public_url.rstrip('/')
        else:
            try:
                with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as route:
                    route.connect(('192.0.2.1',80));address=route.getsockname()[0]
            except OSError:raise SystemExit('Could not detect LAN IP. Pass --public-url http://YOUR-LAN-IP:5173')
            if address.startswith('127.'):raise SystemExit('No LAN IP detected. Pass --public-url.')
            public_url=f'http://{address}:5173'
        (ROOT/'shared-demo.json').write_text(json.dumps({'schema_version':'1.1','server_url':public_url,'note':'Public connection address only. No API key or private keys. Host must stay running; trusted LAN demo.'},ensure_ascii=False,indent=2),encoding='utf-8')
    npm=shutil.which('npm.cmd' if os.name=='nt' else 'npm');node=shutil.which('node')
    if not npm or not node:raise SystemExit('Install Node.js 22.13+ first.')
    if busy(8000) or busy(5173):raise SystemExit('Port 8000 or 5173 is already used. Stop the old FullProof process first.')
    logs=ROOT/'.local-run';logs.mkdir(exist_ok=True)
    children=[];handles=[]
    def spawn(args,cwd,name,env=None):
        handle=(logs/(name+'.log')).open('w',encoding='utf-8');handles.append(handle)
        proc=subprocess.Popen(args,cwd=cwd,stdout=handle,stderr=subprocess.STDOUT,env=env);children.append(proc);return proc
    try:
        print('Preparing FullProof: dependencies, local chain, backend, frontend...',flush=True)
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
        frontend_host='0.0.0.0' if a.share else '127.0.0.1'
        if public_url:
            from urllib.parse import urlparse
            if urlparse(public_url).hostname in ('127.0.0.1','localhost','::1'):frontend_host='127.0.0.1'
        front_child=spawn([node,'node_modules/vite/bin/vite.js','--host',frontend_host,'--open'],FRONT,'frontend',{**os.environ,'VITE_SERVICE_MODE':'api'})
        for _ in range(200):
            try:
                with urllib.request.urlopen('http://127.0.0.1:5173/backend/api/v1/frontend/status',timeout=2) as response:
                    if json.load(response)['chain']['available']:break
            except Exception:pass
            if front_child.poll() is not None:raise RuntimeError('frontend exited; see .local-run/frontend.log')
            time.sleep(.15)
        else:raise RuntimeError('Frontend readiness timeout; see .local-run/frontend.log')
        print('Open http://127.0.0.1:5173 ; official API connection is automatic.',flush=True)
        if a.share:
            print('Shared demo host: '+public_url,flush=True)
            print('Clients: package this folder with py package_project.py, then run py start_shared_client.py on the other computer. No Gemini key on clients.',flush=True)
            print('Trusted LAN test only. Keep this host running. Do not publicly expose the unauthenticated demo API.',flush=True)
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
