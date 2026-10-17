"""One local command: chain -> compile/deploy -> backend -> cases -> frontend.

Stops only child processes it created. Logs stay in .local-run (not in ZIP/Git).
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / 'team-backend'
CHILDREN = []
LOGS = []


def command(args, cwd=ROOT):
    subprocess.run([str(a) for a in args], cwd=cwd, check=True)


def start(args, cwd, name, env=None):
    log = (ROOT / '.local-run' / f'{name}.log').open('w',encoding='utf-8')
    LOGS.append(log)
    process = subprocess.Popen([str(a) for a in args], cwd=cwd, env=env, stdin=subprocess.PIPE,
        stdout=log, stderr=subprocess.STDOUT, start_new_session=os.name != 'nt')
    CHILDREN.append(process)
    return process


def request(url, body=None):
    data = None if body is None else json.dumps(body).encode()
    with urllib.request.urlopen(urllib.request.Request(url,data=data,headers={'Content-Type':'application/json'}), timeout=8) as response:
        return json.load(response)


def wait_for(probe, process, name):
    deadline = time.monotonic()+45
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f'{name} exited; see .local-run/{name}.log')
        try:
            probe()
            return
        except Exception:
            time.sleep(.4)
    raise RuntimeError(f'{name} did not become ready; see .local-run/{name}.log')


def settings():
    file = BACKEND / '.env'
    if not file.exists():
        shutil.copyfile(BACKEND / '.env.example', file)
    values = {}
    for line in file.read_text(encoding='utf-8').splitlines():
        if '=' in line and not line.lstrip().startswith('#'):
            key,value=line.split('=',1)
            values[key.strip()]=value.strip().strip('"\'')
    return values


def npm_setup(npm, directory):
    lock = directory / 'package-lock.json'
    marker = directory / 'node_modules' / '.fullproof-lock.sha256'
    digest = hashlib.sha256(lock.read_bytes()).hexdigest()
    if not marker.exists() or marker.read_text() != digest:
        command([npm,'ci','--no-audit','--no-fund'], directory)
        marker.write_text(digest)


def main():
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--live', action='store_true',help='Require Gemini key; never substitute fixed responses')
    mode.add_argument('--fixture', action='store_true',help='Explicit fixed responses; no AI request')
    parser.add_argument('--no-browser',action='store_true')
    args=parser.parse_args()
    os.chdir(ROOT)
    npm=shutil.which('npm.cmd' if os.name == 'nt' else 'npm')
    node=shutil.which('node')
    if not npm or not node:
        raise RuntimeError('Install Node.js 22.13+ (Node.js 24 recommended).')
    version=subprocess.check_output([node,'--version'],text=True).strip().lstrip('v').split('.')
    if int(version[0]) < 22 or (int(version[0]) == 22 and int(version[1]) < 13):
        raise RuntimeError('Hardhat requires Node.js 22.13+; install Node.js 24.')
    if sys.version_info < (3,10):
        raise RuntimeError('Python 3.10+ required (3.12 recommended).')
    for port in (5173,8000,8545):
        with socket.socket() as check:
            if check.connect_ex(('127.0.0.1',port)) == 0:
                raise RuntimeError(f'Port {port} is already in use. Stop the previous FullProof terminal with Ctrl+C first.')
    values=settings()
    live=bool(values.get('GEMINI_API_KEY')) and not args.fixture
    if args.live and not live:
        raise RuntimeError('No Gemini key. Run: py configure_ai.py')
    provider='gemini' if live else 'fixture'
    print(f'AI mode: {"LIVE GEMINI (API usage)" if live else "FIXED RESPONSES / NO AI CALL"}',flush=True)
    (ROOT / '.local-run').mkdir(exist_ok=True)
    python=BACKEND / '.venv' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    if not python.exists():
        command([sys.executable,'-m','venv',BACKEND / '.venv'])
    requirement=BACKEND/'requirements.txt'
    marker=BACKEND/'.venv/.fullproof-requirements.sha256'
    digest=hashlib.sha256(requirement.read_bytes()).hexdigest()
    if not marker.exists() or marker.read_text() != digest:
        command([python,'-m','pip','install','-r',requirement], BACKEND)
        marker.write_text(digest)
    npm_setup(npm, ROOT)
    npm_setup(npm, BACKEND)
    command([npm,'run','compile'],BACKEND)
    chain=start([npm,'run','node'],BACKEND,'chain')
    wait_for(lambda:request('http://127.0.0.1:8545',{'jsonrpc':'2.0','id':1,'method':'eth_chainId','params':[]}),chain,'chain')
    command([npm,'run','deploy:local'],BACKEND)
    env={**os.environ,'AI_PROVIDER':provider,'LOCAL_DEMO':'1','PYTHONUNBUFFERED':'1'}
    # Keep the team's existing DB separate from the local demo's case snapshot.
    env['CASE_DB_PATH']=str(BACKEND/'data/local-cases.db')
    env['AI_DB_PATH']=str(BACKEND/'data/local-ai.sqlite3')
    backend=start([python,'-m','uvicorn','main:app','--host','127.0.0.1','--port','8000'],BACKEND,'backend',env)
    wait_for(lambda:request('http://127.0.0.1:8000/api/v1/system/status'),backend,'backend')
    request('http://127.0.0.1:8000/api/v1/demo/bootstrap',{})
    frontend=start([npm,'run','dev','--','--host','127.0.0.1','--port','5173','--strictPort'],ROOT,'frontend')
    def frontend_probe():
        with urllib.request.urlopen('http://127.0.0.1:5173',timeout=3) as response:
            if response.status != 200: raise RuntimeError('Frontend not ready')
    wait_for(frontend_probe,frontend,'frontend')
    print('\nReady: http://127.0.0.1:5173/integration\nAPI: http://127.0.0.1:8000/docs\nCtrl+C stops these local servers. Logs: .local-run/',flush=True)
    if not args.no_browser:
        webbrowser.open('http://127.0.0.1:5173/integration')
    while True:
        for child in CHILDREN:
            if child.poll() is not None:
                raise RuntimeError('A service stopped. Check .local-run logs.')
        time.sleep(1)


def cleanup():
    for process in reversed(CHILDREN):
        if process.poll() is None:
            if os.name == 'nt':
                subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            else:
                try: os.killpg(process.pid,signal.SIGTERM)
                except ProcessLookupError: pass
            # Wait for the actual server to release its port before a new run.
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                if os.name != 'nt':
                    try: os.killpg(process.pid,signal.SIGKILL)
                    except ProcessLookupError: pass
                else:
                    process.kill()
                process.wait(timeout=5)
    for log in LOGS:
        log.close()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\nStopping FullProof local servers.')
    except Exception as exc:
        print(f'\nFullProof: {exc}',file=sys.stderr)
        sys.exit(1)
    finally:
        cleanup()
