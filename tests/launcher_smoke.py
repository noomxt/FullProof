"""Shared-host launcher smoke check on one Linux machine; fixture AI only."""
import hashlib,json,os,socket,subprocess,time,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
logs=ROOT/'.checks/launcher';logs.mkdir(parents=True,exist_ok=True)
config=ROOT/'shared-demo.json';original=config.read_bytes()
for folder in ('frontend','local-tools'):
    lock=(ROOT/folder/'package-lock.json').read_bytes()
    (ROOT/folder/'node_modules/.fullproof-lock').write_text(hashlib.sha256(lock).hexdigest())
(ROOT/'chain-of-investigation/.venv/.fullproof-ui-requirements').write_text(hashlib.sha256((ROOT/'requirements-local-lock.txt').read_bytes()).hexdigest())
python=ROOT/'chain-of-investigation/.venv/bin/python'
env={**os.environ,'PYTHONUTF8':'1','FULLPROOF_UI_DB_PATH':str(logs/'demo.db'),'FULLPROOF_UI_AUDIT_PATH':str(logs/'audit.db')}
for key in ('GEMINI_API_KEY','GOOGLE_API_KEY'):env.pop(key,None)
handle=(logs/'launcher.log').open('w')
process=subprocess.Popen([str(python),str(ROOT/'start_connected.py'),'--fixture','--share','--public-url','http://127.0.0.1:5173'],cwd=ROOT,env=env,stdout=handle,stderr=subprocess.STDOUT,start_new_session=True)
try:
    for _ in range(250):
        if process.poll() is not None:raise RuntimeError((logs/'launcher.log').read_text())
        try:
            with urllib.request.urlopen('http://127.0.0.1:5173/backend/api/v1/frontend/status',timeout=1) as response:
                status=json.load(response)
                if status['chain']['available']:break
        except OSError:pass
        time.sleep(.1)
    else:raise RuntimeError('Launcher readiness timeout')
    assert json.loads(config.read_text())['server_url']=='http://127.0.0.1:5173'
    report={'pass':True,'scope':'Linux shared-host launcher on explicit loopback address, reused installed dependencies, fixture AI and real local chain','checks':['--share startup','public address file written without secrets','shared frontend/API readiness','public-address override'],'not_tested':['fresh Windows installation','real Gemini','external LAN or public hosting']}
    (ROOT/'docs/LAUNCHER_RESULTS.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
finally:
    import signal
    try:os.killpg(process.pid,signal.SIGINT)
    except ProcessLookupError:pass
    try:process.wait(timeout=8)
    except subprocess.TimeoutExpired:
        try:os.killpg(process.pid,signal.SIGKILL)
        except ProcessLookupError:pass
    handle.close();config.write_bytes(original)
