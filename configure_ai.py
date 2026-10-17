"""Run locally: py configure_ai.py. Key input is hidden and stays server-side."""
from getpass import getpass
from pathlib import Path
import os
import re

ROOT = Path(__file__).resolve().parent


def main():
    path = ROOT / 'team-backend' / '.env'
    template = ROOT / 'team-backend' / '.env.example'
    text = path.read_text(encoding='utf-8') if path.exists() else template.read_text(encoding='utf-8')
    key = getpass('Gemini API key (hidden; paste then press Enter): ').strip()
    if not key or any(c.isspace() for c in key):
        raise SystemExit('Key is empty or contains whitespace. Nothing was saved.')
    previous = re.search(r'^GEMINI_MODEL=(.*)$', text, re.M)
    default = previous.group(1).strip() if previous and previous.group(1).strip() else 'gemini-3.8-flash'
    model = input(f'Gemini model available to your team [{default}]: ').strip() or default
    if not re.fullmatch(r'[A-Za-z0-9._/-]+', model):
        raise SystemExit('Invalid model name. Nothing was saved.')
    for name, value in {'GEMINI_API_KEY':key, 'GEMINI_MODEL':model, 'AI_PROVIDER':'gemini'}.items():
        pattern = rf'^{name}=.*$'
        text = re.sub(pattern, lambda _:f'{name}={value}', text, flags=re.M) if re.search(pattern,text,re.M) else text+f'\n{name}={value}\n'
    path.write_text(text,encoding='utf-8')
    if os.name != 'nt':
        path.chmod(0o600)
    print('Saved to team-backend/.env. Key value was not printed. Restart the backend to apply.')
    print('Run: py start_fullproof.py --live')


if __name__ == '__main__':
    main()
