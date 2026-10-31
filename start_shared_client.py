"""Keyless client: frontend + proxy to an already running shared demo host.
No Gemini key, backend installation, deployment or database on the client.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import urllib.error
import urllib.request
from urllib.parse import urlparse
from start_connected import busy,install_npm
ROOT=Path(__file__).resolve().parent

def validate_server(value):
    parsed=urlparse(value)
    if parsed.scheme not in ('http','https') or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ('','/') or parsed.hostname in ('0.0.0.0','::'):
        raise ValueError('Use a full http(s) host URL without credentials, query or path.')
    return value.rstrip('/')

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--server',help='Reachable shared host URL; otherwise read shared-demo.json')
    parser.add_argument('--port',type=int,default=5173)
    args=parser.parse_args()
    target=args.server
    if not target:
        try:target=json.loads((ROOT/'shared-demo.json').read_text(encoding='utf-8'))['server_url']
        except (OSError,ValueError,KeyError):target=None
    if not target:raise SystemExit('Shared server is not configured yet. Ask the host for its shared-demo.json or run: py start_shared_client.py --server http://HOST-LAN-IP:5173')
    try:target=validate_server(target)
    except ValueError as exc:raise SystemExit(str(exc))
    if not 1024<=args.port<=65535:raise SystemExit('Use a port between 1024 and 65535.')
    if busy(args.port):raise SystemExit(f'Port {args.port} is already in use. Stop the old client or pass --port 5174.')
    print('Checking shared host: '+target,flush=True)
    try:
        with urllib.request.urlopen(target+'/backend/api/v1/frontend/status',timeout=10) as response:
            status=json.load(response)
            status=status.get('data',status)
            if not status.get('chain',{}).get('available'):raise ValueError('Host chain is not ready.')
    except (OSError,ValueError) as exc:raise SystemExit('Shared host unavailable. Keep the host running and check LAN/firewall/server address. '+str(exc))
    node=shutil.which('node');npm=shutil.which('npm.cmd' if os.name=='nt' else 'npm')
    if not node or not npm:raise SystemExit('Install Node.js 22.13+ first.')
    install_npm(ROOT/'frontend',npm)
    env={**os.environ,'VITE_SERVICE_MODE':'api','VITE_BACKEND_TARGET':target+'/backend','VITE_RPC_TARGET':target+'/rpc'}
    print(f'Open http://127.0.0.1:{args.port} — shared API; no Gemini key on this computer.',flush=True)
    print('Use TEAM API mode. MetaMask and the registered synthetic test accounts are still required for signatures.',flush=True)
    try:subprocess.run([node,'node_modules/vite/bin/vite.js','--host','127.0.0.1','--port',str(args.port),'--open'],cwd=ROOT/'frontend',env=env,check=True)
    except KeyboardInterrupt:pass
    except subprocess.CalledProcessError as exc:raise SystemExit(exc.returncode)
if __name__=='__main__':main()
