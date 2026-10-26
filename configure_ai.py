"""Enter a Gemini key privately; preserve public chain environment settings."""
from pathlib import Path
from getpass import getpass
import re
p=Path(__file__).resolve().parent/'chain-of-investigation/.env'
key=getpass('Gemini API key (hidden): ').strip()
if not key or any(ord(c)<33 or ord(c)>126 for c in key):
    raise SystemExit('Use the actual ASCII key without spaces or quotation marks.')
text=p.read_text(encoding='utf-8-sig') if p.exists() else ''
if '\0' in text:raise SystemExit('Save .env as UTF-8 first; detected null bytes.')
line='GEMINI_API_KEY='+key
text=re.sub(r'^GEMINI_API_KEY=.*$',lambda _:line,text,flags=re.M) if re.search(r'^GEMINI_API_KEY=',text,re.M) else text+'\n'+line
p.write_text(text+'\n',encoding='utf-8')
print('Saved to chain-of-investigation/.env. Do not commit this file.')
