"""Create a source-only ZIP. Runtime secrets, dependencies and data are excluded."""
from pathlib import Path
import zipfile
ROOT=Path(__file__).resolve().parent
output=ROOT.parent/'FullProof_v1.1_Final_Mentor_Theme.zip'
exclude={'node_modules','.venv','dist','__pycache__','.git','.local-run','artifacts','cache','test-tmp','.checks'}
files=[]
for p in ROOT.rglob('*'):
    rel=p.relative_to(ROOT)
    if not p.is_file() or p.is_symlink() or any(part in exclude for part in rel.parts):continue
    if p.name.startswith('.env') and p.name!='.env.example':continue
    if p.suffix in {'.db','.pyc','.log','.tsbuildinfo'} or '.db-' in p.name or p.name=='local-demo.json':continue
    files.append(p)
with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    for p in files:z.write(p,Path('fullproof')/p.relative_to(ROOT))
    assert z.testzip() is None
print(output)
print(f'{len(files)} source files, {output.stat().st_size:,} bytes')
