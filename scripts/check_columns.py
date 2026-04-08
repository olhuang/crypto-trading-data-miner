from storage.db import connection_scope
from sqlalchemy import text

with connection_scope() as conn:
    q = "SELECT column_name FROM information_schema.columns WHERE table_schema='md' AND table_name='bars_1m'"
    rows = conn.execute(text(q)).fetchall()
    print('md.bars_1m columns:', [r[0] for r in rows])
