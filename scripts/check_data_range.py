from storage.db import connection_scope
from sqlalchemy import text

with connection_scope() as conn:
    try:
        row = conn.execute(text("SELECT min(bar_time), max(bar_time), count(*) FROM md.bars_1m WHERE unified_symbol = 'BTCUSDT_PERP'")).fetchone()
        print(f'Data range: {row[0]} to {row[1]} (Count: {row[2]})')
    except Exception as e:
        print(f"Error: {e}")
