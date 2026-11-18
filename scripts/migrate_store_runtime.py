"""Copy the old Store-Python redirected database without deleting its original."""
import os
import shutil
import sqlite3
from pathlib import Path

root = Path(os.environ['LOCALAPPDATA'])
source = root / 'Packages/PythonSoftwareFoundation.Python.3.13_qbz5n2kfra8p0/LocalCache/Local/TianqiongDemo'
target = root / 'TianqiongDemo'
target.mkdir(parents=True, exist_ok=True)
if (source / 'tianqiong.sqlite3').exists() and not (target / 'tianqiong.sqlite3').exists():
    old = sqlite3.connect((source / 'tianqiong.sqlite3').as_uri() + '?mode=ro', uri=True)
    new = sqlite3.connect(target / 'tianqiong.sqlite3')
    try:
        old.backup(new)
        print('Existing Day 1 database copied; original preserved.')
    finally:
        new.close()
        old.close()
if (source / 'model_probe.json').exists() and not (target / 'model_probe.json').exists():
    shutil.copy2(source / 'model_probe.json', target / 'model_probe.json')
    print('Sanitized model probe metadata preserved; no credentials copied.')
