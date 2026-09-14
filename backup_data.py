"""Consistent SQLite backup; safe while the local application is running."""
import sqlite3
from pathlib import Path
from datetime import datetime
root=Path(__file__).resolve().parent
source=root/'data'/'ncs.db'
if not source.exists(): raise SystemExit('No database yet. Run app.py first.')
out=root/'backups';out.mkdir(exist_ok=True)
target=out/('ncs-'+datetime.now().strftime('%Y%m%d-%H%M%S-%f')+'.db')
a=sqlite3.connect(source.as_uri()+'?mode=ro',uri=True)
b=sqlite3.connect(target)
try: a.backup(b)
finally: b.close();a.close()
print('Backup saved:',target)
