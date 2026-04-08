from storage.db import connection_scope
from sqlalchemy import text

with connection_scope() as conn:
    for iid in [5, 7]:
        row = conn.execute(text("SELECT min(bar_time), max(bar_time), count(*) FROM md.bars_1m WHERE instrument_id = :iid"), {"iid": iid}).fetchone()
        print(f'IID {iid}: {row[0]} to {row[1]} (Count: {row[2]})')
