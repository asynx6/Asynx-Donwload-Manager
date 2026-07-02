import json
import os
import re
from pathlib import Path

keys_used = set()
ui_dir = Path(r'C:\Users\asynx\Downloads\AsynxDL\frontend\ui')
for root, dirs, files in os.walk(ui_dir):
    for f in files:
        if f.endswith('.py'):
            text = Path(root, f).read_text(encoding='utf-8')
            keys_used.update(re.findall(r"t\([\"']([^\"']+)[\"']", text))

def flatten(d, prefix=''):
    for k, v in d.items():
        if isinstance(v, dict):
            yield from flatten(v, prefix + k + '.')
        else:
            yield prefix + k

for lang in ['en.json', 'id.json']:
    path = ui_dir / 'i18n' / lang
    data = json.load(open(path, encoding='utf-8'))
    keys_defined = set(flatten(data))
    missing = sorted(keys_used - keys_defined)
    extra = sorted(keys_defined - keys_used)
    print(f'--- {lang} ---')
    print('Missing keys:', missing if missing else 'none')
    print('Extra keys:', extra if extra else 'none')
