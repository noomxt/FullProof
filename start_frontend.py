"""Frontend-only demo: no Python packages, Gemini key, backend or wallet needed."""
from pathlib import Path
import hashlib
import os
import shutil
import subprocess
import sys
ROOT=Path(__file__).resolve().parent/'frontend'

def main():
    npm=shutil.which('npm.cmd' if os.name=='nt' else 'npm')
    node=shutil.which('node')
    if not npm or not node:raise SystemExit('Install Node.js 22.13+ first.')
    marker=ROOT/'node_modules/.fullproof-lock'
    h=hashlib.sha256((ROOT/'package-lock.json').read_bytes()).hexdigest()
    if not marker.exists() or marker.read_text()!=h:
        subprocess.run([npm,'ci'],cwd=ROOT,check=True)
        marker.write_text(h)
    env={**os.environ,'VITE_SERVICE_MODE':'mock'}
    print('FRONTEND MOCK: no AI / wallet / blockchain calls. http://127.0.0.1:5173',flush=True)
    try:subprocess.run([node,'node_modules/vite/bin/vite.js','--host','127.0.0.1','--port','5173','--strictPort','--open'],cwd=ROOT,env=env,check=True)
    except KeyboardInterrupt:pass
if __name__=='__main__':main()
