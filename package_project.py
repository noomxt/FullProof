"""Create a source ZIP without credentials, installed packages or runtime data."""
from pathlib import Path
import os
import re
from zipfile import ZipFile, ZIP_DEFLATED

ROOT=Path(__file__).resolve().parent
EXCLUDED={'node_modules','.venv','dist','artifacts','cache','__pycache__','.git','.local-run'}


def source_files():
    for directory, children, files in os.walk(ROOT):
        children[:]=[name for name in children if name not in EXCLUDED and not (Path(directory)/name).is_symlink()
                     and Path(directory)/name != ROOT/'team-backend/data']
        for name in sorted(files):
            file=Path(directory)/name
            if file.is_symlink() or name in {'.DS_Store','local-demo.json','signed-proof.local.json'}:
                continue
            if name.startswith('.env') and name!='.env.example':
                continue
            if any(name.endswith(suffix) for suffix in ('.db','.db-wal','.db-shm','.sqlite3','.sqlite3-wal','.sqlite3-shm','.log','.tsbuildinfo','.pyc','.zip')):
                continue
            yield file


def main():
    target=ROOT.parent/'FullProof_Connected_Local.zip'
    files=list(source_files())
    for file in files:
        if re.search(rb'AIza[A-Za-z0-9_-]{25,}',file.read_bytes()):
            raise SystemExit('A possible API key was found; archive was not written.')
    with ZipFile(target,'w',ZIP_DEFLATED,compresslevel=9) as archive:
        for file in files:
            archive.write(file,Path('fullproof')/file.relative_to(ROOT))
    with ZipFile(target) as archive:
        if archive.testzip() is not None:
            raise SystemExit('Archive integrity check failed.')
    print(f'{target.name}: {len(files)} source files, {target.stat().st_size} bytes; no .env or runtime databases included.')


if __name__=='__main__':
    main()
