from storage.db import connection_scope
from sqlalchemy import text

with connection_scope() as conn:
    rows = conn.execute(text("SELECT instrument_id, unified_symbol FROM ref.instruments WHERE unified_symbol = 'BTCUSDT_PERP'")).fetchall()
    for r in rows:
        print(r)
